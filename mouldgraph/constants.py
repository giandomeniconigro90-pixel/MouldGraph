# -*- coding: utf-8 -*-
"""
mouldgraph.constants
====================
Tutte le costanti globali dell'applicazione, estratte da
log_analyzer_desktop_live.py senza modifiche alla logica.

Dipendenze: nessuna dipendenza interna al package.
Compatibilità PyInstaller: OK (solo dati, zero import pesanti).
"""

# ---------------------------------------------------------------------------
# Finestra scorrevole grafico live (performance)
# ---------------------------------------------------------------------------
MAX_LIVE_POINTS: int = 500

# Limite dimensione file CSV importabile
MAX_CSV_BYTES: int = 50 * 1024 * 1024  # 50 MB

# Colonne obbligatorie nel CSV ciclo stampo
REQUIRED_COLUMNS: set = {
    "Partita", "Materiale", "IdCiclo", "Parametro",
    "Timestamp", "Valore", "Step",
}

# ---------------------------------------------------------------------------
# Palette UI
# ---------------------------------------------------------------------------
COLORS: dict = {
    "bg":       "#0f1117",
    "surface":  "#1a1d27",
    "surface2": "#22263a",
    "border":   "#2e3350",
    "accent":   "#6c63ff",
    "accent2":  "#00d4ff",
    "error":    "#ff4d4f",
    "warn":     "#faad14",
    "info":     "#52c41a",
    "debug":    "#1890ff",
    "text":     "#e8eaf6",
    "text2":    "#8892b0",
}

LEVEL_COLORS: dict = {
    "ERROR": COLORS["error"],
    "WARN":  COLORS["warn"],
    "INFO":  COLORS["info"],
    "DEBUG": COLORS["debug"],
}

LEVEL_BG: dict = {
    "ERROR": "#4a1a1a",
    "WARN":  "#4a3a00",
    "INFO":  "#1a3a0a",
    "DEBUG": "#0a2a4a",
}

LEVEL_HOVER: dict = {
    "ERROR": "#7a2020",
    "WARN":  "#7a5a00",
    "INFO":  "#2a5a10",
    "DEBUG": "#104070",
}

# ---------------------------------------------------------------------------
# Palette serie grafici CSV universale
# ---------------------------------------------------------------------------
_UC_SERIES_PALETTE: list = [
    "#e5672c", "#3f51b5", "#29b6f6", "#66bb6a",
    "#9c27b0", "#ff9800", "#e7b73b", "#607d8b",
    "#f44322", "#00bcd4", "#8bc34a", "#ff5722",
]

# ---------------------------------------------------------------------------
# Pattern rilevamento unità di misura per colonne CSV
# ---------------------------------------------------------------------------
UNIT_PATTERNS: list = [
    (r"temp|calore|forno|cottura",          "°C",    "Temperatura"),
    (r"press|bar|kpa|psi|mpa",              "bar",   "Pressione"),
    (r"forza|kn|newton|force",              "kN",    "Forza"),
    (r"portata|flow|l_min|lmin|l/min",      "L/min", "Portata"),
    (r"pos|stroke|piano|quota|mm(?!hg)",    "mm",    "Posizione"),
    (r"vel|speed|rpm|giri|rotaz",           "rpm",   "Velocità"),
    (r"vuoto|vacuum|mbar",                  "mbar",  "Vuoto"),
    (r"corr|ampere|current|amps",           "A",     "Corrente"),
    (r"volt|tension|tensione",              "V",     "Tensione"),
    (r"umid|humid|rh(?!\w)",               "%RH",   "Umidità"),
    (r"colla|glue|adhesive|erog",           "g/s",   "Erogazione"),
    (r"angolo|angle|deg(?!\w)|gradi",      "°",     "Angolo"),
    (r"peso|weight|kg(?!\w)|gram",         "kg",    "Peso"),
    (r"freq|hz(?!\w)|hertz",               "Hz",    "Frequenza"),
    (r"pot|watt|kw(?!\w)|power",           "kW",    "Potenza"),
    (r"level|livello|fill|riempim",         "%",     "Livello"),
    (r"co2|o2|gas|ppm",                     "ppm",   "Gas"),
    (r"vibr|accel|g(?!\w)",                "m/s²",  "Vibrazione"),
    (r"torque|coppia|nm(?!\w)",            "Nm",    "Coppia"),
    (r"dist|distanza|range(?!\w)",         "mm",    "Distanza"),
]

# ---------------------------------------------------------------------------
# Profili stampo (codice 2 lettere -> nome stampo, lato)
# ---------------------------------------------------------------------------
MOULD_PROFILES: dict = {
    "VG": ("Inner Tub",            None),
    "PS": ("Polecrasher",          "SX"),
    "PD": ("Polecrasher",          "DX"),
    "TD": ("Tub Floor Shell",      "DX"),
    "ST": ("Tub Floor Shell",      "SX"),
    "RF": ("Front Firewall",       None),
    "IC": ("Central Cofango",      None),
    "SD": ("Side Cofango Inner",   "DX"),
    "SS": ("Side Cofango Inner",   "SX"),
}

# ---------------------------------------------------------------------------
# Formati timestamp supportati (log testuale)
# ---------------------------------------------------------------------------
TS_FORMATS: list = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%d/%m/%Y %H:%M:%S",
    "%d.%m.%Y %H:%M:%S",
    "%b %d %H:%M:%S",
]

# Formati timestamp supportati (CSV universale)
UC_TS_FORMATS: list = [
    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",    "%d/%m/%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",    "%d.%m.%Y %H:%M",
    "%d_%m_%Y_%H_%M_%S",    "%d/%m/%Y_%H_%M_%S",
    "%Y/%m/%d %H:%M:%S",    "%m/%d/%Y %H:%M:%S",
    "%H:%M:%S",
]

# Formato timestamp CSV long-format (Cannon/Persico/Krauss-Maffei)
LONG_TS_FORMAT: str = "%d_%m_%Y_%H_%M_%S"

# Nomi colonna tempo riconosciuti automaticamente nel CSV universale
TIME_COL_NAMES: set = {
    "time", "tempo", "t", "sec", "seconds", "s",
    "zeit", "temps", "elapsed", "elapsed_s", "ts",
    "ticks", "sample",
}

# ---------------------------------------------------------------------------
# Encoding supportati per lettura file
# ---------------------------------------------------------------------------
SUPPORTED_ENCODINGS: list = [
    "utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1",
]
