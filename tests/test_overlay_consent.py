"""Explicit consent, local persistence, revocation and exact-game isolation."""
from dataclasses import replace
from datetime import datetime,date
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch,Mock
from gametime.overlay_consent import Consents,NOTICE_VERSION,PREFIX,token,overlay_reason
from gametime.game_safety import PROTECTED,UNCHECKED
from gametime.model import Game,Settings,norm
from gametime.store import Store


class ConsentStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.store=Store(self.root/'profile.sqlite3'); self.addCleanup(self.store.close)
        self.game=Game('steam:730','Fixture','Steam',str(self.root))
        self.consent=Consents(self.store)

    def test_default_is_denied_persistence_is_game_root_and_notice_specific(self):
        self.assertFalse(self.consent.allows(self.game)); self.consent.set(self.game,True)
        self.assertTrue(Consents(self.store).allows(self.game))
        self.assertFalse(self.consent.allows(replace(self.game,id='steam:other')))
        self.assertFalse(self.consent.allows(replace(self.game,root=str(self.root/'other'))))
        with patch('gametime.overlay_consent.NOTICE_VERSION',NOTICE_VERSION+1): self.assertFalse(Consents(self.store).allows(self.game))
        self.consent.set(self.game,False); self.assertFalse(Consents(self.store).allows(self.game))

    def test_corrupt_or_incomplete_records_do_not_grant_permission(self):
        for value in ('true','[]','{}','{','{"notice_version":true,"accepted":true,"accepted_at":"2026-10-23T00:00:00+00:00"}',
                      '{"notice_version":1,"accepted":true,"accepted_at":"2026-10-23T00:00:00"}'):
            with self.subTest(value=value):
                with self.store.db: self.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(PREFIX+token(self.game),value))
                self.assertFalse(Consents(self.store).allows(self.game))

    def test_consent_is_not_exported_with_statistics_and_does_not_enable_features(self):
        from gametime.statistics_sync import StatisticsData
        before=self.store.settings(); self.consent.set(self.game,True)
        self.assertEqual(self.store.settings(),before); self.assertFalse(before.overlay_enabled); self.assertFalse(before.overlay_rtss_auto)
        snapshot=json.dumps(StatisticsData(self.store).snapshot('a'*32,'Fixture'))
        self.assertNotIn(PREFIX,snapshot); self.assertNotIn(token(self.game),snapshot); self.assertNotIn('accepted_at',snapshot)

    def test_uncheckable_game_and_anticheat_helpers_cannot_be_overridden(self):
        self.consent.set(self.game,True)
        self.assertEqual(self.consent.reason(str(self.root/'BEService.exe'),self.game),PROTECTED)
        unknown=replace(self.game,id='other',root=str(self.root/'missing'))
        self.consent.set(unknown,True); self.assertEqual(self.consent.reason(game=unknown),UNCHECKED)
        known=replace(unknown,id='steam:730')
        self.consent.set(known,True); self.assertEqual(self.consent.reason(game=known),UNCHECKED)


if os.name=='nt': import test_qt_ui as fixtures

@unittest.skipUnless(os.name=='nt','Windows Qt required')
class ConsentInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.QtInterfaceTests.setUpClass.__func__) if os.name=='nt' else classmethod(lambda cls:None)
    if os.name=='nt':
        setUp=fixtures.QtInterfaceTests.setUp; tearDown=fixtures.QtInterfaceTests.tearDown; pump=fixtures.QtInterfaceTests.pump

    def protected(self):
        game=replace(self.games[0],id='steam:730',name='Fixture protected game')
        self.app.catalog.games[game.id]=game; self.app.catalog.rules[norm(self.exe)]=game.id
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_enabled=True,overlay_rtss_auto=True)
        return game

    def modal(self,accept):
        from PySide6.QtCore import QTimer,Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication,QCheckBox,QPushButton
        from gametime.qt_overlay_consent import request_consent
        seen={}
        def interact():
            dialog=QApplication.activeModalWidget(); check=dialog.findChild(QCheckBox)
            enable=next(b for b in dialog.findChildren(QPushButton) if b.text()==self.app.t('Enable at my own risk'))
            seen['unchecked']=not check.isChecked(); seen['disabled']=not enable.isEnabled()
            if accept:
                check.setChecked(True); seen['enabled_after_check']=enable.isEnabled(); enable.click()
            else:
                QTest.keyClick(dialog,Qt.Key_Return)
        QTimer.singleShot(40,interact)
        result=request_consent(self.app,self.app,self.protected())
        self.assertTrue(seen['unchecked']); self.assertTrue(seen['disabled'])
        if accept: self.assertTrue(seen['enabled_after_check'])
        return result

    def test_enter_or_cancel_does_not_accept_and_explicit_checkbox_then_button_does(self):
        self.assertFalse(self.modal(False)); self.assertFalse(self.app.overlay_consents.accepted)
        self.assertTrue(self.modal(True)); self.assertFalse(self.app.overlay_consents.accepted)  # Caller persists only after confirmation.

    def test_editor_accept_cancel_revoke_and_unsaved_display_settings_are_independent(self):
        from PySide6.QtWidgets import QPushButton,QWidget
        game=self.protected(); self.app.game_countdown_dialog(game.id); window=self.app._dialogs[-1]
        def button(key):return next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t(key))
        fields={key:next(w for w in window.findChildren(QWidget) if w.accessibleName()==self.app.t(key))
                for key in ('Hide this countdown','Normal color','Warning color','Monitor','Countdown position','Horizontal (px)','Vertical (px)','Text size','Preview state')}
        def visibility(visible):
            for key,field in fields.items():
                self.assertEqual(field.isVisible(),visible,key)
            for key in ('Preview (10s)','Refresh game image','Default colors','Save'):
                self.assertEqual(button(key).isVisible(),visible,key)
            self.assertTrue(button('Cancel').isVisible())
        visibility(True); self.assertFalse(button('Preview (10s)').isEnabled()); self.assertTrue(button('Allow game image preview…').isVisible())
        with patch('gametime.qt_overlay_consent.request_consent',return_value=False): button('Allow game image preview…').click()
        self.assertFalse(self.app.overlay_consents.allows(game)); visibility(True)
        with patch('gametime.qt_overlay_consent.request_consent',return_value=True): button('Allow game image preview…').click()
        self.assertTrue(self.app.overlay_consents.allows(game)); self.assertEqual(self.store.settings().game_overlays,{}); visibility(True)
        self.app.set_language('en'); button('Revoke game image preview permission').click()
        self.assertFalse(self.app.overlay_consents.allows(game)); self.assertFalse(Consents(self.store).allows(game)); visibility(True)

    def test_switching_between_blocked_and_allowed_games_preserves_drafts_and_saved_preferences(self):
        from PySide6.QtWidgets import QPushButton,QWidget
        game=self.protected(); allowed=self.games[1]
        original={game.id:{'overlay_enabled':True,'overlay_font_size':39,'overlay_color_normal':'#123456'}}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,game_overlays=original)
        self.store.save_settings(self.app.settings)
        self.app.game_countdown_dialog(allowed.id); window=self.app._dialogs[-1]
        def field(key):return next(w for w in window.findChildren(QWidget) if w.accessibleName()==self.app.t(key))
        def button(key):return next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t(key))
        hidden=field('Hide this countdown'); field('Text size').setValue(42)
        games=field('Countdown target'); games.setCurrentIndex(games.findData(game.id))
        self.assertTrue(hidden.isVisible()); self.assertTrue(button('Save').isVisible()); self.assertFalse(button('Preview (10s)').isEnabled())
        self.app.set_language('en'); self.assertTrue(field('Text size').isVisible())
        games.setCurrentIndex(games.findData(allowed.id))
        self.assertTrue(hidden.isVisible()); self.assertEqual(field('Text size').value(),42)
        button('Save').click(); saved=self.store.settings()
        self.assertEqual(saved.game_overlays[game.id],original[game.id])
        self.assertEqual(saved.game_overlays[allowed.id]['overlay_font_size'],42)

    def test_failed_save_keeps_consent_denied(self):
        import sqlite3
        from PySide6.QtWidgets import QPushButton
        game=self.protected(); self.app.game_countdown_dialog(game.id); window=self.app._dialogs[-1]
        button=next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t('Allow game image preview…'))
        with patch('gametime.qt_overlay_consent.request_consent',return_value=True),patch.object(self.app.overlay_consents,'set',side_effect=sqlite3.OperationalError('fixture')):
            button.click()
        self.assertFalse(self.app.overlay_consents.allows(game))

    def test_uncheckable_protected_game_stays_hidden_even_with_consent(self):
        from PySide6.QtWidgets import QPushButton,QLabel
        from gametime.game_preview import GameWindow
        game=replace(self.protected(),root=str(self.base/'unavailable'))
        self.app.catalog.games[game.id]=game; self.app.overlay_consents.set(game,True)
        target=GameWindow(123,456,str(self.exe),'456:789',game.id,PROTECTED,self.app.overlay_consents,token(game),game)
        self.assertTrue(target.blocked())
        self.app.game_countdown_dialog(game.id); window=self.app._dialogs[-1]
        def button(key):return next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t(key))
        self.assertFalse(button('Preview (10s)').isVisible()); self.assertFalse(button('Save').isVisible())
        self.assertTrue(any(w.isVisible() and w.text()==self.app.t(UNCHECKED) for w in window.findChildren(QLabel)))
        button('Revoke game image preview permission').click()
        self.assertFalse(button('Allow game image preview…').isVisible()); self.assertFalse(self.app.overlay_consents.allows(game))

    def test_native_popups_never_send_escape_to_games(self):
        from gametime.tracker import Alert,Sample
        for index,protected in enumerate((False,True,True)):
            game=self.protected() if protected else self.games[0]
            if index==2: self.app.overlay_consents.set(game,True)
            self.app.tracker.active=game; self.app.tracker.identity='12:34'
            current=Sample(datetime.now().astimezone(),100,str(self.exe),'12:34')
            alert=Alert(date.today().isoformat(),('warning:'+str(6000+index),),'warning','Fixture warning','OK')
            self.app.tracker.alerts.append(alert)
            with self.subTest(protected=protected,consented=index==2),patch('gametime.controller.win32.sample',return_value=current),patch('gametime.win32.desktop_overlay_available',return_value=True),patch('gametime.controller.win32.escape_game',return_value=False) as escape,patch.object(self.app.rtss,'present') as rtss,patch.object(self.app.overlay,'present') as desktop,patch.object(self.app.game_snapshots,'request') as capture:
                self.app.notify(alert)
                escape.assert_not_called()
                self.assertTrue(self.app.popup_window.isVisible()); self.assertFalse(self.app.tracker.alerts)
                rtss.assert_not_called(); desktop.assert_not_called(); capture.assert_not_called()
            self.app.dismiss_popup()

    def test_protected_restriction_minimizes_without_escape_even_with_consent(self):
        from datetime import timedelta
        from gametime.tracker import Sample
        game=self.protected(); self.app.overlay_consents.set(game,True)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_enabled=True)
        current=Sample(datetime.now().astimezone().replace(hour=12,minute=0,second=0,microsecond=0),100,str(self.exe),'12:34')
        self.app.tracker.active=game; self.app.tracker.identity=current.identity
        self.app.tracker.cache[str(current.wall.date())]={game.id:self.app.settings.restriction_seconds}
        with patch('gametime.controller.win32.sample',return_value=current),patch('gametime.controller.win32.escape_game') as escape,patch('gametime.controller.win32.minimize_game',return_value=True) as minimize,patch.object(self.app,'restriction_notice'):
            self.assertFalse(self.app.enforce_gameplay(current)); minimize.assert_not_called()
            self.app.minimize_consents.set(game,True)
            for offset in range(11):
                self.assertTrue(self.app.enforce_gameplay(replace(current,awake=current.awake+offset,wall=current.wall+timedelta(seconds=offset))))
            self.pump(.3); minimize.assert_called_once_with(current.path,current.identity,consented=True); escape.assert_not_called()

    def test_accepted_overlay_and_snapshot_work_but_automatic_escape_stays_disabled(self):
        from gametime.tracker import Sample,Alert
        from PySide6.QtGui import QImage,QColor
        from gametime.overlay import screen_device
        game=self.protected(); self.app.overlay_consents.set(game,True); self.app.overlay_consents.set_display_enabled(True)
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'12:34'); self.app.tracker.tick(current)
        target=Mock(path=str(self.exe),game_id=game.id,**{'valid.return_value':True})
        image=QImage(100,100,QImage.Format_RGB32);image.fill(QColor('red'))
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app,'rtss_available',return_value=False),patch.object(self.app.overlay,'present') as present:
            self.app.update_overlay(); present.assert_called_once()
            self.app.overlay_consents.set_display_enabled(False); self.app.refresh_rtss_consent(); self.app.update_overlay()
            self.assertEqual(present.call_count,1);self.assertEqual(self.app._overlay_backend,'none')
        self.app.overlay_consents.set(game,True);self.app.overlay_enabled.setChecked(True)
        with patch('gametime.qt_game_preview.running_window',return_value=target),patch('gametime.game_preview.capture_window',return_value=(image,screen_device(self.qt.primaryScreen()),(0,0,1,1))):
            from PySide6.QtWidgets import QWidget
            self.app.show(); self.app.game_countdown_dialog(game.id); window=self.app._dialogs[-1]
            fields={w.accessibleName():w for w in window.findChildren(QWidget) if w.accessibleName()}
            fields[self.app.t('Hide this countdown')].setChecked(False)
            self.pump(.2);self.assertIsNotNone(fields[self.app.t('Countdown position')].game_background)
        alert=Alert(date.today().isoformat(),('warning:6000',),'warning','Warning','OK');self.app.tracker._queue(alert)
        with patch('gametime.controller.win32.sample',return_value=current),patch('gametime.controller.win32.escape_game') as escape,patch.object(self.app,'popup',return_value=True):
            self.app.notify(alert);escape.assert_not_called()

    def test_rtss_authorization_is_exact_and_known_basename_collisions_fail_closed(self):
        game=self.protected(); self.app.overlay_consents.set_display_enabled(True); self.app.refresh_rtss_consent()
        self.assertIn(norm(self.exe),self.app.rtss.approved)
        other_root=self.base/'Other';other_root.mkdir();other=replace(game,id='other:730',root=str(other_root),name='VALORANT')
        other_exe=other_root/self.exe.name;other_exe.touch();self.app.catalog.games[other.id]=other;self.app.catalog.rules[norm(other_exe)]=other.id
        self.app.catalog.overrides[other.id]=False
        self.app.refresh_rtss_consent();self.assertEqual(self.app.rtss.approved,frozenset())
        self.app.catalog.overrides[other.id]=True;self.app.refresh_rtss_consent()
        self.assertEqual(self.app.rtss.approved,frozenset((norm(self.exe),norm(other_exe))))

    def test_window_permission_is_rechecked_after_revocation(self):
        from gametime.game_preview import GameWindow
        game=self.protected();self.app.overlay_consents.set(game,True)
        target=GameWindow(123,456,str(self.exe),'456:789',game.id,PROTECTED,self.app.overlay_consents,token(game))
        self.assertFalse(target.blocked());self.app.overlay_consents.set(game,False);self.assertTrue(target.blocked())


@unittest.skipUnless(os.name=='nt','Windows required')
class ConsentRTSSTests(unittest.TestCase):
    def test_revocation_cancels_queued_preparation_for_opaque_game_executables(self):
        from gametime.rtss import Backend
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);exe=root/'opaque.exe';exe.touch();backend=Backend(str(root));backend.thread=Mock()
            with patch('gametime.rtss.configure_profile') as enable,patch('gametime.rtss.C.CDLL'):
                try:
                    backend.authorize([str(exe)]);backend.prepare([str(exe)]);self.assertTrue(backend.profiles)
                    backend.authorize([]);self.assertFalse(backend.profiles)
                    self.assertFalse(backend.configure(root/'RTSS.exe',str(exe)));enable.assert_not_called()
                finally:backend.close()

    def test_only_approved_exact_path_can_enable_protected_hook_and_revoke_restores_zero(self):
        from gametime.rtss import Backend
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);exe=root/'cs2.exe';exe.touch();server=root/'RTSS.exe'
            backend=Backend(str(root/'data'))
            with patch('gametime.rtss.installation',return_value=server),patch('gametime.rtss.C.CDLL'),patch('gametime.rtss.start_server') as start,patch.object(backend,'exchange',return_value={'available':True,'healthy':True}):
                try:
                    backend.authorize([str(exe)]);self.assertTrue(backend.configure(server,str(exe)))
                    profile=root/'Profiles/cs2.exe.cfg';self.assertIn('EnableHooking=1',profile.read_text())
                    self.assertFalse(backend.configure(server,str(root/'other/cs2.exe')))
                    backend.authorize([]);backend.close()
                    self.assertIn('EnableHooking=0',profile.read_text());self.assertIn('EnableOSD=0',profile.read_text());start.assert_not_called()
                finally:backend.close()
