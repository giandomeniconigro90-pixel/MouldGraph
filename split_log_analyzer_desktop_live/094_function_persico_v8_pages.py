def _persico_v8_pages(pdf, data, meta, pr, logo_path=None):
    import matplotlib.patches as _mp
    CT1,CT2,CT3,CT4 = "#e5672c","#828282","#407da5","#e7b73b"
    CSP = "#659346"
    TV   = pr.get("x_ticks_tv", list(range(44, 1452+1, 44)))
    POS  = pr.get("x_ticks_pos", list(range(11, 1463+1, 44)))
    FORZ = pr.get("x_ticks_forza", list(range(44, 1496+1, 44)))
    VAC_SUP = pr.get("x_ticks_vac_sup", TV)
    VAC_INF = pr.get("x_ticks_vac_inf", TV)

    _cc_t_max = 0
    PS = dict(
        temp_y      = pr.get("temp_y",   (100,160)),
        temp_yticks = pr.get("temp_yticks",[100,110,120,130,140,150,160]),
        temp_range  = pr.get("temp_range", (130, 150)),
        tss         = pr.get("temp_set_sup", 130.0),
        tsi         = pr.get("temp_set_inf", 128.0),
        forza_y     = pr.get("forza_y",  (6000,6800)),
        forza_yticks= pr.get("forza_yticks",[6000,6100,6200,6300,6400,6500,6600,6700,6800]),
        forza_range = pr.get("forza_range", (6250, 6750)),
        spc         = pr.get("forza_spc", 6500.0),
        vuoto_y     = pr.get("vuoto_y",  (-1000,0)),
        vuoto_yticks= pr.get("vuoto_yticks",[-1000,-900,-800,-700,-600,-500,-400,-300,-200,-100,0]),
        vuoto_range = pr.get("vuoto_range", (-1000, -200)))
    def gs(p):
        if p not in data: return [],[]
        pts=sorted(data[p]); return [x[0] for x in pts],[x[1] for x in pts]
    _skip_s = pr.get("skip_seconds", 0)
    def gs_skip(p):
        if p not in data: return [],[]
        pts=[x for x in sorted(data[p]) if x[0] >= _skip_s]
        if not pts: return [],[]
        return [x[0] for x in pts],[x[1] for x in pts]
    FW,FH = 8.27,11.69; L,W = 0.18,0.64

    # -- Pag.1: copertina + temperatura sup + inf ------------------------------
    fig = plt.figure(figsize=(FW,FH), facecolor="white")
    _persico_v8_hdr(fig, meta, pr, logo_path)
    rows_t=[("ID CICLO",str(meta.get("idciclo",""))),("SERIAL NUMBER",meta.get("partite","")),
            ("RICETTA",pr.get("ricetta","3")),("NOME OPERATORE",meta.get("operatore","NOME OPERATORE")),
            ("CODICE MATERIALE",meta.get("materiale","")),("DATA",meta.get("tsraw","").replace("T"," "))]
    if meta.get("note"): rows_t.append(("NOTE", meta["note"]))
    rh=0.015; ty=0.81
    for lbl,val in rows_t:
        fig.add_artist(_mp.Rectangle((0.18,ty-rh),0.64,rh,fill=False,edgecolor="#000",lw=0.7,
                                     transform=fig.transFigure,clip_on=False))
        fig.add_artist(plt.Line2D([0.33,0.33],[ty-rh,ty],transform=fig.transFigure,color="#000",lw=0.7))
        fig.text(0.185,ty-rh/2,lbl,fontsize=7.5,va="center",fontweight="bold")
        fig.text(0.335,ty-rh/2,str(val),fontsize=7.5,va="center",fontweight="bold"); ty-=rh
    ax_ts=fig.add_axes([L,0.42,W,0.23]); ax_ti=fig.add_axes([L,0.11,W,0.23])
    _persico_v8_setup_ax(ax_ts,"Temperatura semistampo superiore (°C) - Grafico",
                         "[°C]",PS["temp_y"],PS["temp_yticks"],TV,"temp", PS["temp_range"])
    ax_ts.plot([],[],color=CSP,label="SP",lw=1.2); ax_ts.axhline(PS["tss"],color=CSP,lw=0.8,zorder=3)
    for c,col in zip([CT1,CT3,CT2,CT4],["TS1","TS3","TS2","TS4"]):
        xs,ys=gs(col)
        if xs: ax_ts.plot(xs,ys,color=c,lw=1.2,label=col.replace("TS","T"),zorder=4)
    h,l=ax_ts.get_legend_handles_labels(); _persico_v8_cleg(ax_ts,h,l,True)
    
    _persico_v8_setup_ax(ax_ti,"Temperatura semistampo inferiore (°C) - Grafico",
                         "[°C]",PS["temp_y"],PS["temp_yticks"],TV,"temp", PS["temp_range"])
    ax_ti.plot([],[],color=CSP,label="SP",lw=1.2); ax_ti.axhline(PS["tsi"],color=CSP,lw=0.8,zorder=3)
    for c,col in zip([CT3,CT1,CT2,CT4],["TI3","TI1","TI2","TI4"]):
        xs,ys=gs(col)
        if xs: ax_ti.plot(xs,ys,color=c,lw=1.2,label=col.replace("TI","T"),zorder=4)
    h,l=ax_ti.get_legend_handles_labels(); _persico_v8_cleg(ax_ti,h,l,True)
    
    pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)

    # -- Pag.2: posizione (Y ADATTIVA) + forza ---------------------------------
    fig = plt.figure(figsize=(FW,FH), facecolor="white")
    _persico_v8_hdr(fig, meta, pr, logo_path)
    ax_p=fig.add_axes([L,0.48,W,0.28]); ax_f=fig.add_axes([L,0.11,W,0.28])
    _py,_pticks,_pdec = _posiz_y_auto(data)
    _persico_v8_setup_ax(ax_p,"Posizione piano (mm) - Grafico","[mm]",_py,_pticks,POS,"none")
    # Sovrascrive formatter con la precisione calcolata sul passo reale
    ax_p.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda v,_,d=_pdec: f"{v:.{d}f}".replace(".",",")))
    for c,col in zip([CT3,CT1,CT2,CT4],["P1","P2","P3","P4"]):
        xs,ys=gs_skip(col)
        if xs: ax_p.plot(xs,ys,color=c,lw=1.2,label=col,zorder=4)
    h,l=ax_p.get_legend_handles_labels(); _persico_v8_cleg(ax_p,h,l,False)
    _persico_v8_setup_ax(ax_f,"Forza (kN) - Grafico","[kN]",
                         PS["forza_y"],PS["forza_yticks"],FORZ,"forza", PS["forza_range"])
    ax_f.axhline(PS["spc"],color=CT1,lw=1.2,label="SPC",zorder=3)
    # Usa FC se disponibile (nativi caricati), altrimenti F1 come fallback (solo CSV)
    xs,ys=gs_skip("FC") if "FC" in data else gs_skip("F1")
    if xs: ax_f.plot(xs,ys,color=CSP,lw=1.2,label="FC",zorder=4)
    h,l=ax_f.get_legend_handles_labels(); _persico_v8_cleg(ax_f,h,l,True)
    
    pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)

    # -- Pag.3: vuoto superiore + inferiore ------------------------------------
    fig = plt.figure(figsize=(FW,FH), facecolor="white")
    _persico_v8_hdr(fig, meta, pr, logo_path)
    ax_vs=fig.add_axes([L,0.48,W,0.28]); ax_vi=fig.add_axes([L,0.11,W,0.28])
    _persico_v8_setup_ax(ax_vs,"Vuoto semistampo superiore (mbar) - Grafico","[mbar]",
                         PS["vuoto_y"],PS["vuoto_yticks"],VAC_SUP,"vuoto", PS["vuoto_range"])
    for c,col in zip([CT1,CT2],["VS1","VS2"]):
        xs,ys=gs(col)
        if xs: ax_vs.plot(xs,ys,color=c,lw=1.2,label=col.replace("VS","V"),zorder=4)
    h,l=ax_vs.get_legend_handles_labels(); _persico_v8_cleg(ax_vs,h,l,True)
    _persico_v8_setup_ax(ax_vi,"Vuoto semistampo inferiore (mbar) - Grafico","[mbar]",
                         PS["vuoto_y"],PS["vuoto_yticks"],VAC_INF,"vuoto", PS["vuoto_range"])
    for c,col in zip([CT3,CT1],["VI1","VI2"]):
        xs,ys=gs(col)
        if xs: ax_vi.plot(xs,ys,color=c,lw=1.2,label=col.replace("VI","V"),zorder=4)
    h,l=ax_vi.get_legend_handles_labels(); _persico_v8_cleg(ax_vi,h,l,True)
    
    pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
