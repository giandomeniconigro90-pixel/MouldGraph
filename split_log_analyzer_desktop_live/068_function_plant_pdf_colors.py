def _plant_pdf_colors(cols):
    return {c: _PLANT_PALETTE[i % len(_PLANT_PALETTE)] for i, c in enumerate(cols)}
