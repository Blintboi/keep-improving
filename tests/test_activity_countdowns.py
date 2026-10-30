"""Application, website and group countdowns use the same scoped editor."""
from dataclasses import replace
from datetime import datetime,timedelta
from unittest.mock import Mock,patch
import unittest
from PySide6.QtWidgets import QWidget,QPushButton
import test_qt_ui as fixture
from gametime.model import Settings
from gametime.tracker import Sample
from gametime.wellbeing import target,counter_settings
from gametime.qt_budgets import new_rule
from gametime.activities import activity_key,activity_settings


class CountdownSettingsTests(unittest.TestCase):
    def test_strict_profiles_are_local_and_cannot_change_limits_or_unrelated_fields(self):
        from gametime.preferences_sync import LOCAL_FIELDS
        self.assertIn('counter_overlays',LOCAL_FIELDS)
        for value in ([],{'x':{'language':'hu'}},{'x':{'limit_seconds':300}}, {'x':{'overlay_enabled':True}},
                      {'x':{'overlay_x':2}},{'x':{'overlay_font_size':73}},{'x':{'overlay_color_normal':'bad'}}):
            with self.subTest(value=value),self.assertRaises(ValueError): replace(Settings(),counter_overlays=value).validate()
        rule=new_rule('Browser',[target('app',r'C:\Apps\brave.exe')],'browser')
        settings=replace(Settings(),counter_overlays={'browser':{'overlay_x':.3,'overlay_font_size':38}}).validate()
        effective=counter_settings(settings,rule)
        self.assertEqual((effective.overlay_x,effective.overlay_font_size),(.3,38)); self.assertEqual(settings.overlay_x,1)


class ActivityCountdownTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def field(self,window,key):
        return next(w for w in window.findChildren(QWidget) if w.accessibleName()==self.app.t(key))

    def click(self,window,key):
        next(w for w in window.findChildren(QPushButton) if w.text()==self.app.t(key)).click()

    def seed(self):
        self.now=datetime.now().astimezone()
        self.browser=r'c:\apps\brave.exe'; self.site='example.com'
        for kind,value in (('app',self.browser),('site',self.site)):
            self.app.focus._credit(kind,value,value,self.now,self.now+timedelta(seconds=5),5)
        self.app.focus.flush()
        for kind,value in (('app',self.browser),('site',self.site)):
            self.app.open_budget(member=target(kind,value))
        self.app.save_settings()

    def choose(self,window,text):
        selector=self.field(window,'Countdown target')
        index=next(i for i in range(selector.count()) if text in selector.itemText(i))
        selector.setCurrentIndex(index); return selector.currentData()

    def test_configured_app_and_site_budgets_have_independent_countdown_styles(self):
        self.seed(); self.app.game_countdown_dialog(); window=self.app._dialogs[-1]
        app_id=self.choose(window,'brave.exe')
        self.field(window,'Text size').setValue(38); self.field(window,'Horizontal (px)').setValue(100)
        self.field(window,'Text opacity').setValue(45)
        app_position=self.field(window,'Countdown position').x_ratio
        site_id=self.choose(window,self.site); self.field(window,'Text size').setValue(22)
        self.field(window,'Vertical (px)').setValue(180); self.click(window,'Save')
        saved=self.store.settings()
        self.assertEqual([r['members'] for r in saved.wellbeing_rules],[[target('app','brave.exe')],[target('site',self.site)]])
        self.assertTrue(all(r['enabled'] and r['overlay'] for r in saved.wellbeing_rules))
        self.assertEqual(saved.activity_overlays[app_id]['overlay_font_size'],38)
        self.assertEqual(saved.activity_overlays[app_id]['overlay_x'],app_position)
        self.assertEqual(saved.activity_overlays[site_id]['overlay_font_size'],22)
        self.assertEqual(saved.activity_overlays[app_id]['overlay_opacity'],.45)
        self.assertEqual(saved.activity_overlays[site_id]['overlay_opacity'],saved.overlay_opacity)
        self.assertEqual(saved.game_overlays,{})
        self.app.save_settings(); self.assertEqual(self.store.settings().activity_overlays,saved.activity_overlays)

    def test_hide_site_keeps_budget_and_collapses_controls_cancel_preserves_rules(self):
        self.seed(); self.app.game_countdown_dialog(); window=self.app._dialogs[-1]
        before=self.store.settings().wellbeing_rules
        self.choose(window,self.site); self.field(window,'Hide this countdown').setChecked(True)
        self.assertFalse(self.field(window,'Text size').isVisible()); self.click(window,'Cancel')
        self.assertEqual(self.store.settings().wellbeing_rules,before)
        self.app.game_countdown_dialog(); window=self.app._dialogs[-1]; identity=self.choose(window,self.site)
        self.field(window,'Hide this countdown').setChecked(True); self.click(window,'Save')
        saved=self.store.settings(); self.assertEqual(saved.wellbeing_rules,before)
        self.assertFalse(saved.activity_overlays[identity]['overlay_enabled'])
        self.app.save_settings(); self.assertFalse(self.store.settings().activity_overlays[identity]['overlay_enabled'])

    def test_preview_uses_scoped_style_and_never_searches_or_activates_a_game(self):
        self.seed(); self.app.game_countdown_dialog(); window=self.app._dialogs[-1]
        self.choose(window,self.site); self.field(window,'Text size').setValue(41)
        with patch('gametime.qt_ui.running_window') as game,patch('gametime.qt_game_preview.running_window') as capture:
            self.click(window,'Preview (10s)'); self.pump(.03)
            game.assert_not_called(); capture.assert_not_called()
        self.assertEqual(self.app._overlay_preview_settings.overlay_font_size,41)
        self.assertIsNone(self.app._overlay_preview_target)
        self.click(window,'Cancel'); self.assertEqual(self.app._overlay_preview_until,0)

    def test_activity_library_opens_its_countdown_and_keeps_unsaved_budget_changes(self):
        self.app.open_budget(member=target('site','example.com')); editor=self.app.budget_editor
        self.app.save_budgets(); editor.show_editor(editor.rules[0]['id']); editor.minutes.setValue(25)
        self.assertFalse(editor.appearance.isVisible()); self.assertFalse(editor.overlay.isVisible())
        self.app.open_activities('site'); self.app.activity_lists['site'].countdown.click()
        window=self.app._dialogs[-1]; self.assertEqual(self.field(window,'Countdown target').currentData(),'site:example.com')
        self.field(window,'Text size').setValue(36); self.click(window,'Save')
        self.assertEqual(editor.minutes.value(),25); self.app.save_settings()
        saved=self.store.settings(); self.assertEqual(saved.wellbeing_rules[0]['seconds'],1500)
        self.assertEqual(saved.activity_overlays['site:example.com']['overlay_font_size'],36)

    def test_site_and_application_runtime_use_their_own_styles_and_ignore_hidden_counters(self):
        app_rule=new_rule('Browser',[target('app',r'C:\Apps\brave.exe')],'browser')
        site_rule=new_rule('Website',[target('site','example.com')],'website')
        app_rule.update(enabled=True,seconds=120); site_rule.update(enabled=True,seconds=60)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[app_rule,site_rule],
            counter_overlays={'browser':{'overlay_font_size':34,'overlay_color_normal':'#ff0000'},
                              'website':{'overlay_font_size':20,'overlay_color_normal':'#00ff00'}})
        current=Sample(datetime.now().astimezone(),100,r'C:\Apps\brave.exe','fixture:browser')
        self.app.browser_bridge=Mock(); self.app.browser_bridge.website.return_value='example.com'
        self.app.wellbeing.tick(current,'example.com')
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app.rtss,'present') as rtss:
            self.app.update_overlay(); self.assertEqual(self.app.overlay.seconds,60); self.assertEqual(self.app.overlay.font_size,20)
            self.assertEqual(self.app.overlay.color,'#00ff00'); rtss.assert_not_called()
            self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[app_rule,{**site_rule,'overlay':False}])
            self.app.update_overlay(); self.assertEqual(self.app.overlay.seconds,120); self.assertEqual(self.app.overlay.font_size,34)
            self.app.browser_bridge.website.return_value='another.com'
            self.app.wellbeing.tick(replace(current,wall=current.wall+timedelta(seconds=1),awake=101),'another.com')
            self.app.update_overlay(); self.assertEqual(self.app.overlay.font_size,34)

    def test_shared_budget_members_have_independent_styles_and_visibility(self):
        editor=self.app.budget_editor
        members=[target('site','example.com'),target('site','other.com'),target('app',r'C:\Apps\editor.exe')]
        self.app.open_budget(members=members); self.app.save_budgets(); before=self.store.settings().wellbeing_rules
        self.app.game_countdown_dialog('site:example.com'); window=self.app._dialogs[-1]
        self.field(window,'Text size').setValue(35); self.choose(window,'other.com')
        self.field(window,'Hide this countdown').setChecked(True); self.click(window,'Save')
        saved=self.store.settings(); self.assertEqual(saved.wellbeing_rules,before)
        self.assertEqual(activity_settings(saved,members[0]).overlay_font_size,35)
        self.assertFalse(activity_settings(saved,members[1]).overlay_enabled)
        self.assertTrue(activity_settings(saved,members[2]).overlay_enabled)


if __name__=='__main__': unittest.main()
