def _persico_v8_hdr(fig, meta, pr, logo_path=None):
    try:
        from PIL import Image as _PIL_img
        _pil_ok = True
    except ImportError:
        _pil_ok = False
    try:
        lp = logo_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "lamborghini_logo.png")
        if not os.path.exists(lp): lp = lp.replace(".png", ".jpg")
        if lp and os.path.exists(lp):
            ax_l = fig.add_axes([0.18, 0.87, 0.08, 0.06], frameon=False)
            if _pil_ok:
                ax_l.imshow(np.array(_PIL_img.open(lp).convert("RGBA")))
            else:
                ax_l.text(0.5, 0.5, "Logo\nnon disp.", ha="center", va="center",
                          fontsize=8, color="#aaa", transform=ax_l.transAxes)
            ax_l.axis("off")
    except Exception: pass
    fig.text(0.50,0.915,"automobili",fontsize=15,ha="center",va="center",style="italic",family="serif")
    fig.text(0.50,0.890,"Lamborghini",fontsize=24,ha="center",va="center",style="italic",family="serif",fontweight="bold")
    fig.text(0.50,0.870,"COMPRESSION MOULDING SYSTEM - CFK TECNOLOGY",fontsize=8,fontweight="bold",ha="center",va="top")
    axp=fig.add_axes([0.72,0.875,0.09,0.05],frameon=False); axp.set_xlim(0,1); axp.set_ylim(0,1); axp.axis("off")
    axp.add_patch(plt.Polygon([[0.05,0.1],[0.95,0.1],[0.5,0.9]],fill=True,color="#888"))
    t0s=meta.get("tsstart"); tNs=meta.get("tsend")
    fig.text(0.18,0.84,"Report generato:",fontsize=7,fontweight="bold")
    fig.text(0.31,0.84,meta.get("tsraw","")[:16],fontsize=7,fontweight="bold")
    fig.text(0.44,0.84,"Inizio ciclo",fontsize=7)
    fig.text(0.51,0.84,t0s.strftime("%Y-%m-%dT%H:%M:%S.000Z") if t0s else "",fontsize=7,fontweight="bold")
    fig.text(0.44,0.825,"Fine ciclo",fontsize=7)
    fig.text(0.51,0.825,tNs.strftime("%Y-%m-%dT%H:%M:%S.000Z") if tNs else "",fontsize=7,fontweight="bold")
    fig.text(0.72,0.84,"Teorico [Sec]",fontsize=7); fig.text(0.80,0.84,str(pr.get("teorico_sec","-")),fontsize=7)
    fig.text(0.72,0.825,"Durata [Sec]",fontsize=7); fig.text(0.80,0.825,str(meta.get("dursec","-")),fontsize=7)
    fig.text(0.50,0.04,
        "Copyright (c) 2023 Automobili Lamborghini S.p.A., societa ad azionista unico parte del Gruppo Audi.\n"
        "Tutti i diritti riservati. P.IVA n. 00591801204",
        fontsize=7.5,ha="center",va="bottom",color="#111",linespacing=1.6,fontweight="bold")
