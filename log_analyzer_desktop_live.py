# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import re, json, csv, os, math
from datetime import datetime
from collections import defaultdict
import threading
import tkinter.simpledialog as simpledialog
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates  # D1: cached da Python
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import random
import queue as _queue
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

MAX_LIVE_POINTS = 500   # finestra scorrevole grafico live (performance)

COLORS = {
    "bg":"#0f1117","surface":"#1a1d27","surface2":"#22263a","border":"#2e3350",
    "accent":"#6c63ff","accent2":"#00d4ff","error":"#ff4d4f","warn":"#faad14",
    "info":"#52c41a","debug":"#1890ff","text":"#e8eaf6","text2":"#8892b0",
}
LEVEL_COLORS = {"ERROR":COLORS["error"],"WARN":COLORS["warn"],"INFO":COLORS["info"],"DEBUG":COLORS["debug"]}
LEVEL_BG     = {"ERROR":"#4a1a1a","WARN":"#4a3a00","INFO":"#1a3a0a","DEBUG":"#0a2a4a"}
LEVEL_HOVER  = {"ERROR":"#7a2020","WARN":"#7a5a00","INFO":"#2a5a10","DEBUG":"#104070"}

def _isolate_scroll(scrollable_frame):
    """Impedisce al mousewheel di propagarsi al parent quando il cursore
    è dentro il CTkScrollableFrame — fix per Windows/CustomTkinter."""
    sf = scrollable_frame
    # il canvas interno di CTkScrollableFrame è l'unico widget che riceve scroll
    canvas = sf._parent_canvas if hasattr(sf, "_parent_canvas") else None

    def _block(event):
        # scrolla solo il frame interno, blocca la propagazione
        if canvas:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _bind_wheel(event=None):
        sf.bind_all("<MouseWheel>", _block)

    def _unbind_wheel(event=None):
        sf.unbind_all("<MouseWheel>")

    sf.bind("<Enter>", _bind_wheel)
    sf.bind("<Leave>", _unbind_wheel)


# -- PARSER LOG --
PAT1 = re.compile(r'^\[?(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\]?\s+(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\s+\[([^\]]+)\]\s+(.*)',re.IGNORECASE)
PAT_S= re.compile(r'^(\d{2}[./]\d{2}[./]\d{4}\s+\d{2}:\d{2}:\d{2})\s*[|;,]\s*(ERROR|ALARM|ALARM_URGENT|WARNING|WARN|INFO|DEBUG|OK)\s*[|;,]\s*([^|;,]*)[|;,]?\s*(.*)',re.IGNORECASE)
PAT2 = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\s+(.*)',re.IGNORECASE)
PAT3 = re.compile(r'^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\s+(?:\[([^\]]+)\]\s+)?(.*)',re.IGNORECASE)
PAT4 = re.compile(r'^(\S.{7,}?)\s+\b(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\b\s+(.+)',re.IGNORECASE)

def norm_level(l):
    l=l.upper()
    if l=="WARNING":return"WARN"
    if l in("FATAL","CRITICAL","ALARM","ALARM_URGENT"):return"ERROR"
    if l in("TRACE","OK"):return"INFO"
    return l

def parse_ts(s):
    if not s:return None
    for fmt in["%Y-%m-%d %H:%M:%S","%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S.%f",
               "%Y-%m-%dT%H:%M:%S.%f","%d/%m/%Y %H:%M:%S","%d.%m.%Y %H:%M:%S","%b %d %H:%M:%S"]:
        try:return datetime.strptime(s.rstrip("Z").strip(),fmt)
        except Exception:pass
    return None

def parse_line(raw,idx):
    m=PAT1.match(raw)
    if m:return dict(n=idx+1,raw=raw,timestamp=m.group(1),ts=parse_ts(m.group(1)),level=norm_level(m.group(2)),component=m.group(3) or"-",message=m.group(4))
    m=PAT_S.match(raw)
    if m:return dict(n=idx+1,raw=raw,timestamp=m.group(1),ts=parse_ts(m.group(1)),level=norm_level(m.group(2)),component=m.group(3).strip() or"-",message=m.group(4).strip())
    m=PAT2.match(raw)
    if m:return dict(n=idx+1,raw=raw,timestamp=m.group(1),ts=parse_ts(m.group(1)),level=norm_level(m.group(2)),component="-",message=m.group(3))
    m=PAT3.match(raw)
    if m:return dict(n=idx+1,raw=raw,timestamp=m.group(1),ts=parse_ts(m.group(1)),level=norm_level(m.group(2)),component=m.group(3) or"-",message=m.group(4))
    m=PAT4.match(raw)
    if m:return dict(n=idx+1,raw=raw,timestamp=m.group(1) or"",ts=parse_ts(m.group(1)),level=norm_level(m.group(2)),component="-",message=m.group(3))
    return dict(n=idx+1,raw=raw,timestamp="",ts=None,level="INFO",component="-",message=raw)

def parse_log(text):
    return[parse_line(l,i) for i,l in enumerate([x for x in text.splitlines() if x.strip()])]

_RE_IP    = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
_RE_UID   = re.compile(r'user_id=\d+')
_RE_OID   = re.compile(r'order_id=\d+')
_RE_EMAIL = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_RE_NUM   = re.compile(r'\b\d{4,}\b')
_RE_WS    = re.compile(r'\s+')

def norm_sig(msg):
    msg=_RE_IP.sub('<IP>',msg)
    msg=_RE_UID.sub('user_id=<ID>',msg)
    msg=_RE_OID.sub('order_id=<ID>',msg)
    msg=_RE_EMAIL.sub('<EMAIL>',msg)
    msg=_RE_NUM.sub('<NUM>',msg)
    return _RE_WS.sub(' ',msg).strip()

def ai_analysis(parsed):
    if not parsed:return[]
    total=len(parsed);errors=[l for l in parsed if l["level"]=="ERROR"];warns=[l for l in parsed if l["level"]=="WARN"]
    err_r=len(errors)/total*100;warn_r=len(warns)/total*100;insights=[]
    if err_r>20:insights.append(("CRITICO","Alto tasso errori",f"{err_r:.0f}% degli eventi sono ERROR ({len(errors)}/{total}). Verificare subito.","#ff4d4f"))
    elif err_r>5:insights.append(("ATTENZIONE","Tasso errori elevato",f"{err_r:.0f}% degli eventi sono ERROR. Monitorare.","#faad14"))
    else:insights.append(("OK","Tasso errori nella norma",f"Solo {err_r:.1f}% di ERROR. Sistema stabile.","#52c41a"))
    comp_err=defaultdict(int)
    for l in errors:comp_err[l["component"]]+=1
    if comp_err:
        top=max(comp_err,key=comp_err.get)
        insights.append(("ANALISI",f"Componente critico: [{top}]",f"{comp_err[top]} errori. Concentrare il debug su questo modulo.","#6c63ff"))
    sig_map=defaultdict(int)
    for l in parsed:sig_map[norm_sig(l["message"])]+=1
    top_pat=sorted(sig_map.items(),key=lambda x:-x[1])
    if top_pat and top_pat[0][1]>3:
        sig,cnt=top_pat[0]
        insights.append(("PATTERN",f"Evento ripetuto {cnt}x",f'"{sig[:80]}..." - Possibile loop o problema ricorrente.','#00d4ff'))
    with_ts=[l for l in parsed if l["ts"]]
    if len(with_ts)>5:
        hours=defaultdict(lambda:{"ERROR":0,"total":0})
        for l in with_ts:
            h=l["ts"].strftime("%H:00");hours[h]["total"]+=1
            if l["level"]=="ERROR":hours[h]["ERROR"]+=1
        if hours:
            peak=max(hours,key=lambda h:hours[h]["ERROR"])
            if hours[peak]["ERROR"]>0:insights.append(("TEMPORALE",f"Picco errori alle {peak}",f'{hours[peak]["ERROR"]} errori concentrati in quest\'ora.','#faad14'))
    if warn_r>30:insights.append(("WARN",f"Molti warning ({warn_r:.0f}%)",f"Elevato numero di avvisi. Analizzare i trend.","#faad14"))
    return insights

def build_timeline(parsed):
    b=defaultdict(lambda:{"ERROR":0,"WARN":0,"INFO":0,"DEBUG":0,"total":0})
    for l in parsed:
        k=l["ts"].strftime("%H:%M") if l["ts"] else "??:??"
        b[k][l["level"]]=b[k].get(l["level"],0)+1;b[k]["total"]+=1
    return dict(sorted(b.items()))

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
        # dedup per (tipo, colonna) — evita flood su sensori rumorosi
        col_key = a[1].split('[')[0].strip()
        key=(a[0], col_key)
        if key not in seen:seen.add(key);out.append(a)
    return out,stats

# -- TIMELINE CANVAS --
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
    hdr_cols = [h.strip() for h in hdr_line.split(_sep)]

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

class InteractivePlotCanvas:
    """Wrapper matplotlib con hover crosshair, zoom rotella, pan drag."""

    def __init__(self, master, height=320):
        self.master = master
        self.height = height
        self._rows = []
        self._xs_raw = []
        self._xs_num_cache = None  # B1: cache _to_num(_xs_raw), invalidata su cambio dati
        self._series = {}
        self._x_type = "index"
        self._col_meta = {}
        self._y2_cols = set()
        self._colors = {}
        self._x_label = ""
        self._xlim_orig = None
        self._ylim_orig = None
        self._y2lim_orig = None
        self._pan_start = None
        self._pan_xlim = None
        self._hover_cid = None
        self._cross_v = None
        self._tooltip = None
        self._dot_artists = []
        self._hidden = set()
        self._lines = {}
        self._overlay_lines   = {}   # col → Line2D per serie ②
        self._overlay_all_vis = True  # stato toggle globale ②
        self._zoom_stack = []          # stack (xmin, xmax) per undo zoom
        self._cur_a = None             # x-value cursore A
        self._cur_b = None             # x-value cursore B
        self._ab_artists = []          # tutti gli artist A/B da rimuovere
        self.show_markers = True       # mostra/nasconde pallini sui punti
        self._ranges      = []         # [{col, lo, hi}] bande colorate sul grafico
        self._drawing     = False      # True durante canvas.draw() — blocca blit stantio
        self._frame = ctk.CTkFrame(master, fg_color=COLORS["surface"], corner_radius=8)
        self._frame.pack(fill="both", expand=True, padx=0, pady=0)
        # ── info bar (hover) ────────────────────────────────────────────────
        self._info_var = tk.StringVar(value="")
        self._info_lbl = ctk.CTkLabel(
            self._frame, textvariable=self._info_var,
            font=("Courier New", 10), text_color=COLORS["accent2"],
            fg_color=COLORS["surface2"], corner_radius=4, anchor="w")
        self._info_lbl.pack(fill="x", padx=6, pady=(4, 0))
        self._info_lbl.configure(fg_color="transparent")
        # ── canvas matplotlib ───────────────────────────────────────────
        self._plot_area = ctk.CTkFrame(self._frame, fg_color="transparent")
        self._plot_area.pack(fill="both", expand=True)
        # ── barra toggle serie (sotto il grafico) ───────────────────────
        self._legend_panel = ctk.CTkScrollableFrame(
            self._frame, fg_color=COLORS["surface2"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"],
            orientation="horizontal", height=40, corner_radius=4)
        self._legend_panel.pack(fill="x", padx=4, pady=(2, 4))
        self._legend_rows = []
        # ── figura matplotlib ───────────────────────────────────────────────
        self._fig, self._ax1 = plt.subplots(
            figsize=(10, height / 96), facecolor=COLORS["surface"])
        self._ax2 = None
        self._ax1.set_facecolor(COLORS["surface2"])
        for sp in self._ax1.spines.values():
            sp.set_edgecolor(COLORS["border"])
        self._ax1.tick_params(colors=COLORS["text2"])
        self._fig.patch.set_facecolor(COLORS["surface"])
        self._canvas = FigureCanvasTkAgg(self._fig, master=self._plot_area)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        self._canvas.draw()   # disegna subito con sfondo scuro
        self._resize_job = None   # debounce resize
        self._canvas.mpl_connect("resize_event", self._on_resize)
        self._canvas.mpl_connect("scroll_event",        self._on_scroll)
        self._canvas.mpl_connect("button_press_event",  self._on_press)
        self._canvas.mpl_connect("button_release_event",self._on_release)
        self._canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._canvas.get_tk_widget().bind("<Leave>", lambda e: self._clear_hover())

    def _on_resize(self, event):
        """Debounce: ridisegna solo 300ms dopo l'ultimo evento resize."""
        if self._resize_job is not None:
            try: self._frame.after_cancel(self._resize_job)
            except Exception: pass
        self._resize_job = self._frame.after(300, self._on_resize_done)

    def _on_resize_done(self):
        self._resize_job = None
        if self._xs_raw and self._series:
            self._fig.tight_layout(pad=1.2)
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            self._cross_v = None
            self._tooltip = None

    def set_data(self, xs_raw, series, x_type, col_meta,
                 y2_cols=None, colors=None, x_label=""):
        self._xs_raw        = xs_raw
        self._xs_num_cache  = None  # B1: invalida cache
        self._series   = series
        self._x_type   = x_type
        self._col_meta = col_meta
        self._y2_cols  = set(y2_cols or [])
        self._x_label  = x_label
        palette = list(_UC_SERIES_PALETTE)
        self._colors = {}
        for i, col in enumerate(series):
            self._colors[col] = (colors or {}).get(col, palette[i % len(palette)])
        self._xlim_orig = None
        self._ylim_orig = None
        self._y2lim_orig = None
        self._hidden = set()
        self._zoom_stack = []
        self._cur_a = None
        self._cur_b = None
        self._ab_artists = []
        self._redraw()
        self._rebuild_legend_sidebar()

    def _overlay_second_csv(self, rows2, x_col, cols, colors2, col_meta):
        """Sovrappone le serie del secondo CSV sull'asse corrente con linee tratteggiate."""
        if not self._ax1 or not rows2:
            return
        xs2, series2, x_type2 = _uc_build_series(rows2, x_col, cols, col_meta)
        xs_num2 = self._to_num(xs2) if x_type2 == "datetime" else \
                  [float(x) if x is not None else None for x in xs2]
        for col in cols:
            ys = series2.get(col, [])
            xf, yf = self._clean(xs_num2, ys)
            if not xf:
                continue
            color = colors2.get(col, "#aaaaaa")
            lbl = f"{col} ②"
            line, = self._ax1.plot(xf, yf, color=color, linewidth=1.2,
                                   linestyle="--", label=lbl, zorder=2, alpha=0.85)
            self._overlay_lines[col] = line  # salva riferimento per toggle
        self._xs_num_cache = None  # B1x
        self._fig.tight_layout(pad=1.2)
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        self._rebuild_legend_sidebar()  # mostra bottoni ② nel pannello

    def update_live(self, xs_raw, series, x_type, col_meta, colors=None,
                    background=False):
        """Redraw incrementale per Live Data."""
        needs_full = (getattr(self, "_needs_full_redraw", False)
                      or set(series.keys()) != set(self._lines.keys())
                      or not self._lines)
        if needs_full:
            self._needs_full_redraw = False
            self.set_data(xs_raw, series, x_type, col_meta, colors=colors)
            return

        # Fix B: salta il draw se i dati non sono cambiati
        # confronta lunghezza e ultimo valore di ogni serie come fingerprint veloce
        new_fp = (len(xs_raw),
                  tuple((k, len(v), v[-1] if v else None)
                        for k, v in series.items()))
        if new_fp == getattr(self, "_live_data_fp", None):
            return
        self._live_data_fp = new_fp

        self._xs_raw        = xs_raw
        self._xs_num_cache  = None  # B1: invalida cache
        self._series   = series
        self._x_type   = x_type
        self._col_meta = col_meta

        # aggiorna mappa colori se fornita
        if colors:
            for col, c in colors.items():
                if col in self._colors and self._colors[col] != c:
                    self._colors[col] = c
                    if col in self._lines:
                        self._lines[col].set_color(c)

        # ── pulisce artisti animati
        if self._cross_v is not None:
            try:
                self._cross_v.set_xdata([])
                self._cross_v.set_ydata([])
            except Exception:
                pass
            self._cross_v = None
        for dot in self._dot_artists:
            try:
                dot.set_xdata([])
                dot.set_ydata([])
            except Exception:
                pass
        self._dot_artists = []
        if self._tooltip is not None:
            try:
                self._tooltip.set_visible(False)
            except Exception:
                pass
            self._tooltip = None

        xs_num = self._to_num(xs_raw)
        ax1 = self._ax1

        for col, line in self._lines.items():
            ys = series.get(col, [])
            xf, yf = self._clean(xs_num, ys)
            if xf:
                line.set_xdata(xf)
                line.set_ydata(yf)

        # se ci sono serie nascoste ricalcola i limiti solo sulle visibili
        if self._hidden:
            self._rescale_visible()
        else:
            ax1.relim()
            ax1.autoscale_view()
            if self._ax2:
                self._ax2.relim()
                self._ax2.autoscale_view()

        if x_type == "datetime":
            self._fmt_xaxis_datetime(ax1, xs_num)

        self._drawing = True
        try:
            if background:
                self._canvas.draw_idle()
            else:
                self._canvas.draw()
                self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        finally:
            self._drawing = False

    def set_ranges(self, ranges):
        """Imposta le bande di range [{col, lo, hi}] e ridisegna."""
        self._ranges = ranges or []
        self._redraw()
        self._rebuild_legend_sidebar()

    def clear(self):
        self._xs_raw = []
        self._xs_num_cache = None  # B1: invalida cache
        self._series = {}
        self._redraw()

    def get_frame(self):
        return self._frame

    def _redraw(self):
        self._overlay_lines = {}  # reset: _redraw cancella tutto il canvas
        self._fig.clf()
        self._ax1 = self._fig.add_subplot(111)
        self._ax2 = None
        self._cross_v = None
        self._tooltip = None
        self._dot_artists = []
        ax1 = self._ax1
        self._fig.patch.set_facecolor(COLORS["surface"])
        ax1.set_facecolor(COLORS["surface2"])
        for sp in ax1.spines.values():
            sp.set_edgecolor(COLORS["border"])
        ax1.tick_params(colors=COLORS["text2"], labelsize=8)
        ax1.xaxis.label.set_color(COLORS["text2"])
        ax1.yaxis.label.set_color(COLORS["text2"])
        ax1.grid(True, color=COLORS["border"], linewidth=0.4, linestyle="--", alpha=0.6)
        if not self._xs_raw or not self._series:
            ax1.text(0.5, 0.5, "Nessun dato da visualizzare",
                     ha="center", va="center", color=COLORS["text2"],
                     fontsize=11, transform=ax1.transAxes)
            self._drawing = True
            try:
                self._canvas.draw()
                self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)  # aggiorna sempre
            finally:
                self._drawing = False
            return
        xs_num = self._to_num(self._xs_raw)
        y1_cols = [c for c in self._series if c not in self._y2_cols]
        y2_cols = [c for c in self._series if c in self._y2_cols]
        if y2_cols:
            self._ax2 = ax1.twinx()
            ax2 = self._ax2
            ax2.set_facecolor("none")
            for sp in ax2.spines.values():
                sp.set_edgecolor(COLORS["border"])
            ax2.tick_params(colors=COLORS["text2"], labelsize=8)
        self._lines = {}
        # marker adattivo: più punti → marker più piccoli
        def _marker_size(n):
            if n <= 20:   return 6
            if n <= 50:   return 4
            if n <= 200:  return 3
            return 2
        _mk = "o" if self.show_markers else "none"

        for col in y1_cols:
            ys = self._series[col]
            xf, yf = self._clean(xs_num, ys)
            if xf:
                lbl  = self._col_meta.get(col, {}).get("label", col)
                unit = self._col_meta.get(col, {}).get("unit", "")
                full_lbl = f"{lbl} [{unit}]" if unit else lbl
                ms = _marker_size(len(xf))
                line, = ax1.plot(xf, yf, color=self._colors[col],
                                 linewidth=1.4, label=full_lbl,
                                 marker=_mk, markersize=ms,
                                 markerfacecolor=self._colors[col],
                                 markeredgewidth=0, zorder=3)
                self._lines[col] = line
        if self._ax2:
            for col in y2_cols:
                ys = self._series[col]
                xf, yf = self._clean(xs_num, ys)
                if xf:
                    lbl  = self._col_meta.get(col, {}).get("label", col)
                    unit = self._col_meta.get(col, {}).get("unit", "")
                    full_lbl = f"{lbl} [{unit}]" if unit else lbl
                    ms = _marker_size(len(xf))
                    line, = self._ax2.plot(xf, yf, color=self._colors[col],
                                           linewidth=1.4, label=full_lbl,
                                           linestyle="--",
                                           marker=_mk, markersize=ms,
                                           markerfacecolor=self._colors[col],
                                           markeredgewidth=0, zorder=3)
                    self._lines[col] = line
        if self._x_type == "datetime":
            self._fmt_xaxis_datetime(ax1, xs_num)
        else:
            ax1.set_xlabel(self._x_label or "Indice", color=COLORS["text2"], fontsize=8)
        # applica visibilità toggle
        for _c, _l in self._lines.items():
            _l.set_visible(_c not in self._hidden)

        # ── bande colorate per range personalizzati ───────────────────────
        for rule in self._ranges:
            col = rule.get("col")
            lo  = rule.get("lo")
            hi  = rule.get("hi")
            if col in self._hidden:
                continue
            color = self._colors.get(col, COLORS["accent"])
            ax = self._ax2 if (self._ax2 and col in self._y2_cols) else ax1
            # banda tra lo e hi
            if lo is not None and hi is not None:
                ax.axhspan(lo, hi, color=color, alpha=0.12, zorder=1)
            elif lo is not None:
                ax.axhline(lo, color=color, linewidth=1.0,
                           linestyle=":", alpha=0.7, zorder=2)
            elif hi is not None:
                ax.axhline(hi, color=color, linewidth=1.0,
                           linestyle=":", alpha=0.7, zorder=2)
        # legenda esterna: niente legend() dentro il grafico
        if self._xlim_orig:
            ax1.set_xlim(self._xlim_orig)
            if self._ax2:
                self._ax2.set_xlim(self._xlim_orig)
        else:
            self._xlim_orig = ax1.get_xlim()
        self._fig.tight_layout(pad=1.2)
        self._drawing = True
        try:
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        finally:
            self._drawing = False
        self._cross_v = None
        self._tooltip = None

    def _to_num(self, xs):
        if not xs:
            return []
        if self._x_type == "datetime":
            result = []
            for x in xs:
                if isinstance(x, datetime):
                    result.append(mdates.date2num(x))
                else:
                    result.append(None)
            return result
        return [float(x) if x is not None else None for x in xs]

    def _clean(self, xs, ys):
        pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
        if not pairs:
            return [], []
        return [p[0] for p in pairs], [p[1] for p in pairs]

    def _fmt_xaxis_datetime(self, ax, xs_num):
        valid = [x for x in xs_num if x is not None]
        if not valid:
            return
        span_days = (max(valid) - min(valid))
        if span_days < 1 / 24:
            fmt = mdates.DateFormatter("%H:%M:%S")
        elif span_days < 1:
            fmt = mdates.DateFormatter("%H:%M")
        elif span_days < 7:
            fmt = mdates.DateFormatter("%d/%m %H:%M")
        else:
            fmt = mdates.DateFormatter("%d/%m/%Y")
        ax.xaxis.set_major_formatter(fmt)
        plt.setp(ax.get_xticklabels(), rotation=30, fontsize=7, color=COLORS["text2"])

    def _clear_hover(self):
        self._info_var.set("")
        try: self._info_lbl.configure(fg_color="transparent")
        except Exception: pass
        if self._cross_v is not None:
            try: self._cross_v.remove()
            except Exception: pass
            self._cross_v = None
        for a in self._dot_artists:
            try: a.remove()
            except Exception: pass
        self._dot_artists = []
        if self._tooltip is not None:
            try: self._tooltip.remove()
            except Exception: pass
            self._tooltip = None
        try:
            self._canvas.restore_region(self._bg_cache)
            self._canvas.blit(self._fig.bbox)
        except Exception: pass

    def _on_motion(self, event):
        if getattr(self, "_drawing", False):
            return
        if event.inaxes not in (self._ax1, self._ax2):
            self._clear_hover()
            return
        if not self._xs_raw or not self._series:
            # nessun CSV1 ma ci sono linee ② — usa overlay come ancora X
            _ov2 = getattr(self, "_overlay_lines", {})
            if not _ov2:
                self._clear_hover()
                return
            _fl = next(iter(_ov2.values()))
            _lx0 = _fl.get_xdata()
            if not len(_lx0) or event.xdata is None:
                return
            _xm0  = event.xdata
            _idx0 = int(np.nanargmin(np.abs(np.array([float(x) for x in _lx0]) - _xm0)))
            _xs0  = float(_lx0[_idx0])
            _xstr = f"{_xs0:.4g}"
            _tip  = [f"X: {_xstr}"]; _prt = [f"X: {_xstr}"]
            for _c2, _ln2 in _ov2.items():
                if not _ln2.get_visible(): continue
                _ly2 = _ln2.get_ydata()
                if _idx0 < len(_ly2) and _ly2[_idx0] is not None:
                    _tip.append(f"{_c2}③: {float(_ly2[_idx0]):.4g}")
                    _prt.append(f"{_c2}③: {float(_ly2[_idx0]):.4g}")
            self._info_var.set("   ".join(_prt))
            try: self._canvas.restore_region(self._bg_cache)
            except Exception:
                self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
                self._canvas.restore_region(self._bg_cache)
            _ylim0 = self._ax1.get_ylim(); _xlim0 = self._ax1.get_xlim()
            if self._cross_v is None:
                self._cross_v, = self._ax1.plot([_xs0,_xs0], _ylim0,
                    color=COLORS["accent2"], linewidth=0.8, linestyle="--",
                    zorder=10, animated=True)
            else:
                self._cross_v.set_xdata([_xs0, _xs0])
                self._cross_v.set_ydata(_ylim0)
            self._ax1.draw_artist(self._cross_v)
            # dot sulle ② lines
            for _a in self._dot_artists:
                try: _a.remove()
                except Exception: pass
            self._dot_artists = []
            for _c2, _ln2 in _ov2.items():
                if not _ln2.get_visible(): continue
                _ly2 = _ln2.get_ydata()
                if _idx0 < len(_ly2) and _ly2[_idx0] is not None:
                    _d2, = self._ax1.plot(_xs0, float(_ly2[_idx0]), "D",
                        color=_ln2.get_color(), markersize=5, zorder=11,
                        animated=True, markeredgecolor="#fff", markeredgewidth=0.5)
                    self._dot_artists.append(_d2)
                    self._ax1.draw_artist(_d2)
            # tooltip
            _xf0 = ((_xs0-_xlim0[0])/(_xlim0[1]-_xlim0[0])) if _xlim0[1]!=_xlim0[0] else 0.5
            _ha0 = "left" if _xf0 < 0.75 else "right"
            _xoff = _xs0 + (_xlim0[1]-_xlim0[0])*0.015 if _ha0=="left" else _xs0 - (_xlim0[1]-_xlim0[0])*0.015
            _ytip = _ylim0[0] + (_ylim0[1]-_ylim0[0])*0.97
            if self._tooltip is None:
                self._tooltip = self._ax1.text(_xoff, _ytip, "\n".join(_tip),
                    fontsize=7.5, color=COLORS["text"],
                    bbox=dict(boxstyle="round,pad=0.4", fc=COLORS["surface"],
                              ec=COLORS["accent2"], lw=1.0, alpha=0.92),
                    ha=_ha0, va="top", zorder=12, animated=True)
            else:
                self._tooltip.set_position((_xoff, _ytip))
                self._tooltip.set_text("\n".join(_tip))
                self._tooltip.set_ha(_ha0)
                self._tooltip.set_visible(True)
            self._ax1.draw_artist(self._tooltip)
            self._canvas.blit(self._fig.bbox)
            return
        if self._pan_start is not None:
            self._do_pan(event)
            return
        ax1 = self._ax1
        # B1: usa cache — ricalcola solo se invalidata da cambio dati
        if self._xs_num_cache is None:
            self._xs_num_cache = self._to_num(self._xs_raw)
        xs_num = self._xs_num_cache
        xm = event.xdata
        if xm is None:
            return
        # B2: ricerca numpy vettorizzata — 10-50x più veloce del min() Python
        valid_mask = [x is not None for x in xs_num]
        if not any(valid_mask):
            return
        xs_arr = np.array([x if x is not None else np.nan for x in xs_num])
        idx = int(np.nanargmin(np.abs(xs_arr - xm)))
        x_snap = xs_num[idx]
        if x_snap is None:
            return
        if self._x_type == "datetime" and isinstance(self._xs_raw[idx], datetime):
            x_str = self._xs_raw[idx].strftime("%d/%m/%Y %H:%M:%S")
        else:
            x_str = f"{self._xs_raw[idx]:.4g}" if isinstance(self._xs_raw[idx], float) else f"{self._xs_raw[idx]}"

        # ── info bar in cima ─────────────────────────────────────────────
        parts = [f"X: {x_str}"]
        for col, ys in self._series.items():
            if col in self._hidden:
                continue
            if idx < len(ys) and ys[idx] is not None:
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                parts.append(f"{lbl}: {ys[idx]:.4g}{(' ' + unit) if unit else ''}")
        # ── valori ② nell'info bar ───────────────────────────────
        for _c2, _ln2 in getattr(self, "_overlay_lines", {}).items():
            if not _ln2.get_visible(): continue
            _lx2 = _ln2.get_xdata(); _ly2 = _ln2.get_ydata()
            if not len(_lx2): continue
            _li2 = int(np.nanargmin(np.abs(np.array([float(x) for x in _lx2]) - x_snap)))
            if _li2 < len(_ly2) and _ly2[_li2] is not None:
                parts.append(f"{_c2}③: {float(_ly2[_li2]):.4g}")
        try: self._info_lbl.configure(fg_color=COLORS["surface2"])
        except Exception: pass
        self._info_var.set("   ".join(parts))

        try:
            self._canvas.restore_region(self._bg_cache)
        except Exception:
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            self._canvas.restore_region(self._bg_cache)

        ylim = ax1.get_ylim()
        xlim = ax1.get_xlim()

        # ── crosshair verticale ──────────────────────────────────────────
        if self._cross_v is None:
            self._cross_v, = ax1.plot(
                [x_snap, x_snap], ylim,
                color=COLORS["accent2"], linewidth=0.8,
                linestyle="--", zorder=10, animated=True)
        else:
            self._cross_v.set_xdata([x_snap, x_snap])
            self._cross_v.set_ydata(ylim)
        ax1.draw_artist(self._cross_v)

        # ── dot sui punti di snap — usa ys[idx] (stesso punto del tooltip) ──────
        for artist in self._dot_artists:
            try: artist.remove()
            except Exception: pass
        self._dot_artists = []
        for col in self._lines:
            if col in self._hidden: continue
            ys = self._series.get(col, [])
            if idx >= len(ys) or ys[idx] is None: continue
            ax = self._ax2 if (self._ax2 and col in self._y2_cols) else ax1
            dot, = ax.plot(x_snap, float(ys[idx]), "o",
                color=self._colors.get(col, "#fff"), markersize=6, zorder=11, animated=True)
            self._dot_artists.append(dot)
            ax.draw_artist(dot)
        # ── dot sulle linee ② ────────────────────────────────────────────
        for _c2, _ln2 in getattr(self, "_overlay_lines", {}).items():
            if not _ln2.get_visible(): continue
            _lx2 = _ln2.get_xdata(); _ly2 = _ln2.get_ydata()
            if not len(_lx2): continue
            _li2 = int(np.nanargmin(np.abs(np.array([float(x) for x in _lx2]) - x_snap)))
            if _li2 < len(_ly2) and _ly2[_li2] is not None:
                _d2, = ax1.plot(float(_lx2[_li2]), float(_ly2[_li2]), "D",
                    color=_ln2.get_color(), markersize=5, zorder=11, animated=True,
                    markeredgecolor="#fff", markeredgewidth=0.5)
                self._dot_artists.append(_d2)
                ax1.draw_artist(_d2)

        # ── tooltip flottante vicino al cursore ──────────────────────────
        tip_lines = [f"X: {x_str}"]
        for col, ys in self._series.items():
            if col in self._hidden:
                continue
            if idx < len(ys) and ys[idx] is not None:
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                tip_lines.append(f"{lbl}: {ys[idx]:.4g}{(' ' + unit) if unit else ''}")
        # ── valori ② nel tooltip ──────────────────────────────────
        for _c2, _ln2 in getattr(self, "_overlay_lines", {}).items():
            if not _ln2.get_visible(): continue
            _lx2 = _ln2.get_xdata(); _ly2 = _ln2.get_ydata()
            if not len(_lx2): continue
            _li2 = int(np.nanargmin(np.abs(np.array([float(x) for x in _lx2]) - x_snap)))
            if _li2 < len(_ly2) and _ly2[_li2] is not None:
                tip_lines.append(f"{_c2}③: {float(_ly2[_li2]):.4g}")
        tip_txt = "\n".join(tip_lines)

        # posiziona il tooltip a destra del cursore, o a sinistra se vicino al bordo
        x_frac = (x_snap - xlim[0]) / (xlim[1] - xlim[0]) if xlim[1] != xlim[0] else 0.5
        ha = "left" if x_frac < 0.75 else "right"
        x_off = x_snap + (xlim[1] - xlim[0]) * 0.015 if ha == "left" else x_snap - (xlim[1] - xlim[0]) * 0.015
        y_tip = ylim[0] + (ylim[1] - ylim[0]) * 0.97

        if self._tooltip is None:
            self._tooltip = ax1.text(
                x_off, y_tip, tip_txt,
                fontsize=7.5, color=COLORS["text"],
                bbox=dict(boxstyle="round,pad=0.4",
                          fc=COLORS["surface"], ec=COLORS["accent2"],
                          lw=1.0, alpha=0.92),
                ha=ha, va="top", zorder=12, animated=True)
        else:
            self._tooltip.set_position((x_off, y_tip))
            self._tooltip.set_text(tip_txt)
            self._tooltip.set_ha(ha)
            self._tooltip.set_visible(True)
        ax1.draw_artist(self._tooltip)

        self._canvas.blit(self._fig.bbox)

    def _on_scroll(self, event):
        if event.inaxes != self._ax1:
            return
        ax = self._ax1
        xmin, xmax = ax.get_xlim()
        if event.button == "up":
            # zoom-in: push stato corrente (limite a 50 livelli)
            if len(self._zoom_stack) < 50:
                self._zoom_stack.append((xmin, xmax))
                self._live_user_zoomed = True   # utente ha zoomato: blocca auto-scroll
            factor = 0.85
            cx = event.xdata if event.xdata else (xmin + xmax) / 2
            new_min = cx - (cx - xmin) * factor
            new_max = cx + (xmax - cx) * factor
        else:
            # zoom-out: pop stato precedente, se vuoto non fare nulla
            if not self._zoom_stack:
                return
            new_min, new_max = self._zoom_stack.pop()
        if not self._zoom_stack:
                self._live_user_zoomed = False  # tornato alla vista originale
        ax.set_xlim(new_min, new_max)
        if self._ax2:
            self._ax2.set_xlim(new_min, new_max)
        # A2: feedback visivo immediato + bg_cache aggiornata dopo 80ms
        if self._cross_v is not None:
            try: self._cross_v.remove()
            except Exception: pass
            self._cross_v = None
        for _a in self._dot_artists:
            try: _a.remove()
            except Exception: pass
        self._dot_artists = []
        if self._tooltip is not None:
            try: self._tooltip.remove()
            except Exception: pass
            self._tooltip = None
        self._canvas.draw_idle()  # A2: visuale immediata, non bloccante
        if getattr(self, "_scroll_timer", None):
            try: self._canvas.get_tk_widget().after_cancel(self._scroll_timer)
            except Exception: pass
        self._drawing = True  # A2: blocca blit stantio finché bg_cache non è aggiornata
        def _capture_bg():
            self._scroll_timer = None
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            self._drawing = False  # A2: riabilita hover
        self._scroll_timer = self._canvas.get_tk_widget().after(80, _capture_bg)

    def _on_press(self, event):
        if event.inaxes not in [self._ax1, self._ax2]:
            return
        if event.dblclick and event.xdata is not None:
            if event.button == 1:
                # 1° doppio-click sinistro → A; 2° → B; 3° → reset entrambi
                if self._cur_a is None:
                    self._cur_a = event.xdata
                elif self._cur_b is None:
                    self._cur_b = event.xdata
                else:
                    self._cur_a = event.xdata
                    self._cur_b = None
            elif event.button == 3:
                self._cur_b = event.xdata
            self._redraw_cursors_ab()
            return
        if event.inaxes == self._ax1 and event.button == 1:
            self._pan_start = event.xdata
            self._pan_xlim  = self._ax1.get_xlim()
            self._pan_ylim  = self._ax1.get_ylim()  # freeze Y durante il pan

    def _on_release(self, event):
        if getattr(self, "_pan_moved", False):  # A1: draw solo se pan reale
            if self._ax1:
                self._ax1.set_xlim(self._ax1.get_xlim())
                self._ax1.set_ylim(self._ax1.get_ylim())
            self._drawing = True
            try:
                self._canvas.draw()
                self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
            finally:
                self._drawing = False
        self._pan_start  = None
        self._pan_xlim   = None
        self._pan_ylim   = None
        self._pan_moved  = False  # A1: reset flag

    def _redraw_cursors_ab(self):
        """Rimuove i vecchi artist A/B e ridisegna. Traccia TUTTI gli artist creati."""
        if not self._ax1:
            return
        # Rimuove tutti gli artist precedenti (linee + testi + box)
        for a in self._ab_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._ab_artists = []
        ax1 = self._ax1
        # Disabilita autoscale PRIMA di tutto: matplotlib può chiamare
        # autoscale_view() internamente durante canvas.draw() anche con set_ylim.
        ax1.autoscale(enable=False)
        if self._ax2:
            self._ax2.autoscale(enable=False)
        # axvline usa blended_transform (x=dati, y=assi): NON aggiorna dataLim
        # e quindi non causa mai autoscale della Y quando vengono aggiunti i cursori.
        xax_tr = ax1.get_xaxis_transform()

        def _add(artist):
            self._ab_artists.append(artist)
            return artist

        if self._cur_a is not None:
            line_a = ax1.axvline(
                self._cur_a,
                color=COLORS["accent"], linewidth=1.2, linestyle="--", zorder=9)
            txt_a = ax1.text(
                self._cur_a, 0.98, " A",
                transform=xax_tr,
                color=COLORS["accent"], fontsize=8,
                fontweight="bold", va="top", zorder=10)
            _add(line_a); _add(txt_a)

        if self._cur_b is not None:
            line_b = ax1.axvline(
                self._cur_b,
                color=COLORS["accent2"], linewidth=1.2, linestyle="--", zorder=9)
            txt_b = ax1.text(
                self._cur_b, 0.98, " B",
                transform=xax_tr,
                color=COLORS["accent2"], fontsize=8,
                fontweight="bold", va="top", zorder=10)
            _add(line_b); _add(txt_b)

        if self._cur_a is not None and self._cur_b is not None:
            _md = mdates
            xa, xb = sorted([self._cur_a, self._cur_b])
            xs_num = self._to_num(self._xs_raw)

            if self._x_type == "datetime":
                da = _md.num2date(xa)
                db = _md.num2date(xb)
                sec = abs((db - da).total_seconds())
                h, r = divmod(int(sec), 3600)
                m, s = divmod(r, 60)
                dx_str = f"\u0394X = {h:02d}h {m:02d}m {s:02d}s"
            else:
                dx_str = f"\u0394X = {abs(xb - xa):.4g}"

            lines_txt = [dx_str]
            for col in self._series:
                if col in self._hidden:
                    continue
                ys = self._series.get(col, [])
                xf, yf = self._clean(xs_num, ys)
                if not xf:
                    continue
                xarr = np.array(xf)
                yarr = np.array(yf)
                def _interp(xq):
                    i = int(np.searchsorted(xarr, xq))
                    if i == 0: return float(yarr[0])
                    if i >= len(xarr): return float(yarr[-1])
                    x0, x1 = xarr[i-1], xarr[i]
                    y0, y1 = yarr[i-1], yarr[i]
                    return float(y0) if x1 == x0 else float(y0 + (y1-y0)*(xq-x0)/(x1-x0))
                va_v = _interp(xa)
                vb_v = _interp(xb)
                unit = self._col_meta.get(col, {}).get("unit", "")
                lbl  = self._col_meta.get(col, {}).get("label", col)
                dy = vb_v - va_v
                sign = "+" if dy >= 0 else ""
                lines_txt.append(f"{lbl}: {sign}{dy:.4g} {unit}".strip())

            box = ax1.text(
                (xa + xb) / 2, 0.05,
                "\n".join(lines_txt),
                transform=xax_tr,
                fontsize=7.5, color=COLORS["text"],
                bbox=dict(boxstyle="round,pad=0.4",
                          fc=COLORS["surface"], ec=COLORS["accent"],
                          lw=1.2, alpha=0.92),
                ha="center", va="bottom", zorder=11)
            _add(box)

        # Fix: rimuovi overlay e ridisegna in modo sincrono — bg_cache sempre aggiornata
        if self._cross_v is not None:
            try: self._cross_v.remove()
            except Exception: pass
            self._cross_v = None
        for _a in self._dot_artists:
            try: _a.remove()
            except Exception: pass
        self._dot_artists = []
        if self._tooltip is not None:
            try: self._tooltip.remove()
            except Exception: pass
            self._tooltip = None
        # Congela Y (e X) prima del draw: canvas.draw() chiama autoscale_view()
        # internamente se _autoscaleYon=True; set_ylim lo rende sticky (False).
        ax1.set_xlim(ax1.get_xlim())
        ax1.set_ylim(ax1.get_ylim())
        if self._ax2:
            self._ax2.set_ylim(self._ax2.get_ylim())
        self._drawing = True
        try:
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        finally:
            self._drawing = False
        # Se nessun cursore è attivo (reset) riabilita autoscale per la live tab
        if self._cur_a is None and self._cur_b is None:
            ax1.autoscale(enable=True)
            if self._ax2:
                self._ax2.autoscale(enable=True)

    def _do_pan(self, event):
        if event.xdata is None or self._pan_xlim is None:
            return
        dx = self._pan_start - event.xdata
        new_min = self._pan_xlim[0] + dx
        new_max = self._pan_xlim[1] + dx
        # Fix 1: clamp pan entro i limiti dei dati — non si va oltre inizio/fine
        xs_num = self._xs_num_cache if self._xs_num_cache is not None \
                 else self._to_num(self._xs_raw)
        valid = [x for x in xs_num if x is not None]
        if valid:
            data_min, data_max = min(valid), max(valid)
            span = new_max - new_min
            data_span = data_max - data_min
            # Se lo span copre l'intera ampiezza dei dati non è stato fatto zoom:
            # blocca il pan completamente.
            if data_span > 0 and span >= data_span * 0.999:
                return
            if new_min < data_min:
                new_min = data_min
                new_max = data_min + span
            if new_max > data_max:
                new_max = data_max
                new_min = data_max - span
        self._ax1.set_xlim(new_min, new_max)
        if getattr(self, "_pan_ylim", None) is not None:
            self._ax1.set_ylim(self._pan_ylim)  # impedisce autoscale Y durante il pan
        if self._ax2:
            self._ax2.set_xlim(new_min, new_max)
        # Fix: rimuovi overlay e ridisegna in modo sincrono — bg_cache sempre aggiornata
        if self._cross_v is not None:
            try: self._cross_v.remove()
            except Exception: pass
            self._cross_v = None
        for _a in self._dot_artists:
            try: _a.remove()
            except Exception: pass
        self._dot_artists = []
        if self._tooltip is not None:
            try: self._tooltip.remove()
            except Exception: pass
            self._tooltip = None
        self._pan_moved = True  # A1: segnala pan reale avvenuto
        self._canvas.draw_idle()  # A1: non bloccante durante il drag

    def reset_zoom(self):
        self._xlim_orig = None
        self._ylim_orig = None
        self._y2lim_orig = None
        self._zoom_stack = []
        self._cur_a = None
        self._cur_b = None
        self._ab_artists = []
        self._redraw()

    def clear_cursors(self):
        """Rimuove i cursori A/B dagli assi e aggiorna il bg_cache.
        Chiamare prima di ogni nuovo avvio live per evitare cursori congelati."""
        for a in self._ab_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._ab_artists = []
        self._cur_a = None
        self._cur_b = None
        # Ridisegna e aggiorna bg_cache → _on_motion userà la cache pulita
        try:
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        except Exception:
            pass

    def _rebuild_legend_sidebar(self):
        """Ripopola il pannello laterale con le serie attualmente plottate."""
        for w in self._legend_rows:
            try: w.destroy()
            except Exception: pass
        self._legend_rows.clear()
        if not self._series:
            return
        palette = list(_UC_SERIES_PALETTE)
        for col in self._series:
            color = self._colors.get(col, palette[0])
            lbl   = self._col_meta.get(col, {}).get("label", col)
            unit  = self._col_meta.get(col, {}).get("unit", "")
            is_y2 = col in self._y2_cols
            disp = lbl if len(lbl) <= 16 else lbl[:15] + "…"
            if unit:
                disp += f" [{unit}]"
            if is_y2:
                disp += " Y2"
            is_hidden = col in self._hidden
            btn = ctk.CTkButton(
                self._legend_panel,
                text=f"● {disp}",
                fg_color=color if not is_hidden else COLORS["surface2"],
                hover_color=color,
                text_color=COLORS["text"] if not is_hidden else COLORS["text2"],
                font=("Segoe UI", 9),
                anchor="w",
                height=26,
                corner_radius=4,
                command=lambda c=col: self._toggle_series(c)
            )
            btn.pack(side="left", padx=3, pady=4)
            self._legend_rows.append(btn)

        # ── sezione ② ──────────────────────────────────────────────────────
        if getattr(self, "_overlay_lines", {}):
            sep = ctk.CTkFrame(self._legend_panel,
                               fg_color=COLORS["border"], width=1, height=30)
            sep.pack(side="left", padx=6, pady=4)
            self._legend_rows.append(sep)
            all_vis = getattr(self, "_overlay_all_vis", True)
            glob_btn = ctk.CTkButton(
                self._legend_panel,
                text="● ② tutto" if all_vis else "○ ② tutto",
                fg_color=COLORS["accent"] if all_vis else COLORS["surface2"],
                hover_color=COLORS["accent"],
                text_color=COLORS["text"],
                font=("Segoe UI", 9, "bold"),
                height=26, corner_radius=4,
                command=self._toggle_all_overlay)
            glob_btn.pack(side="left", padx=3, pady=4)
            self._legend_rows.append(glob_btn)
            sep2 = ctk.CTkFrame(self._legend_panel,
                                fg_color=COLORS["border"], width=1, height=30)
            sep2.pack(side="left", padx=2, pady=4)
            self._legend_rows.append(sep2)
            for col, line in self._overlay_lines.items():
                color   = line.get_color()
                is_vis  = line.get_visible()
                btn2 = ctk.CTkButton(
                    self._legend_panel,
                    text=f"┄ {col} ②",
                    fg_color=color if is_vis else COLORS["surface2"],
                    hover_color=color,
                    text_color=COLORS["text"] if is_vis else COLORS["text2"],
                    font=("Segoe UI", 9),
                    anchor="w", height=26, corner_radius=4,
                    command=lambda c=col: self._toggle_overlay_line(c))
                btn2.pack(side="left", padx=3, pady=4)
                self._legend_rows.append(btn2)

    def _rescale_visible(self):
        """Ricalcola i limiti Y considerando solo le serie visibili."""
        ax1 = self._ax1
        y1_vals = []
        y2_vals = []
        for col, ys in self._series.items():
            if col in self._hidden:
                continue
            visible_vals = [v for v in ys if v is not None]
            if not visible_vals:
                continue
            if self._ax2 and col in self._y2_cols:
                y2_vals.extend(visible_vals)
            else:
                y1_vals.extend(visible_vals)
        if y1_vals:
            mn, mx = min(y1_vals), max(y1_vals)
            pad = (mx - mn) * 0.05 or 1.0
            ax1.set_ylim(mn - pad, mx + pad)
        if self._ax2 and y2_vals:
            mn, mx = min(y2_vals), max(y2_vals)
            pad = (mx - mn) * 0.05 or 1.0
            self._ax2.set_ylim(mn - pad, mx + pad)

    def _toggle_series(self, col):
        if col in self._hidden:
            self._hidden.discard(col)
        else:
            self._hidden.add(col)
        for c, line in self._lines.items():
            line.set_visible(c not in self._hidden)
        self._rescale_visible()
        self._rebuild_legend_sidebar()
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)

    def _toggle_overlay_line(self, col):
        """Mostra/nasconde singola serie ② dal pannello legenda."""
        if col not in getattr(self, "_overlay_lines", {}):
            return
        line = self._overlay_lines[col]
        line.set_visible(not line.get_visible())
        self._rebuild_legend_sidebar()
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)

    def _toggle_all_overlay(self):
        """Mostra/nasconde tutte le serie ② con un click."""
        self._overlay_all_vis = not getattr(self, "_overlay_all_vis", True)
        for line in getattr(self, "_overlay_lines", {}).values():
            line.set_visible(self._overlay_all_vis)
        self._rebuild_legend_sidebar()
        self._canvas.draw()
        self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)

    def export_png(self, filepath):
        ax1 = self._ax1
        h1, l1 = ax1.get_legend_handles_labels()
        h2, l2 = (self._ax2.get_legend_handles_labels() if self._ax2 else ([], []))
        leg = None
        if h1 or h2:
            leg = ax1.legend(h1+h2, l1+l2, loc="upper left",
                bbox_to_anchor=(1.01,1), borderaxespad=0, fontsize=7.5,
                framealpha=0.85, facecolor=COLORS["surface"],
                edgecolor=COLORS["border"], labelcolor=COLORS["text"])
        _overlay = []
        if self._info_var.get().strip():
            for _a in ([self._cross_v] if self._cross_v is not None else []) + \
                       self._dot_artists + \
                       ([self._tooltip] if self._tooltip is not None else []):
                _a.set_animated(False); _overlay.append(_a)
            if _overlay: self._canvas.draw()
        self._fig.savefig(filepath, dpi=150, bbox_inches="tight",
            bbox_extra_artists=([leg] if leg else None),
            facecolor=self._fig.get_facecolor())
        if leg: leg.remove()
        for _a in _overlay: _a.set_animated(True)
        self._drawing = True
        try:
            self._canvas.draw()
            self._bg_cache = self._canvas.copy_from_bbox(self._fig.bbox)
        finally:
            self._drawing = False


_PC = {
    1:"#f44322",2:"#3f51b5",3:"#29b6f6",4:"#66bb6a",
    5:"#7d0910",6:"#607d8b",7:"#9c27b0",8:"#ff9800",
    "set_temp":"#795548","set_forza":"#7d0910",
    "lmax":"#607d8b","lmin":"#9c27b0",
    "bg":"#ccffff","grid":"#cccccc",
}
_SERIES_COLORS = {
    "TS1":"#e5672c","TS2":"#828282","TS3":"#407da5","TS4":"#e7b73b",
    "TS5":"#9c27b0","TS6":"#607d8b","TS7":"#ff9800","TS8":"#29b6f6",
    "TI1":"#e5672c","TI2":"#828282","TI3":"#407da5","TI4":"#e7b73b",
    "TI5":"#9c27b0","TI6":"#607d8b","TI7":"#ff9800","TI8":"#29b6f6",
    "T1":"#e5672c","T2":"#828282","T3":"#407da5","T4":"#e7b73b",
    "T5":"#9c27b0","T6":"#607d8b","T7":"#ff9800","T8":"#29b6f6",
    "P1":"#407da5","P2":"#e5672c","P3":"#828282","P4":"#e7b73b",
    "Z1":"#407da5","Z2":"#e5672c","Z3":"#828282","Z4":"#e7b73b",
    "F1":"#f44322","F2":"#3f51b5","F3":"#29b6f6","F4":"#66bb6a","FC":"#f44322","SPC":"#7d0910",
    "VS1":"#407da5","VS2":"#e5672c","V1":"#407da5","V2":"#e5672c",
    "VI1":"#407da5","VI2":"#e5672c","VI3":"#828282","VI4":"#e7b73b",
    "V3":"#828282","V4":"#e7b73b",
}
_PROFILES = {
"Inner Tub":{"ricetta":"Tub - Ciclo nuovo","temp_set_sup":127.0,"temp_set_inf":125.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax_sup":1090, "vuoto_bg_ymax_sup":-0.2, "vuoto_no_bg_inf":True,
    "x_ticks":[0,174,349,523,698,872,1047,1221,1396,1570,1745],"x_max":1745,
    "forza_legend_loc":"lower right","pressa":"Cannon 5000T","persico":False},
"Polecrasher":{"ricetta":"Polecrasher - Ciclo nuovo","temp_set_sup":129.0,"temp_set_inf":127.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax_inf":1100,"vuoto_bg_ymax_inf":-0.2, "vuoto_no_bg_sup":True,
    "x_ticks":[0,174,348,522,696,870,1044,1218,1392,1566,1740],"x_max":1740,
    "forza_legend_loc":"upper left","pressa":"Cannon 5000T","persico":False},
"Tub Floor Shell":{"ricetta":"Tub Floor Shell - Ciclo nuovo","temp_set_sup":129.0,"temp_set_inf":130.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax_sup":1070, "vuoto_bg_ymax_sup":-0.2, "vuoto_no_bg_inf":True,
    "x_ticks":[0,150,300,450,600,750,900,1050,1200,1350,1500],"x_max":1500,
    "forza_legend_loc":"upper left","pressa":"Cannon 5000T","persico":False},
"Front Firewall":{"ricetta":"Front Firewall - Ciclo","pressa":"Persico 2500T","persico":True,
    "teorico_sec":2633,"temp_set_sup":130.0,"temp_set_inf":128.0,
    "temp_y":(95.0,165.0),"temp_yticks":[100,110,120,130,140,150,160],
    "forza_y":(5900,6900),"forza_yticks":[6000,6100,6200,6300,6400,6500,6600,6700,6800],
    "forza_spc":6500.0,"forza_delta":200,
    "posiz_y":(-0.35,0.05),"posiz_yticks":[-0.35,-0.30,-0.25,-0.20,-0.15,-0.10,-0.05,0.0,0.05],
    "vuoto_y":(-1050,50),"vuoto_yticks":[-1000,-800,-600,-400,-200,0],
    "x_ticks":[0,132,264,396,528,660,792,924,1056,1188,1320,1452,1496],"x_max":1496,
    "forza_legend_loc":"lower right","temp_range":(120,140),"skip_seconds":8},

"Central Cofango":{"ricetta":"Central Cofango - Ciclo","pressa":"Persico 2500T","persico":True,
    "teorico_sec":879,"temp_set_sup":142.0,"temp_set_inf":142.0,
    "temp_y":(100.0,160.0),"temp_yticks":[100,110,120,130,140,150,160],
    "forza_y":(3500,4300),"forza_yticks":[3500,3600,3700,3800,3900,4000,4100,4200,4300],
    "forza_spc":4000.0,"forza_delta":200,
    "posiz_y":(0.0,0.18),"posiz_yticks":[0.0,0.02,0.04,0.06,0.08,0.10,0.12,0.14,0.16,0.18],
    "vuoto_y":(-1000,0),"vuoto_yticks":[-1000,-900,-800,-700,-600,-500,-400,-300,-200,-100,0],
    "x_ticks_tv":list(range(22, 406+1, 12)),
    "x_ticks_pos":list(range(14, 410+1, 12)),
    "x_ticks_forza":list(range(22, 406+1, 12)),
    "x_ticks_vac_sup":list(range(14, 410+1, 12)),
    "x_ticks_vac_inf":list(range(22, 406+1, 12)),
    "forza_legend_loc":"lower right",
    "forza_range":(3750,4250)},
    "Side Cofango Inner":{"ricetta":"Side Cofango Inner - Ciclo","pressa":"Persico 2500T","persico":True,
        "teorico_sec":990,"temp_set_sup":142.0,"temp_set_inf":142.0,
        "temp_y":(100.0,160.0),"temp_yticks":[100,110,120,130,140,150,160],
        "forza_y":(3500,4300),"forza_yticks":[3500,3600,3700,3800,3900,4000,4100,4200,4300],
        "forza_spc":4000.0,"forza_delta":200,
        "posiz_y":(-0.05,0.3),"posiz_yticks":[-0.05,0.0,0.05,0.1,0.15,0.2,0.25,0.3],
        "vuoto_y":(-1000,0),"vuoto_yticks":[-1000,-900,-800,-700,-600,-500,-400,-300,-200,-100,0],
        "x_ticks_tv":list(range(25, 520+1, 15)),
        "x_ticks_pos":list(range(15, 525+1, 15)),
        "x_ticks_forza":list(range(25, 520+1, 15)),
        "x_ticks_vac_sup":list(range(15, 525+1, 15)),
        "x_ticks_vac_inf":list(range(25, 520+1, 15)),
        "forza_legend_loc":"lower right",
        "forza_range":(3750,4250),"temp_range":(130, 150)},
"Side Cover":{"ricetta":"Side Cover - Ciclo","pressa":"Krauss Maffei","persico":False,
    "temp_set_sup":130.0,"temp_set_inf":128.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax":1070, "vuoto_bg_ymax":-0.2,
    "x_ticks":[0,150,300,450,600,750,900,1050,1200,1350,1500],"x_max":1500,
    "forza_legend_loc":"upper left"},
}
_PRESSA_STAMPI = {
    "Cannon 5000T":["Inner Tub","Tub Floor Shell","Polecrasher"],
    "Persico 2500T":["Front Firewall","Central Cofango","Side Cofango Inner"],
    "Krauss Maffei":["Side Cover"],
}



# -- UNIVERSAL PLANT PDF ---------------------------------------------------

_PLANT_PALETTE = [
    "#e5672c", "#3f51b5", "#29b6f6", "#66bb6a",
    "#9c27b0", "#ff9800", "#e7b73b", "#607d8b",
    "#f44322", "#00bcd4", "#8bc34a", "#ff5722",
]

def _plant_pdf_colors(cols):
    return {c: _PLANT_PALETTE[i % len(_PLANT_PALETTE)] for i, c in enumerate(cols)}


def _plant_pdf_header(fig, title, subtitle, logo_path, page_num, total_pages,
                      generated_at, meta_rows):
    fig.add_artist(plt.Line2D(
        [0.03, 0.97], [0.997, 0.997],
        transform=fig.transFigure, color="#444", lw=1.0))
    if logo_path and os.path.exists(logo_path):
        try:
            import matplotlib.image as _mpi
            ax_l = fig.add_axes([0.03, 0.948, 0.055, 0.042], frameon=False)
            ax_l.imshow(_mpi.imread(logo_path), aspect="auto")
            ax_l.axis("off")
            tx_x = 0.10
        except Exception:
            tx_x = 0.03
    else:
        tx_x = 0.03
    fig.text(tx_x, 0.978, title, fontsize=13, fontweight="bold", va="top", color="#111")
    fig.text(tx_x, 0.961, subtitle, fontsize=8.5, va="top", color="#555")
    fig.text(0.97, 0.978, f"Generato: {generated_at}",
             fontsize=7.5, ha="right", va="top", color="#777")
    fig.text(0.97, 0.963, f"Pag. {page_num} / {total_pages}",
             fontsize=7.5, ha="right", va="top", color="#777")
    fig.add_artist(plt.Line2D(
        [0.03, 0.97], [0.950, 0.950],
        transform=fig.transFigure, color="#aaa", lw=0.5))
    if meta_rows:
        y0 = 0.943
        rh = 0.022
        for lbl, val in meta_rows[:8]:
            fig.text(0.03, y0, lbl, fontsize=7.5, fontweight="bold", va="top", color="#333")
            fig.text(0.22, y0, str(val), fontsize=7.5, va="top", color="#111")
            fig.add_artist(plt.Line2D(
                [0.03, 0.97], [y0 - 0.017, y0 - 0.017],
                transform=fig.transFigure, color="#ddd", lw=0.4))
            y0 -= rh
        fig.add_artist(plt.Line2D(
            [0.03, 0.97], [y0 - 0.004, y0 - 0.004],
            transform=fig.transFigure, color="#888", lw=0.6))
        return y0 - 0.012
    return 0.940


def _plant_pdf_setup_ax(ax, title, unit, xs_all, ys_all, x_type, color_grid="#e0e0e0"):
    ax.set_facecolor("white")
    for sp in ax.spines.values():
        sp.set_edgecolor("#aaa")
        sp.set_linewidth(0.6)
    ax.tick_params(axis="both", labelsize=7, length=3, color="#888", labelcolor="#333")
    ax.grid(True, axis="y", color=color_grid, linewidth=0.5, linestyle="-", alpha=0.8)
    ax.grid(True, axis="x", color=color_grid, linewidth=0.3, linestyle="--", alpha=0.5)
    ax.set_title(title, fontsize=9, fontweight="bold", pad=5, color="#222", loc="left")
    if unit:
        ax.set_ylabel(unit, fontsize=7.5, color="#555", labelpad=3)
    flat = [v for v in ys_all if v is not None]
    if flat:
        mn, mx = min(flat), max(flat)
        pad = (mx - mn) * 0.08 or max(abs(mn) * 0.05, 0.001)
        ax.set_ylim(mn - pad, mx + pad)
    if x_type == "datetime":
        valid_x = [x for x in xs_all if x is not None]
        if valid_x:
            span = max(valid_x) - min(valid_x)
            if span < 1 / 24:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            elif span < 1:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            elif span < 7:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
            else:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y"))
    plt.setp(ax.get_xticklabels(), rotation=25, fontsize=6.5, color="#555")


def _plant_pdf_legend(ax, ncol=4):
    h, l = ax.get_legend_handles_labels()
    if not h:
        return
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              ncol=min(ncol, len(l)), fontsize=7, framealpha=0.9,
              edgecolor="#ccc", handlelength=2.0, borderpad=0.5, labelspacing=0.3)


def _plant_group_series(y_cols, y2_cols, col_meta):
    groups = {}
    for col in y_cols:
        m = col_meta.get(col, {})
        unit  = m.get("unit", "")
        label = m.get("label", col)
        key = m.get("label", col) if m.get("label", col) != col else (unit or "Valori")
        if key not in groups:
            groups[key] = {"unit": unit, "cols": [], "y2": False}
        groups[key]["cols"].append(col)
    result = []
    for title, g in groups.items():
        is_y2 = any(c in y2_cols for c in g["cols"])
        result.append((title, g["unit"], g["cols"], is_y2))
    return result


def _plant_pdf_stats_table(fig, y_cols, col_meta, all_stats, top_y,
                           stats2=None, cols2=None, col_meta2=None):
    ax = fig.add_axes([0.03, 0.05, 0.94, top_y - 0.08])
    ax.axis("off")
    cols2 = cols2 or []
    stats2 = stats2 or {}
    col_meta2 = col_meta2 or {}

    def _fmt(v):
        return f"{v:.4g}" if isinstance(v, float) else "-"

    y_set  = set(y_cols)
    c2_set = set(cols2)
    shared     = [c for c in y_cols if c in c2_set]   # stesso nome
    only_csv1  = [c for c in y_cols if c not in c2_set]
    only_csv2  = [c for c in cols2  if c not in y_set]

    cur_y = top_y - 0.02  # posizione verticale corrente
    ax2 = fig.add_axes([0.03, 0.05, 0.94, top_y - 0.08])
    ax2.axis("off")
    txt_kw = dict(transform=fig.transFigure, fontsize=7.5, va="top")

    def _draw_table(title, col_labels, rows_data, y_start, hdr_color="#333"):
        if not rows_data:
            return y_start
        # titolo sezione
        fig.text(0.05, y_start, title, fontsize=8, fontweight="bold",
                 color="#444", transform=fig.transFigure, va="top")
        y_start -= 0.025
        avail_h = max(0.05, y_start - 0.06)
        ax_t = fig.add_axes([0.03, y_start - avail_h, 0.94, avail_h])
        ax_t.axis("off")
        tbl = ax_t.table(cellText=rows_data, colLabels=col_labels,
                         loc="upper center", cellLoc="center")
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(6.8)
        tbl.scale(1, 1.3)
        for j in range(len(col_labels)):
            cell = tbl[0, j]
            cell.set_facecolor(hdr_color)
            cell.set_text_props(color="white", fontweight="bold")
        for i_r, row in enumerate(rows_data, start=1):
            bg = "#f7f7f7" if i_r % 2 == 0 else "white"
            for j in range(len(col_labels)):
                cell = tbl[i_r, j]
                cell.set_facecolor(bg)
                cell.set_edgecolor("#ddd")
        row_h = avail_h / (len(rows_data) + 1)
        return y_start - avail_h - 0.02

    cur_y = top_y - 0.01

    # ── Sezione affiancata (colonne con stesso nome) ────────────────────────
    if shared:
        hdr_shared = ["Colonna", "Unità",
                      "N ①", "Min ①", "Max ①", "Media ①",
                      "N ②", "Min ②", "Max ②", "Media ②"]
        rows_shared = []
        for col in shared:
            m1  = col_meta.get(col, {})
            m2  = col_meta2.get(col, m1)
            s1  = all_stats.get(col, {})
            s2  = stats2.get(col, {})
            unit = m1.get("unit", m2.get("unit", ""))
            rows_shared.append([
                col[:22], unit,
                str(s1.get("n", "-")),
                _fmt(s1.get("min")), _fmt(s1.get("max")), _fmt(s1.get("mean")),
                str(s2.get("n", "-")),
                _fmt(s2.get("min")), _fmt(s2.get("max")), _fmt(s2.get("mean")),
            ])
        cur_y = _draw_table("Confronto ① vs ②", hdr_shared, rows_shared, cur_y, "#1a6b3a")

    # ── Solo CSV1 ──────────────────────────────────────────────────────────
    if only_csv1:
        hdr1 = ["Colonna ①", "Tipo / Unità", "N", "Min", "Max", "Media (μ)", "Dev.Std (σ)", "Anomalie"]
        rows1 = []
        for col in only_csv1:
            m   = col_meta.get(col, {})
            st  = all_stats.get(col, {})
            anom = st.get("anomalies", 0)
            rows1.append([
                col[:24],
                f"{m.get('label', col)[:18]} / {m.get('unit', '')}",
                str(st.get("n", "-")),
                _fmt(st.get("min")), _fmt(st.get("max")), _fmt(st.get("mean")), _fmt(st.get("std")),
                f"⚠ {anom}" if anom > 0 else "OK",
            ])
        cur_y = _draw_table("Solo CSV principale ①", hdr1, rows1, cur_y, "#333")

    # ── Solo CSV2 ──────────────────────────────────────────────────────────
    if only_csv2:
        hdr2 = ["Colonna ②", "Unità", "N", "Min", "Max", "Media (μ)", "Dev.Std (σ)"]
        rows2_t = []
        for col in only_csv2:
            m2 = col_meta2.get(col, {})
            s2 = stats2.get(col, {})
            rows2_t.append([
                col[:24], m2.get("unit", ""),
                str(s2.get("n", "-")),
                _fmt(s2.get("min")), _fmt(s2.get("max")),
                _fmt(s2.get("mean")), _fmt(s2.get("std")),
            ])
        cur_y = _draw_table("Solo CSV confronto ②", hdr2, rows2_t, cur_y, "#1a3f7a")

    # ── Fallback: solo CSV1 senza confronto ────────────────────────────────
    if not shared and not only_csv2 and not only_csv1:
        ax.text(0.5, 0.5, "Nessuna statistica disponibile",
                ha="center", va="center", fontsize=10, color="#888",
                transform=ax.transAxes)


def generate_plant_pdf(rows, headers, col_meta,
                       x_col, y_cols, y2_cols,
                       output_path,
                       plant_name="Impianto",
                       logo_path=None,
                       notes="",
                       rows2=None, cols2=None,
                       colors2=None, col_meta2=None):
    if not rows:
        raise ValueError("Nessun dato disponibile per generare il PDF.")
    if not y_cols:
        raise ValueError("Seleziona almeno una colonna Y prima di generare il PDF.")
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    FW, FH = 8.27, 11.69
    xs_raw, series, x_type = _uc_build_series(rows, x_col, y_cols, col_meta)

    def to_num(xs):
        if x_type == "datetime":
            return [mdates.date2num(x) if isinstance(x, datetime) else None for x in xs]
        return [float(x) if x is not None else None for x in xs]

    xs_num = to_num(xs_raw)

    def clean(xs, ys):
        pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
        return ([p[0] for p in pairs], [p[1] for p in pairs]) if pairs else ([], [])

    all_stats = {}
    for col in y_cols:
        vals = []
        for r in rows:
            try:
                vals.append(float(r.get(col, "").replace(",", ".")))
            except Exception:
                pass
        if vals:
            mean = sum(vals) / len(vals)
            std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
            anom_count = sum(1 for v in vals if std > 0 and abs(v - mean) > 2.5 * std)
            all_stats[col] = {"n": len(vals), "min": min(vals), "max": max(vals),
                              "mean": mean, "std": std, "anomalies": anom_count}
    # statistiche CSV2 ②
    all_stats2 = {}
    if rows2 and cols2:
        for col in cols2:
            vals2 = []
            for r in rows2:
                _v = r.get(col, "")
                try:
                    vals2.append(float((str(_v) if not isinstance(_v, str) else _v).replace(",", ".")))
                except Exception:
                    pass
            if vals2:
                _m2 = sum(vals2) / len(vals2)
                _s2 = (sum((v - _m2)**2 for v in vals2) / len(vals2)) ** 0.5
                all_stats2[col] = {"n": len(vals2), "min": min(vals2),
                                   "max": max(vals2), "mean": _m2, "std": _s2}

    groups = _plant_group_series(y_cols, y2_cols, col_meta)
    ts_first = xs_raw[0]  if xs_raw  else None
    ts_last  = xs_raw[-1] if xs_raw  else None

    def fmt_ts(t):
        if isinstance(t, datetime):
            return t.strftime("%d/%m/%Y %H:%M:%S")
        return str(t) if t is not None else "—"

    dur_str = "—"
    if isinstance(ts_first, datetime) and isinstance(ts_last, datetime):
        sec = int((ts_last - ts_first).total_seconds())
        h, rem = divmod(sec, 3600)
        m, s   = divmod(rem, 60)
        dur_str = f"{h:02d}:{m:02d}:{s:02d}  ({sec} sec)"

    meta_p1 = [
        ("Impianto",        plant_name),
        ("File CSV",        os.path.basename(output_path)),
        ("Campioni",        str(len(rows))),
        ("Colonne analiz.", str(len(y_cols))),
        ("Inizio",          fmt_ts(ts_first)),
        ("Fine",            fmt_ts(ts_last)),
        ("Durata",          dur_str),
    ]
    if notes:
        meta_p1.append(("Note", notes[:80]))

    graphs_per_page = 2
    n_graph_pages   = max(1, math.ceil(len(groups) / graphs_per_page))
    total_pages     = 1 + n_graph_pages + 1
    colors = _plant_pdf_colors(y_cols)

    with PdfPages(output_path) as pdf:
        # PAG. 1 — copertina
        fig = plt.figure(figsize=(FW, FH), facecolor="white")
        subtitle = (f"Analisi parametri operativi  ·  "
                    f"{len(rows)} campioni  ·  {len(y_cols)} serie")
        plot_top = _plant_pdf_header(
            fig, title=plant_name, subtitle=subtitle, logo_path=logo_path,
            page_num=1, total_pages=total_pages,
            generated_at=generated_at, meta_rows=meta_p1)
        # ── Tabella statistica (opzione A) ──────────────────────────────────────
        tbl_top = max(0.10, plot_top - 0.05)
        ax_tbl = fig.add_axes([0.05, 0.05, 0.90, max(0.10, tbl_top - 0.10)])
        ax_tbl.axis("off")
        col_labels = ["Serie", "Tipo / Unità", "N", "Min", "Max", "Media", "Dev.Std"]
        table_data = []
        for col in y_cols:
            m   = col_meta.get(col, {})
            ys  = [v for v in series.get(col, []) if v is not None]
            if not ys:
                continue
            mean_v = sum(ys) / len(ys)
            std_v  = (sum((v - mean_v) ** 2 for v in ys) / len(ys)) ** 0.5
            table_data.append([
                col[:28],
                f"{m.get('label', col)[:20]} {m.get('unit', '')}".strip(),
                str(len(ys)),
                f"{min(ys):.4g}",
                f"{max(ys):.4g}",
                f"{mean_v:.4g}",
                f"{std_v:.4g}",
            ])
        if table_data:
            tbl = ax_tbl.table(
                cellText=table_data,
                colLabels=col_labels,
                loc="upper center",
                cellLoc="center"
            )
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(7.5)
            tbl.scale(1, 1.45)
            for j in range(len(col_labels)):
                tbl[0, j].set_facecolor("#333")
                tbl[0, j].set_text_props(color="white", fontweight="bold")
            for i in range(1, len(table_data) + 1):
                bg = "#f7f7f7" if i % 2 == 0 else "white"
                for j in range(len(col_labels)):
                    tbl[i, j].set_facecolor(bg)
                    tbl[i, j].set_edgecolor("#ddd")
        else:
            ax_tbl.text(0.5, 0.5, "Nessun dato numerico disponibile",
                        ha="center", va="center", fontsize=10, color="#888",
                        transform=ax_tbl.transAxes)
        if notes:
            fig.text(0.05, 0.03, f"Note: {notes}", fontsize=7, color="#777",
                     style="italic", va="bottom")
        pdf.savefig(fig, bbox_inches="tight", dpi=150)
        plt.close(fig)

        # PAG. 2..N — grafici per gruppo
        page_num = 2
        i = 0
        while i < len(groups):
            fig = plt.figure(figsize=(FW, FH), facecolor="white")
            _plant_pdf_header(fig, title=plant_name,
                              subtitle="Grafici parametri operativi",
                              logo_path=logo_path, page_num=page_num,
                              total_pages=total_pages,
                              generated_at=generated_at, meta_rows=None)
            page_groups = groups[i: i + graphs_per_page]
            n_on_page   = len(page_groups)
            ax_h   = 0.30 if n_on_page == 2 else 0.50
            ax_top = [0.88 - j * (ax_h + 0.12) for j in range(n_on_page)]
            for j, (g_title, g_unit, g_cols, _is_y2) in enumerate(page_groups):
                y1_c = [c for c in g_cols if c not in y2_cols]
                y2_c = [c for c in g_cols if c in y2_cols]
                ax1 = fig.add_axes([0.07, ax_top[j] - ax_h, 0.86, ax_h])
                all_ys = [v for c in y1_c
                          for _, v in zip(*clean(xs_num, series.get(c, [])))
                          if v is not None]
                _plant_pdf_setup_ax(ax1, g_title, g_unit, xs_num, all_ys, x_type)
                for col in y1_c:
                    xf, yf = clean(xs_num, series.get(col, []))
                    if not xf:
                        continue
                    lbl  = col_meta.get(col, {}).get("label", col)
                    unit = col_meta.get(col, {}).get("unit", "")
                    ax1.plot(xf, yf, color=colors[col], linewidth=0.9,
                             label=f"{lbl} [{unit}]" if unit else lbl, zorder=3)
                if y2_c:
                    ax2 = ax1.twinx()
                    ax2.set_facecolor("none")
                    ax2.tick_params(labelsize=7, colors="#9c27b0")
                    ax2.spines["right"].set_edgecolor("#9c27b0")
                    for col in y2_c:
                        xf, yf = clean(xs_num, series.get(col, []))
                        if not xf:
                            continue
                        lbl  = col_meta.get(col, {}).get("label", col)
                        unit = col_meta.get(col, {}).get("unit", "")
                        ax2.plot(xf, yf, color=colors[col], linewidth=0.9,
                                 linestyle="--",
                                 label=f"{lbl} [{unit}] →Y2" if unit else f"{lbl} →Y2",
                                 zorder=3)
                    h2, l2 = ax2.get_legend_handles_labels()
                    ax2.legend(h2, l2, loc="upper right", fontsize=6.5, framealpha=0.8)
                # ── serie ② confronto CSV (linee tratteggiate) ────────
                if rows2 and cols2:
                    _xs2, _s2, _xt2 = _uc_build_series(
                        rows2, x_col, cols2, col_meta2 or {})
                    _xn2 = to_num(_xs2)
                    _pal2 = ["#ff6b6b","#ffd93d","#6bcb77","#4d96ff",
                             "#c77dff","#f9844a","#90e0ef","#f15bb5"]
                    for _j2, _c2 in enumerate(cols2):
                        _xf2, _yf2 = clean(_xn2, _s2.get(_c2, []))
                        if not _xf2:
                            continue
                        _col2 = (colors2 or {}).get(_c2, _pal2[_j2 % 8])
                        ax1.plot(_xf2, _yf2, color=_col2, linewidth=0.9,
                                 linestyle="--", label=f"{_c2} ③",
                                 zorder=2, alpha=0.85)
                _plant_pdf_legend(ax1, ncol=5)
            pdf.savefig(fig, bbox_inches="tight", dpi=150)
            plt.close(fig)
            page_num += 1
            i += graphs_per_page

        # ULTIMA PAG. — statistiche
        fig = plt.figure(figsize=(FW, FH), facecolor="white")
        _plant_pdf_header(fig, title=plant_name, subtitle="Riepilogo statistico",
                          logo_path=logo_path, page_num=total_pages,
                          total_pages=total_pages,
                          generated_at=generated_at, meta_rows=None)
        _plant_pdf_stats_table(fig, y_cols, col_meta, all_stats, top_y=0.92,
                               stats2=all_stats2, cols2=cols2, col_meta2=col_meta2)
        pdf.savefig(fig, bbox_inches="tight", dpi=150)
        plt.close(fig)


# -- PDF GENERATION HELPERS ----------------------------------

def _pdf_parse_csv(filepath):
    raw = None
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]:
        try:
            with open(filepath, encoding=enc) as f:
                raw = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if raw is None:
        raise ValueError("Impossibile leggere il file con gli encoding supportati.")
    lines = [l for l in raw.splitlines() if l.strip()]
    start = 1 if lines and lines[0].upper().startswith("REPORT GENERATED") else 0
    hdr = lines[start]
    data_sep = ";" if (start+1 < len(lines) and ";" in lines[start+1]) else ","
    if data_sep == ";":
        headers = [h.strip() for h in hdr.split(",")]
        rows = []
        for l in lines[start+1:]:
            parts = l.split(";")
            rows.append({h: parts[i].strip().replace(",", ".") if i < len(parts) else ""
                         for i, h in enumerate(headers)})
    else:
        import io as _io
        rows = list(csv.DictReader(_io.StringIO("\n".join(lines[start:]))))
    TSFMTS = ["%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
              "%d_%m_%Y_%H_%M_%S", "%d/%m/%Y_%H_%M_%S", "%Y-%m-%dT%H:%M:%S.%f"]
    def pt(s):
        s = s.strip().rstrip("Z")
        for fmt in TSFMTS:
            try: return datetime.strptime(s, fmt)
            except Exception: pass
        return None
    t0 = None; data = defaultdict(list); tslist = []
    for r in rows:
        ts = pt(r.get("Timestamp", ""))
        if ts is None: continue
        if t0 is None: t0 = ts
        tslist.append(ts); sec = (ts - t0).total_seconds()
        try: val = float(r.get("Valore", "").replace(",", "."))
        except Exception: continue
        try: ss = r.get("Setpoint", "").strip().replace(",", "."); sp = float(ss) if ss else None
        except Exception: sp = None
        try: step = int(r.get("Step", 0))
        except Exception: step = 0
        data[r.get("Parametro", "").strip()].append((sec, val, step, sp))
    tss = tslist[0] if tslist else None; tse = tslist[-1] if tslist else None
    dur = int((tse - tss).total_seconds()) if tss and tse else 0
    meta = {"idciclo": rows[0].get("IdCiclo", "") if rows else "",
            "partite": ", ".join(sorted(set(r.get("Partita", "") for r in rows))),
            "operatore": rows[0].get("Operatore", "") if rows else "",
            "materiale": ", ".join(sorted(set(r.get("Materiale", "") for r in rows))),
            "tsraw": rows[0].get("Timestamp", "") if rows else "",
            "tsstart": tss, "tsend": tse, "dursec": dur}
    return data, meta

_LK = dict(fontsize=7.0, framealpha=0.9, edgecolor="#ccc", handlelength=1.8,
           handleheight=0.9, borderpad=0.6, labelspacing=0.3)

def _pdf_fmt_date(ts):
    try: return datetime.strptime(ts.rstrip("Z"), "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y %H:%M:%S")
    except Exception: return ts

def _pdf_fmt_ts(ts):
    if ts is None: return ""
    try: return ts.strftime("%d/%m/%Y %H:%M:%S")
    except Exception: return ""

def _pdf_setup_ax(ax, title, ylabel, ylim, yticks, xticks, xmax, draw_bg=True, bg_xmax=None, bg_ymax=None):
    if draw_bg:
        yr = ylim[1] - ylim[0]
        y_top = bg_ymax if bg_ymax is not None else ylim[0] + yr * 206.36/309.54
        if bg_xmax is not None:
            ax.fill_between([0, bg_xmax], ylim[0], y_top, color=_PC["bg"], zorder=0, linewidth=0)
        else:
            ax.axhspan(ylim[0], y_top, color=_PC["bg"], zorder=0)
    ax.set_facecolor("white"); ax.set_xlim(0, xmax); ax.set_ylim(ylim[0], ylim[1])
    ax.set_yticks(yticks)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,f: f"{v:.1f}" if v!=int(v) else f"{int(v)}"))
    ax.set_xticks(xticks); ax.tick_params(axis="both", labelsize=7, length=3, color="#404040")
    ax.set_xlabel("sec", fontsize=7, labelpad=1); ax.set_ylabel(ylabel, fontsize=7, labelpad=2)
    ax.set_title(title, fontsize=9, fontweight="bold", pad=4, color="#111")
    ax.grid(True, linestyle="-", linewidth=0.3, color=_PC["grid"], alpha=1.0, zorder=1)
    for sp in ax.spines.values(): sp.set_edgecolor("#888"); sp.set_linewidth(0.5)

def _pdf_temp(ax, data, params, setval, title, pr):
    _pdf_setup_ax(ax, title, "", pr["temp_y"], pr["temp_yticks"], pr["x_ticks"], pr["x_max"])

    # 1. Plot Set per primo
    ax.axhline(setval, color=_PC["set_temp"], lw=0.8, zorder=4, label="SET")

    # 2. Plot Sonde
    for i, p in enumerate(params):
        if p in data:
            pts = sorted(data[p]); ys = [d[1] for d in pts]
            if not all(abs(v) < 0.01 for v in ys):
                ax.plot([d[0] for d in pts], ys, color=_PC[i+1], lw=0.7, zorder=3, label=p)
                continue
        # Dummy plot
        ax.plot([], [], color=_PC[i+1], lw=0.7, label=p)

    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=1+len(params), **_LK)

def _pdf_posiz(ax, data, params, pr):
    _pdf_setup_ax(ax, "POSIZIONE [mm]", "mm", pr["posiz_y"], pr["posiz_yticks"], pr["x_ticks"], pr["x_max"], draw_bg=False)

    # Nessun set qui, solo Sonde / Posizioni
    for i, p in enumerate(params):
        if p in data:
            pts = sorted(data[p])
            if pts:
                ax.plot([d[0] for d in pts], [d[1] for d in pts], color=_PC[i+1], lw=0.7, zorder=3, label=p)
                continue
        ax.plot([], [], color=_PC[i+1], lw=0.7, label=p)

    ax.axhline(0, color="#999", lw=0.4, linestyle="--", zorder=2)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=len(params), **_LK)

def _pdf_forza(ax, data, params, pr):
    _pdf_setup_ax(ax, "FORZA [kN]", "kN", pr["forza_y"], pr["forza_yticks"], pr["x_ticks"], pr["x_max"], draw_bg=False)

    # Determiniamo se abbiamo dei SET da plottare e li mettiamo prima
    ref = next((p for p in params if p in data), None)
    has_set = False
    if ref:
        pts = sorted(data[ref])
        xs = np.array([d[0] for d in pts if d[3] is not None])
        sps = np.array([d[3] for d in pts if d[3] is not None])
        if len(xs):
            has_set = True
            ax.plot(xs, sps, color=_PC["set_forza"], lw=0.8, zorder=5, label="Set")
            ax.plot(xs, sps + pr["forza_delta"], color=_PC["lmax"], lw=1.0, zorder=5, label="LMax")
            ax.plot(xs, sps - pr["forza_delta"], color=_PC["lmin"], lw=1.0, zorder=5, label="LMin")

    if not has_set:
        # Dummy per garantire che Set appaiano in legenda
        ax.plot([], [], color=_PC["set_forza"], lw=0.8, label="Set")
        ax.plot([], [], color=_PC["lmax"], lw=1.0, label="LMax")
        ax.plot([], [], color=_PC["lmin"], lw=1.0, label="LMin")

    for i, p in enumerate(params):
        lbl = f"Forza{i+1}"
        if p in data:
            pts = sorted(data[p])
            if pts:
                ax.plot([d[0] for d in pts], [d[1] for d in pts], color=_PC[i+1], lw=0.7, zorder=3, label=lbl)
                continue
        ax.plot([], [], color=_PC[i+1], lw=0.7, label=lbl)

    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3+len(params), **_LK)

def _pdf_forza_ff(ax, data, pr):
    _pdf_setup_ax(ax, "FORZA [kN]", "kN", pr["forza_y"], pr["forza_yticks"], pr["x_ticks"], pr["x_max"], draw_bg=False)
    spc = pr.get("forza_spc", 6500.0); d = pr["forza_delta"]
    ax.axhline(spc, color=_PC["set_forza"], lw=0.8, zorder=5, label="SPC")
    ax.axhline(spc+d, color=_PC["lmax"], lw=1.0, zorder=5, label="LMax")
    ax.axhline(spc-d, color=_PC["lmin"], lw=1.0, zorder=5, label="LMin")
    if "F1" in data:
        pts = sorted(data["F1"])
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=_PC[1], lw=0.7, zorder=3, label="FC")
    h, l = ax.get_legend_handles_labels(); ax.legend(h, l, loc=pr.get("forza_legend_loc","lower right"), ncol=4, **_LK)

def _pdf_vuoto(ax, data, params, setvals, title, labels, pr, ylabel="bar", bg_xmax=None, bg_ymax=None, draw_bg=True):
    if bg_xmax is None and bg_ymax is None:
        bg_xmax = pr.get("vuoto_bg_xmax", None)
        bg_ymax = pr.get("vuoto_bg_ymax", None)
    _pdf_setup_ax(ax, title, ylabel, pr["vuoto_y"], pr["vuoto_yticks"], pr["x_ticks"], pr["x_max"], bg_xmax=bg_xmax, bg_ymax=bg_ymax, draw_bg=draw_bg)
    sc = ["black","#555","#888","#aaa"]

    # 1. Disegna linee (reali se ci sono dati, altrimenti fuori dal grafico per la legenda)
    for j, sv in enumerate(setvals):
        ax.axhline(sv, color=sc[j%4], lw=0.7, linestyle="--", zorder=4, label=f"Set {j+1}")

    for i, p in enumerate(params):
        lbl = labels[i] if i < len(labels) else p
        if p in data:
            pts = sorted(data[p]); ys = [d[1] for d in pts]
            if not all(abs(v) < 0.001 for v in ys):
                ax.plot([d[0] for d in pts], ys, color=_PC[i+1], lw=0.7, zorder=3, label=lbl)
                continue
        # Dummy plot per la legenda se mancano i dati
        ax.plot([], [], color=_PC[i+1], lw=0.7, label=lbl)

    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=len(setvals)+len(params), **_LK)

def _logo_ax(fig, logo_path):
    ax = fig.add_axes([0.03, 0.912, 0.042, 0.045])
    try:
        import matplotlib.image as mpi
        lp = logo_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "lamborghini_logo.png")
        if lp and os.path.exists(lp):
            ax.imshow(mpi.imread(lp), aspect="auto"); ax.axis("off"); return
    except Exception: pass
    ax.set_facecolor("#e0e0e0")
    ax.text(0.5,0.5,"LOGO",ha="center",va="center",fontsize=6,color="#888",transform=ax.transAxes)
    ax.axis("off")

def _pdf_hdr_p1(fig, meta, pr, n, logo_path=None):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    _logo_ax(fig, logo_path)
    fig.text(0.08,0.966,"Automobili Lamborghini",fontsize=9,fontweight="bold",va="top",color="#111")
    fig.text(0.08,0.952,"Via Modena, 12",fontsize=7.5,va="top",color="#333")
    fig.text(0.08,0.939,"140019 - Sant'Agata Bolognese (BO)",fontsize=7.5,va="top",color="#333")
    fig.text(0.08,0.926,"Tel.: +39 051 959.7611",fontsize=7.5,va="top",color="#333")
    fig.text(0.50,0.985,"CAMPIONAMENTO PARAMETRI OPERATIVI",fontsize=11,fontweight="bold",ha="center",va="top",color="#111")
    fig.add_artist(plt.Line2D([0.03,0.97],[0.913,0.913],transform=fig.transFigure,color="#aaa",lw=0.5))
    fields=[("ID Ciclo",meta["idciclo"]),("Codice Partita",meta["partite"]),
            ("Nome Ricetta",pr["ricetta"]),("Nome Operatore",meta.get("operatore","")),
            ("Codice Materiale",meta["materiale"]),("Data",_pdf_fmt_date(meta["tsraw"]))]
    if meta.get("note"): fields.append(("Note", meta["note"]))
    y0=0.908; rh=0.022
    for i,(lbl,val) in enumerate(fields):
        y=y0-i*rh
        fig.text(0.03,y,lbl,fontsize=7.5,fontweight="bold",va="top",color="#111")
        fig.text(0.22,y,val,fontsize=7.5,va="top",color="#222")
        fig.add_artist(plt.Line2D([0.03,0.97],[y-0.016,y-0.016],transform=fig.transFigure,color="#ccc",lw=0.5))
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")

def _pdf_hdr_g(fig, n):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    fig.add_artist(plt.Line2D([0.03,0.97],[0.965,0.965],transform=fig.transFigure,color="#555",lw=0.8))
    fig.text(0.50,0.985,"CAMPIONAMENTO PARAMETRI OPERATIVI",fontsize=11,fontweight="bold",ha="center",va="top",color="#111")
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")

def _pdf_hdr_p1ff(fig, meta, pr, n, logo_path=None):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    fig.add_artist(plt.Line2D([0.03,0.97],[0.730,0.730],transform=fig.transFigure,color="#555",lw=0.8))
    _logo_ax(fig, logo_path)
    fig.text(0.08,0.966,"Automobili Lamborghini",fontsize=9,fontweight="bold",va="top",color="#111")
    fig.text(0.08,0.952,"Via Modena, 12",fontsize=7.5,va="top",color="#333")
    fig.text(0.08,0.939,"140019 - Sant'Agata Bolognese (BO)",fontsize=7.5,va="top",color="#333")
    fig.text(0.97,0.966,"Report generato",fontsize=8,ha="right",va="top",color="#555")
    fig.text(0.97,0.952,datetime.now().strftime("%d/%m/%Y %H:%M"),fontsize=8,ha="right",va="top",color="#333")
    fig.text(0.50,0.910,"COMPRESSION MOULDING SYSTEM - CFK TECNOLOGY",fontsize=12,fontweight="bold",ha="center",va="top",color="#111")
    y=0.860; step=0.036
    def row(lbl,val):
        nonlocal y
        fig.text(0.08,y,lbl,fontsize=7.5,fontweight="bold",va="top",color="#111")
        fig.text(0.35,y,val,fontsize=7.5,va="top",color="#222")
        fig.add_artist(plt.Line2D([0.08,0.65],[y-0.016,y-0.016],transform=fig.transFigure,color="#ccc",lw=0.5))
        y-=step
    row("ID CICLO",str(meta.get("idciclo",""))); row("SERIAL NUMBER",meta.get("partite",""))
    row("RICETTA",str(pr.get("ricetta",""))); row("NOME OPERATORE",meta.get("operatore",""))
    row("CODICE MATERIALE",meta.get("materiale","")); row("DATA",meta.get("tsraw","").replace("T"," "))
    row("Inizio ciclo",_pdf_fmt_ts(meta.get("tsstart"))); row("Fine ciclo",_pdf_fmt_ts(meta.get("tsend")))
    row("Teorico Sec",str(pr.get("teorico_sec","-"))); row("Durata Sec",str(meta.get("dursec","-")))
    fig.text(0.50,0.72,"Copyright 2023 Automobili Lamborghini S.p.A., societa ad azionista unico parte del Gruppo Audi.",
             fontsize=6,ha="center",va="top",color="#888")
    fig.text(0.50,0.710,"Tutti i diritti riservati. P.IVA n. 00591801204",fontsize=6,ha="center",va="top",color="#888")
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")

def _pdf_hdr_g_ff(fig, n, meta):
    fig.add_artist(plt.Line2D([0.03,0.97],[0.997,0.997],transform=fig.transFigure,color="#555",lw=0.8))
    fig.add_artist(plt.Line2D([0.03,0.97],[0.965,0.965],transform=fig.transFigure,color="#555",lw=0.8))
    fig.text(0.50,0.985,"COMPRESSION MOULDING SYSTEM - CFK TECNOLOGY",fontsize=10,fontweight="bold",ha="center",va="top",color="#111")
    fig.text(0.03,0.975,f"Report: {datetime.now().strftime('%d/%m/%Y %H:%M')}",fontsize=7,va="top",color="#555")
    fig.text(0.03,0.968,
             f"Inizio: {_pdf_fmt_ts(meta.get('tsstart'))}  Fine: {_pdf_fmt_ts(meta.get('tsend'))}  "
             f"Durata: {meta.get('dursec','-')} sec  Teorico: {meta.get('teorico_sec',meta.get('teorico','-'))} sec",
             fontsize=6.5,va="top",color="#444")
    fig.text(0.97,0.01,str(n),fontsize=8,ha="right",va="bottom",color="#666")


# -- PERSICO V8 PDF -------------------------------------------------------------

def _persico_v8_hdr(fig, meta, pr, logo_path=None):
    try:
        from PIL import Image as _PIL_img
        _pil_ok = True
    except ImportError:
        _pil_ok = False
    try:
        lp = logo_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "lamborghini_logo.png")
        if not os.path.exists(lp): lp = lp.replace(".png", ".jpg")
        if lp and os.path.exists(lp):
            ax_l = fig.add_axes([0.18, 0.87, 0.08, 0.06], frameon=False)
            if _pil_ok:
                ax_l.imshow(np.array(_PIL_img.open(lp).convert("RGBA")))
            else:
                ax_l.text(0.5, 0.5, "Logo\nnon disp.", ha="center", va="center",
                          fontsize=8, color="#aaa", transform=ax_l.transAxes)
            ax_l.axis("off")
    except Exception: pass
    fig.text(0.50,0.915,"automobili",fontsize=15,ha="center",va="center",style="italic",family="serif")
    fig.text(0.50,0.890,"Lamborghini",fontsize=24,ha="center",va="center",style="italic",family="serif",fontweight="bold")
    fig.text(0.50,0.870,"COMPRESSION MOULDING SYSTEM - CFK TECNOLOGY",fontsize=8,fontweight="bold",ha="center",va="top")
    axp=fig.add_axes([0.72,0.875,0.09,0.05],frameon=False); axp.set_xlim(0,1); axp.set_ylim(0,1); axp.axis("off")
    axp.add_patch(plt.Polygon([[0.05,0.1],[0.95,0.1],[0.5,0.9]],fill=True,color="#888"))
    t0s=meta.get("tsstart"); tNs=meta.get("tsend")
    fig.text(0.18,0.84,"Report generato:",fontsize=7,fontweight="bold")
    fig.text(0.31,0.84,meta.get("tsraw","")[:16],fontsize=7,fontweight="bold")
    fig.text(0.44,0.84,"Inizio ciclo",fontsize=7)
    fig.text(0.51,0.84,t0s.strftime("%Y-%m-%dT%H:%M:%S.000Z") if t0s else "",fontsize=7,fontweight="bold")
    fig.text(0.44,0.825,"Fine ciclo",fontsize=7)
    fig.text(0.51,0.825,tNs.strftime("%Y-%m-%dT%H:%M:%S.000Z") if tNs else "",fontsize=7,fontweight="bold")
    fig.text(0.72,0.84,"Teorico [Sec]",fontsize=7); fig.text(0.80,0.84,str(pr.get("teorico_sec","-")),fontsize=7)
    fig.text(0.72,0.825,"Durata [Sec]",fontsize=7); fig.text(0.80,0.825,str(meta.get("dursec","-")),fontsize=7)
    fig.text(0.50,0.04,
        "Copyright (c) 2023 Automobili Lamborghini S.p.A., societa ad azionista unico parte del Gruppo Audi.\n"
        "Tutti i diritti riservati. P.IVA n. 00591801204",
        fontsize=7.5,ha="center",va="bottom",color="#111",linespacing=1.6,fontweight="bold")


def _persico_v8_setup_ax(ax, title, unit, ylim, yticks, xticks, bg_type="none", bg_range=None):
    BG="#e5f0db"
    ax.set_facecolor("white"); ax.set_xlim(xticks[0], xticks[-1]); ax.set_ylim(ylim[0],ylim[1])
    ax.autoscale(False)
    if bg_range:
        ax.axhspan(bg_range[0], bg_range[1], color=BG, zorder=0)
    else:
        if bg_type=="temp":  ax.axhspan(130,150,color=BG,zorder=0)
        elif bg_type=="forza": ax.axhspan(6250,6750,color=BG,zorder=0)
        elif bg_type=="vuoto": ax.axhspan(-1000,-200,color=BG,zorder=0)
    for sp in ax.spines.values(): sp.set_visible(True); sp.set_color("#666"); sp.set_linewidth(0.8)
    ax.set_yticks(yticks)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda v,_: f"{v:.2f}".replace(".",",") if "mm" in title else f"{int(v)}"))
    ax.set_xticks(xticks); ax.tick_params(axis="both",labelsize=7,length=3,color="#666",pad=2,labelcolor="#222")
    plt.setp(ax.get_xticklabels(),rotation=90,fontsize=6)
    ax.grid(True,axis="y",color="#eaeaea",lw=0.6,linestyle="-",zorder=1); ax.grid(False,axis="x")
    ax.set_title(title,fontsize=9.5,pad=6,loc="center",color="#444")
    ax.text(-0.01,1.06,unit,transform=ax.transAxes,fontsize=7.5,ha="center",va="bottom",color="#444",clip_on=False)
    ax.text(0.995,0.04,"[Sec]",transform=ax.transAxes,fontsize=7.5,ha="right",va="bottom",color="#444")


def _persico_v8_cleg(ax, handles, labels, badge_ok=False):
    """Leggenda sotto il grafico in coordinate assolute di figura."""
    import matplotlib.patches as _mp
    if not handles: return
    if badge_ok:
        handles.insert(0, _mp.Patch(color="#e5f0db", label="RANGE OK"))
        labels.insert(0, "RANGE OK")
    box = ax.get_position()
    new_bottom = box.y0 + 0.075
    new_height  = box.height - 0.055
    ax.set_position([box.x0, new_bottom, box.width, new_height])
    leg_y_fig = new_bottom - 0.055
    ax.legend(handles, labels,
              loc="upper center",
              bbox_to_anchor=(box.x0 + box.width / 2, leg_y_fig),
              bbox_transform=ax.figure.transFigure,
              frameon=True, facecolor="white", edgecolor="#bbb",
              fontsize=8, handlelength=2.5, handletextpad=0.5,
              columnspacing=1.5, ncol=len(labels))


def _posiz_y_auto(data, x_min=None):
    """Calcola ylim, yticks e decimali corretti per il grafico posizione."""
    vals = [v for col in ["P1","P2","P3","P4"]
            for _sec,v,_st,_sp in data.get(col,[])
            if isinstance(v,(int,float)) and (x_min is None or _sec >= x_min)]
    if not vals:
        return (-0.35,0.05), [-0.35,-0.30,-0.25,-0.20,-0.15,-0.10,-0.05,0.0,0.05], 2
    mn,mx = min(vals),max(vals)
    # Se tutti i valori sono negativi, ancora y1 a 0.0 (riferimento stampo chiuso)
    if mx < 0:
        y1 = 0.0
        y0 = mn - max(abs(mn)*0.20, 0.005)
    else:
        pad = max((mx-mn)*0.20, 0.005)
        y0,y1 = mn-pad, mx+pad
    rng   = y1-y0 or 0.01
    # Step "bello": potenza di 10 scalata per avere più tick (~8-12 tick)
    exp   = math.floor(math.log10(rng/8))
    raw   = rng/8 / (10**exp)
    mult  = 1 if raw<2 else 2 if raw<5 else 5
    step  = round(mult * (10**exp), 8)
    # Numero di decimali necessari: abbastanza per distinguere i tick
    dec   = max(0, -int(math.floor(math.log10(step)))) if step > 0 else 2
    # Genera tick e arrotonda per evitare floating-point artifacts
    t0    = math.ceil(y0 / step) * step
    ticks = [round(t0 + i*step, dec+1) for i in range(30)
             if t0 + i*step <= y1 + step*0.01]
    return (y0, y1), ticks, dec


def _persico_v8_pages(pdf, data, meta, pr, logo_path=None):
    import matplotlib.patches as _mp
    CT1,CT2,CT3,CT4 = "#e5672c","#828282","#407da5","#e7b73b"
    CSP = "#659346"
    TV   = pr.get("x_ticks_tv", list(range(44, 1452+1, 44)))
    POS  = pr.get("x_ticks_pos", list(range(11, 1463+1, 44)))
    FORZ = pr.get("x_ticks_forza", list(range(44, 1496+1, 44)))
    VAC_SUP = pr.get("x_ticks_vac_sup", TV)
    VAC_INF = pr.get("x_ticks_vac_inf", TV)

    _cc_t_max = 0
    PS = dict(
        temp_y      = pr.get("temp_y",   (100,160)),
        temp_yticks = pr.get("temp_yticks",[100,110,120,130,140,150,160]),
        temp_range  = pr.get("temp_range", (130, 150)),
        tss         = pr.get("temp_set_sup", 130.0),
        tsi         = pr.get("temp_set_inf", 128.0),
        forza_y     = pr.get("forza_y",  (6000,6800)),
        forza_yticks= pr.get("forza_yticks",[6000,6100,6200,6300,6400,6500,6600,6700,6800]),
        forza_range = pr.get("forza_range", (6250, 6750)),
        spc         = pr.get("forza_spc", 6500.0),
        vuoto_y     = pr.get("vuoto_y",  (-1000,0)),
        vuoto_yticks= pr.get("vuoto_yticks",[-1000,-900,-800,-700,-600,-500,-400,-300,-200,-100,0]),
        vuoto_range = pr.get("vuoto_range", (-1000, -200)))
    def gs(p):
        if p not in data: return [],[]
        pts=sorted(data[p]); return [x[0] for x in pts],[x[1] for x in pts]
    _skip_s = pr.get("skip_seconds", 0)
    def gs_skip(p):
        if p not in data: return [],[]
        pts=[x for x in sorted(data[p]) if x[0] >= _skip_s]
        if not pts: return [],[]
        return [x[0] for x in pts],[x[1] for x in pts]
    FW,FH = 8.27,11.69; L,W = 0.18,0.64

    # -- Pag.1: copertina + temperatura sup + inf ------------------------------
    fig = plt.figure(figsize=(FW,FH), facecolor="white")
    _persico_v8_hdr(fig, meta, pr, logo_path)
    rows_t=[("ID CICLO",str(meta.get("idciclo",""))),("SERIAL NUMBER",meta.get("partite","")),
            ("RICETTA",pr.get("ricetta","3")),("NOME OPERATORE",meta.get("operatore","NOME OPERATORE")),
            ("CODICE MATERIALE",meta.get("materiale","")),("DATA",meta.get("tsraw","").replace("T"," "))]
    if meta.get("note"): rows_t.append(("NOTE", meta["note"]))
    rh=0.015; ty=0.81
    for lbl,val in rows_t:
        fig.add_artist(_mp.Rectangle((0.18,ty-rh),0.64,rh,fill=False,edgecolor="#000",lw=0.7,
                                     transform=fig.transFigure,clip_on=False))
        fig.add_artist(plt.Line2D([0.33,0.33],[ty-rh,ty],transform=fig.transFigure,color="#000",lw=0.7))
        fig.text(0.185,ty-rh/2,lbl,fontsize=7.5,va="center",fontweight="bold")
        fig.text(0.335,ty-rh/2,str(val),fontsize=7.5,va="center",fontweight="bold"); ty-=rh
    ax_ts=fig.add_axes([L,0.42,W,0.23]); ax_ti=fig.add_axes([L,0.11,W,0.23])
    _persico_v8_setup_ax(ax_ts,"Temperatura semistampo superiore (°C) - Grafico",
                         "[°C]",PS["temp_y"],PS["temp_yticks"],TV,"temp", PS["temp_range"])
    ax_ts.plot([],[],color=CSP,label="SP",lw=1.2); ax_ts.axhline(PS["tss"],color=CSP,lw=0.8,zorder=3)
    for c,col in zip([CT1,CT3,CT2,CT4],["TS1","TS3","TS2","TS4"]):
        xs,ys=gs(col)
        if xs: ax_ts.plot(xs,ys,color=c,lw=1.2,label=col.replace("TS","T"),zorder=4)
    h,l=ax_ts.get_legend_handles_labels(); _persico_v8_cleg(ax_ts,h,l,True)
    
    _persico_v8_setup_ax(ax_ti,"Temperatura semistampo inferiore (°C) - Grafico",
                         "[°C]",PS["temp_y"],PS["temp_yticks"],TV,"temp", PS["temp_range"])
    ax_ti.plot([],[],color=CSP,label="SP",lw=1.2); ax_ti.axhline(PS["tsi"],color=CSP,lw=0.8,zorder=3)
    for c,col in zip([CT3,CT1,CT2,CT4],["TI3","TI1","TI2","TI4"]):
        xs,ys=gs(col)
        if xs: ax_ti.plot(xs,ys,color=c,lw=1.2,label=col.replace("TI","T"),zorder=4)
    h,l=ax_ti.get_legend_handles_labels(); _persico_v8_cleg(ax_ti,h,l,True)
    
    pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)

    # -- Pag.2: posizione (Y ADATTIVA) + forza ---------------------------------
    fig = plt.figure(figsize=(FW,FH), facecolor="white")
    _persico_v8_hdr(fig, meta, pr, logo_path)
    ax_p=fig.add_axes([L,0.48,W,0.28]); ax_f=fig.add_axes([L,0.11,W,0.28])
    _py,_pticks,_pdec = _posiz_y_auto(data)
    _persico_v8_setup_ax(ax_p,"Posizione piano (mm) - Grafico","[mm]",_py,_pticks,POS,"none")
    # Sovrascrive formatter con la precisione calcolata sul passo reale
    ax_p.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda v,_,d=_pdec: f"{v:.{d}f}".replace(".",",")))
    for c,col in zip([CT3,CT1,CT2,CT4],["P1","P2","P3","P4"]):
        xs,ys=gs_skip(col)
        if xs: ax_p.plot(xs,ys,color=c,lw=1.2,label=col,zorder=4)
    h,l=ax_p.get_legend_handles_labels(); _persico_v8_cleg(ax_p,h,l,False)
    _persico_v8_setup_ax(ax_f,"Forza (kN) - Grafico","[kN]",
                         PS["forza_y"],PS["forza_yticks"],FORZ,"forza", PS["forza_range"])
    ax_f.axhline(PS["spc"],color=CT1,lw=1.2,label="SPC",zorder=3)
    # Usa FC se disponibile (nativi caricati), altrimenti F1 come fallback (solo CSV)
    xs,ys=gs_skip("FC") if "FC" in data else gs_skip("F1")
    if xs: ax_f.plot(xs,ys,color=CSP,lw=1.2,label="FC",zorder=4)
    h,l=ax_f.get_legend_handles_labels(); _persico_v8_cleg(ax_f,h,l,True)
    
    pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)

    # -- Pag.3: vuoto superiore + inferiore ------------------------------------
    fig = plt.figure(figsize=(FW,FH), facecolor="white")
    _persico_v8_hdr(fig, meta, pr, logo_path)
    ax_vs=fig.add_axes([L,0.48,W,0.28]); ax_vi=fig.add_axes([L,0.11,W,0.28])
    _persico_v8_setup_ax(ax_vs,"Vuoto semistampo superiore (mbar) - Grafico","[mbar]",
                         PS["vuoto_y"],PS["vuoto_yticks"],VAC_SUP,"vuoto", PS["vuoto_range"])
    for c,col in zip([CT1,CT2],["VS1","VS2"]):
        xs,ys=gs(col)
        if xs: ax_vs.plot(xs,ys,color=c,lw=1.2,label=col.replace("VS","V"),zorder=4)
    h,l=ax_vs.get_legend_handles_labels(); _persico_v8_cleg(ax_vs,h,l,True)
    _persico_v8_setup_ax(ax_vi,"Vuoto semistampo inferiore (mbar) - Grafico","[mbar]",
                         PS["vuoto_y"],PS["vuoto_yticks"],VAC_INF,"vuoto", PS["vuoto_range"])
    for c,col in zip([CT3,CT1],["VI1","VI2"]):
        xs,ys=gs(col)
        if xs: ax_vi.plot(xs,ys,color=c,lw=1.2,label=col.replace("VI","V"),zorder=4)
    h,l=ax_vi.get_legend_handles_labels(); _persico_v8_cleg(ax_vi,h,l,True)
    
    pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)


def _parse_native_pack(native_paths, stampo_name=""):
    """Legge file nativi Persico 2500T. native_paths = dict {tipo: filepath}"""
    from datetime import datetime as _dt
    def _read_wide(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = [l for l in f.readlines() if l.strip()]
        start = 1 if lines and lines[0].upper().startswith("REPORT") else 0
        hdr = [h.strip() for h in lines[start].split(";")]
        rows = []
        for l in lines[start+1:]:
            parts = l.strip().split(";")
            row = {hdr[i]: parts[i].strip().replace(",",".") for i in range(min(len(hdr),len(parts))) if hdr[i]}
            rows.append(row)
        return hdr, rows
    def _to_pts(rows, col, sp_col=None):
        pts = []
        for r in rows:
            try:
                t = float(r.get("Time",""))
                s = r.get(col,"").strip()
                if not s: continue
                val = float(s)
                sp = None
                if sp_col:
                    try: sp = float(r.get(sp_col,"").strip())
                    except Exception: pass
                pts.append((t, val, 0, sp))
            except Exception: continue
        return pts
    data = {}; meta_patch = {}
    if "DATI_GENERALI" in native_paths:
        with open(native_paths["DATI_GENERALI"], encoding="utf-8", errors="replace") as f:
            dg = [l.strip() for l in f.readlines()]
        keys = ["idciclo","partite","_stampo","operatore","materiale"]
        for i,k in enumerate(keys):
            if i < len(dg) and k != "_stampo": meta_patch[k] = dg[i]
        # Filtra partita in base al profilo
        if len(dg) >= 2:
            all_parts = [p.strip() for p in dg[1].split("/") if p.strip()]
            sn = stampo_name.upper()
            if "FRONT FIREWALL" in sn:
                filtered = [p for p in all_parts if "RF" in p.upper()]
            elif "CENTRAL COFANGO" in sn:
                filtered = [p for p in all_parts if "IC" in p.upper()]
            elif "SIDE COFANGO" in sn:
                # DX = SD, SX = SS - tienile entrambe
                filtered = [p for p in all_parts if "SD" in p.upper() or "SS" in p.upper()]
            else:
                filtered = all_parts
            if filtered:
                meta_patch["partite"] = " / ".join(filtered)
        if len(dg) >= 9:
            try: meta_patch["tsraw"] = dg[8].rstrip("Z").split(".")[0].replace("T"," ")
            except Exception: pass
    if "FORZA" in native_paths:
        _, rows = _read_wide(native_paths["FORZA"])
        # Legge F1÷F4 (sensori singoli) e FC (forza combinata con setpoint SPC)
        for _c in ["F1","F2","F3","F4"]:
            pts = _to_pts(rows, _c)
            if pts: data[_c] = pts
        pts = _to_pts(rows, "FC", "SPC")
        if pts: data["FC"] = pts
    if "POSIZIONE" in native_paths:
        _, rows = _read_wide(native_paths["POSIZIONE"])
        for c in ["P1","P2","P3","P4"]:
            pts = _to_pts(rows, c)
            if pts: data[c] = pts
    if "TEMPS_SUP" in native_paths:
        _, rows = _read_wide(native_paths["TEMPS_SUP"])
        for i,c in enumerate(["T1","T2","T3","T4","T5"],1):
            pts = _to_pts(rows, c, "SP")
            if pts: data[f"TS{i}"] = pts
    if "TEMPS_INF" in native_paths:
        _, rows = _read_wide(native_paths["TEMPS_INF"])
        for i,c in enumerate(["T1","T2","T3","T4","T5"],1):
            pts = _to_pts(rows, c, "SP")
            if pts: data[f"TI{i}"] = pts
    if "VUOTO_SUP" in native_paths:
        _, rows = _read_wide(native_paths["VUOTO_SUP"])
        for i,c in enumerate(["V1","V2"],1):
            pts = _to_pts(rows, c, "SET -")
            if pts: data[f"VS{i}"] = pts
    if "VUOTO_INF" in native_paths:
        _, rows = _read_wide(native_paths["VUOTO_INF"])
        for i,c in enumerate(["V1","V2"],1):
            pts = _to_pts(rows, c, "SET -")
            if pts: data[f"VI{i}"] = pts
    return data, meta_patch


def _merge_native_data(base_data, base_meta, native_data, meta_patch):
    merged = dict(base_data); merged.update(native_data)
    meta = dict(base_meta); meta.update(meta_patch)
    return merged, meta


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


def generate_lamborghini_pdf(csv_path, stampo_name, output_path, logo_path=None, filter_params=None, t_start=None, t_end=None, preloaded_data=None, preloaded_meta=None):
    if logo_path is None:
        here=os.path.dirname(os.path.abspath(csv_path))
        candidate=os.path.join(here,"lamborghini_logo.png")
        if os.path.exists(candidate): logo_path=candidate
    pr=_PROFILES[stampo_name]
    if preloaded_data is not None and preloaded_meta is not None:
        data, meta = preloaded_data, preloaded_meta
    else:
        data, meta = _pdf_parse_csv(csv_path)
    if filter_params is not None:
        data={k:v for k,v in data.items() if k in filter_params}
    if t_start is not None or t_end is not None:
        _ts0=t_start or 0; _ts1=t_end or float("inf")
        data={k:[(s,v,st,sp) for s,v,st,sp in pts if _ts0<=s<=_ts1] for k,pts in data.items()}
        data={k:v for k,v in data.items() if v}
    FW,FH=8.27,11.69; L,W,MID,BOT,H=0.10,0.87,0.490,0.055,0.375
    with PdfPages(output_path) as pdf:
        if pr.get("persico"):
            _persico_v8_pages(pdf, data, meta, pr, logo_path=logo_path)
        else:
            fig=plt.figure(figsize=(FW,FH),facecolor="white")
            _pdf_hdr_p1(fig,meta,pr,1,logo_path=logo_path); pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
            fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g(fig,2)
            _pdf_temp(fig.add_axes([L,MID+0.01,W,H]),data,[f"TS{i}" for i in range(1,9)],pr["temp_set_sup"],"TEMPERATURA SUPERIORE (°C)",pr)
            _pdf_temp(fig.add_axes([L,BOT,W,H]),data,[f"TI{i}" for i in range(1,9)],pr["temp_set_inf"],"TEMPERATURA INFERIORE (°C)",pr)
            pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
            fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g(fig,3)
            _skip = pr.get("skip_seconds", 0)
            _data_pf = {k:[(s,v,st,sp) for s,v,st,sp in pts if s >= _skip] for k,pts in data.items()} if _skip else data
            _pdf_posiz(fig.add_axes([L,MID+0.01,W,H]),_data_pf,[f"Z{i}" for i in range(1,5)],pr)
            _pdf_forza(fig.add_axes([L,BOT,W,H]),_data_pf,[f"F{i}" for i in range(1,5)],pr)
            pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
            fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g(fig,4)
            _vuoto_sup_bg_xmax = pr.get("vuoto_bg_xmax_sup", pr.get("vuoto_bg_xmax"))
            _vuoto_sup_bg_ymax = pr.get("vuoto_bg_ymax_sup", pr.get("vuoto_bg_ymax"))
            _vuoto_inf_bg_xmax = pr.get("vuoto_bg_xmax_inf", pr.get("vuoto_bg_xmax"))
            _vuoto_inf_bg_ymax = pr.get("vuoto_bg_ymax_inf", pr.get("vuoto_bg_ymax"))
            _sup_draw_bg = not pr.get("vuoto_no_bg_sup", False)
            _inf_draw_bg = not pr.get("vuoto_no_bg_inf", False)
            _pdf_vuoto(fig.add_axes([L,MID+0.01,W,H]),data,["VS1","VS2"],[0.0,0.0],"VUOTO SUPERIORE [bar]",["V1 Sup","V2 Sup"],pr, bg_xmax=_vuoto_sup_bg_xmax, bg_ymax=_vuoto_sup_bg_ymax, draw_bg=_sup_draw_bg)
            _pdf_vuoto(fig.add_axes([L,BOT,W,H]),data,["VI1","VI2","VI3","VI4"],[0.0,0.0,0.0,0.0],"VUOTO INFERIORE [bar]",["V1 Inf","V2 Inf","V3 Inf","V4 Inf"],pr, bg_xmax=_vuoto_inf_bg_xmax, bg_ymax=_vuoto_inf_bg_ymax, draw_bg=_inf_draw_bg)
            pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)

def detect_csv_type(headers):
    h=set(headers)
    temp_cols=sum(1 for i in range(1,9) if f"T{i}" in h or f"TS{i}" in h or f"TI{i}" in h)
    pos_cols =sum(1 for i in range(1,5) if f"P{i}" in h)
    force_ok =any(c in h for c in ("SPC","FC","F1","Forza"))
    vac_ok   =any(c in h for c in ("V1","V2","VS1","VI1","Vuoto"))
    if temp_cols>=2 and (pos_cols>=2 or force_ok or vac_ok): return "front_firewall"
    return "siemens"

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

def generate_front_firewall_pdf(rows, headers, output_path, logo_path=None):
    if not rows: raise ValueError("Nessun dato disponibile.")
    pr=_PROFILES["Front Firewall"]; grp=_group_ff_cols(headers)
    times=[r["_ts"] for r in rows if r.get("_ts")]
    if not times: raise ValueError("Nessun timestamp valido.")
    t0=times[0]; tN=times[-1]
    xs=[(r["_ts"]-t0).total_seconds() if r.get("_ts") else None for r in rows]
    xmax=max((x for x in xs if x is not None),default=pr["x_max"])
    pr2=dict(pr); pr2["x_ticks"]=[round(i*xmax/10) for i in range(11)]; pr2["x_max"]=xmax if xmax>0 else pr["x_max"]
    def gs(col): return [(xs[i],rows[i][col]) for i in range(len(rows)) if xs[i] is not None and isinstance(rows[i].get(col),float)]
    meta={"idciclo":"","partite":"Front Firewall","operatore":"","materiale":"",
          "tsraw":t0.strftime("%d/%m/%Y %H:%M:%S") if t0 else "","tsstart":t0,"tsend":tN,
          "dursec":int((tN-t0).total_seconds()) if t0 and tN else 0,"teorico_sec":pr.get("teorico_sec","")}
    FW,FH=8.27,11.69; L,W,MID,BOT,H=0.10,0.87,0.490,0.055,0.375
    with PdfPages(output_path) as pdf:
        fig=plt.figure(figsize=(FW,FH),facecolor="white")
        _pdf_hdr_p1ff(fig,meta,pr2,1,logo_path=logo_path); pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
        fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g_ff(fig,2,meta)
        ax_ts=fig.add_axes([L,MID+0.01,W,H]); ax_ti=fig.add_axes([L,BOT,W,H])
        _pdf_setup_ax(ax_ts,"Temperatura semistampo superiore [°C]","°C",pr2["temp_y"],pr2["temp_yticks"],pr2["x_ticks"],pr2["x_max"])
        ax_ts.axhline(pr2["temp_set_sup"],color=_PC["set_temp"],lw=0.8,label="SET")
        for i,col in enumerate(grp["temp_sup"][:4]):
            pts=gs(col)
            if pts: ax_ts.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_ts.get_legend_handles_labels(); ax_ts.legend(h2,l2,loc="lower right",ncol=5,**_LK)
        _pdf_setup_ax(ax_ti,"Temperatura semistampo inferiore [°C]","°C",pr2["temp_y"],pr2["temp_yticks"],pr2["x_ticks"],pr2["x_max"])
        ax_ti.axhline(pr2["temp_set_inf"],color=_PC["set_temp"],lw=0.8,label="SET")
        for i,col in enumerate(grp["temp_inf"][:4]):
            pts=gs(col)
            if pts: ax_ti.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_ti.get_legend_handles_labels(); ax_ti.legend(h2,l2,loc="lower right",ncol=5,**_LK)
        pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
        fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g_ff(fig,3,meta)
        ax_p=fig.add_axes([L,MID+0.01,W,H]); ax_f=fig.add_axes([L,BOT,W,H])
        _pdf_setup_ax(ax_p,"Posizione piano [mm]","mm",pr2["posiz_y"],pr2["posiz_yticks"],pr2["x_ticks"],pr2["x_max"],draw_bg=False)
        for i,col in enumerate(grp["pos"][:4]):
            pts=gs(col)
            if pts: ax_p.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        ax_p.axhline(0,color="#999",lw=0.4,linestyle="--",zorder=2)
        h2,l2=ax_p.get_legend_handles_labels(); ax_p.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        _pdf_setup_ax(ax_f,"Forza SPC / FC [kN]","kN",pr2["forza_y"],pr2["forza_yticks"],pr2["x_ticks"],pr2["x_max"],draw_bg=False)
        spc=pr2.get("forza_spc",6500.0); fd=pr2["forza_delta"]
        ax_f.axhline(spc,color=_PC["set_forza"],lw=0.8,label="SPC"); ax_f.axhline(spc+fd,color=_PC["lmax"],lw=1.0,label="LMax"); ax_f.axhline(spc-fd,color=_PC["lmin"],lw=1.0,label="LMin")
        for i,col in enumerate(grp["force"][:2]):
            pts=gs(col)
            if pts: ax_f.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_f.get_legend_handles_labels(); ax_f.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
        fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g_ff(fig,4,meta)
        ax_vs=fig.add_axes([L,MID+0.01,W,H]); ax_vi=fig.add_axes([L,BOT,W,H])
        _pdf_setup_ax(ax_vs,"Vuoto semistampo superiore [mbar]","mbar",pr2["vuoto_y"],pr2["vuoto_yticks"],pr2["x_ticks"],pr2["x_max"])
        for i,col in enumerate(grp["vac_s"][:2]):
            pts=gs(col)
            if pts: ax_vs.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_vs.get_legend_handles_labels(); ax_vs.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        _pdf_setup_ax(ax_vi,"Vuoto semistampo inferiore [mbar]","mbar",pr2["vuoto_y"],pr2["vuoto_yticks"],pr2["x_ticks"],pr2["x_max"])
        for i,col in enumerate(grp["vac_i"][:2]):
            pts=gs(col)
            if pts: ax_vi.plot([p[0] for p in pts],[p[1] for p in pts],color=_PC[i+1],lw=0.7,label=col)
        h2,l2=ax_vi.get_legend_handles_labels(); ax_vi.legend(h2,l2,loc="lower right",ncol=4,**_LK)
        pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)


# ================================================

MAX_CSV_BYTES = 50 * 1024 * 1024
REQUIRED_COLUMNS = {"Partita","Materiale","IdCiclo","Parametro","Timestamp","Valore","Step"}

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


class LogAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MouldGraph")
        w,h=1100,720;sw=self.winfo_screenwidth();sh=self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}");self.minsize(1100,700)
        self.configure(fg_color=COLORS["bg"])
        self.all_parsed=[];self.filtered=[]
        self.active_levels={"ERROR":True,"WARN":True,"INFO":True,"DEBUG":True}
        self.siemens_headers=[];self.siemens_rows=[]
        self._last_csv_type="siemens"
        # Live Data
        self._live_queue        = _queue.Queue(maxsize=2000)  # limite memoria
        self._live_running      = threading.Event()  # set=in corso, clear=fermo
        self._live_paused       = threading.Event()  # set=in pausa, clear=attivo
        self._live_thread       = None
        self._live_rows         = []     # {col: val, …} accumulati
        self._live_headers      = []
        self._live_col_meta     = {}
        self._live_numeric_cols = []
        self._live_plot_cols    = []
        # Allarmi live
        self._live_alarm_rules  = []     # [{col, lo, hi, label, active}]
        self._live_alarm_count  = 0      # contatore totale scatti
        self._live_alarm_active = set()  # colonne attualmente in allarme
        # interpolazione
        self._live_interp_job   = None   # after() handle del timer interpolazione
        # multi-grafico
        self._live_multi_mode   = False
        self._live_multi_ipcs   = {}     # {group_name: InteractivePlotCanvas}
        self._build_ui()

    def _build_ui(self):
        hdr=ctk.CTkFrame(self,fg_color=COLORS["surface"],corner_radius=0,height=54)
        hdr.pack(fill="x",side="top");hdr.pack_propagate(False)
        ctk.CTkLabel(hdr,text="Log",font=("Segoe UI",20,"bold"),text_color=COLORS["text"]).pack(side="left",padx=(18,0),pady=10)
        ctk.CTkLabel(hdr,text="Analyzer",font=("Segoe UI",20,"bold"),text_color=COLORS["accent"]).pack(side="left",pady=10)
        # for txt,cmd,fg in[("Analizza",self.analyze,COLORS["accent"]),("Apri file",self.open_file,COLORS["surface2"])]:
        #     ctk.CTkButton(hdr,text=txt,width=100,height=30,fg_color=fg,hover_color=COLORS["border"],
        #                    text_color=COLORS["text"],command=cmd).pack(side="right",padx=5,pady=10)
        sb=ctk.CTkFrame(self,fg_color=COLORS["surface"],corner_radius=0,height=26)
        sb.pack(fill="x",side="bottom");sb.pack_propagate(False)
        self.status_lbl=ctk.CTkLabel(sb,text="Pronto.",font=("Segoe UI",11),text_color=COLORS["text2"])
        self.status_lbl.pack(side="left",padx=12)
        self.tabs=ctk.CTkTabview(self,fg_color=COLORS["bg"],
                                  segmented_button_fg_color=COLORS["surface"],
                                  segmented_button_selected_color=COLORS["accent"],
                                  segmented_button_selected_hover_color="#5a52e0",
                                  segmented_button_unselected_color=COLORS["surface"],
                                  segmented_button_unselected_hover_color=COLORS["surface2"],
                                  text_color=COLORS["text"])
        self.tabs.pack(fill="both",expand=True,padx=10,pady=6)
        for t in["  Grafici  ", "  Dati CSV  ", "  Live Data  ", "  Come usare  "]:
            self.tabs.add(t)

        # ── lazy loading: costruisce ogni tab solo alla prima selezione ──
        self._tabs_built = set()
        self._tab_builders = {
            "  Grafici  "    : self._build_grafici_tab,
            "  Dati CSV  "   : self.build_csv_tab,
            "  Live Data  "  : self._build_live_tab,
            "  Come usare  " : self._build_help,
        }

        def _on_tab_change():
            name = self.tabs.get()
            if name not in self._tabs_built:
                self._tabs_built.add(name)
                builder = self._tab_builders.get(name)
                if builder:
                    builder(self.tabs.tab(name))

        self.tabs.configure(command=_on_tab_change)

        # costruisce subito solo il primo tab visibile
        first = "  Grafici  "
        self._tabs_built.add(first)
        self._build_grafici_tab(self.tabs.tab(first))

    # -- TAB ANALISI --
    def _build_analisi(self,parent):
        paned=ctk.CTkFrame(parent,fg_color=COLORS["bg"])
        paned.pack(fill="both",expand=True,pady=4)
        lw=ctk.CTkFrame(paned,fg_color=COLORS["bg"],width=375)
        lw.pack(side="left",fill="y",padx=(0,8));lw.pack_propagate(False)
        left=ctk.CTkScrollableFrame(lw,fg_color=COLORS["bg"],scrollbar_button_color=COLORS["border"],
                                     scrollbar_button_hover_color=COLORS["accent"])
        left.pack(fill="both",expand=True)
        self._sec(left,"Input Log")
        self.txt_input=ctk.CTkTextbox(left,height=130,font=("Courier New",10),
                                       fg_color=COLORS["surface2"],text_color=COLORS["text"],
                                       border_color=COLORS["border"],border_width=1)
        self.txt_input.pack(fill="x",pady=(0,8))
        self.txt_input.insert("0.0","Incolla log qui oppure usa Apri file / Demo...")
        self._sec(left,"Filtri")
        fcard=ctk.CTkFrame(left,fg_color=COLORS["surface"],corner_radius=8)
        fcard.pack(fill="x",pady=(0,8))
        lf=ctk.CTkFrame(fcard,fg_color="transparent");lf.pack(fill="x",padx=10,pady=(10,4))
        ctk.CTkLabel(lf,text="LIVELLO",font=("Segoe UI",10,"bold"),text_color=COLORS["text2"]).pack(anchor="w")
        btns=ctk.CTkFrame(lf,fg_color="transparent");btns.pack(anchor="w")
        self.lvl_btns={}
        for lvl in["ERROR","WARN","INFO","DEBUG"]:
            b=ctk.CTkButton(btns,text=lvl,width=66,height=26,fg_color=LEVEL_BG[lvl],
                             hover_color=LEVEL_HOVER[lvl],text_color=LEVEL_COLORS[lvl],
                             font=("Segoe UI",11,"bold"),command=lambda l=lvl:self.toggle_level(l))
            b.pack(side="left",padx=(0,4),pady=4);self.lvl_btns[lvl]=b
        kf=ctk.CTkFrame(fcard,fg_color="transparent");kf.pack(fill="x",padx=10,pady=4)
        ctk.CTkLabel(kf,text="KEYWORD",font=("Segoe UI",10,"bold"),text_color=COLORS["text2"]).pack(anchor="w")
        self.entry_kw=ctk.CTkEntry(kf,placeholder_text="es. timeout, alarm...",
                                    fg_color=COLORS["surface2"],border_color=COLORS["border"],
                                    text_color=COLORS["text"],height=30)
        self.entry_kw.pack(fill="x")
        self.entry_kw.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        tf=ctk.CTkFrame(fcard,fg_color="transparent");tf.pack(fill="x",padx=10,pady=(4,4))
        ctk.CTkLabel(tf,text="INTERVALLO",font=("Segoe UI",10,"bold"),text_color=COLORS["text2"]).pack(anchor="w")
        tr=ctk.CTkFrame(tf,fg_color="transparent");tr.pack(fill="x")
        self.entry_from=ctk.CTkEntry(tr,placeholder_text="Dal (YYYY-MM-DD HH:MM)",
                                      fg_color=COLORS["surface2"],border_color=COLORS["border"],
                                      text_color=COLORS["text"],height=28)
        self.entry_from.pack(side="left",fill="x",expand=True,padx=(0,4))
        self.entry_from.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        self.entry_to=ctk.CTkEntry(tr,placeholder_text="Al...",
                                    fg_color=COLORS["surface2"],border_color=COLORS["border"],
                                    text_color=COLORS["text"],height=28)
        self.entry_to.pack(side="left",fill="x",expand=True)
        self.entry_to.bind("<KeyRelease>", lambda e: self._debounced_apply_filters())
        ctk.CTkButton(fcard,text="Reset filtri",width=110,height=26,fg_color=COLORS["surface2"],
                       hover_color=COLORS["border"],text_color=COLORS["text2"],
                       command=self.reset_filters).pack(anchor="e",padx=10,pady=(4,10))
        self._sec(left,"Statistiche")
        srow=ctk.CTkFrame(left,fg_color="transparent");srow.pack(fill="x",pady=(0,8))
        self.stat_labels={}
        for key,color,label in[("total",COLORS["accent2"],"Totale"),("ERROR",COLORS["error"],"Errori"),
                                 ("WARN",COLORS["warn"],"Warning"),("INFO",COLORS["info"],"Info")]:
            sc=ctk.CTkFrame(srow,fg_color=COLORS["surface"],corner_radius=8)
            sc.pack(side="left",expand=True,fill="x",padx=2)
            lv=ctk.CTkLabel(sc,text="0",font=("Segoe UI",22,"bold"),text_color=color)
            lv.pack(pady=(8,0))
            ctk.CTkLabel(sc,text=label,font=("Segoe UI",10),text_color=COLORS["text2"]).pack(pady=(0,8))
            self.stat_labels[key]=lv
        self._sec(left,"Pattern / Firme (Top 10)")
        pf=ctk.CTkFrame(left,fg_color=COLORS["surface"],corner_radius=8)
        pf.pack(fill="x",pady=(0,8))
        self.patterns_box=ctk.CTkTextbox(pf,height=280,font=("Courier New",10),
                                          fg_color=COLORS["surface"],text_color=COLORS["text2"],
                                          border_width=0,wrap="word")
        self.patterns_box.pack(fill="x",padx=6,pady=6)
        right=ctk.CTkFrame(paned,fg_color=COLORS["bg"])
        right.pack(side="left",fill="both",expand=True)
        th=ctk.CTkFrame(right,fg_color="transparent");th.pack(fill="x",pady=(0,6))
        self._sec_inline(th,"Log Dettaglio")
        self.lbl_count=ctk.CTkLabel(th,text="",font=("Segoe UI",12),text_color=COLORS["accent"])
        self.lbl_count.pack(side="left",padx=8)
        er=ctk.CTkFrame(th,fg_color="transparent");er.pack(side="right")
        ctk.CTkButton(er,text="Esporta JSON",width=110,height=28,fg_color=COLORS["surface2"],
                       hover_color=COLORS["border"],text_color=COLORS["text"],command=self.export_json).pack(side="left",padx=4)
        ctk.CTkButton(er,text="Esporta CSV",width=110,height=28,fg_color=COLORS["surface2"],
                       hover_color=COLORS["border"],text_color=COLORS["text"],command=self.export_csv).pack(side="left",padx=4)
        tf2=ctk.CTkFrame(right,fg_color=COLORS["surface"],corner_radius=8)
        tf2.pack(fill="both",expand=True)
        ch2=ctk.CTkFrame(tf2,fg_color=COLORS["surface2"],corner_radius=0,height=28)
        ch2.pack(fill="x");ch2.pack_propagate(False)
        for txt,ww in[("#",40),("Timestamp",160),("Liv.",60),("Component",110),("Messaggio",500)]:
            ctk.CTkLabel(ch2,text=txt,font=("Segoe UI",10,"bold"),text_color=COLORS["text2"],width=ww,anchor="w").pack(side="left",padx=4)
        self.tbl=tk.Text(tf2,bg=COLORS["surface"],fg=COLORS["text"],font=("Courier New",11),
                          relief="flat",bd=0,selectbackground="#3a3580",highlightthickness=0,
                          wrap="none",state="disabled")
        vsb=ctk.CTkScrollbar(tf2,command=self.tbl.yview)
        hsb=ctk.CTkScrollbar(tf2,orientation="horizontal",command=self.tbl.xview)
        self.tbl.configure(yscrollcommand=vsb.set,xscrollcommand=hsb.set)
        vsb.pack(side="right",fill="y");hsb.pack(side="bottom",fill="x")
        self.tbl.pack(fill="both",expand=True)
        for tag,fgc,bgc in[("ERROR",COLORS["error"],None),("WARN",COLORS["warn"],None),
                             ("INFO",COLORS["info"],None),("DEBUG",COLORS["debug"],None),
                             ("hl",None,"#4a3a00"),("dim",COLORS["text2"],None),
                             ("comp",COLORS["accent2"],None),("roweven",None,"#1e2133"),
                             ("rowodd",None,COLORS["surface"])]:
            kw={};
            if fgc:kw["foreground"]=fgc
            if bgc:kw["background"]=bgc
            self.tbl.tag_configure(tag,**kw)

    # -- TAB TIMELINE --
    def _build_timeline_tab(self,parent):
        self._sec(parent,"Timeline eventi")
        ctk.CTkLabel(parent,text="Distribuzione eventi nel tempo - barre impilate per livello",
                     font=("Segoe UI",11),text_color=COLORS["text2"]).pack(anchor="w",padx=4,pady=(0,8))
        fc=ctk.CTkFrame(parent,fg_color=COLORS["surface"],corner_radius=8)
        fc.pack(fill="both",expand=True)
        self.timeline_canvas=TimelineCanvas(fc)
        self.timeline_canvas.pack(fill="both",expand=True,padx=8,pady=8)
        self.timeline_canvas.bind("<Configure>",lambda e:self.timeline_canvas.redraw())
        self._sec(parent,"Riepilogo per componente")
        cf=ctk.CTkFrame(parent,fg_color=COLORS["surface"],corner_radius=8)
        cf.pack(fill="both",expand=True,pady=(8,0))
        self.comp_box=ctk.CTkTextbox(cf,font=("Courier New",11),fg_color=COLORS["surface"],
                                      text_color=COLORS["text"],border_width=0)
        self.comp_box.pack(fill="both",expand=True,padx=8,pady=8)

    # -- TAB AI --
    def _build_ai_tab(self,parent):
        self._sec(parent,"AI Insights - Analisi automatica del log")
        ctk.CTkLabel(parent,text="Suggerimenti e rilevamento anomalie basati sul contenuto del log",
                     font=("Segoe UI",11),text_color=COLORS["text2"]).pack(anchor="w",padx=4,pady=(0,10))
        scroll=ctk.CTkScrollableFrame(parent,fg_color=COLORS["bg"],corner_radius=0)
        scroll.pack(fill="both",expand=True)
        self.ai_container=scroll

    # -- TAB DATI SIEMENS --
    def _build_siemens_tab(self,parent):
        # toolbar
        toolbar=ctk.CTkFrame(parent,fg_color=COLORS["surface"],corner_radius=8,height=44)
        toolbar.pack(fill="x",pady=(0,8));toolbar.pack_propagate(False)
        ctk.CTkButton(toolbar,text="Apri CSV Siemens",width=150,height=30,
                       fg_color=COLORS["accent"],hover_color="#5a52e0",text_color=COLORS["text"],
                       command=self.open_siemens_csv).pack(side="left",padx=10,pady=7)
        self.siemens_info_lbl=ctk.CTkLabel(toolbar,text="Nessun file caricato",
                                            font=("Segoe UI",11),text_color=COLORS["text2"])
        self.siemens_info_lbl.pack(side="left",padx=10)
        ctk.CTkButton(toolbar,text="Genera PDF Grafico",width=150,height=30,
                       fg_color="#7c3aed",hover_color="#6d28d9",text_color=COLORS["text"],
                       command=self.export_pdf_grafico).pack(side="right",padx=6,pady=7)
        ctk.CTkButton(toolbar,text="Esporta report",width=120,height=30,
                       fg_color=COLORS["surface2"],hover_color=COLORS["border"],text_color=COLORS["text"],
                       command=self.export_siemens_report).pack(side="right",padx=10,pady=7)

        # selector colonne
        sel_frame=ctk.CTkFrame(parent,fg_color=COLORS["surface"],corner_radius=8,height=40)
        sel_frame.pack(fill="x",pady=(0,8));sel_frame.pack_propagate(False)
        ctk.CTkLabel(sel_frame,text="Visualizza:",font=("Segoe UI",11),text_color=COLORS["text2"]).pack(side="left",padx=10,pady=8)
        self.siemens_col_var=ctk.StringVar(value="Temp_Vasca_01")
        self.siemens_col_menu=ctk.CTkOptionMenu(sel_frame,variable=self.siemens_col_var,
                                                  values=["-"],width=180,
                                                  fg_color=COLORS["surface2"],
                                                  button_color=COLORS["accent"],
                                                  text_color=COLORS["text"],
                                                  command=self._on_col_change)
        self.siemens_col_menu.pack(side="left",padx=4,pady=8)
        ctk.CTkLabel(sel_frame,text="vs",font=("Segoe UI",11),text_color=COLORS["text2"]).pack(side="left",padx=4)
        self.siemens_col2_var=ctk.StringVar(value="-")
        self.siemens_col2_menu=ctk.CTkOptionMenu(sel_frame,variable=self.siemens_col2_var,
                                                   values=["-"],width=180,
                                                   fg_color=COLORS["surface2"],
                                                   button_color=COLORS["accent"],
                                                   text_color=COLORS["text"],
                                                   command=self._on_col_change)
        self.siemens_col2_menu.pack(side="left",padx=4,pady=8)

        # charts
        charts_frame=ctk.CTkFrame(parent,fg_color=COLORS["bg"])
        charts_frame.pack(fill="both",expand=True)

        # left: grafico linee + pompa
        chart_left=ctk.CTkFrame(charts_frame,fg_color=COLORS["bg"])
        chart_left.pack(side="left",fill="both",expand=True,padx=(0,6))
        self._sec(chart_left,"Grafico dati")
        lc_frame=ctk.CTkFrame(chart_left,fg_color=COLORS["surface"],corner_radius=8)
        lc_frame.pack(fill="both",expand=True)
        self.line_chart=LineChart(lc_frame,height=220)
        self.line_chart.pack(fill="both",expand=True,padx=6,pady=6)
        self.line_chart.bind("<Configure>",lambda e:self.line_chart.redraw())
        self._sec(chart_left,"Stato Pompa")
        pc_frame=ctk.CTkFrame(chart_left,fg_color=COLORS["surface"],corner_radius=8)
        pc_frame.pack(fill="x")
        self.pump_canvas=PumpCanvas(pc_frame,height=70)
        self.pump_canvas.pack(fill="x",padx=6,pady=6)
        self.pump_canvas.bind("<Configure>",lambda e:self.pump_canvas.redraw())

        # right: anomalie + stats + tabella
        chart_right=ctk.CTkFrame(charts_frame,fg_color=COLORS["bg"],width=380)
        chart_right.pack(side="left",fill="y")
        chart_right.pack_propagate(False)
        right_scroll=ctk.CTkScrollableFrame(chart_right,fg_color=COLORS["bg"],
                                             scrollbar_button_color=COLORS["border"],
                                             scrollbar_button_hover_color=COLORS["accent"])
        right_scroll.pack(fill="both",expand=True)

        self._sec(right_scroll,"Anomalie rilevate")
        self.anomaly_container=ctk.CTkFrame(right_scroll,fg_color=COLORS["bg"])
        self.anomaly_container.pack(fill="x",pady=(0,8))

        self._sec(right_scroll,"Statistiche colonne")
        stats_frame=ctk.CTkFrame(right_scroll,fg_color=COLORS["surface"],corner_radius=8)
        stats_frame.pack(fill="x",pady=(0,8))
        self.stats_box=ctk.CTkTextbox(stats_frame,height=160,font=("Courier New",10),
                                       fg_color=COLORS["surface"],text_color=COLORS["text"],
                                       border_width=0)
        self.stats_box.pack(fill="x",padx=6,pady=6)

        self._sec(right_scroll,"Dati grezzi")
        raw_frame=ctk.CTkFrame(right_scroll,fg_color=COLORS["surface"],corner_radius=8)
        raw_frame.pack(fill="x",pady=(0,8))
        self.raw_box=ctk.CTkTextbox(raw_frame,height=200,font=("Courier New",9),
                                     fg_color=COLORS["surface"],text_color=COLORS["text2"],
                                     border_width=0,wrap="none")
        self.raw_box.pack(fill="x",padx=6,pady=6)

    # -- TAB HELP --

    # -- EXPORT PDF GRAFICO (v3.1) ------------------------------

    def export_pdf_grafico(self):
        if not self.siemens_rows:
            messagebox.showwarning("Attenzione","Nessun dato Siemens caricato."); return
        csv_t = detect_csv_type(self.siemens_headers)
        if csv_t != "front_firewall":
            messagebox.showwarning("Attenzione",
                "Funzione disponibile solo per dati Front Firewall (Persico).\n"
                "Le colonne rilevate non corrispondono al profilo."); return
        import os
        base_name = os.path.splitext(os.path.basename(self.siemens_csv_path))[0] if hasattr(self, 'siemens_csv_path') and self.siemens_csv_path else "Grafico-Front_Firewall"
        path = filedialog.asksaveasfilename(defaultextension=".pdf",
               initialfile=f"{base_name}.pdf", filetypes=[("PDF","*.pdf")])
        if not path: return
        self.set_status("Generazione PDF in corso...")
        def _run():
            try:
                generate_front_firewall_pdf(self.siemens_rows, self.siemens_headers, path)
                self.after(0, lambda: self.set_status(f"PDF salvato: {os.path.basename(path)}"))
                self.after(0, lambda: messagebox.showinfo("Completato", f"PDF salvato:\n{path}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore PDF", str(e)))
                self.after(0, lambda: self.set_status("Errore generazione PDF"))
        threading.Thread(target=_run, daemon=True).start()

    # -- TAB GRAFICI LAMBORGHINI --------------------------------

    def _build_grafici_tab(self, parent):
        self._grafici_csv_path = None; self._grafici_logo_path = None; self._grafici_native_paths = {}; self._grafici_merged_data = None; self._grafici_merged_meta = None
        self._grafici_data = None; self._grafici_meta = None; self._grafici_note_box = None
        self._grafici_param_vars = {}; self._grafici_canvases = {}
        self._grafici_preview_job = None; self._grafici_groups = []
        # -- Top toolbar --
        top = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        top.pack(fill="x", side="top", padx=6, pady=4)
        row1 = ctk.CTkFrame(top, fg_color=COLORS["surface"], corner_radius=8)
        row1.pack(fill="x", pady=(0,4))
        ctk.CTkLabel(row1, text="Pressa", font=("Segoe UI",11,"bold"),
                     text_color=COLORS["text2"]).pack(side="left", padx=14, pady=10)
        self._grafici_pressa_var = ctk.StringVar(value=list(_PRESSA_STAMPI.keys())[0])
        def _on_pressa_change(val):
            stampi = _PRESSA_STAMPI.get(val, [])
            self._grafici_stampo_var.set(stampi[0] if stampi else "")
            self._grafici_stampo_menu.configure(values=stampi if stampi else [""])
        ctk.CTkOptionMenu(row1, variable=self._grafici_pressa_var,
                          values=list(_PRESSA_STAMPI.keys()), width=160,
                          fg_color=COLORS["surface2"], button_color=COLORS["accent"],
                          text_color=COLORS["text"],
                          command=_on_pressa_change).pack(side="left", padx=8, pady=10)
        ctk.CTkLabel(row1, text="Stampo", font=("Segoe UI",11,"bold"),
                     text_color=COLORS["text2"]).pack(side="left", padx=(12,0), pady=10)
        self._grafici_stampo_var = ctk.StringVar(value=_PRESSA_STAMPI[list(_PRESSA_STAMPI.keys())[0]][0])
        self._grafici_stampo_menu = ctk.CTkOptionMenu(
            row1, variable=self._grafici_stampo_var,
            values=_PRESSA_STAMPI[list(_PRESSA_STAMPI.keys())[0]], width=180,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"], state="disabled")
        self._grafici_stampo_menu.pack(side="left", padx=8, pady=10)
        row2 = ctk.CTkFrame(top, fg_color=COLORS["surface"], corner_radius=8)
        row2.pack(fill="x", pady=(0,4))
        ctk.CTkButton(row2, text="Apri CSV", width=100, height=28,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"],
                      command=self._grafici_open_csv).pack(side="left", padx=10, pady=8)
        self._grafici_csv_lbl = ctk.CTkLabel(row2, text="Nessun file selezionato",
                                              font=("Segoe UI",11), text_color=COLORS["text2"])
        self._grafici_csv_lbl.pack(side="left", padx=8)
        self._grafici_native_btn = ctk.CTkButton(row2, text="+ File nativi", width=110, height=28,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text"], state="disabled",
                      command=self._grafici_open_native)
        self._grafici_native_btn.pack(side="left", padx=4, pady=8)
        self._grafici_native_lbl = ctk.CTkLabel(row2, text="",
                                                 font=("Segoe UI",10), text_color=COLORS["text2"])
        self._grafici_native_lbl.pack(side="left", padx=4)
        ctk.CTkButton(row2, text="Logo (opzionale)", width=130, height=28,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text"],
                      command=self._grafici_open_logo).pack(side="right", padx=10, pady=8)
        self._grafici_logo_lbl = ctk.CTkLabel(row2, text="auto",
                                               font=("Segoe UI",10), text_color=COLORS["text2"])
        self._grafici_logo_lbl.pack(side="right", padx=4)
        row3 = ctk.CTkFrame(top, fg_color="transparent")
        row3.pack(fill="x", pady=(0,2))
        self._grafici_gen_btn = ctk.CTkButton(row3, text="Genera PDF", width=140, height=34,
                                               fg_color=COLORS["accent"], hover_color="#5a52e0",
                                               font=("Segoe UI",12,"bold"), text_color=COLORS["text"],
                                               state="disabled", command=self._grafici_generate)
        self._grafici_gen_btn.pack(side="left", padx=2)
        self._grafici_status = ctk.CTkLabel(row3, text="", font=("Segoe UI",11),
                                             text_color=COLORS["text2"])
        self._grafici_status.pack(side="left", padx=12)
        # -- Main split: filter (left) + chart preview (right) --
        self._grafici_main = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        self._grafici_filter_scroll = ctk.CTkScrollableFrame(
            self._grafici_main, fg_color=COLORS["surface"], width=260, corner_radius=0)
        self._grafici_filter_scroll.pack(side="left", fill="y", padx=(0,4))
        self._grafici_chart_scroll = ctk.CTkScrollableFrame(
            self._grafici_main, fg_color=COLORS["bg"])
        self._grafici_chart_scroll.pack(side="left", fill="both", expand=True)
        # -- Note box persistente: creato UNA VOLTA qui, mai distrutto/ricreato.
        # _grafici_build_preview distrugge solo i figli del _grafici_params_container
        # (i checkbox), lasciando intatto questo widget. Evita "invalid command name"
        # che si verificava quando il textbox veniva ricreato e il vecchio riferimento
        # veniva ancora usato dai binding KeyRelease. --
        self._grafici_params_container = ctk.CTkFrame(
            self._grafici_filter_scroll, fg_color="transparent")
        self._grafici_params_container.pack(fill="x")
        ctk.CTkLabel(self._grafici_filter_scroll, text="NOTE OPERATIVE",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=8, pady=(16, 2))
        self._grafici_note_frame = ctk.CTkFrame(
            self._grafici_filter_scroll, fg_color=COLORS["surface2"], corner_radius=6)
        self._grafici_note_frame.pack(fill="x", padx=4, pady=(0, 8))
        self._grafici_note_box = ctk.CTkTextbox(
            self._grafici_note_frame, height=80, font=("Segoe UI", 10),
            fg_color=COLORS["surface2"], text_color=COLORS["text"],
            border_width=0, wrap="word")
        self._grafici_note_box.pack(fill="x", padx=4, pady=4)
        self._grafici_note_box.bind(
            "<KeyRelease>", lambda e: self._grafici_save_note())

    def _grafici_get_groups(self, data_keys):
        all_keys = set(data_keys)
        groups = []
        def _safe_int(s):
            try: return int(s)
            except Exception: return -1
        ts = sorted([k for k in all_keys if
                     (k.startswith("TS") and k[2:].isdigit()) or
                     (k.startswith("T") and not k.startswith("TI") and
                      k[1:].isdigit() and 1 <= _safe_int(k[1:]) <= 4)])
        if ts: groups.append(("temp_sup", "Temperatura Superiore", "[T]", ts))
        ti = sorted([k for k in all_keys if k.startswith("TI") and k[2:].isdigit()])
        if not ti:
            ti = sorted([k for k in all_keys if k.startswith("T") and
                         k[1:].isdigit() and 4 < _safe_int(k[1:]) <= 8])
        if ti: groups.append(("temp_inf", "Temperatura Inferiore", "[T]", ti))
        pos = sorted([k for k in all_keys if
                      (k.startswith("P") and k[1:].isdigit()) or
                      (k.startswith("Z") and k[1:].isdigit())])
        if pos: groups.append(("posiz", "Posizione Piano", "[P]", pos))
        # Forza: se F1÷F4 presenti (nativo caricato) -> due gruppi separati.
        # Altrimenti gruppo unico con FC/SPC/Forza.
        f_sensors = [k for k in all_keys if k in ("F1","F2","F3","F4")]
        f_combined = [k for k in all_keys if k in ("FC","SPC","Forza")]
        if f_sensors:
            groups.append(("forza_sensori", "Forza Sensori", "*", sorted(f_sensors)))
            if f_combined:
                groups.append(("forza", "Forza", "*", sorted(f_combined)))
        else:
            force = sorted(f_combined)
            if force: groups.append(("forza", "Forza", "*", force))
        vs = sorted([k for k in all_keys if k in ("VS1","VS2","V1","V2")])
        if vs: groups.append(("vuoto_sup", "Vuoto Superiore", "[V]", vs))
        vi = sorted([k for k in all_keys if k in ("VI1","VI2","VI3","VI4","V3","V4")])
        if vi: groups.append(("vuoto_inf", "Vuoto Inferiore", "[V]", vi))
        return groups

    def _grafici_build_preview(self, data, meta):
        if not self._grafici_main.winfo_ismapped():
            self._grafici_main.pack(fill="both", expand=True, padx=6, pady=(0,4))
        self._grafici_groups = self._grafici_get_groups(list(data.keys()))
        # Distrugge solo i checkbox — il note box è persistente e non viene toccato
        for w in self._grafici_params_container.winfo_children(): w.destroy()
        self._grafici_param_vars = {}
        ctk.CTkLabel(self._grafici_params_container, text="FILTRO PARAMETRI",
                     font=("Segoe UI",11,"bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=8, pady=(8,4))
        for key, title, emoji, params in self._grafici_groups:
            hdr = ctk.CTkFrame(self._grafici_params_container,
                               fg_color=COLORS["surface2"], corner_radius=6)
            hdr.pack(fill="x", padx=4, pady=(8,2))
            ctk.CTkLabel(hdr, text=f"{emoji}  {title}",
                         font=("Segoe UI",10,"bold"),
                         text_color=COLORS["text"]).pack(side="left", padx=8, pady=6)
            for param in params:
                color = _SERIES_COLORS.get(param, "#6c63ff")
                row = ctk.CTkFrame(self._grafici_params_container, fg_color="transparent")
                row.pack(fill="x", padx=6, pady=2)
                ctk.CTkFrame(row, width=11, height=11, fg_color=color,
                             corner_radius=2).pack(side="left", padx=(6,5))
                var = tk.BooleanVar(value=True)
                self._grafici_param_vars[param] = var
                ctk.CTkCheckBox(row, text=param, variable=var,
                                fg_color=color, hover_color=color,
                                checkmark_color="#fff",
                                font=("Segoe UI",10,"bold"),
                                text_color=COLORS["text"],
                                command=self._grafici_schedule_update
                                ).pack(side="left")
        # -- Chart canvases --
        for w in self._grafici_chart_scroll.winfo_children(): w.destroy()
        self._grafici_canvases = {}
        for key, title, emoji, params in self._grafici_groups:
            frame = ctk.CTkFrame(self._grafici_chart_scroll,
                                 fg_color=COLORS["surface"], corner_radius=8)
            frame.pack(fill="x", pady=4, padx=2)
            title_bar = ctk.CTkFrame(frame, fg_color=COLORS["surface2"], corner_radius=0)
            title_bar.pack(fill="x")
            ctk.CTkLabel(title_bar, text=f"{emoji}  {title}",
                         font=("Segoe UI",11,"bold"),
                         text_color=COLORS["text"]).pack(side="left", padx=12, pady=7)
            _k = key
            ctk.CTkButton(title_bar, text="[ ]", width=36, height=24,
                          fg_color="transparent", hover_color=COLORS["border"],
                          text_color=COLORS["text2"], font=("Segoe UI",10),
                          command=lambda k=_k: self._grafici_open_fullscreen(k)
                          ).pack(side="right", padx=6)
            fig = plt.Figure(figsize=(10, 2.2), facecolor="#22263a", dpi=80)
            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.get_tk_widget().configure(bg="#22263a", highlightthickness=0)
            canvas.get_tk_widget().pack(fill="x", padx=2, pady=2)
            self._grafici_canvases[key] = (fig, canvas, params)
        self._grafici_update_preview()

    def _grafici_schedule_update(self):
        if self._grafici_preview_job:
            self.after_cancel(self._grafici_preview_job)
        self._grafici_preview_job = self.after(120, self._grafici_update_preview)

    def _grafici_update_preview(self):
        if not self._grafici_data: return
        selected = {p for p, v in self._grafici_param_vars.items() if v.get()}
        _preview_data = self._grafici_merged_data or self._grafici_data
        for key, (fig, canvas, params) in self._grafici_canvases.items():
            fig.clear()
            ax = fig.add_subplot(111)
            ax.set_facecolor("#22263a")
            fig.patch.set_facecolor("#22263a")
            has_data = False
            for param in params:
                if param not in selected: continue
                pts = _preview_data.get(param, [])
                if not pts: continue
                ys = [p[1] for p in pts]
                # Salta serie con tutti i valori a zero (sensori non collegati)
                if all(abs(v) < 0.001 for v in ys): continue
                xs = [p[0] for p in pts]
                ax.plot(xs, ys, color=_SERIES_COLORS.get(param, "#6c63ff"),
                        lw=1.0, label=param)
                has_data = True
            if not has_data:
                ax.text(0.5, 0.5, "Nessun parametro selezionato",
                        transform=ax.transAxes, ha="center", va="center",
                        color=COLORS["text2"], fontsize=9)
            ax.tick_params(colors="#8892b0", labelsize=7, length=2)
            for sp in ax.spines.values():
                sp.set_color("#2e3350"); sp.set_linewidth(0.5)
            ax.grid(True, color="#2e3350", lw=0.5, linestyle="--")
            ax.set_xlabel("Sec", color="#8892b0", fontsize=7, labelpad=2)
            if has_data:
                ax.legend(loc="upper right", fontsize=7, framealpha=0.8,
                          facecolor="#1a1d27", edgecolor="#2e3350",
                          labelcolor="#e8eaf6", handlelength=1.5)
            fig.subplots_adjust(left=0.05, right=0.98, top=0.90, bottom=0.22)
            canvas.draw()

    def _grafici_open_fullscreen(self, key):
        """Apre il grafico in fullscreen con zoom, pan e modalità hover interattive (blit)."""
        if key not in self._grafici_canvases: return
        _, _, params = self._grafici_canvases[key]
        selected = {p for p, v in self._grafici_param_vars.items() if v.get()}
        data = self._grafici_merged_data or self._grafici_data
        if not data: return

        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        import matplotlib.pyplot as _plt

        win = tk.Toplevel(self)
        win.title(key)
        win.configure(bg="#22263a")
        win.state("zoomed")

        # -- Barra modalità hover --
        mode_bar = tk.Frame(win, bg="#1a1d27", height=36)
        mode_bar.pack(side="top", fill="x")
        mode_bar.pack_propagate(False)
        tk.Label(mode_bar, text="Hover:", bg="#1a1d27", fg="#8892b0",
                 font=("Segoe UI", 10)).pack(side="left", padx=(12, 6))
        _hover_mode = tk.StringVar(value="Nessuno")
        _MODE_COLORS = {"active_bg": "#6c63ff", "active_fg": "#ffffff",
                        "idle_bg": "#22263a", "idle_fg": "#8892b0"}
        _mode_btns = {}
        def _set_mode(m):
            _hover_mode.set(m)
            for _m, _b in _mode_btns.items():
                if _m == m:
                    _b.configure(bg=_MODE_COLORS["active_bg"], fg=_MODE_COLORS["active_fg"])
                else:
                    _b.configure(bg=_MODE_COLORS["idle_bg"], fg=_MODE_COLORS["idle_fg"])
            _clear_overlay()
        for lbl in ["Nessuno", "Tooltip", "Crosshair", "Snap", "Completo"]:
            _l = lbl
            b = tk.Button(mode_bar, text=lbl, bg=_MODE_COLORS["idle_bg"],
                          fg=_MODE_COLORS["idle_fg"], relief="flat",
                          font=("Segoe UI", 10), padx=10, pady=4,
                          activebackground="#5a52e0", activeforeground="#fff",
                          command=lambda m=_l: _set_mode(m))
            b.pack(side="left", padx=3, pady=4)
            _mode_btns[lbl] = b
        _mode_btns["Nessuno"].configure(bg=_MODE_COLORS["active_bg"], fg=_MODE_COLORS["active_fg"])

        # -- Figura e assi --
        fig = _plt.Figure(figsize=(16, 6), facecolor="#22263a")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#22263a")
        for sp in ax.spines.values(): sp.set_color("#2e3350"); sp.set_linewidth(0.6)
        ax.tick_params(colors="#8892b0", labelsize=9, length=3)
        ax.grid(True, color="#2e3350", lw=0.5, linestyle="--")
        ax.set_xlabel("Sec", color="#8892b0", fontsize=9, labelpad=4)

        # Raccoglie serie: {param: (xs_array, ys_array, color)}
        _series = {}
        has_data = False
        for param in params:
            if param not in selected: continue
            pts = data.get(param, [])
            if not pts: continue
            ys = [p[1] for p in pts]
            if all(abs(v) < 0.001 for v in ys): continue
            xs = [p[0] for p in pts]
            color = _SERIES_COLORS.get(param, "#6c63ff")
            ax.plot(xs, ys, color=color, lw=1.2, label=param)
            _series[param] = (np.array(xs), np.array(ys), color)
            has_data = True
        if has_data:
            ax.legend(loc="upper right", fontsize=9, framealpha=0.8,
                      facecolor="#1a1d27", edgecolor="#2e3350",
                      labelcolor="#e8eaf6", handlelength=2)
        fig.subplots_adjust(left=0.06, right=0.98, top=0.93, bottom=0.10)

        # -- Canvas e toolbar matplotlib (stile dark) --
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().configure(bg="#22263a", highlightthickness=0)
        toolbar_frame = tk.Frame(win, bg="#2a2d3e")
        toolbar_frame.pack(side="bottom", fill="x")
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.config(background="#2a2d3e")
        def _style_toolbar(widget):
            try:
                cls = widget.winfo_class()
                if cls in ("Button", "Label"):
                    widget.config(bg="#2a2d3e", fg="#e8eaf6",
                                  activebackground="#4a4f72", activeforeground="#ffffff",
                                  relief="flat", borderwidth=0)
                elif cls in ("Frame", "Checkbutton"):
                    widget.config(bg="#2a2d3e")
            except Exception: pass
            for child in widget.winfo_children():
                _style_toolbar(child)
        toolbar.update()
        _style_toolbar(toolbar)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        canvas.draw()

        # -- Background statico per blit --
        _bg = [None]
        def _save_bg():
            _bg[0] = canvas.copy_from_bbox(fig.bbox)
        win.after(100, _save_bg)

        # -- Artisti overlay (animated=True → esclusi dal draw statico) --
        _vline, = ax.plot([], [], color="#ffffff", lw=0.7, linestyle="--", alpha=0.5, animated=True)
        _hline, = ax.plot([], [], color="#ffffff", lw=0.7, linestyle="--", alpha=0.5, animated=True)
        _snap_dot, = ax.plot([], [], "o", ms=7, color="#ffffff", zorder=10, animated=True)
        _tooltip = ax.annotate("", xy=(0, 0), xytext=(15, 15),
                               textcoords="offset points",
                               bbox=dict(boxstyle="round,pad=0.4", fc="#1a1d27",
                                         ec="#6c63ff", lw=1.2, alpha=0.92),
                               fontsize=8.5, color="#e8eaf6", animated=True,
                               annotation_clip=False)
        _tooltip.set_visible(False)

        def _place_tooltip(bx, by):
            """Ribalta l'offset del tooltip vicino ai bordi degli assi."""
            xl = ax.get_xlim(); yl = ax.get_ylim()
            xfrac = (bx - xl[0]) / (xl[1] - xl[0]) if xl[1] != xl[0] else 0.5
            yfrac = (by - yl[0]) / (yl[1] - yl[0]) if yl[1] != yl[0] else 0.5
            ox = -120 if xfrac > 0.75 else 15
            oy = -60  if yfrac > 0.70 else 15
            _tooltip.xyann = (ox, oy)
        _info_box = ax.text(0.01, 0.98, "", transform=ax.transAxes,
                            va="top", ha="left", fontsize=8.5, color="#e8eaf6",
                            bbox=dict(boxstyle="round,pad=0.5", fc="#1a1d27",
                                      ec="#2e3350", lw=1.0, alpha=0.90),
                            animated=True)
        _info_box.set_visible(False)

        def _clear_overlay():
            _vline.set_data([], [])
            _hline.set_data([], [])
            _snap_dot.set_data([], [])
            _tooltip.set_visible(False)
            _info_box.set_visible(False)
            if _bg[0] is not None:
                canvas.restore_region(_bg[0])
                canvas.blit(fig.bbox)

        def _interp_y(xs_arr, ys_arr, x):
            if len(xs_arr) == 0: return None
            idx = np.searchsorted(xs_arr, x)
            if idx == 0: return float(ys_arr[0])
            if idx >= len(xs_arr): return float(ys_arr[-1])
            x0, x1 = xs_arr[idx-1], xs_arr[idx]
            y0, y1 = ys_arr[idx-1], ys_arr[idx]
            if x1 == x0: return float(y0)
            return float(y0 + (y1 - y0) * (x - x0) / (x1 - x0))

        def _nearest_point(xs_arr, ys_arr, x, y, ax_obj):
            if len(xs_arr) == 0: return None, None, None
            disp = ax_obj.transData.transform(np.column_stack([xs_arr, ys_arr]))
            cx, cy = ax_obj.transData.transform([[x, y]])[0]
            dists = np.hypot(disp[:, 0] - cx, disp[:, 1] - cy)
            idx = int(np.argmin(dists))
            return float(xs_arr[idx]), float(ys_arr[idx]), float(dists[idx])

        def _on_motion(event):
            if event.inaxes != ax or _bg[0] is None: return
            mode = _hover_mode.get()
            if mode == "Nessuno": return
            x, y = event.xdata, event.ydata
            if x is None or y is None: return
            canvas.restore_region(_bg[0])
            xl = ax.get_xlim(); yl = ax.get_ylim()
            if mode == "Tooltip":
                best_param, best_x, best_y, best_dist = None, None, None, float("inf")
                for param, (xs_arr, ys_arr, color) in _series.items():
                    nx, ny, dist = _nearest_point(xs_arr, ys_arr, x, y, ax)
                    if nx is not None and dist < best_dist:
                        best_dist = dist; best_param = param
                        best_x = nx; best_y = ny
                if best_param is not None and best_dist < 40:
                    _tooltip.xy = (best_x, best_y)
                    _place_tooltip(best_x, best_y)
                    _tooltip.set_text(f"{best_param}\nX: {best_x:.1f} s\nY: {best_y:.4g}")
                    _tooltip.set_visible(True)
                else:
                    _tooltip.set_visible(False)
                ax.draw_artist(_tooltip)
            elif mode == "Crosshair":
                _vline.set_data([x, x], [yl[0], yl[1]])
                _hline.set_data([xl[0], xl[1]], [y, y])
                lines = [f"X: {x:.1f} s"]
                for param, (xs_arr, ys_arr, _c) in _series.items():
                    iv = _interp_y(xs_arr, ys_arr, x)
                    if iv is not None: lines.append(f"{param}: {iv:.4g}")
                _info_box.set_text("\n".join(lines))
                _info_box.set_visible(True)
                ax.draw_artist(_vline); ax.draw_artist(_hline); ax.draw_artist(_info_box)
            elif mode == "Snap":
                best_param, best_x, best_y, best_dist = None, None, None, float("inf")
                best_color = "#ffffff"
                for param, (xs_arr, ys_arr, color) in _series.items():
                    nx, ny, dist = _nearest_point(xs_arr, ys_arr, x, y, ax)
                    if nx is not None and dist < best_dist:
                        best_dist = dist; best_param = param
                        best_x = nx; best_y = ny; best_color = color
                if best_param is not None and best_dist < 50:
                    _snap_dot.set_data([best_x], [best_y])
                    _snap_dot.set_color(best_color)
                    _tooltip.xy = (best_x, best_y)
                    _place_tooltip(best_x, best_y)
                    _tooltip.set_text(f"{best_param}\nX: {best_x:.1f} s\nY: {best_y:.4g}")
                    _tooltip.set_visible(True)
                else:
                    _snap_dot.set_data([], []); _tooltip.set_visible(False)
                ax.draw_artist(_snap_dot); ax.draw_artist(_tooltip)
            elif mode == "Completo":
                _vline.set_data([x, x], [yl[0], yl[1]])
                _hline.set_data([xl[0], xl[1]], [y, y])
                best_param, best_x, best_y, best_dist = None, None, None, float("inf")
                best_color = "#ffffff"
                for param, (xs_arr, ys_arr, color) in _series.items():
                    nx, ny, dist = _nearest_point(xs_arr, ys_arr, x, y, ax)
                    if nx is not None and dist < best_dist:
                        best_dist = dist; best_param = param
                        best_x = nx; best_y = ny; best_color = color
                if best_param is not None and best_dist < 50:
                    _snap_dot.set_data([best_x], [best_y]); _snap_dot.set_color(best_color)
                else:
                    _snap_dot.set_data([], [])
                lines = [f"X: {x:.1f} s"]
                for param, (xs_arr, ys_arr, _c) in _series.items():
                    iv = _interp_y(xs_arr, ys_arr, x)
                    marker = " ◀" if param == best_param else ""
                    if iv is not None: lines.append(f"{param}: {iv:.4g}{marker}")
                _info_box.set_text("\n".join(lines)); _info_box.set_visible(True)
                ax.draw_artist(_vline); ax.draw_artist(_hline)
                ax.draw_artist(_snap_dot); ax.draw_artist(_info_box)
            canvas.blit(ax.bbox)

        def _on_leave(event):
            _clear_overlay()

        canvas.mpl_connect("motion_notify_event", _on_motion)
        canvas.mpl_connect("axes_leave_event", _on_leave)

        # -- Limiti originali --
        _orig_xlim = list(ax.get_xlim())
        _orig_ylim = list(ax.get_ylim())
        _zoomed = [False]

        # -- Zoom rotella: out solo se già zoomato, clamp ai limiti originali --
        def _on_scroll(event):
            if event.inaxes is None: return
            if event.button == "down" and not _zoomed[0]: return
            factor = 0.85 if event.button == "up" else 1.0 / 0.85
            xl = list(ax.get_xlim()); yl = list(ax.get_ylim())
            cx = event.xdata; cy = event.ydata
            new_xl = [cx + (x - cx) * factor for x in xl]
            new_yl = [cy + (y - cy) * factor for y in yl]
            if event.button == "down":
                new_xl[0] = max(new_xl[0], _orig_xlim[0]); new_xl[1] = min(new_xl[1], _orig_xlim[1])
                new_yl[0] = max(new_yl[0], _orig_ylim[0]); new_yl[1] = min(new_yl[1], _orig_ylim[1])
                if (abs(new_xl[0]-_orig_xlim[0]) < 1e-6 and abs(new_xl[1]-_orig_xlim[1]) < 1e-6 and
                    abs(new_yl[0]-_orig_ylim[0]) < 1e-6 and abs(new_yl[1]-_orig_ylim[1]) < 1e-6):
                    _zoomed[0] = False
            else:
                _zoomed[0] = True
                new_xl[0] = max(new_xl[0], _orig_xlim[0]); new_xl[1] = min(new_xl[1], _orig_xlim[1])
                new_yl[0] = max(new_yl[0], _orig_ylim[0]); new_yl[1] = min(new_yl[1], _orig_ylim[1])
            if new_xl[1] > new_xl[0] and new_yl[1] > new_yl[0]:
                ax.set_xlim(new_xl); ax.set_ylim(new_yl)
                canvas.draw()
                _save_bg()

        # -- Pan limitato: X e Y non scendono sotto i limiti originali --
        _clamping = [False]
        def _on_xlim_change(ax_changed):
            if _clamping[0]: return
            xl = list(ax_changed.get_xlim())
            if xl[0] < _orig_xlim[0]:
                _clamping[0] = True
                ax_changed.set_xlim(_orig_xlim[0], xl[1] + (_orig_xlim[0] - xl[0]))
                _clamping[0] = False
        def _on_ylim_change(ax_changed):
            if _clamping[0]: return
            yl = list(ax_changed.get_ylim())
            if yl[0] < _orig_ylim[0]:
                _clamping[0] = True
                ax_changed.set_ylim(_orig_ylim[0], yl[1] + (_orig_ylim[0] - yl[0]))
                _clamping[0] = False

        ax.callbacks.connect("xlim_changed", _on_xlim_change)
        ax.callbacks.connect("ylim_changed", _on_ylim_change)
        canvas.mpl_connect("scroll_event", _on_scroll)
        canvas.mpl_connect("resize_event", lambda e: (canvas.draw(), _save_bg()))

    def _grafici_save_note(self):
        """Salva la nota corrente nel file JSON locale."""
        idciclo = (self._grafici_meta or {}).get("idciclo", "")
        if not idciclo: return
        note_text = self._grafici_note_box.get("1.0", "end").strip() if self._grafici_note_box else ""
        try:
            notes = {}
            if os.path.exists(_NOTES_FILE):
                with open(_NOTES_FILE, encoding="utf-8") as f: notes = json.load(f)
            if note_text: notes[idciclo] = note_text
            elif idciclo in notes: del notes[idciclo]
            with open(_NOTES_FILE, "w", encoding="utf-8") as f: json.dump(notes, f, ensure_ascii=False, indent=2)
        except Exception: pass

    def _grafici_load_note(self, idciclo):
        """Carica la nota salvata per l'ID ciclo dato."""
        note_text = ""
        try:
            if os.path.exists(_NOTES_FILE):
                with open(_NOTES_FILE, encoding="utf-8") as f: notes = json.load(f)
                note_text = notes.get(str(idciclo), "")
        except Exception: pass
        if self._grafici_note_box is not None:
            self._grafici_note_box.delete("1.0", "end")
            if note_text: self._grafici_note_box.insert("1.0", note_text)

    def _grafici_open_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if not path: return
        ok, err = _validate_csv(path)
        if not ok:
            messagebox.showerror("File non valido", err)
            self._grafici_status.configure(text=f"X {err}", text_color=COLORS["error"]); return
        # Reset file nativi: un nuovo CSV appartiene a un ciclo diverso,
        # i nativi precedenti non sono più validi.
        self._grafici_native_paths = {}
        self._grafici_native_lbl.configure(text="", text_color=COLORS["text2"])
        self._grafici_csv_path = path
        self._grafici_csv_lbl.configure(text=os.path.basename(path), text_color=COLORS["text"])
        detected, lati_dict, partite = _autodetect_profile(path)
        if detected:
            self._grafici_stampo_var.set(detected)
            self._grafici_stampo_menu.configure(state="disabled")
            pressa_rilevata = _PROFILES.get(detected, {}).get("pressa", "Cannon 5000T")
            self._grafici_pressa_var.set(pressa_rilevata)
            self._grafici_stampo_menu.configure(values=_PRESSA_STAMPI.get(pressa_rilevata, [detected]))
            if "Cannon" in pressa_rilevata:
                self._grafici_native_btn.configure(state="disabled")
            else:
                self._grafici_native_btn.configure(state="normal")
            parti = []
            for prof, lati in lati_dict.items():
                lati_str = f" ({'/'.join(sorted(lati))})" if lati else ""
                parti.append(f"{prof}{lati_str}")
            partite_str = ", ".join(partite[:6]) + ("..." if len(partite) > 6 else "")
            self._grafici_status.configure(
                text=f"OK Rilevato: {' + '.join(parti)} | Partite: {partite_str}",
                text_color=COLORS["info"])
        else:
            self._grafici_stampo_menu.configure(state="normal")
            msg = (f"/!\\ Codici non riconosciuti: {', '.join(partite[:4])} - seleziona manualmente."
                   if partite else "i Campo Partita non trovato - seleziona il profilo manualmente.")
            self._grafici_status.configure(text=msg, text_color=COLORS["warn"])
        try:
            data, meta = _pdf_parse_csv(path)
            self._grafici_data = data; self._grafici_meta = meta
            if self._grafici_native_paths:
                try:
                    nd, mp = _parse_native_pack(self._grafici_native_paths, self._grafici_stampo_var.get())
                    md, mm = _merge_native_data(data, meta, nd, mp)
                except Exception:
                    md, mm = data, meta
            else:
                md, mm = data, meta
            self._grafici_merged_data = md; self._grafici_merged_meta = mm
            self._grafici_build_preview(md, mm)
            self._grafici_gen_btn.configure(state="normal")
            idciclo = (self._grafici_meta or {}).get("idciclo", "")
            self._grafici_load_note(idciclo)
        except Exception as e:
            self._grafici_status.configure(
                text=f"X Errore lettura: {e}", text_color=COLORS["error"])

    def _grafici_open_native(self):
        _TYPES = {"FORZA":"FORZA","POSIZIONE":"POSIZIONE","TEMPS_SUP":"TEMPS_SUP",
                  "TEMPS_INF":"TEMPS_INF","VUOTO_SUP":"VUOTO_SUP","VUOTO_INF":"VUOTO_INF",
                  "DATI_GENERALI":"DATI_GENERALI"}
        paths = filedialog.askopenfilenames(
            title="Seleziona file nativi Persico",
            filetypes=[("CSV files","*.csv *.CSV"),("All files","*.*")])
        if not paths: return
        # FIX 5: accumulo — i file vengono aggiunti a quelli già caricati,
        # non sostituiti. Così si può selezionare un file alla volta.
        if not hasattr(self, "_grafici_native_paths") or not self._grafici_native_paths:
            self._grafici_native_paths = {}
        ignored = []
        for p in paths:
            base = os.path.basename(p).upper()
            matched = next((k for k in _TYPES if base.startswith(k)), None)
            if matched: self._grafici_native_paths[matched] = p
            else: ignored.append(os.path.basename(p))
        n = len(self._grafici_native_paths)
        if n == 0:
            self._grafici_native_lbl.configure(text="Nessun file riconosciuto", text_color=COLORS["warn"]); return
        # Label: mostra tutti i tipi caricati finora, uno per riga se sono molti
        tipi = list(self._grafici_native_paths.keys())
        lbl = f"{n}/7 nativi: {', '.join(tipi)}"
        if ignored: lbl += f"  |  ignorati: {', '.join(ignored)}"
        self._grafici_native_lbl.configure(text=lbl, text_color=COLORS["info"])
        if self._grafici_data is not None:
            try:
                nd, mp = _parse_native_pack(self._grafici_native_paths, self._grafici_stampo_var.get())
                md, mm = _merge_native_data(self._grafici_data, self._grafici_meta, nd, mp)
                self._grafici_merged_data = md; self._grafici_merged_meta = mm
                self._grafici_build_preview(md, mm)
            except Exception as e:
                self._grafici_native_lbl.configure(text=f"Errore nativi: {e}", text_color=COLORS["error"])

    def _grafici_open_logo(self):
        path = filedialog.askopenfilename(filetypes=[("Immagini","*.png *.jpg *.jpeg"),("All files","*.*")])
        if not path: return
        self._grafici_logo_path = path
        self._grafici_logo_lbl.configure(text=os.path.basename(path), text_color=COLORS["text"])

    def _grafici_generate(self):
        if not self._grafici_csv_path:
            messagebox.showwarning("Attenzione","Seleziona prima un file CSV."); return
        selected = {p for p, v in self._grafici_param_vars.items() if v.get()} if self._grafici_param_vars else None
        if selected is not None and not selected:
            messagebox.showwarning("Attenzione","Seleziona almeno un parametro."); return
        stampo = self._grafici_stampo_var.get()
        _base = os.path.splitext(os.path.basename(self._grafici_csv_path))[0] if self._grafici_csv_path else f"Grafico-{stampo.replace(' ','_')}"
        out = filedialog.asksaveasfilename(defaultextension=".pdf",
              initialfile=f"{_base}.pdf", filetypes=[("PDF","*.pdf")])
        if not out: return
        self._grafici_gen_btn.configure(state="disabled", text="Generazione...")
        self._grafici_status.configure(text="Generazione in corso...", text_color=COLORS["warn"])
        logo = self._grafici_logo_path
        md = self._grafici_merged_data or self._grafici_data
        mm = dict(self._grafici_merged_meta or self._grafici_meta)
        note_text = self._grafici_note_box.get("1.0", "end").strip() if hasattr(self, "_grafici_note_box") else ""
        if note_text: mm["note"] = note_text
        if mm.get("partite"):
            mm["partite"] = _filter_partite(mm["partite"], stampo)
        def _run():
            try:
                generate_lamborghini_pdf(self._grafici_csv_path, stampo, out,
                                         logo_path=logo, filter_params=selected,
                                         preloaded_data=md, preloaded_meta=mm)
                self.after(0, lambda: self._grafici_done(out))
            except Exception as e:
                self.after(0, lambda: self._grafici_error(str(e)))
        threading.Thread(target=_run, daemon=True).start()

    def _grafici_done(self, path):
        self._grafici_gen_btn.configure(state="normal", text="Genera PDF")
        self._grafici_status.configure(text=f"OK PDF salvato: {os.path.basename(path)}", text_color=COLORS["info"])
        self.set_status(f"PDF generato: {os.path.basename(path)}")
        try:
            import subprocess, sys
            if sys.platform == "win32": os.startfile(path)
            elif sys.platform == "darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        except Exception: pass

    def _grafici_error(self, msg):
        self._grafici_gen_btn.configure(state="normal", text="Genera PDF")
        self._grafici_status.configure(text=f"Errore: {msg}", text_color=COLORS["error"])
        messagebox.showerror("Errore generazione PDF", msg)


    def _build_help(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color=COLORS["bg"],
                                        scrollbar_button_color=COLORS["border"],
                                        scrollbar_button_hover_color=COLORS["accent"])
        scroll.pack(fill="both", expand=True)

        def _section_title(icon, title, subtitle=""):
            f = ctk.CTkFrame(scroll, fg_color="transparent")
            f.pack(fill="x", padx=16, pady=(22, 6))
            ctk.CTkLabel(f, text=icon, font=("Segoe UI", 22),
                         text_color=COLORS["accent"]).pack(side="left", padx=(0, 10))
            col = ctk.CTkFrame(f, fg_color="transparent")
            col.pack(side="left")
            ctk.CTkLabel(col, text=title, font=("Segoe UI", 15, "bold"),
                         text_color=COLORS["text"]).pack(anchor="w")
            if subtitle:
                ctk.CTkLabel(col, text=subtitle, font=("Segoe UI", 10),
                             text_color=COLORS["text2"]).pack(anchor="w")
            ctk.CTkFrame(scroll, fg_color=COLORS["border"], height=1).pack(
                fill="x", padx=16, pady=(0, 8))

        def _card(icon, title, body, example=None):
            outer = ctk.CTkFrame(scroll, fg_color=COLORS["surface"], corner_radius=10)
            outer.pack(fill="x", padx=16, pady=4)
            hdr = ctk.CTkFrame(outer, fg_color="transparent")
            hdr.pack(fill="x", padx=14, pady=(12, 4))
            ctk.CTkLabel(hdr, text=icon, font=("Segoe UI", 16),
                         text_color=COLORS["accent2"], width=28).pack(side="left")
            ctk.CTkLabel(hdr, text=title, font=("Segoe UI", 11, "bold"),
                         text_color=COLORS["text"]).pack(side="left", padx=6)
            ctk.CTkLabel(outer, text=body, font=("Segoe UI", 10),
                         text_color=COLORS["text2"], anchor="w", justify="left",
                         wraplength=860).pack(anchor="w", padx=46, pady=(0, 4))
            if example:
                ex_frame = ctk.CTkFrame(outer, fg_color=COLORS["surface2"], corner_radius=6)
                ex_frame.pack(fill="x", padx=46, pady=(2, 12))
                ctk.CTkLabel(ex_frame, text="  ESEMPIO  ",
                             font=("Segoe UI", 8, "bold"),
                             text_color=COLORS["accent"],
                             fg_color=COLORS["surface2"]).pack(anchor="w", padx=8, pady=(6, 0))
                ctk.CTkLabel(ex_frame, text=example, font=("Courier New", 9),
                             text_color=COLORS["accent2"], anchor="w", justify="left",
                             wraplength=820).pack(anchor="w", padx=8, pady=(0, 8))
            else:
                ctk.CTkFrame(outer, fg_color="transparent", height=6).pack()

        # intro
        intro = ctk.CTkFrame(scroll, fg_color=COLORS["surface2"], corner_radius=12)
        intro.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(intro, text="MouldGraph  —  Analisi e monitoraggio dati industriali",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(14, 2))
        ctk.CTkLabel(intro,
                     text="L'app si divide in tre tab principali: Grafici, Dati CSV e Live Data.\n"
                          "Ogni tab e' indipendente: puoi usarle in qualsiasi ordine senza interferenze.",
                     font=("Segoe UI", 10), text_color=COLORS["text2"],
                     justify="left", anchor="w").pack(anchor="w", padx=20, pady=(0, 14))

        # TAB GRAFICI
        _section_title("📊", "Tab Grafici",
                       "Generazione PDF professionali per presse Persico 2500T e Cannon 5000T")
        _card("🏭", "Seleziona Pressa e Stampo",
              "Scegli la pressa (Persico 2500T o Cannon 5000T) dal menu in alto a sinistra, "
              "poi seleziona il profilo stampo. Il profilo determina automaticamente le scale "
              "degli assi, i setpoint di temperatura, forza e vuoto.",
              "Pressa: Persico 2500T  ->  Stampo: Front Firewall\n"
              "Pressa: Cannon 5000T  ->  Stampo: Inner Tub")
        _card("📂", "Carica il CSV del ciclo",
              "Clicca Apri CSV e seleziona il file esportato dalla pressa. "
              "Il profilo viene rilevato automaticamente dal codice nella colonna Partita "
              "(es. 26RF005449 -> RF -> Front Firewall). "
              "Puoi anche caricare file nativi Persico separati tramite i pulsanti dedicati.",
              "File CSV con Partita 26RF005449  ->  profilo rilevato: Front Firewall")
        _card("🖼", "Anteprima e generazione PDF",
              "Il grafico si aggiorna in anteprima. Clicca Genera PDF per il report multi-pagina: "
              "pagina 1 cover + temperature, pagina 2 posizione + forza, pagina 3 vuoto. "
              "Il logo aziendale viene incluso automaticamente se presente nella stessa cartella del CSV.",
              "PDF: Firewall_RF_21103.pdf  (3 pagine, 150 dpi)")
        _card("⏱", "Filtro temporale",
              "Usa i cursori T-Start e T-End per restringere il plot a un intervallo del ciclo. "
              "Utile per isolare la fase di pressatura o di raffreddamento.",
              "T-Start: 200s  ->  T-End: 800s  ->  mostra solo la fase di consolidamento")

        # TAB DATI CSV
        _section_title("📋", "Tab Dati CSV",
                       "Analisi universale di qualsiasi file CSV da qualsiasi impianto")
        _card("📂", "Caricamento CSV universale",
              "Clicca Apri CSV. L'app rileva automaticamente: encoding (UTF-8, Latin-1, CP1252), "
              "separatore (; , | TAB), intestazioni, tipo colonna (numerico, datetime, binario, testo) "
              "e unita' di misura dal nome (es. Temp_Forno -> gradi C, Pressione_Bar -> bar).",
              "File: dati_forno.csv  ->  sep=;, 12 colonne numeriche, 1 datetime, 2 binarie")
        _card("📈", "Selezione assi e plot",
              "Seleziona la colonna X (asse temporale) dal menu. "
              "Attiva/disattiva le serie Y cliccando le pillole colorate. "
              "Alcune serie possono essere assegnate all'asse Y2 (destra) per scale diverse. "
              "Il grafico supporta zoom rotella, pan tasto centrale, cursori A/B doppio click.",
              "X: UTC_Time  |  Y1: Temperatura, Pressione  |  Y2: Portata_Lmin")
        _card("🔍", "Rilevamento anomalie automatico",
              "Il pannello Anomalie segnala: spike fuori 2.5 sigma dalla media, pompa spenta, "
              "livello > 95%, pressione < 1.0 bar. "
              "Ogni anomalia mostra timestamp, valore rilevato e descrizione.",
              "[ANOMALIA] Temperatura fuori range [14:32:05]  ->  val=187.3 C (media 162.5 +/- 8.2)")
        _card("📊", "Statistiche colonne",
              "Per ogni colonna numerica selezionata: minimo, massimo, media e deviazione standard.",
              "Temperatura:  min=158.2 C  max=165.8 C  media=162.4 C  sigma=1.3")
        _card("💾", "Export Dati CSV",
              "PNG: salva il grafico corrente con legenda.\n"
              "Report TXT: statistiche complete + anomalie + metadati.\n"
              "PDF impianto: report professionale con intestazione e grafici.",
              "Bottoni:  PNG  /  Report TXT  /  PDF impianto")

        # TAB LIVE DATA
        _section_title("📡", "Tab Live Data",
                       "Monitoraggio in tempo reale: simulazione CSV o acquisizione seriale")
        _card("📂", "Carica CSV di simulazione",
              "Clicca CSV e seleziona un file. L'app rileva la colonna tempo "
              "(datetime o secondi numerici come Time). "
              "Le colonne numeriche appaiono nelle pillole Colonne Y.",
              "File: FORZA_21103.CSV  ->  colonna tempo Time in secondi, 8 colonne numeriche")
        _card("▶", "Avvia, Pausa, Stop",
              "Pulsante verde (triangolo): avvia. I dati vecchi vengono azzerati.\n"
              "Pulsante giallo (pausa): blocca il thread, grafico fermo.\n"
              "Pulsante rosso (stop): termina la sessione.\n"
              "Ad ogni nuovo Avvia la sessione riparte da zero.",
              "Avvia  ->  acquisizione  ->  Pausa  ->  Avvia riprende  ->  Stop fine")
        _card("⚡", "Velocita' simulazione",
              "1x = tempo reale  |  10x = 10 volte piu' veloce  |  60x = molto veloce  |  MAX = istantaneo.\n"
              "Modificabile anche durante la simulazione in corso.",
              "Ciclo FORZA_21103 (1496s):  1x -> 25min  |  10x -> 2.5min  |  60x -> 25s  |  MAX -> 2s")
        _card("〰", "Interpolazione (Interp)",
              "Attivando Interp, ogni 200ms viene calcolato un punto intermedio tra i campioni reali "
              "per animare la curva. I punti interpolati NON vengono salvati nell'export CSV.",
              "Campione t=23s: F1=162.1  ->  interpolato t=23.2s: F1=162.15  ->  t=23.4s: 162.2")
        _card("🔴", "Allarmi live",
              "Clicca + Soglia nel pannello destra. Scegli colonna, Lo (minimo) e/o Hi (massimo). "
              "Al primo scatto appare il badge rosso e viene loggato il momento. "
              "Azzera rimuove tutte le regole e azzera i contatori.",
              "Colonna: FC  |  Lo: 6400  |  Hi: 6600\n"
              "-> [02:35:12] ALLARME [FC] = 6546.4 > 6600")
        _card("💾", "Export Live",
              "CSV: salva tutti i campioni reali con intestazioni.\n"
              "PNG: salva il grafico corrente ad alta risoluzione.",
              "File: live_20260321_023512.csv  (108 righe x 8 colonne)")

        # SCORCIATOIE
        _section_title("⌨", "Scorciatoie e trucchi",
                       "Interazione avanzata con i grafici interattivi")
        _card("🖱", "Zoom con rotella",
              "Rotella su = zoom in centrato sul cursore. Rotella giu' = zoom out.",
              "Rotella su  ->  zoom 15% attorno al punto X del cursore")
        _card("✋", "Pan (trascinamento)",
              "Tasto centrale del mouse (rotella) + trascina per spostarti sull'asse X.",
              "Click centrale + trascina a sinistra  ->  scorre verso destra")
        _card("📍", "Cursori A/B per misure delta",
              "Doppio click sinistro = cursore A. Doppio click destro = cursore B. "
              "Appare un riquadro con delta X, delta Y per serie e pendenza.",
              "A: X=100s FC=6480  |  B: X=200s FC=6520\n"
              "->  DeltaX=100s  |  DeltaFC=+40 kN  |  pendenza=0.4 kN/s")
        _card("👁", "Toggle serie",
              "Clicca le pillole colorate sotto il grafico per mostrare/nascondere serie.",
              "Click su F3  ->  F3 scompare  |  click di nuovo  ->  riappare")
        _card("💡", "Tooltip hover",
              "Muovi il mouse sul grafico: la linea verticale si aggancia al campione piu' vicino "
              "e il tooltip mostra tutti i valori. Mouse fuori dal grafico = tutto sparisce.",
              "X: 135.9  |  FC: 6502  |  SPC: 6500  |  F1: 162.3")
        _card("🔄", "Reset zoom",
              "Clicca Reset zoom per tornare alla vista completa.",
              "Dopo zoom 100s-200s  ->  Reset zoom  ->  vista da 0 a 1496s")

    # -- HELPERS --
    def _sec(self,p,t):
        f=ctk.CTkFrame(p,fg_color="transparent");f.pack(fill="x",pady=(4,4))
        ctk.CTkFrame(f,fg_color=COLORS["accent"],width=4,height=18,corner_radius=2).pack(side="left")
        ctk.CTkLabel(f,text=f"  {t}",font=("Segoe UI",13,"bold"),text_color=COLORS["text"]).pack(side="left")

    def _sec_inline(self,p,t):
        ctk.CTkFrame(p,fg_color=COLORS["accent"],width=4,height=18,corner_radius=2).pack(side="left")
        ctk.CTkLabel(p,text=f"  {t}",font=("Segoe UI",13,"bold"),text_color=COLORS["text"]).pack(side="left")

    # -- LOG ACTIONS --
    def open_file(self):
        path=filedialog.askopenfilename(filetypes=[("Log files","*.log *.txt *.out *.csv"),("All files","*.*")])
        if not path:return
        try:
            with open(path,"r",encoding="utf-8",errors="replace") as f:content=f.read()
            # auto-detect Siemens CSV
            first=content.strip().splitlines()[0] if content.strip() else ""
            if (detect_csv_type([h.strip().strip('"') for h in (first or "").split(",")]) == "front_firewall"
                or ("Record" in first and ("Date" in first or "Time" in first) and "," in first)):
                self.siemens_csv_path = path
                self._load_siemens_data(content,os.path.basename(path))
                self.tabs.set("  Dati Siemens  ");return
            self.txt_input.delete("0.0","end");self.txt_input.insert("0.0",content)
            self.set_status(f"File caricato: {os.path.basename(path)} ({os.path.getsize(path)/1024:.1f} KB)")
            self.analyze()
        except Exception as e:messagebox.showerror("Errore",str(e))

    def analyze(self):
        text=self.txt_input.get("0.0","end").strip()
        if not text or text.startswith("Incolla"):messagebox.showwarning("Attenzione","Incolla un log prima!");return
        self.all_parsed=parse_log(text)
        wt=[l for l in self.all_parsed if l["ts"]]
        if wt:
            mn=min(l["ts"] for l in wt);mx=max(l["ts"] for l in wt)
            self.entry_from.delete(0,"end");self.entry_from.insert(0,mn.strftime("%Y-%m-%d %H:%M"))
            self.entry_to.delete(0,"end");self.entry_to.insert(0,mx.strftime("%Y-%m-%d %H:%M"))
        self.apply_filters();self.set_status(f"Analizzate {len(self.all_parsed)} righe.")

    def toggle_level(self,level):
        self.active_levels[level]=not self.active_levels[level]
        btn=self.lvl_btns[level]
        if self.active_levels[level]:btn.configure(fg_color=LEVEL_BG[level],text_color=LEVEL_COLORS[level])
        else:btn.configure(fg_color=COLORS["surface2"],text_color=COLORS["text2"])
        self.apply_filters()

    def reset_filters(self):
        self.entry_kw.delete(0,"end");self.entry_from.delete(0,"end");self.entry_to.delete(0,"end")
        for lvl in self.active_levels:
            self.active_levels[lvl]=True;self.lvl_btns[lvl].configure(fg_color=LEVEL_BG[lvl],text_color=LEVEL_COLORS[lvl])
        self.apply_filters()

    def _debounced_apply_filters(self):
        """B4: debounce 250ms — esegue apply_filters solo dopo pausa nella digitazione."""
        if getattr(self, "_filter_debounce_job", None):
            try: self.after_cancel(self._filter_debounce_job)
            except Exception: pass
        self._filter_debounce_job = self.after(250, self._run_debounced_filters)

    def _run_debounced_filters(self):
        self._filter_debounce_job = None
        self.apply_filters()

    def apply_filters(self):
        kw=self.entry_kw.get().lower().strip()
        fd=self._pdt(self.entry_from.get().strip());td=self._pdt(self.entry_to.get().strip())
        self.filtered=[]
        for l in self.all_parsed:
            if not self.active_levels.get(l["level"],True):continue
            if kw and kw not in l["raw"].lower():continue
            if fd and l["ts"] and l["ts"]<fd:continue
            if td and l["ts"] and l["ts"]>td:continue
            self.filtered.append(l)
        self._render_stats();self._render_table(kw);self._render_patterns()
        self._render_timeline();self._render_comp();self._render_ai()

    def _pdt(self,s):
        if not s:return None
        for fmt in["%Y-%m-%d %H:%M","%Y-%m-%d %H:%M:%S","%Y-%m-%d"]:
            try:return datetime.strptime(s,fmt)
            except Exception:pass
        return None

    def _render_stats(self):
        self.stat_labels["total"].configure(text=str(len(self.filtered)))
        self.stat_labels["ERROR"].configure(text=str(sum(1 for l in self.filtered if l["level"]=="ERROR")))
        self.stat_labels["WARN"].configure(text=str(sum(1 for l in self.filtered if l["level"]=="WARN")))
        self.stat_labels["INFO"].configure(text=str(sum(1 for l in self.filtered if l["level"]=="INFO")))
        self.lbl_count.configure(text=f"({len(self.filtered)} righe)")

    def _render_table(self,kw=""):
        self.tbl.configure(state="normal");self.tbl.delete("1.0","end")
        for i,l in enumerate(self.filtered):
            tr="roweven" if i%2==0 else "rowodd";lvl=l["level"]
            msg=l["message"][:180]+("..." if len(l["message"])>180 else "")
            self.tbl.insert("end",f"{l['n']:>5}  ",("dim",tr))
            self.tbl.insert("end",f"{l['timestamp']:<20}  ",("dim",tr))
            self.tbl.insert("end",f"{lvl:<7}  ",(lvl,tr))
            self.tbl.insert("end",f"{l['component']:<14}  ",("comp",tr))
            if kw and kw in msg.lower():
                idx=msg.lower().find(kw)
                self.tbl.insert("end",msg[:idx],(tr,))
                self.tbl.insert("end",msg[idx:idx+len(kw)],("hl",tr))
                self.tbl.insert("end",msg[idx+len(kw):]+"\n",(tr,))
            else:self.tbl.insert("end",msg+"\n",(tr,))
        self.tbl.configure(state="disabled")

    def _render_patterns(self):
        sm=defaultdict(lambda:{"count":0,"level":"INFO"})
        for l in self.filtered:s=norm_sig(l["message"]);sm[s]["count"]+=1;sm[s]["level"]=l["level"]
        top=sorted(sm.items(),key=lambda x:-x[1]["count"])[:10]
        mc=top[0][1]["count"] if top else 1
        self.patterns_box.configure(state="normal");self.patterns_box.delete("0.0","end")
        for sig,data in top:
            pct=int((data["count"]/mc)*20);bar="#"*pct+"."*(20-pct)
            label=sig[:65]+"..." if len(sig)>65 else sig
            self.patterns_box.insert("end",f"[{data['level']:<5}]  {data['count']:>3}x  [{bar}]\n  {label}\n\n")
        self.patterns_box.configure(state="disabled")

    def _render_timeline(self):
        self.timeline_canvas.set_data(build_timeline(self.filtered))

    def _render_comp(self):
        comp=defaultdict(lambda:{"ERROR":0,"WARN":0,"INFO":0,"DEBUG":0,"total":0})
        for l in self.filtered:comp[l["component"]][l["level"]]+=1;comp[l["component"]]["total"]+=1
        self.comp_box.configure(state="normal");self.comp_box.delete("0.0","end")
        self.comp_box.insert("end",f"{'COMPONENTE':<20} {'TOT':>5} {'ERR':>5} {'WARN':>5} {'INFO':>5} {'DEBUG':>5}\n")
        self.comp_box.insert("end","-"*55+"\n")
        for c,v in sorted(comp.items(),key=lambda x:-x[1]["total"]):
            self.comp_box.insert("end",f"{c:<20} {v['total']:>5} {v['ERROR']:>5} {v['WARN']:>5} {v['INFO']:>5} {v['DEBUG']:>5}\n")
        self.comp_box.configure(state="disabled")

    def _render_ai(self):
        for w in self.ai_container.winfo_children():w.destroy()
        insights=ai_analysis(self.filtered)
        if not insights:
            ctk.CTkLabel(self.ai_container,text="Nessun dato. Carica un log prima.",
                         font=("Segoe UI",13),text_color=COLORS["text2"]).pack(pady=30);return
        for badge,title,desc,color in insights:
            card=ctk.CTkFrame(self.ai_container,fg_color=COLORS["surface"],corner_radius=10)
            card.pack(fill="x",pady=6,padx=4)
            top=ctk.CTkFrame(card,fg_color="transparent");top.pack(fill="x",padx=14,pady=(12,4))
            ctk.CTkLabel(top,text=f" {badge} ",font=("Segoe UI",10,"bold"),
                         fg_color=color,text_color="#0f1117",corner_radius=4).pack(side="left")
            ctk.CTkLabel(top,text=f"  {title}",font=("Segoe UI",13,"bold"),text_color=color).pack(side="left")
            ctk.CTkLabel(card,text=desc,font=("Segoe UI",12),text_color=COLORS["text"],
                         wraplength=900,anchor="w",justify="left").pack(anchor="w",padx=14,pady=(0,12))

    # -- SIEMENS CSV ACTIONS --
    def open_siemens_csv(self):
        path=filedialog.askopenfilename(filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if not path:return
        try:
            self.siemens_csv_path = path
            with open(path,"r",encoding="utf-8",errors="replace") as f:content=f.read()
            self._load_siemens_data(content,os.path.basename(path))
        except Exception as e:messagebox.showerror("Errore",str(e))

    def _load_siemens_data(self,content,fname):
        self.siemens_headers,self.siemens_rows=parse_siemens_csv(content)
        if not self.siemens_rows:
            messagebox.showwarning("Attenzione","Nessun dato valido nel CSV.");return
        n=len(self.siemens_rows)
        csv_t=detect_csv_type(self.siemens_headers)
        tipo_lbl="Front Firewall (Persico)" if csv_t=="front_firewall" else "Siemens generico"
        self._last_csv_type=csv_t
        self.siemens_info_lbl.configure(text=f"{fname}  |  {n} record  |  tipo: {tipo_lbl}")
        # update col menus
        numeric=[h for h in self.siemens_headers
                 if h not in("Record","Date","Time","UTC Time")
                 and self.siemens_rows and isinstance(self.siemens_rows[0].get(h),float)]
        opts=["-"]+numeric
        self.siemens_col_menu.configure(values=numeric if numeric else["-"])
        self.siemens_col2_menu.configure(values=opts)
        if numeric:self.siemens_col_var.set(numeric[0])
        self.siemens_col2_var.set("-")
        self._refresh_siemens()
        self.set_status(f"CSV Siemens caricato: {fname} ({n} record)")

    def _on_col_change(self,_=None):
        self._refresh_siemens()

    def _refresh_siemens(self):
        if not self.siemens_rows:return
        rows=self.siemens_rows
        times=[r["_ts"] for r in rows]
        col1=self.siemens_col_var.get()
        col2=self.siemens_col2_var.get()
        series={}
        palette=["#6c63ff","#00d4ff","#52c41a","#faad14"]
        if col1 and col1!="-":
            vals=[r.get(col1) for r in rows]
            series[col1]=(palette[0],vals)
        if col2 and col2!="-":
            vals=[r.get(col2) for r in rows]
            series[col2]=(palette[1],vals)
        self.line_chart.set_data(times,series)
        # pump
        pump_col=None
        for pk in["Stato_Pompa","stato_pompa","pump_state","PumpState"]:
            if pk in(self.siemens_headers or[]):pump_col=pk;break
        if pump_col:
            pvals=[r.get(pump_col,0) for r in rows]
            self.pump_canvas.set_data(times,pvals)
        # anomalie
        anomalies,stats=detect_anomalies(rows,self.siemens_headers)
        for w in self.anomaly_container.winfo_children():w.destroy()
        if not anomalies:
            ctk.CTkLabel(self.anomaly_container,text="Nessuna anomalia rilevata.",
                         font=("Segoe UI",12),text_color=COLORS["info"]).pack(pady=8,anchor="w")
        else:
            for badge,title,desc,color in anomalies[:12]:
                card=ctk.CTkFrame(self.anomaly_container,fg_color=COLORS["surface"],corner_radius=8)
                card.pack(fill="x",pady=3)
                top=ctk.CTkFrame(card,fg_color="transparent");top.pack(fill="x",padx=10,pady=(8,2))
                ctk.CTkLabel(top,text=f" {badge} ",font=("Segoe UI",9,"bold"),
                             fg_color=color,text_color="#0f1117",corner_radius=3).pack(side="left")
                ctk.CTkLabel(top,text=f"  {title}",font=("Segoe UI",11,"bold"),text_color=color).pack(side="left")
                ctk.CTkLabel(card,text=desc,font=("Segoe UI",10),text_color=COLORS["text"],
                             wraplength=340,anchor="w",justify="left").pack(anchor="w",padx=10,pady=(0,8))
        # stats
        self.stats_box.configure(state="normal");self.stats_box.delete("0.0","end")
        self.stats_box.insert("end",f"{'COLONNA':<22} {'MIN':>8} {'MAX':>8} {'MEDIA':>8} {'STD':>8}\n")
        self.stats_box.insert("end","-"*52+"\n")
        for col,st in stats.items():
            self.stats_box.insert("end",f"{col:<22} {st['min']:>8.2f} {st['max']:>8.2f} {st['mean']:>8.2f} {st['std']:>8.2f}\n")
        self.stats_box.configure(state="disabled")
        # raw data
        self.raw_box.configure(state="normal");self.raw_box.delete("0.0","end")
        cols=[h for h in self.siemens_headers if h!="_ts"]
        header=" | ".join(f"{c:<14}" for c in cols[:8])
        self.raw_box.insert("end",header+"\n"+"-"*min(len(header),100)+"\n")
        for r in rows[:50]:
            line=" | ".join(f"{str(r.get(c,'')):<14}" for c in cols[:8])
            self.raw_box.insert("end",line+"\n")
        if len(rows)>50:self.raw_box.insert("end",f"... ({len(rows)-50} righe aggiuntive)\n")
        self.raw_box.configure(state="disabled")

    def export_siemens_report(self):
        if not self.siemens_rows:messagebox.showwarning("Attenzione","Nessun dato Siemens caricato.");return
        path=filedialog.asksaveasfilename(defaultextension=".txt",filetypes=[("Text report","*.txt")])
        if not path:return
        anomalies,stats=detect_anomalies(self.siemens_rows,self.siemens_headers)
        with open(path,"w",encoding="utf-8") as f:
            f.write("="*60+"\nREPORT DATI SIEMENS / CANNON ERGOS\n"+"="*60+"\n\n")
            f.write(f"Record totali: {len(self.siemens_rows)}\n")
            f.write(f"Colonne: {', '.join(self.siemens_headers)}\n\n")
            f.write("STATISTICHE\n"+"-"*40+"\n")
            for col,st in stats.items():
                f.write(f"{col}: min={st['min']:.2f} max={st['max']:.2f} media={st['mean']:.2f} std={st['std']:.2f}\n")
            f.write("\nANOMALIE RILEVATE\n"+"-"*40+"\n")
            if anomalies:
                for badge,title,desc,_ in anomalies:f.write(f"[{badge}] {title}\n  {desc}\n\n")
            else:f.write("Nessuna anomalia rilevata.\n")
        self.set_status(f"Report esportato: {os.path.basename(path)}")

    def export_json(self):
        if not self.filtered:messagebox.showwarning("Attenzione","Nessun dato.");return
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if not path:return
        with open(path,"w",encoding="utf-8") as f:
            json.dump([{"line":l["n"],"timestamp":l["timestamp"],"level":l["level"],
                        "component":l["component"],"message":l["message"]} for l in self.filtered],
                      f,indent=2,ensure_ascii=False)
        self.set_status(f"JSON esportato: {os.path.basename(path)}")

    def export_csv(self):
        if not self.filtered:messagebox.showwarning("Attenzione","Nessun dato.");return
        path=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not path:return
        with open(path,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f);w.writerow(["#","Timestamp","Level","Component","Message"])
            for l in self.filtered:w.writerow([l["n"],l["timestamp"],l["level"],l["component"],l["message"]])
        self.set_status(f"CSV esportato: {os.path.basename(path)}")

    
    # =========================================================
    #  TAB: DATI CSV  (Universal Plant CSV Analyzer)
    # =========================================================

    def build_csv_tab(self, parent):
        self._csv_rows          = []
        self._csv_rows2         = []   # secondo CSV per confronto
        self._csv_col_meta2     = {}   # col_meta del secondo CSV
        self._csv_num_cols2     = []   # colonne numeriche del secondo CSV
        self._csv_y_vars2       = {}   # checkbox vars colonne CSV2
        self._csv_filepath2     = None
        self._csv_colors2       = {}
        self._csv_headers       = []
        self._csv_col_meta      = {}
        self._csv_numeric_cols  = []
        self._csv_datetime_cols = []
        self._csv_binary_cols   = []
        self._csv_sep           = ","
        self._csv_enc           = "utf-8"
        self._csv_filepath      = None
        self._csv_xcol_var      = tk.StringVar(value="-")
        self._csv_y_vars        = {}
        self._csv_y2_vars       = {}
        self._csv_colors        = {}

        tb = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=8, height=44)
        tb.pack(fill="x", pady=(0, 6))
        tb.pack_propagate(False)
        ctk.CTkButton(tb, text="Apri CSV", width=100, height=30,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"],
                      command=self._csv_open).pack(side="left", padx=10, pady=7)
        self._csv_info_lbl = ctk.CTkLabel(
            tb, text="Nessun file caricato",
            font=("Segoe UI", 11), text_color=COLORS["text2"])
        self._csv_info_lbl.pack(side="left", padx=8)

        # ── badge anomalie ────────────────────────────────────────────
        self._csv_anomaly_badge = ctk.CTkLabel(
            tb, text="",
            font=("Segoe UI", 10, "bold"),
            text_color=COLORS["text"],
            fg_color=COLORS["error"], corner_radius=6)
        # non pakkato finché non ci sono anomalie

        for txt, cmd, fg in [
            ("Export PDF",    self._csv_export_pdf,    "#7c3aed"),
            ("Export PNG",    self._csv_export_png,    COLORS["surface2"]),
            ("Export Report", self._csv_export_report, COLORS["surface2"]),
            ("Reset Zoom",    self._csv_reset_zoom,    COLORS["surface2"]),
            ("Confronta CSV", self._csv_open_compare,  COLORS["surface2"]),
        ]:
            ctk.CTkButton(tb, text=txt, width=115, height=30,
                          fg_color=fg, hover_color=COLORS["border"],
                          text_color=COLORS["text"],
                          command=cmd).pack(side="right", padx=4, pady=7)

        body = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        body.pack(fill="both", expand=True)
        lw = ctk.CTkFrame(body, fg_color=COLORS["bg"], width=294)
        lw.pack(side="left", fill="y", padx=(0, 6))
        lw.pack_propagate(False)
        left = ctk.CTkScrollableFrame(
            lw, fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        left.pack(fill="both", expand=True)
        _isolate_scroll(left)

        # ── Asse X (evidenziato) ──────────────────────────────────────
        self._sec(left, "Asse X")
        self._csv_xcard = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_xcard.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(self._csv_xcard, text="Colonna X",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=10, pady=(8, 2))
        self._csv_xcol_menu = ctk.CTkOptionMenu(
            self._csv_xcard, variable=self._csv_xcol_var, values=["-"],
            width=256, fg_color=COLORS["surface2"],
            button_color=COLORS["accent"], text_color=COLORS["text"],
            command=self._csv_on_xcol_change)
        self._csv_xcol_menu.pack(padx=10, pady=(0, 6))

        # filtro temporale (Dal / Al) — visibile solo se X è datetime
        self._csv_tfilter_frame = ctk.CTkFrame(self._csv_xcard, fg_color="transparent")
        ctk.CTkLabel(self._csv_tfilter_frame, text="Filtra intervallo",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=10, pady=(2, 2))
        tf_row = ctk.CTkFrame(self._csv_tfilter_frame, fg_color="transparent")
        tf_row.pack(fill="x", padx=8, pady=(0, 6))
        self._csv_from_var = tk.StringVar()
        self._csv_to_var   = tk.StringVar()
        ctk.CTkLabel(tf_row, text="Dal", font=("Segoe UI", 9),
                     text_color=COLORS["text2"]).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(tf_row, textvariable=self._csv_from_var,
                     placeholder_text="HH:MM:SS",
                     width=80, height=24,
                     fg_color=COLORS["surface2"], text_color=COLORS["text"]
                     ).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(tf_row, text="Al", font=("Segoe UI", 9),
                     text_color=COLORS["text2"]).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(tf_row, textvariable=self._csv_to_var,
                     placeholder_text="HH:MM:SS",
                     width=80, height=24,
                     fg_color=COLORS["surface2"], text_color=COLORS["text"]
                     ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(tf_row, text="✓", width=28, height=24,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 10),
                      command=self._csv_refresh_plot).pack(side="left")

        self._sec(left, "Serie Y")
        self._csv_series_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_series_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self._csv_series_card,
                     text="Carica un CSV per vedere le colonne",
                     font=("Segoe UI", 10),
                     text_color=COLORS["text2"]).pack(padx=10, pady=10)

        self._sec(left, "Confronto CSV ②")
        self._csv_series2_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_series2_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self._csv_series2_card,
                     text="Carica un CSV di confronto (pulsante sopra)",
                     font=("Segoe UI", 9), text_color=COLORS["text2"]).pack(padx=10, pady=6)

        self._sec(left, "Stati digitali")
        self._csv_digital_card = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        self._csv_digital_card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self._csv_digital_card, text="—",
                     font=("Segoe UI", 10),
                     text_color=COLORS["text2"]).pack(padx=10, pady=6)

        # ── Statistiche come card ──────────────────────────────────────
        self._sec(left, "Statistiche")
        self._csv_stats_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._csv_stats_container.pack(fill="x", pady=(0, 8))
        # mantengo anche il textbox originale (nascosto) per compatibilità export
        self._csv_statsbox = ctk.CTkTextbox(
            left, height=1, font=("Courier New", 10),
            fg_color=COLORS["bg"], text_color=COLORS["bg"], border_width=0)
        self._csv_statsbox.pack_forget()  # nascosto, solo per export report

        # ── Range personalizzati ──────────────────────────────────────
        self._csv_ranges = []   # [{col, lo, hi}]
        self._sec(left, "Range personalizzati")
        range_hdr = ctk.CTkFrame(left, fg_color="transparent")
        range_hdr.pack(fill="x", pady=(0, 2))
        ctk.CTkButton(range_hdr, text="+ Aggiungi range", width=130, height=24,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 9),
                      command=self._csv_add_range).pack(side="left")
        ctk.CTkButton(range_hdr, text="Azzera", width=70, height=24,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      command=self._csv_clear_ranges).pack(side="left", padx=6)
        self._csv_ranges_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._csv_ranges_container.pack(fill="x", pady=(0, 8))

        self._sec(left, "Anomalie rilevate")
        self._csv_anomaly_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._csv_anomaly_container.pack(fill="x", pady=(0, 8))

        right = ctk.CTkFrame(body, fg_color=COLORS["bg"])
        right.pack(side="left", fill="both", expand=True)
        self._csv_iplot = InteractivePlotCanvas(right, height=430)

    def _csv_on_xcol_change(self, val):
        """Chiamato al cambio colonna X: mostra filtro temporale se datetime."""
        is_dt = val in self._csv_datetime_cols
        if is_dt:
            self._csv_xcard.configure(border_width=2, border_color=COLORS["accent"])
            self._csv_tfilter_frame.pack(fill="x", pady=(0, 4))
        else:
            self._csv_xcard.configure(border_width=0)
            self._csv_tfilter_frame.pack_forget()
        self._csv_refresh_plot()

    def _csv_get_filtered_rows(self):
        """Ritorna le righe filtrate per intervallo temporale (se impostato)."""
        rows = self._csv_rows
        x_col = self._csv_xcol_var.get()
        if x_col not in self._csv_datetime_cols:
            return rows
        from_s = self._csv_from_var.get().strip()
        to_s   = self._csv_to_var.get().strip()
        if not from_s and not to_s:
            return rows
        filtered = []
        for r in rows:
            ts = _uc_parse_dt(r.get(x_col, ""))
            if ts is None:
                filtered.append(r)
                continue
            t = ts.strftime("%H:%M:%S")
            if from_s and t < from_s:
                continue
            if to_s and t > to_s:
                continue
            filtered.append(r)
        return filtered

    def _csv_open_compare(self):
        """Carica un secondo CSV e sovrappone le curve al grafico corrente."""
        if not self._csv_rows:
            messagebox.showwarning("Confronta", "Carica prima il CSV principale.")
            return
        path = filedialog.askopenfilename(
            title="Seleziona CSV da confrontare",
            filetypes=[("CSV / TSV / TXT", "*.csv *.tsv *.txt"), ("Tutti i file", "*.*")])
        if not path:
            return
        self.set_status("Caricamento CSV confronto...")
        def run():
            try:
                if _is_long_cycle_csv(path):
                    rows2, headers2, col_meta2, num_cols2, _, _, _, _ = \
                        _parse_long_cycle_csv(path)
                else:
                    rows2, headers2, col_meta2, num_cols2, _, _, _, _ = \
                        parse_universal_csv(path)
                palette2 = ["#ff6b6b","#ffd93d","#6bcb77","#4d96ff",
                            "#c77dff","#f9844a","#90e0ef","#f15bb5"]
                colors2 = {col: palette2[i % len(palette2)]
                           for i, col in enumerate(num_cols2)}
                def _apply():
                    self._csv_rows2     = rows2
                    self._csv_col_meta2 = col_meta2
                    self._csv_num_cols2 = list(num_cols2)
                    self._csv_filepath2 = path
                    self._csv_colors2.update(colors2)
                    self._csv_rebuild_series2_panel()
                    self._csv_refresh_plot()
                    self.set_status(
                        f"Confronto: {os.path.basename(path)} ({len(rows2)} righe)")
                self.after(0, _apply)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore CSV confronto", str(e)))
        threading.Thread(target=run, daemon=True).start()


    def _csv_rebuild_series2_panel(self):
        """Ricostruisce il pannello checkbox per le colonne del secondo CSV."""
        for w in self._csv_series2_card.winfo_children():
            try: w.destroy()
            except Exception: pass
        if not self._csv_rows2 or not self._csv_num_cols2:
            ctk.CTkLabel(self._csv_series2_card,
                         text="Carica un CSV di confronto (pulsante sopra)",
                         font=("Segoe UI", 9), text_color=COLORS["text2"]).pack(padx=10, pady=6)
            return
        # bottoni Tutti / Nessuno
        hf = ctk.CTkFrame(self._csv_series2_card, fg_color="transparent")
        hf.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkButton(hf, text="Tutti", width=62, height=22,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"],
                      command=lambda: self._csv_sel_all_2(True)).pack(side="left", padx=2)
        ctk.CTkButton(hf, text="Nessuno", width=72, height=22,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"],
                      command=lambda: self._csv_sel_all_2(False)).pack(side="left", padx=2)
        # ricrea vars preservando stato precedente
        prev2 = {c: v.get() for c, v in self._csv_y_vars2.items()}
        self._csv_y_vars2 = {}
        for col in self._csv_num_cols2:
            var = tk.BooleanVar(value=prev2.get(col, True))
            self._csv_y_vars2[col] = var
            color = self._csv_colors2.get(col, COLORS["accent"])
            row = ctk.CTkFrame(self._csv_series2_card, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=1)
            dot = tk.Canvas(row, width=12, height=12,
                            bg=COLORS["surface"], highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=color, outline="")
            dot.pack(side="left", padx=(4, 2), pady=4)
            ctk.CTkCheckBox(
                row, text=col, variable=var,
                font=("Segoe UI", 10), text_color=COLORS["text"],
                fg_color=COLORS["accent"], hover_color="#5a52e0",
                checkmark_color=COLORS["text"],
                border_color=COLORS["border"],
                command=self._csv_refresh_plot
            ).pack(side="left", fill="x", expand=True)

    def _csv_sel_all_2(self, val):
        """Seleziona/deseleziona tutte le colonne del secondo CSV."""
        for v in self._csv_y_vars2.values():
            v.set(val)
        self._csv_refresh_plot()

    def _csv_update_stats_cards(self, y_cols):
        """Rende le statistiche come card colorate invece di un textbox."""
        for w in self._csv_stats_container.winfo_children():
            try: w.destroy()
            except Exception: pass
        if not self._csv_rows or not y_cols:
            return
        # aggiorna anche il textbox nascosto per l'export report
        self._csv_statsbox.configure(state="normal")
        self._csv_statsbox.delete("1.0", "end")
        rows = self._csv_get_filtered_rows()
        for col in y_cols:
            vals = []
            for r in rows:
                try:
                    vals.append(float(r.get(col, "").replace(",", ".")))
                except Exception:
                    pass
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
            unit = self._csv_col_meta.get(col, {}).get("unit", "")
            u    = f" {unit}" if unit else ""
            color = self._csv_colors.get(col, COLORS["accent"])
            # card
            card = ctk.CTkFrame(self._csv_stats_container,
                                fg_color=COLORS["surface"], corner_radius=8)
            card.pack(fill="x", pady=2)
            # intestazione colorata
            hdr_f = ctk.CTkFrame(card, fg_color=color, corner_radius=6, height=22)
            hdr_f.pack(fill="x", padx=4, pady=(4, 2))
            hdr_f.pack_propagate(False)
            ctk.CTkLabel(hdr_f, text=col, font=("Segoe UI", 9, "bold"),
                         text_color="#fff").pack(side="left", padx=8)
            ctk.CTkLabel(hdr_f, text=f"N={len(vals)}",
                         font=("Segoe UI", 8), text_color="#ffffff99").pack(side="right", padx=6)
            # valori in griglia 2×2
            grid = ctk.CTkFrame(card, fg_color="transparent")
            grid.pack(fill="x", padx=6, pady=(2, 6))
            for i, (lbl, val) in enumerate([
                ("min", f"{min(vals):.4g}{u}"),
                ("max", f"{max(vals):.4g}{u}"),
                ("μ",   f"{mean:.4g}{u}"),
                ("σ",   f"{std:.4g}"),
            ]):
                col_f = ctk.CTkFrame(grid, fg_color="transparent")
                col_f.grid(row=i//2, column=i%2, sticky="w", padx=4, pady=1)
                ctk.CTkLabel(col_f, text=lbl, font=("Segoe UI", 8),
                             text_color=COLORS["text2"]).pack(side="left")
                ctk.CTkLabel(col_f, text=f"  {val}", font=("Segoe UI", 9, "bold"),
                             text_color=COLORS["text"]).pack(side="left")
            # aggiorna textbox nascosto
            self._csv_statsbox.insert("end",
                f"▸ {col[:24]}\n"
                f"  min={min(vals):.4g}{u}  max={max(vals):.4g}{u}\n"
                f"  μ={mean:.4g}{u}  σ={std:.4g}  N={len(vals)}\n\n")
        self._csv_statsbox.configure(state="disabled")

    def _csv_add_range(self):
        """Dialogo per aggiungere un range personalizzato su una colonna."""
        if not self._csv_numeric_cols:
            messagebox.showinfo("Range", "Carica prima un CSV.")
            return
        win = ctk.CTkToplevel(self)
        win.title("Nuovo range")
        win.geometry("340x280")
        win.resizable(False, False)
        win.configure(fg_color=COLORS["bg"])
        win.grab_set()

        ctk.CTkLabel(win, text="Colonna", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 2))
        col_var = ctk.StringVar(value=self._csv_numeric_cols[0])
        ctk.CTkOptionMenu(win, variable=col_var,
                          values=self._csv_numeric_cols, width=290,
                          fg_color=COLORS["surface2"], button_color=COLORS["accent"],
                          text_color=COLORS["text"]).pack(padx=20)

        ctk.CTkLabel(win, text="Minimo (Lo) — lascia vuoto per ignorare",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(12, 2))
        lo_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=lo_var, placeholder_text="es. 0.5",
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     width=290).pack(padx=20)

        ctk.CTkLabel(win, text="Massimo (Hi) — lascia vuoto per ignorare",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(10, 2))
        hi_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=hi_var, placeholder_text="es. 150.0",
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     width=290).pack(padx=20)

        def _confirm():
            col = col_var.get()
            lo = None; hi = None
            try: lo = float(lo_var.get().replace(",", "."))
            except Exception: pass
            try: hi = float(hi_var.get().replace(",", "."))
            except Exception: pass
            if lo is None and hi is None:
                messagebox.showwarning("Range", "Inserisci almeno un valore Lo o Hi.")
                return
            self._csv_ranges.append({"col": col, "lo": lo, "hi": hi})
            self._csv_rebuild_range_cards()
            self._csv_refresh_plot()
            win.destroy()

        ctk.CTkButton(win, text="Aggiungi", width=140, height=32,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], command=_confirm).pack(pady=16)

    def _csv_clear_ranges(self):
        self._csv_ranges.clear()
        self._csv_rebuild_range_cards()
        self._csv_refresh_plot()

    def _csv_rebuild_range_cards(self):
        for w in self._csv_ranges_container.winfo_children():
            try: w.destroy()
            except Exception: pass
        if not self._csv_ranges:
            ctk.CTkLabel(self._csv_ranges_container,
                         text="Nessun range definito",
                         font=("Segoe UI", 9), text_color=COLORS["text2"]).pack(
                anchor="w", padx=4, pady=2)
            return
        for idx, rule in enumerate(self._csv_ranges):
            col = rule["col"]; lo = rule.get("lo"); hi = rule.get("hi")
            parts = []
            if lo is not None: parts.append(f"Lo={lo:.4g}")
            if hi is not None: parts.append(f"Hi={hi:.4g}")
            label = f"{col}  [{',  '.join(parts)}]"
            card = ctk.CTkFrame(self._csv_ranges_container,
                                fg_color=COLORS["surface"], corner_radius=6)
            card.pack(fill="x", pady=2)
            ctk.CTkLabel(card, text=label, font=("Segoe UI", 9),
                         text_color=COLORS["text"]).pack(side="left", padx=8, pady=4)
            ctk.CTkButton(card, text="✕", width=22, height=22,
                          fg_color="transparent", hover_color=COLORS["border"],
                          text_color=COLORS["text2"], font=("Segoe UI", 9),
                          command=lambda i=idx: self._csv_remove_range(i)
                          ).pack(side="right", padx=4)

    def _csv_remove_range(self, idx):
        if 0 <= idx < len(self._csv_ranges):
            self._csv_ranges.pop(idx)
        self._csv_rebuild_range_cards()
        self._csv_refresh_plot()

    def _csv_open(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV / TSV / TXT", "*.csv *.tsv *.txt"), ("Tutti i file", "*.*")])
        if not path:
            return
        self.set_status("Caricamento CSV in corso...")
        def run():
            try:
                rows, headers, col_meta, num_cols, dt_cols, bin_cols, sep, enc = \
                    parse_universal_csv(path)
                def _apply():
                    self._csv_rows          = rows
                    self._csv_headers       = headers
                    self._csv_col_meta      = col_meta
                    self._csv_numeric_cols  = num_cols
                    self._csv_datetime_cols = dt_cols
                    self._csv_binary_cols   = bin_cols
                    self._csv_sep           = sep
                    self._csv_enc           = enc
                    self._csv_filepath      = path
                    self._csv_populate_controls()
                    self.set_status(
                        f"CSV caricato: {len(rows)} righe · {len(headers)} colonne · "
                        f"sep='{sep}' · enc={enc}")
                self.after(0, _apply)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore CSV", str(e)))
                self.after(0, lambda: self.set_status("Errore caricamento CSV."))
        threading.Thread(target=run, daemon=True).start()

    def _csv_populate_controls(self):
        basename = os.path.basename(self._csv_filepath or "")
        self._csv_info_lbl.configure(
            text=f"{basename}  │  {len(self._csv_rows)} righe  │  "
                 f"sep='{self._csv_sep}'  enc={self._csv_enc}")
        x_choices = self._csv_datetime_cols + self._csv_numeric_cols
        if not x_choices:
            x_choices = ["-"]
        self._csv_xcol_menu.configure(values=x_choices)
        self._csv_xcol_var.set(x_choices[0])
        palette = list(_UC_SERIES_PALETTE)
        for i, col in enumerate(self._csv_numeric_cols):
            if col not in self._csv_colors:
                self._csv_colors[col] = palette[i % len(palette)]
        for w in self._csv_series_card.winfo_children():
            w.destroy()
        self._csv_y_vars  = {}
        self._csv_y2_vars = {}
        if not self._csv_numeric_cols:
            ctk.CTkLabel(self._csv_series_card,
                         text="Nessuna colonna numerica trovata",
                         font=("Segoe UI", 10),
                         text_color=COLORS["text2"]).pack(padx=10, pady=8)
        else:
            hf = ctk.CTkFrame(self._csv_series_card, fg_color="transparent")
            hf.pack(fill="x", padx=8, pady=(6, 2))
            ctk.CTkButton(hf, text="Tutti", width=62, height=22,
                          fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                          text_color=COLORS["text2"],
                          command=lambda: self._csv_sel_all(True)).pack(side="left", padx=2)
            ctk.CTkButton(hf, text="Nessuno", width=72, height=22,
                          fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                          text_color=COLORS["text2"],
                          command=lambda: self._csv_sel_all(False)).pack(side="left", padx=2)
            for col in self._csv_numeric_cols:
                var  = tk.BooleanVar(value=True)
                var2 = tk.BooleanVar(value=False)
                self._csv_y_vars[col]  = var
                self._csv_y2_vars[col] = var2
                color = self._csv_colors[col]
                meta  = self._csv_col_meta.get(col, {})
                unit  = meta.get("unit", "")
                label = meta.get("label", col)
                disp = col if col == label else f"{col} [{label}]"
                if unit:
                    disp += f" {unit}"
                row_f = ctk.CTkFrame(self._csv_series_card, fg_color="transparent")
                row_f.pack(fill="x", padx=6, pady=1)
                dot = tk.Canvas(row_f, width=12, height=12,
                                bg=COLORS["surface"], highlightthickness=0)
                dot.create_oval(1, 1, 11, 11, fill=color, outline="")
                dot.pack(side="left", padx=(4, 2), pady=4)
                ctk.CTkCheckBox(
                    row_f, text=disp, variable=var,
                    font=("Segoe UI", 10), text_color=COLORS["text"],
                    fg_color=COLORS["accent"], hover_color="#5a52e0",
                    checkmark_color=COLORS["text"],
                    border_color=COLORS["border"],
                    command=self._csv_refresh_plot
                ).pack(side="left", fill="x", expand=True)
                btn_holder = {}
                def _make_toggle(c=col, bv=var2, bh=btn_holder):
                    def _toggle():
                        bv.set(not bv.get())
                        bh["b"].configure(
                            text="Y2" if bv.get() else "Y1",
                            fg_color="#7c3aed" if bv.get() else COLORS["surface2"])
                        self._csv_refresh_plot()
                    return _toggle
                y2b = ctk.CTkButton(
                    row_f, text="Y1", width=34, height=22,
                    fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                    text_color=COLORS["text2"], font=("Segoe UI", 9),
                    command=_make_toggle())
                y2b.pack(side="right", padx=(2, 6))
                btn_holder["b"] = y2b
        for w in self._csv_digital_card.winfo_children():
            w.destroy()
        if not self._csv_binary_cols:
            ctk.CTkLabel(self._csv_digital_card, text="—",
                         font=("Segoe UI", 10),
                         text_color=COLORS["text2"]).pack(padx=10, pady=6)
        else:
            for col in self._csv_binary_cols:
                ctk.CTkLabel(self._csv_digital_card,
                             text=f"⚡  {col}",
                             font=("Segoe UI", 10),
                             text_color=COLORS["accent2"],
                             anchor="w").pack(anchor="w", padx=10, pady=2)
        self._csv_refresh_plot()

    def _csv_refresh_plot(self):
        if not self._csv_rows:
            return
        x_col  = self._csv_xcol_var.get()
        if x_col == "-":
            x_col = None
        y_cols  = [c for c, v in self._csv_y_vars.items() if v.get()]
        y2_cols = {c for c, v in self._csv_y2_vars.items() if v.get()}

        # usa righe filtrate per intervallo temporale
        rows = self._csv_get_filtered_rows()
        xs_raw, series, x_type = _uc_build_series(
            rows, x_col, y_cols, self._csv_col_meta)
        colors  = {c: self._csv_colors[c] for c in y_cols if c in self._csv_colors}
        x_label = x_col or "Indice"

        # serie principali CSV1
        self._csv_iplot.set_data(
            xs_raw, series, x_type, self._csv_col_meta,
            y2_cols=y2_cols, colors=colors, x_label=x_label)

        # ── bande range personalizzati sul grafico ─────────────────────
        self._csv_iplot.set_ranges(getattr(self, "_csv_ranges", []))

        # ── overlay ② DOPO set_ranges: colonne spuntate nel pannello CSV2 ──
        if self._csv_rows2:
            cols_ov = [c for c, v in self._csv_y_vars2.items() if v.get()]
            if cols_ov:
                self._csv_iplot._overlay_second_csv(
                    self._csv_rows2, x_col, cols_ov,
                    self._csv_colors2,
                    getattr(self, "_csv_col_meta2", self._csv_col_meta))

        self._csv_update_stats_cards(y_cols)
        self._csv_update_anomalies()

    def _csv_sel_all(self, val):
        for v in self._csv_y_vars.values():
            v.set(val)
        self._csv_refresh_plot()

    def _csv_update_stats(self, y_cols):
        # alias per compatibilità export — usa il nuovo metodo con card
        self._csv_update_stats_cards(y_cols)

    def _csv_update_anomalies(self):
        for w in self._csv_anomaly_container.winfo_children():
            w.destroy()
        if not self._csv_rows:
            self._csv_anomaly_badge.pack_forget()
            return
        x_col = self._csv_xcol_var.get()
        rows = self._csv_get_filtered_rows()
        anomalies = []

        # ── Range personalizzati (priorità assoluta) ──────────────────
        for rule in self._csv_ranges:
            col = rule["col"]; lo = rule.get("lo"); hi = rule.get("hi")
            violations = []
            for i, r in enumerate(rows):
                try:
                    val = float(r.get(col, "").replace(",", "."))
                except Exception:
                    continue
                ts = _uc_parse_dt(r.get(x_col, "")) if x_col and x_col != "-" else None
                ts_str = ts.strftime("%H:%M:%S") if ts else f"riga {i+1}"
                if lo is not None and val < lo:
                    violations.append((ts_str, val, f"< {lo:.4g}"))
                elif hi is not None and val > hi:
                    violations.append((ts_str, val, f"> {hi:.4g}"))
            if violations:
                # raggruppa: mostra prima e ultima violazione + conteggio
                cnt = len(violations)
                first_ts, first_val, first_dir = violations[0]
                last_ts,  last_val,  last_dir  = violations[-1]
                desc = (f"{cnt} campion{'e' if cnt==1 else 'i'} fuori range. "
                        f"Primo: {first_val:.4g} {first_dir} @ {first_ts}. "
                        f"Ultimo: {last_val:.4g} {last_dir} @ {last_ts}.")
                anomalies.append(("RANGE", f"{col} — {cnt} violazion{'e' if cnt==1 else 'i'}",
                                  desc, COLORS["error"]))

        # ── Rilevamento automatico (solo se nessun range manuale definito) ──
        if not self._csv_ranges:
            all_cols = self._csv_numeric_cols + self._csv_binary_cols
            num_rows = []
            for i, r in enumerate(rows):
                d = {"_ts": _uc_parse_dt(r.get(x_col, "")) if x_col != "-" else None}
                for col in all_cols:
                    try:
                        d[col] = float(r.get(col, "").replace(",", "."))
                    except Exception:
                        d[col] = 0.0
                num_rows.append(d)
            try:
                auto_anomalies, _ = detect_anomalies(num_rows, all_cols)
                anomalies.extend(auto_anomalies)
            except Exception:
                pass

        # aggiorna badge
        if anomalies:
            self._csv_anomaly_badge.configure(
                text=f"  ⚠ {len(anomalies)} anomalie  ")
            self._csv_anomaly_badge.pack(side="left", padx=6, pady=7)
        else:
            self._csv_anomaly_badge.pack_forget()

        if not anomalies:
            ctk.CTkLabel(self._csv_anomaly_container,
                         text="Nessuna anomalia rilevata",
                         font=("Segoe UI", 10),
                         text_color=COLORS["info"]).pack(anchor="w", padx=4, pady=4)
            return
        for tag, title, desc, color in anomalies[:30]:
            card = ctk.CTkFrame(self._csv_anomaly_container,
                                fg_color=COLORS["surface"], corner_radius=6)
            card.pack(fill="x", pady=2)
            ctk.CTkLabel(card, text=f"[{tag}]  {title}",
                         font=("Segoe UI", 10, "bold"),
                         text_color=color, anchor="w").pack(anchor="w", padx=8, pady=(6, 1))
            ctk.CTkLabel(card, text=desc,
                         font=("Segoe UI", 9),
                         text_color=COLORS["text2"],
                         anchor="w", wraplength=250).pack(anchor="w", padx=8, pady=(0, 6))

    def _csv_reset_zoom(self):
        if self._csv_iplot:
            self._csv_iplot.reset_zoom()

    def _csv_export_png(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato da esportare.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
            initialfile="grafico_csv.png")
        if not path:
            return
        try:
            self._csv_iplot.export_png(path)
            self.set_status(f"PNG salvato: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Errore PNG", str(e))

    def _csv_export_report(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato caricato.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt")],
            initialfile="report_csv.txt")
        if not path:
            return
        lines = [
            f"REPORT CSV  —  {os.path.basename(self._csv_filepath or '')}",
            f"Generato:  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            f"Righe: {len(self._csv_rows)}   Colonne: {len(self._csv_headers)}",
            f"Separatore: '{self._csv_sep}'   Encoding: {self._csv_enc}",
            "", "=" * 55, "COLONNE RILEVATE:", "=" * 55,
        ]
        for col in self._csv_headers:
            m = self._csv_col_meta.get(col, {})
            lines.append(
                f"  {col:<32}  [{m.get('col_type','?'):8}]  "
                f"{m.get('unit',''):6}  {m.get('label','')}")
        lines += ["", "=" * 55, "STATISTICHE:", "=" * 55]
        for col in self._csv_numeric_cols:
            vals = []
            for r in self._csv_rows:
                try:
                    vals.append(float(r.get(col, "").replace(",", ".")))
                except Exception:
                    pass
            if vals:
                mean = sum(vals) / len(vals)
                std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
                lines.append(
                    f"  {col:<32}  min={min(vals):.4g}  max={max(vals):.4g}"
                    f"  μ={mean:.4g}  σ={std:.4g}  N={len(vals)}")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.set_status(f"Report salvato: {os.path.basename(path)}")
            messagebox.showinfo("Completato", f"Report salvato:\n{path}")
        except Exception as e:
            messagebox.showerror("Errore salvataggio", str(e))

    def _csv_export_pdf(self):
        if not self._csv_rows:
            messagebox.showwarning("Attenzione", "Nessun dato caricato.")
            return
        y_cols = [c for c, v in self._csv_y_vars.items() if v.get()]
        if not y_cols:
            messagebox.showwarning("Attenzione", "Seleziona almeno una serie Y.")
            return
        plant = simpledialog.askstring(
            "Nome impianto",
            "Inserisci il nome dell'impianto (es. Forno 3, CNC-A, Pressa 5T):",
            initialvalue="Impianto")
        if plant is None:
            return
        plant = plant.strip() or "Impianto"
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"report_{plant.replace(' ', '_')}.pdf")
        if not path:
            return
        y2_cols = {c for c, v in self._csv_y2_vars.items() if v.get()}
        x_col   = self._csv_xcol_var.get()
        if x_col == "-":
            x_col = None
        logo = getattr(self, "_grafici_logo_path", None)
        self.set_status("Generazione PDF impianto in corso...")
        def run():
            try:
                _cols2_exp = [c for c, v in self._csv_y_vars2.items() if v.get()]
                generate_plant_pdf(
                    rows        = self._csv_rows,
                    headers     = self._csv_headers,
                    col_meta    = self._csv_col_meta,
                    x_col       = x_col,
                    y_cols      = y_cols,
                    y2_cols     = y2_cols,
                    output_path = path,
                    plant_name  = plant,
                    logo_path   = logo,
                    notes       = "",
                    rows2       = self._csv_rows2 if (self._csv_rows2 and _cols2_exp) else None,
                    cols2       = _cols2_exp or None,
                    colors2     = self._csv_colors2,
                    col_meta2   = getattr(self, "_csv_col_meta2", {}),
                )
                self.after(0, lambda: self.set_status(
                    f"PDF salvato: {os.path.basename(path)}"))
                self.after(0, lambda: messagebox.showinfo(
                    "Completato", f"PDF salvato:\n{path}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Errore PDF", str(e)))
                self.after(0, lambda: self.set_status("Errore generazione PDF."))
        threading.Thread(target=run, daemon=True).start()


    def _live_check_alarms(self):
        """Controlla l'ultimo campione rispetto alle soglie configurate."""
        if not self._live_rows or not self._live_alarm_rules:
            return
        last = self._live_rows[-1]
        newly_triggered = []
        now_active = set()
        for rule in self._live_alarm_rules:
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
                if col not in self._live_alarm_active:
                    # nuovo scatto
                    self._live_alarm_count += 1
                    newly_triggered.append((col, val, direction))
        # aggiorna badge
        self._live_alarm_active = now_active
        if now_active:
            self._live_alarm_badge.configure(
                text=f"🔴  {len(now_active)} ALLARME/I  |  Totale scatti: {self._live_alarm_count}",
                text_color=COLORS["error"])
        else:
            badge_txt = (f"✅  OK  |  Scatti totali: {self._live_alarm_count}"
                         if self._live_alarm_count else "")
            self._live_alarm_badge.configure(
                text=badge_txt,
                text_color=COLORS["info"])
        # log nuovi scatti
        for col, val, direction in newly_triggered:
            self._live_log_append(
                f"⚠ ALLARME [{col}] = {val:.4g} {direction}", scroll=True)

    def _live_add_alarm_rule(self):
        """Dialogo per aggiungere una soglia di allarme."""
        if not self._live_numeric_cols:
            messagebox.showinfo("Allarmi", "Carica prima un CSV o avvia la simulazione.")
            return
        win = ctk.CTkToplevel(self)
        win.title("Nuova soglia allarme")
        win.geometry("340x300")
        win.resizable(False, False)
        win.configure(fg_color=COLORS["bg"])
        win.grab_set()

        ctk.CTkLabel(win, text="Colonna", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(18, 2))
        col_var = ctk.StringVar(value=self._live_numeric_cols[0])
        ctk.CTkOptionMenu(win, variable=col_var,
                          values=self._live_numeric_cols, width=280,
                          fg_color=COLORS["surface2"], button_color=COLORS["accent"],
                          text_color=COLORS["text"]).pack(padx=20)

        ctk.CTkLabel(win, text="Soglia minima (Lo) — lascia vuoto per ignorare",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(12, 2))
        lo_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=lo_var, placeholder_text="es. 0.5",
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     width=280).pack(padx=20)

        ctk.CTkLabel(win, text="Soglia massima (Hi) — lascia vuoto per ignorare",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(10, 2))
        hi_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=hi_var, placeholder_text="es. 150.0",
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     width=280).pack(padx=20)

        def _confirm():
            col = col_var.get()
            lo = None; hi = None
            try: lo = float(lo_var.get().replace(",", "."))
            except Exception: pass
            try: hi = float(hi_var.get().replace(",", "."))
            except Exception: pass
            if lo is None and hi is None:
                messagebox.showwarning("Soglia", "Inserisci almeno un valore Lo o Hi.")
                return
            self._live_alarm_rules.append({"col": col, "lo": lo, "hi": hi})
            self._live_rebuild_alarm_cards()
            win.destroy()

        ctk.CTkButton(win, text="Aggiungi", width=140, height=32,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], command=_confirm).pack(pady=16)

    def _live_rebuild_alarm_cards(self):
        """Ripopola il pannello card soglie."""
        for w in self._live_alarm_cards_ui:
            try: w.destroy()
            except Exception: pass
        self._live_alarm_cards_ui.clear()
        for idx, rule in enumerate(self._live_alarm_rules):
            col = rule["col"]
            lo  = rule.get("lo")
            hi  = rule.get("hi")
            parts = []
            if lo is not None: parts.append(f"Lo={lo:.4g}")
            if hi is not None: parts.append(f"Hi={hi:.4g}")
            label = f"{col}  [{', '.join(parts)}]"
            is_alarm = col in self._live_alarm_active
            card = ctk.CTkFrame(
                self._live_alarm_rules_frame,
                fg_color=COLORS["error"] if is_alarm else COLORS["surface"],
                corner_radius=6)
            card.pack(fill="x", padx=4, pady=3, ipadx=4, ipady=2)
            ctk.CTkLabel(card, text=label, font=("Segoe UI", 9, "bold"),
                         text_color=COLORS["text"]).pack(side="left", padx=6)
            del_btn = ctk.CTkButton(
                card, text="✕", width=20, height=20,
                fg_color="transparent", hover_color=COLORS["border"],
                text_color=COLORS["text2"], font=("Segoe UI", 9),
                command=lambda i=idx: self._live_remove_alarm(i))
            del_btn.pack(side="left", padx=(0, 4))
            self._live_alarm_cards_ui.append(card)

    def _live_remove_alarm(self, idx):
        if 0 <= idx < len(self._live_alarm_rules):
            self._live_alarm_rules.pop(idx)
            self._live_rebuild_alarm_cards()

    def _live_reset_alarms(self):
        self._live_alarm_rules.clear()
        self._live_alarm_count = 0
        self._live_alarm_active.clear()
        self._live_alarm_badge.configure(text="")
        self._live_rebuild_alarm_cards()

    def _live_export_png(self):
        """Esporta il/i grafico/i. In multi: finestra selezione → unico file."""
        if not self._live_rows:
            messagebox.showinfo("Esporta", "Nessun dato da esportare.")
            return
        if self._live_multi_mode and self._live_multi_ipcs:
            self._live_export_multi_dialog("png")
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG", "*.png")],
                title="Salva grafico live come PNG",
                initialfile="live_plot.png")
            if not path:
                return
            try:
                self._live_ipc.export_png(path)
                self.set_status(f"PNG salvato: {os.path.basename(path)}")
                messagebox.showinfo("Esportato", f"PNG salvato:\n{path}")
            except Exception as e:
                messagebox.showerror("Errore PNG", str(e))

    def _live_export_multi_dialog(self, fmt="png"):
        """Finestra di selezione grafici per export multi → unico file PNG o PDF."""
        groups = list(self._live_multi_ipcs.keys())
        if not groups:
            return

        win = ctk.CTkToplevel(self)
        win.title("Esporta grafici")
        win.geometry("340x420")
        win.resizable(False, False)
        win.configure(fg_color=COLORS["bg"])
        win.grab_set()

        ctk.CTkLabel(win, text="Seleziona i grafici da esportare",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 8))

        # checkbox per ogni gruppo
        vars_ = {}
        scroll = ctk.CTkScrollableFrame(win, fg_color=COLORS["surface"],
                                        corner_radius=8, height=220)
        scroll.pack(fill="x", padx=20, pady=(0, 8))
        for gn in groups:
            v = tk.BooleanVar(value=True)
            vars_[gn] = v
            ctk.CTkCheckBox(scroll, text=gn, variable=v,
                            font=("Segoe UI", 10), text_color=COLORS["text"],
                            fg_color=COLORS["accent"], hover_color="#5a52e0",
                            checkmark_color="#fff").pack(anchor="w", padx=10, pady=4)

        # selezione tutti/nessuno
        sel_row = ctk.CTkFrame(win, fg_color="transparent")
        sel_row.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkButton(sel_row, text="Tutti", width=80, height=24,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      command=lambda: [v.set(True) for v in vars_.values()]
                      ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(sel_row, text="Nessuno", width=80, height=24,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      command=lambda: [v.set(False) for v in vars_.values()]
                      ).pack(side="left")

        # layout
        ctk.CTkLabel(win, text="Layout:",
                     font=("Segoe UI", 10), text_color=COLORS["text2"]).pack(
            anchor="w", padx=20, pady=(0, 2))
        layout_var = ctk.StringVar(value="Verticale")
        ctk.CTkOptionMenu(win, variable=layout_var,
                          values=["Verticale", "Griglia 2 colonne"],
                          width=200, fg_color=COLORS["surface2"],
                          button_color=COLORS["accent"],
                          text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(0, 12))

        def _do_export():
            selected = [gn for gn, v in vars_.items() if v.get()]
            if not selected:
                messagebox.showwarning("Selezione", "Seleziona almeno un grafico.")
                return
            if fmt == "png":
                path = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG", "*.png")],
                    initialfile="live_multi.png")
            else:
                path = filedialog.asksaveasfilename(
                    defaultextension=".pdf",
                    filetypes=[("PDF", "*.pdf")],
                    initialfile="live_multi.pdf")
            if not path:
                return
            win.destroy()
            try:
                self._live_export_multi_render(selected, path, fmt,
                                               layout_var.get())
            except Exception as e:
                messagebox.showerror("Errore export", str(e))

        ctk.CTkButton(win, text=f"Esporta {fmt.upper()}",
                      width=200, height=34,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 11),
                      command=_do_export).pack(pady=(0, 16))

    def _live_export_multi_render(self, selected, path, fmt, layout):
        """Costruisce una figura matplotlib con i grafici selezionati e salva."""
        n = len(selected)
        if layout == "Griglia 2 colonne":
            ncols = 2; nrows = (n + 1) // 2
        else:
            ncols = 1; nrows = n

        fig, axes = plt.subplots(nrows, ncols,
                                 figsize=(10 * ncols, 4 * nrows),
                                 facecolor="#1e1e2e")
        if n == 1:
            axes = [axes]
        elif ncols == 1:
            axes = list(axes)
        else:
            axes = [ax for row in axes for ax in (row if hasattr(row, '__iter__') else [row])]

        palette = list(_UC_SERIES_PALETTE)
        colors = {col: palette[i % len(palette)]
                  for i, col in enumerate(self._live_numeric_cols)}

        try:
            max_pts = int(self._live_maxpts_var.get())
        except Exception:
            max_pts = MAX_LIVE_POINTS
        rows = self._live_rows[-max_pts:]

        x_col = "_ts" if rows and "_ts" in rows[0] else (
                "_sim_t" if rows and "_sim_t" in rows[0] else None)
        xs_raw = [r.get(x_col, i) if x_col else i for i, r in enumerate(rows)]

        for ax_idx, gn in enumerate(selected):
            if ax_idx >= len(axes):
                break
            ax = axes[ax_idx]
            ax.set_facecolor("#252535")
            ax.set_title(gn, color="#a0a0c0", fontsize=10, pad=4)
            for sp in ax.spines.values():
                sp.set_edgecolor("#3a3a5c")
            ax.tick_params(colors="#a0a0c0", labelsize=7)
            ax.grid(True, color="#3a3a5c", linewidth=0.4,
                    linestyle="--", alpha=0.6)

            ipc, group_cols, _ = self._live_multi_ipcs[gn]
            for col in group_cols:
                vals = [float(r.get(col)) if isinstance(r.get(col),
                        (int, float)) else None for r in rows]
                xf = [x for x, y in zip(xs_raw, vals) if y is not None]
                yf = [y for y in vals if y is not None]
                if xf:
                    color = colors.get(col, "#ffffff")
                    ax.plot(xf, yf, color=color, linewidth=1.2, label=col)
            ax.legend(fontsize=7, loc="upper left",
                      facecolor="#252535", labelcolor="#c0c0e0",
                      edgecolor="#3a3a5c")

        # nascondi assi vuoti se griglia dispari
        for ax_idx in range(len(selected), len(axes)):
            axes[ax_idx].set_visible(False)

        fig.tight_layout(pad=1.5)
        if fmt == "pdf":
            from matplotlib.backends.backend_pdf import PdfPages
            with PdfPages(path) as pdf:
                pdf.savefig(fig, bbox_inches="tight", facecolor=fig.get_facecolor())
        else:
            fig.savefig(path, dpi=150, bbox_inches="tight",
                        facecolor=fig.get_facecolor())
        plt.close(fig)
        self.set_status(f"Esportato: {os.path.basename(path)}")
        messagebox.showinfo("Esportato", f"File salvato:\n{path}")

    def _live_export_pdf(self):
        """Esporta il/i grafico/i come PDF. In multi: finestra selezione."""
        if not self._live_rows:
            messagebox.showinfo("Esporta", "Nessun dato da esportare.")
            return
        if self._live_multi_mode and self._live_multi_ipcs:
            self._live_export_multi_dialog("pdf")
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                title="Salva grafico live come PDF",
                initialfile="live_plot.pdf")
            if not path:
                return
            try:
                from matplotlib.backends.backend_pdf import PdfPages
                fig = self._live_ipc._fig
                with PdfPages(path) as pdf:
                    pdf.savefig(fig, bbox_inches="tight",
                                facecolor=fig.get_facecolor())
                self.set_status(f"PDF salvato: {os.path.basename(path)}")
                messagebox.showinfo("Esportato", f"PDF salvato:\n{path}")
            except Exception as e:
                messagebox.showerror("Errore PDF", str(e))

    def set_status(self, msg): self.status_lbl.configure(text=msg)


    # ══════════════════════════════════════════════════════════════════════
    # TAB LIVE DATA
    # ══════════════════════════════════════════════════════════════════════

    def _build_live_tab(self, parent):
        """Tab per monitoraggio live: seriale reale o simulazione CSV."""

        # ══════════════════════════════════════════════════════════════
        # TOOLBAR (scrollabile orizzontalmente se la finestra è stretta)
        # ══════════════════════════════════════════════════════════════
        toolbar_wrap = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        toolbar_wrap.pack(fill="x", side="top", padx=4, pady=(4, 0))

        # ── riga 1: sorgente + CSV + porte ───────────────────────────
        row1 = ctk.CTkFrame(toolbar_wrap, fg_color=COLORS["surface"], corner_radius=8)
        row1.pack(fill="x", pady=(0, 3))

        ctk.CTkLabel(row1, text="Sorgente", font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(side="left", padx=10, pady=8)

        self._live_src_var = ctk.StringVar(value="Simulazione CSV")
        src_opts = ["Simulazione CSV"]
        if SERIAL_AVAILABLE:
            src_opts.append("Seriale")
        self._live_src_menu = ctk.CTkOptionMenu(
            row1, variable=self._live_src_var, values=src_opts, width=150,
            fg_color=COLORS["surface2"], button_color=COLORS["accent"],
            text_color=COLORS["text"], command=self._live_on_source_change)
        self._live_src_menu.pack(side="left", padx=6, pady=8)

        # porta seriale (nascosta di default)
        self._live_port_lbl = ctk.CTkLabel(row1, text="Porta",
                                           font=("Segoe UI", 10, "bold"),
                                           text_color=COLORS["text2"])
        self._live_port_var = ctk.StringVar(value="")
        self._live_port_menu = ctk.CTkOptionMenu(
            row1, variable=self._live_port_var, values=["—"],
            width=120, fg_color=COLORS["surface2"],
            button_color=COLORS["accent"], text_color=COLORS["text"])
        self._live_baud_lbl = ctk.CTkLabel(row1, text="Baud",
                                           font=("Segoe UI", 10, "bold"),
                                           text_color=COLORS["text2"])
        self._live_baud_var = ctk.StringVar(value="9600")
        self._live_baud_entry = ctk.CTkEntry(
            row1, textvariable=self._live_baud_var,
            width=65, fg_color=COLORS["surface2"], text_color=COLORS["text"])
        self._live_refresh_btn = ctk.CTkButton(
            row1, text="↻", width=28, height=26,
            fg_color=COLORS["surface2"], hover_color=COLORS["border"],
            text_color=COLORS["text"], command=self._live_refresh_ports)

        # CSV simulazione
        self._live_csv_path = None
        ctk.CTkButton(row1, text="📂 CSV", width=80, height=26,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 10),
                      command=self._live_open_csv).pack(side="left", padx=4, pady=8)
        self._live_csv_lbl = ctk.CTkLabel(row1, text="Nessun file",
                                          font=("Segoe UI", 9),
                                          text_color=COLORS["text2"])
        self._live_csv_lbl.pack(side="left", padx=4)

        ctk.CTkButton(row1, text="↻ Porte", width=80, height=26,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 9),
                      command=self._live_refresh_ports).pack(side="right", padx=8, pady=8)

        # ── riga 3: controlli compatti ────────────────────────────────
        row3 = ctk.CTkFrame(toolbar_wrap, fg_color=COLORS["surface"], corner_radius=8)
        row3.pack(fill="x", pady=(0, 3))

        # ── riga 3a: bottoni azione principali ───────────────────────────
        # pulsanti azione rotondi con icona
        RBTN = dict(width=44, height=44, corner_radius=22,
                    font=("Segoe UI", 18), text_color=COLORS["text"])
        self._live_start_btn = ctk.CTkButton(
            row3, text="▶", fg_color=COLORS["info"],
            hover_color="#3a9a10", **RBTN,
            command=self._live_start)
        self._live_start_btn.pack(side="left", padx=(8, 4), pady=6)

        self._live_stop_btn = ctk.CTkButton(
            row3, text="⏹", fg_color=COLORS["error"],
            hover_color="#cc2a2c", **RBTN,
            state="disabled", command=self._live_stop)
        self._live_stop_btn.pack(side="left", padx=4, pady=6)

        self._live_pause_btn = ctk.CTkButton(
            row3, text="⏸", fg_color=COLORS["warn"],
            hover_color="#c87d00", **RBTN,
            state="disabled", command=self._live_toggle_pause)
        self._live_pause_btn.pack(side="left", padx=4, pady=6)

        SBTN = dict(height=28, font=("Segoe UI", 9), text_color=COLORS["text"],
                    fg_color=COLORS["surface2"], hover_color=COLORS["border"])
        ctk.CTkButton(row3, text="Pulisci", width=65, **SBTN,
                      command=self._live_clear).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="↓ CSV", width=60, **SBTN,
                      command=self._live_export_csv).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="↓ PNG", width=60, **SBTN,
                      command=self._live_export_png).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="↓ PDF", width=60, **SBTN,
                      command=self._live_export_pdf).pack(side="left", padx=3, pady=7)
        ctk.CTkButton(row3, text="✕ Δ", width=46, **SBTN,
                      command=self._live_reset_cursors).pack(side="left", padx=3, pady=7)

        self._live_multi_btn = ctk.CTkButton(
            row3, text="⊞ Multi", width=72, height=28,
            fg_color=COLORS["surface2"], hover_color=COLORS["accent"],
            text_color=COLORS["text"], font=("Segoe UI", 9),
            command=self._live_toggle_multi)
        self._live_multi_btn.pack(side="left", padx=3, pady=7)

        # separatore
        ctk.CTkFrame(row3, width=1, height=24,
                     fg_color=COLORS["border"]).pack(side="left", padx=6, pady=7)

        # ── parametri (parte destra row3) ────────────────────────────────
        LBL = dict(font=("Segoe UI", 9), text_color=COLORS["text2"])
        ctk.CTkLabel(row3, text="Max pt", **LBL).pack(side="left", padx=(2, 2))
        self._live_maxpts_var = ctk.StringVar(value="500")
        ctk.CTkEntry(row3, textvariable=self._live_maxpts_var, width=48,
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     height=26).pack(side="left", padx=(0, 4))

        ctk.CTkLabel(row3, text="Vel", **LBL).pack(side="left", padx=(4, 2))
        self._live_speed_var = ctk.StringVar(value="1x")
        self._live_speed_snapshot = "1x"

        def _on_speed_change(val):
            # aggiorna snapshot nel thread UI — il sim thread legge solo snapshot
            self._live_speed_snapshot = val

        ctk.CTkOptionMenu(row3, variable=self._live_speed_var,
                          values=["0.25x", "0.5x", "1x", "2x", "5x", "10x",
                                  "15x", "20x", "30x", "60x", "100x", "MAX"],
                          width=75, height=26,
                          fg_color=COLORS["surface2"], button_color=COLORS["accent"],
                          text_color=COLORS["text"],
                          command=_on_speed_change).pack(side="left", padx=(0, 6))

        self._live_interp_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row3, text="Interp", variable=self._live_interp_var,
                        font=("Segoe UI", 9), text_color=COLORS["text2"],
                        fg_color=COLORS["accent"], hover_color="#5a52e0",
                        checkmark_color=COLORS["text"],
                        width=16, height=16).pack(side="left", padx=(0, 8))

        self._live_show_pts_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row3, text="Punti", variable=self._live_show_pts_var,
                        font=("Segoe UI", 9), text_color=COLORS["text2"],
                        fg_color=COLORS["accent"], hover_color="#5a52e0",
                        checkmark_color=COLORS["text"],
                        width=16, height=16,
                        command=self._live_toggle_markers).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(row3, text="Rate", **LBL).pack(side="left", padx=(4, 2))
        self._live_rate_var = ctk.StringVar(value="500")
        ctk.CTkEntry(row3, textvariable=self._live_rate_var, width=52,
                     fg_color=COLORS["surface2"], text_color=COLORS["text"],
                     height=26).pack(side="left")
        ctk.CTkLabel(row3, text="ms", **LBL).pack(side="left", padx=(2, 8))

        self._live_status_lbl = ctk.CTkLabel(
            row3, text="● In attesa", font=("Segoe UI", 10),
            text_color=COLORS["text2"])
        self._live_status_lbl.pack(side="left", padx=8)

        # ── riga contatori ────────────────────────────────────────────
        cnt_row = ctk.CTkFrame(toolbar_wrap, fg_color=COLORS["surface"], corner_radius=8)
        cnt_row.pack(fill="x", pady=(0, 3))
        self._live_cnt_lbl = ctk.CTkLabel(
            cnt_row, text="Campioni: 0  |  In coda: 0",
            font=("Courier New", 10), text_color=COLORS["accent2"])
        self._live_cnt_lbl.pack(side="left", padx=14, pady=5)
        self._live_alarm_badge = ctk.CTkLabel(
            cnt_row, text="", font=("Segoe UI", 10, "bold"),
            text_color=COLORS["error"])
        self._live_alarm_badge.pack(side="left", padx=10, pady=5)
        self._live_col_btns = []  # inizializzato qui, sidebar creata nel body

        # ══════════════════════════════════════════════════════════════
        # BODY: colonne Y (sx, fisso) | grafico (centro, espanso) | allarmi (dx, fisso)
        # ══════════════════════════════════════════════════════════════
        body = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # ── pannello allarmi (destra, fisso 220px) ────────────────────
        right = ctk.CTkFrame(body, fg_color=COLORS["surface"],
                             corner_radius=8, width=220)
        right.pack(side="right", fill="y", padx=(4, 0), pady=0)
        right.pack_propagate(False)

        alarm_hdr = ctk.CTkFrame(right, fg_color="transparent")
        alarm_hdr.pack(fill="x", padx=8, pady=(8, 2))
        ctk.CTkLabel(alarm_hdr, text="⚠ Allarmi live",
                     font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text2"]).pack(side="left")
        ctk.CTkButton(alarm_hdr, text="+ Soglia", width=70, height=22,
                      fg_color=COLORS["accent"], hover_color="#5a52e0",
                      text_color=COLORS["text"], font=("Segoe UI", 9),
                      command=self._live_add_alarm_rule).pack(side="right")
        ctk.CTkButton(alarm_hdr, text="Azzera", width=58, height=22,
                      fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      command=self._live_reset_alarms).pack(side="right", padx=4)

        self._live_alarm_rules_frame = ctk.CTkScrollableFrame(
            right, fg_color=COLORS["surface2"],
            orientation="vertical", corner_radius=4)
        self._live_alarm_rules_frame.pack(fill="both", expand=True,
                                          padx=8, pady=(2, 8))
        _isolate_scroll(self._live_alarm_rules_frame)
        self._live_alarm_cards_ui = []

        # ── sidebar Colonne Y (sinistra, fisso 110px) ─────────────────
        col_sidebar = ctk.CTkFrame(body, fg_color=COLORS["surface"],
                                   corner_radius=8, width=145)
        col_sidebar.pack(side="left", fill="y", padx=(0, 4), pady=0)
        col_sidebar.pack_propagate(False)

        ctk.CTkLabel(col_sidebar, text="Colonne Y",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(8, 2))

        btn_row = ctk.CTkFrame(col_sidebar, fg_color="transparent")
        btn_row.pack(anchor="w", padx=6, pady=(0, 4))
        ctk.CTkButton(btn_row, text="✓", width=36, height=18,
                      fg_color=COLORS["surface2"], hover_color=COLORS["accent"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      corner_radius=4,
                      command=self._live_sel_all).pack(side="left", padx=(0, 2))
        ctk.CTkButton(btn_row, text="✗", width=36, height=18,
                      fg_color=COLORS["surface2"], hover_color=COLORS["error"],
                      text_color=COLORS["text2"], font=("Segoe UI", 9),
                      corner_radius=4,
                      command=self._live_sel_none).pack(side="left")

        self._live_col_scroll = ctk.CTkScrollableFrame(
            col_sidebar, fg_color="transparent",
            orientation="vertical", corner_radius=0)
        self._live_col_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        _isolate_scroll(self._live_col_scroll)

        # ── pannello centro: grafico + log ────────────────────────────
        left = ctk.CTkFrame(body, fg_color=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True)

        # ── log messaggi (prima del grafico così non viene schiacciato) ──
        log_frame = ctk.CTkFrame(left, fg_color=COLORS["surface"], corner_radius=8)
        log_frame.pack(fill="x", side="bottom", pady=(4, 0))
        ctk.CTkLabel(log_frame, text="Log",
                     font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text2"]).pack(anchor="w", padx=8, pady=(4, 0))
        self._live_log_box = ctk.CTkTextbox(
            log_frame, height=75, font=("Courier New", 9),
            fg_color=COLORS["surface2"], text_color=COLORS["text"],
            border_width=0, state="disabled")
        self._live_log_box.pack(fill="x", padx=6, pady=(2, 6))

        # ── grafico live — swap pulito con pack/pack_forget ───────────────
        self._live_graph_container = ctk.CTkFrame(left, fg_color=COLORS["bg"])
        self._live_graph_container.pack(fill="both", expand=True)

        # frame multi — non pakkato all'avvio, appare solo con Multi ON
        self._live_multi_holder = ctk.CTkFrame(
            self._live_graph_container, fg_color=COLORS["bg"])

        # frame singolo — occupa tutto lo spazio all'avvio
        self._live_plot_frame = ctk.CTkFrame(
            self._live_graph_container, fg_color=COLORS["bg"])
        self._live_plot_frame.pack(fill="both", expand=True)
        self._live_ipc = InteractivePlotCanvas(self._live_plot_frame, height=380)

    # ── Multi-grafico ────────────────────────────────────────────────────
    _MULTI_GROUPS = [
        ("Temp. Superiore", lambda c: c.upper().startswith("TS")),
        ("Temp. Inferiore", lambda c: c.upper().startswith("TI")),
        ("Temperatura",     lambda c: c.upper().startswith("T") and not c.upper().startswith("TS") and not c.upper().startswith("TI")),
        ("Forza",           lambda c: c.upper().startswith("F")),
        ("Posizione",       lambda c: c.upper().startswith("P")),
        ("Vuoto",           lambda c: c.upper().startswith("V")),
    ]

    def _live_group_cols(self, cols):
        """Raggruppa le colonne per grandezza fisica."""
        groups = {}
        assigned = set()
        for name, predicate in self._MULTI_GROUPS:
            matched = [c for c in cols if predicate(c) and c not in assigned]
            if matched:
                groups[name] = matched
                assigned.update(matched)
        remaining = [c for c in cols if c not in assigned]
        if remaining:
            groups["Altri"] = remaining
        return groups

    def _live_toggle_multi(self):
        self._live_multi_mode = not self._live_multi_mode
        if self._live_multi_mode:
            self._live_multi_btn.configure(
                fg_color=COLORS["accent"], text="⊞ Multi ON")
            # Fix: se la singola è in play/pausa, fermala prima di entrare in multi
            if self._live_running.is_set() or self._live_paused.is_set():
                self._live_stop()
            self._live_build_multi()
        else:
            self._live_multi_btn.configure(
                fg_color=COLORS["surface2"], text="⊞ Multi")
            self._live_destroy_multi()

    def _live_build_multi(self):
        """Costruisce vista multi a 2 colonne con overlay di caricamento."""
        if hasattr(self, "_live_multi_frame"):
            try: self._live_multi_frame.destroy()
            except Exception: pass
            try: del self._live_multi_frame
            except Exception: pass
        self._live_multi_ipcs = {}

        cols = self._live_numeric_cols
        if not cols:
            self._live_multi_mode = False
            self._live_multi_btn.configure(fg_color=COLORS["surface2"], text="⊞ Multi")
            return
        groups = self._live_group_cols(cols)
        if len(groups) <= 1:
            self._live_multi_mode = False
            self._live_multi_btn.configure(fg_color=COLORS["surface2"], text="⊞ Multi")
            return

        # disabilita tasti principali
        self._live_start_btn.configure(state="disabled")
        self._live_pause_btn.configure(state="disabled")
        self._live_stop_btn.configure(state="disabled")

        # swap: nascondi singolo, mostra holder
        self._live_plot_frame.pack_forget()
        for w in self._live_multi_holder.winfo_children():
            try: w.destroy()
            except Exception: pass
        self._live_multi_holder.pack(fill="both", expand=True)

        # ── overlay "Caricamento..." visibile subito ──────────────────
        loading_frame = ctk.CTkFrame(
            self._live_multi_holder, fg_color=COLORS["bg"])
        loading_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(loading_frame,
                     text="⟳  Caricamento grafici...",
                     font=("Segoe UI", 14), text_color=COLORS["text2"]
                     ).place(relx=0.5, rely=0.5, anchor="center")
        self._live_multi_holder.update_idletasks()

        # ── costruisce struttura celle (senza IPC, solo widget UI) ────
        self._live_multi_frame = ctk.CTkScrollableFrame(
            self._live_multi_holder,
            fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        _isolate_scroll(self._live_multi_frame)

        groups_list = list(groups.items())
        show_pts = getattr(self, "_live_show_pts_var",
                           ctk.BooleanVar(value=True)).get()

        # mappa {group_name: (cell_frame, group_cols, state)}
        cell_data = {}
        for row_i in range(0, len(groups_list), 2):
            row_frame = ctk.CTkFrame(self._live_multi_frame, fg_color=COLORS["bg"])
            row_frame.pack(fill="x", pady=4)
            row_frame.columnconfigure(0, weight=1)
            row_frame.columnconfigure(1, weight=1)

            for col_i in range(2):
                idx = row_i + col_i
                if idx >= len(groups_list):
                    break
                group_name, group_cols = groups_list[idx]

                cell = ctk.CTkFrame(row_frame, fg_color=COLORS["surface"],
                                    corner_radius=8)
                cell.grid(row=0, column=col_i, sticky="nsew", padx=3)

                hdr = ctk.CTkFrame(cell, fg_color="transparent")
                hdr.pack(fill="x", padx=6, pady=(4, 0))
                ctk.CTkLabel(hdr, text=group_name,
                             font=("Segoe UI", 9, "bold"),
                             text_color=COLORS["accent2"]).pack(side="left")

                state = {"active": False, "paused": False}
                MBTN = dict(width=22, height=22, corner_radius=11,
                            font=("Segoe UI", 10), text_color=COLORS["text"])
                stop_btn  = ctk.CTkButton(hdr, text="⏹",
                                          fg_color=COLORS["error"],
                                          hover_color="#cc2a2c", **MBTN)
                pause_btn = ctk.CTkButton(hdr, text="⏸",
                                          fg_color=COLORS["warn"],
                                          hover_color="#c87d00", **MBTN)
                play_btn  = ctk.CTkButton(hdr, text="▶",
                                          fg_color=COLORS["surface2"],
                                          hover_color="#3a9a10", **MBTN)

                def _make_ctrl(st=state, pb=play_btn, psb=pause_btn):
                    def _play():
                        st["active"] = True; st["paused"] = False
                        pb.configure(fg_color=COLORS["info"])
                        psb.configure(fg_color=COLORS["warn"])
                        if not self._live_running.is_set():
                            self._live_start()
                        elif self._live_paused.is_set():
                            # Fix: era in pausa globale → riprendi il thread
                            self._live_paused.clear()
                    def _pause():
                        st["paused"] = not st["paused"]
                        psb.configure(fg_color=COLORS["accent"]
                                      if st["paused"] else COLORS["warn"])
                    def _stop():
                        st["active"] = False; st["paused"] = False
                        pb.configure(fg_color=COLORS["surface2"])
                        psb.configure(fg_color=COLORS["warn"])
                        all_stopped = all(
                            not e[2].get("active")
                            for e in self._live_multi_ipcs.values())
                        if all_stopped and self._live_running.is_set():
                            self._live_stop()
                    return _play, _pause, _stop

                pf, psf, sf = _make_ctrl()
                play_btn.configure(command=pf)
                pause_btn.configure(command=psf)
                stop_btn.configure(command=sf)
                stop_btn.pack(side="right", padx=(0, 4), pady=4)
                pause_btn.pack(side="right", padx=2, pady=4)
                play_btn.pack(side="right", padx=2, pady=4)

                cell_data[group_name] = (cell, hdr, group_cols, state)

        # ── crea IPC uno per volta via after() — UI rimane responsiva ─
        groups_todo = list(cell_data.items())

        def _build_next(idx):
            if idx >= len(groups_todo):
                # tutti costruiti: rimuovi overlay, mostra grafici
                try: loading_frame.destroy()
                except Exception: pass
                self._live_multi_frame.pack(fill="both", expand=True)
                if self._live_rows:
                    self._live_refresh_plot()
                return

            group_name, (cell, hdr, group_cols, state) = groups_todo[idx]

            ipc = InteractivePlotCanvas(cell, height=220)
            ipc.show_markers = show_pts

            def _make_delta_reset(i):
                def _reset():
                    i._cur_a = None; i._cur_b = None
                    i._redraw_cursors_ab()
                    i._canvas.draw()
                    i._bg_cache = i._canvas.copy_from_bbox(i._fig.bbox)
                return _reset

            ctk.CTkButton(
                hdr, text="✕Δ", width=26, height=22,
                fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                text_color=COLORS["text2"], font=("Segoe UI", 8),
                corner_radius=4,
                command=_make_delta_reset(ipc)).pack(side="right", padx=(0, 2), pady=4)

            def _make_png(i=ipc, gn=group_name):
                def _export():
                    p = filedialog.asksaveasfilename(
                        defaultextension=".png",
                        filetypes=[("PNG", "*.png")],
                        initialfile=f"live_{gn.replace(' ','_')}.png")
                    if p:
                        try: i.export_png(p); self.set_status(f"PNG: {os.path.basename(p)}")
                        except Exception as e: messagebox.showerror("Errore PNG", str(e))
                return _export

            ctk.CTkButton(
                hdr, text="↓PNG", width=36, height=22,
                fg_color=COLORS["surface2"], hover_color=COLORS["border"],
                text_color=COLORS["text2"], font=("Segoe UI", 8),
                corner_radius=4,
                command=_make_png()).pack(side="right", padx=2, pady=4)

            self._live_multi_ipcs[group_name] = (ipc, group_cols, state)
            # prossimo IPC dopo 50ms — lascia il ciclo eventi respirare
            self.after(50, lambda i=idx+1: _build_next(i))

        # avvia la costruzione al prossimo ciclo eventi
        self.after(10, lambda: _build_next(0))

    def _live_destroy_multi(self):
        """Rimuove multi e ripristina grafico singolo."""
        # Fix: ferma il thread se ancora in corsa (grafici multi attivi)
        if self._live_running.is_set() or self._live_paused.is_set():
            self._live_stop()
        # distruggi multi PRIMA di re-pack plot_frame
        # così plot_frame è l'unico figlio → pack order corretto
        if hasattr(self, "_live_multi_frame"):
            try: self._live_multi_frame.destroy()
            except Exception: pass
            try: del self._live_multi_frame
            except Exception: pass
        self._live_multi_ipcs = {}

        # swap: nascondi holder, ripristina singolo
        self._live_multi_holder.pack_forget()
        self._live_plot_frame.pack(fill="both", expand=True)

        # ── riabilita tasti principali in base allo stato simulazione ────
        if self._live_running.is_set():
            self._live_start_btn.configure(state="disabled")
            self._live_stop_btn.configure(state="normal")
            self._live_pause_btn.configure(state="normal")
        else:
            self._live_start_btn.configure(state="normal")
            self._live_stop_btn.configure(state="disabled")
            self._live_pause_btn.configure(state="disabled")

        self._live_ipc._needs_full_redraw = True
        if self._live_rows:
            self.after(50, self._live_refresh_plot)

    # ── helper sorgente ──────────────────────────────────────────────────
    def _live_on_source_change(self, val):
        """Mostra i controlli seriale solo se la sorgente è 'Seriale'."""
        if val == "Seriale":
            self._live_port_lbl.pack(side="left", padx=(12, 2), pady=10)
            self._live_port_menu.pack(side="left", padx=4, pady=10)
            self._live_baud_lbl.pack(side="left", padx=(8, 2), pady=10)
            self._live_baud_entry.pack(side="left", padx=4, pady=10)
            self._live_refresh_btn.pack(side="left", padx=2, pady=10)
            self._live_refresh_ports()
        else:
            self._live_port_lbl.pack_forget()
            self._live_port_menu.pack_forget()
            self._live_baud_lbl.pack_forget()
            self._live_baud_entry.pack_forget()
            self._live_refresh_btn.pack_forget()

    def _live_refresh_ports(self):
        if not SERIAL_AVAILABLE:
            return
        try:
            ports = [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            ports = []
        if not ports:
            ports = ["—"]
        self._live_port_menu.configure(values=ports)
        self._live_port_var.set(ports[0])

    def _live_open_csv(self):
        path = filedialog.askopenfilename(
            title="Seleziona CSV per simulazione",
            filetypes=[("CSV", "*.csv"), ("Tutti", "*.*")])
        if not path:
            return
        self._live_csv_path = path
        self._live_csv_lbl.configure(text=os.path.basename(path))
        self._live_log_append(f"CSV simulazione: {path}")

        # ── reset COMPLETO stato colonne (fix: CSV precedente non spariva) ──
        self._live_headers      = []
        self._live_col_meta     = {}
        self._live_numeric_cols = []
        self._live_plot_cols    = []
        # distruggi tutti i widget figli rimasti nel frame scorrevole
        for w in self._live_col_scroll.winfo_children():
            try: w.destroy()
            except Exception: pass
        self._live_col_btns.clear()

        self._live_set_status("Caricamento CSV…", COLORS["text2"])

        def _load():
            try:
                if _is_long_cycle_csv(path):
                    _, headers, col_meta, numeric_cols, _, _, _, _ = \
                        _parse_long_cycle_csv(path)
                    long_fmt = True
                else:
                    _, headers, col_meta, numeric_cols, _, _, _, _ = \
                        parse_universal_csv(path)
                    long_fmt = False
                def _apply():
                    if long_fmt:
                        self._live_log_append(
                            "Formato rilevato: Long CSV (Cannon/Persico/Krauss Maffei)")
                    self._live_headers      = headers
                    self._live_col_meta     = col_meta
                    self._live_numeric_cols = numeric_cols
                    self._live_plot_cols    = list(numeric_cols[:8])
                    self._live_rebuild_col_buttons()
                    self._live_log_append(
                        f"Colonne numeriche: {len(numeric_cols)} — "
                        f"{', '.join(numeric_cols[:12])}")
                    self._live_set_status("CSV pronto.", COLORS["info"])
                self.after(0, _apply)
            except Exception as e:
                self.after(0, self._live_log_append, f"Errore lettura CSV: {e}")
                self.after(0, self._live_set_status,
                           "Errore caricamento CSV.", COLORS["warn"])

        threading.Thread(target=_load, daemon=True).start()

    def _live_rebuild_col_buttons(self):
        for w in self._live_col_btns:
            try: w.destroy()
            except Exception: pass
        self._live_col_btns.clear()
        for w in self._live_col_scroll.winfo_children():
            try: w.destroy()
            except Exception: pass

        palette = list(_UC_SERIES_PALETTE)
        for i, col in enumerate(self._live_numeric_cols):
            color = palette[i % len(palette)]
            is_sel = col in self._live_plot_cols
            var = tk.BooleanVar(value=is_sel)

            row_f = ctk.CTkFrame(self._live_col_scroll, fg_color="transparent")
            row_f.pack(fill="x", pady=1)

            # pallino colorato
            dot = tk.Canvas(row_f, width=12, height=12,
                            bg=COLORS["surface"], highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=color, outline="")
            dot.pack(side="left", padx=(2, 2), pady=4)

            label = col if len(col) <= 10 else col[:9] + "…"

            def _make_cmd(c=col, v=var):
                def _cmd():
                    if v.get():
                        if c not in self._live_plot_cols:
                            self._live_plot_cols.append(c)
                    else:
                        if len(self._live_plot_cols) > 1 and c in self._live_plot_cols:
                            self._live_plot_cols.remove(c)
                        else:
                            v.set(True)  # mantieni almeno una
                return _cmd

            cb = ctk.CTkCheckBox(
                row_f, text=label, variable=var,
                font=("Segoe UI", 9), text_color=COLORS["text"],
                fg_color=color, hover_color=color,
                checkmark_color="#fff",
                border_color=COLORS["border"],
                width=16, height=16,
                command=_make_cmd(col, var))
            cb.pack(side="left", fill="x", expand=True)
            self._live_col_btns.append(row_f)

    def _live_sel_all(self):
        self._live_plot_cols = list(self._live_numeric_cols)
        self._live_rebuild_col_buttons()

    def _live_sel_none(self):
        if self._live_numeric_cols:
            self._live_plot_cols = [self._live_numeric_cols[0]]
        self._live_rebuild_col_buttons()

    def _live_toggle_col(self, col):
        if col in self._live_plot_cols:
            if len(self._live_plot_cols) > 1:
                self._live_plot_cols.remove(col)
        else:
            self._live_plot_cols.append(col)
        self._live_rebuild_col_buttons()

    # ── start / stop ─────────────────────────────────────────────────────
    def _live_start(self):
        if self._live_running.is_set():
            return
        src = self._live_src_var.get()

        # ── blocca se simulazione CSV senza file caricato ──
        if src == "Simulazione CSV" and not self._live_csv_path:
            messagebox.showwarning(
                "Nessun file",
                "Carica prima un CSV tramite il pulsante «CSV simulazione».")
            return

        # ── reset completo ad ogni avvio ─────────────────────────────────
        self._live_rows.clear()
        self._live_ipc.clear()
        self._live_ipc._needs_full_redraw = True
        # Fix: resetta zoom degli IPC multi al riavvio
        if self._live_multi_mode:
            for ipc, _, __ in self._live_multi_ipcs.values():
                ipc.reset_zoom()
        self._live_last_cols_set = set()
        self._live_dropped = 0  # Fix 4: reset contatore campioni scartati
        self._live_log_box.configure(state="normal")
        self._live_log_box.delete("1.0", "end")
        self._live_log_box.configure(state="disabled")
        self._live_cnt_lbl.configure(text="Campioni: 0  |  In coda: 0")
        self._live_alarm_active.clear()
        self._live_alarm_count = 0
        self._live_alarm_badge.configure(text="")
        # svuota coda residua dal run precedente
        while not self._live_queue.empty():
            try: self._live_queue.get_nowait()
            except _queue.Empty: break

        # Fix 1 — thread zombie: aspetta terminazione, poi verifica
        if self._live_thread is not None and self._live_thread.is_alive():
            self._live_running.clear()
            self._live_ipc._live_user_zoomed = False  # reset zoom dopo pausa
            self._live_thread.join(timeout=2.0)
            if self._live_thread.is_alive():
                # thread non terminato: rinuncia all'avvio per sicurezza
                messagebox.showwarning("Attenzione",
                    "Thread precedente non terminato. Riprova tra un momento.")
                self._live_running.clear()
                return

        # svuota coda residua in modo sicuro (Fix race condition)
        try:
            while True:
                self._live_queue.get_nowait()
        except _queue.Empty:
            pass
                
        # 🔄 RESET automatico zoom al PLAY
        self._live_ipc.reset_zoom()
        self._live_ipc._live_user_zoomed = False  # Fix zoom: reset flag al PLAY
        self._live_ipc.clear_cursors()
        self._live_ipc._needs_full_redraw = True
        self._live_running.set()
        self._live_paused.clear()
        self._live_start_btn.configure(state="disabled")
        self._live_stop_btn.configure(state="normal")
        self._live_pause_btn.configure(state="normal", text="⏸",
                                       fg_color=COLORS["warn"])

        # Fix 4 — leggi StringVar nel thread UI prima di avviare il thread background
        self._live_speed_snapshot = self._live_speed_var.get()

        if src == "Simulazione CSV":
            self._live_sim_random = False
            self._live_thread = threading.Thread(
                target=self._live_sim_thread, daemon=True)
        else:
            port = self._live_port_var.get()
            try:
                baud = int(self._live_baud_var.get())
            except Exception:
                baud = 9600
            self._live_thread = threading.Thread(
                target=self._live_serial_thread,
                args=(port, baud), daemon=True)

        self._live_thread.start()
        self._live_set_status("● Acquisizione in corso", COLORS["info"])
        self._live_poll()

    def _live_stop(self):
        self._live_running.clear()
        self._live_paused.clear()
        self._live_stop_interp_timer()
        self._live_start_btn.configure(state="normal")
        self._live_stop_btn.configure(state="disabled")
        self._live_pause_btn.configure(state="disabled", text="⏸",
                                       fg_color=COLORS["warn"])
        self._live_set_status("● Fermato", COLORS["warn"])

    def _live_toggle_pause(self):
        if not self._live_running.is_set():
            return
        if self._live_paused.is_set():
            self._live_paused.clear()
            self._live_ipc._live_user_zoomed = False  # Fix zoom: reset flag alla ripresa
            self._live_ipc.reset_zoom()               # Fix zoom: ritorna alla vista completa
        else:
            self._live_paused.set()
        if self._live_paused.is_set():
            self._live_pause_btn.configure(text="▶",
                                           fg_color=COLORS["info"],
                                           hover_color="#3a9a10")
            self._live_set_status("⏸ In pausa", COLORS["warn"])
        else:
            self._live_pause_btn.configure(text="⏸",
                                           fg_color=COLORS["warn"],
                                           hover_color="#c87d00")
            self._live_set_status("● Acquisizione in corso", COLORS["info"])

    def _live_clear(self):
        _was_running = self._live_running.is_set()
        if _was_running:
            self._live_running.clear()
        self._live_stop_interp_timer()
        self._live_rows.clear()
        self._live_dropped = 0  # B2x: reset contatore scartati ad ogni clear
        try:
            while True: self._live_queue.get_nowait()
        except Exception: pass
        if self._live_multi_mode:
            for ipc, _, __ in self._live_multi_ipcs.values():
                ipc.clear(); ipc._needs_full_redraw = True
        else:
            self._live_ipc.clear()
        self._live_log_box.configure(state="normal")
        self._live_log_box.delete("1.0", "end")
        self._live_log_box.configure(state="disabled")
        self._live_cnt_lbl.configure(text="Campioni: 0  |  In coda: 0")
        self._live_alarm_active.clear()
        self._live_alarm_count = 0
        self._live_alarm_badge.configure(text="")
        self._live_rebuild_alarm_cards()
        if _was_running:
            self.after(400, self._live_start)

    # — thread simulazione CSV ──────────────────────────────────────────
    def _live_sim_thread(self):
        """Delega a live_monitor.live_sim_thread, riusando self._live_queue."""
        from mouldgraph.live_monitor import live_sim_thread
        live_sim_thread(
            random, _queue, self._live_running, self._live_paused,
            lambda: getattr(self, "_live_speed_snapshot", "1x"),
            getattr(self, "_live_sim_random", True), self._live_csv_path,
            _is_long_cycle_csv, _parse_long_cycle_csv, parse_universal_csv,
            _uc_try_float, _uc_parse_dt,
            on_log=lambda msg: self.after(0, self._live_log_append, msg),
            existing_queue=self._live_queue,
        )

    # — thread seriale reale ──────────────────────────────────────────
    def _live_serial_thread(self, port, baud):
        """Delega a live_monitor.live_serial_thread, riusando self._live_queue."""
        from mouldgraph.live_monitor import live_serial_thread
        live_serial_thread(
            serial if SERIAL_AVAILABLE else None, _queue, port, baud,
            self._live_running, self._live_parse_line,
            on_open_log=lambda msg: self.after(0, self._live_log_append, msg),
            on_error_status=lambda msg: self.after(0, self._live_set_status, msg, COLORS["warn"]),
            existing_queue=self._live_queue,
        )

    def _live_parse_line(self, line):
        """Parsa una riga CSV o key=val da seriale."""
        from mouldgraph.live_monitor import parse_live_line
        return parse_live_line(line, self._live_headers)

    # ── polling UI ───────────────────────────────────────────────────────
    def _live_poll(self):
        if not self._live_running.is_set():
            return
        drained = 0
        last_row = None
        while drained < 100:  # max 100 campioni per tick per non bloccare la UI
            try:
                row = self._live_queue.get_nowait()
            except _queue.Empty:
                break
            drained += 1
            if "_error" in row:
                self._live_log_append(f"ERRORE: {row['_error']}")
                self._live_stop()
                return
            self._live_rows.append(row)
            # C2: finestra scorrevole — memoria bounded, non cresce infinitamente
            if len(self._live_rows) > MAX_LIVE_POINTS:
                del self._live_rows[:-MAX_LIVE_POINTS]
            # aggiorna col_meta e plot_cols automaticamente
            for k, v in row.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, (int, float)) and k not in self._live_col_meta:
                    unit, label, col_type = _uc_col_meta(k, ["1.0"])
                    self._live_col_meta[k] = {"unit": unit, "label": label,
                                               "col_type": "numeric"}
                    if k not in self._live_numeric_cols:
                        self._live_numeric_cols.append(k)
                    if len(self._live_plot_cols) < 8 and k not in self._live_plot_cols:
                        self._live_plot_cols.append(k)
            last_row = row
        # una sola riga di log per tick: valori dell'ultimo campione + conteggio
        if drained > 0 and last_row is not None:
            vals = "  ".join(
                f"{k}={v:.3g}" if isinstance(v, float) else f"{k}={v}"
                for k, v in last_row.items() if not k.startswith("_"))
            self._live_log_append(
                f"+{drained}  {vals}", scroll=False)

        if drained > 0:
            self._live_last_poll_draw = getattr(self, "_live_last_poll_draw", 0)
            import time as _t; self._live_last_poll_draw = _t.monotonic()
            dropped = getattr(self, "_live_dropped", 0)
            drop_txt = f"  |  Scartati: {dropped}" if dropped > 0 else ""
            self._live_cnt_lbl.configure(
                text=f"Campioni: {len(self._live_rows)}  |  In coda: {self._live_queue.qsize()}{drop_txt}")
            if set(self._live_numeric_cols) != getattr(self, "_live_last_cols_set", set()):
                self._live_last_cols_set = set(self._live_numeric_cols)
                self._live_rebuild_col_buttons()
            self._live_check_alarms()
            # Fix 2: se interp attiva, il tick a 200ms è già autoritative per il render
            # il poll aggiorna solo i dati, non ridisegna (elimina doppio redraw 2+5 Hz)
            interp_on = (getattr(self, "_live_interp_var", None) and
                         self._live_interp_var.get() and
                         self._live_interp_job is not None)
            if not interp_on:
                self._live_refresh_plot()

        try:
            ms = max(100, int(self._live_rate_var.get()))
        except Exception:
            ms = 500
        self.after(ms, self._live_poll)

    def _live_refresh_plot(self):
        if not self._live_rows or not self._live_plot_cols:
            return
        try:
            max_pts = int(self._live_maxpts_var.get())
            if max_pts < 10:
                max_pts = 10
        except Exception:
            max_pts = MAX_LIVE_POINTS
        rows = self._live_rows[-max_pts:]

        x_col = None
        for r in rows[:1]:
            if "_ts" in r:
                x_col = "_ts"
            elif "_sim_t" in r:
                x_col = "_sim_t"
        xs_raw = []
        for i, r in enumerate(rows):
            if x_col == "_ts":
                xs_raw.append(r.get("_ts"))
            elif x_col == "_sim_t":
                xs_raw.append(r.get("_sim_t", i))
            else:
                xs_raw.append(i)

        x_type = "datetime" if x_col == "_ts" else "index"
        series = {}
        for col in self._live_plot_cols:
            vals = []
            for r in rows:
                v = r.get(col)
                vals.append(float(v) if isinstance(v, (int, float)) else None)
            series[col] = vals

        # ── mappa colori fissa basata su _live_numeric_cols (combacia con sidebar) ──
        palette = list(_UC_SERIES_PALETTE)
        colors = {col: palette[i % len(palette)]
                  for i, col in enumerate(self._live_numeric_cols)}

        # ── modalità multi-grafico ─────────────────────────────────────
        if self._live_multi_mode and self._live_multi_ipcs:
            # Fix 3: distribuisci i draw nel tempo (20ms offset ciascuno)
            # invece di eseguirli in sequenza bloccante
            active_entries = [
                (ipc, gc, st)
                for _, (ipc, gc, st) in self._live_multi_ipcs.items()
                if st.get("active") and not st.get("paused")]

            def _draw_one(entries, idx, xs=xs_raw, xt=x_type,
                          cm=self._live_col_meta, cl=colors, rw=rows):
                if idx >= len(entries):
                    return
                ipc, gc, st = entries[idx]
                g_series = {col: [float(r.get(col)) if isinstance(r.get(col),
                            (int, float)) else None for r in rw] for col in gc}
                if g_series:
                    ipc._ranges = [r for r in getattr(self, "_live_alarm_rules", [])
                                   if r.get("col") in gc]
                    ipc.update_live(xs, g_series, xt, cm, colors=cl)
                if idx + 1 < len(entries):
                    self.after(20, lambda i=idx+1: _draw_one(entries, i))

            if active_entries:
                _draw_one(active_entries, 0)
            return

        # ── B: redraw incrementale — no clf, no flash ──────────────────
        # aggiorna bande range solo se le regole sono cambiate
        current_rules = getattr(self, "_live_alarm_rules", [])
        if current_rules != getattr(self, "_live_last_rules_snapshot", None):
            self._live_last_rules_snapshot = list(current_rules)
            self._live_ipc._ranges = current_rules
            self._live_ipc._needs_full_redraw = True
        self._live_ipc.update_live(xs_raw, series, x_type,self._live_col_meta, colors=colors)
        
        # ⚡ AUTO-SCROLL live: finestra scorre automaticamente
        if (hasattr(self.master, '_live_running') and self.master._live_running.is_set()
                and not getattr(self._live_ipc, '_live_user_zoomed', False)):
            xs_num = [self._to_num(x) for x in xs_raw if self._to_num(x) is not None]
            if xs_num:
                last_x = max(xs_num)
                xlim = self._live_ipc._ax1.get_xlim()
                width = xlim[1] - xlim[0]
                new_left = max(last_x - width * 0.9, min(xs_num))
                self._live_ipc._ax1.set_xlim(new_left, new_left + width)
                if hasattr(self._live_ipc, '_ax2') and self._live_ipc._ax2: 
                    self._live_ipc._ax2.set_xlim(new_left, new_left + width)
        

        # ── A: avvia/ferma il timer interpolazione in base alla checkbox ─
        if getattr(self, "_live_interp_var", None) and self._live_interp_var.get():
            self._live_start_interp_timer()
        else:
            self._live_stop_interp_timer()

    # ── interpolazione (A) ───────────────────────────────────────────────
    def _live_start_interp_timer(self):
        """Avvia il ticker da 200ms per aggiornare il grafico con punti interpolati."""
        if self._live_interp_job is not None:
            return  # già attivo
        self._live_interp_tick()

    def _live_stop_interp_timer(self):
        if self._live_interp_job is not None:
            try: self.after_cancel(self._live_interp_job)
            except Exception: pass
            self._live_interp_job = None

    def _live_interp_tick(self):
        """Ogni 200ms aggiunge un punto interpolato. Fix 2: salta se il poll
        ha già ridisegnato negli ultimi 150ms (evita doppio redraw)."""
        if not self._live_running.is_set():
            self._live_interp_job = None
            return
        if not self._live_rows or len(self._live_rows) < 2:
            self._live_interp_job = self.after(200, self._live_interp_tick)
            return

        # Fix 2: se il poll ha ridisegnato di recente, non ridisegnare di nuovo
        import time as _t
        last_poll = getattr(self, "_live_last_poll_draw", 0)
        if (_t.monotonic() - last_poll) < 0.15:
            self._live_interp_job = self.after(200, self._live_interp_tick)
            return

        last   = self._live_rows[-1]
        prev   = self._live_rows[-2]

        # calcola il delta temporale reale tra gli ultimi due campioni
        def _xval(r):
            if "_ts" in r:   return r["_ts"].timestamp()
            if "_sim_t" in r: return r["_sim_t"]
            return None

        x0 = _xval(prev)
        x1 = _xval(last)
        if x0 is None or x1 is None or x1 <= x0:
            self._live_interp_job = self.after(200, self._live_interp_tick)
            return

        # quanto tempo è passato dal secondo punto
        import time as _time
        now = _time.monotonic()
        # stimiamo la posizione "ora" nel tempo del CSV
        try:
            sf_str = getattr(self, "_live_speed_snapshot", "1x")
            sf = 1.0 if sf_str == "MAX" else float(sf_str.rstrip("x"))
        except Exception:
            sf = 1.0

        elapsed_real = 0.2 * sf   # 200ms reali × velocità
        alpha = min(1.0, elapsed_real / (x1 - x0))  # 0..1

        # costruisce una riga interpolata lineare
        interp_row = {}
        for col in self._live_plot_cols:
            v0 = prev.get(col)
            v1 = last.get(col)
            if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
                interp_row[col] = v0 + (v1 - v0) * alpha
            else:
                interp_row[col] = v1

        # x interpolata
        if "_sim_t" in last:
            interp_row["_sim_t"] = x0 + (x1 - x0) * alpha
        elif "_ts" in last:
            from datetime import timedelta
            interp_row["_ts"] = prev["_ts"] + timedelta(seconds=(x1 - x0) * alpha)

        # costruisce serie da mostrare: rows reali + punto interpolato
        try:
            max_pts = int(self._live_maxpts_var.get())
            if max_pts < 10: max_pts = 10
        except Exception:
            max_pts = MAX_LIVE_POINTS
        rows_disp = self._live_rows[-(max_pts - 1):] + [interp_row]

        x_col = "_ts" if "_ts" in last else ("_sim_t" if "_sim_t" in last else None)
        xs_raw = []
        for i, r in enumerate(rows_disp):
            if x_col == "_ts":    xs_raw.append(r.get("_ts"))
            elif x_col == "_sim_t": xs_raw.append(r.get("_sim_t", i))
            else:                 xs_raw.append(i)

        x_type = "datetime" if x_col == "_ts" else "index"
        series = {}
        for col in self._live_plot_cols:
            vals = [float(r.get(col)) if isinstance(r.get(col), (int, float)) else None
                    for r in rows_disp]
            series[col] = vals

        self._live_ipc.update_live(xs_raw, series, x_type, self._live_col_meta)
        self._live_interp_job = self.after(200, self._live_interp_tick)

    def _live_reset_cursors(self):
        """Azzera i cursori A/B e le linee delta dal grafico."""
        self._live_ipc._cur_a = None
        self._live_ipc._cur_b = None
        self._live_ipc._redraw_cursors_ab()
        self._live_ipc._canvas.draw()
        self._live_ipc._bg_cache = self._live_ipc._canvas.copy_from_bbox(
            self._live_ipc._fig.bbox)

    def _live_toggle_markers(self):
        v = self._live_show_pts_var.get()
        self._live_ipc.show_markers = v
        self._live_ipc._needs_full_redraw = True
        # Fix: propaga anche agli IPC multi
        if self._live_multi_mode:
            for ipc, _, __ in self._live_multi_ipcs.values():
                ipc.show_markers = v
                ipc._needs_full_redraw = True
        self._live_refresh_plot()

    def _live_set_status(self, text, color):
        self._live_status_lbl.configure(text=text, text_color=color)

    def _live_log_append(self, text, scroll=True):
        self._live_log_box.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self._live_log_box.insert("end", f"[{ts}] {text}\n")
        # C3: cap a 500 righe — elimina la più vecchia se superato il limite
        if int(self._live_log_box.index("end-1c").split(".")[0]) > 500:
            self._live_log_box.delete("1.0", "2.0")
        if scroll:
            self._live_log_box.see("end")
        self._live_log_box.configure(state="disabled")

    def _live_export_csv(self):
        if not self._live_rows:
            messagebox.showinfo("Esporta", "Nessun dato da esportare.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Salva dati live come CSV")
        if not path:
            return
        # raccoglie tutte le chiavi non private (O(n) con dict per preservare l'ordine)
        seen = {}
        for r in self._live_rows:
            for k in r:
                if not k.startswith("_"):
                    seen.setdefault(k, None)
        all_keys = list(seen.keys())
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
                writer.writeheader()
                for r in self._live_rows:
                    writer.writerow({k: r.get(k, "") for k in all_keys})
            messagebox.showinfo("Esporta", f"Salvato: {path}")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

if __name__=="__main__":
    app=LogAnalyzerApp();app.mainloop()
