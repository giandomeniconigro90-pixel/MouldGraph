def norm_level(l):
    l=l.upper()
    if l=="WARNING":return"WARN"
    if l in("FATAL","CRITICAL","ALARM","ALARM_URGENT"):return"ERROR"
    if l in("TRACE","OK"):return"INFO"
    return l
