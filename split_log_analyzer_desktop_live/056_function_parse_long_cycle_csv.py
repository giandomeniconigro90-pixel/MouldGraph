def _parse_long_cycle_csv(filepath):
    """Parsea il CSV long-format e lo pivota in wide.
    Ritorna stessa firma di parse_universal_csv."""
    raw = None
    detected_enc = "utf-8"
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            with open(filepath, encoding=enc) as f:
                raw = f.read()
            detected_enc = enc
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        raise ValueError("Impossibile leggere il file.")

    lines = [l for l in raw.splitlines() if l.strip()]
    start = 1 if lines and lines[0].upper().startswith("REPORT") else 0
    hdr_line = lines[start]
    
    # rileva separatore dall'header (virgola o punto-e-virgola)
    _data_line = lines[start + 1] if start + 1 < len(lines) else hdr_line
    _sep = ";" if _data_line.count(";") > _data_line.count(",") else ","
    
    # header SEMPRE split con virgola
    hdr_cols = [h.strip() for h in hdr_line.split(_sep)]

    # indici colonne chiave
    try:
        i_param = hdr_cols.index("Parametro")
        i_ts    = hdr_cols.index("Timestamp")
        i_val   = hdr_cols.index("Valore")
    except ValueError as e:
        raise ValueError(f"Colonna mancante: {e}")

    # raggruppa per timestamp → {ts_str: {param: valore}}
    from collections import OrderedDict
    buckets = OrderedDict()
    for line in lines[start + 1:]:
        parts = line.split(_sep)
        if len(parts) <= max(i_param, i_ts, i_val):
            continue
        param = parts[i_param].strip()
        ts_str = parts[i_ts].strip()
        val_s  = parts[i_val].strip().replace(",", ".")
        if not param or not ts_str:
            continue
        if ts_str not in buckets:
            buckets[ts_str] = {}
        try:
            buckets[ts_str][param] = float(val_s)
        except ValueError:
            buckets[ts_str][param] = val_s

    if not buckets:
        raise ValueError("Nessun dato trovato nel CSV long-format.")

    # ordina per timestamp reale
    def _parse_ts(s):
        for fmt in [_LONG_TS_FMT,
                    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%fZ",
                    "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(s.rstrip("Z").strip(), fmt.rstrip("Z"))
            except Exception:
                pass
        return None

    sorted_ts = sorted(buckets.keys(), key=lambda s: (_parse_ts(s) or datetime.min))

    # raccoglie tutti i parametri nell'ordine di prima apparizione
    all_params = list(dict.fromkeys(
        p for ts in sorted_ts for p in buckets[ts]))

    # costruisce le righe wide
    rows = []
    for ts_str in sorted_ts:
        r = {"_ts_str": ts_str}
        ts_dt = _parse_ts(ts_str)
        if ts_dt:
            r["_ts"] = ts_dt
        for p in all_params:
            r[p] = buckets[ts_str].get(p, None)
        rows.append(r)

    # costruisce col_meta per ogni parametro numerico
    headers      = all_params
    col_meta     = {}
    numeric_cols = []
    for p in all_params:
        unit, label, col_type = _uc_col_meta(p, [
            str(rows[i].get(p, "")) for i in range(min(20, len(rows)))])
        col_meta[p] = {"unit": unit, "label": label, "col_type": "numeric"}
        numeric_cols.append(p)

    datetime_cols = []   # usiamo _ts direttamente
    binary_cols   = []

    return rows, headers, col_meta, numeric_cols, datetime_cols, binary_cols, _sep, detected_enc
