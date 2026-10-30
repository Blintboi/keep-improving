"""Universal day boundaries preserve history and consumed budgets on edits."""
from dataclasses import replace
from datetime import datetime, date, timedelta
from pathlib import Path
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from gametime.budget import quota_plan, remaining_budget
from gametime.model import Settings, Catalog, Game
from gametime.quota import reset_clock, period_day, period_slices, reset_at
from gametime.store import Store
from gametime.tracker import Tracker
if os.name == 'nt': import test_qt_ui as fixtures


class QuotaResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'usage.sqlite3'); self.addCleanup(self.store.close)
        self.settings=replace(Settings(),budget_reset_minute=360)
        self.catalog=Catalog(self.settings)
        self.tracker=Tracker(self.store,self.catalog)
        self.game=Game('fixture','Fixture','Games',str(Path(self.tmp.name)/'Games'))
        self.now=datetime(2026,10,23,23,59,59)

    def used(self,wall): return sum(self.tracker.quota_totals(wall).values())

    def test_default_midnight_and_strict_global_and_per_day_validation(self):
        self.assertEqual(Settings().budget_reset_minute,0)
        for value in (-1,1440,True,6.5,'06:00',None):
            with self.subTest(value=value),self.assertRaises(ValueError): replace(Settings(),budget_reset_minute=value).validate()
            with self.subTest(day=value),self.assertRaises(ValueError): replace(Settings(),daily_schedules={'1':{'budget_reset_minute':value}}).validate()

    def test_weekday_plan_changes_at_the_universal_boundary(self):
        settings=replace(self.settings,daily_schedules={'5':{'budget_reset_minute':480,'limit_seconds':10800,'warning_seconds':9000}})
        before=datetime(2026,10,24,5,59,59); at=before+timedelta(seconds=1)
        self.assertEqual(period_day(before,reset_clock(settings)),date(2026,10,23))
        self.assertEqual(quota_plan(settings,before).limit_seconds,7200)
        self.assertEqual(quota_plan(settings,at).limit_seconds,10800)
        legacy=replace(Settings(),weekend_enabled=True,weekend_schedule={'budget_reset_minute':480})
        self.assertEqual(reset_clock(legacy),(0,)*7)

    def test_midnight_keeps_both_history_and_quota_on_the_previous_day(self):
        self.tracker._credit(self.game,self.now,self.now+timedelta(seconds=2),2)
        self.assertEqual(self.used(self.now+timedelta(seconds=2)),2)
        self.tracker.flush()
        self.assertEqual(self.store.totals('2026-10-23'),{'fixture':2})
        self.assertEqual(self.store.totals('2026-10-24'),{})
        self.assertEqual(self.store.budget_totals('2026-10-23'),{'fixture':2})

    def test_fractional_interval_splits_at_the_selected_reset(self):
        start=datetime(2026,10,24,5,59,59,500000); end=start+timedelta(seconds=2)
        self.tracker._credit(self.game,start,end,2)
        self.assertEqual(self.used(start),.5); self.assertEqual(self.used(end),1.5)
        self.assertEqual(sum(self.tracker.totals('2026-10-23').values()),.5)
        self.assertEqual(sum(self.tracker.totals('2026-10-24').values()),1.5)
        self.assertEqual(list(period_slices(start,end,2,reset_clock(self.settings))),[('2026-10-23',.5),('2026-10-24',1.5)])

    def test_legacy_weekday_override_does_not_change_universal_reset(self):
        self.catalog.settings=replace(self.settings,daily_schedules={'5':{'budget_reset_minute':480}})
        self.tracker._credit(self.game,self.now,self.now+timedelta(seconds=2),2)
        self.assertEqual(self.used(datetime(2026,10,24,5,59)),2)
        start=datetime(2026,10,24,5,59,59)
        self.tracker._credit(self.game,start,start+timedelta(seconds=2),2)
        self.assertEqual(self.used(start),3)
        self.assertEqual(self.used(start+timedelta(seconds=2)),1)

    def test_old_profile_consumption_survives_enable_change_disable_and_restart(self):
        self.store.add_usage({('2026-10-23','fixture'):6100})
        self.assertEqual(self.used(self.now),6100)
        after=datetime(2026,10,24,0,10)
        self.assertEqual(self.used(after),6100)
        self.catalog.settings=replace(self.settings,budget_reset_minute=480)
        self.assertEqual(self.used(after),6100)
        self.catalog.settings=replace(self.settings,budget_reset_minute=0)
        self.assertEqual(self.used(after),6100)
        self.tracker=Tracker(self.store,self.catalog)
        self.assertEqual(self.used(after),6100)
        self.assertEqual(self.used(datetime(2026,10,25,0)),0)
        self.assertEqual(self.store.totals('2026-10-23'),{'fixture':6100})

    def test_default_profiles_reuse_calendar_cache_without_extra_quota_writes(self):
        tracker=Tracker(self.store,Catalog(Settings()))
        tracker.cache['2026-10-23']={'fixture':6000}
        self.assertEqual(sum(tracker.quota_totals(self.now).values()),6000)
        self.assertIsNone(tracker.budget_clock)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM budget_usage').fetchone()[0],0)

    def test_warning_is_not_repeated_at_midnight_or_after_edit_but_renews_next_period(self):
        self.store.add_usage({('2026-10-23','fixture'):6000})
        self.tracker.evaluate(self.now); alert=self.tracker.alerts.popleft(); self.tracker.delivered(alert)
        self.tracker.evaluate(datetime(2026,10,24,0,10)); self.assertFalse(self.tracker.alerts)
        self.catalog.settings=replace(self.settings,budget_reset_minute=480)
        self.tracker.evaluate(datetime(2026,10,24,0,10)); self.assertFalse(self.tracker.alerts)
        start=datetime(2026,10,24,8)
        self.tracker._credit(self.game,start,start+timedelta(seconds=1),6000)
        self.tracker.evaluate(start+timedelta(seconds=1)); self.assertEqual(len(self.tracker.alerts),1)
        self.assertEqual(self.tracker.alerts[0].day,'2026-10-24')

    def test_restart_does_not_charge_offline_time_or_reset_the_quota(self):
        self.tracker._credit(self.game,self.now,self.now+timedelta(seconds=1),1); self.tracker.flush()
        self.tracker=Tracker(self.store,self.catalog)
        self.assertEqual(self.used(datetime(2026,10,24,5,59)),1)
        self.assertEqual(self.used(datetime(2026,10,24,6)),0)

    def test_history_and_quota_checkpoints_are_atomic(self):
        self.used(self.now)
        self.store.db.executescript("CREATE TRIGGER reject_budget BEFORE INSERT ON budget_usage BEGIN SELECT RAISE(ABORT,'fixture'); END;")
        self.tracker._credit(self.game,self.now,self.now+timedelta(seconds=1),1)
        with self.assertRaises(sqlite3.IntegrityError): self.tracker.flush()
        self.assertEqual(self.store.totals('2026-10-23'),{})
        self.assertEqual(sum(self.tracker.pending.values()),1); self.assertEqual(sum(self.tracker.budget_pending.values()),1)
        self.store.db.execute('DROP TRIGGER reject_budget'); self.tracker.flush()
        self.assertEqual(self.store.budget_totals('2026-10-23'),{'fixture':1})

    def test_catalog_id_merge_and_cloud_history_keep_the_shared_day(self):
        from gametime.statistics_sync import StatisticsData
        self.catalog.games[self.game.id]=self.game
        self.tracker._credit(self.game,self.now,self.now+timedelta(seconds=2),2); self.tracker.flush()
        with self.store.db: self.store._merge('fixture','renamed')
        self.tracker.budget_cache.clear()
        self.assertEqual(self.tracker.quota_totals(self.now+timedelta(seconds=2)),{'renamed':2})
        snapshot=StatisticsData(self.store).snapshot('b'*32,'Fixture')
        self.assertEqual({row[0] for row in snapshot['rows']},{'2026-10-23'})
        self.assertNotIn('budget_',str(snapshot))

    def test_bedtime_cap_still_wins_even_when_the_new_quota_arrives_before_resume(self):
        settings=replace(self.settings,bedtime_enabled=True,bedtime_caps_budget=True,bedtime_resume_minute=480)
        self.assertEqual(remaining_budget(settings,datetime(2026,10,24,6),0).remaining,0)
        self.assertEqual(remaining_budget(settings,datetime(2026,10,24,8),0).remaining,7200)

    def test_native_dst_boundary_is_used_once_and_interval_duration_is_conserved(self):
        wall=datetime(2026,10,25,0).astimezone(); clock=(150,)*7
        boundary=reset_at(wall.date(),150,wall)
        start=datetime.fromtimestamp(boundary.timestamp()-1).astimezone()
        end=datetime.fromtimestamp(boundary.timestamp()+1).astimezone()
        self.assertEqual(list(period_slices(start,end,2,clock)),[('2026-10-24',1),('2026-10-25',1)])
        later=datetime.fromtimestamp(boundary.timestamp()+3600).astimezone()
        self.assertEqual(period_day(later,clock),date(2026,10,25))


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class QuotaResetInterfaceTests(unittest.TestCase):
    if os.name=='nt':
        setUpClass=classmethod(fixtures.QtInterfaceTests.setUpClass.__func__)
        setUp=fixtures.QtInterfaceTests.setUp; tearDown=fixtures.QtInterfaceTests.tearDown; pump=fixtures.QtInterfaceTests.pump

    def test_universal_dialog_saves_only_day_start_and_cancel_discards(self):
        from PySide6.QtCore import QTime
        from PySide6.QtWidgets import QPushButton
        from gametime.qt_widgets import NoWheelTimeEdit
        from gametime.qt_day_start import day_start_dialog
        self.assertNotIn('budget_reset_minute',self.app.schedule_editor._fields)
        window=day_start_dialog(self.app)
        edit=window.findChild(NoWheelTimeEdit,'DayStartTime'); edit.setTime(QTime(1,0))
        window.reject(); self.assertEqual(self.store.settings().budget_reset_minute,0)
        # An unrelated schedule draft must survive saving this global setting.
        self.app.schedule_editor.limit.setValue(180)
        window=day_start_dialog(self.app)
        edit=window.findChild(NoWheelTimeEdit,'DayStartTime'); edit.setTime(QTime(1,0))
        save=next(b for b in window.findChildren(QPushButton) if b.text()=='Mentés'); save.click()
        self.assertEqual(self.store.settings().budget_reset_minute,60)
        self.assertEqual(self.store.settings().limit_seconds,7200)
        self.assertEqual(self.app.focus.day_start_minute,60)
        self.app.save_settings()
        self.assertEqual(self.store.settings().budget_reset_minute,60)
        self.assertEqual(self.store.settings().limit_seconds,10800)

    def test_failed_day_start_save_keeps_draft_and_profile_unchanged(self):
        from PySide6.QtCore import QTime
        from PySide6.QtWidgets import QPushButton
        from gametime.qt_widgets import NoWheelTimeEdit
        from gametime.qt_day_start import day_start_dialog
        window=day_start_dialog(self.app)
        edit=window.findChild(NoWheelTimeEdit,'DayStartTime'); edit.setTime(QTime(1,0))
        save=next(b for b in window.findChildren(QPushButton) if b.text()=='Mentés')
        with patch.object(self.store,'save_settings',side_effect=OSError('fixture')): save.click()
        self.assertTrue(window.isVisible()); self.assertEqual(edit.time(),QTime(1,0))
        self.assertEqual(self.store.settings().budget_reset_minute,0)
        save.click(); self.assertEqual(self.store.settings().budget_reset_minute,60)

    def test_statistics_today_yesterday_and_live_rollover_use_one_am(self):
        from gametime.quota import current_day
        settings=replace(self.app.settings,budget_reset_minute=60)
        self.app.settings=self.app.catalog.settings=settings
        before=current_day(settings,datetime(2026,11,1,0,59,59))
        after=current_day(settings,datetime(2026,11,1,1))
        page=self.app.statistics
        with patch('gametime.qt_statistics.current_day',return_value=before):
            page.period.setCurrentIndex(page.period.findData('today')); page.choose_period()
            self.assertEqual(page._range,('2026-10-31','2026-10-31'))
            self.assertEqual(page.period_dates('yesterday'),('2026-10-30','2026-10-30'))
        with patch('gametime.qt_statistics.current_day',return_value=after):
            page.refresh(live=True)
            self.assertEqual(page._range,('2026-11-01','2026-11-01'))

    def test_hub_tray_and_restriction_keep_previous_budget_after_midnight(self):
        wall=datetime(2026,10,23,23,59)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,budget_reset_minute=360,restriction_enabled=True,restriction_seconds=6500)
        self.app.tracker.cache['2026-10-23']={self.games[0].id:6600}
        self.app.tracker.quota_totals(wall)
        wall=datetime(2026,10,24,0,10)
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None): return wall
        with patch('gametime.qt_ui.datetime',Clock),patch.object(self.app.tray,'update') as tray:
            self.app.render()
        self.assertEqual(self.app.remaining_label.text(),'00:10:00')
        self.assertIn('06:00',self.app.remaining_label.toolTip())
        self.assertIn('00:10:00',tray.call_args[0][0])
        self.assertTrue(self.app.restriction_reached(wall))
        self.assertFalse(self.app.restriction_reached(wall.replace(hour=6)))

    def test_desktop_and_rtss_receive_the_same_overnight_remaining_time(self):
        from gametime.tracker import Sample
        wall=datetime(2026,10,23,23,59)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,budget_reset_minute=360,overlay_enabled=True)
        self.app.tracker.cache['2026-10-23']={self.games[0].id:6000}
        self.app.tracker.quota_totals(wall)
        wall=datetime(2026,10,24,0,10)
        self.app.tracker.active=self.games[0]; self.app.tracker.identity='fixture:1'
        sample=Sample(wall,100,str(self.exe),'fixture:1')
        with patch('gametime.qt_ui.win32.sample',return_value=sample),patch('gametime.qt_ui.foreground_screen_name',return_value=''):
            self.app.update_overlay()
            self.assertEqual(self.app.overlay.seconds,1200)
            self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_rtss_auto=True)
            with patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app.rtss,'present',return_value=True) as present:
                self.app.update_overlay()
                self.pump(.25); self.app.update_overlay()
            self.assertIn('00:20:00',present.call_args[0][2])

    def test_delayed_alert_can_finish_after_midnight_until_the_actual_reset(self):
        wall=datetime(2026,10,23,23,59)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,budget_reset_minute=360)
        self.app.tracker.cache['2026-10-23']={self.games[0].id:7200}
        self.app.tracker.evaluate(wall); alert=self.app.tracker.alerts[0]
        wall=datetime(2026,10,24,0,10)
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None): return wall
        with patch('gametime.controller.datetime',Clock),patch.object(self.app,'popup',return_value=True) as popup:
            self.app.finish_notification(alert)
        popup.assert_called_once_with(alert)
        self.assertFalse(self.app.tracker.alerts)


if __name__=='__main__': unittest.main()
