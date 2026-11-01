import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from gametime.budget_periods import BudgetPeriods
from gametime.restriction_policy import Budget, RestrictionState, new_plan, step


class IndependentBudgetPeriodsTest(unittest.TestCase):
    def setUp(self):
        self.store = SimpleNamespace(db=sqlite3.connect(':memory:'))
        self.ledger = BudgetPeriods(self.store)
        self.start = datetime(2026, 10, 30, 5, 59, 59, tzinfo=timezone.utc)

    def test_independent_boundaries_split_and_survive_restart(self):
        seed = lambda: {'game': 90}
        self.ledger.credit('early', 360, 'game', self.start, self.start+timedelta(seconds=2), 2, seed)
        self.ledger.credit('late', 480, 'game', self.start, self.start+timedelta(seconds=2), 2, seed)
        self.ledger.flush()
        loaded = BudgetPeriods(self.store)
        after = self.start + timedelta(seconds=2)
        self.assertEqual(loaded.totals('early', 360, after, seed)['game'], 1)
        self.assertEqual(loaded.totals('late', 480, after, seed)['game'], 92)

    def test_edit_carries_consumption_without_erasing_other_budget(self):
        seed = lambda: {'app': 55}
        self.ledger.totals('one', 360, self.start, seed)
        self.ledger.totals('two', 480, self.start, seed)
        self.ledger.credit('one', 360, 'app', self.start, self.start+timedelta(seconds=0.5), .5, seed)
        self.assertEqual(self.ledger.totals('one', 600, self.start, seed)['app'], 55.5)
        self.assertEqual(self.ledger.totals('two', 480, self.start, seed)['app'], 55)
        tomorrow = self.start + timedelta(days=1)
        self.assertEqual(self.ledger.totals('one', 600, tomorrow, seed), {})

    def test_restriction_delivery_is_independent_by_budget_period(self):
        engine = RestrictionState(self.store)
        plan = new_plan(); plan['steps'] = [step('notify', popup=True)]
        plans = {'one': plan, 'two': plan}
        def budgets(one_day, two_day):
            return [Budget('one', 'One', 60, 60, (), day=one_day),
                    Budget('two', 'Two', 60, 60, (), day=two_day)]
        engine.update('2026-10-30', 1000, budgets('2026-10-30', '2026-10-30'), plans)
        for key in plans: engine.delivered(key, plan['steps'][0]['id'])
        engine.update('2026-10-31', 2000, budgets('2026-10-31', '2026-10-30'), plans)
        self.assertEqual(len(engine.warnings('one')), 1)
        self.assertEqual(engine.warnings('two'), [])

    def test_clock_edit_carries_warning_and_extension_state(self):
        self.store.db.execute('CREATE TABLE alerts (day TEXT NOT NULL,key TEXT NOT NULL,PRIMARY KEY(day,key))')
        engine=RestrictionState(self.store)
        plan=new_plan(); plan['steps']=[step('cover')]; plan['extension_minutes']=5
        engine.update('2026-10-30',1000,[Budget('one','One',60,60,())],{'one':plan})
        self.assertIsNotNone(engine.extend(['one'],'app:c:\\example.exe'))
        self.store.db.execute('INSERT INTO alerts VALUES (?,?)',('2026-10-30','wellbeing:one:60'))
        self.ledger.totals('one',600,self.start,lambda:{'app':60},marker_key='one',previous_day='2026-10-30')
        self.assertIsNotNone(self.store.db.execute('SELECT 1 FROM alerts WHERE day=? AND key=?',('2026-10-29','wellbeing:one:60')).fetchone())
        engine.update('2026-10-30',1001,[Budget('one','One',60,60,(),day='2026-10-29')],{'one':plan})
        self.assertTrue(engine.rows['one']['used_extension'])


if __name__ == '__main__': unittest.main()
