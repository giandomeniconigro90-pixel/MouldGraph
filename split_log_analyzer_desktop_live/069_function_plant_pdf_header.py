def _plant_pdf_header(fig, title, subtitle, logo_path, page_num, total_pages,
                      generated_at, meta_rows):
    fig.add_artist(plt.Line2D(
        [0.03, 0.97], [0.997, 0.997],
        transform=fig.transFigure, color="#444", lw=1.0))
    if logo_path and os.path.exists(logo_path):
        try:
            import matplotlib.image as _mpi
            ax_l = fig.add_axes([0.03, 0.948, 0.055, 0.042], frameon=False)
            ax_l.imshow(_mpi.imread(logo_path), aspect="auto")
            ax_l.axis("off")
            tx_x = 0.10
        except Exception:
            tx_x = 0.03
    else:
        tx_x = 0.03
    fig.text(tx_x, 0.978, title, fontsize=13, fontweight="bold", va="top", color="#111")
    fig.text(tx_x, 0.961, subtitle, fontsize=8.5, va="top", color="#555")
    fig.text(0.97, 0.978, f"Generato: {generated_at}",
             fontsize=7.5, ha="right", va="top", color="#777")
    fig.text(0.97, 0.963, f"Pag. {page_num} / {total_pages}",
             fontsize=7.5, ha="right", va="top", color="#777")
    fig.add_artist(plt.Line2D(
        [0.03, 0.97], [0.950, 0.950],
        transform=fig.transFigure, color="#aaa", lw=0.5))
    if meta_rows:
        y0 = 0.943
        rh = 0.022
        for lbl, val in meta_rows[:8]:
            fig.text(0.03, y0, lbl, fontsize=7.5, fontweight="bold", va="top", color="#333")
            fig.text(0.22, y0, str(val), fontsize=7.5, va="top", color="#111")
            fig.add_artist(plt.Line2D(
                [0.03, 0.97], [y0 - 0.017, y0 - 0.017],
                transform=fig.transFigure, color="#ddd", lw=0.4))
            y0 -= rh
        fig.add_artist(plt.Line2D(
            [0.03, 0.97], [y0 - 0.004, y0 - 0.004],
            transform=fig.transFigure, color="#888", lw=0.6))
        return y0 - 0.012
    return 0.940
