from pathlib import Path
import sys,json
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests')]
from PySide6.QtCore import QTimer
import test_qt_ui as fixture
from gametime.browser_control import BrowserControl
from gametime.browser_activity import BrowserBridge
from gametime.qt_budgets import new_rule
from gametime.wellbeing import target
from datetime import date,timedelta

report=Path(sys.argv[1]);report.mkdir(parents=True,exist_ok=True)
case=fixture.QtInterfaceTests();case.setUpClass();case.setUp()
try:
    app=case.app; control=BrowserControl(app)
    today=date.today()
    case.store.add_usage({((today-timedelta(days=i)).isoformat(),case.games[0].id):600*(i+1) for i in range(7)})
    bridge=BrowserBridge(case.store,port=0,control=control.request);app.browser_bridge=bridge
    control.budget_save(dict(key='fun',kind='group',name='Szabadidő',members=[target('site','youtube.com'),target('site','chess.com')],seconds=3600,enabled=True,overlay=True,days=list(range(7)),usage=True,plan=None))
    (report/'fixture.json').write_text(json.dumps(dict(port=bridge.port,token=bridge.token,profile=str(case.base))),encoding='utf-8')
    timer=QTimer();timer.setInterval(500);timer.timeout.connect(lambda:case.qt.quit() if (report/'stop-fixture').exists() else None);timer.start()
    case.qt.exec()
finally:
    case.tearDown();case.doCleanups()
