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
