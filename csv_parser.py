# -*- coding: utf-8 -*-
import csv, re, math, os
import io as _io
from datetime import datetime
from collections import OrderedDict, defaultdict

# -- SIEMENS CSV PARSER --
def parse_siemens_csv(text):
    rows=[];headers=[]
    reader=csv.reader(text.splitlines())
    for i,row in enumerate(reader):
        if i==0:
            headers=[h.strip().strip('"') for h in row]
        else:
            if not any(c.strip() for c in row):continue
            d={}
            for j,h in enumerate(headers):
                val=row[j].strip().strip('"') if j<len(row) else ""
                try:d[h]=float(val)
                except Exception:d[h]=val
            # parse timestamp
            ts=None
            for tcol in["UTC Time","Date_Time","Datetime","timestamp","Time","Date"]:
                if tcol in d and d[tcol]:
                    for fmt in["%Y-%m-%d %H:%M:%S","%Y-%m-%dT%H:%M:%S","%d/%m/%Y %H:%M:%S",
                               "%Y-%m-%d %H:%M:%S.%f","%d-%m-%Y %H:%M:%S"]:
                        try:ts=datetime.strptime(str(d[tcol]),fmt);break
                        except Exception:pass
                if ts:break
            if ts is None and "Date" in d and "Time" in d:
                try:ts=datetime.strptime(f"{d['Date']} {d['Time']}","%Y-%m-%d %H:%M:%S")
                except Exception:pass
            d["_ts"]=ts
            rows.append(d)
    return headers,rows

def detect_anomalies(rows,headers):
    anomalies=[]
    numeric_cols=[h for h in headers if h not in("Record","Date","Time","UTC Time","_ts")
                  and rows and isinstance(rows[0].get(h),float)]
    # compute stats
    stats={}
    for col in numeric_cols:
        vals=[r[col] for r in rows if isinstance(r.get(col),float)]
        if not vals:continue
        mn=sum(vals)/len(vals)
        sd=math.sqrt(sum((v-mn)**2 for v in vals)/len(vals)) if len(vals)>1 else 0
        stats[col]={"min":min(vals),"max":max(vals),"mean":mn,"std":sd}

    for i,row in enumerate(rows):
        ts=row.get("_ts")
        ts_str=ts.strftime("%H:%M:%S") if ts else f"riga {i+1}"

        # Pompa spenta
        for pk in["Stato_Pompa","stato_pompa","pump_state","PumpState"]:
            if pk in row and str(row[pk]).strip() in("0","0.0"):
                prev=rows[i-1] if i>0 else None
                if prev and str(prev.get(pk,1)).strip() not in("0","0.0"):
                    anomalies.append(("ALLARME",f"Pompa spenta [{ts_str}]",
                        f"Stato_Pompa = 0 al record {int(row.get('Record',i+1))}. La pompa si e' fermata.","#ff4d4f"))

        # Spike fuori 2.5 sigma
        for col in numeric_cols:
            if col in("Record","Stato_Pompa","stato_pompa"):continue
            if col not in stats:continue
            val=row.get(col)
            if not isinstance(val,float):continue
            st=stats[col]
            if st["std"]>0 and abs(val-st["mean"])>2.5*st["std"]:
                direction="alto" if val>st["mean"] else "basso"
                anomalies.append(("ANOMALIA",f"{col} fuori range [{ts_str}]",
                    f"Valore {val:.2f} (media {st['mean']:.2f} +/- {st['std']:.2f}). Picco verso il {direction}.","#faad14"))

        # Livello >95%
        for lk in["Livello_Perc","livello","level","Livello"]:
            if lk in row and isinstance(row[lk],float) and row[lk]>95:
                anomalies.append(("ATTENZIONE",f"Livello critico [{ts_str}]",
                    f"{lk} = {row[lk]:.1f}% (soglia: 95%). Rischio overflow.","#faad14"))

        # Pressione <1.0 bar
        for pk2 in["Pressione_Bar","pressione","pressure","Pressione"]:
            if pk2 in row and isinstance(row[pk2],float) and row[pk2]<1.0:
                anomalies.append(("ATTENZIONE",f"Pressione bassa [{ts_str}]",
                    f"{pk2} = {row[pk2]:.2f} bar. Valore sotto la soglia minima (1.0 bar).","#ff4d4f"))

    # deduplica ravvicinati
    seen=set();out=[]
    for a in anomalies:
        key=(a[0],a[1][:30])
        if key not in seen:seen.add(key);out.append(a)
    return out,stats

# -- TIMELINE CANVAS --
# -- UNIVERSAL CSV PARSER --------------------------------------------------

UNIT_PATTERNS = [
    (r"temp|calore|forno|cottura",          "°C",    "Temperatura"),
    (r"press|bar|kpa|psi|mpa",              "bar",   "Pressione"),
    (r"forza|kn|newton|force",              "kN",    "Forza"),
    (r"portata|flow|l_min|lmin|l/min",      "L/min", "Portata"),
    (r"pos|stroke|piano|quota|mm(?!hg)",    "mm",    "Posizione"),
    (r"vel|speed|rpm|giri|rotaz",           "rpm",   "Velocità"),
    (r"vuoto|vacuum|mbar",                  "mbar",  "Vuoto"),
    (r"corr|ampere|current|amps",           "A",     "Corrente"),
    (r"volt|tension|tensione",              "V",     "Tensione"),
    (r"umid|humid|rh(?!\w)",               "%RH",   "Umidità"),
    (r"colla|glue|adhesive|erog",           "g/s",   "Erogazione"),
    (r"angolo|angle|deg(?!\w)|gradi",      "°",     "Angolo"),
    (r"peso|weight|kg(?!\w)|gram",         "kg",    "Peso"),
    (r"freq|hz(?!\w)|hertz",               "Hz",    "Frequenza"),
    (r"pot|watt|kw(?!\w)|power",           "kW",    "Potenza"),
    (r"level|livello|fill|riempim",         "%",     "Livello"),
    (r"co2|o2|gas|ppm",                     "ppm",   "Gas"),
    (r"vibr|accel|g(?!\w)",                "m/s²",  "Vibrazione"),
    (r"torque|coppia|nm(?!\w)",            "Nm",    "Coppia"),
    (r"dist|distanza|range(?!\w)",         "mm",    "Distanza"),
]

_UC_TSFMTS = [
    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",    "%d/%m/%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",    "%d.%m.%Y %H:%M",
    "%d_%m_%Y_%H_%M_%S",    "%d/%m/%Y_%H_%M_%S",
    "%Y/%m/%d %H:%M:%S",    "%m/%d/%Y %H:%M:%S",
    "%H:%M:%S",
]

def _uc_parse_dt(s):
    s = s.strip().rstrip("Z")
    for fmt in _UC_TSFMTS:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None

def _uc_try_float(s):
    try:
        float(s.replace(",", ".").replace(" ", ""))
        return True
    except Exception:
        return False

def _uc_col_meta(col_name, sample_vals):
    non_empty = [v.strip() for v in sample_vals if v.strip()]
    if not non_empty:
        return "", col_name, "text"
    dt_ok = sum(1 for v in non_empty[:8] if _uc_parse_dt(v) is not None)
    if dt_ok >= max(1, len(non_empty[:8]) // 2):
        return "", col_name, "datetime"
    num_ok = sum(1 for v in non_empty[:20] if _uc_try_float(v))
    if num_ok >= max(1, len(non_empty[:20]) * 0.7):
        uniq = set(v.strip() for v in non_empty[:50])
        if uniq <= {"0", "1", "0.0", "1.0", "True", "False", "true", "false"}:
            return "", col_name, "binary"
        cn_low = col_name.lower()
        for pattern, unit, label in UNIT_PATTERNS:
            if re.search(pattern, cn_low):
                return unit, label, "numeric"
        return "", col_name, "numeric"
    return "", col_name, "text"

def parse_universal_csv(filepath):
    raw = None
    detected_enc = "utf-8"
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]:
        try:
            with open(filepath, encoding=enc) as f:
                raw = f.read()
            detected_enc = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if raw is None:
        raise ValueError("Impossibile leggere il file con gli encoding supportati.")
    lines = [l for l in raw.splitlines() if l.strip()]
    if lines and re.match(r"^(report|export|generated|file|date)\b", lines[0], re.IGNORECASE):
        lines = lines[1:]
    if not lines:
        raise ValueError("File CSV vuoto o non leggibile.")
    sample = "\n".join(lines[:6])
    counts = {s: sample.count(s) for s in [";", ",", "\t", "|"]}
    sep = max(counts, key=counts.get)
    if counts[sep] == 0:
        sep = ","
    import io as _io
    reader = csv.DictReader(_io.StringIO("\n".join(lines)), delimiter=sep)
    rows = []
    for row in reader:
        rows.append({k.strip().strip(chr(34)): v.strip().strip(chr(34))
                     for k, v in row.items() if k is not None})
    if not rows:
        raise ValueError("Nessuna riga dati trovata nel CSV.")
    headers = [h.strip().strip('"') for h in (reader.fieldnames or []) if h]
    col_meta = {}
    numeric_cols, datetime_cols, binary_cols, text_cols = [], [], [], []
    for h in headers:
        sample_vals = [rows[i].get(h, "") for i in range(min(50, len(rows)))]
        unit, label, col_type = _uc_col_meta(h, sample_vals)
        col_meta[h] = {"unit": unit, "label": label, "col_type": col_type}
        if col_type == "numeric":
            numeric_cols.append(h)
        elif col_type == "datetime":
            datetime_cols.append(h)
        elif col_type == "binary":
            binary_cols.append(h)
        else:
            text_cols.append(h)
    return rows, headers, col_meta, numeric_cols, datetime_cols, binary_cols, sep, detected_enc


# ── PARSER CSV LONG FORMAT (Cannon / Persico / Krauss Maffei) ─────────────
# Formato: una riga per (Timestamp × Parametro), colonne Parametro+Valore
# Viene pivotato in wide format: una riga per Timestamp, colonne = Parametri

_LONG_TS_FMT = "%d_%m_%Y_%H_%M_%S"

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

def _parse_long_cycle_csv(filepath):
    """Parsea il CSV long-format e lo pivota in wide.
    Ritorna stessa firma di parse_universal_csv."""
    raw = None
    detected_enc = "utf-8"
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            with open(filepath, encoding=enc) as f:
                raw = f.read()
            detected_enc = enc
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        raise ValueError("Impossibile leggere il file.")

    lines = [l for l in raw.splitlines() if l.strip()]
    start = 1 if lines and lines[0].upper().startswith("REPORT") else 0
    hdr_line = lines[start]
    
    # rileva separatore dall'header (virgola o punto-e-virgola)
    _data_line = lines[start + 1] if start + 1 < len(lines) else hdr_line
    _sep = ";" if _data_line.count(";") > _data_line.count(",") else ","
    
    # header SEMPRE split con virgola
    hdr_cols = [h.strip() for h in hdr_line.split(",")]

    # indici colonne chiave
    try:
        i_param = hdr_cols.index("Parametro")
        i_ts    = hdr_cols.index("Timestamp")
        i_val   = hdr_cols.index("Valore")
    except ValueError as e:
        raise ValueError(f"Colonna mancante: {e}")

    # raggruppa per timestamp → {ts_str: {param: valore}}
    from collections import OrderedDict
    buckets = OrderedDict()
    for line in lines[start + 1:]:
        parts = line.split(_sep)
        if len(parts) <= max(i_param, i_ts, i_val):
            continue
        param = parts[i_param].strip()
        ts_str = parts[i_ts].strip()
        val_s  = parts[i_val].strip().replace(",", ".")
        if not param or not ts_str:
            continue
        if ts_str not in buckets:
            buckets[ts_str] = {}
        try:
            buckets[ts_str][param] = float(val_s)
        except ValueError:
            buckets[ts_str][param] = val_s

    if not buckets:
        raise ValueError("Nessun dato trovato nel CSV long-format.")

    # ordina per timestamp reale
    def _parse_ts(s):
        for fmt in [_LONG_TS_FMT,
                    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%fZ",
                    "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(s.rstrip("Z").strip(), fmt.rstrip("Z"))
            except Exception:
                pass
        return None

    sorted_ts = sorted(buckets.keys(), key=lambda s: (_parse_ts(s) or datetime.min))

    # raccoglie tutti i parametri nell'ordine di prima apparizione
    all_params = list(dict.fromkeys(
        p for ts in sorted_ts for p in buckets[ts]))

    # costruisce le righe wide
    rows = []
    for ts_str in sorted_ts:
        r = {"_ts_str": ts_str}
        ts_dt = _parse_ts(ts_str)
        if ts_dt:
            r["_ts"] = ts_dt
        for p in all_params:
            r[p] = buckets[ts_str].get(p, None)
        rows.append(r)

    # costruisce col_meta per ogni parametro numerico
    headers      = all_params
    col_meta     = {}
    numeric_cols = []
    for p in all_params:
        unit, label, col_type = _uc_col_meta(p, [
            str(rows[i].get(p, "")) for i in range(min(20, len(rows)))])
        col_meta[p] = {"unit": unit, "label": label, "col_type": "numeric"}
        numeric_cols.append(p)

    datetime_cols = []   # usiamo _ts direttamente
    binary_cols   = []

    return rows, headers, col_meta, numeric_cols, datetime_cols, binary_cols, _sep, detected_enc


def _uc_interpolate_timestamps(xs_raw):
    """Se più campioni hanno lo stesso timestamp (es. logger al minuto),
    li distribuisce uniformemente nell'intervallo fino al timestamp successivo."""
    from datetime import timedelta
    if not xs_raw or not any(isinstance(x, datetime) for x in xs_raw):
        return xs_raw
    # Raggruppa indici per timestamp identico consecutivo
    result = list(xs_raw)
    i = 0
    while i < len(xs_raw):
        if xs_raw[i] is None:
            i += 1
            continue
        # Trova la fine del gruppo con stesso timestamp
        j = i + 1
        while j < len(xs_raw) and xs_raw[j] == xs_raw[i]:
            j += 1
        group_size = j - i
        if group_size > 1:
            # Calcola l'intervallo verso il prossimo timestamp diverso
            next_ts = None
            for k in range(j, len(xs_raw)):
                if xs_raw[k] is not None and xs_raw[k] != xs_raw[i]:
                    next_ts = xs_raw[k]
                    break
            if next_ts is None:
                # Ultimo gruppo: usa l'intervallo del gruppo precedente
                if i > 0:
                    prev_ts = xs_raw[i - 1] if xs_raw[i - 1] != xs_raw[i] else xs_raw[i]
                    interval = xs_raw[i] - prev_ts if prev_ts != xs_raw[i] else timedelta(minutes=1)
                else:
                    interval = timedelta(minutes=1)
                next_ts = xs_raw[i] + interval
            total_span = (next_ts - xs_raw[i]).total_seconds()
            step = total_span / group_size
            for k in range(group_size):
                result[i + k] = xs_raw[i] + timedelta(seconds=k * step)
        i = j
    return result

def _uc_build_series(rows, x_col, y_cols, col_meta):
    if not rows:
        return [], {}, "index"
    x_type = "index"
    if x_col and x_col in col_meta:
        x_type = col_meta[x_col]["col_type"]
        if x_type not in ("datetime", "numeric"):
            x_type = "index"
    xs_raw = []
    for i, r in enumerate(rows):
        if x_col and x_type == "datetime":
            val = _uc_parse_dt(r.get(x_col, ""))
            xs_raw.append(val)
        elif x_col and x_type == "numeric":
            try:
                xs_raw.append(float(r.get(x_col, "").replace(",", ".")))
            except Exception:
                xs_raw.append(None)
        else:
            xs_raw.append(i)
    # Corregge automaticamente timestamp duplicati (es. logger al minuto)
    if x_type == "datetime":
        xs_raw = _uc_interpolate_timestamps(xs_raw)
    series = {}
    for col in y_cols:
        vals = []
        for r in rows:
            _v = r.get(col, "")
            raw_v = _v.replace(",", ".") if isinstance(_v, str) else _v
            try:
                vals.append(float(raw_v))
            except Exception:
                vals.append(None)
        series[col] = vals
    return xs_raw, series, x_type


# -- SIEMENS LINE CHART --
# -- PUMP STATE CANVAS --
# -- INTERACTIVE PLOT CANVAS (Universal CSV Plotter) -----------------------

_UC_SERIES_PALETTE = [
    "#e5672c", "#3f51b5", "#29b6f6", "#66bb6a",
    "#9c27b0", "#ff9800", "#e7b73b", "#607d8b",
    "#f44322", "#00bcd4", "#8bc34a", "#ff5722",
]

