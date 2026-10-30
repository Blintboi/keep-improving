"""Interactive adapter smoke on a disposable, pre-scanned process only."""
import argparse
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
import json,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_qt_ui import QtInterfaceTests
from gametime import win32
from gametime.restriction_policy import Budget,new_plan,step
from gametime import restriction_native as native
from gametime.tracker import Sample
from gametime.wellbeing import target as member
from gametime.qt_restriction_steps import edit_steps

parser=argparse.ArgumentParser(); parser.add_argument('fixture',type=Path); args=parser.parse_args()
fixture=args.fixture.resolve(); assert fixture.name=='FixtureRestriction.exe' and fixture.is_file()
QtInterfaceTests.setUpClass(); case=QtInterfaceTests(); case.setUp()
process=None; report=[]
try:
    process=subprocess.Popen([str(fixture)])
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        path,identity=win32.process_image(process.pid)
        if identity and native.windows(identity): break
        case.pump(.05)
    assert identity and native.windows(identity)
    native.restore_target(path,identity); case.pump(.2)
    app=case.app; app.set_language("en"); runtime=app.restrictions
    app.focus.configure(replace(app.focus.settings,tracking=True))
    plan=new_plan(); plan.update(extension_minutes=1,close_confirmed=True,steps=[step('cover')])
    app.settings=app.catalog.settings=replace(app.settings,restriction_plans={'smoke':plan})
    runtime.budgets=lambda wall:[Budget('smoke','Restriction test budget',1,1,(member('app',path),))]
    runtime.legacy_block=lambda atom:False
    native.restore_target(path,identity); case.pump(.2)
    # A background test must wait for deliberate activation, not bypass the
    # user's foreground lock or inject keys into whichever app they are using.
    deadline=time.monotonic()+45
    while not native.target_rect(path,identity) and time.monotonic()<deadline: case.pump(.1)
    assert native.target_rect(path,identity), repr({'foreground':win32.u.GetForegroundWindow(),'windows':native.windows(identity),'allowed':native.permitted(path,identity),'reason':native.policy.reason(path)})
    current=Sample(datetime.now().astimezone(),1,path,identity)
    runtime.tick(current); case.pump(.2)
    assert runtime.screen and runtime.screen.isVisible(), 'cover did not appear'
    assert runtime.screen.extra.isVisible()
    assert runtime.screen.width()>=520
    runtime.screen.grab().save(str(Path('test-reports/restriction-screen.png').resolve()))
    report.append('opaque target cover displayed with allowance')
    runtime.screen.extra.click(); case.pump(.2)
    assert not runtime.screen.isVisible()
    assert runtime.state.rows['smoke']['used_extension']
    runtime.tick(replace(current,wall=datetime.now().astimezone(),awake=2)); case.pump(.1)
    assert runtime.save_counter and runtime.save_counter.isVisible()
    assert win32.u.GetForegroundWindow() in native.windows(identity), 'save counter stole focus'
    assert 0<runtime.save_remaining(path)<=60
    report.append('single allowance restores target; countdown keeps target focus')
    runtime.tick(replace(current,wall=datetime.now().astimezone()+timedelta(seconds=62),awake=64))
    deadline=time.monotonic()+8
    while process.poll() is None and time.monotonic()<deadline: case.pump(.05)
    assert process.poll() is not None, 'fixture did not close after allowance'
    report.append('allowance expiry closes only the fixture')
    app.open_budget(); app.budget_editor.show_editor('shared-games')
    window=edit_steps(app.budget_editor); case.pump(.15)
    window.grab().save(str(Path('test-reports/restriction-editor.png').resolve()))
    window.reject()
    print(json.dumps({'passed':report},ensure_ascii=False))
finally:
    if process and process.poll() is None: process.terminate(); process.wait(timeout=8)
    case.tearDown(); case.doCleanups()
