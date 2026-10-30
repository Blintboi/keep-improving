"""Back exits drafts without saving, including invalid input and other-page drafts."""
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

    def test_each_page_has_contextual_settings_and_no_settings_tab(self):
        app=self.app; app.show()
        self.assertNotIn(2,app.nav)
        for index,context in ((0,'activities'),(1,'overview'),(4,'focus'),(5,'budgets')):
            app.switch_page(index); self.pump(.02)
            controls=[w for w in app.pages.currentWidget().findChildren(QPushButton) if w.property('settingsContext')==context]
            self.assertEqual(len(controls),1)
            self.assertTrue(controls[0].isVisible()); self.assertEqual(controls[0].accessibleName(),app.t('Page settings'))
        app.switch_page(0)
        control=next(w for w in app.hub_page.findChildren(QPushButton) if w.property('settingsContext')=='activities')
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        def choose():
            menu=QApplication.activePopupWidget()
            if menu:
                action=next(a for a in menu.actions() if a.text()==app.t('Game folders'))
                menu.close(); action.trigger()
        QTimer.singleShot(100,choose); control.click()
        self.assertEqual(app.pages.currentIndex(),2); self.assertTrue(app.settings_sections['games'].isVisible())
        self.assertEqual(app.settings_back.text(),''); self.assertEqual(app.settings_back.accessibleName(),app.t('Back without saving'))
        app.settings_back.click(); self.assertEqual(app.pages.currentIndex(),0)

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

    def test_back_removes_even_invalid_new_budget_and_clears_validation_error(self):
        app=self.app; saved=self.store.settings(); app.open_budget(); editor=app.budget_editor
        editor.create_new(); key=editor.current; editor.name.setText(''); app.save_budgets()
        self.assertTrue(app.budget_error.text())
        editor.back_button.click()
        self.assertEqual(editor.views.currentIndex(),0); self.assertNotIn(key,editor.row_keys)
        self.assertFalse(app.budget_error.text()); self.assertFalse(app.settings_error.text())
        app.save_budgets(); self.assertEqual(self.store.settings(),saved)

    def test_cancel_existing_budget_reverts_members_name_and_limit_only_for_that_budget(self):
        app=self.app; editor=app.budget_editor
        rules=[new_rule(name,[target('site',name+'.com')],name) for name in ('one','two')]
        settings=replace(app.settings,wellbeing_rules=rules); self.store.save_settings(settings); app.settings=app.catalog.settings=settings; editor.saved(settings)
        app.open_budget(); editor.show_editor('one'); editor.minutes.setValue(25); editor.show_list()
        editor.show_editor('two'); editor.name.setText('Renamed'); editor.replace_members(editor.rule('two'),[target('site','changed.com')])
        editor.minutes.setValue(30); editor.name.setText(''); app.budget_back.click()
        self.assertEqual(editor.rule('two'),rules[1]); self.assertEqual(editor.rule('one')['seconds'],1500)
        self.assertEqual(self.store.settings(),settings)
        app.save_budgets(); self.assertEqual(self.store.settings().wellbeing_rules[1],rules[1])
        self.assertEqual(self.store.settings().wellbeing_rules[0]['seconds'],1500)

    def test_shared_schedule_and_new_game_budget_cancel_without_touching_general_draft(self):
        app=self.app; saved=self.store.settings(); app.games_path.setText(str(self.base/'pending'))
        app.open_budget(); app.budget_editor.show_editor('shared-games'); app.limit.setValue(97)
        app.schedule_editor.restriction_enabled.setChecked(True); app.budget_back.click()
        self.assertEqual(app.schedule_editor.settings(saved),saved)
        app.open_budget(member=target('game',self.games[0].id)); app.budget_editor.minutes.setValue(33)
        app.budget_back.click(); self.assertNotIn(self.games[0].id,app.budget_editor.game_limits)
        self.assertNotIn(self.games[0].id,app.budget_editor.draft_games)
        self.assertEqual(app.games_path.text(),str(self.base/'pending'))
        self.assertEqual(self.store.settings(),saved)

    def test_list_cancel_discards_all_budget_drafts_and_returns_without_navigation_loop(self):
        app=self.app; saved=self.store.settings(); app.switch_page(0); app.switch_page(2)
        app.open_budget(member=target('site','example.com')); app.budget_editor.minutes.setValue(25); app.budget_editor.show_list()
        app.budget_back.click(); self.assertEqual(app.pages.currentIndex(),2)
        self.assertEqual(app.budget_editor.settings(app.schedule_editor.settings(saved)),saved)
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


if __name__=='__main__': unittest.main()
