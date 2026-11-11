"""Local bridge for the headless opening-choice integration fixture."""
from pathlib import Path
import sys,json,time
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests')]
from dataclasses import replace
from datetime import datetime
from PySide6.QtCore import QTimer
from unittest.mock import patch
from test_qt_ui import QtInterfaceTests
from gametime.browser_activity import BrowserBridge
from gametime.browser_control import BrowserControl
from gametime.qt_budgets import new_rule
from gametime.restriction_policy import new_plan,step
from gametime.session_choices import defaults
from gametime.tracker import Sample
from gametime.wellbeing import target

report=Path(sys.argv[1]);report.mkdir(parents=True,exist_ok=True)
QtInterfaceTests.setUpClass();case=QtInterfaceTests();case.setUp()
try:
    app=case.app;case.enterContext(patch('gametime.win32.sample',side_effect=lambda:Sample(datetime.now().astimezone(),time.monotonic(),interactive=False)))
    rule=new_rule('Webes próba',[target('site',sys.argv[2] if len(sys.argv)>2 else 'choice.example.com'),target('site','second.example.com')],'web-choices');rule['enabled']=True
    regression=len(sys.argv)>3 and sys.argv[3]=='reconnect'
    plan=new_plan();s=step('cover' if regression else 'notify',5 if regression else 2,popup=True);s.update(time_mode='sessions',session_choice=defaults(app.t));plan['steps']=[s]
    if regression:s['session_choice']['allocation']='activity'
    app.settings=app.catalog.settings=replace(app.settings,wellbeing_rules=[rule],restriction_plans={rule['id']:plan},budget_usage_limits={rule['id']:False})
    app.wellbeing.configure(datetime.now().astimezone());case.store.save_settings(app.settings)
    app.schedule_editor.saved(app.settings);app.budget_editor.saved(app.settings)
    app.browser_control=BrowserControl(app);app.browser_bridge=BrowserBridge(case.store,port=0,control=app.browser_control.request)
    (report/'fixture.json').write_text(json.dumps(dict(port=app.browser_bridge.port,token=app.browser_bridge.token,limited=s['session_choice']['options'][1]['id'])),encoding='utf-8')
    def update():
        if (report/'stop-fixture').exists():case.qt.quit();return
        app.restrictions.prepare(datetime.now().astimezone());app.update_focus_policy()
    timer=QTimer();timer.setInterval(200);timer.timeout.connect(update);timer.start();update();case.qt.exec()
finally:case.tearDown();case.doCleanups()
