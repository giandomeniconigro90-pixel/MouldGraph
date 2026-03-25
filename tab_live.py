# -*- coding: utf-8 -*-
"""
tab_live.py  —  LiveMixin
Contiene _build_live_tab e tutti i metodi _live_* estratti da app_main.py.
Importato come mixin da LogAnalyzerApp in app_main.py.
"""
import os
import time
import csv
import threading
import queue as _queue
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

import customtkinter as ctk
import matplotlib.pyplot as plt

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from colors import COLORS
from plot_canvas import InteractivePlotCanvas
from charts import _isolate_scroll
from csv_parser import parse_universal_csv, _uc_build_series

MAX_LIVE_POINTS = 500
_UC_SERIES_PALETTE = [
    "#e5672c", "#3f51b5", "#29b6f6", "#66bb6a",
    "#9c27b0", "#ff9800", "#e7b73b", "#607d8b",
    "#f44322", "#00bcd4", "#8bc34a", "#ff5722",
]


class LiveMixin:
    """Mixin con tutta la logica della tab 'Live Data'."""

    # ------------------------------------------------------------------
    # BUILD TAB
    # ------------------------------------------------------------------
    def _build_live_tab(self, parent):
        """Tab per monitoraggio live (seriale reale o simulazione CSV)."""
        # ---- toolbar wrapper ----
        toolbar_wrap = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        toolbar_wrap.pack(fill="x", side="top", padx=6, pady=(4, 2))

        # riga 1: sorgente / CSV / porte
        row1 = ctk.CTkFrame(toolbar_wrap, fg_color=COLORS["surface"], corner_radius=8)
        row1.pack(fill="x", pady=(0, 3))
        ctk.CTkLabel(row1, text="Sorgente",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(side="left", padx=10, pady=8)
        self._live_src_var = ctk.StringVar(value="Simulazione CSV")
        srcopts = ["Simulazione CSV"]
        if SERIAL_AVAILABLE:
            srcopts.append("Seriale")
        self._live_src_menu = ctk.CTkOptionMenu(
            row1, variable=self._live_src_var, values=srcopts,
            width=150, fg_color=COLORS["surface2"],
            button_color=COLORS["accent"], text_color=COLORS["text"],
            command=self._live_on_source_change)
        self._live_src_menu.pack(side="left", padx=6, pady=8)

        self._live_csv_path = None
        ctk.CTkButton(row1, text="CSV", width=80, height=26,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 10),
                      command=self._live_open_csv).pack(side="left", padx=4, pady=8)
        self._live_csv_lbl = ctk.CTkLabel(
            row1, text="Nessun file",
            font=("Segoe UI", 9), text_color=COLORS["text2"])
        self._live_csv_lbl.pack(side="left", padx=4)

        ctk.CTkButton(row1, text="↻ Porte", width=80, height=26,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 9),
                      command=self._live_refresh_ports).pack(side="right", padx=8, pady=8)

        # porta seriale (nascosta di default)
        self._live_port_lbl = ctk.CTkLabel(
            row1, text="Porta", font=("Segoe UI", 10, "bold"),
            text_color=COLORS["text2"])
        self._live_port_var = ctk.StringVar(value="")
        self._live_port_menu = ctk.CTkOptionMenu(
            row1, variable=self._live_port_var, values=[""],
            width=120, fg_color=COLORS["surface2"],
            button_color=COLORS["accent"], text_color=COLORS["text"])
        self._live_baud_lbl = ctk.CTkLabel(
            row1, text="Baud", font=("Segoe UI", 10, "bold"),
            text_color=COLORS["text2"])
        self._live_baud_var = ctk.StringVar(value="9600")
        self._live_baud_entry = ctk.CTkEntry(
            row1, textvariable=self._live_baud_var,
            width=65, fg_color=COLORS["surface2"], text_color=COLORS["text"])
        self._live_refresh_btn = ctk.CTkButton(
            row1, text="↻", width=28, height=26,
            fg_color=COLORS["surface2"], hover_color=COLORS["border"],
            text_color=COLORS["text"], command=self._live_refresh_ports)
        # La riga seriale viene mostrata/nascosta da _live_on_source_change

        # riga 2: controlli play/pause/stop + parametri
        row3 = ctk.CTkFrame(toolbar_wrap, fg_color=COLORS["surface"], corner_radius=8)
        row3.pack(fill="x", pady=(0, 3))
        RBTN = dict(width=44, height=44, corner_radius=22,
                    font=("Segoe UI", 18), text_color=COLORS["text"])
        self._live_start_btn = ctk.CTkButton(
            row3, text="▶", fg_color=COLORS["info"], hover_color="#3a9a10",
            **RBTN, command=self._live_start)
        self._live_start_btn.pack(side="left", padx=(8, 4), pady=6)
        self._live_stop_btn = ctk.CTkButton(
            row3, text="■", fg_color=COLORS["error"], hover_color="#cc2a2c",
            **RBTN, state="disabled", command=self._live_stop)
        self._live_stop_btn.pack(side="left", padx=4, pady=6)
        self._live_pause_btn = ctk.CTkButton(
            row3, text="⏸", fg_color=COLORS["warn"], hover_color="#c87d00",
            **RBTN, state="disabled", command=self._live_toggle_pause)
        self._live_pause_btn.pack(side="left", padx=4, pady=6)

        SBTN = dict(height=28, font=("Segoe UI", 9),
                    text_color=COLORS["text"],
                    fg_color=COLORS["surface2"], hover_color=COLORS["border"])
        ctk.CTkButton(row3, text="Pulisci",  width=65, **SBTN,
                      command=self._live_clear).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="↓ CSV",    width=60, **SBTN,
                      command=self._live_export_csv).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="↓ PNG",    width=60, **SBTN,
                      command=self._live_export_png).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="↓ PDF",    width=60, **SBTN,
                      command=self._live_export_pdf).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="↺",        width=46, **SBTN,
                      command=self._live_reset_cursors).pack(side="left", padx=3, pady=7)
        self._live_multi_btn = ctk.CTkButton(
            row3, text="Multi", width=72, height=28,
            fg_color=COLORS["surface2"], hover_color=COLORS["accent"],
            text_color=COLORS["text"], font=("Segoe UI", 9),
            command=self._live_toggle_multi)
        self._live_multi_btn.pack(side="left", padx=3, pady=7)

        LBL = dict(font=("Segoe UI", 9), text_color=COLORS["text2"])
        ctk.CTkLabel(row3, text="Max pt", **LBL).pack(side="left", padx=(2, 2))
        self._live_max_pts_var = ctk.StringVar(value="500")
        ctk.CTkEntry(row3, textvariable=self._live_max_pts_var,
                     width=48, fg_color=COLORS["surface2"],
                     text_color=COLORS["text"], height=26).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(row3, text="Vel", **LBL).pack(side="left", padx=(4, 2))
        self._live_speed_var = ctk.StringVar(value="1x")
        self._live_speed_snapshot = "1x"

        def _on_speed_change(val):
            self._live_speed_snapshot = val

        ctk.CTkOptionMenu(
            row3, variable=self._live_speed_var,
            values=["0.25x", "0.5x", "1x", "2x", "5x", "10x",
                    "15x", "20x", "30x", "60x", "100x", "MAX"],
            width=75, height=26, fg_color=COLORS["surface2"],
            button_color=COLORS["accent"], text_color=COLORS["text"],
            command=_on_speed_change).pack(side="left", padx=(0, 6))

        self._live_interp_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row3, text="Interp", variable=self._live_interp_var,
                        font=("Segoe UI", 9), text_color=COLORS["text2"],
                        fg_color=COLORS["accent"], hover_color="#5a52e0",
                        checkmark_color=COLORS["text"],
                        width=16, height=16).pack(side="left", padx=(0, 8))
        self._live_show_pts_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row3, text="Punti", variable=self._live_show_pts_var,
                        font=("Segoe UI", 9), text_color=COLORS["text2"],
                        fg_color=COLORS["accent"], hover_color="#5a52e0",
                        checkmark_color=COLORS["text"],
                        width=16, height=16,
                        command=self._live_toggle_markers).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row3, text="Rate", **LBL).pack(side="left", padx=(4, 2))
        self._live_rate_var = ctk.StringVar(value="500")
        ctk.CTkEntry(row3, textvariable=self._live_rate_var,
                     width=52, fg_color=COLORS["surface2"],
                     text_color=COLORS["text"], height=26).pack(side="left")
        ctk.CTkLabel(row3, text="ms", **LBL).pack(side="left", padx=(2, 8))

        self._live_status_lbl = ctk.CTkLabel(
            row3, text="In attesa",
            font=("Segoe UI", 10), text_color=COLORS["text2"])
        self._live_status_lbl.pack(side="left", padx=8)

        # riga contatori
        cnt_row = ctk.CTkFrame(toolbar_wrap, fg_color=COLORS["surface"], corner_radius=8)
        cnt_row.pack(fill="x", pady=(0, 3))
        self._live_cnt_lbl = ctk.CTkLabel(
            cnt_row, text="Campioni: 0  In coda: 0",
            font=("Courier New", 10), text_color=COLORS["accent2"])
        self._live_cnt_lbl.pack(side="left", padx=14, pady=5)
        self._live_alarm_badge = ctk.CTkLabel(
            cnt_row, text="",
            font=("Segoe UI", 10, "bold"), text_color=COLORS["error"])
        self._live_alarm_badge.pack(side="left", padx=10, pady=5)

        # ---- body: sidebar Colonne Y + area grafico + pannello allarmi ----
        body = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        # sidebar Colonne Y
        col_sidebar = ctk.CTkFrame(body, fg_color=COLORS["surface"],
                                   corner_radius=8, width=145)
        col_sidebar.pack(side="left", fill="y", padx=(0, 4), pady=0)
        col_sidebar.pack_propagate(False)
        ctk.CTkLabel(col_sidebar, text="Colonne Y",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(8, 2))
        btn_row = ctk.CTkFrame(col_sidebar, fg_color="transparent")
        btn_row.pack(anchor="w", padx=6, pady=(0, 4))
        ctk.CTkButton(btn_row, text="☑", width=36, height=18,
                      fg_color=COLORS["surface2"], hover_color=COLORS["accent"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      corner_radius=4,
                      command=self._live_sel_all).pack(side="left", padx=(0, 2))
        ctk.CTkButton(btn_row, text="☒", width=36, height=18,
                      fg_color=COLORS["surface2"], hover_color=COLORS["error"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      corner_radius=4,
                      command=self._live_sel_none).pack(side="left")
        self._live_col_btns = []
        self._live_col_scroll = ctk.CTkScrollableFrame(
            col_sidebar, fg_color="transparent",
            orientation="vertical", corner_radius=0)
        self._live_col_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        _isolate_scroll(self._live_col_scroll)

        # area centrale: grafico + log
        center = ctk.CTkFrame(body, fg_color=COLORS["bg"])
        center.pack(side="left", fill="both", expand=True)

        self._live_ipc = InteractivePlotCanvas(center, height=3.4)
        self._live_ipc.get_frame().pack(fill="both", expand=True)

        log_frame = ctk.CTkFrame(center, fg_color=COLORS["surface"],
                                  corner_radius=8, height=100)
        log_frame.pack(fill="x", pady=(4, 0))
        log_frame.pack_propagate(False)
        self._live_log_box = ctk.CTkTextbox(
            log_frame, font=("Courier New", 9),
            fg_color=COLORS["surface"], text_color=COLORS["text2"],
            border_width=0, state="disabled")
        self._live_log_box.pack(fill="both", expand=True, padx=4, pady=4)

        # pannello destra: allarmi
        alarm_panel = ctk.CTkFrame(body, fg_color=COLORS["surface"],
                                    corner_radius=8, width=200)
        alarm_panel.pack(side="left", fill="y", padx=(4, 0), pady=0)
        alarm_panel.pack_propagate(False)
        alarm_scroll = ctk.CTkScrollableFrame(
            alarm_panel, fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        alarm_scroll.pack(fill="both", expand=True)
        ctk.CTkLabel(alarm_scroll, text="ALLARMI",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=8, pady=(8, 2))
        ctk.CTkButton(alarm_scroll, text="+ Soglia", width=90, height=24,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 9),
                      command=self._live_add_alarm).pack(anchor="w", padx=8, pady=(0, 6))
        ctk.CTkButton(alarm_scroll, text="Azzera", width=70, height=22,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      command=self._live_clear_alarms).pack(anchor="w", padx=8, pady=(0, 8))
        self._live_alarm_cards_frame = ctk.CTkFrame(
            alarm_scroll, fg_color="transparent")
        self._live_alarm_cards_frame.pack(fill="x")

    # ------------------------------------------------------------------
    # SOURCE CHANGE
    # ------------------------------------------------------------------
    def _live_on_source_change(self, val):
        is_serial = (val == "Seriale")
        widgets_serial = [
            self._live_port_lbl, self._live_port_menu,
            self._live_baud_lbl, self._live_baud_entry, self._live_refresh_btn
        ]
        for w in widgets_serial:
            if is_serial:
                w.pack(side="left", padx=4, pady=8)
            else:
                w.pack_forget()

    # ------------------------------------------------------------------
    # OPEN CSV
    # ------------------------------------------------------------------
    def _live_open_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv *.CSV"), ("All files", "*.*")])
        if not path:
            return
        self._live_csv_path = path
        self._live_csv_lbl.configure(
            text=os.path.basename(path), text_color=COLORS["text"])
        # Legge colonne per popolare la sidebar
        try:
            rows, headers, _, _, col_meta = parse_universal_csv(path)
            self._live_headers      = headers
            self._live_col_meta     = col_meta
            self._live_numeric_cols = [
                h for h in headers
                if col_meta.get(h, {}).get("coltype") == "numeric"
            ]
            self._live_plot_cols    = list(self._live_numeric_cols[:8])
            self._live_rebuild_col_buttons()
            self.set_status(f"Live CSV pronto: {os.path.basename(path)} "
                            f"({len(rows)} righe, "
                            f"{len(self._live_numeric_cols)} colonne numeriche)")
        except Exception as e:
            messagebox.showerror("Errore CSV Live", str(e))

    # ------------------------------------------------------------------
    # PORTA SERIALE
    # ------------------------------------------------------------------
    def _live_refresh_ports(self):
        if not SERIAL_AVAILABLE:
            return
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self._live_port_menu.configure(values=ports if ports else [""])
        if ports:
            self._live_port_var.set(ports[0])

    # ------------------------------------------------------------------
    # SIDEBAR COLONNE
    # ------------------------------------------------------------------
    def _live_rebuild_col_buttons(self):
        for w in self._live_col_btns:
            try: w.destroy()
            except Exception: pass
        self._live_col_btns.clear()
        for w in self._live_col_scroll.winfo_children():
            try: w.destroy()
            except Exception: pass
        palette = list(_UC_SERIES_PALETTE)
        for i, col in enumerate(self._live_numeric_cols):
            color  = palette[i % len(palette)]
            is_sel = col in self._live_plot_cols
            var    = tk.BooleanVar(value=is_sel)
            rowf   = ctk.CTkFrame(self._live_col_scroll, fg_color="transparent")
            rowf.pack(fill="x", pady=1)
            dot = tk.Canvas(rowf, width=12, height=12,
                            bg=COLORS["surface"], highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=color, outline="")
            dot.pack(side="left", padx=(2, 2), pady=4)
            label = col if len(col) <= 10 else col[:9] + "…"

            def _make_cmd(c=col, v=var):
                def cmd():
                    if v.get():
                        if c not in self._live_plot_cols:
                            self._live_plot_cols.append(c)
                    else:
                        if len(self._live_plot_cols) > 1 and c in self._live_plot_cols:
                            self._live_plot_cols.remove(c)
                        else:
                            v.set(True)  # mantieni almeno una
                return cmd

            ctk.CTkCheckBox(
                rowf, text=label, variable=var,
                font=("Segoe UI", 9), text_color=COLORS["text"],
                fg_color=color, hover_color=color,
                checkmark_color="#fff", border_color=COLORS["border"],
                width=16, height=16,
                command=_make_cmd(col, var)
            ).pack(side="left", fill="x", expand=True)
            self._live_col_btns.append(rowf)

    def _live_sel_all(self):
        self._live_plot_cols = list(self._live_numeric_cols)
        self._live_rebuild_col_buttons()

    def _live_sel_none(self):
        if self._live_numeric_cols:
            self._live_plot_cols = [self._live_numeric_cols[0]]
        self._live_rebuild_col_buttons()

    def _live_toggle_col(self, col):
        if col in self._live_plot_cols:
            if len(self._live_plot_cols) > 1:
                self._live_plot_cols.remove(col)
        else:
            self._live_plot_cols.append(col)
        self._live_rebuild_col_buttons()

    # ------------------------------------------------------------------
    # START / STOP / PAUSE
    # ------------------------------------------------------------------
    def _live_start(self):
        if self._live_running.is_set():
            return
        src = self._live_src_var.get()
        # Reset completo ad ogni avvio
        self._live_rows.clear()
        self._live_ipc.clear()
        self._live_ipc.needs_full_redraw = True
        try:
            while True:
                self._live_queue.get_nowait()
        except Exception:
            pass
        self._live_alarm_active.clear()
        self._live_alarm_count  = 0
        self._live_alarm_badge.configure(text="")

        if src == "Simulazione CSV":
            if not self._live_csv_path:
                messagebox.showwarning("Attenzione", "Seleziona prima un file CSV.")
                return
            self._live_running.set()
            self._live_paused.clear()
            self._live_thread = threading.Thread(
                target=self._live_sim_thread, daemon=True)
            self._live_thread.start()
        else:
            # Seriale
            port = self._live_port_var.get()
            try:
                baud = int(self._live_baud_var.get())
            except Exception:
                baud = 9600
            if not port:
                messagebox.showwarning("Attenzione", "Seleziona una porta seriale.")
                return
            self._live_running.set()
            self._live_paused.clear()
            self._live_thread = threading.Thread(
                target=self._live_serial_thread,
                args=(port, baud), daemon=True)
            self._live_thread.start()

        self._live_start_btn.configure(state="disabled")
        self._live_stop_btn.configure(state="normal")
        self._live_pause_btn.configure(state="normal")
        self._live_status_lbl.configure(
            text="▶ In corso", text_color=COLORS["info"])
        self._live_dropped = 0
        self.after(500, self._live_poll)

    def _live_stop(self):
        self._live_running.clear()
        self._live_paused.clear()
        self._live_stop_interp_timer()
        self._live_start_btn.configure(state="normal")
        self._live_stop_btn.configure(state="disabled")
        self._live_pause_btn.configure(state="disabled")
        self._live_ipc.needs_full_redraw = True
        self._live_status_lbl.configure(
            text="■ Fermato", text_color=COLORS["error"])
        if self._live_rows:
            self.after(50, self._live_refresh_plot)

    def _live_toggle_pause(self):
        if not self._live_running.is_set():
            return
        if self._live_paused.is_set():
            self._live_paused.clear()
            self._live_pause_btn.configure(text="⏸")
            self._live_status_lbl.configure(
                text="▶ In corso", text_color=COLORS["info"])
        else:
            self._live_paused.set()
            self._live_pause_btn.configure(text="▶")
            self._live_status_lbl.configure(
                text="⏸ In pausa", text_color=COLORS["warn"])

    # ------------------------------------------------------------------
    # THREAD SIMULAZIONE CSV
    # ------------------------------------------------------------------
    def _live_sim_thread(self):
        try:
            rows, headers, _, _, col_meta = parse_universal_csv(self._live_csv_path)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Errore CSV", str(e)))
            self._live_running.clear()
            return

        numeric_cols = [
            h for h in headers
            if col_meta.get(h, {}).get("coltype") == "numeric"
        ]
        datetime_cols = [
            h for h in headers
            if col_meta.get(h, {}).get("coltype") == "datetime"
        ]
        self.after(0, lambda: self._live_log_append(
            f"Colonne numeriche: {numeric_cols}"))
        self.after(0, lambda: self._live_log_append(
            f"Colonne datetime : {datetime_cols}"))

        # Aggiorna col_meta e plot_cols
        for k, v in col_meta.items():
            if col_meta.get(k, {}).get("coltype") == "numeric" \
                    and k not in self._live_col_meta:
                self._live_col_meta[k] = v
            if k not in self._live_numeric_cols:
                self._live_numeric_cols.append(k)
            if len(self._live_plot_cols) < 8 and k not in self._live_plot_cols:
                self._live_plot_cols.append(k)

        # Rileva colonna tempo
        _TIMENAMES = {
            "time", "tempo", "t", "sec", "seconds", "s",
            "zeit", "temps", "elapsed", "elapsed_s", "ts", "ticks", "sample"
        }
        has_embedded_ts = bool(datetime_cols)
        xcol_dt  = datetime_cols[0] if datetime_cols else None
        xcol_num = None
        if not has_embedded_ts:
            for h in headers:
                if h.lower().rstrip("_") in _TIMENAMES:
                    sample = [rows[i].get(h) for i in range(min(5, len(rows)))]
                    samples = [str(v) for v in sample if v is not None and str(v).strip()]
                    try:
                        if all(float(v) for v in samples):
                            xcol_num = h
                            break
                    except Exception:
                        pass

        use_datetime = has_embedded_ts or xcol_dt is not None
        use_num_time = not use_datetime and xcol_num is not None
        self.after(0, lambda: self._live_log_append(
            f"Tempo: datetime={xcol_dt}" if use_datetime else
            f"Tempo: numerico={xcol_num}" if use_num_time else "Tempo: indice fisso"))

        prev_dt  = None
        prev_num = None

        def _wait_if_paused():
            while self._live_paused.is_set() and self._live_running.is_set():
                time.sleep(0.05)

        sf_map = {
            "0.25x": 4.0, "0.5x": 2.0, "1x": 1.0, "2x": 0.5,
            "5x": 0.2, "10x": 0.1, "15x": 1/15, "20x": 0.05,
            "30x": 1/30, "60x": 1/60, "100x": 0.01, "MAX": None,
        }

        for i, r in enumerate(rows):
            if not self._live_running.is_set():
                break
            _wait_if_paused()
            if not self._live_running.is_set():
                break

            rowout = {}
            for col in numeric_cols:
                v = r.get(col)
                if isinstance(v, float):
                    rowout[col] = v
                else:
                    try:
                        rowout[col] = float(str(v).replace(",", "."))
                    except Exception:
                        rowout[col] = None

            sf = sf_map.get(self._live_speed_snapshot)

            if has_embedded_ts:
                ts = r.get("_ts")
                if ts:
                    rowout["_ts"] = ts
                    if prev_dt is not None and sf is not None:
                        delta = (ts - prev_dt).total_seconds()
                        if delta > 0:
                            time.sleep(max(0.01, delta * sf))
                    prev_dt = ts
                else:
                    if sf is not None:
                        time.sleep(0.1 * sf)
            elif use_datetime:
                ts = r.get(xcol_dt)
                if ts:
                    rowout["_ts"] = ts
                    if prev_dt is not None and sf is not None:
                        delta = (ts - prev_dt).total_seconds()
                        time.sleep(max(0.01, delta * sf))
                    prev_dt = ts
                else:
                    if sf is not None:
                        time.sleep(0.1 * sf)
            elif use_num_time:
                try:
                    t_now = float(str(r.get(xcol_num, "")).replace(",", "."))
                    rowout["_sim_t"] = t_now
                    if prev_num is not None and sf is not None:
                        delta = t_now - prev_num
                        if delta > 0:
                            time.sleep(max(0.01, delta * sf))
                    prev_num = t_now
                except Exception:
                    if sf is not None:
                        time.sleep(0.1 * sf)
            else:
                rowout["_sim_i"] = i
                if sf is not None:
                    time.sleep(max(0.01, 1.0 * sf))

            try:
                self._live_queue.put_nowait(rowout)
            except _queue.Full:
                self._live_dropped = getattr(self, "_live_dropped", 0) + 1

        self._live_running.clear()
        self.after(0, lambda: self._live_status_lbl.configure(
            text="✓ Completato", text_color=COLORS["info"]))
        self.after(0, lambda: self._live_start_btn.configure(state="normal"))
        self.after(0, lambda: self._live_stop_btn.configure(state="disabled"))
        self.after(0, lambda: self._live_pause_btn.configure(state="disabled"))

    # ------------------------------------------------------------------
    # THREAD SERIALE
    # ------------------------------------------------------------------
    def _live_serial_thread(self, port, baud):
        try:
            ser = serial.Serial(port, baud, timeout=1)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Seriale", str(e)))
            self._live_running.clear()
            return
        self.after(0, lambda: self._live_log_append(f"Seriale aperta: {port} @ {baud}"))
        while self._live_running.is_set():
            while self._live_paused.is_set() and self._live_running.is_set():
                time.sleep(0.05)
            try:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if not self._live_headers:
                    self._live_headers = line.split(",")
                    self._live_numeric_cols = self._live_headers
                    self._live_plot_cols    = self._live_headers[:8]
                    self.after(0, self._live_rebuild_col_buttons)
                    continue
                vals = line.split(",")
                rowout = {}
                for h, v in zip(self._live_headers, vals):
                    try:
                        rowout[h] = float(v.strip())
                    except Exception:
                        rowout[h] = v.strip()
                try:
                    self._live_queue.put_nowait(rowout)
                except _queue.Full:
                    self._live_dropped = getattr(self, "_live_dropped", 0) + 1
            except Exception:
                pass
        try:
            ser.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # POLL (UI thread)
    # ------------------------------------------------------------------
    def _live_poll(self):
        if not self._live_running.is_set() and self._live_queue.empty():
            return
        # Drain queue
        count = 0
        while not self._live_queue.empty() and count < 200:
            try:
                row = self._live_queue.get_nowait()
                self._live_rows.append(row)
                # Aggiorna col_meta dinamicamente
                last_row = row
                for k, v in last_row.items():
                    if k.startswith("_"):
                        continue
                    if isinstance(v, (int, float)) and k not in self._live_col_meta:
                        unit, label, coltype = "", k, "numeric"
                        self._live_col_meta[k] = {
                            "unit": unit, "label": label, "coltype": coltype}
                        if k not in self._live_numeric_cols:
                            self._live_numeric_cols.append(k)
                        if len(self._live_plot_cols) < 8 \
                                and k not in self._live_plot_cols:
                            self._live_plot_cols.append(k)
                count += 1
            except _queue.Empty:
                break

        # Aggiorna contatori
        n_rows = len(self._live_rows)
        n_q    = self._live_queue.qsize()
        dropped = getattr(self, "_live_dropped", 0)
        cnt_txt = f"Campioni: {n_rows}  In coda: {n_q}"
        if dropped:
            cnt_txt += f"  Scartati: {dropped}"
        self._live_cnt_lbl.configure(text=cnt_txt)

        # Allarmi
        if count > 0 and self._live_rows:
            self._live_check_alarms(self._live_rows[-1])

        # Interpolazione
        interp_on = (
            getattr(self, "_live_interp_var", None) is not None
            and self._live_interp_var.get()
            and self._live_interp_job is not None
        )
        if not interp_on:
            self._live_refresh_plot()

        try:
            ms = max(100, int(self._live_rate_var.get()))
        except Exception:
            ms = 500

        if self._live_running.is_set() or not self._live_queue.empty():
            self.after(ms, self._live_poll)

    # ------------------------------------------------------------------
    # REFRESH PLOT
    # ------------------------------------------------------------------
    def _live_refresh_plot(self):
        if not self._live_rows or not self._live_plot_cols:
            return
        try:
            max_pts = int(self._live_max_pts_var.get())
            if max_pts < 10:
                max_pts = 10
        except Exception:
            max_pts = MAX_LIVE_POINTS

        rows = self._live_rows[-max_pts:]
        xcol = None
        for r in rows[:1]:
            if "_ts"    in r: xcol = "_ts"
            elif "_sim_t" in r: xcol = "_sim_t"

        xsraw = []
        for i, r in enumerate(rows):
            if xcol == "_ts":    xsraw.append(r.get("_ts"))
            elif xcol == "_sim_t": xsraw.append(r.get("_sim_t", i))
            else:                  xsraw.append(i)

        xtype  = "datetime" if xcol == "_ts" else "index"
        series = {}
        for col in self._live_plot_cols:
            vals = []
            for r in rows:
                v = r.get(col)
                vals.append(float(v) if isinstance(v, (int, float)) else None)
            series[col] = vals

        palette = list(_UC_SERIES_PALETTE)
        colors  = {
            col: palette[i % len(palette)]
            for i, col in enumerate(self._live_numeric_cols)
        }

        # Aggiorna allarmi se cambiate
        current_rules = getattr(self, "_live_alarm_rules", [])
        if current_rules != getattr(self, "_live_last_rules_snapshot", None):
            self._live_last_rules_snapshot = list(current_rules)
            self._live_ipc.ranges = current_rules
            self._live_ipc.needs_full_redraw = True

        self._live_ipc.update_live(
            xsraw, series, xtype, self._live_col_meta, colors=colors)

    # ------------------------------------------------------------------
    # ALLARMI
    # ------------------------------------------------------------------
    def _live_add_alarm(self):
        import tkinter.simpledialog as sd
        if not self._live_numeric_cols:
            messagebox.showwarning("Attenzione", "Nessuna colonna numerica disponibile.")
            return
        win = tk.Toplevel(self)
        win.title("Aggiungi soglia allarme")
        win.configure(bg=COLORS["surface"])
        win.resizable(False, False)
        win.geometry("320x220")

        ctk.CTkLabel(win, text="Colonna", font=("Segoe UI", 11),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=20, pady=(16, 2))
        col_var = ctk.StringVar(value=self._live_numeric_cols[0])
        ctk.CTkOptionMenu(win, variable=col_var,
                          values=self._live_numeric_cols, width=200,
                          fg_color=COLORS["surface2"],
                          button_color=COLORS["accent"],
                          text_color=COLORS["text"]).pack(anchor="w", padx=20)

        fr = ctk.CTkFrame(win, fg_color="transparent")
        fr.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(fr, text="Lo (min)", font=("Segoe UI", 10),
                     text_color=COLORS["text2"]).pack(side="left")
        lo_var = ctk.StringVar(value="")
        ctk.CTkEntry(fr, textvariable=lo_var, width=80,
                     fg_color=COLORS["surface2"],
                     text_color=COLORS["text"], height=26).pack(side="left", padx=8)
        ctk.CTkLabel(fr, text="Hi (max)", font=("Segoe UI", 10),
                     text_color=COLORS["text2"]).pack(side="left")
        hi_var = ctk.StringVar(value="")
        ctk.CTkEntry(fr, textvariable=hi_var, width=80,
                     fg_color=COLORS["surface2"],
                     text_color=COLORS["text"], height=26).pack(side="left", padx=8)

        def _confirm():
            col = col_var.get()
            lo  = None
            hi  = None
            try:
                if lo_var.get().strip():
                    lo = float(lo_var.get().strip().replace(",", "."))
            except Exception:
                pass
            try:
                if hi_var.get().strip():
                    hi = float(hi_var.get().strip().replace(",", "."))
            except Exception:
                pass
            if lo is None and hi is None:
                messagebox.showwarning("Attenzione",
                                       "Inserisci almeno un valore Lo o Hi.")
                return
            rule = {"col": col, "lo": lo, "hi": hi,
                    "label": col, "active": True}
            self._live_alarm_rules.append(rule)
            self._live_rebuild_alarm_cards()
            win.destroy()

        ctk.CTkButton(win, text="Aggiungi", width=120, height=30,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"],
                      command=_confirm).pack(pady=12)

    def _live_clear_alarms(self):
        self._live_alarm_rules  = []
        self._live_alarm_count  = 0
        self._live_alarm_active = set()
        self._live_alarm_badge.configure(text="")
        self._live_rebuild_alarm_cards()

    def _live_rebuild_alarm_cards(self):
        for w in self._live_alarm_cards_frame.winfo_children():
            try: w.destroy()
            except Exception: pass
        for idx, rule in enumerate(self._live_alarm_rules):
            col  = rule.get("col", "?")
            lo   = rule.get("lo")
            hi   = rule.get("hi")
            lo_s = f"Lo:{lo:.4g}" if lo is not None else ""
            hi_s = f"Hi:{hi:.4g}" if hi is not None else ""
            card = ctk.CTkFrame(self._live_alarm_cards_frame,
                                fg_color=COLORS["surface2"], corner_radius=6)
            card.pack(fill="x", padx=4, pady=2)
            ctk.CTkLabel(card, text=col, font=("Segoe UI", 9, "bold"),
                         text_color=COLORS["accent"]).pack(anchor="w", padx=8, pady=(4, 0))
            ctk.CTkLabel(card, text=f"{lo_s}  {hi_s}",
                         font=("Segoe UI", 9),
                         text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(0, 2))

            def _make_del(i=idx):
                def _del():
                    if i < len(self._live_alarm_rules):
                        self._live_alarm_rules.pop(i)
                    self._live_rebuild_alarm_cards()
                return _del

            ctk.CTkButton(card, text="✕", width=22, height=18,
                          fg_color="transparent", hover_color=COLORS["error"],
                          text_color=COLORS["text2"], font=("Segoe UI", 9),
                          command=_make_del(idx)).pack(anchor="e", padx=4, pady=(0, 4))

    def _live_check_alarms(self, row):
        for rule in self._live_alarm_rules:
            col = rule.get("col")
            lo  = rule.get("lo")
            hi  = rule.get("hi")
            val = row.get(col)
            if val is None:
                continue
            try:
                val = float(val)
            except Exception:
                continue
            fired = (lo is not None and val < lo) or (hi is not None and val > hi)
            if fired and col not in self._live_alarm_active:
                self._live_alarm_active.add(col)
                self._live_alarm_count += 1
                ts = datetime.now().strftime("%H:%M:%S")
                msg = f"ALLARME {col}: {val:.4g} "
                msg += (f"< {lo}" if lo is not None and val < lo
                        else f"> {hi}")
                self._live_log_append(f"[{ts}] ⚠ {msg}")
                self._live_alarm_badge.configure(
                    text=f"⚠ {self._live_alarm_count} allarmi")
            elif not fired and col in self._live_alarm_active:
                self._live_alarm_active.discard(col)

    # ------------------------------------------------------------------
    # INTERPOLAZIONE
    # ------------------------------------------------------------------
    def _live_stop_interp_timer(self):
        if self._live_interp_job is not None:
            try:
                self.after_cancel(self._live_interp_job)
            except Exception:
                pass
            self._live_interp_job = None

    # ------------------------------------------------------------------
    # TOGGLE MULTI
    # ------------------------------------------------------------------
    def _live_toggle_multi(self):
        """Apre finestra di scelta gruppi per export multi-grafico."""
        if not self._live_rows:
            messagebox.showwarning("Attenzione", "Nessun dato live acquisito.")
            return
        win = tk.Toplevel(self)
        win.title("Esporta multi-grafico")
        win.configure(bg=COLORS["surface"])
        win.geometry("320x400")
        win.resizable(False, True)

        ctk.CTkLabel(win, text="Seleziona colonne da esportare",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 4))
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent", height=220)
        scroll.pack(fill="x", padx=16, pady=(0, 8))
        vars = {}
        palette = list(_UC_SERIES_PALETTE)
        for i, col in enumerate(self._live_plot_cols):
            color = palette[i % len(palette)]
            v     = tk.BooleanVar(value=True)
            vars[col] = v
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            dot = tk.Canvas(row, width=12, height=12,
                            bg=COLORS["surface"], highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=color, outline="")
            dot.pack(side="left", padx=(4, 6))
            ctk.CTkCheckBox(row, text=col, variable=v,
                            font=("Segoe UI", 10), text_color=COLORS["text"],
                            fg_color=COLORS["accent"], hover_color="#5a52e0",
                            checkmark_color=COLORS["text"],
                            border_color=COLORS["border"]).pack(side="left")

        ctk.CTkLabel(win, text="Layout",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]
                     ).pack(anchor="w", padx=20, pady=(0, 2))
        layout_var = ctk.StringVar(value="Verticale")
        ctk.CTkOptionMenu(win, variable=layout_var,
                          values=["Verticale", "Griglia 2 colonne"],
                          width=200, fg_color=COLORS["surface2"],
                          button_color=COLORS["accent"],
                          text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(0, 12))

        for fmt in ["png", "pdf"]:
            _f = fmt
            def _do_export(fmt=_f):
                selected = [gn for gn, v in vars.items() if v.get()]
                if not selected:
                    messagebox.showwarning("Selezione",
                                           "Seleziona almeno un grafico.")
                    return
                ext = ".png" if fmt == "png" else ".pdf"
                path = filedialog.asksaveasfilename(
                    defaultextension=ext,
                    filetypes=[(fmt.upper(), f"*{ext}")],
                    initialfile=f"live_multi{ext}")
                if not path:
                    return
                win.destroy()
                try:
                    self._live_export_multi_render(selected, path, fmt, layout_var.get())
                except Exception as e:
                    messagebox.showerror("Errore export", str(e))
            ctk.CTkButton(win, text=f"Esporta {fmt.upper()}",
                          width=200, height=34,
                          fg_color=COLORS["accent"], hover_color="#5a52e0",
                          text_color=COLORS["text"], font=("Segoe UI", 11),
                          command=_do_export).pack(pady=(0, 8))

    def _live_export_multi_render(self, selected, path, fmt, layout):
        """Costruisce una figura matplotlib con i grafici selezionati e salva."""
        n = len(selected)
        if layout == "Griglia 2 colonne":
            ncols = 2
            nrows = (n + 1) // 2
        else:
            ncols = 1
            nrows = n
        fig, axes = plt.subplots(nrows, ncols,
                                  figsize=(10 * ncols, 4 * nrows),
                                  facecolor="#1e1e2e")
        if n == 1:
            axes = [axes]
        elif ncols == 1:
            axes = list(axes)
        else:
            axes = [ax for row in axes
                    for ax in (row if hasattr(row, "__iter__") else [row])]

        palette = list(_UC_SERIES_PALETTE)
        colors  = {
            col: palette[i % len(palette)]
            for i, col in enumerate(self._live_numeric_cols)
        }
        try:
            max_pts = int(self._live_max_pts_var.get())
        except Exception:
            max_pts = MAX_LIVE_POINTS
        rows   = self._live_rows[-max_pts:]
        xcol   = ("_ts" if rows and "_ts" in rows[0]
                  else "_sim_t" if rows and "_sim_t" in rows[0]
                  else None)
        xsraw  = [r.get(xcol, i) if xcol else i for i, r in enumerate(rows)]

        for ax_idx, col in enumerate(selected):
            if ax_idx >= len(axes):
                break
            ax = axes[ax_idx]
            ax.set_facecolor("#252535")
            ax.set_title(col, color="#a0a0c0", fontsize=10, pad=4)
            for sp in ax.spines.values():
                sp.set_edgecolor("#3a3a5c")
            ax.tick_params(colors="#a0a0c0", labelsize=7)
            ax.grid(True, color="#3a3a5c", linewidth=0.4,
                    linestyle="--", alpha=0.6)
            vals = []
            for r in rows:
                v = r.get(col)
                vals.append(
                    float(v) if isinstance(v, (int, float)) else None)
            xf = [x for x, y in zip(xsraw, vals) if y is not None]
            yf = [y for y in vals          if y is not None]
            if xf:
                color = colors.get(col, "#ffffff")
                ax.plot(xf, yf, color=color, linewidth=1.2, label=col)
                ax.legend(fontsize=7, loc="upper left",
                          facecolor="#252535", labelcolor="#c0c0e0",
                          edgecolor="#3a3a5c")

        # Nascondi assi vuoti se griglia
        for j in range(n, len(axes)):
            axes[j].set_visible(False)

        fig.tight_layout(pad=1.5)
        if fmt == "pdf":
            from matplotlib.backends.backend_pdf import PdfPages
            with PdfPages(path) as pp:
                pp.savefig(fig, bbox_inches="tight")
        else:
            fig.savefig(path, dpi=150, bbox_inches="tight",
                        facecolor=fig.get_facecolor())
        plt.close(fig)
        self.set_status(f"Multi-export salvato: {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # TOGGLE MARKERS
    # ------------------------------------------------------------------
    def _live_toggle_markers(self):
        self._live_ipc.show_markers = self._live_show_pts_var.get()
        self._live_ipc.needs_full_redraw = True
        if self._live_rows:
            self._live_refresh_plot()

    # ------------------------------------------------------------------
    # RESET CURSORI
    # ------------------------------------------------------------------
    def _live_reset_cursors(self):
        self._live_ipc.clear_cursors()

    # ------------------------------------------------------------------
    # CLEAR
    # ------------------------------------------------------------------
    def _live_clear(self):
        was_running = self._live_running.is_set()
        if was_running:
            self._live_running.clear()
        self._live_stop_interp_timer()
        self._live_rows.clear()
        self._live_dropped = 0
        try:
            while True:
                self._live_queue.get_nowait()
        except Exception:
            pass
        if self._live_multi_mode:
            for ipc, _, _ in self._live_multi_ipcs.values():
                ipc.clear()
                ipc.needs_full_redraw = True
        else:
            self._live_ipc.clear()
        self._live_log_box.configure(state="normal")
        self._live_log_box.delete("1.0", "end")
        self._live_log_box.configure(state="disabled")
        self._live_cnt_lbl.configure(text="Campioni: 0  In coda: 0")
        self._live_alarm_active.clear()
        self._live_alarm_count  = 0
        self._live_alarm_badge.configure(text="")
        self._live_rebuild_alarm_cards()
        if was_running:
            self.after(400, self._live_start)

    # ------------------------------------------------------------------
    # LOG
    # ------------------------------------------------------------------
    def _live_log_append(self, msg):
        try:
            self._live_log_box.configure(state="normal")
            self._live_log_box.insert("end", msg + "\n")
            self._live_log_box.see("end")
            self._live_log_box.configure(state="disabled")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # EXPORT CSV / PNG / PDF
    # ------------------------------------------------------------------
    def _live_export_csv(self):
        if not self._live_rows:
            messagebox.showwarning("Attenzione", "Nessun dato live da esportare.")
            return
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"live_{ts}.csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        cols = [c for c in self._live_headers
                if not c.startswith("_")] if self._live_headers \
            else sorted({k for r in self._live_rows
                         for k in r if not k.startswith("_")})
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(self._live_rows)
        self.set_status(f"Live CSV salvato: {os.path.basename(path)}")
        messagebox.showinfo("Completato", f"CSV salvato:\n{path}")

    def _live_export_png(self):
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"live_{ts}.png",
            filetypes=[("PNG", "*.png")])
        if not path:
            return
        self._live_ipc.export_png(path)
        self.set_status(f"PNG salvato: {os.path.basename(path)}")

    def _live_export_pdf(self):
        if not self._live_rows:
            messagebox.showwarning("Attenzione", "Nessun dato live da esportare.")
            return
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"live_{ts}.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            max_pts = int(self._live_max_pts_var.get())
        except Exception:
            max_pts = MAX_LIVE_POINTS
        rows  = self._live_rows[-max_pts:]
        xcol  = ("_ts" if rows and "_ts" in rows[0]
                 else "_sim_t" if rows and "_sim_t" in rows[0]
                 else None)
        xsraw = [r.get(xcol, i) if xcol else i for i, r in enumerate(rows)]
        palette = list(_UC_SERIES_PALETTE)
        colors  = {col: palette[i % len(palette)]
                   for i, col in enumerate(self._live_numeric_cols)}
        from matplotlib.backends.backend_pdf import PdfPages
        fig = plt.Figure(figsize=(14, 5 * len(self._live_plot_cols)),
                         facecolor="#1e1e2e")
        for idx, col in enumerate(self._live_plot_cols):
            ax = fig.add_subplot(len(self._live_plot_cols), 1, idx + 1)
            ax.set_facecolor("#252535")
            ax.set_title(col, color="#a0a0c0", fontsize=10)
            for sp in ax.spines.values():
                sp.set_edgecolor("#3a3a5c")
            ax.tick_params(colors="#a0a0c0", labelsize=7)
            ax.grid(True, color="#3a3a5c", lw=0.4, linestyle="--")
            vals = []
            for r in rows:
                v = r.get(col)
                vals.append(float(v) if isinstance(v, (int, float)) else None)
            xf = [x for x, y in zip(xsraw, vals) if y is not None]
            yf = [y for y in vals if y is not None]
            if xf:
                ax.plot(xf, yf, color=colors.get(col, "#ffffff"), lw=1.2)
        fig.tight_layout(pad=1.5)
        with PdfPages(path) as pp:
            pp.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        self.set_status(f"Live PDF salvato: {os.path.basename(path)}")
        messagebox.showinfo("Completato", f"PDF salvato:\n{path}")
