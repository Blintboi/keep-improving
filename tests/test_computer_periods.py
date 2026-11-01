"""Split older weekdays losslessly and run independent scheduled periods."""
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
import tempfile
import unittest
from gametime.model import Settings
from gametime.computer_periods import FIELDS,split_weekly,schedules,project
from gametime.schedule import day_settings,bedtime_occurrence
from gametime.budget import remaining_budget
from gametime.budget_access import active
from gametime.bedtime import Bedtime
from gametime.store import Store
from gametime.tracker import Sample


class ComputerPeriodTests(unittest.TestCase):
    def old_settings(self):
        return replace(Settings(),bedtime_enabled=True,bedtime_minimize=True,bedtime_caps_budget=True,
            weekend_enabled=True,weekend_schedule={'limit_seconds':10800,'warning_seconds':9600,
                'bedtime_warning_minute':30,'bedtime_minute':60,'bedtime_resume_minute':8*60},
            budget_active_days={'shared-games':[0,1,2,3,4,5,6],'computer-window':[0,1,2,3,4,5,6]}).validate()

    def test_migration_preserves_each_days_game_limit_and_computer_phases(self):
        original=self.old_settings(); saved=deepcopy(original); split=split_weekly(original).validate()
        self.assertEqual(original,saved); self.assertFalse(split.daily_schedules); self.assertFalse(split.weekend_enabled)
        self.assertEqual(split.budget_active_days['shared-games'],[0,1,2,3,4])
        self.assertEqual(len(split.wellbeing_rules),1); self.assertEqual(split.budget_active_days[split.wellbeing_rules[0]['id']],[5,6])
        self.assertEqual(len(split.computer_periods),1); self.assertEqual(split_weekly(split),split)
        hungarian=split_weekly(replace(original,language='hu'))
        self.assertEqual(hungarian.computer_periods[0]['name'],'Géphasználat')
        self.assertEqual(hungarian.wellbeing_rules[0]['name'],'Játékok · közös keret')
        monday=datetime(2026,11,2)
        for index in range(8*48):
            wall=monday+timedelta(minutes=30*index)
            before=bedtime_occurrence(original,wall)[0]
            phases=[bedtime_occurrence(settings,wall)[0] for _,_,settings in schedules(split)]
            self.assertEqual(before=='bedtime','bedtime' in phases,wall)
        for day in range(7):
            wall=monday.replace(hour=12)+timedelta(days=day)
            limits=([split.limit_seconds] if active(split,'shared-games',wall) else [])
            limits.extend(r['seconds'] for r in split.wellbeing_rules if active(split,r['id'],wall))
            self.assertEqual(limits,[day_settings(original,wall).limit_seconds])

    def test_overlapping_periods_have_separate_warning_ledgers_and_caps(self):
        base=replace(Settings(),bedtime_enabled=False,game_budget_enabled=False)
        def period(key,start):
            values={k:getattr(base,k) for k in FIELDS}
            values.update(bedtime_enabled=True,bedtime_minimize=True,bedtime_caps_budget=True,
                          bedtime_warning_minute=start-5,bedtime_minute=start,bedtime_resume_minute=360)
            return dict(id=key,name=key,values=values)
        items=[period('computer-one',22*60),period('computer-two',23*60)]
        settings=replace(base,computer_periods=items,budget_active_days={'computer-one':[0],'computer-two':[1]}).validate()
        self.assertEqual(remaining_budget(settings,datetime(2026,11,2,21),0).remaining,3600)
        self.assertEqual(remaining_budget(settings,datetime(2026,11,3,22),0).remaining,3600)
        with tempfile.TemporaryDirectory() as directory,closing(Store(Path(directory)/'usage.sqlite3')) as store:
            wall=datetime(2026,11,2,21,55)
            settings=replace(settings,budget_active_days={})
            first=Bedtime(store,'computer-one'); marker=first.update(project(settings,items[0]),Sample(wall,100))[1]
            self.assertIsNotNone(marker); first.delivered(marker)
            second=Bedtime(store,'computer-two'); other=dict(items[1],values=dict(items[0]['values']))
            self.assertIsNotNone(second.update(project(settings,other),Sample(wall,100))[1])
            self.assertIsNone(Bedtime(store,'computer-one').update(project(settings,items[0]),Sample(wall,100))[1])

    def test_invalid_periods_are_rejected(self):
        item=split_weekly(self.old_settings()).computer_periods[0]
        for values in (None,{},[item,item],[dict(item,id='computer-window')],[dict(item,values={})],
                       [dict(item,values=dict(item['values'],bedtime_minute=1440))]):
            with self.subTest(values=values),self.assertRaises(ValueError): replace(Settings(),computer_periods=values).validate()

    def test_split_game_budget_carries_independent_usage_and_does_not_double_credit(self):
        from gametime.model import Catalog,Game
        from gametime.tracker import Tracker
        original=replace(self.old_settings(),budget_reset_overrides={'shared-games':360})
        now=datetime(2026,11,7,12); game=Game('fixture','Fixture','Games',r'C:\Fixture')
        with tempfile.TemporaryDirectory() as directory,closing(Store(Path(directory)/'usage.sqlite3')) as store:
            store.save_settings(original); store.upsert([game]); store.add_usage({(now.date().isoformat(),game.id):100})
            tracker=Tracker(store,Catalog(original)); tracker.quota_totals(now)
            tracker.periods.credit('quota:shared-games',360,game.id,now-timedelta(seconds=100),now,100,lambda:{})
            split=split_weekly(original); tracker.catalog.settings=split; store.save_settings(split)
            tracker._credit(game,now,now+timedelta(seconds=1),1)
            key=split.wellbeing_rules[0]['id']
            self.assertEqual(tracker.quota_totals(now+timedelta(seconds=1),key),{game.id:201})
            self.assertEqual(tracker.quota_totals(now+timedelta(seconds=1)),{game.id:201})
            tracker.close()

    def test_twenty_legacy_actions_keep_their_warning_and_granted_save_time(self):
        import json
        from gametime.restriction_policy import new_plan,step,RestrictionState,Budget
        from gametime.computer_periods import carry_runtime
        plan=new_plan(legacy=True); plan.update(extension_minutes=3,close_confirmed=True)
        plan['steps']=[step('notify',index+1,usage=True,popup=True) for index in range(19)]+[step('restrict',120,usage=True)]
        original=replace(self.old_settings(),restriction_plans={'shared-games':plan})
        split=split_weekly(original).validate(); key=split.wellbeing_rules[0]['id']
        self.assertEqual(len(split.restriction_plans[key]['steps']),21)
        now=datetime(2026,11,7,12); day=now.date().isoformat()
        with tempfile.TemporaryDirectory() as directory,closing(Store(Path(directory)/'usage.sqlite3')) as store:
            state=RestrictionState(store); budget=Budget('shared-games','Games',10800,200,(),day=day)
            state.update(day,now.timestamp(),[budget],original.restriction_plans)
            until=state.extend(['shared-games'],'app:fixture','fixture:process'); self.assertIsNotNone(until)
            store.mark_alert(day,['warning:9600'])
            carry_runtime(store,original,split,now)
            state=RestrictionState(store); state.update(day,now.timestamp()+1,[replace(budget,key=key)],split.restriction_plans)
            self.assertEqual(state.rows[key]['grant']['until'],until); self.assertTrue(state.rows[key]['used_extension'])
            self.assertIn('legacy-warning',state.rows[key]['delivered'])


if __name__=='__main__': unittest.main()
