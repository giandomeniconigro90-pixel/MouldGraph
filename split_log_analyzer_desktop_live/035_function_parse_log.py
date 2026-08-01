def parse_log(text):
    return[parse_line(l,i) for i,l in enumerate([x for x in text.splitlines() if x.strip()])]
