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
from dataclasses import replace
import time
from gametime.timer_view import TimerView
from gametime.qt_activity_icons import ActivityIcons
from unittest.mock import patch
icon_fetch=ActivityIcons.fetch

report=Path(sys.argv[1]);report.mkdir(parents=True,exist_ok=True)
case=fixture.QtInterfaceTests();case.setUpClass();case.setUp()
try:
    app=case.app; control=BrowserControl(app);app.browser_control=control
    today=date.today()
    from gametime.activity_sessions import record
    from datetime import datetime
    from gametime.tracker import Sample
    # Browser status polling must not add the real desktop's foreground activity
    # to this synthetic profile while the fixture asserts exact session counts.
    case.enterContext(patch('gametime.win32.sample',side_effect=lambda:Sample(datetime.now().astimezone(),time.monotonic(),interactive=False)))
    with case.store.db:
        case.store.db.execute("UPDATE settings SET value=? WHERE key='sessions_since'",(str(time.time()-8*86400),))
        for i in range(7):
            day=today-timedelta(days=i);start=datetime.combine(day,datetime.min.time()).astimezone().timestamp()+3600
            for n in range(2):record(case.store.db,'game',case.games[0].id,start+n*60,start+n*60+30,day)
    case.store.add_usage({((today-timedelta(days=i)).isoformat(),case.games[0].id):600*(i+1) for i in range(7)})
    from gametime.statistics_sync import FORMAT
    from PySide6.QtGui import QPixmap,QColor
    group='ab'*16;remote='12'*16
    app.settings=app.catalog.settings=replace(app.settings,statistics_sync_group=group,statistics_sync_enabled=False,statistics_device_name='Desktop')
    case.store.save_settings(app.settings)
    app.statistics_data.ingest(dict(format=FORMAT,group=group,device=remote,name='Laptop',revision=1,started=today.isoformat(),
        sessions=dict(since=(today-timedelta(days=8)).isoformat(),rows=[[(today-timedelta(days=i)).isoformat(),'game','qt:1',3] for i in range(7)]),
        rows=[[(today-timedelta(days=i)).isoformat(),'qt:1','Fixture Beta','Steam',300*(i+1)] for i in range(7)],
        activity_started=today.isoformat(),activity=[[today.isoformat(),'site','example.com','example.com',120]]+
            [[today.isoformat(),'app',f'short-{i}.exe',f'Short activity {i}',.01] for i in range(40)]),group)
    # A retired duplicate must not be rendered, nor poison a visible image batch.
    case.store.upsert([replace(case.games[0],id='retired:alpha',installed=False)])
    icon=QPixmap(64,64);icon.fill(QColor('#b9a1ff'))
    app.art.artwork=lambda game,rules:(None,icon)
    from test_activity_icons import IconTests,png_bytes
    import os
    executable=str(Path(os.environ['WINDIR'])/'System32/notepad.exe')
    control.library.activity_add(dict(kind='app',value=executable))
    control.library.activity_add(dict(kind='site',value='example.com'))
    app.focus.configure(replace(app.focus.settings,block_apps=[executable],block_sites=['example.com']))
    case.requests=[];case.replies=[]
    case.enterContext(patch('gametime.notification_applications.choices',return_value=[(executable,'Notepad')]))
    case.enterContext(patch('gametime.browser_icons.BrowserIcons.fetch',icon_fetch))
    case.enterContext(IconTests.network(case,{'https://'+host+'/favicon.ico':(png_bytes('#2779b8'),False) for host in ('example.com','youtube.com','chess.com')}))
    bridge=BrowserBridge(case.store,port=0,control=control.request);app.browser_bridge=bridge
    control.budget_save(dict(key='fun',kind='group',name='Szabadidő',members=[target('site','youtube.com'),target('site','chess.com')],seconds=3600,enabled=True,overlay=True,days=list(range(7)),usage=True,plan=None))
    (report/'fixture.json').write_text(json.dumps(dict(port=bridge.port,token=bridge.token,profile=str(case.base))),encoding='utf-8')
    timer_scenario=None; scenario_at=0; scenario_stamp=None
    def poll_fixture():
        global timer_scenario,scenario_at,scenario_stamp
        if (report/'stop-fixture').exists(): case.qt.quit(); return
        scenario_path=report/'timer-fixture.json'
        if scenario_path.exists() and scenario_path.stat().st_mtime_ns!=scenario_stamp:
            try: value=json.loads(scenario_path.read_text(encoding='utf-8'))
            except (ValueError,OSError): return
            timer_scenario=value;scenario_at=time.monotonic();scenario_stamp=scenario_path.stat().st_mtime_ns
            app.settings=replace(app.settings,language=value.get('language','en'))
            def timers(**kwargs):
                elapsed=time.monotonic()-scenario_at
                return [TimerView(**dict(item,seconds=max(0,item['seconds']-(elapsed if item.get('wall_clock') or item.get('active') else 0)))) for item in timer_scenario['timers']]
            app.timer_views=timers
    timer=QTimer();timer.setInterval(500);timer.timeout.connect(poll_fixture);timer.start()
    case.qt.exec()
finally:
    case.tearDown();case.doCleanups()
