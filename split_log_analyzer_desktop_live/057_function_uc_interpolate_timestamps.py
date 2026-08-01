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
