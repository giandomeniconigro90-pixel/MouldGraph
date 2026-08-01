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
