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
