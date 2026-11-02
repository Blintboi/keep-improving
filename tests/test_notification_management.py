"""Create/delete drafts, independent reminder removal, and safe recovery."""
from dataclasses import replace
from datetime import datetime,timedelta
import json
from unittest import TestCase
from unittest.mock import patch
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QApplication,QPushButton,QLabel
import test_qt_ui as fixture
from gametime.notification_text import KINDS
from gametime import notification_drafts as drafts
from gametime.model import Settings
from gametime.bedtime import Bedtime
from gametime.tracker import Sample,Alert


class NotificationManagementTests(TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp; tearDown=fixture.QtInterfaceTests.tearDown; pump=fixture.QtInterfaceTests.pump

    def test_all_rows_have_trash_and_builtin_deletion_only_applies_on_save(self):
        page=self.app.notifications_page; before=self.store.settings()
        for index in range(page.rows.count()):
            row=page.rows.itemAt(index).widget()
            trash=next(button for button in row.findChildren(QPushButton) if not button.icon().isNull())
            with patch.object(page,'ask_delete',return_value=False): trash.click()
            self.assertFalse(page.changes)
        with patch.object(page,'ask_delete',return_value=True):
            for kind in KINDS: page.confirm_remove('builtin:'+kind,kind)
        self.assertEqual(page.row_keys,[]); self.assertEqual(self.store.settings(),before)
        self.assertEqual(set(drafts.read(self.store)),{'builtin:'+kind for kind in KINDS})
        page.save(); saved=self.store.settings()
        self.assertEqual(saved.removed_notifications,list(KINDS)); self.assertEqual(drafts.read(self.store),{})
        self.assertEqual(replace(saved,removed_notifications=[]),before)
        page.create(); editor=page.editor
        editor.trigger.setCurrentIndex(editor.trigger.findData('bedtime'))
        editor.title.setText('Bedtime')
        editor.message.setPlainText('Go to bed at {bedtime}.')
        page.save(); self.assertEqual(self.store.settings().scheduled_notifications[0]['trigger'],'bedtime')
        self.assertEqual(self.store.settings().scheduled_notifications[0]['text'],'Go to bed at {bedtime}.')
        self.assertEqual(self.store.settings().bedtime_enabled,before.bedtime_enabled)

    def test_incomplete_draft_survives_navigation_failure_and_restart_without_activation(self):
        page=self.app.notifications_page; page.create(); key=page.editor.key
        page.editor.message.setPlainText('Drink water'); page.show_list()
        self.assertEqual(self.store.settings().scheduled_notifications,[])
        self.assertIn(key,drafts.read(self.store)); page.save()
        self.assertTrue(page.error.text()); self.assertIn(key,drafts.read(self.store))
        from gametime.qt_notification_list import NotificationsPage
        restored=NotificationsPage(self.app)
        try:
            restored.edit(key); self.assertEqual(restored.editor.message.toPlainText(),'Drink water')
            restored.editor.title.setText('Water'); self.app.settings=self.app.catalog.settings=replace(self.app.settings,notification_sound='silent')
            with patch.object(self.store,'save_settings',side_effect=OSError('fixture')): restored.save()
            self.assertIn(key,restored.changes); self.assertTrue(restored.error.text())
            restored.save(); self.assertFalse(restored.changes)
            self.assertEqual(self.store.settings().scheduled_notifications[0]['title'],'Water')
            self.assertEqual(self.store.settings().notification_sound,'silent')
        finally:
            restored.hide(); restored.deleteLater(); page.changes.clear()

    def test_new_and_restored_reminders_cancel_without_changing_existing_drafts(self):
        page=self.app.notifications_page
        page.record('builtin:warning',None); page.create()
        page.editor.trigger.setCurrentIndex(page.editor.trigger.findData('warning'))
        page.cancel_edit(); self.assertEqual(page.changes,{'builtin:warning':None})
        page.create(); page.editor.trigger.setCurrentIndex(page.editor.trigger.findData('warning'))
        page.editor.trigger.setCurrentIndex(0); page.cancel_edit()
        self.assertEqual(page.changes,{'builtin:warning':None})

    def test_draft_discard_and_idle_flush_are_safe(self):
        page=self.app.notifications_page; page.create(); page.show_list()
        with patch.object(page,'ask_delete',return_value=False): page.discard_draft()
        self.assertTrue(page.changes)
        page.flush_draft(); changes=self.store.db.total_changes; page.flush_draft(); page.flush_draft()
        self.assertEqual(self.store.db.total_changes,changes)
        with patch.object(page,'ask_delete',return_value=True): page.discard_draft()
        self.assertEqual(drafts.read(self.store),{}); self.assertEqual(self.store.settings().scheduled_notifications,[])

    def test_confirmation_uses_plain_title_cancel_default_and_both_languages(self):
        page=self.app.notifications_page
        for language,title in (('hu','Értesítés törlése'),('en','Delete notification')):
            self.app.set_language(language)
            def cancel():
                window=QApplication.activeModalWidget(); self.assertEqual(window.windowTitle(),title)
                self.assertEqual(window.objectName(),'Surface')
                self.assertTrue(any('<test>' in item.text() and item.textFormat()==Qt.PlainText for item in window.findChildren(QLabel)))
                buttons=window.findChildren(QPushButton)
                self.assertEqual([button.text() for button in buttons if button.isDefault()],[self.app.t('Cancel')])
                next(button for button in buttons if button.text()==self.app.t('Cancel')).click()
            QTimer.singleShot(0,cancel); self.assertFalse(page.ask_delete('<test>'))

    def test_removed_builtins_do_not_deliver_but_other_reminders_and_limits_remain(self):
        tracker=self.app.tracker; now=datetime.now().astimezone(); day=now.date().isoformat()
        settings=replace(self.app.settings,removed_notifications=list(KINDS),bedtime_enabled=True,bedtime_warning_minute=720,bedtime_minute=780,bedtime_resume_minute=840)
        self.app.settings=self.app.catalog.settings=settings
        with patch.object(tracker,'quota_totals',return_value={'fixture':settings.limit_seconds+1}): tracker.evaluate(now)
        self.assertFalse(tracker.alerts)
        alert=Alert(day,('warning',),'warning','Old queued warning','')
        self.assertFalse(tracker.alert_current(alert,now))
        schedule=Bedtime(self.store); sample=Sample(now.replace(hour=12,minute=0,second=0),100)
        self.assertIsNone(schedule.update(settings,sample)[1])
        self.assertEqual(schedule.update(replace(settings,removed_notifications=[]),sample)[0],'warning')
        self.assertIsNotNone(schedule.update(replace(settings,removed_notifications=[]),sample)[1])
        self.assertTrue(settings.game_budget_enabled)

    def test_old_profiles_default_and_removed_selection_is_strict(self):
        for invalid in (None,'warning',['nope'],['warning','warning'],[{}]):
            with self.subTest(value=invalid),self.assertRaises(ValueError): replace(Settings(),removed_notifications=invalid).validate()
        self.assertEqual(Settings().removed_notifications,[])
