"""Logica pura (senza GUI) per il parsing delle righe Live Data.

Estratto dal monolite log_analyzer_desktop_live.py (metodo
LogAnalyzerApp._live_parse_line) come primo passo del refactor.
Nessun cambiamento di comportamento: stessa logica, stesso output.
"""


def parse_live_line(line, live_headers=None):
    """Parsa una riga CSV o key=val proveniente dalla seriale Live.

    Riproduce fedelmente il comportamento originale di
    LogAnalyzerApp._live_parse_line:
      - formato seriale key=val,key=val,...
      - CSV separato da ',' o ';'
      - mapping dei valori sulle intestazioni Live (live_headers)
      - righe non interpretabili restituite come {"_raw": line}

    Parametri:
        line: stringa grezza ricevuta dalla seriale/sorgente.
        live_headers: lista di intestazioni correnti del tab Live
            (equivalente a self._live_headers nel monolite).

    Ritorna:
        dict con i valori interpretati, oppure None se la riga è vuota
        o non produce alcuna coppia chiave/valore nel formato key=val.
    """
    if not line:
        return None

    if live_headers is None:
        live_headers = []

    # formato key=val,key=val,...
    if "=" in line:
        row = {}
        for part in line.split(","):
            kv = part.strip().split("=", 1)
            if len(kv) == 2:
                k, v = kv[0].strip(), kv[1].strip()
                try:
                    row[k] = float(v)
                except Exception:
                    row[k] = v
        return row if row else None

    # formato CSV
    parts = line.split(",")
    if len(parts) < 2:
        parts = line.split(";")

    if live_headers and len(parts) == len(live_headers):
        row = {}
        for h, v in zip(live_headers, parts):
            try:
                row[h] = float(v.strip().replace(",", "."))
            except Exception:
                row[h] = v.strip()
        return row

    return {"_raw": line}
