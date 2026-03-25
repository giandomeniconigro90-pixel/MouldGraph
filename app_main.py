# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import re, json, csv, os, math, threading, random
import tkinter.simpledialog as simpledialog
from datetime import datetime
from collections import defaultdict
import queue as _queue
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
MAX_LIVE_POINTS = 500

from colors import COLORS, LEVEL_COLORS, LEVEL_BG, LEVEL_HOVER
from log_parser import norm_level, parse_ts, parse_line, parse_log, norm_sig, ai_analysis, build_timeline
from csv_parser import (parse_siemens_csv, detect_anomalies, parse_universal_csv,
                         _is_long_cycle_csv, _parse_long_cycle_csv, _uc_build_series)
from charts import TimelineCanvas, LineChart, PumpCanvas, _isolate_scroll
from plot_canvas import InteractivePlotCanvas
from pdf_export import (generate_plant_pdf, generate_lamborghini_pdf,
                         generate_front_firewall_pdf, detect_csv_type,
                         _autodetect_profile, _validate_csv, PROFILES, PRESSASTAMPI)

class LogAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MouldGraph")
        w,h=1100,720;sw=self.winfo_screenwidth();sh=self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}");self.minsize(1100,700)
        self.configure(fg_color=COLORS["bg"])
        self.all_parsed=[];self.filtered=[]
        self.active_levels={"ERROR":True,"WARN":True,"INFO":True,"DEBUG":True}
        self.siemens_headers=[];self.siemens_rows=[]
        self._last_csv_type="siemens"
        # Live Data
        self._live_queue        = _queue.Queue(maxsize=2000)  # limite memoria
        self._live_running      = threading.Event()  # set=in corso, clear=fermo
        self._live_paused       = threading.Event()  # set=in pausa, clear=attivo
        self._live_thread       = None
        self._live_rows         = []     # {col: val, …} accumulati
        self._live_headers      = []
        self._live_col_meta     = {}
        self._live_numeric_cols = []
        self._live_plot_cols    = []
        # Allarmi live
        self._live_alarm_rules  = []     # [{col, lo, hi, label, active}]
        self._live_alarm_count  = 0      # contatore totale scatti
        self._live_alarm_active = set()  # colonne attualmente in allarme
        # interpolazione
        self._live_interp_job   = None   # after() handle del timer interpolazione
        # multi-grafico
        self._live_multi_mode   = False
        self._live_multi_ipcs   = {}     # {group_name: InteractivePlotCanvas}
        self._build_ui()

    def _build_ui(self):
        hdr=ctk.CTkFrame(self,fg_color=COLORS["surface"],corner_radius=0,height=54)
        hdr.pack(fill="x",side="top");hdr.pack_propagate(False)
        ctk.CTkLabel(hdr,text="Log",font=("Segoe UI",20,"bold"),text_color=COLORS["text"]).pack(side="left",padx=(18,0),pady=10)
        ctk.CTkLabel(hdr,text="Analyzer",font=("Segoe UI",20,"bold"),text_color=COLORS["accent"]).pack(side="left",pady=10)
        # for txt,cmd,fg in[("Analizza",self.analyze,COLORS["accent"]),("Apri file",self.open_file,COLORS["surface2"])]:
        #     ctk.CTkButton(hdr,text=txt,width=100,height=30,fg_color=fg,hover_color=COLORS["border"],
        #                    text_color=COLORS["text"],command=cmd).pack(side="right",padx=5,pady=10)
        sb=ctk.CTkFrame(self,fg_color=COLORS["surface"],corner_radius=0,height=26)
        sb.pack(fill="x",side="bottom");sb.pack_propagate(False)
        self.status_lbl=ctk.CTkLabel(sb,text="Pronto.",font=("Segoe UI",11),text_color=COLORS["text2"])
        self.status_lbl.pack(side="left",padx=12)
        self.tabs=ctk.CTkTabview(self,fg_color=COLORS["bg"],
                                  segmented_button_fg_color=COLORS["surface"],
                                  segmented_button_selected_color=COLORS["accent"],
                                  segmented_button_selected_hover_color="#5a52e0",
                                  segmented_button_unselected_color=COLORS["surface"],
                                  segmented_button_unselected_hover_color=COLORS["surface2"],
                                  text_color=COLORS["text"])
        self.tabs.pack(fill="both",expand=True,padx=10,pady=6)
        for t in["  Grafici  ", "  Dati CSV  ", "  Live Data  ", "  Come usare  "]:
            self.tabs.add(t)

        # ── lazy loading: costruisce ogni tab solo alla prima selezione ──
        self._tabs_built = set()
        self._tab_builders = {
            "  Grafici  "    : self._build_grafici_tab,
            "  Dati CSV  "   : self.build_csv_tab,
            "  Live Data  "  : self._build_live_tab,
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

    # -- TAB ANALISI --
    def _build_analisi(self,parent):
        paned=ctk.CTkFrame(parent,fg_color=COLORS["bg"])
        paned.pack(fill="both",expand=True,pady=4)
        lw=ctk.CTkFrame(paned,fg_color=COLORS["bg"],width=375)
        lw.pack(side="left",fill="y",padx=(0,8));lw.pack_propagate(False)
        left=ctk.CTkScrollableFrame(lw,fg_color=COLORS["bg"],scrollbar_button_color=COLORS["border"],
                                     scrollbar_button_hover_color=COLORS["accent"])
        left.pack(fill="both",expand=True)
        self._sec(left,"Input Log")
        self.txt_input=ctk.CTkTextbox(left,height=130,font=("Courier New",10),
                                       fg_color=COLORS["surface2"],text_color=COLORS["text"],
                                       border_color=COLORS["border"],border_width=1)
        self.txt_input.pack(fill="x",pady=(0,8))
        self.txt_input.insert("0.0","Incolla log qui oppure usa Apri file / Demo...")
        self._sec(left,"Filtri")
        fcard=ctk.CTkFrame(left,fg_color=COLORS["surface"],corner_radius=8)
        fcard.pack(fill="x",pady=(0,8))
        lf=ctk.CTkFrame(fcard,fg_color="transparent");lf.pack(fill="x",padx=10,pady=(10,4))
        ctk.CTkLabel(lf,text="LIVELLO",font=("Segoe UI",10,"bold"),text_color=COLORS["text2"]).pack(anchor="w")
        btns=ctk.CTkFrame(lf,fg_color="transparent");btns.pack(anchor="w")
        self.lvl_btns={}
        for lvl in["ERROR","WARN","INFO","DEBUG"]:
            b=ctk.CTkButton(btns,text=lvl,width=66,height=26,fg_color=LEVEL_BG[lvl],
                             hover_color=LEVEL_HOVER[lvl],text_color=LEVEL_COLORS[lvl],
                             font=("Segoe UI",11,"bold"),command=lambda l=lvl:self.toggle_level(l))
            b.pack(side="left",padx=(0,4),pady=4);self.lvl_btns[lvl]=b
        kf=ctk.CTkFrame(fcard,fg_color="transparent");kf.pack(fill="x",padx=10,pady=4)
        ctk.CTkLabel(kf,text="KEYWORD",font=("Segoe UI",10,"bold"),text_color=COLORS["text2"]).pack(anchor="w")
        self.entry_kw=ctk.CTkEntry(kf,placeholder_text="es. timeout, alarm...",
                                    fg_color=COLORS["surface2"],border_color=COLORS["border"],
                                    text_color=COLORS["text"],height=30)
        self.entry_kw.pack(fill="x")
        self.entry_kw.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        tf=ctk.CTkFrame(fcard,fg_color="transparent");tf.pack(fill="x",padx=10,pady=(4,4))
        ctk.CTkLabel(tf,text="INTERVALLO",font=("Segoe UI",10,"bold"),text_color=COLORS["text2"]).pack(anchor="w")
        tr=ctk.CTkFrame(tf,fg_color="transparent");tr.pack(fill="x")
        self.entry_from=ctk.CTkEntry(tr,placeholder_text="Dal (YYYY-MM-DD HH:MM)",
                                      fg_color=COLORS["surface2"],border_color=COLORS["border"],
                                      text_color=COLORS["text"],height=28)
        self.entry_from.pack(side="left",fill="x",expand=True,padx=(0,4))
        self.entry_from.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        self.entry_to=ctk.CTkEntry(tr,placeholder_text="Al...",
                                    fg_color=COLORS["surface2"],border_color=COLORS["border"],
                                    text_color=COLORS["text"],height=28)
        self.entry_to.pack(side="left",fill="x",expand=True)
        self.entry_to.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        ctk.CTkButton(fcard,text="Reset filtri",width=110,height=26,fg_color=COLORS["surface2"],
                       hover_color=COLORS["border"],text_color=COLORS["text2"],
                       command=self.reset_filters).pack(anchor="e",padx=10,pady=(4,10))
        self._sec(left,"Statistiche")
        srow=ctk.CTkFrame(left,fg_color="transparent");srow.pack(fill="x",pady=(0,8))
        self.stat_labels={}
        for key,color,label in[("total",COLORS["accent2"],"Totale"),("ERROR",COLORS["error"],"Errori"),
                                 ("WARN",COLORS["warn"],"Warning"),("INFO",COLORS["info"],"Info")]:
            sc=ctk.CTkFrame(srow,fg_color=COLORS["surface"],corner_radius=8)
            sc.pack(side="left",expand=True,fill="x",padx=2)
            lv=ctk.CTkLabel(sc,text="0",font=("Segoe UI",22,"bold"),text_color=color)
            lv.pack(pady=(8,0))
            ctk.CTkLabel(sc,text=label,font=("Segoe UI",10),text_color=COLORS["text2"]).pack(pady=(0,8))
            self.stat_labels[key]=lv
        self._sec(left,"Pattern / Firme (Top 10)")
        pf=ctk.CTkFrame(left,fg_color=COLORS["surface"],corner_radius=8)
        pf.pack(fill="x",pady=(0,8))
        self.patterns_box=ctk.CTkTextbox(pf,height=280,font=("Courier New",10),
                                          fg_color=COLORS["surface"],text_color=COLORS["text2"],
                                          border_width=0,wrap="word")
        self.patterns_box.pack(fill="x",padx=6,pady=6)
        right=ctk.CTkFrame(paned,fg_color=COLORS["bg"])
        right.pack(side="left",fill="both",expand=True)
        th=ctk.CTkFrame(right,fg_color="transparent");th.pack(fill="x",pady=(0,6))
        self._sec_inline(th,"Log Dettaglio")
        self.lbl_count=ctk.CTkLabel(th,text="",font=("Segoe UI",12),text_color=COLORS["accent"])
        self.lbl_count.pack(side="left",padx=8)
        er=ctk.CTkFrame(th,fg_color="transparent");er.pack(side="right")
        ctk.CTkButton(er,text="Esporta JSON",width=110,height=28,fg_color=COLORS["surface2"],
                       hover_color=COLORS["border"],text_color=COLORS["text"],command=self.export_json).pack(side="left",padx=4)
        ctk.CTkButton(er,text="Esporta CSV",width=110,height=28,fg_color=COLORS["surface2"],
                       hover_color=COLORS["border"],text_color=COLORS["text"],command=self.export_csv).pack(side="left",padx=4)
        tf2=ctk.CTkFrame(right,fg_color=COLORS["surface"],corner_radius=8)
        tf2.pack(fill="both",expand=True)
        ch2=ctk.CTkFrame(tf2,fg_color=COLORS["surface2"],corner_radius=0,height=28)
        ch2.pack(fill="x");ch2.pack_propagate(False)
        for txt,ww in[("#",40),("Timestamp",160),("Liv.",60),("Component",110),("Messaggio",500)]:
            ctk.CTkLabel(ch2,text=txt,font=("Segoe UI",10,"bold"),text_color=COLORS["text2"],width=ww,anchor="w").pack(side="left",padx=4)
        self.tbl=tk.Text(tf2,bg=COLORS["surface"],fg=COLORS["text"],font=("Courier New",11),
                          relief="flat",bd=0,selectbackground="#3a3580",highlightthickness=0,
                          wrap="none",state="disabled")
        vsb=ctk.CTkScrollbar(tf2,command=self.tbl.yview)
        hsb=ctk.CTkScrollbar(tf2,orientation="horizontal",command=self.tbl.xview)
        self.tbl.configure(yscrollcommand=vsb.set,xscrollcommand=hsb.set)
        vsb.pack(side="right",fill="y");hsb.pack(side="bottom",fill="x")
        self.tbl.pack(fill="both",expand=True)
        for tag,fgc,bgc in[("ERROR",COLORS["error"],None),("WARN",COLORS["warn"],None),
                             ("INFO",COLORS["info"],None),("DEBUG",COLORS["debug"],None),
                             ("hl",None,"#4a3a00"),("dim",COLORS["text2"],None),
                             ("comp",COLORS["accent2"],None),("roweven",None,"#1e2133"),
                             ("rowodd",None,COLORS["surface"])]:
            kw={};
            if fgc:kw["foreground"]=fgc
            if bgc:kw["background"]=bgc
            self.tbl.tag_configure(tag,**kw)

    # -- TAB TIMELINE --
    def _build_timeline_tab(self,parent):
        self._sec(parent,"Timeline eventi")
        ctk.CTkLabel(parent,text="Distribuzione eventi nel tempo - barre impilate per livello",
                     font=("Segoe UI",11),text_color=COLORS["text2"]).pack(anchor="w",padx=4,pady=(0,8))
        fc=ctk.CTkFrame(parent,fg_color=COLORS["surface"],corner_radius=8)
        fc.pack(fill="both",expand=True)
        self.timeline_canvas=TimelineCanvas(fc)
        self.timeline_canvas.pack(fill="both",expand=True,padx=8,pady=8)
        self.timeline_canvas.bind("<Configure>",lambda e:self.timeline_canvas.redraw())
        self._sec(parent,"Riepilogo per componente")
        cf=ctk.CTkFrame(parent,fg_color=COLORS["surface"],corner_radius=8)
        cf.pack(fill="both",expand=True,pady=(8,0))
        self.comp_box=ctk.CTkTextbox(cf,font=("Courier New",11),fg_color=COLORS["surface"],
                                      text_color=COLORS["text"],border_width=0)
        self.comp_box.pack(fill="both",expand=True,padx=8,pady=8)

    # -- TAB AI --
    def _build_ai_tab(self,parent):
        self._sec(parent,"AI Insights - Analisi automatica del log")
        ctk.CTkLabel(parent,text="Suggerimenti e rilevamento anomalie basati sul contenuto del log",
                     font=("Segoe UI",11),text_color=COLORS["text2"]).pack(anchor="w",padx=4,pady=(0,10))
        scroll=ctk.CTkScrollableFrame(parent,fg_color=COLORS["bg"],corner_radius=0)
        scroll.pack(fill="both",expand=True)
        self.ai_container=scroll

    # -- TAB DATI SIEMENS --
    def _build_siemens_tab(self,parent):
        # toolbar
        toolbar=ctk.CTkFrame(parent,fg_color=COLORS["surface"],corner_radius=8,height=44)
        toolbar.pack(fill="x",pady=(0,8));toolbar.pack_propagate(False)
        ctk.CTkButton(toolbar,text="Apri CSV Siemens",width=150,height=30,
                       fg_color=COLORS["accent"],hover_color="#5a52e0",text_color=COLORS["text"],
                       command=self.open_siemens_csv).pack(side="left",padx=10,pady=7)
        self.siemens_info_lbl=ctk.CTkLabel(toolbar,text="Nessun file caricato",
                                            font=("Segoe UI",11),text_color=COLORS["text2"])
        self.siemens_info_lbl.pack(side="left",padx=10)
        ctk.CTkButton(toolbar,text="Genera PDF Grafico",width=150,height=30,
                       fg_color="#7c3aed",hover_color="#6d28d9",text_color=COLORS["text"],
                       command=self.export_pdf_grafico).pack(side="right",padx=6,pady=7)
        ctk.CTkButton(toolbar,text="Esporta report",width=120,height=30,
                       fg_color=COLORS["surface2"],hover_color=COLORS["border"],text_color=COLORS["text"],
                       command=self.export_siemens_report).pack(side="right",padx=10,pady=7)

        # selector colonne
        sel_frame=ctk.CTkFrame(parent,fg_color=COLORS["surface"],corner_radius=8,height=40)
        sel_frame.pack(fill="x",pady=(0,8));sel_frame.pack_propagate(False)
        ctk.CTkLabel(sel_frame,text="Visualizza:",font=("Segoe UI",11),text_color=COLORS["text2"]).pack(side="left",padx=10,pady=8)
        self.siemens_col_var=ctk.StringVar(value="Temp_Vasca_01")
        self.siemens_col_menu=ctk.CTkOptionMenu(sel_frame,variable=self.siemens_col_var,
                                                  values=["-"],width=180,
                                                  fg_color=COLORS["surface2"],
                                                  button_color=COLORS["accent"],
                                                  text_color=COLORS["text"],
                                                  command=self._on_col_change)
        self.siemens_col_menu.pack(side="left",padx=4,pady=8)
        ctk.CTkLabel(sel_frame,text="vs",font=("Segoe UI",11),text_color=COLORS["text2"]).pack(side="left",padx=4)
        self.siemens_col2_var=ctk.StringVar(value="-")
        self.siemens_col2_menu=ctk.CTkOptionMenu(sel_frame,variable=self.siemens_col2_var,
                                                   values=["-"],width=180,
                                                   fg_color=COLORS["surface2"],
                                                   button_color=COLORS["accent"],
                                                   text_color=COLORS["text"],
                                                   command=self._on_col_change)
        self.siemens_col2_menu.pack(side="left",padx=4,pady=8)

        # charts
        charts_frame=ctk.CTkFrame(parent,fg_color=COLORS["bg"])
        charts_frame.pack(fill="both",expand=True)

        # left: grafico linee + pompa
        chart_left=ctk.CTkFrame(charts_frame,fg_color=COLORS["bg"])
        chart_left.pack(side="left",fill="both",expand=True,padx=(0,6))
        self._sec(chart_left,"Grafico dati")
        lc_frame=ctk.CTkFrame(chart_left,fg_color=COLORS["surface"],corner_radius=8)
        lc_frame.pack(fill="both",expand=True)
        self.line_chart=LineChart(lc_frame,height=220)
        self.line_chart.pack(fill="both",expand=True,padx=6,pady=6)
        self.line_chart.bind("<Configure>",lambda e:self.line_chart.redraw())
        self._sec(chart_left,"Stato Pompa")
        pc_frame=ctk.CTkFrame(chart_left,fg_color=COLORS["surface"],corner_radius=8)
        pc_frame.pack(fill="x")
        self.pump_canvas=PumpCanvas(pc_frame,height=70)
        self.pump_canvas.pack(fill="x",padx=6,pady=6)
        self.pump_canvas.bind("<Configure>",lambda e:self.pump_canvas.redraw())

        # right: anomalie + stats + tabella
        chart_right=ctk.CTkFrame(charts_frame,fg_color=COLORS["bg"],width=380)
        chart_right.pack(side="left",fill="y")
        chart_right.pack_propagate(False)
        right_scroll=ctk.CTkScrollableFrame(chart_right,fg_color=COLORS["bg"],
                                             scrollbar_button_color=COLORS["border"],
                                             scrollbar_button_hover_color=COLORS["accent"])
        right_scroll.pack(fill="both",expand=True)

        self._sec(right_scroll,"Anomalie rilevate")
        self.anomaly_container=ctk.CTkFrame(right_scroll,fg_color=COLORS["bg"])
        self.anomaly_container.pack(fill="x",pady=(0,8))

        self._sec(right_scroll,"Statistiche colonne")
        stats_frame=ctk.CTkFrame(right_scroll,fg_color=COLORS["surface"],corner_radius=8)
        stats_frame.pack(fill="x",pady=(0,8))
        self.stats_box=ctk.CTkTextbox(stats_frame,height=160,font=("Courier New",10),
                                       fg_color=COLORS["surface"],text_color=COLORS["text"],
                                       border_width=0)
        self.stats_box.pack(fill="x",padx=6,pady=6)

        self._sec(right_scroll,"Dati grezzi")
        raw_frame=ctk.CTkFrame(right_scroll,fg_color=COLORS["surface"],corner_radius=8)
        raw_frame.pack(fill="x",pady=(0,8))
        self.raw_box=ctk.CTkTextbox(raw_frame,height=200,font=("Courier New",9),
                                     fg_color=COLORS["surface"],text_color=COLORS["text2"],
                                     border_width=0,wrap="none")
        self.raw_box.pack(fill="x",padx=6,pady=6)

    # -- TAB HELP --

    # -- EXPORT PDF GRAFICO (v3.1) ------------------------------

    def export_pdf_grafico(self):
        if not self.siemens_rows:
            messagebox.showwarning("Attenzione","Nessun dato Siemens caricato."); return
        csv_t = detect_csv_type(self.siemens_headers)
        if csv_t != "front_firewall":
            messagebox.showwarning("Attenzione",
                "Funzione disponibile solo per dati Front Firewall (Persico).\n"
                "Le colonne rilevate non corrispondono al profilo."); return
        import os
        base_name = os.path.splitext(os.path.basename(self.siemens_csv_path))[0] if hasattr(self, 'siemens_csv_path') and self.siemens_csv_path else "Grafico-Front_Firewall"
        path = filedialog.asksaveasfilename(defaultextension=".pdf",
               initialfile=f"{base_name}.pdf", filetypes=[("PDF","*.pdf")])
        if not path: return
        self.set_status("Generazione PDF in corso...")
        def _run():
            try:
                generate_front_firewall_pdf(self.siemens_rows, self.siemens_headers, path)
                self.after(0, lambda: self.set_status(f"PDF salvato: {os.path.basename(path)}"))
                self.after(0, lambda: messagebox.showinfo("Completato", f"PDF salvato:\n{path}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore PDF", str(e)))
                self.after(0, lambda: self.set_status("Errore generazione PDF"))
        threading.Thread(target=_run, daemon=True).start()

    # -- TAB GRAFICI LAMBORGHINI --------------------------------

    def _build_grafici_tab(self, parent):
        self._grafici_csv_path = None; self._grafici_logo_path = None; self._grafici_native_paths = {}; self._grafici_merged_data = None; self._grafici_merged_meta = None
        self._grafici_data = None; self._grafici_meta = None; self._grafici_note_box = None
        self._grafici_param_vars = {}; self._grafici_canvases = {}
        self._grafici_preview_job = None; self._grafici_groups = []
        # -- Top toolbar --
        top = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        top.pack(fill="x", side="top", padx=6, pady=4)
        row1 = ctk.CTkFrame(top, fg_color=COLORS["surface"], corner_radius=8)
        row1.pack(fill="x", pady=(0,4))
        ctk.CTkLabel(row1, text="Pressa", font=("Segoe UI",11,"bold"),
                     text_color=COLORS["text2"]).pack(side="left", padx=14, pady=10)
        self._grafici_pressa_var = ctk.StringVar(value=list(_PRESSA_STAMPI.keys())[0])
        def _on_pressa_change(val):
            stampi = _PRESSA_STAMPI.get(val, [])
            self._grafici_stampo_var.set(stampi[0] if stampi else "")
            self._grafici_stampo_menu.configure(values=stampi if stampi else [""])
        ctk.CTkOptionMenu(row1, variable=self._grafici_pressa_var,
                          values=list(_PRESSA_STAMPI.keys()), width=160,
                          fg_color=COLORS["surface2"], button_color=COLORS["accent"],
                          text_color=COLORS["text"],
                          command=_on_pressa_change).pack(side="left", padx=8, pady=10)
        ctk.CTkLabel(row1, text="Stampo", font=("Segoe UI",11,"bold"),
                     text_color=COLORS["text2"]).pack(side="left", padx=(12,0), pady=10)
        self._grafici_stampo_var = ctk.StringVar(value=_PRESSA_STAMPI[list(_PRESSA_STAMPI.keys())[0]][0])
        self._grafici_stampo_menu = ctk.CTkOptionMenu(
            row1, variable=self._grafici_stampo_var,
            values=_PRESSA_STAMPI[list(_PRESSA_STAMPI.keys())[0]], width=180,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"], state="disabled")
        self._grafici_stampo_menu.pack(side="left", padx=8, pady=10)
        row2 = ctk.CTkFrame(top, fg_color=COLORS["surface"], corner_radius=8)
        row2.pack(fill="x", pady=(0,4))
        ctk.CTkButton(row2, text="Apri CSV", width=100, height=28,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"],
                      command=self._grafici_open_csv).pack(side="left", padx=10, pady=8)
        self._grafici_csv_lbl = ctk.CTkLabel(row2, text="Nessun file selezionato",
                                              font=("Segoe UI",11), text_color=COLORS["text2"])
        self._grafici_csv_lbl.pack(side="left", padx=8)
        self._grafici_native_btn = ctk.CTkButton(row2, text="+ File nativi", width=110, height=28,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text"], state="disabled",
                      command=self._grafici_open_native)
        self._grafici_native_btn.pack(side="left", padx=4, pady=8)
        self._grafici_native_lbl = ctk.CTkLabel(row2, text="",
                                                 font=("Segoe UI",10), text_color=COLORS["text2"])
        self._grafici_native_lbl.pack(side="left", padx=4)
        ctk.CTkButton(row2, text="Logo (opzionale)", width=130, height=28,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text"],
                      command=self._grafici_open_logo).pack(side="right", padx=10, pady=8)
        self._grafici_logo_lbl = ctk.CTkLabel(row2, text="auto",
                                               font=("Segoe UI",10), text_color=COLORS["text2"])
        self._grafici_logo_lbl.pack(side="right", padx=4)
        row3 = ctk.CTkFrame(top, fg_color="transparent")
        row3.pack(fill="x", pady=(0,2))
        self._grafici_gen_btn = ctk.CTkButton(row3, text="Genera PDF", width=140, height=34,
                                               fg_color=COLORS["accent"], hover_color="#5a52e0",
                                               font=("Segoe UI",12,"bold"), text_color=COLORS["text"],
                                               state="disabled", command=self._grafici_generate)
        self._grafici_gen_btn.pack(side="left", padx=2)
        self._grafici_status = ctk.CTkLabel(row3, text="", font=("Segoe UI",11),
                                             text_color=COLORS["text2"])
        self._grafici_status.pack(side="left", padx=12)
        # -- Main split: filter (left) + chart preview (right) --
        self._grafici_main = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        self._grafici_filter_scroll = ctk.CTkScrollableFrame(
            self._grafici_main, fg_color=COLORS["surface"], width=260, corner_radius=0)
        self._grafici_filter_scroll.pack(side="left", fill="y", padx=(0,4))
        self._grafici_chart_scroll = ctk.CTkScrollableFrame(
            self._grafici_main, fg_color=COLORS["bg"])
        self._grafici_chart_scroll.pack(side="left", fill="both", expand=True)
        # -- Note box persistente: creato UNA VOLTA qui, mai distrutto/ricreato.
        # _grafici_build_preview distrugge solo i figli del _grafici_params_container
        # (i checkbox), lasciando intatto questo widget. Evita "invalid command name"
        # che si verificava quando il textbox veniva ricreato e il vecchio riferimento
        # veniva ancora usato dai binding KeyRelease. --
        self._grafici_params_container = ctk.CTkFrame(
            self._grafici_filter_scroll, fg_color="transparent")
        self._grafici_params_container.pack(fill="x")
        ctk.CTkLabel(self._grafici_filter_scroll, text="NOTE OPERATIVE",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=8, pady=(16, 2))
        self._grafici_note_frame = ctk.CTkFrame(
            self._grafici_filter_scroll, fg_color=COLORS["surface2"], corner_radius=6)
        self._grafici_note_frame.pack(fill="x", padx=4, pady=(0, 8))
        self._grafici_note_box = ctk.CTkTextbox(
            self._grafici_note_frame, height=80, font=("Segoe UI", 10),
            fg_color=COLORS["surface2"], text_color=COLORS["text"],
            border_width=0, wrap="word")
        self._grafici_note_box.pack(fill="x", padx=4, pady=4)
        self._grafici_note_box.bind(
            "<KeyRelease>", lambda e: self._grafici_save_note())

    def _grafici_get_groups(self, data_keys):
        all_keys = set(data_keys)
        groups = []
        def _safe_int(s):
            try: return int(s)
            except Exception: return -1
        ts = sorted([k for k in all_keys if
                     (k.startswith("TS") and k[2:].isdigit()) or
                     (k.startswith("T") and not k.startswith("TI") and
                      k[1:].isdigit() and 1 <= _safe_int(k[1:]) <= 4)])
        if ts: groups.append(("temp_sup", "Temperatura Superiore", "[T]", ts))
        ti = sorted([k for k in all_keys if k.startswith("TI") and k[2:].isdigit()])
        if not ti:
            ti = sorted([k for k in all_keys if k.startswith("T") and
                         k[1:].isdigit() and 4 < _safe_int(k[1:]) <= 8])
        if ti: groups.append(("temp_inf", "Temperatura Inferiore", "[T]", ti))
        pos = sorted([k for k in all_keys if
                      (k.startswith("P") and k[1:].isdigit()) or
                      (k.startswith("Z") and k[1:].isdigit())])
        if pos: groups.append(("posiz", "Posizione Piano", "[P]", pos))
        # Forza: se F1÷F4 presenti (nativo caricato) -> due gruppi separati.
        # Altrimenti gruppo unico con FC/SPC/Forza.
        f_sensors = [k for k in all_keys if k in ("F1","F2","F3","F4")]
        f_combined = [k for k in all_keys if k in ("FC","SPC","Forza")]
        if f_sensors:
            groups.append(("forza_sensori", "Forza Sensori", "*", sorted(f_sensors)))
            if f_combined:
                groups.append(("forza", "Forza", "*", sorted(f_combined)))
        else:
            force = sorted(f_combined)
            if force: groups.append(("forza", "Forza", "*", force))
        vs = sorted([k for k in all_keys if k in ("VS1","VS2","V1","V2")])
        if vs: groups.append(("vuoto_sup", "Vuoto Superiore", "[V]", vs))
        vi = sorted([k for k in all_keys if k in ("VI1","VI2","VI3","VI4","V3","V4")])
        if vi: groups.append(("vuoto_inf", "Vuoto Inferiore", "[V]", vi))
        return groups

    def _grafici_build_preview(self, data, meta):
        if not self._grafici_main.winfo_ismapped():
            self._grafici_main.pack(fill="both", expand=True, padx=6, pady=(0,4))
        self._grafici_groups = self._grafici_get_groups(list(data.keys()))
        # Distrugge solo i checkbox — il note box è persistente e non viene toccato
        for w in self._grafici_params_container.winfo_children(): w.destroy()
        self._grafici_param_vars = {}
        ctk.CTkLabel(self._grafici_params_container, text="FILTRO PARAMETRI",
                     font=("Segoe UI",11,"bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=8, pady=(8,4))
        for key, title, emoji, params in self._grafici_groups:
            hdr = ctk.CTkFrame(self._grafici_params_container,
                               fg_color=COLORS["surface2"], corner_radius=6)
            hdr.pack(fill="x", padx=4, pady=(8,2))
            ctk.CTkLabel(hdr, text=f"{emoji}  {title}",
                         font=("Segoe UI",10,"bold"),
                         text_color=COLORS["text"]).pack(side="left", padx=8, pady=6)
            for param in params:
                color = _SERIES_COLORS.get(param, "#6c63ff")
                row = ctk.CTkFrame(self._grafici_params_container, fg_color="transparent")
                row.pack(fill="x", padx=6, pady=2)
                ctk.CTkFrame(row, width=11, height=11, fg_color=color,
                             corner_radius=2).pack(side="left", padx=(6,5))
                var = tk.BooleanVar(value=True)
                self._grafici_param_vars[param] = var
                ctk.CTkCheckBox(row, text=param, variable=var,
                                fg_color=color, hover_color=color,
                                checkmark_color="#fff",
                                font=("Segoe UI",10,"bold"),
                                text_color=COLORS["text"],
                                command=self._grafici_schedule_update
                                ).pack(side="left")
        # -- Chart canvases --
        for w in self._grafici_chart_scroll.winfo_children(): w.destroy()
        self._grafici_canvases = {}
        for key, title, emoji, params in self._grafici_groups:
            frame = ctk.CTkFrame(self._grafici_chart_scroll,
                                 fg_color=COLORS["surface"], corner_radius=8)
            frame.pack(fill="x", pady=4, padx=2)
            title_bar = ctk.CTkFrame(frame, fg_color=COLORS["surface2"], corner_radius=0)
            title_bar.pack(fill="x")
            ctk.CTkLabel(title_bar, text=f"{emoji}  {title}",
                         font=("Segoe UI",11,"bold"),
                         text_color=COLORS["text"]).pack(side="left", padx=12, pady=7)
            _k = key
            ctk.CTkButton(title_bar, text="[ ]", width=36, height=24,
                          fg_color="transparent", hover_color=COLORS["border"],
                          text_color=COLORS["text2"], font=("Segoe UI",10),
                          command=lambda k=_k: self._grafici_open_fullscreen(k)
                          ).pack(side="right", padx=6)
            fig = plt.Figure(figsize=(10, 2.2), facecolor="#22263a", dpi=80)
            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.get_tk_widget().configure(bg="#22263a", highlightthickness=0)
            canvas.get_tk_widget().pack(fill="x", padx=2, pady=2)
            self._grafici_canvases[key] = (fig, canvas, params)
        self._grafici_update_preview()

    def _grafici_schedule_update(self):
        if self._grafici_preview_job:
            self.after_cancel(self._grafici_preview_job)
        self._grafici_preview_job = self.after(120, self._grafici_update_preview)

    def _grafici_update_preview(self):
        if not self._grafici_data: return
        selected = {p for p, v in self._grafici_param_vars.items() if v.get()}
        _preview_data = self._grafici_merged_data or self._grafici_data
        for key, (fig, canvas, params) in self._grafici_canvases.items():
            fig.clear()
            ax = fig.add_subplot(111)
            ax.set_facecolor("#22263a")
            fig.patch.set_facecolor("#22263a")
            has_data = False
            for param in params:
                if param not in selected: continue
                pts = _preview_data.get(param, [])
                if not pts: continue
                ys = [p[1] for p in pts]
                # Salta serie con tutti i valori a zero (sensori non collegati)
                if all(abs(v) < 0.001 for v in ys): continue
                xs = [p[0] for p in pts]
                ax.plot(xs, ys, color=_SERIES_COLORS.get(param, "#6c63ff"),
                        lw=1.0, label=param)
                has_data = True
            if not has_data:
                ax.text(0.5, 0.5, "Nessun parametro selezionato",
                        transform=ax.transAxes, ha="center", va="center",
                        color=COLORS["text2"], fontsize=9)
            ax.tick_params(colors="#8892b0", labelsize=7, length=2)
            for sp in ax.spines.values():
                sp.set_color("#2e3350"); sp.set_linewidth(0.5)
            ax.grid(True, color="#2e3350", lw=0.5, linestyle="--")
            ax.set_xlabel("Sec", color="#8892b0", fontsize=7, labelpad=2)
            if has_data:
                ax.legend(loc="upper right", fontsize=7, framealpha=0.8,
                          facecolor="#1a1d27", edgecolor="#2e3350",
                          labelcolor="#e8eaf6", handlelength=1.5)
            fig.subplots_adjust(left=0.05, right=0.98, top=0.90, bottom=0.22)
            canvas.draw()

    def _grafici_open_fullscreen(self, key):
        """Apre il grafico in fullscreen con zoom, pan e modalità hover interattive (blit)."""
        if key not in self._grafici_canvases: return
        _, _, params = self._grafici_canvases[key]
        selected = {p for p, v in self._grafici_param_vars.items() if v.get()}
        data = self._grafici_merged_data or self._grafici_data
        if not data: return

        import numpy as _np
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        import matplotlib.pyplot as _plt

        win = tk.Toplevel(self)
        win.title(key)
        win.configure(bg="#22263a")
        win.state("zoomed")

        # -- Barra modalità hover --
        mode_bar = tk.Frame(win, bg="#1a1d27", height=36)
        mode_bar.pack(side="top", fill="x")
        mode_bar.pack_propagate(False)
        tk.Label(mode_bar, text="Hover:", bg="#1a1d27", fg="#8892b0",
                 font=("Segoe UI", 10)).pack(side="left", padx=(12, 6))
        _hover_mode = tk.StringVar(value="Nessuno")
        _MODE_COLORS = {"active_bg": "#6c63ff", "active_fg": "#ffffff",
                        "idle_bg": "#22263a", "idle_fg": "#8892b0"}
        _mode_btns = {}
        def _set_mode(m):
            _hover_mode.set(m)
            for _m, _b in _mode_btns.items():
                if _m == m:
                    _b.configure(bg=_MODE_COLORS["active_bg"], fg=_MODE_COLORS["active_fg"])
                else:
                    _b.configure(bg=_MODE_COLORS["idle_bg"], fg=_MODE_COLORS["idle_fg"])
            _clear_overlay()
        for lbl in ["Nessuno", "Tooltip", "Crosshair", "Snap", "Completo"]:
            _l = lbl
            b = tk.Button(mode_bar, text=lbl, bg=_MODE_COLORS["idle_bg"],
                          fg=_MODE_COLORS["idle_fg"], relief="flat",
                          font=("Segoe UI", 10), padx=10, pady=4,
                          activebackground="#5a52e0", activeforeground="#fff",
                          command=lambda m=_l: _set_mode(m))
            b.pack(side="left", padx=3, pady=4)
            _mode_btns[lbl] = b
        _mode_btns["Nessuno"].configure(bg=_MODE_COLORS["active_bg"], fg=_MODE_COLORS["active_fg"])

        # -- Figura e assi --
        fig = _plt.Figure(figsize=(16, 6), facecolor="#22263a")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#22263a")
        for sp in ax.spines.values(): sp.set_color("#2e3350"); sp.set_linewidth(0.6)
        ax.tick_params(colors="#8892b0", labelsize=9, length=3)
        ax.grid(True, color="#2e3350", lw=0.5, linestyle="--")
        ax.set_xlabel("Sec", color="#8892b0", fontsize=9, labelpad=4)

        # Raccoglie serie: {param: (xs_array, ys_array, color)}
        _series = {}
        has_data = False
        for param in params:
            if param not in selected: continue
            pts = data.get(param, [])
            if not pts: continue
            ys = [p[1] for p in pts]
            if all(abs(v) < 0.001 for v in ys): continue
            xs = [p[0] for p in pts]
            color = _SERIES_COLORS.get(param, "#6c63ff")
            ax.plot(xs, ys, color=color, lw=1.2, label=param)
            _series[param] = (_np.array(xs), _np.array(ys), color)
            has_data = True
        if has_data:
            ax.legend(loc="upper right", fontsize=9, framealpha=0.8,
                      facecolor="#1a1d27", edgecolor="#2e3350",
                      labelcolor="#e8eaf6", handlelength=2)
        fig.subplots_adjust(left=0.06, right=0.98, top=0.93, bottom=0.10)

        # -- Canvas e toolbar matplotlib (stile dark) --
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().configure(bg="#22263a", highlightthickness=0)
        toolbar_frame = tk.Frame(win, bg="#2a2d3e")
        toolbar_frame.pack(side="bottom", fill="x")
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.config(background="#2a2d3e")
        def _style_toolbar(widget):
            try:
                cls = widget.winfo_class()
                if cls in ("Button", "Label"):
                    widget.config(bg="#2a2d3e", fg="#e8eaf6",
                                  activebackground="#4a4f72", activeforeground="#ffffff",
                                  relief="flat", borderwidth=0)
                elif cls in ("Frame", "Checkbutton"):
                    widget.config(bg="#2a2d3e")
            except Exception: pass
            for child in widget.winfo_children():
                _style_toolbar(child)
        toolbar.update()
        _style_toolbar(toolbar)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        canvas.draw()

        # -- Background statico per blit --
        _bg = [None]
        def _save_bg():
            _bg[0] = canvas.copy_from_bbox(fig.bbox)
        win.after(100, _save_bg)

        # -- Artisti overlay (animated=True → esclusi dal draw statico) --
        _vline, = ax.plot([], [], color="#ffffff", lw=0.7, linestyle="--", alpha=0.5, animated=True)
        _hline, = ax.plot([], [], color="#ffffff", lw=0.7, linestyle="--", alpha=0.5, animated=True)
        _snap_dot, = ax.plot([], [], "o", ms=7, color="#ffffff", zorder=10, animated=True)
        _tooltip = ax.annotate("", xy=(0, 0), xytext=(15, 15),
                               textcoords="offset points",
                               bbox=dict(boxstyle="round,pad=0.4", fc="#1a1d27",
                                         ec="#6c63ff", lw=1.2, alpha=0.92),
                               fontsize=8.5, color="#e8eaf6", animated=True,
                               annotation_clip=False)
        _tooltip.set_visible(False)

        def _place_tooltip(bx, by):
            """Ribalta l'offset del tooltip vicino ai bordi degli assi."""
            xl = ax.get_xlim(); yl = ax.get_ylim()
            xfrac = (bx - xl[0]) / (xl[1] - xl[0]) if xl[1] != xl[0] else 0.5
            yfrac = (by - yl[0]) / (yl[1] - yl[0]) if yl[1] != yl[0] else 0.5
            ox = -120 if xfrac > 0.75 else 15
            oy = -60  if yfrac > 0.70 else 15
            _tooltip.xyann = (ox, oy)
        _info_box = ax.text(0.01, 0.98, "", transform=ax.transAxes,
                            va="top", ha="left", fontsize=8.5, color="#e8eaf6",
                            bbox=dict(boxstyle="round,pad=0.5", fc="#1a1d27",
                                      ec="#2e3350", lw=1.0, alpha=0.90),
                            animated=True)
        _info_box.set_visible(False)

        def _clear_overlay():
            _vline.set_data([], [])
            _hline.set_data([], [])
            _snap_dot.set_data([], [])
            _tooltip.set_visible(False)
            _info_box.set_visible(False)
            if _bg[0] is not None:
                canvas.restore_region(_bg[0])
                canvas.blit(fig.bbox)

        def _interp_y(xs_arr, ys_arr, x):
            if len(xs_arr) == 0: return None
            idx = _np.searchsorted(xs_arr, x)
            if idx == 0: return float(ys_arr[0])
            if idx >= len(xs_arr): return float(ys_arr[-1])
            x0, x1 = xs_arr[idx-1], xs_arr[idx]
            y0, y1 = ys_arr[idx-1], ys_arr[idx]
            if x1 == x0: return float(y0)
            return float(y0 + (y1 - y0) * (x - x0) / (x1 - x0))

        def _nearest_point(xs_arr, ys_arr, x, y, ax_obj):
            if len(xs_arr) == 0: return None, None, None
            disp = ax_obj.transData.transform(_np.column_stack([xs_arr, ys_arr]))
            cx, cy = ax_obj.transData.transform([[x, y]])[0]
            dists = _np.hypot(disp[:, 0] - cx, disp[:, 1] - cy)
            idx = int(_np.argmin(dists))
            return float(xs_arr[idx]), float(ys_arr[idx]), float(dists[idx])

        def _on_motion(event):
            if event.inaxes != ax or _bg[0] is None: return
            mode = _hover_mode.get()
            if mode == "Nessuno": return
            x, y = event.xdata, event.ydata
            if x is None or y is None: return
            canvas.restore_region(_bg[0])
            xl = ax.get_xlim(); yl = ax.get_ylim()
            if mode == "Tooltip":
                best_param, best_x, best_y, best_dist = None, None, None, float("inf")
                for param, (xs_arr, ys_arr, color) in _series.items():
                    nx, ny, dist = _nearest_point(xs_arr, ys_arr, x, y, ax)
                    if nx is not None and dist < best_dist:
                        best_dist = dist; best_param = param
                        best_x = nx; best_y = ny
                if best_param is not None and best_dist < 40:
                    _tooltip.xy = (best_x, best_y)
                    _place_tooltip(best_x, best_y)
                    _tooltip.set_text(f"{best_param}\nX: {best_x:.1f} s\nY: {best_y:.4g}")
                    _tooltip.set_visible(True)
                else:
                    _tooltip.set_visible(False)
                ax.draw_artist(_tooltip)
            elif mode == "Crosshair":
                _vline.set_data([x, x], [yl[0], yl[1]])
                _hline.set_data([xl[0], xl[1]], [y, y])
                lines = [f"X: {x:.1f} s"]
                for param, (xs_arr, ys_arr, _c) in _series.items():
                    iv = _interp_y(xs_arr, ys_arr, x)
                    if iv is not None: lines.append(f"{param}: {iv:.4g}")
                _info_box.set_text("\n".join(lines))
                _info_box.set_visible(True)
                ax.draw_artist(_vline); ax.draw_artist(_hline); ax.draw_artist(_info_box)
            elif mode == "Snap":
                best_param, best_x, best_y, best_dist = None, None, None, float("inf")
                best_color = "#ffffff"
                for param, (xs_arr, ys_arr, color) in _series.items():
                    nx, ny, dist = _nearest_point(xs_arr, ys_arr, x, y, ax)
                    if nx is not None and dist < best_dist:
                        best_dist = dist; best_param = param
                        best_x = nx; best_y = ny; best_color = color
                if best_param is not None and best_dist < 50:
                    _snap_dot.set_data([best_x], [best_y])
                    _snap_dot.set_color(best_color)
                    _tooltip.xy = (best_x, best_y)
                    _place_tooltip(best_x, best_y)
                    _tooltip.set_text(f"{best_param}\nX: {best_x:.1f} s\nY: {best_y:.4g}")
                    _tooltip.set_visible(True)
                else:
                    _snap_dot.set_data([], []); _tooltip.set_visible(False)
                ax.draw_artist(_snap_dot); ax.draw_artist(_tooltip)
            elif mode == "Completo":
                _vline.set_data([x, x], [yl[0], yl[1]])
                _hline.set_data([xl[0], xl[1]], [y, y])
                best_param, best_x, best_y, best_dist = None, None, None, float("inf")
                best_color = "#ffffff"
                for param, (xs_arr, ys_arr, color) in _series.items():
                    nx, ny, dist = _nearest_point(xs_arr, ys_arr, x, y, ax)
                    if nx is not None and dist < best_dist:
                        best_dist = dist; best_param = param
                        best_x = nx; best_y = ny; best_color = color
                if best_param is not None and best_dist < 50:
                    _snap_dot.set_data([best_x], [best_y]); _snap_dot.set_color(best_color)
                else:
                    _snap_dot.set_data([], [])
                lines = [f"X: {x:.1f} s"]
                for param, (xs_arr, ys_arr, _c) in _series.items():
                    iv = _interp_y(xs_arr, ys_arr, x)
                    marker = " ◀" if param == best_param else ""
                    if iv is not None: lines.append(f"{param}: {iv:.4g}{marker}")
                _info_box.set_text("\n".join(lines)); _info_box.set_visible(True)
                ax.draw_artist(_vline); ax.draw_artist(_hline)
                ax.draw_artist(_snap_dot); ax.draw_artist(_info_box)
            canvas.blit(ax.bbox)

        def _on_leave(event):
            _clear_overlay()

        canvas.mpl_connect("motion_notify_event", _on_motion)
        canvas.mpl_connect("axes_leave_event", _on_leave)

        # -- Limiti originali --
        _orig_xlim = list(ax.get_xlim())
        _orig_ylim = list(ax.get_ylim())
        _zoomed = [False]

        # -- Zoom rotella: out solo se già zoomato, clamp ai limiti originali --
        def _on_scroll(event):
            if event.inaxes is None: return
            if event.button == "down" and not _zoomed[0]: return
            factor = 0.85 if event.button == "up" else 1.0 / 0.85
            xl = list(ax.get_xlim()); yl = list(ax.get_ylim())
            cx = event.xdata; cy = event.ydata
            new_xl = [cx + (x - cx) * factor for x in xl]
            new_yl = [cy + (y - cy) * factor for y in yl]
            if event.button == "down":
                new_xl[0] = max(new_xl[0], _orig_xlim[0]); new_xl[1] = min(new_xl[1], _orig_xlim[1])
                new_yl[0] = max(new_yl[0], _orig_ylim[0]); new_yl[1] = min(new_yl[1], _orig_ylim[1])
                if (abs(new_xl[0]-_orig_xlim[0]) < 1e-6 and abs(new_xl[1]-_orig_xlim[1]) < 1e-6 and
                    abs(new_yl[0]-_orig_ylim[0]) < 1e-6 and abs(new_yl[1]-_orig_ylim[1]) < 1e-6):
                    _zoomed[0] = False
            else:
                _zoomed[0] = True
                new_xl[0] = max(new_xl[0], _orig_xlim[0]); new_xl[1] = min(new_xl[1], _orig_xlim[1])
                new_yl[0] = max(new_yl[0], _orig_ylim[0]); new_yl[1] = min(new_yl[1], _orig_ylim[1])
            if new_xl[1] > new_xl[0] and new_yl[1] > new_yl[0]:
                ax.set_xlim(new_xl); ax.set_ylim(new_yl)
                canvas.draw()
                _save_bg()

        # -- Pan limitato: X e Y non scendono sotto i limiti originali --
        _clamping = [False]
        def _on_xlim_change(ax_changed):
            if _clamping[0]: return
            xl = list(ax_changed.get_xlim())
            if xl[0] < _orig_xlim[0]:
                _clamping[0] = True
                ax_changed.set_xlim(_orig_xlim[0], xl[1] + (_orig_xlim[0] - xl[0]))
                _clamping[0] = False
        def _on_ylim_change(ax_changed):
            if _clamping[0]: return
            yl = list(ax_changed.get_ylim())
            if yl[0] < _orig_ylim[0]:
                _clamping[0] = True
                ax_changed.set_ylim(_orig_ylim[0], yl[1] + (_orig_ylim[0] - yl[0]))
                _clamping[0] = False

        ax.callbacks.connect("xlim_changed", _on_xlim_change)
        ax.callbacks.connect("ylim_changed", _on_ylim_change)
        canvas.mpl_connect("scroll_event", _on_scroll)
        canvas.mpl_connect("resize_event", lambda e: (canvas.draw(), _save_bg()))

    def _grafici_save_note(self):
        """Salva la nota corrente nel file JSON locale."""
        idciclo = (self._grafici_meta or {}).get("idciclo", "")
        if not idciclo: return
        note_text = self._grafici_note_box.get("1.0", "end").strip() if self._grafici_note_box else ""
        try:
            notes = {}
            if os.path.exists(_NOTES_FILE):
                with open(_NOTES_FILE, encoding="utf-8") as f: notes = json.load(f)
            if note_text: notes[idciclo] = note_text
            elif idciclo in notes: del notes[idciclo]
            with open(_NOTES_FILE, "w", encoding="utf-8") as f: json.dump(notes, f, ensure_ascii=False, indent=2)
        except Exception: pass

    def _grafici_load_note(self, idciclo):
        """Carica la nota salvata per l'ID ciclo dato."""
        note_text = ""
        try:
            if os.path.exists(_NOTES_FILE):
                with open(_NOTES_FILE, encoding="utf-8") as f: notes = json.load(f)
                note_text = notes.get(str(idciclo), "")
        except Exception: pass
        if self._grafici_note_box is not None:
            self._grafici_note_box.delete("1.0", "end")
            if note_text: self._grafici_note_box.insert("1.0", note_text)

    def _grafici_open_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if not path: return
        ok, err = _validate_csv(path)
        if not ok:
            messagebox.showerror("File non valido", err)
            self._grafici_status.configure(text=f"X {err}", text_color=COLORS["error"]); return
        # Reset file nativi: un nuovo CSV appartiene a un ciclo diverso,
        # i nativi precedenti non sono più validi.
        self._grafici_native_paths = {}
        self._grafici_native_lbl.configure(text="", text_color=COLORS["text2"])
        self._grafici_csv_path = path
        self._grafici_csv_lbl.configure(text=os.path.basename(path), text_color=COLORS["text"])
        detected, lati_dict, partite = _autodetect_profile(path)
        if detected:
            self._grafici_stampo_var.set(detected)
            self._grafici_stampo_menu.configure(state="disabled")
            pressa_rilevata = _PROFILES.get(detected, {}).get("pressa", "Cannon 5000T")
            self._grafici_pressa_var.set(pressa_rilevata)
            self._grafici_stampo_menu.configure(values=_PRESSA_STAMPI.get(pressa_rilevata, [detected]))
            if "Cannon" in pressa_rilevata:
                self._grafici_native_btn.configure(state="disabled")
            else:
                self._grafici_native_btn.configure(state="normal")
            parti = []
            for prof, lati in lati_dict.items():
                lati_str = f" ({'/'.join(sorted(lati))})" if lati else ""
                parti.append(f"{prof}{lati_str}")
            partite_str = ", ".join(partite[:6]) + ("..." if len(partite) > 6 else "")
            self._grafici_status.configure(
                text=f"OK Rilevato: {' + '.join(parti)} | Partite: {partite_str}",
                text_color=COLORS["info"])
        else:
            self._grafici_stampo_menu.configure(state="normal")
            msg = (f"/!\\ Codici non riconosciuti: {', '.join(partite[:4])} - seleziona manualmente."
                   if partite else "i Campo Partita non trovato - seleziona il profilo manualmente.")
            self._grafici_status.configure(text=msg, text_color=COLORS["warn"])
        try:
            data, meta = _pdf_parse_csv(path)
            self._grafici_data = data; self._grafici_meta = meta
            if self._grafici_native_paths:
                try:
                    nd, mp = _parse_native_pack(self._grafici_native_paths, self._grafici_stampo_var.get())
                    md, mm = _merge_native_data(data, meta, nd, mp)
                except Exception:
                    md, mm = data, meta
            else:
                md, mm = data, meta
            self._grafici_merged_data = md; self._grafici_merged_meta = mm
            self._grafici_build_preview(md, mm)
            self._grafici_gen_btn.configure(state="normal")
            idciclo = (self._grafici_meta or {}).get("idciclo", "")
            self._grafici_load_note(idciclo)
        except Exception as e:
            self._grafici_status.configure(
                text=f"X Errore lettura: {e}", text_color=COLORS["error"])

    def _grafici_open_native(self):
        _TYPES = {"FORZA":"FORZA","POSIZIONE":"POSIZIONE","TEMPS_SUP":"TEMPS_SUP",
                  "TEMPS_INF":"TEMPS_INF","VUOTO_SUP":"VUOTO_SUP","VUOTO_INF":"VUOTO_INF",
                  "DATI_GENERALI":"DATI_GENERALI"}
        paths = filedialog.askopenfilenames(
            title="Seleziona file nativi Persico",
            filetypes=[("CSV files","*.csv *.CSV"),("All files","*.*")])
        if not paths: return
        # FIX 5: accumulo — i file vengono aggiunti a quelli già caricati,
        # non sostituiti. Così si può selezionare un file alla volta.
        if not hasattr(self, "_grafici_native_paths") or not self._grafici_native_paths:
            self._grafici_native_paths = {}
        ignored = []
        for p in paths:
            base = os.path.basename(p).upper()
            matched = next((k for k in _TYPES if base.startswith(k)), None)
            if matched: self._grafici_native_paths[matched] = p
            else: ignored.append(os.path.basename(p))
        n = len(self._grafici_native_paths)
        if n == 0:
            self._grafici_native_lbl.configure(text="Nessun file riconosciuto", text_color=COLORS["warn"]); return
        # Label: mostra tutti i tipi caricati finora, uno per riga se sono molti
        tipi = list(self._grafici_native_paths.keys())
        lbl = f"{n}/7 nativi: {', '.join(tipi)}"
        if ignored: lbl += f"  |  ignorati: {', '.join(ignored)}"
        self._grafici_native_lbl.configure(text=lbl, text_color=COLORS["info"])
        if self._grafici_data is not None:
            try:
                nd, mp = _parse_native_pack(self._grafici_native_paths, self._grafici_stampo_var.get())
                md, mm = _merge_native_data(self._grafici_data, self._grafici_meta, nd, mp)
                self._grafici_merged_data = md; self._grafici_merged_meta = mm
                self._grafici_build_preview(md, mm)
            except Exception as e:
                self._grafici_native_lbl.configure(text=f"Errore nativi: {e}", text_color=COLORS["error"])

    def _grafici_open_logo(self):
        path = filedialog.askopenfilename(filetypes=[("Immagini","*.png *.jpg *.jpeg"),("All files","*.*")])
        if not path: return
        self._grafici_logo_path = path
        self._grafici_logo_lbl.configure(text=os.path.basename(path), text_color=COLORS["text"])

    def _grafici_generate(self):
        if not self._grafici_csv_path:
            messagebox.showwarning("Attenzione","Seleziona prima un file CSV."); return
        selected = {p for p, v in self._grafici_param_vars.items() if v.get()} if self._grafici_param_vars else None
        if selected is not None and not selected:
            messagebox.showwarning("Attenzione","Seleziona almeno un parametro."); return
        stampo = self._grafici_stampo_var.get()
        _base = os.path.splitext(os.path.basename(self._grafici_csv_path))[0] if self._grafici_csv_path else f"Grafico-{stampo.replace(' ','_')}"
        out = filedialog.asksaveasfilename(defaultextension=".pdf",
              initialfile=f"{_base}.pdf", filetypes=[("PDF","*.pdf")])
        if not out: return
        self._grafici_gen_btn.configure(state="disabled", text="Generazione...")
        self._grafici_status.configure(text="Generazione in corso...", text_color=COLORS["warn"])
        logo = self._grafici_logo_path
        md = self._grafici_merged_data or self._grafici_data
        mm = dict(self._grafici_merged_meta or self._grafici_meta)
        note_text = self._grafici_note_box.get("1.0", "end").strip() if hasattr(self, "_grafici_note_box") else ""
        if note_text: mm["note"] = note_text
        if mm.get("partite"):
            mm["partite"] = _filter_partite(mm["partite"], stampo)
        def _run():
            try:
                generate_lamborghini_pdf(self._grafici_csv_path, stampo, out,
                                         logo_path=logo, filter_params=selected,
                                         preloaded_data=md, preloaded_meta=mm)
                self.after(0, lambda: self._grafici_done(out))
            except Exception as e:
                self.after(0, lambda: self._grafici_error(str(e)))
        threading.Thread(target=_run, daemon=True).start()

    def _grafici_done(self, path):
        self._grafici_gen_btn.configure(state="normal", text="Genera PDF")
        self._grafici_status.configure(text=f"OK PDF salvato: {os.path.basename(path)}", text_color=COLORS["info"])
        self.set_status(f"PDF generato: {os.path.basename(path)}")
        try:
            import subprocess, sys
            if sys.platform == "win32": os.startfile(path)
            elif sys.platform == "darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        except Exception: pass

    def _grafici_error(self, msg):
        self._grafici_gen_btn.configure(state="normal", text="Genera PDF")
        self._grafici_status.configure(text=f"Errore: {msg}", text_color=COLORS["error"])
        messagebox.showerror("Errore generazione PDF", msg)


    def _build_help(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color=COLORS["bg"],
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
            ctk.CTkLabel(col, text=title, font=("Segoe UI", 15, "bold"),
                         text_color=COLORS["text"]).pack(anchor="w")
            if subtitle:
                ctk.CTkLabel(col, text=subtitle, font=("Segoe UI", 10),
                             text_color=COLORS["text2"]).pack(anchor="w")
            ctk.CTkFrame(scroll, fg_color=COLORS["border"], height=1).pack(
                fill="x", padx=16, pady=(0, 8))

        def _card(icon, title, body, example=None):
            outer = ctk.CTkFrame(scroll, fg_color=COLORS["surface"], corner_radius=10)
            outer.pack(fill="x", padx=16, pady=4)
            hdr = ctk.CTkFrame(outer, fg_color="transparent")
            hdr.pack(fill="x", padx=14, pady=(12, 4))
            ctk.CTkLabel(hdr, text=icon, font=("Segoe UI", 16),
                         text_color=COLORS["accent2"], width=28).pack(side="left")
            ctk.CTkLabel(hdr, text=title, font=("Segoe UI", 11, "bold"),
                         text_color=COLORS["text"]).pack(side="left", padx=6)
            ctk.CTkLabel(outer, text=body, font=("Segoe UI", 10),
                         text_color=COLORS["text2"], anchor="w", justify="left",
                         wraplength=860).pack(anchor="w", padx=46, pady=(0, 4))
            if example:
                ex_frame = ctk.CTkFrame(outer, fg_color=COLORS["surface2"], corner_radius=6)
                ex_frame.pack(fill="x", padx=46, pady=(2, 12))
                ctk.CTkLabel(ex_frame, text="  ESEMPIO  ",
                             font=("Segoe UI", 8, "bold"),
                             text_color=COLORS["accent"],
                             fg_color=COLORS["surface2"]).pack(anchor="w", padx=8, pady=(6, 0))
                ctk.CTkLabel(ex_frame, text=example, font=("Courier New", 9),
                             text_color=COLORS["accent2"], anchor="w", justify="left",
                             wraplength=820).pack(anchor="w", padx=8, pady=(0, 8))
            else:
                ctk.CTkFrame(outer, fg_color="transparent", height=6).pack()

        # intro
        intro = ctk.CTkFrame(scroll, fg_color=COLORS["surface2"], corner_radius=12)
        intro.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(intro, text="MouldGraph  —  Analisi e monitoraggio dati industriali",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(14, 2))
        ctk.CTkLabel(intro,
                     text="L'app si divide in tre tab principali: Grafici, Dati CSV e Live Data.\n"
                          "Ogni tab e' indipendente: puoi usarle in qualsiasi ordine senza interferenze.",
                     font=("Segoe UI", 10), text_color=COLORS["text2"],
                     justify="left", anchor="w").pack(anchor="w", padx=20, pady=(0, 14))

        # TAB GRAFICI
        _section_title("📊", "Tab Grafici",
                       "Generazione PDF professionali per presse Persico 2500T e Cannon 5000T")
        _card("🏭", "Seleziona Pressa e Stampo",
              "Scegli la pressa (Persico 2500T o Cannon 5000T) dal menu in alto a sinistra, "
              "poi seleziona il profilo stampo. Il profilo determina automaticamente le scale "
              "degli assi, i setpoint di temperatura, forza e vuoto.",
              "Pressa: Persico 2500T  ->  Stampo: Front Firewall\n"
              "Pressa: Cannon 5000T  ->  Stampo: Inner Tub")
        _card("📂", "Carica il CSV del ciclo",
              "Clicca Apri CSV e seleziona il file esportato dalla pressa. "
              "Il profilo viene rilevato automaticamente dal codice nella colonna Partita "
              "(es. 26RF005449 -> RF -> Front Firewall). "
              "Puoi anche caricare file nativi Persico separati tramite i pulsanti dedicati.",
              "File CSV con Partita 26RF005449  ->  profilo rilevato: Front Firewall")
        _card("🖼", "Anteprima e generazione PDF",
              "Il grafico si aggiorna in anteprima. Clicca Genera PDF per il report multi-pagina: "
              "pagina 1 cover + temperature, pagina 2 posizione + forza, pagina 3 vuoto. "
              "Il logo aziendale viene incluso automaticamente se presente nella stessa cartella del CSV.",
              "PDF: Firewall_RF_21103.pdf  (3 pagine, 150 dpi)")
        _card("⏱", "Filtro temporale",
              "Usa i cursori T-Start e T-End per restringere il plot a un intervallo del ciclo. "
              "Utile per isolare la fase di pressatura o di raffreddamento.",
              "T-Start: 200s  ->  T-End: 800s  ->  mostra solo la fase di consolidamento")

        # TAB DATI CSV
        _section_title("📋", "Tab Dati CSV",
                       "Analisi universale di qualsiasi file CSV da qualsiasi impianto")
        _card("📂", "Caricamento CSV universale",
              "Clicca Apri CSV. L'app rileva automaticamente: encoding (UTF-8, Latin-1, CP1252), "
              "separatore (; , | TAB), intestazioni, tipo colonna (numerico, datetime, binario, testo) "
              "e unita' di misura dal nome (es. Temp_Forno -> gradi C, Pressione_Bar -> bar).",
              "File: dati_forno.csv  ->  sep=;, 12 colonne numeriche, 1 datetime, 2 binarie")
        _card("📈", "Selezione assi e plot",
              "Seleziona la colonna X (asse temporale) dal menu. "
              "Attiva/disattiva le serie Y cliccando le pillole colorate. "
              "Alcune serie possono essere assegnate all'asse Y2 (destra) per scale diverse. "
              "Il grafico supporta zoom rotella, pan tasto centrale, cursori A/B doppio click.",
              "X: UTC_Time  |  Y1: Temperatura, Pressione  |  Y2: Portata_Lmin")
        _card("🔍", "Rilevamento anomalie automatico",
              "Il pannello Anomalie segnala: spike fuori 2.5 sigma dalla media, pompa spenta, "
              "livello > 95%, pressione < 1.0 bar. "
              "Ogni anomalia mostra timestamp, valore rilevato e descrizione.",
              "[ANOMALIA] Temperatura fuori range [14:32:05]  ->  val=187.3 C (media 162.5 +/- 8.2)")
        _card("📊", "Statistiche colonne",
              "Per ogni colonna numerica selezionata: minimo, massimo, media e deviazione standard.",
              "Temperatura:  min=158.2 C  max=165.8 C  media=162.4 C  sigma=1.3")
        _card("💾", "Export Dati CSV",
              "PNG: salva il grafico corrente con legenda.\n"
              "Report TXT: statistiche complete + anomalie + metadati.\n"
              "PDF impianto: report professionale con intestazione e grafici.",
              "Bottoni:  PNG  /  Report TXT  /  PDF impianto")

        # TAB LIVE DATA
        _section_title("📡", "Tab Live Data",
                       "Monitoraggio in tempo reale: simulazione CSV o acquisizione seriale")
        _card("📂", "Carica CSV di simulazione",
              "Clicca CSV e seleziona un file. L'app rileva la colonna tempo "
              "(datetime o secondi numerici come Time). "
              "Le colonne numeriche appaiono nelle pillole Colonne Y.",
              "File: FORZA_21103.CSV  ->  colonna tempo Time in secondi, 8 colonne numeriche")
        _card("▶", "Avvia, Pausa, Stop",
              "Pulsante verde (triangolo): avvia. I dati vecchi vengono azzerati.\n"
              "Pulsante giallo (pausa): blocca il thread, grafico fermo.\n"
              "Pulsante rosso (stop): termina la sessione.\n"
              "Ad ogni nuovo Avvia la sessione riparte da zero.",
              "Avvia  ->  acquisizione  ->  Pausa  ->  Avvia riprende  ->  Stop fine")
        _card("⚡", "Velocita' simulazione",
              "1x = tempo reale  |  10x = 10 volte piu' veloce  |  60x = molto veloce  |  MAX = istantaneo.\n"
              "Modificabile anche durante la simulazione in corso.",
              "Ciclo FORZA_21103 (1496s):  1x -> 25min  |  10x -> 2.5min  |  60x -> 25s  |  MAX -> 2s")
        _card("〰", "Interpolazione (Interp)",
              "Attivando Interp, ogni 200ms viene calcolato un punto intermedio tra i campioni reali "
              "per animare la curva. I punti interpolati NON vengono salvati nell'export CSV.",
              "Campione t=23s: F1=162.1  ->  interpolato t=23.2s: F1=162.15  ->  t=23.4s: 162.2")
        _card("🔴", "Allarmi live",
              "Clicca + Soglia nel pannello destra. Scegli colonna, Lo (minimo) e/o Hi (massimo). "
              "Al primo scatto appare il badge rosso e viene loggato il momento. "
              "Azzera rimuove tutte le regole e azzera i contatori.",
              "Colonna: FC  |  Lo: 6400  |  Hi: 6600\n"
              "-> [02:35:12] ALLARME [FC] = 6546.4 > 6600")
        _card("💾", "Export Live",
              "CSV: salva tutti i campioni reali con intestazioni.\n"
              "PNG: salva il grafico corrente ad alta risoluzione.",
              "File: live_20260321_023512.csv  (108 righe x 8 colonne)")

        # SCORCIATOIE
        _section_title("⌨", "Scorciatoie e trucchi",
                       "Interazione avanzata con i grafici interattivi")
        _card("🖱", "Zoom con rotella",
              "Rotella su = zoom in centrato sul cursore. Rotella giu' = zoom out.",
              "Rotella su  ->  zoom 15% attorno al punto X del cursore")
        _card("✋", "Pan (trascinamento)",
              "Tasto centrale del mouse (rotella) + trascina per spostarti sull'asse X.",
              "Click centrale + trascina a sinistra  ->  scorre verso destra")
        _card("📍", "Cursori A/B per misure delta",
              "Doppio click sinistro = cursore A. Doppio click destro = cursore B. "
              "Appare un riquadro con delta X, delta Y per serie e pendenza.",
              "A: X=100s FC=6480  |  B: X=200s FC=6520\n"
              "->  DeltaX=100s  |  DeltaFC=+40 kN  |  pendenza=0.4 kN/s")
        _card("👁", "Toggle serie",
              "Clicca le pillole colorate sotto il grafico per mostrare/nascondere serie.",
              "Click su F3  ->  F3 scompare  |  click di nuovo  ->  riappare")
        _card("💡", "Tooltip hover",
              "Muovi il mouse sul grafico: la linea verticale si aggancia al campione piu' vicino "
              "e il tooltip mostra tutti i valori. Mouse fuori dal grafico = tutto sparisce.",
              "X: 135.9  |  FC: 6502  |  SPC: 6500  |  F1: 162.3")
        _card("🔄", "Reset zoom",
              "Clicca Reset zoom per tornare alla vista completa.",
              "Dopo zoom 100s-200s  ->  Reset zoom  ->  vista da 0 a 1496s")

    # -- HELPERS --
    def _sec(self,p,t):
        f=ctk.CTkFrame(p,fg_color="transparent");f.pack(fill="x",pady=(4,4))
        ctk.CTkFrame(f,fg_color=COLORS["accent"],width=4,height=18,corner_radius=2).pack(side="left")
        ctk.CTkLabel(f,text=f"  {t}",font=("Segoe UI",13,"bold"),text_color=COLORS["text"]).pack(side="left")

    def _sec_inline(self,p,t):
        ctk.CTkFrame(p,fg_color=COLORS["accent"],width=4,height=18,corner_radius=2).pack(side="left")
        ctk.CTkLabel(p,text=f"  {t}",font=("Segoe UI",13,"bold"),text_color=COLORS["text"]).pack(side="left")

    # -- LOG ACTIONS --
    def open_file(self):
        path=filedialog.askopenfilename(filetypes=[("Log files","*.log *.txt *.out *.csv"),("All files","*.*")])
        if not path:return
        try:
            with open(path,"r",encoding="utf-8",errors="replace") as f:content=f.read()
            # auto-detect Siemens CSV
            first=content.strip().splitlines()[0] if content.strip() else ""
            if (detect_csv_type([h.strip().strip('"') for h in (first or "").split(",")]) == "front_firewall"
                or ("Record" in first and ("Date" in first or "Time" in first) and "," in first)):
                self.siemens_csv_path = path
                self._load_siemens_data(content,os.path.basename(path))
                self.tabs.set("  Dati Siemens  ");return
            self.txt_input.delete("0.0","end");self.txt_input.insert("0.0",content)
            self.set_status(f"File caricato: {os.path.basename(path)} ({os.path.getsize(path)/1024:.1f} KB)")
            self.analyze()
        except Exception as e:messagebox.showerror("Errore",str(e))

    def analyze(self):
        text=self.txt_input.get("0.0","end").strip()
        if not text or text.startswith("Incolla"):messagebox.showwarning("Attenzione","Incolla un log prima!");return
        self.all_parsed=parse_log(text)
        wt=[l for l in self.all_parsed if l["ts"]]
        if wt:
            mn=min(l["ts"] for l in wt);mx=max(l["ts"] for l in wt)
            self.entry_from.delete(0,"end");self.entry_from.insert(0,mn.strftime("%Y-%m-%d %H:%M"))
            self.entry_to.delete(0,"end");self.entry_to.insert(0,mx.strftime("%Y-%m-%d %H:%M"))
        self.apply_filters();self.set_status(f"Analizzate {len(self.all_parsed)} righe.")

    def toggle_level(self,level):
        self.active_levels[level]=not self.active_levels[level]
        btn=self.lvl_btns[level]
        if self.active_levels[level]:btn.configure(fg_color=LEVEL_BG[level],text_color=LEVEL_COLORS[level])
        else:btn.configure(fg_color=COLORS["surface2"],text_color=COLORS["text2"])
        self.apply_filters()

    def reset_filters(self):
        self.entry_kw.delete(0,"end");self.entry_from.delete(0,"end");self.entry_to.delete(0,"end")
        for lvl in self.active_levels:
            self.active_levels[lvl]=True;self.lvl_btns[lvl].configure(fg_color=LEVEL_BG[lvl],text_color=LEVEL_COLORS[lvl])
        self.apply_filters()

    def _debounced_apply_filters(self):
        """B4: debounce 250ms — esegue apply_filters solo dopo pausa nella digitazione."""
        if getattr(self, "_filter_debounce_job", None):
            try: self.after_cancel(self._filter_debounce_job)
            except Exception: pass
        self._filter_debounce_job = self.after(250, self._run_debounced_filters)

    def _run_debounced_filters(self):
        self._filter_debounce_job = None
        self.apply_filters()

    def apply_filters(self):
        kw=self.entry_kw.get().lower().strip()
        fd=self._pdt(self.entry_from.get().strip());td=self._pdt(self.entry_to.get().strip())
        self.filtered=[]
        for l in self.all_parsed:
            if not self.active_levels.get(l["level"],True):continue
            if kw and kw not in l["raw"].lower():continue
            if fd and l["ts"] and l["ts"]<fd:continue
            if td and l["ts"] and l["ts"]>td:continue
            self.filtered.append(l)
        self._render_stats();self._render_table(kw);self._render_patterns()
        self._render_timeline();self._render_comp();self._render_ai()

    def _pdt(self,s):
        if not s:return None
        for fmt in["%Y-%m-%d %H:%M","%Y-%m-%d %H:%M:%S","%Y-%m-%d"]:
            try:return datetime.strptime(s,fmt)
            except Exception:pass
        return None

    def _render_stats(self):
        self.stat_labels["total"].configure(text=str(len(self.filtered)))
        self.stat_labels["ERROR"].configure(text=str(sum(1 for l in self.filtered if l["level"]=="ERROR")))
        self.stat_labels["WARN"].configure(text=str(sum(1 for l in self.filtered if l["level"]=="WARN")))
        self.stat_labels["INFO"].configure(text=str(sum(1 for l in self.filtered if l["level"]=="INFO")))
        self.lbl_count.configure(text=f"({len(self.filtered)} righe)")

    def _render_table(self,kw=""):
        self.tbl.configure(state="normal");self.tbl.delete("1.0","end")
        for i,l in enumerate(self.filtered):
            tr="roweven" if i%2==0 else "rowodd";lvl=l["level"]
            msg=l["message"][:180]+("..." if len(l["message"])>180 else "")
            self.tbl.insert("end",f"{l['n']:>5}  ",("dim",tr))
            self.tbl.insert("end",f"{l['timestamp']:<20}  ",("dim",tr))
            self.tbl.insert("end",f"{lvl:<7}  ",(lvl,tr))
            self.tbl.insert("end",f"{l['component']:<14}  ",("comp",tr))
            if kw and kw in msg.lower():
                idx=msg.lower().find(kw)
                self.tbl.insert("end",msg[:idx],(tr,))
                self.tbl.insert("end",msg[idx:idx+len(kw)],("hl",tr))
                self.tbl.insert("end",msg[idx+len(kw):]+"\n",(tr,))
            else:self.tbl.insert("end",msg+"\n",(tr,))
        self.tbl.configure(state="disabled")

    def _render_patterns(self):
        sm=defaultdict(lambda:{"count":0,"level":"INFO"})
        for l in self.filtered:s=norm_sig(l["message"]);sm[s]["count"]+=1;sm[s]["level"]=l["level"]
        top=sorted(sm.items(),key=lambda x:-x[1]["count"])[:10]
        mc=top[0][1]["count"] if top else 1
        self.patterns_box.configure(state="normal");self.patterns_box.delete("0.0","end")
        for sig,data in top:
            pct=int((data["count"]/mc)*20);bar="#"*pct+"."*(20-pct)
            label=sig[:65]+"..." if len(sig)>65 else sig
            self.patterns_box.insert("end",f"[{data['level']:<5}]  {data['count']:>3}x  [{bar}]\n  {label}\n\n")
        self.patterns_box.configure(state="disabled")

    def _render_timeline(self):
        self.timeline_canvas.set_data(build_timeline(self.filtered))

    def _render_comp(self):
        comp=defaultdict(lambda:{"ERROR":0,"WARN":0,"INFO":0,"DEBUG":0,"total":0})
        for l in self.filtered:comp[l["component"]][l["level"]]+=1;comp[l["component"]]["total"]+=1
        self.comp_box.configure(state="normal");self.comp_box.delete("0.0","end")
        self.comp_box.insert("end",f"{'COMPONENTE':<20} {'TOT':>5} {'ERR':>5} {'WARN':>5} {'INFO':>5} {'DEBUG':>5}\n")
        self.comp_box.insert("end","-"*55+"\n")
        for c,v in sorted(comp.items(),key=lambda x:-x[1]["total"]):
            self.comp_box.insert("end",f"{c:<20} {v['total']:>5} {v['ERROR']:>5} {v['WARN']:>5} {v['INFO']:>5} {v['DEBUG']:>5}\n")
        self.comp_box.configure(state="disabled")

    def _render_ai(self):
        for w in self.ai_container.winfo_children():w.destroy()
        insights=ai_analysis(self.filtered)
        if not insights:
            ctk.CTkLabel(self.ai_container,text="Nessun dato. Carica un log prima.",
                         font=("Segoe UI",13),text_color=COLORS["text2"]).pack(pady=30);return
        for badge,title,desc,color in insights:
            card=ctk.CTkFrame(self.ai_container,fg_color=COLORS["surface"],corner_radius=10)
            card.pack(fill="x",pady=6,padx=4)
            top=ctk.CTkFrame(card,fg_color="transparent");top.pack(fill="x",padx=14,pady=(12,4))
            ctk.CTkLabel(top,text=f" {badge} ",font=("Segoe UI",10,"bold"),
                         fg_color=color,text_color="#0f1117",corner_radius=4).pack(side="left")
            ctk.CTkLabel(top,text=f"  {title}",font=("Segoe UI",13,"bold"),text_color=color).pack(side="left")
            ctk.CTkLabel(card,text=desc,font=("Segoe UI",12),text_color=COLORS["text"],
                         wraplength=900,anchor="w",justify="left").pack(anchor="w",padx=14,pady=(0,12))

    # -- SIEMENS CSV ACTIONS --
    def open_siemens_csv(self):
        path=filedialog.askopenfilename(filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if not path:return
        try:
            self.siemens_csv_path = path
            with open(path,"r",encoding="utf-8",errors="replace") as f:content=f.read()
            self._load_siemens_data(content,os.path.basename(path))
        except Exception as e:messagebox.showerror("Errore",str(e))

    def _load_siemens_data(self,content,fname):
        self.siemens_headers,self.siemens_rows=parse_siemens_csv(content)
        if not self.siemens_rows:
            messagebox.showwarning("Attenzione","Nessun dato valido nel CSV.");return
        n=len(self.siemens_rows)
        csv_t=detect_csv_type(self.siemens_headers)
        tipo_lbl="Front Firewall (Persico)" if csv_t=="front_firewall" else "Siemens generico"
        self._last_csv_type=csv_t
        self.siemens_info_lbl.configure(text=f"{fname}  |  {n} record  |  tipo: {tipo_lbl}")
        # update col menus
        numeric=[h for h in self.siemens_headers
                 if h not in("Record","Date","Time","UTC Time")
                 and self.siemens_rows and isinstance(self.siemens_rows[0].get(h),float)]
        opts=["-"]+numeric
        self.siemens_col_menu.configure(values=numeric if numeric else["-"])
        self.siemens_col2_menu.configure(values=opts)
        if numeric:self.siemens_col_var.set(numeric[0])
        self.siemens_col2_var.set("-")
        self._refresh_siemens()
        self.set_status(f"CSV Siemens caricato: {fname} ({n} record)")

    def _on_col_change(self,_=None):
        self._refresh_siemens()

    def _refresh_siemens(self):
        if not self.siemens_rows:return
        rows=self.siemens_rows
        times=[r["_ts"] for r in rows]
        col1=self.siemens_col_var.get()
        col2=self.siemens_col2_var.get()
        series={}
        palette=["#6c63ff","#00d4ff","#52c41a","#faad14"]
        if col1 and col1!="-":
            vals=[r.get(col1) for r in rows]
            series[col1]=(palette[0],vals)
        if col2 and col2!="-":
            vals=[r.get(col2) for r in rows]
            series[col2]=(palette[1],vals)
        self.line_chart.set_data(times,series)
        # pump
        pump_col=None
        for pk in["Stato_Pompa","stato_pompa","pump_state","PumpState"]:
            if pk in(self.siemens_headers or[]):pump_col=pk;break
        if pump_col:
            pvals=[r.get(pump_col,0) for r in rows]
            self.pump_canvas.set_data(times,pvals)
        # anomalie
        anomalies,stats=detect_anomalies(rows,self.siemens_headers)
        for w in self.anomaly_container.winfo_children():w.destroy()
        if not anomalies:
            ctk.CTkLabel(self.anomaly_container,text="Nessuna anomalia rilevata.",
                         font=("Segoe UI",12),text_color=COLORS["info"]).pack(pady=8,anchor="w")
        else:
            for badge,title,desc,color in anomalies[:12]:
                card=ctk.CTkFrame(self.anomaly_container,fg_color=COLORS["surface"],corner_radius=8)
                card.pack(fill="x",pady=3)
                top=ctk.CTkFrame(card,fg_color="transparent");top.pack(fill="x",padx=10,pady=(8,2))
                ctk.CTkLabel(top,text=f" {badge} ",font=("Segoe UI",9,"bold"),
                             fg_color=color,text_color="#0f1117",corner_radius=3).pack(side="left")
                ctk.CTkLabel(top,text=f"  {title}",font=("Segoe UI",11,"bold"),text_color=color).pack(side="left")
                ctk.CTkLabel(card,text=desc,font=("Segoe UI",10),text_color=COLORS["text"],
                             wraplength=340,anchor="w",justify="left").pack(anchor="w",padx=10,pady=(0,8))
        # stats
        self.stats_box.configure(state="normal");self.stats_box.delete("0.0","end")
        self.stats_box.insert("end",f"{'COLONNA':<22} {'MIN':>8} {'MAX':>8} {'MEDIA':>8} {'STD':>8}\n")
        self.stats_box.insert("end","-"*52+"\n")
        for col,st in stats.items():
            self.stats_box.insert("end",f"{col:<22} {st['min']:>8.2f} {st['max']:>8.2f} {st['mean']:>8.2f} {st['std']:>8.2f}\n")
        self.stats_box.configure(state="disabled")
        # raw data
        self.raw_box.configure(state="normal");self.raw_box.delete("0.0","end")
        cols=[h for h in self.siemens_headers if h!="_ts"]
        header=" | ".join(f"{c:<14}" for c in cols[:8])
        self.raw_box.insert("end",header+"\n"+"-"*min(len(header),100)+"\n")
        for r in rows[:50]:
            line=" | ".join(f"{str(r.get(c,'')):<14}" for c in cols[:8])
            self.raw_box.insert("end",line+"\n")
        if len(rows)>50:self.raw_box.insert("end",f"... ({len(rows)-50} righe aggiuntive)\n")
        self.raw_box.configure(state="disabled")

    def export_siemens_report(self):
        if not self.siemens_rows:messagebox.showwarning("Attenzione","Nessun dato Siemens caricato.");return
        path=filedialog.asksaveasfilename(defaultextension=".txt",filetypes=[("Text report","*.txt")])
        if not path:return
        anomalies,stats=detect_anomalies(self.siemens_rows,self.siemens_headers)
        with open(path,"w",encoding="utf-8") as f:
            f.write("="*60+"\nREPORT DATI SIEMENS / CANNON ERGOS\n"+"="*60+"\n\n")
            f.write(f"Record totali: {len(self.siemens_rows)}\n")
            f.write(f"Colonne: {', '.join(self.siemens_headers)}\n\n")
            f.write("STATISTICHE\n"+"-"*40+"\n")
            for col,st in stats.items():
                f.write(f"{col}: min={st['min']:.2f} max={st['max']:.2f} media={st['mean']:.2f} std={st['std']:.2f}\n")
            f.write("\nANOMALIE RILEVATE\n"+"-"*40+"\n")
            if anomalies:
                for badge,title,desc,_ in anomalies:f.write(f"[{badge}] {title}\n  {desc}\n\n")
            else:f.write("Nessuna anomalia rilevata.\n")
        self.set_status(f"Report esportato: {os.path.basename(path)}")

    def export_json(self):
        if not self.filtered:messagebox.showwarning("Attenzione","Nessun dato.");return
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if not path:return
        with open(path,"w",encoding="utf-8") as f:
            json.dump([{"line":l["n"],"timestamp":l["timestamp"],"level":l["level"],
                        "component":l["component"],"message":l["message"]} for l in self.filtered],
                      f,indent=2,ensure_ascii=False)
        self.set_status(f"JSON esportato: {os.path.basename(path)}")

    def export_csv(self):
        if not self.filtered:messagebox.showwarning("Attenzione","Nessun dato.");return
        path=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not path:return
        with open(path,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f);w.writerow(["#","Timestamp","Level","Component","Message"])
            for l in self.filtered:w.writerow([l["n"],l["timestamp"],l["level"],l["component"],l["message"]])
        self.set_status(f"CSV esportato: {os.path.basename(path)}")

    
    # =========================================================
    #  TAB: DATI CSV  (Universal Plant CSV Analyzer)
    # =========================================================

    def build_csv_tab(self, parent):
        self._csv_rows          = []
        self._csv_rows2         = []   # secondo CSV per confronto
        self._csv_col_meta2     = {}   # col_meta del secondo CSV
        self._csv_num_cols2     = []   # colonne numeriche del secondo CSV
        self._csv_y_vars2       = {}   # checkbox vars colonne CSV2
        self._csv_filepath2     = None
        self._csv_colors2       = {}
        self._csv_headers       = []
        self._csv_col_meta      = {}
        self._csv_numeric_cols  = []
        self._csv_datetime_cols = []
        self._csv_binary_cols   = []
        self._csv_sep           = ","
        self._csv_enc           = "utf-8"
        self._csv_filepath      = None
        self._csv_xcol_var      = tk.StringVar(value="-")
        self._csv_y_vars        = {}
        self._csv_y2_vars       = {}
        self._csv_colors        = {}

        tb = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=8, height=44)
        tb.pack(fill="x", pady=(0, 6))
        tb.pack_propagate(False)
        ctk.CTkButton(tb, text="Apri CSV", width=100, height=30,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"],
                      command=self._csv_open).pack(side="left", padx=10, pady=7)
        self._csv_info_lbl = ctk.CTkLabel(
            tb, text="Nessun file caricato",
            font=("Segoe UI", 11), text_color=COLORS["text2"])
        self._csv_info_lbl.pack(side="left", padx=8)

        # ── badge anomalie ────────────────────────────────────────────
        self._csv_anomaly_badge = ctk.CTkLabel(
            tb, text="",
            font=("Segoe UI", 10, "bold"),
            text_color=COLORS["text"],
            fg_color=COLORS["error"], corner_radius=6)
        # non pakkato finché non ci sono anomalie

        for txt, cmd, fg in [
            ("Export PDF",    self._csv_export_pdf,    "#7c3aed"),
            ("Export PNG",    self._csv_export_png,    COLORS["surface2"]),
            ("Export Report", self._csv_export_report, COLORS["surface2"]),
            ("Reset Zoom",    self._csv_reset_zoom,    COLORS["surface2"]),
            ("Confronta CSV", self._csv_open_compare,  COLORS["surface2"]),
        ]:
            ctk.CTkButton(tb, text=txt, width=115, height=30,
                          fg_color=fg, hover_color=COLORS["border"],
                          text_color=COLORS["text"],
                          command=cmd).pack(side="right", padx=4, pady=7)

        body = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        body.pack(fill="both", expand=True)
        lw = ctk.CTkFrame(body, fg_color=COLORS["bg"], width=294)
        lw.pack(side="left", fill="y", padx=(0, 6))
        lw.pack_propagate(False)
        left = ctk.CTkScrollableFrame(
            lw, fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        left.pack(fill="both", expand=True)
        _isolate_scroll(left)

        # ── Asse X (evidenziato) ──────────────────────────────────────
        self._sec(left, "Asse X")
        self._csv_xcard = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_xcard.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(self._csv_xcard, text="Colonna X",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=10, pady=(8, 2))
        self._csv_xcol_menu = ctk.CTkOptionMenu(
            self._csv_xcard, variable=self._csv_xcol_var, values=["-"],
            width=256, fg_color=COLORS["surface2"],
            button_color=COLORS["accent"], text_color=COLORS["text"],
            command=self._csv_on_xcol_change)
        self._csv_xcol_menu.pack(padx=10, pady=(0, 6))

        # filtro temporale (Dal / Al) — visibile solo se X è datetime
        self._csv_tfilter_frame = ctk.CTkFrame(self._csv_xcard, fg_color="transparent")
        ctk.CTkLabel(self._csv_tfilter_frame, text="Filtra intervallo",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=10, pady=(2, 2))
        tf_row = ctk.CTkFrame(self._csv_tfilter_frame, fg_color="transparent")
        tf_row.pack(fill="x", padx=8, pady=(0, 6))
        self._csv_from_var = tk.StringVar()
        self._csv_to_var   = tk.StringVar()
        ctk.CTkLabel(tf_row, text="Dal", font=("Segoe UI", 9),
                     text_color=COLORS["text2"]).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(tf_row, textvariable=self._csv_from_var,
                     placeholder_text="HH:MM:SS",
                     width=80, height=24,
                     fg_color=COLORS["surface2"], text_color=COLORS["text"]
                     ).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(tf_row, text="Al", font=("Segoe UI", 9),
                     text_color=COLORS["text2"]).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(tf_row, textvariable=self._csv_to_var,
                     placeholder_text="HH:MM:SS",
                     width=80, height=24,
                     fg_color=COLORS["surface2"], text_color=COLORS["text"]
                     ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(tf_row, text="✓", width=28, height=24,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 10),
                      command=self._csv_refresh_plot).pack(side="left")

        self._sec(left, "Serie Y")
        self._csv_series_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_series_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self._csv_series_card,
                     text="Carica un CSV per vedere le colonne",
                     font=("Segoe UI", 10),
                     text_color=COLORS["text2"]).pack(padx=10, pady=10)

        self._sec(left, "Confronto CSV ②")
        self._csv_series2_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_series2_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self._csv_series2_card,
                     text="Carica un CSV di confronto (pulsante sopra)",
                     font=("Segoe UI", 9), text_color=COLORS["text2"]).pack(padx=10, pady=6)

        self._sec(left, "Stati digitali")
        self._csv_digital_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_digital_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self._csv_digital_card, text="—",
                     font=("Segoe UI", 10),
                     text_color=COLORS["text2"]).pack(padx=10, pady=6)

        # ── Statistiche come card ──────────────────────────────────────
        self._sec(left, "Statistiche")
        self._csv_stats_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._csv_stats_container.pack(fill="x", pady=(0, 8))
        # mantengo anche il textbox originale (nascosto) per compatibilità export
        self._csv_statsbox = ctk.CTkTextbox(
            left, height=1, font=("Courier New", 10),
            fg_color=COLORS["bg"], text_color=COLORS["bg"], border_width=0)
        self._csv_statsbox.pack_forget()  # nascosto, solo per export report

        # ── Range personalizzati ──────────────────────────────────────
        self._csv_ranges = []   # [{col, lo, hi}]
        self._sec(left, "Range personalizzati")
        range_hdr = ctk.CTkFrame(left, fg_color="transparent")
        range_hdr.pack(fill="x", pady=(0, 2))
        ctk.CTkButton(range_hdr, text="+ Aggiungi range", width=130, height=24,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 9),
                      command=self._csv_add_range).pack(side="left")
        ctk.CTkButton(range_hdr, text="Azzera", width=70, height=24,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      command=self._csv_clear_ranges).pack(side="left", padx=6)
        self._csv_ranges_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._csv_ranges_container.pack(fill="x", pady=(0, 8))

        self._sec(left, "Anomalie rilevate")
        self._csv_anomaly_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._csv_anomaly_container.pack(fill="x", pady=(0, 8))

        right = ctk.CTkFrame(body, fg_color=COLORS["bg"])
        right.pack(side="left", fill="both", expand=True)
        self._csv_iplot = InteractivePlotCanvas(right, height=430)

    def _csv_on_xcol_change(self, val):
        """Chiamato al cambio colonna X: mostra filtro temporale se datetime."""
        is_dt = val in self._csv_datetime_cols
        if is_dt:
            self._csv_xcard.configure(border_width=2, border_color=COLORS["accent"])
            self._csv_tfilter_frame.pack(fill="x", pady=(0, 4))
        else:
            self._csv_xcard.configure(border_width=0)
            self._csv_tfilter_frame.pack_forget()
        self._csv_refresh_plot()

    def _csv_get_filtered_rows(self):
        """Ritorna le righe filtrate per intervallo temporale (se impostato)."""
        rows = self._csv_rows
        x_col = self._csv_xcol_var.get()
        if x_col not in self._csv_datetime_cols:
            return rows
        from_s = self._csv_from_var.get().strip()
        to_s   = self._csv_to_var.get().strip()
        if not from_s and not to_s:
            return rows
        filtered = []
        for r in rows:
            ts = _uc_parse_dt(r.get(x_col, ""))
            if ts is None:
                filtered.append(r)
                continue
            t = ts.strftime("%H:%M:%S")
            if from_s and t < from_s:
                continue
            if to_s and t > to_s:
                continue
            filtered.append(r)
        return filtered

    def _csv_open_compare(self):
        """Carica un secondo CSV e sovrappone le curve al grafico corrente."""
        if not self._csv_rows:
            messagebox.showwarning("Confronta", "Carica prima il CSV principale.")
            return
        path = filedialog.askopenfilename(
            title="Seleziona CSV da confrontare",
            filetypes=[("CSV / TSV / TXT", "*.csv *.tsv *.txt"), ("Tutti i file", "*.*")])
        if not path:
            return
        self.set_status("Caricamento CSV confronto...")
        def run():
            try:
                if _is_long_cycle_csv(path):
                    rows2, headers2, col_meta2, num_cols2, _, _, _, _ = \
                        _parse_long_cycle_csv(path)
                else:
                    rows2, headers2, col_meta2, num_cols2, _, _, _, _ = \
                        parse_universal_csv(path)
                palette2 = ["#ff6b6b","#ffd93d","#6bcb77","#4d96ff",
                            "#c77dff","#f9844a","#90e0ef","#f15bb5"]
                colors2 = {col: palette2[i % len(palette2)]
                           for i, col in enumerate(num_cols2)}
                def _apply():
                    self._csv_rows2     = rows2
                    self._csv_col_meta2 = col_meta2
                    self._csv_num_cols2 = list(num_cols2)
                    self._csv_filepath2 = path
                    self._csv_colors2.update(colors2)
                    self._csv_rebuild_series2_panel()
                    self._csv_refresh_plot()
                    self.set_status(
                        f"Confronto: {os.path.basename(path)} ({len(rows2)} righe)")
                self.after(0, _apply)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore CSV confronto", str(e)))
        threading.Thread(target=run, daemon=True).start()


    def _csv_rebuild_series2_panel(self):
        """Ricostruisce il pannello checkbox per le colonne del secondo CSV."""
        for w in self._csv_series2_card.winfo_children():
            try: w.destroy()
            except Exception: pass
        if not self._csv_rows2 or not self._csv_num_cols2:
            ctk.CTkLabel(self._csv_series2_card,
                         text="Carica un CSV di confronto (pulsante sopra)",
                         font=("Segoe UI", 9), text_color=COLORS["text2"]).pack(padx=10, pady=6)
            return
        # bottoni Tutti / Nessuno
        hf = ctk.CTkFrame(self._csv_series2_card, fg_color="transparent")
        hf.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkButton(hf, text="Tutti", width=62, height=22,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"],
                      command=lambda: self._csv_sel_all_2(True)).pack(side="left", padx=2)
        ctk.CTkButton(hf, text="Nessuno", width=72, height=22,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"],
                      command=lambda: self._csv_sel_all_2(False)).pack(side="left", padx=2)
        # ricrea vars preservando stato precedente
        prev2 = {c: v.get() for c, v in self._csv_y_vars2.items()}
        self._csv_y_vars2 = {}
        for col in self._csv_num_cols2:
            var = tk.BooleanVar(value=prev2.get(col, True))
            self._csv_y_vars2[col] = var
            color = self._csv_colors2.get(col, COLORS["accent"])
            row = ctk.CTkFrame(self._csv_series2_card, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=1)
            dot = tk.Canvas(row, width=12, height=12,
                            bg=COLORS["surface"], highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=color, outline="")
            dot.pack(side="left", padx=(4, 2), pady=4)
            ctk.CTkCheckBox(
                row, text=col, variable=var,
                font=("Segoe UI", 10), text_color=COLORS["text"],
                fg_color=COLORS["accent"], hover_color="#5a52e0",
                checkmark_color=COLORS["text"],
                border_color=COLORS["border"],
                command=self._csv_refresh_plot
            ).pack(side="left", fill="x", expand=True)

    def _csv_sel_all_2(self, val):
        """Seleziona/deseleziona tutte le colonne del secondo CSV."""
        for v in self._csv_y_vars2.values():
            v.set(val)
        self._csv_refresh_plot()

    def _csv_update_stats_cards(self, y_cols):
        """Rende le statistiche come card colorate invece di un textbox."""
        for w in self._csv_stats_container.winfo_children():
            try: w.destroy()
            except Exception: pass
        if not self._csv_rows or not y_cols:
            return
        # aggiorna anche il textbox nascosto per l'export report
        self._csv_statsbox.configure(state="normal")
        self._csv_statsbox.delete("1.0", "end")
        rows = self._csv_get_filtered_rows()
        for col in y_cols:
            vals = []
            for r in rows:
                try:
                    vals.append(float(r.get(col, "").replace(",", ".")))
                except Exception:
                    pass
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
            unit = self._csv_col_meta.get(col, {}).get("unit", "")
            u    = f" {unit}" if unit else ""
            color = self._csv_colors.get(col, COLORS["accent"])
            # card
            card = ctk.CTkFrame(self._csv_stats_container,
                                fg_color=COLORS["surface"], corner_radius=8)
            card.pack(fill="x", pady=2)
            # intestazione colorata
            hdr_f = ctk.CTkFrame(card, fg_color=color, corner_radius=6, height=22)
            hdr_f.pack(fill="x", padx=4, pady=(4, 2))
            hdr_f.pack_propagate(False)
            ctk.CTkLabel(hdr_f, text=col, font=("Segoe UI", 9, "bold"),
                         text_color="#fff").pack(side="left", padx=8)
            ctk.CTkLabel(hdr_f, text=f"N={len(vals)}",
                         font=("Segoe UI", 8), text_color="#ffffff99").pack(side="right", padx=6)
            # valori in griglia 2×2
            grid = ctk.CTkFrame(card, fg_color="transparent")
            grid.pack(fill="x", padx=6, pady=(2, 6))
            for i, (lbl, val) in enumerate([
                ("min", f"{min(vals):.4g}{u}"),
                ("max", f"{max(vals):.4g}{u}"),
                ("μ",   f"{mean:.4g}{u}"),
                ("σ",   f"{std:.4g}"),
            ]):
                col_f = ctk.CTkFrame(grid, fg_color="transparent")
                col_f.grid(row=i//2, column=i%2, sticky="w", padx=4, pady=1)
                ctk.CTkLabel(col_f, text=lbl, font=("Segoe UI", 8),
                             text_color=COLORS["text2"]).pack(side="left")
                ctk.CTkLabel(col_f, text=f"  {val}", font=("Segoe UI", 9, "bold"),
                             text_color=COLORS["text"]).pack(side="left")
            # aggiorna textbox nascosto
            self._csv_statsbox.insert("end",
                f"▸ {col[:24]}\n"
                f"  min={min(vals):.4g}{u}  max={max(vals):.4g}{u}\n"
                f"  μ={mean:.4g}{u}  σ={std:.4g}  N={len(vals)}\n\n")
        self._csv_statsbox.configure(state="disabled")

    def _csv_add_range(self):
        """Dialogo per aggiungere un range personalizzato su una colonna."""
        if not self._csv_numeric_cols:
            messagebox.showinfo("Range", "Carica prima un CSV.")
            return
        win = ctk.CTkToplevel(self)
        win.title("Nuovo range")
        win.geometry("340x280")
        win.resizable(False, False)
        win.configure(fg_color=COLORS["bg"])
        win.grab_set()

        ctk.CTkLabel(win, text="Colonna", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 2))
        col_var = ctk.StringVar(value=self._csv_numeric_cols[0])
        ctk.CTkOptionMenu(win, variable=col_var,
                          values=self._csv_numeric_cols, width=290,
                          fg_color=COLORS["surface2"], button_color=COLORS["accent"],
                          text_color=COLORS["text"]).pack(padx=20)

        ctk.CTkLabel(win, text="Minimo (Lo) — lascia vuoto per ignorare",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(12, 2))
        lo_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=lo_var, placeholder_text="es. 0.5",
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     width=290).pack(padx=20)

        ctk.CTkLabel(win, text="Massimo (Hi) — lascia vuoto per ignorare",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(10, 2))
        hi_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=hi_var, placeholder_text="es. 150.0",
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     width=290).pack(padx=20)

        def _confirm():
            col = col_var.get()
            lo = None; hi = None
            try: lo = float(lo_var.get().replace(",", "."))
            except Exception: pass
            try: hi = float(hi_var.get().replace(",", "."))
            except Exception: pass
            if lo is None and hi is None:
                messagebox.showwarning("Range", "Inserisci almeno un valore Lo o Hi.")
                return
            self._csv_ranges.append({"col": col, "lo": lo, "hi": hi})
            self._csv_rebuild_range_cards()
            self._csv_refresh_plot()
            win.destroy()

        ctk.CTkButton(win, text="Aggiungi", width=140, height=32,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], command=_confirm).pack(pady=16)

    def _csv_clear_ranges(self):
        self._csv_ranges.clear()
        self._csv_rebuild_range_cards()
        self._csv_refresh_plot()

    def _csv_rebuild_range_cards(self):
        for w in self._csv_ranges_container.winfo_children():
            try: w.destroy()
            except Exception: pass
        if not self._csv_ranges:
            ctk.CTkLabel(self._csv_ranges_container,
                         text="Nessun range definito",
                         font=("Segoe UI", 9), text_color=COLORS["text2"]).pack(
                anchor="w", padx=4, pady=2)
            return
        for idx, rule in enumerate(self._csv_ranges):
            col = rule["col"]; lo = rule.get("lo"); hi = rule.get("hi")
            parts = []
            if lo is not None: parts.append(f"Lo={lo:.4g}")
            if hi is not None: parts.append(f"Hi={hi:.4g}")
            label = f"{col}  [{',  '.join(parts)}]"
            card = ctk.CTkFrame(self._csv_ranges_container,
                                fg_color=COLORS["surface"], corner_radius=6)
            card.pack(fill="x", pady=2)
            ctk.CTkLabel(card, text=label, font=("Segoe UI", 9),
                         text_color=COLORS["text"]).pack(side="left", padx=8, pady=4)
            ctk.CTkButton(card, text="✕", width=22, height=22,
                          fg_color="transparent", hover_color=COLORS["border"],
                          text_color=COLORS["text2"], font=("Segoe UI", 9),
                          command=lambda i=idx: self._csv_remove_range(i)
                          ).pack(side="right", padx=4)

    def _csv_remove_range(self, idx):
        if 0 <= idx < len(self._csv_ranges):
            self._csv_ranges.pop(idx)
        self._csv_rebuild_range_cards()
        self._csv_refresh_plot()

    def _csv_open(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV / TSV / TXT", "*.csv *.tsv *.txt"), ("Tutti i file", "*.*")])
        if not path:
            return
        self.set_status("Caricamento CSV in corso...")
        def run():
            try:
                rows, headers, col_meta, num_cols, dt_cols, bin_cols, sep, enc = \
                    parse_universal_csv(path)
                def _apply():
                    self._csv_rows          = rows
                    self._csv_headers       = headers
                    self._csv_col_meta      = col_meta
                    self._csv_numeric_cols  = num_cols
                    self._csv_datetime_cols = dt_cols
                    self._csv_binary_cols   = bin_cols
                    self._csv_sep           = sep
                    self._csv_enc           = enc
                    self._csv_filepath      = path
                    self._csv_populate_controls()
                    self.set_status(
                        f"CSV caricato: {len(rows)} righe · {len(headers)} colonne · "
                        f"sep='{sep}' · enc={enc}")
                self.after(0, _apply)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore CSV", str(e)))
                self.after(0, lambda: self.set_status("Errore caricamento CSV."))
        threading.Thread(target=run, daemon=True).start()

    def _csv_populate_controls(self):
        basename = os.path.basename(self._csv_filepath or "")
        self._csv_info_lbl.configure(
            text=f"{basename}  │  {len(self._csv_rows)} righe  │  "
                 f"sep='{self._csv_sep}'  enc={self._csv_enc}")
        x_choices = self._csv_datetime_cols + self._csv_numeric_cols
        if not x_choices:
            x_choices = ["-"]
        self._csv_xcol_menu.configure(values=x_choices)
        self._csv_xcol_var.set(x_choices[0])
        palette = list(_UC_SERIES_PALETTE)
        for i, col in enumerate(self._csv_numeric_cols):
            if col not in self._csv_colors:
                self._csv_colors[col] = palette[i % len(palette)]
        for w in self._csv_series_card.winfo_children():
            w.destroy()
        self._csv_y_vars  = {}
        self._csv_y2_vars = {}
        if not self._csv_numeric_cols:
            ctk.CTkLabel(self._csv_series_card,
                         text="Nessuna colonna numerica trovata",
                         font=("Segoe UI", 10),
                         text_color=COLORS["text2"]).pack(padx=10, pady=8)
        else:
            hf = ctk.CTkFrame(self._csv_series_card, fg_color="transparent")
            hf.pack(fill="x", padx=8, pady=(6, 2))
            ctk.CTkButton(hf, text="Tutti", width=62, height=22,
                          fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                          text_color=COLORS["text2"],
                          command=lambda: self._csv_sel_all(True)).pack(side="left", padx=2)
            ctk.CTkButton(hf, text="Nessuno", width=72, height=22,
                          fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                          text_color=COLORS["text2"],
                          command=lambda: self._csv_sel_all(False)).pack(side="left", padx=2)
            for col in self._csv_numeric_cols:
                var  = tk.BooleanVar(value=True)
                var2 = tk.BooleanVar(value=False)
                self._csv_y_vars[col]  = var
                self._csv_y2_vars[col] = var2
                color = self._csv_colors[col]
                meta  = self._csv_col_meta.get(col, {})
                unit  = meta.get("unit", "")
                label = meta.get("label", col)
                disp = col if col == label else f"{col} [{label}]"
                if unit:
                    disp += f" {unit}"
                row_f = ctk.CTkFrame(self._csv_series_card, fg_color="transparent")
                row_f.pack(fill="x", padx=6, pady=1)
                dot = tk.Canvas(row_f, width=12, height=12,
                                bg=COLORS["surface"], highlightthickness=0)
                dot.create_oval(1, 1, 11, 11, fill=color, outline="")
                dot.pack(side="left", padx=(4, 2), pady=4)
                ctk.CTkCheckBox(
                    row_f, text=disp, variable=var,
                    font=("Segoe UI", 10), text_color=COLORS["text"],
                    fg_color=COLORS["accent"], hover_color="#5a52e0",
                    checkmark_color=COLORS["text"],
                    border_color=COLORS["border"],
                    command=self._csv_refresh_plot
                ).pack(side="left", fill="x", expand=True)
                btn_holder = {}
                def _make_toggle(c=col, bv=var2, bh=btn_holder):
                    def _toggle():
                        bv.set(not bv.get())
                        bh["b"].configure(
                            text="Y2" if bv.get() else "Y1",
                            fg_color="#7c3aed" if bv.get() else COLORS["surface2"])
                        self._csv_refresh_plot()
                    return _toggle
                y2b = ctk.CTkButton(
                    row_f, text="Y1", width=34, height=22,
                    fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                    text_color=COLORS["text2"], font=("Segoe UI", 9),
                    command=_make_toggle())
                y2b.pack(side="right", padx=(2, 6))
                btn_holder["b"] = y2b
        for w in self._csv_digital_card.winfo_children():
            w.destroy()
        if not self._csv_binary_cols:
            ctk.CTkLabel(self._csv_digital_card, text="—",
                         font=("Segoe UI", 10),
                         text_color=COLORS["text2"]).pack(padx=10, pady=6)
        else:
            for col in self._csv_binary_cols:
                ctk.CTkLabel(self._csv_digital_card,
                             text=f"⚡  {col}",
                             font=("Segoe UI", 10),
                             text_color=COLORS["accent2"],
                             anchor="w").pack(anchor="w", padx=10, pady=2)
        self._csv_refresh_plot()

    def _csv_refresh_plot(self):
        if not self._csv_rows:
            return
        x_col  = self._csv_xcol_var.get()
        if x_col == "-":
            x_col = None
        y_cols  = [c for c, v in self._csv_y_vars.items() if v.get()]
        y2_cols = {c for c, v in self._csv_y2_vars.items() if v.get()}

        # usa righe filtrate per intervallo temporale
        rows = self._csv_get_filtered_rows()
        xs_raw, series, x_type = _uc_build_series(
            rows, x_col, y_cols, self._csv_col_meta)
        colors  = {c: self._csv_colors[c] for c in y_cols if c in self._csv_colors}
        x_label = x_col or "Indice"

        # serie principali CSV1
        self._csv_iplot.set_data(
            xs_raw, series, x_type, self._csv_col_meta,
            y2_cols=y2_cols, colors=colors, x_label=x_label)

        # ── bande range personalizzati sul grafico ─────────────────────
        self._csv_iplot.set_ranges(getattr(self, "_csv_ranges", []))

        # ── overlay ② DOPO set_ranges: colonne spuntate nel pannello CSV2 ──
        if self._csv_rows2:
            cols_ov = [c for c, v in self._csv_y_vars2.items() if v.get()]
            if cols_ov:
                self._csv_iplot._overlay_second_csv(
                    self._csv_rows2, x_col, cols_ov,
                    self._csv_colors2,
                    getattr(self, "_csv_col_meta2", self._csv_col_meta))

        self._csv_update_stats_cards(y_cols)
        self._csv_update_anomalies()

    def _csv_sel_all(self, val):
        for v in self._csv_y_vars.values():
            v.set(val)
        self._csv_refresh_plot()

    def _csv_update_stats(self, y_cols):
        # alias per compatibilità export — usa il nuovo metodo con card
        self._csv_update_stats_cards(y_cols)

    def _csv_update_anomalies(self):
        for w in self._csv_anomaly_container.winfo_children():
            w.destroy()
        if not self._csv_rows:
            self._csv_anomaly_badge.pack_forget()
            return
        x_col = self._csv_xcol_var.get()
        rows = self._csv_get_filtered_rows()
        anomalies = []

        # ── Range personalizzati (priorità assoluta) ──────────────────
        for rule in self._csv_ranges:
            col = rule["col"]; lo = rule.get("lo"); hi = rule.get("hi")
            violations = []
            for i, r in enumerate(rows):
                try:
                    val = float(r.get(col, "").replace(",", "."))
                except Exception:
                    continue
                ts = _uc_parse_dt(r.get(x_col, "")) if x_col and x_col != "-" else None
                ts_str = ts.strftime("%H:%M:%S") if ts else f"riga {i+1}"
                if lo is not None and val < lo:
                    violations.append((ts_str, val, f"< {lo:.4g}"))
                elif hi is not None and val > hi:
                    violations.append((ts_str, val, f"> {hi:.4g}"))
            if violations:
                # raggruppa: mostra prima e ultima violazione + conteggio
                cnt = len(violations)
                first_ts, first_val, first_dir = violations[0]
                last_ts,  last_val,  last_dir  = violations[-1]
                desc = (f"{cnt} campion{'e' if cnt==1 else 'i'} fuori range. "
                        f"Primo: {first_val:.4g} {first_dir} @ {first_ts}. "
                        f"Ultimo: {last_val:.4g} {last_dir} @ {last_ts}.")
                anomalies.append(("RANGE", f"{col} — {cnt} violazion{'e' if cnt==1 else 'i'}",
                                  desc, COLORS["error"]))

        # ── Rilevamento automatico (solo se nessun range manuale definito) ──
        if not self._csv_ranges:
            all_cols = self._csv_numeric_cols + self._csv_binary_cols
            num_rows = []
            for i, r in enumerate(rows):
                d = {"_ts": _uc_parse_dt(r.get(x_col, "")) if x_col != "-" else None}
                for col in all_cols:
                    try:
                        d[col] = float(r.get(col, "").replace(",", "."))
                    except Exception:
                        d[col] = 0.0
                num_rows.append(d)
            try:
                auto_anomalies, _ = detect_anomalies(num_rows, all_cols)
                anomalies.extend(auto_anomalies)
            except Exception:
                pass

        # aggiorna badge
        if anomalies:
            self._csv_anomaly_badge.configure(
                text=f"  ⚠ {len(anomalies)} anomalie  ")
            self._csv_anomaly_badge.pack(side="left", padx=6, pady=7)
        else:
            self._csv_anomaly_badge.pack_forget()

        if not anomalies:
            ctk.CTkLabel(self._csv_anomaly_container,
                         text="Nessuna anomalia rilevata",
                         font=("Segoe UI", 10),
                         text_color=COLORS["info"]).pack(anchor="w", padx=4, pady=4)
            return
        for tag, title, desc, color in anomalies[:30]:
            card = ctk.CTkFrame(self._csv_anomaly_container,
                                fg_color=COLORS["surface"], corner_radius=6)
            card.pack(fill="x", pady=2)
            ctk.CTkLabel(card, text=f"[{tag}]  {title}",
                         font=("Segoe UI", 10, "bold"),
                         text_color=color, anchor="w").pack(anchor="w", padx=8, pady=(6, 1))
            ctk.CTkLabel(card, text=desc,
                         font=("Segoe UI", 9),
                         text_color=COLORS["text2"],
                         anchor="w", wraplength=250).pack(anchor="w", padx=8, pady=(0, 6))

    def _csv_reset_zoom(self):
        if self._csv_iplot:
            self._csv_iplot.reset_zoom()

    def _csv_export_png(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato da esportare.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
            initialfile="grafico_csv.png")
        if not path:
            return
        try:
            self._csv_iplot.export_png(path)
            self.set_status(f"PNG salvato: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Errore PNG", str(e))

    def _csv_export_report(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato caricato.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt")],
            initialfile="report_csv.txt")
        if not path:
            return
        lines = [
            f"REPORT CSV  —  {os.path.basename(self._csv_filepath or '')}",
            f"Generato:  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            f"Righe: {len(self._csv_rows)}   Colonne: {len(self._csv_headers)}",
            f"Separatore: '{self._csv_sep}'   Encoding: {self._csv_enc}",
            "", "=" * 55, "COLONNE RILEVATE:", "=" * 55,
        ]
        for col in self._csv_headers:
            m = self._csv_col_meta.get(col, {})
            lines.append(
                f"  {col:<32}  [{m.get('col_type','?'):8}]  "
                f"{m.get('unit',''):6}  {m.get('label','')}")
        lines += ["", "=" * 55, "STATISTICHE:", "=" * 55]
        for col in self._csv_numeric_cols:
            vals = []
            for r in self._csv_rows:
                try:
                    vals.append(float(r.get(col, "").replace(",", ".")))
                except Exception:
                    pass
            if vals:
                mean = sum(vals) / len(vals)
                std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
                lines.append(
                    f"  {col:<32}  min={min(vals):.4g}  max={max(vals):.4g}"
                    f"  μ={mean:.4g}  σ={std:.4g}  N={len(vals)}")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.set_status(f"Report salvato: {os.path.basename(path)}")
            messagebox.showinfo("Completato", f"Report salvato:\n{path}")
        except Exception as e:
            messagebox.showerror("Errore salvataggio", str(e))

    def _csv_export_pdf(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato caricato.")
            return
        y_cols = [c for c, v in self._csv_y_vars.items() if v.get()]
        if not y_cols:
            messagebox.showwarning("Attenzione", "Seleziona almeno una serie Y.")
            return
        plant = simpledialog.askstring(
            "Nome impianto",
            "Inserisci il nome dell'impianto (es. Forno 3, CNC-A, Pressa 5T):",
            initialvalue="Impianto")
        if plant is None:
            return
        plant = plant.strip() or "Impianto"
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"report_{plant.replace(' ', '_')}.pdf")
        if not path:
            return
        y2_cols = {c for c, v in self._csv_y2_vars.items() if v.get()}
        x_col   = self._csv_xcol_var.get()
        if x_col == "-":
            x_col = None
        logo = getattr(self, "_grafici_logo_path", None)
        self.set_status("Generazione PDF impianto in corso...")
        def run():
            try:
                _cols2_exp = [c for c, v in self._csv_y_vars2.items() if v.get()]
                generate_plant_pdf(
                    rows        = self._csv_rows,
                    headers     = self._csv_headers,
                    col_meta    = self._csv_col_meta,
                    x_col       = x_col,
                    y_cols      = y_cols,
                    y2_cols     = y2_cols,
                    output_path = path,
                    plant_name  = plant,
                    logo_path   = logo,
                    notes       = "",
                    rows2       = self._csv_rows2 if (self._csv_rows2 and _cols2_exp) else None,
                    cols2       = _cols2_exp or None,
                    colors2     = self._csv_colors2,
                    col_meta2   = getattr(self, "_csv_col_meta2", {}),
                )
                self.after(0, lambda: self.set_status(
                    f"PDF salvato: {os.path.basename(path)}"))
                self.after(0, lambda: messagebox.showinfo(
                    "Completato", f"PDF salvato:\n{path}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore PDF", str(e)))
                self.after(0, lambda: self.set_status("Errore generazione PDF."))
        threading.Thread(target=run, daemon=True).start()


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

    def set_status(self, msg): self.status_lbl.configure(text=msg)


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
        path = filedialog.askopenfilename(
            title="Seleziona CSV per simulazione",
            filetypes=[("CSV", "*.csv"), ("Tutti", "*.*")])
        if not path:
            return
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

        # Fix 1 — thread zombie: aspetta terminazione, poi verifica
        if self._live_thread is not None and self._live_thread.is_alive():
            self._live_running.clear()
            self._live_ipc._live_user_zoomed = False  # reset zoom dopo pausa
            self._live_thread.join(timeout=2.0)
            if self._live_thread.is_alive():
                # thread non terminato: rinuncia all'avvio per sicurezza
                messagebox.showwarning("Attenzione",
                    "Thread precedente non terminato. Riprova tra un momento.")
                self._live_running.clear()
                return

        # svuota coda residua in modo sicuro (Fix race condition)
        try:
            while True:
                self._live_queue.get_nowait()
        except _queue.Empty:
            pass
                
        # 🔄 RESET automatico zoom al PLAY
        self._live_ipc.reset_zoom()
        self._live_ipc._live_user_zoomed = False  # Fix zoom: reset flag al PLAY
        self._live_ipc.clear_cursors()
        self._live_ipc._needs_full_redraw = True
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
                target=self._live_sim_thread, daemon=True)
        else:
            port = self._live_port_var.get()
            try:
                baud = int(self._live_baud_var.get())
            except Exception:
                baud = 9600
            self._live_thread = threading.Thread(
                target=self._live_serial_thread,
                args=(port, baud), daemon=True)

        self._live_thread.start()
        self._live_set_status("● Acquisizione in corso", COLORS["info"])
        self._live_poll()

    def _live_stop(self):
        self._live_running.clear()
        self._live_paused.clear()
        self._live_stop_interp_timer()
        self._live_start_btn.configure(state="normal")
        self._live_stop_btn.configure(state="disabled")
        self._live_pause_btn.configure(state="disabled", text="⏸",
                                       fg_color=COLORS["warn"])
        self._live_set_status("● Fermato", COLORS["warn"])

    def _live_toggle_pause(self):
        if not self._live_running.is_set():
            return
        if self._live_paused.is_set():
            self._live_paused.clear()
            self._live_ipc._live_user_zoomed = False  # Fix zoom: reset flag alla ripresa
            self._live_ipc.reset_zoom()               # Fix zoom: ritorna alla vista completa
        else:
            self._live_paused.set()
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

    def _live_clear(self):
        _was_running = self._live_running.is_set()
        if _was_running:
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
        if _was_running:
            self.after(400, self._live_start)

    # ── thread simulazione CSV ──────────────────────────────────────────
    def _live_sim_thread(self):
        import time

        def _wait_if_paused():
            """Blocca il thread finché la simulazione è in pausa."""
            while self._live_paused.is_set() and self._live_running.is_set():
                time.sleep(0.1)

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
                time.sleep(0.5 / sf if sf else 0)
            return

        # ── riproduzione CSV ────────────────────────────────────────────
        try:
            if _is_long_cycle_csv(self._live_csv_path):
                rows, headers, col_meta, numeric_cols, datetime_cols, _, _, _ = \
                    _parse_long_cycle_csv(self._live_csv_path)
                _has_embedded_ts = True
                self.after(0, self._live_log_append, "Formato: Long CSV (Cannon/Persico/Krauss Maffei)")
            else:
                rows, headers, col_meta, numeric_cols, datetime_cols, _, _, _ = \
                    parse_universal_csv(self._live_csv_path)
                _has_embedded_ts = False
        except Exception as e:
            self._live_queue.put({"_error": str(e)})
            return

        if not numeric_cols:
            self._live_queue.put({"_error": "Nessuna colonna numerica nel CSV."})
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

        if not _has_embedded_ts:
            self.after(0, self._live_log_append,
                f"Tempo: {'datetime «' + x_col_dt + '»' if use_datetime else '«' + x_col_num + '» (sec)' if use_num_time else 'indice fisso'}"
            )

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
                            time.sleep(max(0.01, delta / sf))
                    prev_dt = ts
                else:
                    if sf is not None:
                        time.sleep(0.1 / sf)

            elif use_datetime:
                ts = _uc_parse_dt(r.get(x_col_dt, ""))
                if ts:
                    row_out["_ts"] = ts
                    if prev_dt is not None and sf is not None:
                        delta = (ts - prev_dt).total_seconds()
                        time.sleep(max(0.01, delta / sf))
                    prev_dt = ts
                else:
                    if sf is not None:
                        time.sleep(0.1 / sf)

            elif use_num_time:
                try:
                    t_now = float(str(r.get(x_col_num, "")).replace(",", "."))
                    row_out["_sim_t"] = t_now
                    if prev_num is not None and sf is not None:
                        delta = t_now - prev_num
                        if delta > 0:
                            time.sleep(max(0.01, delta / sf))
                    prev_num = t_now
                except Exception:
                    if sf is not None:
                        time.sleep(0.1 / sf)

            else:
                row_out["_sim_i"] = i
                if sf is not None:
                    time.sleep(max(0.01, 1.0 / sf))

            try:
                self._live_queue.put_nowait(row_out)
            except _queue.Full:
                self._live_dropped = getattr(self, "_live_dropped", 0) + 1

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
        if not self._live_running.is_set():
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
                self._live_stop()
                return
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
                text=f"Campioni: {len(self._live_rows)}  |  In coda: {self._live_queue.qsize()}{drop_txt}")
            if set(self._live_numeric_cols) != getattr(self, "_live_last_cols_set", set()):
                self._live_last_cols_set = set(self._live_numeric_cols)
                self._live_rebuild_col_buttons()
            self._live_check_alarms()
            # Fix 2: se interp attiva, il tick a 200ms è già autoritative per il render
            # il poll aggiorna solo i dati, non ridisegna (elimina doppio redraw 2+5 Hz)
            interp_on = (getattr(self, "_live_interp_var", None) and
                         self._live_interp_var.get() and
                         self._live_interp_job is not None)
            if not interp_on:
                self._live_refresh_plot()

        try:
            ms = max(100, int(self._live_rate_var.get()))
        except Exception:
            ms = 500
        self.after(ms, self._live_poll)

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
        if (hasattr(self.master, '_live_running') and self.master._live_running.is_set()
                and not getattr(self._live_ipc, '_live_user_zoomed', False)):
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
        if not self._live_running.is_set():
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

if __name__=="__main__":
    app=LogAnalyzerApp();app.mainloop()
