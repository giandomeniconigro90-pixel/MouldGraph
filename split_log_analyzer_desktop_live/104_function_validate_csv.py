def _validate_csv(csv_path):
    size = os.path.getsize(csv_path)
    if size > MAX_CSV_BYTES:
        return False, f"File troppo grande ({size/(1024*1024):.1f} MB). Limite: 50 MB."
    try:
        with open(csv_path, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        start = 1 if lines and lines[0].upper().startswith("REPORT GENERATED") else 0
        hdr_line = lines[start] if start < len(lines) else ""
        headers = set(h.strip() for h in hdr_line.split(_sep))
        missing = REQUIRED_COLUMNS - headers
        if missing: return False, f"Colonne mancanti: {', '.join(sorted(missing))}"
    except Exception as e:
        return False, f"Errore lettura CSV: {e}"
    return True, ""
