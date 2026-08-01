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
