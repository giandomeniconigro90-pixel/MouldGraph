def _pdf_hdr_p1ff(fig, meta, pr, n, logo_path=None):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    fig.add_artist(plt.Line2D([0.03,0.97],[0.730,0.730],transform=fig.transFigure,color="#555",lw=0.8))
    _logo_ax(fig, logo_path)
    fig.text(0.08,0.966,"Automobili Lamborghini",fontsize=9,fontweight="bold",va="top",color="#111")
    fig.text(0.08,0.952,"Via Modena, 12",fontsize=7.5,va="top",color="#333")
    fig.text(0.08,0.939,"140019 - Sant'Agata Bolognese (BO)",fontsize=7.5,va="top",color="#333")
    fig.text(0.97,0.966,"Report generato",fontsize=8,ha="right",va="top",color="#555")
    fig.text(0.97,0.952,datetime.now().strftime("%d/%m/%Y %H:%M"),fontsize=8,ha="right",va="top",color="#333")
    fig.text(0.50,0.910,"COMPRESSION MOULDING SYSTEM - CFK TECNOLOGY",fontsize=12,fontweight="bold",ha="center",va="top",color="#111")
    y=0.860; step=0.036
    def row(lbl,val):
        nonlocal y
        fig.text(0.08,y,lbl,fontsize=7.5,fontweight="bold",va="top",color="#111")
        fig.text(0.35,y,val,fontsize=7.5,va="top",color="#222")
        fig.add_artist(plt.Line2D([0.08,0.65],[y-0.016,y-0.016],transform=fig.transFigure,color="#ccc",lw=0.5))
        y-=step
    row("ID CICLO",str(meta.get("idciclo",""))); row("SERIAL NUMBER",meta.get("partite",""))
    row("RICETTA",str(pr.get("ricetta",""))); row("NOME OPERATORE",meta.get("operatore",""))
    row("CODICE MATERIALE",meta.get("materiale","")); row("DATA",meta.get("tsraw","").replace("T"," "))
    row("Inizio ciclo",_pdf_fmt_ts(meta.get("tsstart"))); row("Fine ciclo",_pdf_fmt_ts(meta.get("tsend")))
    row("Teorico Sec",str(pr.get("teorico_sec","-"))); row("Durata Sec",str(meta.get("dursec","-")))
    fig.text(0.50,0.72,"Copyright 2023 Automobili Lamborghini S.p.A., societa ad azionista unico parte del Gruppo Audi.",
             fontsize=6,ha="center",va="top",color="#888")
    fig.text(0.50,0.710,"Tutti i diritti riservati. P.IVA n. 00591801204",fontsize=6,ha="center",va="top",color="#888")
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")
