def _pdf_parse_csv(filepath):
    raw = None
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]:
        try:
            with open(filepath, encoding=enc) as f:
                raw = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if raw is None:
        raise ValueError("Impossibile leggere il file con gli encoding supportati.")
    lines = [l for l in raw.splitlines() if l.strip()]
    start = 1 if lines and lines[0].upper().startswith("REPORT GENERATED") else 0
    hdr = lines[start]
    data_sep = ";" if (start+1 < len(lines) and ";" in lines[start+1]) else ","
    if data_sep == ";":
        headers = [h.strip() for h in hdr.split(",")]
        rows = []
        for l in lines[start+1:]:
            parts = l.split(";")
            rows.append({h: parts[i].strip().replace(",", ".") if i < len(parts) else ""
                         for i, h in enumerate(headers)})
    else:
        import io as _io
        rows = list(csv.DictReader(_io.StringIO("\n".join(lines[start:]))))
    TSFMTS = ["%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
              "%d_%m_%Y_%H_%M_%S", "%d/%m/%Y_%H_%M_%S", "%Y-%m-%dT%H:%M:%S.%f"]
    def pt(s):
        s = s.strip().rstrip("Z")
        for fmt in TSFMTS:
            try: return datetime.strptime(s, fmt)
            except Exception: pass
        return None
    t0 = None; data = defaultdict(list); tslist = []
    for r in rows:
        ts = pt(r.get("Timestamp", ""))
        if ts is None: continue
        if t0 is None: t0 = ts
        tslist.append(ts); sec = (ts - t0).total_seconds()
        try: val = float(r.get("Valore", "").replace(",", "."))
        except Exception: continue
        try: ss = r.get("Setpoint", "").strip().replace(",", "."); sp = float(ss) if ss else None
        except Exception: sp = None
        try: step = int(r.get("Step", 0))
        except Exception: step = 0
        data[r.get("Parametro", "").strip()].append((sec, val, step, sp))
    tss = tslist[0] if tslist else None; tse = tslist[-1] if tslist else None
    dur = int((tse - tss).total_seconds()) if tss and tse else 0
    meta = {"idciclo": rows[0].get("IdCiclo", "") if rows else "",
            "partite": ", ".join(sorted(set(r.get("Partita", "") for r in rows))),
            "operatore": rows[0].get("Operatore", "") if rows else "",
            "materiale": ", ".join(sorted(set(r.get("Materiale", "") for r in rows))),
            "tsraw": rows[0].get("Timestamp", "") if rows else "",
            "tsstart": tss, "tsend": tse, "dursec": dur}
    return data, meta
