# -*- coding: utf-8 -*-
"""
MouldGraph - Entry point per PyInstaller.
Esegue il file originale nel namespace __main__ cosi'
tutti i riferimenti globali e il mainloop() funzionano correttamente.
"""
import sys, os

# Cartella base: funziona sia da .py che da .exe (PyInstaller)
_base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
if _base not in sys.path:
    sys.path.insert(0, _base)

_app = os.path.join(_base, 'log_analyzer_desktop_live.py')
with open(_app, encoding='utf-8') as _f:
    exec(compile(_f.read(), _app, 'exec'), {'__name__': '__main__', '__file__': _app})
