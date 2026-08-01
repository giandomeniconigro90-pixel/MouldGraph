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
