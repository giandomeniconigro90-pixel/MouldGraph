# -*- coding: utf-8 -*-
"""Riconoscimento tipo CSV e report PDF Front Firewall."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from .pdf_lamborghini import _LK, _pdf_hdr_g_ff, _pdf_hdr_p1ff, _pdf_setup_ax
from .pdf_plant import _PC, _PROFILES


def detect_csv_type(headers):
    h=set(headers)
    temp_cols=sum(1 for i in range(1,9) if f"T{i}" in h or f"TS{i}" in h or f"TI{i}" in h)
    pos_cols =sum(1 for i in range(1,5) if f"P{i}" in h)
    force_ok =any(c in h for c in ("SPC","FC","F1","Forza"))
    vac_ok   =any(c in h for c in ("V1","V2","VS1","VI1","Vuoto"))
    if temp_cols>=2 and (pos_cols>=2 or force_ok or vac_ok): return "front_firewall"
    return "siemens"


def _group_ff_cols(headers):
    temp_sup=[c for c in headers if c.startswith("TS") and c[2:].isdigit()]
    temp_inf=[c for c in headers if c.startswith("TI") and c[2:].isdigit()]
    if not temp_sup: temp_sup=[c for c in headers if c.startswith("T") and c[1:].isdigit() and 1<=int(c[1:])<=4]
    if not temp_inf: temp_inf=[c for c in headers if c.startswith("T") and c[1:].isdigit() and 4<int(c[1:])<=8]
    pos  =[c for c in headers if c.startswith("P") and c[1:].isdigit()]
    force=[c for c in headers if c in ("SPC","FC","F1","Forza")]
    vac_s=[c for c in headers if c in ("VS1","VS2","V1","V2")]
    vac_i=[c for c in headers if c in ("VI1","VI2","VI3","VI4","V3","V4")]
    return {"temp_sup":temp_sup,"temp_inf":temp_inf,"pos":pos,"force":force,"vac_s":vac_s,"vac_i":vac_i}


def generate_front_firewall_pdf(rows, headers, output_path, logo_path=None):
    if not rows: raise ValueError("Nessun dato disponibile.")
    pr=_PROFILES["Front Firewall"]; grp=_group_ff_cols(headers)
    times=[r["_ts"] for r in rows if r.get("_ts")]
    if not times: raise ValueError("Nessun timestamp valido.")
    t0=times[0]; tN=times[-1]
    xs=[(r["_ts"]-t0).total_seconds() if r.get("_ts") else None for r in rows]
    xmax=max((x for x in xs if x is not None),default=pr["x_max"])
    pr2=dict(pr); pr2["x_ticks"]=[round(i*xmax/10) for i in range(11)]; pr2["x_max"]=xmax if xmax>0 else pr["x_max"]
    def gs(col): return [(xs[i],rows[i][col]) for i in range(len(rows)) if xs[i] is not None and isinstance(rows[i].get(col),float)]
    meta={"idciclo":"","partite":"Front Firewall","operatore":"","materiale":"",
          "tsraw":t0.strftime("%d/%m/%Y %H:%M:%S") if t0 else "","tsstart":t0,"tsend":tN,
          "dursec":int((tN-t0).total_seconds()) if t0 and tN else 0,"teorico_sec":pr.get("teorico_sec","")}
    FW,FH=8.27,11.69; L,W,MID,BOT,H=0.10,0.87,0.490,0.055,0.375
    with PdfPages(output_path) as pdf:
        fig=plt.figure(figsize=(FW,FH),facecolor="white")
        _pdf_hdr_p1ff(fig,meta,pr2,1,logo_path=logo_path); pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
        fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g_ff(fig,2,meta)
        ax_ts=fig.add_axes([L,MID+0.01,W,H]); ax_ti=fig.add_axes([L,BOT,W,H])
        _pdf_setup_ax(ax_ts,"Temperatura semistampo superiore [°C]","°C",pr2["temp_y"],pr2["temp_yticks"],pr2["x_ticks"],pr2["x_max"])
        ax_ts.axhline(pr2["temp_set_sup"],color=_PC["set_temp"],lw=0.8,label="SET")
        for i,col in enumerate(grp["temp_sup"][:4]):
            pts=gs(col)
            if pts: ax_ts.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_ts.get_legend_handles_labels(); ax_ts.legend(h2,l2,loc="lower right",ncol=5,**_LK)
        _pdf_setup_ax(ax_ti,"Temperatura semistampo inferiore [°C]","°C",pr2["temp_y"],pr2["temp_yticks"],pr2["x_ticks"],pr2["x_max"])
        ax_ti.axhline(pr2["temp_set_inf"],color=_PC["set_temp"],lw=0.8,label="SET")
        for i,col in enumerate(grp["temp_inf"][:4]):
            pts=gs(col)
            if pts: ax_ti.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_ti.get_legend_handles_labels(); ax_ti.legend(h2,l2,loc="lower right",ncol=5,**_LK)
        pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
        fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g_ff(fig,3,meta)
        ax_p=fig.add_axes([L,MID+0.01,W,H]); ax_f=fig.add_axes([L,BOT,W,H])
        _pdf_setup_ax(ax_p,"Posizione piano [mm]","mm",pr2["posiz_y"],pr2["posiz_yticks"],pr2["x_ticks"],pr2["x_max"],draw_bg=False)
        for i,col in enumerate(grp["pos"][:4]):
            pts=gs(col)
            if pts: ax_p.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        ax_p.axhline(0,color="#999",lw=0.4,linestyle="--",zorder=2)
        h2,l2=ax_p.get_legend_handles_labels(); ax_p.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        _pdf_setup_ax(ax_f,"Forza SPC / FC [kN]","kN",pr2["forza_y"],pr2["forza_yticks"],pr2["x_ticks"],pr2["x_max"],draw_bg=False)
        spc=pr2.get("forza_spc",6500.0); fd=pr2["forza_delta"]
        ax_f.axhline(spc,color=_PC["set_forza"],lw=0.8,label="SPC"); ax_f.axhline(spc+fd,color=_PC["lmax"],lw=1.0,label="LMax"); ax_f.axhline(spc-fd,color=_PC["lmin"],lw=1.0,label="LMin")
        for i,col in enumerate(grp["force"][:2]):
            pts=gs(col)
            if pts: ax_f.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_f.get_legend_handles_labels(); ax_f.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
        fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g_ff(fig,4,meta)
        ax_vs=fig.add_axes([L,MID+0.01,W,H]); ax_vi=fig.add_axes([L,BOT,W,H])
        _pdf_setup_ax(ax_vs,"Vuoto semistampo superiore [mbar]","mbar",pr2["vuoto_y"],pr2["vuoto_yticks"],pr2["x_ticks"],pr2["x_max"])
        for i,col in enumerate(grp["vac_s"][:2]):
            pts=gs(col)
            if pts: ax_vs.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_vs.get_legend_handles_labels(); ax_vs.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        _pdf_setup_ax(ax_vi,"Vuoto semistampo inferiore [mbar]","mbar",pr2["vuoto_y"],pr2["vuoto_yticks"],pr2["x_ticks"],pr2["x_max"])
        for i,col in enumerate(grp["vac_i"][:2]):
            pts=gs(col)
            if pts: ax_vi.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_vi.get_legend_handles_labels(); ax_vi.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
