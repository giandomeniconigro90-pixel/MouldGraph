def _pdf_vuoto(ax, data, params, setvals, title, labels, pr, ylabel="bar", bg_xmax=None, bg_ymax=None, draw_bg=True):
    if bg_xmax is None and bg_ymax is None:
        bg_xmax = pr.get("vuoto_bg_xmax", None)
        bg_ymax = pr.get("vuoto_bg_ymax", None)
    _pdf_setup_ax(ax, title, ylabel, pr["vuoto_y"], pr["vuoto_yticks"], pr["x_ticks"], pr["x_max"], bg_xmax=bg_xmax, bg_ymax=bg_ymax, draw_bg=draw_bg)
    sc = ["black","#555","#888","#aaa"]

    # 1. Disegna linee (reali se ci sono dati, altrimenti fuori dal grafico per la legenda)
    for j, sv in enumerate(setvals):
        ax.axhline(sv, color=sc[j%4], lw=0.7, linestyle="--", zorder=4, label=f"Set {j+1}")

    for i, p in enumerate(params):
        lbl = labels[i] if i < len(labels) else p
        if p in data:
            pts = sorted(data[p]); ys = [d[1] for d in pts]
            if not all(abs(v) < 0.001 for v in ys):
                ax.plot([d[0] for d in pts], ys, color=_PC[i+1], lw=0.7, zorder=3, label=lbl)
                continue
        # Dummy plot per la legenda se mancano i dati
        ax.plot([], [], color=_PC[i+1], lw=0.7, label=lbl)

    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=len(setvals)+len(params), **_LK)
