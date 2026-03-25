# -*- coding: utf-8 -*-
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

class InteractivePlotCanvas:
    """Wrapper matplotlib con hover crosshair, zoom rotella, pan drag."""

    def __init__(self, master, height=320):
        self.master = master
        self.height = height
        self._rows = []
        self._xs_raw = []
        self._xs_num_cache = None  # B1: cache _to_num(_xs_raw), invalidata su cambio dati
        self._series = {}
        self._x_type = "index"
        self._col_meta = {}
        self._y2_cols = set()
        self._colors = {}
        self._x_label = ""
        self._xlim_orig = None
        self._ylim_orig = None
        self._y2lim_orig = None
        self._pan_start = None
        self._pan_xlim = None
        self._hover_cid = None
        self._cross_v = None
        self._tooltip = None
        self._dot_artists = []
        self._hidden = set()
        self._lines = {}
        self._overlay_lines   = {}   # col → Line2D per serie ②
        self._overlay_all_vis = True  # stato toggle globale ②
        self._zoom_stack = []          # stack (xmin, xmax) per undo zoom
        self._cur_a = None             # x-value cursore A
        self._cur_b = None             # x-value cursore B
        self._ab_artists = []          # tutti gli artist A/B da rimuovere
        self.show_markers = True       # mostra/nasconde pallini sui punti
        self._ranges      = []         # [{col, lo, hi}] bande colorate sul grafico
        self._drawing     = False      # True durante canvas.draw() — blocca blit stantio
        self._frame = ctk.CTkFrame(master, fg_color=COLORS["surface"], corner_radius=8)
        self._frame.pack(fill="both", expand=True, padx=0, pady=0)
        # ── info bar (hover) ────────────────────────────────────────────────
        self._info_var = tk.StringVar(value="")
        self._info_lbl = ctk.CTkLabel(
            self._frame, textvariable=self._info_var,
            font=("Courier New", 10), text_color=COLORS["accent2"],
            fg_color=COLORS["surface2"], corner_radius=4, anchor="w")
        self._info_lbl.pack(fill="x", padx=6, pady=(4, 0))
        self._info_lbl.configure(fg_color="transparent")
        # ── canvas matplotlib ───────────────────────────────────────────
        self._plot_area = ctk.CTkFrame(self._frame, fg_color="transparent")
        self._plot_area.pack(fill="both", expand=True)
        # ── barra toggle serie (sotto il grafico) ───────────────────────
        self._legend_panel = ctk.CTkScrollableFrame(
            self._frame, fg_color=COLORS["surface2"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"],
            orientation="horizontal", height=40, corner_radius=4)
        self._legend_panel.pack(fill="x", padx=4, pady=(2, 4))
        self._legend_rows = []
        # ── figura matplotlib ───────────────────────────────────────────────
        self._fig, self._ax1 = plt.subplots(
            figsize=(10, height / 96), facecolor=COLORS["surface"])
        self._ax2 = None
        self._ax1.set_facecolor(COLORS["surface2"])
        for sp in self._ax1.spines.values():
            sp.set_edgecolor(COLORS["border"])
        self._ax1.tick_params(colors=COLORS["text2"])
        self._fig.patch.set_facecolor(COLORS["surface"])
        self._canvas = FigureCanvasTkAgg(self._fig, master=self._plot_area)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        self._canvas.draw()   # disegna subito con sfondo scuro
        self._resize_job = None   # debounce resize
        self._canvas.mpl_connect("resize_event", self._on_resize)
        self._canvas.mpl_connect("scroll_event",        self._on_scroll)
        self._canvas.mpl_connect("button_press_event",  self._on_press)
        self._canvas.mpl_connect("button_release_event",self._on_release)
        self._canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._canvas.get_tk_widget().bind("<Leave>", lambda e: self._clear_hover())

    def _on_resize(self, event):
        """Debounce: ridisegna solo 300ms dopo l'ultimo evento resize."""
        if self._resize_job is not None:
            try: self._frame.after_cancel(self._resize_job)
            except Exception: pass
        self._resize_job = self._frame.after(300, self._on_resize_done)

    def _on_resize_done(self):
        self._resize_job = None
        if self._xs_raw and self._series:
            self._fig.tight_layout(pad=1.2)
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            self._cross_v = None
            self._tooltip = None

    def set_data(self, xs_raw, series, x_type, col_meta,
                 y2_cols=None, colors=None, x_label=""):
        self._xs_raw        = xs_raw
        self._xs_num_cache  = None  # B1: invalida cache
        self._series   = series
        self._x_type   = x_type
        self._col_meta = col_meta
        self._y2_cols  = set(y2_cols or [])
        self._x_label  = x_label
        palette = list(_UC_SERIES_PALETTE)
        self._colors = {}
        for i, col in enumerate(series):
            self._colors[col] = (colors or {}).get(col, palette[i % len(palette)])
        self._xlim_orig = None
        self._ylim_orig = None
        self._y2lim_orig = None
        self._hidden = set()
        self._zoom_stack = []
        self._cur_a = None
        self._cur_b = None
        self._ab_artists = []
        self._redraw()
        self._rebuild_legend_sidebar()

    def _overlay_second_csv(self, rows2, x_col, cols, colors2, col_meta):
        """Sovrappone le serie del secondo CSV sull'asse corrente con linee tratteggiate."""
        if not self._ax1 or not rows2:
            return
        xs2, series2, x_type2 = _uc_build_series(rows2, x_col, cols, col_meta)
        xs_num2 = self._to_num(xs2) if x_type2 == "datetime" else \
                  [float(x) if x is not None else None for x in xs2]
        for col in cols:
            ys = series2.get(col, [])
            xf, yf = self._clean(xs_num2, ys)
            if not xf:
                continue
            color = colors2.get(col, "#aaaaaa")
            lbl = f"{col} ②"
            line, = self._ax1.plot(xf, yf, color=color, linewidth=1.2,
                                   linestyle="--", label=lbl, zorder=2, alpha=0.85)
            self._overlay_lines[col] = line  # salva riferimento per toggle
        self._xs_num_cache = None  # B1x
        self._fig.tight_layout(pad=1.2)
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        self._rebuild_legend_sidebar()  # mostra bottoni ② nel pannello

    def update_live(self, xs_raw, series, x_type, col_meta, colors=None,
                    background=False):
        """Redraw incrementale per Live Data."""
        needs_full = (getattr(self, "_needs_full_redraw", False)
                      or set(series.keys()) != set(self._lines.keys())
                      or not self._lines)
        if needs_full:
            self._needs_full_redraw = False
            self.set_data(xs_raw, series, x_type, col_meta, colors=colors)
            return

        # Fix B: salta il draw se i dati non sono cambiati
        # confronta lunghezza e ultimo valore di ogni serie come fingerprint veloce
        new_fp = (len(xs_raw),
                  tuple((k, len(v), v[-1] if v else None)
                        for k, v in series.items()))
        if new_fp == getattr(self, "_live_data_fp", None):
            return
        self._live_data_fp = new_fp

        self._xs_raw        = xs_raw
        self._xs_num_cache  = None  # B1: invalida cache
        self._series   = series
        self._x_type   = x_type
        self._col_meta = col_meta

        # aggiorna mappa colori se fornita
        if colors:
            for col, c in colors.items():
                if col in self._colors and self._colors[col] != c:
                    self._colors[col] = c
                    if col in self._lines:
                        self._lines[col].set_color(c)

        # ── pulisce artisti animati
        if self._cross_v is not None:
            try:
                self._cross_v.set_xdata([])
                self._cross_v.set_ydata([])
            except Exception:
                pass
            self._cross_v = None
        for dot in self._dot_artists:
            try:
                dot.set_xdata([])
                dot.set_ydata([])
            except Exception:
                pass
        self._dot_artists = []
        if self._tooltip is not None:
            try:
                self._tooltip.set_visible(False)
            except Exception:
                pass
            self._tooltip = None

        xs_num = self._to_num(xs_raw)
        ax1 = self._ax1

        for col, line in self._lines.items():
            ys = series.get(col, [])
            xf, yf = self._clean(xs_num, ys)
            if xf:
                line.set_xdata(xf)
                line.set_ydata(yf)

        # se ci sono serie nascoste ricalcola i limiti solo sulle visibili
        if self._hidden:
            self._rescale_visible()
        else:
            ax1.relim()
            ax1.autoscale_view()
            if self._ax2:
                self._ax2.relim()
                self._ax2.autoscale_view()

        if x_type == "datetime":
            self._fmt_xaxis_datetime(ax1, xs_num)

        self._drawing = True
        try:
            if background:
                self._canvas.draw_idle()
            else:
                self._canvas.draw()
                self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        finally:
            self._drawing = False

    def set_ranges(self, ranges):
        """Imposta le bande di range [{col, lo, hi}] e ridisegna."""
        self._ranges = ranges or []
        self._redraw()
        self._rebuild_legend_sidebar()

    def clear(self):
        self._xs_raw = []
        self._xs_num_cache = None  # B1: invalida cache
        self._series = {}
        self._redraw()

    def get_frame(self):
        return self._frame

    def _redraw(self):
        self._overlay_lines = {}  # reset: _redraw cancella tutto il canvas
        self._fig.clf()
        self._ax1 = self._fig.add_subplot(111)
        self._ax2 = None
        self._cross_v = None
        self._tooltip = None
        self._dot_artists = []
        ax1 = self._ax1
        self._fig.patch.set_facecolor(COLORS["surface"])
        ax1.set_facecolor(COLORS["surface2"])
        for sp in ax1.spines.values():
            sp.set_edgecolor(COLORS["border"])
        ax1.tick_params(colors=COLORS["text2"], labelsize=8)
        ax1.xaxis.label.set_color(COLORS["text2"])
        ax1.yaxis.label.set_color(COLORS["text2"])
        ax1.grid(True, color=COLORS["border"], linewidth=0.4, linestyle="--", alpha=0.6)
        if not self._xs_raw or not self._series:
            ax1.text(0.5, 0.5, "Nessun dato da visualizzare",
                     ha="center", va="center", color=COLORS["text2"],
                     fontsize=11, transform=ax1.transAxes)
            self._drawing = True
            try:
                self._canvas.draw()
                self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)  # aggiorna sempre
            finally:
                self._drawing = False
            return
        xs_num = self._to_num(self._xs_raw)
        y1_cols = [c for c in self._series if c not in self._y2_cols]
        y2_cols = [c for c in self._series if c in self._y2_cols]
        if y2_cols:
            self._ax2 = ax1.twinx()
            ax2 = self._ax2
            ax2.set_facecolor("none")
            for sp in ax2.spines.values():
                sp.set_edgecolor(COLORS["border"])
            ax2.tick_params(colors=COLORS["text2"], labelsize=8)
        self._lines = {}
        # marker adattivo: più punti → marker più piccoli
        def _marker_size(n):
            if n <= 20:   return 6
            if n <= 50:   return 4
            if n <= 200:  return 3
            return 2
        _mk = "o" if self.show_markers else "none"

        for col in y1_cols:
            ys = self._series[col]
            xf, yf = self._clean(xs_num, ys)
            if xf:
                lbl  = self._col_meta.get(col, {}).get("label", col)
                unit = self._col_meta.get(col, {}).get("unit", "")
                full_lbl = f"{lbl} [{unit}]" if unit else lbl
                ms = _marker_size(len(xf))
                line, = ax1.plot(xf, yf, color=self._colors[col],
                                 linewidth=1.4, label=full_lbl,
                                 marker=_mk, markersize=ms,
                                 markerfacecolor=self._colors[col],
                                 markeredgewidth=0, zorder=3)
                self._lines[col] = line
        if self._ax2:
            for col in y2_cols:
                ys = self._series[col]
                xf, yf = self._clean(xs_num, ys)
                if xf:
                    lbl  = self._col_meta.get(col, {}).get("label", col)
                    unit = self._col_meta.get(col, {}).get("unit", "")
                    full_lbl = f"{lbl} [{unit}]" if unit else lbl
                    ms = _marker_size(len(xf))
                    line, = self._ax2.plot(xf, yf, color=self._colors[col],
                                           linewidth=1.4, label=full_lbl,
                                           linestyle="--",
                                           marker=_mk, markersize=ms,
                                           markerfacecolor=self._colors[col],
                                           markeredgewidth=0, zorder=3)
                    self._lines[col] = line
        if self._x_type == "datetime":
            self._fmt_xaxis_datetime(ax1, xs_num)
        else:
            ax1.set_xlabel(self._x_label or "Indice", color=COLORS["text2"], fontsize=8)
        # applica visibilità toggle
        for _c, _l in self._lines.items():
            _l.set_visible(_c not in self._hidden)

        # ── bande colorate per range personalizzati ───────────────────────
        for rule in self._ranges:
            col = rule.get("col")
            lo  = rule.get("lo")
            hi  = rule.get("hi")
            if col in self._hidden:
                continue
            color = self._colors.get(col, COLORS["accent"])
            ax = self._ax2 if (self._ax2 and col in self._y2_cols) else ax1
            # banda tra lo e hi
            if lo is not None and hi is not None:
                ax.axhspan(lo, hi, color=color, alpha=0.12, zorder=1)
            elif lo is not None:
                ax.axhline(lo, color=color, linewidth=1.0,
                           linestyle=":", alpha=0.7, zorder=2)
            elif hi is not None:
                ax.axhline(hi, color=color, linewidth=1.0,
                           linestyle=":", alpha=0.7, zorder=2)
        # legenda esterna: niente legend() dentro il grafico
        if self._xlim_orig:
            ax1.set_xlim(self._xlim_orig)
            if self._ax2:
                self._ax2.set_xlim(self._xlim_orig)
        else:
            self._xlim_orig = ax1.get_xlim()
        self._fig.tight_layout(pad=1.2)
        self._drawing = True
        try:
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        finally:
            self._drawing = False
        self._cross_v = None
        self._tooltip = None

    def _to_num(self, xs):
        if not xs:
            return []
        if self._x_type == "datetime":
            result = []
            for x in xs:
                if isinstance(x, datetime):
                    result.append(mdates.date2num(x))
                else:
                    result.append(None)
            return result
        return [float(x) if x is not None else None for x in xs]

    def _clean(self, xs, ys):
        pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
        if not pairs:
            return [], []
        return [p[0] for p in pairs], [p[1] for p in pairs]

    def _fmt_xaxis_datetime(self, ax, xs_num):
        valid = [x for x in xs_num if x is not None]
        if not valid:
            return
        span_days = (max(valid) - min(valid))
        if span_days < 1 / 24:
            fmt = mdates.DateFormatter("%H:%M:%S")
        elif span_days < 1:
            fmt = mdates.DateFormatter("%H:%M")
        elif span_days < 7:
            fmt = mdates.DateFormatter("%d/%m %H:%M")
        else:
            fmt = mdates.DateFormatter("%d/%m/%Y")
        ax.xaxis.set_major_formatter(fmt)
        plt.setp(ax.get_xticklabels(), rotation=30, fontsize=7, color=COLORS["text2"])

    def _clear_hover(self):
        self._info_var.set("")
        try: self._info_lbl.configure(fg_color="transparent")
        except Exception: pass
        if self._cross_v is not None:
            try: self._cross_v.remove()
            except Exception: pass
            self._cross_v = None
        for a in self._dot_artists:
            try: a.remove()
            except Exception: pass
        self._dot_artists = []
        if self._tooltip is not None:
            try: self._tooltip.remove()
            except Exception: pass
            self._tooltip = None
        try:
            self._canvas.restore_region(self._bg_cache)
            self._canvas.blit(self._fig.bbox)
        except Exception: pass

    def _on_motion(self, event):
        if getattr(self, "_drawing", False):
            return
        if event.inaxes not in (self._ax1, self._ax2):
            self._clear_hover()
            return
        if not self._xs_raw or not self._series:
            # nessun CSV1 ma ci sono linee ② — usa overlay come ancora X
            _ov2 = getattr(self, "_overlay_lines", {})
            if not _ov2:
                self._clear_hover()
                return
            _fl = next(iter(_ov2.values()))
            _lx0 = _fl.get_xdata()
            if not len(_lx0) or event.xdata is None:
                return
            _xm0  = event.xdata
            _idx0 = int(np.nanargmin(np.abs(np.array([float(x) for x in _lx0]) - _xm0)))
            _xs0  = float(_lx0[_idx0])
            _xstr = f"{_xs0:.4g}"
            _tip  = [f"X: {_xstr}"]; _prt = [f"X: {_xstr}"]
            for _c2, _ln2 in _ov2.items():
                if not _ln2.get_visible(): continue
                _ly2 = _ln2.get_ydata()
                if _idx0 < len(_ly2) and _ly2[_idx0] is not None:
                    _tip.append(f"{_c2}③: {float(_ly2[_idx0]):.4g}")
                    _prt.append(f"{_c2}③: {float(_ly2[_idx0]):.4g}")
            self._info_var.set("   ".join(_prt))
            try: self._canvas.restore_region(self._bg_cache)
            except Exception:
                self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
                self._canvas.restore_region(self._bg_cache)
            _ylim0 = self._ax1.get_ylim(); _xlim0 = self._ax1.get_xlim()
            if self._cross_v is None:
                self._cross_v, = self._ax1.plot([_xs0,_xs0], _ylim0,
                    color=COLORS["accent2"], linewidth=0.8, linestyle="--",
                    zorder=10, animated=True)
            else:
                self._cross_v.set_xdata([_xs0, _xs0])
                self._cross_v.set_ydata(_ylim0)
            self._ax1.draw_artist(self._cross_v)
            # dot sulle ② lines
            for _a in self._dot_artists:
                try: _a.remove()
                except Exception: pass
            self._dot_artists = []
            for _c2, _ln2 in _ov2.items():
                if not _ln2.get_visible(): continue
                _ly2 = _ln2.get_ydata()
                if _idx0 < len(_ly2) and _ly2[_idx0] is not None:
                    _d2, = self._ax1.plot(_xs0, float(_ly2[_idx0]), "D",
                        color=_ln2.get_color(), markersize=5, zorder=11,
                        animated=True, markeredgecolor="#fff", markeredgewidth=0.5)
                    self._dot_artists.append(_d2)
                    self._ax1.draw_artist(_d2)
            # tooltip
            _xf0 = ((_xs0-_xlim0[0])/(_xlim0[1]-_xlim0[0])) if _xlim0[1]!=_xlim0[0] else 0.5
            _ha0 = "left" if _xf0 < 0.75 else "right"
            _xoff = _xs0 + (_xlim0[1]-_xlim0[0])*0.015 if _ha0=="left" else _xs0 - (_xlim0[1]-_xlim0[0])*0.015
            _ytip = _ylim0[0] + (_ylim0[1]-_ylim0[0])*0.97
            if self._tooltip is None:
                self._tooltip = self._ax1.text(_xoff, _ytip, "\n".join(_tip),
                    fontsize=7.5, color=COLORS["text"],
                    bbox=dict(boxstyle="round,pad=0.4", fc=COLORS["surface"],
                              ec=COLORS["accent2"], lw=1.0, alpha=0.92),
                    ha=_ha0, va="top", zorder=12, animated=True)
            else:
                self._tooltip.set_position((_xoff, _ytip))
                self._tooltip.set_text("\n".join(_tip))
                self._tooltip.set_ha(_ha0)
                self._tooltip.set_visible(True)
            self._ax1.draw_artist(self._tooltip)
            self._canvas.blit(self._fig.bbox)
            return
        if self._pan_start is not None:
            self._do_pan(event)
            return
        ax1 = self._ax1
        # B1: usa cache — ricalcola solo se invalidata da cambio dati
        if self._xs_num_cache is None:
            self._xs_num_cache = self._to_num(self._xs_raw)
        xs_num = self._xs_num_cache
        xm = event.xdata
        if xm is None:
            return
        # B2: ricerca numpy vettorizzata — 10-50x più veloce del min() Python
        valid_mask = [x is not None for x in xs_num]
        if not any(valid_mask):
            return
        xs_arr = np.array([x if x is not None else np.nan for x in xs_num])
        idx = int(np.nanargmin(np.abs(xs_arr - xm)))
        x_snap = xs_num[idx]
        if x_snap is None:
            return
        if self._x_type == "datetime" and isinstance(self._xs_raw[idx], datetime):
            x_str = self._xs_raw[idx].strftime("%d/%m/%Y %H:%M:%S")
        else:
            x_str = f"{self._xs_raw[idx]:.4g}" if isinstance(self._xs_raw[idx], float) else f"{self._xs_raw[idx]}"

        # ── info bar in cima ─────────────────────────────────────────────
        parts = [f"X: {x_str}"]
        for col, ys in self._series.items():
            if col in self._hidden:
                continue
            if idx < len(ys) and ys[idx] is not None:
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                parts.append(f"{lbl}: {ys[idx]:.4g}{(' ' + unit) if unit else ''}")
        # ── valori ② nell'info bar ───────────────────────────────
        for _c2, _ln2 in getattr(self, "_overlay_lines", {}).items():
            if not _ln2.get_visible(): continue
            _lx2 = _ln2.get_xdata(); _ly2 = _ln2.get_ydata()
            if not len(_lx2): continue
            _li2 = int(np.nanargmin(np.abs(np.array([float(x) for x in _lx2]) - x_snap)))
            if _li2 < len(_ly2) and _ly2[_li2] is not None:
                parts.append(f"{_c2}③: {float(_ly2[_li2]):.4g}")
        try: self._info_lbl.configure(fg_color=COLORS["surface2"])
        except Exception: pass
        self._info_var.set("   ".join(parts))

        try:
            self._canvas.restore_region(self._bg_cache)
        except Exception:
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            self._canvas.restore_region(self._bg_cache)

        ylim = ax1.get_ylim()
        xlim = ax1.get_xlim()

        # ── crosshair verticale ──────────────────────────────────────────
        if self._cross_v is None:
            self._cross_v, = ax1.plot(
                [x_snap, x_snap], ylim,
                color=COLORS["accent2"], linewidth=0.8,
                linestyle="--", zorder=10, animated=True)
        else:
            self._cross_v.set_xdata([x_snap, x_snap])
            self._cross_v.set_ydata(ylim)
        ax1.draw_artist(self._cross_v)

        # ── dot sui punti di snap — usa ys[idx] (stesso punto del tooltip) ──────
        for artist in self._dot_artists:
            try: artist.remove()
            except Exception: pass
        self._dot_artists = []
        for col in self._lines:
            if col in self._hidden: continue
            ys = self._series.get(col, [])
            if idx >= len(ys) or ys[idx] is None: continue
            ax = self._ax2 if (self._ax2 and col in self._y2_cols) else ax1
            dot, = ax.plot(x_snap, float(ys[idx]), "o",
                color=self._colors.get(col, "#fff"), markersize=6, zorder=11, animated=True)
            self._dot_artists.append(dot)
            ax.draw_artist(dot)
        # ── dot sulle linee ② ────────────────────────────────────────────
        for _c2, _ln2 in getattr(self, "_overlay_lines", {}).items():
            if not _ln2.get_visible(): continue
            _lx2 = _ln2.get_xdata(); _ly2 = _ln2.get_ydata()
            if not len(_lx2): continue
            _li2 = int(np.nanargmin(np.abs(np.array([float(x) for x in _lx2]) - x_snap)))
            if _li2 < len(_ly2) and _ly2[_li2] is not None:
                _d2, = ax1.plot(float(_lx2[_li2]), float(_ly2[_li2]), "D",
                    color=_ln2.get_color(), markersize=5, zorder=11, animated=True,
                    markeredgecolor="#fff", markeredgewidth=0.5)
                self._dot_artists.append(_d2)
                ax1.draw_artist(_d2)

        # ── tooltip flottante vicino al cursore ──────────────────────────
        tip_lines = [f"X: {x_str}"]
        for col, ys in self._series.items():
            if col in self._hidden:
                continue
            if idx < len(ys) and ys[idx] is not None:
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                tip_lines.append(f"{lbl}: {ys[idx]:.4g}{(' ' + unit) if unit else ''}")
        # ── valori ② nel tooltip ──────────────────────────────────
        for _c2, _ln2 in getattr(self, "_overlay_lines", {}).items():
            if not _ln2.get_visible(): continue
            _lx2 = _ln2.get_xdata(); _ly2 = _ln2.get_ydata()
            if not len(_lx2): continue
            _li2 = int(np.nanargmin(np.abs(np.array([float(x) for x in _lx2]) - x_snap)))
            if _li2 < len(_ly2) and _ly2[_li2] is not None:
                tip_lines.append(f"{_c2}③: {float(_ly2[_li2]):.4g}")
        tip_txt = "\n".join(tip_lines)

        # posiziona il tooltip a destra del cursore, o a sinistra se vicino al bordo
        x_frac = (x_snap - xlim[0]) / (xlim[1] - xlim[0]) if xlim[1] != xlim[0] else 0.5
        ha = "left" if x_frac < 0.75 else "right"
        x_off = x_snap + (xlim[1] - xlim[0]) * 0.015 if ha == "left" else x_snap - (xlim[1] - xlim[0]) * 0.015
        y_tip = ylim[0] + (ylim[1] - ylim[0]) * 0.97

        if self._tooltip is None:
            self._tooltip = ax1.text(
                x_off, y_tip, tip_txt,
                fontsize=7.5, color=COLORS["text"],
                bbox=dict(boxstyle="round,pad=0.4",
                          fc=COLORS["surface"], ec=COLORS["accent2"],
                          lw=1.0, alpha=0.92),
                ha=ha, va="top", zorder=12, animated=True)
        else:
            self._tooltip.set_position((x_off, y_tip))
            self._tooltip.set_text(tip_txt)
            self._tooltip.set_ha(ha)
            self._tooltip.set_visible(True)
        ax1.draw_artist(self._tooltip)

        self._canvas.blit(self._fig.bbox)

    def _on_scroll(self, event):
        if event.inaxes != self._ax1:
            return
        ax = self._ax1
        xmin, xmax = ax.get_xlim()
        if event.button == "up":
            # zoom-in: push stato corrente (limite a 50 livelli)
            if len(self._zoom_stack) < 50:
                self._zoom_stack.append((xmin, xmax))
                self._live_user_zoomed = True   # utente ha zoomato: blocca auto-scroll
            factor = 0.85
            cx = event.xdata if event.xdata else (xmin + xmax) / 2
            new_min = cx - (cx - xmin) * factor
            new_max = cx + (xmax - cx) * factor
        else:
            # zoom-out: pop stato precedente, se vuoto non fare nulla
            if not self._zoom_stack:
                return
            new_min, new_max = self._zoom_stack.pop()
        if not self._zoom_stack:
                self._live_user_zoomed = False  # tornato alla vista originale
        ax.set_xlim(new_min, new_max)
        if self._ax2:
            self._ax2.set_xlim(new_min, new_max)
        # A2: feedback visivo immediato + bg_cache aggiornata dopo 80ms
        if self._cross_v is not None:
            try: self._cross_v.remove()
            except Exception: pass
            self._cross_v = None
        for _a in self._dot_artists:
            try: _a.remove()
            except Exception: pass
        self._dot_artists = []
        if self._tooltip is not None:
            try: self._tooltip.remove()
            except Exception: pass
            self._tooltip = None
        self._canvas.draw_idle()  # A2: visuale immediata, non bloccante
        if getattr(self, "_scroll_timer", None):
            try: self._canvas.get_tk_widget().after_cancel(self._scroll_timer)
            except Exception: pass
        self._drawing = True  # A2: blocca blit stantio finché bg_cache non è aggiornata
        def _capture_bg():
            self._scroll_timer = None
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            self._drawing = False  # A2: riabilita hover
        self._scroll_timer = self._canvas.get_tk_widget().after(80, _capture_bg)

    def _on_press(self, event):
        if event.inaxes not in [self._ax1, self._ax2]:
            return
        if event.dblclick and event.xdata is not None:
            if event.button == 1:
                # 1° doppio-click sinistro → A; 2° → B; 3° → reset entrambi
                if self._cur_a is None:
                    self._cur_a = event.xdata
                elif self._cur_b is None:
                    self._cur_b = event.xdata
                else:
                    self._cur_a = event.xdata
                    self._cur_b = None
            elif event.button == 3:
                self._cur_b = event.xdata
            self._redraw_cursors_ab()
            return
        if event.inaxes == self._ax1 and event.button == 1:
            self._pan_start = event.xdata
            self._pan_xlim  = self._ax1.get_xlim()
            self._pan_ylim  = self._ax1.get_ylim()  # freeze Y durante il pan

    def _on_release(self, event):
        if getattr(self, "_pan_moved", False):  # A1: draw solo se pan reale
            if self._ax1:
                self._ax1.set_xlim(self._ax1.get_xlim())
                self._ax1.set_ylim(self._ax1.get_ylim())
            self._drawing = True
            try:
                self._canvas.draw()
                self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            finally:
                self._drawing = False
        self._pan_start  = None
        self._pan_xlim   = None
        self._pan_ylim   = None
        self._pan_moved  = False  # A1: reset flag

    def _redraw_cursors_ab(self):
        """Rimuove i vecchi artist A/B e ridisegna. Traccia TUTTI gli artist creati."""
        if not self._ax1:
            return
        # Rimuove tutti gli artist precedenti (linee + testi + box)
        for a in self._ab_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._ab_artists = []
        ax1 = self._ax1
        # Disabilita autoscale PRIMA di tutto: matplotlib può chiamare
        # autoscale_view() internamente durante canvas.draw() anche con set_ylim.
        ax1.autoscale(enable=False)
        if self._ax2:
            self._ax2.autoscale(enable=False)
        # axvline usa blended_transform (x=dati, y=assi): NON aggiorna dataLim
        # e quindi non causa mai autoscale della Y quando vengono aggiunti i cursori.
        xax_tr = ax1.get_xaxis_transform()

        def _add(artist):
            self._ab_artists.append(artist)
            return artist

        if self._cur_a is not None:
            line_a = ax1.axvline(
                self._cur_a,
                color=COLORS["accent"], linewidth=1.2, linestyle="--", zorder=9)
            txt_a = ax1.text(
                self._cur_a, 0.98, " A",
                transform=xax_tr,
                color=COLORS["accent"], fontsize=8,
                fontweight="bold", va="top", zorder=10)
            _add(line_a); _add(txt_a)

        if self._cur_b is not None:
            line_b = ax1.axvline(
                self._cur_b,
                color=COLORS["accent2"], linewidth=1.2, linestyle="--", zorder=9)
            txt_b = ax1.text(
                self._cur_b, 0.98, " B",
                transform=xax_tr,
                color=COLORS["accent2"], fontsize=8,
                fontweight="bold", va="top", zorder=10)
            _add(line_b); _add(txt_b)

        if self._cur_a is not None and self._cur_b is not None:
            import numpy as _np
            _md = mdates
            xa, xb = sorted([self._cur_a, self._cur_b])
            xs_num = self._to_num(self._xs_raw)

            if self._x_type == "datetime":
                da = _md.num2date(xa)
                db = _md.num2date(xb)
                sec = abs((db - da).total_seconds())
                h, r = divmod(int(sec), 3600)
                m, s = divmod(r, 60)
                dx_str = f"\u0394X = {h:02d}h {m:02d}m {s:02d}s"
            else:
                dx_str = f"\u0394X = {abs(xb - xa):.4g}"

            lines_txt = [dx_str]
            for col in self._series:
                if col in self._hidden:
                    continue
                ys = self._series.get(col, [])
                xf, yf = self._clean(xs_num, ys)
                if not xf:
                    continue
                xarr = _np.array(xf)
                yarr = _np.array(yf)
                def _interp(xq):
                    i = int(_np.searchsorted(xarr, xq))
                    if i == 0: return float(yarr[0])
                    if i >= len(xarr): return float(yarr[-1])
                    x0, x1 = xarr[i-1], xarr[i]
                    y0, y1 = yarr[i-1], yarr[i]
                    return float(y0) if x1 == x0 else float(y0 + (y1-y0)*(xq-x0)/(x1-x0))
                va_v = _interp(xa)
                vb_v = _interp(xb)
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                dy = vb_v - va_v
                sign = "+" if dy >= 0 else ""
                lines_txt.append(f"{lbl}: {sign}{dy:.4g} {unit}".strip())

            box = ax1.text(
                (xa + xb) / 2, 0.05,
                "\n".join(lines_txt),
                transform=xax_tr,
                fontsize=7.5, color=COLORS["text"],
                bbox=dict(boxstyle="round,pad=0.4",
                          fc=COLORS["surface"], ec=COLORS["accent"],
                          lw=1.2, alpha=0.92),
                ha="center", va="bottom", zorder=11)
            _add(box)

        # Fix: rimuovi overlay e ridisegna in modo sincrono — bg_cache sempre aggiornata
        if self._cross_v is not None:
            try: self._cross_v.remove()
            except Exception: pass
            self._cross_v = None
        for _a in self._dot_artists:
            try: _a.remove()
            except Exception: pass
        self._dot_artists = []
        if self._tooltip is not None:
            try: self._tooltip.remove()
            except Exception: pass
            self._tooltip = None
        # Congela Y (e X) prima del draw: canvas.draw() chiama autoscale_view()
        # internamente se _autoscaleYon=True; set_ylim lo rende sticky (False).
        ax1.set_xlim(ax1.get_xlim())
        ax1.set_ylim(ax1.get_ylim())
        if self._ax2:
            self._ax2.set_ylim(self._ax2.get_ylim())
        self._drawing = True
        try:
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        finally:
            self._drawing = False
        # Se nessun cursore è attivo (reset) riabilita autoscale per la live tab
        if self._cur_a is None and self._cur_b is None:
            ax1.autoscale(enable=True)
            if self._ax2:
                self._ax2.autoscale(enable=True)

    def _do_pan(self, event):
        if event.xdata is None or self._pan_xlim is None:
            return
        dx = self._pan_start - event.xdata
        new_min = self._pan_xlim[0] + dx
        new_max = self._pan_xlim[1] + dx
        # Fix 1: clamp pan entro i limiti dei dati — non si va oltre inizio/fine
        xs_num = self._xs_num_cache if self._xs_num_cache is not None \
                 else self._to_num(self._xs_raw)
        valid = [x for x in xs_num if x is not None]
        if valid:
            data_min, data_max = min(valid), max(valid)
            span = new_max - new_min
            data_span = data_max - data_min
            # Se lo span copre l'intera ampiezza dei dati non è stato fatto zoom:
            # blocca il pan completamente.
            if data_span > 0 and span >= data_span * 0.999:
                return
            if new_min < data_min:
                new_min = data_min
                new_max = data_min + span
            if new_max > data_max:
                new_max = data_max
                new_min = data_max - span
        self._ax1.set_xlim(new_min, new_max)
        if getattr(self, "_pan_ylim", None) is not None:
            self._ax1.set_ylim(self._pan_ylim)  # impedisce autoscale Y durante il pan
        if self._ax2:
            self._ax2.set_xlim(new_min, new_max)
        # Fix: rimuovi overlay e ridisegna in modo sincrono — bg_cache sempre aggiornata
        if self._cross_v is not None:
            try: self._cross_v.remove()
            except Exception: pass
            self._cross_v = None
        for _a in self._dot_artists:
            try: _a.remove()
            except Exception: pass
        self._dot_artists = []
        if self._tooltip is not None:
            try: self._tooltip.remove()
            except Exception: pass
            self._tooltip = None
        self._pan_moved = True  # A1: segnala pan reale avvenuto
        self._canvas.draw_idle()  # A1: non bloccante durante il drag

    def reset_zoom(self):
        self._xlim_orig = None
        self._ylim_orig = None
        self._y2lim_orig = None
        self._zoom_stack = []
        self._cur_a = None
        self._cur_b = None
        self._ab_artists = []
        self._redraw()

    def clear_cursors(self):
        """Rimuove i cursori A/B dagli assi e aggiorna il bg_cache.
        Chiamare prima di ogni nuovo avvio live per evitare cursori congelati."""
        for a in self._ab_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._ab_artists = []
        self._cur_a = None
        self._cur_b = None
        # Ridisegna e aggiorna bg_cache → _on_motion userà la cache pulita
        try:
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        except Exception:
            pass

    def _rebuild_legend_sidebar(self):
        """Ripopola il pannello laterale con le serie attualmente plottate."""
        for w in self._legend_rows:
            try: w.destroy()
            except Exception: pass
        self._legend_rows.clear()
        if not self._series:
            return
        palette = list(_UC_SERIES_PALETTE)
        for col in self._series:
            color = self._colors.get(col, palette[0])
            lbl   = self._col_meta.get(col, {}).get("label", col)
            unit  = self._col_meta.get(col, {}).get("unit", "")
            is_y2 = col in self._y2_cols
            disp = lbl if len(lbl) <= 16 else lbl[:15] + "…"
            if unit:
                disp += f" [{unit}]"
            if is_y2:
                disp += " Y2"
            is_hidden = col in self._hidden
            btn = ctk.CTkButton(
                self._legend_panel,
                text=f"● {disp}",
                fg_color=color if not is_hidden else COLORS["surface2"],
                hover_color=color,
                text_color=COLORS["text"] if not is_hidden else COLORS["text2"],
                font=("Segoe UI", 9),
                anchor="w",
                height=26,
                corner_radius=4,
                command=lambda c=col: self._toggle_series(c)
            )
            btn.pack(side="left", padx=3, pady=4)
            self._legend_rows.append(btn)

        # ── sezione ② ──────────────────────────────────────────────────────
        if getattr(self, "_overlay_lines", {}):
            sep = ctk.CTkFrame(self._legend_panel,
                               fg_color=COLORS["border"], width=1, height=30)
            sep.pack(side="left", padx=6, pady=4)
            self._legend_rows.append(sep)
            all_vis = getattr(self, "_overlay_all_vis", True)
            glob_btn = ctk.CTkButton(
                self._legend_panel,
                text="● ② tutto" if all_vis else "○ ② tutto",
                fg_color=COLORS["accent"] if all_vis else COLORS["surface2"],
                hover_color=COLORS["accent"],
                text_color=COLORS["text"],
                font=("Segoe UI", 9, "bold"),
                height=26, corner_radius=4,
                command=self._toggle_all_overlay)
            glob_btn.pack(side="left", padx=3, pady=4)
            self._legend_rows.append(glob_btn)
            sep2 = ctk.CTkFrame(self._legend_panel,
                                fg_color=COLORS["border"], width=1, height=30)
            sep2.pack(side="left", padx=2, pady=4)
            self._legend_rows.append(sep2)
            for col, line in self._overlay_lines.items():
                color   = line.get_color()
                is_vis  = line.get_visible()
                btn2 = ctk.CTkButton(
                    self._legend_panel,
                    text=f"┄ {col} ②",
                    fg_color=color if is_vis else COLORS["surface2"],
                    hover_color=color,
                    text_color=COLORS["text"] if is_vis else COLORS["text2"],
                    font=("Segoe UI", 9),
                    anchor="w", height=26, corner_radius=4,
                    command=lambda c=col: self._toggle_overlay_line(c))
                btn2.pack(side="left", padx=3, pady=4)
                self._legend_rows.append(btn2)

    def _rescale_visible(self):
        """Ricalcola i limiti Y considerando solo le serie visibili."""
        ax1 = self._ax1
        y1_vals = []
        y2_vals = []
        for col, ys in self._series.items():
            if col in self._hidden:
                continue
            visible_vals = [v for v in ys if v is not None]
            if not visible_vals:
                continue
            if self._ax2 and col in self._y2_cols:
                y2_vals.extend(visible_vals)
            else:
                y1_vals.extend(visible_vals)
        if y1_vals:
            mn, mx = min(y1_vals), max(y1_vals)
            pad = (mx - mn) * 0.05 or 1.0
            ax1.set_ylim(mn - pad, mx + pad)
        if self._ax2 and y2_vals:
            mn, mx = min(y2_vals), max(y2_vals)
            pad = (mx - mn) * 0.05 or 1.0
            self._ax2.set_ylim(mn - pad, mx + pad)

    def _toggle_series(self, col):
        if col in self._hidden:
            self._hidden.discard(col)
        else:
            self._hidden.add(col)
        for c, line in self._lines.items():
            line.set_visible(c not in self._hidden)
        self._rescale_visible()
        self._rebuild_legend_sidebar()
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)

    def _toggle_overlay_line(self, col):
        """Mostra/nasconde singola serie ② dal pannello legenda."""
        if col not in getattr(self, "_overlay_lines", {}):
            return
        line = self._overlay_lines[col]
        line.set_visible(not line.get_visible())
        self._rebuild_legend_sidebar()
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)

    def _toggle_all_overlay(self):
        """Mostra/nasconde tutte le serie ② con un click."""
        self._overlay_all_vis = not getattr(self, "_overlay_all_vis", True)
        for line in getattr(self, "_overlay_lines", {}).values():
            line.set_visible(self._overlay_all_vis)
        self._rebuild_legend_sidebar()
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)

    def export_png(self, filepath):
        ax1 = self._ax1
        h1, l1 = ax1.get_legend_handles_labels()
        h2, l2 = (self._ax2.get_legend_handles_labels() if self._ax2 else ([], []))
        leg = None
        if h1 or h2:
            leg = ax1.legend(h1+h2, l1+l2, loc="upper left",
                bbox_to_anchor=(1.01,1), borderaxespad=0, fontsize=7.5,
                framealpha=0.85, facecolor=COLORS["surface"],
                edgecolor=COLORS["border"], labelcolor=COLORS["text"])
        _overlay = []
        if self._info_var.get().strip():
            for _a in ([self._cross_v] if self._cross_v is not None else []) + \
                       self._dot_artists + \
                       ([self._tooltip] if self._tooltip is not None else []):
                _a.set_animated(False); _overlay.append(_a)
            if _overlay: self._canvas.draw()
        self._fig.savefig(filepath, dpi=150, bbox_inches="tight",
            bbox_extra_artists=([leg] if leg else None),
            facecolor=self._fig.get_facecolor())
        if leg: leg.remove()
        for _a in _overlay: _a.set_animated(True)
        self._drawing = True
        try:
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        finally:
            self._drawing = False


_PC = {
    1:"#f44322",2:"#3f51b5",3:"#29b6f6",4:"#66bb6a",
    5:"#7d0910",6:"#607d8b",7:"#9c27b0",8:"#ff9800",
    "set_temp":"#795548","set_forza":"#7d0910",
    "lmax":"#607d8b","lmin":"#9c27b0",
    "bg":"#ccffff","grid":"#cccccc",
}
_SERIES_COLORS = {
    "TS1":"#e5672c","TS2":"#828282","TS3":"#407da5","TS4":"#e7b73b",
    "TS5":"#9c27b0","TS6":"#607d8b","TS7":"#ff9800","TS8":"#29b6f6",
    "TI1":"#e5672c","TI2":"#828282","TI3":"#407da5","TI4":"#e7b73b",
    "TI5":"#9c27b0","TI6":"#607d8b","TI7":"#ff9800","TI8":"#29b6f6",
    "T1":"#e5672c","T2":"#828282","T3":"#407da5","T4":"#e7b73b",
    "T5":"#9c27b0","T6":"#607d8b","T7":"#ff9800","T8":"#29b6f6",
    "P1":"#407da5","P2":"#e5672c","P3":"#828282","P4":"#e7b73b",
    "Z1":"#407da5","Z2":"#e5672c","Z3":"#828282","Z4":"#e7b73b",
    "F1":"#f44322","F2":"#3f51b5","F3":"#29b6f6","F4":"#66bb6a","FC":"#f44322","SPC":"#7d0910",
    "VS1":"#407da5","VS2":"#e5672c","V1":"#407da5","V2":"#e5672c",
    "VI1":"#407da5","VI2":"#e5672c","VI3":"#828282","VI4":"#e7b73b",
    "V3":"#828282","V4":"#e7b73b",
}
_PROFILES = {
"Inner Tub":{"ricetta":"Tub - Ciclo nuovo","temp_set_sup":127.0,"temp_set_inf":125.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax_sup":1090, "vuoto_bg_ymax_sup":-0.2, "vuoto_no_bg_inf":True,
    "x_ticks":[0,174,349,523,698,872,1047,1221,1396,1570,1745],"x_max":1745,
    "forza_legend_loc":"lower right","pressa":"Cannon 5000T","persico":False},
"Polecrasher":{"ricetta":"Polecrasher - Ciclo nuovo","temp_set_sup":129.0,"temp_set_inf":127.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax_inf":1100,"vuoto_bg_ymax_inf":-0.2, "vuoto_no_bg_sup":True,
    "x_ticks":[0,174,348,522,696,870,1044,1218,1392,1566,1740],"x_max":1740,
    "forza_legend_loc":"upper left","pressa":"Cannon 5000T","persico":False},
"Tub Floor Shell":{"ricetta":"Tub Floor Shell - Ciclo nuovo","temp_set_sup":129.0,"temp_set_inf":130.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax_sup":1070, "vuoto_bg_ymax_sup":-0.2, "vuoto_no_bg_inf":True,
    "x_ticks":[0,150,300,450,600,750,900,1050,1200,1350,1500],"x_max":1500,
    "forza_legend_loc":"upper left","pressa":"Cannon 5000T","persico":False},
"Front Firewall":{"ricetta":"Front Firewall - Ciclo","pressa":"Persico 2500T","persico":True,
    "teorico_sec":2633,"temp_set_sup":130.0,"temp_set_inf":128.0,
    "temp_y":(95.0,165.0),"temp_yticks":[100,110,120,130,140,150,160],
    "forza_y":(5900,6900),"forza_yticks":[6000,6100,6200,6300,6400,6500,6600,6700,6800],
    "forza_spc":6500.0,"forza_delta":200,
    "posiz_y":(-0.35,0.05),"posiz_yticks":[-0.35,-0.30,-0.25,-0.20,-0.15,-0.10,-0.05,0.0,0.05],
    "vuoto_y":(-1050,50),"vuoto_yticks":[-1000,-800,-600,-400,-200,0],
    "x_ticks":[0,132,264,396,528,660,792,924,1056,1188,1320,1452,1496],"x_max":1496,
    "forza_legend_loc":"lower right","temp_range":(120,140),"skip_seconds":8},

"Central Cofango":{"ricetta":"Central Cofango - Ciclo","pressa":"Persico 2500T","persico":True,
    "teorico_sec":879,"temp_set_sup":142.0,"temp_set_inf":142.0,
    "temp_y":(100.0,160.0),"temp_yticks":[100,110,120,130,140,150,160],
    "forza_y":(3500,4300),"forza_yticks":[3500,3600,3700,3800,3900,4000,4100,4200,4300],
    "forza_spc":4000.0,"forza_delta":200,
    "posiz_y":(0.0,0.18),"posiz_yticks":[0.0,0.02,0.04,0.06,0.08,0.10,0.12,0.14,0.16,0.18],
    "vuoto_y":(-1000,0),"vuoto_yticks":[-1000,-900,-800,-700,-600,-500,-400,-300,-200,-100,0],
    "x_ticks_tv":list(range(22, 406+1, 12)),
    "x_ticks_pos":list(range(14, 410+1, 12)),
    "x_ticks_forza":list(range(22, 406+1, 12)),
    "x_ticks_vac_sup":list(range(14, 410+1, 12)),
    "x_ticks_vac_inf":list(range(22, 406+1, 12)),
    "forza_legend_loc":"lower right",
    "forza_range":(3750,4250)},
    "Side Cofango Inner":{"ricetta":"Side Cofango Inner - Ciclo","pressa":"Persico 2500T","persico":True,
        "teorico_sec":990,"temp_set_sup":142.0,"temp_set_inf":142.0,
        "temp_y":(100.0,160.0),"temp_yticks":[100,110,120,130,140,150,160],
        "forza_y":(3500,4300),"forza_yticks":[3500,3600,3700,3800,3900,4000,4100,4200,4300],
        "forza_spc":4000.0,"forza_delta":200,
        "posiz_y":(-0.05,0.3),"posiz_yticks":[-0.05,0.0,0.05,0.1,0.15,0.2,0.25,0.3],
        "vuoto_y":(-1000,0),"vuoto_yticks":[-1000,-900,-800,-700,-600,-500,-400,-300,-200,-100,0],
        "x_ticks_tv":list(range(25, 520+1, 15)),
        "x_ticks_pos":list(range(15, 525+1, 15)),
        "x_ticks_forza":list(range(25, 520+1, 15)),
        "x_ticks_vac_sup":list(range(15, 525+1, 15)),
        "x_ticks_vac_inf":list(range(25, 520+1, 15)),
        "forza_legend_loc":"lower right",
        "forza_range":(3750,4250),"temp_range":(130, 150)},
"Side Cover":{"ricetta":"Side Cover - Ciclo","pressa":"Krauss Maffei","persico":False,
    "temp_set_sup":130.0,"temp_set_inf":128.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax":1070, "vuoto_bg_ymax":-0.2,
    "x_ticks":[0,150,300,450,600,750,900,1050,1200,1350,1500],"x_max":1500,
    "forza_legend_loc":"upper left"},
}
_PRESSA_STAMPI = {
    "Cannon 5000T":["Inner Tub","Tub Floor Shell","Polecrasher"],
    "Persico 2500T":["Front Firewall","Central Cofango","Side Cofango Inner"],
    "Krauss Maffei":["Side Cover"],
}



# -- UNIVERSAL PLANT PDF ---------------------------------------------------

_PLANT_PALETTE = [
    "#e5672c", "#3f51b5", "#29b6f6", "#66bb6a",
    "#9c27b0", "#ff9800", "#e7b73b", "#607d8b",
    "#f44322", "#00bcd4", "#8bc34a", "#ff5722",
]

def _plant_pdf_colors(cols):
    return {c: _PLANT_PALETTE[i % len(_PLANT_PALETTE)] for i, c in enumerate(cols)}


def _plant_pdf_header(fig, title, subtitle, logo_path, page_num, total_pages,
                      generated_at, meta_rows):
    fig.add_artist(plt.Line2D(
        [0.03, 0.97], [0.997, 0.997],
        transform=fig.transFigure, color="#444", lw=1.0))
    if logo_path and os.path.exists(logo_path):
        try:
            import matplotlib.image as _mpi
            ax_l = fig.add_axes([0.03, 0.948, 0.055, 0.042], frameon=False)
            ax_l.imshow(_mpi.imread(logo_path), aspect="auto")
            ax_l.axis("off")
            tx_x = 0.10
        except Exception:
            tx_x = 0.03
    else:
        tx_x = 0.03
    fig.text(tx_x, 0.978, title, fontsize=13, fontweight="bold", va="top", color="#111")
    fig.text(tx_x, 0.961, subtitle, fontsize=8.5, va="top", color="#555")
    fig.text(0.97, 0.978, f"Generato: {generated_at}",
             fontsize=7.5, ha="right", va="top", color="#777")
    fig.text(0.97, 0.963, f"Pag. {page_num} / {total_pages}",
             fontsize=7.5, ha="right", va="top", color="#777")
    fig.add_artist(plt.Line2D(
        [0.03, 0.97], [0.950, 0.950],
        transform=fig.transFigure, color="#aaa", lw=0.5))
    if meta_rows:
        y0 = 0.943
        rh = 0.022
        for lbl, val in meta_rows[:8]:
            fig.text(0.03, y0, lbl, fontsize=7.5, fontweight="bold", va="top", color="#333")
            fig.text(0.22, y0, str(val), fontsize=7.5, va="top", color="#111")
            fig.add_artist(plt.Line2D(
                [0.03, 0.97], [y0 - 0.017, y0 - 0.017],
                transform=fig.transFigure, color="#ddd", lw=0.4))
            y0 -= rh
        fig.add_artist(plt.Line2D(
            [0.03, 0.97], [y0 - 0.004, y0 - 0.004],
            transform=fig.transFigure, color="#888", lw=0.6))
        return y0 - 0.012
    return 0.940


def _plant_pdf_setup_ax(ax, title, unit, xs_all, ys_all, x_type, color_grid="#e0e0e0"):
    ax.set_facecolor("white")
    for sp in ax.spines.values():
        sp.set_edgecolor("#aaa")
        sp.set_linewidth(0.6)
    ax.tick_params(axis="both", labelsize=7, length=3, color="#888", labelcolor="#333")
    ax.grid(True, axis="y", color=color_grid, linewidth=0.5, linestyle="-", alpha=0.8)
    ax.grid(True, axis="x", color=color_grid, linewidth=0.3, linestyle="--", alpha=0.5)
    ax.set_title(title, fontsize=9, fontweight="bold", pad=5, color="#222", loc="left")
    if unit:
        ax.set_ylabel(unit, fontsize=7.5, color="#555", labelpad=3)
    flat = [v for v in ys_all if v is not None]
    if flat:
        mn, mx = min(flat), max(flat)
        pad = (mx - mn) * 0.08 or max(abs(mn) * 0.05, 0.001)
        ax.set_ylim(mn - pad, mx + pad)
    if x_type == "datetime":
        valid_x = [x for x in xs_all if x is not None]
        if valid_x:
            span = max(valid_x) - min(valid_x)
            if span < 1 / 24:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            elif span < 1:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            elif span < 7:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
            else:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y"))
    plt.setp(ax.get_xticklabels(), rotation=25, fontsize=6.5, color="#555")


def _plant_pdf_legend(ax, ncol=4):
    h, l = ax.get_legend_handles_labels()
    if not h:
        return
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              ncol=min(ncol, len(l)), fontsize=7, framealpha=0.9,
              edgecolor="#ccc", handlelength=2.0, borderpad=0.5, labelspacing=0.3)


def _plant_group_series(y_cols, y2_cols, col_meta):
    groups = {}
    for col in y_cols:
        m = col_meta.get(col, {})
        unit  = m.get("unit", "")
        label = m.get("label", col)
        key = m.get("label", col) if m.get("label", col) != col else (unit or "Valori")
        if key not in groups:
            groups[key] = {"unit": unit, "cols": [], "y2": False}
        groups[key]["cols"].append(col)
    result = []
    for title, g in groups.items():
        is_y2 = any(c in y2_cols for c in g["cols"])
        result.append((title, g["unit"], g["cols"], is_y2))
    return result


def _plant_pdf_stats_table(fig, y_cols, col_meta, all_stats, top_y,
                           stats2=None, cols2=None, col_meta2=None):
    ax = fig.add_axes([0.03, 0.05, 0.94, top_y - 0.08])
    ax.axis("off")
    cols2 = cols2 or []
    stats2 = stats2 or {}
    col_meta2 = col_meta2 or {}

    def _fmt(v):
        return f"{v:.4g}" if isinstance(v, float) else "-"

    y_set  = set(y_cols)
    c2_set = set(cols2)
    shared     = [c for c in y_cols if c in c2_set]   # stesso nome
    only_csv1  = [c for c in y_cols if c not in c2_set]
    only_csv2  = [c for c in cols2  if c not in y_set]

    cur_y = top_y - 0.02  # posizione verticale corrente
    ax2 = fig.add_axes([0.03, 0.05, 0.94, top_y - 0.08])
    ax2.axis("off")
    txt_kw = dict(transform=fig.transFigure, fontsize=7.5, va="top")

    def _draw_table(title, col_labels, rows_data, y_start, hdr_color="#333"):
        if not rows_data:
            return y_start
        # titolo sezione
        fig.text(0.05, y_start, title, fontsize=8, fontweight="bold",
                 color="#444", transform=fig.transFigure, va="top")
        y_start -= 0.025
        avail_h = max(0.05, y_start - 0.06)
        ax_t = fig.add_axes([0.03, y_start - avail_h, 0.94, avail_h])
        ax_t.axis("off")
        tbl = ax_t.table(cellText=rows_data, colLabels=col_labels,
                         loc="upper center", cellLoc="center")
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(6.8)
        tbl.scale(1, 1.3)
        for j in range(len(col_labels)):
            cell = tbl[0, j]
            cell.set_facecolor(hdr_color)
            cell.set_text_props(color="white", fontweight="bold")
        for i_r, row in enumerate(rows_data, start=1):
            bg = "#f7f7f7" if i_r % 2 == 0 else "white"
            for j in range(len(col_labels)):
                cell = tbl[i_r, j]
                cell.set_facecolor(bg)
                cell.set_edgecolor("#ddd")
        row_h = avail_h / (len(rows_data) + 1)
        return y_start - avail_h - 0.02

    cur_y = top_y - 0.01

    # ── Sezione affiancata (colonne con stesso nome) ────────────────────────
    if shared:
        hdr_shared = ["Colonna", "Unità",
                      "N ①", "Min ①", "Max ①", "Media ①",
                      "N ②", "Min ②", "Max ②", "Media ②"]
        rows_shared = []
        for col in shared:
            m1  = col_meta.get(col, {})
            m2  = col_meta2.get(col, m1)
            s1  = all_stats.get(col, {})
            s2  = stats2.get(col, {})
            unit = m1.get("unit", m2.get("unit", ""))
            rows_shared.append([
                col[:22], unit,
                str(s1.get("n", "-")),
                _fmt(s1.get("min")), _fmt(s1.get("max")), _fmt(s1.get("mean")),
                str(s2.get("n", "-")),
                _fmt(s2.get("min")), _fmt(s2.get("max")), _fmt(s2.get("mean")),
            ])
        cur_y = _draw_table("Confronto ① vs ②", hdr_shared, rows_shared, cur_y, "#1a6b3a")

    # ── Solo CSV1 ──────────────────────────────────────────────────────────
    if only_csv1:
        hdr1 = ["Colonna ①", "Tipo / Unità", "N", "Min", "Max", "Media (μ)", "Dev.Std (σ)", "Anomalie"]
        rows1 = []
        for col in only_csv1:
            m   = col_meta.get(col, {})
            st  = all_stats.get(col, {})
            anom = st.get("anomalies", 0)
            rows1.append([
                col[:24],
                f"{m.get('label', col)[:18]} / {m.get('unit', '')}",
                str(st.get("n", "-")),
                _fmt(st.get("min")), _fmt(st.get("max")), _fmt(st.get("mean")), _fmt(st.get("std")),
                f"⚠ {anom}" if anom > 0 else "OK",
            ])
        cur_y = _draw_table("Solo CSV principale ①", hdr1, rows1, cur_y, "#333")

    # ── Solo CSV2 ──────────────────────────────────────────────────────────
    if only_csv2:
        hdr2 = ["Colonna ②", "Unità", "N", "Min", "Max", "Media (μ)", "Dev.Std (σ)"]
        rows2_t = []
        for col in only_csv2:
            m2 = col_meta2.get(col, {})
            s2 = stats2.get(col, {})
            rows2_t.append([
                col[:24], m2.get("unit", ""),
                str(s2.get("n", "-")),
                _fmt(s2.get("min")), _fmt(s2.get("max")),
                _fmt(s2.get("mean")), _fmt(s2.get("std")),
            ])
        cur_y = _draw_table("Solo CSV confronto ②", hdr2, rows2_t, cur_y, "#1a3f7a")

    # ── Fallback: solo CSV1 senza confronto ────────────────────────────────
    if not shared and not only_csv2 and not only_csv1:
        ax.text(0.5, 0.5, "Nessuna statistica disponibile",
                ha="center", va="center", fontsize=10, color="#888",
                transform=ax.transAxes)


