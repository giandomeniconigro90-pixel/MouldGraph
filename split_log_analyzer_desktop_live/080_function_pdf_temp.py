def _pdf_temp(ax, data, params, setval, title, pr):
    _pdf_setup_ax(ax, title, "", pr["temp_y"], pr["temp_yticks"], pr["x_ticks"], pr["x_max"])

    # 1. Plot Set per primo
    ax.axhline(setval, color=_PC["set_temp"], lw=0.8, zorder=4, label="SET")

    # 2. Plot Sonde
    for i, p in enumerate(params):
        if p in data:
            pts = sorted(data[p]); ys = [d[1] for d in pts]
            if not all(abs(v) < 0.01 for v in ys):
                ax.plot([d[0] for d in pts], ys, color=_PC[i+1], lw=0.7, zorder=3, label=p)
                continue
        # Dummy plot
        ax.plot([], [], color=_PC[i+1], lw=0.7, label=p)

    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=1+len(params), **_LK)
