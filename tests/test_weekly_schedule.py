"""Day grouping must never silently replace other days or mixed fields."""
from dataclasses import replace
from datetime import datetime,date,timedelta
from contextlib import closing
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from gametime.model import Settings,Catalog
from gametime.schedule import day_settings,week_plans,bedtime_occurrence,DayScheduleError
from gametime.store import Store
from gametime.tracker import Tracker
from gametime.notification_text import notification_text
import test_qt_ui as fixture


class WeeklyScheduleTests(unittest.TestCase):
    def test_daily_validation_and_each_day_resolution(self):
        for plans in (None,[],{'7':{}},{'0':None},{0:{}},{'1':{'language':'hu'}},{'2':{'limit_seconds':100}}, {'3':{'bedtime_minute':1435}}):
            with self.subTest(plans=plans),self.assertRaises(ValueError): replace(Settings(),daily_schedules=plans).validate()
        plans={str(day):dict(limit_seconds=(130+day)*60,warning_seconds=6000) for day in range(7)}
        settings=replace(Settings(),daily_schedules=plans).validate()
        for day in range(7):
            text=(date(2026,10,19)+timedelta(days=day)).isoformat()
            plan=day_settings(settings,text); self.assertEqual(plan.limit_seconds,(130+day)*60); self.assertEqual(plan.daily_schedules,{})
            self.assertEqual(notification_text(settings,'limit',day=text),notification_text(plan,'limit',day=text))
        self.assertEqual(settings.limit_seconds,7200); self.assertEqual(settings.daily_schedules,plans)

    def test_legacy_weekend_is_preserved_when_opening_and_explicit_days_take_precedence(self):
        settings=replace(Settings(),weekend_enabled=True,weekend_schedule={'limit_seconds':10800,'warning_seconds':9000})
        plans=week_plans(settings); self.assertEqual([plan['limit_seconds'] for plan in plans.values()],[7200]*5+[10800]*2)
        explicit=replace(settings,daily_schedules={'5':{'limit_seconds':14400,'warning_seconds':12000}})
        self.assertEqual(week_plans(explicit)[5]['limit_seconds'],14400); self.assertEqual(week_plans(explicit)[6]['limit_seconds'],10800)
        self.assertEqual(settings.daily_schedules,{})

    def test_daily_overnight_rules_keep_the_start_day_until_its_resume_time(self):
        settings=replace(Settings(),bedtime_enabled=False,daily_schedules={'6':dict(bedtime_enabled=True,bedtime_warning_minute=23*60,bedtime_minute=30,bedtime_resume_minute=8*60,bedtime_minimize=True),
                     '0':dict(bedtime_enabled=True,bedtime_warning_minute=60,bedtime_minute=65,bedtime_resume_minute=10*60)})
        for text,expected in (('2026-10-25T23:00',('warning','2026-10-25')),('2026-10-26T00:30',('bedtime','2026-10-25')),
                              ('2026-10-26T01:00',('bedtime','2026-10-25')),('2026-10-26T08:00',('bedtime','2026-10-26')),
                              ('2026-10-26T10:00',('off','2026-10-26'))):
            self.assertEqual(bedtime_occurrence(settings,datetime.fromisoformat(text))[:2],expected)

    def test_midweek_tracker_uses_selected_day_thresholds_and_persists_preferences(self):
        with tempfile.TemporaryDirectory() as tmp,closing(Store(Path(tmp)/'usage.sqlite3')) as store:
            settings=replace(Settings(games_root=str(Path(tmp)/'Games')),daily_schedules={'2':{'limit_seconds':5400,'warning_seconds':4200}},notification_messages={'warning':'{remaining}/{minutes}'})
            store.save_settings(settings); store.add_usage({('2026-10-21','fixture'):4200}); store.set_enabled('fixture',False)
            tracker=Tracker(store,Catalog(store.settings())); tracker.evaluate(datetime(2026,10,21,12)); alert=tracker.alerts[0]
            self.assertEqual((alert.text,alert.keys),('20/90',('warning:4200',)))
            self.assertEqual(store.settings().daily_schedules,settings.daily_schedules); self.assertEqual(store.totals('2026-10-21'),{'fixture':4200})
            self.assertFalse(store.overrides()['fixture'])
            from gametime.statistics_sync import StatisticsData
            self.assertNotIn('daily_schedules',str(StatisticsData(store).snapshot('b'*32,'Fixture')))


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class WeeklyScheduleInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def test_seven_pills_can_select_individual_and_group_days_and_keep_drafts(self):
        from PySide6.QtWidgets import QPushButton
        editor=self.app.schedule_editor
        self.assertEqual(len(editor.day_buttons),7); self.assertEqual(editor._selected,set(range(7)))
        next(item for item in editor.findChildren(QPushButton) if item.text()==self.app.t('Weekdays')).click()
        self.assertEqual(editor._selected,set(range(5))); self.app.limit.setValue(150)
        next(item for item in editor.findChildren(QPushButton) if item.text()==self.app.t('Weekend')).click()
        self.app.limit.setValue(180); self.app.warning.setValue(150)
        editor.day_buttons[5].click(); self.assertEqual(editor._selected,{6})
        self.app.limit.setValue(210); editor.select_days((5,)); self.assertEqual(self.app.limit.value(),180)
        self.assertEqual(self.store.settings().daily_schedules,{})
        self.app.save_settings(); plans=week_plans(self.store.settings())
        self.assertEqual([plan['limit_seconds']/60 for plan in plans.values()],[150]*5+[180,210])

    def test_mixed_days_only_apply_changed_fields_and_unify_requires_a_click(self):
        editor=self.app.schedule_editor; editor.select_days((0,)); self.app.limit.setValue(150)
        editor.select_days((1,)); self.app.limit.setValue(180); self.app.warning.setValue(160)
        editor.select_days((0,1)); self.assertFalse(editor._mixed['limit_seconds'].isHidden()); self.assertFalse(editor.unify.isHidden())
        self.app.bedtime_enabled.setChecked(True)
        self.app.save_settings(); plans=week_plans(self.store.settings())
        self.assertEqual((plans[0]['limit_seconds'],plans[1]['limit_seconds']),(9000,10800))
        self.assertEqual((plans[0]['warning_seconds'],plans[1]['warning_seconds']),(6000,9600))
        self.assertTrue(plans[0]['bedtime_enabled']); self.assertTrue(plans[1]['bedtime_enabled'])
        editor.unify.click(); self.app.save_settings(); plans=week_plans(self.store.settings())
        self.assertEqual(plans[0],plans[1]); self.assertEqual(plans[2]['limit_seconds'],7200)

    def test_saved_daily_edit_converts_legacy_weekend_without_changing_its_values(self):
        legacy=replace(self.app.settings,weekend_enabled=True,weekend_schedule={'limit_seconds':10800,'warning_seconds':9000,'bedtime_minute':30})
        self.app.settings=self.app.catalog.settings=legacy; self.store.save_settings(legacy)
        editor=self.app.schedule_editor; editor.saved(legacy); editor.select_days((3,)); self.app.limit.setValue(150)
        self.app.save_settings(); saved=self.store.settings(); plans=week_plans(saved)
        self.assertFalse(saved.weekend_enabled); self.assertEqual(saved.weekend_schedule,{})
        self.assertEqual(plans[5],week_plans(legacy)[5]); self.assertEqual(plans[6],week_plans(legacy)[6]); self.assertEqual(plans[3]['limit_seconds'],9000)

    def test_no_selection_disables_controls_and_translation_keeps_selection_and_drafts(self):
        editor=self.app.schedule_editor; editor.select_days((1,3)); self.app.limit.setValue(155)
        self.app.set_language('en'); self.assertEqual(editor._selected,{1,3}); self.assertEqual(self.app.limit.value(),155)
        self.assertIn('Tuesday, Thursday',editor.selection_label.text()); self.assertEqual(editor.day_buttons[3].text(),'Thu')
        editor.select_days(()); self.assertFalse(editor.controls.isEnabled()); self.assertIn('Select at least',editor.selection_label.text())
        editor.select_days((1,)); self.assertEqual(self.app.limit.value(),155)

    def test_failed_save_has_localized_day_error_and_retains_all_drafts(self):
        editor=self.app.schedule_editor; editor.select_days((2,)); self.app.limit.setValue(60)
        self.app.save_settings(); self.assertIn('Szerda:',self.app.settings_error.text()); self.assertEqual(self.store.settings().daily_schedules,{})
        self.app.warning.setValue(50)
        with patch.object(self.store,'save_settings',side_effect=OSError('fixture')): self.app.save_settings()
        self.assertEqual(self.store.settings().daily_schedules,{}); self.assertEqual(self.app.limit.value(),60)
        self.app.save_settings(); self.assertEqual(week_plans(self.store.settings())[2]['limit_seconds'],3600)

    def test_mixed_checkbox_click_sets_all_selected_days_and_does_not_touch_other_fields(self):
        from PySide6.QtCore import Qt
        editor=self.app.schedule_editor; editor.select_days((0,)); self.app.restriction_enabled.setChecked(True)
        editor.select_days((0,1)); self.assertEqual(self.app.restriction_enabled.checkState(),Qt.PartiallyChecked)
        self.app.restriction_enabled.click(); self.assertEqual(self.app.restriction_enabled.checkState(),Qt.Checked)
        self.app.save_settings(); plans=week_plans(self.store.settings())
        self.assertTrue(plans[0]['restriction_enabled']); self.assertTrue(plans[1]['restriction_enabled']); self.assertFalse(plans[2]['restriction_enabled'])

    def test_typing_the_displayed_value_applies_it_to_other_mixed_days(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        editor=self.app.schedule_editor; editor.select_days((1,)); self.app.limit.setValue(180)
        editor.select_days((0,1)); edit=self.app.limit
        self.app.settings_dialog(); self.pump(.03); edit.setFocus(); edit.selectAll(); QTest.keyClicks(edit,'120'); QTest.keyClick(edit,Qt.Key_Tab)
        self.app.save_settings(); plans=week_plans(self.store.settings())
        self.assertEqual((plans[0]['limit_seconds'],plans[1]['limit_seconds']),(7200,7200))
        from PySide6.QtCore import QTime
        editor.select_days((0,1)); self.app.bedtime_enabled.setChecked(True)
        editor.select_days((0,)); self.app.bedtime_times['bedtime_minute'].setTime(QTime(0,30))
        editor.select_days((1,)); self.app.bedtime_times['bedtime_minute'].setTime(QTime(1,0))
        editor.select_days((0,1)); edit=self.app.bedtime_times['bedtime_minute']; edit.setFocus(); edit.selectAll()
        QTest.keyClicks(edit,'00:30'); QTest.keyClick(edit,Qt.Key_Tab); self.app.save_settings(); plans=week_plans(self.store.settings())
        self.assertEqual((plans[0]['bedtime_minute'],plans[1]['bedtime_minute']),(30,30))
