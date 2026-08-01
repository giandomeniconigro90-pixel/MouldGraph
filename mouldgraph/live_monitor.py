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



def live_serial_thread(ser_module, queue_module, port, baud, running_event,
                        parse_line_fn, on_open_log=None, on_error_status=None):
    """Worker di lettura seriale per il tab Live Data.

    Estratto fedelmente da LogAnalyzerApp._live_serial_thread. Nessun
    cambiamento di comportamento: stessa apertura porta, stesso buffering
    a righe, stesso inoltro in coda e stessa gestione errori.

    Parametri (tutti equivalenti alle dipendenze usate dal monolite):
        ser_module: modulo 'serial' (pyserial) gia' importato dal chiamante.
        queue_module: modulo 'queue' (alias _queue nel monolite), usato per
            intercettare _queue.Full.
        port, baud: parametri di apertura porta seriale.
        running_event: threading.Event equivalente a self._live_running.
        parse_line_fn: funzione (line) -> dict|None, equivalente a
            self._live_parse_line (qui: parse_live_line gia' bindata agli
            headers correnti dal chiamante).
        on_open_log(msg): callback opzionale invocata dopo apertura porta
            riuscita, equivalente a self.after(0, self._live_log_append, ...).
        on_error_status(msg): callback opzionale invocata sugli errori di
            lettura, equivalente a self.after(0, self._live_set_status, ...).

    Ritorna:
        queue.Queue: coda con le righe lette (equivalente a self._live_queue),
            oppure la coda passata da fuori se si desidera integrarla — vedi
            nota d'uso in tabs/live_data.py (non ancora implementato).
    """
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
                     on_log=None):
    """Worker di simulazione/riproduzione CSV per il tab Live Data.

    Estratto fedelmente da LogAnalyzerApp._live_sim_thread. Nessun
    cambiamento di comportamento: stessa simulazione random pura, stessa
    riproduzione CSV (long-cycle o universale), stesso rilevamento della
    colonna tempo, stesso ritmo di invio basato sullo speed factor.

    Parametri (equivalenti alle dipendenze usate dal monolite):
        random_module: modulo 'random' gia' importato dal chiamante.
        queue_module: modulo 'queue' (alias _queue nel monolite).
        running_event: threading.Event equivalente a self._live_running.
        paused_event: threading.Event equivalente a self._live_paused.
        get_speed_snapshot: funzione () -> str, equivalente alla lettura di
            self._live_speed_snapshot (mai una StringVar dal thread).
        sim_random: bool, equivalente a self._live_sim_random.
        csv_path: str|None, equivalente a self._live_csv_path.
        is_long_cycle_csv_fn, parse_long_cycle_csv_fn, parse_universal_csv_fn,
            uc_try_float_fn, uc_parse_dt_fn: funzioni di mouldgraph.csv_parsers
            (rispettivamente _is_long_cycle_csv, _parse_long_cycle_csv,
            parse_universal_csv, _uc_try_float, _uc_parse_dt).
        on_log(msg): callback opzionale per il log, equivalente a
            self.after(0, self._live_log_append, ...).

    Ritorna:
        queue.Queue: coda con le righe generate/riprodotte (equivalente a
            self._live_queue).
    """
    import time

    live_queue = existing_queue if existing_queue is not None else queue_module.Queue(maxsize=2000)
    dropped = 0

    def _wait_if_paused():
        """Blocca il thread finche' la simulazione e' in pausa."""
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
        # simulazione puramente random
        t = 0.0
        while running_event.is_set():
            _wait_if_paused()
            if not running_event.is_set():
                break
            row = {"_sim_t": t,
                   "Temperatura": round(120 + random_module.gauss(0, 2), 2),
                   "Pressione": round(5.0 + random_module.gauss(0, 0.3), 3),
                   "Forza": round(3000 + random_module.gauss(0, 150), 1)}
            try:
                live_queue.put_nowait(row)
            except queue_module.Full:
                dropped += 1
            t += 0.5
            sf = _speed_factor()
            time.sleep(0.5 / sf if sf else 0)
        return live_queue

    # ── riproduzione CSV ──────────────────────────────────────────
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

    # ── rileva la colonna tempo ────────────────────────────────────
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



def live_serial_thread(ser_module, queue_module, port, baud, running_event,
                        parse_line_fn, on_open_log=None, on_error_status=None,
                        existing_queue=None):
    """Worker di lettura seriale per il tab Live Data.

    Estratto fedelmente da LogAnalyzerApp._live_serial_thread. Nessun
    cambiamento di comportamento: stessa apertura porta, stesso buffering
    a righe, stesso inoltro in coda e stessa gestione errori.

    Parametri (tutti equivalenti alle dipendenze usate dal monolite):
        ser_module: modulo 'serial' (pyserial) gia' importato dal chiamante.
        queue_module: modulo 'queue' (alias _queue nel monolite), usato per
            intercettare _queue.Full.
        port, baud: parametri di apertura porta seriale.
        running_event: threading.Event equivalente a self._live_running.
        parse_line_fn: funzione (line) -> dict|None, equivalente a
            self._live_parse_line (qui: parse_live_line gia' bindata agli
            headers correnti dal chiamante).
        on_open_log(msg): callback opzionale invocata dopo apertura porta
            riuscita, equivalente a self.after(0, self._live_log_append, ...).
        on_error_status(msg): callback opzionale invocata sugli errori di
            lettura, equivalente a self.after(0, self._live_set_status, ...).

    Ritorna:
        queue.Queue: coda con le righe lette (equivalente a self._live_queue).
    """
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
                     on_log=None,
                     existing_queue=None):
    """Worker di simulazione/riproduzione CSV per il tab Live Data.

    Estratto fedelmente da LogAnalyzerApp._live_sim_thread. Nessun
    cambiamento di comportamento: stessa simulazione random pura, stessa
    riproduzione CSV (long-cycle o universale), stesso rilevamento della
    colonna tempo, stesso ritmo di invio basato sullo speed factor.

    Ritorna:
        queue.Queue: coda con le righe generate/riprodotte (equivalente a
            self._live_queue).
    """
    import time

    live_queue = existing_queue if existing_queue is not None else queue_module.Queue(maxsize=2000)
    dropped = 0

    def _wait_if_paused():
        """Blocca il thread finche' la simulazione e' in pausa."""
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
            row = {"_sim_t": t,
                   "Temperatura": round(120 + random_module.gauss(0, 2), 2),
                   "Pressione": round(5.0 + random_module.gauss(0, 0.3), 3),
                   "Forza": round(3000 + random_module.gauss(0, 150), 1)}
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
