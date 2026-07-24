# -*- coding: utf-8 -*-

COLORS = {
    "bg":"#0f1117","surface":"#1a1d27","surface2":"#22263a","border":"#2e3350",
    "accent":"#6c63ff","accent2":"#00d4ff","error":"#ff4d4f","warn":"#faad14",
    "info":"#52c41a","debug":"#1890ff","text":"#e8eaf6","text2":"#8892b0",
}
LEVEL_COLORS = {"ERROR":COLORS["error"],"WARN":COLORS["warn"],"INFO":COLORS["info"],"DEBUG":COLORS["debug"]}
LEVEL_BG     = {"ERROR":"#4a1a1a","WARN":"#4a3a00","INFO":"#1a3a0a","DEBUG":"#0a2a4a"}
LEVEL_HOVER  = {"ERROR":"#7a2020","WARN":"#7a5a00","INFO":"#2a5a10","DEBUG":"#104070"}

MAX_LIVE_POINTS = 500

UNIT_PATTERNS = [
    (r"temp|calore|forno|cottura",          "\u00b0C",    "Temperatura"),
    (r"press|bar|kpa|psi|mpa",              "bar",   "Pressione"),
    (r"forza|kn|newton|force",              "kN",    "Forza"),
    (r"portata|flow|l_min|lmin|l/min",      "L/min", "Portata"),
    (r"pos|stroke|piano|quota|mm(?!hg)",    "mm",    "Posizione"),
    (r"vel|speed|rpm|giri|rotaz",           "rpm",   "Velocit\u00e0"),
    (r"vuoto|vacuum|mbar",                  "mbar",  "Vuoto"),
    (r"corr|ampere|current|amps",           "A",     "Corrente"),
    (r"volt|tension|tensione",              "V",     "Tensione"),
    (r"umid|humid|rh(?!\w)",               "%RH",   "Umidit\u00e0"),
    (r"colla|glue|adhesive|erog",           "g/s",   "Erogazione"),
    (r"angolo|angle|deg(?!\w)|gradi",      "\u00b0",     "Angolo"),
    (r"peso|weight|kg(?!\w)|gram",         "kg",    "Peso"),
    (r"freq|hz(?!\w)|hertz",               "Hz",    "Frequenza"),
    (r"pot|watt|kw(?!\w)|power",           "kW",    "Potenza"),
    (r"level|livello|fill|riempim",         "%",     "Livello"),
    (r"co2|o2|gas|ppm",                     "ppm",   "Gas"),
    (r"vibr|accel|g(?!\w)",                "m/s\u00b2",  "Vibrazione"),
    (r"torque|coppia|nm(?!\w)",            "Nm",    "Coppia"),
    (r"dist|distanza|range(?!\w)",         "mm",    "Distanza"),
]

_UC_SERIES_PALETTE = [
    "#e5672c", "#3f51b5", "#29b6f6", "#66bb6a",
    "#9c27b0", "#ff9800", "#e7b73b", "#607d8b",
    "#f44322", "#00bcd4", "#8bc34a", "#ff5722",
]

_PLANT_PALETTE = [
    "#e5672c", "#3f51b5", "#29b6f6", "#66bb6a",
    "#9c27b0", "#ff9800", "#e7b73b", "#607d8b",
    "#f44322", "#00bcd4", "#8bc34a", "#ff5722",
]

_PC = {
    1:"#f44322",2:"#3f51b5",3:"#29b6f6",4:"#66bb6a",
    5:"#7d0910",6:"#607d8b",7:"#9c27b0",8:"#ff9800",
    "set_temp":"#795548","set_forza":"#7d0910",
    "lmax":"#607d8b","lmin":"#9c27b0",
    "bg":"#ccffff","grid":"#cccccc",
}

_SERIES_COLORS = {
    "TS1":"#e5672c","TS2":"#828282","TS3":"#407da5","TS4":"#e7b73b",
    "TS5":"#9c27b0","TS6":"#607d8b","TS7":"#ff9800","TS8":"#29b6f6",
    "TI1":"#e5672c","TI2":"#828282","TI3":"#407da5","TI4":"#e7b73b",
    "TI5":"#9c27b0","TI6":"#607d8b","TI7":"#ff9800","TI8":"#29b6f6",
    "T1":"#e5672c","T2":"#828282","T3":"#407da5","T4":"#e7b73b",
    "T5":"#9c27b0","T6":"#607d8b","T7":"#ff9800","T8":"#29b6f6",
    "P1":"#407da5","P2":"#e5672c","P3":"#828282","P4":"#e7b73b",
    "Z1":"#407da5","Z2":"#e5672c","Z3":"#828282","Z4":"#e7b73b",
    "F1":"#f44322","F2":"#3f51b5","F3":"#29b6f6","F4":"#66bb6a","FC":"#f44322","SPC":"#7d0910",
    "VS1":"#407da5","VS2":"#e5672c","V1":"#407da5","V2":"#e5672c",
    "VI1":"#407da5","VI2":"#e5672c","VI3":"#828282","VI4":"#e7b73b",
    "V3":"#828282","V4":"#e7b73b",
}

_PROFILES = {
"Inner Tub":{"ricetta":"Tub - Ciclo nuovo","temp_set_sup":127.0,"temp_set_inf":125.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax_sup":1090, "vuoto_bg_ymax_sup":-0.2, "vuoto_no_bg_inf":True,
    "x_ticks":[0,174,349,523,698,872,1047,1221,1396,1570,1745],"x_max":1745,
    "forza_legend_loc":"lower right","pressa":"Cannon 5000T","persico":False},
"Polecrasher":{"ricetta":"Polecrasher - Ciclo nuovo","temp_set_sup":129.0,"temp_set_inf":127.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax_inf":1100,"vuoto_bg_ymax_inf":-0.2, "vuoto_no_bg_sup":True,
    "x_ticks":[0,174,348,522,696,870,1044,1218,1392,1566,1740],"x_max":1740,
    "forza_legend_loc":"upper left","pressa":"Cannon 5000T","persico":False},
"Tub Floor Shell":{"ricetta":"Tub Floor Shell - Ciclo nuovo","temp_set_sup":129.0,"temp_set_inf":130.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax_sup":1070, "vuoto_bg_ymax_sup":-0.2, "vuoto_no_bg_inf":True,
    "x_ticks":[0,150,300,450,600,750,900,1050,1200,1350,1500],"x_max":1500,
    "forza_legend_loc":"upper left","pressa":"Cannon 5000T","persico":False},
"Front Firewall":{"ricetta":"Front Firewall - Ciclo","pressa":"Persico 2500T","persico":True,
    "teorico_sec":2633,"temp_set_sup":130.0,"temp_set_inf":128.0,
    "temp_y":(95.0,165.0),"temp_yticks":[100,110,120,130,140,150,160],
    "forza_y":(5900,6900),"forza_yticks":[6000,6100,6200,6300,6400,6500,6600,6700,6800],
    "forza_spc":6500.0,"forza_delta":200,
    "posiz_y":(-0.35,0.05),"posiz_yticks":[-0.35,-0.30,-0.25,-0.20,-0.15,-0.10,-0.05,0.0,0.05],
    "vuoto_y":(-1050,50),"vuoto_yticks":[-1000,-800,-600,-400,-200,0],
    "x_ticks":[0,132,264,396,528,660,792,924,1056,1188,1320,1452,1496],"x_max":1496,
    "forza_legend_loc":"lower right","temp_range":(120,140),"skip_seconds":8},
"Central Cofango":{"ricetta":"Central Cofango - Ciclo","pressa":"Persico 2500T","persico":True,
    "teorico_sec":879,"temp_set_sup":142.0,"temp_set_inf":142.0,
    "temp_y":(100.0,160.0),"temp_yticks":[100,110,120,130,140,150,160],
    "forza_y":(3500,4300),"forza_yticks":[3500,3600,3700,3800,3900,4000,4100,4200,4300],
    "forza_spc":4000.0,"forza_delta":200,
    "posiz_y":(0.0,0.18),"posiz_yticks":[0.0,0.02,0.04,0.06,0.08,0.10,0.12,0.14,0.16,0.18],
    "vuoto_y":(-1000,0),"vuoto_yticks":[-1000,-900,-800,-700,-600,-500,-400,-300,-200,-100,0],
    "x_ticks_tv":list(range(22, 406+1, 12)),
    "x_ticks_pos":list(range(14, 410+1, 12)),
    "x_ticks_forza":list(range(22, 406+1, 12)),
    "x_ticks_vac_sup":list(range(14, 410+1, 12)),
    "x_ticks_vac_inf":list(range(22, 406+1, 12)),
    "forza_legend_loc":"lower right",
    "forza_range":(3750,4250)},
"Side Cofango Inner":{"ricetta":"Side Cofango Inner - Ciclo","pressa":"Persico 2500T","persico":True,
    "teorico_sec":990,"temp_set_sup":142.0,"temp_set_inf":142.0,
    "temp_y":(100.0,160.0),"temp_yticks":[100,110,120,130,140,150,160],
    "forza_y":(3500,4300),"forza_yticks":[3500,3600,3700,3800,3900,4000,4100,4200,4300],
    "forza_spc":4000.0,"forza_delta":200,
    "posiz_y":(-0.05,0.3),"posiz_yticks":[-0.05,0.0,0.05,0.1,0.15,0.2,0.25,0.3],
    "vuoto_y":(-1000,0),"vuoto_yticks":[-1000,-900,-800,-700,-600,-500,-400,-300,-200,-100,0],
    "x_ticks_tv":list(range(25, 520+1, 15)),
    "x_ticks_pos":list(range(15, 525+1, 15)),
    "x_ticks_forza":list(range(25, 520+1, 15)),
    "x_ticks_vac_sup":list(range(15, 525+1, 15)),
    "x_ticks_vac_inf":list(range(25, 520+1, 15)),
    "forza_legend_loc":"lower right",
    "forza_range":(3750,4250),"temp_range":(130, 150)},
"Side Cover":{"ricetta":"Side Cover - Ciclo","pressa":"Krauss Maffei","persico":False,
    "temp_set_sup":130.0,"temp_set_inf":128.0,
    "temp_y":(120.0,150.0),"temp_yticks":[120,126,132,138,144,150],
    "forza_y":(0,13000),"forza_yticks":[0,2600,5200,7800,10400,13000],"forza_delta":1000,
    "posiz_y":(-6.0,6.0),"posiz_yticks":[-6,-3.6,-1.2,1.2,3.6,6.0],
    "vuoto_y":(-1.0,1.0),"vuoto_yticks":[-1.0,-0.6,-0.2,0.2,0.6,1.0],
    "vuoto_bg_xmax":1070, "vuoto_bg_ymax":-0.2,
    "x_ticks":[0,150,300,450,600,750,900,1050,1200,1350,1500],"x_max":1500,
    "forza_legend_loc":"upper left"},
}

_PRESSA_STAMPI = {
    "Cannon 5000T":["Inner Tub","Tub Floor Shell","Polecrasher"],
    "Persico 2500T":["Front Firewall","Central Cofango","Side Cofango Inner"],
    "Krauss Maffei":["Side Cover"],
}

_LK = dict(fontsize=7.0, framealpha=0.9, edgecolor="#ccc", handlelength=1.8,
           handleheight=0.9, borderpad=0.6, labelspacing=0.3)
