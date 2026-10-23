"""Personal text and colors must not alter timing, isolation or delivery policy."""
from dataclasses import replace
from datetime import date,datetime
from contextlib import closing
from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from gametime.model import Settings,Catalog,Game
from gametime.notification_text import KINDS,notification_text,default_notification_template
from gametime.store import Store
from gametime.tracker import Tracker,Sample
import test_qt_ui as fixtures


class PersonalReminderTests(unittest.TestCase):
    def test_validation_rejects_bad_messages_and_colors(self):
        for messages in (None,[],{'unknown':'hello'},{'warning':5},{'warning':'x'*1001},{'limit':'bad\0text'}):
            with self.subTest(messages=messages),self.assertRaises(ValueError): replace(Settings(),notification_messages=messages).validate()
        for color in (None,123,'red','#abc','#12345678','<C=FFFFFFFF>'):
            for field in ('overlay_color_normal','overlay_color_warning'):
                with self.subTest(color=color,field=field),self.assertRaises(ValueError): replace(Settings(),**{field:color}).validate()
        replace(Settings(),notification_messages={'warning':'é🙂\n'*300},overlay_color_normal='#ABCd12').validate()

    def test_tokens_are_bounded_literal_substitutions_and_user_text_never_translates(self):
        text='Settings <b>tanulás</b>\n{remaining}/{minutes} {time} → {bedtime}; {unknown} {obj.__class__} {'
        settings=replace(Settings(),notification_messages={'warning':text})
        expected='Settings <b>tanulás</b>\n17/120 23:55 → 00:00; {unknown} {obj.__class__} {'
        for language in ('hu','en'):
            self.assertEqual(notification_text(replace(settings,language=language),'warning',17),expected)
        self.assertIn('minutes',notification_text(Settings(),'warning'))
        self.assertIn('20 perc',notification_text(replace(Settings(),language='hu'),'warning'))
        self.assertEqual(notification_text(Settings(),'limit'),'Your daily 2-hour game time limit has been reached. Time to finish playing.')
        self.assertIn('90-minute',notification_text(replace(Settings(),limit_seconds=5400,warning_seconds=3600),'limit'))
        self.assertIn('Test:',notification_text(Settings(),'limit',test=True))
        self.assertNotIn('Test:',notification_text(replace(Settings(),notification_messages={'limit':'Egyéni'}),'limit',test=True))
        for kind in ('limit','session'):
            self.assertEqual(notification_text(replace(Settings(),notification_messages={kind:'{remaining}'}),kind),'0')

    def test_editable_defaults_keep_live_time_tokens(self):
        for language in ('en','hu'):
            for minutes in (90,120,150.5):
                settings=replace(Settings(),language=language,limit_seconds=minutes*60,warning_seconds=3600)
                for kind in KINDS:
                    with self.subTest(language=language,minutes=minutes,kind=kind):
                        template=default_notification_template(settings,kind)
                        personal=replace(settings,notification_messages={kind:template+' Extra.'})
                        self.assertEqual(notification_text(personal,kind,17),notification_text(settings,kind,17)+' Extra.')

    def test_old_profile_defaults_and_new_preferences_survive_without_history_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'usage.sqlite3'; store=Store(path)
            with store.db: store.db.execute("INSERT INTO settings VALUES ('config',?)",(json.dumps({'games_root':str(Path(tmp)/'Games')}),))
            settings=store.settings(); self.assertEqual(settings.notification_messages,{})
            self.assertEqual((settings.overlay_color_normal,settings.overlay_color_warning),('#ffffff','#ff5c65'))
            store.add_usage({('2026-10-23','fixture'):120}); store.set_enabled('fixture',False); store.set_hidden('fixture',True)
            settings=replace(settings,notification_messages={'bedtime':'Most pihenj! {bedtime}'},overlay_color_normal='#12ab34',overlay_color_warning='#bc56ef')
            store.save_settings(settings); store.close(); reader=Store(path)
            try:
                self.assertEqual(reader.settings(),settings); self.assertEqual(reader.totals('2026-10-23'),{'fixture':120})
                self.assertFalse(reader.overrides()['fixture']); self.assertIn('fixture',reader.hidden_ids())
                from gametime.statistics_sync import StatisticsData
                snapshot=json.dumps(StatisticsData(reader).snapshot('b'*32,'Fixture'))
                self.assertNotIn('Most pihenj!',snapshot); self.assertNotIn('notification_messages',snapshot); self.assertNotIn('#12ab34',snapshot)
            finally: reader.close()

    def test_custom_tracker_messages_keep_thresholds_keys_and_later_session_delivery(self):
        with tempfile.TemporaryDirectory() as tmp,closing(Store(Path(tmp)/'usage.sqlite3')) as store:
            settings=replace(Settings(),notification_messages={'warning':'Még {remaining} perc.','limit':'Vége: {minutes}.','session':'Ma már játszottál.'})
            tracker=Tracker(store,Catalog(settings)); day=date.today().isoformat(); now=datetime.now()
            tracker.cache[day]={'fixture':5999}; tracker.evaluate(now); self.assertFalse(tracker.alerts)
            tracker.cache[day]={'fixture':6000}; tracker.evaluate(now); alert=tracker.alerts.popleft()
            self.assertEqual((alert.kind,alert.text,alert.keys),('warning','Még 20 perc.',('warning:6000',)))
            tracker.delivered(alert); tracker.cache[day]={'fixture':7200}; tracker.evaluate(now); alert=tracker.alerts.popleft()
            self.assertEqual((alert.kind,alert.text),('limit','Vége: 120.')); tracker.delivered(alert)
            tracker.identity='fixture:2'; tracker.evaluate(now); alert=tracker.alerts.popleft()
            self.assertEqual((alert.kind,alert.text),('session','Ma már játszottál.'))
            self.assertEqual(alert.keys,('session:7200:fixture:2',)); self.assertEqual(store.totals(day),{})

    @unittest.skipUnless(os.name=='nt','Windows RTSS module required')
    def test_rtss_colors_match_custom_states_and_keep_opacity_and_font(self):
        from gametime.rtss import countdown
        self.assertIn('<C=8012AB34>',countdown(1200,False,.5,36,'#12ab34','#bc56ef'))
        text=countdown(1200,True,1,36,'#12ab34','#bc56ef')
        self.assertIn('<C=FFBC56EF>',text); self.assertIn('<FNT=Consolas,-48,700,1>',text); self.assertIn('00:20:00',text)
        with self.assertRaises(ValueError): countdown(1200,True,1,25,'#ffffff','<C=FFFFFFFF>')


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class PersonalReminderInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.QtInterfaceTests.setUpClass.__func__)
    setUp=fixtures.QtInterfaceTests.setUp
    tearDown=fixtures.QtInterfaceTests.tearDown
    pump=fixtures.QtInterfaceTests.pump

    def editor(self):
        from PySide6.QtWidgets import QPlainTextEdit,QComboBox
        self.app.custom_messages_dialog(); window=self.app._dialogs[-1]
        return window,window.findChild(QPlainTextEdit),window.findChild(QComboBox)

    def click(self,window,key):
        from PySide6.QtWidgets import QPushButton
        next(item for item in window.findChildren(QPushButton) if item.text()==self.app.t(key)).click()

    def test_message_drafts_preview_language_save_and_failure_preserve_other_settings(self):
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import Qt
        from sqlite3 import OperationalError
        self.app.limit.setValue(155); window,editor,kinds=self.editor()
        raw='Settings <b>szünet</b>\nMég {remaining} perc. {unknown}'
        editor.setPlainText(raw); kinds.setCurrentIndex(kinds.findData('bedtime')); editor.setPlainText('Alvás {bedtime}')
        kinds.setCurrentIndex(kinds.findData('warning')); self.assertEqual(editor.toPlainText(),raw)
        editor.selectAll(); self.app.set_language('en')
        self.assertEqual(editor.toPlainText(),raw); self.assertEqual(editor.textCursor().selectedText().replace('\u2029','\n'),raw)
        self.assertEqual(window.windowTitle(),'Custom messages')
        with patch('gametime.controller.win32.escape_game') as escape,patch('gametime.controller.win32.minimize_foreground') as minimize:
            self.click(window,'Preview message'); self.pump(.03)
            labels=self.app.popup_window.findChildren(QLabel)
            body=next(item for item in labels if 'Settings <b>' in item.text())
            self.assertEqual(body.text(),'Settings <b>szünet</b>\nMég 20 perc. {unknown}'); self.assertEqual(body.textFormat(),Qt.PlainText)
            escape.assert_not_called(); minimize.assert_not_called()
        self.assertEqual(self.store.alert_keys(date.today().isoformat()),set()); self.assertEqual(self.store.totals(date.today()),{})
        self.assertEqual(self.store.settings().notification_messages,{}); self.app.dismiss_popup()
        before=self.app.settings
        with patch.object(self.store,'save_settings',side_effect=OperationalError('fixture')): self.click(window,'Save')
        self.assertEqual(self.app.settings,before); self.assertTrue(window.isVisible())
        self.click(window,'Save'); self.assertEqual(self.store.settings().notification_messages,{'warning':raw,'bedtime':'Alvás {bedtime}'})
        self.assertEqual(self.app.limit.value(),155); self.assertEqual(self.store.settings().limit_seconds,7200)
        self.app.test_bedtime_popup(); self.pump(.02)
        self.assertTrue(any(item.text()=='Alvás 00:00' for item in self.app.popup_window.findChildren(QLabel))); self.app.dismiss_popup()
        self.app.settings=replace(self.app.settings,notification_messages={'bedtime':'Még {remaining} perc játék.'})
        self.app.tracker.cache[date.today().isoformat()]={self.games[0].id:6000}
        self.app.test_bedtime_popup(); self.pump(.02)
        self.assertTrue(any(item.text()=='Még 20 perc játék.' for item in self.app.popup_window.findChildren(QLabel))); self.app.dismiss_popup()

    def test_cancel_defaults_limits_and_long_multiline_message_remain_readable(self):
        from PySide6.QtWidgets import QScrollArea,QLabel
        window,editor,kinds=self.editor(); editor.setPlainText('x'*1001)
        self.click(window,'Save'); self.assertTrue(window.isVisible()); self.assertEqual(self.store.settings().notification_messages,{})
        text=('Ez egy személyes üzenet.\n'*40)[:1000]; editor.setPlainText(text)
        self.click(window,'Preview message'); self.pump(.05)
        self.assertTrue(any(item.text()==text for item in self.app.popup_window.findChildren(QLabel)))
        self.assertGreater(self.app.popup_window.findChild(QScrollArea).verticalScrollBar().maximum(),0)
        self.app.dismiss_popup(); self.click(window,'Cancel'); self.assertEqual(self.store.settings().notification_messages,{})
        window,editor,kinds=self.editor(); editor.setPlainText('Egyéni'); self.click(window,'Use default message')
        self.assertEqual(editor.toPlainText(),default_notification_template(self.app.settings,'warning')); self.click(window,'Preview message'); self.pump(.02)
        self.assertTrue(any('20 perc' in item.text() for item in self.app.popup_window.findChildren(QLabel)))
        self.app.dismiss_popup(); self.click(window,'Save'); self.assertEqual(self.store.settings().notification_messages,{})

    def test_prefilled_defaults_translate_without_saving_untouched_messages(self):
        window,editor,kinds=self.editor()
        for kind in KINDS:
            kinds.setCurrentIndex(kinds.findData(kind))
            self.assertEqual(editor.toPlainText(),default_notification_template(self.app.settings,kind))
            self.assertTrue(editor.toPlainText())
        self.app.set_language('en')
        self.assertEqual(editor.toPlainText(),default_notification_template(self.app.settings,'bedtime'))
        self.click(window,'Save'); self.assertEqual(self.store.settings().notification_messages,{})
        window,editor,kinds=self.editor(); custom=editor.toPlainText()+' Have fun!'; editor.setPlainText(custom)
        kinds.setCurrentIndex(kinds.findData('bedtime')); self.app.set_language('hu')
        self.assertEqual(editor.toPlainText(),default_notification_template(self.app.settings,'bedtime'))
        kinds.setCurrentIndex(kinds.findData('warning')); self.assertEqual(editor.toPlainText(),custom)
        self.click(window,'Save'); self.assertEqual(self.store.settings().notification_messages,{'warning':custom})
        self.assertIn('17 minutes',notification_text(self.store.settings(),'warning',17))

    def test_both_countdown_colors_preview_pixels_translation_and_save(self):
        from PySide6.QtGui import QColor
        self.app.overlay_enabled.setChecked(True)
        for kind,color in (('normal','#12ab34'),('warning','#bc56ef')):
            with patch('gametime.qt_ui.QColorDialog.getColor',return_value=QColor(color)): self.app.choose_overlay_color(kind)
        before=dict(self.app.overlay_colors)
        with patch('gametime.qt_ui.QColorDialog.getColor',return_value=QColor()): self.app.choose_overlay_color('normal')
        self.assertEqual(self.app.overlay_colors,before)
        for kind,color in before.items():
            self.app.overlay_preview_state.setCurrentIndex(self.app.overlay_preview_state.findData(kind)); self.app.preview_overlay(); self.pump(.02)
            image=self.app.overlay.grab().toImage()
            pixel=max((image.pixelColor(x,y) for y in range(image.height()) for x in range(image.width())),key=lambda value:value.alpha())
            expected=QColor(color)
            for channel in ('red','green','blue'): self.assertLessEqual(abs(getattr(pixel,channel)()-getattr(expected,channel)()),2)
        self.assertEqual(self.store.settings().overlay_color_normal,'#ffffff')
        icons={kind:item.icon().cacheKey() for kind,item in self.app.overlay_color_buttons.items()}
        self.app.set_language('en'); self.assertEqual(self.app.overlay_colors,before)
        self.assertEqual(icons,{kind:item.icon().cacheKey() for kind,item in self.app.overlay_color_buttons.items()})
        self.app.save_settings(); saved=self.store.settings()
        self.assertEqual((saved.overlay_color_normal,saved.overlay_color_warning),('#12ab34','#bc56ef'))
        self.assertEqual(saved.limit_seconds,7200); self.assertEqual(self.store.totals(date.today()),{})
        self.app.reset_overlay_colors(); self.assertEqual(self.app.overlay_colors,{'normal':'#ffffff','warning':'#ff5c65'})
        self.assertEqual(self.store.settings().overlay_color_normal,'#12ab34')

    def test_saved_colors_reach_rtss_for_both_states(self):
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_enabled=True,overlay_rtss_auto=True,overlay_color_normal='#12ab34',overlay_color_warning='#bc56ef')
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'fixture:1'); self.app.tracker.active=self.games[0]; self.app.tracker.identity=current.identity
        for total,color in ((10,'12AB34'),(6000,'BC56EF')):
            self.app.tracker.cache[current.wall.date().isoformat()]={self.games[0].id:total}
            with patch.object(self.app,'rtss_available',return_value=True),patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app.rtss,'present',return_value=True) as present:
                self.app.update_overlay(); self.assertIn(color,present.call_args.args[2])
