# -*- coding: utf-8 -*-
import os, re, csv, math
from collections import defaultdict
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from colors import COLORS

# ---------------------------------------------------------------------------
# Palette colori PDF (usata da _pdf_setup_ax, _pdf_temp, _pdf_forza, ecc.)
# ---------------------------------------------------------------------------
_PC = {
    "bg":        "#dff0d8",   # sfondo fascia verde OK
    "grid":      "#dddddd",   # griglia assi
    "set_temp":  "#e5672c",   # linea SET temperatura
    "set_forza": "#e5672c",   # linea SET / SPC forza
    "lmax":      "#cc0000",   # linea LMax
    "lmin":      "#0055cc",   # linea LMin
    1:           "#407da5",
    2:           "#e5672c",
    3:           "#659346",
    4:           "#e7b73b",
    5:           "#9b59b6",
    6:           "#1abc9c",
    7:           "#e74c3c",
    8:           "#34495e",
}

# ---------------------------------------------------------------------------
# Profili stampo – parametri grafici per generate_lamborghini_pdf
# ---------------------------------------------------------------------------
_PROFILES = {
    "Front Firewall": dict(
        persico         = True,
        ricetta         = "3",
        teorico_sec     = 1496,
        skip_seconds    = 0,
        temp_set_sup    = 130.0,
        temp_set_inf    = 128.0,
        temp_y          = (100, 160),
        temp_yticks     = [100, 110, 120, 130, 140, 150, 160],
        temp_range      = (130, 150),
        forza_spc       = 6500.0,
        forza_delta     = 250.0,
        forza_y         = (6000, 6800),
        forza_yticks    = [6000, 6100, 6200, 6300, 6400, 6500, 6600, 6700, 6800],
        forza_range     = (6250, 6750),
        forza_legend_loc= "lower right",
        vuoto_y         = (-1000, 0),
        vuoto_yticks    = [-1000, -900, -800, -700, -600, -500, -400, -300, -200, -100, 0],
        vuoto_range     = (-1000, -200),
        posiz_y         = (-0.35, 0.05),
        posiz_yticks    = [-0.35, -0.30, -0.25, -0.20, -0.15, -0.10, -0.05, 0.0, 0.05],
        x_max           = 1496,
        x_ticks         = list(range(0, 1497, 150)),
        x_ticks_tv      = list(range(44, 1453, 44)),
        x_ticks_pos     = list(range(11, 1464, 44)),
        x_ticks_forza   = list(range(44, 1497, 44)),
        x_ticks_vac_sup = list(range(44, 1453, 44)),
        x_ticks_vac_inf = list(range(44, 1453, 44)),
    ),
    "Central Cofango": dict(
        persico         = True,
        ricetta         = "5",
        teorico_sec     = 1200,
        skip_seconds    = 0,
        temp_set_sup    = 130.0,
        temp_set_inf    = 128.0,
        temp_y          = (100, 160),
        temp_yticks     = [100, 110, 120, 130, 140, 150, 160],
        temp_range      = (130, 150),
        forza_spc       = 6500.0,
        forza_delta     = 250.0,
        forza_y         = (6000, 6800),
        forza_yticks    = [6000, 6100, 6200, 6300, 6400, 6500, 6600, 6700, 6800],
        forza_range     = (6250, 6750),
        forza_legend_loc= "lower right",
        vuoto_y         = (-1000, 0),
        vuoto_yticks    = [-1000, -900, -800, -700, -600, -500, -400, -300, -200, -100, 0],
        vuoto_range     = (-1000, -200),
        posiz_y         = (-0.35, 0.05),
        posiz_yticks    = [-0.35, -0.30, -0.25, -0.20, -0.15, -0.10, -0.05, 0.0, 0.05],
        x_max           = 1200,
        x_ticks         = list(range(0, 1201, 120)),
        x_ticks_tv      = list(range(44, 1201, 44)),
        x_ticks_pos     = list(range(11, 1212, 44)),
        x_ticks_forza   = list(range(44, 1201, 44)),
        x_ticks_vac_sup = list(range(44, 1201, 44)),
        x_ticks_vac_inf = list(range(44, 1201, 44)),
    ),
    "Side Cofango Inner": dict(
        persico         = True,
        ricetta         = "6",
        teorico_sec     = 1200,
        skip_seconds    = 0,
        temp_set_sup    = 130.0,
        temp_set_inf    = 128.0,
        temp_y          = (100, 160),
        temp_yticks     = [100, 110, 120, 130, 140, 150, 160],
        temp_range      = (130, 150),
        forza_spc       = 6500.0,
        forza_delta     = 250.0,
        forza_y         = (6000, 6800),
        forza_yticks    = [6000, 6100, 6200, 6300, 6400, 6500, 6600, 6700, 6800],
        forza_range     = (6250, 6750),
        forza_legend_loc= "lower right",
        vuoto_y         = (-1000, 0),
        vuoto_yticks    = [-1000, -900, -800, -700, -600, -500, -400, -300, -200, -100, 0],
        vuoto_range     = (-1000, -200),
        posiz_y         = (-0.35, 0.05),
        posiz_yticks    = [-0.35, -0.30, -0.25, -0.20, -0.15, -0.10, -0.05, 0.0, 0.05],
        x_max           = 1200,
        x_ticks         = list(range(0, 1201, 120)),
        x_ticks_tv      = list(range(44, 1201, 44)),
        x_ticks_pos     = list(range(11, 1212, 44)),
        x_ticks_forza   = list(range(44, 1201, 44)),
        x_ticks_vac_sup = list(range(44, 1201, 44)),
        x_ticks_vac_inf = list(range(44, 1201, 44)),
    ),
    "Inner Tub": dict(
        persico         = False,
        ricetta         = "1",
        teorico_sec     = 1800,
        skip_seconds    = 0,
        temp_set_sup    = 145.0,
        temp_set_inf    = 143.0,
        temp_y          = (100, 180),
        temp_yticks     = [100, 110, 120, 130, 140, 150, 160, 170, 180],
        forza_spc       = 6500.0,
        forza_delta     = 300.0,
        forza_y         = (5800, 7000),
        forza_yticks    = [5800, 6000, 6200, 6400, 6600, 6800, 7000],
        forza_legend_loc= "lower right",
        vuoto_y         = (0.0, 1.2),
        vuoto_yticks    = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2],
        posiz_y         = (-350, 50),
        posiz_yticks    = list(range(-350, 51, 50)),
        x_max           = 1800,
        x_ticks         = list(range(0, 1801, 180)),
    ),
    "Polecrasher": dict(
        persico         = False,
        ricetta         = "2",
        teorico_sec     = 1500,
        skip_seconds    = 0,
        temp_set_sup    = 140.0,
        temp_set_inf    = 138.0,
        temp_y          = (100, 170),
        temp_yticks     = [100, 110, 120, 130, 140, 150, 160, 170],
        forza_spc       = 6500.0,
        forza_delta     = 300.0,
        forza_y         = (5800, 7200),
        forza_yticks    = [5800, 6000, 6200, 6400, 6600, 6800, 7000, 7200],
        forza_legend_loc= "lower right",
        vuoto_y         = (0.0, 1.2),
        vuoto_yticks    = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2],
        posiz_y         = (-350, 50),
        posiz_yticks    = list(range(-350, 51, 50)),
        x_max           = 1500,
        x_ticks         = list(range(0, 1501, 150)),
    ),
    "Tub Floor Shell": dict(
        persico         = False,
        ricetta         = "4",
        teorico_sec     = 1400,
        skip_seconds    = 0,
        temp_set_sup    = 135.0,
        temp_set_inf    = 133.0,
        temp_y          = (100, 170),
        temp_yticks     = [100, 110, 120, 130, 140, 150, 160, 170],
        forza_spc       = 6500.0,
        forza_delta     = 300.0,
        forza_y         = (5800, 7200),
        forza_yticks    = [5800, 6000, 6200, 6400, 6600, 6800, 7000, 7200],
        forza_legend_loc= "lower right",
        vuoto_y         = (0.0, 1.2),
        vuoto_yticks    = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2],
        posiz_y         = (-350, 50),
        posiz_yticks    = list(range(-350, 51, 50)),
        x_max           = 1400,
        x_ticks         = list(range(0, 1401, 140)),
    ),
}

# ---------------------------------------------------------------------------
# Mappa presse -> stampi disponibili (usata dalla UI, tab Grafici)
# ---------------------------------------------------------------------------
PRESSASTAMPI = {
    "Persico 2500T": [
        "Front Firewall",
        "Central Cofango",
        "Side Cofango Inner",
    ],
    "Cannon 5000T": [
        "Inner Tub",
        "Polecrasher",
        "Tub Floor Shell",
    ],
}

# ---------------------------------------------------------------------------
# Alias pubblici richiesti da app_main.py
# ---------------------------------------------------------------------------
PROFILES = _PROFILES


def generate_plant_pdf(rows, headers, col_meta,
                       x_col, y_cols, y2_cols,
                       output_path,
                       plant_name="Impianto",
                       logo_path=None,
                       notes="",
                       rows2=None, cols2=None,
                       colors2=None, col_meta2=None):
    if not rows:
        raise ValueError("Nessun dato disponibile per generare il PDF.")
    if not y_cols:
        raise ValueError("Seleziona almeno una colonna Y prima di generare il PDF.")
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    FW, FH = 8.27, 11.69
    xs_raw, series, x_type = _uc_build_series(rows, x_col, y_cols, col_meta)

    def to_num(xs):
        if x_type == "datetime":
            return [mdates.date2num(x) if isinstance(x, datetime) else None for x in xs]
        return [float(x) if x is not None else None for x in xs]

    xs_num = to_num(xs_raw)

    def clean(xs, ys):
        pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
        return ([p[0] for p in pairs], [p[1] for p in pairs]) if pairs else ([], [])

    all_stats = {}
    for col in y_cols:
        vals = []
        for r in rows:
            try:
                vals.append(float(r.get(col, "").replace(",", ".")))
            except Exception:
                pass
        if vals:
            mean = sum(vals) / len(vals)
            std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
            anom_count = sum(1 for v in vals if std > 0 and abs(v - mean) > 2.5 * std)
            all_stats[col] = {"n": len(vals), "min": min(vals), "max": max(vals),
                              "mean": mean, "std": std, "anomalies": anom_count}
    # statistiche CSV2 ②
    all_stats2 = {}
    if rows2 and cols2:
        for col in cols2:
            vals2 = []
            for r in rows2:
                _v = r.get(col, "")
                try:
                    vals2.append(float((str(_v) if not isinstance(_v, str) else _v).replace(",", ".")))
                except Exception:
                    pass
            if vals2:
                _m2 = sum(vals2) / len(vals2)
                _s2 = (sum((v - _m2)**2 for v in vals2) / len(vals2)) ** 0.5
                all_stats2[col] = {"n": len(vals2), "min": min(vals2),
                                   "max": max(vals2), "mean": _m2, "std": _s2}

    groups = _plant_group_series(y_cols, y2_cols, col_meta)
    ts_first = xs_raw[0]  if xs_raw  else None
    ts_last  = xs_raw[-1] if xs_raw  else None

    def fmt_ts(t):
        if isinstance(t, datetime):
            return t.strftime("%d/%m/%Y %H:%M:%S")
        return str(t) if t is not None else "—"

    dur_str = "—"
    if isinstance(ts_first, datetime) and isinstance(ts_last, datetime):
        sec = int((ts_last - ts_first).total_seconds())
        h, rem = divmod(sec, 3600)
        m, s   = divmod(rem, 60)
        dur_str = f"{h:02d}:{m:02d}:{s:02d}  ({sec} sec)"

    meta_p1 = [
        ("Impianto",        plant_name),
        ("File CSV",        os.path.basename(output_path)),
        ("Campioni",        str(len(rows))),
        ("Colonne analiz.", str(len(y_cols))),
        ("Inizio",          fmt_ts(ts_first)),
        ("Fine",            fmt_ts(ts_last)),
        ("Durata",          dur_str),
    ]
    if notes:
        meta_p1.append(("Note", notes[:80]))

    graphs_per_page = 2
    n_graph_pages   = max(1, math.ceil(len(groups) / graphs_per_page))
    total_pages     = 1 + n_graph_pages + 1
    colors = _plant_pdf_colors(y_cols)

    with PdfPages(output_path) as pdf:
        # PAG. 1 — copertina
        fig = plt.figure(figsize=(FW, FH), facecolor="white")
        subtitle = (f"Analisi parametri operativi  ·  "
                    f"{len(rows)} campioni  ·  {len(y_cols)} serie")
        plot_top = _plant_pdf_header(
            fig, title=plant_name, subtitle=subtitle, logo_path=logo_path,
            page_num=1, total_pages=total_pages,
            generated_at=generated_at, meta_rows=meta_p1)
        tbl_top = max(0.10, plot_top - 0.05)
        ax_tbl = fig.add_axes([0.05, 0.05, 0.90, max(0.10, tbl_top - 0.10)])
        ax_tbl.axis("off")
        col_labels = ["Serie", "Tipo / Unità", "N", "Min", "Max", "Media", "Dev.Std"]
        table_data = []
        for col in y_cols:
            m   = col_meta.get(col, {})
            ys  = [v for v in series.get(col, []) if v is not None]
            if not ys:
                continue
            mean_v = sum(ys) / len(ys)
            std_v  = (sum((v - mean_v) ** 2 for v in ys) / len(ys)) ** 0.5
            table_data.append([
                col[:28],
                f"{m.get('label', col)[:20]} {m.get('unit', '')}".strip(),
                str(len(ys)),
                f"{min(ys):.4g}",
                f"{max(ys):.4g}",
                f"{mean_v:.4g}",
                f"{std_v:.4g}",
            ])
        if table_data:
            tbl = ax_tbl.table(
                cellText=table_data,
                colLabels=col_labels,
                loc="upper center",
                cellLoc="center"
            )
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(7.5)
            tbl.scale(1, 1.45)
            for j in range(len(col_labels)):
                tbl[0, j].set_facecolor("#333")
                tbl[0, j].set_text_props(color="white", fontweight="bold")
            for i in range(1, len(table_data) + 1):
                bg = "#f7f7f7" if i % 2 == 0 else "white"
                for j in range(len(col_labels)):
                    tbl[i, j].set_facecolor(bg)
                    tbl[i, j].set_edgecolor("#ddd")
        else:
            ax_tbl.text(0.5, 0.5, "Nessun dato numerico disponibile",
                        ha="center", va="center", fontsize=10, color="#888",
                        transform=ax_tbl.transAxes)
        if notes:
            fig.text(0.05, 0.03, f"Note: {notes}", fontsize=7, color="#777",
                     style="italic", va="bottom")
        pdf.savefig(fig, bbox_inches="tight", dpi=150)
        plt.close(fig)

        # PAG. 2..N — grafici per gruppo
        page_num = 2
        i = 0
        while i < len(groups):
            fig = plt.figure(figsize=(FW, FH), facecolor="white")
            _plant_pdf_header(fig, title=plant_name,
                              subtitle="Grafici parametri operativi",
                              logo_path=logo_path, page_num=page_num,
                              total_pages=total_pages,
                              generated_at=generated_at, meta_rows=None)
            page_groups = groups[i: i + graphs_per_page]
            n_on_page   = len(page_groups)
            ax_h   = 0.30 if n_on_page == 2 else 0.50
            ax_top = [0.88 - j * (ax_h + 0.12) for j in range(n_on_page)]
            for j, (g_title, g_unit, g_cols, _is_y2) in enumerate(page_groups):
                y1_c = [c for c in g_cols if c not in y2_cols]
                y2_c = [c for c in g_cols if c in y2_cols]
                ax1 = fig.add_axes([0.07, ax_top[j] - ax_h, 0.86, ax_h])
                all_ys = [v for c in y1_c
                          for _, v in zip(*clean(xs_num, series.get(c, [])))
                          if v is not None]
                _plant_pdf_setup_ax(ax1, g_title, g_unit, xs_num, all_ys, x_type)
                for col in y1_c:
                    xf, yf = clean(xs_num, series.get(col, []))
                    if not xf:
                        continue
                    lbl  = col_meta.get(col, {}).get("label", col)
                    unit = col_meta.get(col, {}).get("unit", "")
                    ax1.plot(xf, yf, color=colors[col], linewidth=0.9,
                             label=f"{lbl} [{unit}]" if unit else lbl, zorder=3)
                if y2_c:
                    ax2 = ax1.twinx()
                    ax2.set_facecolor("none")
                    ax2.tick_params(labelsize=7, colors="#9c27b0")
                    ax2.spines["right"].set_edgecolor("#9c27b0")
                    for col in y2_c:
                        xf, yf = clean(xs_num, series.get(col, []))
                        if not xf:
                            continue
                        lbl  = col_meta.get(col, {}).get("label", col)
                        unit = col_meta.get(col, {}).get("unit", "")
                        ax2.plot(xf, yf, color=colors[col], linewidth=0.9,
                                 linestyle="--",
                                 label=f"{lbl} [{unit}] →Y2" if unit else f"{lbl} →Y2",
                                 zorder=3)
                    h2, l2 = ax2.get_legend_handles_labels()
                    ax2.legend(h2, l2, loc="upper right", fontsize=6.5, framealpha=0.8)
                if rows2 and cols2:
                    _xs2, _s2, _xt2 = _uc_build_series(
                        rows2, x_col, cols2, col_meta2 or {})
                    _xn2 = to_num(_xs2)
                    _pal2 = ["#ff6b6b","#ffd93d","#6bcb77","#4d96ff",
                             "#c77dff","#f9844a","#90e0ef","#f15bb5"]
                    for _j2, _c2 in enumerate(cols2):
                        _xf2, _yf2 = clean(_xn2, _s2.get(_c2, []))
                        if not _xf2:
                            continue
                        _col2 = (colors2 or {}).get(_c2, _pal2[_j2 % 8])
                        ax1.plot(_xf2, _yf2, color=_col2, linewidth=0.9,
                                 linestyle="--", label=f"{_c2} ③",
                                 zorder=2, alpha=0.85)
                _plant_pdf_legend(ax1, ncol=5)
            pdf.savefig(fig, bbox_inches="tight", dpi=150)
            plt.close(fig)
            page_num += 1
            i += graphs_per_page

        # ULTIMA PAG. — statistiche
        fig = plt.figure(figsize=(FW, FH), facecolor="white")
        _plant_pdf_header(fig, title=plant_name, subtitle="Riepilogo statistico",
                          logo_path=logo_path, page_num=total_pages,
                          total_pages=total_pages,
                          generated_at=generated_at, meta_rows=None)
        _plant_pdf_stats_table(fig, y_cols, col_meta, all_stats, top_y=0.92,
                               stats2=all_stats2, cols2=cols2, col_meta2=col_meta2)
        pdf.savefig(fig, bbox_inches="tight", dpi=150)
        plt.close(fig)


# -- PDF GENERATION HELPERS ----------------------------------

def _pdf_parse_csv(filepath):
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
    hdr = lines[start]
    data_sep = ";" if (start+1 < len(lines) and ";" in lines[start+1]) else ","
    if data_sep == ";":
        headers = [h.strip() for h in hdr.split(",")]
        rows = []
        for l in lines[start+1:]:
            parts = l.split(";")
            rows.append({h: parts[i].strip().replace(",", ".") if i < len(parts) else ""
                         for i, h in enumerate(headers)})
    else:
        import io as _io
        rows = list(csv.DictReader(_io.StringIO("\n".join(lines[start:]))))
    TSFMTS = ["%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
              "%d_%m_%Y_%H_%M_%S", "%d/%m/%Y_%H_%M_%S", "%Y-%m-%dT%H:%M:%S.%f"]
    def pt(s):
        s = s.strip().rstrip("Z")
        for fmt in TSFMTS:
            try: return datetime.strptime(s, fmt)
            except Exception: pass
        return None
    t0 = None; data = defaultdict(list); tslist = []
    for r in rows:
        ts = pt(r.get("Timestamp", ""))
        if ts is None: continue
        if t0 is None: t0 = ts
        tslist.append(ts); sec = (ts - t0).total_seconds()
        try: val = float(r.get("Valore", "").replace(",", "."))
        except Exception: continue
        try: ss = r.get("Setpoint", "").strip().replace(",", "."); sp = float(ss) if ss else None
        except Exception: sp = None
        try: step = int(r.get("Step", 0))
        except Exception: step = 0
        data[r.get("Parametro", "").strip()].append((sec, val, step, sp))
    tss = tslist[0] if tslist else None; tse = tslist[-1] if tslist else None
    dur = int((tse - tss).total_seconds()) if tss and tse else 0
    meta = {"idciclo": rows[0].get("IdCiclo", "") if rows else "",
            "partite": ", ".join(sorted(set(r.get("Partita", "") for r in rows))),
            "operatore": rows[0].get("Operatore", "") if rows else "",
            "materiale": ", ".join(sorted(set(r.get("Materiale", "") for r in rows))),
            "tsraw": rows[0].get("Timestamp", "") if rows else "",
            "tsstart": tss, "tsend": tse, "dursec": dur}
    return data, meta

_LK = dict(fontsize=7.0, framealpha=0.9, edgecolor="#ccc", handlelength=1.8,
           handleheight=0.9, borderpad=0.6, labelspacing=0.3)

def _pdf_fmt_date(ts):
    try: return datetime.strptime(ts.rstrip("Z"), "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y %H:%M:%S")
    except Exception: return ts

def _pdf_fmt_ts(ts):
    if ts is None: return ""
    try: return ts.strftime("%d/%m/%Y %H:%M:%S")
    except Exception: return ""

def _pdf_setup_ax(ax, title, ylabel, ylim, yticks, xticks, xmax, draw_bg=True, bg_xmax=None, bg_ymax=None):
    if draw_bg:
        yr = ylim[1] - ylim[0]
        y_top = bg_ymax if bg_ymax is not None else ylim[0] + yr * 206.36/309.54
        if bg_xmax is not None:
            ax.fill_between([0, bg_xmax], ylim[0], y_top, color=_PC["bg"], zorder=0, linewidth=0)
        else:
            ax.axhspan(ylim[0], y_top, color=_PC["bg"], zorder=0)
    ax.set_facecolor("white"); ax.set_xlim(0, xmax); ax.set_ylim(ylim[0], ylim[1])
    ax.set_yticks(yticks)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,f: f"{v:.1f}" if v!=int(v) else f"{int(v)}"))
    ax.set_xticks(xticks); ax.tick_params(axis="both", labelsize=7, length=3, color="#404040")
    ax.set_xlabel("sec", fontsize=7, labelpad=1); ax.set_ylabel(ylabel, fontsize=7, labelpad=2)
    ax.set_title(title, fontsize=9, fontweight="bold", pad=4, color="#111")
    ax.grid(True, linestyle="-", linewidth=0.3, color=_PC["grid"], alpha=1.0, zorder=1)
    for sp in ax.spines.values(): sp.set_edgecolor("#888"); sp.set_linewidth(0.5)

def _pdf_temp(ax, data, params, setval, title, pr):
    _pdf_setup_ax(ax, title, "", pr["temp_y"], pr["temp_yticks"], pr["x_ticks"], pr["x_max"])
    ax.axhline(setval, color=_PC["set_temp"], lw=0.8, zorder=4, label="SET")
    for i, p in enumerate(params):
        if p in data:
            pts = sorted(data[p]); ys = [d[1] for d in pts]
            if not all(abs(v) < 0.01 for v in ys):
                ax.plot([d[0] for d in pts], ys, color=_PC[i+1], lw=0.7, zorder=3, label=p)
                continue
        ax.plot([], [], color=_PC[i+1], lw=0.7, label=p)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=1+len(params), **_LK)

def _pdf_posiz(ax, data, params, pr):
    _pdf_setup_ax(ax, "POSIZIONE [mm]", "mm", pr["posiz_y"], pr["posiz_yticks"], pr["x_ticks"], pr["x_max"], draw_bg=False)
    for i, p in enumerate(params):
        if p in data:
            pts = sorted(data[p])
            if pts:
                ax.plot([d[0] for d in pts], [d[1] for d in pts], color=_PC[i+1], lw=0.7, zorder=3, label=p)
                continue
        ax.plot([], [], color=_PC[i+1], lw=0.7, label=p)
    ax.axhline(0, color="#999", lw=0.4, linestyle="--", zorder=2)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=len(params), **_LK)

def _pdf_forza(ax, data, params, pr):
    _pdf_setup_ax(ax, "FORZA [kN]", "kN", pr["forza_y"], pr["forza_yticks"], pr["x_ticks"], pr["x_max"], draw_bg=False)
    ref = next((p for p in params if p in data), None)
    has_set = False
    if ref:
        pts = sorted(data[ref])
        xs = np.array([d[0] for d in pts if d[3] is not None])
        sps = np.array([d[3] for d in pts if d[3] is not None])
        if len(xs):
            has_set = True
            ax.plot(xs, sps, color=_PC["set_forza"], lw=0.8, zorder=5, label="Set")
            ax.plot(xs, sps + pr["forza_delta"], color=_PC["lmax"], lw=1.0, zorder=5, label="LMax")
            ax.plot(xs, sps - pr["forza_delta"], color=_PC["lmin"], lw=1.0, zorder=5, label="LMin")
    if not has_set:
        ax.plot([], [], color=_PC["set_forza"], lw=0.8, label="Set")
        ax.plot([], [], color=_PC["lmax"], lw=1.0, label="LMax")
        ax.plot([], [], color=_PC["lmin"], lw=1.0, label="LMin")
    for i, p in enumerate(params):
        lbl = f"Forza{i+1}"
        if p in data:
            pts = sorted(data[p])
            if pts:
                ax.plot([d[0] for d in pts], [d[1] for d in pts], color=_PC[i+1], lw=0.7, zorder=3, label=lbl)
                continue
        ax.plot([], [], color=_PC[i+1], lw=0.7, label=lbl)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3+len(params), **_LK)

def _pdf_forza_ff(ax, data, pr):
    _pdf_setup_ax(ax, "FORZA [kN]", "kN", pr["forza_y"], pr["forza_yticks"], pr["x_ticks"], pr["x_max"], draw_bg=False)
    spc = pr.get("forza_spc", 6500.0); d = pr["forza_delta"]
    ax.axhline(spc, color=_PC["set_forza"], lw=0.8, zorder=5, label="SPC")
    ax.axhline(spc+d, color=_PC["lmax"], lw=1.0, zorder=5, label="LMax")
    ax.axhline(spc-d, color=_PC["lmin"], lw=1.0, zorder=5, label="LMin")
    if "F1" in data:
        pts = sorted(data["F1"])
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=_PC[1], lw=0.7, zorder=3, label="FC")
    h, l = ax.get_legend_handles_labels(); ax.legend(h, l, loc=pr.get("forza_legend_loc","lower right"), ncol=4, **_LK)

def _pdf_vuoto(ax, data, params, setvals, title, labels, pr, ylabel="bar", bg_xmax=None, bg_ymax=None, draw_bg=True):
    if bg_xmax is None and bg_ymax is None:
        bg_xmax = pr.get("vuoto_bg_xmax", None)
        bg_ymax = pr.get("vuoto_bg_ymax", None)
    _pdf_setup_ax(ax, title, ylabel, pr["vuoto_y"], pr["vuoto_yticks"], pr["x_ticks"], pr["x_max"], bg_xmax=bg_xmax, bg_ymax=bg_ymax, draw_bg=draw_bg)
    sc = ["black","#555","#888","#aaa"]
    for j, sv in enumerate(setvals):
        ax.axhline(sv, color=sc[j%4], lw=0.7, linestyle="--", zorder=4, label=f"Set {j+1}")
    for i, p in enumerate(params):
        lbl = labels[i] if i < len(labels) else p
        if p in data:
            pts = sorted(data[p]); ys = [d[1] for d in pts]
            if not all(abs(v) < 0.001 for v in ys):
                ax.plot([d[0] for d in pts], ys, color=_PC[i+1], lw=0.7, zorder=3, label=lbl)
                continue
        ax.plot([], [], color=_PC[i+1], lw=0.7, label=lbl)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=len(setvals)+len(params), **_LK)

def _logo_ax(fig, logo_path):
    ax = fig.add_axes([0.03, 0.912, 0.042, 0.045])
    try:
        import matplotlib.image as mpi
        lp = logo_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "lamborghini_logo.png")
        if lp and os.path.exists(lp):
            ax.imshow(mpi.imread(lp), aspect="auto"); ax.axis("off"); return
    except Exception: pass
    ax.set_facecolor("#e0e0e0")
    ax.text(0.5,0.5,"LOGO",ha="center",va="center",fontsize=6,color="#888",transform=ax.transAxes)
    ax.axis("off")

def _pdf_hdr_p1(fig, meta, pr, n, logo_path=None):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    _logo_ax(fig, logo_path)
    fig.text(0.08,0.966,"Automobili Lamborghini",fontsize=9,fontweight="bold",va="top",color="#111")
    fig.text(0.08,0.952,"Via Modena, 12",fontsize=7.5,va="top",color="#333")
    fig.text(0.08,0.939,"140019 - Sant'Agata Bolognese (BO)",fontsize=7.5,va="top",color="#333")
    fig.text(0.08,0.926,"Tel.: +39 051 959.7611",fontsize=7.5,va="top",color="#333")
    fig.text(0.50,0.985,"CAMPIONAMENTO PARAMETRI OPERATIVI",fontsize=11,fontweight="bold",ha="center",va="top",color="#111")
    fig.add_artist(plt.Line2D([0.03,0.97],[0.913,0.913],transform=fig.transFigure,color="#aaa",lw=0.5))
    fields=[("ID Ciclo",meta["idciclo"]),("Codice Partita",meta["partite"]),
            ("Nome Ricetta",pr["ricetta"]),("Nome Operatore",meta.get("operatore","")),
            ("Codice Materiale",meta["materiale"]),("Data",_pdf_fmt_date(meta["tsraw"]))]
    if meta.get("note"): fields.append(("Note", meta["note"]))
    y0=0.908; rh=0.022
    for i,(lbl,val) in enumerate(fields):
        y=y0-i*rh
        fig.text(0.03,y,lbl,fontsize=7.5,fontweight="bold",va="top",color="#111")
        fig.text(0.22,y,val,fontsize=7.5,va="top",color="#222")
        fig.add_artist(plt.Line2D([0.03,0.97],[y-0.016,y-0.016],transform=fig.transFigure,color="#ccc",lw=0.5))
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")

def _pdf_hdr_g(fig, n):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    fig.add_artist(plt.Line2D([0.03,0.97],[0.965,0.965],transform=fig.transFigure,color="#555",lw=0.8))
    fig.text(0.50,0.985,"CAMPIONAMENTO PARAMETRI OPERATIVI",fontsize=11,fontweight="bold",ha="center",va="top",color="#111")
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")

def _pdf_hdr_p1ff(fig, meta, pr, n, logo_path=None):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    fig.add_artist(plt.Line2D([0.03,0.97],[0.730,0.730],transform=fig.transFigure,color="#555",lw=0.8))
    _logo_ax(fig, logo_path)
    fig.text(0.08,0.966,"Automobili Lamborghini",fontsize=9,fontweight="bold",va="top",color="#111")
    fig.text(0.08,0.952,"Via Modena, 12",fontsize=7.5,va="top",color="#333")
    fig.text(0.08,0.939,"140019 - Sant'Agata Bolognese (BO)",fontsize=7.5,va="top",color="#333")
    fig.text(0.97,0.966,"Report generato",fontsize=8,ha="right",va="top",color="#555")
    fig.text(0.97,0.952,datetime.now().strftime("%d/%m/%Y %H:%M"),fontsize=8,ha="right",va="top",color="#333")
    fig.text(0.50,0.910,"COMPRESSION MOULDING SYSTEM - CFK TECNOLOGY",fontsize=12,fontweight="bold",ha="center",va="top",color="#111")
    y=0.860; step=0.036
    def row(lbl,val):
        nonlocal y
        fig.text(0.08,y,lbl,fontsize=7.5,fontweight="bold",va="top",color="#111")
        fig.text(0.35,y,val,fontsize=7.5,va="top",color="#222")
        fig.add_artist(plt.Line2D([0.08,0.65],[y-0.016,y-0.016],transform=fig.transFigure,color="#ccc",lw=0.5))
        y-=step
    row("ID CICLO",str(meta.get("idciclo",""))); row("SERIAL NUMBER",meta.get("partite",""))
    row("RICETTA",str(pr.get("ricetta",""))); row("NOME OPERATORE",meta.get("operatore",""))
    row("CODICE MATERIALE",meta.get("materiale","")); row("DATA",meta.get("tsraw","").replace("T"," "))
    row("Inizio ciclo",_pdf_fmt_ts(meta.get("tsstart"))); row("Fine ciclo",_pdf_fmt_ts(meta.get("tsend")))
    row("Teorico Sec",str(pr.get("teorico_sec","-"))); row("Durata Sec",str(meta.get("dursec","-")))
    fig.text(0.50,0.72,"Copyright 2023 Automobili Lamborghini S.p.A., societa ad azionista unico parte del Gruppo Audi.",
             fontsize=6,ha="center",va="top",color="#888")
    fig.text(0.50,0.710,"Tutti i diritti riservati. P.IVA n. 00591801204",fontsize=6,ha="center",va="top",color="#888")
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")

def _pdf_hdr_g_ff(fig, n, meta):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    fig.add_artist(plt.Line2D([0.03,0.97],[0.965,0.965],transform=fig.transFigure,color="#555",lw=0.8))
    fig.text(0.50,0.985,"COMPRESSION MOULDING SYSTEM - CFK TECNOLOGY",fontsize=10,fontweight="bold",ha="center",va="top",color="#111")
    fig.text(0.03,0.975,f"Report: {datetime.now().strftime('%d/%m/%Y %H:%M')}",fontsize=7,va="top",color="#555")
    fig.text(0.03,0.968,
             f"Inizio: {_pdf_fmt_ts(meta.get('tsstart'))}  Fine: {_pdf_fmt_ts(meta.get('tsend'))}  "
             f"Durata: {meta.get('dursec','-')} sec  Teorico: {meta.get('teorico_sec',meta.get('teorico','-'))} sec",
             fontsize=6.5,va="top",color="#444")
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")


# -- PERSICO V8 PDF -------------------------------------------------------------

def _persico_v8_hdr(fig, meta, pr, logo_path=None):
    import numpy as _np
    from PIL import Image as _PIL
    try:
        lp = logo_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "lamborghini_logo.png")
        if not os.path.exists(lp): lp = lp.replace(".png", ".jpg")
        if lp and os.path.exists(lp):
            ax_l = fig.add_axes([0.18, 0.87, 0.08, 0.06], frameon=False)
            ax_l.imshow(_np.array(_PIL.open(lp).convert("RGBA"))); ax_l.axis("off")
    except Exception: pass
    fig.text(0.50,0.915,"automobili",fontsize=15,ha="center",va="center",style="italic",family="serif")
    fig.text(0.50,0.890,"Lamborghini",fontsize=24,ha="center",va="center",style="italic",family="serif",fontweight="bold")
    fig.text(0.50,0.870,"COMPRESSION MOULDING SYSTEM - CFK TECNOLOGY",fontsize=8,fontweight="bold",ha="center",va="top")
    axp=fig.add_axes([0.72,0.875,0.09,0.05],frameon=False); axp.set_xlim(0,1); axp.set_ylim(0,1); axp.axis("off")
    axp.add_patch(plt.Polygon([[0.05,0.1],[0.95,0.1],[0.5,0.9]],fill=True,color="#888"))
    t0s=meta.get("tsstart"); tNs=meta.get("tsend")
    fig.text(0.18,0.84,"Report generato:",fontsize=7,fontweight="bold")
    fig.text(0.31,0.84,meta.get("tsraw","")[:16],fontsize=7,fontweight="bold")
    fig.text(0.44,0.84,"Inizio ciclo",fontsize=7)
    fig.text(0.51,0.84,t0s.strftime("%Y-%m-%dT%H:%M:%S.000Z") if t0s else "",fontsize=7,fontweight="bold")
    fig.text(0.44,0.825,"Fine ciclo",fontsize=7)
    fig.text(0.51,0.825,tNs.strftime("%Y-%m-%dT%H:%M:%S.000Z") if tNs else "",fontsize=7,fontweight="bold")
    fig.text(0.72,0.84,"Teorico [Sec]",fontsize=7); fig.text(0.80,0.84,str(pr.get("teorico_sec","-")),fontsize=7)
    fig.text(0.72,0.825,"Durata [Sec]",fontsize=7); fig.text(0.80,0.825,str(meta.get("dursec","-")),fontsize=7)
    fig.text(0.50,0.04,
        "Copyright (c) 2023 Automobili Lamborghini S.p.A., societa ad azionista unico parte del Gruppo Audi.\n"
        "Tutti i diritti riservati. P.IVA n. 00591801204",
        fontsize=7.5,ha="center",va="bottom",color="#111",linespacing=1.6,fontweight="bold")


def _persico_v8_setup_ax(ax, title, unit, ylim, yticks, xticks, bg_type="none", bg_range=None):
    BG="#e5f0db"
    ax.set_facecolor("white"); ax.set_xlim(xticks[0], xticks[-1]); ax.set_ylim(ylim[0],ylim[1])
    ax.autoscale(False)
    if bg_range:
        ax.axhspan(bg_range[0], bg_range[1], color=BG, zorder=0)
    else:
        if bg_type=="temp":  ax.axhspan(130,150,color=BG,zorder=0)
        elif bg_type=="forza": ax.axhspan(6250,6750,color=BG,zorder=0)
        elif bg_type=="vuoto": ax.axhspan(-1000,-200,color=BG,zorder=0)
    for sp in ax.spines.values(): sp.set_visible(True); sp.set_color("#666"); sp.set_linewidth(0.8)
    ax.set_yticks(yticks)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda v,_: f"{v:.2f}".replace(".",",") if "mm" in title else f"{int(v)}"))
    ax.set_xticks(xticks); ax.tick_params(axis="both",labelsize=7,length=3,color="#666",pad=2,labelcolor="#222")
    plt.setp(ax.get_xticklabels(),rotation=90,fontsize=6)
    ax.grid(True,axis="y",color="#eaeaea",lw=0.6,linestyle="-",zorder=1); ax.grid(False,axis="x")
    ax.set_title(title,fontsize=9.5,pad=6,loc="center",color="#444")
    ax.text(-0.01,1.06,unit,transform=ax.transAxes,fontsize=7.5,ha="center",va="bottom",color="#444",clip_on=False)
    ax.text(0.995,0.04,"[Sec]",transform=ax.transAxes,fontsize=7.5,ha="right",va="bottom",color="#444")


def _persico_v8_cleg(ax, handles, labels, badge_ok=False):
    import matplotlib.patches as _mp
    if not handles: return
    if badge_ok:
        handles.insert(0, _mp.Patch(color="#e5f0db", label="RANGE OK"))
        labels.insert(0, "RANGE OK")
    box = ax.get_position()
    new_bottom = box.y0 + 0.075
    new_height  = box.height - 0.055
    ax.set_position([box.x0, new_bottom, box.width, new_height])
    leg_y_fig = new_bottom - 0.055
    ax.legend(handles, labels,
              loc="upper center",
              bbox_to_anchor=(box.x0 + box.width / 2, leg_y_fig),
              bbox_transform=ax.figure.transFigure,
              frameon=True, facecolor="white", edgecolor="#bbb",
              fontsize=8, handlelength=2.5, handletextpad=0.5,
              columnspacing=1.5, ncol=len(labels))


def _posiz_y_auto(data, x_min=None):
    vals = [v for col in ["P1","P2","P3","P4"]
            for _sec,v,_st,_sp in data.get(col,[])
            if isinstance(v,(int,float)) and (x_min is None or _sec >= x_min)]
    if not vals:
        return (-0.35,0.05), [-0.35,-0.30,-0.25,-0.20,-0.15,-0.10,-0.05,0.0,0.05], 2
    mn,mx = min(vals),max(vals)
    if mx < 0:
        y1 = 0.0
        y0 = mn - max(abs(mn)*0.20, 0.005)
    else:
        pad = max((mx-mn)*0.20, 0.005)
        y0,y1 = mn-pad, mx+pad
    rng   = y1-y0 or 0.01
    exp   = math.floor(math.log10(rng/8))
    raw   = rng/8 / (10**exp)
    mult  = 1 if raw<2 else 2 if raw<5 else 5
    step  = round(mult * (10**exp), 8)
    dec   = max(0, -int(math.floor(math.log10(step)))) if step > 0 else 2
    t0    = math.ceil(y0 / step) * step
    ticks = [round(t0 + i*step, dec+1) for i in range(30)
             if t0 + i*step <= y1 + step*0.01]
    return (y0, y1), ticks, dec


def _persico_v8_pages(pdf, data, meta, pr, logo_path=None):
    import matplotlib.patches as _mp
    CT1,CT2,CT3,CT4 = "#e5672c","#828282","#407da5","#e7b73b"
    CSP = "#659346"
    TV   = pr.get("x_ticks_tv", list(range(44, 1452+1, 44)))
    POS  = pr.get("x_ticks_pos", list(range(11, 1463+1, 44)))
    FORZ = pr.get("x_ticks_forza", list(range(44, 1496+1, 44)))
    VAC_SUP = pr.get("x_ticks_vac_sup", TV)
    VAC_INF = pr.get("x_ticks_vac_inf", TV)

    _cc_t_max = 0
    PS = dict(
        temp_y      = pr.get("temp_y",   (100,160)),
        temp_yticks = pr.get("temp_yticks",[100,110,120,130,140,150,160]),
        temp_range  = pr.get("temp_range", (130, 150)),
        tss         = pr.get("temp_set_sup", 130.0),
        tsi         = pr.get("temp_set_inf", 128.0),
        forza_y     = pr.get("forza_y",  (6000,6800)),
        forza_yticks= pr.get("forza_yticks",[6000,6100,6200,6300,6400,6500,6600,6700,6800]),
        forza_range = pr.get("forza_range", (6250, 6750)),
        spc         = pr.get("forza_spc", 6500.0),
        vuoto_y     = pr.get("vuoto_y",  (-1000,0)),
        vuoto_yticks= pr.get("vuoto_yticks",[-1000,-900,-800,-700,-600,-500,-400,-300,-200,-100,0]),
        vuoto_range = pr.get("vuoto_range", (-1000, -200)))
    def gs(p):
        if p not in data: return [],[]
        pts=sorted(data[p]); return [x[0] for x in pts],[x[1] for x in pts]
    _skip_s = pr.get("skip_seconds", 0)
    def gs_skip(p):
        if p not in data: return [],[]
        pts=[x for x in sorted(data[p]) if x[0] >= _skip_s]
        if not pts: return [],[]
        return [x[0] for x in pts],[x[1] for x in pts]
    FW,FH = 8.27,11.69; L,W = 0.18,0.64

    fig = plt.figure(figsize=(FW,FH), facecolor="white")
    _persico_v8_hdr(fig, meta, pr, logo_path)
    rows_t=[("ID CICLO",str(meta.get("idciclo",""))),("SERIAL NUMBER",meta.get("partite","")),
            ("RICETTA",pr.get("ricetta","3")),("NOME OPERATORE",meta.get("operatore","NOME OPERATORE")),
            ("CODICE MATERIALE",meta.get("materiale","")),("DATA",meta.get("tsraw","").replace("T"," "))]
    if meta.get("note"): rows_t.append(("NOTE", meta["note"]))
    rh=0.015; ty=0.81
    for lbl,val in rows_t:
        fig.add_artist(_mp.Rectangle((0.18,ty-rh),0.64,rh,fill=False,edgecolor="#000",lw=0.7,
                                     transform=fig.transFigure,clip_on=False))
        fig.add_artist(plt.Line2D([0.33,0.33],[ty-rh,ty],transform=fig.transFigure,color="#000",lw=0.7))
        fig.text(0.185,ty-rh/2,lbl,fontsize=7.5,va="center",fontweight="bold")
        fig.text(0.335,ty-rh/2,str(val),fontsize=7.5,va="center",fontweight="bold"); ty-=rh
    ax_ts=fig.add_axes([L,0.42,W,0.23]); ax_ti=fig.add_axes([L,0.11,W,0.23])
    _persico_v8_setup_ax(ax_ts,"Temperatura semistampo superiore (°C) - Grafico",
                         "[°C]",PS["temp_y"],PS["temp_yticks"],TV,"temp", PS["temp_range"])
    ax_ts.plot([],[],color=CSP,label="SP",lw=1.2); ax_ts.axhline(PS["tss"],color=CSP,lw=0.8,zorder=3)
    for c,col in zip([CT1,CT3,CT2,CT4],["TS1","TS3","TS2","TS4"]):
        xs,ys=gs(col)
        if xs: ax_ts.plot(xs,ys,color=c,lw=1.2,label=col.replace("TS","T"),zorder=4)
    h,l=ax_ts.get_legend_handles_labels(); _persico_v8_cleg(ax_ts,h,l,True)

    _persico_v8_setup_ax(ax_ti,"Temperatura semistampo inferiore (°C) - Grafico",
                         "[°C]",PS["temp_y"],PS["temp_yticks"],TV,"temp", PS["temp_range"])
    ax_ti.plot([],[],color=CSP,label="SP",lw=1.2); ax_ti.axhline(PS["tsi"],color=CSP,lw=0.8,zorder=3)
    for c,col in zip([CT3,CT1,CT2,CT4],["TI3","TI1","TI2","TI4"]):
        xs,ys=gs(col)
        if xs: ax_ti.plot(xs,ys,color=c,lw=1.2,label=col.replace("TI","T"),zorder=4)
    h,l=ax_ti.get_legend_handles_labels(); _persico_v8_cleg(ax_ti,h,l,True)

    pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)

    fig = plt.figure(figsize=(FW,FH), facecolor="white")
    _persico_v8_hdr(fig, meta, pr, logo_path)
    ax_p=fig.add_axes([L,0.48,W,0.28]); ax_f=fig.add_axes([L,0.11,W,0.28])
    _py,_pticks,_pdec = _posiz_y_auto(data)
    _persico_v8_setup_ax(ax_p,"Posizione piano (mm) - Grafico","[mm]",_py,_pticks,POS,"none")
    ax_p.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda v,_,d=_pdec: f"{v:.{d}f}".replace(".",",")))
    for c,col in zip([CT3,CT1,CT2,CT4],["P1","P2","P3","P4"]):
        xs,ys=gs_skip(col)
        if xs: ax_p.plot(xs,ys,color=c,lw=1.2,label=col,zorder=4)
    h,l=ax_p.get_legend_handles_labels(); _persico_v8_cleg(ax_p,h,l,False)
    _persico_v8_setup_ax(ax_f,"Forza (kN) - Grafico","[kN]",
                         PS["forza_y"],PS["forza_yticks"],FORZ,"forza", PS["forza_range"])
    ax_f.axhline(PS["spc"],color=CT1,lw=1.2,label="SPC",zorder=3)
    xs,ys=gs_skip("FC") if "FC" in data else gs_skip("F1")
    if xs: ax_f.plot(xs,ys,color=CSP,lw=1.2,label="FC",zorder=4)
    h,l=ax_f.get_legend_handles_labels(); _persico_v8_cleg(ax_f,h,l,True)

    pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)

    fig = plt.figure(figsize=(FW,FH), facecolor="white")
    _persico_v8_hdr(fig, meta, pr, logo_path)
    ax_vs=fig.add_axes([L,0.48,W,0.28]); ax_vi=fig.add_axes([L,0.11,W,0.28])
    _persico_v8_setup_ax(ax_vs,"Vuoto semistampo superiore (mbar) - Grafico","[mbar]",
                         PS["vuoto_y"],PS["vuoto_yticks"],VAC_SUP,"vuoto", PS["vuoto_range"])
    for c,col in zip([CT1,CT2],["VS1","VS2"]):
        xs,ys=gs(col)
        if xs: ax_vs.plot(xs,ys,color=c,lw=1.2,label=col.replace("VS","V"),zorder=4)
    h,l=ax_vs.get_legend_handles_labels(); _persico_v8_cleg(ax_vs,h,l,True)
    _persico_v8_setup_ax(ax_vi,"Vuoto semistampo inferiore (mbar) - Grafico","[mbar]",
                         PS["vuoto_y"],PS["vuoto_yticks"],VAC_INF,"vuoto", PS["vuoto_range"])
    for c,col in zip([CT3,CT1],["VI1","VI2"]):
        xs,ys=gs(col)
        if xs: ax_vi.plot(xs,ys,color=c,lw=1.2,label=col.replace("VI","V"),zorder=4)
    h,l=ax_vi.get_legend_handles_labels(); _persico_v8_cleg(ax_vi,h,l,True)

    pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)


def _parse_native_pack(native_paths, stampo_name=""):
    from datetime import datetime as _dt
    def _read_wide(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = [l for l in f.readlines() if l.strip()]
        start = 1 if lines and lines[0].upper().startswith("REPORT") else 0
        hdr = [h.strip() for h in lines[start].split(";")]
        rows = []
        for l in lines[start+1:]:
            parts = l.strip().split(";")
            row = {hdr[i]: parts[i].strip().replace(",",".") for i in range(min(len(hdr),len(parts))) if hdr[i]}
            rows.append(row)
        return hdr, rows
    def _to_pts(rows, col, sp_col=None):
        pts = []
        for r in rows:
            try:
                t = float(r.get("Time",""))
                s = r.get(col,"").strip()
                if not s: continue
                val = float(s)
                sp = None
                if sp_col:
                    try: sp = float(r.get(sp_col,"").strip())
                    except Exception: pass
                pts.append((t, val, 0, sp))
            except Exception: continue
        return pts
    data = {}; meta_patch = {}
    if "DATI_GENERALI" in native_paths:
        with open(native_paths["DATI_GENERALI"], encoding="utf-8", errors="replace") as f:
            dg = [l.strip() for l in f.readlines()]
        keys = ["idciclo","partite","_stampo","operatore","materiale"]
        for i,k in enumerate(keys):
            if i < len(dg) and k != "_stampo": meta_patch[k] = dg[i]
        if len(dg) >= 2:
            all_parts = [p.strip() for p in dg[1].split("/") if p.strip()]
            sn = stampo_name.upper()
            if "FRONT FIREWALL" in sn:
                filtered = [p for p in all_parts if "RF" in p.upper()]
            elif "CENTRAL COFANGO" in sn:
                filtered = [p for p in all_parts if "IC" in p.upper()]
            elif "SIDE COFANGO" in sn:
                filtered = [p for p in all_parts if "SD" in p.upper() or "SS" in p.upper()]
            else:
                filtered = all_parts
            if filtered:
                meta_patch["partite"] = " / ".join(filtered)
        if len(dg) >= 9:
            try: meta_patch["tsraw"] = dg[8].rstrip("Z").split(".")[0].replace("T"," ")
            except Exception: pass
    if "FORZA" in native_paths:
        _, rows = _read_wide(native_paths["FORZA"])
        for _c in ["F1","F2","F3","F4"]:
            pts = _to_pts(rows, _c)
            if pts: data[_c] = pts
        pts = _to_pts(rows, "FC", "SPC")
        if pts: data["FC"] = pts
    if "POSIZIONE" in native_paths:
        _, rows = _read_wide(native_paths["POSIZIONE"])
        for c in ["P1","P2","P3","P4"]:
            pts = _to_pts(rows, c)
            if pts: data[c] = pts
    if "TEMPS_SUP" in native_paths:
        _, rows = _read_wide(native_paths["TEMPS_SUP"])
        for i,c in enumerate(["T1","T2","T3","T4","T5"],1):
            pts = _to_pts(rows, c, "SP")
            if pts: data[f"TS{i}"] = pts
    if "TEMPS_INF" in native_paths:
        _, rows = _read_wide(native_paths["TEMPS_INF"])
        for i,c in enumerate(["T1","T2","T3","T4","T5"],1):
            pts = _to_pts(rows, c, "SP")
            if pts: data[f"TI{i}"] = pts
    if "VUOTO_SUP" in native_paths:
        _, rows = _read_wide(native_paths["VUOTO_SUP"])
        for i,c in enumerate(["V1","V2"],1):
            pts = _to_pts(rows, c, "SET -")
            if pts: data[f"VS{i}"] = pts
    if "VUOTO_INF" in native_paths:
        _, rows = _read_wide(native_paths["VUOTO_INF"])
        for i,c in enumerate(["V1","V2"],1):
            pts = _to_pts(rows, c, "SET -")
            if pts: data[f"VI{i}"] = pts
    return data, meta_patch


def _merge_native_data(base_data, base_meta, native_data, meta_patch):
    merged = dict(base_data); merged.update(native_data)
    meta = dict(base_meta); meta.update(meta_patch)
    return merged, meta


def _filter_partite(partite_str, stampo_name):
    if not partite_str: return partite_str
    parts = [p.strip() for p in partite_str.replace("/",",").split(",") if p.strip()]
    sn = stampo_name.upper()
    if "FRONT FIREWALL" in sn:
        filtered = [p for p in parts if "RF" in p.upper()]
    elif "CENTRAL COFANGO" in sn:
        filtered = [p for p in parts if "IC" in p.upper()]
    elif "SIDE COFANGO" in sn:
        filtered = [p for p in parts if "SD" in p.upper() or "SS" in p.upper()]
    else:
        return partite_str
    return " / ".join(filtered) if filtered else partite_str


def generate_lamborghini_pdf(csv_path, stampo_name, output_path, logo_path=None, filter_params=None, t_start=None, t_end=None, preloaded_data=None, preloaded_meta=None):
    if logo_path is None:
        here=os.path.dirname(os.path.abspath(csv_path))
        candidate=os.path.join(here,"lamborghini_logo.png")
        if os.path.exists(candidate): logo_path=candidate
    pr=_PROFILES[stampo_name]
    if preloaded_data is not None and preloaded_meta is not None:
        data, meta = preloaded_data, preloaded_meta
    else:
        data, meta = _pdf_parse_csv(csv_path)
    if filter_params is not None:
        data={k:v for k,v in data.items() if k in filter_params}
    if t_start is not None or t_end is not None:
        _ts0=t_start or 0; _ts1=t_end or float("inf")
        data={k:[(s,v,st,sp) for s,v,st,sp in pts if _ts0<=s<=_ts1] for k,pts in data.items()}
        data={k:v for k,v in data.items() if v}
    FW,FH=8.27,11.69; L,W,MID,BOT,H=0.10,0.87,0.490,0.055,0.375
    with PdfPages(output_path) as pdf:
        if pr.get("persico"):
            _persico_v8_pages(pdf, data, meta, pr, logo_path=logo_path)
        else:
            fig=plt.figure(figsize=(FW,FH),facecolor="white")
            _pdf_hdr_p1(fig,meta,pr,1,logo_path=logo_path); pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
            fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g(fig,2)
            _pdf_temp(fig.add_axes([L,MID+0.01,W,H]),data,[f"TS{i}" for i in range(1,9)],pr["temp_set_sup"],"TEMPERATURA SUPERIORE (°C)",pr)
            _pdf_temp(fig.add_axes([L,BOT,W,H]),data,[f"TI{i}" for i in range(1,9)],pr["temp_set_inf"],"TEMPERATURA INFERIORE (°C)",pr)
            pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
            fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g(fig,3)
            _skip = pr.get("skip_seconds", 0)
            _data_pf = {k:[(s,v,st,sp) for s,v,st,sp in pts if s >= _skip] for k,pts in data.items()} if _skip else data
            _pdf_posiz(fig.add_axes([L,MID+0.01,W,H]),_data_pf,[f"Z{i}" for i in range(1,5)],pr)
            _pdf_forza(fig.add_axes([L,BOT,W,H]),_data_pf,[f"F{i}" for i in range(1,5)],pr)
            pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
            fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g(fig,4)
            _vuoto_sup_bg_xmax = pr.get("vuoto_bg_xmax_sup", pr.get("vuoto_bg_xmax"))
            _vuoto_sup_bg_ymax = pr.get("vuoto_bg_ymax_sup", pr.get("vuoto_bg_ymax"))
            _vuoto_inf_bg_xmax = pr.get("vuoto_bg_xmax_inf", pr.get("vuoto_bg_xmax"))
            _vuoto_inf_bg_ymax = pr.get("vuoto_bg_ymax_inf", pr.get("vuoto_bg_ymax"))
            _sup_draw_bg = not pr.get("vuoto_no_bg_sup", False)
            _inf_draw_bg = not pr.get("vuoto_no_bg_inf", False)
            _pdf_vuoto(fig.add_axes([L,MID+0.01,W,H]),data,["VS1","VS2"],[0.0,0.0],"VUOTO SUPERIORE [bar]",["V1 Sup","V2 Sup"],pr, bg_xmax=_vuoto_sup_bg_xmax, bg_ymax=_vuoto_sup_bg_ymax, draw_bg=_sup_draw_bg)
            _pdf_vuoto(fig.add_axes([L,BOT,W,H]),data,["VI1","VI2","VI3","VI4"],[0.0,0.0,0.0,0.0],"VUOTO INFERIORE [bar]",["V1 Inf","V2 Inf","V3 Inf","V4 Inf"],pr, bg_xmax=_vuoto_inf_bg_xmax, bg_ymax=_vuoto_inf_bg_ymax, draw_bg=_inf_draw_bg)
            pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)

def detect_csv_type(headers):
    h=set(headers)
    temp_cols=sum(1 for i in range(1,9) if f"T{i}" in h or f"TS{i}" in h or f"TI{i}" in h)
    pos_cols =sum(1 for i in range(1,5) if f"P{i}" in h)
    force_ok =any(c in h for c in ("SPC","FC","F1","Forza"))
    vac_ok   =any(c in h for c in ("V1","V2","VS1","VI1","Vuoto"))
    if temp_cols>=2 and (pos_cols>=2 or force_ok or vac_ok): return "front_firewall"
    return "siemens"

def _group_ff_cols(headers):
    temp_sup=[c for c in headers if c.startswith("TS") and c[2:].isdigit()]
    temp_inf=[c for c in headers if c.startswith("TI") and c[2:].isdigit()]
    if not temp_sup: temp_sup=[c for c in headers if c.startswith("T") and c[1:].isdigit() and 1<=int(c[1:])<=4]
    if not temp_inf: temp_inf=[c for c in headers if c.startswith("T") and c[1:].isdigit() and 4<int(c[1:])<=8]
    pos  =[c for c in headers if c.startswith("P") and c[1:].isdigit()]
    force=[c for c in headers if c in ("SPC","FC","F1","Forza")]
    vac_s=[c for c in headers if c in ("VS1","VS2","V1","V2")]
    vac_i=[c for c in headers if c in ("VI1","VI2","VI3","VI4","V3","V4")]
    return {"temp_sup":temp_sup,"temp_inf":temp_inf,"pos":pos,"force":force,"vac_s":vac_s,"vac_i":vac_i}

def generate_front_firewall_pdf(rows, headers, output_path, logo_path=None):
    if not rows: raise ValueError("Nessun dato disponibile.")
    pr=_PROFILES["Front Firewall"]; grp=_group_ff_cols(headers)
    times=[r["_ts"] for r in rows if r.get("_ts")]
    if not times: raise ValueError("Nessun timestamp valido.")
    t0=times[0]; tN=times[-1]
    xs=[(r["_ts"]-t0).total_seconds() if r.get("_ts") else None for r in rows]
    xmax=max((x for x in xs if x is not None),default=pr["x_max"])
    pr2=dict(pr); pr2["x_ticks"]=[round(i*xmax/10) for i in range(11)]; pr2["x_max"]=xmax if xmax>0 else pr["x_max"]
    def gs(col): return [(xs[i],rows[i][col]) for i in range(len(rows)) if xs[i] is not None and isinstance(rows[i].get(col),float)]
    meta={"idciclo":"","partite":"Front Firewall","operatore":"","materiale":"",
          "tsraw":t0.strftime("%d/%m/%Y %H:%M:%S") if t0 else "","tsstart":t0,"tsend":tN,
          "dursec":int((tN-t0).total_seconds()) if t0 and tN else 0,"teorico_sec":pr.get("teorico_sec","")}
    FW,FH=8.27,11.69; L,W,MID,BOT,H=0.10,0.87,0.490,0.055,0.375
    with PdfPages(output_path) as pdf:
        fig=plt.figure(figsize=(FW,FH),facecolor="white")
        _pdf_hdr_p1ff(fig,meta,pr2,1,logo_path=logo_path); pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
        fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g_ff(fig,2,meta)
        ax_ts=fig.add_axes([L,MID+0.01,W,H]); ax_ti=fig.add_axes([L,BOT,W,H])
        _pdf_setup_ax(ax_ts,"Temperatura semistampo superiore [°C]","°C",pr2["temp_y"],pr2["temp_yticks"],pr2["x_ticks"],pr2["x_max"])
        ax_ts.axhline(pr2["temp_set_sup"],color=_PC["set_temp"],lw=0.8,label="SET")
        for i,col in enumerate(grp["temp_sup"][:4]):
            pts=gs(col)
            if pts: ax_ts.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_ts.get_legend_handles_labels(); ax_ts.legend(h2,l2,loc="lower right",ncol=5,**_LK)
        _pdf_setup_ax(ax_ti,"Temperatura semistampo inferiore [°C]","°C",pr2["temp_y"],pr2["temp_yticks"],pr2["x_ticks"],pr2["x_max"])
        ax_ti.axhline(pr2["temp_set_inf"],color=_PC["set_temp"],lw=0.8,label="SET")
        for i,col in enumerate(grp["temp_inf"][:4]):
            pts=gs(col)
            if pts: ax_ti.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_ti.get_legend_handles_labels(); ax_ti.legend(h2,l2,loc="lower right",ncol=5,**_LK)
        pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
        fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g_ff(fig,3,meta)
        ax_p=fig.add_axes([L,MID+0.01,W,H]); ax_f=fig.add_axes([L,BOT,W,H])
        _pdf_setup_ax(ax_p,"Posizione piano [mm]","mm",pr2["posiz_y"],pr2["posiz_yticks"],pr2["x_ticks"],pr2["x_max"],draw_bg=False)
        for i,col in enumerate(grp["pos"][:4]):
            pts=gs(col)
            if pts: ax_p.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        ax_p.axhline(0,color="#999",lw=0.4,linestyle="--",zorder=2)
        h2,l2=ax_p.get_legend_handles_labels(); ax_p.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        _pdf_setup_ax(ax_f,"Forza SPC / FC [kN]","kN",pr2["forza_y"],pr2["forza_yticks"],pr2["x_ticks"],pr2["x_max"],draw_bg=False)
        spc=pr2.get("forza_spc",6500.0); fd=pr2["forza_delta"]
        ax_f.axhline(spc,color=_PC["set_forza"],lw=0.8,label="SPC"); ax_f.axhline(spc+fd,color=_PC["lmax"],lw=1.0,label="LMax"); ax_f.axhline(spc-fd,color=_PC["lmin"],lw=1.0,label="LMin")
        for i,col in enumerate(grp["force"][:2]):
            pts=gs(col)
            if pts: ax_f.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_f.get_legend_handles_labels(); ax_f.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
        fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g_ff(fig,4,meta)
        ax_vs=fig.add_axes([L,MID+0.01,W,H]); ax_vi=fig.add_axes([L,BOT,W,H])
        _pdf_setup_ax(ax_vs,"Vuoto semistampo superiore [mbar]","mbar",pr2["vuoto_y"],pr2["vuoto_yticks"],pr2["x_ticks"],pr2["x_max"])
        for i,col in enumerate(grp["vac_s"][:2]):
            pts=gs(col)
            if pts: ax_vs.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_vs.get_legend_handles_labels(); ax_vs.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        _pdf_setup_ax(ax_vi,"Vuoto semistampo inferiore [mbar]","mbar",pr2["vuoto_y"],pr2["vuoto_yticks"],pr2["x_ticks"],pr2["x_max"])
        for i,col in enumerate(grp["vac_i"][:2]):
            pts=gs(col)
            if pts: ax_vi.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_vi.get_legend_handles_labels(); ax_vi.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)


# ================================================

MAX_CSV_BYTES = 50 * 1024 * 1024
REQUIRED_COLUMNS = {"Partita","Materiale","IdCiclo","Parametro","Timestamp","Valore","Step"}

def _validate_csv(csv_path):
    size = os.path.getsize(csv_path)
    if size > MAX_CSV_BYTES:
        return False, f"File troppo grande ({size/(1024*1024):.1f} MB). Limite: 50 MB."
    try:
        with open(csv_path, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        start = 1 if lines and lines[0].upper().startswith("REPORT GENERATED") else 0
        hdr_line = lines[start] if start < len(lines) else ""
        headers = set(h.strip() for h in hdr_line.split(","))
        missing = REQUIRED_COLUMNS - headers
        if missing: return False, f"Colonne mancanti: {', '.join(sorted(missing))}"
    except Exception as e:
        return False, f"Errore lettura CSV: {e}"
    return True, ""

def _autodetect_profile(csv_path):
    _PM = {
        "VG": ("Inner Tub", None), "PS": ("Polecrasher", "SX"), "PD": ("Polecrasher", "DX"),
        "TD": ("Tub Floor Shell", "DX"), "ST": ("Tub Floor Shell", "SX"),
        "RF": ("Front Firewall", None), "IC": ("Central Cofango", None),
        "SD": ("Side Cofango Inner", "DX"), "SS": ("Side Cofango Inner", "SX"),
    }
    try:
        with open(csv_path, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        if not lines: return None, {}, []
        start = 1 if lines[0].upper().startswith("REPORT GENERATED") else 0
        hdr_line = lines[start] if start < len(lines) else ""
        hdr_cols = [h.strip().strip('"') for h in hdr_line.split(",")]
        partita_idx = hdr_cols.index("Partita") if "Partita" in hdr_cols else 0
        data_sep = ";" if (start + 1 < len(lines) and ";" in lines[start+1]) else ","
        seen = set(); partite_uniche = []
        for line in lines[start+1:]:
            parts = line.split(data_sep)
            if partita_idx < len(parts):
                p = parts[partita_idx].strip().strip('"').upper()
                if p and p not in seen:
                    seen.add(p); partite_uniche.append(p)
        profili_trovati = {}
        for p in partite_uniche:
            m = re.search(r'\d{2}([A-Z]{2})\d', p)
            if m:
                codice = m.group(1)
                if codice in _PM:
                    prof, side = _PM[codice]
                    if prof not in profili_trovati: profili_trovati[prof] = set()
                    if side: profili_trovati[prof].add(side)
        if not profili_trovati: return None, {}, partite_uniche
        return next(iter(profili_trovati)), profili_trovati, partite_uniche
    except Exception: return None, {}, []
