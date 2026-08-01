def parse_ts(s):
    if not s:return None
    for fmt in["%Y-%m-%d %H:%M:%S","%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S.%f",
               "%Y-%m-%dT%H:%M:%S.%f","%d/%m/%Y %H:%M:%S","%d.%m.%Y %H:%M:%S","%b %d %H:%M:%S"]:
        try:return datetime.strptime(s.rstrip("Z").strip(),fmt)
        except Exception:pass
    return None
