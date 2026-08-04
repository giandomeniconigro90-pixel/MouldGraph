"""Logica pura (senza GUI) per il parsing delle righe Live Data.

Estratto dal monolite log_analyzer_desktop_live.py (metodo
LogAnalyzerApp._live_parse_line) come primo passo del refactor.
Nessun cambiamento di comportamento: stessa logica, stesso output.
"""


def parse_live_line(line, live_headers=None):
    if not line:
        return None

    if live_headers is None:
        live_headers = []

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


def live_serial_thread(ser_module, queue_module, port, baud, running_event,
                        parse_line_fn, on_open_log=None, on_error_status=None,
                        existing_queue=None):
    import time
    live_queue = existing_queue if existing_queue is not None else queue_module.Queue(maxsize=2000)

    if ser_module is None:
        live_queue.put({"_error": "pyserial non installato."})
        return live_queue

    try:
        ser = ser_module.Serial(port, baud, timeout=1)
        if on_open_log:
            on_open_log(f"Seriale aperta: {port} @ {baud}")
    except Exception as e:
        live_queue.put({"_error": f"Errore apertura {port}: {e}"})
        return live_queue

    buf = ""
    dropped = 0
    while running_event.is_set():
        try:
            chunk = ser.read(256).decode("utf-8", errors="replace")
            buf += chunk
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                row = parse_line_fn(line.strip())
                if row:
                    try:
                        live_queue.put_nowait(row)
                    except queue_module.Full:
                        dropped += 1
        except Exception as e:
            if on_error_status:
                on_error_status(f"Errore seriale: {e}")
            time.sleep(0.05)

    try:
        ser.close()
    except Exception:
        pass
    return live_queue


def live_sim_thread(random_module, queue_module, running_event, paused_event,
                     get_speed_snapshot, sim_random, csv_path,
                     is_long_cycle_csv_fn, parse_long_cycle_csv_fn,
                     parse_universal_csv_fn, uc_try_float_fn, uc_parse_dt_fn,
                     on_log=None, existing_queue=None):
    import time
    live_queue = existing_queue if existing_queue is not None else queue_module.Queue(maxsize=2000)
    dropped = 0

    def _wait_if_paused():
        while paused_event.is_set() and running_event.is_set():
            time.sleep(0.1)

    def _speed_factor():
        sv = get_speed_snapshot() if get_speed_snapshot else "1x"
        if sv == "MAX":
            return None
        try:
            return float(sv.rstrip("x"))
        except Exception:
            return 1.0

    if sim_random or not csv_path:
        t = 0.0
        while running_event.is_set():
            _wait_if_paused()
            if not running_event.is_set():
                break
            row = {
                "_sim_t": t,
                "Temperatura": round(120 + random_module.gauss(0, 2), 2),
                "Pressione": round(5.0 + random_module.gauss(0, 0.3), 3),
                "Forza": round(3000 + random_module.gauss(0, 150), 1),
            }
            try:
                live_queue.put_nowait(row)
            except queue_module.Full:
                dropped += 1
            t += 0.5
            sf = _speed_factor()
            time.sleep(0.5 / sf if sf else 0)
        return live_queue

    try:
        if is_long_cycle_csv_fn(csv_path):
            rows, headers, col_meta, numeric_cols, datetime_cols, _, _, _ = \
                parse_long_cycle_csv_fn(csv_path)
            _has_embedded_ts = True
            if on_log:
                on_log("Formato: Long CSV (Cannon/Persico/Krauss Maffei)")
        else:
            rows, headers, col_meta, numeric_cols, datetime_cols, _, _, _ = \
                parse_universal_csv_fn(csv_path)
            _has_embedded_ts = False
    except Exception as e:
        live_queue.put({"_error": str(e)})
        return live_queue

    if not numeric_cols:
        live_queue.put({"_error": "Nessuna colonna numerica nel CSV."})
        return live_queue

    _TIME_NAMES = {"time", "tempo", "t", "sec", "seconds", "s", "zeit", "temps",
                   "elapsed", "elapsed_s", "ts", "ticks", "sample"}
    x_col_dt = datetime_cols[0] if datetime_cols else None
    x_col_num = None
    if not _has_embedded_ts:
        for h in headers:
            if h.lower().rstrip("_") in _TIME_NAMES:
                sample = [rows[i].get(h, "") for i in range(min(5, len(rows)))]
                sample_s = [str(v) for v in sample if v is not None and str(v).strip()]
                if all(uc_try_float_fn(v) for v in sample_s):
                    x_col_num = h
                    break

    use_datetime = _has_embedded_ts or (x_col_dt is not None)
    use_num_time = (not use_datetime) and (x_col_num is not None)
    prev_dt = None
    prev_num = None

    for i, r in enumerate(rows):
        if not running_event.is_set():
            break
        _wait_if_paused()
        if not running_event.is_set():
            break

        row_out = {}
        for col in numeric_cols:
            v = r.get(col)
            if isinstance(v, float):
                row_out[col] = v
            else:
                try:
                    row_out[col] = float(str(v).replace(",", "."))
                except Exception:
                    row_out[col] = None

        sf = _speed_factor()
        if _has_embedded_ts:
            ts = r.get("_ts")
            if ts:
                row_out["_ts"] = ts
                if prev_dt is not None and sf is not None:
                    delta = (ts - prev_dt).total_seconds()
                    if delta > 0:
                        time.sleep(max(0.01, delta / sf))
                prev_dt = ts
            else:
                if sf is not None:
                    time.sleep(0.1 / sf)
        elif use_datetime:
            ts = uc_parse_dt_fn(r.get(x_col_dt, ""))
            if ts:
                row_out["_ts"] = ts
                if prev_dt is not None and sf is not None:
                    delta = (ts - prev_dt).total_seconds()
                    time.sleep(max(0.01, delta / sf))
                prev_dt = ts
            else:
                if sf is not None:
                    time.sleep(0.1 / sf)
        elif use_num_time:
            try:
                t_now = float(str(r.get(x_col_num, "")).replace(",", "."))
                row_out["_sim_t"] = t_now
                if prev_num is not None and sf is not None:
                    delta = t_now - prev_num
                    if delta > 0:
                        time.sleep(max(0.01, delta / sf))
                prev_num = t_now
            except Exception:
                if sf is not None:
                    time.sleep(0.1 / sf)
        else:
            row_out["_sim_i"] = i
            if sf is not None:
                time.sleep(max(0.01, 1.0 / sf))

        try:
            live_queue.put_nowait(row_out)
        except queue_module.Full:
            dropped += 1

    return live_queue



MULTI_GROUPS = [
    ("Temp. Superiore", lambda c: c.upper().startswith("TS")),
    ("Temp. Inferiore", lambda c: c.upper().startswith("TI")),
    ("Temperatura", lambda c: c.upper().startswith("T") and not c.upper().startswith("TS") and not c.upper().startswith("TI")),
    ("Forza", lambda c: c.upper().startswith("F")),
    ("Posizione", lambda c: c.upper().startswith("P")),
    ("Vuoto", lambda c: c.upper().startswith("V")),
]


def group_live_cols(cols, groups_def=None):
    """Raggruppa le colonne per grandezza fisica.

    Estratto dal monolite log_analyzer_desktop_live.py (metodo
    LogAnalyzerApp._live_group_cols). Nessun cambiamento di comportamento.
    """
    if groups_def is None:
        groups_def = MULTI_GROUPS
    groups = {}
    assigned = set()
    for name, predicate in groups_def:
        matched = [c for c in cols if predicate(c) and c not in assigned]
        if matched:
            groups[name] = matched
            assigned.update(matched)
    remaining = [c for c in cols if c not in assigned]
    if remaining:
        groups["Altri"] = remaining
    return groups



def check_live_alarms(rows, alarm_rules, alarm_active, alarm_count):
    """Valuta l'ultimo campione rispetto alle soglie configurate (logica pura).

    Estratto dal monolite log_analyzer_desktop_live.py (metodo
    LogAnalyzerApp._live_check_alarms). Nessun cambiamento di comportamento:
    stessa logica di valutazione soglie; la parte di aggiornamento GUI
    (badge, log) resta nel monolite tramite il wrapper.

    Ritorna una tupla (now_active, newly_triggered, alarm_count) dove:
    - now_active: set delle colonne attualmente in allarme
    - newly_triggered: lista di tuple (col, val, direction) per i nuovi scatti
    - alarm_count: contatore totale scatti aggiornato
    """
    if not rows or not alarm_rules:
        return alarm_active, [], alarm_count
    last = rows[-1]
    newly_triggered = []
    now_active = set()
    for rule in alarm_rules:
        col = rule["col"]
        val = last.get(col)
        if not isinstance(val, (int, float)):
            continue
        lo = rule.get("lo")
        hi = rule.get("hi")
        in_alarm = False
        if lo is not None and val < lo:
            in_alarm = True
            direction = f"< {lo}"
        elif hi is not None and val > hi:
            in_alarm = True
            direction = f"> {hi}"
        if in_alarm:
            now_active.add(col)
            if col not in alarm_active:
                alarm_count += 1
                newly_triggered.append((col, val, direction))
    return now_active, newly_triggered, alarm_count



def export_live_rows_csv(rows, path):
    """Scrive rows (lista di dict) su file CSV, escludendo le chiavi private (prefisso '_').

    Estratto dal monolite log_analyzer_desktop_live.py (metodo
    LogAnalyzerApp._live_export_csv) come logica pura di scrittura file.
    Nessun cambiamento di comportamento: stessa logica, stesso output.
    Solleva l'eccezione in caso di errore, cosi' il chiamante puo' gestire
    l'esposizione all'utente (messagebox) senza cambiare comportamento.
    """
    import csv
    seen = {}
    for r in rows:
        for k in r:
            if not k.startswith("_"):
                seen.setdefault(k, None)
    all_keys = list(seen.keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in all_keys})
