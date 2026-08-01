def generate_lamborghini_pdf(csv_path, stampo_name, output_path, logo_path=None, filter_params=None, t_start=None, t_end=None, preloaded_data=None, preloaded_meta=None):
    if logo_path is None:
        here=os.path.dirname(os.path.abspath(csv_path))
        candidate=os.path.join(here,"lamborghini_logo.png")
        if os.path.exists(candidate): logo_path=candidate
    pr=_PROFILES[stampo_name]
    if preloaded_data is not None and preloaded_meta is not None:
        data, meta = preloaded_data, preloaded_meta
    else:
        data, meta = _pdf_parse_csv(csv_path)
    if filter_params is not None:
        data={k:v for k,v in data.items() if k in filter_params}
    if t_start is not None or t_end is not None:
        _ts0=t_start or 0; _ts1=t_end or float("inf")
        data={k:[(s,v,st,sp) for s,v,st,sp in pts if _ts0<=s<=_ts1] for k,pts in data.items()}
        data={k:v for k,v in data.items() if v}
    FW,FH=8.27,11.69; L,W,MID,BOT,H=0.10,0.87,0.490,0.055,0.375
    with PdfPages(output_path) as pdf:
        if pr.get("persico"):
            _persico_v8_pages(pdf, data, meta, pr, logo_path=logo_path)
        else:
            fig=plt.figure(figsize=(FW,FH),facecolor="white")
            _pdf_hdr_p1(fig,meta,pr,1,logo_path=logo_path); pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
            fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g(fig,2)
            _pdf_temp(fig.add_axes([L,MID+0.01,W,H]),data,[f"TS{i}" for i in range(1,9)],pr["temp_set_sup"],"TEMPERATURA SUPERIORE (°C)",pr)
            _pdf_temp(fig.add_axes([L,BOT,W,H]),data,[f"TI{i}" for i in range(1,9)],pr["temp_set_inf"],"TEMPERATURA INFERIORE (°C)",pr)
            pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
            fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g(fig,3)
            _skip = pr.get("skip_seconds", 0)
            _data_pf = {k:[(s,v,st,sp) for s,v,st,sp in pts if s >= _skip] for k,pts in data.items()} if _skip else data
            _pdf_posiz(fig.add_axes([L,MID+0.01,W,H]),_data_pf,[f"Z{i}" for i in range(1,5)],pr)
            _pdf_forza(fig.add_axes([L,BOT,W,H]),_data_pf,[f"F{i}" for i in range(1,5)],pr)
            pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
            fig=plt.figure(figsize=(FW,FH),facecolor="white"); _pdf_hdr_g(fig,4)
            _vuoto_sup_bg_xmax = pr.get("vuoto_bg_xmax_sup", pr.get("vuoto_bg_xmax"))
            _vuoto_sup_bg_ymax = pr.get("vuoto_bg_ymax_sup", pr.get("vuoto_bg_ymax"))
            _vuoto_inf_bg_xmax = pr.get("vuoto_bg_xmax_inf", pr.get("vuoto_bg_xmax"))
            _vuoto_inf_bg_ymax = pr.get("vuoto_bg_ymax_inf", pr.get("vuoto_bg_ymax"))
            _sup_draw_bg = not pr.get("vuoto_no_bg_sup", False)
            _inf_draw_bg = not pr.get("vuoto_no_bg_inf", False)
            _pdf_vuoto(fig.add_axes([L,MID+0.01,W,H]),data,["VS1","VS2"],[0.0,0.0],"VUOTO SUPERIORE [bar]",["V1 Sup","V2 Sup"],pr, bg_xmax=_vuoto_sup_bg_xmax, bg_ymax=_vuoto_sup_bg_ymax, draw_bg=_sup_draw_bg)
            _pdf_vuoto(fig.add_axes([L,BOT,W,H]),data,["VI1","VI2","VI3","VI4"],[0.0,0.0,0.0,0.0],"VUOTO INFERIORE [bar]",["V1 Inf","V2 Inf","V3 Inf","V4 Inf"],pr, bg_xmax=_vuoto_inf_bg_xmax, bg_ymax=_vuoto_inf_bg_ymax, draw_bg=_inf_draw_bg)
            pdf.savefig(fig,bbox_inches="tight",dpi=150); plt.close(fig)
