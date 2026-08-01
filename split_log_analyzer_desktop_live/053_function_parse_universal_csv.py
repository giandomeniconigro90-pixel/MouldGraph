def parse_universal_csv(filepath):
    raw = None
    detected_enc = "utf-8"
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]:
        try:
            with open(filepath, encoding=enc) as f:
                raw = f.read()
            detected_enc = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if raw is None:
        raise ValueError("Impossibile leggere il file con gli encoding supportati.")
    lines = [l for l in raw.splitlines() if l.strip()]
    if lines and re.match(r"^(report|export|generated|file|date)\b", lines[0], re.IGNORECASE):
        lines = lines[1:]
    if not lines:
        raise ValueError("File CSV vuoto o non leggibile.")
    sample = "\n".join(lines[:6])
    counts = {s: sample.count(s) for s in [";", ",", "\t", "|"]}
    sep = max(counts, key=counts.get)
    if counts[sep] == 0:
        sep = ","
    import io as _io
    reader = csv.DictReader(_io.StringIO("\n".join(lines)), delimiter=sep)
    rows = []
    for row in reader:
        rows.append({k.strip().strip(chr(34)): v.strip().strip(chr(34))
                     for k, v in row.items() if k is not None})
    if not rows:
        raise ValueError("Nessuna riga dati trovata nel CSV.")
    headers = [h.strip().strip('"') for h in (reader.fieldnames or []) if h]
    col_meta = {}
    numeric_cols, datetime_cols, binary_cols, text_cols = [], [], [], []
    for h in headers:
        sample_vals = [rows[i].get(h, "") for i in range(min(50, len(rows)))]
        unit, label, col_type = _uc_col_meta(h, sample_vals)
        col_meta[h] = {"unit": unit, "label": label, "col_type": col_type}
        if col_type == "numeric":
            numeric_cols.append(h)
        elif col_type == "datetime":
            datetime_cols.append(h)
        elif col_type == "binary":
            binary_cols.append(h)
        else:
            text_cols.append(h)
    return rows, headers, col_meta, numeric_cols, datetime_cols, binary_cols, sep, detected_enc
