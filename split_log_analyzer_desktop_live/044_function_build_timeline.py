def build_timeline(parsed):
    b=defaultdict(lambda:{"ERROR":0,"WARN":0,"INFO":0,"DEBUG":0,"total":0})
    for l in parsed:
        k=l["ts"].strftime("%H:%M") if l["ts"] else "??:??"
        b[k][l["level"]]=b[k].get(l["level"],0)+1;b[k]["total"]+=1
    return dict(sorted(b.items()))
