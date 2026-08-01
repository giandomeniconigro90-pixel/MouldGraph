# -*- coding: utf-8 -*-
"""
mouldgraph — Package modulare parallelo (Refactor Phase 1)
==========================================================

STRUTTURA PARALLELA
-------------------
Questo package è una struttura PARALLELA al monolite
``log_analyzer_desktop_live.py``, che rimane invariato come backup
funzionante. NON viene usato da main.py: la connessione avverrà
soltanto nella Fase 2, dopo verifica completa.

STUB - app.py (Fase 1)
----------------------
``mouldgraph/app.py`` è intenzionalmente uno stub vuoto.
La classe ``LogAnalyzerApp`` NON è ancora estratta dal monolite.
L'estrazione è pianificata per la Fase 2 e richiede:
  - isolamento completo delle dipendenze globali (tk root, variabili di stato)
  - test di compatibilità PyInstaller / CustomTkinter
  - validazione matplotlib backend (Agg vs TkAgg)

MODULI DISPONIBILI
------------------
  constants   — Costanti UI, colori, soglie numeriche
  log_parsers — Parser log testuali (parse_line, parse_log, ai_analysis …)
  csv_parsers — Parser CSV Siemens, Universal, Long-format Cannon/Persico
  widgets     — Widget Canvas Tkinter riutilizzabili (Timeline, LineChart …)
  pdf_reports — Generazione report PDF con matplotlib (⚠ dipende da widgets)
  app         — Stub Fase 1 (⚠ LogAnalyzerApp non ancora estratta)

DIPENDENZE OPZIONALI
--------------------
  customtkinter  — richiesta da widgets
  matplotlib     — richiesta da pdf_reports
  numpy          — richiesta da pdf_reports / widgets

REVERSIBILITÀ
-------------
Per ripristinare il comportamento originale è sufficiente eseguire
``main.py`` che punta esclusivamente al monolite. Nessun file del monolite
è stato modificato.
"""

__version__ = "0.1.0-refactor"
__author__ = "Giandomenico Nigro"
__status__ = "Phase 1 — Parallel structure, not yet connected to main.py"

__all__ = [
    "constants",
    "log_parsers",
    "csv_parsers",
    "widgets",
    "pdf_reports",
    # "app" intentionally excluded: stub only, LogAnalyzerApp not extracted yet
]
