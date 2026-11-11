from copy import deepcopy
from pathlib import Path
import math
import tempfile
import unittest
from gametime.store import Store
from gametime.session_choices import ChoiceLedger, Visits, defaults, validate, allowance_activity
from gametime.restriction_policy import Budget, RestrictionState, new_plan, step, validate_plans, remap_state
from gametime.timer_view import project


class ChoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'usage.db';self.store=Store(self.path);self.addCleanup(self.store.close)
        self.ledger=ChoiceLedger(self.store);self.value=defaults()
        self.work,self.casual=[o['id'] for o in self.value['options']]

    def choose(self,visit,choice=None,day='2026-11-11',budget='web',step_id='why'):
        return self.ledger.choose(budget,step_id,day,visit,self.value,choice or self.casual,1000)

    def test_two_allowed_third_disabled_unlimited_independent(self):
        self.assertTrue(self.choose('1'));self.assertTrue(self.choose('2'));self.assertFalse(self.choose('3'))
        for n in range(10):self.assertTrue(self.choose('work'+str(n),self.work))
        options=self.ledger.options('web','why','2026-11-11',self.value)
        self.assertEqual([o['remaining'] for o in options],[None,0])
        self.assertEqual([o['used'] for o in options],[10,2])

    def test_duplicate_click_retries_are_idempotent_and_restart_retains_counts(self):
        self.assertTrue(self.choose('one'));self.assertTrue(self.choose('one'))
        self.assertFalse(self.choose('one',self.work))
        self.store.close();self.store=Store(self.path);self.addCleanup(self.store.close);self.ledger=ChoiceLedger(self.store)
        self.assertTrue(self.choose('two'));self.assertFalse(self.choose('three'))

    def test_renewal_budget_and_step_are_independent(self):
        self.choose('one');self.choose('two')
        self.assertTrue(self.choose('three',day='2026-11-12'))
        self.assertTrue(self.choose('four',budget='other'))
        self.assertTrue(self.choose('five',step_id='other'))

    def test_renaming_preserves_usage_and_budget_remap_preserves_ledger(self):
        self.choose('one');self.choose('two');self.value['options'][1]['label']='Renamed'
        self.assertFalse(self.choose('three'))
        RestrictionState(self.store)
        with self.store.db:remap_state(self.store.db,'web','merged')
        self.ledger=ChoiceLedger(self.store)
        self.assertFalse(self.choose('three',budget='merged'))

    def test_invalid_config_is_rejected_before_consuming(self):
        invalid=[]
        for limit in (0,True,1.5,10001,-1):
            v=deepcopy(self.value);v['options'][1]['limit']=limit;invalid.append(v)
        for field,bad in (('question',''),('question','x'*181),('options',[])):
            v=deepcopy(self.value);v[field]=bad;invalid.append(v)
        v=deepcopy(self.value);v['options'][1]['id']=self.work;invalid.append(v)
        v=deepcopy(self.value);v['options'][0]['label']='';invalid.append(v)
        for v in invalid:
            with self.assertRaises(ValueError):validate(v)
        self.assertFalse(self.choose('unknown','missing'))
        self.assertEqual(self.ledger.counts('web','why','2026-11-11'),{})

    def test_normal_thresholds_do_not_fire_for_choices_other_rules_still_apply(self):
        for kind in ('notify','cover','restrict','break'):
            p=new_plan();s=step(kind,2,popup=True);s.update(time_mode='sessions',session_choice=self.value);p['steps']=[s]
            validate_plans({'web':p})
            state=RestrictionState(self.store);b=Budget('web','Web',math.inf,100,(),sessions=200)
            state.update('2026-11-11',1000,[b],{'web':p})
            self.assertFalse(state.action('web','site:example.com'));self.assertFalse(state.warnings('web','site:example.com'))
            self.assertIsNone(project(b,p,state.rows['web'],1000,'site:example.com'))
            p['steps'].append(step('cover',50,usage=True))
            state.update('2026-11-11',1001,[b],{'web':p})
            self.assertEqual(state.action('web','site:example.com'),'cover')

    def test_choices_require_session_timing(self):
        p=new_plan();s=step('notify',60,popup=True,usage=True);s['session_choice']=self.value;p['steps']=[s]
        with self.assertRaises(ValueError):validate_plans({'web':p})

    def test_foreground_return_gets_new_token_continuous_visit_does_not(self):
        v=Visits();key=('web','why');a=v.observe({key:'one:site:a.test'})[key]
        a['choice']=self.work
        self.assertIs(v.observe({key:'one:site:a.test'})[key],a)
        b=v.observe({key:'one:site:b.test'})[key];self.assertNotEqual(a['token'],b['token'])
        v.observe({});c=v.observe({key:'one:site:a.test'})[key]
        self.assertNotEqual(a['token'],c['token']);self.assertIsNone(c['choice'])

    def test_shared_count_combines_members_separate_count_keeps_each_allowance(self):
        def pick(visit,activity):return self.ledger.choose('web','why','2026-11-11',visit,self.value,self.casual,1000,activity)
        self.assertTrue(pick('a1','site:a.test'));self.assertTrue(pick('b1','site:b.test'))
        self.assertFalse(pick('c1','app:one.exe'))
        self.value['allocation']='activity'
        # Changing allocation keeps all accepted history, rather than resetting it.
        self.assertTrue(pick('a2','site:a.test'));self.assertFalse(pick('a3','site:a.test'))
        self.assertTrue(pick('b2','site:b.test'));self.assertFalse(pick('b3','site:b.test'))
        self.assertTrue(pick('c1','app:one.exe'));self.assertTrue(pick('c2','app:one.exe'))
        self.assertEqual(self.ledger.options('web','why','2026-11-11',self.value,'site:a.test')[1]['remaining'],0)
        self.assertEqual(self.ledger.options('web','why','2026-11-11',self.value,'app:two.exe')[1]['remaining'],2)
        self.ledger=ChoiceLedger(self.store);self.assertFalse(pick('a4','site:a.test'))
        self.value['allocation']='shared';self.assertFalse(pick('d1','app:two.exe'))

    def test_member_identity_groups_subdomains_app_paths_and_game_executables(self):
        members=[{'kind':'site','value':'example.com'},{'kind':'site','value':'special.example.com'}]
        self.assertEqual(allowance_activity(members,('','','www.example.com'),'site'),'site:example.com')
        self.assertEqual(allowance_activity(members,('','','a.example.com'),'site'),'site:example.com')
        self.assertEqual(allowance_activity(members,('','','special.example.com'),'site'),'site:special.example.com')
        self.assertEqual(allowance_activity([],('',r'C:\New\App.exe',''),'app'),'app:app.exe')
        self.assertEqual(allowance_activity([{'kind':'category','value':'games'}],('g1','main.exe',''),'app'),'game:g1')
        self.value['allocation']='bad'
        with self.assertRaises(ValueError):validate(self.value)

    def test_existing_ledger_migrates_without_losing_shared_receipts(self):
        db=self.store.db
        with db:
            db.execute('DROP TABLE session_choices')
            db.execute('CREATE TABLE session_choices (budget TEXT,step TEXT,day TEXT,visit TEXT,choice TEXT,at REAL,PRIMARY KEY(budget,step,visit))')
            db.execute('INSERT INTO session_choices VALUES (?,?,?,?,?,?)',('web','why','2026-11-11','old',self.casual,1000))
        self.ledger=ChoiceLedger(self.store)
        self.assertEqual(self.ledger.counts('web','why','2026-11-11'),{self.casual:1})
        self.assertTrue(self.choose('new'));self.assertFalse(self.choose('exhausted'))
