def _pdf_forza(ax, data, params, pr):
    _pdf_setup_ax(ax, "FORZA [kN]", "kN", pr["forza_y"], pr["forza_yticks"], pr["x_ticks"], pr["x_max"], draw_bg=False)

    # Determiniamo se abbiamo dei SET da plottare e li mettiamo prima
    ref = next((p for p in params if p in data), None)
    has_set = False
    if ref:
        pts = sorted(data[ref])
        xs = np.array([d[0] for d in pts if d[3] is not None])
        sps = np.array([d[3] for d in pts if d[3] is not None])
        if len(xs):
            has_set = True
            ax.plot(xs, sps, color=_PC["set_forza"], lw=0.8, zorder=5, label="Set")
            ax.plot(xs, sps + pr["forza_delta"], color=_PC["lmax"], lw=1.0, zorder=5, label="LMax")
            ax.plot(xs, sps - pr["forza_delta"], color=_PC["lmin"], lw=1.0, zorder=5, label="LMin")

    if not has_set:
        # Dummy per garantire che Set appaiano in legenda
        ax.plot([], [], color=_PC["set_forza"], lw=0.8, label="Set")
        ax.plot([], [], color=_PC["lmax"], lw=1.0, label="LMax")
        ax.plot([], [], color=_PC["lmin"], lw=1.0, label="LMin")

    for i, p in enumerate(params):
        lbl = f"Forza{i+1}"
        if p in data:
            pts = sorted(data[p])
            if pts:
                ax.plot([d[0] for d in pts], [d[1] for d in pts], color=_PC[i+1], lw=0.7, zorder=3, label=lbl)
                continue
        ax.plot([], [], color=_PC[i+1], lw=0.7, label=lbl)

    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3+len(params), **_LK)
