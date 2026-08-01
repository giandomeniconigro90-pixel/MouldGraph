# -*- coding: utf-8 -*-
"""
mouldgraph.app
==============
** STUB - Fase 1: estrazione DIFFERITA **

La classe LogAnalyzerApp NON viene estratta in questo primo passaggio.

Motivazione (blocco documentato come da vincoli di refactoring):

1. ALTISSIMO ACCOPPIAMENTO:
   LogAnalyzerApp presenta oltre 60 metodi che si chiamano reciprocamente
   con self.* senza passaggio esplicito di dipendenze. Non è sicuro
   spezzarla in fasi intermediate senza test di regressione.

2. STATO CONDIVISO GLOBALE (self.*):
   La classe mantiene decine di attributi di stato (self.parsed,
   self.rows_csv, self.live_thread, self.canvas_live, ecc.) che
   vengono scritti e letti da quasi tutti i metodi. Una rifattorizzazione
   sicura richiede prima di identificare quali attributi appartengono
   a quale sotto-componente (LiveMonitor, CsvAnalysisTab, LogTab, ecc.).

3. DIPENDENZE CIRCOLARI POTENZIALI:
   Molti metodi istanziano widget (TimelineCanvas, InteractivePlotCanvas)
   e li configurano inline. Se si estrae app.py prima di verificare che
   widgets.py si importi correttamente nell'ambiente target, si rischia
   un ImportError silenzioso che rompe l'avvio.

4. THREAD E LIVE SERIAL:
   I metodi di monitoraggio live usano threading.Thread + queue.
   Estrarre questa logica in isolamento richiede un sub-modulo dedicato
   (es. mouldgraph/live_monitor.py) che non fa parte della fase 1.

PIANO FASE 2 (proposto):
  - Verificare che tutti i moduli della fase 1 si importino senza errori
    su una installazione pulita (venv con customtkinter, matplotlib, numpy).
  - Creare mouldgraph/live_monitor.py (LiveSerialWorker, LiveFileWorker)
    che non dipendono da Tkinter/CTk.
  - Creare mouldgraph/app.py con LogAnalyzerApp che fa:
      from .widgets import TimelineCanvas, InteractivePlotCanvas, ...
      from .log_parsers import parse_log, ai_analysis
      from .csv_parsers import parse_universal_csv, ...
      from .pdf_reports import export_pdf_log, ...
      from .live_monitor import LiveSerialWorker, ...
  - Aggiornare main.py solo dopo test manuale completo.

In caso di problemi in fase 2, il monolite log_analyzer_desktop_live.py
rimane invariato e funzionante come fallback al 100%%.
"""

# Placeholder: nessun codice eseguibile in questa stub.
# LogAnalyzerApp resta in log_analyzer_desktop_live.py (backup monolite).

__all__ = []
