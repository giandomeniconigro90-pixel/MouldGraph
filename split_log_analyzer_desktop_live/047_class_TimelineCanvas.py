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
