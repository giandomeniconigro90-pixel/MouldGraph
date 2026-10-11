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
        self._live_interp_var=Widget(True)
        self._live_ipc=SimpleNamespace(clear=lambda:None,_ranges=[],update_live=self.draw)
        self.draws=[];self.jobs={};self.job_id=0;self.logs=[]
        for name in ['start_btn','stop_btn','pause_btn','alarm_badge','cnt_lbl','status_lbl']:
            setattr(self,'_live_'+name,Widget())
    def after(self,ms,func,*args):
        self.job_id+=1;self.jobs[self.job_id]=(func,args);return self.job_id
    def after_cancel(self,job): self.jobs.pop(job,None)
    def _live_log_append(self,text,**kw): self.logs.append(text)
    def _live_rebuild_col_buttons(self): pass
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

class LiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'input.csv'
        self.path.write_text('Time,Temp\n0,20\n1,21\n',encoding='utf-8')
        self.apps=[]
        NS['messagebox']=SimpleNamespace(showinfo=lambda *a:None,showerror=lambda *a:None,
                                         showwarning=lambda *a:None,askyesnocancel=lambda *a:False)
    def app(self):
        a=Harness(self.path);self.apps.append(a);return a
    def tearDown(self):
        for a in self.apps:
            a._live_stop_event.set()
            if a._live_thread:a._live_thread.join(.5)
            if a._live_archive:a._live_archive.close()
        self.tmp.cleanup()
    def test_max_replay_lossless_and_export_beyond_500(self):
        self.path.write_text('Time,Temp\n'+''.join(f'{i},20\n' for i in range(750)))
        a=self.app();a._live_start();a.drain()
        self.assertEqual(a._live_total,750);self.assertEqual(len(a._live_rows),500)
        self.assertEqual(a._live_dropped,0);self.assertFalse(a._live_running.is_set())
        out=Path(self.tmp.name)/'out.csv';NS['filedialog']=SimpleNamespace(asksaveasfilename=lambda **kw:str(out))
        self.assertTrue(a._live_export_csv())
        with out.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),750);self.assertEqual(float(rows[0]['_sim_t']),0)
        self.assertEqual(float(rows[-1]['_sim_t']),749)
        self.assertIn('completata',a._live_status_lbl.options['text'])
        self.assertFalse(a.jobs)
    def test_stop_interrupts_long_gap(self):
        self.path.write_text('Time,Temp\n0,20\n600,21\n')
        a=self.app();a._live_speed_var.set('1x');a._live_start()
        end=time.monotonic()+1
        while a._live_total==0 and time.monotonic()<end:a._live_poll();time.sleep(.001)
        a._live_stop();a.drain()
        self.assertEqual(a._live_total,1)
        self.assertEqual(a._live_start_btn.options['state'],'normal')
    def test_pause_freezes_consumption_then_resumes(self):
        self.path.write_text('Time,Temp\n'+''.join(f'{i},{20+i}\n' for i in range(100)))
        a=self.app();a._live_start();a._live_toggle_pause()
        total=a._live_total;draws=len(a.draws)
        for _ in range(4):a._live_poll();time.sleep(.01)
        self.assertEqual(a._live_total,total);self.assertEqual(len(a.draws),draws)
        a._live_toggle_pause();a.drain();self.assertEqual(a._live_total,100)
    def test_speed_change_wakes_long_wait(self):
        a=self.app();a._live_speed_snapshot='1x';result=[]
        worker=threading.Thread(target=lambda:result.append(a._live_wait(600)))
        worker.start();time.sleep(.03);a._live_speed_snapshot='MAX';worker.join(.3)
        self.assertFalse(worker.is_alive());self.assertEqual(result,[True])
    def test_alarm_detects_middle_of_batch(self):
        self.path.write_text('Time,Temp\n0,20\n1,150\n2,20\n')
        a=self.app();a._live_alarm_rules=[{'col':'Temp','hi':100}]
        a._live_start();a.drain();self.assertEqual(a._live_alarm_count,1)
    def test_binary_columns_are_replayed(self):
        self.path.write_text('Time,Pump\n0,0\n1,1\n2,0\n')
        a=self.app();a._live_start();a.drain()
        self.assertEqual([r['Pump'] for r in a._live_rows],[0,1,0])
    def test_long_csv_retains_real_timestamp(self):
        self.path.write_text('Parametro,Timestamp,Valore\nTemp,06_10_2026_10_00_00,20\nTemp,06_10_2026_10_00_01,21\n')
        a=self.app();a._live_start();a.drain()
        self.assertEqual(a._live_rows[0]['_ts'],datetime(2026,10,6,10,0,0))
        self.assertEqual(a._live_total,2)
    def test_index_and_missing_values(self):
        self.path.write_text('Temp,Force\n20,100\n21,\n22,102\n')
        a=self.app();a._live_start();a.drain()
        self.assertEqual([r['_sim_i'] for r in a._live_rows],[0,1,2])
        self.assertIsNone(a._live_rows[1]['Force'])
    def test_selection_and_lines_preserve_samples(self):
        a=self.app();a._live_start();a.drain()
        a.draws.clear();a._live_sel_all()
        self.assertEqual(a.draws[-1][0][0],[0,1]);self.assertEqual(len(a.draws),1)
        a._live_interp_var.set(False);a._live_refresh_plot()
        self.assertFalse(a.draws[-1][1]['connect_lines'])
        a._live_paused.set();n=len(a.draws);a._live_interp_tick()
        self.assertEqual(len(a.draws),n)
    def test_parse_failure_restores_controls(self):
        self.path.write_text('')
        a=self.app();a._live_start();a.drain()
        self.assertTrue(a._live_worker_error);self.assertFalse(a._live_running.is_set())
        self.assertEqual(a._live_start_btn.options['state'],'normal')
    def test_cancel_new_session_keeps_archive(self):
        a=self.app();a._live_start();a.drain();archive=a._live_archive
        NS['messagebox'].askyesnocancel=lambda *a:None
        a._live_start();self.assertIs(a._live_archive,archive);self.assertEqual(a._live_total,2)
    def test_one_poll_timer_after_restarts(self):
        a=self.app()
        for _ in range(3):a._live_start();a.drain();self.assertFalse(a.jobs)
        self.assertEqual(a._live_total,2)

    def test_multi_selection_refreshes_only_active_panels(self):
        a=self.app();a._live_start();a.drain()
        calls=[];first=SimpleNamespace(_ranges=[],update_live=lambda *x,**k:calls.append('first'),clear=lambda:None)
        second=SimpleNamespace(_ranges=[],update_live=lambda *x,**k:calls.append('second'),clear=lambda:None)
        a._live_multi_mode=True
        a._live_multi_ipcs={'one':(first,['Temp'],{'active':True,'paused':False}),
                           'two':(second,['Temp'],{'active':True,'paused':True})}
        a._live_refresh_plot();self.assertEqual(calls,['first'])

    def test_serial_pause_keeps_recording_and_closes_port(self):
        a=self.app();a._live_src_var.set('Seriale');a._live_port_var=Widget('COM_TEST')
        a._live_baud_var=Widget('9600')
        class Port:
            closed=False
            def __init__(self,*args,**kwargs):self.first=True
            def read(self,n):
                if self.first:
                    self.first=False;return b'Temp=150\nTemp=20\n'
                a._live_stop_event.set();return b''
            def close(self):Port.closed=True
        with patch.dict(NS,SERIAL_AVAILABLE=True,serial=SimpleNamespace(Serial=Port)):
            a._live_start();a._live_paused.set();a.drain()
        self.assertEqual(a._live_total,2);self.assertTrue(Port.closed)
        self.assertTrue(all('_ts' in r for r in a._live_rows))

    def test_one_panel_grid_export(self):
        a=self.app();a._live_start();a.drain()
        a._live_multi_ipcs={'Temp':(a._live_ipc,['Temp'],{})};a.set_status=lambda x:None
        path=Path(self.tmp.name)/'graph.png'
        a._live_export_multi_render(['Temp'],str(path),'png','Griglia 2 colonne')
        self.assertGreater(path.stat().st_size,1000)

class PlotTests(unittest.TestCase):
    def plot(self):
        p=Plot.__new__(Plot);p._fig=Figure();p._canvas=FigureCanvasAgg(p._fig)
        p._ax1=p._fig.add_subplot();p._ax2=None;p._lines={};p._ranges=[]
        p._hidden=set();p._overlay_lines={};p._dot_artists=[];p._cross_v=None;p._tooltip=None
        p._info_var=Widget();p._info_lbl=Widget();p._rebuild_legend_sidebar=lambda:None
        p.show_markers=True;p._live_user_zoomed=False;p._drawing=False
        return p
    def test_constant_values_advance_time(self):
        p=self.plot()
        p.update_live([0,1],{'Temp':[20,20]},'index',{})
        p.update_live([1,2],{'Temp':[20,20]},'index',{})
        p.update_live([2,3],{'Temp':[20,20]},'index',{})
        self.assertEqual(list(p._lines['Temp'].get_xdata()),[2,3])
    def test_zoom_preserved_and_missing_values_break_line(self):
        p=self.plot();p.update_live([0,1,2],{'Temp':[20,21,22]},'index',{})
        p._ax1.set_xlim(.5,1.5);p._ax1.set_ylim(19,23);p._live_user_zoomed=True
        p.update_live([1,2,3],{'Temp':[21,None,23]},'index',{})
        self.assertEqual(p._ax1.get_xlim(),(.5,1.5));self.assertTrue(np.isnan(p._lines['Temp'].get_ydata()[1]))
    def test_points_mode_does_not_change_real_values(self):
        p=self.plot();p.update_live([0,1],{'Temp':[20,21]},'index',{},connect_lines=False)
        self.assertEqual(p._lines['Temp'].get_linestyle(),'None')
        self.assertEqual(list(p._lines['Temp'].get_ydata()),[20,21])

if __name__=='__main__':unittest.main()
