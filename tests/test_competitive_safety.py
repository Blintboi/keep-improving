"""Competitive-game boundaries: passive windows, audio fallback and interruption consent."""
from dataclasses import replace
from datetime import datetime,date,timedelta
import json
import os
import unittest
from unittest.mock import patch

if os.name=='nt': import test_overlay_consent as fixtures


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class CompetitiveSafetyTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.ConsentInterfaceTests.setUpClass.__func__) if os.name=='nt' else classmethod(lambda cls:None)
    if os.name=='nt':
        setUp=fixtures.ConsentInterfaceTests.setUp;tearDown=fixtures.ConsentInterfaceTests.tearDown
        pump=fixtures.ConsentInterfaceTests.pump;protected=fixtures.ConsentInterfaceTests.protected
    def alert(self,index=0):
        from gametime.tracker import Alert,Sample
        game=self.protected(); self.app.tracker.active=game;self.app.tracker.identity='12:34'
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'12:34')
        alert=Alert(date.today().isoformat(),('warning:'+str(6000+index),),'warning','Fixture warning','OK')
        self.app.tracker.alerts.append(alert)
        return game,current,alert

    def test_protected_windowed_popup_does_not_request_focus_or_game_input(self):
        from PySide6.QtCore import Qt
        game,current,alert=self.alert()
        with patch('gametime.controller.win32.sample',return_value=current),patch('gametime.win32.desktop_overlay_available',return_value=True),patch('gametime.win32.u.SetForegroundWindow') as focus,patch('gametime.win32.u.SendInput') as keys:
            self.app.notify(alert);window=self.app.popup_window
            self.assertTrue(window.isVisible());self.assertTrue(window.windowFlags()&Qt.WindowDoesNotAcceptFocus)
            self.assertTrue(window.testAttribute(Qt.WA_ShowWithoutActivating));focus.assert_not_called();keys.assert_not_called()
            self.assertFalse(self.app.tracker.alerts)

    def test_protected_fullscreen_uses_only_sound_and_commits_delivery_once(self):
        game,current,alert=self.alert()
        with patch('gametime.controller.win32.sample',return_value=current),patch('gametime.win32.desktop_overlay_available',return_value=False),patch('gametime.sound.play_notification',return_value=True) as sound,patch('gametime.win32.present_notification') as present,patch('gametime.win32.u.SendInput') as keys:
            self.app.notify(alert);self.app.finish_notification(alert)
            sound.assert_called_once();present.assert_not_called();keys.assert_not_called()
            self.assertIsNone(self.app.popup_window);self.assertFalse(self.app.tracker.alerts)
            self.assertIn(alert.keys[0],self.store.alert_keys(date.today()))

    def test_muted_or_failed_sound_keeps_alert_pending_until_visual_delivery_is_possible(self):
        game,current,alert=self.alert()
        with patch('gametime.controller.win32.sample',return_value=current),patch('gametime.win32.desktop_overlay_available',return_value=False),patch('gametime.sound.play_notification',return_value=False) as sound:
            self.app.settings=replace(self.app.settings,notification_sound='silent');self.app.notify(alert);sound.assert_not_called()
            self.app.settings=replace(self.app.settings,notification_sound='default')
            for _ in range(5):self.app.notify(alert)
            sound.assert_called_once();self.assertEqual(list(self.app.tracker.alerts),[alert]);self.assertFalse(self.store.alert_keys(date.today()))
        with patch('gametime.controller.win32.sample',return_value=current),patch('gametime.win32.desktop_overlay_available',return_value=True):
            self.app.notify(alert);self.assertTrue(self.app.popup_window.isVisible());self.assertFalse(self.app.tracker.alerts)

    def test_presentation_failure_is_retryable_without_input_or_duplicate_windows(self):
        game,current,alert=self.alert()
        with patch('gametime.controller.win32.sample',return_value=current),patch('gametime.win32.desktop_overlay_available',return_value=True),patch('gametime.win32.present_notification',side_effect=OSError('fixture')),patch('gametime.win32.u.SendInput') as keys:
            self.app.notify(alert);self.assertIsNone(self.app.popup_window);self.assertEqual(list(self.app.tracker.alerts),[alert]);keys.assert_not_called()
        with patch('gametime.controller.win32.sample',return_value=current),patch('gametime.win32.desktop_overlay_available',return_value=True):
            self.app.notify(alert);window=self.app.popup_window
            self.assertFalse(self.app.popup(alert));self.assertIs(self.app.popup_window,window);self.assertTrue(window.isVisible())

    def test_minimization_consent_is_independent_local_and_revocable_during_pending_action(self):
        from gametime.overlay_consent import MinimizeConsents,MINIMIZE_PREFIX
        from gametime.statistics_sync import StatisticsData
        from PySide6.QtWidgets import QPushButton
        game,current,alert=self.alert();self.app.overlay_consents.set(game,True)
        self.assertFalse(self.app.minimization_allowed(current.path));self.assertFalse(MinimizeConsents(self.store).accepted)
        self.app.game_countdown_dialog(game.id);window=self.app._dialogs[-1]
        def button(key):return next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t(key))
        with patch('gametime.qt_overlay_consent.request_consent',return_value=False):button('Review minimization risks…').click()
        self.assertFalse(self.app.minimization_allowed(current.path))
        with patch('gametime.qt_overlay_consent.request_consent',return_value=True) as request:button('Review minimization risks…').click()
        self.assertTrue(request.call_args.kwargs['minimization']);self.assertTrue(self.app.minimization_allowed(current.path))
        self.assertTrue(MinimizeConsents(self.store).allows(game))
        self.assertNotIn(MINIMIZE_PREFIX,json.dumps(StatisticsData(self.store).snapshot('a'*32,'Fixture')))
        self.app.settings=replace(self.app.settings,restriction_enabled=True)
        self.app.tracker.cache[str(current.wall.date())]={game.id:self.app.settings.restriction_seconds}
        button('Revoke minimization permission').click()
        with patch('gametime.controller.win32.sample',return_value=current),patch('gametime.win32.minimize_game') as minimize:
            self.app.finish_restriction(current.path,current.identity,str(current.wall.date()));minimize.assert_not_called()
        self.assertFalse(MinimizeConsents(self.store).allows(game));self.assertTrue(self.app.overlay_consents.allows(game))

    def test_protected_restriction_does_not_suppress_reminders_without_interruption_permission(self):
        game,current,alert=self.alert();self.app.settings=replace(self.app.settings,restriction_enabled=True)
        self.app.tracker.cache[str(current.wall.date())]={game.id:self.app.settings.restriction_seconds}
        self.assertFalse(self.app.enforce_gameplay(current));self.assertFalse(self.app.consume_silent_alert(alert))

    def test_native_minimization_never_overrides_helpers_or_uncheckable_paths(self):
        from gametime import win32
        for path in (str(self.base/'BEService.exe'),r'\\server\share\cs2.exe'):
            with patch.object(win32.u,'ShowWindowAsync') as show:
                self.assertFalse(win32.minimize_game(path,'12:34',consented=True));show.assert_not_called()
