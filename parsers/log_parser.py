# -*- coding: utf-8 -*-
import re
from datetime import datetime
from collections import defaultdict

PAT1 = re.compile(r'^\[?(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\]?\s+(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\s+\[([^\]]+)\]\s+(.*)',re.IGNORECASE)
PAT_S= re.compile(r'^(\d{2}[./]\d{2}[./]\d{4}\s+\d{2}:\d{2}:\d{2})\s*[|;,]\s*(ERROR|ALARM|ALARM_URGENT|WARNING|WARN|INFO|DEBUG|OK)\s*[|;,]\s*([^|;,]*)[|;,]?\s*(.*)',re.IGNORECASE)
PAT2 = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\s+(.*)',re.IGNORECASE)
PAT3 = re.compile(r'^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\s+(?:\[([^\]]+)\]\s+)?(.*)',re.IGNORECASE)
PAT4 = re.compile(r'^(\S.{7,}?)\s+\b(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\b\s+(.+)',re.IGNORECASE)

_RE_IP    = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
_RE_UID   = re.compile(r'user_id=\d+')
_RE_OID   = re.compile(r'order_id=\d+')
_RE_EMAIL = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_RE_NUM   = re.compile(r'\b\d{4,}\b')
_RE_WS    = re.compile(r'\s+')

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
