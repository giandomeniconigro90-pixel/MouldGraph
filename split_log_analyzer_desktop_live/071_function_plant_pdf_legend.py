def _plant_pdf_legend(ax, ncol=4):
    h, l = ax.get_legend_handles_labels()
    if not h:
        return
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              ncol=min(ncol, len(l)), fontsize=7, framealpha=0.9,
              edgecolor="#ccc", handlelength=2.0, borderpad=0.5, labelspacing=0.3)
