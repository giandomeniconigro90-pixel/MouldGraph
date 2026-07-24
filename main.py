# -*- coding: utf-8 -*-
"""
MouldGraph - Entry point
Avvia l'applicazione importando dai moduli separati.
Logica e grafica identiche al file originale log_analyzer_desktop_live.py
"""

# Re-import tutto dall'applicazione originale tramite i moduli
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

# Avvia l'app principale (il file originale contiene ancora la GUI e il loop)
import runpy
runpy.run_path("log_analyzer_desktop_live.py", run_name="__main__")
