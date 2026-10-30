"""Progressive settings reveal must preserve drafts and saved preferences."""
import os
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDoubleSpinBox
import test_qt_ui as fixture


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class SettingsUsabilityTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def test_first_visit_fits_small_window_and_only_shows_common_time_fields(self):
        self.app.resize(1020,740); self.app.show(); self.app.open_budget(); self.pump(.05)
        self.assertEqual(self.app.pages.currentIndex(),5)
        fields=[widget for widget in self.app.budget_page.findChildren(QDoubleSpinBox) if widget.isVisible()]
        self.assertEqual(fields,[])
        self.assertEqual(self.app.budget_scroll.horizontalScrollBar().maximum(),0)
        self.assertEqual(self.app.budget_scroll.verticalScrollBar().maximum(),0)
        self.app.budget_editor.show_editor('shared-games'); self.pump(.02)
        self.assertTrue(self.app.limit.isVisible())
        self.assertTrue(self.app.schedule_editor.day_details.content.isHidden())
        self.assertTrue(all(item.content.isHidden() for item in self.app.schedule_editor.details.values()))

    def test_keyboard_disclosure_and_hidden_settings_keep_drafts_and_save(self):
        self.app.show(); self.app.open_budget(); self.app.budget_editor.show_editor('shared-games'); self.pump(.03)
        editor=self.app.schedule_editor; details=editor.details['restriction']
        details.toggle.setFocus(); QTest.keyClick(details.toggle,Qt.Key_Space); self.pump(.02)
        self.assertTrue(details.content.isVisible()); self.assertFalse(editor.restriction_controls.isVisible())
        editor.restriction_enabled.setChecked(True)
        self.assertTrue(editor.restriction_controls.isVisible())
        editor.restriction_minutes.setValue(135); self.app.limit.setValue(155)
        details.setExpanded(False); self.app.switch_page(2); self.app.show_settings_section('other'); self.app.set_language('en')
        self.assertIn('On',details.toggle.text())
        self.assertTrue(self.app.settings_sections['other'].isVisible())
        self.app.save_settings(); saved=self.store.settings()
        self.assertTrue(saved.restriction_enabled); self.assertEqual(saved.restriction_seconds,135*60)
        self.assertEqual(saved.limit_seconds,155*60)
        self.app.open_budget(); self.app.budget_editor.show_editor('shared-games'); details.setExpanded(True)
        self.assertEqual(editor.restriction_minutes.value(),135)

    def test_browsing_and_collapsing_sections_does_not_change_existing_preferences(self):
        saved=self.store.settings(); self.app.show(); self.app.switch_page(2)
        for key in self.app.settings_sections:
            self.app.show_settings_section(key)
        for item in self.app.schedule_editor.details.values():
            item.setExpanded(True); item.setExpanded(False)
        self.app.overlay_details.setExpanded(True); self.app.overlay_details.setExpanded(False)
        self.app.save_settings()
        self.assertEqual(self.store.settings(),saved)

    def test_collapsed_countdown_does_not_capture_and_opening_it_keeps_position_visible(self):
        with patch('gametime.qt_game_preview.running_window',return_value=None) as lookup:
            self.app.show(); self.app.switch_page(2); self.app.show_settings_section('countdown'); self.pump(.05)
            lookup.assert_not_called(); self.assertFalse(self.app.overlay_picker.isVisible())
            from PySide6.QtWidgets import QWidget
            self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]
            fields={w.accessibleName():w for w in window.findChildren(QWidget) if w.accessibleName()}
            fields[self.app.t('Hide this countdown')].setChecked(False); self.pump(.05)
            picker=fields[self.app.t('Countdown position')]
            self.assertTrue(picker.isVisible()); self.assertTrue(lookup.called)
            monitor,hud=picker.rectangles(); self.assertTrue(monitor.contains(hud)); window.reject()
            self.app.open_budget(); lookup.reset_mock()
            for _ in range(3): self.app.render_tick(); self.app.update_overlay()
            lookup.assert_not_called(); self.assertIsNone(self.app.overlay_picker.game_background)


if __name__=='__main__': unittest.main()
