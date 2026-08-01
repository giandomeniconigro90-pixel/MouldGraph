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
