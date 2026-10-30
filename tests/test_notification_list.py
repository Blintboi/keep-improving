"""The notification list exposes existing defaults without duplicating delivery."""
from dataclasses import replace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from PySide6.QtCore import QTime
from PySide6.QtWidgets import QWidget,QPushButton
import test_qt_ui as fixture
from gametime.notification_text import KINDS,default_notification_template


class NotificationListTests(TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def field(self,window,name):
        return next(w for w in window.findChildren(QWidget) if w.accessibleName()==self.app.t(name))

    def click(self,window,name):
        next(w for w in window.findChildren(QPushButton) if w.text()==self.app.t(name)).click()

    def test_fresh_profile_has_all_builtins_without_creating_or_enabling_notifications(self):
        saved=self.store.settings(); page=self.app.notifications_page
        self.app.switch_page(6); self.assertTrue(self.app.nav[6].isChecked())
        self.assertEqual(page.row_keys,['builtin:'+kind for kind in KINDS])
        self.assertEqual(self.store.settings(),saved)
        self.assertEqual(saved.scheduled_notifications,[])
        self.assertEqual(len(page.entries()),4)
        with patch.object(page.rows,'addWidget') as rebuild:
            page.refresh(); page.refresh(); rebuild.assert_not_called()

    def test_add_edit_cancel_and_remove_custom_notification_from_its_row(self):
        page=self.app.notifications_page; self.app.switch_page(6)
        page.add_button.click(); window=page.editor
        self.field(window,'Title').setText('Igyál vizet'); self.field(window,'Message').setPlainText('Egy pohár víz, és tarts szünetet!')
        self.field(window,'Time').setTime(QTime(14,35)); self.click(window,'Save')
        self.pump(.02); item=self.store.settings().scheduled_notifications[0]; key='scheduled:'+item['id']
        self.assertIn(key,page.row_keys); self.assertEqual(item['minute'],875)
        page.edit(key); window=page.editor; self.assertEqual(self.field(window,'Title').text(),'Igyál vizet')
        self.assertTrue(self.field(window,'Scheduled notifications').isHidden())
        self.field(window,'Title').setText('Discard this'); window.reject(); self.pump(.02)
        self.assertEqual(self.store.settings().scheduled_notifications[0]['title'],'Igyál vizet')
        page.edit(key); self.field(page.editor,'Title').setText('Szünet'); self.click(page.editor,'Save'); self.pump(.02)
        self.assertEqual(next(row[1] for row in page.entries() if row[0]==key),'Szünet')
        page.edit(key); self.click(page.editor,'Delete'); self.pump(.02)
        self.assertEqual(self.store.settings().scheduled_notifications,[]); self.assertEqual(len(page.row_keys),4)

    def test_builtin_row_opens_correct_existing_template_and_keeps_schedule_and_other_messages(self):
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,notification_messages={'warning':'Existing warning'})
        self.store.save_settings(self.app.settings); before=self.app.settings
        page=self.app.notifications_page; page.edit('builtin:bedtime'); window=page.editor
        self.assertEqual(self.field(window,'Reminder type').currentData(),'bedtime')
        self.assertEqual(self.field(window,'Personal message').toPlainText(),default_notification_template(before,'bedtime'))
        self.field(window,'Personal message').setPlainText('Lefekvés {bedtime}-kor.'); self.click(window,'Save'); self.pump(.02)
        saved=self.store.settings(); self.assertEqual(saved.notification_messages,{'warning':'Existing warning','bedtime':'Lefekvés {bedtime}-kor.'})
        self.assertEqual(saved.bedtime_enabled,before.bedtime_enabled); self.assertEqual(saved.bedtime_warning_minute,before.bedtime_warning_minute)
        self.assertEqual(saved.scheduled_notifications,[]); self.assertEqual(len(page.row_keys),4)

    def test_list_layout_language_and_settings_return(self):
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,scheduled_notifications=[
            dict(id='a'*32,title='Szünet és víz',text='Állj fel egy percre, és igyál egy pohár vizet.',icon='',minute=870,enabled=True),
            dict(id='b'*32,title='Hosszabb egyéni emlékeztető címe '*2,text='Második üzenet '*40,icon='',minute=1020,enabled=False)])
        page=self.app.notifications_page; self.app.resize(1020,740); self.app.show(); self.app.switch_page(6); self.pump(.08)
        self.assertEqual(page.scroll.horizontalScrollBar().maximum(),0)
        Path('test-reports').mkdir(exist_ok=True); self.app.grab().save('test-reports/notification-list-hu.png')
        self.app.open_settings_section('reminders'); self.app.cancel_general_settings()
        self.assertEqual(self.app.pages.currentIndex(),6); self.assertTrue(self.app.nav[6].isChecked())
        self.app.set_language('en'); self.assertEqual(self.app.nav[6].text(),'Notifications')
        self.assertEqual(page.add_button.text(),'Add notification'); self.assertEqual(len(page.row_keys),6)
        self.assertEqual(next(row[1] for row in page.entries() if row[0]=='scheduled:'+'a'*32),'Szünet és víz')

    def test_disabled_and_weekday_builtins_reflect_saved_settings(self):
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,game_budget_enabled=False,bedtime_enabled=False,
            daily_schedules={'0':{'bedtime_enabled':True,'bedtime_warning_minute':1320}})
        entries={row[0]:row for row in self.app.notifications_page.entries()}
        self.assertIn(self.app.t('Disabled'),entries['builtin:limit'][2])
        self.assertIn(self.app.t('Enabled'),entries['builtin:bedtime'][2])
        self.assertIn(self.app.t('Varies by day'),entries['builtin:bedtime'][2])
