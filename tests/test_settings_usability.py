"""Progressive settings reveal must preserve drafts and saved preferences."""
import os
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QPoint,QTime
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDoubleSpinBox,QAbstractSpinBox,QTimeEdit
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
        self.assertFalse(self.app.schedule_editor.day_details.content.isVisible())
        self.assertTrue(self.app.budget_editor.access.widget.isVisible())
        self.assertTrue(self.app.schedule_editor.warning.isVisible())
        self.assertTrue(self.app.schedule_editor.details['bedtime'].isHidden())

    def test_keyboard_disclosure_and_hidden_settings_keep_drafts_and_save(self):
        self.app.show(); self.app.open_budget(); self.app.budget_editor.show_editor('shared-games'); self.pump(.03)
        editor=self.app.schedule_editor; blocks=self.app.budget_editor.steps
        blocks.add_step.setFocus(); QTest.keyClick(blocks.add_step,Qt.Key_Space); self.pump(.02)
        self.assertEqual(len(blocks.cards),1)
        blocks.cards[0].kind.setCurrentIndex(blocks.cards[0].kind.findData('restrict')); blocks.cards[0].consent.setChecked(True); blocks.cards[0].minutes.setValue(15); self.app.limit.setValue(155)
        self.app.switch_page(2); self.app.show_settings_section('other'); self.app.set_language('en')
        self.assertTrue(self.app.settings_sections['other'].isVisible())
        self.app.save_settings(); saved=self.store.settings()
        self.assertEqual(saved.restriction_plans['shared-games']['steps'][0]['offset'],15*60)
        self.assertEqual(saved.limit_seconds,155*60)
        self.app.open_budget(); self.app.budget_editor.show_editor('shared-games')
        self.assertEqual(blocks.cards[0].minutes.value(),15)

    def test_plain_number_and_time_fields_keep_keyboard_editing_and_have_no_step_hotspots(self):
        from gametime.wellbeing import target
        self.app.open_budget(member=target('site','example.com')); editor=self.app.budget_editor
        editor.steps.add_step.click(); card=editor.steps.cards[0]
        card.kind.setCurrentIndex(card.kind.findData('break'))
        self.app.show(); self.pump(.03)
        for field in (editor.minutes,card.minutes,card.break_minutes,card.extra,self.app.global_day_start):
            self.assertEqual(field.buttonSymbols(),QAbstractSpinBox.NoButtons)
        card.minutes.setFocus(); card.minutes.selectAll()
        QTest.keyClicks(card.minutes,'12'+card.minutes.locale().decimalPoint()+'50'); QTest.keyClick(card.minutes,Qt.Key_Tab)
        self.assertEqual(card.minutes.value(),12.5)
        card.break_minutes.setFocus(); card.break_minutes.selectAll()
        QTest.keyClicks(card.break_minutes,'30'); QTest.keyClick(card.break_minutes,Qt.Key_Tab)
        self.assertEqual(card.break_minutes.value(),30)
        self.app.open_settings_section('general'); reset=self.app.global_day_start
        reset.setFocus(); reset.setSelectedSection(QTimeEdit.HourSection)
        QTest.keyClicks(reset,'09'); reset.setSelectedSection(QTimeEdit.MinuteSection)
        QTest.keyClicks(reset,'45'); QTest.keyClick(reset,Qt.Key_Tab)
        self.assertEqual(reset.time(),QTime(9,45)); self.app.switch_page(5)
        for width in (1000,1380):
            self.app.resize(width,740); self.pump(.03)
            QTest.mouseClick(card.break_minutes,Qt.LeftButton,pos=QPoint(card.break_minutes.width()-4,10))
            self.assertEqual(card.break_minutes.value(),30)
            self.assertGreaterEqual(card.break_minutes.lineEdit().x(),10)
            self.assertGreater(card.break_minutes.lineEdit().width(),card.break_minutes.fontMetrics().horizontalAdvance('30'))
        key=editor.current; self.app.save_budgets(); self.assertFalse(self.app.budget_error.text())
        saved=self.store.settings(); action=saved.restriction_plans[key]['steps'][0]
        self.assertEqual((action['offset'],action['break_minutes']),(750,30))
        self.assertNotIn(key,saved.budget_reset_overrides)

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
