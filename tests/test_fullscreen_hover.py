"""Headless regression checks for the fullscreen chart's real callbacks."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backend_bases import MouseEvent


class FullscreenHoverTests(unittest.TestCase):
    def setUp(self):
        source = (Path(__file__).parents[1] / 'log_analyzer_desktop_live.py').read_text()
        tree = ast.parse(source)
        app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LogAnalyzerApp')
        method = next(n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == '_grafici_open_fullscreen')
        # Execute the actual overlay setup/callbacks, without creating Tk windows.
        first = next(i for i,n in enumerate(method.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_bg' for t in n.targets))
        last = next(i for i,n in enumerate(method.body) if isinstance(n,ast.FunctionDef) and n.name=='_reset_view')
        fig = Figure(figsize=(8,4)); canvas = FigureCanvasAgg(fig); ax = fig.add_subplot()
        xs=np.linspace(0,100,101); ys=100+np.sin(xs/10)*10
        ax.plot(xs,ys); canvas.draw()
        self.mode='Completo'
        self.ns=dict(np=np,fig=fig,ax=ax,canvas=canvas,toolbar=SimpleNamespace(mode=''),
                     _hover_mode=SimpleNamespace(get=lambda:self.mode),_series={'Temperature':(xs,ys,'red')})
        exec(compile(ast.Module(body=method.body[first:last+1],type_ignores=[]),'fullscreen_callbacks','exec'),self.ns)
        canvas.draw()

    def motion(self):
        ax=self.ns['ax']; x=sum(ax.get_xlim())/2; y=sum(ax.get_ylim())/2
        px,py=ax.transData.transform((x,y))
        self.ns['_on_motion'](MouseEvent('motion_notify_event',self.ns['canvas'],px,py))

    def test_zoom_leave_reenter_keeps_current_view(self):
        ax=self.ns['ax']; canvas=self.ns['canvas']
        ax.set_xlim(30,60); ax.set_ylim(92,108); canvas.draw()
        expected=np.asarray(canvas.buffer_rgba()).copy()
        self.motion(); self.ns['_on_leave'](None)
        np.testing.assert_array_equal(np.asarray(canvas.buffer_rgba()),expected)
        self.motion(); self.ns['_on_leave'](None)
        np.testing.assert_array_equal(np.asarray(canvas.buffer_rgba()),expected)
        self.assertEqual(ax.get_xlim(),(30,60))

    def test_limits_invalidate_cache_before_redraw(self):
        self.ns['ax'].set_xlim(20,40)
        self.assertIsNone(self.ns['_bg'][0])
        self.motion()
        self.assertIsNotNone(self.ns['_bg'][0])

    def test_toolbar_and_resize(self):
        self.motion(); self.ns['toolbar'].mode='pan/zoom'; self.motion()
        self.assertFalse(self.ns['_info_box'].get_visible())
        self.ns['toolbar'].mode=''
        self.ns['fig'].set_size_inches(10,5); self.ns['canvas'].draw()
        self.motion(); self.ns['_on_leave'](None)
        self.assertEqual(self.ns['canvas'].get_width_height(),(1000,500))

    def test_scroll_after_toolbar_zoom(self):
        ax=self.ns['ax']; ax.set_xlim(30,60); ax.set_ylim(92,108)
        self.ns['_on_scroll'](SimpleNamespace(inaxes=ax,button='down',xdata=45,ydata=100))
        self.assertGreater(ax.get_xlim()[1]-ax.get_xlim()[0],30)

    def test_no_values_outside_series(self):
        interp=self.ns['_interp_y']
        self.assertIsNone(interp(np.array([1,2]),np.array([10,20]),3))
        self.assertEqual(interp(np.array([1,2]),np.array([10,20]),1.5),15)

if __name__=='__main__': unittest.main()
