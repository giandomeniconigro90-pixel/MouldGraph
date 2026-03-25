# -*- coding: utf-8 -*-
import tkinter as tk
import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from datetime import datetime
from colors import COLORS
from csv_parser import _uc_build_series

class TimelineCanvas(tk.Canvas):
    def __init__(self,master,**kw):
        super().__init__(master,bg=COLORS["surface2"],highlightthickness=0,**kw)
        self.data={}
    def set_data(self,data):self.data=data;self.after(50,self.redraw)
    def redraw(self):
        self.delete("all")
        if not self.data:return
        w=self.winfo_width();h=self.winfo_height()
        if w<10 or h<10:return
        pl,pr,pt,pb=40,10,10,30
        keys=list(self.data.keys());n=len(keys)
        if n==0:return
        max_t=max(v["total"] for v in self.data.values()) or 1
        baw=w-pl-pr;bw=max(2,baw/n-2);ch=h-pt-pb
        for i in range(5):
            y=pt+(ch*i//4)
            self.create_line(pl,y,w-pr,y,fill=COLORS["border"],dash=(2,4))
            self.create_text(pl-4,y,text=str(int(max_t*(4-i)/4)),fill=COLORS["text2"],font=("Segoe UI",8),anchor="e")
        for i,key in enumerate(keys):
            v=self.data[key];x=pl+i*(baw/n)+(baw/n-bw)/2;sy=h-pb
            for lvl,color in[("DEBUG","#1890ff"),("INFO","#52c41a"),("WARN","#faad14"),("ERROR","#ff4d4f")]:
                cnt=v.get(lvl,0)
                if cnt==0:continue
                bh=max(2,cnt/max_t*ch);y0=sy-bh
                self.create_rectangle(x,y0,x+bw,sy,fill=color,outline="");sy=y0
        step=max(1,n//8)
        for i in range(0,n,step):
            x=pl+i*(baw/n)+baw/(n*2)
            self.create_text(x,h-pb+10,text=keys[i],fill=COLORS["text2"],font=("Segoe UI",8),anchor="n")
        lx=pl
        for lvl,color in[("ERROR","#ff4d4f"),("WARN","#faad14"),("INFO","#52c41a"),("DEBUG","#1890ff")]:
            self.create_rectangle(lx,2,lx+10,12,fill=color,outline="")
            self.create_text(lx+13,7,text=lvl,fill=COLORS["text2"],font=("Segoe UI",8),anchor="w");lx+=60


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
class LineChart(tk.Canvas):
    def __init__(self,master,**kw):
        super().__init__(master,bg=COLORS["surface2"],highlightthickness=0,**kw)
        self.series={}   # {label:(color,[values])}
        self.times=[]
    def set_data(self,times,series):
        self.times=times;self.series=series;self.after(50,self.redraw)
    def redraw(self):
        self.delete("all")
        if not self.series or not self.times:return
        w=self.winfo_width();h=self.winfo_height()
        if w<20 or h<20:return
        pl,pr,pt,pb=50,20,15,35
        all_vals=[v for (_c,vals) in self.series.values() for v in vals if v is not None]
        if not all_vals:return
        mn_v=min(all_vals);mx_v=max(all_vals)
        rng=mx_v-mn_v or 1
        mn_v-=rng*0.05;mx_v+=rng*0.05;rng=mx_v-mn_v
        cw=w-pl-pr;ch=h-pt-pb;n=len(self.times)
        # grid
        for i in range(6):
            y=pt+ch*i//5
            val=mx_v-(rng*i/5)
            self.create_line(pl,y,w-pr,y,fill=COLORS["border"],dash=(2,4))
            self.create_text(pl-4,y,text=f"{val:.1f}",fill=COLORS["text2"],font=("Segoe UI",8),anchor="e")
        # x labels
        step=max(1,n//8)
        for i in range(0,n,step):
            x=pl+i*cw/(n-1) if n>1 else pl+cw//2
            lbl=self.times[i].strftime("%H:%M:%S") if hasattr(self.times[i],"strftime") else str(self.times[i])
            self.create_text(x,h-pb+10,text=lbl,fill=COLORS["text2"],font=("Segoe UI",8),anchor="n")
        # lines
        for label,(color,vals) in self.series.items():
            pts=[]
            for i,v in enumerate(vals):
                if v is None:continue
                x=pl+i*cw/(n-1) if n>1 else pl+cw//2
                y=pt+ch*(1-(v-mn_v)/rng)
                pts.append((x,y))
            for i in range(len(pts)-1):
                self.create_line(pts[i][0],pts[i][1],pts[i+1][0],pts[i+1][1],fill=color,width=2)
            if pts:
                self.create_oval(pts[-1][0]-3,pts[-1][1]-3,pts[-1][0]+3,pts[-1][1]+3,fill=color,outline="")
        # legend
        lx=pl;ly=5
        for label,(color,_) in self.series.items():
            self.create_rectangle(lx,ly,lx+12,ly+10,fill=color,outline="")
            self.create_text(lx+15,ly+5,text=label,fill=COLORS["text2"],font=("Segoe UI",8),anchor="w")
            lx+=len(label)*6+30

# -- PUMP STATE CANVAS --
class PumpCanvas(tk.Canvas):
    def __init__(self,master,**kw):
        super().__init__(master,bg=COLORS["surface2"],highlightthickness=0,**kw)
        self.data=[]
    def set_data(self,times,vals):self.data=list(zip(times,vals));self.after(50,self.redraw)
    def redraw(self):
        self.delete("all")
        if not self.data:return
        w=self.winfo_width();h=self.winfo_height()
        if w<20 or h<20:return
        pl,pr,pt,pb=50,20,10,30
        n=len(self.data);cw=w-pl-pr;ch=h-pt-pb
        bw=max(2,cw/n-1)
        for i,(ts,val) in enumerate(self.data):
            x=pl+i*cw/n
            color="#52c41a" if val==1 else "#ff4d4f"
            self.create_rectangle(x,pt,x+bw,pt+ch,fill=color,outline="")
        self.create_text(pl-4,pt+ch//4,text="ON",fill="#52c41a",font=("Segoe UI",9,"bold"),anchor="e")
        self.create_text(pl-4,pt+ch*3//4,text="OFF",fill="#ff4d4f",font=("Segoe UI",9,"bold"),anchor="e")
        step=max(1,n//8)
        for i in range(0,n,step):
            ts=self.data[i][0]
            x=pl+i*cw/n+bw/2
            lbl=ts.strftime("%H:%M:%S") if hasattr(ts,"strftime") else str(ts)
            self.create_text(x,h-pb+10,text=lbl,fill=COLORS["text2"],font=("Segoe UI",8),anchor="n")




# -- INTERACTIVE PLOT CANVAS (Universal CSV Plotter) -----------------------

_UC_SERIES_PALETTE = [
    "#e5672c", "#3f51b5", "#29b6f6", "#66bb6a",
    "#9c27b0", "#ff9800", "#e7b73b", "#607d8b",
    "#f44322", "#00bcd4", "#8bc34a", "#ff5722",
]

