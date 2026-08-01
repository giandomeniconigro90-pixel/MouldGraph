def _persico_v8_cleg(ax, handles, labels, badge_ok=False):
    """Leggenda sotto il grafico in coordinate assolute di figura."""
    import matplotlib.patches as _mp
    if not handles: return
    if badge_ok:
        handles.insert(0, _mp.Patch(color="#e5f0db", label="RANGE OK"))
        labels.insert(0, "RANGE OK")
    box = ax.get_position()
    new_bottom = box.y0 + 0.075
    new_height  = box.height - 0.055
    ax.set_position([box.x0, new_bottom, box.width, new_height])
    leg_y_fig = new_bottom - 0.055
    ax.legend(handles, labels,
              loc="upper center",
              bbox_to_anchor=(box.x0 + box.width / 2, leg_y_fig),
              bbox_transform=ax.figure.transFigure,
              frameon=True, facecolor="white", edgecolor="#bbb",
              fontsize=8, handlelength=2.5, handletextpad=0.5,
              columnspacing=1.5, ncol=len(labels))
