"""Opt-in play restriction: isolated profiles and mocked input/launch boundaries."""
from dataclasses import replace
from datetime import date,datetime,timedelta
import os
import unittest
from unittest.mock import patch
import test_overlay as fixtures
from gametime.model import Settings

class RestrictionSettingsTests(unittest.TestCase):
    def test_opt_in_default_and_independent_threshold(self):
        self.assertFalse(Settings().restriction_enabled)
        self.assertEqual(Settings().restriction_seconds,125*60)
        for value in (float('nan'),float('inf'),0,-1,86401,True,'125'):
            with self.subTest(value=value),self.assertRaises(ValueError): replace(Settings(),restriction_seconds=value).validate()
        with self.assertRaises(ValueError): replace(Settings(),restriction_enabled='yes').validate()
        if os.name=='nt': replace(Settings(),restriction_seconds=60).validate()

@unittest.skipUnless(os.name=='nt','Windows required')
class RestrictionInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.OverlayInterfaceTests.setUpClass.__func__)
    tearDown=fixtures.OverlayInterfaceTests.tearDown
    pump=fixtures.OverlayInterfaceTests.pump
    sample=fixtures.OverlayInterfaceTests.sample

    def setUp(self):
        fixtures.OverlayInterfaceTests.setUp(self)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_enabled=True)

    def reach(self,total=7500):
        # A one-hour clock-jump fixture must stay on this day even at 23:xx.
        current=replace(self.sample(),wall=datetime.now().astimezone().replace(hour=12,minute=0,second=0,microsecond=0)); self.app.tracker.tick(current)
        self.app.tracker.cache[str(current.wall.date())]={self.game.id:total}
        return current

    def advance_grace(self,current,seconds=10):
        for offset in range(1,seconds+1):
            later=replace(current,wall=current.wall+timedelta(seconds=offset),awake=current.awake+offset)
            self.assertTrue(self.app.enforce_gameplay(later))
        return later

    def test_exact_threshold_and_disabled_mode(self):
        current=self.reach(7499)
        with patch('gametime.controller.win32.escape_game') as escape:
            self.assertFalse(self.app.enforce_gameplay(current)); escape.assert_not_called()
        self.assertFalse(self.app.restriction_reached())
        self.reach(); self.assertTrue(self.app.restriction_reached())
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_enabled=False)
        self.assertFalse(self.app.enforce_gameplay(current)); self.assertFalse(self.app.launch_restricted(self.game))

    def test_crossing_and_every_retry_allow_ten_seconds_before_escape_or_minimize(self):
        from gametime.tracker import Sample
        previous=self.reach(7499)
        current=Sample(previous.wall+timedelta(seconds=1),previous.awake+1,previous.path,previous.identity)
        self.app.tracker.tick(current)
        with patch('gametime.controller.win32.escape_game',return_value=True) as escape,patch('gametime.controller.win32.minimize_game',return_value=True) as minimize,patch('gametime.controller.win32.sample',return_value=current),patch.object(self.app,'restriction_notice') as notice:
            self.assertTrue(self.app.enforce_gameplay(current)); escape.assert_not_called(); minimize.assert_not_called()
            self.advance_grace(current,9)
            self.app.enforce_gameplay(replace(current,wall=current.wall+timedelta(seconds=9.999),awake=current.awake+9.999))
            escape.assert_not_called(); minimize.assert_not_called()
            due=replace(current,wall=current.wall+timedelta(seconds=10),awake=current.awake+10)
            self.app.enforce_gameplay(due); escape.assert_called_once(); minimize.assert_not_called()
            self.pump(.3); minimize.assert_called_once_with(current.path,current.identity); notice.assert_called_once()
            self.app.enforce_gameplay(due); self.advance_grace(due,9)
            self.pump(.22); self.assertEqual(minimize.call_count,1)
            self.advance_grace(replace(due,wall=due.wall+timedelta(seconds=9),awake=due.awake+9),1); self.pump(.3)
            self.assertEqual(minimize.call_count,2); escape.assert_called_once()

    def test_disabled_during_delay_cancels_action_and_next_day_resets(self):
        current=self.reach()
        with patch('gametime.controller.win32.escape_game'),patch('gametime.controller.win32.minimize_game') as minimize,patch('gametime.controller.win32.sample',return_value=current):
            self.app.enforce_gameplay(current); self.advance_grace(current)
            self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_enabled=False)
            self.pump(.3); minimize.assert_not_called()
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_enabled=True)
        self.assertFalse(self.app.restriction_reached(current.wall.date()+timedelta(days=1)))

    def test_leaving_or_locking_restarts_the_full_grace_on_return(self):
        current=self.reach()
        for fields in ({'path':'C:/Windows/notepad.exe'},{'identity':'reused:pid'},{'interactive':False}):
            with self.subTest(fields=fields),patch('gametime.controller.win32.escape_game') as escape,patch('gametime.controller.win32.minimize_game',return_value=True) as minimize,patch('gametime.controller.win32.sample',return_value=current),patch.object(self.app,'restriction_notice'):
                self.app.enforce_gameplay(current); self.advance_grace(current,9)
                away=replace(current,wall=current.wall+timedelta(seconds=9.5),awake=current.awake+9.5,**fields)
                self.assertFalse(self.app.enforce_gameplay(away))
                returned=replace(current,wall=current.wall+timedelta(seconds=10),awake=current.awake+10)
                self.app.enforce_gameplay(returned); self.advance_grace(returned,9)
                escape.assert_not_called(); minimize.assert_not_called()
                self.advance_grace(replace(returned,wall=returned.wall+timedelta(seconds=9),awake=returned.awake+9),1)
                self.pump(.3); minimize.assert_called_once()

    def test_stall_sleep_clock_jump_and_disable_restart_the_full_grace(self):
        current=self.reach()
        for awake,wall in ((20,20),(10,3610),(10,-50)):
            with self.subTest(awake=awake,wall=wall),patch('gametime.controller.win32.escape_game') as escape:
                self.app._restriction_grace=None
                self.app.enforce_gameplay(current); self.advance_grace(current,9)
                resumed=replace(current,awake=current.awake+awake,wall=current.wall+timedelta(seconds=wall))
                self.assertTrue(self.app.enforce_gameplay(resumed)); self.advance_grace(resumed,9)
                escape.assert_not_called()
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_enabled=False)
        self.assertFalse(self.app.enforce_gameplay(resumed)); self.assertIsNone(self.app._restriction_grace)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_enabled=True)
        with patch('gametime.controller.win32.escape_game') as escape:
            self.app.enforce_gameplay(resumed); self.advance_grace(resumed,9); escape.assert_not_called()

    def test_focus_or_identity_change_exclusion_and_lock_cancel_delayed_action(self):
        current=self.reach()
        for other in (replace(current,path='C:/Windows/notepad.exe'),replace(current,identity='reused:pid'),replace(current,interactive=False)):
            with self.subTest(other=other),patch('gametime.controller.win32.minimize_game') as minimize,patch('gametime.controller.win32.sample',return_value=other):
                self.app.finish_restriction(current.path,current.identity,str(current.wall.date())); minimize.assert_not_called()
        self.app.catalog.overrides[self.game.id]=False
        with patch('gametime.controller.win32.minimize_game') as minimize,patch('gametime.controller.win32.sample',return_value=current):
            self.assertFalse(self.app.enforce_gameplay(current)); self.app.finish_restriction(current.path,current.identity,str(current.wall.date())); minimize.assert_not_called()

    def test_guarded_escape_failure_still_attempts_minimize(self):
        current=self.reach()
        with patch('gametime.controller.win32.escape_game',side_effect=OSError('fixture')),patch('gametime.controller.win32.minimize_game',return_value=False) as minimize,patch('gametime.controller.win32.sample',return_value=current):
            self.app.enforce_gameplay(current); self.advance_grace(current); self.pump(.3)
            minimize.assert_called_once(); self.assertIn('Could not minimize',self.app.status_key)
            self.app.enforce_gameplay(current); self.advance_grace(current,9); self.pump(.22)
            minimize.assert_called_once()

    def test_hub_blocks_launch_and_rechecks_worker_but_excluded_game_can_launch(self):
        from queue import Queue
        current=self.reach(); self.app.select_game(self.game.id)
        with patch.object(self.app,'restriction_notice') as notice,patch('gametime.launch.LaunchWorker') as worker:
            self.app.launch_selected(); worker.assert_not_called(); notice.assert_called_once()
        class Worker:
            def __init__(self): self.results=Queue()
            def close(self): pass
        self.app.launcher=Worker(); self.app.launcher.results.put((self.game,object(),'')); self.app.launching=self.game.id
        with patch('gametime.launch.execute') as execute,patch.object(self.app,'restriction_notice'):
            self.app.poll_launch(); execute.assert_not_called()
        self.app.catalog.overrides[self.game.id]=False
        self.assertFalse(self.app.launch_restricted(self.game))

    def test_settings_persist_and_banner_and_buttons_follow_policy(self):
        self.app.restriction_enabled.setChecked(True); self.app.restriction_minutes.setValue(125)
        self.app.save_settings(); saved=self.store.settings()
        self.assertTrue(saved.restriction_enabled); self.assertEqual(saved.restriction_seconds,7500)
        self.assertEqual(saved.limit_seconds,7200); self.assertTrue(saved.overlay_enabled)
        self.reach(); self.app.render(); self.app.select_game(self.game.id)
        self.assertFalse(self.app.restriction_banner.isHidden()); self.assertFalse(self.app.launch_button.isEnabled())
        self.assertFalse(self.app.cards[self.game.id].play.isEnabled())
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_enabled=False)
        self.app.render(); self.assertTrue(self.app.restriction_banner.isHidden()); self.assertTrue(self.app.launch_button.isEnabled())

    def test_new_process_after_restriction_gets_its_own_escape_and_hidden_game_is_included(self):
        current=self.reach(); self.store.set_hidden(self.game.id,True)
        with patch('gametime.controller.win32.escape_game') as escape:
            self.assertTrue(self.app.enforce_gameplay(current)); escape.assert_not_called()
            self.advance_grace(current); self.assertEqual(escape.call_count,1)
            self.app.restriction_timer.stop(); self.app.restriction_timer=None
            other=replace(current,identity='different:creation'); self.app.tracker.identity=other.identity
            self.assertTrue(self.app.enforce_gameplay(other)); self.assertEqual(escape.call_count,1)
            self.advance_grace(other); self.assertEqual(escape.call_count,2)

    def test_no_early_or_expiry_popup_conflicts_after_restriction(self):
        from gametime.tracker import Alert
        self.reach(); alert=Alert(str(date.today()),('limit:7200',),'limit','Expired','OK'); self.app.tracker._queue(alert)
        with patch.object(self.app,'popup') as popup,patch('gametime.controller.win32.escape_game') as escape:
            self.app.notify(alert); popup.assert_not_called(); escape.assert_not_called()

@unittest.skipUnless(os.name=='nt','Windows required')
class NativeMinimizeGuardTests(unittest.TestCase):
    def test_exact_path_and_process_creation_and_focus_are_required(self):
        from gametime import win32
        def pid(hwnd,ptr): ptr._obj.value=42; return 1
        with patch.object(win32,'interactive_desktop',return_value=True),patch.object(win32.u,'GetForegroundWindow',return_value=123),patch.object(win32.u,'GetWindowThreadProcessId',side_effect=pid),patch.object(win32,'process_image',return_value=('C:\\Games\\game.exe','42:creation')),patch.object(win32.u,'ShowWindowAsync',return_value=True) as show:
            self.assertFalse(win32.minimize_game('C:\\Other\\game.exe','42:creation'))
            self.assertFalse(win32.minimize_game('C:\\Games\\game.exe','42:reused')); show.assert_not_called()
            self.assertTrue(win32.minimize_game('c:\\games\\GAME.exe','42:creation')); show.assert_called_once_with(123,6)
            show.reset_mock()
            with patch.object(win32.u,'GetForegroundWindow',side_effect=[123,999]):
                self.assertFalse(win32.minimize_game('C:\\Games\\game.exe','42:creation')); show.assert_not_called()
        with patch.object(win32,'interactive_desktop',return_value=False),patch.object(win32.u,'ShowWindowAsync') as show:
            self.assertFalse(win32.minimize_game('C:\\Games\\game.exe','42:creation')); show.assert_not_called()

if __name__=='__main__': unittest.main()
