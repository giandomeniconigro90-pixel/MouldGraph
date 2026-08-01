def _logo_ax(fig, logo_path):
    ax = fig.add_axes([0.03, 0.912, 0.042, 0.045])
    try:
        import matplotlib.image as mpi
        lp = logo_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "lamborghini_logo.png")
        if lp and os.path.exists(lp):
            ax.imshow(mpi.imread(lp), aspect="auto"); ax.axis("off"); return
    except Exception: pass
    ax.set_facecolor("#e0e0e0")
    ax.text(0.5,0.5,"LOGO",ha="center",va="center",fontsize=6,color="#888",transform=ax.transAxes)
    ax.axis("off")
