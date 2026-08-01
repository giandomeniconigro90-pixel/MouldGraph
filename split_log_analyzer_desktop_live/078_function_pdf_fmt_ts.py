def _pdf_fmt_ts(ts):
    if ts is None: return ""
    try: return ts.strftime("%d/%m/%Y %H:%M:%S")
    except Exception: return ""
