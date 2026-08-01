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
