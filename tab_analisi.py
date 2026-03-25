# -*- coding: utf-8 -*-
"""Mixin per i sotto-tab del tab Analisi Log:
  - _build_analisi  (pannello log con filtri e tabella)
  - _build_timeline_tab
  - _build_ai_tab
  - _build_siemens_tab
  - export_pdf_grafico (Front Firewall)

Importato da app_main.py come:
    from tab_analisi import AnalisiMixin
"""
import os, threading
from tkinter import filedialog, messagebox
import tkinter as tk
import customtkinter as ctk

from colors import COLORS, LEVEL_COLORS, LEVEL_BG, LEVEL_HOVER
from charts import TimelineCanvas, LineChart, PumpCanvas
from pdf_export import generate_front_firewall_pdf, detect_csv_type


class AnalisiMixin:
    """Mixin che porta i tab Analisi, Timeline, AI e Siemens in LogAnalyzerApp."""

    # ------------------------------------------------------------------
    # TAB ANALISI
    # ------------------------------------------------------------------
    def _build_analisi(self, parent):
        paned = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        paned.pack(fill="both", expand=True, pady=4)
        lw = ctk.CTkFrame(paned, fg_color=COLORS["bg"], width=375)
        lw.pack(side="left", fill="y", padx=(0, 8)); lw.pack_propagate(False)
        left = ctk.CTkScrollableFrame(lw, fg_color=COLORS["bg"],
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
        ctk.CTkLabel(lf, text="LIVELLO", font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w")
        btns = ctk.CTkFrame(lf, fg_color="transparent")
        btns.pack(anchor="w")
        self.lvl_btns = {}
        for lvl in ["ERROR", "WARN", "INFO", "DEBUG"]:
            b = ctk.CTkButton(btns, text=lvl, width=66, height=26,
                              fg_color=LEVEL_BG[lvl], hover_color=LEVEL_HOVER[lvl],
                              text_color=LEVEL_COLORS[lvl],
                              font=("Segoe UI", 11, "bold"),
                              command=lambda l=lvl: self.toggle_level(l))
            b.pack(side="left", padx=(0, 4), pady=4)
            self.lvl_btns[lvl] = b
        kf = ctk.CTkFrame(fcard, fg_color="transparent")
        kf.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(kf, text="KEYWORD", font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w")
        self.entry_kw = ctk.CTkEntry(
            kf, placeholder_text="es. timeout, alarm...",
            fg_color=COLORS["surface2"], border_color=COLORS["border"],
            text_color=COLORS["text"], height=30)
        self.entry_kw.pack(fill="x")
        self.entry_kw.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        tf = ctk.CTkFrame(fcard, fg_color="transparent")
        tf.pack(fill="x", padx=10, pady=(4, 4))
        ctk.CTkLabel(tf, text="INTERVALLO", font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w")
        tr = ctk.CTkFrame(tf, fg_color="transparent")
        tr.pack(fill="x")
        self.entry_from = ctk.CTkEntry(
            tr, placeholder_text="Dal (YYYY-MM-DD HH:MM)",
            fg_color=COLORS["surface2"], border_color=COLORS["border"],
            text_color=COLORS["text"], height=28)
        self.entry_from.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.entry_from.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        self.entry_to = ctk.CTkEntry(
            tr, placeholder_text="Al...",
            fg_color=COLORS["surface2"], border_color=COLORS["border"],
            text_color=COLORS["text"], height=28)
        self.entry_to.pack(side="left", fill="x", expand=True)
        self.entry_to.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        ctk.CTkButton(fcard, text="Reset filtri", width=110, height=26,
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
            lv = ctk.CTkLabel(sc, text="0", font=("Segoe UI", 22, "bold"), text_color=color)
            lv.pack(pady=(8, 0))
            ctk.CTkLabel(sc, text=label, font=("Segoe UI", 10),
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
        self.lbl_count = ctk.CTkLabel(th, text="", font=("Segoe UI", 12),
                                       text_color=COLORS["accent"])
        self.lbl_count.pack(side="left", padx=8)
        er = ctk.CTkFrame(th, fg_color="transparent")
        er.pack(side="right")
        ctk.CTkButton(er, text="Esporta JSON", width=110, height=28,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text"],
                      command=self.export_json).pack(side="left", padx=4)
        ctk.CTkButton(er, text="Esporta CSV", width=110, height=28,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text"],
                      command=self.export_csv).pack(side="left", padx=4)
        tf2 = ctk.CTkFrame(right, fg_color=COLORS["surface"], corner_radius=8)
        tf2.pack(fill="both", expand=True)
        ch2 = ctk.CTkFrame(tf2, fg_color=COLORS["surface2"], corner_radius=0, height=28)
        ch2.pack(fill="x"); ch2.pack_propagate(False)
        for txt, ww in [("#", 40), ("Timestamp", 160), ("Liv.", 60),
                        ("Component", 110), ("Messaggio", 500)]:
            ctk.CTkLabel(ch2, text=txt, font=("Segoe UI", 10, "bold"),
                         text_color=COLORS["text2"], width=ww, anchor="w").pack(side="left", padx=4)
        self.tbl = tk.Text(
            tf2, bg=COLORS["surface"], fg=COLORS["text"],
            font=("Courier New", 11), relief="flat", bd=0,
            selectbackground="#3a3580", highlightthickness=0,
            wrap="none", state="disabled")
        vsb = ctk.CTkScrollbar(tf2, command=self.tbl.yview)
        hsb = ctk.CTkScrollbar(tf2, orientation="horizontal", command=self.tbl.xview)
        self.tbl.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y"); hsb.pack(side="bottom", fill="x")
        self.tbl.pack(fill="both", expand=True)
        for tag, fgc, bgc in [
            ("ERROR", COLORS["error"], None), ("WARN", COLORS["warn"], None),
            ("INFO",  COLORS["info"],  None), ("DEBUG", COLORS["debug"], None),
            ("hl",   None, "#4a3a00"),
            ("dim",  COLORS["text2"], None), ("comp", COLORS["accent2"], None),
            ("roweven", None, "#1e2133"), ("rowodd", None, COLORS["surface"]),
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
        ctk.CTkLabel(parent,
                     text="Distribuzione eventi nel tempo - barre impilate per livello",
                     font=("Segoe UI", 11), text_color=COLORS["text2"]).pack(
            anchor="w", padx=4, pady=(0, 8))
        fc = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=8)
        fc.pack(fill="both", expand=True)
        self.timeline_canvas = TimelineCanvas(fc)
        self.timeline_canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self.timeline_canvas.bind("<Configure>", lambda e: self.timeline_canvas.redraw())
        self._sec(parent, "Riepilogo per componente")
        cf = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=8)
        cf.pack(fill="both", expand=True, pady=(8, 0))
        self.comp_box = ctk.CTkTextbox(
            cf, font=("Courier New", 11), fg_color=COLORS["surface"],
            text_color=COLORS["text"], border_width=0)
        self.comp_box.pack(fill="both", expand=True, padx=8, pady=8)

    # ------------------------------------------------------------------
    # TAB AI
    # ------------------------------------------------------------------
    def _build_ai_tab(self, parent):
        self._sec(parent, "AI Insights - Analisi automatica del log")
        ctk.CTkLabel(parent,
                     text="Suggerimenti e rilevamento anomalie basati sul contenuto del log",
                     font=("Segoe UI", 11), text_color=COLORS["text2"]).pack(
            anchor="w", padx=4, pady=(0, 10))
        scroll = ctk.CTkScrollableFrame(parent, fg_color=COLORS["bg"], corner_radius=0)
        scroll.pack(fill="both", expand=True)
        self.ai_container = scroll

    # ------------------------------------------------------------------
    # TAB SIEMENS
    # ------------------------------------------------------------------
    def _build_siemens_tab(self, parent):
        toolbar = ctk.CTkFrame(parent, fg_color=COLORS["surface"],
                               corner_radius=8, height=44)
        toolbar.pack(fill="x", pady=(0, 8)); toolbar.pack_propagate(False)
        ctk.CTkButton(toolbar, text="Apri CSV Siemens", width=150, height=30,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"],
                      command=self.open_siemens_csv).pack(side="left", padx=10, pady=7)
        self.siemens_info_lbl = ctk.CTkLabel(
            toolbar, text="Nessun file caricato",
            font=("Segoe UI", 11), text_color=COLORS["text2"])
        self.siemens_info_lbl.pack(side="left", padx=10)
        ctk.CTkButton(toolbar, text="Genera PDF Grafico", width=150, height=30,
                      fg_color="#7c3aed", hover_color="#6d28d9",
                      text_color=COLORS["text"],
                      command=self.export_pdf_grafico).pack(side="right", padx=6, pady=7)
        ctk.CTkButton(toolbar, text="Esporta report", width=120, height=30,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text"],
                      command=self.export_siemens_report).pack(side="right", padx=10, pady=7)
        sel_frame = ctk.CTkFrame(parent, fg_color=COLORS["surface"],
                                 corner_radius=8, height=40)
        sel_frame.pack(fill="x", pady=(0, 8)); sel_frame.pack_propagate(False)
        ctk.CTkLabel(sel_frame, text="Visualizza:",
                     font=("Segoe UI", 11), text_color=COLORS["text2"]).pack(
            side="left", padx=10, pady=8)
        self.siemens_col_var = ctk.StringVar(value="Temp_Vasca_01")
        self.siemens_col_menu = ctk.CTkOptionMenu(
            sel_frame, variable=self.siemens_col_var, values=["-"], width=180,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"], command=self._on_col_change)
        self.siemens_col_menu.pack(side="left", padx=4, pady=8)
        ctk.CTkLabel(sel_frame, text="vs",
                     font=("Segoe UI", 11), text_color=COLORS["text2"]).pack(
            side="left", padx=4)
        self.siemens_col2_var = ctk.StringVar(value="-")
        self.siemens_col2_menu = ctk.CTkOptionMenu(
            sel_frame, variable=self.siemens_col2_var, values=["-"], width=180,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"], command=self._on_col_change)
        self.siemens_col2_menu.pack(side="left", padx=4, pady=8)
        charts_frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        charts_frame.pack(fill="both", expand=True)
        chart_left = ctk.CTkFrame(charts_frame, fg_color=COLORS["bg"])
        chart_left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._sec(chart_left, "Grafico dati")
        lc_frame = ctk.CTkFrame(chart_left, fg_color=COLORS["surface"], corner_radius=8)
        lc_frame.pack(fill="both", expand=True)
        self.line_chart = LineChart(lc_frame, height=220)
        self.line_chart.pack(fill="both", expand=True, padx=6, pady=6)
        self.line_chart.bind("<Configure>", lambda e: self.line_chart.redraw())
        self._sec(chart_left, "Stato Pompa")
        pc_frame = ctk.CTkFrame(chart_left, fg_color=COLORS["surface"], corner_radius=8)
        pc_frame.pack(fill="x")
        self.pump_canvas = PumpCanvas(pc_frame, height=70)
        self.pump_canvas.pack(fill="x", padx=6, pady=6)
        self.pump_canvas.bind("<Configure>", lambda e: self.pump_canvas.redraw())
        chart_right = ctk.CTkFrame(charts_frame, fg_color=COLORS["bg"], width=380)
        chart_right.pack(side="left", fill="y"); chart_right.pack_propagate(False)
        right_scroll = ctk.CTkScrollableFrame(
            chart_right, fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        right_scroll.pack(fill="both", expand=True)
        self._sec(right_scroll, "Anomalie rilevate")
        self.anomaly_container = ctk.CTkFrame(right_scroll, fg_color=COLORS["bg"])
        self.anomaly_container.pack(fill="x", pady=(0, 8))
        self._sec(right_scroll, "Statistiche colonne")
        stats_frame = ctk.CTkFrame(right_scroll, fg_color=COLORS["surface"], corner_radius=8)
        stats_frame.pack(fill="x", pady=(0, 8))
        self.stats_box = ctk.CTkTextbox(
            stats_frame, height=160, font=("Courier New", 10),
            fg_color=COLORS["surface"], text_color=COLORS["text"], border_width=0)
        self.stats_box.pack(fill="x", padx=6, pady=6)
        self._sec(right_scroll, "Dati grezzi")
        raw_frame = ctk.CTkFrame(right_scroll, fg_color=COLORS["surface"], corner_radius=8)
        raw_frame.pack(fill="x", pady=(0, 8))
        self.raw_box = ctk.CTkTextbox(
            raw_frame, height=200, font=("Courier New", 9),
            fg_color=COLORS["surface"], text_color=COLORS["text2"],
            border_width=0, wrap="none")
        self.raw_box.pack(fill="x", padx=6, pady=6)

    # ------------------------------------------------------------------
    # Export PDF grafico (Front Firewall Persico)
    # ------------------------------------------------------------------
    def export_pdf_grafico(self):
        if not self.siemens_rows:
            messagebox.showwarning("Attenzione", "Nessun dato Siemens caricato."); return
        csv_t = detect_csv_type(self.siemens_headers)
        if csv_t != "front_firewall":
            messagebox.showwarning(
                "Attenzione",
                "Funzione disponibile solo per dati Front Firewall (Persico).\n"
                "Le colonne rilevate non corrispondono al profilo."); return
        base_name = (os.path.splitext(os.path.basename(self.siemens_csv_path))[0]
                     if hasattr(self, "siemens_csv_path") and self.siemens_csv_path
                     else "Grafico-Front_Firewall")
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", initialfile=f"{base_name}.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not path: return
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
