"""User-visible save acknowledgement, duplicate protection and contextual help."""
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
import test_qt_ui


class UsabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):test_qt_ui.QtInterfaceTests.setUpClass()
    def setUp(self):
        self.case=test_qt_ui.QtInterfaceTests();self.case.setUp();self.app=self.case.app
        self.addCleanup(self.case.doCleanups);self.addCleanup(self.case.tearDown)

    def test_save_acknowledges_before_work_and_rejects_duplicate_clicks(self):
        app=self.app;app.switch_page(2);seen=[]
        def save(scope):
            seen.append((scope,app.feedback.text.text(),not app.general_save.isEnabled(),app.feedback.busy))
            return True
        with patch.object(app,'save_settings',side_effect=save):
            self.assertTrue(app.request_general_save());self.assertEqual(seen,[])
            self.assertFalse(app.request_general_save());self.assertFalse(app.general_save.isEnabled())
            self.case.pump(.04)
        self.assertEqual(seen,[('general',app.t('Saving…'),True,True)])
        self.assertEqual(app.feedback.text.text(),app.t('Saved.'));self.assertTrue(app.general_save.isEnabled())
        self.assertTrue(app.feedback.progress.isHidden())
        app.set_language('en');self.assertEqual(app.general_save.text(),'Save')
        app.set_language('hu');self.assertEqual(app.general_save.text(),'Mentés')

    def test_failed_save_keeps_draft_and_restores_action_for_retry(self):
        app=self.app;app.switch_page(2);app.games_path.setText('unsaved path')
        with patch.object(app,'save_settings',return_value=False):
            app.request_general_save();self.case.pump(.04)
        self.assertEqual(app.games_path.text(),'unsaved path');self.assertTrue(app.general_save.isEnabled())
        self.assertNotEqual(app.feedback.text.text(),app.t('Saved.'));self.assertFalse(app.feedback.busy)
        with patch.object(app,'save_settings',return_value=True):
            app.request_general_save();self.case.pump(.04)
        self.assertEqual(app.feedback.text.text(),app.t('Saved.'))

    def test_budget_only_save_does_not_restart_discovery_or_artwork(self):
        app=self.app
        with patch.object(app.service,'configure') as discovery,patch.object(app.art,'invalidate') as artwork,patch.object(app.art,'refresh_links') as links:
            self.assertTrue(app.save_settings(scope='budgets'))
            discovery.assert_not_called();artwork.assert_not_called();links.assert_not_called()
        destination=self.case.base/'AnotherGamesFolder';destination.mkdir();app.games_path.setText(str(destination))
        with patch.object(app.service,'configure') as discovery,patch.object(app.art,'refresh_links') as links:
            self.assertTrue(app.save_settings(scope='general'));discovery.assert_called_once();links.assert_called_once()
        app.hub_enabled.setChecked(not app.settings.hub_enabled)
        with patch.object(app.service,'configure') as discovery:
            self.assertTrue(app.save_settings(scope='general'));discovery.assert_called_once()

    def test_help_is_optional_keyboard_accessible_and_retranslates_in_place(self):
        from gametime.qt_widgets import help_text
        from gametime.qt_translation import retranslate_widgets
        help=help_text(self.app.t('Breaks repeat after the same amount of use, only while time remains in the budget. The break ends after this time even in another application.'))
        self.addCleanup(help.deleteLater)
        self.assertTrue(help.content.isHidden());self.assertTrue(help.toggle.isCheckable())
        help.toggle.click();self.assertFalse(help.content.isHidden())
        retranslate_widgets(help,'en');self.assertEqual(help.toggle.text(),'Help')
        self.assertTrue(help.toggle.isChecked());self.assertTrue(help.text().startswith('Breaks repeat'))
        help.toggle.click();self.assertTrue(help.content.isHidden())

    def test_shortcut_routes_only_to_current_editable_page(self):
        app=self.app
        for page,method in [(2,'request_general_save'),(5,'request_budget_save')]:
            app.switch_page(page)
            with patch.object(app,method) as save:app.save_current_page();save.assert_called_once()
        app.switch_page(1)
        with patch.object(app,'request_general_save') as save:app.save_current_page();save.assert_not_called()

    def test_direct_action_buttons_add_the_requested_kind(self):
        app=self.app;editor=app.budget_editor;editor.shared_created=True;editor.show_editor('shared-games')
        for name,kind in [('add_break','break'),('add_restriction','restrict'),('add_step','notify')]:
            getattr(editor.steps,name).click()
            self.assertEqual(editor.restriction_plans['shared-games']['steps'][-1]['kind'],kind)
        card=next(card for card in editor.steps.cards if card.value['kind']=='break')
        self.assertFalse(card.help.isHidden());self.assertTrue(card.help.content.isHidden())
        card.help.toggle.click();self.assertFalse(card.help.content.isHidden())
        self.assertFalse(card.hint.isHidden());self.assertIn('Breaks repeat',card.hint._ui_strings['setText'].key)
        self.assertEqual(editor.steps.add_break.text(),app.t('Take a break'))

    def test_pending_operation_does_not_run_after_close(self):
        app=self.app;calls=[];app.feedback.run('Saving…',lambda:calls.append(True));app.feedback.close_operation();self.case.pump(.03)
        self.assertEqual(calls,[]);self.assertFalse(app.feedback.busy)
