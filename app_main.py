# -*- coding: utf-8 -*-
"""
app_main.py  —  Entry point slim di MouldGraph.

La logica delle tre tab principali è suddivisa in mixin dedicati:
  - GraficiMixin  → tab_grafici.py   (Tab Grafici / Lamborghini PDF)
  - CsvMixin      → tab_csv.py        (Tab Dati CSV)
  - LiveMixin     → tab_live.py       (Tab Live Data)

Qui rimangono solo:
  - _build_ui: header, status-bar, TabView, lazy-loading
  - Tab Analisi log (build_analisi, timeline, AI)
  - Tab Dati Siemens (build_siemens_tab)
  - Tab Come usare (_build_help)
  - Helpers comuni (_sec, _sec_inline, set_status)
  - Azioni log (open_file, analyze, apply_filters, …)
  - Azioni Siemens (open_siemens_csv, _refresh_siemens, …)
  - export_json / export_csv
"""
import os, re, json, csv, math, threading, random
import tkinter as tk
import tkinter.simpledialog as simpledialog
from tkinter import filedialog, messagebox
from datetime import datetime
from collections import defaultdict
import queue as _queue

import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

from colors import COLORS, LEVEL_COLORS, LEVEL_BG, LEVEL_HOVER
from log_parser import (norm_level, parse_ts, parse_line, parse_log,
                        norm_sig, ai_analysis, build_timeline)
from csv_parser import (parse_siemens_csv, detect_anomalies, parse_universal_csv,
                        _is_long_cycle_csv, _parse_long_cycle_csv, _uc_build_series)
from charts import TimelineCanvas, LineChart, PumpCanvas, _isolate_scroll
from plot_canvas import InteractivePlotCanvas
from pdf_export import (generate_plant_pdf, generate_lamborghini_pdf,
                        generate_front_firewall_pdf, detect_csv_type,
                        _autodetect_profile, _validate_csv, PROFILES, PRESSASTAMPI)

# —— Mixin delle tre tab principali ————————————————————————————————
from tab_grafici import GraficiMixin
from tab_csv    import CsvMixin
from tab_live   import LiveMixin
# —————————————————————————————————————————————————————

# costanti live (ancora usate dai mixin)
MAX_LIVE_POINTS = 500


class LogAnalyzerApp(GraficiMixin, CsvMixin, LiveMixin, ctk.CTk):
    """Applicazione principale. La logica delle tab è nei mixin."""

    def __init__(self):
        super().__init__()
        self.title("MouldGraph")
        w, h = 1100, 720
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.minsize(1100, 700)
        self.configure(fg_color=COLORS["bg"])

        # — stato analisi log —
        self.all_parsed   = []
        self.filtered     = []
        self.active_levels = {"ERROR": True, "WARN": True,
                              "INFO": True, "DEBUG": True}

        # — stato Siemens —
        self.siemens_headers = []
        self.siemens_rows    = []
        self._last_csv_type  = "siemens"

        # — stato Live Data (inizializzato qui, usato da LiveMixin) —
        self._live_queue        = _queue.Queue(maxsize=2000)
        self._live_running      = threading.Event()
        self._live_paused       = threading.Event()
        self._live_thread       = None
        self._live_rows         = []
        self._live_headers      = []
        self._live_col_meta     = {}
        self._live_numeric_cols = []
        self._live_plot_cols    = []
        self._live_alarm_rules  = []
        self._live_alarm_count  = 0
        self._live_alarm_active = set()
        self._live_interp_job   = None
        self._live_multi_mode   = False
        self._live_multi_ipcs   = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # BUILD UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        # header
        hdr = ctk.CTkFrame(self, fg_color=COLORS["surface"],
                           corner_radius=0, height=54)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Log",
                     font=("Segoe UI", 20, "bold"),
                     text_color=COLORS["text"]).pack(side="left", padx=(18, 0), pady=10)
        ctk.CTkLabel(hdr, text="Analyzer",
                     font=("Segoe UI", 20, "bold"),
                     text_color=COLORS["accent"]).pack(side="left", pady=10)

        # status bar
        sb = ctk.CTkFrame(self, fg_color=COLORS["surface"],
                          corner_radius=0, height=26)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self.status_lbl = ctk.CTkLabel(
            sb, text="Pronto.",
            font=("Segoe UI", 11), text_color=COLORS["text2"])
        self.status_lbl.pack(side="left", padx=12)

        # tabview
        self.tabs = ctk.CTkTabview(
            self, fg_color=COLORS["bg"],
            segmented_button_fg_color=COLORS["surface"],
            segmented_button_selected_color=COLORS["accent"],
            segmented_button_selected_hover_color="#5a52e0",
            segmented_button_unselected_color=COLORS["surface"],
            segmented_button_unselected_hover_color=COLORS["surface2"],
            text_color=COLORS["text"])
        self.tabs.pack(fill="both", expand=True, padx=10, pady=6)
        for t in ["  Grafici  ", "  Dati CSV  ",
                  "  Live Data  ", "  Come usare  "]:
            self.tabs.add(t)

        # lazy loading
        self._tabs_built   = set()
        self._tab_builders = {
            "  Grafici  "    : self._build_grafici_tab,   # GraficiMixin
            "  Dati CSV  "   : self._build_csv_tab,       # CsvMixin
            "  Live Data  "  : self._build_live_tab,      # LiveMixin
            "  Come usare  " : self._build_help,
        }

        def _on_tab_change():
            name = self.tabs.get()
            if name not in self._tabs_built:
                self._tabs_built.add(name)
                builder = self._tab_builders.get(name)
                if builder:
                    builder(self.tabs.tab(name))

        self.tabs.configure(command=_on_tab_change)

        # costruisce subito solo il primo tab visibile
        first = "  Grafici  "
        self._tabs_built.add(first)
        self._build_grafici_tab(self.tabs.tab(first))

    # ------------------------------------------------------------------
    # HELPER COMUNE
    # ------------------------------------------------------------------
    def set_status(self, msg: str):
        try:
            self.status_lbl.configure(text=msg)
        except Exception:
            pass

    def _sec(self, p, t):
        f = ctk.CTkFrame(p, fg_color="transparent")
        f.pack(fill="x", pady=(4, 4))
        ctk.CTkFrame(f, fg_color=COLORS["accent"],
                     width=4, height=18, corner_radius=2).pack(side="left")
        ctk.CTkLabel(f, text=f"  {t}",
                     font=("Segoe UI", 13, "bold"),
                     text_color=COLORS["text"]).pack(side="left")

    def _sec_inline(self, p, t):
        ctk.CTkFrame(p, fg_color=COLORS["accent"],
                     width=4, height=18, corner_radius=2).pack(side="left")
        ctk.CTkLabel(p, text=f"  {t}",
                     font=("Segoe UI", 13, "bold"),
                     text_color=COLORS["text"]).pack(side="left")

    # ------------------------------------------------------------------
    # TAB ANALISI LOG
    # ------------------------------------------------------------------
    def _build_analisi(self, parent):
        paned = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        paned.pack(fill="both", expand=True, pady=4)
        lw = ctk.CTkFrame(paned, fg_color=COLORS["bg"], width=375)
        lw.pack(side="left", fill="y", padx=(0, 8))
        lw.pack_propagate(False)
        left = ctk.CTkScrollableFrame(
            lw, fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        left.pack(fill="both", expand=True)

        self._sec(left, "Input Log")
        self.txt_input = ctk.CTkTextbox(
            left, height=130, font=("Courier New", 10),
            fg_color=COLORS["surface2"], text_color=COLORS["text"],
            border_color=COLORS["border"], border_width=1)
        self.txt_input.pack(fill="x", pady=(0, 8))
        self.txt_input.insert("0.0", "Incolla log qui oppure usa Apri file / Demo...")

        self._sec(left, "Filtri")
        fcard = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        fcard.pack(fill="x", pady=(0, 8))
        lf = ctk.CTkFrame(fcard, fg_color="transparent")
        lf.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(lf, text="LIVELLO",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w")
        btns = ctk.CTkFrame(lf, fg_color="transparent")
        btns.pack(anchor="w")
        self.lvl_btns = {}
        for lvl in ["ERROR", "WARN", "INFO", "DEBUG"]:
            b = ctk.CTkButton(
                btns, text=lvl, width=66, height=26,
                fg_color=LEVEL_BG[lvl], hover_color=LEVEL_HOVER[lvl],
                text_color=LEVEL_COLORS[lvl], font=("Segoe UI", 11, "bold"),
                command=lambda l=lvl: self.toggle_level(l))
            b.pack(side="left", padx=(0, 4), pady=4)
            self.lvl_btns[lvl] = b

        kf = ctk.CTkFrame(fcard, fg_color="transparent")
        kf.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(kf, text="KEYWORD",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w")
        self.entry_kw = ctk.CTkEntry(
            kf, placeholder_text="es. timeout, alarm...",
            fg_color=COLORS["surface2"], border_color=COLORS["border"],
            text_color=COLORS["text"], height=30)
        self.entry_kw.pack(fill="x")
        self.entry_kw.bind("<KeyRelease>",
                           lambda e: self._debounced_apply_filters())

        tf = ctk.CTkFrame(fcard, fg_color="transparent")
        tf.pack(fill="x", padx=10, pady=(4, 4))
        ctk.CTkLabel(tf, text="INTERVALLO",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w")
        tr = ctk.CTkFrame(tf, fg_color="transparent")
        tr.pack(fill="x")
        self.entry_from = ctk.CTkEntry(
            tr, placeholder_text="Dal (YYYY-MM-DD HH:MM)",
            fg_color=COLORS["surface2"], border_color=COLORS["border"],
            text_color=COLORS["text"], height=28)
        self.entry_from.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.entry_from.bind("<KeyRelease>",
                             lambda e: self._debounced_apply_filters())
        self.entry_to = ctk.CTkEntry(
            tr, placeholder_text="Al...",
            fg_color=COLORS["surface2"], border_color=COLORS["border"],
            text_color=COLORS["text"], height=28)
        self.entry_to.pack(side="left", fill="x", expand=True)
        self.entry_to.bind("<KeyRelease>",
                           lambda e: self._debounced_apply_filters())
        ctk.CTkButton(
            fcard, text="Reset filtri", width=110, height=26,
            fg_color=COLORS["surface2"], hover_color=COLORS["border"],
            text_color=COLORS["text2"],
            command=self.reset_filters).pack(anchor="e", padx=10, pady=(4, 10))

        self._sec(left, "Statistiche")
        srow = ctk.CTkFrame(left, fg_color="transparent")
        srow.pack(fill="x", pady=(0, 8))
        self.stat_labels = {}
        for key, color, label in [
            ("total", COLORS["accent2"], "Totale"),
            ("ERROR", COLORS["error"],   "Errori"),
            ("WARN",  COLORS["warn"],    "Warning"),
            ("INFO",  COLORS["info"],    "Info"),
        ]:
            sc = ctk.CTkFrame(srow, fg_color=COLORS["surface"], corner_radius=8)
            sc.pack(side="left", expand=True, fill="x", padx=2)
            lv = ctk.CTkLabel(sc, text="0",
                              font=("Segoe UI", 22, "bold"), text_color=color)
            lv.pack(pady=(8, 0))
            ctk.CTkLabel(sc, text=label,
                         font=("Segoe UI", 10),
                         text_color=COLORS["text2"]).pack(pady=(0, 8))
            self.stat_labels[key] = lv

        self._sec(left, "Pattern / Firme (Top 10)")
        pf = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        pf.pack(fill="x", pady=(0, 8))
        self.patterns_box = ctk.CTkTextbox(
            pf, height=280, font=("Courier New", 10),
            fg_color=COLORS["surface"], text_color=COLORS["text2"],
            border_width=0, wrap="word")
        self.patterns_box.pack(fill="x", padx=6, pady=6)

        right = ctk.CTkFrame(paned, fg_color=COLORS["bg"])
        right.pack(side="left", fill="both", expand=True)
        th = ctk.CTkFrame(right, fg_color="transparent")
        th.pack(fill="x", pady=(0, 6))
        self._sec_inline(th, "Log Dettaglio")
        self.lbl_count = ctk.CTkLabel(
            th, text="", font=("Segoe UI", 12), text_color=COLORS["accent"])
        self.lbl_count.pack(side="left", padx=8)
        er = ctk.CTkFrame(th, fg_color="transparent")
        er.pack(side="right")
        ctk.CTkButton(
            er, text="Esporta JSON", width=110, height=28,
            fg_color=COLORS["surface2"], hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=self.export_json).pack(side="left", padx=4)
        ctk.CTkButton(
            er, text="Esporta CSV", width=110, height=28,
            fg_color=COLORS["surface2"], hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=self.export_csv).pack(side="left", padx=4)

        tf2 = ctk.CTkFrame(right, fg_color=COLORS["surface"], corner_radius=8)
        tf2.pack(fill="both", expand=True)
        ch2 = ctk.CTkFrame(tf2, fg_color=COLORS["surface2"],
                           corner_radius=0, height=28)
        ch2.pack(fill="x")
        ch2.pack_propagate(False)
        for txt, ww in [("#", 40), ("Timestamp", 160), ("Liv.", 60),
                        ("Component", 110), ("Messaggio", 500)]:
            ctk.CTkLabel(ch2, text=txt, font=("Segoe UI", 10, "bold"),
                         text_color=COLORS["text2"],
                         width=ww, anchor="w").pack(side="left", padx=4)
        self.tbl = tk.Text(
            tf2, bg=COLORS["surface"], fg=COLORS["text"],
            font=("Courier New", 11), relief="flat", bd=0,
            selectbackground="#3a3580", highlightthickness=0,
            wrap="none", state="disabled")
        vsb = ctk.CTkScrollbar(tf2, command=self.tbl.yview)
        hsb = ctk.CTkScrollbar(tf2, orientation="horizontal",
                               command=self.tbl.xview)
        self.tbl.configure(yscrollcommand=vsb.set,
                           xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tbl.pack(fill="both", expand=True)
        for tag, fgc, bgc in [
            ("ERROR", COLORS["error"],  None),
            ("WARN",  COLORS["warn"],   None),
            ("INFO",  COLORS["info"],   None),
            ("DEBUG", COLORS["debug"],  None),
            ("hl",    None, "#4a3a00"),
            ("dim",   COLORS["text2"],  None),
            ("comp",  COLORS["accent2"], None),
            ("roweven", None, "#1e2133"),
            ("rowodd",  None, COLORS["surface"]),
        ]:
            kw = {}
            if fgc: kw["foreground"] = fgc
            if bgc: kw["background"] = bgc
            self.tbl.tag_configure(tag, **kw)

    # ------------------------------------------------------------------
    # TAB TIMELINE
    # ------------------------------------------------------------------
    def _build_timeline_tab(self, parent):
        self._sec(parent, "Timeline eventi")
        ctk.CTkLabel(
            parent,
            text="Distribuzione eventi nel tempo - barre impilate per livello",
            font=("Segoe UI", 11),
            text_color=COLORS["text2"]).pack(anchor="w", padx=4, pady=(0, 8))
        fc = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=8)
        fc.pack(fill="both", expand=True)
        self.timeline_canvas = TimelineCanvas(fc)
        self.timeline_canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self.timeline_canvas.bind(
            "<Configure>", lambda e: self.timeline_canvas.redraw())
        self._sec(parent, "Riepilogo per componente")
        cf = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=8)
        cf.pack(fill="both", expand=True, pady=(8, 0))
        self.comp_box = ctk.CTkTextbox(
            cf, font=("Courier New", 11),
            fg_color=COLORS["surface"], text_color=COLORS["text"],
            border_width=0)
        self.comp_box.pack(fill="both", expand=True, padx=8, pady=8)

    # ------------------------------------------------------------------
    # TAB AI
    # ------------------------------------------------------------------
    def _build_ai_tab(self, parent):
        self._sec(parent, "AI Insights - Analisi automatica del log")
        ctk.CTkLabel(
            parent,
            text="Suggerimenti e rilevamento anomalie basati sul contenuto del log",
            font=("Segoe UI", 11),
            text_color=COLORS["text2"]).pack(anchor="w", padx=4, pady=(0, 10))
        scroll = ctk.CTkScrollableFrame(
            parent, fg_color=COLORS["bg"], corner_radius=0)
        scroll.pack(fill="both", expand=True)
        self.ai_container = scroll

    # ------------------------------------------------------------------
    # TAB DATI SIEMENS
    # ------------------------------------------------------------------
    def _build_siemens_tab(self, parent):
        toolbar = ctk.CTkFrame(
            parent, fg_color=COLORS["surface"], corner_radius=8, height=44)
        toolbar.pack(fill="x", pady=(0, 8))
        toolbar.pack_propagate(False)
        ctk.CTkButton(
            toolbar, text="Apri CSV Siemens", width=150, height=30,
            fg_color=COLORS["accent"], hover_color="#5a52e0",
            text_color=COLORS["text"],
            command=self.open_siemens_csv).pack(side="left", padx=10, pady=7)
        self.siemens_info_lbl = ctk.CTkLabel(
            toolbar, text="Nessun file caricato",
            font=("Segoe UI", 11), text_color=COLORS["text2"])
        self.siemens_info_lbl.pack(side="left", padx=10)
        ctk.CTkButton(
            toolbar, text="Genera PDF Grafico", width=150, height=30,
            fg_color="#7c3aed", hover_color="#6d28d9",
            text_color=COLORS["text"],
            command=self.export_pdf_grafico).pack(side="right", padx=6, pady=7)
        ctk.CTkButton(
            toolbar, text="Esporta report", width=120, height=30,
            fg_color=COLORS["surface2"], hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=self.export_siemens_report).pack(side="right", padx=10, pady=7)

        sel_frame = ctk.CTkFrame(
            parent, fg_color=COLORS["surface"], corner_radius=8, height=40)
        sel_frame.pack(fill="x", pady=(0, 8))
        sel_frame.pack_propagate(False)
        ctk.CTkLabel(
            sel_frame, text="Visualizza:",
            font=("Segoe UI", 11),
            text_color=COLORS["text2"]).pack(side="left", padx=10, pady=8)
        self.siemens_col_var = ctk.StringVar(value="Temp_Vasca_01")
        self.siemens_col_menu = ctk.CTkOptionMenu(
            sel_frame, variable=self.siemens_col_var,
            values=["-"], width=180,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"],
            command=self._on_col_change)
        self.siemens_col_menu.pack(side="left", padx=4, pady=8)
        ctk.CTkLabel(
            sel_frame, text="vs",
            font=("Segoe UI", 11),
            text_color=COLORS["text2"]).pack(side="left", padx=4)
        self.siemens_col2_var = ctk.StringVar(value="-")
        self.siemens_col2_menu = ctk.CTkOptionMenu(
            sel_frame, variable=self.siemens_col2_var,
            values=["-"], width=180,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"],
            command=self._on_col_change)
        self.siemens_col2_menu.pack(side="left", padx=4, pady=8)

        charts_frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        charts_frame.pack(fill="both", expand=True)

        chart_left = ctk.CTkFrame(charts_frame, fg_color=COLORS["bg"])
        chart_left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._sec(chart_left, "Grafico dati")
        lc_frame = ctk.CTkFrame(
            chart_left, fg_color=COLORS["surface"], corner_radius=8)
        lc_frame.pack(fill="both", expand=True)
        self.line_chart = LineChart(lc_frame, height=220)
        self.line_chart.pack(fill="both", expand=True, padx=6, pady=6)
        self.line_chart.bind(
            "<Configure>", lambda e: self.line_chart.redraw())
        self._sec(chart_left, "Stato Pompa")
        pc_frame = ctk.CTkFrame(
            chart_left, fg_color=COLORS["surface"], corner_radius=8)
        pc_frame.pack(fill="x")
        self.pump_canvas = PumpCanvas(pc_frame, height=70)
        self.pump_canvas.pack(fill="x", padx=6, pady=6)
        self.pump_canvas.bind(
            "<Configure>", lambda e: self.pump_canvas.redraw())

        chart_right = ctk.CTkFrame(
            charts_frame, fg_color=COLORS["bg"], width=380)
        chart_right.pack(side="left", fill="y")
        chart_right.pack_propagate(False)
        right_scroll = ctk.CTkScrollableFrame(
            chart_right, fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        right_scroll.pack(fill="both", expand=True)

        self._sec(right_scroll, "Anomalie rilevate")
        self.anomaly_container = ctk.CTkFrame(
            right_scroll, fg_color=COLORS["bg"])
        self.anomaly_container.pack(fill="x", pady=(0, 8))

        self._sec(right_scroll, "Statistiche colonne")
        stats_frame = ctk.CTkFrame(
            right_scroll, fg_color=COLORS["surface"], corner_radius=8)
        stats_frame.pack(fill="x", pady=(0, 8))
        self.stats_box = ctk.CTkTextbox(
            stats_frame, height=160, font=("Courier New", 10),
            fg_color=COLORS["surface"], text_color=COLORS["text"],
            border_width=0)
        self.stats_box.pack(fill="x", padx=6, pady=6)

        self._sec(right_scroll, "Dati grezzi")
        raw_frame = ctk.CTkFrame(
            right_scroll, fg_color=COLORS["surface"], corner_radius=8)
        raw_frame.pack(fill="x", pady=(0, 8))
        self.raw_box = ctk.CTkTextbox(
            raw_frame, height=200, font=("Courier New", 9),
            fg_color=COLORS["surface"], text_color=COLORS["text2"],
            border_width=0, wrap="none")
        self.raw_box.pack(fill="x", padx=6, pady=6)

    # ------------------------------------------------------------------
    # TAB COME USARE
    # ------------------------------------------------------------------
    def _build_help(self, parent):
        scroll = ctk.CTkScrollableFrame(
            parent, fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        scroll.pack(fill="both", expand=True)

        def _section_title(icon, title, subtitle=""):
            f = ctk.CTkFrame(scroll, fg_color="transparent")
            f.pack(fill="x", padx=16, pady=(22, 6))
            ctk.CTkLabel(f, text=icon, font=("Segoe UI", 22),
                         text_color=COLORS["accent"]).pack(side="left", padx=(0, 10))
            col = ctk.CTkFrame(f, fg_color="transparent")
            col.pack(side="left")
            ctk.CTkLabel(col, text=title,
                         font=("Segoe UI", 15, "bold"),
                         text_color=COLORS["text"]).pack(anchor="w")
            if subtitle:
                ctk.CTkLabel(col, text=subtitle,
                             font=("Segoe UI", 10),
                             text_color=COLORS["text2"]).pack(anchor="w")
            ctk.CTkFrame(scroll, fg_color=COLORS["border"], height=1).pack(
                fill="x", padx=16, pady=(0, 8))

        def _card(icon, title, body, example=None):
            outer = ctk.CTkFrame(
                scroll, fg_color=COLORS["surface"], corner_radius=10)
            outer.pack(fill="x", padx=16, pady=4)
            hdr = ctk.CTkFrame(outer, fg_color="transparent")
            hdr.pack(fill="x", padx=14, pady=(12, 4))
            ctk.CTkLabel(hdr, text=icon, font=("Segoe UI", 16),
                         text_color=COLORS["accent2"],
                         width=28).pack(side="left")
            ctk.CTkLabel(hdr, text=title,
                         font=("Segoe UI", 11, "bold"),
                         text_color=COLORS["text"]).pack(side="left", padx=6)
            ctk.CTkLabel(outer, text=body,
                         font=("Segoe UI", 10),
                         text_color=COLORS["text2"],
                         anchor="w", justify="left",
                         wraplength=860).pack(anchor="w", padx=46, pady=(0, 4))
            if example:
                ex = ctk.CTkFrame(
                    outer, fg_color=COLORS["surface2"], corner_radius=6)
                ex.pack(fill="x", padx=46, pady=(2, 12))
                ctk.CTkLabel(ex, text="  ESEMPIO  ",
                             font=("Segoe UI", 8, "bold"),
                             text_color=COLORS["accent"],
                             fg_color=COLORS["surface2"]).pack(
                    anchor="w", padx=8, pady=(6, 0))
                ctk.CTkLabel(ex, text=example,
                             font=("Courier New", 9),
                             text_color=COLORS["accent2"],
                             anchor="w", justify="left",
                             wraplength=820).pack(
                    anchor="w", padx=8, pady=(0, 8))
            else:
                ctk.CTkFrame(outer, fg_color="transparent", height=6).pack()

        intro = ctk.CTkFrame(
            scroll, fg_color=COLORS["surface2"], corner_radius=12)
        intro.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            intro,
            text="MouldGraph  —  Analisi e monitoraggio dati industriali",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(14, 2))
        ctk.CTkLabel(
            intro,
            text=("L'app si divide in tre tab principali: Grafici, Dati CSV e Live Data.\n"
                  "Ogni tab è indipendente: puoi usarle in qualsiasi ordine senza interferenze."),
            font=("Segoe UI", 10), text_color=COLORS["text2"],
            justify="left", anchor="w").pack(anchor="w", padx=20, pady=(0, 14))

        _section_title("📊", "Tab Grafici",
                       "Generazione PDF professionali per presse Persico 2500T e Cannon 5000T")
        _card("🏭", "Seleziona Pressa e Stampo",
              "Scegli la pressa dal menu, poi il profilo stampo. "
              "Determina scale, setpoint temperatura, forza e vuoto.",
              "Pressa: Persico 2500T -> Stampo: Front Firewall")
        _card("📂", "Carica il CSV del ciclo",
              "Apri CSV e seleziona il file esportato dalla pressa. "
              "Il profilo viene rilevato dal codice nella colonna Partita.",
              "Partita 26RF005449 -> profilo: Front Firewall")
        _card("🖼", "Genera PDF",
              "Il grafico si aggiorna in anteprima. Genera PDF crea il report multi-pagina "
              "(cover, temperature, posizione/forza, vuoto).",
              "PDF: Firewall_RF_21103.pdf  (3 pagine, 150 dpi)")

        _section_title("📋", "Tab Dati CSV",
                       "Analisi universale di qualsiasi file CSV")
        _card("📂", "Caricamento CSV",
              "L'app rileva encoding, separatore, tipo colonna e unità di misura automaticamente.",
              "dati_forno.csv -> sep=;, 12 colonne numeriche, 1 datetime")
        _card("📈", "Plot e zoom",
              "Seleziona X, attiva/disattiva serie Y, assegna a Y2. "
              "Zoom rotella, pan tasto centrale, cursori A/B doppio click.",
              "X: UTC_Time | Y1: Temperatura | Y2: Portata_Lmin")
        _card("🔍", "Anomalie",
              "Spike > 2.5 sigma, pompa spenta, livello > 95%, pressione < 1.0 bar.",
              "[ANOMALIA] Temperatura 187.3 C (media 162.5)")

        _section_title("📡", "Tab Live Data",
                       "Monitoraggio in tempo reale o simulazione CSV")
        _card("📂", "CSV simulazione",
              "Carica un CSV e premi Avvia. L'app scorre i campioni in tempo reale.",
              "FORZA_21103.CSV -> colonna Time in secondi, 8 colonne")
        _card("▶", "Avvia / Pausa / Stop",
              "Verde: avvia. Giallo: pausa. Rosso: stop. "
              "Ogni Avvia azera la sessione precedente.",
              "Avvia -> pausa -> riprende -> stop")
        _card("⚡", "Velocità",
              "1x = tempo reale | 10x | 60x | MAX = istantaneo.",
              "Ciclo 1496s: 1x->25min | 10x->2.5min | MAX->2s")
        _card("🔴", "Allarmi live",
              "+ Soglia: scegli colonna, Lo e/o Hi. Badge rosso al primo scatto.",
              "FC Lo=6400 Hi=6600 -> [02:35:12] ALLARME FC=6546.4")

        _section_title("⌨", "Scorciatoie",
                       "Interazione avanzata con i grafici")
        _card("🖱", "Zoom rotella",
              "Su = zoom in centrato sul cursore. Giu' = zoom out.",
              "Rotella su -> zoom 15%")
        _card("✋", "Pan",
              "Tasto centrale + trascina per spostarti sull'asse X.",
              "Click centrale + trascina")
        _card("📍", "Cursori A/B",
              "Doppio click sinistro = A. Doppio click destro = B. "
              "Riquadro delta X, delta Y, pendenza.",
              "A: X=100s FC=6480 | B: X=200s FC=6520 -> Delta=+40 kN")

    # ------------------------------------------------------------------
    # EXPORT PDF GRAFICO (Siemens / Front Firewall)
    # ------------------------------------------------------------------
    def export_pdf_grafico(self):
        if not self.siemens_rows:
            messagebox.showwarning("Attenzione",
                                   "Nessun dato Siemens caricato.")
            return
        csv_t = detect_csv_type(self.siemens_headers)
        if csv_t != "front_firewall":
            messagebox.showwarning(
                "Attenzione",
                "Funzione disponibile solo per dati Front Firewall (Persico).\n"
                "Le colonne rilevate non corrispondono al profilo.")
            return
        base = (os.path.splitext(os.path.basename(
                    self.siemens_csv_path))[0]
                if hasattr(self, "siemens_csv_path") and self.siemens_csv_path
                else "Grafico-Front_Firewall")
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"{base}.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        self.set_status("Generazione PDF in corso...")
        def _run():
            try:
                generate_front_firewall_pdf(
                    self.siemens_rows, self.siemens_headers, path)
                self.after(0, lambda: self.set_status(
                    f"PDF salvato: {os.path.basename(path)}"))
                self.after(0, lambda: messagebox.showinfo(
                    "Completato", f"PDF salvato:\n{path}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore PDF", str(e)))
                self.after(0, lambda: self.set_status("Errore generazione PDF"))
        threading.Thread(target=_run, daemon=True).start()

    # ------------------------------------------------------------------
    # AZIONI LOG
    # ------------------------------------------------------------------
    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Log files", "*.log *.txt *.out *.csv"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            first = content.strip().splitlines()[0] if content.strip() else ""
            if (detect_csv_type(
                    [h.strip().strip('"') for h in (first or "").split(",")])
                    == "front_firewall"
                    or ("Record" in first
                        and ("Date" in first or "Time" in first)
                        and "," in first)):
                self.siemens_csv_path = path
                self._load_siemens_data(content, os.path.basename(path))
                return
            self.txt_input.delete("0.0", "end")
            self.txt_input.insert("0.0", content)
            self.set_status(
                f"File caricato: {os.path.basename(path)} "
                f"({os.path.getsize(path)/1024:.1f} KB)")
            self.analyze()
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def analyze(self):
        text = self.txt_input.get("0.0", "end").strip()
        if not text or text.startswith("Incolla"):
            messagebox.showwarning("Attenzione", "Incolla un log prima!")
            return
        self.all_parsed = parse_log(text)
        wt = [l for l in self.all_parsed if l["ts"]]
        if wt:
            mn = min(l["ts"] for l in wt)
            mx = max(l["ts"] for l in wt)
            self.entry_from.delete(0, "end")
            self.entry_from.insert(0, mn.strftime("%Y-%m-%d %H:%M"))
            self.entry_to.delete(0, "end")
            self.entry_to.insert(0, mx.strftime("%Y-%m-%d %H:%M"))
        self.apply_filters()
        self.set_status(f"Analizzate {len(self.all_parsed)} righe.")

    def toggle_level(self, level):
        self.active_levels[level] = not self.active_levels[level]
        btn = self.lvl_btns[level]
        if self.active_levels[level]:
            btn.configure(fg_color=LEVEL_BG[level],
                          text_color=LEVEL_COLORS[level])
        else:
            btn.configure(fg_color=COLORS["surface2"],
                          text_color=COLORS["text2"])
        self.apply_filters()

    def reset_filters(self):
        self.entry_kw.delete(0, "end")
        self.entry_from.delete(0, "end")
        self.entry_to.delete(0, "end")
        for lvl in self.active_levels:
            self.active_levels[lvl] = True
            self.lvl_btns[lvl].configure(
                fg_color=LEVEL_BG[lvl], text_color=LEVEL_COLORS[lvl])
        self.apply_filters()

    def _debounced_apply_filters(self):
        if getattr(self, "_filter_debounce_job", None):
            try:
                self.after_cancel(self._filter_debounce_job)
            except Exception:
                pass
        self._filter_debounce_job = self.after(
            250, self._run_debounced_filters)

    def _run_debounced_filters(self):
        self._filter_debounce_job = None
        self.apply_filters()

    def apply_filters(self):
        kw = self.entry_kw.get().lower().strip()
        fd = self._pdt(self.entry_from.get().strip())
        td = self._pdt(self.entry_to.get().strip())
        self.filtered = []
        for l in self.all_parsed:
            if not self.active_levels.get(l["level"], True):
                continue
            if kw and kw not in l["raw"].lower():
                continue
            if fd and l["ts"] and l["ts"] < fd:
                continue
            if td and l["ts"] and l["ts"] > td:
                continue
            self.filtered.append(l)
        self._render_stats()
        self._render_table(kw)
        self._render_patterns()
        self._render_timeline()
        self._render_comp()
        self._render_ai()

    def _pdt(self, s):
        if not s:
            return None
        for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                pass
        return None

    def _render_stats(self):
        self.stat_labels["total"].configure(text=str(len(self.filtered)))
        self.stat_labels["ERROR"].configure(
            text=str(sum(1 for l in self.filtered if l["level"] == "ERROR")))
        self.stat_labels["WARN"].configure(
            text=str(sum(1 for l in self.filtered if l["level"] == "WARN")))
        self.stat_labels["INFO"].configure(
            text=str(sum(1 for l in self.filtered if l["level"] == "INFO")))
        self.lbl_count.configure(text=f"({len(self.filtered)} righe)")

    def _render_table(self, kw=""):
        self.tbl.configure(state="normal")
        self.tbl.delete("1.0", "end")
        for i, l in enumerate(self.filtered):
            tr  = "roweven" if i % 2 == 0 else "rowodd"
            lvl = l["level"]
            msg = (l["message"][:180]
                   + ("..." if len(l["message"]) > 180 else ""))
            self.tbl.insert("end", f"{l['n']:>5}  ",  ("dim", tr))
            self.tbl.insert("end", f"{l['timestamp']:<20}  ", ("dim", tr))
            self.tbl.insert("end", f"{lvl:<7}  ",  (lvl, tr))
            self.tbl.insert("end", f"{l['component']:<14}  ", ("comp", tr))
            if kw and kw in msg.lower():
                idx = msg.lower().find(kw)
                self.tbl.insert("end", msg[:idx], (tr,))
                self.tbl.insert("end", msg[idx:idx+len(kw)], ("hl", tr))
                self.tbl.insert("end", msg[idx+len(kw):] + "\n", (tr,))
            else:
                self.tbl.insert("end", msg + "\n", (tr,))
        self.tbl.configure(state="disabled")

    def _render_patterns(self):
        sm = defaultdict(lambda: {"count": 0, "level": "INFO"})
        for l in self.filtered:
            s = norm_sig(l["message"])
            sm[s]["count"] += 1
            sm[s]["level"] = l["level"]
        top = sorted(sm.items(), key=lambda x: -x[1]["count"])[:10]
        mc  = top[0][1]["count"] if top else 1
        self.patterns_box.configure(state="normal")
        self.patterns_box.delete("0.0", "end")
        for sig, data in top:
            pct   = int((data["count"] / mc) * 20)
            bar   = "#" * pct + "." * (20 - pct)
            label = sig[:65] + "..." if len(sig) > 65 else sig
            self.patterns_box.insert(
                "end",
                f"[{data['level']:<5}]  {data['count']:>3}x  [{bar}]\n"
                f"  {label}\n\n")
        self.patterns_box.configure(state="disabled")

    def _render_timeline(self):
        self.timeline_canvas.set_data(build_timeline(self.filtered))

    def _render_comp(self):
        comp = defaultdict(
            lambda: {"ERROR": 0, "WARN": 0, "INFO": 0, "DEBUG": 0, "total": 0})
        for l in self.filtered:
            comp[l["component"]][l["level"]] += 1
            comp[l["component"]]["total"]    += 1
        self.comp_box.configure(state="normal")
        self.comp_box.delete("0.0", "end")
        self.comp_box.insert(
            "end",
            f"{'COMPONENTE':<20} {'TOT':>5} {'ERR':>5} "
            f"{'WARN':>5} {'INFO':>5} {'DEBUG':>5}\n")
        self.comp_box.insert("end", "-" * 55 + "\n")
        for c, v in sorted(comp.items(), key=lambda x: -x[1]["total"]):
            self.comp_box.insert(
                "end",
                f"{c:<20} {v['total']:>5} {v['ERROR']:>5} "
                f"{v['WARN']:>5} {v['INFO']:>5} {v['DEBUG']:>5}\n")
        self.comp_box.configure(state="disabled")

    def _render_ai(self):
        for w in self.ai_container.winfo_children():
            w.destroy()
        insights = ai_analysis(self.filtered)
        if not insights:
            ctk.CTkLabel(
                self.ai_container,
                text="Nessun dato. Carica un log prima.",
                font=("Segoe UI", 13),
                text_color=COLORS["text2"]).pack(pady=30)
            return
        for badge, title, desc, color in insights:
            card = ctk.CTkFrame(
                self.ai_container, fg_color=COLORS["surface"], corner_radius=10)
            card.pack(fill="x", pady=6, padx=4)
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(12, 4))
            ctk.CTkLabel(
                top, text=f" {badge} ",
                font=("Segoe UI", 10, "bold"),
                fg_color=color, text_color="#0f1117",
                corner_radius=4).pack(side="left")
            ctk.CTkLabel(
                top, text=f"  {title}",
                font=("Segoe UI", 13, "bold"),
                text_color=color).pack(side="left")
            ctk.CTkLabel(
                card, text=desc,
                font=("Segoe UI", 12), text_color=COLORS["text"],
                wraplength=900, anchor="w",
                justify="left").pack(anchor="w", padx=14, pady=(0, 12))

    # ------------------------------------------------------------------
    # AZIONI SIEMENS
    # ------------------------------------------------------------------
    def open_siemens_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.siemens_csv_path = path
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self._load_siemens_data(content, os.path.basename(path))
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def _load_siemens_data(self, content, fname):
        self.siemens_headers, self.siemens_rows = parse_siemens_csv(content)
        if not self.siemens_rows:
            messagebox.showwarning("Attenzione",
                                   "Nessun dato valido nel CSV.")
            return
        n     = len(self.siemens_rows)
        csv_t = detect_csv_type(self.siemens_headers)
        tipo  = ("Front Firewall (Persico)"
                 if csv_t == "front_firewall" else "Siemens generico")
        self._last_csv_type = csv_t
        self.siemens_info_lbl.configure(
            text=f"{fname}  |  {n} record  |  tipo: {tipo}")
        numeric = [
            h for h in self.siemens_headers
            if h not in ("Record", "Date", "Time", "UTC Time")
            and self.siemens_rows
            and isinstance(self.siemens_rows[0].get(h), float)
        ]
        opts = ["-"] + numeric
        self.siemens_col_menu.configure(values=numeric if numeric else ["-"])
        self.siemens_col2_menu.configure(values=opts)
        if numeric:
            self.siemens_col_var.set(numeric[0])
        self.siemens_col2_var.set("-")
        self._refresh_siemens()
        self.set_status(f"CSV Siemens caricato: {fname} ({n} record)")

    def _on_col_change(self, _=None):
        self._refresh_siemens()

    def _refresh_siemens(self):
        if not self.siemens_rows:
            return
        rows   = self.siemens_rows
        times  = [r["_ts"] for r in rows]
        col1   = self.siemens_col_var.get()
        col2   = self.siemens_col2_var.get()
        series = {}
        pal    = ["#6c63ff", "#00d4ff", "#52c41a", "#faad14"]
        if col1 and col1 != "-":
            series[col1] = (pal[0], [r.get(col1) for r in rows])
        if col2 and col2 != "-":
            series[col2] = (pal[1], [r.get(col2) for r in rows])
        self.line_chart.set_data(times, series)
        pump_col = None
        for pk in ["Stato_Pompa", "stato_pompa", "pump_state", "PumpState"]:
            if pk in (self.siemens_headers or []):
                pump_col = pk
                break
        if pump_col:
            self.pump_canvas.set_data(
                times, [r.get(pump_col, 0) for r in rows])
        anomalies, stats = detect_anomalies(rows, self.siemens_headers)
        for w in self.anomaly_container.winfo_children():
            w.destroy()
        if not anomalies:
            ctk.CTkLabel(
                self.anomaly_container,
                text="Nessuna anomalia rilevata.",
                font=("Segoe UI", 12),
                text_color=COLORS["info"]).pack(pady=8, anchor="w")
        else:
            for badge, title, desc, color in anomalies[:12]:
                card = ctk.CTkFrame(
                    self.anomaly_container,
                    fg_color=COLORS["surface"], corner_radius=8)
                card.pack(fill="x", pady=3)
                top = ctk.CTkFrame(card, fg_color="transparent")
                top.pack(fill="x", padx=10, pady=(8, 2))
                ctk.CTkLabel(
                    top, text=f" {badge} ",
                    font=("Segoe UI", 9, "bold"),
                    fg_color=color, text_color="#0f1117",
                    corner_radius=3).pack(side="left")
                ctk.CTkLabel(
                    top, text=f"  {title}",
                    font=("Segoe UI", 11, "bold"),
                    text_color=color).pack(side="left")
                ctk.CTkLabel(
                    card, text=desc,
                    font=("Segoe UI", 10), text_color=COLORS["text"],
                    wraplength=340, anchor="w",
                    justify="left").pack(anchor="w", padx=10, pady=(0, 8))
        self.stats_box.configure(state="normal")
        self.stats_box.delete("0.0", "end")
        self.stats_box.insert(
            "end",
            f"{'COLONNA':<22} {'MIN':>8} {'MAX':>8} "
            f"{'MEDIA':>8} {'STD':>8}\n" + "-" * 52 + "\n")
        for col, st in stats.items():
            self.stats_box.insert(
                "end",
                f"{col:<22} {st['min']:>8.2f} {st['max']:>8.2f} "
                f"{st['mean']:>8.2f} {st['std']:>8.2f}\n")
        self.stats_box.configure(state="disabled")
        self.raw_box.configure(state="normal")
        self.raw_box.delete("0.0", "end")
        cols   = [h for h in self.siemens_headers if h != "_ts"]
        header = " | ".join(f"{c:<14}" for c in cols[:8])
        self.raw_box.insert(
            "end", header + "\n" + "-" * min(len(header), 100) + "\n")
        for r in rows[:50]:
            self.raw_box.insert(
                "end",
                " | ".join(f"{str(r.get(c, '')):<14}" for c in cols[:8])
                + "\n")
        if len(rows) > 50:
            self.raw_box.insert(
                "end", f"... ({len(rows)-50} righe aggiuntive)\n")
        self.raw_box.configure(state="disabled")

    def export_siemens_report(self):
        if not self.siemens_rows:
            messagebox.showwarning("Attenzione",
                                   "Nessun dato Siemens caricato.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text report", "*.txt")])
        if not path:
            return
        anomalies, stats = detect_anomalies(
            self.siemens_rows, self.siemens_headers)
        with open(path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\nREPORT DATI SIEMENS\n" + "=" * 60 + "\n\n")
            f.write(f"Record totali: {len(self.siemens_rows)}\n")
            f.write(f"Colonne: {', '.join(self.siemens_headers)}\n\n")
            f.write("STATISTICHE\n" + "-" * 40 + "\n")
            for col, st in stats.items():
                f.write(
                    f"{col}: min={st['min']:.2f} max={st['max']:.2f} "
                    f"media={st['mean']:.2f} std={st['std']:.2f}\n")
            f.write("\nANOMALIE\n" + "-" * 40 + "\n")
            if anomalies:
                for badge, title, desc, _ in anomalies:
                    f.write(f"[{badge}] {title}\n  {desc}\n\n")
            else:
                f.write("Nessuna anomalia rilevata.\n")
        self.set_status(f"Report esportato: {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # EXPORT LOG JSON / CSV
    # ------------------------------------------------------------------
    def export_json(self):
        if not self.filtered:
            messagebox.showwarning("Attenzione", "Nessun dato.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                [{"line":      l["n"],
                  "timestamp": l["timestamp"],
                  "level":     l["level"],
                  "component": l["component"],
                  "message":   l["message"]}
                 for l in self.filtered],
                f, indent=2, ensure_ascii=False)
        self.set_status(f"JSON esportato: {os.path.basename(path)}")

    def export_csv(self):
        if not self.filtered:
            messagebox.showwarning("Attenzione", "Nessun dato.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["#", "Timestamp", "Level", "Component", "Message"])
            for l in self.filtered:
                w.writerow([l["n"], l["timestamp"], l["level"],
                            l["component"], l["message"]])
        self.set_status(f"CSV esportato: {os.path.basename(path)}")


# ----------------------------------------------------------------------
if __name__ == "__main__":
    app = LogAnalyzerApp()
    app.mainloop()
