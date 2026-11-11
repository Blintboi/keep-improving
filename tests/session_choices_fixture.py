"""Disposable interactive fixture for native opening-choice verification."""
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import json, math, subprocess, sys, time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_qt_ui import QtInterfaceTests
from gametime.restriction_policy import Budget,new_plan,step
from gametime.session_choices import defaults
from gametime.wellbeing import target
from gametime import win32

report=Path(sys.argv[1]).resolve();report.mkdir(parents=True,exist_ok=True)
fixture=Path(sys.argv[2]).resolve();assert fixture.name=='FixtureRestriction.exe' and fixture.is_file()
QtInterfaceTests.setUpClass();case=QtInterfaceTests();case.setUp();app=case.app;runtime=app.restrictions
process=None
try:
    process=subprocess.Popen([str(fixture)])
    app.setWindowTitle('Keep Improving · opening-choice test');app.hide()
    app.focus.configure(replace(app.focus.settings,tracking=True))
    plan=new_plan();action=step('notify',2,popup=True);action.update(time_mode='sessions',session_choice=defaults(app.t));plan['steps']=[action]
    app.settings=app.catalog.settings=replace(app.settings,restriction_plans={'choice-fixture':plan})
    runtime.budgets=lambda wall:[Budget('choice-fixture','Search Console · próba',math.inf,0,(target('app',str(fixture)),),day='2026-11-11')]
    last=None;mode='overlay';deadline=time.monotonic()+900
    while time.monotonic()<deadline and not (report/'stop').exists():
        try:
            command=(report/'command.json').read_text(encoding='utf-8-sig') if (report/'command.json').exists() else ''
            value=json.loads(command) if command else {}
        except (OSError,ValueError):case.pump(.2);continue
        if command and command!=last:
            last=command;mode=value.get('mode',mode)
            if 'language' in value:
                app.set_language(value['language']);action['session_choice']=defaults(app.t)
                if runtime.choices.screen:runtime.choices.screen.signature=None
            if 'allocation' in value:action['session_choice']['allocation']=value['allocation']
            if value.get('depleted'):
                for n in range(2):runtime.choices.ledger.choose('choice-fixture',action['id'],'2026-11-11','seed'+str(n)+action['session_choice']['options'][1]['id'],action['session_choice'],action['session_choice']['options'][1]['id'],time.time())
            if mode=='editor':
                runtime.choices.reset();app.open_budget(member=target('site','search.google.com'))
                editor=app.budget_editor;editor.steps.add_step.click();card=editor.steps.cards[-1]
                card.time_mode.setCurrentIndex(card.time_mode.findData('sessions'));card.choices.enabled.setChecked(True)
                card.choices.allocation.setCurrentIndex(card.choices.allocation.findData(value.get('allocation','shared')))
                app.resize(value.get('width',1100),value.get('height',850));app.show()
                case.pump(.1);app.budget_scroll.ensureWidgetVisible(card.choices)
            else:app.hide()
        if mode=='overlay':runtime.tick(win32.sample())
        state={'target_pid':process.pid,'mode':mode,'visible':bool(runtime.choices.screen and runtime.choices.screen.isVisible()),
               'counts':runtime.choices.ledger.counts('choice-fixture',action['id'],'2026-11-11')}
        (report/'state.json').write_text(json.dumps(state),encoding='utf-8')
        case.pump(.2)
finally:
    if process and process.poll() is None:process.terminate();process.wait(timeout=8)
    case.tearDown();case.doCleanups()
