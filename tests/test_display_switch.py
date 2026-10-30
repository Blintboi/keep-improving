"""Protected-game display is an explicit local choice, separate from previews."""
from dataclasses import replace
from datetime import datetime
import json
import sqlite3
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from PySide6.QtCore import QTimer,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QCheckBox,QPushButton
import test_qt_ui as fixture
from gametime.overlay_consent import Consents,MinimizeConsents,display_reason,DISPLAY_KEY
from gametime.game_safety import PROTECTED,UNCHECKED
from gametime.model import norm
from gametime.tracker import Alert,Sample


class DisplaySwitchTests(TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def protected_game(self):
        game=replace(self.games[0],id='steam:730',name='Protected fixture')
        self.app.catalog.games[game.id]=game; self.app.catalog.rules[norm(self.exe)]=game.id
        return game

    def test_default_persistence_revocation_and_permission_separation(self):
        from gametime.statistics_sync import StatisticsData
        game=self.protected_game(); consent=self.app.overlay_consents; before=self.store.settings()
        self.assertFalse(consent.display_enabled)
        consent.set(game,True); self.assertEqual(display_reason(self.app.catalog,str(self.exe),game),PROTECTED)
        consent.set_display_enabled(True)
        self.assertTrue(Consents(self.store).display_enabled); self.assertFalse(MinimizeConsents(self.store).display_enabled)
        self.assertEqual(display_reason(self.app.catalog,str(self.exe),game),'')
        self.assertEqual(display_reason(self.app.catalog,str(self.base/'BEService.exe'),game),PROTECTED)
        self.assertEqual(display_reason(self.app.catalog,str(self.exe),replace(game,root=str(self.base/'missing'))),UNCHECKED)
        self.assertEqual(self.store.settings(),before)
        self.assertNotIn(DISPLAY_KEY,json.dumps(StatisticsData(self.store).snapshot('a'*32,'Fixture')))
        with patch('gametime.overlay_consent.DISPLAY_NOTICE_VERSION',2): self.assertFalse(Consents(self.store).display_enabled)
        consent.set_display_enabled(False); self.assertFalse(Consents(self.store).display_enabled)
        self.assertTrue(consent.allows(game))  # The old image-preview permission is preserved.

    def test_corrupt_global_permission_fails_closed(self):
        for value in ('true','[]','{}','{','{"notice_version":true,"accepted":true,"accepted_at":"2026-10-29T00:00:00+00:00"}',
                      '{"notice_version":1,"accepted":true,"accepted_at":"2026-10-29T00:00:00"}'):
            with self.subTest(value=value):
                with self.store.db: self.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(DISPLAY_KEY,value))
                self.assertFalse(Consents(self.store).display_enabled)

    def test_switch_cancel_explicit_accept_revoke_and_save_failure(self):
        page=self.app.notifications_page; self.app.switch_page(6)
        for accepted in (False,True):
            with patch('gametime.qt_overlay_consent.request_display_consent',return_value=accepted): page.protected.click()
            self.assertEqual(page.protected.isChecked(),accepted)
            self.assertEqual(Consents(self.store).display_enabled,accepted)
        with patch('gametime.qt_overlay_consent.request_display_consent') as confirmation:
            page.protected.click(); confirmation.assert_not_called()
        self.assertFalse(Consents(self.store).display_enabled)
        with patch('gametime.qt_overlay_consent.request_display_consent',return_value=True),patch.object(self.app.overlay_consents,'set_display_enabled',side_effect=sqlite3.OperationalError('fixture')):
            page.protected.click()
        self.assertFalse(page.protected.isChecked()); self.assertFalse(Consents(self.store).display_enabled)

    def test_confirmation_requires_checkbox_and_button_never_enter_or_close(self):
        from gametime.qt_overlay_consent import request_display_consent
        for action in ('enter','close','accept'):
            def interact():
                dialog=QApplication.activeModalWidget(); check=dialog.findChild(QCheckBox)
                accept=next(b for b in dialog.findChildren(QPushButton) if b.text()==self.app.t('Enable at my own risk'))
                self.assertFalse(check.isChecked()); self.assertFalse(accept.isEnabled())
                if action=='accept':
                    check.setChecked(True); accept.click()
                elif action=='enter': QTest.keyClick(dialog,Qt.Key_Return)
                else: dialog.close()
            QTimer.singleShot(20,interact)
            self.assertEqual(request_display_consent(self.app,self.app),action=='accept')
        self.assertFalse(self.app.overlay_consents.display_enabled)

    def test_live_countdown_and_fullscreen_notice_stop_on_revocation_without_input(self):
        from gametime.qt_fullscreen_notifications import present
        game=self.protected_game(); self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_enabled=True,overlay_rtss_auto=True)
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'12:34'); self.app.tracker.tick(current)
        alert=Alert(str(current.wall.date()),(),'scheduled','Szünet','',title='Emlékeztető')
        backend=Mock(); backend.identity=''; backend.desktop_ready=True; backend.failed_paths=set()
        backend.present.return_value=True; backend.fallback_for.return_value=False; backend.retry_due.return_value=False
        with patch.object(self.app,'rtss',backend),patch.object(self.app,'rtss_available',return_value=True),patch('gametime.win32.sample',return_value=current),patch('gametime.qt_fullscreen_notifications.play_notification'),patch('gametime.win32.u.SetForegroundWindow') as focus,patch('gametime.win32.u.SendInput') as keys:
            self.app.update_overlay(); backend.present.assert_not_called()
            self.assertFalse(present(self.app,alert,current)); self.assertIsNone(getattr(self.app,'_fullscreen_alert',None))
            self.app.overlay_consents.set_display_enabled(True); self.app.apply_display_settings()
            self.assertEqual(self.app._overlay_backend,'rtss')
            self.assertFalse(self.app.overlay_consents.allows(game))
            present(self.app,alert,current); active=self.app._fullscreen_alert; self.assertIsNotNone(active)
            active.tick(); self.assertTrue(active.confirmed)
            self.app.notifications_page.protected.click(); self.assertTrue(active.closing)
            active.tick(); self.assertIsNone(self.app._fullscreen_alert)
            self.assertEqual(self.app._overlay_backend,'none'); self.assertFalse(self.app.overlay.isVisible())
            self.assertEqual(self.app._rtss_consent_paths,frozenset())
            focus.assert_not_called(); keys.assert_not_called()
