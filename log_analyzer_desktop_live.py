# -*- coding: utf-8 -*-
"""MouldGraph - avvio.

Il codice dell'app e' nel package mouldgraph/ (vedi mouldgraph/app.py).
Questo file resta come punto di ingresso per python e PyInstaller.
"""
from mouldgraph.app import LogAnalyzerApp

if __name__=="__main__":
    app=LogAnalyzerApp();app.mainloop()
