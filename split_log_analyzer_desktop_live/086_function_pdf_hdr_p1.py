def _pdf_hdr_p1(fig, meta, pr, n, logo_path=None):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    _logo_ax(fig, logo_path)
    fig.text(0.08,0.966,"Automobili Lamborghini",fontsize=9,fontweight="bold",va="top",color="#111")
    fig.text(0.08,0.952,"Via Modena, 12",fontsize=7.5,va="top",color="#333")
    fig.text(0.08,0.939,"140019 - Sant'Agata Bolognese (BO)",fontsize=7.5,va="top",color="#333")
    fig.text(0.08,0.926,"Tel.: +39 051 959.7611",fontsize=7.5,va="top",color="#333")
    fig.text(0.50,0.985,"CAMPIONAMENTO PARAMETRI OPERATIVI",fontsize=11,fontweight="bold",ha="center",va="top",color="#111")
    fig.add_artist(plt.Line2D([0.03,0.97],[0.913,0.913],transform=fig.transFigure,color="#aaa",lw=0.5))
    fields=[("ID Ciclo",meta["idciclo"]),("Codice Partita",meta["partite"]),
            ("Nome Ricetta",pr["ricetta"]),("Nome Operatore",meta.get("operatore","")),
            ("Codice Materiale",meta["materiale"]),("Data",_pdf_fmt_date(meta["tsraw"]))]
    if meta.get("note"): fields.append(("Note", meta["note"]))
    y0=0.908; rh=0.022
    for i,(lbl,val) in enumerate(fields):
        y=y0-i*rh
        fig.text(0.03,y,lbl,fontsize=7.5,fontweight="bold",va="top",color="#111")
        fig.text(0.22,y,val,fontsize=7.5,va="top",color="#222")
        fig.add_artist(plt.Line2D([0.03,0.97],[y-0.016,y-0.016],transform=fig.transFigure,color="#ccc",lw=0.5))
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")
