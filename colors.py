# -*- coding: utf-8 -*-
"""
colors.py  —  Costanti colore centralizzate per MouldGraph.
Importare con:  from colors import COLORS, LEVEL_COLORS, LEVEL_BG, LEVEL_HOVER
"""

COLORS = {
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
