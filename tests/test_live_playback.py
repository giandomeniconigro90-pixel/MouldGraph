"""Regression tests of the actual monolith, without requiring a Tk display."""
import ast
import csv
import io
import json
import math
import os
from pathlib import Path
import queue
import re
import tempfile
import threading
import time
import unittest
from datetime import datetime
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

SOURCE = Path(__file__).parents[1] / 'log_analyzer_desktop_live.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
NAMES = {'parse_universal_csv','_uc_parse_dt','_uc_try_float','_uc_col_meta',
         '_is_long_cycle_csv','_parse_long_cycle_csv'}
CONSTANTS = {'COLORS','MAX_LIVE_POINTS','UNIT_PATTERNS','_UC_TSFMTS',
             '_LONG_TS_FMT','_UC_SERIES_PALETTE'}
nodes = []
for n in TREE.body:
    if isinstance(n, ast.FunctionDef) and n.name in NAMES:
        nodes.append(n)
    elif isinstance(n, ast.Assign) and any(isinstance(x,ast.Name) and x.id in CONSTANTS for x in n.targets):
        nodes.append(n)
    elif isinstance(n, ast.ClassDef) and n.name in ('LogAnalyzerApp','InteractivePlotCanvas'):
        n.bases=[]
        nodes.append(n)
NS = dict(np=np,plt=plt,mdates=mdates,csv=csv,json=json,math=math,os=os,re=re,
          datetime=datetime,defaultdict=defaultdict,threading=threading,_queue=queue,
          SERIAL_AVAILABLE=False)
exec(compile(ast.Module(body=nodes,type_ignores=[]), str(SOURCE), 'exec'),NS)
App = NS['LogAnalyzerApp']; Plot = NS['InteractivePlotCanvas']

class Widget:
    def __init__(self,value=None): self.value=value; self.options={}
    def get(self): return self.value
    def set(self,value): self.value=value
    def configure(self,**kw): self.options.update(kw)

class Harness(App):
    def __init__(self,path):
        self._live_running=threading.Event();self._live_paused=threading.Event()
        self._live_stop_event=threading.Event();self._live_done_event=threading.Event()
        self._live_queue=queue.Queue(maxsize=3);self._live_thread=None
        self._live_poll_job=None;self._live_interp_job=None;self._live_worker_error=None
        self._live_archive=None;self._live_archive_keys={};self._live_total=0
        self._live_rows=[];self._live_loading=False;self._live_load_id=0
        self._live_headers=['Time','Temp'];self._live_col_meta={}
        self._live_numeric_cols=['Time','Temp'];self._live_plot_cols=['Temp']
        self._live_alarm_rules=[];self._live_alarm_count=0;self._live_alarm_active=set()
        self._live_multi_mode=False;self._live_multi_ipcs={};self._live_csv_path=str(path)
        self._live_src_var=Widget('Simulazione CSV');self._live_speed_var=Widget('MAX')
        self._live_rate_var=Widget('20');self._live_maxpts_var=Widget('500')
        self._live_interp_var=Widget(False)
        self._live_ipc=SimpleNamespace(clear=lambda:None,reset_zoom=lambda:None,clear_cursors=lambda:None,_ranges=[],update_live=self.draw)
        self._live_log_box=SimpleNamespace(configure=lambda **k:None,delete=lambda *a:None)
        self.draws=[];self.jobs={};self.job_id=0;self.logs=[]
        for name in ['start_btn','stop_btn','pause_btn','alarm_badge','cnt_lbl','status_lbl']:
            setattr(self,'_live_'+name,Widget())
    def after(self,ms,func,*args):
        self.job_id+=1;self.jobs[self.job_id]=(func,args);return self.job_id
    def after_cancel(self,job): self.jobs.pop(job,None)
    def _live_log_append(self,text,**kw): self.logs.append(text)
    def _live_rebuild_col_buttons(self): pass
    def _live_rebuild_alarm_cards(self): pass
    def _live_refresh_plot(self): self.draws.append(len(self._live_rows))
    def _live_set_status(self,text,color): self.status=text
    def draw(self,*args,**kwargs): self.draws.append((args,kwargs))
    def drain(self,timeout=3):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            self._live_poll()
            if self._live_done_event.is_set() and self._live_queue.empty():
                self._live_thread.join(.2)
                return
            time.sleep(.001)
        raise AssertionError('session did not finish')


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'input.csv'
        self.path.write_text('Time,Temp\n0,20\n1,21\n')
        self.a=Harness(self.path)
        NS['messagebox']=SimpleNamespace(showinfo=lambda *a:None,showwarning=lambda *a:None)
    def tearDown(self):
        self.a._live_stop_event.set();self.a._live_running.clear()
        if self.a._live_thread: self.a._live_thread.join(.5)
        self.tmp.cleanup()
    def test_max_750_rows_small_queue(self):
        self.path.write_text('Time,Temp\n'+''.join(f'{i},{20+i}\n' for i in range(750)))
        seen=[]; original=self.a._live_queue.get_nowait
        def get():
            r=original();seen.append(r);return r
        self.a._live_queue.get_nowait=get
        self.a._live_start();self.a.drain()
        self.assertEqual(len(seen),750)
        self.assertEqual([r['_sim_t'] for r in seen],list(range(750)))
        self.assertEqual(self.a._live_total,750);self.assertEqual(len(self.a._live_rows),500)
        self.assertEqual(self.a._live_dropped,0);self.assertEqual(self.a.status,'Riproduzione completata')
        self.assertFalse(self.a._live_running.is_set());self.assertFalse(self.a.jobs)
        self.assertEqual(self.a._live_start_btn.options['state'],'normal')
    def first_sample(self):
        end=time.monotonic()+1
        while not self.a._live_total and time.monotonic()<end:
            self.a._live_poll();time.sleep(.005)
        self.assertEqual(self.a._live_total,1)
    def test_stop_interrupts_600_second_gap(self):
        self.path.write_text('Time,Temp\n0,20\n600,21\n');self.a._live_speed_var.set('1x')
        self.a._live_start();self.first_sample();start=time.monotonic()
        self.a._live_stop();self.a._live_thread.join(.3);self.a._live_poll()
        self.assertFalse(self.a._live_thread.is_alive());self.assertLess(time.monotonic()-start,.3)
        self.assertEqual(self.a._live_total,1);self.assertFalse(self.a.jobs)
    def test_pause_freezes_consumption_then_resume(self):
        self.path.write_text('Time,Temp\n'+''.join(f'{i},{20+i}\n' for i in range(100)))
        self.a._live_start();self.a._live_toggle_pause();n=self.a._live_total;draws=len(self.a.draws)
        for _ in range(5):self.a._live_poll();time.sleep(.01)
        self.assertEqual(self.a._live_total,n);self.assertEqual(len(self.a.draws),draws)
        self.a._live_toggle_pause();self.a.drain();self.assertEqual(self.a._live_total,100)
    def test_speed_max_during_gap(self):
        self.path.write_text('Time,Temp\n0,20\n600,21\n');self.a._live_speed_var.set('1x')
        self.a._live_start();self.first_sample();self.a._live_speed_snapshot='MAX';self.a.drain()
        self.assertEqual(self.a._live_total,2)
    def test_stop_while_paused_and_queue_full(self):
        self.path.write_text('Time,Temp\n'+''.join(f'{i},{20+i}\n' for i in range(100)))
        self.a._live_start();self.a._live_toggle_pause();self.a._live_stop();self.a.drain()
        self.assertFalse(self.a._live_thread.is_alive());self.assertFalse(self.a.jobs)
    def test_error_restores_buttons(self):
        self.path.unlink();self.a._live_start();self.a.drain()
        self.assertEqual(self.a._live_start_btn.options['state'],'normal')
        self.assertTrue(any('ERRORE' in s for s in self.a.logs));self.assertFalse(self.a.jobs)
    def test_restart_single_timer(self):
        self.a._live_start();self.a.drain();self.a._live_start();self.a.drain()
        self.assertEqual(self.a._live_total,2);self.assertFalse(self.a.jobs)
    def test_long_mixed_csv(self):
        self.path.write_text('Partita,Parametro,Timestamp,Valore\n26RF001;Temp;11_10_2026_12_00_00;120,5\n26RF001;Temp;11_10_2026_12_00_01;121,5\n')
        self.a._live_start();self.a.drain();self.assertEqual(self.a._live_total,2)
        self.assertEqual(self.a._live_rows[0]['Temp'],120.5)
        self.assertEqual((self.a._live_rows[1]['_ts']-self.a._live_rows[0]['_ts']).total_seconds(),1)
    def test_clear_waits_for_worker_and_stays_stopped(self):
        self.path.write_text('Time,Temp\n0,20\n600,21\n');self.a._live_speed_var.set('1x')
        self.a._live_start();self.first_sample();self.a._live_clear()
        self.a._live_thread.join(.3)
        jobs=list(self.a.jobs.values());self.a.jobs.clear()
        for func,args in jobs:func(*args)
        self.assertEqual(self.a._live_rows,[]);self.assertFalse(self.a._live_running.is_set())
        self.assertEqual(self.a._live_total,0)
if __name__=='__main__':unittest.main()

