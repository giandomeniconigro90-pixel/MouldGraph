# -*- coding: utf-8 -*-
"""
tab_grafici.py  —  GraficiMixin
Contiene _build_grafici_tab e tutti i metodi _grafici_* estratti da app_main.py.
Importato come mixin da LogAnalyzerApp in app_main.py.
"""
import os
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as _np

import customtkinter as ctk

from colors import COLORS
from pdf_export import (
    generate_lamborghini_pdf,
    _autodetect_profile,
    _validate_csv,
    PROFILES,
    PRESSASTAMPI,
)

# ── costanti locali (rimangono qui, non duplicate in app_main) ────────────────
try:
    from pdf_export import _pdf_parse_csv, _parse_native_pack, _merge_native_data, _filter_partite
except ImportError:
    _pdf_parse_csv = _parse_native_pack = _merge_native_data = _filter_partite = None

_NOTES_FILE = "notes.json"

# Alias comodi per non riscrivere PRESSASTAMPI/PROFILES ovunque
_PRESSA_STAMPI = PRESSASTAMPI
_PROFILES      = PROFILES

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
    "VS1": "#407da5", "VS2": "#e5672c", "V1":  "#407da5", "V2":  "#e5672c",
    "VI1": "#407da5", "VI2": "#e5672c", "VI3": "#828282", "VI4": "#e7b73b",
    "V3":  "#828282", "V4":  "#e7b73b",
}


class GraficiMixin:
    """Mixin con tutta la logica della tab 'Grafici' (PDF Lamborghini/Persico/Cannon)."""

    # ------------------------------------------------------------------
    # BUILD TAB
    # ------------------------------------------------------------------
    def _build_grafici_tab(self, parent):
        self._grafici_csv_path       = None
        self._grafici_logo_path      = None
        self._grafici_native_paths   = {}
        self._grafici_merged_data    = None
        self._grafici_merged_meta    = None
        self._grafici_data           = None
        self._grafici_meta           = None
        self._grafici_note_box       = None
        self._grafici_param_vars     = {}
        self._grafici_canvases       = {}
        self._grafici_preview_job    = None
        self._grafici_groups         = []

        # -- Top toolbar --
        top = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        top.pack(fill="x", side="top", padx=6, pady=4)

        row1 = ctk.CTkFrame(top, fg_color=COLORS["surface"], corner_radius=8)
        row1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(row1, text="Pressa", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text2"]).pack(side="left", padx=14, pady=10)
        self._grafici_pressa_var = ctk.StringVar(value=list(_PRESSA_STAMPI.keys())[0])

        def _on_pressa_change(val):
            stampi = _PRESSA_STAMPI.get(val, [])
            self._grafici_stampo_var.set(stampi[0] if stampi else "")
            self._grafici_stampo_menu.configure(values=stampi if stampi else [""])

        ctk.CTkOptionMenu(row1, variable=self._grafici_pressa_var,
                          values=list(_PRESSA_STAMPI.keys()), width=160,
                          fg_color=COLORS["surface2"], button_color=COLORS["accent"],
                          text_color=COLORS["text"],
                          command=_on_pressa_change).pack(side="left", padx=8, pady=10)
        ctk.CTkLabel(row1, text="Stampo", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text2"]).pack(side="left", padx=(12, 0), pady=10)
        self._grafici_stampo_var = ctk.StringVar(
            value=_PRESSA_STAMPI[list(_PRESSA_STAMPI.keys())[0]][0])
        self._grafici_stampo_menu = ctk.CTkOptionMenu(
            row1, variable=self._grafici_stampo_var,
            values=_PRESSA_STAMPI[list(_PRESSA_STAMPI.keys())[0]], width=180,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"], state="disabled")
        self._grafici_stampo_menu.pack(side="left", padx=8, pady=10)

        row2 = ctk.CTkFrame(top, fg_color=COLORS["surface"], corner_radius=8)
        row2.pack(fill="x", pady=(0, 4))
        ctk.CTkButton(row2, text="Apri CSV", width=100, height=28,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"],
                      command=self._grafici_open_csv).pack(side="left", padx=10, pady=8)
        self._grafici_csv_lbl = ctk.CTkLabel(row2, text="Nessun file selezionato",
                                              font=("Segoe UI", 11), text_color=COLORS["text2"])
        self._grafici_csv_lbl.pack(side="left", padx=8)
        self._grafici_native_btn = ctk.CTkButton(
            row2, text="+ File nativi", width=110, height=28,
            fg_color=COLORS["surface2"], hover_color=COLORS["border"],
            text_color=COLORS["text"], state="disabled",
            command=self._grafici_open_native)
        self._grafici_native_btn.pack(side="left", padx=4, pady=8)
        self._grafici_native_lbl = ctk.CTkLabel(row2, text="",
                                                 font=("Segoe UI", 10), text_color=COLORS["text2"])
        self._grafici_native_lbl.pack(side="left", padx=4)
        ctk.CTkButton(row2, text="Logo (opzionale)", width=130, height=28,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text"],
                      command=self._grafici_open_logo).pack(side="right", padx=10, pady=8)
        self._grafici_logo_lbl = ctk.CTkLabel(row2, text="auto",
                                               font=("Segoe UI", 10), text_color=COLORS["text2"])
        self._grafici_logo_lbl.pack(side="right", padx=4)

        row3 = ctk.CTkFrame(top, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 2))
        self._grafici_gen_btn = ctk.CTkButton(
            row3, text="Genera PDF", width=140, height=34,
            fg_color=COLORS["accent"], hover_color="#5a52e0",
            font=("Segoe UI", 12, "bold"), text_color=COLORS["text"],
            state="disabled", command=self._grafici_generate)
        self._grafici_gen_btn.pack(side="left", padx=2)
        self._grafici_status = ctk.CTkLabel(row3, text="", font=("Segoe UI", 11),
                                             text_color=COLORS["text2"])
        self._grafici_status.pack(side="left", padx=12)

        # -- Main split: filter (left) + chart preview (right) --
        self._grafici_main = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        self._grafici_filter_scroll = ctk.CTkScrollableFrame(
            self._grafici_main, fg_color=COLORS["surface"], width=260, corner_radius=0)
        self._grafici_filter_scroll.pack(side="left", fill="y", padx=(0, 4))
        self._grafici_chart_scroll = ctk.CTkScrollableFrame(
            self._grafici_main, fg_color=COLORS["bg"])
        self._grafici_chart_scroll.pack(side="left", fill="both", expand=True)

        # Note box persistente — creato UNA VOLTA, mai distrutto/ricreato
        self._grafici_params_container = ctk.CTkFrame(
            self._grafici_filter_scroll, fg_color="transparent")
        self._grafici_params_container.pack(fill="x")
        ctk.CTkLabel(self._grafici_filter_scroll, text="NOTE OPERATIVE",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=8, pady=(16, 2))
        self._grafici_note_frame = ctk.CTkFrame(
            self._grafici_filter_scroll, fg_color=COLORS["surface2"], corner_radius=6)
        self._grafici_note_frame.pack(fill="x", padx=4, pady=(0, 8))
        self._grafici_note_box = ctk.CTkTextbox(
            self._grafici_note_frame, height=80, font=("Segoe UI", 10),
            fg_color=COLORS["surface2"], text_color=COLORS["text"],
            border_width=0, wrap="word")
        self._grafici_note_box.pack(fill="x", padx=4, pady=4)
        self._grafici_note_box.bind("<KeyRelease>", lambda e: self._grafici_save_note())

    # ------------------------------------------------------------------
    # GROUPS
    # ------------------------------------------------------------------
    def _grafici_get_groups(self, data_keys):
        all_keys = set(data_keys)
        groups = []

        def _safe_int(s):
            try: return int(s)
            except Exception: return -1

        ts = sorted([k for k in all_keys if
                     (k.startswith("TS") and k[2:].isdigit()) or
                     (k.startswith("T") and not k.startswith("TI") and
                      k[1:].isdigit() and 1 <= _safe_int(k[1:]) <= 4)])
        if ts: groups.append(("temp_sup", "Temperatura Superiore", "[T]", ts))

        ti = sorted([k for k in all_keys if k.startswith("TI") and k[2:].isdigit()])
        if not ti:
            ti = sorted([k for k in all_keys if k.startswith("T") and
                         k[1:].isdigit() and 4 < _safe_int(k[1:]) <= 8])
        if ti: groups.append(("temp_inf", "Temperatura Inferiore", "[T]", ti))

        pos = sorted([k for k in all_keys if
                      (k.startswith("P") and k[1:].isdigit()) or
                      (k.startswith("Z") and k[1:].isdigit())])
        if pos: groups.append(("posiz", "Posizione Piano", "[P]", pos))

        f_sensors  = [k for k in all_keys if k in ("F1", "F2", "F3", "F4")]
        f_combined = [k for k in all_keys if k in ("FC", "SPC", "Forza")]
        if f_sensors:
            groups.append(("forza_sensori", "Forza Sensori", "*", sorted(f_sensors)))
            if f_combined:
                groups.append(("forza", "Forza", "*", sorted(f_combined)))
        else:
            force = sorted(f_combined)
            if force: groups.append(("forza", "Forza", "*", force))

        vs = sorted([k for k in all_keys if k in ("VS1", "VS2", "V1", "V2")])
        if vs: groups.append(("vuoto_sup", "Vuoto Superiore", "[V]", vs))

        vi = sorted([k for k in all_keys if k in ("VI1", "VI2", "VI3", "VI4", "V3", "V4")])
        if vi: groups.append(("vuoto_inf", "Vuoto Inferiore", "[V]", vi))

        return groups

    # ------------------------------------------------------------------
    # PREVIEW
    # ------------------------------------------------------------------
    def _grafici_build_preview(self, data, meta):
        if not self._grafici_main.winfo_ismapped():
            self._grafici_main.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self._grafici_groups = self._grafici_get_groups(list(data.keys()))

        # Distrugge solo i checkbox — il note box è persistente
        for w in self._grafici_params_container.winfo_children():
            w.destroy()
        self._grafici_param_vars = {}

        ctk.CTkLabel(self._grafici_params_container, text="FILTRO PARAMETRI",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=8, pady=(8, 4))

        for key, title, emoji, params in self._grafici_groups:
            hdr = ctk.CTkFrame(self._grafici_params_container,
                               fg_color=COLORS["surface2"], corner_radius=6)
            hdr.pack(fill="x", padx=4, pady=(8, 2))
            ctk.CTkLabel(hdr, text=f"{emoji}  {title}",
                         font=("Segoe UI", 10, "bold"),
                         text_color=COLORS["text"]).pack(side="left", padx=8, pady=6)
            for param in params:
                color = _SERIES_COLORS.get(param, "#6c63ff")
                row = ctk.CTkFrame(self._grafici_params_container, fg_color="transparent")
                row.pack(fill="x", padx=6, pady=2)
                ctk.CTkFrame(row, width=11, height=11, fg_color=color,
                             corner_radius=2).pack(side="left", padx=(6, 5))
                var = tk.BooleanVar(value=True)
                self._grafici_param_vars[param] = var
                ctk.CTkCheckBox(row, text=param, variable=var,
                                fg_color=color, hover_color=color,
                                checkmark_color="#fff",
                                font=("Segoe UI", 10, "bold"),
                                text_color=COLORS["text"],
                                command=self._grafici_schedule_update
                                ).pack(side="left")

        # Chart canvases
        for w in self._grafici_chart_scroll.winfo_children():
            w.destroy()
        self._grafici_canvases = {}

        for key, title, emoji, params in self._grafici_groups:
            frame = ctk.CTkFrame(self._grafici_chart_scroll,
                                 fg_color=COLORS["surface"], corner_radius=8)
            frame.pack(fill="x", pady=4, padx=2)
            title_bar = ctk.CTkFrame(frame, fg_color=COLORS["surface2"], corner_radius=0)
            title_bar.pack(fill="x")
            ctk.CTkLabel(title_bar, text=f"{emoji}  {title}",
                         font=("Segoe UI", 11, "bold"),
                         text_color=COLORS["text"]).pack(side="left", padx=12, pady=7)
            _k = key
            ctk.CTkButton(title_bar, text="[ ]", width=36, height=24,
                          fg_color="transparent", hover_color=COLORS["border"],
                          text_color=COLORS["text2"], font=("Segoe UI", 10),
                          command=lambda k=_k: self._grafici_open_fullscreen(k)
                          ).pack(side="right", padx=6)
            fig = plt.Figure(figsize=(10, 2.2), facecolor="#22263a", dpi=80)
            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.get_tk_widget().configure(bg="#22263a", highlightthickness=0)
            canvas.get_tk_widget().pack(fill="x", padx=2, pady=2)
            self._grafici_canvases[key] = (fig, canvas, params)

        self._grafici_update_preview()

    def _grafici_schedule_update(self):
        if self._grafici_preview_job:
            self.after_cancel(self._grafici_preview_job)
        self._grafici_preview_job = self.after(120, self._grafici_update_preview)

    def _grafici_update_preview(self):
        if not self._grafici_data:
            return
        selected = {p for p, v in self._grafici_param_vars.items() if v.get()}
        _preview_data = self._grafici_merged_data or self._grafici_data

        for key, (fig, canvas, params) in self._grafici_canvases.items():
            fig.clear()
            ax = fig.add_subplot(111)
            ax.set_facecolor("#22263a")
            fig.patch.set_facecolor("#22263a")
            has_data = False
            for param in params:
                if param not in selected:
                    continue
                pts = _preview_data.get(param, [])
                if not pts:
                    continue
                ys = [p[1] for p in pts]
                if all(abs(v) < 0.001 for v in ys):
                    continue
                xs = [p[0] for p in pts]
                ax.plot(xs, ys, color=_SERIES_COLORS.get(param, "#6c63ff"),
                        lw=1.0, label=param)
                has_data = True
            if not has_data:
                ax.text(0.5, 0.5, "Nessun parametro selezionato",
                        transform=ax.transAxes, ha="center", va="center",
                        color=COLORS["text2"], fontsize=9)
            ax.tick_params(colors="#8892b0", labelsize=7, length=2)
            for sp in ax.spines.values():
                sp.set_color("#2e3350")
                sp.set_linewidth(0.5)
            ax.grid(True, color="#2e3350", lw=0.5, linestyle="--")
            ax.set_xlabel("Sec", color="#8892b0", fontsize=7, labelpad=2)
            if has_data:
                ax.legend(loc="upper right", fontsize=7, framealpha=0.8,
                          facecolor="#1a1d27", edgecolor="#2e3350",
                          labelcolor="#e8eaf6", handlelength=1.5)
            fig.subplots_adjust(left=0.05, right=0.98, top=0.90, bottom=0.22)
            canvas.draw()

    # ------------------------------------------------------------------
    # FULLSCREEN
    # ------------------------------------------------------------------
    def _grafici_open_fullscreen(self, key):
        """Apre il grafico in fullscreen con zoom, pan e hover interattivi (blit)."""
        if key not in self._grafici_canvases:
            return
        _, _, params = self._grafici_canvases[key]
        selected = {p for p, v in self._grafici_param_vars.items() if v.get()}
        data = self._grafici_merged_data or self._grafici_data
        if not data:
            return

        win = tk.Toplevel(self)
        win.title(key)
        win.configure(bg="#22263a")
        win.state("zoomed")

        # Barra modalità hover
        mode_bar = tk.Frame(win, bg="#1a1d27", height=36)
        mode_bar.pack(side="top", fill="x")
        mode_bar.pack_propagate(False)
        tk.Label(mode_bar, text="Hover:", bg="#1a1d27", fg="#8892b0",
                 font=("Segoe UI", 10)).pack(side="left", padx=(12, 6))
        _hover_mode = tk.StringVar(value="Nessuno")
        _MODE_COLORS = {"active_bg": "#6c63ff", "active_fg": "#ffffff",
                        "idle_bg":   "#22263a", "idle_fg":   "#8892b0"}
        _mode_btns = {}

        def _set_mode(m):
            _hover_mode.set(m)
            for _m, _b in _mode_btns.items():
                if _m == m:
                    _b.configure(bg=_MODE_COLORS["active_bg"], fg=_MODE_COLORS["active_fg"])
                else:
                    _b.configure(bg=_MODE_COLORS["idle_bg"],   fg=_MODE_COLORS["idle_fg"])
            _clear_overlay()

        for lbl in ["Nessuno", "Tooltip", "Crosshair", "Snap", "Completo"]:
            _l = lbl
            b = tk.Button(mode_bar, text=lbl,
                          bg=_MODE_COLORS["idle_bg"], fg=_MODE_COLORS["idle_fg"],
                          relief="flat", font=("Segoe UI", 10), padx=10, pady=4,
                          activebackground="#5a52e0", activeforeground="#fff",
                          command=lambda m=_l: _set_mode(m))
            b.pack(side="left", padx=3, pady=4)
            _mode_btns[lbl] = b
        _mode_btns["Nessuno"].configure(bg=_MODE_COLORS["active_bg"],
                                         fg=_MODE_COLORS["active_fg"])

        # Figura e assi
        fig = plt.Figure(figsize=(16, 6), facecolor="#22263a")
        ax  = fig.add_subplot(111)
        ax.set_facecolor("#22263a")
        for sp in ax.spines.values():
            sp.set_color("#2e3350")
            sp.set_linewidth(0.6)
        ax.tick_params(colors="#8892b0", labelsize=9, length=3)
        ax.grid(True, color="#2e3350", lw=0.5, linestyle="--")
        ax.set_xlabel("Sec", color="#8892b0", fontsize=9, labelpad=4)

        _series = {}
        has_data = False
        for param in params:
            if param not in selected:
                continue
            pts = data.get(param, [])
            if not pts:
                continue
            ys = [p[1] for p in pts]
            if all(abs(v) < 0.001 for v in ys):
                continue
            xs    = [p[0] for p in pts]
            color = _SERIES_COLORS.get(param, "#6c63ff")
            ax.plot(xs, ys, color=color, lw=1.2, label=param)
            _series[param] = (_np.array(xs), _np.array(ys), color)
            has_data = True

        if has_data:
            ax.legend(loc="upper right", fontsize=9, framealpha=0.8,
                      facecolor="#1a1d27", edgecolor="#2e3350",
                      labelcolor="#e8eaf6", handlelength=2)
        fig.subplots_adjust(left=0.06, right=0.98, top=0.93, bottom=0.10)

        # Canvas e toolbar
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().configure(bg="#22263a", highlightthickness=0)
        toolbar_frame = tk.Frame(win, bg="#2a2d3e")
        toolbar_frame.pack(side="bottom", fill="x")
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.config(background="#2a2d3e")

        def _style_toolbar(widget):
            try:
                cls = widget.winfo_class()
                if cls in ("Button", "Label"):
                    widget.config(bg="#2a2d3e", fg="#e8eaf6",
                                  activebackground="#4a4f72", activeforeground="#ffffff",
                                  relief="flat", borderwidth=0)
                elif cls in ("Frame", "Checkbutton"):
                    widget.config(bg="#2a2d3e")
            except Exception:
                pass
            for child in widget.winfo_children():
                _style_toolbar(child)

        toolbar.update()
        _style_toolbar(toolbar)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        canvas.draw()

        # Background statico per blit
        _bg = [None]
        def _save_bg():
            _bg[0] = canvas.copy_from_bbox(fig.bbox)
        win.after(100, _save_bg)

        # Artisti overlay
        _vline,     = ax.plot([], [], color="#ffffff", lw=0.7, linestyle="--", alpha=0.5, animated=True)
        _hline,     = ax.plot([], [], color="#ffffff", lw=0.7, linestyle="--", alpha=0.5, animated=True)
        _snap_dot,  = ax.plot([], [], "o", ms=7, color="#ffffff", zorder=10, animated=True)
        _tooltip    = ax.annotate("", xy=(0, 0), xytext=(15, 15),
                                   textcoords="offset points",
                                   bbox=dict(boxstyle="round,pad=0.4", fc="#1a1d27",
                                             ec="#6c63ff", lw=1.2, alpha=0.92),
                                   fontsize=8.5, color="#e8eaf6", animated=True,
                                   annotation_clip=False)
        _tooltip.set_visible(False)

        def _place_tooltip(bx, by):
            xl = ax.get_xlim(); yl = ax.get_ylim()
            xfrac = (bx - xl[0]) / (xl[1] - xl[0]) if xl[1] != xl[0] else 0.5
            yfrac = (by - yl[0]) / (yl[1] - yl[0]) if yl[1] != yl[0] else 0.5
            ox = -120 if xfrac > 0.75 else 15
            oy = -60  if yfrac > 0.70 else 15
            _tooltip.xyann = (ox, oy)

        _info_box = ax.text(0.01, 0.98, "", transform=ax.transAxes,
                            va="top", ha="left", fontsize=8.5, color="#e8eaf6",
                            bbox=dict(boxstyle="round,pad=0.5", fc="#1a1d27",
                                      ec="#2e3350", lw=1.0, alpha=0.90),
                            animated=True)
        _info_box.set_visible(False)

        def _clear_overlay():
            _vline.set_data([], [])
            _hline.set_data([], [])
            _snap_dot.set_data([], [])
            _tooltip.set_visible(False)
            _info_box.set_visible(False)
            if _bg[0] is not None:
                canvas.restore_region(_bg[0])
                canvas.blit(fig.bbox)

        def _interp_y(xs_arr, ys_arr, x):
            if len(xs_arr) == 0:
                return None
            idx = _np.searchsorted(xs_arr, x)
            if idx == 0:
                return float(ys_arr[0])
            if idx >= len(xs_arr):
                return float(ys_arr[-1])
            x0, x1 = xs_arr[idx - 1], xs_arr[idx]
            y0, y1 = ys_arr[idx - 1], ys_arr[idx]
            if x1 == x0:
                return float(y0)
            return float(y0 + (y1 - y0) * (x - x0) / (x1 - x0))

        def _nearest_point(xs_arr, ys_arr, x, y, ax_obj):
            if len(xs_arr) == 0:
                return None, None, None
            disp = ax_obj.transData.transform(_np.column_stack([xs_arr, ys_arr]))
            cx, cy = ax_obj.transData.transform([[x, y]])[0]
            dists  = _np.hypot(disp[:, 0] - cx, disp[:, 1] - cy)
            idx    = int(_np.argmin(dists))
            return float(xs_arr[idx]), float(ys_arr[idx]), float(dists[idx])

        def _on_motion(event):
            if event.inaxes != ax or _bg[0] is None:
                return
            mode = _hover_mode.get()
            if mode == "Nessuno":
                return
            x, y = event.xdata, event.ydata
            if x is None or y is None:
                return
            canvas.restore_region(_bg[0])
            xl = ax.get_xlim()
            yl = ax.get_ylim()

            if mode == "Tooltip":
                best_param, best_x, best_y, best_dist = None, None, None, float("inf")
                for param, (xs_arr, ys_arr, color) in _series.items():
                    nx, ny, dist = _nearest_point(xs_arr, ys_arr, x, y, ax)
                    if nx is not None and dist < best_dist:
                        best_dist = dist; best_param = param
                        best_x = nx;     best_y = ny
                if best_param is not None and best_dist < 40:
                    _tooltip.xy = (best_x, best_y)
                    _place_tooltip(best_x, best_y)
                    _tooltip.set_text(f"{best_param}\nX: {best_x:.1f} s\nY: {best_y:.4g}")
                    _tooltip.set_visible(True)
                else:
                    _tooltip.set_visible(False)
                ax.draw_artist(_tooltip)

            elif mode == "Crosshair":
                _vline.set_data([x, x], [yl[0], yl[1]])
                _hline.set_data([xl[0], xl[1]], [y, y])
                lines = [f"X: {x:.1f} s"]
                for param, (xs_arr, ys_arr, _c) in _series.items():
                    iv = _interp_y(xs_arr, ys_arr, x)
                    if iv is not None:
                        lines.append(f"{param}: {iv:.4g}")
                _info_box.set_text("\n".join(lines))
                _info_box.set_visible(True)
                ax.draw_artist(_vline)
                ax.draw_artist(_hline)
                ax.draw_artist(_info_box)

            elif mode == "Snap":
                best_param, best_x, best_y, best_dist = None, None, None, float("inf")
                best_color = "#ffffff"
                for param, (xs_arr, ys_arr, color) in _series.items():
                    nx, ny, dist = _nearest_point(xs_arr, ys_arr, x, y, ax)
                    if nx is not None and dist < best_dist:
                        best_dist = dist; best_param = param
                        best_x = nx;     best_y = ny; best_color = color
                if best_param is not None and best_dist < 50:
                    _snap_dot.set_data([best_x], [best_y])
                    _snap_dot.set_color(best_color)
                    _tooltip.xy = (best_x, best_y)
                    _place_tooltip(best_x, best_y)
                    _tooltip.set_text(f"{best_param}\nX: {best_x:.1f} s\nY: {best_y:.4g}")
                    _tooltip.set_visible(True)
                else:
                    _snap_dot.set_data([], [])
                    _tooltip.set_visible(False)
                ax.draw_artist(_snap_dot)
                ax.draw_artist(_tooltip)

            elif mode == "Completo":
                _vline.set_data([x, x], [yl[0], yl[1]])
                _hline.set_data([xl[0], xl[1]], [y, y])
                best_param, best_x, best_y, best_dist = None, None, None, float("inf")
                best_color = "#ffffff"
                for param, (xs_arr, ys_arr, color) in _series.items():
                    nx, ny, dist = _nearest_point(xs_arr, ys_arr, x, y, ax)
                    if nx is not None and dist < best_dist:
                        best_dist = dist; best_param = param
                        best_x = nx;     best_y = ny; best_color = color
                if best_param is not None and best_dist < 50:
                    _snap_dot.set_data([best_x], [best_y])
                    _snap_dot.set_color(best_color)
                else:
                    _snap_dot.set_data([], [])
                lines = [f"X: {x:.1f} s"]
                for param, (xs_arr, ys_arr, _c) in _series.items():
                    iv     = _interp_y(xs_arr, ys_arr, x)
                    marker = " ◀" if param == best_param else ""
                    if iv is not None:
                        lines.append(f"{param}: {iv:.4g}{marker}")
                _info_box.set_text("\n".join(lines))
                _info_box.set_visible(True)
                ax.draw_artist(_vline)
                ax.draw_artist(_hline)
                ax.draw_artist(_snap_dot)
                ax.draw_artist(_info_box)

            canvas.blit(ax.bbox)

        def _on_leave(event):
            _clear_overlay()

        canvas.mpl_connect("motion_notify_event", _on_motion)
        canvas.mpl_connect("axes_leave_event",    _on_leave)

        # Limiti originali
        _orig_xlim = list(ax.get_xlim())
        _orig_ylim = list(ax.get_ylim())
        _zoomed    = [False]

        def _on_scroll(event):
            if event.inaxes is None:
                return
            if event.button == "down" and not _zoomed[0]:
                return
            factor = 0.85 if event.button == "up" else 1.0 / 0.85
            xl = list(ax.get_xlim())
            yl = list(ax.get_ylim())
            cx = event.xdata
            cy = event.ydata
            new_xl = [cx + (x - cx) * factor for x in xl]
            new_yl = [cy + (y - cy) * factor for y in yl]
            if event.button == "down":
                new_xl[0] = max(new_xl[0], _orig_xlim[0])
                new_xl[1] = min(new_xl[1], _orig_xlim[1])
                new_yl[0] = max(new_yl[0], _orig_ylim[0])
                new_yl[1] = min(new_yl[1], _orig_ylim[1])
                if (abs(new_xl[0] - _orig_xlim[0]) < 1e-6 and
                        abs(new_xl[1] - _orig_xlim[1]) < 1e-6 and
                        abs(new_yl[0] - _orig_ylim[0]) < 1e-6 and
                        abs(new_yl[1] - _orig_ylim[1]) < 1e-6):
                    _zoomed[0] = False
            else:
                _zoomed[0] = True
                new_xl[0] = max(new_xl[0], _orig_xlim[0])
                new_xl[1] = min(new_xl[1], _orig_xlim[1])
                new_yl[0] = max(new_yl[0], _orig_ylim[0])
                new_yl[1] = min(new_yl[1], _orig_ylim[1])
            if new_xl[1] > new_xl[0] and new_yl[1] > new_yl[0]:
                ax.set_xlim(new_xl)
                ax.set_ylim(new_yl)
                canvas.draw()
                _save_bg()

        _clamping = [False]

        def _on_xlim_change(ax_changed):
            if _clamping[0]: return
            xl = list(ax_changed.get_xlim())
            if xl[0] < _orig_xlim[0]:
                _clamping[0] = True
                ax_changed.set_xlim(_orig_xlim[0], xl[1] + (_orig_xlim[0] - xl[0]))
                _clamping[0] = False

        def _on_ylim_change(ax_changed):
            if _clamping[0]: return
            yl = list(ax_changed.get_ylim())
            if yl[0] < _orig_ylim[0]:
                _clamping[0] = True
                ax_changed.set_ylim(_orig_ylim[0], yl[1] + (_orig_ylim[0] - yl[0]))
                _clamping[0] = False

        ax.callbacks.connect("xlim_changed", _on_xlim_change)
        ax.callbacks.connect("ylim_changed", _on_ylim_change)
        canvas.mpl_connect("scroll_event",  _on_scroll)
        canvas.mpl_connect("resize_event",  lambda e: (canvas.draw(), _save_bg()))

    # ------------------------------------------------------------------
    # NOTE
    # ------------------------------------------------------------------
    def _grafici_save_note(self):
        idciclo = (self._grafici_meta or {}).get("idciclo", "")
        if not idciclo:
            return
        note_text = (
            self._grafici_note_box.get("1.0", "end").strip()
            if self._grafici_note_box else ""
        )
        try:
            notes = {}
            if os.path.exists(_NOTES_FILE):
                with open(_NOTES_FILE, encoding="utf-8") as f:
                    notes = json.load(f)
            if note_text:
                notes[idciclo] = note_text
            elif idciclo in notes:
                del notes[idciclo]
            with open(_NOTES_FILE, "w", encoding="utf-8") as f:
                json.dump(notes, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _grafici_load_note(self, idciclo):
        note_text = ""
        try:
            if os.path.exists(_NOTES_FILE):
                with open(_NOTES_FILE, encoding="utf-8") as f:
                    notes = json.load(f)
                note_text = notes.get(str(idciclo), "")
        except Exception:
            pass
        if self._grafici_note_box is not None:
            self._grafici_note_box.delete("1.0", "end")
            if note_text:
                self._grafici_note_box.insert("1.0", note_text)

    # ------------------------------------------------------------------
    # FILE OPEN
    # ------------------------------------------------------------------
    def _grafici_open_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        ok, err = _validate_csv(path)
        if not ok:
            messagebox.showerror("File non valido", err)
            self._grafici_status.configure(
                text=f"X {err}", text_color=COLORS["error"])
            return
        # Reset file nativi
        self._grafici_native_paths = {}
        self._grafici_native_lbl.configure(text="", text_color=COLORS["text2"])
        self._grafici_csv_path = path
        self._grafici_csv_lbl.configure(
            text=os.path.basename(path), text_color=COLORS["text"])

        detected, lati_dict, partite = _autodetect_profile(path)
        if detected:
            self._grafici_stampo_var.set(detected)
            self._grafici_stampo_menu.configure(state="disabled")
            pressa_rilevata = _PROFILES.get(detected, {}).get("pressa", "Cannon 5000T")
            self._grafici_pressa_var.set(pressa_rilevata)
            self._grafici_stampo_menu.configure(
                values=_PRESSA_STAMPI.get(pressa_rilevata, [detected]))
            if "Cannon" in pressa_rilevata:
                self._grafici_native_btn.configure(state="disabled")
            else:
                self._grafici_native_btn.configure(state="normal")
            parti = []
            for prof, lati in lati_dict.items():
                lati_str = f" ({'/'.join(sorted(lati))})" if lati else ""
                parti.append(f"{prof}{lati_str}")
            partite_str = ", ".join(partite[:6]) + ("..." if len(partite) > 6 else "")
            self._grafici_status.configure(
                text=f"OK Rilevato: {' + '.join(parti)} | Partite: {partite_str}",
                text_color=COLORS["info"])
        else:
            self._grafici_stampo_menu.configure(state="normal")
            msg = (
                f"/!\ Codici non riconosciuti: {', '.join(partite[:4])} - seleziona manualmente."
                if partite
                else "i Campo Partita non trovato - seleziona il profilo manualmente."
            )
            self._grafici_status.configure(text=msg, text_color=COLORS["warn"])

        try:
            data, meta = _pdf_parse_csv(path)
            self._grafici_data = data
            self._grafici_meta = meta
            if self._grafici_native_paths:
                try:
                    nd, mp = _parse_native_pack(
                        self._grafici_native_paths, self._grafici_stampo_var.get())
                    md, mm = _merge_native_data(data, meta, nd, mp)
                except Exception:
                    md, mm = data, meta
            else:
                md, mm = data, meta
            self._grafici_merged_data = md
            self._grafici_merged_meta = mm
            self._grafici_build_preview(md, mm)
            self._grafici_gen_btn.configure(state="normal")
            idciclo = (self._grafici_meta or {}).get("idciclo", "")
            self._grafici_load_note(idciclo)
        except Exception as e:
            self._grafici_status.configure(
                text=f"X Errore lettura: {e}", text_color=COLORS["error"])

    def _grafici_open_native(self):
        _TYPES = {
            "FORZA": "FORZA", "POSIZIONE": "POSIZIONE",
            "TEMPS_SUP": "TEMPS_SUP", "TEMPS_INF": "TEMPS_INF",
            "VUOTO_SUP": "VUOTO_SUP", "VUOTO_INF": "VUOTO_INF",
            "DATI_GENERALI": "DATI_GENERALI",
        }
        paths = filedialog.askopenfilenames(
            title="Seleziona file nativi Persico",
            filetypes=[("CSV files", "*.csv *.CSV"), ("All files", "*.*")])
        if not paths:
            return
        if not hasattr(self, "_grafici_native_paths") or not self._grafici_native_paths:
            self._grafici_native_paths = {}
        ignored = []
        for p in paths:
            base    = os.path.basename(p).upper()
            matched = next((k for k in _TYPES if base.startswith(k)), None)
            if matched:
                self._grafici_native_paths[matched] = p
            else:
                ignored.append(os.path.basename(p))
        n = len(self._grafici_native_paths)
        if n == 0:
            self._grafici_native_lbl.configure(
                text="Nessun file riconosciuto", text_color=COLORS["warn"])
            return
        tipi = list(self._grafici_native_paths.keys())
        lbl  = f"{n}/7 nativi: {', '.join(tipi)}"
        if ignored:
            lbl += f"  |  ignorati: {', '.join(ignored)}"
        self._grafici_native_lbl.configure(text=lbl, text_color=COLORS["info"])
        if self._grafici_data is not None:
            try:
                nd, mp = _parse_native_pack(
                    self._grafici_native_paths, self._grafici_stampo_var.get())
                md, mm = _merge_native_data(
                    self._grafici_data, self._grafici_meta, nd, mp)
                self._grafici_merged_data = md
                self._grafici_merged_meta = mm
                self._grafici_build_preview(md, mm)
            except Exception as e:
                self._grafici_native_lbl.configure(
                    text=f"Errore nativi: {e}", text_color=COLORS["error"])

    def _grafici_open_logo(self):
        path = filedialog.askopenfilename(
            filetypes=[("Immagini", "*.png *.jpg *.jpeg"), ("All files", "*.*")])
        if not path:
            return
        self._grafici_logo_path = path
        self._grafici_logo_lbl.configure(
            text=os.path.basename(path), text_color=COLORS["text"])

    # ------------------------------------------------------------------
    # GENERA PDF
    # ------------------------------------------------------------------
    def _grafici_generate(self):
        if not self._grafici_csv_path:
            messagebox.showwarning("Attenzione", "Seleziona prima un file CSV.")
            return
        selected = (
            {p for p, v in self._grafici_param_vars.items() if v.get()}
            if self._grafici_param_vars else None
        )
        if selected is not None and not selected:
            messagebox.showwarning("Attenzione", "Seleziona almeno un parametro.")
            return
        stampo = self._grafici_stampo_var.get()
        _base  = (
            os.path.splitext(os.path.basename(self._grafici_csv_path))[0]
            if self._grafici_csv_path
            else f"Grafico-{stampo.replace(' ', '_')}"
        )
        out = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"{_base}.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        self._grafici_gen_btn.configure(state="disabled", text="Generazione...")
        self._grafici_status.configure(
            text="Generazione in corso...", text_color=COLORS["warn"])
        logo = self._grafici_logo_path
        md   = self._grafici_merged_data or self._grafici_data
        mm   = dict(self._grafici_merged_meta or self._grafici_meta)
        note_text = (
            self._grafici_note_box.get("1.0", "end").strip()
            if hasattr(self, "_grafici_note_box") else ""
        )
        if note_text:
            mm["note"] = note_text
        if mm.get("partite"):
            mm["partite"] = _filter_partite(mm["partite"], stampo)

        def _run():
            try:
                generate_lamborghini_pdf(
                    self._grafici_csv_path, stampo, out,
                    logo_path=logo, filter_params=selected,
                    preloaded_data=md, preloaded_meta=mm)
                self.after(0, lambda: self._grafici_done(out))
            except Exception as e:
                self.after(0, lambda: self._grafici_error(str(e)))

        threading.Thread(target=_run, daemon=True).start()

    def _grafici_done(self, path):
        self._grafici_gen_btn.configure(state="normal", text="Genera PDF")
        self._grafici_status.configure(
            text=f"OK PDF salvato: {os.path.basename(path)}",
            text_color=COLORS["info"])
        self.set_status(f"PDF generato: {os.path.basename(path)}")
        try:
            import subprocess, sys
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    def _grafici_error(self, msg):
        self._grafici_gen_btn.configure(state="normal", text="Genera PDF")
        self._grafici_status.configure(
            text=f"Errore: {msg}", text_color=COLORS["error"])
        messagebox.showerror("Errore generazione PDF", msg)
