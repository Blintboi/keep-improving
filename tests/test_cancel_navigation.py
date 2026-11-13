"""Budget back preserves drafts; general settings and dialogs retain cancellation."""
from dataclasses import replace
from unittest.mock import patch
import unittest
from PySide6.QtWidgets import QPushButton,QWidget
import test_qt_ui as fixture
from gametime.qt_budgets import new_rule
from gametime.wellbeing import target


class CancelNavigationTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def back(self,window):
        buttons=[button for button in window.findChildren(QPushButton) if button.accessibleName()==self.app.t('Back without saving') and not button.text()]
        self.assertTrue(buttons); self.assertFalse(buttons[0].autoDefault()); buttons[0].click(); self.pump(.02)

    def test_global_settings_only_in_sidebar_and_linking_stays_on_statistics(self):
        app=self.app; app.show()
        for language in ('hu','en'):
            app.set_language(language)
            for index in (0,1,4,5,6):
                app.switch_page(index); self.pump(.02)
                controls=app.pages.currentWidget().findChildren(QPushButton)
                self.assertFalse(any(w.property('settingsContext') for w in controls))
                self.assertFalse(any(w.isVisible() and w.text()==app.t('Game folders') for w in controls))
            app.switch_page(1); app.statistics.computers_button.click()
            self.assertTrue(app.statistics.computer_panel.isVisible())
            self.assertTrue(any(w.isVisible() and w.text()==app.t('Link computers') for w in app.statistics.findChildren(QPushButton)))
            app.statistics.computers_button.click()
            app.nav[2].click(); self.pump(.02); self.assertTrue(app.global_day_start.isVisible())
            self.assertTrue(app.activity_tracking.isVisible())
            self.assertFalse(any(w.text()==app.t('Link computers') for w in app.settings_page.findChildren(QPushButton)))
            app.show_settings_section('reminders'); self.assertTrue(app.display_settings.isVisible())
            self.assertEqual(app.display_settings.parentWidget(),app.settings_sections['reminders'])
            app.show_settings_section('games'); self.assertTrue(app.games_path.isVisible())
            app.settings_back.click(); self.assertEqual(app.pages.currentIndex(),1)

    def test_exclusive_fullscreen_does_not_mark_invisible_notification_delivered(self):
        from gametime.tracker import Sample,Alert
        from datetime import datetime
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'fixture:1')
        with patch('gametime.controller.win32.sample',return_value=current),patch('gametime.controller.win32.desktop_overlay_available',return_value=False):
            self.assertEqual(self.app.notification_mode(),'defer')
            self.assertFalse(self.app.popup(Alert(current.wall.date().isoformat(),(),'warning','test','OK')))
            self.assertIsNone(self.app.popup_window)

    def test_general_back_discards_all_general_fields_and_preserves_budget_draft(self):
        app=self.app; saved=self.store.settings()
        app.open_budget(member=target('site','example.com')); app.budget_editor.minutes.setValue(25)
        app.switch_page(2); app.games_path.setText(str(self.base/'unsaved'))
        app.paths['steam'].setText('invalid draft'); app.hub_enabled.setChecked(not saved.hub_enabled)
        app.overlay_warning.setChecked(not saved.overlay_replace_warning); app.limit_popup.setChecked(not saved.limit_popup_enabled)
        app.updates.automatic.setChecked(not saved.check_updates)
        sound=next(w for w in app.settings_page.findChildren(QWidget) if w.accessibleName()==app.t('Notification sound'))
        sound.setCurrentIndex(sound.findData('silent'))
        with patch.object(self.store,'save_settings',wraps=self.store.save_settings) as save:
            app.settings_back.click(); save.assert_not_called()
        self.assertEqual(app.pages.currentIndex(),5); self.assertEqual(self.store.settings(),saved)
        self.assertEqual(app.budget_editor.minutes.value(),25)
        self.assertEqual(app.games_path.text(),saved.games_root); self.assertEqual(app.paths['steam'].text(),';'.join(saved.steam_roots))
        self.assertEqual(app.sound_values()['notification_sound'],saved.notification_sound)
        app.save_settings(scope='general'); self.assertEqual(self.store.settings(),saved)
        app.save_budgets(); self.assertEqual(self.store.settings().wellbeing_rules[0]['seconds'],1500)

    def test_back_preserves_even_invalid_new_budget_without_applying_it(self):
        app=self.app; saved=self.store.settings(); app.open_budget(); editor=app.budget_editor
        editor.create_new(); key=editor.current; editor.name.setText(''); app.save_budgets()
        self.assertTrue(app.budget_error.text())
        editor.back_button.click()
        self.assertEqual(editor.views.currentIndex(),0); self.assertIn(key,editor.row_keys)
        self.assertEqual(editor.rule(key)['name'],'')
        app.save_budgets(); self.assertEqual(self.store.settings(),saved)

    def test_cancel_existing_budget_reverts_members_name_and_limit_only_for_that_budget(self):
        app=self.app; editor=app.budget_editor
        rules=[new_rule(name,[target('site',name+'.com')],name) for name in ('one','two')]
        settings=replace(app.settings,wellbeing_rules=rules); self.store.save_settings(settings); app.settings=app.catalog.settings=settings; editor.saved(settings)
        app.open_budget(); editor.show_editor('one'); editor.minutes.setValue(25); editor.show_list()
        editor.show_editor('two'); editor.name.setText('Renamed'); editor.replace_members(editor.rule('two'),[target('site','changed.com')])
        editor.minutes.setValue(30); editor.name.setText(''); app.budget_back.click()
        self.assertEqual(editor.rule('two')['name'],''); self.assertEqual(editor.rule('one')['seconds'],1500)
        self.assertEqual(self.store.settings(),settings)
        editor.show_editor('two'); editor.cancel_edit()
        app.save_budgets(); self.assertEqual(self.store.settings().wellbeing_rules[1],rules[1])
        self.assertEqual(self.store.settings().wellbeing_rules[0]['seconds'],1500)

    def test_shared_schedule_and_new_game_budget_cancel_without_touching_general_draft(self):
        app=self.app; saved=self.store.settings(); app.games_path.setText(str(self.base/'pending'))
        app.open_budget(); app.budget_editor.show_editor('shared-games'); app.limit.setValue(97)
        app.schedule_editor.restriction_enabled.setChecked(True); app.budget_back.click()
        self.assertEqual(app.schedule_editor.settings(saved).limit_seconds,97*60)
        app.open_budget(member=target('game',self.games[0].id)); app.budget_editor.minutes.setValue(33)
        app.budget_back.click(); self.assertEqual(app.budget_editor.game_limits[self.games[0].id],33*60)
        self.assertIn(self.games[0].id,app.budget_editor.draft_games)
        self.assertEqual(app.games_path.text(),str(self.base/'pending'))
        self.assertEqual(self.store.settings(),saved)

    def test_list_cancel_discards_all_budget_drafts_and_returns_without_navigation_loop(self):
        app=self.app; saved=self.store.settings(); app.switch_page(0); app.switch_page(2)
        app.open_budget(member=target('site','example.com')); app.budget_editor.minutes.setValue(25); app.budget_editor.show_list()
        app.budget_back.click(); self.assertEqual(app.pages.currentIndex(),2)
        self.assertEqual(app.budget_editor.rules[0]['seconds'],1500)
        app.settings_back.click(); self.assertEqual(app.pages.currentIndex(),0)
        self.assertEqual(self.store.settings(),saved)

    def test_top_back_on_countdown_messages_and_focus_editors_never_saves(self):
        app=self.app; saved=self.store.settings(); focus=replace(app.focus.settings)
        cases=((lambda:app.game_countdown_dialog(self.games[0].id),'Text size',lambda field:field.setValue(38)),
               (app.custom_messages_dialog,'Personal message',lambda field:field.setPlainText('Unsaved message')),
               (app.focus_page.timer_settings,'Focus minutes',lambda field:field.setValue(42)),
               (app.focus_page.rules_dialog,'Blocked websites',lambda field:field.setPlainText('invalid entry')))
        for open_editor,field_name,edit in cases:
            open_editor(); window=app._dialogs[-1]; self.pump(.02)
            field=next(w for w in window.findChildren(QWidget) if w.accessibleName()==app.t(field_name)); edit(field)
            self.back(window); self.assertNotIn(window,app._dialogs)
            self.assertEqual(self.store.settings(),saved); self.assertEqual(app.focus.settings,focus)

    def test_browser_help_has_back_and_budget_footer_stays_visible_when_scrolled(self):
        app=self.app; app.resize(1020,740); app.open_budget(); app.budget_editor.show_editor('shared-games')
        for section in app.schedule_editor.details.values(): section.setExpanded(True)
        app.schedule_editor.day_details.setExpanded(True); self.pump(.03)
        app.budget_scroll.verticalScrollBar().setValue(app.budget_scroll.verticalScrollBar().maximum()); self.pump(.02)
        self.assertTrue(app.budget_back.isVisible()); self.assertTrue(app.budget_back.isEnabled())
        app.budget_back.click(); self.assertEqual(app.budget_editor.views.currentIndex(),0)
        with patch.object(app,'enable_browser_bridge',return_value=None): app.focus_page.browser_dialog()
        window=app._dialogs[-1]
        next(b for b in window.findChildren(QPushButton) if b.text()==app.t('Back')).click()
        self.assertNotIn(window,app._dialogs)

    def test_page_back_controls_stay_in_top_left_and_budget_editor_has_one(self):
        from PySide6.QtCore import QPoint
        app=self.app; app.show(); app.switch_page(2); self.pump(.02)
        self.assertIs(app.settings_page.layout().itemAt(0).layout().itemAt(0).widget(),app.settings_back)
        point=app.settings_back.mapTo(app.settings_page,QPoint(0,0))
        self.assertLess(point.x(),80); self.assertLess(point.y(),80)
        app.open_budget(); self.pump(.02)
        self.assertIs(app.budget_page.layout().itemAt(0).layout().itemAt(0).widget(),app.budget_back)
        for editing in (False,True):
            if editing: app.budget_editor.show_editor('shared-games')
            self.pump(.02)
            point=app.budget_back.mapTo(app.budget_page,QPoint(0,0))
            self.assertLess(point.x(),80); self.assertLess(point.y(),80)
            visible=[b for b in app.budget_page.findChildren(QPushButton)
                     if b.isVisible() and b.accessibleName()==app.t('Back')]
            self.assertEqual(visible,[app.budget_back])


if __name__=='__main__': unittest.main()
