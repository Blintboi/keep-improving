"""Zero durations, single sessions, notification drafts and application choices."""
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch,Mock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QPushButton,QLineEdit,QListWidget,QLabel
from gametime.focus import Focus,FocusSettings
from gametime.store import Store
from gametime.model import Settings
from gametime.tracker import Alert
from gametime.notification_rules import validate_action
from gametime import notification_drafts as drafts
import test_qt_ui as fixture


class SingleSessionTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'usage.sqlite3'); self.addCleanup(self.store.close)
        self.focus=Focus(self.store); self.now=datetime(2026,11,2,12,0).astimezone()

    def test_any_positive_work_length_finishes_once_without_breaks_or_restrictions(self):
        for work in (1,17,30,45,90,240):
            with self.subTest(work=work):
                f=self.focus; f.stop(); f.configure(FocusSettings(work=work,short_break=0,long_break=0,rounds=0,block_sites=['example.com']))
                count=f.completed_rounds; f.start(100); f.advance(100+work*60-1,self.now)
                self.assertTrue(f.restricting); self.assertEqual(f.remaining,1)
                f.advance(100+work*60,self.now); self.assertTrue(f.finished); self.assertFalse(f.running)
                self.assertEqual((f.phase,f.remaining,f.completed_rounds),('focus',0,count+1)); self.assertFalse(f.policy()['active'])
                for step in (1,10,10000): f.advance(100+work*60+step,self.now)
                self.assertEqual(f.completed_rounds,count+1)
                restored=Focus(self.store); self.assertTrue(restored.finished); self.assertEqual(restored.settings,f.settings)
                restored.start(100000); self.assertEqual(restored.remaining,work*60); self.assertTrue(restored.restricting)
                self.assertEqual(restored.completed_rounds,count+1); restored.stop()

    def test_zero_and_positive_break_combinations_preserve_cadence_and_wait_for_start(self):
        for short in (0,2):
            for long in (0,5):
                for rounds in (0,1,3):
                    with self.subTest(short=short,long=long,rounds=rounds):
                        f=self.focus; f.stop(); f.configure(FocusSettings(work=7,short_break=short,long_break=long,rounds=rounds))
                        for index in range(1,4):
                            f.start(0); f.advance(420,self.now)
                            if rounds==0:
                                self.assertTrue(f.finished); self.assertFalse(f.running); break
                            duration=long if index%rounds==0 else short
                            if duration:
                                self.assertTrue(f.running); self.assertEqual(f.remaining,duration*60)
                                self.assertEqual(f.phase,'long_break' if index%rounds==0 else 'short_break')
                                f.advance(420+duration*60,self.now)
                            self.assertFalse(f.running); self.assertFalse(f.restricting); self.assertEqual(f.phase,'focus'); self.assertEqual(f.remaining,420)

    def test_pause_restart_and_next_session_settings_do_not_reset_progress(self):
        f=self.focus; f.configure(FocusSettings(work=40,short_break=0,long_break=0,rounds=0)); f.start(0); f.pause(600)
        restored=Focus(self.store); self.assertEqual(restored.remaining,1800); self.assertFalse(restored.finished)
        restored.configure(replace(restored.settings,work=15)); self.assertEqual(restored.remaining,1800)
        restored.start(1000); restored.advance(2800,self.now); self.assertTrue(restored.finished)
        restored.start(3000); self.assertEqual(restored.remaining,900)

    def test_zero_work_is_an_explicit_error_without_changing_saved_preferences(self):
        old=self.focus.settings
        with self.assertRaisesRegex(ValueError,'focus duration'): self.focus.configure(FocusSettings(work=0,short_break=0,long_break=0,rounds=0))
        self.assertEqual(self.focus.settings,old)
        for key in ('short_break','long_break','rounds'):
            with self.subTest(key=key),self.assertRaises(ValueError): replace(old,**{key:-1}).validate()
        validate_action(dict(kind='pomodoro',work=23,short_break=0,long_break=0,rounds=0))

    def test_disabling_an_unstarted_paused_break_returns_to_ready_without_false_notice(self):
        f=self.focus; f.configure(FocusSettings(work=1,short_break=2,long_break=5,rounds=3))
        f.start(0); f.advance(60,self.now); f.pause(60)
        f.configure(replace(f.settings,short_break=0))
        self.assertEqual((f.phase,f.remaining,f.running),('focus',60,False))
        self.assertNotEqual(f.notice,'Focus complete. Time for a break.')


class SingleSessionInterfaceTests(TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp; tearDown=fixture.QtInterfaceTests.tearDown; pump=fixture.QtInterfaceTests.pump

    def test_notification_edit_reopen_popup_start_and_completed_state(self):
        page=self.app.notifications_page; page.create(); editor=page.editor
        editor.title.setText('One session'); editor.message.setPlainText('Start when ready')
        editor.action.setCurrentIndex(editor.action.findData('pomodoro'))
        for key,value in dict(work=37,short_break=0,long_break=0,rounds=0).items():
            editor.pomodoro.inputs[key].setValue(value)
        key=editor.key; page.show_list(); self.assertEqual(drafts.read(self.store)[key]['action']['rounds'],0)
        page.save(); self.assertFalse(page.error.text()); page.edit(key)
        self.assertEqual(editor.pomodoro.value(),dict(work=37,short_break=0,long_break=0,rounds=0))
        with patch.object(self.app,'notification_mode',return_value='normal'):
            editor.preview(); window=self.app.popup_window; self.assertIsNotNone(window)
            self.assertEqual(window.pomodoro_fields.value(),editor.pomodoro.value())
            window.pomodoro_fields.inputs['work'].setValue(12); window.action_button.click(); window.close()
        f=self.app.focus; self.assertEqual(f.remaining,720)
        f.advance(f.last_awake+720); self.app.focus_page.refresh(force=True)
        self.assertEqual(self.app.focus_page.clock.text(),'00:00'); self.assertEqual(self.app.focus_page.timer_state.text(),self.app.t('Completed'))
        self.assertEqual(self.app.focus_page.start_button.text(),self.app.t('Start focus')); self.assertEqual(f.completed_rounds,1)

    def test_focus_settings_accept_zero_breaks_and_report_invalid_work_without_reverting_it(self):
        self.app.focus_page.timer_settings(); dialog=self.app._dialogs[-1]
        def field(name): return next(w for w in dialog.findChildren(QWidget) if w.accessibleName()==self.app.t(name))
        field('Focus minutes').setValue(18)
        for name in ('Short break minutes','Long break minutes','Rounds before long break'): field(name).setValue(0)
        from PySide6.QtTest import QTest
        edit=field('Rounds before long break'); edit.lineEdit().selectAll(); QTest.keyClicks(edit.lineEdit(),'0'); QTest.keyClick(edit.lineEdit(),Qt.Key_Tab)
        self.assertEqual(edit.value(),0)
        save=next(w for w in dialog.findChildren(QPushButton) if w.text()==self.app.t('Save')); save.click()
        self.assertEqual((self.app.focus.settings.work,self.app.focus.settings.short_break,self.app.focus.settings.long_break,self.app.focus.settings.rounds),(18,0,0,0))
        self.app.focus_page.timer_settings(); dialog=self.app._dialogs[-1]; field('Focus minutes').setValue(0)
        next(w for w in dialog.findChildren(QPushButton) if w.text()==self.app.t('Save')).click()
        self.assertTrue(dialog.isVisible()); self.assertEqual(field('Focus minutes').value(),0)
        self.assertTrue(any(w.text()==self.app.t('Set a focus duration from 1 to 240 minutes.') for w in dialog.findChildren(QLabel)))
        self.assertEqual(self.app.focus.settings.work,18); dialog.reject()

    def test_incomplete_zero_work_draft_is_kept_and_can_be_fixed(self):
        page=self.app.notifications_page; page.create(); editor=page.editor
        editor.title.setText('Work'); editor.message.setPlainText('Work'); editor.action.setCurrentIndex(editor.action.findData('pomodoro'))
        editor.pomodoro.inputs['work'].setValue(0); key=editor.key; page.show_list(); page.save()
        self.assertTrue(page.error.text()); self.assertEqual(drafts.read(self.store)[key]['action']['work'],0)
        self.assertFalse(self.store.settings().scheduled_notifications)
        page.edit(key); self.assertEqual(editor.pomodoro.inputs['work'].value(),0)
        editor.pomodoro.inputs['work'].setValue(8); page.save(); self.assertFalse(page.error.text())

    def test_application_picker_is_searchable_cancellable_and_does_not_launch(self):
        from gametime.qt_notification_applications import choose
        other=self.base/'Other Editor.exe'; other.write_bytes(b'MZ fixture'); accepted=Mock()
        with patch('gametime.qt_notification_applications.choices',return_value=[(str(self.exe),'Fixture'),(str(other),'Other Editor')]),patch('gametime.qt_notification_options.subprocess.Popen') as launch:
            dialog=choose(self.app,str(self.exe),accepted); listing=dialog.findChild(QListWidget)
            search=next(w for w in dialog.findChildren(QLineEdit) if w.accessibleName()==self.app.t('Search applications…'))
            select=next(w for w in dialog.findChildren(QPushButton) if w.text()==self.app.t('Select application'))
            self.assertTrue(select.isEnabled()); search.setText('Other Editor'); self.assertTrue(listing.item(0).isHidden()); self.assertFalse(select.isEnabled())
            listing.setCurrentRow(1); self.assertTrue(select.isEnabled()); accepted.assert_not_called(); dialog.reject(); accepted.assert_not_called()
            dialog=choose(self.app,'',accepted); listing=dialog.findChild(QListWidget); listing.setCurrentRow(1)
            next(w for w in dialog.findChildren(QPushButton) if w.text()==self.app.t('Select application')).click()
            accepted.assert_called_once_with(str(other)); launch.assert_not_called()

    def test_application_choices_merge_existing_sources_deduplicate_and_exclude_missing_paths(self):
        from gametime.notification_applications import choices
        other=self.base/'Registered.exe'; other.write_bytes(b'MZ fixture')
        with self.store.db:
            self.store.db.execute('INSERT OR REPLACE INTO activity_items VALUES (?,?,?)',('app',str(self.exe),'Fixture.exe'))
            self.store.db.execute('INSERT OR REPLACE INTO activity_items VALUES (?,?,?)',('app',str(self.base/'Gone.exe'),'Gone'))
            self.store.db.execute('INSERT OR REPLACE INTO activity_items VALUES (?,?,?)',('app','relative.exe','Relative'))
        with patch('gametime.notification_applications.registered_applications',return_value=[(str(self.exe).upper(),'Duplicate'),(str(other),'Registered'),(r'\\server\remote.exe','Remote')]):
            found=choices(self.app,str(other))
        self.assertEqual({path.casefold() for path,name in found},{str(self.exe).casefold(),str(other).casefold()})
        self.assertEqual(len(found),2)
