def _parse_native_pack(native_paths, stampo_name=""):
    """Legge file nativi Persico 2500T. native_paths = dict {tipo: filepath}"""
    from datetime import datetime as _dt
    def _read_wide(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = [l for l in f.readlines() if l.strip()]
        start = 1 if lines and lines[0].upper().startswith("REPORT") else 0
        hdr = [h.strip() for h in lines[start].split(";")]
        rows = []
        for l in lines[start+1:]:
            parts = l.strip().split(";")
            row = {hdr[i]: parts[i].strip().replace(",",".") for i in range(min(len(hdr),len(parts))) if hdr[i]}
            rows.append(row)
        return hdr, rows
    def _to_pts(rows, col, sp_col=None):
        pts = []
        for r in rows:
            try:
                t = float(r.get("Time",""))
                s = r.get(col,"").strip()
                if not s: continue
                val = float(s)
                sp = None
                if sp_col:
                    try: sp = float(r.get(sp_col,"").strip())
                    except Exception: pass
                pts.append((t, val, 0, sp))
            except Exception: continue
        return pts
    data = {}; meta_patch = {}
    if "DATI_GENERALI" in native_paths:
        with open(native_paths["DATI_GENERALI"], encoding="utf-8", errors="replace") as f:
            dg = [l.strip() for l in f.readlines()]
        keys = ["idciclo","partite","_stampo","operatore","materiale"]
        for i,k in enumerate(keys):
            if i < len(dg) and k != "_stampo": meta_patch[k] = dg[i]
        # Filtra partita in base al profilo
        if len(dg) >= 2:
            all_parts = [p.strip() for p in dg[1].split("/") if p.strip()]
            sn = stampo_name.upper()
            if "FRONT FIREWALL" in sn:
                filtered = [p for p in all_parts if "RF" in p.upper()]
            elif "CENTRAL COFANGO" in sn:
                filtered = [p for p in all_parts if "IC" in p.upper()]
            elif "SIDE COFANGO" in sn:
                # DX = SD, SX = SS - tienile entrambe
                filtered = [p for p in all_parts if "SD" in p.upper() or "SS" in p.upper()]
            else:
                filtered = all_parts
            if filtered:
                meta_patch["partite"] = " / ".join(filtered)
        if len(dg) >= 9:
            try: meta_patch["tsraw"] = dg[8].rstrip("Z").split(".")[0].replace("T"," ")
            except Exception: pass
    if "FORZA" in native_paths:
        _, rows = _read_wide(native_paths["FORZA"])
        # Legge F1÷F4 (sensori singoli) e FC (forza combinata con setpoint SPC)
        for _c in ["F1","F2","F3","F4"]:
            pts = _to_pts(rows, _c)
            if pts: data[_c] = pts
        pts = _to_pts(rows, "FC", "SPC")
        if pts: data["FC"] = pts
    if "POSIZIONE" in native_paths:
        _, rows = _read_wide(native_paths["POSIZIONE"])
        for c in ["P1","P2","P3","P4"]:
            pts = _to_pts(rows, c)
            if pts: data[c] = pts
    if "TEMPS_SUP" in native_paths:
        _, rows = _read_wide(native_paths["TEMPS_SUP"])
        for i,c in enumerate(["T1","T2","T3","T4","T5"],1):
            pts = _to_pts(rows, c, "SP")
            if pts: data[f"TS{i}"] = pts
    if "TEMPS_INF" in native_paths:
        _, rows = _read_wide(native_paths["TEMPS_INF"])
        for i,c in enumerate(["T1","T2","T3","T4","T5"],1):
            pts = _to_pts(rows, c, "SP")
            if pts: data[f"TI{i}"] = pts
    if "VUOTO_SUP" in native_paths:
        _, rows = _read_wide(native_paths["VUOTO_SUP"])
        for i,c in enumerate(["V1","V2"],1):
            pts = _to_pts(rows, c, "SET -")
            if pts: data[f"VS{i}"] = pts
    if "VUOTO_INF" in native_paths:
        _, rows = _read_wide(native_paths["VUOTO_INF"])
        for i,c in enumerate(["V1","V2"],1):
            pts = _to_pts(rows, c, "SET -")
            if pts: data[f"VI{i}"] = pts
    return data, meta_patch
