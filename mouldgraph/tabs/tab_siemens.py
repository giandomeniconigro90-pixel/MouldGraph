# -*- coding: utf-8 -*-
"""Tab Siemens: caricamento CSV Siemens, grafico e report."""
import customtkinter as ctk
from tkinter import filedialog
from tkinter import messagebox
import os
from ..constants import COLORS
from ..log_analysis import detect_anomalies, parse_siemens_csv
from ..pdf_front_firewall import detect_csv_type
from ..widgets import LineChart, PumpCanvas


class SiemensMixin:
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
