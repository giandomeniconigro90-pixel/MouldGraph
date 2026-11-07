# -*- coding: utf-8 -*-
"""Parsing e analisi dei log testuali (pattern, timeline, AI, anomalie) e CSV Siemens."""
import re
import csv
import math
from datetime import datetime
from collections import defaultdict


# -- PARSER LOG --
PAT1 = re.compile(r'^\[?(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\]?\s+(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\s+\[([^\]]+)\]\s+(.*)',re.IGNORECASE)


PAT_S= re.compile(r'^(\d{2}[./]\d{2}[./]\d{4}\s+\d{2}:\d{2}:\d{2})\s*[|;,]\s*(ERROR|ALARM|ALARM_URGENT|WARNING|WARN|INFO|DEBUG|OK)\s*[|;,]\s*([^|;,]*)[|;,]?\s*(.*)',re.IGNORECASE)


PAT2 = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\s+(.*)',re.IGNORECASE)


PAT3 = re.compile(r'^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\s+(?:\[([^\]]+)\]\s+)?(.*)',re.IGNORECASE)


PAT4 = re.compile(r'^(\S.*?)\s+\b(ERROR|WARNING|WARN|INFO|DEBUG|TRACE|FATAL|CRITICAL)\b\s+(.*)',re.IGNORECASE)


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
    msg=re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}','<IP>',msg)
    msg=re.sub(r'user_id=\d+','user_id=<ID>',msg)
    msg=re.sub(r'order_id=\d+','order_id=<ID>',msg)
    msg=re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}','<EMAIL>',msg)
    msg=re.sub(r'\b\d{4,}\b','<NUM>',msg)
    return re.sub(r'\s+',' ',msg).strip()


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
        key=(a[0],a[1][:30])
        if key not in seen:seen.add(key);out.append(a)
    return out,stats
