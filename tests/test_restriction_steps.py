"""Durable schedules, overlap and exact-target boundaries; isolated databases."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from gametime.store import Store
from gametime.model import Settings
from gametime.restriction_policy import Budget, RestrictionState, new_plan, step, validate_plans,legacy_active,legacy_warning_active,legacy_restriction_active


class StepsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.store = Store(Path(self.tmp.name)/'usage.sqlite3')
        self.engine = RestrictionState(self.store)
        self.plan = new_plan(); self.plan.update(extension_minutes=3, close_confirmed=True,
            steps=[step('notify',-60,sound=True),step('cover'),step('close',300)])
        self.plans = {'budget':self.plan}; self.day='2026-10-30'
        self.subject='app:c:\\fixture.exe'
    def tearDown(self): self.store.close(); self.tmp.cleanup()
    def update(self, used=120, now=1000, key='budget', limit=120):
        self.engine.update(self.day,now,[Budget(key,'Fixture',limit,used,())],self.plans)
    def test_warning_only_has_no_block_and_delivery_is_durable(self):
        self.plan['steps']=[step('notify',-60,popup=True)]; self.update(60)
        warning=self.engine.warnings('budget')[0]
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.engine.delivered('budget',warning['id'])
        self.engine=RestrictionState(self.store); self.update(60)
        self.assertEqual(self.engine.warnings('budget'),[])
    def test_post_limit_time_runs_without_more_activity(self):
        self.plan['extension_minutes']=0
        self.update(); self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.update(now=1299); self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.update(now=1300); self.assertEqual(self.engine.action('budget',self.subject),'close')
    def test_use_time_actions_ignore_idle_wall_time_and_work_before_limit(self):
        self.plan['steps']=[step('notify',30,popup=True,usage=True),step('cover',60,usage=True),step('close',90,usage=True)]
        validate_plans(self.plans)
        self.update(29,1000); self.assertEqual(self.engine.warnings('budget'),[])
        self.update(30,1001); self.assertEqual(len(self.engine.warnings('budget')),1)
        self.update(60,1002); self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.assertEqual(self.engine.extend(['budget'],self.subject),1182)
        self.update(60,1100); self.assertEqual(self.engine.action('budget',self.subject),'')
        self.update(60,1182); self.assertEqual(self.engine.action('budget',self.subject),'close')
        self.update(90,1183); self.assertEqual(self.engine.action('budget','app:another.exe'),'close')

    def test_legacy_expiry_relative_timing_is_unchanged(self):
        self.plan['extension_minutes']=0
        self.plan['steps']=[step('close',300)]
        self.update(120,1000); self.update(120,1299)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.update(120,1300); self.assertEqual(self.engine.action('budget',self.subject),'close')

    def test_break_repeats_after_more_use_and_releases_without_activity(self):
        self.plan['steps']=[step('break',60,usage=True,break_mode='cover',break_minutes=2)]
        validate_plans(self.plans)
        self.update(59,1000,limit=180); self.assertEqual(self.engine.action('budget',self.subject),'')
        self.update(60,1001,limit=180); self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.assertEqual(self.engine.break_remaining('budget'),120)
        self.assertEqual(self.engine.allowance(['budget'],self.subject),0)
        self.update(60,1120,limit=180); self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.update(60,1121,limit=180); self.assertEqual(self.engine.action('budget',self.subject),'')
        self.update(119,1200,limit=180); self.assertEqual(self.engine.action('budget',self.subject),'')
        self.update(120,1201,limit=180); self.assertEqual(self.engine.action('budget',self.subject),'cover')

    def test_break_never_starts_at_or_after_budget_expiry(self):
        self.plan['steps']=[step('break',60,usage=True,break_mode='cover',break_minutes=2)]
        self.update(60,1000); self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.update(60,1120); self.assertEqual(self.engine.action('budget',self.subject),'')
        self.update(119,1200); self.assertEqual(self.engine.action('budget',self.subject),'')
        self.update(120,1201); self.assertEqual(self.engine.action('budget',self.subject),'')
        self.update(150,1202); self.assertEqual(self.engine.action('budget',self.subject),'')
        self.engine=RestrictionState(self.store); self.update(150,1300)
        self.assertEqual(self.engine.action('budget',self.subject),'')

    def test_redirect_break_covers_apps_redirects_sites_and_releases_both(self):
        pause=step('break',60,usage=True,break_mode='redirect',break_minutes=2)
        pause['redirect_url']=''; self.plan['steps']=[pause]
        validate_plans(self.plans)
        site='site:example.com:token'
        for used,now,app_action,site_action in (
                (59,1000,'',''),(60,1001,'cover','redirect'),(60,1120,'cover','redirect'),
                (60,1121,'',''),(119,1200,'',''),(120,1201,'cover','redirect')):
            with self.subTest(used=used,now=now):
                self.update(used,now,limit=180)
                self.assertEqual(self.engine.action('budget',self.subject),app_action)
                self.assertEqual(self.engine.action('budget',site),site_action)
                self.assertEqual(self.engine.allowance(['budget'],self.subject),0)
        self.engine=RestrictionState(self.store); self.day='2026-10-31'
        self.update(0,1250,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.assertEqual(self.engine.action('budget',site),'redirect')
        self.update(0,1321,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.assertEqual(self.engine.action('budget',site),'')

    def test_redirect_break_is_ranked_as_cover_for_apps_and_yields_to_save_time(self):
        pause=step('break',60,usage=True,break_mode='redirect',break_minutes=4)
        pause['redirect_url']='https://rest.example.org/'
        self.plan['steps']=[pause,step('break',60,usage=True,break_mode='minimize')]
        self.update(60,1000,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.assertEqual(self.engine.action('budget','site:example.com'),'minimize')
        self.plan['steps']=[pause,step('restrict',60,usage=True)]
        self.update(60,1001,limit=500)
        self.assertEqual(self.engine.action('budget','site:example.com'),'cover')
        self.assertEqual(self.engine.extend(['budget'],self.subject,'123:456'),1181)
        self.update(60,1060,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.assertGreater(self.engine.break_remaining('budget'),0)
        self.update(60,1181,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'close')

    def test_break_does_not_start_when_a_separate_budget_cap_is_exhausted(self):
        self.plan['steps']=[step('break',60,usage=True,break_mode='cover',break_minutes=2)]
        budget=Budget('budget','Fixture',120,60,(),breaks_allowed=False)
        self.engine.update(self.day,1000,[budget],self.plans)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.engine.update(self.day,1001,[replace(budget,breaks_allowed=True)],self.plans)
        self.assertEqual(self.engine.action('budget',self.subject),'cover')

    def test_existing_break_finishes_if_budget_expires_during_it(self):
        self.plan['steps']=[step('break',60,usage=True,break_mode='cover',break_minutes=2)]
        self.update(60,1000); self.update(120,1050)
        self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.update(120,1120); self.assertEqual(self.engine.action('budget',self.subject),'')

    def test_break_survives_restart_and_crosses_daily_boundary(self):
        self.plan['steps']=[step('break',60,usage=True,break_minutes=2)]
        self.update(60,1000); self.assertEqual(self.engine.action('budget',self.subject),'minimize')
        self.engine=RestrictionState(self.store); self.update(60,1050)
        self.assertEqual(self.engine.break_remaining('budget'),70)
        self.day='2026-10-31'; self.engine=RestrictionState(self.store); self.update(0,1060)
        self.assertEqual(self.engine.action('budget',self.subject),'minimize')
        self.update(0,1120); self.assertEqual(self.engine.action('budget',self.subject),'')
        self.update(60,1121); self.assertEqual(self.engine.action('budget',self.subject),'minimize')

    def test_break_does_not_interrupt_existing_restriction_save_grant(self):
        self.plan['steps']=[step('cover',0,usage=True),step('break',60,usage=True,break_mode='minimize')]
        self.update(0,1000); self.assertIsNotNone(self.engine.extend(['budget'],self.subject))
        self.update(60,1001); self.assertEqual(self.engine.action('budget',self.subject),'')
        self.assertIsNotNone(self.engine.grant('budget',self.subject))
        self.assertEqual(self.engine.allowance(['budget'],self.subject),0)
        self.update(60,1301); self.assertEqual(self.engine.action('budget',self.subject),'close')

    def test_regular_restriction_takes_priority_and_break_allows_saving(self):
        self.plan['steps']=[step('break',60,usage=True,break_mode='close',break_minutes=2),
                            step('restrict',60,usage=True)]
        self.update(60,1000,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.assertEqual(self.engine.break_remaining('budget'),120)
        self.assertEqual(self.engine.extend(['budget'],self.subject,'123:456'),1180)
        self.update(60,1060,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.assertEqual(self.engine.break_remaining('budget'),60)
        self.update(60,1120,limit=500)
        self.assertEqual(self.engine.break_remaining('budget'),0)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.update(60,1180,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'close')

    def test_regular_restriction_dominates_break_in_another_budget(self):
        self.plan['steps']=[step('restrict',60,usage=True)]
        pause=new_plan(); pause['steps']=[step('break',60,usage=True,break_mode='close',break_minutes=2)]
        plans={'budget':self.plan,'pause':pause}
        budgets=[Budget(key,key,500,60,()) for key in plans]
        self.engine.update(self.day,1000,budgets,plans)
        self.assertEqual(self.engine.dominant(['pause','budget'],self.subject),['budget'])
        self.assertEqual(self.engine.extend(['budget'],self.subject,'123:456'),1180)
        self.engine.update(self.day,1050,budgets,plans)
        self.assertEqual(self.engine.dominant(['pause','budget'],self.subject,'123:456'),['budget'])
        self.assertEqual(self.engine.break_remaining('pause'),70)

    def test_break_clock_correction_and_idle_ticks_do_not_write_repeatedly(self):
        self.plan['steps']=[step('break',60,usage=True,break_minutes=2)]
        self.update(60,1000); writes=self.store.db.total_changes
        for now in range(1001,1021): self.update(60,now)
        self.assertEqual(self.store.db.total_changes,writes)
        self.day='2026-10-29'; self.engine=RestrictionState(self.store); self.update(0,1021)
        self.assertEqual(self.engine.break_remaining('budget'),99)
        self.assertEqual(self.engine.action('budget',self.subject),'minimize')

    def test_break_validation_and_close_consent(self):
        self.plan['steps']=[step('break',60,usage=True,break_mode='close')]
        self.plan['close_confirmed']=False
        with self.assertRaises(ValueError): validate_plans(self.plans)
        self.plan['close_confirmed']=True; validate_plans(self.plans)
        for key,value in (('break_mode','notify'),('break_mode',[]),('break_minutes',0),('break_minutes',True),('offset',0)):
            candidate=deepcopy(self.plan); candidate['steps'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError): validate_plans({'budget':candidate})

    def test_explicit_close_offers_one_save_interval_without_delaying_browser_tab_close(self):
        self.plan['steps']=[step('close',60,usage=True)]
        self.update(60,1000,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.assertEqual(self.engine.action('budget','site:example.com'),'close')
        self.assertEqual(self.engine.allowance(['budget'],'site:example.com'),0)
        self.assertEqual(self.engine.extend(['budget'],self.subject,'123:456'),1180)
        self.engine=RestrictionState(self.store); self.update(60,1050,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.assertIsNone(self.engine.extend(['budget'],self.subject,'123:456'))
        self.update(60,1180,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'close')
        self.engine.finish_grant('budget',self.subject,'123:456')
        self.assertEqual(self.engine.action('budget',self.subject,'124:789'),'close')

    def test_closing_break_offers_save_time_once_and_releases_after_break(self):
        self.plan.update(extension_minutes=1,steps=[step('break',60,usage=True,break_mode='close',break_minutes=2)])
        self.update(60,1000,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.assertEqual(self.engine.action('budget','site:example.com'),'close')
        self.assertEqual(self.engine.allowance(['budget'],'site:example.com'),0)
        self.assertEqual(self.engine.extend(['budget'],self.subject,'123:456'),1060)
        self.engine=RestrictionState(self.store); self.update(60,1020,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.assertIsNone(self.engine.extend(['budget'],self.subject,'123:456'))
        self.update(60,1060,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'close')
        self.engine.finish_grant('budget',self.subject,'123:456')
        self.assertEqual(self.engine.action('budget',self.subject,'124:789'),'close')
        self.update(60,1120,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.update(120,1200,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject),'close')
        self.assertEqual(self.engine.allowance(['budget'],self.subject),0)

    def test_requested_break_save_interval_survives_short_break_and_renewal(self):
        self.plan['steps']=[step('break',60,usage=True,break_mode='close',break_minutes=1)]
        self.update(60,1000,limit=500)
        self.assertEqual(self.engine.extend(['budget'],self.subject,'123:456'),1180)
        self.update(60,1060,limit=500)
        self.assertEqual(self.engine.break_remaining('budget'),0)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.engine=RestrictionState(self.store); self.day='2026-10-31'; self.update(0,1100,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.update(0,1180,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'close')
        self.assertEqual(self.engine.action('budget',self.subject,'124:789'),'')
        self.engine.finish_grant('budget',self.subject,'123:456')
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.assertFalse(self.engine.rows['budget']['used_extension'])

    def test_zero_save_time_keeps_all_explicit_closures_immediate(self):
        for item in (step('close',60,usage=True),step('break',60,usage=True,break_mode='close')):
            with self.subTest(kind=item['kind']):
                self.plan.update(extension_minutes=0,steps=[item]); self.update(60,1000,limit=500)
                self.assertEqual(self.engine.action('budget',self.subject),'close')
                self.assertIsNone(self.engine.extend(['budget'],self.subject,'123:456'))

    def test_removing_closing_break_cancels_its_pending_saved_closure(self):
        self.plan['steps']=[step('break',60,usage=True,break_mode='close',break_minutes=1)]
        self.update(60,1000,limit=500); self.engine.extend(['budget'],self.subject,'123:456')
        self.plan['steps']=[]; self.update(60,1180,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.assertIsNone(self.engine.grant('budget',self.subject,'123:456'))

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

    def test_minimize_save_allowance_survives_restart_and_closes_at_deadline(self):
        self.plan['steps']=[step('minimize',60,usage=True)]
        self.update(60,1000,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject),'minimize')
        self.assertEqual(self.engine.allowance(['budget'],self.subject),3)
        self.assertEqual(self.engine.extend(['budget'],self.subject),1180)
        self.engine=RestrictionState(self.store); self.update(60,1050,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.assertEqual(self.engine.allowance(['budget'],self.subject),0)
        self.update(60,1180,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject),'close')

    def test_unified_restriction_requests_time_and_closes_after_it(self):
        self.plan['steps']=[step('restrict',60,usage=True)]
        validate_plans(self.plans)
        self.update(60,1000,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject),'cover')
        self.assertEqual(self.engine.extend(['budget'],self.subject,'123:456'),1180)
        self.update(60,1100,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.assertEqual(self.engine.action('budget',self.subject,''),'close')
        self.update(60,1180,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'close')

    def test_unified_restriction_without_save_time_closes_apps_but_covers_websites(self):
        self.plan.update(extension_minutes=0,steps=[step('restrict',60,usage=True)])
        self.update(60,1000,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject),'close')
        self.assertEqual(self.engine.action('budget','site:example.com:token'),'cover')
        self.assertEqual(self.engine.allowance(['budget'],self.subject),0)

    def test_reopened_app_closes_after_budget_save_allowance_was_consumed(self):
        self.plan['steps']=[step('restrict',60,usage=True)]
        self.update(60,1000,limit=180)
        self.engine.extend(['budget'],self.subject,'123:456')
        self.update(60,1181,limit=180)
        self.engine.finish_grant('budget',self.subject,'123:456')
        self.assertEqual(self.engine.action('budget',self.subject,'124:789'),'close')

    def test_minimize_site_save_allowance_reblocks_the_tab_at_deadline(self):
        self.plan['steps']=[step('minimize',60,usage=True)]
        subject='site:example.com:token'
        self.update(60,1000,limit=180)
        self.assertEqual(self.engine.extend(['budget'],subject),1180)
        self.update(60,1180,limit=180)
        self.assertEqual(self.engine.action('budget',subject),'cover')

    def test_save_allowance_crosses_renewal_and_only_closes_original_process(self):
        self.plan['steps']=[step('minimize',60,usage=True)]
        self.update(60,1000,limit=180)
        self.assertEqual(self.engine.extend(['budget'],self.subject,'123:456'),1180)
        self.day='2026-10-31'; self.engine=RestrictionState(self.store)
        self.update(0,1050,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.assertEqual(self.engine.action('budget',self.subject,'123:999'),'')
        self.update(0,1180,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'close')
        self.assertEqual(self.engine.action('budget',self.subject,'123:999'),'')
        self.engine.finish_grant('budget',self.subject,'123:999')
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'close')
        self.engine.finish_grant('budget',self.subject,'123:456')
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.assertFalse(self.engine.rows['budget']['used_extension'])

    def test_save_grant_can_recover_after_restart_past_the_deadline(self):
        self.plan['steps']=[step('minimize',60,usage=True)]
        self.update(60,1000,limit=180)
        self.engine.extend(['budget'],self.subject,'123:456')
        self.day='2026-10-31'; self.engine=RestrictionState(self.store); self.update(0,1200,limit=180)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'close')

    def test_site_save_grant_crosses_renewal_but_does_not_stop_the_break(self):
        self.plan['steps']=[step('restrict',60,usage=True),step('break',60,usage=True,break_mode='minimize',break_minutes=4)]
        subject='site:example.com:token'
        self.update(60,1000,limit=500)
        self.assertEqual(self.engine.extend(['budget'],subject),1180)
        self.day='2026-10-31'; self.engine=RestrictionState(self.store); self.update(0,1050,limit=500)
        self.assertEqual(self.engine.action('budget',subject),'')
        self.assertEqual(self.engine.break_remaining('budget'),190)
        self.update(0,1180,limit=500)
        self.assertEqual(self.engine.action('budget',subject),'minimize')
        self.assertEqual(self.engine.break_remaining('budget'),60)
        self.assertFalse(self.engine.rows['budget']['used_extension'])
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

    def test_break_redirect_accepts_only_safe_web_addresses(self):
        candidate=deepcopy(self.plan)
        pause=step('break',60,usage=True,break_mode='redirect',break_minutes=5)
        candidate['steps']=[pause]
        for address in ('javascript:alert(1)', 'file:///C:/secret', 'https://user:pass@example.com/',
                        'https://example.com\\attacker', 'https://example.com/\nnext', 'https://example.com/'+('x'*401)):
            pause['redirect_url']=address
            with self.subTest(address=address),self.assertRaises(ValueError): validate_plans({'b':candidate})
        pause['redirect_url']='https://example.com/relax?q=tea'
        self.assertEqual(validate_plans({'b':candidate})['b']['steps'][0]['redirect_url'],pause['redirect_url'])
        pause['redirect_url']=''
        self.assertEqual(validate_plans({'b':candidate})['b']['steps'][0]['redirect_url'],'')
    def test_settings_roundtrip_defaults_and_local_scope(self):
        self.assertEqual(Settings().restriction_plans,{})
        self.store.save_settings(replace(Settings(),restriction_plans=self.plans))
        self.assertEqual(self.store.settings().restriction_plans,self.plans)
        from gametime.preferences_sync import CONFIG_FIELDS
        self.assertNotIn('restriction_plans',CONFIG_FIELDS)

    def test_additive_plan_keeps_legacy_and_can_disable_only_its_warning(self):
        plan=new_plan(legacy=True); plan['steps']=[step('notify',-60,popup=True)]
        validate_plans({'budget':plan})
        self.assertTrue(legacy_active({'budget':plan},'budget'))
        self.assertTrue(legacy_warning_active({'budget':plan},'budget'))
        plan['legacy_warning']=False
        self.assertTrue(legacy_active({'budget':plan},'budget'))
        self.assertFalse(legacy_warning_active({'budget':plan},'budget'))
        self.assertFalse(legacy_active({'budget':new_plan()},'budget'))
        for change in ({'legacy':False},{'legacy_warning':'no'},{'unexpected':True}):
            candidate=deepcopy(plan); candidate.update(change)
            with self.assertRaises(ValueError): validate_plans({'budget':candidate})

    def test_legacy_game_restriction_can_be_disabled_without_disabling_alerts(self):
        key='game:fixture'; plan=new_plan(legacy=True); plan['legacy_enforce']=False
        validate_plans({key:plan})
        self.assertTrue(legacy_active({key:plan},key)); self.assertTrue(legacy_warning_active({key:plan},key))
        self.assertFalse(legacy_restriction_active({key:plan},key))
        self.assertTrue(legacy_restriction_active({},key))
        invalid=deepcopy(plan); invalid['legacy_enforce']='no'
        with self.assertRaises(ValueError): validate_plans({key:invalid})

    def test_tracker_delivers_old_warning_alongside_new_steps_and_can_remove_it(self):
        from datetime import datetime
        from gametime.model import Catalog
        from gametime.tracker import Tracker
        day='2026-10-30'; self.store.add_usage({(day,'fixture'):6000})
        plan=new_plan(legacy=True); plan['steps']=[step('notify',-300,popup=True)]
        catalog=Catalog(replace(Settings(),restriction_plans={'shared-games':plan}))
        tracker=Tracker(self.store,catalog); tracker.evaluate(datetime.fromisoformat(day+'T12:00'))
        self.assertEqual([alert.kind for alert in tracker.alerts],['warning'])
        plan['legacy_warning']=False; tracker.evaluate(datetime.fromisoformat(day+'T12:00'))
        self.assertFalse(tracker.alerts)
        self.store.add_usage({(day,'fixture'):1200}); tracker.cache.clear()
        tracker.evaluate(datetime.fromisoformat(day+'T12:01'))
        self.assertFalse(tracker.alerts)  # No implicit expiry warning beside explicit actions.


class NativeOwnershipTests(unittest.TestCase):
    def test_focusing_an_overlay_target_preserves_its_existing_window_size(self):
        from gametime import restriction_native as native
        for minimized in (False,True):
            with (patch.object(native,'open_target',return_value=123),patch.object(native,'windows',return_value=[456]),
                  patch.object(native.u,'IsIconic',return_value=minimized),patch.object(native.u,'ShowWindowAsync') as show,
                  patch.object(native.u,'SetForegroundWindow',return_value=True) as focus,patch.object(native.k,'CloseHandle')):
                self.assertTrue(native.restore_target(r'C:\Fixture\fixture.exe','12:34'))
                if minimized:show.assert_called_once_with(456,9)
                else:show.assert_not_called()
                focus.assert_called_once_with(456)

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
