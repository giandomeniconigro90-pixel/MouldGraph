def _pdf_hdr_g(fig, n):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    fig.add_artist(plt.Line2D([0.03,0.97],[0.965,0.965],transform=fig.transFigure,color="#555",lw=0.8))
    fig.text(0.50,0.985,"CAMPIONAMENTO PARAMETRI OPERATIVI",fontsize=11,fontweight="bold",ha="center",va="top",color="#111")
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")
