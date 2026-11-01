"""Action editor integration with temp profiles; native effects are mocked."""
from dataclasses import replace
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch
import test_qt_ui as fixture
from gametime.restriction_policy import new_plan, step
from gametime.tracker import Sample


class StepsInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def test_new_application_action_has_only_one_restriction_choice(self):
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games')
        editor.steps.add_step.click(); card=editor.steps.cards[0]
        self.assertEqual([card.kind.itemData(i) for i in range(card.kind.count())],['notify','restrict','break'])
        card.kind.setCurrentIndex(card.kind.findData('restrict'))
        self.assertEqual(card.extra.value(),5)
        self.assertFalse(card.allowance.isHidden()); self.assertFalse(card.consent.isHidden())

    def test_website_has_one_restriction_and_zero_stays_numeric_in_both_languages(self):
        from gametime.wellbeing import target
        self.app.open_budget(member=target('site','example.com')); editor=self.app.budget_editor
        editor.steps.add_step.click(); card=editor.steps.cards[0]
        self.assertEqual([card.kind.itemData(i) for i in range(card.kind.count())],['notify','restrict','break'])
        card.kind.setCurrentIndex(card.kind.findData('restrict'))
        for language in ('hu','en'):
            self.app.set_language(language)
            self.assertEqual(card.extra.text(),'0'); self.assertEqual(card.extra.specialValueText(),'')
        self.assertEqual(card.value['kind'],'cover'); self.assertTrue(card.consent.isHidden())
        key=editor.current; self.app.save_budgets()
        self.assertFalse(self.app.budget_error.text())
        self.assertEqual(self.store.settings().restriction_plans[key]['steps'][0]['kind'],'cover')
        editor.show_editor(key); card=editor.steps.cards[0]
        self.assertEqual(card.kind.currentData(),'restrict')

    def test_existing_application_restriction_remains_unchanged_until_edited(self):
        plan=new_plan(); plan['steps']=[step('minimize',60,usage=True)]
        settings=replace(self.app.settings,restriction_plans={'shared-games':plan})
        self.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
        editor=self.app.budget_editor; editor.saved(settings); self.app.open_budget(); editor.show_editor('shared-games')
        card=editor.steps.cards[0]
        self.assertEqual(card.kind.currentData(),'minimize')
        self.assertTrue(card.kind.view().isRowHidden(card.kind.findData('minimize')))
        self.assertEqual(editor.settings(settings).restriction_plans['shared-games'],plan)
        card.kind.setCurrentIndex(card.kind.findData('restrict'))
        self.assertEqual(card.kind.findData('minimize'),-1)
        self.assertEqual(card.value['kind'],'restrict')

    def test_inline_steps_are_opt_in_and_cancel_or_save_with_the_budget(self):
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games')
        blocks=editor.steps; self.assertTrue(blocks.isVisible()); self.assertNotIn('shared-games',editor.restriction_plans)
        self.assertTrue(self.app.schedule_editor.warning.isVisibleTo(editor))
        blocks.add_step.click()
        self.assertTrue(self.app.schedule_editor.warning.isVisibleTo(editor))
        self.assertTrue(editor.restriction_plans['shared-games']['legacy'])
        self.assertIn('shared-games',editor.restriction_plans)
        self.assertEqual(self.store.settings().restriction_plans,{})
        self.app.budget_back.click(); self.assertIn('shared-games',editor.restriction_plans)
        editor.show_editor('shared-games'); editor.cancel_edit(); self.assertEqual(editor.restriction_plans,{})
        editor.show_editor('shared-games'); blocks.add_step.click()
        self.app.save_budgets()
        self.assertIn('shared-games',self.store.settings().restriction_plans)

    def test_legacy_weekly_warnings_restriction_and_bedtime_stay_unchanged(self):
        settings=replace(self.app.settings,restriction_enabled=True,restriction_seconds=7500,
            bedtime_enabled=True,daily_schedules={'0':{'warning_seconds':4800,'limit_seconds':7200,
                                                       'restriction_enabled':True,'restriction_seconds':7800}})
        self.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
        self.app.schedule_editor.saved(settings); editor=self.app.budget_editor; editor.saved(settings)
        self.app.open_budget(); editor.show_editor('shared-games')
        self.assertEqual(self.store.settings(),settings)
        from gametime.computer_periods import split_weekly
        expected=split_weekly(settings); self.app.save_budgets()
        self.assertEqual(self.store.settings(),expected)
        editor.show_editor('shared-games'); editor.steps.add_step.click()
        self.assertEqual(self.store.settings(),expected)
        editor.cancel_edit(); self.app.save_budgets()
        self.assertEqual(self.store.settings(),expected)

    def test_blocks_sort_by_active_use_and_keep_ids_and_other_budgets(self):
        from gametime.wellbeing import target
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games'); blocks=editor.steps
        blocks.add_step.click(); first=blocks.cards[0]; first.minutes.setValue(5); first_id=first.value['id']
        blocks.add_step.click(); later=next(card for card in blocks.cards if card is not first); later.minutes.setValue(20); later_id=later.value['id']
        blocks.add_step.click(); restriction=next(card for card in blocks.cards if card not in (first,later))
        restriction.kind.setCurrentIndex(restriction.kind.findData('restrict')); restriction.consent.setChecked(True); restriction.minutes.setValue(2); self.pump(.03)
        order=[restriction.value['id'],first_id,later_id]
        self.assertEqual([c.value['id'] for c in blocks.cards],order)
        self.assertEqual([s['offset'] for s in editor.restriction_plans['shared-games']['steps']],[120,300,1200])
        self.app.open_budget(member=target('site','example.com')); other=editor.current; editor.steps.add_step.click()
        editor.show_editor('shared-games'); self.app.set_language('en')
        self.assertEqual([c.value['id'] for c in blocks.cards],order)
        self.app.save_budgets(); plans=self.store.settings().restriction_plans
        self.assertEqual([s['offset'] for s in plans['shared-games']['steps']],[120,300,1200])
        self.assertTrue(all(s['time_mode']=='usage' for s in plans['shared-games']['steps'])); self.assertIn(other,plans)

    def test_existing_plan_is_preserved_until_changed_and_can_be_restored(self):
        from copy import deepcopy
        plan=new_plan(); plan['steps']=[step('notify',-37.5,popup=True),step('cover',30)]
        settings=replace(self.app.settings,restriction_plans={'shared-games':deepcopy(plan)})
        self.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
        editor=self.app.budget_editor; editor.saved(settings); self.app.open_budget(); editor.show_editor('shared-games')
        self.assertEqual(editor.settings(settings).restriction_plans['shared-games'],plan)
        editor.steps.restore.click(); self.assertNotIn('shared-games',editor.restriction_plans)
        editor.cancel_edit(); self.app.save_budgets()
        self.assertEqual(self.store.settings().restriction_plans['shared-games'],plan)

    def test_close_before_budget_expiry_requires_consent_on_its_card(self):
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games'); blocks=editor.steps
        blocks.add_step.click(); card=blocks.cards[0]; card.minutes.setValue(10)
        card.kind.setCurrentIndex(card.kind.findData('restrict'))
        self.assertEqual(card.value['offset'],600); self.assertEqual(card.value['time_mode'],'usage')
        self.assertFalse(card.consent.isHidden())
        self.app.save_budgets(); self.assertTrue(self.app.budget_error.text())
        self.assertEqual(self.store.settings().restriction_plans,{})
        card.consent.setChecked(True); self.app.save_budgets()
        plan=self.store.settings().restriction_plans['shared-games']
        self.assertTrue(plan['close_confirmed']); self.assertEqual(plan['steps'][0]['kind'],'restrict')

    def test_allowance_controls_live_on_cover_and_match_other_cover_cards(self):
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games'); blocks=editor.steps
        blocks.add_step.click(); first=blocks.cards[0]; first.kind.setCurrentIndex(first.kind.findData('restrict'))
        self.assertFalse(first.allowance.isHidden()); first.extra.setValue(4)
        self.assertFalse(first.consent.isHidden()); first.consent.setChecked(True)
        blocks.add_step.click(); second=next(c for c in blocks.cards if c is not first)
        second.kind.setCurrentIndex(second.kind.findData('restrict'))
        self.assertEqual(second.extra.value(),4); self.assertTrue(second.consent.isChecked())
        second.extra.setValue(3); self.assertEqual(first.extra.value(),3)
        self.app.save_budgets(); self.assertEqual(self.store.settings().restriction_plans['shared-games']['extension_minutes'],3)

    def test_minimize_action_can_configure_the_same_save_allowance(self):
        plan=new_plan(); plan['steps']=[step('minimize',60,usage=True)]
        settings=replace(self.app.settings,restriction_plans={'shared-games':plan})
        self.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
        editor=self.app.budget_editor; editor.saved(settings); self.app.open_budget(); editor.show_editor('shared-games'); blocks=editor.steps
        card=blocks.cards[0]
        self.assertFalse(card.allowance.isHidden()); card.extra.setValue(4)
        self.assertFalse(card.consent.isHidden())
        self.app.save_budgets(); self.assertTrue(self.app.budget_error.text())
        card.consent.setChecked(True); self.app.save_budgets()
        plan=self.store.settings().restriction_plans['shared-games']
        self.assertEqual((plan['steps'][0]['kind'],plan['extension_minutes'],plan['close_confirmed']),('minimize',4,True))

    def test_minimize_site_policy_offers_save_time_and_reblocks_after_it(self):
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan()
        plan.update(extension_minutes=2,close_confirmed=True,steps=[step('minimize',60,usage=True)])
        budget=Budget('site','Fixture',1000,60,(target('site','example.com'),)); plans={'site':plan}
        runtime.state.update('2026-10-30',1000,[budget],plans)
        entry=runtime.browser_policy({})['restrictions'][0]
        self.assertEqual((entry['kind'],entry['minutes']),('cover',2))
        subject='site:example.com:token'
        self.assertEqual(runtime.state.extend(['site'],subject),1120)
        runtime.state.update('2026-10-30',1120,[budget],plans)
        self.assertEqual(runtime.state.action('site',subject),'cover')

    def test_browser_marks_break_separately_when_a_restriction_overlaps(self):
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        runtime=self.app.restrictions; regular=new_plan(); pause=new_plan()
        regular.update(extension_minutes=2,close_confirmed=True,steps=[step('restrict',60,usage=True)])
        pause.update(close_confirmed=True,steps=[step('break',60,usage=True,break_mode='close',break_minutes=2)])
        members=(target('site','example.com'),)
        budgets=[Budget(key,key,1000,60,members) for key in ('regular','pause')]
        runtime.state.update('2026-10-30',1000,budgets,{'regular':regular,'pause':pause})
        entries={entry['key']:entry for entry in runtime.browser_policy({})['restrictions']}
        self.assertEqual((entries['regular']['kind'],entries['regular']['minutes'],entries['regular']['is_break']),('cover',2,False))
        self.assertNotIn('break_until',entries['regular'])
        self.assertEqual((entries['pause']['kind'],entries['pause']['is_break'],entries['pause']['break_until']),('close',True,1120))

    def test_site_save_grant_still_dominates_break_after_budget_renews(self):
        from gametime.restriction_policy import Budget,RestrictionState
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan()
        plan.update(extension_minutes=3,close_confirmed=True,steps=[step('restrict',60,usage=True),
                    step('break',60,usage=True,break_mode='close',break_minutes=4)])
        members=(target('site','example.com'),); subject='site:example.com:'+'a'*32
        runtime.state.update('2026-10-30',1000,[Budget('web','Web',500,60,members)],{'web':plan})
        runtime.state.extend(['web'],subject)
        runtime.state=RestrictionState(self.store)
        runtime.state.update('2026-10-31',1050,[Budget('web','Web',500,0,members)],{'web':plan})
        entries=runtime.browser_policy({})['restrictions']
        self.assertEqual(len(entries),2)
        self.assertTrue(any(entry.get('grant_only') and entry['grant']['subject']==subject for entry in entries))
        self.assertTrue(any(entry['is_break'] and entry['kind']=='close' for entry in entries))

    def test_same_budget_legacy_game_restriction_allows_its_own_save_grant(self):
        from gametime.focus import app_key
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan(legacy=True)
        plan.update(extension_minutes=2,close_confirmed=True,steps=[step('restrict',60,usage=True)])
        settings=replace(self.app.settings,game_budget_enabled=True,restriction_enabled=True,restriction_seconds=60,
                         restriction_plans={'shared-games':plan})
        self.app.settings=self.app.catalog.settings=settings
        wall=datetime.now().astimezone(); identity='123:456'; path=str(self.exe); game=self.games[0]
        budget=Budget('shared-games','Fixture',1000,60,(target('category','games'),))
        runtime.state.update(wall.date().isoformat(),wall.timestamp(),[budget],settings.restriction_plans)
        atom=(game.id,app_key(path),''); subject='app:'+app_key(path)
        with patch.object(self.app.tracker,'quota_totals',return_value={game.id:60}):
            self.assertTrue(runtime.legacy_block(atom))
            self.assertFalse(runtime.legacy_block(atom,['shared-games']))
            runtime.state.extend(['shared-games'],subject,identity)
            self.assertFalse(self.app.restriction_reached(wall,game,path,identity))
            self.assertTrue(self.app.restriction_reached(wall,game,path,'999:999'))

    def test_legacy_website_rule_delegates_to_its_matching_restriction_only(self):
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import BudgetState,target
        rule={'id':'web','name':'Web','members':[target('site','example.com')],
              'seconds':60,'enabled':True,'enforce':True,'overlay':False}
        runtime=self.app.restrictions; plan=new_plan(legacy=True)
        plan.update(extension_minutes=2,close_confirmed=True,steps=[step('restrict',60,usage=True)])
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[rule],restriction_plans={'web':plan})
        wall=datetime.now().astimezone(); budget=Budget('web','Web',60,60,tuple(rule['members']))
        runtime.state.update(wall.date().isoformat(),wall.timestamp(),[budget],{'web':plan})
        with patch.object(self.app.wellbeing,'states',return_value=[BudgetState(rule,60)]):
            self.assertTrue(self.app.wellbeing.policy(self.app.focus.policy(),wall)['active'])
            base=self.app.wellbeing.policy(self.app.focus.policy(),wall,runtime.delegated_website_rules())
            self.assertFalse(base['active'])
            entry=runtime.browser_policy(base)['restrictions'][0]
            self.assertEqual((entry['key'],entry['kind'],entry['minutes']),('web','cover',2))
            from threading import Event
            from unittest.mock import Mock
            answer={}; event=Event(); self.app.browser_bridge=Mock()
            self.app.browser_bridge.take_requests.return_value=[({'domain':'example.com','token':'a'*32},answer,event)]
            with patch.object(runtime,'prepare'),patch.object(self.app,'update_focus_policy'):
                runtime.process_browser_requests()
            self.assertTrue(event.is_set()); self.assertTrue(answer['ok'])
        other=dict(rule,id='other')
        with patch.object(self.app.wellbeing,'states',return_value=[BudgetState(rule,60),BudgetState(other,60)]):
            self.assertTrue(self.app.wellbeing.policy(self.app.focus.policy(),wall,runtime.delegated_website_rules())['active'])

    def test_app_save_grant_does_not_expose_process_identity_to_browser(self):
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan()
        plan.update(extension_minutes=2,close_confirmed=True,steps=[step('restrict',60,usage=True)])
        members=(target('app',str(self.exe)),target('site','example.com'))
        budget=Budget('mixed','Fixture',1000,60,members); plans={'mixed':plan}
        runtime.state.update('2026-10-30',1000,[budget],plans)
        runtime.state.extend(['mixed'],'app:c:\\private\\app.exe','123:456')
        entry=runtime.browser_policy({})['restrictions'][0]
        self.assertIsNone(entry['grant'])
        self.assertNotIn('private',str(entry)); self.assertNotIn('123:456',str(entry))

    def test_minimize_offers_save_then_closes_the_same_application(self):
        from gametime.focus import app_key
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan()
        plan.update(extension_minutes=2,close_confirmed=True,steps=[step('minimize',60,usage=True)])
        member=target('app',str(self.exe)); atom=('',member['value'],'')
        budget=Budget('app','Fixture',1000,60,(member,)); plans={'app':plan}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_plans=plans)
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'123:456')
        runtime.state.update('2026-10-30',1000,[budget],plans)
        with patch.object(runtime,'prepare'),patch.object(runtime,'legacy_block',return_value=False), \
             patch.object(self.app.wellbeing,'atom',return_value=atom),patch.object(self.app,'minimization_allowed',return_value=True), \
             patch('gametime.qt_restrictions.native.permitted',return_value=True),patch('gametime.qt_restrictions.native.open_target',return_value=1), \
             patch('gametime.qt_restrictions.win32.k.CloseHandle'),patch('gametime.qt_restrictions.win32.minimize_game') as minimize, \
             patch.object(runtime,'present') as present,patch.object(runtime,'close_target') as close, \
             patch.object(runtime,'show_save_counter'),patch.object(runtime,'process_browser_requests'),patch.object(runtime.audio,'update'),patch.object(self.app,'update_focus_policy'):
            runtime.tick(current)
            present.assert_called_once(); minimize.assert_not_called()
            subject='app:'+app_key(current.path)
            self.assertEqual(runtime.extend(['app'],subject),1120)
            self.assertEqual(runtime.state.rows['app']['grant']['identity'],current.identity)
            runtime.state.update('2026-10-30',1060,[budget],plans); runtime.tick(current)
            close.assert_not_called()
            runtime.state.update('2026-10-30',1120,[budget],plans); runtime.tick(current)
            close.assert_called_once_with(current,['app'])

    def test_previous_minimize_without_allowance_stays_a_minimize(self):
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan(); plan['steps']=[step('minimize',60,usage=True)]
        member=target('app',str(self.exe)); atom=('',member['value'],'')
        budget=Budget('app','Fixture',1000,60,(member,)); plans={'app':plan}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_plans=plans)
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'123:456')
        runtime.state.update('2026-10-30',1000,[budget],plans)
        with patch.object(runtime,'prepare'),patch.object(self.app.wellbeing,'atom',return_value=atom), \
             patch.object(self.app,'minimization_allowed',return_value=True), \
             patch('gametime.qt_restrictions.win32.minimize_game') as minimize,patch.object(runtime,'present') as present, \
             patch.object(runtime,'show_save_counter'),patch.object(runtime,'process_browser_requests'),patch.object(runtime.audio,'update'):
            runtime.tick(current)
        minimize.assert_called_once_with(current.path,current.identity,consented=True); present.assert_not_called()

    def test_application_restriction_takes_priority_over_an_overlapping_break(self):
        from gametime.focus import app_key
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        runtime=self.app.restrictions; regular=new_plan(); pause=new_plan()
        regular.update(extension_minutes=2,close_confirmed=True,steps=[step('restrict',60,usage=True)])
        pause.update(close_confirmed=True,steps=[step('break',60,usage=True,break_mode='close',break_minutes=2)])
        member=target('app',str(self.exe)); atom=('',member['value'],'')
        budgets=[Budget(key,key,1000,60,(member,)) for key in ('regular','pause')]; plans={'regular':regular,'pause':pause}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_plans=plans)
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'123:456')
        runtime.state.update('2026-10-30',1000,budgets,plans)
        with patch.object(runtime,'prepare'),patch.object(runtime,'legacy_block',return_value=False), \
             patch.object(self.app.wellbeing,'atom',return_value=atom),patch('gametime.qt_restrictions.native.open_target',return_value=1), \
             patch('gametime.qt_restrictions.win32.k.CloseHandle'),patch.object(runtime,'present') as present, \
             patch.object(runtime,'close_target') as close,patch.object(runtime,'show_save_counter'), \
             patch.object(runtime,'process_browser_requests'),patch.object(runtime.audio,'update'),patch.object(self.app,'update_focus_policy'):
            runtime.tick(current)
            self.assertEqual(present.call_args.args[1],['regular']); close.assert_not_called()
            subject='app:'+app_key(current.path)
            self.assertEqual(runtime.extend(['regular'],subject),1120)
            runtime.state.update('2026-10-30',1050,budgets,plans); runtime.tick(current)
            close.assert_not_called(); self.assertEqual(runtime.state.break_remaining('pause'),70)
            runtime.state.update('2026-10-30',1120,budgets,plans); runtime.tick(current)
            close.assert_called_once_with(current,['regular'])

    def test_save_grant_is_recovered_after_restart_and_closes_in_background(self):
        from gametime.focus import app_key
        from gametime.restriction_policy import Budget,RestrictionState
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan()
        plan.update(extension_minutes=2,close_confirmed=True,steps=[step('restrict',60,usage=True)])
        member=target('app',str(self.exe)); start=datetime(2026,10,30,23,59,30).astimezone()
        subject='app:'+app_key(str(self.exe)); identity='123:456'; plans={'app':plan}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_plans=plans)
        initial=Budget('app','Fixture',1000,60,(member,),day='2026-10-30')
        runtime.state.update('2026-10-30',start.timestamp(),[initial],plans)
        runtime.state.extend(['app'],subject,identity)
        runtime.state=RestrictionState(self.store); runtime.targets.clear(); runtime._clock=None; runtime._max_now=0
        def budgets(wall): return [Budget('app','Fixture',1000,0,(member,),day=wall.date().isoformat())]
        other=Sample(start+timedelta(seconds=90),100,r'C:\Apps\other.exe','999:111')
        atom=('',member['value'],'')
        with patch.object(runtime,'budgets',side_effect=budgets),patch.object(self.app.wellbeing,'atom',side_effect=lambda sample,*args: atom if sample.identity==identity else None), \
             patch('gametime.qt_restrictions.native.open_target',return_value=1),patch('gametime.qt_restrictions.win32.k.CloseHandle'), \
             patch.object(runtime,'close_target') as close,patch.object(runtime,'show_save_counter'), \
             patch.object(runtime,'process_browser_requests'),patch.object(runtime.audio,'update'):
            runtime.tick(other); close.assert_not_called()
            runtime.tick(replace(other,wall=start+timedelta(seconds=121)))
            self.assertEqual(close.call_count,1)
            self.assertEqual(close.call_args.args[0].identity,identity)
            self.assertEqual(close.call_args.args[1],['app'])

    def test_temporary_process_access_failure_does_not_cancel_save_grant(self):
        from gametime.focus import app_key
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan()
        plan.update(extension_minutes=2,close_confirmed=True,steps=[step('restrict',60,usage=True)])
        member=target('app',str(self.exe)); atom=('',member['value'],''); identity='123:456'
        budget=Budget('app','Fixture',1000,60,(member,)); plans={'app':plan}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_plans=plans)
        current=Sample(datetime.now().astimezone(),100,str(self.exe),identity); subject='app:'+app_key(current.path)
        runtime.state.update('2026-10-30',1000,[budget],plans); runtime.state.extend(['app'],subject,identity)
        with patch.object(runtime,'prepare'),patch.object(self.app.wellbeing,'atom',return_value=atom), \
             patch('gametime.qt_restrictions.native.open_target',return_value=None), \
             patch('gametime.qt_restrictions.win32.process_image',return_value=(str(self.exe),identity)), \
             patch.object(runtime,'show_save_counter'),patch.object(runtime,'process_browser_requests'),patch.object(runtime.audio,'update'):
            runtime.tick(current)
        self.assertIsNotNone(runtime.state.grant('app',subject,identity))
        self.assertIn(identity,runtime.failed)

    def test_recovery_does_not_reactivate_an_excluded_application(self):
        from gametime.focus import app_key
        from gametime.restriction_policy import Budget,RestrictionState
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan()
        plan.update(extension_minutes=2,close_confirmed=True,steps=[step('restrict',60,usage=True)])
        member=target('app',str(self.exe)); wall=datetime.now().astimezone(); subject='app:'+app_key(str(self.exe))
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_plans={'app':plan})
        budget=Budget('app','Fixture',1000,60,(member,)); plans={'app':plan}
        runtime.state.update(wall.date().isoformat(),wall.timestamp(),[budget],plans)
        runtime.state.extend(['app'],subject,'123:456')
        runtime.state=RestrictionState(self.store); runtime.targets.clear(); runtime._clock=None; runtime._max_now=0
        with patch.object(runtime,'budgets',return_value=[budget]),patch.object(self.app.wellbeing,'atom',return_value=None):
            runtime.prepare(wall)
        self.assertNotIn('123:456',runtime.targets)

    def test_break_card_saves_interval_duration_mode_and_close_consent(self):
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games'); blocks=editor.steps
        blocks.add_step.click(); card=blocks.cards[0]; card.kind.setCurrentIndex(card.kind.findData('break'))
        card.minutes.setValue(30); card.break_minutes.setValue(10); card.break_mode.setCurrentIndex(card.break_mode.findData('cover'))
        self.assertFalse(card.break_controls.isHidden()); self.assertTrue(card.consent.isHidden())
        self.app.save_budgets(); saved=self.store.settings().restriction_plans['shared-games']['steps'][0]
        self.assertEqual((saved['kind'],saved['offset'],saved['break_mode'],saved['break_minutes']),('break',1800,'cover',10))
        editor.show_editor('shared-games'); card=blocks.cards[0]
        self.assertEqual((card.minutes.value(),card.break_minutes.value(),card.break_mode.currentData()),(30,10,'cover'))
        card.break_mode.setCurrentIndex(card.break_mode.findData('close')); self.assertFalse(card.consent.isHidden())
        self.assertFalse(card.allowance.isHidden()); card.extra.setValue(4)
        self.app.save_budgets(); self.assertTrue(self.app.budget_error.text())
        card.consent.setChecked(True); self.app.save_budgets()
        self.assertEqual(self.store.settings().restriction_plans['shared-games']['steps'][0]['break_mode'],'close')
        self.assertEqual(self.store.settings().restriction_plans['shared-games']['extension_minutes'],4)
        editor.show_editor('shared-games'); card=blocks.cards[0]
        self.assertEqual(card.extra.value(),4); self.assertFalse(card.allowance.isHidden())
        card.break_mode.setCurrentIndex(card.break_mode.findData('cover')); self.assertTrue(card.allowance.isHidden())

    def test_previous_close_action_can_configure_save_time_on_its_card(self):
        plan=new_plan(); plan.update(close_confirmed=True,steps=[step('close',60,usage=True)])
        settings=replace(self.app.settings,restriction_plans={'shared-games':plan})
        self.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
        editor=self.app.budget_editor; editor.saved(settings); self.app.open_budget(); editor.show_editor('shared-games')
        card=editor.steps.cards[0]; self.assertFalse(card.allowance.isHidden()); card.extra.setValue(2)
        self.app.save_budgets(); saved=self.store.settings().restriction_plans['shared-games']
        self.assertEqual(saved['extension_minutes'],2); self.assertEqual(saved['steps'][0]['kind'],'close')

    def test_closing_break_offers_time_then_closes_the_same_process_after_expiry(self):
        from gametime.focus import app_key
        from gametime.restriction_policy import Budget,RestrictionState
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan()
        plan.update(extension_minutes=2,close_confirmed=True,steps=[step('break',60,usage=True,break_mode='close',break_minutes=1)])
        member=target('app',str(self.exe)); atom=('',member['value'],'')
        budget=Budget('app','Fixture',1000,60,(member,)); plans={'app':plan}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_plans=plans)
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'123:456')
        runtime.state.update('2026-10-30',1000,[budget],plans)
        with patch.object(runtime,'prepare'),patch.object(runtime,'legacy_block',return_value=False), \
             patch.object(self.app.wellbeing,'atom',return_value=atom),patch('gametime.qt_restrictions.native.open_target',return_value=1), \
             patch('gametime.qt_restrictions.win32.k.CloseHandle'),patch.object(runtime,'present') as present, \
             patch.object(runtime,'close_target') as close,patch.object(runtime,'show_save_counter'), \
             patch.object(runtime,'process_browser_requests'),patch.object(runtime.audio,'update') as audio,patch.object(self.app,'update_focus_policy'):
            runtime.tick(current); present.assert_called_once(); close.assert_not_called()
            self.assertEqual(runtime.extend(['app'],'app:'+app_key(current.path)),1120)
            runtime.state=RestrictionState(self.store)
            runtime.state.update('2026-10-30',1060,[budget],plans); runtime.tick(current)
            close.assert_not_called(); audio.assert_called_with([])
            runtime.state.update('2026-10-30',1120,[budget],plans); runtime.tick(current)
            close.assert_called_once_with(current,['app'])

    def test_shared_break_respects_a_bedtime_cap(self):
        plan=new_plan(); plan['steps']=[step('break',60,usage=True,break_minutes=2)]
        settings=replace(self.app.settings,game_budget_enabled=True,bedtime_enabled=True,
                         bedtime_caps_budget=True,restriction_plans={'shared-games':plan})
        self.app.settings=self.app.catalog.settings=settings
        wall=datetime(2026,10,30,0,30).astimezone()
        with patch.object(self.app.tracker,'quota_totals',return_value={self.games[0].id:60}):
            budgets=self.app.restrictions.budgets(wall)
        shared=next(item for item in budgets if item.key=='shared-games')
        self.assertFalse(shared.breaks_allowed)
        self.app.restrictions.state.update('2026-10-29',1000,budgets,settings.restriction_plans)
        self.assertEqual(self.app.restrictions.state.action('shared-games','app:test.exe'),'')

    def test_break_browser_policy_blocks_only_during_break_and_offers_no_bypass(self):
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan()
        plan['steps']=[step('break',60,usage=True,break_mode='cover',break_minutes=2)]
        key='site'; budget=Budget(key,'Fixture',1000,60,(target('site','example.com'),))
        runtime.state.update('2026-10-30',1000,[budget],{key:plan})
        entries=runtime.browser_policy({})['restrictions']
        self.assertEqual(len(entries),1); self.assertEqual(entries[0]['kind'],'cover'); self.assertEqual(entries[0]['minutes'],0); self.assertEqual(entries[0]['break_until'],1120)
        runtime.state.update('2026-10-30',1120,[budget],{key:plan})
        self.assertEqual(runtime.browser_policy({})['restrictions'],[])

    def test_site_break_redirect_requires_and_persists_a_valid_address(self):
        from gametime.wellbeing import target
        editor=self.app.budget_editor; self.app.open_budget(member=target('site','example.com'))
        key=editor.current; blocks=editor.steps; blocks.add_step.click(); card=blocks.cards[0]
        card.kind.setCurrentIndex(card.kind.findData('break'))
        card.break_mode.setCurrentIndex(card.break_mode.findData('redirect'))
        self.assertFalse(card.redirect_controls.isHidden())
        card.redirect_url.setText('javascript:alert(1)'); self.app.save_budgets()
        self.assertTrue(self.app.budget_error.text()); self.assertNotIn(key,self.store.settings().restriction_plans)
        card.redirect_url.setText('https://rest.example.org/path'); self.app.save_budgets()
        saved=self.store.settings().restriction_plans[key]['steps'][0]
        self.assertEqual((saved['break_mode'],saved['redirect_url']),('redirect','https://rest.example.org/path'))
        editor.show_editor(key); card=blocks.cards[0]
        self.assertEqual(card.redirect_url.text(),'https://rest.example.org/path')

    def test_redirect_is_in_browser_policy_only_while_break_is_active(self):
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan()
        pause=step('break',60,usage=True,break_mode='redirect',break_minutes=2)
        pause['redirect_url']='https://rest.example.org/'; plan['steps']=[pause]
        budget=Budget('site','Fixture',1000,60,(target('site','example.com'),))
        runtime.state.update('2026-10-30',1000,[budget],{'site':plan})
        entry=runtime.browser_policy({})['restrictions'][0]
        self.assertEqual((entry['kind'],entry['redirect_url'],entry['break_until']),('redirect','https://rest.example.org/',1120))
        runtime.state.update('2026-10-30',1120,[budget],{'site':plan})
        self.assertEqual(runtime.browser_policy({})['restrictions'],[])

    def test_empty_redirect_address_is_saved_and_published_as_new_tab(self):
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        editor=self.app.budget_editor; self.app.open_budget(member=target('site','example.com'))
        key=editor.current; blocks=editor.steps; blocks.add_step.click(); card=blocks.cards[0]
        card.kind.setCurrentIndex(card.kind.findData('break'))
        card.break_mode.setCurrentIndex(card.break_mode.findData('redirect'))
        self.assertEqual(card.redirect_url.text(),'')
        self.app.save_budgets()
        plan=self.store.settings().restriction_plans[key]
        self.assertEqual(plan['steps'][0]['redirect_url'],'')
        budget=Budget(key,'Fixture',10000,plan['steps'][0]['offset'],(target('site','example.com'),))
        self.app.restrictions.state.update('2026-10-30',1000,[budget],{key:plan})
        entry=self.app.restrictions.browser_policy({})['restrictions'][0]
        self.assertEqual((entry['kind'],entry['redirect_url']),('redirect',''))

    def test_mixed_redirect_break_covers_and_mutes_native_members_then_releases(self):
        from gametime.focus import app_key
        from gametime.restriction_policy import Budget
        from gametime.wellbeing import target
        runtime=self.app.restrictions; plan=new_plan()
        pause=step('break',60,usage=True,break_mode='redirect',break_minutes=2)
        pause['redirect_url']='https://rest.example.org/'; plan['steps']=[pause]
        game=self.games[0]; editor_path=r'C:\Fixture\editor.exe'; browser_path=r'C:\Fixture\browser.exe'
        members=(target('game',game.id),target('app',editor_path),target('site','example.com'))
        budget=Budget('mixed','Mixed break',1000,60,members); plans={'mixed':plan}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_plans=plans)
        wall=datetime.now().astimezone()
        game_sample=Sample(wall,100,str(self.exe),'123:456')
        editor_sample=Sample(wall,101,editor_path,'124:456')
        browser_sample=Sample(wall,102,browser_path,'125:456')
        atoms={game_sample.identity:(game.id,app_key(str(self.exe)),''),
               editor_sample.identity:('',app_key(editor_path),''),
               browser_sample.identity:('',app_key(browser_path),'example.com')}
        runtime.state.update('2026-10-30',1000,[budget],plans)
        with patch.object(runtime,'prepare'),patch.object(self.app.wellbeing,'atom',side_effect=lambda sample,*args:atoms[sample.identity]), \
             patch('gametime.qt_restrictions.native.open_target',return_value=1),patch('gametime.qt_restrictions.win32.k.CloseHandle'), \
             patch.object(runtime,'present') as present,patch.object(runtime,'close_target') as close, \
             patch.object(runtime,'show_save_counter'),patch.object(runtime,'process_browser_requests'),patch.object(runtime.audio,'update') as audio:
            for sample in (game_sample,editor_sample):
                self.assertTrue(runtime.tick(sample))
                present.assert_called_with(sample,['mixed'],'app:'+app_key(sample.path),atoms[sample.identity])
            audio.assert_called_with([{'path':s.path,'identity':s.identity} for s in (game_sample,editor_sample)])
            present.reset_mock()
            self.assertFalse(runtime.tick(browser_sample)); present.assert_not_called()
            audio.assert_called_with([{'path':s.path,'identity':s.identity} for s in (game_sample,editor_sample)])
            entry=runtime.browser_policy({})['restrictions'][0]
            self.assertEqual((entry['kind'],entry['redirect_url'],entry['break_until']),('redirect',pause['redirect_url'],1120))
            runtime.state.update('2026-10-30',1120,[budget],plans)
            self.assertFalse(runtime.tick(game_sample)); present.assert_not_called(); close.assert_not_called()
            audio.assert_called_with([])
            self.assertEqual(runtime.browser_policy({})['restrictions'],[])

    def test_old_timing_stays_unchanged_until_explicit_conversion(self):
        plan=new_plan(); plan['steps']=[step('notify',-300,popup=True),step('minimize',300)]
        settings=replace(self.app.settings,restriction_plans={'shared-games':plan})
        self.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
        editor=self.app.budget_editor; editor.saved(settings); self.app.open_budget(); editor.show_editor('shared-games')
        self.assertFalse(editor.steps.cards[0].old_time.isHidden())
        self.app.save_budgets(); self.assertEqual(self.store.settings().restriction_plans['shared-games'],plan)
        editor.show_editor('shared-games'); card=editor.steps.cards[1]; minutes=card.minutes.value(); card.convert_time.click()
        self.app.save_budgets(); saved=self.store.settings().restriction_plans['shared-games']['steps']
        self.assertEqual(saved[1]['time_mode'],'usage'); self.assertEqual(saved[1]['offset'],minutes*60)

    def test_too_many_steps_are_bounded_and_deleting_a_step_updates_the_order(self):
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games'); blocks=editor.steps
        for _ in range(20): blocks.add_step.click()
        self.assertEqual(len(blocks.cards),20); self.assertFalse(blocks.add_step.isEnabled())
        deleted=blocks.cards[0].value['id']; blocks.cards[0].remove.click()
        self.assertTrue(blocks.add_step.isEnabled()); self.assertNotIn(deleted,[s['id'] for s in editor.restriction_plans['shared-games']['steps']])
        self.assertEqual([c.number.text() for c in blocks.cards],[str(i)+'.' for i in range(2,21)])

    def test_legacy_blocks_remain_independent_and_ordered(self):
        settings=replace(self.app.settings,restriction_enabled=True,restriction_seconds=7500)
        self.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
        self.app.schedule_editor.saved(settings); editor=self.app.budget_editor; editor.saved(settings)
        self.app.open_budget(); editor.show_editor('shared-games'); blocks=editor.steps
        self.assertTrue(blocks.legacy_warning_card.isVisibleTo(editor))
        self.assertTrue(blocks.legacy_restrict_card.isVisibleTo(editor))
        blocks.add_step.click(); custom=blocks.cards[0]; custom.minutes.setValue(10); self.pump(.03)
        self.assertEqual((blocks.legacy_warning_card.number.text(),custom.number.text(),blocks.legacy_restrict_card.number.text()),('2.','1.','3.'))
        blocks.remove_legacy_warning(); self.assertTrue(blocks.legacy_warning_card.isHidden())
        self.assertTrue(editor.restriction_plans['shared-games']['legacy'])
        self.assertFalse(editor.restriction_plans['shared-games']['legacy_warning'])
        self.app.save_budgets(); now=datetime.now().astimezone()
        with patch.object(self.app.tracker,'quota_day_totals',return_value={self.games[0].id:8000}):
            self.assertTrue(self.app.restriction_reached(now,self.games[0]))

    def test_removed_warning_does_not_prevent_a_shorter_daily_budget(self):
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games')
        editor.steps.remove_legacy_warning(); self.app.schedule_editor.limit.setValue(60)
        self.app.save_budgets()
        self.assertFalse(self.app.budget_error.text())
        self.assertEqual(self.store.settings().limit_seconds,3600)
        self.assertFalse(self.store.settings().restriction_plans['shared-games']['legacy_warning'])

    def test_old_activity_restriction_is_a_removable_action_and_cancel_preserves_it(self):
        from gametime.qt_budgets import new_rule
        from gametime.wellbeing import target
        from PySide6.QtWidgets import QCheckBox,QPushButton
        rule=new_rule('Fixture',[target('site','example.com')],'fixture-rule'); rule.update(enabled=True,enforce=True)
        settings=replace(self.app.settings,wellbeing_rules=[rule])
        self.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
        editor=self.app.budget_editor; editor.saved(settings); self.app.open_budget(); editor.show_editor(rule['id'])
        self.assertFalse(any(c.text()==self.app.t('Restrict after the budget runs out') for c in editor.findChildren(QCheckBox)))
        self.assertFalse(hasattr(editor,'details'))
        self.assertFalse(editor.steps.legacy_single_card.isHidden())
        trash=next(b for b in editor.steps.legacy_single_card.findChildren(QPushButton) if b.accessibleName()==self.app.t('Remove step'))
        trash.click(); self.assertTrue(editor.steps.legacy_single_card.isHidden()); self.assertTrue(self.store.settings().wellbeing_rules[0]['enforce'])
        editor.cancel_edit(); editor.show_editor(rule['id']); self.assertFalse(editor.steps.legacy_single_card.isHidden())
        next(b for b in editor.steps.legacy_single_card.findChildren(QPushButton) if b.accessibleName()==self.app.t('Remove step')).click()
        self.app.save_budgets(); self.assertFalse(self.store.settings().wellbeing_rules[0]['enforce'])
        self.assertEqual(self.store.settings().wellbeing_rules[0]['members'],rule['members'])

    def test_old_game_restriction_can_be_removed_without_removing_its_budget_or_adding_alert(self):
        from PySide6.QtWidgets import QPushButton
        from gametime.restriction_policy import legacy_active,legacy_restriction_active
        game=self.games[0]; settings=replace(self.app.settings,game_budget_enabled=False,game_limits={game.id:60})
        self.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
        editor=self.app.budget_editor; editor.saved(settings); self.app.open_budget(); editor.show_editor('game:'+game.id)
        self.assertFalse(editor.steps.legacy_single_card.isHidden())
        with patch.object(self.app.tracker,'quota_day_totals',return_value={game.id:60}):
            self.assertTrue(self.app.restriction_reached(game=game))
        next(b for b in editor.steps.legacy_single_card.findChildren(QPushButton) if b.accessibleName()==self.app.t('Remove step')).click()
        self.app.save_budgets(); saved=self.store.settings(); key='game:'+game.id
        self.assertEqual(saved.game_limits[game.id],60)
        self.assertTrue(legacy_active(saved.restriction_plans,key)); self.assertFalse(legacy_restriction_active(saved.restriction_plans,key))
        with patch.object(self.app.tracker,'quota_day_totals',return_value={game.id:60}):
            self.assertFalse(self.app.restriction_reached(game=game))
        self.app.tracker.active=game; self.app.tracker.identity='fixture:game'
        with patch.object(self.app.tracker,'quota_totals',return_value={game.id:60}):
            self.app.tracker.evaluate(datetime.now().astimezone())
        self.assertFalse(any(alert.game_id==game.id for alert in self.app.tracker.alerts))
        editor.show_editor(key); self.assertTrue(editor.steps.legacy_single_card.isHidden())
        editor.steps.add_step.click(); editor.steps.cards[0].kind.setCurrentIndex(editor.steps.cards[0].kind.findData('restrict'))
        editor.steps.cards[0].consent.setChecked(True)
        self.app.save_budgets(); self.assertEqual(self.store.settings().restriction_plans[key]['steps'][0]['kind'],'restrict')

    def test_computer_period_is_separate_and_changes_do_not_replace_game_settings(self):
        from PySide6.QtCore import QTime
        from gametime.schedule import week_plans
        settings=replace(self.app.settings,bedtime_enabled=True,bedtime_minimize=True)
        self.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
        self.app.schedule_editor.saved(settings); editor=self.app.budget_editor; editor.saved(settings)
        self.app.open_budget(); self.assertIn('computer-window',editor.row_keys)
        editor.show_editor('computer-window'); schedule=self.app.schedule_editor
        self.assertTrue(schedule.day_details.isHidden()); self.assertTrue(schedule.controls.isHidden())
        self.assertIs(editor.access.widget.parent(),schedule)
        schedule.bedtime_times['bedtime_minute'].setTime(QTime(22,0))
        schedule.bedtime_times['bedtime_resume_minute'].setTime(QTime(7,0))
        self.app.save_budgets(); saved=self.store.settings(); plans=week_plans(saved)
        self.assertTrue(all((p['bedtime_minute'],p['bedtime_resume_minute'])==(1320,420) for p in plans.values()))
        self.assertEqual(saved.limit_seconds,settings.limit_seconds); self.assertEqual(saved.warning_seconds,settings.warning_seconds)
        editor.show_editor('computer-window'); editor.remove_budget('computer-window'); self.app.save_budgets()
        self.assertTrue(all(not p['bedtime_enabled'] for p in week_plans(self.store.settings()).values()))
        self.assertEqual(self.store.settings().limit_seconds,settings.limit_seconds)

    def test_many_blocks_scroll_without_hiding_save_or_creating_horizontal_scroll(self):
        import time
        from PySide6.QtCore import QPoint
        self.app.resize(1020,740); self.app.show(); self.app.open_budget()
        self.app.budget_editor.show_editor('shared-games'); blocks=self.app.budget_editor.steps
        for _ in range(20): blocks.add_step.click()
        scroll=self.app.budget_scroll; deadline=time.monotonic()+3
        while scroll.verticalScrollBar().maximum()==0 and time.monotonic()<deadline: self.pump(.05)
        self.assertGreater(scroll.verticalScrollBar().maximum(),0)
        self.assertEqual(scroll.horizontalScrollBar().maximum(),0)
        self.pump(.15)  # Let the newly added cards finish their layout before scrolling.
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum()); self.pump(.05)
        self.assertTrue(blocks.add_step.isVisible()); self.assertTrue(self.app.budget_back.isVisible())
        point=blocks.add_step.mapTo(scroll.viewport(),QPoint(0,0))
        self.assertGreaterEqual(point.y(),0); self.assertLess(point.y(),scroll.viewport().height())

    def test_saved_blocks_drive_warning_and_restriction_at_the_selected_times(self):
        from gametime.restriction_policy import Budget,RestrictionState
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games'); blocks=editor.steps
        blocks.add_step.click(); warning=blocks.cards[0]; warning.minutes.setValue(2); warning.sound.setChecked(False)
        blocks.add_step.click(); restriction=next(c for c in blocks.cards if c is not warning); restriction.kind.setCurrentIndex(restriction.kind.findData('restrict')); restriction.consent.setChecked(True); restriction.minutes.setValue(120); self.app.save_budgets()
        plan=self.store.settings().restriction_plans['shared-games']; engine=RestrictionState(self.store)
        key='shared-games'; day='2026-10-30'; subject='app:fixture.exe'
        def update(used,now): engine.update(day,now,[Budget(key,'Fixture',7200,used,())],{key:plan})
        update(119,1000); self.assertEqual(engine.warnings(key),[]); self.assertEqual(engine.action(key,subject),'')
        update(120,1001); due=engine.warnings(key); self.assertEqual(len(due),1)
        self.assertFalse(due[0]['sound']); self.assertTrue(due[0]['popup']); self.assertEqual(engine.action(key,subject),'')
        engine.delivered(key,due[0]['id']); update(7200,1002)
        self.assertEqual(engine.warnings(key),[]); self.assertEqual(engine.action(key,subject),'cover')

    def test_custom_warning_only_replaces_legacy_game_minimization(self):
        plan=new_plan(); plan['steps']=[step('notify',popup=True)]
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_enabled=True,
            restriction_seconds=1,restriction_plans={'shared-games':plan})
        now=datetime.now().astimezone()
        with patch.object(self.app.tracker,'quota_day_totals',return_value={self.games[0].id:10000}):
            self.assertFalse(self.app.restriction_reached(now,self.games[0]))

    def test_popup_only_step_does_not_play_sound(self):
        from gametime.tracker import Alert
        self.app.dismiss_popup()
        with patch.object(self.app,'notification_mode',return_value='normal'),patch('gametime.qt_ui.play_notification') as sound:
            self.assertTrue(self.app.popup(Alert(datetime.now().date().isoformat(),(),'wellbeing','Fixture','OK',sound=False)))
            sound.assert_not_called()

    def test_extension_deadline_close_is_cancelled_when_plan_removed(self):
        from concurrent.futures import Future
        import threading
        runtime=self.app.restrictions; cancelled=threading.Event(); future=Future()
        target=Sample(datetime.now().astimezone(),100,str(self.exe),'123:456')
        runtime.jobs[target.identity]=(future,cancelled,target,('shared-games',))
        with patch.object(runtime,'process_browser_requests'),patch.object(runtime.audio,'update'):
            runtime.tick(replace(target,interactive=False))
        self.assertTrue(cancelled.is_set()); future.set_result(False)

    def test_clock_change_moves_one_time_allowance(self):
        from gametime.qt_day_start import apply_day_start
        from gametime.quota import current_day
        from gametime.restriction_policy import Budget
        now=datetime.now().astimezone().replace(hour=0,minute=30)
        plan=new_plan(); plan.update(extension_minutes=2,close_confirmed=True,steps=[step('cover')])
        state=self.app.restrictions.state
        day=current_day(self.app.settings,now).isoformat()
        state.update(day,100,[Budget('shared-games','x',1,1,())],{'shared-games':plan})
        state.extend(['shared-games'],'app:fixture.exe')
        previous=self.app.settings; self.app.settings=self.app.catalog.settings=replace(previous,budget_reset_minute=60)
        apply_day_start(self.app,previous,now)
        newday=current_day(self.app.settings,now).isoformat()
        state.update(newday,101,[Budget('shared-games','x',1,1,())],{'shared-games':plan})
        self.assertTrue(state.rows['shared-games']['used_extension'])
