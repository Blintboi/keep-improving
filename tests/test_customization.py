"""Personalization must preserve accounting, reminder delivery and local data."""
from dataclasses import replace
from datetime import date,datetime,timedelta
from pathlib import Path
from sqlite3 import OperationalError
from contextlib import closing
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from gametime.model import Settings,Game,Catalog
from gametime.store import Store
from gametime.tracker import Tracker,Sample,Alert
from gametime.schedule import day_settings,game_settings,bedtime_occurrence
from gametime.bedtime import Bedtime,phase
from gametime.notification_text import notification_text
import test_qt_ui as fixture

WEEKEND=dict(warning_seconds=9000,limit_seconds=10800,restriction_enabled=True,restriction_seconds=11400,
             bedtime_enabled=True,bedtime_warning_minute=22*60,bedtime_minute=23*60,bedtime_resume_minute=7*60,bedtime_minimize=True)


class CustomizationTests(unittest.TestCase):
    def test_validation_does_not_allow_schedule_or_game_overrides_to_change_unrelated_fields(self):
        settings=Settings()
        for fields in ({'weekend_enabled':1},{'weekend_schedule':[]},{'weekend_schedule':{'language':'hu'}},
                       {'weekend_schedule':{'warning_seconds':8000}},{'weekend_schedule':{'bedtime_minute':1435}},
                       {'notification_sound':'unknown'},{'notification_sound':'custom'},
                       {'notification_sound':'custom','notification_sound_path':'relative.wav'},
                       {'game_overlays':{'x':{'limit_seconds':60}}},{'game_overlays':{'x':{'overlay_font_size':73}}},
                       {'game_overlays':{'x':{'overlay_x':float('nan')}}},{'game_overlays':{'x':{'overlay_enabled':1}}}):
            with self.subTest(fields=fields),self.assertRaises(ValueError): replace(settings,**fields).validate()
        replace(settings,weekend_enabled=True,weekend_schedule=WEEKEND,game_overlays={'x':{'overlay_enabled':False}},notification_sound='custom',notification_sound_path=r'C:\Sounds\custom.wav').validate()

    def test_weekend_plan_is_local_and_does_not_mutate_normal_settings(self):
        settings=replace(Settings(),weekend_enabled=True,weekend_schedule=WEEKEND)
        for text,expected in (('2026-10-23',7200),('2026-10-24',10800),('2026-10-25',10800),('2026-10-26',7200)):
            plan=day_settings(settings,text); self.assertEqual(plan.limit_seconds,expected)
            self.assertEqual(notification_text(settings,'warning',17,day=text),notification_text(plan,'warning',17,day=text))
        self.assertEqual(settings.limit_seconds,7200); self.assertTrue(settings.weekend_enabled)
        self.assertEqual(day_settings(replace(settings,weekend_enabled=False),'2026-10-24').limit_seconds,7200)
        empty=replace(settings,weekend_schedule={}); self.assertIs(day_settings(empty,date(2026,10,24)),empty)

    def test_overnight_bedtime_uses_start_day_including_sunday_to_monday(self):
        settings=replace(Settings(),bedtime_enabled=True,bedtime_minimize=True,weekend_enabled=True,weekend_schedule=WEEKEND)
        for text,state,day,resume in (('2026-10-23T23:55','warning','2026-10-23',360),
                                    ('2026-10-24T00:30','bedtime','2026-10-23',360),
                                    ('2026-10-24T06:00','off',None,None),
                                    ('2026-10-24T22:00','warning','2026-10-24',420),
                                    ('2026-10-25T01:00','bedtime','2026-10-24',420),
                                    ('2026-10-26T01:00','bedtime','2026-10-25',420),
                                    ('2026-10-26T07:00','off',None,None),
                                    ('2026-10-26T23:55','warning','2026-10-26',360)):
            actual=bedtime_occurrence(settings,datetime.fromisoformat(text)); self.assertEqual(actual[0],state,text)
            if day: self.assertEqual((actual[1],actual[2].bedtime_resume_minute),(day,resume))
        settings.bedtime_enabled=False
        self.assertEqual(phase(settings,datetime(2026,10,26,1))[0],'bedtime')
        self.assertEqual(phase(settings,datetime(2026,10,26,23,55))[0],'off')

    def test_overlapping_weekend_reminder_does_not_end_the_previous_night_early(self):
        settings=replace(Settings(),bedtime_enabled=True,weekend_enabled=True,weekend_schedule=dict(bedtime_warning_minute=60,bedtime_minute=65,bedtime_resume_minute=720))
        state,day,plan=bedtime_occurrence(settings,datetime(2026,10,24,1))
        self.assertEqual((state,day,plan.bedtime_resume_minute),('bedtime','2026-10-23',360))
        self.assertEqual(bedtime_occurrence(settings,datetime(2026,10,24,6))[:2],('bedtime','2026-10-24'))

    def test_weekend_alerts_use_weekend_threshold_and_keep_midnight_accounting(self):
        with tempfile.TemporaryDirectory() as tmp,closing(Store(Path(tmp)/'usage.sqlite3')) as store:
            settings=replace(Settings(),weekend_enabled=True,weekend_schedule=WEEKEND,notification_messages={'warning':'{remaining}/{minutes}','limit':'Limit {minutes}'})
            catalog=Catalog(settings); tracker=Tracker(store,catalog)
            tracker.cache['2026-10-24']={'fixture':7200}; tracker.evaluate(datetime(2026,10,24,12)); self.assertFalse(tracker.alerts)
            tracker.cache['2026-10-24']={'fixture':9000}; tracker.evaluate(datetime(2026,10,24,13)); alert=tracker.alerts.popleft()
            self.assertEqual((alert.text,alert.keys),('30/180',('warning:9000',))); tracker.delivered(alert)
            tracker.cache['2026-10-24']={'fixture':10800}; tracker.evaluate(datetime(2026,10,24,14)); alert=tracker.alerts.popleft()
            self.assertEqual(alert.text,'Limit 180'); self.assertIn('limit:10800',alert.keys)
            game=Game('fixture','Fixture','Games',str(Path(tmp)/'Games'))
            tracker._credit(game,datetime(2026,10,23,23,59,59),datetime(2026,10,24,0,0,1),2)
            self.assertEqual(tracker.pending[('2026-10-23','fixture')],1); self.assertEqual(tracker.pending[('2026-10-24','fixture')],1)

    def test_weekend_bedtime_keeps_grace_and_ledger_after_midnight_on_monday(self):
        with tempfile.TemporaryDirectory() as tmp,closing(Store(Path(tmp)/'usage.sqlite3')) as store:
            settings=replace(Settings(),bedtime_enabled=False,weekend_enabled=True,weekend_schedule=WEEKEND)
            bedtime=Bedtime(store); first=Sample(datetime(2026,10,25,23,59,55),100)
            bedtime.update(settings,first); ledger=bedtime.ledger
            for second in range(1,11):
                state,marker,minimize=bedtime.update(settings,replace(first,wall=first.wall+timedelta(seconds=second),awake=100+second))
                self.assertEqual(state,'bedtime'); self.assertEqual(bedtime.ledger,ledger); self.assertEqual(minimize,second==10)

    @unittest.skipUnless(os.name=='nt','Windows sound required')
    def test_silent_alias_and_custom_sound_are_async_and_failure_falls_back(self):
        from gametime.sound import play_notification
        import winsound
        with patch('gametime.sound.winsound.PlaySound') as play:
            self.assertTrue(play_notification(replace(Settings(),notification_sound='silent'))); play.assert_not_called()
            for mode,alias in (('default','SystemExclamation'),('information','SystemAsterisk'),('error','SystemHand')):
                play_notification(replace(Settings(),notification_sound=mode)); source,flags=play.call_args.args
                self.assertEqual(source,alias); self.assertTrue(flags & winsound.SND_ASYNC); self.assertTrue(flags & winsound.SND_ALIAS)
            custom=replace(Settings(),notification_sound='custom',notification_sound_path=r'C:\Missing\sound.wav')
            play.side_effect=[RuntimeError('missing'),None]; self.assertTrue(play_notification(custom))
            self.assertEqual(play.call_args_list[-2].args[0],custom.notification_sound_path); self.assertTrue(play.call_args_list[-2].args[1]&winsound.SND_FILENAME)
            self.assertEqual(play.call_args.args[0],'SystemExclamation')

    def test_profiles_reopen_and_reconciliation_preserves_per_game_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'usage.sqlite3'; store=Store(path)
            old=Game('games:fixture','Fixture','Games',str(Path(tmp)/'Fixture')); new=replace(old,id='steam:42',source='Steam')
            settings=replace(Settings(games_root=str(Path(tmp)/'Games')),weekend_enabled=True,weekend_schedule=WEEKEND,notification_sound='silent',game_overlays={old.id:{'overlay_enabled':True,'overlay_font_size':38,'overlay_x':.2,'overlay_y':.8}})
            store.save_settings(settings); store.upsert([old]); store.add_usage({('2026-10-23',old.id):123}); store.set_hidden(old.id,True); store.set_enabled(old.id,False)
            tracker=Tracker(store,Catalog(settings,[old])); tracker.reconcile([new],lambda game:False)
            self.assertNotIn(old.id,settings.game_overlays); self.assertEqual(settings.game_overlays[new.id]['overlay_font_size'],38)
            store.close(); store=Store(path)
            try:
                saved=store.settings(); self.assertEqual(saved.game_overlays,settings.game_overlays); self.assertEqual(saved.weekend_schedule,WEEKEND); self.assertEqual(saved.notification_sound,'silent')
                self.assertEqual(store.totals('2026-10-23'),{new.id:123}); self.assertIn(new.id,store.hidden_ids()); self.assertFalse(store.overrides()[new.id])
                from gametime.statistics_sync import StatisticsData
                snapshot=json.dumps(StatisticsData(store).snapshot('b'*32,'Fixture'))
                for key in ('game_overlays','weekend_schedule','notification_sound'): self.assertNotIn(key,snapshot)
            finally: store.close()


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class CustomizationInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def field(self,window,name,kind=None):
        from PySide6.QtWidgets import QWidget
        return next(widget for widget in window.findChildren(kind or QWidget) if widget.accessibleName()==self.app.t(name))

    def click(self,window,key):
        from PySide6.QtWidgets import QPushButton
        next(item for item in window.findChildren(QPushButton) if item.text()==self.app.t(key)).click()

    def test_weekly_groups_failure_translation_and_save_preserve_other_days(self):
        from PySide6.QtCore import QTime
        from gametime.schedule import week_plans
        editor=self.app.schedule_editor; editor.select_days(range(5)); self.app.limit.setValue(155)
        editor.select_days((5,6)); self.app.limit.setValue(180); self.app.warning.setValue(150)
        self.app.bedtime_times['bedtime_minute'].setTime(QTime(1,0)); self.app.set_language('en')
        self.assertEqual(self.app.bedtime_times['bedtime_minute'].time(),QTime(1,0))
        with patch.object(self.store,'save_settings',side_effect=OperationalError('fixture')): self.app.save_settings()
        self.assertEqual(self.store.settings().daily_schedules,{})
        self.app.save_settings(); saved=self.store.settings(); plans=week_plans(saved)
        self.assertEqual((plans[0]['limit_seconds'],plans[5]['limit_seconds']),(9300,10800))
        editor.select_days(range(5)); self.assertEqual(self.app.limit.value(),155)
        self.app.save_settings(); self.assertEqual(week_plans(self.store.settings())[5]['limit_seconds'],10800)

    def test_per_game_drafts_preview_cancel_save_reset_and_translation(self):
        from PySide6.QtWidgets import QComboBox
        self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]
        self.field(window,'Hide this countdown').setChecked(False)
        self.field(window,'Text size').setValue(42); self.field(window,'Horizontal (px)').setValue(137); self.field(window,'Vertical (px)').setValue(219)
        self.click(window,'Preview (10s)'); self.pump(.03)
        self.assertEqual(self.app._overlay_preview_settings.overlay_font_size,42); self.assertEqual(self.store.settings().game_overlays,{})
        self.app.set_language('en'); self.assertEqual(self.field(window,'Horizontal (px)').value(),137)
        self.click(window,'Cancel'); self.assertEqual(self.store.settings().game_overlays,{}); self.assertIsNone(self.app._overlay_preview_settings)
        self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]
        self.field(window,'Hide this countdown').setChecked(False)
        self.field(window,'Text size').setValue(42); self.click(window,'Save')
        saved=self.store.settings(); self.assertFalse(saved.overlay_enabled); self.assertTrue(saved.game_overlays[self.games[0].id]['overlay_enabled'])
        self.assertEqual(game_settings(saved,self.games[0].id).overlay_font_size,42); self.assertFalse(game_settings(saved,self.games[1].id).overlay_enabled)

    def test_hidden_game_starts_without_position_controls_and_only_explicitly_enabled_game_changes(self):
        from PySide6.QtWidgets import QComboBox,QCheckBox
        self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]
        hidden=self.field(window,'Hide this countdown',QCheckBox); games=self.field(window,'Countdown target',QComboBox)
        self.assertTrue(hidden.isChecked())
        self.assertFalse(self.field(window,'Text size').isVisible())
        self.assertEqual(self.store.settings().game_overlays,{})
        games.setCurrentIndex(games.findData(self.games[1].id))
        self.assertTrue(hidden.isChecked())
        games.setCurrentIndex(games.findData(self.games[0].id))
        hidden.setChecked(False)
        self.click(window,'Save')
        self.assertEqual(set(self.store.settings().game_overlays),{self.games[0].id})
        self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]
        hidden=self.field(window,'Hide this countdown',QCheckBox); hidden.setChecked(True)
        self.assertFalse(self.field(window,'Text size').isVisible())
        self.click(window,'Save'); self.assertFalse(self.store.settings().game_overlays[self.games[0].id]['overlay_enabled'])

    def test_existing_hidden_game_remains_hidden_in_editor(self):
        from PySide6.QtWidgets import QCheckBox
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,game_overlays={self.games[0].id:{'overlay_enabled':False}})
        self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]
        self.assertTrue(self.field(window,'Hide this countdown',QCheckBox).isChecked())
        self.assertFalse(self.field(window,'Text size').isVisible())

    def test_game_hidden_countdown_keeps_tracker_and_warning_popup(self):
        settings=replace(self.app.settings,overlay_enabled=True,game_overlays={self.games[0].id:{'overlay_enabled':False}})
        self.app.settings=self.app.catalog.settings=settings; self.app.tracker.active=self.games[0]; self.app.tracker.identity='fixture:1'
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'fixture:1')
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app.rtss,'present') as present:
            self.app.update_overlay(); self.assertFalse(self.app.overlay.isVisible()); present.assert_not_called()
        alert=Alert(str(date.today()),('warning:6000',),'warning','Warning','OK'); self.app.tracker.alerts.append(alert)
        self.assertFalse(self.app.consume_silent_alert(alert)); self.assertEqual(self.store.alert_keys(date.today()),set())

    def test_game_custom_countdown_reaches_desktop_rtss_and_warning_suppression_with_global_off(self):
        settings=replace(self.app.settings,overlay_enabled=False,overlay_rtss_auto=True,game_overlays={self.games[0].id:{'overlay_enabled':True,'overlay_font_size':42,'overlay_x':.2,'overlay_y':.8}})
        self.app.settings=self.app.catalog.settings=settings; self.app.tracker.active=self.games[0]; self.app.tracker.identity='fixture:1'
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'fixture:1')
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app,'rtss_available',return_value=False),patch.object(self.app.overlay,'present') as present:
            self.app.update_overlay(); self.assertEqual(present.call_args.args[2].overlay_font_size,42)
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app.rtss,'present',return_value=True) as present:
            self.app.update_overlay(); self.assertEqual(present.call_args.args[3][-1],42); self.assertIn('<FNT=Consolas,-56',present.call_args.args[2])
        alert=Alert(str(date.today()),('warning:6000',),'warning','Warning','OK'); self.app.tracker.alerts.append(alert)
        with patch.object(self.app,'overlay_warning_visible',return_value=True): self.assertTrue(self.app.consume_silent_alert(alert))

    def test_sound_drafts_are_saved_only_by_save_and_silent_popup_is_visible(self):
        from PySide6.QtWidgets import QComboBox,QCheckBox
        mode=self.field(self.app,'Notification sound',QComboBox); mode.setCurrentIndex(mode.findData('silent'))
        self.assertEqual(self.store.settings().notification_sound,'default'); self.app.set_language('en'); self.assertEqual(mode.currentData(),'silent')
        self.app.save_settings(); self.assertEqual(self.store.settings().notification_sound,'silent')
        with patch('gametime.sound.winsound.PlaySound') as sound:
            self.app.test_popup(); self.pump(.03); self.assertTrue(self.app.popup_window.isVisible()); sound.assert_not_called()

    def test_two_game_drafts_and_failed_save_preserve_other_preferences(self):
        from PySide6.QtWidgets import QComboBox,QCheckBox
        self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]
        hidden=self.field(window,'Hide this countdown',QCheckBox); games=self.field(window,'Countdown target',QComboBox)
        self.field(window,'Text size').setValue(38)
        games.setCurrentIndex(games.findData(self.games[1].id)); hidden.setChecked(False); hidden.setChecked(True)
        games.setCurrentIndex(games.findData(self.games[0].id)); self.assertEqual(self.field(window,'Text size').value(),38)
        with patch.object(self.store,'save_settings',side_effect=OperationalError('fixture')): self.click(window,'Save')
        self.assertTrue(window.isVisible()); self.assertEqual(self.app.settings.game_overlays,{})
        self.click(window,'Save'); saved=self.store.settings(); self.assertEqual(len(saved.game_overlays),2)
        self.assertFalse(saved.game_overlays[self.games[1].id]['overlay_enabled']); self.assertEqual(saved.game_overlays[self.games[0].id]['overlay_font_size'],38)
        self.assertEqual(self.store.totals(date.today()),{}); self.assertEqual(saved.limit_seconds,7200)

    def test_weekend_render_restriction_and_both_countdown_budgets_agree(self):
        class Saturday(datetime):
            @classmethod
            def now(cls,*args,**kwargs): return cls(2026,10,24,12)
        settings=replace(self.app.settings,overlay_enabled=True,overlay_rtss_auto=True,weekend_enabled=True,weekend_schedule=WEEKEND)
        self.app.settings=self.app.catalog.settings=settings; self.app.tracker.active=self.games[0]; self.app.tracker.identity='fixture:1'
        self.app.tracker.cache['2026-10-24']={self.games[0].id:9000}
        current=Sample(Saturday.now(),100,str(self.exe),'fixture:1')
        with patch('gametime.qt_ui.datetime',Saturday),patch('gametime.controller.datetime',Saturday),patch('gametime.qt_ui.win32.sample',return_value=current):
            self.app.render(); self.assertEqual(self.app.remaining_label.text(),'00:30:00'); self.assertAlmostEqual(self.app.ring.ratio,9000/10800)
            self.assertFalse(self.app.restriction_reached())
            with patch.object(self.app,'rtss_available',return_value=False),patch.object(self.app.overlay,'present') as present:
                self.app.update_overlay(); self.assertEqual(present.call_args.args[:2],(1800,9000)); self.assertEqual(present.call_args.args[2].limit_seconds,10800)
            with patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app.rtss,'present',return_value=True) as present:
                self.app.update_overlay(); self.assertIn('00:30:00',present.call_args.args[2])
            self.app.tracker.cache['2026-10-24'][self.games[0].id]=11400; self.assertTrue(self.app.restriction_reached())

    def test_only_enabled_game_profiles_are_prepared_for_rtss_when_global_countdown_is_off(self):
        other=self.base/'another.exe'; other.write_bytes(b'MZ fixture')
        self.app.catalog.rules[str(other)]=self.games[1].id
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_enabled=False,overlay_rtss_auto=True,game_overlays={self.games[0].id:{'overlay_enabled':True}})
        with patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app.rtss,'prepare') as prepare:
            self.app.prepare_rtss_profiles(); self.assertEqual([path.casefold() for path in prepare.call_args.args[0]],[str(self.exe).casefold()])
