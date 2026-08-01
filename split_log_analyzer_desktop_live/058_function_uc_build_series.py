def _uc_build_series(rows, x_col, y_cols, col_meta):
    if not rows:
        return [], {}, "index"
    x_type = "index"
    if x_col and x_col in col_meta:
        x_type = col_meta[x_col]["col_type"]
        if x_type not in ("datetime", "numeric"):
            x_type = "index"
    xs_raw = []
    for i, r in enumerate(rows):
        if x_col and x_type == "datetime":
            val = _uc_parse_dt(r.get(x_col, ""))
            xs_raw.append(val)
        elif x_col and x_type == "numeric":
            try:
                xs_raw.append(float(r.get(x_col, "").replace(",", ".")))
            except Exception:
                xs_raw.append(None)
        else:
            xs_raw.append(i)
    # Corregge automaticamente timestamp duplicati (es. logger al minuto)
    if x_type == "datetime":
        xs_raw = _uc_interpolate_timestamps(xs_raw)
    series = {}
    for col in y_cols:
        vals = []
        for r in rows:
            _v = r.get(col, "")
            raw_v = _v.replace(",", ".") if isinstance(_v, str) else _v
            try:
                vals.append(float(raw_v))
            except Exception:
                vals.append(None)
        series[col] = vals
    return xs_raw, series, x_type
