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
        self._csv_from_var     = tk.StringVar()
        self._csv_to_var       = tk.StringVar()

        # ---- toolbar ----
        tb = ctk.CTkFrame(parent, fg_color=COLORS["surface"],
                          corner_radius=8, height=44)
        tb.pack(fill="x", pady=(0, 6))
        tb.pack_propagate(False)

        ctk.CTkButton(
            tb, text="Apri CSV", width=100, height=30,
            fg_color=COLORS["accent"], hover_color="#5a52e0",
            text_color=COLORS["text"],
            command=self._csv_open
        ).pack(side="left", padx=10, pady=7)

        self._csv_info_lbl = ctk.CTkLabel(
            tb, text="Nessun file caricato",
            font=("Segoe UI", 11), text_color=COLORS["text2"])
        self._csv_info_lbl.pack(side="left", padx=8)

        for txt, cmd, fg in [
            ("Export PDF",     self._csv_export_pdf,     "#7c3aed"),
            ("Export PNG",     self._csv_export_png,     COLORS["surface2"]),
            ("Export Report",  self._csv_export_report,  COLORS["surface2"]),
            ("Reset Zoom",     self._csv_reset_zoom,     COLORS["surface2"]),
            ("Confronta CSV",  self._csv_open_compare,   COLORS["surface2"]),
        ]:
            ctk.CTkButton(
                tb, text=txt, width=115, height=30,
                fg_color=fg, hover_color=COLORS["border"],
                text_color=COLORS["text"], command=cmd
            ).pack(side="right", padx=4, pady=7)

        # ---- body ----
        body = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        body.pack(fill="both", expand=True)

        # colonna sinistra: sidebar controlli
        lw = ctk.CTkFrame(body, fg_color=COLORS["bg"], width=294)
        lw.pack(side="left", fill="y", padx=(0, 6))
        lw.pack_propagate(False)
        left = ctk.CTkScrollableFrame(
            lw, fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        left.pack(fill="both", expand=True)
        _isolate_scroll(left)

        # Asse X
        self._sec(left, "Asse X")
        self._csv_x_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_x_card.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(self._csv_x_card, text="Colonna X",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=10, pady=(8, 2))
        self._csv_x_col_menu = ctk.CTkOptionMenu(
            self._csv_x_card, variable=self._csv_x_col_var,
            values=["-"], width=256,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"],
            command=self._csv_on_x_col_change)
        self._csv_x_col_menu.pack(padx=10, pady=(0, 6))

        # Filtro temporale (visibile solo se X è datetime)
        self._csv_t_filter_frame = ctk.CTkFrame(self._csv_x_card, fg_color="transparent")
        ctk.CTkLabel(self._csv_t_filter_frame, text="Filtra intervallo",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=10, pady=(2, 2))
        tfrow = ctk.CTkFrame(self._csv_t_filter_frame, fg_color="transparent")
        tfrow.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkLabel(tfrow, text="Dal", font=("Segoe UI", 9),
                     text_color=COLORS["text2"]).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(tfrow, textvariable=self._csv_from_var,
                     placeholder_text="HH:MM:SS", width=80, height=24,
                     fg_color=COLORS["surface2"],
                     text_color=COLORS["text"]).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(tfrow, text="Al", font=("Segoe UI", 9),
                     text_color=COLORS["text2"]).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(tfrow, textvariable=self._csv_to_var,
                     placeholder_text="HH:MM:SS", width=80, height=24,
                     fg_color=COLORS["surface2"],
                     text_color=COLORS["text"]).pack(side="left", padx=(0, 6))
        ctk.CTkButton(tfrow, text="↻", width=28, height=24,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 10),
                      command=self._csv_refresh_plot).pack(side="left")

        # Serie Y
        self._sec(left, "Serie Y")
        self._csv_y_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_y_card.pack(fill="x", pady=(0, 4))
        btn_row_y = ctk.CTkFrame(self._csv_y_card, fg_color="transparent")
        btn_row_y.pack(anchor="w", padx=8, pady=(6, 2))
        ctk.CTkButton(btn_row_y, text="☑", width=36, height=18,
                      fg_color=COLORS["surface2"], hover_color=COLORS["accent"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      corner_radius=4,
                      command=self._csv_sel_all_y).pack(side="left", padx=(0, 2))
        ctk.CTkButton(btn_row_y, text="☒", width=36, height=18,
                      fg_color=COLORS["surface2"], hover_color=COLORS["error"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      corner_radius=4,
                      command=self._csv_sel_none_y).pack(side="left")
        self._csv_y_scroll = ctk.CTkScrollableFrame(
            self._csv_y_card, fg_color="transparent",
            orientation="vertical", corner_radius=0, height=160)
        self._csv_y_scroll.pack(fill="x", padx=4, pady=(0, 6))
        _isolate_scroll(self._csv_y_scroll)

        # Serie Y2
        self._sec(left, "Asse Y2 (destra)")
        self._csv_y2_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_y2_card.pack(fill="x", pady=(0, 4))
        self._csv_y2_scroll = ctk.CTkScrollableFrame(
            self._csv_y2_card, fg_color="transparent",
            orientation="vertical", corner_radius=0, height=100)
        self._csv_y2_scroll.pack(fill="x", padx=4, pady=6)
        _isolate_scroll(self._csv_y2_scroll)

        # Statistiche
        self._sec(left, "Statistiche")
        self._csv_stats_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._csv_stats_container.pack(fill="x", pady=(0, 8))

        # Anomalie
        self._sec(left, "Anomalie rilevate")
        self._csv_anomaly_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        # pack rimandato: appare solo se ci sono anomalie

        # ---- area destra: canvas ----
        right = ctk.CTkFrame(body, fg_color=COLORS["bg"])
        right.pack(side="left", fill="both", expand=True)

        self._csv_ipc = InteractivePlotCanvas(right, height=4.8)
        self._csv_ipc.get_frame().pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # HELPERS UI
    # ------------------------------------------------------------------
    def _sec(self, parent, title):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", pady=(4, 4))
        ctk.CTkFrame(f, fg_color=COLORS["accent"],
                     width=4, height=18, corner_radius=2).pack(side="left")
        ctk.CTkLabel(f, text=f" {title}",
                     font=("Segoe UI", 13, "bold"),
                     text_color=COLORS["text"]).pack(side="left")

    # ------------------------------------------------------------------
    # OPEN CSV
    # ------------------------------------------------------------------
    def _csv_open(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv *.CSV"), ("All files", "*.*")])
        if not path:
            return
        try:
            rows, headers, sep, enc, col_meta = parse_universal_csv(path)
        except Exception as e:
            messagebox.showerror("Errore CSV", str(e))
            return
        self._csv_rows          = rows
        self._csv_headers       = headers
        self._csv_sep           = sep
        self._csv_enc           = enc
        self._csv_col_meta      = col_meta
        self._csv_filepath      = path
        self._csv_numeric_cols  = [
            h for h in headers if col_meta.get(h, {}).get("coltype") == "numeric"]
        self._csv_datetime_cols = [
            h for h in headers if col_meta.get(h, {}).get("coltype") == "datetime"]
        self._csv_binary_cols   = [
            h for h in headers if col_meta.get(h, {}).get("coltype") == "binary"]

        # colori
        palette = list(_UC_SERIES_PALETTE)
        self._csv_colors = {
            col: palette[i % len(palette)]
            for i, col in enumerate(self._csv_numeric_cols)
        }

        n_num = len(self._csv_numeric_cols)
        n_dt  = len(self._csv_datetime_cols)
        n_bin = len(self._csv_binary_cols)
        n_row = len(rows)
        self._csv_info_lbl.configure(
            text=(f"{os.path.basename(path)}  "
                  f"({n_row} righe, {n_num} num, {n_dt} dt, {n_bin} bin)"),
            text_color=COLORS["text"])

        # popola menu X
        xcols = ["-"] + self._csv_datetime_cols + self._csv_numeric_cols
        self._csv_x_col_menu.configure(values=xcols)
        default_x = (self._csv_datetime_cols[0] if self._csv_datetime_cols
                     else (self._csv_numeric_cols[0] if self._csv_numeric_cols else "-"))
        self._csv_x_col_var.set(default_x)
        self._csv_on_x_col_change(default_x)

        # popola checkbox Y / Y2
        self._csv_rebuild_y_buttons()
        self._csv_rebuild_y2_buttons()

        # statistiche + anomalie
        self._csv_render_stats()
        self._csv_render_anomalies()

        # plot
        self._csv_refresh_plot()
        self.set_status(f"CSV caricato: {os.path.basename(path)}")

    def _csv_open_compare(self):
        path = filedialog.askopenfilename(
            title="Seleziona secondo CSV per confronto",
            filetypes=[("CSV files", "*.csv *.CSV"), ("All files", "*.*")])
        if not path:
            return
        try:
            rows2, headers2, _, _, col_meta2 = parse_universal_csv(path)
        except Exception as e:
            messagebox.showerror("Errore CSV confronto", str(e))
            return
        self._csv_rows2         = rows2
        self._csv_col_meta2     = col_meta2
        self._csv_numeric_cols2 = [
            h for h in headers2 if col_meta2.get(h, {}).get("coltype") == "numeric"]
        palette = list(_UC_SERIES_PALETTE)
        self._csv_colors2 = {
            col: palette[(i + 6) % len(palette)]
            for i, col in enumerate(self._csv_numeric_cols2)
        }
        self._csv_y_vars2 = {}
        self._csv_refresh_plot()
        self.set_status(
            f"Confronto CSV: {os.path.basename(path)} "
            f"({len(rows2)} righe)")

    # ------------------------------------------------------------------
    # X COL CHANGE
    # ------------------------------------------------------------------
    def _csv_on_x_col_change(self, val):
        is_dt = (val in self._csv_datetime_cols)
        if is_dt:
            self._csv_t_filter_frame.pack(fill="x", pady=(0, 6))
        else:
            self._csv_t_filter_frame.pack_forget()
        self._csv_refresh_plot()

    # ------------------------------------------------------------------
    # SIDEBAR Y / Y2
    # ------------------------------------------------------------------
    def _csv_rebuild_y_buttons(self):
        for w in self._csv_y_scroll.winfo_children():
            try: w.destroy()
            except Exception: pass
        self._csv_y_vars = {}
        for col in self._csv_numeric_cols:
            color = self._csv_colors.get(col, "#ffffff")
            var   = tk.BooleanVar(value=True)
            self._csv_y_vars[col] = var
            rowf = ctk.CTkFrame(self._csv_y_scroll, fg_color="transparent")
            rowf.pack(fill="x", pady=1)
            dot = tk.Canvas(rowf, width=12, height=12,
                            bg=COLORS["surface"], highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=color, outline="")
            dot.pack(side="left", padx=(2, 4), pady=3)
            label = col if len(col) <= 14 else col[:13] + "…"

            def _make_cmd(c=col, v=var):
                def cmd():
                    self._csv_refresh_plot()
                return cmd

            ctk.CTkCheckBox(
                rowf, text=label, variable=var,
                font=("Segoe UI", 9), text_color=COLORS["text"],
                fg_color=color, hover_color=color,
                checkmark_color="#fff", border_color=COLORS["border"],
                width=16, height=16,
                command=_make_cmd(col, var)
            ).pack(side="left", fill="x", expand=True)

    def _csv_rebuild_y2_buttons(self):
        for w in self._csv_y2_scroll.winfo_children():
            try: w.destroy()
            except Exception: pass
        self._csv_y2_vars = {}
        for col in self._csv_numeric_cols:
            color = self._csv_colors.get(col, "#ffffff")
            var   = tk.BooleanVar(value=False)
            self._csv_y2_vars[col] = var
            rowf = ctk.CTkFrame(self._csv_y2_scroll, fg_color="transparent")
            rowf.pack(fill="x", pady=1)
            label = col if len(col) <= 14 else col[:13] + "…"

            def _make_cmd2(c=col, v=var):
                def cmd():
                    self._csv_refresh_plot()
                return cmd

            ctk.CTkCheckBox(
                rowf, text=label, variable=var,
                font=("Segoe UI", 9), text_color=COLORS["text2"],
                fg_color=color, hover_color=color,
                checkmark_color="#fff", border_color=COLORS["border"],
                width=16, height=16,
                command=_make_cmd2(col, var)
            ).pack(side="left", fill="x", expand=True)

    def _csv_sel_all_y(self):
        for v in self._csv_y_vars.values():
            v.set(True)
        self._csv_refresh_plot()

    def _csv_sel_none_y(self):
        for v in self._csv_y_vars.values():
            v.set(False)
        self._csv_refresh_plot()

    # ------------------------------------------------------------------
    # REFRESH PLOT
    # ------------------------------------------------------------------
    def _csv_refresh_plot(self):
        if not self._csv_rows:
            return

        xcol    = self._csv_x_col_var.get()
        xtype   = ("datetime" if xcol in self._csv_datetime_cols
                   else "numeric" if xcol in self._csv_numeric_cols
                   else "index")
        sel_y   = [c for c, v in self._csv_y_vars.items()  if v.get()]
        sel_y2  = [c for c, v in self._csv_y2_vars.items() if v.get()]

        rows = self._csv_rows

        # Filtro temporale
        if xtype == "datetime":
            from_s = self._csv_from_var.get().strip()
            to_s   = self._csv_to_var.get().strip()
            if from_s or to_s:
                rows = self._csv_filter_time(rows, xcol, from_s, to_s)

        # Asse X
        xsraw = []
        for i, r in enumerate(rows):
            if xcol == "-" or xcol not in r:
                xsraw.append(i)
            else:
                xsraw.append(r[xcol])

        series    = {}
        series_y2 = {}
        for col in sel_y:
            series[col] = [
                (float(r[col]) if isinstance(r.get(col), (int, float))
                 else None)
                for r in rows
            ]
        for col in sel_y2:
            series_y2[col] = [
                (float(r[col]) if isinstance(r.get(col), (int, float))
                 else None)
                for r in rows
            ]

        # Serie CSV2 (confronto)
        if self._csv_rows2:
            xcol2 = xcol if xcol in (self._csv_headers or []) else "-"
            xsraw2 = []
            for i, r in enumerate(self._csv_rows2):
                xsraw2.append(r.get(xcol2, i) if xcol2 != "-" else i)
            for col in self._csv_numeric_cols2:
                key = f"{col} [2]"
                series[key] = [
                    (float(r[col]) if isinstance(r.get(col), (int, float))
                     else None)
                    for r in self._csv_rows2
                ]
                self._csv_colors[key] = self._csv_colors2.get(col, "#aaaaaa")

        self._csv_ipc.update_static(
            xsraw, series, xtype, self._csv_col_meta,
            colors=self._csv_colors,
            series_y2=series_y2 if series_y2 else None)

    def _csv_filter_time(self, rows, xcol, from_s, to_s):
        out = []
        for r in rows:
            ts = r.get(xcol)
            if ts is None:
                out.append(r)
                continue
            ts_str = str(ts)[-8:] if len(str(ts)) >= 8 else str(ts)
            if from_s and ts_str < from_s:
                continue
            if to_s and ts_str > to_s:
                continue
            out.append(r)
        return out if out else rows

    # ------------------------------------------------------------------
    # STATISTICHE
    # ------------------------------------------------------------------
    def _csv_render_stats(self):
        for w in self._csv_stats_container.winfo_children():
            try: w.destroy()
            except Exception: pass
        if not self._csv_numeric_cols:
            return
        for col in self._csv_numeric_cols[:12]:
            vals = []
            for r in self._csv_rows:
                v = r.get(col)
                if isinstance(v, (int, float)) and not math.isnan(v):
                    vals.append(float(v))
            if not vals:
                continue
            mn   = min(vals)
            mx   = max(vals)
            avg  = statistics.mean(vals)
            sig  = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            unit = self._csv_col_meta.get(col, {}).get("unit", "")
            card = ctk.CTkFrame(self._csv_stats_container,
                                fg_color=COLORS["surface"], corner_radius=6)
            card.pack(fill="x", pady=2)
            color = self._csv_colors.get(col, COLORS["accent"])
            ctk.CTkLabel(card, text=col,
                         font=("Segoe UI", 9, "bold"),
                         text_color=color).pack(anchor="w", padx=8, pady=(4, 0))
            line = (f"min {mn:.4g}  max {mx:.4g}  "
                    f"avg {avg:.4g}  σ {sig:.4g}")
            if unit:
                line += f"  [{unit}]"
            ctk.CTkLabel(card, text=line,
                         font=("Courier New", 9),
                         text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(0, 4))

    # ------------------------------------------------------------------
    # ANOMALIE
    # ------------------------------------------------------------------
    def _csv_render_anomalies(self):
        for w in self._csv_anomaly_container.winfo_children():
            try: w.destroy()
            except Exception: pass

        anomalies = self._csv_detect_anomalies()
        if not anomalies:
            self._csv_anomaly_container.pack_forget()
            return

        self._csv_anomaly_container.pack(fill="x", pady=(0, 8))
        for a in anomalies[:20]:
            card = ctk.CTkFrame(self._csv_anomaly_container,
                                fg_color=COLORS["surface2"], corner_radius=6)
            card.pack(fill="x", pady=2)
            ctk.CTkLabel(card, text=a["label"],
                         font=("Segoe UI", 9, "bold"),
                         text_color=COLORS["error"]).pack(anchor="w", padx=8, pady=(4, 0))
            ctk.CTkLabel(card, text=a["desc"],
                         font=("Courier New", 9),
                         text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(0, 4))

    def _csv_detect_anomalies(self):
        anomalies = []
        for col in self._csv_numeric_cols:
            vals = []
            for r in self._csv_rows:
                v = r.get(col)
                if isinstance(v, (int, float)) and not math.isnan(v):
                    vals.append((r, float(v)))
            if len(vals) < 5:
                continue
            ys   = [v for _, v in vals]
            avg  = statistics.mean(ys)
            sig  = statistics.pstdev(ys) if len(ys) > 1 else 0.0
            if sig == 0:
                continue
            for r, v in vals:
                if abs(v - avg) > _ANOMALY_SIGMA * sig:
                    # ricava timestamp se disponibile
                    ts = ""
                    for dcol in self._csv_datetime_cols:
                        ts = str(r.get(dcol, ""))[-8:]
                        break
                    anomalies.append({
                        "label": f"⚠ {col} spike",
                        "desc":  (f"{ts}  val={v:.4g}  "
                                  f"avg={avg:.4g}  "
                                  f"Δ={abs(v-avg):.4g} ({abs(v-avg)/sig:.1f}σ)")
                    })
        return anomalies

    # ------------------------------------------------------------------
    # RESET ZOOM
    # ------------------------------------------------------------------
    def _csv_reset_zoom(self):
        self._csv_ipc.reset_zoom()

    # ------------------------------------------------------------------
    # EXPORT PNG
    # ------------------------------------------------------------------
    def _csv_export_png(self):
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"csv_plot_{ts}.png",
            filetypes=[("PNG", "*.png")])
        if not path:
            return
        self._csv_ipc.export_png(path)
        self.set_status(f"PNG salvato: {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # EXPORT REPORT TXT
    # ------------------------------------------------------------------
    def _csv_export_report(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato CSV caricato.")
            return
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"report_{ts}.txt",
            filetypes=[("Testo", "*.txt")])
        if not path:
            return
        lines = []
        lines.append("=" * 60)
        lines.append(f"REPORT CSV  —  {os.path.basename(self._csv_filepath or '')}")
        lines.append(f"Generato il {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Righe: {len(self._csv_rows)}  "
                     f"Colonne: {len(self._csv_headers)}")
        lines.append(f"Separatore: {repr(self._csv_sep)}  "
                     f"Encoding: {self._csv_enc}")
        lines.append("=" * 60)
        lines.append("")
        lines.append("STATISTICHE COLONNE NUMERICHE")
        lines.append("-" * 40)
        for col in self._csv_numeric_cols:
            vals = [float(r[col]) for r in self._csv_rows
                    if isinstance(r.get(col), (int, float))
                    and not math.isnan(r[col])]
            if not vals:
                continue
            unit = self._csv_col_meta.get(col, {}).get("unit", "")
            lines.append(
                f"  {col:<30} "
                f"min={min(vals):.6g}  max={max(vals):.6g}  "
                f"avg={statistics.mean(vals):.6g}  "
                f"σ={statistics.pstdev(vals):.6g}"
                + (f"  [{unit}]" if unit else ""))
        lines.append("")
        lines.append("ANOMALIE RILEVATE")
        lines.append("-" * 40)
        anomalies = self._csv_detect_anomalies()
        if anomalies:
            for a in anomalies:
                lines.append(f"  {a['label']}  {a['desc']}")
        else:
            lines.append("  Nessuna anomalia rilevata.")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self.set_status(f"Report salvato: {os.path.basename(path)}")
        messagebox.showinfo("Completato", f"Report salvato:\n{path}")

    # ------------------------------------------------------------------
    # EXPORT PDF
    # ------------------------------------------------------------------
    def _csv_export_pdf(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato CSV caricato.")
            return
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"csv_report_{ts}.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        self.set_status("Generazione PDF in corso…")

        def _run():
            try:
                self._csv_generate_pdf(path)
                self.after(0, lambda: self.set_status(
                    f"PDF salvato: {os.path.basename(path)}"))
                self.after(0, lambda: messagebox.showinfo(
                    "Completato", f"PDF salvato:\n{path}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore PDF", str(e)))
                self.after(0, lambda: self.set_status("Errore generazione PDF"))

        threading.Thread(target=_run, daemon=True).start()

    def _csv_generate_pdf(self, path):
        xcol  = self._csv_x_col_var.get()
        xtype = ("datetime" if xcol in self._csv_datetime_cols
                 else "numeric" if xcol in self._csv_numeric_cols
                 else "index")
        sel_y = [c for c, v in self._csv_y_vars.items() if v.get()]
        if not sel_y:
            sel_y = self._csv_numeric_cols[:8]

        rows  = self._csv_rows
        xsraw = [r.get(xcol, i) if xcol != "-" else i
                 for i, r in enumerate(rows)]

        with PdfPages(path) as pdf:
            # Copertina
            fig_cov = plt.Figure(figsize=(11, 4), facecolor="#1e1e2e")
            ax_cov  = fig_cov.add_subplot(111)
            ax_cov.set_facecolor("#1e1e2e")
            ax_cov.axis("off")
            ax_cov.text(0.5, 0.65,
                        os.path.basename(self._csv_filepath or "CSV Report"),
                        ha="center", va="center",
                        fontsize=18, color="#a0a0ff",
                        fontweight="bold",
                        transform=ax_cov.transAxes)
            ax_cov.text(0.5, 0.45,
                        f"Righe: {len(rows)}  |  "
                        f"Colonne numeriche: {len(self._csv_numeric_cols)}",
                        ha="center", va="center",
                        fontsize=11, color="#808080",
                        transform=ax_cov.transAxes)
            ax_cov.text(0.5, 0.30,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        ha="center", va="center",
                        fontsize=9, color="#606060",
                        transform=ax_cov.transAxes)
            pdf.savefig(fig_cov, bbox_inches="tight")
            plt.close(fig_cov)

            # Una pagina per serie Y (max 4 per pagina)
            chunks = [sel_y[i:i+4] for i in range(0, len(sel_y), 4)]
            for chunk in chunks:
                n    = len(chunk)
                fig  = plt.Figure(figsize=(14, 4 * n), facecolor="#1e1e2e")
                for idx, col in enumerate(chunk):
                    ax = fig.add_subplot(n, 1, idx + 1)
                    ax.set_facecolor("#252535")
                    ax.set_title(col, color="#a0a0c0", fontsize=10, pad=4)
                    for sp in ax.spines.values():
                        sp.set_edgecolor("#3a3a5c")
                    ax.tick_params(colors="#a0a0c0", labelsize=7)
                    ax.grid(True, color="#3a3a5c", lw=0.4,
                            linestyle="--", alpha=0.6)
                    vals = [
                        (float(r[col]) if isinstance(r.get(col), (int, float))
                         else None)
                        for r in rows
                    ]
                    xf = [x for x, y in zip(xsraw, vals) if y is not None]
                    yf = [y for y in vals if y is not None]
                    if xf:
                        ax.plot(xf, yf,
                                color=self._csv_colors.get(col, "#ffffff"),
                                linewidth=1.2, label=col)
                        ax.legend(fontsize=7, loc="upper left",
                                  facecolor="#252535",
                                  labelcolor="#c0c0e0",
                                  edgecolor="#3a3a5c")
                fig.tight_layout(pad=1.5)
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)

            # Pagina statistiche
            fig_st = plt.Figure(figsize=(11, 8), facecolor="#1e1e2e")
            ax_st  = fig_st.add_subplot(111)
            ax_st.set_facecolor("#1e1e2e")
            ax_st.axis("off")
            lines_st = ["STATISTICHE COLONNE NUMERICHE\n"]
            for col in self._csv_numeric_cols[:20]:
                vals = [float(r[col]) for r in rows
                        if isinstance(r.get(col), (int, float))
                        and not math.isnan(r[col])]
                if not vals:
                    continue
                unit = self._csv_col_meta.get(col, {}).get("unit", "")
                lines_st.append(
                    f"  {col:<28} "
                    f"min={min(vals):.5g}  max={max(vals):.5g}  "
                    f"avg={statistics.mean(vals):.5g}  "
                    f"σ={statistics.pstdev(vals):.5g}"
                    + (f" [{unit}]" if unit else ""))
            ax_st.text(0.02, 0.98, "\n".join(lines_st),
                       ha="left", va="top",
                       fontsize=8, color="#c0c0c0",
                       fontfamily="monospace",
                       transform=ax_st.transAxes)
            pdf.savefig(fig_st, bbox_inches="tight")
            plt.close(fig_st)
