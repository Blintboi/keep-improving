"""Fullscreen image, delivery acknowledgement and focus safety regressions."""
from dataclasses import replace
from datetime import datetime,timedelta
import os
from pathlib import Path
from unittest import TestCase,skipUnless
from unittest.mock import Mock,patch
from PySide6.QtGui import QImage,QColor
from gametime.tracker import Alert,Sample
from gametime.scheduled_notifications import tick
import test_qt_ui as fixture


@skipUnless(os.name=='nt','Windows Qt required')
class FullscreenTests(TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def test_game_limit_warning_and_bedtime_use_in_game_receipts_even_in_normal_mode(self):
        from gametime.model import norm
        now=datetime.now().astimezone(); current=Sample(now,123,str(self.exe),'123:456')
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_rtss_auto=True)
        self.app.catalog.rules[norm(self.exe)]=self.games[0].id
        backend=Mock(); backend.fallback_for.return_value=False; backend.retry_due.return_value=False
        backend.present.return_value=False; backend.desktop_ready=True
        with patch.object(self.app,'rtss',backend),patch.object(self.app,'rtss_available',return_value=True),patch('gametime.qt_fullscreen_notifications.win32.sample',return_value=current),patch('gametime.qt_fullscreen_notifications.overlay_reason',return_value=''),patch('gametime.qt_fullscreen_notifications.play_notification'),patch.object(self.app,'update_overlay') as restore,patch('gametime.win32.u.SetForegroundWindow') as focus,patch('gametime.win32.u.SendInput') as keys:
            for mode in ('normal','defer'):
                for kind in ('warning','limit','session','bedtime','wellbeing'):
                    with self.subTest(mode=mode,kind=kind),patch.object(self.app,'notification_mode',return_value=mode):
                        self.app._fullscreen_retry=None; backend.present.return_value=False
                        alert=Alert(str(now.date()),(kind,),kind,'A játék befejezésének ideje.','OK')
                        self.assertFalse(self.app.popup(alert)); active=self.app._fullscreen_alert
                        self.assertIsNotNone(active); self.assertIsNone(self.app.popup_window)
                        active.tick(); self.assertFalse(self.app.popup(alert))
                        backend.present.return_value=True; active.tick(); self.assertTrue(self.app.popup(alert))
                        active.finish(); active.tick(); self.assertIsNone(self.app._fullscreen_alert)
            self.assertEqual(restore.call_count,10); focus.assert_not_called(); keys.assert_not_called()

    def test_unicode_icon_render_receipt_then_restore(self):
        from gametime.qt_fullscreen_notifications import present,WIDTH,HEIGHT
        from gametime.model import norm
        now=datetime.now().astimezone()
        icon=QImage(32,32,QImage.Format_ARGB32); icon.fill(QColor('#f12835')); icon_path=self.base/'custom-icon.png'; icon.save(str(icon_path))
        item={'id':'a'*32,'title':'Szünet és víz','text':'Árvíztűrő tükörfúrógép 🍎\nMásodik sor','icon':str(icon_path),'minute':now.hour*60+now.minute,'enabled':True}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_rtss_auto=True,scheduled_notifications=[item])
        current=Sample(now,123,str(self.exe),'123:456')
        self.app.catalog.rules[norm(self.exe)]=self.games[0].id
        backend=Mock(); backend.fallback_for.return_value=False; backend.present.return_value=False; backend.desktop_ready=True
        with patch.object(self.app,'rtss',backend),patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app,'notification_mode',return_value='defer'),patch('gametime.qt_fullscreen_notifications.win32.sample',return_value=current),patch('gametime.qt_fullscreen_notifications.overlay_reason',return_value=''),patch('gametime.qt_fullscreen_notifications.play_notification') as sound,patch('gametime.win32.u.SetForegroundWindow') as focus,patch('gametime.win32.u.SendInput') as keys:
            tick(self.app,current); active=self.app._fullscreen_alert; self.assertIsNotNone(active)
            self.assertFalse(self.store.alert_keys(now.date())); self.assertIn('<LI=',active.text)
            image=QImage(str(Path(active.directory.name)/'notice-0.png')); self.assertEqual((image.width(),image.height()),(1024,1024))
            self.assertGreater(sum(1 for x in range(24,WIDTH-24,4) for y in range(119,210,3) if image.pixelColor(x,y).lightness()>140),20)
            self.assertGreater(image.pixelColor(45,45).red(),220); image.save('test-reports/fullscreen-notification-example.png')
            active.tick(); tick(self.app,current); self.assertFalse(self.store.alert_keys(now.date()))
            backend.present.return_value=True; active.tick(); tick(self.app,current)
            self.assertIn('scheduled:'+item['id'],self.store.alert_keys(now.date())); sound.assert_called_once()
            self.assertTrue(backend.present.call_args.kwargs['require_current']); focus.assert_not_called(); keys.assert_not_called()
            with patch.object(self.app,'update_overlay') as restore:
                active.finish(); active.tick(); self.assertIsNone(self.app._fullscreen_alert); backend.hide.assert_called_once(); restore.assert_called_once()

    def test_foreground_change_cancels_unconfirmed_and_keeps_delivery_pending(self):
        from gametime.model import norm
        now=datetime.now().astimezone(); current=Sample(now,123,str(self.exe),'123:456')
        item={'id':'b'*32,'title':'Alert','text':'Must be seen','icon':'','minute':now.hour*60+now.minute,'enabled':True}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_rtss_auto=True,scheduled_notifications=[item]); self.app.catalog.rules[norm(self.exe)]=self.games[0].id
        backend=Mock(); backend.fallback_for.return_value=False; backend.present.return_value=False; backend.desktop_ready=True
        with patch.object(self.app,'rtss',backend),patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app,'notification_mode',return_value='defer'),patch('gametime.qt_fullscreen_notifications.overlay_reason',return_value=''),patch('gametime.qt_fullscreen_notifications.win32.sample',return_value=replace(current,identity='other:123')):
            tick(self.app,current); active=self.app._fullscreen_alert; active.tick()
            self.assertTrue(active.closing); active.tick(); self.assertIsNone(self.app._fullscreen_alert)
            self.assertFalse(self.store.alert_keys(now.date())); self.assertEqual(self.app._scheduled_pending,['scheduled:'+item['id']])

    def test_denied_or_unavailable_overlay_keeps_notification_pending(self):
        from gametime.model import norm
        now=datetime.now().astimezone(); current=Sample(now,123,str(self.exe),'123:456')
        item={'id':'c'*32,'title':'Alert','text':'Must be seen','icon':'','minute':now.hour*60+now.minute,'enabled':True}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_rtss_auto=True,scheduled_notifications=[item]); self.app.catalog.rules[norm(self.exe)]=self.games[0].id
        backend=Mock(); backend.fallback_for.return_value=False
        with patch.object(self.app,'rtss',backend),patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app,'notification_mode',return_value='audio'),patch('gametime.qt_fullscreen_notifications.overlay_reason',return_value='Protected'):
            tick(self.app,current)
            self.assertIsNone(getattr(self.app,'_fullscreen_alert',None)); backend.present.assert_not_called()
            self.assertFalse(self.store.alert_keys(now.date())); self.assertEqual(self.app._scheduled_pending,['scheduled:'+item['id']])

    def test_cleanup_failure_does_not_block_closing_or_future_alerts(self):
        from gametime.qt_fullscreen_notifications import FullscreenNotification
        current=Sample(datetime.now().astimezone(),123,str(self.exe),'123:456')
        with patch.object(self.app,'rtss'):
            view=FullscreenNotification(self.app,Alert(str(current.wall.date()),(),'scheduled','Text','',title='Title'),current)
            self.app._fullscreen_alert=view
            with patch.object(view.directory,'cleanup',side_effect=OSError('locked')),self.assertLogs('gametime.qt_fullscreen_notifications',level='WARNING'):
                view.shutdown()
            self.assertIsNone(self.app._fullscreen_alert)
            view.directory.cleanup()

    def test_long_messages_acknowledge_only_after_the_last_page_is_visible(self):
        from gametime.qt_fullscreen_notifications import FullscreenNotification,PAGE_SECONDS
        from types import SimpleNamespace
        now=datetime.now().astimezone(); current=Sample(now,123,str(self.exe),'123:456')
        backend=Mock(); backend.present.return_value=True; backend.fallback_for.return_value=False
        clock=[100.0]
        with patch.object(self.app,'rtss',backend),patch('gametime.qt_fullscreen_notifications.win32.sample',return_value=current),patch('gametime.qt_fullscreen_notifications.overlay_reason',return_value=''),patch('gametime.qt_fullscreen_notifications.play_notification') as sound,patch('gametime.qt_fullscreen_notifications.time',SimpleNamespace(monotonic=lambda:clock[0])):
            view=FullscreenNotification(self.app,Alert(str(now.date()),(),'scheduled','\n'.join('Sor '+str(i) for i in range(80)),'',title='Hosszú üzenet'),current)
            self.app._fullscreen_alert=view; self.assertGreater(view.pages,1)
            for page in range(view.pages):
                self.assertEqual(view.page,page); view.tick()
                self.assertEqual(view.confirmed,page==view.pages-1)
                self.assertTrue((Path(view.directory.name)/f'notice-{page}.png').is_file())
                if page<view.pages-1: clock[0]+=PAGE_SECONDS+1; view.tick()
            sound.assert_called_once(); view.shutdown()
