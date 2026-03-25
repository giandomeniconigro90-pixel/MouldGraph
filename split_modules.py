#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
split_modules.py  –  Refactor automatico di log_analyzer_desktop_live.py
Esegui dalla cartella del progetto:
    python split_modules.py
"""

import os, re, sys

SRC = "log_analyzer_desktop_live.py"

if not os.path.exists(SRC):
    print(f"ERRORE: '{SRC}' non trovato nella cartella corrente.")
    sys.exit(1)

with open(SRC, encoding="utf-8") as f:
    raw = f.read()

lines = raw.splitlines(keepends=True)
total = len(lines)
print(f"\nFile letto: {total} righe  ({len(raw)} caratteri)")

# ── Trova le sezioni ─────────────────────────────────────────────────────────

def find_line(keyword, from_line=0):
    for i in range(from_line, total):
        if keyword in lines[i]:
            return i
    return None

def find_class(name, from_line=0):
    pat = re.compile(rf"^class\s+{name}\b")
    for i in range(from_line, total):
        if pat.match(lines[i]):
            return i
    return None

def find_def(name, from_line=0):
    pat = re.compile(rf"^def\s+{name}\b")
    for i in range(from_line, total):
        if pat.match(lines[i]):
            return i
    return None

def block(start, end):
    return "".join(lines[start:end])

def block_exclude_classes(start, end, exclude_classes):
    """Estrae il blocco [start, end) saltando le classi in exclude_classes."""
    result = []
    skip = False
    for i in range(start, end):
        line = lines[i]
        # Inizia a saltare se troviamo una classe da escludere
        for cls in exclude_classes:
            if re.match(rf"^class\s+{cls}\b", line):
                skip = True
                break
        if skip:
            # Smette di saltare quando trova una riga a livello 0
            # che NON è una delle classi da escludere
            if i > start and line.strip() and not line[0].isspace():
                is_excluded = any(
                    re.match(rf"^class\s+{cls}\b", line)
                    for cls in exclude_classes
                )
                if not is_excluded:
                    skip = False
                    result.append(line)
            continue
        result.append(line)
    return "".join(result)

# ── Marcatori ────────────────────────────────────────────────────────────────

ln_parser_start  = find_line("# -- PARSER LOG --")
ln_siemens_start = find_line("# -- SIEMENS CSV")
ln_univ_start    = find_line("# -- UNIVERSAL CSV")
if ln_univ_start is None:
    ln_univ_start = find_def("_is_long_cycle_csv")

ln_timeline      = find_class("TimelineCanvas")
ln_iplot         = find_class("InteractivePlotCanvas")

ln_pdf_start     = find_line("PLANTPALETTE")
if ln_pdf_start is None:
    ln_pdf_start = find_line("PLANT PALETTE")
if ln_pdf_start is None:
    ln_pdf_start = find_def("generate_plant_pdf")
if ln_pdf_start is None:
    ln_pdf_start = find_def("plantpdfcolors")

ln_app_start     = find_class("LogAnalyzerApp")

print("\n── Confini trovati ──────────────────────────────")
for name, ln in [
    ("PARSER LOG",            ln_parser_start),
    ("SIEMENS CSV",           ln_siemens_start),
    ("UNIVERSAL CSV",         ln_univ_start),
    ("TimelineCanvas",        ln_timeline),
    ("InteractivePlotCanvas", ln_iplot),
    ("PDF start",             ln_pdf_start),
    ("LogAnalyzerApp",        ln_app_start),
]:
    print(f"  {name:28s}: riga {(ln or -1)+1}")

# ── Intestazioni import ───────────────────────────────────────────────────────

HDR = {
"log_parser.py": """# -*- coding: utf-8 -*-
import re
from datetime import datetime
from collections import defaultdict
""",
"csv_parser.py": """# -*- coding: utf-8 -*-
import csv, re, math, os
import io as _io
from datetime import datetime
from collections import OrderedDict, defaultdict
""",
"charts.py": """# -*- coding: utf-8 -*-
import tkinter as tk
import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from datetime import datetime
from colors import COLORS
from csv_parser import _uc_build_series
""",
"plot_canvas.py": """# -*- coding: utf-8 -*-
import tkinter as tk
import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from datetime import datetime
from colors import COLORS
from csv_parser import _uc_build_series
""",
"pdf_export.py": """# -*- coding: utf-8 -*-
import os, re, csv, math
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from colors import COLORS
""",
"app_main.py": """# -*- coding: utf-8 -*-
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
""",
}

# ── Generazione contenuti ─────────────────────────────────────────────────────

print("\n── Generazione file ─────────────────────────────")
ok = True

files = {}

# log_parser.py: da PARSER LOG a SIEMENS CSV
files["log_parser.py"] = HDR["log_parser.py"] + "\n" + block(ln_parser_start, ln_siemens_start)

# csv_parser.py: da SIEMENS CSV a iplot, ESCLUDENDO le classi Canvas
files["csv_parser.py"] = HDR["csv_parser.py"] + "\n" + block_exclude_classes(
    ln_siemens_start, ln_iplot,
    ["TimelineCanvas", "LineChart", "PumpCanvas"]
)

# charts.py: da TimelineCanvas a InteractivePlotCanvas
files["charts.py"] = HDR["charts.py"] + "\n" + block(ln_timeline, ln_iplot)

# plot_canvas.py: da InteractivePlotCanvas a PDF start
files["plot_canvas.py"] = HDR["plot_canvas.py"] + "\n" + block(ln_iplot, ln_pdf_start)

# pdf_export.py: da PDF start a LogAnalyzerApp
files["pdf_export.py"] = HDR["pdf_export.py"] + "\n" + block(ln_pdf_start, ln_app_start)

# app_main.py: da LogAnalyzerApp a fine file
files["app_main.py"] = HDR["app_main.py"] + "\n" + block(ln_app_start, total)

# ── Scrivi i file ─────────────────────────────────────────────────────────────

for fname, content in files.items():
    if not content.strip():
        print(f"  ✗ {fname}  — contenuto vuoto!")
        ok = False
        continue
    with open(fname, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✓ {fname:25s}  ({len(content.splitlines()):4d} righe)")

if ok:
    print("""
── Prossimi passi ────────────────────────────────
1. Verifica imports:
     python -c "import log_parser; import csv_parser; import charts; import plot_canvas; import pdf_export"
2. Avvia l'app:
     python app_main.py
3. Push su GitHub:
     git add .
     git commit -m "Refactor: split in moduli separati"
     git push origin main
""")
else:
    print("\n⚠  Alcuni file non sono stati generati. Controlla i confini sopra.")
