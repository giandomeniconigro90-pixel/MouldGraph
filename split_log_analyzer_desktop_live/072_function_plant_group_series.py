def _plant_group_series(y_cols, y2_cols, col_meta):
    groups = {}
    for col in y_cols:
        m = col_meta.get(col, {})
        unit  = m.get("unit", "")
        label = m.get("label", col)
        key = m.get("label", col) if m.get("label", col) != col else (unit or "Valori")
        if key not in groups:
            groups[key] = {"unit": unit, "cols": [], "y2": False}
        groups[key]["cols"].append(col)
    result = []
    for title, g in groups.items():
        is_y2 = any(c in y2_cols for c in g["cols"])
        result.append((title, g["unit"], g["cols"], is_y2))
    return result
