"""Zero means blocked, including before first use and without an action plan."""
from dataclasses import replace
from datetime import datetime,timedelta
import unittest
from unittest.mock import patch
import test_restriction_steps as policy_fixture
import test_qt_ui as ui_fixture
import test_preferences_sync as sync_fixture
from gametime.model import Settings
from gametime.restriction_policy import Budget,RestrictionState,new_plan,step
from gametime.wellbeing import target
from gametime.qt_budgets import new_rule


class ZeroPolicyTests(unittest.TestCase):
    setUp=policy_fixture.StepsTests.setUp
    tearDown=policy_fixture.StepsTests.tearDown
    update=policy_fixture.StepsTests.update

    def test_zero_blocks_without_actions_and_survives_restart_and_renewal(self):
        self.plans={}; self.update(used=0,limit=0)
        for subject in (self.subject,'site:example.com:tab'):
            self.assertEqual(self.engine.action('budget',subject),'cover')
            self.assertEqual(self.engine.allowance(['budget'],subject),0)
            self.assertIsNone(self.engine.extend(['budget'],subject))
        self.assertEqual(self.plans,{})
        self.engine=RestrictionState(self.store); self.day='2026-11-01'; self.update(used=0,limit=0)
        self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.update(used=0,limit=60)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.update(used=0,limit=0)
        self.engine.update(self.day,1001,[],{})
        self.assertEqual(self.engine.action('budget',self.subject),'')

    def test_zero_overrides_delayed_or_disabled_actions_without_closing(self):
        self.plan['steps']=[step('notify',popup=True),step('close'),step('break',30,usage=True)]
        self.plan['steps'][1]['targets']={'app':{'enabled':False},'site':{'enabled':False}}
        self.update(used=0,limit=0)
        self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.assertTrue(self.engine.has_restriction('budget'))
        self.assertEqual(self.engine.warnings('budget'),[])
        self.assertEqual(self.engine.break_remaining('budget'),0)

    def test_zero_cancels_save_grant_without_later_delayed_closure(self):
        self.update(); self.engine.extend(['budget'],self.subject,'123:456')
        self.update(limit=0,now=1001)
        self.assertIsNone(self.engine.grant('budget',self.subject,'123:456'))
        self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.update(limit=600,now=1300)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.assertTrue(self.engine.rows['budget']['used_extension'])

    def test_zero_has_priority_over_another_budget_break(self):
        pause=new_plan(); pause['steps']=[step('break',30,usage=True,break_mode='close')]
        self.engine.update(self.day,1000,[Budget('zero','Zero',0,0,()),Budget('pause','Pause',120,30,())],{'pause':pause})
        self.assertEqual(self.engine.dominant(['zero','pause'],self.subject),['zero'])
        self.assertEqual(self.engine.action('zero',self.subject),'cover')

    def test_zero_values_round_trip_and_invalid_values_still_fail(self):
        rule=new_rule('Zero',[target('site','example.com')]); rule.update(seconds=0,enabled=True)
        settings=replace(Settings(),limit_seconds=0,game_limits={'fixture':0},wellbeing_rules=[rule],daily_schedules={'0':{'limit_seconds':0}})
        self.store.save_settings(settings)
        saved=self.store.settings()
        self.assertEqual((saved.limit_seconds,saved.game_limits['fixture'],saved.wellbeing_rules[0]['seconds']),(0,0,0))
        for value in (-1,True,float('nan'),float('inf')):
            with self.subTest(value=value),self.assertRaises(ValueError): replace(settings,limit_seconds=value).validate()


class ZeroInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(ui_fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=ui_fixture.QtInterfaceTests.setUp
    tearDown=ui_fixture.QtInterfaceTests.tearDown
    pump=ui_fixture.QtInterfaceTests.pump

    def test_custom_zero_blocks_both_types_without_actions_and_releases(self):
        members=[target('game',self.games[0].id),target('site','example.com')]
        self.app.open_budget(members=members); editor=self.app.budget_editor; key=editor.current
        editor.minutes.setValue(0); self.app.save_budgets()
        self.assertFalse(self.app.budget_error.text()); self.assertNotIn(key,self.app.settings.restriction_plans)
        editor.show_editor(key); self.assertEqual(editor.minutes.value(),0); self.assertFalse(editor.zero_limit_note.isHidden())
        runtime=self.app.restrictions
        self.assertEqual(runtime.state.action(key,'app:fixture.exe'),'cover')
        policy=runtime.browser_policy({}); entry=policy['restrictions'][0]
        self.assertTrue(policy['active']); self.assertEqual(policy['block'],['example.com'])
        self.assertEqual(policy['mode'],'blocklist'); self.assertGreaterEqual(policy['remaining'],30)
        self.assertEqual((entry['kind'],entry['minutes'],entry['is_break']),('cover',0,False))
        self.assertEqual(entry['domains'],['example.com']); self.assertIsNone(entry['grant'])
        self.assertIn(key,runtime.delegated_website_rules())
        editor.minutes.setValue(1); self.app.save_budgets()
        self.assertEqual(runtime.browser_policy({})['restrictions'],[])
        self.assertEqual(runtime.state.action(key,'app:fixture.exe'),'')

    def test_legacy_zero_block_never_activates_dormant_focus_lists(self):
        runtime=self.app.restrictions; now=datetime.now().astimezone()
        budget=Budget('zero','Zero',0,0,(target('site','example.com'),))
        runtime.state.update(now.date().isoformat(),1000,[budget],{})
        base={'active':False,'mode':'allowlist','allow':['allowed.org'],'block':['dormant.org'],'remaining':0}
        policy=runtime.browser_policy(base)
        self.assertEqual((policy['mode'],policy['allow'],policy['block']),('blocklist',[],['example.com']))
        self.assertEqual(base['block'],['dormant.org']); self.assertFalse(base['active'])
        active=dict(base,active=True,remaining=90)
        policy=runtime.browser_policy(active)
        self.assertEqual((policy['mode'],policy['allow'],policy['block'],policy['remaining']),
                         ('allowlist',['allowed.org'],['dormant.org','example.com'],90))
        runtime.state.update(now.date().isoformat(),1001,[replace(budget,members=(target('category','sites'),))],{})
        policy=runtime.browser_policy(active)
        self.assertEqual((policy['active'],policy['mode'],policy['allow']),(True,'allowlist',[]))
        runtime.state.update(now.date().isoformat(),1002,[],{})
        policy=runtime.browser_policy(base)
        self.assertFalse(policy['active']); self.assertEqual(policy['restrictions'],[])

    def test_zero_block_reaches_authenticated_browser_connection_without_a_plan(self):
        import json
        from urllib.request import Request,urlopen
        from gametime.browser_activity import BrowserBridge
        self.app.browser_bridge=BrowserBridge(self.store,port=0)
        self.app.open_budget(member=target('site','example.com')); editor=self.app.budget_editor; key=editor.current
        editor.minutes.setValue(0); self.app.save_budgets()
        bridge=self.app.browser_bridge
        def receive():
            request=Request(f'http://127.0.0.1:{bridge.port}/activity',data=json.dumps(
                {'browser':'brave','domain':'example.com','focused':True,'private':False}).encode(),
                headers={'Authorization':'Bearer '+bridge.token,'Content-Type':'application/json'})
            with urlopen(request,timeout=3) as response: return json.load(response)
        policy=receive()
        self.assertTrue(policy['active']); self.assertEqual(policy['block'],['example.com'])
        self.assertGreaterEqual(policy['remaining'],30); self.assertFalse(self.app.settings.restriction_plans)
        self.app.budget_editor.show_editor(key); editor.minutes.setValue(1); self.app.save_budgets()
        self.assertFalse(receive()['active'])

    def test_zero_individual_game_reopens_as_zero_and_exclusion_still_applies(self):
        gid=self.games[0].id; self.app.open_budget(member=target('game',gid)); editor=self.app.budget_editor
        editor.minutes.setValue(0); self.app.save_budgets(); self.assertFalse(self.app.budget_error.text())
        editor.show_editor('game:'+gid); self.assertEqual(editor.minutes.value(),0)
        runtime=self.app.restrictions; runtime.prepare(datetime.now().astimezone())
        self.assertEqual(runtime.state.action('game:'+gid,'app:fixture.exe'),'cover')
        self.app.catalog.overrides[gid]=False; runtime.prepare(datetime.now().astimezone())
        self.assertEqual(runtime.state.action('game:'+gid,'app:fixture.exe'),'')

    def test_shared_weekday_zero_releases_next_day_and_renders_dashboard(self):
        self.app.open_budget(member=target('category','games')); editor=self.app.budget_editor; schedule=editor.schedule
        schedule.select_days([0]); schedule.limit.setValue(0); self.app.save_budgets()
        self.assertFalse(self.app.budget_error.text())
        monday=datetime(2026,11,2,12).astimezone(); runtime=self.app.restrictions
        runtime.prepare(monday); self.assertEqual(runtime.state.action('shared-games','app:fixture.exe'),'cover')
        self.app.tracker.evaluate(monday); self.assertFalse(self.app.tracker.alerts)
        runtime.prepare(monday+timedelta(days=1)); self.assertEqual(runtime.state.action('shared-games','app:fixture.exe'),'')
        editor.show_editor('shared-games'); schedule.select_days(range(7)); schedule.change('limit_seconds',0); self.app.save_budgets()
        self.assertFalse(self.app.budget_error.text()); self.app.refresh_view(); self.pump(.03)
        editor.show_editor('shared-games'); schedule.limit.setValue(10); self.app.save_budgets()
        self.assertFalse(self.app.budget_error.text()); self.assertEqual(self.app.settings.limit_seconds,600)
        self.assertGreater(self.app.settings.warning_seconds,0)

    def test_native_zero_covers_and_mutes_but_site_only_does_not_cover_browser(self):
        from gametime.tracker import Sample
        from gametime.focus import app_key
        now=datetime.now().astimezone(); runtime=self.app.restrictions
        current=Sample(now,100,str(self.exe),'123:456'); atom=(self.games[0].id,app_key(current.path),'')
        budgets=[Budget('zero','Zero',0,0,(target('game',self.games[0].id),))]
        runtime.state.update(now.date().isoformat(),1000,budgets,{})
        with patch.object(runtime,'prepare'),patch.object(self.app.wellbeing,'atom',return_value=atom), \
             patch('gametime.qt_restrictions.native.open_target',return_value=1),patch('gametime.qt_restrictions.win32.k.CloseHandle'), \
             patch.object(runtime,'present') as present,patch.object(runtime,'close_target') as close, \
             patch.object(runtime.audio,'update') as mute,patch.object(runtime,'show_save_counter'),patch.object(runtime,'process_browser_requests'):
            self.assertTrue(runtime.tick(current)); present.assert_called_once(); close.assert_not_called()
            self.assertEqual(mute.call_args.args[0],[{'path':current.path,'identity':current.identity}])
            runtime.targets.clear(); present.reset_mock()
            runtime.state.update(now.date().isoformat(),1001,[replace(budgets[0],members=(target('site','example.com'),))],{})
            atom=('',app_key(current.path),'example.com'); self.app.wellbeing.atom.return_value=atom
            self.assertFalse(runtime.tick(current)); present.assert_not_called(); self.assertEqual(mute.call_args.args[0],[])

    def test_zero_cover_message_has_no_save_or_close_button_without_plan(self):
        from gametime.tracker import Sample
        runtime=self.app.restrictions; now=datetime.now().astimezone(); current=Sample(now,100,str(self.exe),'123:456')
        runtime.state.update(now.date().isoformat(),1000,[Budget('zero','Zero',0,0,())],{})
        with patch.object(runtime,'legacy_block',return_value=False),patch('gametime.qt_restrictions.native.target_rect',return_value=None):
            runtime.present(current,['zero'],'app:fixture.exe',('',str(self.exe),''))
        self.assertTrue(runtime.screen.extra.isHidden()); self.assertTrue(runtime.screen.quit.isHidden())
        self.assertEqual(runtime.screen.status.text(),self.app.t('Access is blocked because the daily budget is 0.'))


class ZeroSyncTests(unittest.TestCase):
    setUp=sync_fixture.PreferenceSyncTests.setUp
    transfer=sync_fixture.PreferenceSyncTests.transfer

    def test_zero_shared_weekday_and_game_limits_sync(self):
        self.stores[0].save_settings(replace(self.stores[0].settings(),limit_seconds=0,game_limits={'steam:42':0},daily_schedules={'0':{'limit_seconds':0}}))
        self.transfer(0,1); saved=self.stores[1].settings()
        self.assertEqual(saved.limit_seconds,0); self.assertEqual(saved.game_limits,{'steam:42':0})
        self.assertEqual(saved.daily_schedules,{'0':{'limit_seconds':0}})


if __name__=='__main__': unittest.main()
