# -*- coding: utf-8 -*-
"""
mouldgraph.pdf_reports
======================
Generazione report PDF con matplotlib (PdfPages).

Funzioni esportate:
    export_pdf_log(parsed, filepath, filters, ai_insights)
    export_pdf_csv(rows, headers, stats, anomalies, filepath, title)
    export_pdf_mould_cycle(rows, headers, col_meta, numeric_cols, filepath, title)

Estratto da log_analyzer_desktop_live.py senza modifiche alla logica.

Dipendenze interne:
    from .constants import COLORS, LEVEL_COLORS, LEVEL_BG, _UC_SERIES_PALETTE
    from .csv_parsers import _uc_build_series, _uc_parse_dt

Dipendenze esterne:
    matplotlib (Agg backend richiesto prima dell'import, fatto dall'entry-point)
    numpy, datetime, collections, os
"""

from datetime import datetime
from collections import defaultdict
import os

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from .constants import COLORS, LEVEL_COLORS, LEVEL_BG, _UC_SERIES_PALETTE
from .csv_parsers import _uc_build_series, _uc_parse_dt


# ---------------------------------------------------------------------------
# Utility di stile PDF
# ---------------------------------------------------------------------------

_BG  = "#0f1117"
_SRF = "#1a1d27"
_TXT = "#e8eaf6"
_TXT2 = "#8892b0"
_ACC  = "#6c63ff"
_ACC2 = "#00d4ff"
_ERR  = "#ff4d4f"
_WRN  = "#faad14"
_INF  = "#52c41a"
_DBG  = "#1890ff"


def _dark_fig(w=11.69, h=8.27):
    fig = plt.figure(figsize=(w, h), facecolor=_BG)
    return fig


def _ax_dark(fig, *args, **kwargs):
    ax = fig.add_subplot(*args, **kwargs)
    ax.set_facecolor(_SRF)
    for sp in ax.spines.values():
        sp.set_edgecolor(COLORS["border"])
    ax.tick_params(colors=_TXT2, labelsize=8)
    ax.xaxis.label.set_color(_TXT2)
    ax.yaxis.label.set_color(_TXT2)
    ax.grid(True, color=COLORS["border"], linewidth=0.3, linestyle="--", alpha=0.5)
    return ax


def _title_page(pdf, title, subtitle="", meta=None):
    fig = _dark_fig()
    fig.patch.set_facecolor(_BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(_BG)
    ax.axis("off")
    ax.text(0.5, 0.72, title, ha="center", va="center",
            fontsize=28, fontweight="bold", color=_TXT, transform=ax.transAxes)
    ax.text(0.5, 0.62, subtitle, ha="center", va="center",
            fontsize=14, color=_TXT2, transform=ax.transAxes)
    if meta:
        ax.text(0.5, 0.50, meta, ha="center", va="center",
                fontsize=10, color=_TXT2, transform=ax.transAxes)
    ax.text(0.5, 0.40,
            f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            ha="center", va="center",
            fontsize=9, color=_TXT2, transform=ax.transAxes)
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


# ---------------------------------------------------------------------------
# Report log testuale
# ---------------------------------------------------------------------------

def export_pdf_log(parsed: list, filepath: str,
                   filters: dict = None, ai_insights: list = None):
    """
    Genera PDF di analisi per un log testuale.
    parsed: output di parse_log()
    filters: {'level':'ALL', 'component':'ALL', 'keyword':''}
    ai_insights: output di ai_analysis()
    """
    if not parsed:
        raise ValueError("Nessun evento da esportare.")

    filt = filters or {}
    level_f     = filt.get("level", "ALL")
    component_f = filt.get("component", "ALL")
    keyword_f   = filt.get("keyword", "").lower()

    events = parsed
    if level_f != "ALL":
        events = [e for e in events if e["level"] == level_f]
    if component_f and component_f != "ALL":
        events = [e for e in events if e["component"] == component_f]
    if keyword_f:
        events = [e for e in events if keyword_f in e["message"].lower()]

    total = len(parsed)
    n_err  = sum(1 for e in parsed if e["level"] == "ERROR")
    n_warn = sum(1 for e in parsed if e["level"] == "WARN")
    n_info = sum(1 for e in parsed if e["level"] == "INFO")
    n_dbg  = sum(1 for e in parsed if e["level"] == "DEBUG")

    with PdfPages(filepath) as pdf:
        _title_page(
            pdf, "MouldGraph — Log Analysis Report",
            subtitle="Analisi log testuale",
            meta=f"Totale eventi: {total} • Filtrati: {len(events)} • Generato da MouldGraph",
        )

        # --- Pagina 2: statistiche e donut ---
        fig = _dark_fig()
        ax_donut = _ax_dark(fig, 1, 2, 1)
        ax_donut.set_title("Distribuzione livelli", color=_TXT, pad=8, fontsize=13)
        labels_d = ["ERROR", "WARN", "INFO", "DEBUG"]
        counts_d = [n_err, n_warn, n_info, n_dbg]
        colors_d = [_ERR, _WRN, _INF, _DBG]
        if sum(counts_d) > 0:
            wedges, _, autotexts = ax_donut.pie(
                counts_d, labels=labels_d, colors=colors_d,
                autopct="%1.0f%%", startangle=90,
                pctdistance=0.75,
                wedgeprops=dict(width=0.55, edgecolor=_BG, linewidth=1.5),
            )
            for t in autotexts:
                t.set_fontsize(9)
                t.set_color(_TXT)
        else:
            ax_donut.text(0.5, 0.5, "Nessun evento", ha="center",
                          color=_TXT2, transform=ax_donut.transAxes)

        ax_stats = _ax_dark(fig, 1, 2, 2)
        ax_stats.axis("off")
        ax_stats.set_title("Riepilogo", color=_TXT, pad=8, fontsize=13)
        stat_rows = [
            ("Totale eventi",       str(total)),
            ("ERROR",               f"{n_err} ({n_err / total * 100:.1f}%)"),
            ("WARN",                f"{n_warn} ({n_warn / total * 100:.1f}%)"),
            ("INFO",                f"{n_info} ({n_info / total * 100:.1f}%)"),
            ("DEBUG",               f"{n_dbg} ({n_dbg / total * 100:.1f}%)"),
            ("Filtrati (in report)", str(len(events))),
        ]
        with_ts = [e for e in parsed if e["ts"]]
        if with_ts:
            t0 = min(e["ts"] for e in with_ts)
            t1 = max(e["ts"] for e in with_ts)
            stat_rows += [
                ("Inizio log", t0.strftime("%d/%m/%Y %H:%M:%S")),
                ("Fine log",   t1.strftime("%d/%m/%Y %H:%M:%S")),
            ]
        tbl = ax_stats.table(
            cellText=stat_rows, colLabels=["Metrica", "Valore"],
            cellLoc="left", loc="center",
            bbox=[0.0, 0.0, 1.0, 1.0],
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)
        for (row, col), cell in tbl.get_celld().items():
            cell.set_facecolor(_SRF if row % 2 == 0 else _BG)
            cell.set_edgecolor(COLORS["border"])
            cell.set_text_props(color=_TXT)
        fig.tight_layout(pad=1.5)
        pdf.savefig(fig, facecolor=fig.get_facecolor())
        plt.close(fig)

        # --- Pagina 3: timeline oraria ---
        if with_ts:
            hours_data = defaultdict(lambda: {"ERROR": 0, "WARN": 0, "INFO": 0, "DEBUG": 0})
            for e in with_ts:
                h = e["ts"].strftime("%H:00")
                hours_data[h][e["level"]] = hours_data[h].get(e["level"], 0) + 1
            hours_sorted = sorted(hours_data.keys())
            fig = _dark_fig()
            ax_tl = _ax_dark(fig, 1, 1, 1)
            ax_tl.set_title("Timeline oraria degli eventi", color=_TXT, pad=8, fontsize=13)
            bw = 0.2
            xs = np.arange(len(hours_sorted))
            for i, (lvl, color) in enumerate([
                ("DEBUG", _DBG), ("INFO", _INF), ("WARN", _WRN), ("ERROR", _ERR)
            ]):
                ax_tl.bar(xs + i * bw, [hours_data[h].get(lvl, 0) for h in hours_sorted],
                          bw, label=lvl, color=color, alpha=0.85)
            ax_tl.set_xticks(xs + bw * 1.5)
            ax_tl.set_xticklabels(hours_sorted, rotation=45, ha="right",
                                   fontsize=7, color=_TXT2)
            ax_tl.set_ylabel("N. eventi", color=_TXT2, fontsize=9)
            ax_tl.legend(fontsize=8, labelcolor=_TXT,
                         facecolor=_SRF, edgecolor=COLORS["border"])
            fig.tight_layout(pad=1.5)
            pdf.savefig(fig, facecolor=fig.get_facecolor())
            plt.close(fig)

        # --- Pagina 4: AI Insights ---
        if ai_insights:
            fig = _dark_fig()
            ax_ai = fig.add_axes([0.05, 0.05, 0.9, 0.88])
            ax_ai.set_facecolor(_BG)
            ax_ai.axis("off")
            ax_ai.set_title("AI Insights", color=_TXT, pad=12, fontsize=15,
                            fontweight="bold")
            y = 0.88
            for tipo, titolo, dettaglio, color in ai_insights:
                ax_ai.text(0.02, y, f"[{tipo}]", color=color, fontsize=10,
                           fontweight="bold", transform=ax_ai.transAxes)
                ax_ai.text(0.15, y, titolo, color=_TXT, fontsize=10,
                           fontweight="bold", transform=ax_ai.transAxes)
                ax_ai.text(0.02, y - 0.04, dettaglio, color=_TXT2, fontsize=8,
                           transform=ax_ai.transAxes, wrap=True)
                y -= 0.12
                if y < 0.05:
                    pdf.savefig(fig, facecolor=fig.get_facecolor())
                    plt.close(fig)
                    fig = _dark_fig()
                    ax_ai = fig.add_axes([0.05, 0.05, 0.9, 0.88])
                    ax_ai.set_facecolor(_BG)
                    ax_ai.axis("off")
                    y = 0.88
            pdf.savefig(fig, facecolor=fig.get_facecolor())
            plt.close(fig)

        # --- Pagina 5+: tabella eventi ---
        PAGE_ROWS = 40
        for page_start in range(0, min(len(events), 2000), PAGE_ROWS):
            chunk = events[page_start:page_start + PAGE_ROWS]
            fig = _dark_fig()
            ax_tbl = _ax_dark(fig, 1, 1, 1)
            ax_tbl.axis("off")
            ax_tbl.set_title(
                f"Dettaglio eventi (righe {page_start + 1}-{page_start + len(chunk)})",
                color=_TXT, pad=8, fontsize=11)
            tbl_data = [
                [str(e["n"]), e["timestamp"][:19] or "-",
                 e["level"], e["component"][:20], e["message"][:80]]
                for e in chunk
            ]
            t = ax_tbl.table(
                cellText=tbl_data,
                colLabels=["#", "Timestamp", "Livello", "Componente", "Messaggio"],
                cellLoc="left", loc="center",
                bbox=[0.0, 0.0, 1.0, 1.0],
            )
            t.auto_set_font_size(False)
            t.set_fontsize(6.5)
            for (r, c), cell in t.get_celld().items():
                cell.set_edgecolor(COLORS["border"])
                if r == 0:
                    cell.set_facecolor(_ACC)
                    cell.set_text_props(color=_TXT, fontsize=7, fontweight="bold")
                else:
                    ev = chunk[r - 1] if r - 1 < len(chunk) else None
                    lvl = ev["level"] if ev else "INFO"
                    cell.set_facecolor(LEVEL_BG.get(lvl, _SRF))
                    cell.set_text_props(
                        color=LEVEL_COLORS.get(lvl, _TXT) if c == 2 else _TXT,
                        fontsize=6.5)
            t.auto_set_column_width([0, 1, 2, 3, 4])
            pdf.savefig(fig, facecolor=fig.get_facecolor())
            plt.close(fig)


# ---------------------------------------------------------------------------
# Report CSV Siemens
# ---------------------------------------------------------------------------

def export_pdf_csv(rows: list, headers: list, stats: dict,
                   anomalies: list, filepath: str, title: str = "MouldGraph CSV Report"):
    """Genera PDF di analisi Siemens CSV con grafici e tabella anomalie."""
    if not rows:
        raise ValueError("Nessun dato da esportare.")
    times = [r.get("_ts") for r in rows]
    times_valid = [t for t in times if t is not None]
    numeric_cols = [
        h for h in headers
        if h not in ("Record", "Date", "Time", "UTC Time", "_ts")
        and rows and isinstance(rows[0].get(h), float)
    ]
    palette = list(_UC_SERIES_PALETTE)

    with PdfPages(filepath) as pdf:
        _title_page(
            pdf, title,
            subtitle="Analisi dati CSV Siemens",
            meta=(
                f"{len(rows)} record • "
                f"{len(numeric_cols)} parametri numerici • "
                f"{len(anomalies)} anomalie rilevate"
            ),
        )

        COLS_PER_PAGE = 4
        for page_start in range(0, len(numeric_cols), COLS_PER_PAGE):
            chunk = numeric_cols[page_start:page_start + COLS_PER_PAGE]
            n_plots = len(chunk)
            if n_plots == 0:
                continue
            fig = _dark_fig(11.69, 8.27)
            for i, col in enumerate(chunk):
                ax = _ax_dark(fig, 1, n_plots, i + 1)
                ax.set_title(col, color=_TXT, fontsize=9, pad=4)
                vals = [r.get(col) for r in rows]
                xs = times_valid if times_valid else list(range(len(vals)))
                xs_p = xs[:len(vals)] if len(xs) >= len(vals) else (list(range(len(vals))))
                pairs = [(x, y) for x, y in zip(xs_p, vals) if y is not None]
                if pairs:
                    xp, yp = zip(*pairs)
                    color = palette[i % len(palette)]
                    ax.plot(xp, yp, color=color, linewidth=1.2)
                    if isinstance(xp[0], datetime):
                        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
                        plt.setp(ax.get_xticklabels(), rotation=30, fontsize=6, color=_TXT2)
                    st = stats.get(col, {})
                    if st:
                        ax.axhline(st["mean"], color="#ffffff", linewidth=0.6,
                                   linestyle=":", alpha=0.5)
            fig.tight_layout(pad=1.5)
            pdf.savefig(fig, facecolor=fig.get_facecolor())
            plt.close(fig)

        if anomalies:
            fig = _dark_fig()
            ax_an = _ax_dark(fig, 1, 1, 1)
            ax_an.axis("off")
            ax_an.set_title("Anomalie rilevate", color=_TXT, pad=8, fontsize=13)
            tbl_data = [[a[0], a[1], a[2][:80]] for a in anomalies]
            t = ax_an.table(
                cellText=tbl_data,
                colLabels=["Tipo", "Titolo", "Dettaglio"],
                cellLoc="left", loc="center",
                bbox=[0.0, 0.0, 1.0, 1.0],
            )
            t.auto_set_font_size(False)
            t.set_fontsize(7.5)
            for (r, c), cell in t.get_celld().items():
                cell.set_edgecolor(COLORS["border"])
                if r == 0:
                    cell.set_facecolor(_ACC)
                    cell.set_text_props(color=_TXT, fontsize=8, fontweight="bold")
                else:
                    cell.set_facecolor(_SRF if r % 2 == 0 else _BG)
                    an = anomalies[r - 1] if r - 1 < len(anomalies) else None
                    fc = an[3] if an and c == 0 else _TXT
                    cell.set_text_props(color=fc, fontsize=7.5)
            t.auto_set_column_width([0, 1, 2])
            pdf.savefig(fig, facecolor=fig.get_facecolor())
            plt.close(fig)


# ---------------------------------------------------------------------------
# Report CSV ciclo stampo (Universal / Long-format)
# ---------------------------------------------------------------------------

def export_pdf_mould_cycle(rows: list, headers: list, col_meta: dict,
                           numeric_cols: list, filepath: str,
                           title: str = "MouldGraph — Ciclo Stampo Report",
                           mould_info: str = ""):
    """
    Genera PDF per dati ciclo stampo (Universal CSV o Long-format).
    rows, headers, col_meta, numeric_cols: output di parse_universal_csv
    o _parse_long_cycle_csv.
    """
    if not rows:
        raise ValueError("Nessun dato ciclo da esportare.")
    palette = list(_UC_SERIES_PALETTE)

    ts_col = None
    for r in rows[:5]:
        if "_ts" in r and isinstance(r["_ts"], datetime):
            ts_col = "_ts"
            break
        if "_ts_str" in r:
            ts_col = "_ts_str"
            break

    def _get_xs(r_list):
        if ts_col == "_ts":
            return [r.get("_ts") for r in r_list]
        if ts_col == "_ts_str":
            return [_uc_parse_dt(r.get("_ts_str", "")) for r in r_list]
        return list(range(len(r_list)))

    xs = _get_xs(rows)
    use_dt = ts_col == "_ts" or (ts_col == "_ts_str" and any(isinstance(x, datetime) for x in xs))

    with PdfPages(filepath) as pdf:
        _title_page(
            pdf, title,
            subtitle="Analisi ciclo stampo",
            meta=(
                f"{len(rows)} campioni • "
                f"{len(numeric_cols)} parametri • "
                f"{mould_info or 'MouldGraph'}"
            ),
        )

        COLS_PER_PAGE = 3
        for page_start in range(0, len(numeric_cols), COLS_PER_PAGE):
            chunk = numeric_cols[page_start:page_start + COLS_PER_PAGE]
            n_plots = len(chunk)
            if not n_plots:
                continue
            fig = _dark_fig(11.69, 8.27)
            for i, col in enumerate(chunk):
                ax = _ax_dark(fig, 1, n_plots, i + 1)
                meta = col_meta.get(col, {})
                lbl  = meta.get("label", col)
                unit = meta.get("unit", "")
                ax.set_title(f"{lbl}{' [' + unit + ']' if unit else ''}",
                             color=_TXT, fontsize=9, pad=4)
                ys = []
                for r in rows:
                    val = r.get(col)
                    try:
                        ys.append(float(val))
                    except (TypeError, ValueError):
                        ys.append(None)
                pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
                if pairs:
                    xp, yp = zip(*pairs)
                    color = palette[i % len(palette)]
                    ax.plot(xp, yp, color=color, linewidth=1.2)
                    ax.fill_between(xp, yp, alpha=0.10, color=color)
                    if use_dt and isinstance(xp[0], datetime):
                        span_days = (max(xp) - min(xp)).total_seconds() / 86400 if len(xp) > 1 else 0
                        if span_days < 1:
                            fmt = mdates.DateFormatter("%H:%M:%S")
                        elif span_days < 7:
                            fmt = mdates.DateFormatter("%d/%m %H:%M")
                        else:
                            fmt = mdates.DateFormatter("%d/%m/%Y")
                        ax.xaxis.set_major_formatter(fmt)
                        plt.setp(ax.get_xticklabels(), rotation=30, fontsize=6, color=_TXT2)
                ax.set_ylabel(unit or "valore", color=_TXT2, fontsize=7)
            fig.tight_layout(pad=1.5)
            pdf.savefig(fig, facecolor=fig.get_facecolor())
            plt.close(fig)
