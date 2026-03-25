# -*- coding: utf-8 -*-
"""
tab_grafici.py  —  GraficiMixin
Contiene _build_grafici_tab e tutti i metodi _grafici_* per la Tab Grafici.
Estratto da log_analyzer_desktop_live.py e adattato come mixin.
Importato da LogAnalyzerApp in app_main.py.
"""
import os
import csv
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
from collections import defaultdict

import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

from colors import COLORS, LEVEL_COLORS

# ── costanti colori pressa / PDF ──────────────────────────────────────────────
_PC = {
    1: "#f44322", 2: "#3f51b5", 3: "#29b6f6", 4: "#66bb6a",
    5: "#7d0910", 6: "#607d8b", 7: "#9c27b0", 8: "#ff9800",
    "set_temp": "#795548", "set_forza": "#7d0910",
    "lmax": "#607d8b", "lmin": "#9c27b0",
    "bg": "#ccffff", "grid": "#cccccc",
}

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

_LK = dict(fontsize=7.0, framealpha=0.9, edgecolor="#ccc",
           handlelength=1.8, handleheight=0.9,
           borderpad=0.6, labelspacing=0.3)

# ── profili pressa/stampo ─────────────────────────────────────────────────────
# Formato: { nome_stampo: { "pressa": str, "gruppi": [ {label, cols, y, yticks, set_col?, delta?} ] } }
# Estendibile senza toccare il mixin.
_PRESSA_STAMPI = {
    # ── esempio: aggiungere profili reali qui ────────────────────────────────
    # "Stampo_A": {
    #     "pressa": "Cannon 5000T",
    #     "gruppi": [ ... ]
    # },
}

# lista pressa → stampi per il menu a tendina
_PRESSALIST = {}
for _sn, _sp in _PRESSA_STAMPI.items():
    _pr = _sp.get("pressa", "Generica")
    _PRESSALIST.setdefault(_pr, []).append(_sn)
if not _PRESSALIST:
    _PRESSALIST["Generica"] = []


# ── helpers PDF ───────────────────────────────────────────────────────────────

def _pdf_fmt_date(ts: str) -> str:
    try:
        return datetime.strptime(ts.rstrip("Z"), "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return ts


def _pdf_fmt_ts(ts) -> str:
    if ts is None:
        return ""
    try:
        return ts.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(ts)


def _pdf_parse_csv(filepath: str):
    """Legge un CSV ciclo (Parametro, Timestamp, Valore, Step, Setpoint …)
    e restituisce (data_dict, meta_dict) compatibili con _pdf_temp / _pdf_forza."""
    raw = None
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]:
        try:
            with open(filepath, encoding=enc) as f:
                raw = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if raw is None:
        raise ValueError("Impossibile leggere il file con gli encoding supportati.")

    lines = [l for l in raw.splitlines() if l.strip()]
    start = 1 if lines and lines[0].upper().startswith("REPORT GENERATED") else 0
    hdr   = lines[start]

    data_sep = ";" if (start + 1 < len(lines) and ";" in lines[start + 1]) else ","
    if data_sep == ";":
        headers = [h.strip() for h in hdr.split(",")]
        rows = []
        for l in lines[start + 1:]:
            parts = l.split(";")
            rows.append({h: parts[i].strip().replace(",", ".") if i < len(parts) else ""
                         for i, h in enumerate(headers)})
    else:
        import io as _io
        rows = list(csv.DictReader(_io.StringIO("\n".join(lines[start:]))))

    TSFMTS = [
        "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
        "%d_%m_%Y_%H_%M_%S", "%d/%m/%Y_%H_%M_%S", "%Y-%m-%dT%H:%M:%S.%f",
    ]

    def _pt(s):
        s = s.strip().rstrip("Z")
        for fmt in TSFMTS:
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                pass
        return None

    t0 = None
    data: dict[str, list] = defaultdict(list)
    tslist = []

    for r in rows:
        ts = _pt(r.get("Timestamp", ""))
        if ts is None:
            continue
        if t0 is None:
            t0 = ts
        tslist.append(ts)
        sec = (ts - t0).total_seconds()
        try:
            val = float(r.get("Valore", "").replace(",", "."))
        except Exception:
            continue
        try:
            ss = r.get("Setpoint", "").strip().replace(",", ".")
            sp = float(ss) if ss else None
        except Exception:
            sp = None
        try:
            step = int(r.get("Step", 0))
        except Exception:
            step = 0
        data[r.get("Parametro", "").strip()].append((sec, val, step, sp))

    tss = tslist[0]  if tslist else None
    tse = tslist[-1] if tslist else None
    dur = int((tse - tss).total_seconds()) if tss and tse else 0

    meta = {
        "idciclo":   rows[0].get("IdCiclo",    "") if rows else "",
        "partite":   ", ".join(sorted(set(r.get("Partita",   "") for r in rows))),
        "operatore": rows[0].get("Operatore",  "") if rows else "",
        "materiale": ", ".join(sorted(set(r.get("Materiale", "") for r in rows))),
        "tsraw":     rows[0].get("Timestamp",  "") if rows else "",
        "tsstart":   tss, "tsend": tse, "dursec": dur,
    }
    return data, meta


def _pdf_setup_ax(ax, title, ylabel, ylim, yticks, xticks, xmax,
                  draw_bg=True, bg_xmax=None, bg_ymax=None):
    if draw_bg:
        yr    = ylim[1] - ylim[0]
        y_top = bg_ymax if bg_ymax is not None else ylim[0] + yr * 206.36 / 309.54
        if bg_xmax is not None:
            ax.fill_between([0, bg_xmax], ylim[0], y_top,
                            color=_PC["bg"], zorder=0, linewidth=0)
        else:
            ax.axhspan(ylim[0], y_top, color=_PC["bg"], zorder=0)
    ax.set_facecolor("white")
    ax.set_xlim(0, xmax)
    ax.set_ylim(ylim[0], ylim[1])
    ax.set_yticks(yticks)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, f: f"{v:.1f}" if v != int(v) else f"{int(v)}"))
    ax.set_xticks(xticks)
    ax.tick_params(axis="both", labelsize=7, length=3, color="#404040")
    ax.set_xlabel("sec", fontsize=7, labelpad=1)
    ax.set_ylabel(ylabel, fontsize=7, labelpad=2)
    ax.set_title(title, fontsize=9, fontweight="bold", pad=4, color="#111")
    ax.grid(True, linestyle="-", linewidth=0.3,
            color=_PC["grid"], alpha=1.0, zorder=1)
    for sp in ax.spines.values():
        sp.set_edgecolor("#888")
        sp.set_linewidth(0.5)


def _pdf_temp(ax, data, params, setval, title, pr):
    _pdf_setup_ax(ax, title, "", pr["temp_y"], pr["temp_yticks"],
                  pr["x_ticks"], pr["x_max"])
    ax.axhline(setval, color=_PC["set_temp"], lw=0.8, zorder=4, label="SET")
    for i, p in enumerate(params):
        if p in data:
            pts = sorted(data[p])
            ys  = [d[1] for d in pts]
            if not all(abs(v) < 0.01 for v in ys):
                ax.plot([d[0] for d in pts], ys,
                        color=_PC[i + 1], lw=0.7, zorder=3, label=p)
                continue
        ax.plot([], [], color=_PC[i + 1], lw=0.7, label=p)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center",
              bbox_to_anchor=(0.5, -0.08),
              ncol=1 + len(params), **_LK)


def _pdf_posiz(ax, data, params, pr):
    _pdf_setup_ax(ax, "POSIZIONE [mm]", "mm",
                  pr["posiz_y"], pr["posiz_yticks"],
                  pr["x_ticks"], pr["x_max"], draw_bg=False)
    for i, p in enumerate(params):
        if p in data:
            pts = sorted(data[p])
            if pts:
                ax.plot([d[0] for d in pts], [d[1] for d in pts],
                        color=_PC[i + 1], lw=0.7, zorder=3, label=p)
                continue
        ax.plot([], [], color=_PC[i + 1], lw=0.7, label=p)
    ax.axhline(0, color="#999", lw=0.4, linestyle="--", zorder=2)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center",
              bbox_to_anchor=(0.5, -0.08), ncol=len(params), **_LK)


def _pdf_forza(ax, data, params, pr):
    _pdf_setup_ax(ax, "FORZA [kN]", "kN",
                  pr["forza_y"], pr["forza_yticks"],
                  pr["x_ticks"], pr["x_max"], draw_bg=False)
    ref     = next((p for p in params if p in data), None)
    has_set = False
    if ref:
        pts = sorted(data[ref])
        xs  = np.array([d[0] for d in pts if d[3] is not None])
        sps = np.array([d[3] for d in pts if d[3] is not None])
        if len(xs):
            has_set = True
            ax.plot(xs, sps,                        color=_PC["set_forza"], lw=0.8, zorder=5, label="Set")
            ax.plot(xs, sps + pr["forza_delta"],    color=_PC["lmax"],      lw=1.0, zorder=5, label="LMax")
            ax.plot(xs, sps - pr["forza_delta"],    color=_PC["lmin"],      lw=1.0, zorder=5, label="LMin")
    if not has_set:
        ax.plot([], [], color=_PC["set_forza"], lw=0.8, label="Set")
    for i, p in enumerate(params):
        if p in data:
            pts = sorted(data[p])
            if pts:
                ax.plot([d[0] for d in pts], [d[1] for d in pts],
                        color=_PC[i + 1], lw=0.7, zorder=3, label=p)
                continue
        ax.plot([], [], color=_PC[i + 1], lw=0.7, label=p)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center",
              bbox_to_anchor=(0.5, -0.08),
              ncol=max(1, len(params)), **_LK)


# ── MIXIN ─────────────────────────────────────────────────────────────────────

class GraficiMixin:
    """Mixin con tutta la logica della tab 'Grafici' (PDF ciclo pressa)."""

    # ------------------------------------------------------------------
    # BUILD TAB
    # ------------------------------------------------------------------
    def _build_grafici_tab(self, parent):
        # ── stato interno ──────────────────────────────────────────────
        self._grafici_csv_path    = None
        self._grafici_rows        = []
        self._grafici_headers     = []
        self._grafici_data        = {}   # {parametro: [(sec, val, step, sp), …]}
        self._grafici_meta        = {}
        self._grafici_native_files = []  # file nativi selezionati (percorsi)
        self._grafici_logo_path   = None
        self._grafici_note_var    = tk.StringVar()
        self._grafici_pressa_var  = tk.StringVar(
            value=list(_PRESSALIST.keys())[0])
        pressas = list(_PRESSALIST.keys())
        stampi0 = _PRESSALIST[pressas[0]]
        self._grafici_stampo_var  = tk.StringVar(
            value=stampi0[0] if stampi0 else "")

        # ── toolbar ────────────────────────────────────────────────────
        tb = ctk.CTkFrame(parent, fg_color=COLORS["surface"],
                          corner_radius=8, height=46)
        tb.pack(fill="x", pady=(0, 6))
        tb.pack_propagate(False)

        # Pressa
        ctk.CTkLabel(tb, text="Pressa:", font=("Segoe UI", 10),
                     text_color=COLORS["text2"]
                     ).pack(side="left", padx=(12, 4), pady=10)
        self._grafici_pressa_menu = ctk.CTkOptionMenu(
            tb, variable=self._grafici_pressa_var,
            values=pressas,
            width=170, height=28,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"],
            command=self._grafici_on_pressa_change)
        self._grafici_pressa_menu.pack(side="left", padx=(0, 10), pady=10)

        # Stampo
        ctk.CTkLabel(tb, text="Stampo:", font=("Segoe UI", 10),
                     text_color=COLORS["text2"]
                     ).pack(side="left", padx=(0, 4))
        self._grafici_stampo_menu = ctk.CTkOptionMenu(
            tb, variable=self._grafici_stampo_var,
            values=stampi0 if stampi0 else ["-"],
            width=200, height=28,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"],
            command=lambda _: self._grafici_build_preview())
        self._grafici_stampo_menu.pack(side="left", padx=(0, 14))

        # Pulsanti destra
        for _txt, _cmd, _fg in [
            ("Genera PDF",   self._grafici_generate_pdf,  "#7c3aed"),
            ("Export PNG",   self._grafici_export_png,    COLORS["surface2"]),
            ("Apri Logo",    self._grafici_open_logo,     COLORS["surface2"]),
            ("Apri CSV",     self._grafici_open_csv,      COLORS["accent"]),
        ]:
            ctk.CTkButton(
                tb, text=_txt, width=100, height=28,
                fg_color=_fg, hover_color=COLORS["border"],
                text_color=COLORS["text"], font=("Segoe UI", 10),
                command=_cmd).pack(side="right", padx=4, pady=9)

        self._grafici_info_lbl = ctk.CTkLabel(
            tb, text="Nessun file caricato",
            font=("Segoe UI", 9), text_color=COLORS["text2"])
        self._grafici_info_lbl.pack(side="left", padx=8)

        # ── body: sinistra (note) + destra (anteprima) ─────────────────
        body = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        body.pack(fill="both", expand=True)

        # pannello note (piccolo, a sinistra)
        left = ctk.CTkFrame(body, fg_color=COLORS["surface"],
                            corner_radius=8, width=220)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="Note / Commento",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]
                     ).pack(anchor="w", padx=10, pady=(10, 2))
        self._grafici_note_box = ctk.CTkTextbox(
            left, height=120,
            fg_color=COLORS["surface2"], text_color=COLORS["text"],
            font=("Segoe UI", 10), corner_radius=6)
        self._grafici_note_box.pack(fill="x", padx=8, pady=(0, 6))

        ctk.CTkButton(
            left, text="Salva nota", width=100, height=26,
            fg_color=COLORS["accent"], hover_color="#5a52e0",
            text_color=COLORS["text"], font=("Segoe UI", 10),
            command=self._grafici_save_note
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # file nativi
        ctk.CTkLabel(left, text="File nativi (opz.)",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]
                     ).pack(anchor="w", padx=10, pady=(6, 2))
        ctk.CTkButton(
            left, text="Aggiungi file", width=120, height=26,
            fg_color=COLORS["surface2"], hover_color=COLORS["border"],
            text_color=COLORS["text"], font=("Segoe UI", 10),
            command=self._grafici_open_native
        ).pack(anchor="w", padx=10)
        self._grafici_native_lbl = ctk.CTkLabel(
            left, text="—", font=("Segoe UI", 9),
            text_color=COLORS["text2"], wraplength=190)
        self._grafici_native_lbl.pack(anchor="w", padx=10, pady=(4, 0))

        # anteprima grafico (destra)
        self._grafici_preview_frame = ctk.CTkFrame(
            body, fg_color=COLORS["surface"], corner_radius=8)
        self._grafici_preview_frame.pack(
            side="left", fill="both", expand=True)

        ctk.CTkLabel(
            self._grafici_preview_frame,
            text="Seleziona pressa / stampo e apri un CSV per l'anteprima.",
            font=("Segoe UI", 12), text_color=COLORS["text2"]
        ).pack(expand=True)

    # ------------------------------------------------------------------
    # CAMBIO PRESSA
    # ------------------------------------------------------------------
    def _grafici_on_pressa_change(self, _=None):
        pressa = self._grafici_pressa_var.get()
        stampi = _PRESSALIST.get(pressa, [])
        self._grafici_stampo_menu.configure(
            values=stampi if stampi else ["-"])
        if stampi:
            self._grafici_stampo_var.set(stampi[0])
        self._grafici_build_preview()

    # ------------------------------------------------------------------
    # APRI CSV
    # ------------------------------------------------------------------
    def _grafici_open_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv *.CSV"), ("All files", "*.*")])
        if not path:
            return
        try:
            self._grafici_csv_path = path
            self._grafici_data, self._grafici_meta = _pdf_parse_csv(path)

            # conta record per info label
            n_rows = len(next(iter(self._grafici_data.values()), []))
            self._grafici_info_lbl.configure(
                text=f"{os.path.basename(path)}  |  ~{n_rows} record",
                text_color=COLORS["text"])
            if hasattr(self, "set_status"):
                self.set_status(
                    f"Grafici: {os.path.basename(path)} (~{n_rows} record)")
            self._grafici_build_preview()
        except Exception as e:
            messagebox.showerror("Errore CSV Grafici", str(e))

    # ------------------------------------------------------------------
    # APRI FILE NATIVI
    # ------------------------------------------------------------------
    def _grafici_open_native(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("Tutti i file", "*.*")])
        if not paths:
            return
        self._grafici_native_files = list(paths)
        names = [os.path.basename(p) for p in paths]
        self._grafici_native_lbl.configure(
            text=", ".join(names[:4]) + ("…" if len(names) > 4 else ""))

    # ------------------------------------------------------------------
    # APRI LOGO
    # ------------------------------------------------------------------
    def _grafici_open_logo(self):
        path = filedialog.askopenfilename(
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.bmp"),
                       ("All files", "*.*")])
        if path:
            self._grafici_logo_path = path
            if hasattr(self, "set_status"):
                self.set_status(f"Logo: {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # SALVA NOTA
    # ------------------------------------------------------------------
    def _grafici_save_note(self):
        note = self._grafici_note_box.get("1.0", "end").strip()
        self._grafici_note_var.set(note)
        if hasattr(self, "set_status"):
            self.set_status("Nota salvata.")

    # ------------------------------------------------------------------
    # ANTEPRIMA
    # ------------------------------------------------------------------
    def _grafici_build_preview(self):
        """Costruisce la figura di anteprima nel frame dedicato."""
        # pulisce
        for w in self._grafici_preview_frame.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        if not self._grafici_csv_path or not self._grafici_data:
            ctk.CTkLabel(
                self._grafici_preview_frame,
                text="Nessun CSV caricato.",
                font=("Segoe UI", 12), text_color=COLORS["text2"]
            ).pack(expand=True)
            return

        try:
            fig = self._grafici_make_fig()
            canvas = FigureCanvasTkAgg(fig, master=self._grafici_preview_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            self._grafici_canvas = canvas
            self._grafici_fig    = fig
        except Exception as e:
            ctk.CTkLabel(
                self._grafici_preview_frame,
                text=f"Errore anteprima:\n{e}",
                font=("Segoe UI", 11),
                text_color=COLORS.get("error", "#ff4444")
            ).pack(expand=True)

    def _grafici_make_fig(self):
        """
        Costruisce la figura matplotlib per l'anteprima.
        Usa il profilo dello stampo selezionato se presente in _PRESSA_STAMPI,
        altrimenti un layout generico 2×2.
        """
        data = self._grafici_data
        meta = self._grafici_meta
        stampo_key = self._grafici_stampo_var.get()
        profile    = _PRESSA_STAMPI.get(stampo_key, {})

        palette = ["#6c63ff", "#00d4ff", "#52c41a", "#faad14",
                   "#f44322", "#e91e63", "#9c27b0", "#ff9800"]

        gruppi = profile.get("gruppi") if profile else None

        if not gruppi:
            # layout generico: raggruppa i parametri per prefisso
            gruppi = self._grafici_get_groups(list(data.keys()))

        n = len(gruppi)
        cols = min(n, 2)
        rows = (n + cols - 1) // cols

        fig, axes_arr = plt.subplots(
            rows, cols,
            figsize=(11, 3.5 * rows),
            facecolor="#1a1b2e",
            squeeze=False)
        fig.suptitle(
            f"{stampo_key}  —  ciclo {meta.get('idciclo', '')}",
            color="#c0c0e0", fontsize=10)

        axes_flat = [ax for row in axes_arr for ax in row]

        for idx, grp in enumerate(gruppi):
            ax    = axes_flat[idx]
            label = grp.get("label", f"Gruppo {idx + 1}")
            cols_ = grp.get("cols", [])
            ax.set_facecolor("#252535")
            ax.set_title(label, color="#c0c0e0", fontsize=8, pad=3)
            ax.tick_params(colors="#a0a0c0", labelsize=6)
            ax.grid(True, color="#3a3a5c", linewidth=0.3,
                    linestyle="--", alpha=0.5)
            for sp in ax.spines.values():
                sp.set_edgecolor("#3a3a5c")
            plotted = False
            for i, col in enumerate(cols_):
                color = _SERIES_COLORS.get(col, palette[i % len(palette)])
                if col in data:
                    pts = sorted(data[col])
                    ax.plot([p[0] for p in pts], [p[1] for p in pts],
                            color=color, linewidth=0.9, label=col)
                    plotted = True
            if plotted:
                ax.legend(fontsize=6, loc="upper left",
                          facecolor="#252535", labelcolor="#c0c0e0",
                          edgecolor="#3a3a5c")

        # nascondi assi vuoti
        for idx in range(len(gruppi), len(axes_flat)):
            axes_flat[idx].set_visible(False)

        fig.tight_layout(pad=1.0)
        return fig

    @staticmethod
    def _grafici_get_groups(param_names: list) -> list:
        """
        Raggruppa automaticamente i parametri per prefisso (TS, TI, T, F, P, Z, V…).
        Restituisce lista di dict {label, cols}.
        """
        groups: dict[str, list] = {}
        order = []
        for p in param_names:
            prefix = "".join(c for c in p if c.isalpha()).upper()
            # tronca a 2 char per raggruppare TS1..TS8, TI1..TI8 ecc.
            key = prefix[:2] if len(prefix) >= 2 else prefix
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(p)
        return [{"label": k, "cols": groups[k]} for k in order]

    # ------------------------------------------------------------------
    # GENERA PDF
    # ------------------------------------------------------------------
    def _grafici_generate_pdf(self):
        if not self._grafici_csv_path:
            messagebox.showwarning("Attenzione", "Nessun CSV caricato.")
            return

        ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
        base    = os.path.splitext(os.path.basename(self._grafici_csv_path))[0]
        out_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"{base}_{ts}.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not out_path:
            return

        if hasattr(self, "set_status"):
            self.set_status("Generazione PDF in corso…")

        stampo_key  = self._grafici_stampo_var.get()
        note        = self._grafici_note_var.get()
        logo_path   = self._grafici_logo_path
        native_files = list(self._grafici_native_files)
        csv_path    = self._grafici_csv_path
        data        = self._grafici_data
        meta        = self._grafici_meta

        def _run():
            try:
                self._grafici_do_generate_pdf(
                    csv_path, data, meta, stampo_key,
                    out_path, note, logo_path, native_files)
                self.after(0, lambda: self.set_status(
                    f"PDF salvato: {os.path.basename(out_path)}") if hasattr(self, "set_status") else None)
                self.after(0, lambda: messagebox.showinfo(
                    "Completato", f"PDF salvato:\n{out_path}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore PDF", str(e)))
                self.after(0, lambda: self.set_status("Errore PDF") if hasattr(self, "set_status") else None)

        threading.Thread(target=_run, daemon=True).start()

    def _grafici_do_generate_pdf(self, csv_path, data, meta, stampo_key,
                                  out_path, note, logo_path, native_files):
        """
        Genera il PDF vero e proprio con matplotlib / PdfPages.
        Può essere esteso con profili specifici per stampo.
        """
        profile = _PRESSA_STAMPI.get(stampo_key, {})
        gruppi  = profile.get("gruppi") if profile else None
        if not gruppi:
            gruppi = self._grafici_get_groups(list(data.keys()))

        palette = ["#6c63ff", "#00d4ff", "#52c41a", "#faad14",
                   "#f44322", "#e91e63", "#9c27b0", "#ff9800"]

        with PdfPages(out_path) as pdf:
            # ── pagina di copertina ────────────────────────────────────
            fig_cov, ax_cov = plt.subplots(figsize=(11.69, 8.27),
                                           facecolor="white")
            ax_cov.axis("off")

            # logo (opzionale)
            if logo_path and os.path.isfile(logo_path):
                try:
                    from matplotlib.image import imread as _imread
                    logo_img = _imread(logo_path)
                    ax_logo = fig_cov.add_axes([0.02, 0.82, 0.18, 0.14])
                    ax_logo.imshow(logo_img)
                    ax_logo.axis("off")
                except Exception:
                    pass

            title_lines = [
                f"REPORT CICLO  —  {stampo_key}",
                f"ID Ciclo:   {meta.get('idciclo', '—')}",
                f"Partite:    {meta.get('partite', '—')}",
                f"Operatore:  {meta.get('operatore', '—')}",
                f"Materiale:  {meta.get('materiale', '—')}",
                f"Inizio:     {_pdf_fmt_ts(meta.get('tsstart'))}",
                f"Fine:       {_pdf_fmt_ts(meta.get('tsend'))}",
                f"Durata:     {meta.get('dursec', 0)} s",
            ]
            if note:
                title_lines.append(f"\nNote:\n{note}")

            ax_cov.text(0.5, 0.55, "\n".join(title_lines),
                        ha="center", va="center",
                        fontsize=12, family="monospace",
                        color="#111", transform=ax_cov.transAxes)
            pdf.savefig(fig_cov, bbox_inches="tight")
            plt.close(fig_cov)

            # ── pagine grafici ─────────────────────────────────────────
            PER_PAGE = 4
            for page_start in range(0, len(gruppi), PER_PAGE):
                chunk = gruppi[page_start: page_start + PER_PAGE]
                n = len(chunk)
                cols_n = min(n, 2)
                rows_n = (n + cols_n - 1) // cols_n

                fig, axes_arr = plt.subplots(
                    rows_n, cols_n,
                    figsize=(11.69, 8.27),
                    facecolor="white",
                    squeeze=False)
                axes_flat = [ax for row in axes_arr for ax in row]

                for idx, grp in enumerate(chunk):
                    ax     = axes_flat[idx]
                    label  = grp.get("label", "")
                    cols_  = grp.get("cols", [])
                    setval = grp.get("set", None)
                    delta  = grp.get("delta", None)

                    # usa _pdf_temp/_pdf_forza se il profilo lo indica
                    kind = grp.get("kind", "generic")
                    if kind == "temp" and setval is not None:
                        pr_fake = {
                            "temp_y": grp.get("y", [0, 250]),
                            "temp_yticks": grp.get("yticks", list(range(0, 251, 25))),
                            "x_ticks": list(range(0, int(meta.get("dursec", 600)) + 1,
                                                   max(1, int(meta.get("dursec", 600)) // 10))),
                            "x_max": meta.get("dursec", 600),
                        }
                        _pdf_temp(ax, data, cols_, setval, label, pr_fake)
                    elif kind == "forza" and delta is not None:
                        pr_fake = {
                            "forza_y": grp.get("y", [0, 6000]),
                            "forza_yticks": grp.get("yticks", list(range(0, 6001, 500))),
                            "x_ticks": list(range(0, int(meta.get("dursec", 600)) + 1,
                                                   max(1, int(meta.get("dursec", 600)) // 10))),
                            "x_max": meta.get("dursec", 600),
                            "forza_delta": delta,
                        }
                        _pdf_forza(ax, data, cols_, pr_fake)
                    else:
                        # layout generico scuro → adattato a sfondo bianco PDF
                        ax.set_facecolor("#f9f9f9")
                        ax.set_title(label, fontsize=9, fontweight="bold",
                                     pad=4, color="#111")
                        ax.tick_params(labelsize=7)
                        ax.grid(True, linestyle="--", linewidth=0.3,
                                color="#cccccc", alpha=0.8)
                        for sp in ax.spines.values():
                            sp.set_edgecolor("#888")
                            sp.set_linewidth(0.5)
                        ax.set_xlabel("sec", fontsize=7)
                        for i, col in enumerate(cols_):
                            color = _SERIES_COLORS.get(col, palette[i % len(palette)])
                            if col in data:
                                pts = sorted(data[col])
                                ax.plot([p[0] for p in pts], [p[1] for p in pts],
                                        color=color, lw=0.8, label=col)
                        h, l = ax.get_legend_handles_labels()
                        if h:
                            ax.legend(h, l, loc="upper center",
                                      bbox_to_anchor=(0.5, -0.08),
                                      ncol=max(1, len(h)), **_LK)

                for idx in range(len(chunk), len(axes_flat)):
                    axes_flat[idx].set_visible(False)

                fig.tight_layout(pad=1.2)
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)

            # ── metadati PDF ───────────────────────────────────────────
            d = pdf.infodict()
            d["Title"]   = f"Report ciclo {meta.get('idciclo', '')}"
            d["Subject"] = stampo_key
            d["Creator"] = "MouldGraph"

    # ------------------------------------------------------------------
    # EXPORT PNG
    # ------------------------------------------------------------------
    def _grafici_export_png(self):
        if not getattr(self, "_grafici_fig", None):
            messagebox.showwarning("Attenzione",
                                   "Genera prima un'anteprima aprendo un CSV.")
            return
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.splitext(
            os.path.basename(self._grafici_csv_path or "grafici"))[0]
        out = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"{base}_{ts}.png",
            filetypes=[("PNG", "*.png")])
        if not out:
            return
        try:
            self._grafici_fig.savefig(out, dpi=150, bbox_inches="tight",
                                      facecolor=self._grafici_fig.get_facecolor())
            if hasattr(self, "set_status"):
                self.set_status(f"PNG salvato: {os.path.basename(out)}")
            messagebox.showinfo("Completato", f"PNG salvato:\n{out}")
        except Exception as e:
            messagebox.showerror("Errore PNG", str(e))
