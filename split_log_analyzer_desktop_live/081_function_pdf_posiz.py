def _pdf_posiz(ax, data, params, pr):
    _pdf_setup_ax(ax, "POSIZIONE [mm]", "mm", pr["posiz_y"], pr["posiz_yticks"], pr["x_ticks"], pr["x_max"], draw_bg=False)

    # Nessun set qui, solo Sonde / Posizioni
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
