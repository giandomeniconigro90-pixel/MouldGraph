# -*- coding: utf-8 -*-
import tkinter as tk
from constants import COLORS

class TimelineCanvas(tk.Canvas):
    def __init__(self,master,**kw):
        super().__init__(master,bg=COLORS["surface2"],highlightthickness=0,**kw)
        self.data={}
    def set_data(self,data):self.data=data;self.after(50,self.redraw)
    def redraw(self):
        self.delete("all")
        if not self.data:return
        w=self.winfo_width();h=self.winfo_height()
        if w<10 or h<10:return
        pl,pr,pt,pb=40,10,10,30
        keys=list(self.data.keys());n=len(keys)
        if n==0:return
        max_t=max(v["total"] for v in self.data.values()) or 1
        baw=w-pl-pr;bw=max(2,baw/n-2);ch=h-pt-pb
        for i in range(5):
            y=pt+(ch*i//4)
            self.create_line(pl,y,w-pr,y,fill=COLORS["border"],dash=(2,4))
            self.create_text(pl-4,y,text=str(int(max_t*(4-i)/4)),fill=COLORS["text2"],font=("Segoe UI",8),anchor="e")
        for i,key in enumerate(keys):
            v=self.data[key];x=pl+i*(baw/n)+(baw/n-bw)/2;sy=h-pb
            for lvl,color in[("DEBUG","#1890ff"),("INFO","#52c41a"),("WARN","#faad14"),("ERROR","#ff4d4f")]:
                cnt=v.get(lvl,0)
                if cnt==0:continue
                bh=max(2,cnt/max_t*ch);y0=sy-bh
                self.create_rectangle(x,y0,x+bw,sy,fill=color,outline="");sy=y0
        step=max(1,n//8)
        for i in range(0,n,step):
            x=pl+i*(baw/n)+baw/(n*2)
            self.create_text(x,h-pb+10,text=keys[i],fill=COLORS["text2"],font=("Segoe UI",8),anchor="n")
        lx=pl
        for lvl,color in[("ERROR","#ff4d4f"),("WARN","#faad14"),("INFO","#52c41a"),("DEBUG","#1890ff")]:
            self.create_rectangle(lx,2,lx+10,12,fill=color,outline="")
            self.create_text(lx+13,7,text=lvl,fill=COLORS["text2"],font=("Segoe UI",8),anchor="w");lx+=60


class LineChart(tk.Canvas):
    def __init__(self,master,**kw):
        super().__init__(master,bg=COLORS["surface2"],highlightthickness=0,**kw)
        self.series={}   # {label:(color,[values])}
        self.times=[]
    def set_data(self,times,series):
        self.times=times;self.series=series;self.after(50,self.redraw)
    def redraw(self):
        self.delete("all")
        if not self.series or not self.times:return
        w=self.winfo_width();h=self.winfo_height()
        if w<20 or h<20:return
        pl,pr,pt,pb=50,20,15,35
        all_vals=[v for (_c,vals) in self.series.values() for v in vals if v is not None]
        if not all_vals:return
        mn_v=min(all_vals);mx_v=max(all_vals)
        rng=mx_v-mn_v or 1
        mn_v-=rng*0.05;mx_v+=rng*0.05;rng=mx_v-mn_v
        cw=w-pl-pr;ch=h-pt-pb;n=len(self.times)
        for i in range(6):
            y=pt+ch*i//5
            val=mx_v-(rng*i/5)
            self.create_line(pl,y,w-pr,y,fill=COLORS["border"],dash=(2,4))
            self.create_text(pl-4,y,text=f"{val:.1f}",fill=COLORS["text2"],font=("Segoe UI",8),anchor="e")
        step=max(1,n//8)
        for i in range(0,n,step):
            x=pl+i*cw/(n-1) if n>1 else pl+cw//2
            lbl=self.times[i].strftime("%H:%M:%S") if hasattr(self.times[i],"strftime") else str(self.times[i])
            self.create_text(x,h-pb+10,text=lbl,fill=COLORS["text2"],font=("Segoe UI",8),anchor="n")
        for label,(color,vals) in self.series.items():
            pts=[]
            for i,v in enumerate(vals):
                if v is None:continue
                x=pl+i*cw/(n-1) if n>1 else pl+cw//2
                y=pt+ch*(1-(v-mn_v)/rng)
                pts.append((x,y))
            for i in range(len(pts)-1):
                self.create_line(pts[i][0],pts[i][1],pts[i+1][0],pts[i+1][1],fill=color,width=2)
            if pts:
                self.create_oval(pts[-1][0]-3,pts[-1][1]-3,pts[-1][0]+3,pts[-1][1]+3,fill=color,outline="")
        lx=pl;ly=5
        for label,(color,_) in self.series.items():
            self.create_rectangle(lx,ly,lx+12,ly+10,fill=color,outline="")
            self.create_text(lx+15,ly+5,text=label,fill=COLORS["text2"],font=("Segoe UI",8),anchor="w")
            lx+=len(label)*6+30


class PumpCanvas(tk.Canvas):
    def __init__(self,master,**kw):
        super().__init__(master,bg=COLORS["surface2"],highlightthickness=0,**kw)
        self.data=[]
    def set_data(self,times,vals):self.data=list(zip(times,vals));self.after(50,self.redraw)
    def redraw(self):
        self.delete("all")
        if not self.data:return
        w=self.winfo_width();h=self.winfo_height()
        if w<20 or h<20:return
        pl,pr,pt,pb=50,20,10,30
        n=len(self.data);cw=w-pl-pr;ch=h-pt-pb
        bw=max(2,cw/n-1)
        for i,(ts,val) in enumerate(self.data):
            x=pl+i*cw/n
            color="#52c41a" if val==1 else "#ff4d4f"
            self.create_rectangle(x,pt,x+bw,pt+ch,fill=color,outline="")
        self.create_text(pl-4,pt+ch//4,text="ON",fill="#52c41a",font=("Segoe UI",9,"bold"),anchor="e")
        self.create_text(pl-4,pt+ch*3//4,text="OFF",fill="#ff4d4f",font=("Segoe UI",9,"bold"),anchor="e")
        step=max(1,n//8)
        for i in range(0,n,step):
            ts=self.data[i][0]
            x=pl+i*cw/n+bw/2
            lbl=ts.strftime("%H:%M:%S") if hasattr(ts,"strftime") else str(ts)
            self.create_text(x,h-pb+10,text=lbl,fill=COLORS["text2"],font=("Segoe UI",8),anchor="n")
