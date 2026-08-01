def _persico_v8_setup_ax(ax, title, unit, ylim, yticks, xticks, bg_type="none", bg_range=None):
    BG="#e5f0db"
    ax.set_facecolor("white"); ax.set_xlim(xticks[0], xticks[-1]); ax.set_ylim(ylim[0],ylim[1])
    ax.autoscale(False)
    if bg_range:
        ax.axhspan(bg_range[0], bg_range[1], color=BG, zorder=0)
    else:
        if bg_type=="temp":  ax.axhspan(130,150,color=BG,zorder=0)
        elif bg_type=="forza": ax.axhspan(6250,6750,color=BG,zorder=0)
        elif bg_type=="vuoto": ax.axhspan(-1000,-200,color=BG,zorder=0)
    for sp in ax.spines.values(): sp.set_visible(True); sp.set_color("#666"); sp.set_linewidth(0.8)
    ax.set_yticks(yticks)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda v,_: f"{v:.2f}".replace(".",",") if "mm" in title else f"{int(v)}"))
    ax.set_xticks(xticks); ax.tick_params(axis="both",labelsize=7,length=3,color="#666",pad=2,labelcolor="#222")
    plt.setp(ax.get_xticklabels(),rotation=90,fontsize=6)
    ax.grid(True,axis="y",color="#eaeaea",lw=0.6,linestyle="-",zorder=1); ax.grid(False,axis="x")
    ax.set_title(title,fontsize=9.5,pad=6,loc="center",color="#444")
    ax.text(-0.01,1.06,unit,transform=ax.transAxes,fontsize=7.5,ha="center",va="bottom",color="#444",clip_on=False)
    ax.text(0.995,0.04,"[Sec]",transform=ax.transAxes,fontsize=7.5,ha="right",va="bottom",color="#444")
