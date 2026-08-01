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
        # grid
        for i in range(6):
            y=pt+ch*i//5
            val=mx_v-(rng*i/5)
            self.create_line(pl,y,w-pr,y,fill=COLORS["border"],dash=(2,4))
            self.create_text(pl-4,y,text=f"{val:.1f}",fill=COLORS["text2"],font=("Segoe UI",8),anchor="e")
        # x labels
        step=max(1,n//8)
        for i in range(0,n,step):
            x=pl+i*cw/(n-1) if n>1 else pl+cw//2
            lbl=self.times[i].strftime("%H:%M:%S") if hasattr(self.times[i],"strftime") else str(self.times[i])
            self.create_text(x,h-pb+10,text=lbl,fill=COLORS["text2"],font=("Segoe UI",8),anchor="n")
        # lines
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
        # legend
        lx=pl;ly=5
        for label,(color,_) in self.series.items():
            self.create_rectangle(lx,ly,lx+12,ly+10,fill=color,outline="")
            self.create_text(lx+15,ly+5,text=label,fill=COLORS["text2"],font=("Segoe UI",8),anchor="w")
            lx+=len(label)*6+30
