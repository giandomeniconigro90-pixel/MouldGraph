# -*- coding: utf-8 -*-
"""
tab_live.py  —  LiveMixin
Contiene _build_live_tab e tutti i metodi _live_* per la Tab Live Data.
Importato come mixin da LogAnalyzerApp in app_main.py.
"""
import os
import csv
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

import customtkinter as ctk

from colors import COLORS
from plot_canvas import InteractivePlotCanvas
from charts import _isolate_scroll

MAX_LIVE_POINTS = 500

_SPEED_MAP = {"1x": 1.0, "10x": 10.0, "60x": 60.0, "MAX": 9999.0}


class LiveMixin:
    """Mixin con tutta la logica della tab 'Live Data'."""

    # ------------------------------------------------------------------
    # BUILD TAB
    # ------------------------------------------------------------------
    def _build_live_tab(self, parent):
        # variabili di stato aggiuntive (quelle base sono in __init__)
        self._live_speed_var    = tk.StringVar(value="1x")
        self._live_filepath     = None
        self._live_col_btns     = []
        self._live_elapsed_job  = None
        self._live_start_ts     = None
        self._live_sample_idx   = 0
        self._live_alarm_defs   = []   # lista (col, lo, hi, label)
        self._live_ipc          = None

        # ---- toolbar ----
        tb = ctk.CTkFrame(parent, fg_color=COLORS["surface"],
                          corner_radius=8, height=46)
        tb.pack(fill="x", pady=(0, 4))
        tb.pack_propagate(False)

        ctk.CTkButton(
            tb, text="Apri CSV", width=86, height=28,
            fg_color=COLORS["accent"], hover_color="#5a52e0",
            text_color=COLORS["text"], font=("Segoe UI", 10),
            command=self._live_open_csv).pack(side="left", padx=(10, 4), pady=8)

        self._live_lbl = ctk.CTkLabel(
            tb, text="Nessun file",
            font=("Segoe UI", 9), text_color=COLORS["text2"])
        self._live_lbl.pack(side="left", padx=(0, 16))

        # pulsanti controllo
        self._live_btn_start = ctk.CTkButton(
            tb, text="▶  Avvia", width=86, height=28,
            fg_color="#2e7d32", hover_color="#1b5e20",
            text_color=COLORS["text"], font=("Segoe UI", 10),
            command=self._live_start)
        self._live_btn_start.pack(side="left", padx=3)

        self._live_btn_pause = ctk.CTkButton(
            tb, text="⏸  Pausa", width=86, height=28,
            fg_color="#e65100", hover_color="#bf360c",
            text_color=COLORS["text"], font=("Segoe UI", 10),
            state="disabled",
            command=self._live_pause)
        self._live_btn_pause.pack(side="left", padx=3)

        self._live_btn_stop = ctk.CTkButton(
            tb, text="■  Stop", width=86, height=28,
            fg_color="#c62828", hover_color="#b71c1c",
            text_color=COLORS["text"], font=("Segoe UI", 10),
            state="disabled",
            command=self._live_stop)
        self._live_btn_stop.pack(side="left", padx=3)

        # velocità
        ctk.CTkLabel(tb, text="Velocità:",
                     font=("Segoe UI", 9), text_color=COLORS["text2"]
                     ).pack(side="left", padx=(16, 4))
        ctk.CTkOptionMenu(
            tb, variable=self._live_speed_var,
            values=list(_SPEED_MAP.keys()),
            width=72, height=26,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"]).pack(side="left", padx=(0, 12))

        # elapsed
        self._live_elapsed_lbl = ctk.CTkLabel(
            tb, text="00:00:00",
            font=("Segoe UI", 12, "bold"), text_color=COLORS["accent2"])
        self._live_elapsed_lbl.pack(side="left", padx=8)

        # badge allarmi
        self._live_alarm_badge = ctk.CTkLabel(
            tb, text="",
            font=("Segoe UI", 10, "bold"), text_color="#fff",
            fg_color="transparent", corner_radius=6)
        self._live_alarm_badge.pack(side="right", padx=10)

        # ---- body ----
        body = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        body.pack(fill="both", expand=True)

        # sidebar sinistra: colonne
        left = ctk.CTkFrame(body, fg_color=COLORS["surface"],
                            corner_radius=8, width=160)
        left.pack(side="left", fill="y", padx=(0, 4))
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="Colonne",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(8, 4))
        self._live_col_scroll = ctk.CTkScrollableFrame(
            left, fg_color="transparent", corner_radius=0)
        self._live_col_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        _isolate_scroll(self._live_col_scroll)

        # area centrale: grafico
        center = ctk.CTkFrame(body, fg_color=COLORS["bg"])
        center.pack(side="left", fill="both", expand=True)

        self._live_ipc = InteractivePlotCanvas(center, height=4.2)
        self._live_ipc.get_frame().pack(fill="both", expand=True)

        # sidebar destra: allarmi
        right = ctk.CTkFrame(body, fg_color=COLORS["surface"],
                             corner_radius=8, width=200)
        right.pack(side="left", fill="y", padx=(4, 0))
        right.pack_propagate(False)

        ah = ctk.CTkFrame(right, fg_color="transparent")
        ah.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(ah, text="Allarmi",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["accent"]).pack(side="left")
        ctk.CTkButton(
            ah, text="+ Soglia", width=66, height=20,
            fg_color=COLORS["surface2"], hover_color=COLORS["accent"],
            text_color=COLORS["text"], font=("Segoe UI", 8),
            command=self._live_add_alarm).pack(side="right")

        self._live_alarm_scroll = ctk.CTkScrollableFrame(
            right, fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        self._live_alarm_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        _isolate_scroll(self._live_alarm_scroll)

        # log allarmi
        ctk.CTkLabel(right, text="Log allarmi",
                     font=("Segoe UI", 8, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(4, 2))
        self._live_alarm_log = ctk.CTkTextbox(
            right, height=100, font=("Courier New", 8),
            fg_color=COLORS["surface2"], text_color=COLORS["text"],
            border_width=0, wrap="none", state="disabled")
        self._live_alarm_log.pack(fill="x", padx=4, pady=(0, 6))

    # ------------------------------------------------------------------
    # OPEN CSV
    # ------------------------------------------------------------------
    def _live_open_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv *.CSV"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows_raw = list(reader)
            if not rows_raw:
                messagebox.showwarning("Attenzione", "File CSV vuoto.")
                return
            headers = [h.strip() for h in rows_raw[0]]
            data    = []
            for row in rows_raw[1:]:
                r = {}
                for h, v in zip(headers, row):
                    try:
                        r[h] = float(v.replace(",", "."))
                    except Exception:
                        r[h] = v.strip()
                data.append(r)
            self._live_filepath  = path
            self._live_headers   = headers
            self._live_rows      = data
            self._live_sample_idx = 0
            num_cols = [
                h for h in headers
                if data and isinstance(data[0].get(h), float)
            ]
            self._live_numeric_cols = num_cols
            self._live_plot_cols    = num_cols[:4]
            self._live_lbl.configure(
                text=f"{os.path.basename(path)}  |  {len(data)} campioni",
                text_color=COLORS["text"])
            self._live_rebuild_col_btns()
            self.set_status(
                f"Live CSV: {os.path.basename(path)} ({len(data)} righe, "
                f"{len(num_cols)} col numeriche)")
        except Exception as e:
            messagebox.showerror("Errore CSV Live", str(e))

    # ------------------------------------------------------------------
    # COLONNE BUTTONS
    # ------------------------------------------------------------------
    def _live_rebuild_col_btns(self):
        for w in self._live_col_btns:
            try: w.destroy()
            except Exception: pass
        self._live_col_btns.clear()
        for w in self._live_col_scroll.winfo_children():
            try: w.destroy()
            except Exception: pass

        palette = ["#6c63ff", "#00d4ff", "#52c41a", "#faad14",
                   "#f44322", "#e91e63", "#9c27b0", "#ff9800"]
        for i, col in enumerate(self._live_numeric_cols[:16]):
            color = palette[i % len(palette)]
            is_on = col in self._live_plot_cols
            v = tk.BooleanVar(value=is_on)
            if not hasattr(self, "_live_col_vars"):
                self._live_col_vars = {}
            self._live_col_vars[col] = v

            rowf = ctk.CTkFrame(self._live_col_scroll, fg_color="transparent")
            rowf.pack(fill="x", pady=1)

            dot = tk.Canvas(rowf, width=10, height=10,
                            bg=COLORS["surface"], highlightthickness=0)
            dot.create_oval(1, 1, 9, 9, fill=color, outline="")
            dot.pack(side="left", padx=(2, 2), pady=3)

            label = col if len(col) <= 11 else col[:10] + "…"

            def _make_cmd(c=col, bv=v):
                def cmd():
                    if bv.get():
                        if c not in self._live_plot_cols:
                            self._live_plot_cols.append(c)
                    else:
                        if c in self._live_plot_cols:
                            self._live_plot_cols.remove(c)
                return cmd

            ctk.CTkCheckBox(
                rowf, text=label, variable=v,
                font=("Segoe UI", 9), text_color=COLORS["text"],
                fg_color=color, hover_color=color,
                checkmark_color="#fff", border_color=COLORS["border"],
                width=16, height=16,
                command=_make_cmd(col, v)
            ).pack(side="left", fill="x", expand=True)

            self._live_col_btns.append(rowf)

    # ------------------------------------------------------------------
    # AVVIA / PAUSA / STOP
    # ------------------------------------------------------------------
    def _live_start(self):
        if not self._live_rows:
            messagebox.showwarning("Attenzione", "Carica un CSV prima.")
            return
        # reset stato
        self._live_running.set()
        self._live_paused.clear()
        self._live_alarm_count  = 0
        self._live_alarm_active = set()
        self._live_sample_idx   = 0
        self._live_queue.queue.clear()
        self._live_start_ts = datetime.now()
        # aggiorna pulsanti
        self._live_btn_start.configure(state="disabled")
        self._live_btn_pause.configure(state="normal")
        self._live_btn_stop.configure(state="normal")
        self._live_alarm_badge.configure(text="", fg_color="transparent")
        # svuota log allarmi
        self._live_alarm_log.configure(state="normal")
        self._live_alarm_log.delete("0.0", "end")
        self._live_alarm_log.configure(state="disabled")
        # avvia thread
        self._live_thread = threading.Thread(
            target=self._live_worker, daemon=True)
        self._live_thread.start()
        self._live_tick_elapsed()
        self._live_poll()

    def _live_pause(self):
        if self._live_paused.is_set():
            self._live_paused.clear()
            self._live_btn_pause.configure(text="⏸  Pausa")
        else:
            self._live_paused.set()
            self._live_btn_pause.configure(text="▶  Riprendi")

    def _live_stop(self):
        self._live_running.clear()
        self._live_paused.clear()
        self._live_btn_start.configure(state="normal")
        self._live_btn_pause.configure(state="disabled",
                                        text="⏸  Pausa")
        self._live_btn_stop.configure(state="disabled")
        if self._live_elapsed_job:
            try:
                self.after_cancel(self._live_elapsed_job)
            except Exception:
                pass
            self._live_elapsed_job = None

    # ------------------------------------------------------------------
    # WORKER THREAD
    # ------------------------------------------------------------------
    def _live_worker(self):
        speed = _SPEED_MAP.get(self._live_speed_var.get(), 1.0)
        rows  = self._live_rows
        idx   = self._live_sample_idx

        while self._live_running.is_set() and idx < len(rows):
            while self._live_paused.is_set():
                time.sleep(0.05)
                if not self._live_running.is_set():
                    return
            row = rows[idx]
            self._live_queue.put(row, block=False) if not self._live_queue.full() else None
            idx += 1
            self._live_sample_idx = idx
            delay = 0.1 / speed
            if speed >= 9000:
                delay = 0.0
            time.sleep(delay)

        if self._live_running.is_set():
            self.after(0, self._live_stop)

    # ------------------------------------------------------------------
    # POLL (main thread)
    # ------------------------------------------------------------------
    def _live_poll(self):
        if not self._live_running.is_set():
            return
        new_rows = []
        while not self._live_queue.empty():
            try:
                new_rows.append(self._live_queue.get_nowait())
            except Exception:
                break
        if new_rows:
            # accodiamo in _live_col_meta per i valori
            if not hasattr(self, "_live_buffer"):
                self._live_buffer = []
            self._live_buffer.extend(new_rows)
            # mantieni MAX_LIVE_POINTS campioni
            if len(self._live_buffer) > MAX_LIVE_POINTS:
                self._live_buffer = self._live_buffer[-MAX_LIVE_POINTS:]
            self._live_refresh_plot()
            self._live_check_alarms(new_rows)
        self.after(150, self._live_poll)

    # ------------------------------------------------------------------
    # REFRESH PLOT
    # ------------------------------------------------------------------
    def _live_refresh_plot(self):
        if not hasattr(self, "_live_buffer") or not self._live_buffer:
            return
        if not self._live_plot_cols:
            return
        buf = self._live_buffer
        # x = indice campione
        xs = list(range(len(buf)))

        palette = ["#6c63ff", "#00d4ff", "#52c41a", "#faad14",
                   "#f44322", "#e91e63", "#9c27b0", "#ff9800"]
        series = {}
        colors = {}
        for i, col in enumerate(self._live_plot_cols):
            vals = [r.get(col) for r in buf]
            series[col] = vals
            colors[col] = palette[i % len(palette)]

        try:
            self._live_ipc.plot_universal(
                xs, series,
                xtype="index",
                col_meta={},
                colors=colors,
                y2_cols=[],
                plot_type="Linea",
                smooth=False,
                show_markers=False,
                show_grid=True,
                show_legend=True,
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # ELAPSED TIMER
    # ------------------------------------------------------------------
    def _live_tick_elapsed(self):
        if not self._live_running.is_set():
            return
        if self._live_start_ts:
            delta = datetime.now() - self._live_start_ts
            s     = int(delta.total_seconds())
            h, r  = divmod(s, 3600)
            m, sc = divmod(r, 60)
            self._live_elapsed_lbl.configure(
                text=f"{h:02d}:{m:02d}:{sc:02d}")
        self._live_elapsed_job = self.after(1000, self._live_tick_elapsed)

    # ------------------------------------------------------------------
    # ALLARMI
    # ------------------------------------------------------------------
    def _live_add_alarm(self):
        if not self._live_numeric_cols:
            messagebox.showwarning("Attenzione", "Carica prima un CSV.")
            return
        win = tk.Toplevel(self)
        win.title("Aggiungi Allarme")
        win.configure(bg=COLORS["surface"])
        win.geometry("300x220")
        win.resizable(False, False)

        ctk.CTkLabel(win, text="Colonna",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]
                     ).pack(anchor="w", padx=20, pady=(14, 2))
        col_var = tk.StringVar(value=self._live_numeric_cols[0])
        ctk.CTkOptionMenu(
            win, variable=col_var,
            values=self._live_numeric_cols,
            width=200, fg_color=COLORS["surface2"],
            button_color=COLORS["accent"], text_color=COLORS["text"]
        ).pack(anchor="w", padx=20)

        ctk.CTkLabel(win, text="Soglia Lo (vuoto = nessuna)",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]
                     ).pack(anchor="w", padx=20, pady=(10, 2))
        lo_entry = ctk.CTkEntry(
            win, placeholder_text="es. 100",
            fg_color=COLORS["surface2"], border_color=COLORS["border"],
            text_color=COLORS["text"], height=28)
        lo_entry.pack(anchor="w", padx=20, fill="x", pady=(0, 4))

        ctk.CTkLabel(win, text="Soglia Hi (vuoto = nessuna)",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]
                     ).pack(anchor="w", padx=20, pady=(0, 2))
        hi_entry = ctk.CTkEntry(
            win, placeholder_text="es. 200",
            fg_color=COLORS["surface2"], border_color=COLORS["border"],
            text_color=COLORS["text"], height=28)
        hi_entry.pack(anchor="w", padx=20, fill="x", pady=(0, 10))

        def _confirm():
            col = col_var.get()
            try: lo = float(lo_entry.get()) if lo_entry.get().strip() else None
            except Exception: lo = None
            try: hi = float(hi_entry.get()) if hi_entry.get().strip() else None
            except Exception: hi = None
            if lo is None and hi is None:
                messagebox.showwarning("Attenzione", "Inserisci almeno una soglia.")
                return
            self._live_alarm_rules.append({"col": col, "lo": lo, "hi": hi})
            self._live_render_alarm_rules()
            win.destroy()

        ctk.CTkButton(
            win, text="Aggiungi", width=120, height=30,
            fg_color=COLORS["accent"], hover_color="#5a52e0",
            text_color=COLORS["text"], command=_confirm
        ).pack(pady=4)

    def _live_render_alarm_rules(self):
        for w in self._live_alarm_scroll.winfo_children():
            try: w.destroy()
            except Exception: pass
        for i, rule in enumerate(self._live_alarm_rules):
            card = ctk.CTkFrame(self._live_alarm_scroll,
                                fg_color=COLORS["surface2"], corner_radius=5)
            card.pack(fill="x", padx=2, pady=2)
            lbl = f"{rule['col']}"
            if rule.get("lo") is not None:
                lbl += f"  Lo={rule['lo']}"
            if rule.get("hi") is not None:
                lbl += f"  Hi={rule['hi']}"
            ctk.CTkLabel(
                card, text=lbl,
                font=("Segoe UI", 8), text_color=COLORS["text"]
            ).pack(side="left", padx=6, pady=4)
            idx = i
            ctk.CTkButton(
                card, text="✕", width=20, height=20,
                fg_color="transparent", hover_color=COLORS["error"],
                text_color=COLORS["text2"], font=("Segoe UI", 9),
                command=lambda ii=idx: self._live_remove_alarm(ii)
            ).pack(side="right", padx=4)

    def _live_remove_alarm(self, idx):
        if 0 <= idx < len(self._live_alarm_rules):
            self._live_alarm_rules.pop(idx)
        self._live_render_alarm_rules()

    def _live_check_alarms(self, new_rows):
        if not self._live_alarm_rules:
            return
        now_str = datetime.now().strftime("%H:%M:%S")
        fired   = []
        for row in new_rows:
            for rule in self._live_alarm_rules:
                col = rule["col"]
                val = row.get(col)
                if not isinstance(val, (int, float)):
                    continue
                lo  = rule.get("lo")
                hi  = rule.get("hi")
                if (lo is not None and val < lo) or (hi is not None and val > hi):
                    key = (col, lo, hi)
                    if key not in self._live_alarm_active:
                        self._live_alarm_active.add(key)
                        self._live_alarm_count += 1
                        fired.append(f"[{now_str}] ALLARME {col}={val:.2f}")

        if fired:
            self._live_alarm_badge.configure(
                text=f"🔴 {self._live_alarm_count} ALARM",
                fg_color="#c62828")
            self._live_alarm_log.configure(state="normal")
            for line in fired:
                self._live_alarm_log.insert("end", line + "\n")
            self._live_alarm_log.see("end")
            self._live_alarm_log.configure(state="disabled")
