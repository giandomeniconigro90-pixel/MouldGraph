def parse_siemens_csv(text):
    rows=[];headers=[]
    reader=csv.reader(text.splitlines())
    for i,row in enumerate(reader):
        if i==0:
            headers=[h.strip().strip('"') for h in row]
        else:
            if not any(c.strip() for c in row):continue
            d={}
            for j,h in enumerate(headers):
                val=row[j].strip().strip('"') if j<len(row) else ""
                try:d[h]=float(val)
                except Exception:d[h]=val
            # parse timestamp
            ts=None
            for tcol in["UTC Time","Date_Time","Datetime","timestamp","Time","Date"]:
                if tcol in d and d[tcol]:
                    for fmt in["%Y-%m-%d %H:%M:%S","%Y-%m-%dT%H:%M:%S","%d/%m/%Y %H:%M:%S",
                               "%Y-%m-%d %H:%M:%S.%f","%d-%m-%Y %H:%M:%S"]:
                        try:ts=datetime.strptime(str(d[tcol]),fmt);break
                        except Exception:pass
                if ts:break
            if ts is None and "Date" in d and "Time" in d:
                try:ts=datetime.strptime(f"{d['Date']} {d['Time']}","%Y-%m-%d %H:%M:%S")
                except Exception:pass
            d["_ts"]=ts
            rows.append(d)
    return headers,rows
