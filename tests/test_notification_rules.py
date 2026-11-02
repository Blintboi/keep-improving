"""Configurable triggers, delivery receipts, local actions and lifetimes."""
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from gametime.model import Settings
from gametime.store import Store
from gametime.focus import Focus
from gametime.tracker import Alert,Sample
from gametime.notification_rules import POMODORO,normalized,validate_item,validate_action
from gametime.scheduled_notifications import tick,initialize_startup
from gametime import notification_drafts as drafts
import test_qt_ui as fixture


def rule(**changes):
    return normalized(dict(id='a'*32,title='Reminder',text='Message',icon='preset:focus',minute=720,enabled=True)|changes)


class TriggerTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'test.sqlite3'); self.addCleanup(self.store.close)
        self.focus=Focus(self.store); self.now=datetime(2026,11,2,12,0).astimezone()
        self.app=SimpleNamespace(settings=Settings(),store=self.store,focus=self.focus,popup_window=None,
            notification_mode=Mock(return_value='normal'),popup=Mock(return_value=True))
    def sample(self,when=None,interactive=True): return Sample(when or self.now,100,interactive=interactive)
    def install(self,item):
        self.app.settings=replace(self.app.settings,scheduled_notifications=[item]); initialize_startup(self.app)

    def test_startup_once_per_process_not_save_or_day_and_retries_until_visible(self):
        self.install(rule(trigger='startup',timeout=0))
        tick(self.app,self.sample(interactive=False)); self.app.popup.assert_not_called()
        self.app.notification_mode.return_value='audio'; self.app.fullscreen_scheduled_notification=Mock(return_value=True)
        tick(self.app,self.sample()); self.app.fullscreen_scheduled_notification.assert_not_called()
        self.app.notification_mode.return_value='normal'; self.app.popup.return_value=False
        tick(self.app,self.sample()); self.assertEqual(len(self.app._scheduled_pending),1)
        self.app.popup.return_value=True; tick(self.app,self.sample()); tick(self.app,self.sample())
        self.assertEqual(self.app.popup.call_count,2); self.assertFalse(self.store.alert_keys(self.now.date()))
        self.app.settings=replace(self.app.settings,scheduled_notifications=[rule(trigger='startup',text='New text')])
        tick(self.app,self.sample(self.now+timedelta(days=1))); self.assertEqual(self.app.popup.call_count,2)
        initialize_startup(self.app); tick(self.app,self.sample()); self.assertEqual(self.app.popup.call_count,3)
        initialize_startup(self.app); self.app.settings=replace(self.app.settings,scheduled_notifications=[dict(rule(trigger='startup'),id='b'*32)])
        tick(self.app,self.sample()); self.assertEqual(self.app.popup.call_count,3)

    def test_pomodoro_goal_global_day_receipt_persists_and_cached_round_count(self):
        self.app.settings=replace(self.app.settings,budget_reset_minute=240); self.focus.configure_day_start(240)
        self.install(rule(trigger='pomodoros',count=2))
        self.now=self.now.replace(hour=3)
        tick(self.app,self.sample()); self.app.popup.assert_not_called()
        self.focus.start(0); self.focus.advance(1500,self.now)
        tick(self.app,self.sample()); self.app.popup.assert_not_called()
        self.focus.stop(); self.focus.start(1500); self.focus.advance(3000,self.now)
        tick(self.app,self.sample()); self.app.popup.assert_called_once()
        self.assertEqual(self.focus.completed_on('2026-11-01'),2)
        queries=[]; self.store.db.set_trace_callback(queries.append)
        for _ in range(10): tick(self.app,self.sample())
        self.store.db.set_trace_callback(None)
        self.assertFalse(any('focus_completions' in q for q in queries))
        self.app._scheduled_day=None; self.app.focus=Focus(self.store)
        tick(self.app,self.sample()); self.app.popup.assert_called_once()
        tick(self.app,self.sample(self.now.replace(hour=4))); self.app.popup.assert_called_once()
        self.assertEqual(self.app.focus.completed_on('2026-11-02'),0)

    def test_pending_edit_disable_or_delete_never_delivers_stale_rule(self):
        self.install(rule(trigger='time')); tick(self.app,self.sample(interactive=False))
        self.app.settings=replace(self.app.settings,scheduled_notifications=[dict(rule(),enabled=False)])
        tick(self.app,self.sample()); self.assertFalse(self.app._scheduled_pending); self.app.popup.assert_not_called()
        self.install(rule()); tick(self.app,self.sample(interactive=False))
        self.app.settings=replace(self.app.settings,scheduled_notifications=[])
        tick(self.app,self.sample()); self.assertFalse(self.app._scheduled_pending)

    def test_validation_and_legacy_fields_round_trip(self):
        for changes in ({'trigger':[]},{'template':{}},{'timeout':-1},{'timeout':True},{'timeout':3601},{'count':0},{'count':1.5},
                        {'icon':'preset:missing'},{'action':{'kind':'shell','path':'anything'}},{'action':{'kind':'pomodoro',**POMODORO,'work':0}}):
            with self.subTest(changes=changes),self.assertRaises(ValueError): validate_item(rule(**changes))
        for path in ('https://example.com/x.exe',r'\\server\x.exe','cmd.exe',r'C:\x.cmd',r'C:\x.exe --arg'):
            with self.subTest(path=path),self.assertRaises(ValueError): validate_action({'kind':'app','path':path})
        for timeout in (None,0,1,3600): validate_item(rule(timeout=timeout))
        item=rule(action={'kind':'pomodoro',**POMODORO},timeout=0,trigger='pomodoros',count=3)
        self.store.save_settings(replace(Settings(),scheduled_notifications=[item])); self.assertEqual(self.store.settings().scheduled_notifications,[item])
        legacy={key:item[key] for key in ('id','title','text','icon','minute','enabled')}
        self.store.save_settings(replace(Settings(),scheduled_notifications=[legacy])); self.assertEqual(self.store.settings().scheduled_notifications,[legacy])

    def test_override_suppresses_legacy_and_drafts_recover_incomplete_app(self):
        item=drafts.original(Settings(),'builtin:warning'); item.update(trigger='startup',timeout=0,icon='preset:water')
        saved=drafts.apply(Settings(),{'builtin:warning':item}).validate()
        self.assertIn('warning',saved.removed_notifications); self.assertEqual(drafts.original(saved,'builtin:warning'),item)
        incomplete=dict(item,action={'kind':'app','path':''})
        drafts.write(self.store,{'builtin:warning':incomplete}); self.assertEqual(drafts.read(self.store),{'builtin:warning':incomplete})
        drafts.write(self.store,{'builtin:warning':dict(item,action={'kind':'invalid'})}); self.assertEqual(drafts.read(self.store),{})
        deleted=drafts.apply(saved,{'builtin:warning':None}).validate(); self.assertIsNone(drafts.original(deleted,'builtin:warning'))


class NotificationInterfaceTests(TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp; tearDown=fixture.QtInterfaceTests.tearDown; pump=fixture.QtInterfaceTests.pump

    def popup(self,**changes):
        alert=Alert(datetime.now().date().isoformat(),(),'scheduled','Message','',title='Reminder',sound=False,**changes)
        with patch.object(self.app,'notification_mode',return_value='normal'),patch('gametime.win32.u.SetForegroundWindow') as focus:
            self.assertTrue(self.app.popup(alert)); focus.assert_not_called()
        return self.app.popup_window

    def test_editor_all_fields_persist_without_types_cancel_and_recover(self):
        page=self.app.notifications_page; page.create(); editor=page.editor; key=editor.key
        editor.title.setText('Daily goal'); editor.message.setPlainText('Take a break')
        editor.trigger.setCurrentIndex(editor.trigger.findData('pomodoros')); editor.count.setValue(4)
        editor.icons.select('preset:water'); editor.action.setCurrentIndex(editor.action.findData('pomodoro'))
        editor.pomodoro.inputs['work'].setValue(50); editor.auto_close.setChecked(False); page.show_list()
        restored=drafts.read(self.store)[key]; self.assertEqual(restored['count'],4); self.assertEqual(restored['timeout'],0)
        page.edit(key); self.assertEqual(editor.pomodoro.value()['work'],50); self.assertEqual(editor.trigger.currentData(),'pomodoros')
        editor.count.setValue(5); page.cancel_edit(); self.assertEqual(page.changes[key]['count'],4)
        page.save(); saved=self.store.settings().scheduled_notifications[0]
        self.assertEqual(saved['icon'],'preset:water'); self.assertEqual(saved['action']['work'],50)
        page.edit('builtin:warning'); editor.trigger.setCurrentIndex(editor.trigger.findData('startup')); editor.auto_close.setChecked(False); page.save()
        self.assertEqual(self.store.settings().notification_overrides['warning']['trigger'],'startup')
        self.assertIn('builtin:warning',page.row_keys)

    def test_launch_requires_click_uses_literal_path_and_only_once(self):
        with patch('gametime.qt_notification_options.subprocess.Popen') as launch:
            window=self.popup(action={'kind':'app','path':str(self.exe)},timeout=0)
            launch.assert_not_called(); self.assertFalse(window.close_timer.isActive())
            window.action_button.click(); launch.assert_called_once_with([str(self.exe)],cwd=str(self.exe.parent),shell=False)
            window.action_button.click(); launch.assert_called_once(); self.assertTrue(window.isVisible())
            self.assertFalse(window.action_button.isEnabled()); window.close()
            window=self.popup(action={'kind':'app','path':str(self.base/'missing.exe')},timeout=0)
            window.action_button.click(); self.assertTrue(window.action_button.isEnabled()); launch.assert_called_once()
            self.assertEqual(window.action_status.text(),self.app.t('Application file was not found.'))

    def test_popup_pomodoro_edit_and_start_preserve_blacklist_and_running_timer(self):
        from PySide6.QtCore import Qt
        before=replace(self.app.focus.settings,block_apps=[str(self.exe)])
        self.app.focus.configure(before)
        window=self.popup(action={'kind':'pomodoro',**POMODORO},timeout=15)
        self.assertTrue(window.close_timer.isActive()); self.assertEqual(window.close_timer.interval(),15000)
        self.assertFalse(window.windowFlags()&Qt.WindowDoesNotAcceptFocus)
        self.assertTrue(window.testAttribute(Qt.WA_ShowWithoutActivating))
        for key,value in {'work':45,'short_break':8,'long_break':20,'rounds':3}.items(): window.pomodoro_fields.inputs[key].setValue(value)
        self.assertFalse(window.close_timer.isActive()); window.action_button.click()
        self.assertTrue(self.app.focus.running); self.assertEqual(self.app.focus.remaining,45*60)
        self.assertEqual(self.app.focus.settings.block_apps,before.block_apps); self.assertEqual(self.app.focus.settings.rounds,3)
        self.assertFalse(window.action_button.isEnabled()); window.close()
        window=self.popup(action={'kind':'pomodoro',**POMODORO},timeout=0); window.action_button.click()
        self.assertTrue(window.action_button.isEnabled()); self.assertEqual(self.app.focus.settings.work,45)
        self.assertEqual(self.app.focus.completed_rounds,0)

    def test_manual_popup_survives_global_day_rollover_and_bedtime(self):
        window=self.popup(timeout=0); self.app.popup_day='2000-01-01'
        settings=replace(self.app.settings,bedtime_enabled=True,bedtime_warning_minute=720,bedtime_minute=780,bedtime_resume_minute=840)
        self.app.settings=self.app.catalog.settings=settings
        current=Sample(datetime.now().astimezone().replace(hour=12,minute=0,second=0),100)
        with patch('gametime.controller.win32.sample',return_value=current): self.app.tick()
        self.app.tick_timer.stop(); self.assertIs(self.app.popup_window,window); self.assertTrue(window.isVisible()); self.assertFalse(window.close_timer.isActive())

    def test_explicit_seconds_close_and_interactive_notifications_defer_fullscreen(self):
        window=self.popup(timeout=1); self.pump(1.2); self.assertIsNone(self.app.popup_window)
        alert=Alert(datetime.now().date().isoformat(),(),'scheduled','Message','',title='Reminder',timeout=0)
        with patch.object(self.app,'notification_mode',return_value='audio'),patch.object(self.app,'audio_notification') as audio:
            self.assertFalse(self.app.popup(alert)); audio.assert_not_called()
