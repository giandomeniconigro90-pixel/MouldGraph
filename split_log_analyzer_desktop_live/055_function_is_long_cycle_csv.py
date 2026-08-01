def _is_long_cycle_csv(filepath):
    """Ritorna True se il CSV è nel formato long (Partita, Parametro, Timestamp, Valore)."""
    try:
        lines = None
        for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            try:
                with open(filepath, encoding=enc) as f:
                    lines = [l for l in f.read().splitlines() if l.strip()]
                break
            except UnicodeDecodeError:
                continue
        if lines is None:
            return False
        # salta riga REPORT GENERATED
        start = 1 if lines and lines[0].upper().startswith("REPORT") else 0
        hdr = lines[start] if start < len(lines) else ""
        cols = [h.strip() for h in hdr.split(",")]
        required = {"Parametro", "Timestamp", "Valore"}
        return required.issubset(set(cols))
    except Exception:
        return False
