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
