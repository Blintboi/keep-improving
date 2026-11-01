"""Budget appearance drafts, activity overrides and actual RTSS selection."""
from dataclasses import replace
from datetime import datetime
from unittest.mock import patch
import unittest
from PySide6.QtWidgets import QWidget,QPushButton
import test_qt_ui as fixture
from gametime.activities import activity_settings
from gametime.tracker import Sample
from gametime.wellbeing import target


class BudgetCountdownTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def field(self,window,name):
        return next(w for w in window.findChildren(QWidget) if w.accessibleName()==self.app.t(name))

    def click(self,window,name):
        next(w for w in window.findChildren(QPushButton) if w.text()==self.app.t(name)).click()

    def test_new_site_budget_countdown_saves_with_budget_and_can_be_cancelled(self):
        self.app.open_budget(member=target('site','example.com')); editor=self.app.budget_editor; key=editor.current
        editor.appearance.click(); window=self.app._dialogs[-1]
        self.assertEqual(self.field(window,'Countdown target').currentData(),key)
        self.assertTrue(self.field(window,'Use RTSS in games').isHidden())
        self.field(window,'Text size').setValue(38)
        with patch('gametime.qt_ui.running_window') as running,patch('gametime.qt_game_preview.running_window') as capture:
            self.click(window,'Preview (10s)'); self.pump(.03)
            running.assert_not_called(); capture.assert_not_called()
        self.assertEqual(self.app._overlay_preview_settings.overlay_font_size,38)
        self.click(window,'Save')
        self.assertEqual(self.store.settings().counter_overlays,{})
        self.app.save_budgets(); saved=self.store.settings()
        self.assertEqual(saved.counter_overlays[key]['overlay_font_size'],38)
        self.assertEqual(activity_settings(saved,target('site','example.com')).overlay_font_size,38)
        editor.show_editor(key); editor.appearance.click(); window=self.app._dialogs[-1]
        self.field(window,'Text size').setValue(46); self.click(window,'Save')
        self.app.budget_back.click(); self.app.save_budgets()
        self.assertEqual(self.store.settings().counter_overlays[key]['overlay_font_size'],38)

    def test_shared_countdown_and_rtss_save_and_cancel_independently(self):
        self.app.open_budget(); editor=self.app.budget_editor; editor.show_editor('shared-games')
        self.assertFalse(editor.shared_appearance.isHidden())
        editor.shared_appearance.click(); window=self.app._dialogs[-1]
        self.field(window,'Use RTSS in games').setChecked(True)
        self.field(window,'Text size').setValue(39); self.click(window,'Save')
        self.assertFalse(self.store.settings().overlay_rtss_auto)
        self.app.save_budgets(); self.assertTrue(self.store.settings().overlay_rtss_auto)
        self.assertEqual(self.store.settings().overlay_font_size,39)
        self.app.save_settings(); self.assertEqual(self.store.settings().overlay_font_size,39)
        editor.show_editor('shared-games'); editor.shared_appearance.click(); window=self.app._dialogs[-1]
        self.field(window,'Use RTSS in games').setChecked(False); self.click(window,'Save')
        self.app.budget_back.click(); self.app.save_budgets()
        self.assertTrue(self.store.settings().overlay_rtss_auto)

    def test_individual_budget_rtss_reaches_renderer_without_global_switch(self):
        game=self.games[0]; self.app.open_budget(member=target('game',game.id)); editor=self.app.budget_editor
        editor.minutes.setValue(20); editor.appearance.click(); window=self.app._dialogs[-1]
        self.field(window,'Hide this countdown').setChecked(False)
        self.field(window,'Use RTSS in games').setChecked(True); self.click(window,'Save'); self.app.save_budgets()
        saved=self.store.settings(); self.assertFalse(saved.overlay_rtss_auto)
        self.assertTrue(saved.game_overlays[game.id]['overlay_rtss_auto'])
        now=datetime.now().astimezone(); self.app.tracker.active=game; self.app.tracker.identity='fixture:1'
        current=Sample(now,100,str(self.exe),'fixture:1')
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch('gametime.qt_ui.foreground_screen_name',return_value=''), \
             patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app.rtss,'present',return_value=True) as present:
            self.app.update_overlay(); self.app._overlay_desktop_until=0; self.app.update_overlay()
            self.assertEqual(self.rtss_renderer.call_args.args[0],1200); self.assertIn('<LI=',present.call_args.args[2])
        self.app.game_countdown_dialog(game.id); window=self.app._dialogs[-1]
        self.field(window,'Text size').setValue(43); self.click(window,'Save')
        self.assertTrue(self.store.settings().game_overlays[game.id]['overlay_rtss_auto'])

    def test_group_budget_defaults_preserve_activity_overrides(self):
        members=[target('game',self.games[0].id),target('site','example.com')]
        self.app.open_budget(members=members); editor=self.app.budget_editor; key=editor.current
        editor.appearance.click(); window=self.app._dialogs[-1]
        self.field(window,'Use RTSS in games').setChecked(True); self.field(window,'Text size').setValue(36)
        self.click(window,'Save'); self.app.save_budgets(); saved=self.store.settings()
        self.assertTrue(saved.counter_overlays[key]['overlay_rtss_auto'])
        self.assertTrue(activity_settings(saved,members[0]).overlay_rtss_auto)
        custom=replace(saved,activity_overlays={'site:example.com':{'overlay_font_size':22}})
        self.assertEqual(activity_settings(custom,members[1]).overlay_font_size,22)
        editor.show_editor(key); editor.appearance.click(); window=self.app._dialogs[-1]
        self.field(window,'Text size').setValue(48); self.click(window,'Cancel'); self.app.save_budgets()
        self.assertEqual(self.store.settings().counter_overlays[key]['overlay_font_size'],36)

    def test_group_members_have_separate_drafts_and_runtime_profiles(self):
        members=[target('game',self.games[0].id),target('app','editor.exe'),target('site','example.com')]
        self.app.open_budget(members=members); editor=self.app.budget_editor; key=editor.current
        editor.appearance.click(); window=self.app._dialogs[-1]; choices=self.field(window,'Countdown target')
        expected={key,'game:'+self.games[0].id,'app:editor.exe','site:example.com'}
        self.assertEqual({choices.itemData(i) for i in range(choices.count())},expected)
        self.field(window,'Text size').setValue(30)
        choices.setCurrentIndex(choices.findData('site:example.com'))
        self.assertEqual(self.field(window,'Text size').value(),30)
        self.assertTrue(self.field(window,'Use RTSS in games').isHidden())
        self.field(window,'Text size').setValue(42)
        choices.setCurrentIndex(choices.findData('game:'+self.games[0].id))
        self.assertFalse(self.field(window,'Use RTSS in games').isHidden())
        self.field(window,'Hide this countdown').setChecked(False)
        self.field(window,'Use RTSS in games').setChecked(True)
        self.field(window,'Text size').setValue(36)
        choices.setCurrentIndex(choices.findData('app:editor.exe'))
        self.field(window,'Hide this countdown').setChecked(True)
        choices.setCurrentIndex(choices.findData('site:example.com'))
        self.assertEqual(self.field(window,'Text size').value(),42)
        self.click(window,'Save')
        self.assertEqual(self.store.settings().activity_overlays,{})
        self.app.save_budgets(); saved=self.store.settings()
        self.assertFalse(self.app.budget_error.text())
        self.assertEqual(saved.counter_overlays[key]['overlay_font_size'],30)
        self.assertEqual(saved.activity_overlays['site:example.com']['overlay_font_size'],42)
        self.assertNotIn('overlay_rtss_auto',saved.activity_overlays['site:example.com'])
        self.assertFalse(activity_settings(saved,members[1]).overlay_enabled)
        self.assertEqual(activity_settings(saved,members[0]).overlay_font_size,36)
        self.assertTrue(activity_settings(saved,members[0]).overlay_rtss_auto)
        editor.show_editor(key); editor.appearance.click(); window=self.app._dialogs[-1]
        choices=self.field(window,'Countdown target'); choices.setCurrentIndex(choices.findData('site:example.com'))
        self.assertEqual(self.field(window,'Text size').value(),42); window.reject()

    def test_shared_games_members_and_budget_cancel_preserve_other_drafts(self):
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games')
        editor.shared_appearance.click(); window=self.app._dialogs[-1]; choices=self.field(window,'Countdown target')
        self.assertEqual({choices.itemData(i) for i in range(choices.count())},
                         {'shared-games',*('game:'+g.id for g in self.games)})
        choices.setCurrentIndex(choices.findData('game:'+self.games[0].id))
        self.field(window,'Text size').setValue(40); self.click(window,'Save')
        self.app.budget_back.click(); self.app.save_budgets()
        self.assertEqual(self.store.settings().game_overlays,{})
        self.app.open_budget(members=[target('site','one.example'),target('site','two.example')]); first=editor.current
        editor.appearance.click(); window=self.app._dialogs[-1]; choices=self.field(window,'Countdown target')
        choices.setCurrentIndex(choices.findData('site:one.example')); self.field(window,'Text size').setValue(35); self.click(window,'Save')
        self.app.open_budget(members=[target('site','one.example'),target('site','three.example')])
        editor.appearance.click(); window=self.app._dialogs[-1]; choices=self.field(window,'Countdown target')
        choices.setCurrentIndex(choices.findData('site:one.example')); self.field(window,'Text size').setValue(47); self.click(window,'Save')
        self.app.budget_back.click(); self.app.save_budgets()
        self.assertEqual(self.store.settings().activity_overlays['site:one.example']['overlay_font_size'],35)
        self.assertIn(first,{r['id'] for r in self.store.settings().wellbeing_rules})

    def test_individual_game_editor_sees_member_draft_and_can_revert_only_its_own_change(self):
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games')
        editor.shared_appearance.click(); window=self.app._dialogs[-1]; choices=self.field(window,'Countdown target')
        choices.setCurrentIndex(choices.findData('game:'+self.games[0].id))
        self.field(window,'Text size').setValue(35); self.click(window,'Save')
        self.app.open_budget(member=target('game',self.games[0].id)); editor.appearance.click(); window=self.app._dialogs[-1]
        self.assertEqual(self.field(window,'Text size').value(),35)
        self.field(window,'Text size').setValue(46); self.click(window,'Save')
        self.assertEqual(editor.countdown_settings(self.app.settings).game_overlays[self.games[0].id]['overlay_font_size'],46)
        self.app.budget_back.click(); self.app.save_budgets()
        self.assertEqual(self.store.settings().game_overlays[self.games[0].id]['overlay_font_size'],35)


if __name__=='__main__': unittest.main()
