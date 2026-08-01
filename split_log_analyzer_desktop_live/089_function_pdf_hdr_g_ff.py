def _pdf_hdr_g_ff(fig, n, meta):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    fig.add_artist(plt.Line2D([0.03,0.97],[0.965,0.965],transform=fig.transFigure,color="#555",lw=0.8))
    fig.text(0.50,0.985,"COMPRESSION MOULDING SYSTEM - CFK TECNOLOGY",fontsize=10,fontweight="bold",ha="center",va="top",color="#111")
    fig.text(0.03,0.975,f"Report: {datetime.now().strftime('%d/%m/%Y %H:%M')}",fontsize=7,va="top",color="#555")
    fig.text(0.03,0.968,
             f"Inizio: {_pdf_fmt_ts(meta.get('tsstart'))}  Fine: {_pdf_fmt_ts(meta.get('tsend'))}  "
             f"Durata: {meta.get('dursec','-')} sec  Teorico: {meta.get('teorico_sec',meta.get('teorico','-'))} sec",
             fontsize=6.5,va="top",color="#444")
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")
