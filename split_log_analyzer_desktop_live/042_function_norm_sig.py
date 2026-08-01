def norm_sig(msg):
    msg=_RE_IP.sub('<IP>',msg)
    msg=_RE_UID.sub('user_id=<ID>',msg)
    msg=_RE_OID.sub('order_id=<ID>',msg)
    msg=_RE_EMAIL.sub('<EMAIL>',msg)
    msg=_RE_NUM.sub('<NUM>',msg)
    return _RE_WS.sub(' ',msg).strip()
