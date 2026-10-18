"""Opt-in native cross-process overlay smoke; only a synthetic Form is started.

Run with a report directory argument on an interactive Windows desktop. No input
is injected: native hit-testing proves the separate Form is under the HUD.
"""
import ctypes as C
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
from queue import Queue
import subprocess
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gametime import win32
from gametime.discovery import Discovery
from gametime.model import Game,Settings
from gametime.overlay import get_style,EX_FLAGS
from gametime.qt_ui import App,setup_application
from gametime.store import Store

def run(output):
    output.mkdir(parents=True,exist_ok=True)
    qt=setup_application()
    def pump(seconds):
        until=time.monotonic()+seconds
        while time.monotonic()<until: qt.processEvents(); time.sleep(.01)
    checks={}
    with tempfile.TemporaryDirectory(prefix='gametime-overlay-') as folder:
        base=Path(folder); exe=base/'FixtureGame.exe'; stop=base/'stop'
        csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        subprocess.run([str(csc),'/nologo','/target:winexe','/reference:System.Windows.Forms.dll',
                        '/reference:System.Drawing.dll','/out:'+str(exe),str(Path(__file__).with_name('FixtureGame.cs'))],check=True,capture_output=True)
        settings=Settings(games_root=str(base/'Games'),language='hu',overlay_enabled=True,overlay_x=.5,overlay_y=.5)
        store=Store(base/'usage.sqlite3'); store.save_settings(settings)
        game=Game('overlay:fixture','Synthetic overlay fixture','Kézi',str(base))
        store.upsert([game]); store.set_rule(str(exe),game.id)
        class Service:
            def __init__(self): self.results=Queue(); self.discovery=Discovery(settings,[],[],base/'none',ubisoft=False,riot=False)
            def start(self): pass
            def close(self): pass
            def request(self,*args): pass
            def configure(self,*args): pass
            def watch_manual(self,*args): pass
        class Hub:
            def __init__(self): self.results=Queue()
            def request(self,*args): pass
            def close(self): pass
        app=App(store,base,background=True,service=Service(),hub=Hub()); app.tick_timer.stop(); app.overlay_timer.stop()
        child=None
        try:
            child=subprocess.Popen([str(exe),str(stop)])
            pump(1.5)
            find=win32.api(win32.u,'FindWindowW',[win32.W.LPCWSTR,win32.W.LPCWSTR],win32.W.HWND)
            fixture=find(None,'Jatekido tesztablak'); assert fixture
            fixture_pid=win32.W.DWORD(); win32.u.GetWindowThreadProcessId(fixture,C.byref(fixture_pid)); assert fixture_pid.value==child.pid
            # Windows can refuse foreground activation while the user works in
            # another app. Test hit-through without forcing their focus away.
            win32.u.SetWindowPos(fixture,win32.W.HWND(-1),0,0,0,0,0x53)
            before=win32.u.GetForegroundWindow()
            app.overlay.present(7200,0,settings,qt.primaryScreen()); pump(.15)
            overlay=app.overlay; hwnd=int(overlay.winId())
            checks['visible_with_hub_hidden']=overlay.isVisible() and not app.isVisible() and bool(win32.u.IsWindowVisible(hwnd))
            checks['foreground_unchanged']=win32.u.GetForegroundWindow()==before
            checks['native_input_and_focus_flags']=get_style(hwnd,-20)&EX_FLAGS==EX_FLAGS
            rect=win32.W.RECT(); win32.u.GetWindowRect(hwnd,C.byref(rect))
            hit=win32.api(win32.u,'WindowFromPoint',[win32.W.POINT],win32.W.HWND)
            ancestor=win32.api(win32.u,'GetAncestor',[win32.W.HWND,win32.W.UINT],win32.W.HWND)
            under=ancestor(hit(win32.W.POINT((rect.left+rect.right)//2,(rect.top+rect.bottom)//2)),2)
            pid=win32.W.DWORD(); win32.u.GetWindowThreadProcessId(under,C.byref(pid))
            checks['hit_test_passes_through_to_other_process']=pid.value==child.pid
            overlay.grab().save(str(output/'countdown-normal.png'))
            app.overlay.present(1200,6000,settings,qt.primaryScreen()); pump(.05)
            overlay.grab().save(str(output/'countdown-warning.png')); checks['warning_is_red']=overlay.warning and overlay.seconds<=1200
            app.show(); pump(.2); app.update_overlay()
            checks['other_app_hides_countdown']=not overlay.isVisible()
            app.switch_page(2); pump(.15)
            app.overlay_picker.grab().save(str(output/'position-picker.png'))
            app.grab().save(str(output/'settings.png'))
            checks['fixture_still_running']=child.poll() is None
        finally:
            stop.touch()
            if child: child.wait(timeout=10)
            app.close(); pump(.05); store.close()
    report={'checks':checks,'note':'Synthetic windowed Form and direct renderer presentation. Native cross-process hit-test and unchanged foreground verified without forcing activation. Tracker/policy covered by integration tests; no real game/fullscreen test or input injection.'}
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report)); assert all(checks.values()),report

if __name__=='__main__': run(Path(sys.argv[1]).resolve())
