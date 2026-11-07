# -*- coding: utf-8 -*-
"""Tab "Live Data": sorgenti seriale/simulazione, allarmi, multi-grafico ed export."""
import matplotlib
matplotlib.use("Agg")
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
import csv
import os
from datetime import datetime
import threading
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import random
import queue as _queue
from ..constants import COLORS, MAX_LIVE_POINTS
from ..csv_parsers import _is_long_cycle_csv, _parse_long_cycle_csv, _uc_col_meta, _uc_parse_dt, _uc_try_float, parse_universal_csv
from ..plot_canvas import InteractivePlotCanvas, _UC_SERIES_PALETTE
from ..serial_support import SERIAL_AVAILABLE
try:
    from ..serial_support import serial
except ImportError:
    pass
from ..ui_utils import _isolate_scroll


class LiveMixin:
    def _live_check_alarms(self):
        """Controlla l'ultimo campione rispetto alle soglie configurate."""
        if not self._live_rows or not self._live_alarm_rules:
            return
        last = self._live_rows[-1]
        newly_triggered = []
        now_active = set()
        for rule in self._live_alarm_rules:
            col = rule["col"]
            val = last.get(col)
            if not isinstance(val, (int, float)):
                continue
            lo = rule.get("lo")
            hi = rule.get("hi")
            in_alarm = False
            if lo is not None and val < lo:
                in_alarm = True
                direction = f"< {lo}"
            elif hi is not None and val > hi:
                in_alarm = True
                direction = f"> {hi}"
            if in_alarm:
                now_active.add(col)
                if col not in self._live_alarm_active:
                    # nuovo scatto
                    self._live_alarm_count += 1
                    newly_triggered.append((col, val, direction))
        # aggiorna badge
        self._live_alarm_active = now_active
        if now_active:
            self._live_alarm_badge.configure(
                text=f"🔴  {len(now_active)} ALLARME/I  |  Totale scatti: {self._live_alarm_count}",
                text_color=COLORS["error"])
        else:
            badge_txt = (f"✅  OK  |  Scatti totali: {self._live_alarm_count}"
                         if self._live_alarm_count else "")
            self._live_alarm_badge.configure(
                text=badge_txt,
                text_color=COLORS["info"])
        # log nuovi scatti
        for col, val, direction in newly_triggered:
            self._live_log_append(
                f"⚠ ALLARME [{col}] = {val:.4g} {direction}", scroll=True)


    def _live_add_alarm_rule(self):
        """Dialogo per aggiungere una soglia di allarme."""
        if not self._live_numeric_cols:
            messagebox.showinfo("Allarmi", "Carica prima un CSV o avvia la simulazione.")
            return
        win = ctk.CTkToplevel(self)
        win.title("Nuova soglia allarme")
        win.geometry("340x300")
        win.resizable(False, False)
        win.configure(fg_color=COLORS["bg"])
        win.grab_set()

        ctk.CTkLabel(win, text="Colonna", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(18, 2))
        col_var = ctk.StringVar(value=self._live_numeric_cols[0])
        ctk.CTkOptionMenu(win, variable=col_var,
                          values=self._live_numeric_cols, width=280,
                          fg_color=COLORS["surface2"], button_color=COLORS["accent"],
                          text_color=COLORS["text"]).pack(padx=20)

        ctk.CTkLabel(win, text="Soglia minima (Lo) — lascia vuoto per ignorare",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(12, 2))
        lo_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=lo_var, placeholder_text="es. 0.5",
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     width=280).pack(padx=20)

        ctk.CTkLabel(win, text="Soglia massima (Hi) — lascia vuoto per ignorare",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(10, 2))
        hi_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=hi_var, placeholder_text="es. 150.0",
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     width=280).pack(padx=20)

        def _confirm():
            col = col_var.get()
            lo = None; hi = None
            try: lo = float(lo_var.get().replace(",", "."))
            except Exception: pass
            try: hi = float(hi_var.get().replace(",", "."))
            except Exception: pass
            if lo is None and hi is None:
                messagebox.showwarning("Soglia", "Inserisci almeno un valore Lo o Hi.")
                return
            self._live_alarm_rules.append({"col": col, "lo": lo, "hi": hi})
            self._live_rebuild_alarm_cards()
            win.destroy()

        ctk.CTkButton(win, text="Aggiungi", width=140, height=32,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], command=_confirm).pack(pady=16)


    def _live_rebuild_alarm_cards(self):
        """Ripopola il pannello card soglie."""
        for w in self._live_alarm_cards_ui:
            try: w.destroy()
            except Exception: pass
        self._live_alarm_cards_ui.clear()
        for idx, rule in enumerate(self._live_alarm_rules):
            col = rule["col"]
            lo  = rule.get("lo")
            hi  = rule.get("hi")
            parts = []
            if lo is not None: parts.append(f"Lo={lo:.4g}")
            if hi is not None: parts.append(f"Hi={hi:.4g}")
            label = f"{col}  [{', '.join(parts)}]"
            is_alarm = col in self._live_alarm_active
            card = ctk.CTkFrame(
                self._live_alarm_rules_frame,
                fg_color=COLORS["error"] if is_alarm else COLORS["surface"],
                corner_radius=6)
            card.pack(fill="x", padx=4, pady=3, ipadx=4, ipady=2)
            ctk.CTkLabel(card, text=label, font=("Segoe UI", 9, "bold"),
                         text_color=COLORS["text"]).pack(side="left", padx=6)
            del_btn = ctk.CTkButton(
                card, text="✕", width=20, height=20,
                fg_color="transparent", hover_color=COLORS["border"],
                text_color=COLORS["text2"], font=("Segoe UI", 9),
                command=lambda i=idx: self._live_remove_alarm(i))
            del_btn.pack(side="left", padx=(0, 4))
            self._live_alarm_cards_ui.append(card)


    def _live_remove_alarm(self, idx):
        if 0 <= idx < len(self._live_alarm_rules):
            self._live_alarm_rules.pop(idx)
            self._live_rebuild_alarm_cards()


    def _live_reset_alarms(self):
        self._live_alarm_rules.clear()
        self._live_alarm_count = 0
        self._live_alarm_active.clear()
        self._live_alarm_badge.configure(text="")
        self._live_rebuild_alarm_cards()


    def _live_export_png(self):
        """Esporta il/i grafico/i. In multi: finestra selezione → unico file."""
        if not self._live_rows:
            messagebox.showinfo("Esporta", "Nessun dato da esportare.")
            return
        if self._live_multi_mode and self._live_multi_ipcs:
            self._live_export_multi_dialog("png")
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG", "*.png")],
                title="Salva grafico live come PNG",
                initialfile="live_plot.png")
            if not path:
                return
            try:
                self._live_ipc.export_png(path)
                self.set_status(f"PNG salvato: {os.path.basename(path)}")
                messagebox.showinfo("Esportato", f"PNG salvato:\n{path}")
            except Exception as e:
                messagebox.showerror("Errore PNG", str(e))


    def _live_export_multi_dialog(self, fmt="png"):
        """Finestra di selezione grafici per export multi → unico file PNG o PDF."""
        groups = list(self._live_multi_ipcs.keys())
        if not groups:
            return

        win = ctk.CTkToplevel(self)
        win.title("Esporta grafici")
        win.geometry("340x420")
        win.resizable(False, False)
        win.configure(fg_color=COLORS["bg"])
        win.grab_set()

        ctk.CTkLabel(win, text="Seleziona i grafici da esportare",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 8))

        # checkbox per ogni gruppo
        vars_ = {}
        scroll = ctk.CTkScrollableFrame(win, fg_color=COLORS["surface"],
                                        corner_radius=8, height=220)
        scroll.pack(fill="x", padx=20, pady=(0, 8))
        for gn in groups:
            v = tk.BooleanVar(value=True)
            vars_[gn] = v
            ctk.CTkCheckBox(scroll, text=gn, variable=v,
                            font=("Segoe UI", 10), text_color=COLORS["text"],
                            fg_color=COLORS["accent"], hover_color="#5a52e0",
                            checkmark_color="#fff").pack(anchor="w", padx=10, pady=4)

        # selezione tutti/nessuno
        sel_row = ctk.CTkFrame(win, fg_color="transparent")
        sel_row.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkButton(sel_row, text="Tutti", width=80, height=24,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      command=lambda: [v.set(True) for v in vars_.values()]
                      ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(sel_row, text="Nessuno", width=80, height=24,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      command=lambda: [v.set(False) for v in vars_.values()]
                      ).pack(side="left")

        # layout
        ctk.CTkLabel(win, text="Layout:",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(0, 2))
        layout_var = ctk.StringVar(value="Verticale")
        ctk.CTkOptionMenu(win, variable=layout_var,
                          values=["Verticale", "Griglia 2 colonne"],
                          width=200, fg_color=COLORS["surface2"],
                          button_color=COLORS["accent"],
                          text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(0, 12))

        def _do_export():
            selected = [gn for gn, v in vars_.items() if v.get()]
            if not selected:
                messagebox.showwarning("Selezione", "Seleziona almeno un grafico.")
                return
            if fmt == "png":
                path = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG", "*.png")],
                    initialfile="live_multi.png")
            else:
                path = filedialog.asksaveasfilename(
                    defaultextension=".pdf",
                    filetypes=[("PDF", "*.pdf")],
                    initialfile="live_multi.pdf")
            if not path:
                return
            win.destroy()
            try:
                self._live_export_multi_render(selected, path, fmt,
                                               layout_var.get())
            except Exception as e:
                messagebox.showerror("Errore export", str(e))

        ctk.CTkButton(win, text=f"Esporta {fmt.upper()}",
                      width=200, height=34,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 11),
                      command=_do_export).pack(pady=(0, 16))


    def _live_export_multi_render(self, selected, path, fmt, layout):
        """Costruisce una figura matplotlib con i grafici selezionati e salva."""
        n = len(selected)
        if layout == "Griglia 2 colonne":
            ncols = 2; nrows = (n + 1) // 2
        else:
            ncols = 1; nrows = n

        fig, axes = plt.subplots(nrows, ncols,
                                 figsize=(10 * ncols, 4 * nrows),
                                 facecolor="#1e1e2e")
        if n == 1:
            axes = [axes]
        elif ncols == 1:
            axes = list(axes)
        else:
            axes = [ax for row in axes for ax in (row if hasattr(row, '__iter__') else [row])]

        palette = list(_UC_SERIES_PALETTE)
        colors = {col: palette[i % len(palette)]
                  for i, col in enumerate(self._live_numeric_cols)}

        try:
            max_pts = int(self._live_maxpts_var.get())
        except Exception:
            max_pts = MAX_LIVE_POINTS
        rows = self._live_rows[-max_pts:]

        x_col = "_ts" if rows and "_ts" in rows[0] else (
                "_sim_t" if rows and "_sim_t" in rows[0] else None)
        xs_raw = [r.get(x_col, i) if x_col else i for i, r in enumerate(rows)]

        for ax_idx, gn in enumerate(selected):
            if ax_idx >= len(axes):
                break
            ax = axes[ax_idx]
            ax.set_facecolor("#252535")
            ax.set_title(gn, color="#a0a0c0", fontsize=10, pad=4)
            for sp in ax.spines.values():
                sp.set_edgecolor("#3a3a5c")
            ax.tick_params(colors="#a0a0c0", labelsize=7)
            ax.grid(True, color="#3a3a5c", linewidth=0.4,
                    linestyle="--", alpha=0.6)

            ipc, group_cols, _ = self._live_multi_ipcs[gn]
            for col in group_cols:
                vals = [float(r.get(col)) if isinstance(r.get(col),
                        (int, float)) else None for r in rows]
                xf = [x for x, y in zip(xs_raw, vals) if y is not None]
                yf = [y for y in vals if y is not None]
                if xf:
                    color = colors.get(col, "#ffffff")
                    ax.plot(xf, yf, color=color, linewidth=1.2, label=col)
            ax.legend(fontsize=7, loc="upper left",
                      facecolor="#252535", labelcolor="#c0c0e0",
                      edgecolor="#3a3a5c")

        # nascondi assi vuoti se griglia dispari
        for ax_idx in range(len(selected), len(axes)):
            axes[ax_idx].set_visible(False)

        fig.tight_layout(pad=1.5)
        if fmt == "pdf":
            from matplotlib.backends.backend_pdf import PdfPages
            with PdfPages(path) as pdf:
                pdf.savefig(fig, bbox_inches="tight", facecolor=fig.get_facecolor())
        else:
            fig.savefig(path, dpi=150, bbox_inches="tight",
                        facecolor=fig.get_facecolor())
        plt.close(fig)
        self.set_status(f"Esportato: {os.path.basename(path)}")
        messagebox.showinfo("Esportato", f"File salvato:\n{path}")


    def _live_export_pdf(self):
        """Esporta il/i grafico/i come PDF. In multi: finestra selezione."""
        if not self._live_rows:
            messagebox.showinfo("Esporta", "Nessun dato da esportare.")
            return
        if self._live_multi_mode and self._live_multi_ipcs:
            self._live_export_multi_dialog("pdf")
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                title="Salva grafico live come PDF",
                initialfile="live_plot.pdf")
            if not path:
                return
            try:
                from matplotlib.backends.backend_pdf import PdfPages
                fig = self._live_ipc._fig
                with PdfPages(path) as pdf:
                    pdf.savefig(fig, bbox_inches="tight",
                                facecolor=fig.get_facecolor())
                self.set_status(f"PDF salvato: {os.path.basename(path)}")
                messagebox.showinfo("Esportato", f"PDF salvato:\n{path}")
            except Exception as e:
                messagebox.showerror("Errore PDF", str(e))


    # ══════════════════════════════════════════════════════════════════════
    # TAB LIVE DATA
    # ══════════════════════════════════════════════════════════════════════

    def _build_live_tab(self, parent):
        """Tab per monitoraggio live: seriale reale o simulazione CSV."""

        # ══════════════════════════════════════════════════════════════
        # TOOLBAR (scrollabile orizzontalmente se la finestra è stretta)
        # ══════════════════════════════════════════════════════════════
        toolbar_wrap = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        toolbar_wrap.pack(fill="x", side="top", padx=4, pady=(4, 0))

        # ── riga 1: sorgente + CSV + porte ───────────────────────────
        row1 = ctk.CTkFrame(toolbar_wrap, fg_color=COLORS["surface"], corner_radius=8)
        row1.pack(fill="x", pady=(0, 3))

        ctk.CTkLabel(row1, text="Sorgente", font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(side="left", padx=10, pady=8)

        self._live_src_var = ctk.StringVar(value="Simulazione CSV")
        src_opts = ["Simulazione CSV"]
        if SERIAL_AVAILABLE:
            src_opts.append("Seriale")
        self._live_src_menu = ctk.CTkOptionMenu(
            row1, variable=self._live_src_var, values=src_opts, width=150,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"], command=self._live_on_source_change)
        self._live_src_menu.pack(side="left", padx=6, pady=8)

        # porta seriale (nascosta di default)
        self._live_port_lbl = ctk.CTkLabel(row1, text="Porta",
                                           font=("Segoe UI", 10, "bold"),
                                           text_color=COLORS["text2"])
        self._live_port_var = ctk.StringVar(value="")
        self._live_port_menu = ctk.CTkOptionMenu(
            row1, variable=self._live_port_var, values=["—"],
            width=120, fg_color=COLORS["surface2"],
            button_color=COLORS["accent"], text_color=COLORS["text"])
        self._live_baud_lbl = ctk.CTkLabel(row1, text="Baud",
                                           font=("Segoe UI", 10, "bold"),
                                           text_color=COLORS["text2"])
        self._live_baud_var = ctk.StringVar(value="9600")
        self._live_baud_entry = ctk.CTkEntry(
            row1, textvariable=self._live_baud_var,
            width=65, fg_color=COLORS["surface2"], text_color=COLORS["text"])
        self._live_refresh_btn = ctk.CTkButton(
            row1, text="↻", width=28, height=26,
            fg_color=COLORS["surface2"], hover_color=COLORS["border"],
            text_color=COLORS["text"], command=self._live_refresh_ports)

        # CSV simulazione
        self._live_csv_path = None
        ctk.CTkButton(row1, text="📂 CSV", width=80, height=26,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 10),
                      command=self._live_open_csv).pack(side="left", padx=4, pady=8)
        self._live_csv_lbl = ctk.CTkLabel(row1, text="Nessun file",
                                          font=("Segoe UI", 9),
                                          text_color=COLORS["text2"])
        self._live_csv_lbl.pack(side="left", padx=4)

        ctk.CTkButton(row1, text="↻ Porte", width=80, height=26,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 9),
                      command=self._live_refresh_ports).pack(side="right", padx=8, pady=8)

        # ── riga 3: controlli compatti ────────────────────────────────
        row3 = ctk.CTkFrame(toolbar_wrap, fg_color=COLORS["surface"], corner_radius=8)
        row3.pack(fill="x", pady=(0, 3))

        # ── riga 3a: bottoni azione principali ───────────────────────────
        # pulsanti azione rotondi con icona
        RBTN = dict(width=44, height=44, corner_radius=22,
                    font=("Segoe UI", 18), text_color=COLORS["text"])
        self._live_start_btn = ctk.CTkButton(
            row3, text="▶", fg_color=COLORS["info"],
            hover_color="#3a9a10", **RBTN,
            command=self._live_start)
        self._live_start_btn.pack(side="left", padx=(8, 4), pady=6)

        self._live_stop_btn = ctk.CTkButton(
            row3, text="⏹", fg_color=COLORS["error"],
            hover_color="#cc2a2c", **RBTN,
            state="disabled", command=self._live_stop)
        self._live_stop_btn.pack(side="left", padx=4, pady=6)

        self._live_pause_btn = ctk.CTkButton(
            row3, text="⏸", fg_color=COLORS["warn"],
            hover_color="#c87d00", **RBTN,
            state="disabled", command=self._live_toggle_pause)
        self._live_pause_btn.pack(side="left", padx=4, pady=6)

        SBTN = dict(height=28, font=("Segoe UI", 9), text_color=COLORS["text"],
                    fg_color=COLORS["surface2"], hover_color=COLORS["border"])
        ctk.CTkButton(row3, text="Pulisci", width=65, **SBTN,
                      command=self._live_clear).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="↓ CSV", width=60, **SBTN,
                      command=self._live_export_csv).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="↓ PNG", width=60, **SBTN,
                      command=self._live_export_png).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="↓ PDF", width=60, **SBTN,
                      command=self._live_export_pdf).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="✕ Δ", width=46, **SBTN,
                      command=self._live_reset_cursors).pack(side="left", padx=3, pady=7)

        self._live_multi_btn = ctk.CTkButton(
            row3, text="⊞ Multi", width=72, height=28,
            fg_color=COLORS["surface2"], hover_color=COLORS["accent"],
            text_color=COLORS["text"], font=("Segoe UI", 9),
            command=self._live_toggle_multi)
        self._live_multi_btn.pack(side="left", padx=3, pady=7)

        # separatore
        ctk.CTkFrame(row3, width=1, height=24,
                     fg_color=COLORS["border"]).pack(side="left", padx=6, pady=7)

        # ── parametri (parte destra row3) ────────────────────────────────
        LBL = dict(font=("Segoe UI", 9), text_color=COLORS["text2"])
        ctk.CTkLabel(row3, text="Max pt", **LBL).pack(side="left", padx=(2, 2))
        self._live_maxpts_var = ctk.StringVar(value="500")
        ctk.CTkEntry(row3, textvariable=self._live_maxpts_var, width=48,
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     height=26).pack(side="left", padx=(0, 4))

        ctk.CTkLabel(row3, text="Vel", **LBL).pack(side="left", padx=(4, 2))
        self._live_speed_var = ctk.StringVar(value="1x")
        self._live_speed_snapshot = "1x"

        def _on_speed_change(val):
            # aggiorna snapshot nel thread UI — il sim thread legge solo snapshot
            self._live_speed_snapshot = val

        ctk.CTkOptionMenu(row3, variable=self._live_speed_var,
                          values=["0.25x", "0.5x", "1x", "2x", "5x", "10x",
                                  "15x", "20x", "30x", "60x", "100x", "MAX"],
                          width=75, height=26,
                          fg_color=COLORS["surface2"], button_color=COLORS["accent"],
                          text_color=COLORS["text"],
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
        ctk.CTkEntry(row3, textvariable=self._live_rate_var, width=52,
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     height=26).pack(side="left")
        ctk.CTkLabel(row3, text="ms", **LBL).pack(side="left", padx=(2, 8))

        self._live_status_lbl = ctk.CTkLabel(
            row3, text="● In attesa", font=("Segoe UI", 10),
            text_color=COLORS["text2"])
        self._live_status_lbl.pack(side="left", padx=8)

        # ── riga contatori ────────────────────────────────────────────
        cnt_row = ctk.CTkFrame(toolbar_wrap, fg_color=COLORS["surface"], corner_radius=8)
        cnt_row.pack(fill="x", pady=(0, 3))
        self._live_cnt_lbl = ctk.CTkLabel(
            cnt_row, text="Campioni: 0  |  In coda: 0",
            font=("Courier New", 10), text_color=COLORS["accent2"])
        self._live_cnt_lbl.pack(side="left", padx=14, pady=5)
        self._live_alarm_badge = ctk.CTkLabel(
            cnt_row, text="", font=("Segoe UI", 10, "bold"),
            text_color=COLORS["error"])
        self._live_alarm_badge.pack(side="left", padx=10, pady=5)
        self._live_col_btns = []  # inizializzato qui, sidebar creata nel body

        # ══════════════════════════════════════════════════════════════
        # BODY: colonne Y (sx, fisso) | grafico (centro, espanso) | allarmi (dx, fisso)
        # ══════════════════════════════════════════════════════════════
        body = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # ── pannello allarmi (destra, fisso 220px) ────────────────────
        right = ctk.CTkFrame(body, fg_color=COLORS["surface"],
                             corner_radius=8, width=220)
        right.pack(side="right", fill="y", padx=(4, 0), pady=0)
        right.pack_propagate(False)

        alarm_hdr = ctk.CTkFrame(right, fg_color="transparent")
        alarm_hdr.pack(fill="x", padx=8, pady=(8, 2))
        ctk.CTkLabel(alarm_hdr, text="⚠ Allarmi live",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(side="left")
        ctk.CTkButton(alarm_hdr, text="+ Soglia", width=70, height=22,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 9),
                      command=self._live_add_alarm_rule).pack(side="right")
        ctk.CTkButton(alarm_hdr, text="Azzera", width=58, height=22,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      command=self._live_reset_alarms).pack(side="right", padx=4)

        self._live_alarm_rules_frame = ctk.CTkScrollableFrame(
            right, fg_color=COLORS["surface2"],
            orientation="vertical", corner_radius=4)
        self._live_alarm_rules_frame.pack(fill="both", expand=True,
                                          padx=8, pady=(2, 8))
        _isolate_scroll(self._live_alarm_rules_frame)
        self._live_alarm_cards_ui = []

        # ── sidebar Colonne Y (sinistra, fisso 110px) ─────────────────
        col_sidebar = ctk.CTkFrame(body, fg_color=COLORS["surface"],
                                   corner_radius=8, width=145)
        col_sidebar.pack(side="left", fill="y", padx=(0, 4), pady=0)
        col_sidebar.pack_propagate(False)

        ctk.CTkLabel(col_sidebar, text="Colonne Y",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(8, 2))

        btn_row = ctk.CTkFrame(col_sidebar, fg_color="transparent")
        btn_row.pack(anchor="w", padx=6, pady=(0, 4))
        ctk.CTkButton(btn_row, text="✓", width=36, height=18,
                      fg_color=COLORS["surface2"], hover_color=COLORS["accent"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      corner_radius=4,
                      command=self._live_sel_all).pack(side="left", padx=(0, 2))
        ctk.CTkButton(btn_row, text="✗", width=36, height=18,
                      fg_color=COLORS["surface2"], hover_color=COLORS["error"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      corner_radius=4,
                      command=self._live_sel_none).pack(side="left")

        self._live_col_scroll = ctk.CTkScrollableFrame(
            col_sidebar, fg_color="transparent",
            orientation="vertical", corner_radius=0)
        self._live_col_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        _isolate_scroll(self._live_col_scroll)

        # ── pannello centro: grafico + log ────────────────────────────
        left = ctk.CTkFrame(body, fg_color=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True)

        # ── log messaggi (prima del grafico così non viene schiacciato) ──
        log_frame = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        log_frame.pack(fill="x", side="bottom", pady=(4, 0))
        ctk.CTkLabel(log_frame, text="Log",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(4, 0))
        self._live_log_box = ctk.CTkTextbox(
            log_frame, height=75, font=("Courier New", 9),
            fg_color=COLORS["surface2"], text_color=COLORS["text"],
            border_width=0, state="disabled")
        self._live_log_box.pack(fill="x", padx=6, pady=(2, 6))

        # ── grafico live — swap pulito con pack/pack_forget ───────────────
        self._live_graph_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._live_graph_container.pack(fill="both", expand=True)

        # frame multi — non pakkato all'avvio, appare solo con Multi ON
        self._live_multi_holder = ctk.CTkFrame(
            self._live_graph_container, fg_color=COLORS["bg"])

        # frame singolo — occupa tutto lo spazio all'avvio
        self._live_plot_frame = ctk.CTkFrame(
            self._live_graph_container, fg_color=COLORS["bg"])
        self._live_plot_frame.pack(fill="both", expand=True)
        self._live_ipc = InteractivePlotCanvas(self._live_plot_frame, height=380)


    # ── Multi-grafico ────────────────────────────────────────────────────
    _MULTI_GROUPS = [
        ("Temp. Superiore", lambda c: c.upper().startswith("TS")),
        ("Temp. Inferiore", lambda c: c.upper().startswith("TI")),
        ("Temperatura",     lambda c: c.upper().startswith("T") and not c.upper().startswith("TS") and not c.upper().startswith("TI")),
        ("Forza",           lambda c: c.upper().startswith("F")),
        ("Posizione",       lambda c: c.upper().startswith("P")),
        ("Vuoto",           lambda c: c.upper().startswith("V")),
    ]


    def _live_group_cols(self, cols):
        """Raggruppa le colonne per grandezza fisica."""
        groups = {}
        assigned = set()
        for name, predicate in self._MULTI_GROUPS:
            matched = [c for c in cols if predicate(c) and c not in assigned]
            if matched:
                groups[name] = matched
                assigned.update(matched)
        remaining = [c for c in cols if c not in assigned]
        if remaining:
            groups["Altri"] = remaining
        return groups


    def _live_toggle_multi(self):
        self._live_multi_mode = not self._live_multi_mode
        if self._live_multi_mode:
            self._live_multi_btn.configure(
                fg_color=COLORS["accent"], text="⊞ Multi ON")
            # Fix: se la singola è in play/pausa, fermala prima di entrare in multi
            if self._live_running.is_set() or self._live_paused.is_set():
                self._live_stop()
            self._live_build_multi()
        else:
            self._live_multi_btn.configure(
                fg_color=COLORS["surface2"], text="⊞ Multi")
            self._live_destroy_multi()


    def _live_build_multi(self):
        """Costruisce vista multi a 2 colonne con overlay di caricamento."""
        if hasattr(self, "_live_multi_frame"):
            try: self._live_multi_frame.destroy()
            except Exception: pass
            try: del self._live_multi_frame
            except Exception: pass
        self._live_multi_ipcs = {}

        cols = self._live_numeric_cols
        if not cols:
            self._live_multi_mode = False
            self._live_multi_btn.configure(fg_color=COLORS["surface2"], text="⊞ Multi")
            return
        groups = self._live_group_cols(cols)
        if len(groups) <= 1:
            self._live_multi_mode = False
            self._live_multi_btn.configure(fg_color=COLORS["surface2"], text="⊞ Multi")
            return

        # disabilita tasti principali
        self._live_start_btn.configure(state="disabled")
        self._live_pause_btn.configure(state="disabled")
        self._live_stop_btn.configure(state="disabled")

        # swap: nascondi singolo, mostra holder
        self._live_plot_frame.pack_forget()
        for w in self._live_multi_holder.winfo_children():
            try: w.destroy()
            except Exception: pass
        self._live_multi_holder.pack(fill="both", expand=True)

        # ── overlay "Caricamento..." visibile subito ──────────────────
        loading_frame = ctk.CTkFrame(
            self._live_multi_holder, fg_color=COLORS["bg"])
        loading_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(loading_frame,
                     text="⟳  Caricamento grafici...",
                     font=("Segoe UI", 14), text_color=COLORS["text2"]
                     ).place(relx=0.5, rely=0.5, anchor="center")
        self._live_multi_holder.update_idletasks()

        # ── costruisce struttura celle (senza IPC, solo widget UI) ────
        self._live_multi_frame = ctk.CTkScrollableFrame(
            self._live_multi_holder,
            fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        _isolate_scroll(self._live_multi_frame)

        groups_list = list(groups.items())
        show_pts = getattr(self, "_live_show_pts_var",
                           ctk.BooleanVar(value=True)).get()

        # mappa {group_name: (cell_frame, group_cols, state)}
        cell_data = {}
        for row_i in range(0, len(groups_list), 2):
            row_frame = ctk.CTkFrame(self._live_multi_frame, fg_color=COLORS["bg"])
            row_frame.pack(fill="x", pady=4)
            row_frame.columnconfigure(0, weight=1)
            row_frame.columnconfigure(1, weight=1)

            for col_i in range(2):
                idx = row_i + col_i
                if idx >= len(groups_list):
                    break
                group_name, group_cols = groups_list[idx]

                cell = ctk.CTkFrame(row_frame, fg_color=COLORS["surface"],
                                    corner_radius=8)
                cell.grid(row=0, column=col_i, sticky="nsew", padx=3)

                hdr = ctk.CTkFrame(cell, fg_color="transparent")
                hdr.pack(fill="x", padx=6, pady=(4, 0))
                ctk.CTkLabel(hdr, text=group_name,
                             font=("Segoe UI", 9, "bold"),
                             text_color=COLORS["accent2"]).pack(side="left")

                state = {"active": False, "paused": False}
                MBTN = dict(width=22, height=22, corner_radius=11,
                            font=("Segoe UI", 10), text_color=COLORS["text"])
                stop_btn  = ctk.CTkButton(hdr, text="⏹",
                                          fg_color=COLORS["error"],
                                          hover_color="#cc2a2c", **MBTN)
                pause_btn = ctk.CTkButton(hdr, text="⏸",
                                          fg_color=COLORS["warn"],
                                          hover_color="#c87d00", **MBTN)
                play_btn  = ctk.CTkButton(hdr, text="▶",
                                          fg_color=COLORS["surface2"],
                                          hover_color="#3a9a10", **MBTN)

                def _make_ctrl(st=state, pb=play_btn, psb=pause_btn):
                    def _play():
                        st["active"] = True; st["paused"] = False
                        pb.configure(fg_color=COLORS["info"])
                        psb.configure(fg_color=COLORS["warn"])
                        if not self._live_running.is_set():
                            self._live_start()
                        elif self._live_paused.is_set():
                            # Fix: era in pausa globale → riprendi il thread
                            self._live_paused.clear()
                    def _pause():
                        st["paused"] = not st["paused"]
                        psb.configure(fg_color=COLORS["accent"]
                                      if st["paused"] else COLORS["warn"])
                    def _stop():
                        st["active"] = False; st["paused"] = False
                        pb.configure(fg_color=COLORS["surface2"])
                        psb.configure(fg_color=COLORS["warn"])
                        all_stopped = all(
                            not e[2].get("active")
                            for e in self._live_multi_ipcs.values())
                        if all_stopped and self._live_running.is_set():
                            self._live_stop()
                    return _play, _pause, _stop

                pf, psf, sf = _make_ctrl()
                play_btn.configure(command=pf)
                pause_btn.configure(command=psf)
                stop_btn.configure(command=sf)
                stop_btn.pack(side="right", padx=(0, 4), pady=4)
                pause_btn.pack(side="right", padx=2, pady=4)
                play_btn.pack(side="right", padx=2, pady=4)

                cell_data[group_name] = (cell, hdr, group_cols, state)

        # ── crea IPC uno per volta via after() — UI rimane responsiva ─
        groups_todo = list(cell_data.items())

        def _build_next(idx):
            if idx >= len(groups_todo):
                # tutti costruiti: rimuovi overlay, mostra grafici
                try: loading_frame.destroy()
                except Exception: pass
                self._live_multi_frame.pack(fill="both", expand=True)
                if self._live_rows:
                    self._live_refresh_plot()
                return

            group_name, (cell, hdr, group_cols, state) = groups_todo[idx]

            ipc = InteractivePlotCanvas(cell, height=220)
            ipc.show_markers = show_pts

            def _make_delta_reset(i):
                def _reset():
                    i._cur_a = None; i._cur_b = None
                    i._redraw_cursors_ab()
                    i._canvas.draw()
                    i._bg_cache = i._canvas.copy_from_bbox(i._fig.bbox)
                return _reset

            ctk.CTkButton(
                hdr, text="✕Δ", width=26, height=22,
                fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                text_color=COLORS["text2"], font=("Segoe UI", 8),
                corner_radius=4,
                command=_make_delta_reset(ipc)).pack(side="right", padx=(0, 2), pady=4)

            def _make_png(i=ipc, gn=group_name):
                def _export():
                    p = filedialog.asksaveasfilename(
                        defaultextension=".png",
                        filetypes=[("PNG", "*.png")],
                        initialfile=f"live_{gn.replace(' ','_')}.png")
                    if p:
                        try: i.export_png(p); self.set_status(f"PNG: {os.path.basename(p)}")
                        except Exception as e: messagebox.showerror("Errore PNG", str(e))
                return _export

            ctk.CTkButton(
                hdr, text="↓PNG", width=36, height=22,
                fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                text_color=COLORS["text2"], font=("Segoe UI", 8),
                corner_radius=4,
                command=_make_png()).pack(side="right", padx=2, pady=4)

            self._live_multi_ipcs[group_name] = (ipc, group_cols, state)
            # prossimo IPC dopo 50ms — lascia il ciclo eventi respirare
            self.after(50, lambda i=idx+1: _build_next(i))

        # avvia la costruzione al prossimo ciclo eventi
        self.after(10, lambda: _build_next(0))


    def _live_destroy_multi(self):
        """Rimuove multi e ripristina grafico singolo."""
        # Fix: ferma il thread se ancora in corsa (grafici multi attivi)
        if self._live_running.is_set() or self._live_paused.is_set():
            self._live_stop()
        # distruggi multi PRIMA di re-pack plot_frame
        # così plot_frame è l'unico figlio → pack order corretto
        if hasattr(self, "_live_multi_frame"):
            try: self._live_multi_frame.destroy()
            except Exception: pass
            try: del self._live_multi_frame
            except Exception: pass
        self._live_multi_ipcs = {}

        # swap: nascondi holder, ripristina singolo
        self._live_multi_holder.pack_forget()
        self._live_plot_frame.pack(fill="both", expand=True)

        # ── riabilita tasti principali in base allo stato simulazione ────
        if self._live_running.is_set():
            self._live_start_btn.configure(state="disabled")
            self._live_stop_btn.configure(state="normal")
            self._live_pause_btn.configure(state="normal")
        else:
            self._live_start_btn.configure(state="normal")
            self._live_stop_btn.configure(state="disabled")
            self._live_pause_btn.configure(state="disabled")

        self._live_ipc._needs_full_redraw = True
        if self._live_rows:
            self.after(50, self._live_refresh_plot)


    # ── helper sorgente ──────────────────────────────────────────────────
    def _live_on_source_change(self, val):
        """Mostra i controlli seriale solo se la sorgente è 'Seriale'."""
        if val == "Seriale":
            self._live_port_lbl.pack(side="left", padx=(12, 2), pady=10)
            self._live_port_menu.pack(side="left", padx=4, pady=10)
            self._live_baud_lbl.pack(side="left", padx=(8, 2), pady=10)
            self._live_baud_entry.pack(side="left", padx=4, pady=10)
            self._live_refresh_btn.pack(side="left", padx=2, pady=10)
            self._live_refresh_ports()
        else:
            self._live_port_lbl.pack_forget()
            self._live_port_menu.pack_forget()
            self._live_baud_lbl.pack_forget()
            self._live_baud_entry.pack_forget()
            self._live_refresh_btn.pack_forget()


    def _live_refresh_ports(self):
        if not SERIAL_AVAILABLE:
            return
        try:
            ports = [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            ports = []
        if not ports:
            ports = ["—"]
        self._live_port_menu.configure(values=ports)
        self._live_port_var.set(ports[0])


    def _live_open_csv(self):
        if self._live_loading or self._live_running.is_set() or (self._live_thread is not None and self._live_thread.is_alive()):
            messagebox.showinfo("Live Data", "Termina la lettura corrente prima di scegliere un altro CSV.")
            return
        path = filedialog.askopenfilename(
            title="Seleziona CSV per simulazione",
            filetypes=[("CSV", "*.csv"), ("Tutti", "*.*")])
        if not path:
            return
        self._live_loading = True
        self._live_csv_path = path
        self._live_csv_lbl.configure(text=os.path.basename(path))
        self._live_log_append(f"CSV simulazione: {path}")

        # ── reset COMPLETO stato colonne (fix: CSV precedente non spariva) ──
        self._live_headers      = []
        self._live_col_meta     = {}
        self._live_numeric_cols = []
        self._live_plot_cols    = []
        # distruggi tutti i widget figli rimasti nel frame scorrevole
        for w in self._live_col_scroll.winfo_children():
            try: w.destroy()
            except Exception: pass
        self._live_col_btns.clear()

        self._live_set_status("Caricamento CSV…", COLORS["text2"])

        def _load():
            try:
                if _is_long_cycle_csv(path):
                    _, headers, col_meta, numeric_cols, _, _, _, _ = \
                        _parse_long_cycle_csv(path)
                    long_fmt = True
                else:
                    _, headers, col_meta, numeric_cols, _, _, _, _ = \
                        parse_universal_csv(path)
                    long_fmt = False
                def _apply():
                    self._live_loading = False
                    if long_fmt:
                        self._live_log_append(
                            "Formato rilevato: Long CSV (Cannon/Persico/Krauss Maffei)")
                    self._live_headers      = headers
                    self._live_col_meta     = col_meta
                    self._live_numeric_cols = numeric_cols
                    self._live_plot_cols    = list(numeric_cols[:8])
                    self._live_rebuild_col_buttons()
                    self._live_log_append(
                        f"Colonne numeriche: {len(numeric_cols)} — "
                        f"{', '.join(numeric_cols[:12])}")
                    self._live_set_status("CSV pronto.", COLORS["info"])
                self.after(0, _apply)
            except Exception as e:
                self.after(0, lambda: setattr(self, "_live_loading", False))
                self.after(0, self._live_log_append, f"Errore lettura CSV: {e}")
                self.after(0, self._live_set_status,
                           "Errore caricamento CSV.", COLORS["warn"])

        threading.Thread(target=_load, daemon=True).start()


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
            color = palette[i % len(palette)]
            is_sel = col in self._live_plot_cols
            var = tk.BooleanVar(value=is_sel)

            row_f = ctk.CTkFrame(self._live_col_scroll, fg_color="transparent")
            row_f.pack(fill="x", pady=1)

            # pallino colorato
            dot = tk.Canvas(row_f, width=12, height=12,
                            bg=COLORS["surface"], highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=color, outline="")
            dot.pack(side="left", padx=(2, 2), pady=4)

            label = col if len(col) <= 10 else col[:9] + "…"

            def _make_cmd(c=col, v=var):
                def _cmd():
                    if v.get():
                        if c not in self._live_plot_cols:
                            self._live_plot_cols.append(c)
                    else:
                        if len(self._live_plot_cols) > 1 and c in self._live_plot_cols:
                            self._live_plot_cols.remove(c)
                        else:
                            v.set(True)  # mantieni almeno una
                return _cmd

            cb = ctk.CTkCheckBox(
                row_f, text=label, variable=var,
                font=("Segoe UI", 9), text_color=COLORS["text"],
                fg_color=color, hover_color=color,
                checkmark_color="#fff",
                border_color=COLORS["border"],
                width=16, height=16,
                command=_make_cmd(col, var))
            cb.pack(side="left", fill="x", expand=True)
            self._live_col_btns.append(row_f)


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


    # ── start / stop ─────────────────────────────────────────────────────
    def _live_start(self):
        if self._live_running.is_set():
            return
        if self._live_loading:
            messagebox.showinfo("Caricamento", "Attendi il completamento del caricamento CSV.")
            return
        if self._live_thread is not None and self._live_thread.is_alive():
            messagebox.showinfo("Arresto in corso", "Attendi la fine della lettura prima di riavviare.")
            return
        self._live_cancel_poll()
        src = self._live_src_var.get()

        # ── blocca se simulazione CSV senza file caricato ──
        if src == "Simulazione CSV" and not self._live_csv_path:
            messagebox.showwarning(
                "Nessun file",
                "Carica prima un CSV tramite il pulsante «CSV simulazione».")
            return

        # ── reset completo ad ogni avvio ─────────────────────────────────
        self._live_rows.clear()
        self._live_ipc.clear()
        self._live_ipc._needs_full_redraw = True
        # Fix: resetta zoom degli IPC multi al riavvio
        if self._live_multi_mode:
            for ipc, _, __ in self._live_multi_ipcs.values():
                ipc.reset_zoom()
        self._live_last_cols_set = set()
        self._live_dropped = 0  # Fix 4: reset contatore campioni scartati
        self._live_log_box.configure(state="normal")
        self._live_log_box.delete("1.0", "end")
        self._live_log_box.configure(state="disabled")
        self._live_cnt_lbl.configure(text="Campioni: 0  |  In coda: 0")
        self._live_alarm_active.clear()
        self._live_alarm_count = 0
        self._live_alarm_badge.configure(text="")
        # svuota coda residua dal run precedente
        while not self._live_queue.empty():
            try: self._live_queue.get_nowait()
            except _queue.Empty: break

        # svuota coda residua in modo sicuro (Fix race condition)
        try:
            while True:
                self._live_queue.get_nowait()
        except _queue.Empty:
            pass
                
        # 🔄 RESET automatico zoom al PLAY
        self._live_ipc.reset_zoom()
        self._live_ipc.clear_cursors()
        self._live_ipc._needs_full_redraw = True
        self._live_source_snapshot = src
        self._live_stop_event.clear()
        self._live_done_event.clear()
        self._live_worker_error = None
        self._live_total = 0
        self._live_running.set()
        self._live_paused.clear()
        self._live_start_btn.configure(state="disabled")
        self._live_stop_btn.configure(state="normal")
        self._live_pause_btn.configure(state="normal", text="⏸",
                                       fg_color=COLORS["warn"])

        # Fix 4 — leggi StringVar nel thread UI prima di avviare il thread background
        self._live_speed_snapshot = self._live_speed_var.get()

        if src == "Simulazione CSV":
            self._live_sim_random = False
            self._live_thread = threading.Thread(
                target=self._live_worker_run, args=(self._live_sim_thread, ()), daemon=True)
        else:
            port = self._live_port_var.get()
            try:
                baud = int(self._live_baud_var.get())
            except Exception:
                baud = 9600
            self._live_thread = threading.Thread(
                target=self._live_worker_run,
                args=(self._live_serial_thread, (port, baud)), daemon=True)

        self._live_thread.start()
        self._live_set_status("● Acquisizione in corso", COLORS["info"])
        self._live_poll()


    def _live_stop(self):
        self._live_stop_event.set()
        self._live_running.clear()
        self._live_paused.clear()
        self._live_stop_interp_timer()
        self._live_start_btn.configure(state="normal")
        self._live_stop_btn.configure(state="disabled")
        self._live_pause_btn.configure(state="disabled", text="⏸",
                                       fg_color=COLORS["warn"])
        self._live_set_status("● Fermato", COLORS["warn"])

        if self._live_poll_job is None:
            self._live_poll()


    def _live_toggle_pause(self):
        if not self._live_running.is_set():
            return
        if self._live_paused.is_set():
            self._live_paused.clear()
        else:
            self._live_paused.set()
            self._live_stop_interp_timer()
        if self._live_paused.is_set():
            self._live_pause_btn.configure(text="▶",
                                           fg_color=COLORS["info"],
                                           hover_color="#3a9a10")
            self._live_set_status("⏸ In pausa", COLORS["warn"])
        else:
            self._live_pause_btn.configure(text="⏸",
                                           fg_color=COLORS["warn"],
                                           hover_color="#c87d00")
            self._live_set_status("● Acquisizione in corso", COLORS["info"])
            self._live_refresh_plot()


    def _live_clear(self):
        if self._live_thread is not None and self._live_thread.is_alive():
            self._live_stop()
            self.after(50, self._live_clear)
            return
        self._live_cancel_poll()
        self._live_total = 0
        self._live_running.clear()
        self._live_stop_interp_timer()
        self._live_rows.clear()
        self._live_dropped = 0  # B2x: reset contatore scartati ad ogni clear
        try:
            while True: self._live_queue.get_nowait()
        except Exception: pass
        if self._live_multi_mode:
            for ipc, _, __ in self._live_multi_ipcs.values():
                ipc.clear(); ipc._needs_full_redraw = True
        else:
            self._live_ipc.clear()
        self._live_log_box.configure(state="normal")
        self._live_log_box.delete("1.0", "end")
        self._live_log_box.configure(state="disabled")
        self._live_cnt_lbl.configure(text="Campioni: 0  |  In coda: 0")
        self._live_alarm_active.clear()
        self._live_alarm_count = 0
        self._live_alarm_badge.configure(text="")
        self._live_rebuild_alarm_cards()


    # ── thread simulazione CSV ──────────────────────────────────────────
    def _live_worker_run(self, target, args):
        try: target(*args)
        except Exception as e: self._live_worker_error = str(e)
        finally: self._live_done_event.set()


    def _live_wait(self, seconds):
        """Tempo CSV; pause/stop/velocità controllati ogni 20 ms."""
        import time
        remaining = max(0.0, seconds)
        while not self._live_stop_event.is_set():
            if self._live_paused.is_set():
                self._live_stop_event.wait(0.02)
                continue
            if remaining <= 0: return True
            value = self._live_speed_snapshot
            if value == "MAX": return True
            try: speed = max(0.01, float(value.rstrip("x")))
            except (ValueError, TypeError): speed = 1.0
            start = time.monotonic()
            self._live_stop_event.wait(min(0.02, remaining / speed))
            if not self._live_paused.is_set():
                remaining -= (time.monotonic() - start) * speed
        return False


    def _live_enqueue(self, row, lossless):
        while not self._live_stop_event.is_set():
            if lossless and not self._live_wait(0): return False
            try:
                self._live_queue.put(row, timeout=0.02 if lossless else 0)
                return True
            except _queue.Full:
                if not lossless:
                    self._live_dropped += 1
                    return True
        return False


    def _live_cancel_poll(self):
        if self._live_poll_job is not None:
            self.after_cancel(self._live_poll_job)
            self._live_poll_job = None


    def _live_sim_thread(self):
        import time

        def _wait_if_paused():
            self._live_wait(0)

        def _speed_factor():
            # Fix 4: legge solo lo snapshot — mai StringVar dal thread background
            sv = getattr(self, "_live_speed_snapshot", "1x")
            if sv == "MAX":
                return None
            try:
                return float(sv.rstrip("x"))
            except Exception:
                return 1.0

        if getattr(self, "_live_sim_random", True) or not self._live_csv_path:
            # simulazione puramente random
            t = 0.0
            while self._live_running.is_set():
                _wait_if_paused()
                if not self._live_running.is_set():
                    break
                row = {"_sim_t": t,
                       "Temperatura": round(120 + random.gauss(0, 2), 2),
                       "Pressione":   round(5.0  + random.gauss(0, 0.3), 3),
                       "Forza":       round(3000 + random.gauss(0, 150), 1)}
                try:
                    self._live_queue.put_nowait(row)
                except _queue.Full:
                    self._live_dropped = getattr(self, "_live_dropped", 0) + 1
                t += 0.5
                sf = _speed_factor()
                self._live_wait(0.5)
            return

        # ── riproduzione CSV ────────────────────────────────────────────
        try:
            if _is_long_cycle_csv(self._live_csv_path):
                rows, headers, col_meta, numeric_cols, datetime_cols, _, _, _ = \
                    _parse_long_cycle_csv(self._live_csv_path)
                _has_embedded_ts = True
            else:
                rows, headers, col_meta, numeric_cols, datetime_cols, _, _, _ = \
                    parse_universal_csv(self._live_csv_path)
                _has_embedded_ts = False
        except Exception as e:
            self._live_worker_error = str(e)
            return

        if not numeric_cols:
            self._live_worker_error = "Nessuna colonna numerica nel CSV."
            return

        # ── rileva la colonna tempo ─────────────────────────────────────
        _TIME_NAMES = {"time","tempo","t","sec","seconds","s","zeit","temps",
                       "elapsed","elapsed_s","ts","ticks","sample"}
        x_col_dt  = datetime_cols[0] if datetime_cols else None
        x_col_num = None
        if not _has_embedded_ts:
            for h in headers:
                if h.lower().rstrip("_") in _TIME_NAMES:
                    sample = [rows[i].get(h, "") for i in range(min(5, len(rows)))]
                    sample_s = [str(v) for v in sample if v is not None and str(v).strip()]
                    if all(_uc_try_float(v) for v in sample_s):
                        x_col_num = h
                        break

        use_datetime = _has_embedded_ts or (x_col_dt is not None)
        use_num_time = (not use_datetime) and (x_col_num is not None)

        prev_dt  = None
        prev_num = None

        for i, r in enumerate(rows):
            if not self._live_running.is_set():
                break
            _wait_if_paused()
            if not self._live_running.is_set():
                break

            row_out = {}
            for col in numeric_cols:
                v = r.get(col)
                if isinstance(v, float):
                    row_out[col] = v
                else:
                    try:
                        row_out[col] = float(str(v).replace(",", "."))
                    except Exception:
                        row_out[col] = None

            sf = _speed_factor()

            if _has_embedded_ts:
                ts = r.get("_ts")
                if ts:
                    row_out["_ts"] = ts
                    if prev_dt is not None and sf is not None:
                        delta = (ts - prev_dt).total_seconds()
                        if delta > 0:
                            self._live_wait(max(0.0, delta))
                    prev_dt = ts
                else:
                    if sf is not None:
                        self._live_wait(0.1)

            elif use_datetime:
                ts = _uc_parse_dt(r.get(x_col_dt, ""))
                if ts:
                    row_out["_ts"] = ts
                    if prev_dt is not None and sf is not None:
                        delta = (ts - prev_dt).total_seconds()
                        self._live_wait(max(0.0, delta))
                    prev_dt = ts
                else:
                    if sf is not None:
                        self._live_wait(0.1)

            elif use_num_time:
                try:
                    t_now = float(str(r.get(x_col_num, "")).replace(",", "."))
                    row_out["_sim_t"] = t_now
                    if prev_num is not None and sf is not None:
                        delta = t_now - prev_num
                        if delta > 0:
                            self._live_wait(max(0.0, delta))
                    prev_num = t_now
                except Exception:
                    if sf is not None:
                        self._live_wait(0.1)

            else:
                row_out["_sim_i"] = i
                if sf is not None:
                    self._live_wait(1.0)

            if not self._live_enqueue(row_out, lossless=True):
                return


    # ── thread seriale reale ────────────────────────────────────────────
    def _live_serial_thread(self, port, baud):
        if not SERIAL_AVAILABLE:
            self._live_queue.put({"_error": "pyserial non installato."})
            return
        import time
        try:
            ser = serial.Serial(port, baud, timeout=1)
            self.after(0, self._live_log_append, f"Seriale aperta: {port} @ {baud}")
        except Exception as e:
            self._live_queue.put({"_error": f"Errore apertura {port}: {e}"})
            return
        buf = ""
        while self._live_running.is_set():
            try:
                chunk = ser.read(256).decode("utf-8", errors="replace")
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    row = self._live_parse_line(line.strip())
                    if row:
                        try:
                            self._live_queue.put_nowait(row)  # C4: non blocca il thread
                        except _queue.Full:
                            self._live_dropped = getattr(self, "_live_dropped", 0) + 1
            except Exception as e:
                self.after(0, self._live_set_status,
                           f"Errore seriale: {e}", COLORS["warn"])
                time.sleep(0.05)
        try:
            ser.close()
        except Exception:
            pass


    def _live_parse_line(self, line):
        """Parsa una riga CSV o key=val da seriale."""
        if not line:
            return None
        # formato key=val,key=val,...
        if "=" in line:
            row = {}
            for part in line.split(","):
                kv = part.strip().split("=", 1)
                if len(kv) == 2:
                    k, v = kv[0].strip(), kv[1].strip()
                    try:
                        row[k] = float(v)
                    except Exception:
                        row[k] = v
            return row if row else None
        # formato CSV
        parts = line.split(",")
        if len(parts) < 2:
            parts = line.split(";")
        if self._live_headers and len(parts) == len(self._live_headers):
            row = {}
            for h, v in zip(self._live_headers, parts):
                try:
                    row[h] = float(v.strip().replace(",", "."))
                except Exception:
                    row[h] = v.strip()
            return row
        return {"_raw": line}


    # ── polling UI ───────────────────────────────────────────────────────
    def _live_poll(self):
        self._live_cancel_poll()
        if self._live_paused.is_set() and self._live_source_snapshot == "Simulazione CSV":
            self._live_poll_job = self.after(50, self._live_poll)
            return
        drained = 0
        last_row = None
        while drained < 100:  # max 100 campioni per tick per non bloccare la UI
            try:
                row = self._live_queue.get_nowait()
            except _queue.Empty:
                break
            drained += 1
            if "_error" in row:
                self._live_log_append(f"ERRORE: {row['_error']}")
                self._live_worker_error = row["_error"]
                self._live_stop_event.set()
                self._live_running.clear()
                continue
            self._live_total += 1
            self._live_rows.append(row)
            # C2: finestra scorrevole — memoria bounded, non cresce infinitamente
            if len(self._live_rows) > MAX_LIVE_POINTS:
                del self._live_rows[:-MAX_LIVE_POINTS]
            # aggiorna col_meta e plot_cols automaticamente
            for k, v in row.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, (int, float)) and k not in self._live_col_meta:
                    unit, label, col_type = _uc_col_meta(k, ["1.0"])
                    self._live_col_meta[k] = {"unit": unit, "label": label,
                                               "col_type": "numeric"}
                    if k not in self._live_numeric_cols:
                        self._live_numeric_cols.append(k)
                    if len(self._live_plot_cols) < 8 and k not in self._live_plot_cols:
                        self._live_plot_cols.append(k)
            last_row = row
        # una sola riga di log per tick: valori dell'ultimo campione + conteggio
        if drained > 0 and last_row is not None:
            vals = "  ".join(
                f"{k}={v:.3g}" if isinstance(v, float) else f"{k}={v}"
                for k, v in last_row.items() if not k.startswith("_"))
            self._live_log_append(
                f"+{drained}  {vals}", scroll=False)

        if drained > 0:
            self._live_last_poll_draw = getattr(self, "_live_last_poll_draw", 0)
            import time as _t; self._live_last_poll_draw = _t.monotonic()
            dropped = getattr(self, "_live_dropped", 0)
            drop_txt = f"  |  Scartati: {dropped}" if dropped > 0 else ""
            self._live_cnt_lbl.configure(
                text=f"Elaborati: {self._live_total}  |  In vista: {len(self._live_rows)}  |  In coda: {self._live_queue.qsize()}{drop_txt}")
            if set(self._live_numeric_cols) != getattr(self, "_live_last_cols_set", set()):
                self._live_last_cols_set = set(self._live_numeric_cols)
                self._live_rebuild_col_buttons()
            self._live_check_alarms()
            # Fix 2: se interp attiva, il tick a 200ms è già autoritative per il render
            # il poll aggiorna solo i dati, non ridisegna (elimina doppio redraw 2+5 Hz)
            interp_on = (getattr(self, "_live_interp_var", None) and
                         self._live_interp_var.get() and
                         self._live_interp_job is not None)
            if not interp_on and not self._live_paused.is_set():
                self._live_refresh_plot()

        try:
            ms = max(100, int(self._live_rate_var.get()))
        except Exception:
            ms = 500
        if self._live_done_event.is_set() and self._live_queue.empty():
            self._live_running.clear()
            self._live_paused.clear()
            self._live_stop_interp_timer()
            self._live_start_btn.configure(state="normal")
            self._live_stop_btn.configure(state="disabled")
            self._live_pause_btn.configure(state="disabled", text="⏸", fg_color=COLORS["warn"])
            if self._live_worker_error:
                self._live_set_status("Errore riproduzione/acquisizione", COLORS["warn"])
                self._live_log_append(f"ERRORE: {self._live_worker_error}")
                self._live_worker_error = None
            elif not self._live_stop_event.is_set():
                self._live_set_status("Riproduzione completata" if self._live_source_snapshot == "Simulazione CSV" else "Acquisizione terminata", COLORS["info"])
            self._live_refresh_plot()
            return
        if self._live_running.is_set() or (self._live_thread is not None and self._live_thread.is_alive()) or not self._live_queue.empty():
            self._live_poll_job = self.after(ms, self._live_poll)


    def _live_refresh_plot(self):
        if not self._live_rows or not self._live_plot_cols:
            return
        try:
            max_pts = int(self._live_maxpts_var.get())
            if max_pts < 10:
                max_pts = 10
        except Exception:
            max_pts = MAX_LIVE_POINTS
        rows = self._live_rows[-max_pts:]

        x_col = None
        for r in rows[:1]:
            if "_ts" in r:
                x_col = "_ts"
            elif "_sim_t" in r:
                x_col = "_sim_t"
        xs_raw = []
        for i, r in enumerate(rows):
            if x_col == "_ts":
                xs_raw.append(r.get("_ts"))
            elif x_col == "_sim_t":
                xs_raw.append(r.get("_sim_t", i))
            else:
                xs_raw.append(i)

        x_type = "datetime" if x_col == "_ts" else "index"
        series = {}
        for col in self._live_plot_cols:
            vals = []
            for r in rows:
                v = r.get(col)
                vals.append(float(v) if isinstance(v, (int, float)) else None)
            series[col] = vals

        # ── mappa colori fissa basata su _live_numeric_cols (combacia con sidebar) ──
        palette = list(_UC_SERIES_PALETTE)
        colors = {col: palette[i % len(palette)]
                  for i, col in enumerate(self._live_numeric_cols)}

        # ── modalità multi-grafico ─────────────────────────────────────
        if self._live_multi_mode and self._live_multi_ipcs:
            # Fix 3: distribuisci i draw nel tempo (20ms offset ciascuno)
            # invece di eseguirli in sequenza bloccante
            active_entries = [
                (ipc, gc, st)
                for _, (ipc, gc, st) in self._live_multi_ipcs.items()
                if st.get("active") and not st.get("paused")]

            def _draw_one(entries, idx, xs=xs_raw, xt=x_type,
                          cm=self._live_col_meta, cl=colors, rw=rows):
                if idx >= len(entries):
                    return
                ipc, gc, st = entries[idx]
                g_series = {col: [float(r.get(col)) if isinstance(r.get(col),
                            (int, float)) else None for r in rw] for col in gc}
                if g_series:
                    ipc._ranges = [r for r in getattr(self, "_live_alarm_rules", [])
                                   if r.get("col") in gc]
                    ipc.update_live(xs, g_series, xt, cm, colors=cl)
                if idx + 1 < len(entries):
                    self.after(20, lambda i=idx+1: _draw_one(entries, i))

            if active_entries:
                _draw_one(active_entries, 0)
            return

        # ── B: redraw incrementale — no clf, no flash ──────────────────
        # aggiorna bande range solo se le regole sono cambiate
        current_rules = getattr(self, "_live_alarm_rules", [])
        if current_rules != getattr(self, "_live_last_rules_snapshot", None):
            self._live_last_rules_snapshot = list(current_rules)
            self._live_ipc._ranges = current_rules
            self._live_ipc._needs_full_redraw = True
        self._live_ipc.update_live(xs_raw, series, x_type,self._live_col_meta, colors=colors)
        
        # ⚡ AUTO-SCROLL live: finestra scorre automaticamente
        if hasattr(self.master, '_live_running') and self.master._live_running.is_set():
            xs_num = [self._to_num(x) for x in xs_raw if self._to_num(x) is not None]
            if xs_num:
                last_x = max(xs_num)
                xlim = self._live_ipc._ax1.get_xlim()
                width = xlim[1] - xlim[0]
                new_left = max(last_x - width * 0.9, min(xs_num))
                self._live_ipc._ax1.set_xlim(new_left, new_left + width)
                if hasattr(self._live_ipc, '_ax2') and self._live_ipc._ax2: 
                    self._live_ipc._ax2.set_xlim(new_left, new_left + width)
        

        # ── A: avvia/ferma il timer interpolazione in base alla checkbox ─
        if getattr(self, "_live_interp_var", None) and self._live_interp_var.get():
            self._live_start_interp_timer()
        else:
            self._live_stop_interp_timer()


    # ── interpolazione (A) ───────────────────────────────────────────────
    def _live_start_interp_timer(self):
        """Avvia il ticker da 200ms per aggiornare il grafico con punti interpolati."""
        if not self._live_running.is_set() or self._live_paused.is_set(): return
        if self._live_interp_job is not None:
            return  # già attivo
        self._live_interp_tick()


    def _live_stop_interp_timer(self):
        if self._live_interp_job is not None:
            try: self.after_cancel(self._live_interp_job)
            except Exception: pass
            self._live_interp_job = None


    def _live_interp_tick(self):
        """Ogni 200ms aggiunge un punto interpolato. Fix 2: salta se il poll
        ha già ridisegnato negli ultimi 150ms (evita doppio redraw)."""
        if not self._live_running.is_set() or self._live_paused.is_set():
            self._live_interp_job = None
            return
        if not self._live_rows or len(self._live_rows) < 2:
            self._live_interp_job = self.after(200, self._live_interp_tick)
            return

        # Fix 2: se il poll ha ridisegnato di recente, non ridisegnare di nuovo
        import time as _t
        last_poll = getattr(self, "_live_last_poll_draw", 0)
        if (_t.monotonic() - last_poll) < 0.15:
            self._live_interp_job = self.after(200, self._live_interp_tick)
            return

        last   = self._live_rows[-1]
        prev   = self._live_rows[-2]

        # calcola il delta temporale reale tra gli ultimi due campioni
        def _xval(r):
            if "_ts" in r:   return r["_ts"].timestamp()
            if "_sim_t" in r: return r["_sim_t"]
            return None

        x0 = _xval(prev)
        x1 = _xval(last)
        if x0 is None or x1 is None or x1 <= x0:
            self._live_interp_job = self.after(200, self._live_interp_tick)
            return

        # quanto tempo è passato dal secondo punto
        import time as _time
        now = _time.monotonic()
        # stimiamo la posizione "ora" nel tempo del CSV
        try:
            sf_str = getattr(self, "_live_speed_snapshot", "1x")
            sf = 1.0 if sf_str == "MAX" else float(sf_str.rstrip("x"))
        except Exception:
            sf = 1.0

        elapsed_real = 0.2 * sf   # 200ms reali × velocità
        alpha = min(1.0, elapsed_real / (x1 - x0))  # 0..1

        # costruisce una riga interpolata lineare
        interp_row = {}
        for col in self._live_plot_cols:
            v0 = prev.get(col)
            v1 = last.get(col)
            if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
                interp_row[col] = v0 + (v1 - v0) * alpha
            else:
                interp_row[col] = v1

        # x interpolata
        if "_sim_t" in last:
            interp_row["_sim_t"] = x0 + (x1 - x0) * alpha
        elif "_ts" in last:
            from datetime import timedelta
            interp_row["_ts"] = prev["_ts"] + timedelta(seconds=(x1 - x0) * alpha)

        # costruisce serie da mostrare: rows reali + punto interpolato
        try:
            max_pts = int(self._live_maxpts_var.get())
            if max_pts < 10: max_pts = 10
        except Exception:
            max_pts = MAX_LIVE_POINTS
        rows_disp = self._live_rows[-(max_pts - 1):] + [interp_row]

        x_col = "_ts" if "_ts" in last else ("_sim_t" if "_sim_t" in last else None)
        xs_raw = []
        for i, r in enumerate(rows_disp):
            if x_col == "_ts":    xs_raw.append(r.get("_ts"))
            elif x_col == "_sim_t": xs_raw.append(r.get("_sim_t", i))
            else:                 xs_raw.append(i)

        x_type = "datetime" if x_col == "_ts" else "index"
        series = {}
        for col in self._live_plot_cols:
            vals = [float(r.get(col)) if isinstance(r.get(col), (int, float)) else None
                    for r in rows_disp]
            series[col] = vals

        self._live_ipc.update_live(xs_raw, series, x_type, self._live_col_meta)
        self._live_interp_job = self.after(200, self._live_interp_tick)


    def _live_reset_cursors(self):
        """Azzera i cursori A/B e le linee delta dal grafico."""
        self._live_ipc._cur_a = None
        self._live_ipc._cur_b = None
        self._live_ipc._redraw_cursors_ab()
        self._live_ipc._canvas.draw()
        self._live_ipc._bg_cache = self._live_ipc._canvas.copy_from_bbox(
            self._live_ipc._fig.bbox)


    def _live_toggle_markers(self):
        v = self._live_show_pts_var.get()
        self._live_ipc.show_markers = v
        self._live_ipc._needs_full_redraw = True
        # Fix: propaga anche agli IPC multi
        if self._live_multi_mode:
            for ipc, _, __ in self._live_multi_ipcs.values():
                ipc.show_markers = v
                ipc._needs_full_redraw = True
        self._live_refresh_plot()


    def _live_set_status(self, text, color):
        self._live_status_lbl.configure(text=text, text_color=color)


    def _live_log_append(self, text, scroll=True):
        self._live_log_box.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self._live_log_box.insert("end", f"[{ts}] {text}\n")
        # C3: cap a 500 righe — elimina la più vecchia se superato il limite
        if int(self._live_log_box.index("end-1c").split(".")[0]) > 500:
            self._live_log_box.delete("1.0", "2.0")
        if scroll:
            self._live_log_box.see("end")
        self._live_log_box.configure(state="disabled")


    def _live_export_csv(self):
        if not self._live_rows:
            messagebox.showinfo("Esporta", "Nessun dato da esportare.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Salva dati live come CSV")
        if not path:
            return
        # raccoglie tutte le chiavi non private (O(n) con dict per preservare l'ordine)
        seen = {}
        for r in self._live_rows:
            for k in r:
                if not k.startswith("_"):
                    seen.setdefault(k, None)
        all_keys = list(seen.keys())
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
                writer.writeheader()
                for r in self._live_rows:
                    writer.writerow({k: r.get(k, "") for k in all_keys})
            messagebox.showinfo("Esporta", f"Salvato: {path}")
        except Exception as e:
            messagebox.showerror("Errore", str(e))
