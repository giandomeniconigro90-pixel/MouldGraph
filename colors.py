# -*- coding: utf-8 -*-
"""
colors.py
Tutte le costanti colore centralizzate per MouldGraph.

Importare con:
    from colors import (
        COLORS, LEVEL_COLORS, LEVEL_BG, LEVEL_HOVER,
        _UC_SERIES_PALETTE, _PLANT_PALETTE,
        _PC, _SERIES_COLORS, plant_pdf_colors,
    )
"""

COLORS = {
    "bg":      "#0f1117",
    "surface": "#1a1d27",
    "surface2":"#22263a",
    "border":  "#2e3350",
    "accent":  "#6c63ff",
    "accent2": "#00d4ff",
    "error":   "#ff4d4f",
    "warn":    "#faad14",
    "info":    "#52c41a",
    "debug":   "#1890ff",
    "text":    "#e8eaf6",
    "text2":   "#8892b0",
}

LEVEL_COLORS = {
    "ERROR": COLORS["error"],
    "WARN":  COLORS["warn"],
    "INFO":  COLORS["info"],
    "DEBUG": COLORS["debug"],
}

LEVEL_BG = {
    "ERROR": "#4a1a1a",
    "WARN":  "#4a3a00",
    "INFO":  "#1a3a0a",
    "DEBUG": "#0a2a4a",
}

LEVEL_HOVER = {
    "ERROR": "#7a2020",
    "WARN":  "#7a5a00",
    "INFO":  "#2a5a10",
    "DEBUG": "#104070",
}

# ── Palette serie grafici universali (InteractivePlotCanvas) ───────────────
_UC_SERIES_PALETTE = [
    "#e5672c", "#3f51b5", "#29b6f6", "#66bb6a",
    "#9c27b0", "#ff9800", "#e7b73b", "#607d8b",
    "#f44322", "#00bcd4", "#8bc34a", "#ff5722",
]

# ── Palette PDF impianto generico ──────────────────────────────────────────
_PLANT_PALETTE = [
    "#e5672c", "#3f51b5", "#29b6f6", "#66bb6a",
    "#9c27b0", "#ff9800", "#e7b73b", "#607d8b",
    "#f44322", "#00bcd4", "#8bc34a", "#ff5722",
]

# ── Colori PDF pressa (Cannon / Persico / Krauss Maffei) ──────────────────
_PC = {
    1: "#f44322", 2: "#3f51b5", 3: "#29b6f6", 4: "#66bb6a",
    5: "#7d0910", 6: "#607d8b", 7: "#9c27b0", 8: "#ff9800",
    "set_temp":  "#795548",
    "set_forza": "#7d0910",
    "lmax":      "#607d8b",
    "lmin":      "#9c27b0",
    "bg":        "#ccffff",
    "grid":      "#cccccc",
}

# ── Colori per nome-sonda (temperature, pressioni, forze, vuoti…) ──────────
_SERIES_COLORS = {
    "TS1": "#e5672c", "TS2": "#828282", "TS3": "#407da5", "TS4": "#e7b73b",
    "TS5": "#9c27b0", "TS6": "#607d8b", "TS7": "#ff9800", "TS8": "#29b6f6",
    "TI1": "#e5672c", "TI2": "#828282", "TI3": "#407da5", "TI4": "#e7b73b",
    "TI5": "#9c27b0", "TI6": "#607d8b", "TI7": "#ff9800", "TI8": "#29b6f6",
    "T1":  "#e5672c", "T2":  "#828282", "T3":  "#407da5", "T4":  "#e7b73b",
    "T5":  "#9c27b0", "T6":  "#607d8b", "T7":  "#ff9800", "T8":  "#29b6f6",
    "P1":  "#407da5", "P2":  "#e5672c", "P3":  "#828282", "P4":  "#e7b73b",
    "Z1":  "#407da5", "Z2":  "#e5672c", "Z3":  "#828282", "Z4":  "#e7b73b",
    "F1":  "#f44322", "F2":  "#3f51b5", "F3":  "#29b6f6", "F4":  "#66bb6a",
    "FC":  "#f44322", "SPC": "#7d0910",
    "VS1": "#407da5", "VS2": "#e5672c",
    "V1":  "#407da5", "V2":  "#e5672c",
    "VI1": "#407da5", "VI2": "#e5672c", "VI3": "#828282", "VI4": "#e7b73b",
    "V3":  "#828282", "V4":  "#e7b73b",
}


def plant_pdf_colors(cols):
    """Assegna un colore dalla _PLANT_PALETTE a ogni colonna."""
    return {c: _PLANT_PALETTE[i % len(_PLANT_PALETTE)] for i, c in enumerate(cols)}
