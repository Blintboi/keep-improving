from unittest.mock import patch
from dataclasses import replace
from datetime import datetime
import unittest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import test_qt_ui as fixture
from gametime.wellbeing import target
from gametime.timer_view import TimerView


class EarlyBreakInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump
    def test_editor_opt_in_roundtrip_and_nonrepeating_timing_removes_option(self):
        for language in ('hu','en'):
            self.app.set_language(language);self.app.open_budget(member=target('site','youtube.com'));e=self.app.budget_editor
            previous={c.value['id'] for c in e.steps.cards};e.steps.add('break');card=next(c for c in e.steps.cards if c.value['id'] not in previous);self.assertFalse(card.early_break.isChecked())
            card.early_break.setChecked(True);key=e.current;self.app.save_budgets()
            identity=card.value['id'];self.assertFalse(self.app.budget_error.text());self.assertTrue(next(s for s in self.store.settings().restriction_plans[key]['steps'] if s['id']==identity)['allow_early_break'])
            e.show_editor(key);card=next(c for c in e.steps.cards if c.value['id']==identity);self.assertTrue(card.early_break.isChecked())
            card.time_mode.setCurrentIndex(card.time_mode.findData('clock'));self.assertNotIn('allow_early_break',card.value)
            self.assertTrue(card.early_break.isHidden())
    def test_hud_has_no_action_window_and_remains_click_through(self):
        overlay=self.app.overlay;self.assertIsNotNone(overlay)
        screen=QApplication.primaryScreen();settings=replace(self.app.settings,overlay_x=1,overlay_y=1)
        timer=TimerView('fixture','YouTube','break',180,break_step='pause')
        before=set(QApplication.topLevelWidgets());overlay.present(180,720,settings,screen,timer=timer)
        self.assertEqual(set(QApplication.topLevelWidgets()),before)
        self.assertFalse(hasattr(overlay,'early_button'));self.assertTrue(overlay.testAttribute(Qt.WA_TransparentForMouseEvents))
    def test_saved_budget_button_works_after_leaving_the_target_and_disables_during_break(self):
        from gametime.restriction_policy import Budget,new_plan,step
        from gametime.qt_budgets import new_rule
        from gametime.tracker import Sample
        import time
        plan=new_plan();item=step('break',900,identity='pause',break_mode='cover',break_minutes=5)
        item['allow_early_break']=True;plan['steps']=[item]
        rule=new_rule('YouTube',[target('site','youtube.com')],'youtube');rule['enabled']=True
        self.app.settings=replace(self.app.settings,wellbeing_rules=[rule],restriction_plans={'youtube':plan})
        budget=Budget('youtube','YouTube',3600,720,tuple(rule['members']))
        with patch.object(self.app.restrictions,'budgets',return_value=[budget]),patch('gametime.win32.sample',side_effect=lambda:Sample(datetime.now().astimezone(),time.monotonic(),interactive=False)):
            self.app.budget_editor.saved(self.app.settings);self.app.open_budget();editor=self.app.budget_editor
            action=editor.break_buttons['youtube'];self.assertFalse(action.isHidden());self.assertTrue(action.isEnabled())
            action.click();self.assertGreater(self.app.restrictions.state.break_remaining('youtube'),298)
            self.assertFalse(action.isEnabled());self.assertIn('Szünetből hátra',action.toolTip())
            editor.refresh_rows();self.assertIs(editor.break_buttons['youtube'],action)
            with patch.object(editor,'refresh_breaks') as refresh:
                self.app.hide();self.app.render_tick();refresh.assert_not_called()
    def test_tray_routes_the_break_action_and_browser_retries_do_not_restart_it(self):
        from gametime.browser_control import BrowserControl
        event=TimerView('fixture','YouTube','break',180,break_step='pause')
        with patch.object(self.app,'timer_views',return_value=[event]),patch.object(self.app.restrictions,'start_early_break',return_value=True) as start:
            items=self.app.timer_menu_items();command=next(command for command,text in items if 'Szünet most' in text)
            self.assertTrue(self.app.open_timer(command));start.assert_called_once_with('fixture','pause');start.reset_mock()
            control=BrowserControl(self.app)
            request=dict(action='break.start',data=dict(key='fixture',step='pause'),revision=control.revision(),id='early-break-retry-fixture')
            first=control.dispatch(request);self.assertTrue(first['ok'],first)
            self.assertEqual(control.dispatch(request),first);start.assert_called_once_with('fixture','pause')
            self.assertFalse(control.dispatch(dict(request,id='early-break-stale-fixture',revision='stale'))['ok'])
            start.assert_called_once()

    def test_browser_quick_break_survives_no_timer_and_explains_unavailability(self):
        from gametime.restriction_policy import Budget,new_plan,step
        from gametime.browser_control import BrowserControl
        plan=new_plan();item=step('break',900,identity='pause',break_mode='cover',break_minutes=5)
        item['allow_early_break']=True;plan['steps']=[item]
        self.app.settings=replace(self.app.settings,restriction_plans={'youtube':plan})
        runtime=self.app.restrictions;budget=Budget('youtube','YouTube',3600,720,(target('site','youtube.com'),))
        with patch.object(runtime,'budgets',return_value=[budget]),patch.object(self.app,'timer_views',return_value=[]):
            runtime.prepare(datetime.now().astimezone());live=BrowserControl(self.app).live({})
            self.assertEqual(live['timers'],[])
            self.assertEqual(live['break_actions']['youtube']['step'],'pause')
            self.assertEqual(live['break_actions']['youtube']['minutes'],5)
            self.assertEqual(live['break_actions']['youtube']['unavailable'],'')
        with patch.object(runtime,'budgets',return_value=[replace(budget,used=3600)]):
            runtime.prepare(datetime.now().astimezone());action=runtime.early_break_actions()['youtube']
            self.assertEqual(action['step'],'');self.assertEqual(action['unavailable'],'limit')
