# -*- coding: utf-8 -*-
"""
plot_canvas.py
Widget matplotlib interattivo per la visualizzazione CSV universale.
Fornisce: hover crosshair, tooltip, zoom rotella con stack undo,
pan drag, cursori A/B con delta, overlay secondo CSV, toggle serie.
"""
import tkinter as tk
import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from datetime import datetime

from colors import COLORS, _UC_SERIES_PALETTE
from csv_parser import _uc_build_series


class InteractivePlotCanvas:
    """Wrapper matplotlib con hover crosshair, zoom rotella, pan drag."""

    def __init__(self, master, height=320):
        self.master  = master
        self.height  = height
        self._rows   = []
        self._xs_raw = []
        self._xs_num_cache = None
        self._series   = {}
        self._x_type   = "index"
        self._col_meta = {}
        self._y2_cols  = set()
        self._colors   = {}
        self._x_label  = ""
        self._xlim_orig  = None
        self._ylim_orig  = None
        self._y2lim_orig = None
        self._pan_start  = None
        self._pan_xlim   = None
        self._hover_cid  = None
        self._cross_v    = None
        self._tooltip    = None
        self._dot_artists   = []
        self._hidden        = set()
        self._lines         = {}
        self._overlay_lines   = {}
        self._overlay_all_vis = True
        self._zoom_stack  = []
        self._cur_a       = None
        self._cur_b       = None
        self._ab_artists  = []
        self.show_markers = True
        self._ranges      = []
        self._drawing     = False

        self._frame = ctk.CTkFrame(master, fg_color=COLORS["surface"], corner_radius=8)
        self._frame.pack(fill="both", expand=True, padx=0, pady=0)

        # info bar hover
        self._info_var = tk.StringVar(value="")
        self._info_lbl = ctk.CTkLabel(
            self._frame, textvariable=self._info_var,
            font=("Courier New", 10), text_color=COLORS["accent2"],
            fg_color=COLORS["surface2"], corner_radius=4, anchor="w")
        self._info_lbl.pack(fill="x", padx=6, pady=(4, 0))
        self._info_lbl.configure(fg_color="transparent")

        self._plot_area = ctk.CTkFrame(self._frame, fg_color="transparent")
        self._plot_area.pack(fill="both", expand=True)

        # barra toggle serie
        self._legend_panel = ctk.CTkScrollableFrame(
            self._frame, fg_color=COLORS["surface2"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"],
            orientation="horizontal", height=40, corner_radius=4)
        self._legend_panel.pack(fill="x", padx=4, pady=(2, 4))
        self._legend_rows = []

        # figura matplotlib
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
        self._canvas.draw()

        self._resize_job = None
        self._canvas.mpl_connect("resize_event",         self._on_resize)
        self._canvas.mpl_connect("scroll_event",         self._on_scroll)
        self._canvas.mpl_connect("button_press_event",   self._on_press)
        self._canvas.mpl_connect("button_release_event", self._on_release)
        self._canvas.mpl_connect("motion_notify_event",  self._on_motion)
        self._canvas.get_tk_widget().bind("<Leave>", lambda e: self._clear_hover())

    # ── Resize ─────────────────────────────────────────────────────────────

    def _on_resize(self, event):
        if self._resize_job is not None:
            try:
                self._frame.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self._frame.after(300, self._on_resize_done)

    def _on_resize_done(self):
        self._resize_job = None
        if self._xs_raw and self._series:
            self._fig.tight_layout(pad=1.2)
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            self._cross_v  = None
            self._tooltip  = None

    # ── Dati ────────────────────────────────────────────────────────────────

    def set_data(self, xs_raw, series, x_type, col_meta,
                 y2_cols=None, colors=None, x_label=""):
        self._xs_raw       = xs_raw
        self._xs_num_cache = None
        self._series   = series
        self._x_type   = x_type
        self._col_meta = col_meta
        self._y2_cols  = set(y2_cols or [])
        self._x_label  = x_label
        palette = list(_UC_SERIES_PALETTE)
        self._colors = {col: (colors or {}).get(col, palette[i % len(palette)])
                        for i, col in enumerate(series)}
        self._xlim_orig  = None
        self._ylim_orig  = None
        self._y2lim_orig = None
        self._hidden     = set()
        self._zoom_stack = []
        self._cur_a = None
        self._cur_b = None
        self._ab_artists = []
        self._redraw()
        self._rebuild_legend_sidebar()

    def _overlay_second_csv(self, rows2, x_col, cols, colors2, col_meta):
        """Sovrappone le serie del secondo CSV sull'asse corrente (linee tratteggiate)."""
        if not self._ax1 or not rows2:
            return
        xs2, series2, x_type2 = _uc_build_series(rows2, x_col, cols, col_meta)
        xs_num2 = (self._to_num(xs2) if x_type2 == "datetime"
                   else [float(x) if x is not None else None for x in xs2])
        for col in cols:
            ys = series2.get(col, [])
            xf, yf = self._clean(xs_num2, ys)
            if not xf:
                continue
            color = colors2.get(col, "#aaaaaa")
            line, = self._ax1.plot(xf, yf, color=color, linewidth=1.2,
                                   linestyle="--", label=f"{col} ②",
                                   zorder=2, alpha=0.85)
            self._overlay_lines[col] = line
        self._xs_num_cache = None
        self._fig.tight_layout(pad=1.2)
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        self._rebuild_legend_sidebar()

    def update_live(self, xs_raw, series, x_type, col_meta,
                    colors=None, background=False):
        """Redraw incrementale per Live Data."""
        needs_full = (getattr(self, "_needs_full_redraw", False)
                      or set(series.keys()) != set(self._lines.keys())
                      or not self._lines)
        if needs_full:
            self._needs_full_redraw = False
            self.set_data(xs_raw, series, x_type, col_meta, colors=colors)
            return
        new_fp = (len(xs_raw),
                  tuple((k, len(v), v[-1] if v else None) for k, v in series.items()))
        if new_fp == getattr(self, "_live_data_fp", None):
            return
        self._live_data_fp  = new_fp
        self._xs_raw        = xs_raw
        self._xs_num_cache  = None
        self._series   = series
        self._x_type   = x_type
        self._col_meta = col_meta
        if colors:
            for col, c in colors.items():
                if col in self._colors and self._colors[col] != c:
                    self._colors[col] = c
                    if col in self._lines:
                        self._lines[col].set_color(c)
        # pulisce artisti animati
        if self._cross_v is not None:
            try:
                self._cross_v.set_xdata([]); self._cross_v.set_ydata([])
            except Exception:
                pass
            self._cross_v = None
        for dot in self._dot_artists:
            try:
                dot.set_xdata([]); dot.set_ydata([])
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
        if self._hidden:
            self._rescale_visible()
        else:
            ax1.relim(); ax1.autoscale_view()
            if self._ax2:
                self._ax2.relim(); self._ax2.autoscale_view()
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
        self._ranges = ranges or []
        self._redraw()
        self._rebuild_legend_sidebar()

    def clear(self):
        self._xs_raw       = []
        self._xs_num_cache = None
        self._series = {}
        self._redraw()

    def get_frame(self):
        return self._frame

    # ── Ridisegno completo ──────────────────────────────────────────────────

    def _redraw(self):
        self._overlay_lines = {}
        self._fig.clf()
        self._ax1    = self._fig.add_subplot(111)
        self._ax2    = None
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
                self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            finally:
                self._drawing = False
            return
        xs_num  = self._to_num(self._xs_raw)
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

        def _marker_size(n):
            if n <= 20:  return 6
            if n <= 50:  return 4
            if n <= 200: return 3
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
            ax1.set_xlabel(self._x_label or "Indice",
                           color=COLORS["text2"], fontsize=8)
        for _c, _l in self._lines.items():
            _l.set_visible(_c not in self._hidden)
        # bande range personalizzati
        for rule in self._ranges:
            col   = rule.get("col")
            lo    = rule.get("lo")
            hi    = rule.get("hi")
            if col in self._hidden:
                continue
            color = self._colors.get(col, COLORS["accent"])
            ax    = self._ax2 if (self._ax2 and col in self._y2_cols) else ax1
            if lo is not None and hi is not None:
                ax.axhspan(lo, hi, color=color, alpha=0.12, zorder=1)
            elif lo is not None:
                ax.axhline(lo, color=color, linewidth=1.0, linestyle=":", alpha=0.7, zorder=2)
            elif hi is not None:
                ax.axhline(hi, color=color, linewidth=1.0, linestyle=":", alpha=0.7, zorder=2)
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

    # ── Helper numerici ────────────────────────────────────────────────────

    def _to_num(self, xs):
        if not xs:
            return []
        if self._x_type == "datetime":
            return [mdates.date2num(x) if isinstance(x, datetime) else None for x in xs]
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
        span = max(valid) - min(valid)
        if span < 1 / 24:
            fmt = mdates.DateFormatter("%H:%M:%S")
        elif span < 1:
            fmt = mdates.DateFormatter("%H:%M")
        elif span < 7:
            fmt = mdates.DateFormatter("%d/%m %H:%M")
        else:
            fmt = mdates.DateFormatter("%d/%m/%Y")
        ax.xaxis.set_major_formatter(fmt)
        plt.setp(ax.get_xticklabels(), rotation=30, fontsize=7, color=COLORS["text2"])

    # ── Hover ───────────────────────────────────────────────────────────────

    def _clear_hover(self):
        self._info_var.set("")
        try:
            self._info_lbl.configure(fg_color="transparent")
        except Exception:
            pass
        if self._cross_v is not None:
            try:
                self._cross_v.remove()
            except Exception:
                pass
            self._cross_v = None
        for a in self._dot_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._dot_artists = []
        if self._tooltip is not None:
            try:
                self._tooltip.remove()
            except Exception:
                pass
            self._tooltip = None
        try:
            self._canvas.restore_region(self._bg_cache)
            self._canvas.blit(self._fig.bbox)
        except Exception:
            pass

    def _on_motion(self, event):
        if getattr(self, "_drawing", False):
            return
        if event.inaxes not in (self._ax1, self._ax2):
            self._clear_hover()
            return
        if not self._xs_raw and not self._series:
            self._clear_hover()
            return
        if self._pan_start is not None:
            self._do_pan(event)
            return
        ax1 = self._ax1
        if self._xs_num_cache is None:
            self._xs_num_cache = self._to_num(self._xs_raw)
        xs_num = self._xs_num_cache
        xm = event.xdata
        if xm is None:
            return
        xs_arr = np.array([x if x is not None else np.nan for x in xs_num])
        idx    = int(np.nanargmin(np.abs(xs_arr - xm)))
        x_snap = xs_num[idx]
        if x_snap is None:
            return
        if self._x_type == "datetime" and isinstance(self._xs_raw[idx], datetime):
            x_str = self._xs_raw[idx].strftime("%d/%m/%Y %H:%M:%S")
        else:
            x_str = (f"{self._xs_raw[idx]:.4g}"
                     if isinstance(self._xs_raw[idx], float)
                     else str(self._xs_raw[idx]))
        parts = [f"X: {x_str}"]
        for col, ys in self._series.items():
            if col in self._hidden:
                continue
            if idx < len(ys) and ys[idx] is not None:
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                parts.append(f"{lbl}: {ys[idx]:.4g}{(' ' + unit) if unit else ''}")
        for _c2, _ln2 in getattr(self, "_overlay_lines", {}).items():
            if not _ln2.get_visible():
                continue
            _lx2 = _ln2.get_xdata()
            _ly2 = _ln2.get_ydata()
            if not len(_lx2):
                continue
            _li2 = int(np.nanargmin(np.abs(np.array([float(x) for x in _lx2]) - x_snap)))
            if _li2 < len(_ly2) and _ly2[_li2] is not None:
                parts.append(f"{_c2}②: {float(_ly2[_li2]):.4g}")
        try:
            self._info_lbl.configure(fg_color=COLORS["surface2"])
        except Exception:
            pass
        self._info_var.set("   ".join(parts))
        try:
            self._canvas.restore_region(self._bg_cache)
        except Exception:
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            self._canvas.restore_region(self._bg_cache)
        ylim = ax1.get_ylim()
        xlim = ax1.get_xlim()
        # crosshair
        if self._cross_v is None:
            self._cross_v, = ax1.plot(
                [x_snap, x_snap], ylim,
                color=COLORS["accent2"], linewidth=0.8,
                linestyle="--", zorder=10, animated=True)
        else:
            self._cross_v.set_xdata([x_snap, x_snap])
            self._cross_v.set_ydata(ylim)
        ax1.draw_artist(self._cross_v)
        # dot snap
        for artist in self._dot_artists:
            try:
                artist.remove()
            except Exception:
                pass
        self._dot_artists = []
        for col in self._lines:
            if col in self._hidden:
                continue
            ys = self._series.get(col, [])
            if idx >= len(ys) or ys[idx] is None:
                continue
            ax = self._ax2 if (self._ax2 and col in self._y2_cols) else ax1
            dot, = ax.plot(x_snap, float(ys[idx]), "o",
                           color=self._colors.get(col, "#fff"),
                           markersize=6, zorder=11, animated=True)
            self._dot_artists.append(dot)
            ax.draw_artist(dot)
        for _c2, _ln2 in getattr(self, "_overlay_lines", {}).items():
            if not _ln2.get_visible():
                continue
            _lx2 = _ln2.get_xdata()
            _ly2 = _ln2.get_ydata()
            if not len(_lx2):
                continue
            _li2 = int(np.nanargmin(np.abs(np.array([float(x) for x in _lx2]) - x_snap)))
            if _li2 < len(_ly2) and _ly2[_li2] is not None:
                _d2, = ax1.plot(float(_lx2[_li2]), float(_ly2[_li2]), "D",
                                color=_ln2.get_color(), markersize=5, zorder=11,
                                animated=True,
                                markeredgecolor="#fff", markeredgewidth=0.5)
                self._dot_artists.append(_d2)
                ax1.draw_artist(_d2)
        # tooltip
        tip_lines = [f"X: {x_str}"]
        for col, ys in self._series.items():
            if col in self._hidden:
                continue
            if idx < len(ys) and ys[idx] is not None:
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                tip_lines.append(f"{lbl}: {ys[idx]:.4g}{(' ' + unit) if unit else ''}")
        tip_txt = "\n".join(tip_lines)
        x_frac = ((x_snap - xlim[0]) / (xlim[1] - xlim[0])
                  if xlim[1] != xlim[0] else 0.5)
        ha    = "left" if x_frac < 0.75 else "right"
        x_off = (x_snap + (xlim[1] - xlim[0]) * 0.015 if ha == "left"
                 else x_snap - (xlim[1] - xlim[0]) * 0.015)
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

    # ── Scroll / Pan / Press ─────────────────────────────────────────────

    def _on_scroll(self, event):
        if event.inaxes != self._ax1:
            return
        ax = self._ax1
        xmin, xmax = ax.get_xlim()
        if event.button == "up":
            if len(self._zoom_stack) < 50:
                self._zoom_stack.append((xmin, xmax))
                self._live_user_zoomed = True
            factor = 0.85
            cx = event.xdata if event.xdata else (xmin + xmax) / 2
            new_min = cx - (cx - xmin) * factor
            new_max = cx + (xmax - cx) * factor
        else:
            if not self._zoom_stack:
                return
            new_min, new_max = self._zoom_stack.pop()
        if not self._zoom_stack:
            self._live_user_zoomed = False
        ax.set_xlim(new_min, new_max)
        if self._ax2:
            self._ax2.set_xlim(new_min, new_max)
        if self._cross_v is not None:
            try:
                self._cross_v.remove()
            except Exception:
                pass
            self._cross_v = None
        for _a in self._dot_artists:
            try:
                _a.remove()
            except Exception:
                pass
        self._dot_artists = []
        if self._tooltip is not None:
            try:
                self._tooltip.remove()
            except Exception:
                pass
            self._tooltip = None
        self._canvas.draw_idle()
        if getattr(self, "_scroll_timer", None):
            try:
                self._canvas.get_tk_widget().after_cancel(self._scroll_timer)
            except Exception:
                pass
        self._drawing = True
        def _capture_bg():
            self._scroll_timer = None
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            self._drawing = False
        self._scroll_timer = self._canvas.get_tk_widget().after(80, _capture_bg)

    def _on_press(self, event):
        if event.inaxes not in [self._ax1, self._ax2]:
            return
        if event.dblclick and event.xdata is not None:
            if event.button == 1:
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
            self._pan_ylim  = self._ax1.get_ylim()

    def _on_release(self, event):
        if getattr(self, "_pan_moved", False):
            if self._ax1:
                self._ax1.set_xlim(self._ax1.get_xlim())
                self._ax1.set_ylim(self._ax1.get_ylim())
            self._drawing = True
            try:
                self._canvas.draw()
                self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            finally:
                self._drawing = False
        self._pan_start = None
        self._pan_xlim  = None
        self._pan_ylim  = None
        self._pan_moved = False

    def _do_pan(self, event):
        if event.xdata is None or self._pan_xlim is None:
            return
        dx      = self._pan_start - event.xdata
        new_min = self._pan_xlim[0] + dx
        new_max = self._pan_xlim[1] + dx
        xs_num  = (self._xs_num_cache if self._xs_num_cache is not None
                   else self._to_num(self._xs_raw))
        valid   = [x for x in xs_num if x is not None]
        if valid:
            data_min, data_max = min(valid), max(valid)
            span = new_max - new_min
            data_span = data_max - data_min
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
            self._ax1.set_ylim(self._pan_ylim)
        if self._ax2:
            self._ax2.set_xlim(new_min, new_max)
        if self._cross_v is not None:
            try:
                self._cross_v.remove()
            except Exception:
                pass
            self._cross_v = None
        for _a in self._dot_artists:
            try:
                _a.remove()
            except Exception:
                pass
        self._dot_artists = []
        if self._tooltip is not None:
            try:
                self._tooltip.remove()
            except Exception:
                pass
            self._tooltip = None
        self._pan_moved = True
        self._canvas.draw_idle()

    # ── Cursori A/B ─────────────────────────────────────────────────────────

    def _redraw_cursors_ab(self):
        for a in self._ab_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._ab_artists = []
        ax1 = self._ax1
        ax1.autoscale(enable=False)
        if self._ax2:
            self._ax2.autoscale(enable=False)
        xax_tr = ax1.get_xaxis_transform()

        def _add(artist):
            self._ab_artists.append(artist)
            return artist

        if self._cur_a is not None:
            _add(ax1.axvline(self._cur_a, color=COLORS["accent"],
                             linewidth=1.2, linestyle="--", zorder=9))
            _add(ax1.text(self._cur_a, 0.98, " A", transform=xax_tr,
                          color=COLORS["accent"], fontsize=8,
                          fontweight="bold", va="top", zorder=10))
        if self._cur_b is not None:
            _add(ax1.axvline(self._cur_b, color=COLORS["accent2"],
                             linewidth=1.2, linestyle="--", zorder=9))
            _add(ax1.text(self._cur_b, 0.98, " B", transform=xax_tr,
                          color=COLORS["accent2"], fontsize=8,
                          fontweight="bold", va="top", zorder=10))
        if self._cur_a is not None and self._cur_b is not None:
            xa, xb   = sorted([self._cur_a, self._cur_b])
            xs_num   = self._to_num(self._xs_raw)
            if self._x_type == "datetime":
                da = mdates.num2date(xa)
                db = mdates.num2date(xb)
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
                xarr = np.array(xf)
                yarr = np.array(yf)
                def _interp(xq, _xa=xarr, _ya=yarr):
                    i = int(np.searchsorted(_xa, xq))
                    if i == 0:          return float(_ya[0])
                    if i >= len(_xa):   return float(_ya[-1])
                    x0, x1 = _xa[i-1], _xa[i]
                    y0, y1 = _ya[i-1], _ya[i]
                    return float(y0) if x1 == x0 else float(y0 + (y1-y0)*(xq-x0)/(x1-x0))
                va_v = _interp(xa)
                vb_v = _interp(xb)
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                dy   = vb_v - va_v
                sign = "+" if dy >= 0 else ""
                lines_txt.append(f"{lbl}: {sign}{dy:.4g} {unit}".strip())
            _add(ax1.text((xa + xb) / 2, 0.05, "\n".join(lines_txt),
                          transform=xax_tr, fontsize=7.5, color=COLORS["text"],
                          bbox=dict(boxstyle="round,pad=0.4",
                                    fc=COLORS["surface"], ec=COLORS["accent"],
                                    lw=1.2, alpha=0.92),
                          ha="center", va="bottom", zorder=11))
        if self._cross_v is not None:
            try:
                self._cross_v.remove()
            except Exception:
                pass
            self._cross_v = None
        for _a in self._dot_artists:
            try:
                _a.remove()
            except Exception:
                pass
        self._dot_artists = []
        if self._tooltip is not None:
            try:
                self._tooltip.remove()
            except Exception:
                pass
            self._tooltip = None
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
        if self._cur_a is None and self._cur_b is None:
            ax1.autoscale(enable=True)
            if self._ax2:
                self._ax2.autoscale(enable=True)

    # ── Zoom / Reset ────────────────────────────────────────────────────────

    def reset_zoom(self):
        self._xlim_orig  = None
        self._ylim_orig  = None
        self._y2lim_orig = None
        self._zoom_stack = []
        self._cur_a      = None
        self._cur_b      = None
        self._ab_artists = []
        self._redraw()

    def clear_cursors(self):
        """Rimuove i cursori A/B e aggiorna il bg_cache."""
        for a in self._ab_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._ab_artists = []
        self._cur_a = None
        self._cur_b = None
        try:
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        except Exception:
            pass

    # ── Toggle serie e legenda ────────────────────────────────────────────

    def _rescale_visible(self):
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
            self._ax1.set_ylim(mn - pad, mx + pad)
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
        if col not in getattr(self, "_overlay_lines", {}):
            return
        line = self._overlay_lines[col]
        line.set_visible(not line.get_visible())
        self._rebuild_legend_sidebar()
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)

    def _toggle_all_overlay(self):
        self._overlay_all_vis = not getattr(self, "_overlay_all_vis", True)
        for line in getattr(self, "_overlay_lines", {}).values():
            line.set_visible(self._overlay_all_vis)
        self._rebuild_legend_sidebar()
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)

    def _rebuild_legend_sidebar(self):
        for w in self._legend_rows:
            try:
                w.destroy()
            except Exception:
                pass
        self._legend_rows.clear()
        if not self._series:
            return
        palette = list(_UC_SERIES_PALETTE)
        for col in self._series:
            color     = self._colors.get(col, palette[0])
            lbl       = self._col_meta.get(col, {}).get("label", col)
            unit      = self._col_meta.get(col, {}).get("unit", "")
            is_y2     = col in self._y2_cols
            is_hidden = col in self._hidden
            disp      = lbl if len(lbl) <= 16 else lbl[:15] + "…"
            if unit:
                disp += f" [{unit}]"
            if is_y2:
                disp += " Y2"
            btn = ctk.CTkButton(
                self._legend_panel, text=f"● {disp}",
                fg_color=color if not is_hidden else COLORS["surface2"],
                hover_color=color,
                text_color=COLORS["text"] if not is_hidden else COLORS["text2"],
                font=("Segoe UI", 9), anchor="w",
                height=26, corner_radius=4,
                command=lambda c=col: self._toggle_series(c))
            btn.pack(side="left", padx=3, pady=4)
            self._legend_rows.append(btn)
        # sezione overlay ②
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
                color  = line.get_color()
                is_vis = line.get_visible()
                btn2 = ctk.CTkButton(
                    self._legend_panel, text=f"┄ {col} ②",
                    fg_color=color if is_vis else COLORS["surface2"],
                    hover_color=color,
                    text_color=COLORS["text"] if is_vis else COLORS["text2"],
                    font=("Segoe UI", 9), anchor="w",
                    height=26, corner_radius=4,
                    command=lambda c=col: self._toggle_overlay_line(c))
                btn2.pack(side="left", padx=3, pady=4)
                self._legend_rows.append(btn2)

    # ── Export PNG ────────────────────────────────────────────────────────────

    def export_png(self, filepath):
        ax1 = self._ax1
        h1, l1 = ax1.get_legend_handles_labels()
        h2, l2 = (self._ax2.get_legend_handles_labels() if self._ax2 else ([], []))
        leg = None
        if h1 or h2:
            leg = ax1.legend(
                h1 + h2, l1 + l2,
                loc="upper left", bbox_to_anchor=(1.01, 1),
                borderaxespad=0, fontsize=7.5, framealpha=0.85,
                facecolor=COLORS["surface"], edgecolor=COLORS["border"],
                labelcolor=COLORS["text"])
        self._fig.savefig(
            filepath, dpi=150, bbox_inches="tight",
            bbox_extra_artists=([leg] if leg else None),
            facecolor=self._fig.get_facecolor())
        if leg:
            leg.remove()
        self._drawing = True
        try:
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        finally:
            self._drawing = False
