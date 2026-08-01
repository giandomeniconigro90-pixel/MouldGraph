def detect_csv_type(headers):
    h=set(headers)
    temp_cols=sum(1 for i in range(1,9) if f"T{i}" in h or f"TS{i}" in h or f"TI{i}" in h)
    pos_cols =sum(1 for i in range(1,5) if f"P{i}" in h)
    force_ok =any(c in h for c in ("SPC","FC","F1","Forza"))
    vac_ok   =any(c in h for c in ("V1","V2","VS1","VI1","Vuoto"))
    if temp_cols>=2 and (pos_cols>=2 or force_ok or vac_ok): return "front_firewall"
    return "siemens"
