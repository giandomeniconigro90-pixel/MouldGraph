# -*- coding: utf-8 -*-
"""
mouldgraph.widgets
==================
Widget canvas riutilizzabili: TimelineCanvas, LineChart, PumpCanvas
e InteractivePlotCanvas (matplotlib embedded in CTk).

Estratto da log_analyzer_desktop_live.py senza modifiche alla logica.

Dipendenze interne:
    from .constants import COLORS, _UC_SERIES_PALETTE
    from .csv_parsers import _uc_build_series

Dipendenze esterne:
    tkinter, customtkinter, matplotlib (Agg backend), numpy

NOTA PyInstaller: matplotlib deve essere importato con
    matplotlib.use("Agg") prima di importare backend_tkagg.
    Questo è già fatto nel monolite (entry-point). Qui non
    richiamiamo use() per evitare effetti collaterali su import.
"""

import tkinter as tk
import customtkinter as ctk
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from datetime import datetime

from .constants import COLORS, _UC_SERIES_PALETTE
from .csv_parsers import _uc_build_series


# ---------------------------------------------------------------------------
# Utility scroll
# ---------------------------------------------------------------------------

def _isolate_scroll(scrollable_frame):
    """
    Impedisce al mousewheel di propagarsi al parent quando il cursore
    è dentro il CTkScrollableFrame — fix per Windows/CustomTkinter.
    """
    sf = scrollable_frame
    canvas = sf._parent_canvas if hasattr(sf, "_parent_canvas") else None

    def _block(event):
        if canvas:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _bind_wheel(event=None):
        sf.bind_all("<MouseWheel>", _block)

    def _unbind_wheel(event=None):
        sf.unbind_all("<MouseWheel>")

    sf.bind("<Enter>", _bind_wheel)
    sf.bind("<Leave>", _unbind_wheel)


# ---------------------------------------------------------------------------
# TimelineCanvas
# ---------------------------------------------------------------------------

class TimelineCanvas(tk.Canvas):
    """Bar chart a colonne impilate per la timeline degli eventi log."""

    def __init__(self, master, **kw):
        super().__init__(master, bg=COLORS["surface2"], highlightthickness=0, **kw)
        self.data = {}

    def set_data(self, data):
        self.data = data
        self.after(50, self.redraw)

    def redraw(self):
        self.delete("all")
        if not self.data:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return
        pl, pr, pt, pb = 40, 10, 10, 30
        keys = list(self.data.keys())
        n = len(keys)
        if n == 0:
            return
        max_t = max(v["total"] for v in self.data.values()) or 1
        baw = w - pl - pr
        bw = max(2, baw / n - 2)
        ch = h - pt - pb
        for i in range(5):
            y = pt + (ch * i // 4)
            self.create_line(pl, y, w - pr, y, fill=COLORS["border"], dash=(2, 4))
            self.create_text(pl - 4, y, text=str(int(max_t * (4 - i) / 4)),
                             fill=COLORS["text2"], font=("Segoe UI", 8), anchor="e")
        for i, key in enumerate(keys):
            v = self.data[key]
            x = pl + i * (baw / n) + (baw / n - bw) / 2
            sy = h - pb
            for lvl, color in [
                ("DEBUG", "#1890ff"), ("INFO", "#52c41a"),
                ("WARN", "#faad14"), ("ERROR", "#ff4d4f"),
            ]:
                cnt = v.get(lvl, 0)
                if cnt == 0:
                    continue
                bh = max(2, cnt / max_t * ch)
                y0 = sy - bh
                self.create_rectangle(x, y0, x + bw, sy, fill=color, outline="")
                sy = y0
        step = max(1, n // 8)
        for i in range(0, n, step):
            x = pl + i * (baw / n) + baw / (n * 2)
            self.create_text(x, h - pb + 10, text=keys[i],
                             fill=COLORS["text2"], font=("Segoe UI", 8), anchor="n")
        lx = pl
        for lvl, color in [
            ("ERROR", "#ff4d4f"), ("WARN", "#faad14"),
            ("INFO", "#52c41a"), ("DEBUG", "#1890ff"),
        ]:
            self.create_rectangle(lx, 2, lx + 10, 12, fill=color, outline="")
            self.create_text(lx + 13, 7, text=lvl,
                             fill=COLORS["text2"], font=("Segoe UI", 8), anchor="w")
            lx += 60


# ---------------------------------------------------------------------------
# LineChart (Siemens)
# ---------------------------------------------------------------------------

class LineChart(tk.Canvas):
    """Line chart multi-serie per dati Siemens CSV."""

    def __init__(self, master, **kw):
        super().__init__(master, bg=COLORS["surface2"], highlightthickness=0, **kw)
        self.series = {}   # {label: (color, [values])}
        self.times = []

    def set_data(self, times, series):
        self.times = times
        self.series = series
        self.after(50, self.redraw)

    def redraw(self):
        self.delete("all")
        if not self.series or not self.times:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 20 or h < 20:
            return
        pl, pr, pt, pb = 50, 20, 15, 35
        all_vals = [v for (_c, vals) in self.series.values() for v in vals if v is not None]
        if not all_vals:
            return
        mn_v = min(all_vals)
        mx_v = max(all_vals)
        rng = mx_v - mn_v or 1
        mn_v -= rng * 0.05
        mx_v += rng * 0.05
        rng = mx_v - mn_v
        cw = w - pl - pr
        ch = h - pt - pb
        n = len(self.times)
        for i in range(6):
            y = pt + ch * i // 5
            val = mx_v - (rng * i / 5)
            self.create_line(pl, y, w - pr, y, fill=COLORS["border"], dash=(2, 4))
            self.create_text(pl - 4, y, text=f"{val:.1f}",
                             fill=COLORS["text2"], font=("Segoe UI", 8), anchor="e")
        step = max(1, n // 8)
        for i in range(0, n, step):
            x = pl + i * cw / (n - 1) if n > 1 else pl + cw // 2
            lbl = (self.times[i].strftime("%H:%M:%S")
                   if hasattr(self.times[i], "strftime") else str(self.times[i]))
            self.create_text(x, h - pb + 10, text=lbl,
                             fill=COLORS["text2"], font=("Segoe UI", 8), anchor="n")
        for label, (color, vals) in self.series.items():
            pts = []
            for i, v in enumerate(vals):
                if v is None:
                    continue
                x = pl + i * cw / (n - 1) if n > 1 else pl + cw // 2
                y = pt + ch * (1 - (v - mn_v) / rng)
                pts.append((x, y))
            for i in range(len(pts) - 1):
                self.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                                 fill=color, width=2)
            if pts:
                self.create_oval(pts[-1][0] - 3, pts[-1][1] - 3,
                                 pts[-1][0] + 3, pts[-1][1] + 3,
                                 fill=color, outline="")
        lx = pl
        ly = 5
        for label, (color, _) in self.series.items():
            self.create_rectangle(lx, ly, lx + 12, ly + 10, fill=color, outline="")
            self.create_text(lx + 15, ly + 5, text=label,
                             fill=COLORS["text2"], font=("Segoe UI", 8), anchor="w")
            lx += len(label) * 6 + 30


# ---------------------------------------------------------------------------
# PumpCanvas
# ---------------------------------------------------------------------------

class PumpCanvas(tk.Canvas):
    """Bar chart binario per visualizzare lo stato pompa ON/OFF nel tempo."""

    def __init__(self, master, **kw):
        super().__init__(master, bg=COLORS["surface2"], highlightthickness=0, **kw)
        self.data = []

    def set_data(self, times, vals):
        self.data = list(zip(times, vals))
        self.after(50, self.redraw)

    def redraw(self):
        self.delete("all")
        if not self.data:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 20 or h < 20:
            return
        pl, pr, pt, pb = 50, 20, 10, 30
        n = len(self.data)
        cw = w - pl - pr
        ch = h - pt - pb
        bw = max(2, cw / n - 1)
        for i, (ts, val) in enumerate(self.data):
            x = pl + i * cw / n
            color = "#52c41a" if val == 1 else "#ff4d4f"
            self.create_rectangle(x, pt, x + bw, pt + ch, fill=color, outline="")
        self.create_text(pl - 4, pt + ch // 4, text="ON",
                         fill="#52c41a", font=("Segoe UI", 9, "bold"), anchor="e")
        self.create_text(pl - 4, pt + ch * 3 // 4, text="OFF",
                         fill="#ff4d4f", font=("Segoe UI", 9, "bold"), anchor="e")
        step = max(1, n // 8)
        for i in range(0, n, step):
            ts = self.data[i][0]
            x = pl + i * cw / n + bw / 2
            lbl = ts.strftime("%H:%M:%S") if hasattr(ts, "strftime") else str(ts)
            self.create_text(x, h - pb + 10, text=lbl,
                             fill=COLORS["text2"], font=("Segoe UI", 8), anchor="n")


# ---------------------------------------------------------------------------
# InteractivePlotCanvas
# ---------------------------------------------------------------------------

class InteractivePlotCanvas:
    """
    Wrapper matplotlib con hover crosshair, zoom rotella, pan drag,
    cursori A/B, overlay secondo CSV, toggle serie.
    """

    def __init__(self, master, height: int = 320):
        self.master = master
        self.height = height
        self._rows = []
        self._xs_raw = []
        self._xs_num_cache = None
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
        self._overlay_lines   = {}
        self._overlay_all_vis = True
        self._zoom_stack = []
        self._cur_a = None
        self._cur_b = None
        self._ab_artists = []
        self.show_markers = True
        self._ranges = []
        self._drawing = False
        self._live_user_zoomed = False
        self._live_data_fp = None
        self._needs_full_redraw = False
        self._scroll_timer = None
        self._bg_cache = None

        self._frame = ctk.CTkFrame(master, fg_color=COLORS["surface"], corner_radius=8)
        self._frame.pack(fill="both", expand=True, padx=0, pady=0)

        self._info_var = tk.StringVar(value="")
        self._info_lbl = ctk.CTkLabel(
            self._frame, textvariable=self._info_var,
            font=("Courier New", 10), text_color=COLORS["accent2"],
            fg_color=COLORS["surface2"], corner_radius=4, anchor="w")
        self._info_lbl.pack(fill="x", padx=6, pady=(4, 0))
        self._info_lbl.configure(fg_color="transparent")

        self._plot_area = ctk.CTkFrame(self._frame, fg_color="transparent")
        self._plot_area.pack(fill="both", expand=True)

        self._legend_panel = ctk.CTkScrollableFrame(
            self._frame, fg_color=COLORS["surface2"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"],
            orientation="horizontal", height=40, corner_radius=4)
        self._legend_panel.pack(fill="x", padx=4, pady=(2, 4))
        self._legend_rows = []

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

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

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
            self._cross_v = None
            self._tooltip = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_data(self, xs_raw, series, x_type, col_meta,
                 y2_cols=None, colors=None, x_label=""):
        self._xs_raw        = xs_raw
        self._xs_num_cache  = None
        self._series        = series
        self._x_type        = x_type
        self._col_meta      = col_meta
        self._y2_cols       = set(y2_cols or [])
        self._x_label       = x_label
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

    def set_ranges(self, ranges):
        self._ranges = ranges or []
        self._redraw()
        self._rebuild_legend_sidebar()

    def clear(self):
        self._xs_raw = []
        self._xs_num_cache = None
        self._series = {}
        self._redraw()

    def get_frame(self):
        return self._frame

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

    # ------------------------------------------------------------------
    # Overlay secondo CSV
    # ------------------------------------------------------------------

    def _overlay_second_csv(self, rows2, x_col, cols, colors2, col_meta):
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
            lbl = f"{col} ②"
            line, = self._ax1.plot(xf, yf, color=color, linewidth=1.2,
                                   linestyle="--", label=lbl, zorder=2, alpha=0.85)
            self._overlay_lines[col] = line
        self._xs_num_cache = None
        self._fig.tight_layout(pad=1.2)
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        self._rebuild_legend_sidebar()

    # ------------------------------------------------------------------
    # Live update
    # ------------------------------------------------------------------

    def update_live(self, xs_raw, series, x_type, col_meta, colors=None, background=False):
        needs_full = (
            getattr(self, "_needs_full_redraw", False)
            or set(series.keys()) != set(self._lines.keys())
            or not self._lines
        )
        if needs_full:
            self._needs_full_redraw = False
            self.set_data(xs_raw, series, x_type, col_meta, colors=colors)
            return

        new_fp = (
            len(xs_raw),
            tuple((k, len(v), v[-1] if v else None) for k, v in series.items()),
        )
        if new_fp == self._live_data_fp:
            return
        self._live_data_fp = new_fp

        self._xs_raw        = xs_raw
        self._xs_num_cache  = None
        self._series        = series
        self._x_type        = x_type
        self._col_meta      = col_meta

        if colors:
            for col, c in colors.items():
                if col in self._colors and self._colors[col] != c:
                    self._colors[col] = c
                    if col in self._lines:
                        self._lines[col].set_color(c)

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

    # ------------------------------------------------------------------
    # Redraw interno
    # ------------------------------------------------------------------

    def _redraw(self):
        self._overlay_lines = {}
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
                self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
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
            ax1.set_xlabel(self._x_label or "Indice", color=COLORS["text2"], fontsize=8)

        for _c, _l in self._lines.items():
            _l.set_visible(_c not in self._hidden)

        for rule in self._ranges:
            col   = rule.get("col")
            lo    = rule.get("lo")
            hi    = rule.get("hi")
            if col in self._hidden:
                continue
            color = self._colors.get(col, COLORS["accent"])
            ax = self._ax2 if (self._ax2 and col in self._y2_cols) else ax1
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

    def _rebuild_legend_sidebar(self):
        """Svuota e ricostruisce i bottoni toggle nella sidebar legenda."""
        for w in self._legend_rows:
            try:
                w.destroy()
            except Exception:
                pass
        self._legend_rows = []
        all_cols = list(self._lines.keys()) + [f"{c} ②" for c in self._overlay_lines]
        for col in all_cols:
            is_overlay = col.endswith(" ②")
            real_col = col[:-2] if is_overlay else col
            color = (self._overlay_lines[real_col].get_color()
                     if is_overlay else self._colors.get(real_col, COLORS["accent"]))
            label = self._col_meta.get(real_col, {}).get("label", real_col)
            full_lbl = f"{label} ②" if is_overlay else label

            def _make_toggle(c=real_col, ov=is_overlay):
                def _toggle():
                    if ov:
                        ln = self._overlay_lines.get(c)
                        if ln:
                            ln.set_visible(not ln.get_visible())
                    else:
                        if c in self._hidden:
                            self._hidden.discard(c)
                        else:
                            self._hidden.add(c)
                        for _c, _l in self._lines.items():
                            _l.set_visible(_c not in self._hidden)
                    self._rescale_visible()
                    self._drawing = True
                    try:
                        self._canvas.draw()
                        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
                    finally:
                        self._drawing = False
                return _toggle

            btn = ctk.CTkButton(
                self._legend_panel,
                text=full_lbl,
                width=max(60, len(full_lbl) * 7 + 20),
                height=28,
                fg_color=color,
                hover_color=COLORS["border"],
                text_color=COLORS["text"],
                font=("Segoe UI", 10),
                command=_make_toggle(),
            )
            btn.pack(side="left", padx=3, pady=2)
            self._legend_rows.append(btn)

    def _rescale_visible(self):
        ax1 = self._ax1
        vis_y1 = [col for col in self._lines
                  if col not in self._hidden and col not in self._y2_cols]
        if vis_y1:
            all_y = [y for col in vis_y1
                     for y in (self._series.get(col) or []) if y is not None]
            if all_y:
                pad = (max(all_y) - min(all_y)) * 0.05 or 1
                ax1.set_ylim(min(all_y) - pad, max(all_y) + pad)
        if self._ax2:
            vis_y2 = [col for col in self._lines
                      if col not in self._hidden and col in self._y2_cols]
            if vis_y2:
                all_y2 = [y for col in vis_y2
                          for y in (self._series.get(col) or []) if y is not None]
                if all_y2:
                    pad2 = (max(all_y2) - min(all_y2)) * 0.05 or 1
                    self._ax2.set_ylim(min(all_y2) - pad2, max(all_y2) + pad2)

    # ------------------------------------------------------------------
    # Helpers coordinate
    # ------------------------------------------------------------------

    def _to_num(self, xs):
        if not xs:
            return []
        if self._x_type == "datetime":
            return [
                mdates.date2num(x) if isinstance(x, datetime) else None
                for x in xs
            ]
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
        span_days = max(valid) - min(valid)
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

    # ------------------------------------------------------------------
    # Hover / crosshair
    # ------------------------------------------------------------------

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
        idx = int(np.nanargmin(np.abs(xs_arr - xm)))
        x_snap = xs_num[idx]
        if x_snap is None:
            return
        if self._x_type == "datetime" and isinstance(self._xs_raw[idx], datetime):
            x_str = self._xs_raw[idx].strftime("%d/%m/%Y %H:%M:%S")
        else:
            x_str = (f"{self._xs_raw[idx]:.4g}"
                     if isinstance(self._xs_raw[idx], float)
                     else f"{self._xs_raw[idx]}")

        parts = [f"X: {x_str}"]
        for col, ys in self._series.items():
            if col in self._hidden:
                continue
            if idx < len(ys) and ys[idx] is not None:
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                parts.append(f"{lbl}: {ys[idx]:.4g}{(' ' + unit) if unit else ''}")
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

        if self._cross_v is None:
            self._cross_v, = ax1.plot(
                [x_snap, x_snap], ylim,
                color=COLORS["accent2"], linewidth=0.8,
                linestyle="--", zorder=10, animated=True)
        else:
            self._cross_v.set_xdata([x_snap, x_snap])
            self._cross_v.set_ydata(ylim)
        ax1.draw_artist(self._cross_v)

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

        tip_lines = [f"X: {x_str}"]
        for col, ys in self._series.items():
            if col in self._hidden:
                continue
            if idx < len(ys) and ys[idx] is not None:
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                tip_lines.append(f"{lbl}: {ys[idx]:.4g}{(' ' + unit) if unit else ''}")

        tip_txt = "\n".join(tip_lines)
        x_frac = (x_snap - xlim[0]) / (xlim[1] - xlim[0]) if xlim[1] != xlim[0] else 0.5
        ha = "left" if x_frac < 0.75 else "right"
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

    # ------------------------------------------------------------------
    # Scroll (zoom)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Press / release / pan
    # ------------------------------------------------------------------

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
        dx = self._pan_start - event.xdata
        new_min = self._pan_xlim[0] + dx
        new_max = self._pan_xlim[1] + dx
        xs_num = (self._xs_num_cache if self._xs_num_cache is not None
                  else self._to_num(self._xs_raw))
        valid = [x for x in xs_num if x is not None]
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

    # ------------------------------------------------------------------
    # Cursori A/B
    # ------------------------------------------------------------------

    def _redraw_cursors_ab(self):
        if not self._ax1:
            return
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
            xa, xb = sorted([self._cur_a, self._cur_b])
            xs_num = self._to_num(self._xs_raw)
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
                    if i == 0: return float(_ya[0])
                    if i >= len(_xa): return float(_ya[-1])
                    x0, x1 = _xa[i - 1], _xa[i]
                    y0, y1 = _ya[i - 1], _ya[i]
                    return float(y0) if x1 == x0 else float(y0 + (y1 - y0) * (xq - x0) / (x1 - x0))

                va_v = _interp(xa)
                vb_v = _interp(xb)
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                dy = vb_v - va_v
                sign = "+" if dy >= 0 else ""
                lines_txt.append(f"{lbl}: {sign}{dy:.4g} {unit}".strip())

            ylim = ax1.get_ylim()
            xlim = ax1.get_xlim()
            _add(ax1.text(
                (xa + xb) / 2, 0.05,
                "\n".join(lines_txt),
                transform=xax_tr,
                fontsize=7.5, color=COLORS["text"],
                bbox=dict(boxstyle="round,pad=0.4",
                          fc=COLORS["surface"], ec=COLORS["accent"],
                          lw=1.2, alpha=0.92),
                ha="center", va="bottom", zorder=11))

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
