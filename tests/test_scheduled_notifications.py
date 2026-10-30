"""Daily delivery, persistence and non-interrupting notification regression tests."""
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from gametime.model import Settings
from gametime.scheduled_notifications import tick
from gametime.store import Store


def item(ident='a'*32,minute=720):
    return dict(id=ident,title='Custom title',text='Custom message',icon='',minute=minute,enabled=True)


class ScheduledTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'test.sqlite3'); self.addCleanup(self.store.close)
        self.app=SimpleNamespace(settings=replace(Settings(),scheduled_notifications=[item(),item('b'*32)]),store=self.store,popup_window=None,notification_mode=Mock(return_value='normal'),popup=Mock(return_value=True))
        self.now=datetime(2026,10,29,12,0).astimezone()
    def sample(self,now=None,interactive=True): return SimpleNamespace(wall=now or self.now,interactive=interactive)
    def test_persists_settings_and_queues_same_minute_then_once_per_day(self):
        self.store.save_settings(self.app.settings); self.assertEqual(self.store.settings().scheduled_notifications,self.app.settings.scheduled_notifications)
        tick(self.app,self.sample()); tick(self.app,self.sample()); tick(self.app,self.sample())
        self.assertEqual(self.app.popup.call_count,2)
        self.assertEqual(self.app.popup.call_args_list[0].args[0].title,'Custom title')
        self.assertEqual(len(self.store.alert_keys(self.now.date())),2)
        fresh=SimpleNamespace(settings=self.app.settings,store=self.store,popup_window=None,notification_mode=Mock(return_value='normal'),popup=Mock(return_value=True))
        tick(fresh,self.sample()); fresh.popup.assert_not_called()
        tick(fresh,self.sample(self.now+timedelta(days=1))); fresh.popup.assert_called_once()
    def test_locked_and_fullscreen_queue_until_text_can_be_shown(self):
        tick(self.app,self.sample(interactive=False)); self.app.popup.assert_not_called()
        self.app.notification_mode.return_value='audio'; tick(self.app,self.sample(self.now+timedelta(minutes=1))); self.app.popup.assert_not_called()
        self.app.notification_mode.return_value='passive'; tick(self.app,self.sample(self.now+timedelta(minutes=2))); self.app.popup.assert_called_once()
    def test_validation_rejects_bad_data(self):
        for change in ({'minute':1440},{'title':' '},{'text':''},{'icon':'relative.png'},{'enabled':1}):
            with self.subTest(change=change),self.assertRaises(ValueError): replace(Settings(),scheduled_notifications=[item()|change]).validate()


if __name__=='__main__': unittest.main()

@unittest.skipUnless(__import__('os').name=='nt','Windows Qt required')
class ScheduledInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_qt_ui
        test_qt_ui.QtInterfaceTests.setUpClass.__func__(cls)
    def setUp(self):
        import test_qt_ui
        test_qt_ui.QtInterfaceTests.setUp(self)
    def tearDown(self):
        import test_qt_ui
        test_qt_ui.QtInterfaceTests.tearDown(self)
    def pump(self,seconds=.1):
        import test_qt_ui
        test_qt_ui.QtInterfaceTests.pump(self,seconds)
    def test_editor_saves_reopens_and_deletes(self):
        from PySide6.QtWidgets import QWidget,QPushButton,QPlainTextEdit
        self.app.scheduled_notifications_dialog(); window=self.app._dialogs[-1]
        def field(name): return next(w for w in window.findChildren(QWidget) if w.accessibleName()==self.app.t(name))
        def click(name): next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t(name)).click()
        field('Title').setText('Szünet'); field('Message').setPlainText('Igyál vizet!'); field('Time').setTime(__import__('PySide6.QtCore',fromlist=['QTime']).QTime(14,35)); click('Save')
        saved=self.store.settings().scheduled_notifications; self.assertEqual((saved[0]['title'],saved[0]['text'],saved[0]['minute']),('Szünet','Igyál vizet!',875))
        click('New'); self.assertEqual(field('Title').text(),''); window.reject()
        self.app.scheduled_notifications_dialog(); window=self.app._dialogs[-1]
        field('Scheduled notifications').setCurrentIndex(0); self.assertEqual(field('Title').text(),'Szünet')
        click('Delete'); self.assertEqual(self.store.settings().scheduled_notifications,[])
    def test_normal_alert_is_movable_and_closable_without_keyboard_activation(self):
        from PySide6.QtCore import Qt
        from gametime.tracker import Alert
        alert=Alert(self.now_day(),(),'warning','Test','OK')
        with patch.object(self.app,'notification_mode',return_value='normal'),patch('gametime.win32.u.SetForegroundWindow') as foreground,patch('gametime.win32.u.SendInput') as keys:
            self.assertTrue(self.app.popup(alert)); window=self.app.popup_window
            self.assertTrue(window.windowFlags()&Qt.WindowDoesNotAcceptFocus)
            self.assertFalse(window.windowFlags()&Qt.WindowTransparentForInput)
            self.assertFalse(window.windowFlags()&Qt.FramelessWindowHint)
            self.assertTrue(window.windowFlags()&Qt.WindowCloseButtonHint)
            import ctypes
            from gametime import win32
            message=win32.W.MSG(); message.message=0x21
            self.assertEqual(window.nativeEvent(b'windows_generic_MSG',ctypes.addressof(message)),(True,3))
            before=window.pos(); window.move(before.x()-100,before.y()+80)
            self.assertNotEqual(window.pos(),before)
            self.assertTrue(window.testAttribute(Qt.WA_ShowWithoutActivating)); foreground.assert_not_called(); keys.assert_not_called()
            window.close(); self.assertIsNone(self.app.popup_window)
    def now_day(self): return datetime.now().date().isoformat()
