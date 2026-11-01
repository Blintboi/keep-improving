"""Independent native/web behavior with a shared usage trigger."""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch
import unittest
import test_restriction_steps as policy_fixture
import test_qt_ui as fixture
from gametime.restriction_policy import Budget,RestrictionState,new_plan,step,validate_plans
from gametime.wellbeing import target


class TargetPolicyTests(unittest.TestCase):
    setUp=policy_fixture.StepsTests.setUp; tearDown=policy_fixture.StepsTests.tearDown; update=policy_fixture.StepsTests.update

    def test_mixed_break_modes_and_durations_expire_independently(self):
        pause=step('break',60,usage=True,break_minutes=5)
        pause['targets']={'app':{'break_mode':'minimize','break_minutes':1},
                          'site':{'break_mode':'redirect','break_minutes':3,'redirect_url':''}}
        self.plan['steps']=[pause]; validate_plans(self.plans); self.update(60,1000,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject),'minimize')
        self.assertEqual(self.engine.action('budget','site:example.com'),'redirect')
        self.assertEqual(self.engine.break_remaining('budget',self.subject),60)
        self.assertEqual(self.engine.break_remaining('budget','site:'),180)
        self.update(60,1060,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.assertEqual(self.engine.action('budget','site:example.com'),'redirect')
        self.engine=RestrictionState(self.store); self.day='2026-10-31'; self.update(0,1100,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.assertEqual(self.engine.break_remaining('budget','site:'),80)
        self.update(0,1180,limit=500); self.assertEqual(self.engine.action('budget','site:'),'')

    def test_warning_choices_and_delivery_are_independent(self):
        warning=step('notify',60,usage=True,sound=True)
        warning['targets']={'app':{'sound':True,'popup':False},'site':{'sound':False,'popup':True}}
        self.plan['steps']=[warning]; self.update(60,1000,limit=500)
        app=self.engine.warnings('budget',self.subject)[0]; site=self.engine.warnings('budget','site:')[0]
        self.assertEqual((app['sound'],app['popup']),(True,False))
        self.assertEqual((site['sound'],site['popup']),(False,True))
        self.engine.delivered('budget',app['id'])
        self.assertEqual(self.engine.warnings('budget',self.subject),[])
        self.assertEqual(len(self.engine.warnings('budget','site:')),1)

    def test_disabled_type_has_no_restriction_or_warning(self):
        action=step('restrict',60,usage=True)
        action['targets']={'app':{'enabled':False},'site':{'mode':'redirect','redirect_url':'https://rest.example.org/'}}
        self.plan['steps']=[action]; validate_plans(self.plans); self.update(60,1000,limit=500)
        self.assertEqual(self.engine.action('budget',self.subject),'')
        self.assertFalse(self.engine.has_restriction('budget',self.subject))
        self.assertEqual(self.engine.action('budget','site:'),'redirect')
        self.assertTrue(self.engine.has_restriction('budget','site:'))

    def test_save_length_is_specific_to_the_active_type(self):
        action=step('restrict',60,usage=True)
        action['targets']={'app':{'extension_minutes':2},'site':{'mode':'cover','extension_minutes':4}}
        self.plan['steps']=[action]; self.update(60,1000,limit=500)
        self.assertEqual(self.engine.allowance(['budget'],self.subject),2)
        self.assertEqual(self.engine.allowance(['budget'],'site:example.com'),4)
        self.assertEqual(self.engine.extend(['budget'],self.subject,'123:456'),1120)
        self.update(60,1120,limit=500); self.assertEqual(self.engine.action('budget',self.subject,'123:456'),'close')

    def test_target_settings_are_strictly_validated(self):
        pause=step('break',60,usage=True); self.plan['steps']=[pause]
        for options in ({'app':{'break_mode':'redirect'}},{'site':{'break_mode':'minimize'}},
                        {'app':{'extension_minutes':True}},{'site':{'break_minutes':0}},
                        {'site':{'redirect_url':'javascript:alert(1)'}},{'other':{}},
                        {'app':{'enabled':1}},{'app':{'unexpected':True}}):
            with self.subTest(options=options),self.assertRaises(ValueError):
                pause['targets']=options; validate_plans(self.plans)


class TargetInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp; tearDown=fixture.QtInterfaceTests.tearDown; pump=fixture.QtInterfaceTests.pump

    def mixed(self):
        self.app.open_budget(members=[target('game',self.games[0].id),target('site','example.com')])
        editor=self.app.budget_editor; editor.steps.add_step.click()
        return editor,editor.steps.cards[0]

    def test_only_selected_types_are_shown_and_membership_updates_them(self):
        self.app.open_budget(member=target('site','example.com')); editor=self.app.budget_editor
        editor.steps.add_step.click(); self.assertEqual(set(editor.steps.cards[0].targets),{'site'})
        key=editor.current; before=deepcopy(editor.restriction_plans[key]); rule=editor.rule(key)
        editor.replace_members(rule,[target('site','example.com'),target('game',self.games[0].id)])
        self.assertEqual(set(editor.steps.cards[0].targets),{'app','site'})
        self.assertEqual(editor.restriction_plans[key],before)
        editor.replace_members(rule,[target('game',self.games[0].id)])
        self.assertEqual(set(editor.steps.cards[0].targets),{'app'})

    def test_mixed_break_controls_save_independent_modes_and_lengths(self):
        editor,card=self.mixed(); key=editor.current; card.kind.setCurrentIndex(card.kind.findData('break'))
        app,site=card.targets['app'],card.targets['site']
        self.assertEqual(app.break_mode.findData('redirect'),-1)
        self.assertEqual(site.break_mode.findData('minimize'),-1)
        app.break_mode.setCurrentIndex(app.break_mode.findData('close')); app.break_minutes.setValue(2); app.extra.setValue(3)
        site.break_mode.setCurrentIndex(site.break_mode.findData('redirect')); site.break_minutes.setValue(7); site.redirect_url.setText('https://rest.example.org/')
        self.assertFalse(app.allowance.isHidden()); self.assertTrue(site.allowance.isHidden()); card.consent.setChecked(True)
        self.app.save_budgets(); self.assertFalse(self.app.budget_error.text())
        saved=self.store.settings().restriction_plans[key]['steps'][0]['targets']
        self.assertEqual((saved['app']['break_mode'],saved['app']['break_minutes'],saved['app']['extension_minutes']),('close',2,3))
        self.assertEqual((saved['site']['break_mode'],saved['site']['break_minutes']),('redirect',7))
        editor.show_editor(key); card=editor.steps.cards[0]
        self.assertEqual(card.targets['app'].extra.value(),3); self.assertEqual(card.targets['site'].break_minutes.value(),7)
        self.assertEqual(card.targets['site'].redirect_url.text(),'https://rest.example.org/')

    def test_warning_settings_are_independent_and_cancel_restores_saved_values(self):
        editor,card=self.mixed(); key=editor.current
        card.targets['app'].popup.setChecked(False); card.targets['site'].sound.setChecked(False)
        self.app.save_budgets(); self.assertFalse(self.app.budget_error.text())
        saved=deepcopy(self.store.settings().restriction_plans[key])
        self.assertFalse(saved['steps'][0]['targets']['app']['popup']); self.assertFalse(saved['steps'][0]['targets']['site']['sound'])
        editor.show_editor(key); editor.steps.cards[0].targets['app'].enabled.setChecked(False)
        self.app.budget_back.click(); self.app.save_budgets()
        self.assertEqual(self.store.settings().restriction_plans[key],saved)

    def test_regular_site_redirect_does_not_change_application_closure(self):
        editor,card=self.mixed(); key=editor.current; card.kind.setCurrentIndex(card.kind.findData('restrict'))
        app,site=card.targets['app'],card.targets['site']; app.extra.setValue(2)
        site.mode.setCurrentIndex(site.mode.findData('redirect')); site.redirect_url.setText('https://rest.example.org/')
        card.consent.setChecked(True); self.app.save_budgets(); self.assertFalse(self.app.budget_error.text())
        plan=self.store.settings().restriction_plans[key]; used=plan['steps'][0]['offset']
        budget=Budget(key,'Mixed',used+60,used,tuple(editor.rule(key)['members']))
        runtime=self.app.restrictions; runtime.state.update('2026-11-01',1000,[budget],{key:plan})
        entry=runtime.browser_policy({})['restrictions'][0]
        self.assertEqual((entry['kind'],entry['redirect_url']),('redirect','https://rest.example.org/'))
        self.assertFalse(entry['is_break']); self.assertNotIn('break_until',entry)
        self.assertEqual(runtime.state.action(key,'app:fixture.exe'),'cover')
        self.assertEqual(runtime.state.allowance([key],'app:fixture.exe'),2)

    def test_runtime_delivers_only_the_warning_for_the_foreground_type(self):
        from datetime import datetime
        from gametime.tracker import Sample
        from gametime.focus import app_key
        editor,card=self.mixed(); key=editor.current
        card.targets['app'].popup.setChecked(False); card.targets['site'].sound.setChecked(False)
        plan=editor.restriction_plans[key]; used=plan['steps'][0]['offset']
        runtime=self.app.restrictions
        runtime.state.update('2026-11-01',1000,[Budget(key,'Mixed',used+60,used,tuple(editor.rule(key)['members']))],{key:plan})
        game=Sample(datetime.now().astimezone(),100,str(self.exe),'123:456')
        browser=replace(game,path=r'C:\Fixture\browser.exe',identity='124:789')
        def atom(sample,*args):
            return (self.games[0].id,app_key(sample.path),'') if sample.identity==game.identity else ('',app_key(sample.path),'example.com')
        with patch.object(runtime,'prepare'),patch.object(self.app.wellbeing,'atom',side_effect=atom), \
             patch.object(runtime,'show_save_counter'),patch.object(runtime,'process_browser_requests'),patch.object(runtime.audio,'update'), \
             patch('gametime.qt_restrictions.play_notification',return_value=True) as sound,patch.object(self.app,'popup',return_value=True) as popup:
            runtime.tick(game); sound.assert_called_once(); popup.assert_not_called()
            runtime.tick(browser); popup.assert_called_once(); self.assertFalse(popup.call_args.args[0].sound)
            self.assertEqual(sound.call_count,1)


if __name__=='__main__': unittest.main()
