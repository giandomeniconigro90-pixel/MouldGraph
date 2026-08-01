def _filter_partite(partite_str, stampo_name):
    """Filtra la stringa partite in base al profilo stampo."""
    if not partite_str: return partite_str
    parts = [p.strip() for p in partite_str.replace("/",",").split(",") if p.strip()]
    sn = stampo_name.upper()
    if "FRONT FIREWALL" in sn:
        filtered = [p for p in parts if "RF" in p.upper()]
    elif "CENTRAL COFANGO" in sn:
        filtered = [p for p in parts if "IC" in p.upper()]
    elif "SIDE COFANGO" in sn:
        filtered = [p for p in parts if "SD" in p.upper() or "SS" in p.upper()]
    else:
        return partite_str
    return " / ".join(filtered) if filtered else partite_str
