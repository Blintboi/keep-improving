from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import math
import unittest
from unittest.mock import patch
import test_qt_ui as fixture
from gametime.restriction_policy import Budget, new_plan, step
from gametime.session_choices import defaults
from gametime.tracker import Sample
from gametime.wellbeing import target


class ChoiceInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def test_editor_changes_and_save_never_show_detached_controls(self):
        from PySide6.QtCore import QObject,QEvent
        from PySide6.QtWidgets import QWidget
        seen=[]
        class Watch(QObject):
            def eventFilter(self,obj,event):
                if event.type()==QEvent.Show and isinstance(obj,QWidget) and obj.isWindow(): seen.append(type(obj).__name__)
                return False
        self.app.open_budget(member=target('site','example.com'));watch=Watch();self.qt.installEventFilter(watch)
        try:
            editor=self.app.budget_editor;editor.steps.add_step.click();card=editor.steps.cards[-1]
            card.time_mode.setCurrentIndex(card.time_mode.findData('sessions'));card.choices.enabled.setChecked(True)
            card.choices.add.click();self.app.save_budgets();self.pump(.02)
            self.assertEqual(seen,[])
        finally:self.qt.removeEventFilter(watch)

    def test_browser_choices_use_shared_ledger_and_preserve_visit_on_retry(self):
        from gametime.browser_choices import request
        gate,s,current=self.configure_gate(site=True);runtime=self.app.restrictions
        runtime.state.budgets['choice']=replace(runtime.state.budgets['choice'],members=(target('site','example.com'),target('site','example.org')))
        s['session_choice']['allocation']='activity';casual=s['session_choice']['options'][1]['id'];work=s['session_choice']['options'][0]['id']
        def data(n,host='example.com'):return dict(browser='brave',domain=host,visit=f'{n:032x}')
        for n in (1,2):
            d=data(n);self.assertIsNotNone(request(self.app,d)['choice'])
            accept=dict(d,budget='choice',step=s['id'],choice=casual)
            self.assertTrue(request(self.app,accept,True)['accepted']);self.assertTrue(request(self.app,accept,True)['accepted'])
            self.assertIsNone(request(self.app,d)['choice'])
        d=data(3);pending=request(self.app,d)['choice'];self.assertEqual(pending['options'][1]['remaining'],0)
        self.assertFalse(request(self.app,dict(d,budget='choice',step=s['id'],choice=casual),True)['accepted'])
        self.assertEqual(request(self.app,data(4,'example.org'))['choice']['options'][1]['remaining'],2)
        self.assertTrue(request(self.app,dict(d,budget='choice',step=s['id'],choice=work),True)['accepted'])
        self.assertEqual(gate.ledger.counts('choice',s['id'],'2026-11-11'),{casual:2,work:1})
        runtime.state.plans['choice']['steps'].append(step('cover',0,usage=True))
        self.assertTrue(request(self.app,data(5))['blocked'])

    def test_compatible_browser_uses_website_choice_without_native_window(self):
        from unittest.mock import Mock
        gate,s,current=self.configure_gate(site=True)
        bridge=Mock();bridge.uses_site_choices.return_value=True
        with patch.object(self.app,'browser_bridge',bridge):
            self.assertFalse(gate.tick(current,'example.com'));self.assertIsNone(gate.screen)

    def test_native_repeat_delay_survives_return_and_other_restrictions_win(self):
        gate,s,current=self.configure_gate();s['session_choice']['remember_minutes']=5
        work=s['session_choice']['options'][0]['id'];runtime=self.app.restrictions
        self.assertTrue(gate.tick(current,''));self.assertTrue(gate.choose(work))
        other=replace(current,path='',identity='');gate.tick(other,'')
        runtime.state.now=1100;self.assertFalse(gate.tick(current,''))
        runtime.state.now=1400;self.assertFalse(gate.tick(current,''))
        gate.tick(other,'');self.assertTrue(gate.tick(current,''))
        self.assertEqual(gate.ledger.counts('choice',s['id'],'2026-11-11'),{work:1})
        runtime.state.now=1100;runtime.state.plans['choice']['steps'].append(step('cover',0,usage=True))
        self.assertFalse(gate.choose(work))

    def test_browser_repeat_delay_keeps_other_sites_and_limits_independent(self):
        from gametime.browser_choices import request
        gate,s,current=self.configure_gate(site=True);runtime=self.app.restrictions
        runtime.state.budgets['choice']=replace(runtime.state.budgets['choice'],members=(target('site','example.com'),target('site','example.org')))
        s['session_choice']['remember_minutes']=5;work=s['session_choice']['options'][0]['id']
        def data(n,host='example.com'):return dict(browser='brave',domain=host,visit=f'{n:032x}')
        self.assertTrue(request(self.app,dict(data(1),budget='choice',step=s['id'],choice=work),True)['accepted'])
        runtime.state.now=1100;self.assertIsNone(request(self.app,data(2))['choice'])
        self.assertIsNotNone(request(self.app,data(3,'example.org'))['choice'])
        runtime.state.now=1300;self.assertIsNone(request(self.app,data(2))['choice'])
        self.assertIsNotNone(request(self.app,data(4))['choice'])
        self.assertEqual(gate.ledger.counts('choice',s['id'],'2026-11-11'),{work:1})
        runtime.state.plans['choice']['steps'].append(step('cover',0,usage=True))
        self.assertTrue(request(self.app,data(2))['blocked'])

    def test_editor_roundtrip_and_timing_change_in_both_languages(self):
        for language in ('hu','en'):
            self.app.set_language(language)
            self.app.open_budget(member=target('site','example.com'));editor=self.app.budget_editor
            editor.steps.add_step.click();card=editor.steps.cards[-1]
            card.time_mode.setCurrentIndex(card.time_mode.findData('sessions'));card.choices.enabled.setChecked(True)
            self.assertTrue(card.kind.isHidden());self.assertTrue(card.session_limit.isHidden());self.assertTrue(card.consent.isHidden())
            card.choices.remember_minutes.setValue(15)
            card.choices.question.setText('Miért?');card.choices.option_widgets[1][0].setText('Csak úgy')
            card.choices.allocation.setCurrentIndex(card.choices.allocation.findData('activity'))
            card.choices.option_widgets[1][2].setValue(2)
            expected=deepcopy(card.value['session_choice']);key=editor.current
            self.app.save_budgets();self.assertFalse(self.app.budget_error.text())
            self.assertEqual(self.store.settings().restriction_plans[key]['steps'][-1]['session_choice'],expected)
            editor.show_editor(key);card=editor.steps.cards[-1]
            self.assertEqual(card.choices.allocation.currentData(),'activity')
            self.assertEqual(card.choices.remember_minutes.value(),15)
            card.choices.add.click();self.assertEqual(len(card.value['session_choice']['options']),3)
            card.choices.option_widgets[-1][3].click();self.assertEqual(card.value['session_choice'],expected)
            card.choices.enabled.setChecked(False);self.assertNotIn('session_choice',card.value)
            card.choices.enabled.setChecked(True);self.assertEqual(card.value['session_choice'],expected)
            card.time_mode.setCurrentIndex(card.time_mode.findData('clock'));self.assertNotIn('session_choice',card.value)

    def configure_gate(self,site=False):
        runtime=self.app.restrictions;gate=runtime.choices;p=new_plan();s=step('notify',2,popup=True)
        s.update(time_mode='sessions',session_choice=defaults());p['steps']=[s]
        members=(target('site','example.com'),) if site else (target('app',str(self.exe)),)
        b=Budget('choice','Example',math.inf,0,members,day='2026-11-11')
        self.app.settings=replace(self.app.settings,restriction_plans={'choice':p})
        runtime.state.update('2026-11-11',1000,[b],{'choice':p})
        for name,value in [('prepare',None),('legacy_block',False)]:
            mock=patch.object(runtime,name,return_value=value);mock.start();self.addCleanup(mock.stop)
        def position(screen,target,same=False):screen.setGeometry(0,0,650,500);screen.show()
        mock=patch.object(runtime,'position_screen',side_effect=position);mock.start();self.addCleanup(mock.stop)
        for name,result in [('permitted',True),('open_target',123),('restore_target',True),('minimize_target',True)]:
            mock=patch('gametime.qt_choice_runtime.native.'+name,return_value=result);mock.start();self.addCleanup(mock.stop)
        mock=patch('gametime.qt_choice_runtime.win32.k.CloseHandle',return_value=True);mock.start();self.addCleanup(mock.stop)
        mock=patch.object(gate,'owned',return_value=False);self.owned=mock.start();self.addCleanup(mock.stop)
        current=Sample(datetime.now().astimezone(),1000,str(self.exe),'1234:1')
        if site:
            mock=patch.object(self.app.wellbeing,'atom',side_effect=lambda sample,host: ('',sample.path,host) if host else None)
            mock.start();self.addCleanup(mock.stop)
        return gate,s,current

    def test_runtime_depletes_only_limited_choice_no_duplicate_or_overlay_visit(self):
        gate,s,current=self.configure_gate();work,casual=[o['id'] for o in s['session_choice']['options']]
        self.app.focus.previous=(current,'');self.app.tracker.previous=current
        self.assertTrue(gate.tick(current,''));self.assertIsNone(self.app.focus.previous);self.assertIsNone(self.app.tracker.previous)
        token=gate.pending[2]['token'];self.owned.return_value=True
        self.assertTrue(gate.tick(current,''));self.assertEqual(gate.pending[2]['token'],token)
        self.assertTrue(gate.choose(casual));self.assertFalse(gate.choose(casual));self.owned.return_value=False
        self.assertFalse(gate.tick(current,''))
        other=replace(current,path='',identity='');gate.tick(other,'')
        self.assertTrue(gate.tick(current,''));self.assertTrue(gate.choose(casual))
        gate.tick(other,'');self.assertTrue(gate.tick(current,''))
        self.assertFalse(gate.screen.choice_buttons[casual].isEnabled());self.assertTrue(gate.screen.choice_buttons[work].isEnabled())
        self.app.set_language('en');gate.present()
        self.assertEqual(gate.screen.windowTitle(),'Opening choice')
        self.assertEqual(gate.screen.leave_button.text(),'Use another application')
        self.assertFalse(gate.choose(casual));self.assertTrue(gate.choose(work))
        self.assertEqual(gate.ledger.counts('choice',s['id'],'2026-11-11'),{casual:2,work:1})

    def test_cancel_no_charge_and_new_restriction_prevents_acceptance(self):
        gate,s,current=self.configure_gate();gate.tick(current,'');gate.leave()
        self.assertEqual(gate.ledger.counts('choice',s['id'],'2026-11-11'),{})
        gate.tick(current,'');self.app.restrictions.state.plans['choice']['steps'].append(step('cover',0,usage=True))
        self.assertFalse(gate.choose(s['session_choice']['options'][0]['id']))
        self.assertEqual(gate.ledger.counts('choice',s['id'],'2026-11-11'),{})

    def test_site_scope_changes_end_visit_and_target_disable_is_respected(self):
        gate,s,current=self.configure_gate(site=True)
        self.assertTrue(gate.tick(current,'example.com'));self.assertTrue(gate.choose(s['session_choice']['options'][0]['id']))
        self.assertFalse(gate.tick(current,''))
        self.assertFalse(gate.tick(current,'example.com'))

        self.assertFalse(gate.tick(current,'elsewhere.test'));self.assertTrue(gate.tick(current,'example.com'))
        gate.reset();s['targets']={'site':{'enabled':False}}
        self.assertFalse(gate.tick(current,'example.com'))

    def test_separate_site_allowances_route_counts_to_the_matching_member(self):
        gate,s,current=self.configure_gate(site=True);runtime=self.app.restrictions
        runtime.state.budgets['choice']=replace(runtime.state.budgets['choice'],members=(target('site','example.com'),target('site','example.org')))
        s['session_choice']['allocation']='activity';casual=s['session_choice']['options'][1]['id']
        for host in ('example.com','example.org','example.com'):
            self.assertTrue(gate.tick(current,host));self.assertTrue(gate.choose(casual))
        self.assertTrue(gate.tick(current,'example.org'))
        self.assertTrue(gate.screen.choice_buttons[casual].isEnabled());self.assertTrue(gate.choose(casual))
        self.assertTrue(gate.tick(current,'example.com'));self.assertFalse(gate.screen.choice_buttons[casual].isEnabled())
        self.assertEqual(gate.ledger.counts('choice',s['id'],'2026-11-11','site:example.com'),{casual:2})
        self.assertEqual(gate.ledger.counts('choice',s['id'],'2026-11-11','site:example.org'),{casual:2})
