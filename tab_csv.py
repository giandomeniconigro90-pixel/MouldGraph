# -*- coding: utf-8 -*-
"""
tab_csv.py  —  CsvMixin
Contiene _build_csv_tab e tutti i metodi _csv_* estratti da app_main.py.
Importato come mixin da LogAnalyzerApp in app_main.py.
"""
import os
import csv
import math
import statistics
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from colors import COLORS
from plot_canvas import InteractivePlotCanvas
from charts import _isolate_scroll
from csv_parser import parse_universal_csv

_UC_SERIES_PALETTE = [
    "#e5672c", "#3f51b5", "#29b6f6", "#66bb6a",
    "#9c27b0", "#ff9800", "#e7b73b", "#607d8b",
    "#f44322", "#00bcd4", "#8bc34a", "#ff5722",
]

_ANOMALY_SIGMA = 2.5


class CsvMixin:
    """Mixin con tutta la logica della tab 'Dati CSV'."""

    # ------------------------------------------------------------------
    # BUILD TAB
    # ------------------------------------------------------------------
    def _build_csv_tab(self, parent):
        # ---- stato interno ----
        self._csv_rows         = []
        self._csv_rows2        = []          # secondo CSV confronto
        self._csv_col_meta     = {}
        self._csv_col_meta2    = {}
        self._csv_numeric_cols = []
        self._csv_numeric_cols2= []
        self._csv_datetime_cols= []
        self._csv_binary_cols  = []
        self._csv_headers      = []
        self._csv_sep          = ","
        self._csv_enc          = "utf-8"
        self._csv_filepath     = None
        self._csv_filepath2    = None
        self._csv_x_col_var    = tk.StringVar(value="-")
        self._csv_y_vars       = {}
        self._csv_y2_vars      = {}
        self._csv_y_vars2      = {}
        self._csv_colors       = {}
        self._csv_colors2      = {}
        self._csv_show_anomaly = tk.BooleanVar(value=True)
        self._csv_compare_mode = False
        self._csv_plot_type    = tk.StringVar(value="Linea")
        self._csv_smooth_var   = tk.BooleanVar(value=False)
        self._csv_show_pts_var = tk.BooleanVar(value=True)
        self._csv_norm_var     = tk.BooleanVar(value=False)
        self._csv_grid_var     = tk.BooleanVar(value=True)
        self._csv_legend_var   = tk.BooleanVar(value=True)
        self._csv_col_btns     = []
        self._csv_col_btns2    = []
        self._csv_x2_col_var   = tk.StringVar(value="-")

        # ---- layout principale ----
        toolbar_wrap = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        toolbar_wrap.pack(fill="x", side="top", padx=6, pady=(4, 2))

        # riga 1: file CSV
        row1 = ctk.CTkFrame(toolbar_wrap, fg_color=COLORS["surface"], corner_radius=8)
        row1.pack(fill="x", pady=(0, 3))
        ctk.CTkButton(
            row1, text="Apri CSV", width=90, height=28,
            fg_color=COLORS["accent"], hover_color="#5a52e0",
            text_color=COLORS["text"], font=("Segoe UI", 10),
            command=self._csv_open).pack(side="left", padx=(10, 4), pady=6)
        self._csv_lbl = ctk.CTkLabel(
            row1, text="Nessun file",
            font=("Segoe UI", 9), text_color=COLORS["text2"])
        self._csv_lbl.pack(side="left", padx=4)

        ctk.CTkButton(
            row1, text="+ Confronto", width=90, height=28,
            fg_color=COLORS["surface2"], hover_color=COLORS["accent"],
            text_color=COLORS["text"], font=("Segoe UI", 10),
            command=self._csv_open2).pack(side="left", padx=(20, 4), pady=6)
        self._csv_lbl2 = ctk.CTkLabel(
            row1, text="",
            font=("Segoe UI", 9), text_color=COLORS["text2"])
        self._csv_lbl2.pack(side="left", padx=4)

        # riga 2: opzioni plot
        row2 = ctk.CTkFrame(toolbar_wrap, fg_color=COLORS["surface"], corner_radius=8)
        row2.pack(fill="x", pady=(0, 3))

        LBL = dict(font=("Segoe UI", 9), text_color=COLORS["text2"])
        CHK = dict(font=("Segoe UI", 9), text_color=COLORS["text"],
                   fg_color=COLORS["accent"], hover_color="#5a52e0",
                   checkmark_color=COLORS["text"],
                   border_color=COLORS["border"], width=16, height=16)
        BTN = dict(height=28, font=("Segoe UI", 9),
                   text_color=COLORS["text"],
                   fg_color=COLORS["surface2"], hover_color=COLORS["border"])

        ctk.CTkLabel(row2, text="Tipo", **LBL).pack(side="left", padx=(10, 2), pady=6)
        ctk.CTkOptionMenu(
            row2, variable=self._csv_plot_type,
            values=["Linea", "Scatter", "Barre", "Istogramma"],
            width=100, height=26, fg_color=COLORS["surface2"],
            button_color=COLORS["accent"], text_color=COLORS["text"],
            command=lambda _: self._csv_plot()).pack(side="left", padx=(0, 8), pady=6)

        ctk.CTkCheckBox(row2, text="Smooth", variable=self._csv_smooth_var,
                        command=self._csv_plot, **CHK).pack(side="left", padx=4, pady=6)
        ctk.CTkCheckBox(row2, text="Punti", variable=self._csv_show_pts_var,
                        command=self._csv_plot, **CHK).pack(side="left", padx=4, pady=6)
        ctk.CTkCheckBox(row2, text="Normalizza", variable=self._csv_norm_var,
                        command=self._csv_plot, **CHK).pack(side="left", padx=4, pady=6)
        ctk.CTkCheckBox(row2, text="Griglia", variable=self._csv_grid_var,
                        command=self._csv_plot, **CHK).pack(side="left", padx=4, pady=6)
        ctk.CTkCheckBox(row2, text="Legenda", variable=self._csv_legend_var,
                        command=self._csv_plot, **CHK).pack(side="left", padx=4, pady=6)
        ctk.CTkCheckBox(row2, text="Anomalie", variable=self._csv_show_anomaly,
                        command=self._csv_plot, **CHK).pack(side="left", padx=4, pady=6)

        ctk.CTkButton(row2, text="↓ PNG",  width=58, **BTN,
                      command=self._csv_export_png).pack(side="left", padx=(16, 3), pady=6)
        ctk.CTkButton(row2, text="↓ PDF",  width=58, **BTN,
                      command=self._csv_export_pdf).pack(side="left", padx=3, pady=6)
        ctk.CTkButton(row2, text="Multi",  width=58, **BTN,
                      command=self._csv_export_multi).pack(side="left", padx=3, pady=6)
        ctk.CTkButton(row2, text="↺",      width=40, **BTN,
                      command=self._csv_reset_cursors).pack(side="left", padx=3, pady=6)
        ctk.CTkButton(row2, text="Stat",   width=50, **BTN,
                      command=self._csv_show_stats).pack(side="left", padx=3, pady=6)
        ctk.CTkButton(row2, text="Anomalie", width=72, **BTN,
                      command=self._csv_show_anomalies_window).pack(side="left", padx=3, pady=6)

        # body: sidebar Y + area grafico
        body = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        # sidebar sinistra: asse X e colonne Y
        left_panel = ctk.CTkFrame(body, fg_color=COLORS["surface"],
                                   corner_radius=8, width=160)
        left_panel.pack(side="left", fill="y", padx=(0, 4), pady=0)
        left_panel.pack_propagate(False)

        ctk.CTkLabel(left_panel, text="Asse X",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(8, 2))
        self._csv_x_menu = ctk.CTkOptionMenu(
            left_panel, variable=self._csv_x_col_var,
            values=["-"],
            width=144, height=26, fg_color=COLORS["surface2"],
            button_color=COLORS["accent"], text_color=COLORS["text"],
            command=lambda _: self._csv_plot())
        self._csv_x_menu.pack(padx=8, pady=(0, 6))

        ctk.CTkLabel(left_panel, text="Colonne Y",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(4, 2))
        btn_row = ctk.CTkFrame(left_panel, fg_color="transparent")
        btn_row.pack(anchor="w", padx=6, pady=(0, 4))
        ctk.CTkButton(btn_row, text="☑", width=36, height=18,
                      fg_color=COLORS["surface2"], hover_color=COLORS["accent"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      corner_radius=4,
                      command=self._csv_sel_all).pack(side="left", padx=(0, 2))
        ctk.CTkButton(btn_row, text="☒", width=36, height=18,
                      fg_color=COLORS["surface2"], hover_color=COLORS["error"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      corner_radius=4,
                      command=self._csv_sel_none).pack(side="left")
        self._csv_col_scroll = ctk.CTkScrollableFrame(
            left_panel, fg_color="transparent",
            orientation="vertical", corner_radius=0)
        self._csv_col_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        _isolate_scroll(self._csv_col_scroll)

        # area centrale: grafico
        center = ctk.CTkFrame(body, fg_color=COLORS["bg"])
        center.pack(side="left", fill="both", expand=True)

        self._csv_ipc = InteractivePlotCanvas(center, height=4.2)
        self._csv_ipc.get_frame().pack(fill="both", expand=True)

        # sidebar destra: anomalie mini-panel
        right_panel = ctk.CTkFrame(body, fg_color=COLORS["surface"],
                                    corner_radius=8, width=190)
        right_panel.pack(side="left", fill="y", padx=(4, 0), pady=0)
        right_panel.pack_propagate(False)
        ctk.CTkLabel(right_panel, text="Anomalie",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=8, pady=(8, 2))
        self._csv_anomaly_scroll = ctk.CTkScrollableFrame(
            right_panel, fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        self._csv_anomaly_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        self._csv_anomaly_label = ctk.CTkLabel(
            self._csv_anomaly_scroll, text="Nessun dato",
            font=("Segoe UI", 9), text_color=COLORS["text2"])
        self._csv_anomaly_label.pack(anchor="w", padx=4, pady=4)

    # ------------------------------------------------------------------
    # OPEN CSV
    # ------------------------------------------------------------------
    def _csv_open(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv *.CSV"), ("All files", "*.*")])
        if not path:
            return
        self._csv_filepath = path
        self._csv_lbl.configure(text=os.path.basename(path),
                                 text_color=COLORS["text"])
        self._csv_compare_mode = False
        self._csv_lbl2.configure(text="", text_color=COLORS["text2"])
        self._csv_rows2.clear()
        try:
            rows, headers, sep, enc, col_meta = parse_universal_csv(path)
            self._csv_rows    = rows
            self._csv_headers = headers
            self._csv_sep     = sep
            self._csv_enc     = enc
            self._csv_col_meta = col_meta
            self._csv_numeric_cols  = [
                h for h in headers if col_meta.get(h, {}).get("coltype") == "numeric"]
            self._csv_datetime_cols = [
                h for h in headers if col_meta.get(h, {}).get("coltype") == "datetime"]
            self._csv_binary_cols   = [
                h for h in headers if col_meta.get(h, {}).get("coltype") == "binary"]
            # X default: prima colonna datetime o prima numerica
            xcol = (self._csv_datetime_cols[0] if self._csv_datetime_cols
                    else (self._csv_numeric_cols[0] if self._csv_numeric_cols else "-"))
            self._csv_x_col_var.set(xcol)
            x_opts = ["-"] + headers
            self._csv_x_menu.configure(values=x_opts)
            self._csv_colors = {
                col: _UC_SERIES_PALETTE[i % len(_UC_SERIES_PALETTE)]
                for i, col in enumerate(self._csv_numeric_cols)
            }
            self._csv_y_vars  = {}
            self._csv_y2_vars = {}
            self._csv_rebuild_col_buttons()
            self.set_status(
                f"CSV: {os.path.basename(path)} | "
                f"{len(rows)} righe | sep='{sep}' | enc={enc} | "
                f"{len(self._csv_numeric_cols)} num | "
                f"{len(self._csv_datetime_cols)} datetime")
            self._csv_plot()
        except Exception as e:
            messagebox.showerror("Errore CSV", str(e))

    def _csv_open2(self):
        """Apre secondo CSV per confronto sovrapposto."""
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv *.CSV"), ("All files", "*.*")])
        if not path:
            return
        self._csv_filepath2 = path
        self._csv_lbl2.configure(text=os.path.basename(path),
                                  text_color=COLORS["accent2"])
        self._csv_compare_mode = True
        try:
            rows2, headers2, _, _, col_meta2 = parse_universal_csv(path)
            self._csv_rows2        = rows2
            self._csv_col_meta2    = col_meta2
            self._csv_numeric_cols2 = [
                h for h in headers2
                if col_meta2.get(h, {}).get("coltype") == "numeric"
            ]
            self._csv_colors2 = {
                col: _UC_SERIES_PALETTE[(i + 6) % len(_UC_SERIES_PALETTE)]
                for i, col in enumerate(self._csv_numeric_cols2)
            }
            self._csv_y_vars2 = {}
            self.set_status(
                f"CSV2: {os.path.basename(path)} | "
                f"{len(rows2)} righe | "
                f"{len(self._csv_numeric_cols2)} colonne numeriche")
            self._csv_plot()
        except Exception as e:
            messagebox.showerror("Errore CSV confronto", str(e))

    # ------------------------------------------------------------------
    # REBUILD COLUMN BUTTONS
    # ------------------------------------------------------------------
    def _csv_rebuild_col_buttons(self):
        for w in self._csv_col_btns:
            try: w.destroy()
            except Exception: pass
        self._csv_col_btns.clear()
        for w in self._csv_col_scroll.winfo_children():
            try: w.destroy()
            except Exception: pass

        for i, col in enumerate(self._csv_numeric_cols):
            color = self._csv_colors.get(col, "#aaaaaa")
            is_sel = i < 6
            v_y  = tk.BooleanVar(value=is_sel)
            v_y2 = tk.BooleanVar(value=False)
            self._csv_y_vars[col]  = v_y
            self._csv_y2_vars[col] = v_y2

            rowf = ctk.CTkFrame(self._csv_col_scroll, fg_color="transparent")
            rowf.pack(fill="x", pady=1)

            dot = tk.Canvas(rowf, width=10, height=10,
                            bg=COLORS["surface"], highlightthickness=0)
            dot.create_oval(1, 1, 9, 9, fill=color, outline="")
            dot.pack(side="left", padx=(2, 2), pady=3)

            label = col if len(col) <= 10 else col[:9] + "…"

            def _make_cmd(c=col):
                def cmd():
                    self._csv_plot()
                return cmd

            ctk.CTkCheckBox(
                rowf, text=label, variable=v_y,
                font=("Segoe UI", 9), text_color=COLORS["text"],
                fg_color=color, hover_color=color,
                checkmark_color="#fff", border_color=COLORS["border"],
                width=16, height=16,
                command=_make_cmd(col)
            ).pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(
                rowf, text="Y2",
                font=("Segoe UI", 8), text_color=COLORS["text2"],
                width=20
            ).pack(side="left")

            ctk.CTkCheckBox(
                rowf, text="", variable=v_y2,
                fg_color="#ff9800", hover_color="#ff9800",
                checkmark_color="#fff", border_color=COLORS["border"],
                width=14, height=14,
                command=_make_cmd(col)
            ).pack(side="left", padx=(0, 4))

            self._csv_col_btns.append(rowf)

    def _csv_sel_all(self):
        for v in self._csv_y_vars.values():
            v.set(True)
        self._csv_plot()

    def _csv_sel_none(self):
        first = True
        for v in self._csv_y_vars.values():
            v.set(first)
            first = False
        self._csv_plot()

    # ------------------------------------------------------------------
    # PLOT
    # ------------------------------------------------------------------
    def _csv_plot(self):
        if not self._csv_rows:
            return

        xcol  = self._csv_x_col_var.get()
        y_cols  = [c for c, v in self._csv_y_vars.items()  if v.get()]
        y2_cols = [c for c, v in self._csv_y2_vars.items() if v.get()]

        if not y_cols:
            return

        rows   = self._csv_rows
        xtype  = ("datetime"
                  if xcol != "-"
                  and self._csv_col_meta.get(xcol, {}).get("coltype") == "datetime"
                  else "index")

        if xcol == "-" or xcol not in self._csv_col_meta:
            xsraw = list(range(len(rows)))
        else:
            xsraw = [r.get(xcol) for r in rows]

        series = {}
        for col in y_cols:
            vals = [r.get(col) for r in rows]
            if self._csv_norm_var.get():
                nums = [v for v in vals if isinstance(v, (int, float)) and v is not None]
                if nums:
                    mn, mx = min(nums), max(nums)
                    rng = mx - mn if mx != mn else 1
                    vals = [(v - mn) / rng
                            if isinstance(v, (int, float)) and v is not None
                            else None for v in vals]
            series[col] = vals

        series2 = None
        if self._csv_compare_mode and self._csv_rows2:
            y2c = [c for c, v in self._csv_y_vars2.items() if v.get()]
            if not y2c:
                y2c = self._csv_numeric_cols2[:4]
            xcol2 = self._csv_x2_col_var.get()
            xsraw2 = list(range(len(self._csv_rows2)))
            if xcol2 and xcol2 != "-":
                xsraw2 = [r.get(xcol2) for r in self._csv_rows2]
            series2 = {
                col: [r.get(col) for r in self._csv_rows2]
                for col in y2c
            }

        # anomalie
        anomaly_xs = []
        anomaly_ys = []
        anomaly_cols = []
        if self._csv_show_anomaly.get():
            for col in y_cols:
                vals_num = [
                    (i, v) for i, v in enumerate(
                        r.get(col) for r in rows
                    ) if isinstance(v, (int, float)) and v is not None
                ]
                if len(vals_num) < 4:
                    continue
                ys = [v for _, v in vals_num]
                try:
                    mu  = statistics.mean(ys)
                    sig = statistics.stdev(ys)
                except Exception:
                    continue
                if sig == 0:
                    continue
                for idx, v in vals_num:
                    if abs(v - mu) > _ANOMALY_SIGMA * sig:
                        ax = xsraw[idx] if idx < len(xsraw) else idx
                        anomaly_xs.append(ax)
                        anomaly_ys.append(v)
                        anomaly_cols.append(col)

        self._csv_ipc.plot_universal(
            xsraw, series,
            xtype=xtype,
            col_meta=self._csv_col_meta,
            colors=self._csv_colors,
            y2_cols=y2_cols,
            plot_type=self._csv_plot_type.get(),
            smooth=self._csv_smooth_var.get(),
            show_markers=self._csv_show_pts_var.get(),
            show_grid=self._csv_grid_var.get(),
            show_legend=self._csv_legend_var.get(),
            anomaly_xs=anomaly_xs,
            anomaly_ys=anomaly_ys,
            series2=series2,
            xsraw2=(xsraw2 if series2 is not None else None),
            colors2=self._csv_colors2,
        )

        # aggiorna mini-panel anomalie
        self._csv_update_anomaly_panel(anomaly_cols, anomaly_xs, anomaly_ys)

    def _csv_update_anomaly_panel(self, cols, xs, ys):
        for w in self._csv_anomaly_scroll.winfo_children():
            try: w.destroy()
            except Exception: pass
        if not cols:
            ctk.CTkLabel(
                self._csv_anomaly_scroll, text="Nessuna anomalia",
                font=("Segoe UI", 9), text_color=COLORS["text2"]
            ).pack(anchor="w", padx=4, pady=4)
            return
        for col, x, y in zip(cols, xs, ys):
            card = ctk.CTkFrame(self._csv_anomaly_scroll,
                                fg_color=COLORS["surface2"], corner_radius=5)
            card.pack(fill="x", padx=2, pady=1)
            ctk.CTkLabel(card, text=f"{col}",
                         font=("Segoe UI", 8, "bold"),
                         text_color=COLORS["warn"]).pack(anchor="w", padx=6, pady=(3, 0))
            ctk.CTkLabel(card, text=f"x={x!r:.8}  y={y:.4g}",
                         font=("Segoe UI", 8),
                         text_color=COLORS["text2"]).pack(anchor="w", padx=6, pady=(0, 3))

    # ------------------------------------------------------------------
    # RESET CURSORI
    # ------------------------------------------------------------------
    def _csv_reset_cursors(self):
        self._csv_ipc.clear_cursors()

    # ------------------------------------------------------------------
    # EXPORT PNG / PDF / MULTI
    # ------------------------------------------------------------------
    def _csv_export_png(self):
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"csv_{ts}.png",
            filetypes=[("PNG", "*.png")])
        if not path:
            return
        self._csv_ipc.export_png(path)
        self.set_status(f"PNG salvato: {os.path.basename(path)}")

    def _csv_export_pdf(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato CSV caricato.")
            return
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"csv_{ts}.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        self._csv_ipc.export_pdf(path)
        self.set_status(f"PDF salvato: {os.path.basename(path)}")

    def _csv_export_multi(self):
        """Esporta ogni serie Y selezionata come grafico separato in un PDF o PNG."""
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato CSV caricato.")
            return
        y_cols = [c for c, v in self._csv_y_vars.items() if v.get()]
        if not y_cols:
            messagebox.showwarning("Attenzione", "Seleziona almeno una colonna Y.")
            return

        win = tk.Toplevel(self)
        win.title("Esporta multi-grafico CSV")
        win.configure(bg=COLORS["surface"])
        win.geometry("320x340")
        win.resizable(False, False)

        ctk.CTkLabel(win, text="Colonne da esportare",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 4))
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent", height=160)
        scroll.pack(fill="x", padx=16, pady=(0, 8))
        vars_ = {}
        for col in y_cols:
            v = tk.BooleanVar(value=True)
            vars_[col] = v
            ctk.CTkCheckBox(scroll, text=col, variable=v,
                            font=("Segoe UI", 10), text_color=COLORS["text"],
                            fg_color=COLORS["accent"], hover_color="#5a52e0",
                            checkmark_color=COLORS["text"],
                            border_color=COLORS["border"]).pack(anchor="w", pady=2)

        layout_var = ctk.StringVar(value="Verticale")
        ctk.CTkLabel(win, text="Layout",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]
                     ).pack(anchor="w", padx=20, pady=(0, 2))
        ctk.CTkOptionMenu(win, variable=layout_var,
                          values=["Verticale", "Griglia 2 colonne"],
                          width=200, fg_color=COLORS["surface2"],
                          button_color=COLORS["accent"],
                          text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(0, 10))

        for fmt in ["png", "pdf"]:
            def _do(fmt=fmt):
                sel = [c for c, v in vars_.items() if v.get()]
                if not sel:
                    messagebox.showwarning("Selezione", "Seleziona almeno una colonna.")
                    return
                ext = ".png" if fmt == "png" else ".pdf"
                p = filedialog.asksaveasfilename(
                    defaultextension=ext,
                    filetypes=[(fmt.upper(), f"*{ext}")],
                    initialfile=f"csv_multi{ext}")
                if not p:
                    return
                win.destroy()
                self._csv_multi_render(sel, p, fmt, layout_var.get())
            ctk.CTkButton(win, text=f"Esporta {fmt.upper()}",
                          width=200, height=32,
                          fg_color=COLORS["accent"], hover_color="#5a52e0",
                          text_color=COLORS["text"],
                          command=_do).pack(pady=(0, 6))

    def _csv_multi_render(self, selected, path, fmt, layout):
        xcol  = self._csv_x_col_var.get()
        xtype = ("datetime"
                 if xcol != "-"
                 and self._csv_col_meta.get(xcol, {}).get("coltype") == "datetime"
                 else "index")
        rows  = self._csv_rows
        if xcol == "-" or xcol not in self._csv_col_meta:
            xsraw = list(range(len(rows)))
        else:
            xsraw = [r.get(xcol) for r in rows]

        n = len(selected)
        ncols = 2 if layout == "Griglia 2 colonne" else 1
        nrows = (n + ncols - 1) // ncols
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

        for idx, col in enumerate(selected):
            if idx >= len(axes):
                break
            ax = axes[idx]
            ax.set_facecolor("#252535")
            ax.set_title(col, color="#a0a0c0", fontsize=10, pad=4)
            for sp in ax.spines.values():
                sp.set_edgecolor("#3a3a5c")
            ax.tick_params(colors="#a0a0c0", labelsize=7)
            ax.grid(True, color="#3a3a5c", linewidth=0.4,
                    linestyle="--", alpha=0.6)
            vals = [r.get(col) for r in rows]
            xf   = [x for x, y in zip(xsraw, vals) if y is not None]
            yf   = [y for y in vals if y is not None]
            if xf:
                color = self._csv_colors.get(col, "#ffffff")
                ax.plot(xf, yf, color=color, linewidth=1.2, label=col)
                ax.legend(fontsize=7, loc="upper left",
                          facecolor="#252535", labelcolor="#c0c0e0",
                          edgecolor="#3a3a5c")

        for j in range(n, len(axes)):
            axes[j].set_visible(False)

        fig.tight_layout(pad=1.5)
        if fmt == "pdf":
            with PdfPages(path) as pp:
                pp.savefig(fig, bbox_inches="tight")
        else:
            fig.savefig(path, dpi=150, bbox_inches="tight",
                        facecolor=fig.get_facecolor())
        plt.close(fig)
        self.set_status(f"Multi-export CSV salvato: {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # STATISTICHE
    # ------------------------------------------------------------------
    def _csv_show_stats(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato CSV caricato.")
            return
        y_cols = [c for c, v in self._csv_y_vars.items() if v.get()]
        if not y_cols:
            y_cols = self._csv_numeric_cols
        win = tk.Toplevel(self)
        win.title("Statistiche CSV")
        win.configure(bg=COLORS["surface"])
        win.geometry("520x480")
        txt = ctk.CTkTextbox(
            win, font=("Courier New", 10),
            fg_color=COLORS["surface"], text_color=COLORS["text"],
            border_width=0)
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.configure(state="normal")
        header = f"{'COLONNA':<20} {'MIN':>10} {'MAX':>10} {'MEDIA':>10} {'STD':>10} {'N':>6}\n"
        txt.insert("end", header)
        txt.insert("end", "-" * 70 + "\n")
        for col in y_cols:
            vals = [
                r.get(col) for r in self._csv_rows
                if isinstance(r.get(col), (int, float)) and r.get(col) is not None
            ]
            if not vals:
                continue
            try:
                mu  = statistics.mean(vals)
                sig = statistics.stdev(vals) if len(vals) > 1 else 0.0
                mn  = min(vals)
                mx  = max(vals)
                txt.insert(
                    "end",
                    f"{col:<20} {mn:>10.4g} {mx:>10.4g} "
                    f"{mu:>10.4g} {sig:>10.4g} {len(vals):>6}\n")
            except Exception:
                pass
        txt.configure(state="disabled")

    # ------------------------------------------------------------------
    # FINESTRA ANOMALIE
    # ------------------------------------------------------------------
    def _csv_show_anomalies_window(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato CSV caricato.")
            return
        y_cols = [c for c, v in self._csv_y_vars.items() if v.get()]
        if not y_cols:
            y_cols = self._csv_numeric_cols
        xcol  = self._csv_x_col_var.get()
        rows  = self._csv_rows
        xsraw = (list(range(len(rows)))
                 if xcol == "-" or xcol not in self._csv_col_meta
                 else [r.get(xcol) for r in rows])

        anomalies = []
        for col in y_cols:
            vals_num = [
                (i, v)
                for i, v in enumerate(r.get(col) for r in rows)
                if isinstance(v, (int, float)) and v is not None
            ]
            if len(vals_num) < 4:
                continue
            ys = [v for _, v in vals_num]
            try:
                mu  = statistics.mean(ys)
                sig = statistics.stdev(ys)
            except Exception:
                continue
            if sig == 0:
                continue
            for idx, v in vals_num:
                if abs(v - mu) > _ANOMALY_SIGMA * sig:
                    anomalies.append({
                        "col": col,
                        "x":   xsraw[idx] if idx < len(xsraw) else idx,
                        "y":   v,
                        "dev": (v - mu) / sig
                    })

        win = tk.Toplevel(self)
        win.title("Anomalie CSV")
        win.configure(bg=COLORS["surface"])
        win.geometry("560x400")
        txt = ctk.CTkTextbox(
            win, font=("Courier New", 10),
            fg_color=COLORS["surface"], text_color=COLORS["text"],
            border_width=0)
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.configure(state="normal")
        if not anomalies:
            txt.insert("end", "Nessuna anomalia rilevata (soglia 2.5σ).\n")
        else:
            header = f"{'COLONNA':<18} {'X':>20} {'VALORE':>12} {'DEVIAZ(σ)':>12}\n"
            txt.insert("end", header)
            txt.insert("end", "-" * 66 + "\n")
            for a in sorted(anomalies, key=lambda x: -abs(x["dev"])):
                txt.insert(
                    "end",
                    f"{a['col']:<18} {str(a['x'])[:20]:>20} "
                    f"{a['y']:>12.4g} {a['dev']:>12.2f}σ\n")
        txt.configure(state="disabled")
