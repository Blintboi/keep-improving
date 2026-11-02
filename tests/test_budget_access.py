"""Clock-triggered actions, optional usage caps and budget-local weekdays."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import math
import unittest
from PySide6.QtCore import QTime
import test_qt_ui as ui_fixture
import test_restriction_steps as policy_fixture
from gametime.model import Settings
from gametime import budget_access
from gametime.budget import remaining_budget,gameplay_budget
from gametime.qt_budgets import new_rule
from gametime.restriction_policy import Budget,RestrictionState,new_plan,step,validate_plans
from gametime.wellbeing import target


def clock_step(kind='cover',minute=22*60,**kwargs):
    result=step(kind,usage=True,**kwargs); result.update(time_mode='clock',clock_minute=minute,offset=0)
    return result


class ClockPolicyTests(unittest.TestCase):
    setUp=policy_fixture.StepsTests.setUp
    tearDown=policy_fixture.StepsTests.tearDown

    def test_clock_boundary_and_renewal_ignore_accumulated_usage(self):
        self.plan.update(steps=[clock_step()],extension_minutes=0)
        budget=Budget('budget','Clock',math.inf,999999,(),clock_deadlines={1320:1100})
        for now,expected in ((1099,''),(1100,'cover'),(2000,'cover')):
            self.engine.update(self.day,now,[budget],self.plans)
            self.assertEqual(self.engine.action('budget',self.subject),expected)
        self.engine=RestrictionState(self.store)
        self.engine.update('2026-10-31',2001,[replace(budget,used=0,clock_deadlines={1320:3000})],self.plans)
        self.assertEqual(self.engine.action('budget',self.subject),'')

    def test_clock_break_uses_scheduled_end_and_does_not_repeat_or_catch_up(self):
        self.plan['steps']=[clock_step('break',break_mode='cover',break_minutes=2)]
        budget=Budget('budget','Clock',math.inf,0,(),clock_deadlines={1320:1100})
        for now,remaining in ((1099,0),(1100,120),(1150,70),(1220,0),(1400,0)):
            self.engine.update(self.day,now,[budget],self.plans)
            self.assertEqual(self.engine.break_remaining('budget'),remaining)
        self.engine=RestrictionState(self.store)
        self.engine.update('2026-10-31',3000,[replace(budget,clock_deadlines={1320:2700})],self.plans)
        self.assertEqual(self.engine.action('budget',self.subject),'')

    def test_clock_break_continues_through_renewal(self):
        self.plan['steps']=[clock_step('break',break_mode='cover',break_minutes=5)]
        budget=Budget('budget','Clock',math.inf,0,(),clock_deadlines={1320:1000})
        self.engine.update(self.day,1000,[budget],self.plans)
        self.engine=RestrictionState(self.store)
        self.engine.update('2026-10-31',1100,[replace(budget,clock_deadlines={1320:2000})],self.plans)
        self.assertEqual(self.engine.break_remaining('budget'),200)
        self.engine.update('2026-10-31',1300,[replace(budget,clock_deadlines={1320:2000})],self.plans)
        self.assertEqual(self.engine.break_remaining('budget'),0)

    def test_clock_warning_is_once_per_budget_day_and_survives_restart(self):
        self.plan['steps']=[clock_step('notify',popup=True)]
        budget=Budget('budget','Clock',math.inf,0,(),clock_deadlines={1320:1000})
        self.engine.update(self.day,1000,[budget],self.plans)
        warning=self.engine.warnings('budget')[0]; self.engine.delivered('budget',warning['id'])
        self.engine=RestrictionState(self.store); self.engine.update(self.day,1001,[budget],self.plans)
        self.assertEqual(self.engine.warnings('budget'),[])

    def test_clock_close_keeps_one_time_save_interval_through_renewal(self):
        self.plan['steps']=[clock_step('restrict')]
        budget=Budget('budget','Clock',math.inf,0,(),clock_deadlines={1320:1000})
        self.engine.update(self.day,1000,[budget],self.plans)
        self.assertEqual(self.engine.extend(['budget'],self.subject,'123:456'),1180)
        self.engine.update('2026-10-31',1100,[replace(budget,clock_deadlines={1320:2000})],self.plans)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'')
        self.engine.update('2026-10-31',1180,[replace(budget,clock_deadlines={1320:2000})],self.plans)
        self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'close')

    def test_validation_accepts_clock_steps_and_rejects_bad_times_and_days(self):
        for kind in ('notify','cover','restrict','break'):
            self.plan['steps']=[clock_step(kind,popup=kind=='notify')]; validate_plans(self.plans)
        for value in (-1,1440,True,1.5,None):
            self.plan['steps']=[dict(clock_step(),clock_minute=value)]
            with self.subTest(value=value),self.assertRaises(ValueError): validate_plans(self.plans)
        for days in ([7],[-1],[True],[1,1],None,'Monday'):
            with self.subTest(days=days),self.assertRaises(ValueError): replace(Settings(),budget_active_days={'budget':days}).validate()

    def test_overnight_deadline_and_active_days_follow_the_renewal_day(self):
        plan=new_plan(); plan['steps']=[clock_step(minute=2*60)]
        settings=replace(Settings(),budget_reset_overrides={'budget':6*60},
                         budget_active_days={'budget':[0]},restriction_plans={'budget':plan})
        monday=datetime(2026,11,2,22,tzinfo=timezone.utc)
        self.assertEqual(budget_access.clock_deadlines(settings,'budget',monday)[120],monday.replace(day=3,hour=2).timestamp())
        self.assertTrue(budget_access.active(settings,'budget',monday.replace(day=3,hour=1)))
        self.assertEqual(budget_access.clock_remaining(settings,'budget',monday.replace(day=3,hour=2)),0)
        self.assertFalse(budget_access.active(settings,'budget',monday.replace(day=3,hour=6)))

    def test_clock_only_shared_and_game_counters_use_wall_time_not_minutes_used(self):
        plan=new_plan(); plan['steps']=[clock_step()]
        settings=replace(Settings(),limit_seconds=0,game_limits={'fixture':0},
            budget_usage_limits={'shared-games':False,'game:fixture':False},
            restriction_plans={'shared-games':plan,'game:fixture':plan})
        now=datetime(2026,11,2,21,30,tzinfo=timezone.utc)
        self.assertEqual(remaining_budget(settings,now,999999).remaining,1800)
        self.assertEqual(gameplay_budget(settings,now,{'fixture':999999},'fixture').remaining,1800)
        self.assertEqual(remaining_budget(settings,now+timedelta(minutes=10),999999).remaining,1200)
        off=replace(settings,budget_active_days={'shared-games':[],'game:fixture':[]})
        self.assertTrue(math.isinf(gameplay_budget(off,now,{'fixture':999999},'fixture').remaining))


class ClockInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(ui_fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=ui_fixture.QtInterfaceTests.setUp; tearDown=ui_fixture.QtInterfaceTests.tearDown; pump=ui_fixture.QtInterfaceTests.pump

    def setup_clock(self,member=None):
        self.app.open_budget(member=member or target('site','example.com')); editor=self.app.budget_editor
        (editor.shared_usage_limit if editor.current=='shared-games' else editor.usage_limit).setChecked(False)
        editor.access.select([0,2]); editor.steps.add_step.click(); card=editor.steps.cards[0]
        card.kind.setCurrentIndex(card.kind.findData('restrict'))
        card.time_mode.setCurrentIndex(card.time_mode.findData('clock')); card.clock_time.setTime(QTime(22,0))
        return editor,card

    def test_clock_only_website_budget_saves_reopens_cancels_and_obeys_active_days(self):
        self.app.switch_page(2); self.app.show_settings_section('general')
        self.app.global_day_start.setTime(QTime(6,0)); self.app.save_settings()
        editor,card=self.setup_clock(); key=editor.current; editor.minutes.setValue(0)
        self.assertTrue(editor.reset_time.isHidden())
        self.app.save_budgets(); self.assertFalse(self.app.budget_error.text())
        saved=self.store.settings(); self.assertEqual(saved.budget_active_days[key],[0,2]); self.assertFalse(saved.budget_usage_limits[key])
        self.assertEqual(saved.restriction_plans[key]['steps'][0]['clock_minute'],1320)
        editor.show_editor(key); self.assertFalse(editor.minutes.isEnabled()); self.assertTrue(editor.zero_limit_note.isHidden())
        self.assertEqual(editor.steps.cards[0].clock_time.time(),QTime(22,0))
        editor.access.select([5,6]); editor.usage_limit.setChecked(True); self.app.budget_back.click()
        self.assertEqual(editor.access.active_days[key],[5,6])
        editor.show_editor(key); editor.cancel_edit(); self.app.save_budgets()
        self.assertEqual(self.store.settings().budget_active_days,saved.budget_active_days)
        self.assertEqual(self.store.settings().budget_usage_limits,saved.budget_usage_limits)
        runtime=self.app.restrictions
        for when,blocked in ((datetime(2026,11,2,21,59),False),(datetime(2026,11,2,22),True),
                             (datetime(2026,11,3,1),True),(datetime(2026,11,3,6),False),(datetime(2026,11,4,6),False)):
            runtime.prepare(when.astimezone())
            self.assertEqual(bool(runtime.state.action(key,'site:example.com')),blocked)

    def test_shared_game_day_filter_and_no_usage_cap_survive_save(self):
        editor,card=self.setup_clock(target('category','games')); card.consent.setChecked(True)
        self.app.save_budgets(); self.assertFalse(self.app.budget_error.text())
        self.assertFalse(self.app.settings.budget_usage_limits['shared-games'])
        self.assertEqual(self.app.settings.budget_active_days['shared-games'],[0,2])
        editor.show_editor('shared-games'); self.assertFalse(editor.schedule.limit.isEnabled())
        now=datetime(2026,11,3,22).astimezone(); self.app.restrictions.prepare(now)
        self.assertNotIn('shared-games',self.app.restrictions.state.budgets)
        self.app.tracker.evaluate(now); self.assertFalse(self.app.tracker.alerts)

    def test_computer_period_has_active_days_without_changing_its_saved_hours(self):
        from gametime.bedtime import phase
        self.app.open_budget(); editor=self.app.budget_editor; editor.create_computer(); editor.access.select([0])
        editor.schedule.change('bedtime_warning_minute',21*60+55); editor.schedule.change('bedtime_minute',22*60)
        self.app.save_budgets(); self.assertFalse(self.app.budget_error.text())
        settings=self.app.settings
        self.assertEqual(settings.budget_active_days['computer-window'],[0])
        self.assertEqual(phase(settings,datetime(2026,11,2,23).astimezone())[0],'bedtime')
        self.assertEqual(phase(settings,datetime(2026,11,3,23).astimezone())[0],'off')

    def test_individual_game_zero_is_inert_when_minute_limit_is_off_and_clock_still_closes(self):
        editor,card=self.setup_clock(target('game',self.games[0].id)); key=editor.current
        editor.minutes.setValue(0); card.consent.setChecked(True); self.app.save_budgets()
        self.assertFalse(self.app.budget_error.text()); self.assertEqual(self.app.settings.game_limits[self.games[0].id],0)
        runtime=self.app.restrictions
        before=datetime(2026,11,2,21,55).astimezone(); runtime.prepare(before)
        self.assertFalse(runtime.state.zero_budget(key)); self.assertEqual(runtime.state.action(key,'app:fixture'),'')
        counter=gameplay_budget(self.app.settings,before,{},self.games[0].id)
        self.assertEqual(counter.remaining,300); self.assertTrue(counter.warning)
        runtime.prepare(before.replace(hour=22,minute=0))
        self.assertEqual(runtime.state.action(key,'app:fixture'),'cover')
        self.assertIsNotNone(runtime.state.extend([key],'app:fixture','fixture:process'))
        runtime.state.now+=301
        self.assertEqual(runtime.state.action(key,'app:fixture','fixture:process'),'close')
        editor.show_editor(key); editor.access.select([]); self.app.save_budgets()
        runtime.prepare(before.replace(day=4,hour=23)); self.assertNotIn(key,runtime.state.budgets)


if __name__=='__main__': unittest.main()
