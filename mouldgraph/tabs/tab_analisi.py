# -*- coding: utf-8 -*-
"""Tab "Analisi log": apertura log, filtri, statistiche, timeline, AI, export."""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
import json
import csv
import os
from datetime import datetime
from collections import defaultdict
from ..constants import COLORS, LEVEL_BG, LEVEL_COLORS, LEVEL_HOVER
from ..log_analysis import ai_analysis, build_timeline, norm_sig, parse_log
from ..pdf_front_firewall import detect_csv_type
from ..widgets import TimelineCanvas


class AnalisiLogMixin:
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
