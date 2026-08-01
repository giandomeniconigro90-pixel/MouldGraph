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
