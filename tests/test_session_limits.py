from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta
import math
from pathlib import Path
import tempfile
import unittest
from gametime.store import Store
from gametime.restriction_policy import Budget,RestrictionState,new_plan,step,validate_plans
from gametime.budget_sessions import count
from gametime.timer_view import project


class SessionLimitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'usage.db');self.addCleanup(self.store.close)
        self.state=RestrictionState(self.store);self.plan=new_plan();self.day='2026-11-10'
    def action(self,kind,n=5):
        item=step(kind,n,popup=kind=='notify',break_mode='cover',break_minutes=1)
        item['time_mode']='sessions';self.plan['steps'].append(item);return item
    def update(self,sessions,now=1000,limit=math.inf):
        self.budget=Budget('test','Test',limit,10,(),sessions=sessions)
        self.state.update(self.day,now,[self.budget],{'test':self.plan})
    def test_allows_five_blocks_sixth_and_survives_restart(self):
        self.action('cover');validate_plans({'test':self.plan})
        for n in range(6):
            self.update(n);self.assertEqual(self.state.action('test','app:fixture.exe'),'')
        self.update(6);self.assertEqual(self.state.action('test','app:fixture.exe'),'cover')
        self.state=RestrictionState(self.store);self.update(6,2000)
        self.assertEqual(self.state.action('test','app:fixture.exe'),'cover')
        self.day='2026-11-11';self.update(1,3000)
        self.assertEqual(self.state.action('test','app:fixture.exe'),'')
    def test_warning_once_and_no_seconds_countdown(self):
        item=self.action('notify');self.update(5)
        self.assertFalse(self.state.warnings('test'))
        self.assertIsNone(project(self.budget,self.plan,self.state.rows['test'],1000,'app:fixture.exe'))
        self.update(6);self.assertEqual(self.state.warnings('test'),[item]);self.state.delivered('test',item['id'])
        self.state=RestrictionState(self.store);self.update(7)
        self.assertFalse(self.state.warnings('test'))
    def test_break_repeats_only_after_new_visits(self):
        self.action('break');self.update(6)
        self.assertEqual(self.state.break_remaining('test'),60)
        self.update(6,1060);self.assertEqual(self.state.break_remaining('test'),0)
        self.update(11,1100);self.assertEqual(self.state.break_remaining('test'),0)
        self.update(12,1200);self.assertEqual(self.state.break_remaining('test'),60)
        event=project(self.budget,self.plan,self.state.rows['test'],1200,'app:fixture.exe')
        self.assertEqual((event.event,event.seconds),('break_active',60))
    def test_break_carries_across_renewal_and_time_limit_wins(self):
        self.action('break');self.update(6);self.day='2026-11-11';self.update(0,1030)
        self.assertEqual(self.state.break_remaining('test'),30)
        self.update(0,1060);self.assertEqual(self.state.break_remaining('test'),0)
        self.update(6,1200,limit=10);self.assertEqual(self.state.break_remaining('test'),0)
    def test_rejects_fractional_boolean_negative_and_excessive_limits(self):
        item=self.action('cover')
        for bad in (True,1.5,0,-1,10001,5.0):
            item['offset']=bad
            with self.assertRaises(ValueError):validate_plans({'test':self.plan})
    def test_overlap_pending_batches_and_member_switches(self):
        rows=[('app','game.exe',10,20),('game','g',10,20),('app','other.exe',20,30),('app','game.exe',30,40),('app','game.exe',40,45)]
        members=[{'kind':'category','value':'games'},{'kind':'category','value':'apps'}]
        self.assertEqual(count(rows,members,0,50,lambda p:'g' if p=='game.exe' else ''),3)
        self.assertEqual(count(rows,members,15,50,lambda p:'g' if p=='game.exe' else ''),2)
        web=[('app','browser.exe',10,40),('site','a.test',10,20),('site','b.test',20,30),('site','a.test',30,40)]
        self.assertEqual(count(web,[{'kind':'category','value':'sites'}],0,50),3)
        self.assertEqual(count(web,[{'kind':'app','value':'browser.exe'},{'kind':'category','value':'sites'}],0,50),1)


import test_qt_ui as fixture
class SessionLimitInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump
    def test_edit_save_and_restore_in_both_languages(self):
        for language in ('hu','en'):
            self.app.set_language(language);self.app.open_budget();editor=self.app.budget_editor;editor.show_editor('shared-games')
            editor.steps.add('notify');card=editor.steps.cards[-1]
            card.time_mode.setCurrentIndex(card.time_mode.findData('sessions'));card.session_limit.setValue(5)
            self.assertEqual(card.value['offset'],5);self.assertIs(type(card.value['offset']),int)
            self.assertFalse(card.session_limit.isHidden());self.assertTrue(card.minutes.isHidden());self.assertTrue(card.clock_time.isHidden())
            card.kind.setCurrentIndex(card.kind.findData('break'));self.assertEqual(card.value['time_mode'],'sessions')
            editor.drafts.flush();self.assertTrue(editor.drafts.prepare_save())
            validate_plans(editor.restriction_plans)
            editor.setMinimumWidth(0);self.app.resize(1000,760);self.pump(.4);self.app.budget_scroll.ensureWidgetVisible(card);self.pump(.4)
            output=Path('test-reports/session-limits');output.mkdir(parents=True,exist_ok=True)
            self.app.grab().save(str(output/f'windows-{language}.png'))
    def test_runtime_counts_pending_game_and_app_once_without_flush(self):
        from gametime.tracker import Sample
        plan=new_plan();plan['steps']=[dict(step('notify',1,popup=True),time_mode='sessions')]
        self.app.settings=replace(self.app.settings,game_budget_enabled=True,restriction_plans={'shared-games':plan})
        start=datetime.now().astimezone()+timedelta(seconds=1)
        for second,path in enumerate([str(self.exe),'other.exe',str(self.exe),'other.exe']):
            sample=Sample(start+timedelta(seconds=second),100+second,path,'test')
            self.app.focus.tick(sample);self.app.tracker.tick(sample)
        budgets=self.app.restrictions.budgets(start+timedelta(seconds=3))
        self.assertEqual(next(b.sessions for b in budgets if b.key=='shared-games'),2)
        self.app.focus.flush();self.app.tracker.flush()
        self.assertEqual(next(b.sessions for b in self.app.restrictions.budgets(start+timedelta(seconds=3)) if b.key=='shared-games'),2)
