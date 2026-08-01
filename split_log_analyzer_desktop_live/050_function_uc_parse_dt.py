def _uc_parse_dt(s):
    s = s.strip().rstrip("Z")
    for fmt in _UC_TSFMTS:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None
