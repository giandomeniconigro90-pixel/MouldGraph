def _pdf_fmt_date(ts):
    try: return datetime.strptime(ts.rstrip("Z"), "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y %H:%M:%S")
    except Exception: return ts
