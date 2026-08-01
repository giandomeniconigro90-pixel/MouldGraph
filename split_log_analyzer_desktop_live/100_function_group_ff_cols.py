def _group_ff_cols(headers):
    temp_sup=[c for c in headers if c.startswith("TS") and c[2:].isdigit()]
    temp_inf=[c for c in headers if c.startswith("TI") and c[2:].isdigit()]
    if not temp_sup: temp_sup=[c for c in headers if c.startswith("T") and c[1:].isdigit() and 1<=int(c[1:])<=4]
    if not temp_inf: temp_inf=[c for c in headers if c.startswith("T") and c[1:].isdigit() and 4<int(c[1:])<=8]
    pos  =[c for c in headers if c.startswith("P") and c[1:].isdigit()]
    force=[c for c in headers if c in ("SPC","FC","F1","Forza")]
    vac_s=[c for c in headers if c in ("VS1","VS2","V1","V2")]
    vac_i=[c for c in headers if c in ("VI1","VI2","VI3","VI4","V3","V4")]
    return {"temp_sup":temp_sup,"temp_inf":temp_inf,"pos":pos,"force":force,"vac_s":vac_s,"vac_i":vac_i}
