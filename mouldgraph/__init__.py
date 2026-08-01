# -*- coding: utf-8 -*-
"""
mouldgraph — package modulare parallelo (refactor phase 1).

Questo package è una struttura PARALLELA al monolite
log_analyzer_desktop_live.py, che rimane invariato come backup funzionante.
NON viene ancora usato da main.py: va verificato prima dell'integrazione.

Moduli disponibili:
  constants   — costanti UI, colori, soglie
  log_parsers — parser log testuali (parse_line, parse_log, ai_analysis …)
  csv_parsers — parser CSV (Siemens, Universal, Long-format Cannon/Persico)
  widgets     — widget Canvas Tkinter riutilizzabili (Timeline, LineChart …)
  pdf_reports — generazione report PDF con matplotlib (⚠ dipende da widgets)
  app         — classe LogAnalyzerApp (⚠ estrazione futura, non ancora fatta)
"""

__version__ = "0.1.0-refactor"
__all__ = [
    "constants",
    "log_parsers",
    "csv_parsers",
    "widgets",
    "pdf_reports",
]
