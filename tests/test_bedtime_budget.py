"""Opt-in bedtime caps share one calculation without altering measured history."""
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from gametime.budget import remaining_budget
from gametime.model import Settings, Catalog, Game
from gametime.schedule import week_plans
from gametime.store import Store
from gametime.tracker import Tracker, Sample

if os.name == 'nt': import test_qt_ui as fixtures

CAP = dict(bedtime_enabled=True, bedtime_caps_budget=True)


class BedtimeBudgetTests(unittest.TestCase):
    def budget(self, text, used=0, **fields):
        return remaining_budget(replace(Settings(), **(CAP | fields)), datetime.fromisoformat(text), used)

    def test_2300_start_with_two_hour_quota_shows_one_hour_until_midnight(self):
        budget = self.budget('2026-10-23T23:00:00+02:00')
        self.assertEqual((budget.remaining, budget.quota_remaining), (3600, 7200))
        self.assertEqual(budget.bedtime.isoformat(), '2026-10-24T00:00:00+02:00')
        self.assertFalse(budget.warning)

    def test_quota_wins_when_it_runs_out_earlier(self):
        budget = self.budget('2026-10-23T23:00:00', 6500)
        self.assertEqual(budget.remaining, 700); self.assertIsNone(budget.bedtime); self.assertTrue(budget.warning)

    def test_clock_keeps_counting_down_while_play_time_is_paused(self):
        self.assertEqual(self.budget('2026-10-23T23:00', 600).remaining, 3600)
        self.assertEqual(self.budget('2026-10-23T23:30', 600).remaining, 1800)

    def test_cap_is_off_by_default_and_disabled_bedtime_does_not_cap(self):
        self.assertFalse(Settings().bedtime_caps_budget)
        for fields in ({'bedtime_caps_budget': False}, {'bedtime_enabled': False}):
            budget = self.budget('2026-10-23T23:30', **fields)
            self.assertEqual(budget.remaining, 7200); self.assertIsNone(budget.bedtime)

    def test_warning_uses_the_bedtime_warning_and_configured_quota_warning(self):
        for text, expected in (('23:54:59', False), ('23:55:00', True), ('00:00:00', True)):
            self.assertEqual(self.budget('2026-10-23T'+text).warning, expected)
        self.assertTrue(self.budget('2026-10-23T23:10', 6100).warning)

    def test_midnight_and_resume_boundaries_do_not_offer_a_fresh_quota_during_bedtime(self):
        for text, seconds in (('2026-10-23T23:59:59', 1), ('2026-10-24T00:00:00', 0),
                              ('2026-10-24T05:59:59', 0), ('2026-10-24T06:00:00', 7200)):
            self.assertEqual(self.budget(text).remaining, seconds, text)

    def test_after_midnight_bedtime_is_found_before_its_reminder(self):
        fields = dict(bedtime_warning_minute=55, bedtime_minute=60, bedtime_resume_minute=8*60)
        self.assertEqual(self.budget('2026-10-23T23:30', **fields).remaining, 5400)
        self.assertEqual(self.budget('2026-10-24T00:30', **fields).remaining, 1800)
        self.assertEqual(self.budget('2026-10-24T01:00', **fields).remaining, 0)

    def test_same_day_sleep_window_ends_at_its_resume_time(self):
        fields = dict(bedtime_warning_minute=20*60, bedtime_minute=21*60, bedtime_resume_minute=23*60)
        self.assertEqual(self.budget('2026-10-23T20:30', **fields).remaining, 1800)
        self.assertEqual(self.budget('2026-10-23T22:00', **fields).remaining, 0)
        self.assertEqual(self.budget('2026-10-23T23:00', **fields).remaining, 7200)

    def test_fractional_seconds_are_preserved_and_over_quota_never_goes_negative(self):
        self.assertAlmostEqual(self.budget('2026-10-23T23:59:59.750000').remaining, .25)
        self.assertEqual(self.budget('2026-10-23T23:00', 8000).remaining, 0)

    def test_native_local_offset_follows_the_deadlines_timezone_across_dst(self):
        wall = datetime(2026,10,24,23,30).astimezone()
        settings = replace(Settings(), **CAP, limit_seconds=12*3600, bedtime_minute=210, bedtime_resume_minute=480)
        expected = datetime(2026,10,25,3,30).timestamp() - wall.timestamp()
        self.assertEqual(remaining_budget(settings, wall, 0).remaining, expected)

    def test_per_day_and_legacy_weekend_options_follow_the_owning_night(self):
        settings = replace(Settings(), daily_schedules={'6': CAP | {'bedtime_warning_minute': 23*60, 'bedtime_minute': 30, 'bedtime_resume_minute': 8*60}})
        for text, seconds in (('2026-10-25T23:30', 3600), ('2026-10-26T00:10', 1200), ('2026-10-26T01:00', 0), ('2026-10-26T08:00', 7200)):
            self.assertEqual(remaining_budget(settings, datetime.fromisoformat(text), 0).remaining, seconds, text)
        weekend = replace(Settings(), weekend_enabled=True, weekend_schedule=CAP)
        self.assertEqual(remaining_budget(weekend, datetime(2026,10,24,23), 0).remaining, 3600)
        self.assertEqual(remaining_budget(weekend, datetime(2026,10,23,23), 0).remaining, 7200)

    def test_an_uncapped_current_sleep_window_does_not_inherit_a_later_days_cap(self):
        settings = replace(Settings(), bedtime_enabled=True, daily_schedules={'5': CAP | {'bedtime_warning_minute': 60, 'bedtime_minute': 65, 'bedtime_resume_minute': 720}})
        budget = remaining_budget(settings, datetime(2026,10,24,1), 0)
        self.assertEqual(budget.remaining, 7200); self.assertIsNone(budget.bedtime)

    def test_new_toggle_is_strictly_boolean_in_global_and_daily_settings(self):
        for value in ('yes', 1, None, []):
            with self.subTest(value=value), self.assertRaises(ValueError): replace(Settings(), bedtime_caps_budget=value).validate()
            with self.subTest(day_value=value), self.assertRaises(ValueError): replace(Settings(), daily_schedules={'0': {'bedtime_caps_budget': value}}).validate()

    def test_old_profiles_remain_opted_out_and_history_exclusions_and_sync_stay_intact(self):
        with tempfile.TemporaryDirectory() as tmp, closing(Store(Path(tmp)/'usage.sqlite3')) as store:
            with store.db: store.db.execute("INSERT INTO settings VALUES ('config',?)", (json.dumps({'games_root': str(Path(tmp)/'Games')}),))
            self.assertFalse(store.settings().bedtime_caps_budget)
            store.add_usage({('2026-10-23', 'fixture'): 600}); store.set_enabled('fixture', False)
            settings = replace(store.settings(), **CAP); store.save_settings(settings)
            self.assertTrue(store.settings().bedtime_caps_budget)
            self.assertEqual(store.totals('2026-10-23'), {'fixture': 600}); self.assertFalse(store.overrides()['fixture'])
            from gametime.statistics_sync import StatisticsData
            self.assertNotIn('bedtime_caps_budget', json.dumps(StatisticsData(store).snapshot('b'*32, 'Fixture')))

    def test_warning_remaining_token_uses_cap_without_changing_alert_thresholds_or_history(self):
        with tempfile.TemporaryDirectory() as tmp, closing(Store(Path(tmp)/'usage.sqlite3')) as store:
            settings = replace(Settings(), **CAP, notification_messages={'warning': '{remaining}/{minutes}'})
            tracker = Tracker(store, Catalog(settings)); tracker.cache['2026-10-23'] = {'fixture': 6000}
            tracker.evaluate(datetime(2026,10,23,23,50)); alert = tracker.alerts[0]
            self.assertEqual((alert.text, alert.keys), ('10/120', ('warning:6000',)))
            tracker.delivered(alert); self.assertEqual(store.totals('2026-10-23'), {})

    def test_capped_midnight_still_splits_measured_usage_by_calendar_day(self):
        with tempfile.TemporaryDirectory() as tmp, closing(Store(Path(tmp)/'usage.sqlite3')) as store:
            settings = replace(Settings(), **CAP); tracker = Tracker(store, Catalog(settings))
            game = Game('fixture','Fixture','Games',str(Path(tmp)/'Games'))
            tracker._credit(game, datetime(2026,10,23,23,59,59), datetime(2026,10,24,0,0,1), 2)
            self.assertEqual(dict(tracker.pending), {('2026-10-23','fixture'):1, ('2026-10-24','fixture'):1})
            tracker.evaluate(datetime(2026,10,24,0,0,1)); self.assertFalse(tracker.alerts)


@unittest.skipUnless(os.name == 'nt', 'Windows Qt required')
class BedtimeBudgetInterfaceTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.QtInterfaceTests.setUpClass.__func__) if os.name == 'nt' else classmethod(lambda cls:None)
    if os.name == 'nt':
        setUp = fixtures.QtInterfaceTests.setUp; tearDown = fixtures.QtInterfaceTests.tearDown; pump = fixtures.QtInterfaceTests.pump

    def configure(self, used=0):
        self.wall = datetime(2026,10,23,23,tzinfo=timezone(timedelta(hours=2)))
        self.app.settings = self.app.catalog.settings = replace(self.app.settings, **CAP, overlay_enabled=True, overlay_rtss_auto=False)
        self.app.tracker.cache[self.wall.date().isoformat()] = {self.games[0].id: used}
        self.app.tracker.active = self.games[0]; self.app.tracker.identity = 'fixture:1'

    def clock(self):
        wall = self.wall
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None): return wall
        return patch('gametime.qt_ui.datetime', Clock)

    def show_overlay(self):
        current = Sample(self.wall, 100, str(self.exe), 'fixture:1')
        with patch('gametime.qt_ui.win32.sample', return_value=current), patch('gametime.qt_ui.foreground_screen_name', return_value=''):
            self.app.update_overlay()

    def test_hub_and_tray_agree_and_explain_why_only_one_hour_remains(self):
        self.configure()
        with self.clock(), patch.object(self.app.tray, 'update') as tray:
            self.app.render()
        self.assertEqual(self.app.remaining_label.text(), '01:00:00')
        self.assertIn('02:00:00', self.app.remaining_label.toolTip()); self.assertIn('00:00', self.app.remaining_reason.text())
        self.assertFalse(self.app.remaining_reason.isHidden()); self.assertIn('01:00:00', tray.call_args[0][0])
        self.app.set_language('en'); self.assertEqual(self.app.remaining_reason.text(), 'Until bedtime at 00:00')

    def test_disabling_cap_restores_quota_and_removes_bedtime_caption(self):
        self.configure(); self.app.settings = self.app.catalog.settings = replace(self.app.settings, bedtime_caps_budget=False)
        with self.clock(): self.app.render()
        self.assertEqual(self.app.remaining_label.text(), '02:00:00'); self.assertTrue(self.app.remaining_reason.isHidden())

    def test_hub_explains_zero_time_after_bedtime(self):
        self.configure(); self.wall += timedelta(hours=2)
        with self.clock(): self.app.render()
        self.assertEqual(self.app.remaining_label.text(), '00:00:00')
        self.assertEqual(self.app.remaining_reason.text(), self.app.t('Bedtime has started'))

    def test_desktop_countdown_uses_cap_and_bedtime_warning_color(self):
        self.configure(); self.show_overlay()
        self.assertEqual(self.app.overlay.seconds, 3600); self.assertFalse(self.app.overlay.warning)
        self.wall = self.wall.replace(minute=55); self.show_overlay()
        self.assertEqual(self.app.overlay.seconds, 300); self.assertTrue(self.app.overlay.warning)
        self.wall += timedelta(minutes=5); self.show_overlay()
        self.assertEqual(self.app.overlay.seconds, 0); self.assertTrue(self.app.overlay.warning)

    def test_rtss_gets_the_same_capped_time_and_warning_palette(self):
        self.configure(); self.wall = self.wall.replace(minute=55)
        self.app.settings = self.app.catalog.settings = replace(self.app.settings, overlay_rtss_auto=True)
        with patch.object(self.app, 'rtss_available', return_value=True), patch.object(self.app.rtss, 'present', return_value=True) as present:
            self.show_overlay()
        text = present.call_args[0][2]
        self.assertIn('00:05:00', text); self.assertIn('FF5C65>', text)
        self.assertFalse(self.app.overlay.isVisible())

    def test_weekly_option_supports_groups_mixed_values_save_and_language_drafts(self):
        from PySide6.QtCore import Qt
        editor = self.app.schedule_editor
        self.assertFalse(self.app.bedtime_caps_budget.isChecked()); self.assertFalse(self.app.bedtime_caps_budget.isEnabled())
        editor.select_days((0,1)); self.app.bedtime_enabled.setChecked(True); self.app.bedtime_caps_budget.setChecked(True)
        editor.select_days((1,2)); self.assertEqual(self.app.bedtime_caps_budget.checkState(), Qt.PartiallyChecked)
        self.app.set_language('en'); self.assertEqual(editor._selected, {1,2})
        editor.select_days((0,1)); self.app.save_settings(); plans = week_plans(self.store.settings())
        self.assertTrue(plans[0]['bedtime_caps_budget']); self.assertTrue(plans[1]['bedtime_caps_budget']); self.assertFalse(plans[2]['bedtime_caps_budget'])

    def test_failed_save_retains_opt_in_draft_without_changing_stored_settings(self):
        self.app.bedtime_enabled.setChecked(True); self.app.bedtime_caps_budget.setChecked(True)
        with patch.object(self.store, 'save_settings', side_effect=OSError('fixture')): self.app.save_settings()
        self.assertTrue(self.app.bedtime_caps_budget.isChecked()); self.assertFalse(self.store.settings().bedtime_caps_budget)
        self.app.save_settings(); self.assertTrue(self.store.settings().bedtime_caps_budget)

    def test_custom_bedtime_remaining_uses_cap_and_overnight_reminder_owner(self):
        self.configure(); self.wall = self.wall.replace(hour=23, minute=55)
        self.app.settings = self.app.catalog.settings = replace(self.app.settings, notification_messages={'bedtime': '{remaining} / {bedtime}'})
        self.assertEqual(self.app.bedtime_message('2026-10-23', self.wall), '5 / 00:00')
        self.app.settings = self.app.catalog.settings = replace(self.app.settings, daily_schedules={'4': {'bedtime_minute':30}})
        self.wall = datetime(2026,10,24,0,5,tzinfo=self.wall.tzinfo)
        self.assertEqual(self.app.bedtime_message('2026-10-23', self.wall), '25 / 00:30')

    def test_opted_in_hidden_hub_updates_time_without_catalog_or_widget_rebuilds(self):
        self.configure()
        with self.clock(), patch.object(self.store, 'games') as games, patch.object(self.store, 'hidden_ids') as hidden, patch.object(self.app, 'render') as render:
            self.app.render_tick()
        games.assert_not_called(); hidden.assert_not_called(); render.assert_not_called()
        self.assertIn('01:00:00', self.app.tray.data.szTip)


if __name__ == '__main__': unittest.main()
