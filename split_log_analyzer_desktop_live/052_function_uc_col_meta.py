def _uc_col_meta(col_name, sample_vals):
    non_empty = [v.strip() for v in sample_vals if v.strip()]
    if not non_empty:
        return "", col_name, "text"
    dt_ok = sum(1 for v in non_empty[:8] if _uc_parse_dt(v) is not None)
    if dt_ok >= max(1, len(non_empty[:8]) // 2):
        return "", col_name, "datetime"
    num_ok = sum(1 for v in non_empty[:20] if _uc_try_float(v))
    if num_ok >= max(1, len(non_empty[:20]) * 0.7):
        uniq = set(v.strip() for v in non_empty[:50])
        if uniq <= {"0", "1", "0.0", "1.0", "True", "False", "true", "false"}:
            return "", col_name, "binary"
        cn_low = col_name.lower()
        for pattern, unit, label in UNIT_PATTERNS:
            if re.search(pattern, cn_low):
                return unit, label, "numeric"
        return "", col_name, "numeric"
    return "", col_name, "text"
