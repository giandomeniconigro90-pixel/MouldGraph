# -*- coding: utf-8 -*-
"""Finestra principale di MouldGraph: compone i mixin dei tab."""
import customtkinter as ctk
import threading
import queue as _queue
from .constants import COLORS
from .tabs import AnalisiLogMixin, SiemensMixin, GraficiMixin, HelpMixin, CsvMixin, LiveMixin

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class LogAnalyzerApp(AnalisiLogMixin, SiemensMixin, GraficiMixin, HelpMixin, CsvMixin, LiveMixin, ctk.CTk):
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
        self._live_stop_event = threading.Event()
        self._live_done_event = threading.Event()
        self._live_poll_job = None
        self._live_worker_error = None
        self._live_total = 0
        self._live_loading = False
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


    def set_status(self, msg): self.status_lbl.configure(text=msg)


def main():
    app=LogAnalyzerApp();app.mainloop()
