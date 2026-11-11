"""Early breaks consume a full pause and renew only their usage interval."""
from dataclasses import replace
from pathlib import Path
import tempfile,unittest
from gametime.store import Store
from gametime.restriction_policy import Budget,RestrictionState,new_plan,step,validate_plans
from gametime.timer_view import project


class EarlyBreakTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'usage.sqlite3')
        self.state=RestrictionState(self.store);self.plan=new_plan()
        self.item=step('break',900,identity='pause',break_mode='cover',break_minutes=5);self.item['allow_early_break']=True
        self.plan['steps']=[self.item];self.budget=Budget('youtube','YouTube',3600,720,())
        self.update()
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def update(self,now=1000,used=720,day='2026-11-11'):
        self.budget=replace(self.budget,used=used);self.state.update(day,now,[self.budget],{'youtube':self.plan})
    def test_twelve_minutes_then_full_break_then_fifteen_new_minutes(self):
        self.assertTrue(self.state.start_early_break('youtube','pause'))
        self.assertEqual(self.state.break_remaining('youtube'),300)
        self.assertFalse(self.state.start_early_break('youtube','pause'))
        self.update(1299);self.assertEqual(self.state.action('youtube','site:youtube.com'),'cover')
        self.update(1300);self.assertEqual(self.state.action('youtube','site:youtube.com'),'')
        self.assertEqual(self.state.rows['youtube']['breaks']['pause']['next_at'],1620)
        self.update(1400,1619);self.assertEqual(self.state.break_remaining('youtube'),0)
        self.update(1401,1620);self.assertEqual(self.state.break_remaining('youtube'),300)
        self.assertEqual(self.state.budgets['youtube'].limit,3600)
    def test_restart_and_renewal_preserve_the_whole_break(self):
        self.state.start_early_break('youtube','pause');self.state=RestrictionState(self.store)
        self.update(1100,0,'2026-11-12');self.assertEqual(self.state.break_remaining('youtube'),200)
        self.update(1300,0,'2026-11-12');self.assertEqual(self.state.rows['youtube']['breaks']['pause']['next_at'],900)
    def test_rejects_disabled_or_stale_buttons_and_never_resets_daily_limit(self):
        self.assertFalse(self.state.start_early_break('missing','pause'))
        self.assertFalse(self.state.start_early_break('youtube','other'))
        self.item.pop('allow_early_break');self.update();self.assertFalse(self.state.start_early_break('youtube','pause'))
        self.item['allow_early_break']=True;self.update(1000,3600);self.assertFalse(self.state.start_early_break('youtube','pause'))
        self.budget=replace(self.budget,breaks_allowed=False);self.update();self.assertFalse(self.state.start_early_break('youtube','pause'))
    def test_regular_restrictions_and_existing_breaks_win(self):
        self.plan['steps'].append(step('cover',600,usage=True));self.update()
        self.assertFalse(self.state.start_early_break('youtube','pause'))
        self.plan['steps'].pop();self.update(1000,900)
        self.assertFalse(self.state.start_early_break('youtube','pause'));self.assertEqual(self.state.break_remaining('youtube'),300)
    def test_mixed_member_targets_start_together_using_their_configured_lengths(self):
        self.item['targets']={'app':{'break_minutes':4},'site':{'break_minutes':6}};self.update()
        self.assertTrue(self.state.start_early_break('youtube','pause'))
        self.assertEqual(self.state.break_remaining('youtube','app:fixture.exe'),240)
        self.assertEqual(self.state.break_remaining('youtube','site:youtube.com'),360)
    def test_timer_button_is_opt_in_and_absent_during_pause_or_grant(self):
        def view():return project(self.budget,self.plan,self.state.rows['youtube'],self.state.now,'site:youtube.com')
        self.assertEqual(view().seconds,180);self.assertEqual(view().break_step,'pause')
        self.item.pop('allow_early_break');self.update();self.assertEqual(view().break_step,'')
        self.item['allow_early_break']=True;self.update();self.state.start_early_break('youtube','pause')
        self.assertEqual(view().event,'break_active');self.assertEqual(view().break_step,'')
    def test_option_is_valid_only_for_repeating_time_breaks(self):
        validate_plans({'youtube':self.plan})
        for value in (1,'yes'):
            self.item['allow_early_break']=value
            with self.assertRaises(ValueError):validate_plans({'youtube':self.plan})
        self.item['allow_early_break']=True;self.item.update(time_mode='clock',clock_minute=900)
        with self.assertRaises(ValueError):validate_plans({'youtube':self.plan})
