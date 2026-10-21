"""Bedtime schedules, durable delivery, foreground guards and native Qt controls."""
from dataclasses import replace
from datetime import datetime, timedelta
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from gametime.bedtime import Bedtime, phase
from gametime.model import Settings
from gametime.store import Store
from gametime.tracker import Sample


class BedtimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name)/'usage.sqlite3'); self.addCleanup(self.store.close)
        self.schedule = Bedtime(self.store)
        self.settings = Settings(games_root=str(Path(self.temp.name)/'Games'), bedtime_enabled=True, bedtime_minimize=True)

    def sample(self, text, awake=0, interactive=True):
        return Sample(datetime.fromisoformat(text), awake, r'C:\Browser\chrome.exe', '42:created', interactive)

    def advance(self, current, seconds, settings=None):
        results=[]
        for second in range(1, seconds+1):
            results.append(self.schedule.update(settings or self.settings, replace(current, wall=current.wall+timedelta(seconds=second), awake=current.awake+second)))
        return results

    def test_defaults_and_validation(self):
        self.assertFalse(Settings().bedtime_enabled); self.assertFalse(Settings().bedtime_minimize)
        self.assertEqual((Settings().bedtime_warning_minute,Settings().bedtime_minute,Settings().bedtime_resume_minute),(1435,0,360))
        for fields in ({'bedtime_minute':True},{'bedtime_minute':1440},{'bedtime_warning_minute':-1},{'bedtime_resume_minute':'06:00'},
                       {'bedtime_enabled':1},{'bedtime_minimize':'yes'},{'bedtime_minute':1435},{'bedtime_resume_minute':1436}):
            with self.subTest(fields=fields),self.assertRaises(ValueError): replace(self.settings,**fields).validate()
        self.settings.validate()

    def test_midnight_and_morning_boundaries(self):
        for text, expected in [('2026-10-21T23:54:59','off'),('2026-10-21T23:55:00','warning'),
                              ('2026-10-22T00:00:00','bedtime'),('2026-10-22T05:59:59','bedtime'),('2026-10-22T06:00:00','off')]:
            self.assertEqual(phase(self.settings,datetime.fromisoformat(text))[0],expected)
        self.assertEqual(phase(self.settings,datetime.fromisoformat('2026-10-22T01:00'))[1],'2026-10-21')

    def test_custom_same_day_and_after_midnight_times(self):
        for warning,bedtime,resume in ((20*60,21*60,23*60),(60,65,8*60)):
            settings=replace(self.settings,bedtime_warning_minute=warning,bedtime_minute=bedtime,bedtime_resume_minute=resume).validate()
            self.assertEqual(phase(settings,datetime(2026,10,21,bedtime//60,bedtime%60))[0],'bedtime')
            self.assertEqual(phase(settings,datetime(2026,10,21,resume//60,resume%60))[0],'off')

    def test_warning_is_persisted_once_and_ledger_is_cached(self):
        current=self.sample('2026-10-21T23:55:00')
        with patch.object(self.store,'alert_keys',wraps=self.store.alert_keys) as read:
            marker=self.schedule.update(self.settings,current)[1]; self.assertIsNotNone(marker)
            self.schedule.delivered(marker)
            for result in self.advance(current,59): self.assertIsNone(result[1])
            read.assert_called_once()
        restarted=Bedtime(self.store)
        self.assertIsNone(restarted.update(self.settings,current)[1])
        self.assertIsNotNone(Bedtime(self.store).update(self.settings,self.sample('2026-10-22T23:55:00',86400))[1])

    def test_missed_warning_lock_sleep_clock_jump_and_busy_popup(self):
        self.assertIsNone(self.schedule.update(self.settings,self.sample('2026-10-21T23:56'))[1])
        for current,next_sample in ((self.sample('2026-10-21T23:54:59'),self.sample('2026-10-21T23:55:20',1)),
                                    (self.sample('2026-10-21T23:54:59'),self.sample('2026-10-21T23:55:20',21)),
                                    (self.sample('2026-10-21T23:55',interactive=False),self.sample('2026-10-21T23:55:01',1))):
            self.schedule=Bedtime(self.store); self.schedule.update(self.settings,current)
            self.assertIsNone(self.schedule.update(self.settings,next_sample)[1])
        self.schedule=Bedtime(self.store)
        self.assertIsNone(self.schedule.update(self.settings,self.sample('2026-10-21T23:55'),False)[1])
        self.assertIsNotNone(self.schedule.update(self.settings,self.sample('2026-10-21T23:55:01',1))[1])

    def test_minimizes_at_ten_second_cadence_across_windows(self):
        current=self.sample('2026-10-22T00:00')
        self.assertFalse(self.schedule.update(self.settings,current)[2])
        results=self.advance(current,30)
        self.assertEqual([i+1 for i,r in enumerate(results) if r[2]],[10,20,30])

    def test_disable_morning_and_reminder_only_stop_minimization(self):
        current=self.sample('2026-10-22T00:00'); self.schedule.update(self.settings,current)
        for settings in (replace(self.settings,bedtime_enabled=False),replace(self.settings,bedtime_minimize=False)):
            self.assertFalse(self.schedule.update(settings,replace(current,awake=10))[2])
        self.assertFalse(self.schedule.update(self.settings,self.sample('2026-10-22T06:00',21600))[2])

    def test_resume_and_clock_changes_grant_ten_awake_seconds(self):
        current=self.sample('2026-10-22T00:00'); self.schedule.update(self.settings,current)
        for resumed in (self.sample('2026-10-22T00:20',1),self.sample('2026-10-22T00:20',1200),self.sample('2026-10-22T00:00:01',1200)):
            self.schedule.update(self.settings,replace(current,interactive=False))
            self.assertFalse(self.schedule.update(self.settings,resumed)[2])
            results=self.advance(resumed,10)
            self.assertTrue(results[-1][2]); self.assertFalse(any(r[2] for r in results[:-1]))

    def test_legacy_profile_and_history_survive_save(self):
        self.store.db.execute("INSERT INTO settings VALUES ('config',?)",('{"games_root":"C:\\\\Games"}',))
        self.store.add_usage({('2026-10-21','fixture'):123}); self.store.set_enabled('fixture',False)
        self.assertFalse(self.store.settings().bedtime_enabled)
        self.store.save_settings(self.settings)
        self.assertTrue(self.store.settings().bedtime_enabled); self.assertEqual(self.store.totals('2026-10-21')['fixture'],123)
        self.assertFalse(self.store.overrides()['fixture'])


@unittest.skipUnless(os.name=='nt','Windows required')
class BedtimeNativeTests(unittest.TestCase):
    def test_browser_is_minimized_without_keyboard_input(self):
        from gametime import win32
        def pid(hwnd,ptr): ptr._obj.value=42; return 1
        def name(hwnd,buffer,length): buffer.value='Chrome_WidgetWin_1'; return 19
        with patch.object(win32,'interactive_desktop',return_value=True),patch.object(win32.u,'GetForegroundWindow',return_value=123),patch.object(win32.u,'GetShellWindow',return_value=2),patch.object(win32.u,'GetDesktopWindow',return_value=3),patch.object(win32.u,'IsIconic',return_value=False),patch.object(win32.u,'GetWindowThreadProcessId',side_effect=pid),patch.object(win32.u,'GetClassNameW',side_effect=name),patch.object(win32,'process_image',return_value=(r'C:\Browser\chrome.exe','42:created')),patch.object(win32.u,'ShowWindowAsync',return_value=True) as show,patch.object(win32.u,'SendInput') as keys:
            self.assertTrue(win32.minimize_foreground()); show.assert_called_once_with(123,6); keys.assert_not_called()
            show.reset_mock()
            with patch.object(win32.os,'getpid',return_value=42): self.assertFalse(win32.minimize_foreground())
            with patch.object(win32.u,'GetShellWindow',return_value=123): self.assertFalse(win32.minimize_foreground())
            with patch.object(win32,'interactive_desktop',return_value=False): self.assertFalse(win32.minimize_foreground())
            with patch.object(win32.u,'GetForegroundWindow',side_effect=[123,999]): self.assertFalse(win32.minimize_foreground())
            show.assert_not_called()

    def test_legacy_handover_is_scoped_backed_up_and_once(self):
        from gametime.bedtime_legacy import migrate
        with tempfile.TemporaryDirectory() as tmp:
            docs=Path(tmp); data=docs/'GameTimeMonitor/data'; data.mkdir(parents=True); store=Store(data/'usage.sqlite3')
            try:
                with patch('gametime.bedtime_legacy.documents',return_value=docs),patch('gametime.bedtime_legacy.legacy_task',side_effect=['<Task>fixture</Task>','disabled']) as task:
                    migrate(store,docs/'other'); task.assert_not_called()
                    migrate(store,data); self.assertTrue(store.settings().bedtime_enabled); self.assertFalse(store.settings().bedtime_minimize)
                    self.assertEqual((data/'backups/bedtime-reminder-task.xml').read_text(encoding='utf-16'),'<Task>fixture</Task>')
                    migrate(store,data); self.assertEqual(task.call_count,2)
            finally: store.close()


@unittest.skipUnless(os.name=='nt','Windows required')
class BedtimeInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_qt_ui as fixture
        fixture.QtInterfaceTests.setUpClass.__func__(cls)

    def setUp(self):
        import test_qt_ui as fixture
        fixture.QtInterfaceTests.setUp(self)

    def tearDown(self):
        import test_qt_ui as fixture
        fixture.QtInterfaceTests.tearDown(self)

    def pump(self,seconds=.03):
        import test_qt_ui as fixture
        fixture.QtInterfaceTests.pump(self,seconds)

    def test_controls_persist_and_translate_and_test_never_minimizes(self):
        from PySide6.QtCore import QTime
        self.app.bedtime_enabled.setChecked(True); self.app.bedtime_minimize.setChecked(True)
        self.app.bedtime_times['bedtime_minute'].setTime(QTime(0,30)); self.app.save_settings()
        saved=self.store.settings(); self.assertTrue(saved.bedtime_minimize); self.assertEqual(saved.bedtime_minute,30)
        with patch('gametime.controller.win32.escape_game') as escape,patch('gametime.controller.win32.minimize_foreground') as minimize:
            self.app.test_bedtime_popup(); self.pump()
            self.assertEqual(self.app.popup_window.windowTitle(),'Lefekvési emlékeztető'); escape.assert_not_called(); minimize.assert_not_called()
        self.app.dismiss_popup(); self.app.set_language('en'); self.assertEqual(self.app.bedtime_times['bedtime_minute'].time(),QTime(0,30))

    def test_controller_shows_warning_without_esc_and_enforces_without_game(self):
        self.app.settings=replace(self.app.settings,bedtime_enabled=True,bedtime_minimize=True)
        current=Sample(datetime(2026,10,21,23,55),100,r'C:\Browser\chrome.exe','42:created')
        with patch('gametime.controller.win32.escape_game') as escape,patch('gametime.controller.win32.minimize_foreground') as minimize,patch.object(self.app,'popup',return_value=True) as popup:
            self.assertFalse(self.app.bedtime_tick(current)); popup.assert_called_once(); self.assertEqual(popup.call_args.args[0].kind,'bedtime')
            current=replace(current,wall=datetime(2026,10,22,0,0),awake=400)
            self.assertTrue(self.app.bedtime_tick(current)); self.assertFalse(self.app.bedtime_banner.isHidden())
            for second in range(1,21): self.app.bedtime_tick(replace(current,wall=current.wall+timedelta(seconds=second),awake=current.awake+second))
            self.assertEqual(minimize.call_count,2); escape.assert_not_called()
