"""Disposable desktop bridge for the real extension's early-break button."""
from pathlib import Path
import sys,json,time
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests')]
from dataclasses import replace
from datetime import datetime,timedelta
from unittest.mock import patch
from PySide6.QtCore import QTimer
from test_qt_ui import QtInterfaceTests
from gametime.browser_activity import BrowserBridge
from gametime.browser_control import BrowserControl
from gametime.restriction_policy import Budget,new_plan,step
from gametime.timer_view import project
from gametime.tracker import Sample
from gametime.qt_budgets import new_rule

report=Path(sys.argv[1]);report.mkdir(parents=True,exist_ok=True)
no_timer=len(sys.argv)>2 and sys.argv[2]=='no-timer'
QtInterfaceTests.setUpClass();case=QtInterfaceTests();case.setUp();offset=0
class Clock(datetime):
    @classmethod
    def now(cls,*args,**kwargs):return datetime.now(*args,**kwargs)+timedelta(seconds=offset)
try:
    app=case.app;runtime=app.restrictions
    case.enterContext(patch('gametime.qt_restrictions.datetime',Clock))
    case.enterContext(patch('gametime.win32.sample',side_effect=lambda:Sample(Clock.now().astimezone(),time.monotonic(),interactive=False)))
    plan=new_plan();item=step('break',900,identity='pause',break_mode='cover',break_minutes=5);item['allow_early_break']=True;plan['steps']=[item]
    rule=new_rule('YouTube',[{'kind':'site','value':'youtube.com'}],'youtube');rule['enabled']=True;rule['seconds']=3600
    if no_timer:rule['overlay']=False
    app.settings=app.catalog.settings=replace(app.settings,restriction_plans={'youtube':plan},wellbeing_rules=[rule])
    app.wellbeing.configure(Clock.now().astimezone())
    case.store.save_settings(app.settings);app.schedule_editor.saved(app.settings);app.budget_editor.saved(app.settings)
    budget=Budget('youtube','YouTube',3600,720,({'kind':'site','value':'youtube.com'},))
    runtime.budgets=lambda wall:[budget]
    def timers(**kwargs):
        runtime.prepare(Clock.now().astimezone())
        return [] if no_timer else [project(budget,plan,runtime.state.rows['youtube'],runtime.state.now,'site:youtube.com')]
    app.timer_views=timers
    app.browser_control=BrowserControl(app)
    app.browser_bridge=BrowserBridge(case.store,port=0,control=app.browser_control.request)
    (report/'fixture.json').write_text(json.dumps(dict(port=app.browser_bridge.port,token=app.browser_bridge.token)),encoding='utf-8')
    def update():
        global offset
        if (report/'stop-fixture').exists():case.qt.quit();return
        if (report/'finish-break').exists():
            (report/'finish-break').unlink();offset+=300
        runtime.prepare(Clock.now().astimezone());app.update_focus_policy()
    timer=QTimer();timer.setInterval(200);timer.timeout.connect(update);timer.start();update();case.qt.exec()
finally:case.tearDown();case.doCleanups()
