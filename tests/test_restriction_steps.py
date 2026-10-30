"""Durable schedules, overlap and exact-target boundaries; isolated databases."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from gametime.store import Store
from gametime.model import Settings
from gametime.restriction_policy import Budget, RestrictionState, new_plan, step, validate_plans


class StepsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.store = Store(Path(self.tmp.name)/'usage.sqlite3')
        self.engine = RestrictionState(self.store)
        self.plan = new_plan(); self.plan.update(extension_minutes=3, close_confirmed=True,
            steps=[step('notify',-60,sound=True),step('cover'),step('close',300)])
        self.plans = {'budget':self.plan}; self.day='2026-10-30'
        self.subject='app:c:\\fixture.exe'
    def tearDown(self): self.store.close(); self.tmp.cleanup()
    def update(self, used=120, now=1000, key='budget'):
        self.engine.update(self.day,now,[Budget(key,'Fixture',120,used,())],self.plans)
    def test_warning_only_has_no_block_and_delivery_is_durable(self):
        self.plan['steps']=[step('notify',-60,popup=True)]; self.update(60)
        warning=self.engine.warnings('budget')[0]
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.engine.delivered('budget',warning['id'])
        self.engine=RestrictionState(self.store); self.update(60)
        self.assertEqual(self.engine.warnings('budget'),[])
    def test_post_limit_time_runs_without_more_activity(self):
        self.update(); self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.update(now=1299); self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.update(now=1300); self.assertEqual(self.engine.action('budget',self.subject),'close')
    def test_game_identity_merge_keeps_consumed_allowance(self):
        from gametime.restriction_policy import remap_state
        self.update(); self.engine.extend(['budget'],self.subject)
        with self.store.db: remap_state(self.store.db,'budget','new-budget')
        self.engine=RestrictionState(self.store)
        self.engine.update(self.day,1001,[Budget('new-budget','x',120,120,())],{'new-budget':self.plan})
        self.assertIsNone(self.engine.extend(['new-budget'],self.subject))
        self.assertEqual(self.engine.grant('new-budget',self.subject)['until'],1180)
    def test_extension_once_survives_restart_and_cannot_unlock_another_target(self):
        self.update(); self.assertEqual(self.engine.extend(['budget'],self.subject),1180)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.assertEqual(self.engine.action('budget','app:another.exe'),'cover')
        self.engine=RestrictionState(self.store); self.update(now=1020)
        self.assertIsNone(self.engine.extend(['budget'],self.subject))
        self.update(now=1180); self.assertEqual(self.engine.action('budget',self.subject),'close')
    def test_site_allowance_returns_to_blocking_not_implicit_tab_close(self):
        self.update(); subject='site:example.com:token'
        self.engine.extend(['budget'],subject); self.update(now=1180)
        self.assertEqual(self.engine.action('budget',subject),'cover')
    def test_multiple_budgets_get_shortest_allowance_and_all_are_consumed(self):
        self.plans['other']=deepcopy(self.plan); self.plans['other']['extension_minutes']=1
        self.engine.update(self.day,1000,[Budget(k,k,120,120,()) for k in self.plans],self.plans)
        self.assertEqual(self.engine.extend(list(self.plans),self.subject),1060)
        self.assertTrue(all(self.engine.rows[k]['used_extension'] for k in self.plans))
    def test_non_extendable_overlap_does_not_consume_any_allowance(self):
        self.plans['other']=deepcopy(self.plan); self.plans['other']['extension_minutes']=0
        self.engine.update(self.day,1000,[Budget(k,k,120,120,()) for k in self.plans],self.plans)
        self.assertIsNone(self.engine.extend(list(self.plans),self.subject))
        self.assertFalse(self.engine.rows['budget']['used_extension'])
    def test_independent_connection_cannot_grant_twice(self):
        self.update(); other=Store(self.store.path)
        try:
            competitor=RestrictionState(other); competitor.update(self.day,1000,[Budget('budget','x',120,120,())],self.plans)
            self.assertIsNotNone(self.engine.extend(['budget'],self.subject))
            self.assertIsNone(competitor.extend(['budget'],self.subject))
        finally: other.close()
    def test_increased_budget_and_removed_plan_cancel_pending_close(self):
        self.update(); self.engine.extend(['budget'],self.subject)
        self.engine.update(self.day,2000,[Budget('budget','x',500,120,())],self.plans)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.assertTrue(self.engine.rows['budget']['used_extension'])
        self.engine.update(self.day,2100,[],{})
        self.assertEqual(self.engine.action('budget',self.subject),'')
    def test_edited_plan_cancels_old_grant_without_refreshing_allowance(self):
        self.update(); self.engine.extend(['budget'],self.subject)
        self.plan['steps']=[step('notify',popup=True)]; self.update(now=2000)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.assertTrue(self.engine.rows['budget']['used_extension'])
    def test_day_change_renews_but_clock_setting_change_does_not(self):
        self.update(); self.engine.extend(['budget'],self.subject)
        self.engine.move_day(self.day,'2026-10-29'); self.day='2026-10-29'; self.update()
        self.assertIsNone(self.engine.extend(['budget'],self.subject))
        self.day='2026-10-31'; self.update(now=90000)
        self.assertIsNotNone(self.engine.extend(['budget'],self.subject))
    def test_validation_rejects_danger_without_ack_and_nonfinite_values(self):
        for value in (-1,61,True,1.5):
            candidate=deepcopy(self.plan); candidate['extension_minutes']=value
            with self.assertRaises(ValueError): validate_plans({'b':candidate})
        for value in (float('nan'),float('inf'),True):
            candidate=deepcopy(self.plan); candidate['steps'][0]['offset']=value
            with self.assertRaises(ValueError): validate_plans({'b':candidate})
        candidate=deepcopy(self.plan); candidate['close_confirmed']=False
        with self.assertRaises(ValueError): validate_plans({'b':candidate})
    def test_settings_roundtrip_defaults_and_local_scope(self):
        self.assertEqual(Settings().restriction_plans,{})
        self.store.save_settings(replace(Settings(),restriction_plans=self.plans))
        self.assertEqual(self.store.settings().restriction_plans,self.plans)
        from gametime.preferences_sync import CONFIG_FIELDS
        self.assertNotIn('restriction_plans',CONFIG_FIELDS)


class NativeOwnershipTests(unittest.TestCase):
    def test_critical_processes_and_own_python_are_never_targets(self):
        from gametime.restriction_native import permitted
        for name in (r'C:\Windows\System32\winlogon.exe',r'C:\Apps\steam.exe',r'C:\Apps\python.exe',
                     r'C:\Apps\EasyAntiCheat.exe',r'C:\Apps\GameTimeMonitor.exe'):
            self.assertFalse(permitted(name,'123:456'))
    def test_failed_identity_never_sends_close_or_terminate(self):
        from gametime import restriction_native as native
        with (patch.object(native,'open_target',return_value=None),patch.object(native.u,'PostMessageW') as close,
                patch.object(native.k,'TerminateProcess') as terminate):
            self.assertFalse(native.close_target('fixture.exe','12:13'))
            close.assert_not_called(); terminate.assert_not_called()
