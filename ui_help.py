# -*- coding: utf-8 -*-
"""
ui_help.py  —  Tab "Come usare" di MouldGraph.
Contiene il solo metodo _build_help, da mixare in LogAnalyzerApp.
"""
import customtkinter as ctk
from colors import COLORS


class HelpTabMixin:
    """Mixin che aggiunge il tab di aiuto all'app principale."""

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
