def _autodetect_profile(csv_path):
    """Rileva profilo stampo dal codice nella Partita (es. 26RF005449 -> RF -> Front Firewall).
    Supporta CSV con header virgola + dati punto-e-virgola e riga REPORT GENERATED iniziale.
    """
    _PM = {
        "VG": ("Inner Tub", None), "PS": ("Polecrasher", "SX"), "PD": ("Polecrasher", "DX"),
        "TD": ("Tub Floor Shell", "DX"), "ST": ("Tub Floor Shell", "SX"),
        "RF": ("Front Firewall", None), "IC": ("Central Cofango", None),
        "SD": ("Side Cofango Inner", "DX"), "SS": ("Side Cofango Inner", "SX"),
    }
    try:
        with open(csv_path, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        if not lines: return None, {}, []
        # Salta riga "REPORT GENERATED ON: ..."
        start = 1 if lines[0].upper().startswith("REPORT GENERATED") else 0
        hdr_line = lines[start] if start < len(lines) else ""
        # Indice colonna Partita (header separato da virgola)
        hdr_cols = [h.strip().strip('"') for h in hdr_line.split(_sep)]
        partita_idx = hdr_cols.index("Partita") if "Partita" in hdr_cols else 0
        # Separatore dati: ";" per Persico, "," per Cannon
        data_sep = ";" if (start + 1 < len(lines) and ";" in lines[start+1]) else ","
        # Raccolta valori Partita univoci per indice colonna
        seen = set(); partite_uniche = []
        for line in lines[start+1:]:
            parts = line.split(data_sep)
            if partita_idx < len(parts):
                p = parts[partita_idx].strip().strip('"').upper()
                if p and p not in seen:
                    seen.add(p); partite_uniche.append(p)
        # Regex: "26RF005449" -> gruppo 1 = "RF"
        profili_trovati = {}
        for p in partite_uniche:
            m = re.search(r'\d{2}([A-Z]{2})\d', p)
            if m:
                codice = m.group(1)
                if codice in _PM:
                    prof, side = _PM[codice]
                    if prof not in profili_trovati: profili_trovati[prof] = set()
                    if side: profili_trovati[prof].add(side)
        if not profili_trovati: return None, {}, partite_uniche
        return next(iter(profili_trovati)), profili_trovati, partite_uniche
    except Exception: return None, {}, []
