def _uc_try_float(s):
    try:
        float(s.replace(",", ".").replace(" ", ""))
        return True
    except Exception:
        return False
