"""Restartable isolated desktop for the real Brave handoff test."""
from pathlib import Path
import sys,json,time
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests')]
from dataclasses import replace
from datetime import datetime
from queue import Queue
from unittest.mock import patch
from contextlib import ExitStack
from PySide6.QtCore import QTimer
from gametime.qt_ui import App,setup_application
from gametime.store import Store
from gametime.model import Settings
from gametime.discovery import Discovery
from gametime.browser_activity import BrowserBridge
from gametime.browser_control import BrowserControl
from gametime.tracker import Sample

root=Path(sys.argv[1]).resolve();root.mkdir(parents=True,exist_ok=True)
profile=root/'profile';profile.mkdir(exist_ok=True)
store=Store(profile/'usage.sqlite3');browser_path=r'C:\ContinuityFixture\brave.exe'
first=not (root/'fixture.json').exists()
if first:
    store.save_settings(replace(Settings(),games_root=str(profile/'Games'),language='en',budget_setup_completed=True,
        check_updates=False,notification_sound='silent',game_budget_enabled=False,hub_enabled=False,
        wellbeing_rules=[dict(id='web',name='Offline website budget',members=[dict(kind='site',value='example.com'),dict(kind='app',value='brave.exe')],seconds=120,enabled=True,enforce=True,overlay=False)]))
settings=store.settings()
class Service:
    def __init__(self): self.results=Queue();self.discovery=Discovery(settings,[],[],profile/'none',platforms=False,ubisoft=False,riot=False)
    def start(self): pass
    def close(self): pass
    def request(self,*args): pass
    def configure(self,*args): pass
    def watch_manual(self,*args): pass
class Hub:
    def __init__(self): self.results=Queue()
    def request(self,*args): pass
    def close(self): pass
def sample(): return Sample(datetime.now().astimezone(),time.monotonic(),browser_path,'987654:fixture',interactive=True)

qt=setup_application()
with ExitStack() as stack:
    for target,value in [('gametime.qt_ui.winsound.PlaySound',None),('gametime.win32.s.Shell_NotifyIconW',True),('gametime.rtss.installation',None),('gametime.qt_ui.rtss_installation',None),('gametime.qt_activity_icons.ActivityIcons.fetch',None)]:
        stack.enter_context(patch(target,return_value=value))
    stack.enter_context(patch('gametime.win32.sample',side_effect=sample))
    stack.enter_context(patch.object(App,'enable_browser_bridge',return_value=None))
    app=App(store,profile,background=True,service=Service(),hub=Hub());app.tick_timer.stop()
    app.focus_awake=time.monotonic
    with store.db: store.db.execute('INSERT OR IGNORE INTO activity_items VALUES (?,?,?)',('app',browser_path.lower(),'brave.exe'))
    app.browser_control=BrowserControl(app)
    port=0 if first else json.loads((root/'fixture.json').read_text())['port']
    app.browser_bridge=BrowserBridge(store,port=port,control=app.browser_control.request)
    assert app.browser_bridge.server,app.browser_bridge.error
    app.update_focus_policy()
    (root/'fixture.json').write_text(json.dumps(dict(port=app.browser_bridge.port,token=app.browser_bridge.token,profile=str(profile))))
    last_scenario=None
    def status():
        app.focus.flush();app.wellbeing.flush()
        totals=dict(store.db.execute('SELECT kind,SUM(seconds) FROM activity_usage GROUP BY kind'))
        data=dict(focus=app.browser_control.live({})['focus'],token=app.focus.continuity_token,totals=totals,
            wellbeing=store.db.execute('SELECT COALESCE(SUM(seconds),0) FROM wellbeing_usage').fetchone()[0],
            journal_rows=store.db.execute('SELECT COUNT(*) FROM browser_journals').fetchone()[0])
        (root/'status.json').write_text(json.dumps(data))
    def tick():
        global last_scenario
        if (root/'stop-fixture').exists():
            status();app.close();qt.quit();return
        scenario=root/'scenario.json'
        if scenario.exists() and scenario.stat().st_mtime_ns!=last_scenario:
            value=json.loads(scenario.read_text());last_scenario=scenario.stat().st_mtime_ns
            if value.get('language'): app.set_language(value['language'])
            if 'remaining' in value:
                app.focus.configure(replace(app.focus.settings,rounds=0,block_sites=[]));app.focus.stop();app.focus.start(time.monotonic())
                app.focus.remaining=value['remaining'];app.focus._dirty=True;app.focus.flush()
            if 'budget' in value:
                rules=[dict(rule,seconds=value['budget']) for rule in app.settings.wellbeing_rules]
                app.settings=app.catalog.settings=replace(app.settings,wellbeing_rules=rules);store.save_settings(app.settings)
        app.focus_tick(sample());app.restrictions.prepare(datetime.now().astimezone());status()
    timer=QTimer();timer.setInterval(250);timer.timeout.connect(tick);timer.start()
    try: qt.exec()
    finally: app.close();store.close()
