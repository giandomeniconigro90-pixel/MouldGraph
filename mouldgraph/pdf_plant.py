# -*- coding: utf-8 -*-
"""Report PDF "plant" (profili presse/stampi)."""
import matplotlib
matplotlib.use("Agg")
import os
import math
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages
from .csv_parsers import _uc_build_series


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
        # ── Tabella statistica (opzione A) ──────────────────────────────────────
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
                # ── serie ② confronto CSV (linee tratteggiate) ────────
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
