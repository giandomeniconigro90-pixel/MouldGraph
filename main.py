# -*- coding: utf-8 -*-
"""
MouldGraph - Entry point
Avvia l'applicazione importando dai moduli separati.
Logica e grafica identiche al file originale log_analyzer_desktop_live.py
"""

import sys, os

# Assicura che la cartella del progetto sia sempre in PYTHONPATH
# (necessario quando lanciato come .exe da PyInstaller)
_base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
if _base not in sys.path:
    sys.path.insert(0, _base)

# Pre-carica i moduli separati
from constants import (
    COLORS, LEVEL_COLORS, LEVEL_BG, LEVEL_HOVER,
    MAX_LIVE_POINTS, UNIT_PATTERNS,
    _UC_SERIES_PALETTE, _PLANT_PALETTE, _PC, _SERIES_COLORS,
    _PROFILES, _PRESSA_STAMPI, _LK
)
from parsers import (
    parse_line, parse_log, norm_level, parse_ts, norm_sig,
    ai_analysis, build_timeline,
    parse_siemens_csv, detect_anomalies,
    parse_universal_csv, _is_long_cycle_csv, _parse_long_cycle_csv,
    _uc_build_series, _uc_interpolate_timestamps
)
from charts import TimelineCanvas, LineChart, PumpCanvas, InteractivePlotCanvas

# Inietta i simboli nel namespace di __main__ cosi'
# log_analyzer_desktop_live li trova gia' definiti
import __main__
for _name, _obj in [
    ("COLORS", COLORS), ("LEVEL_COLORS", LEVEL_COLORS),
    ("LEVEL_BG", LEVEL_BG), ("LEVEL_HOVER", LEVEL_HOVER),
    ("MAX_LIVE_POINTS", MAX_LIVE_POINTS), ("UNIT_PATTERNS", UNIT_PATTERNS),
    ("_UC_SERIES_PALETTE", _UC_SERIES_PALETTE), ("_PLANT_PALETTE", _PLANT_PALETTE),
    ("_PC", _PC), ("_SERIES_COLORS", _SERIES_COLORS),
    ("_PROFILES", _PROFILES), ("_PRESSA_STAMPI", _PRESSA_STAMPI), ("_LK", _LK),
    ("parse_line", parse_line), ("parse_log", parse_log),
    ("norm_level", norm_level), ("parse_ts", parse_ts), ("norm_sig", norm_sig),
    ("ai_analysis", ai_analysis), ("build_timeline", build_timeline),
    ("parse_siemens_csv", parse_siemens_csv), ("detect_anomalies", detect_anomalies),
    ("parse_universal_csv", parse_universal_csv),
    ("_is_long_cycle_csv", _is_long_cycle_csv),
    ("_parse_long_cycle_csv", _parse_long_cycle_csv),
    ("_uc_build_series", _uc_build_series),
    ("_uc_interpolate_timestamps", _uc_interpolate_timestamps),
    ("TimelineCanvas", TimelineCanvas), ("LineChart", LineChart),
    ("PumpCanvas", PumpCanvas), ("InteractivePlotCanvas", InteractivePlotCanvas),
]:
    setattr(__main__, _name, _obj)

# Avvia l'app principale
import log_analyzer_desktop_live  # noqa
