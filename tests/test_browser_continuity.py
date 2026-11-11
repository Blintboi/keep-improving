"""Offline replay uses synthetic time and disposable profiles only."""
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
import json
import sqlite3
import time

from gametime.store import Store
from gametime.model import Settings
from gametime.model import Catalog
from gametime.focus import Focus,FocusSettings
from gametime.wellbeing import Wellbeing
from gametime.browser_continuity import BrowserContinuity
from gametime.continuity_ledger import cover,uncovered
from gametime.restriction_policy import RestrictionState,new_plan,step


class BrowserContinuityTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'usage.sqlite3');self.addCleanup(self.store.close)
        self.path=r'c:\browser\brave.exe';self.base=time.time()-600
        self.settings=replace(Settings(),game_budget_enabled=False,wellbeing_rules=[dict(id='web',name='Browser and site',members=[dict(kind='app',value='brave.exe'),dict(kind='site',value='example.com')],seconds=600,enabled=True,enforce=True,overlay=False)])
        self.store.save_settings(self.settings)
        focus=Focus(self.store);catalog=Catalog(self.settings,[],{},{});wellbeing=Wellbeing(self.store,catalog,focus)
        runtime=SimpleNamespace(state=RestrictionState(self.store),prepare=lambda now:None)
        self.app=SimpleNamespace(store=self.store,settings=self.settings,focus=focus,catalog=catalog,wellbeing=wellbeing,
            restrictions=runtime,focus_awake=lambda:10000,update_focus_policy=Mock(),schedule_statistics_event=Mock(),_focus_notice='')
        self.store.db.execute('INSERT INTO activity_items VALUES (?,?,?)',('app',self.path,'brave.exe'));self.store.db.commit()
        self.service=BrowserContinuity(self.app);self.service.started=self.base+300;self.service.safe_until=self.base+400
        self.stream='a'*32

    def sample(self,seq,start,end,**changes):
        return dict(seq=seq,kind='sample',start=self.base+start,end=self.base+end,host='example.com',active=True,redirect='',timer='')|changes

    def send(self,records,stream=None):
        return self.service.exchange(dict(version=1,stream=stream or self.stream,browser='brave',records=records))

    def total(self,kind):
        return self.store.db.execute('SELECT COALESCE(SUM(seconds),0) FROM activity_usage WHERE kind=?',(kind,)).fetchone()[0]

    def test_native_overlap_replay_lost_response_and_second_stream_never_add_time_twice(self):
        with self.store.db:
            for kind in ('activity','wellbeing'): cover(self.store.db,kind,self.base,self.base+20)
        records=[self.sample(1,0,10),self.sample(2,10,30),self.sample(3,30,45)]
        self.assertEqual(self.send(records)['ack'],3)
        self.assertEqual(self.total('app'),25);self.assertEqual(self.total('site'),25)
        self.assertEqual(self.send(records)['ack'],3)
        self.service=BrowserContinuity(self.app);self.service.started=self.base+300;self.service.safe_until=self.base+400
        self.send(records);self.send(records,stream='b'*32)
        self.assertEqual(self.total('app'),25);self.assertEqual(self.total('site'),25)
        self.app.wellbeing.configure(datetime.fromtimestamp(self.base+45).astimezone())
        self.assertEqual(self.app.wellbeing.totals['web'],25)

    def test_import_ack_waits_for_native_sample_and_never_counts_live_desktop(self):
        self.service.started=self.base+20;self.service.safe_until=self.base+30
        records=[self.sample(1,10,25),self.sample(2,25,35)]
        self.assertEqual(self.send(records)['ack'],1);self.assertEqual(self.total('app'),10)
        self.service.safe_until=self.base+40
        self.assertEqual(self.send(records)['ack'],2);self.assertEqual(self.total('app'),10)

    def test_transaction_failure_rolls_back_credits_coverage_and_receipt(self):
        self.store.db.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON browser_journals BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.send([self.sample(1,0,10)])
        self.assertEqual(self.total('app'),0)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM continuity_coverage').fetchone()[0],0)
        self.store.db.execute('DROP TRIGGER reject_receipt');self.store.db.commit()
        self.send([self.sample(1,0,10)]);self.assertEqual(self.total('app'),10)

    def test_gap_invalid_future_private_url_and_reordered_packets_cannot_credit(self):
        bad=[self.sample(2,0,10),self.sample(1,0,60),self.sample(1,0,10,host='https://example.com/private'),
             self.sample(1,0,10,host='127.0.0.1'),self.sample(1,0,10,active=1),self.sample(1,0,10,timer='bad'),self.sample(1,0,10,timer=False)]
        for record in bad:
            with self.subTest(record=record),self.assertRaises(ValueError): self.send([record])
        with self.assertRaises(ValueError): self.send([self.sample(1,10,20),self.sample(2,5,10)])
        self.assertEqual(self.total('app'),0)

    def test_inactive_and_excluded_browser_add_no_usage_but_are_acknowledged(self):
        self.send([self.sample(1,0,10,active=False)])
        self.app.focus.configure(replace(self.app.focus.settings,excluded_apps=[self.path]))
        self.assertEqual(self.send([self.sample(2,10,20)])['ack'],2)
        self.assertEqual(self.total('app'),0)

    def test_midnight_and_global_day_start_split_history_once(self):
        boundary=datetime.now().astimezone().replace(hour=4,minute=0,second=0,microsecond=0)-timedelta(days=1)
        self.base=boundary.timestamp()-10;self.service.started=self.base+300;self.service.safe_until=self.base+400
        self.app.focus.configure_day_start(240)
        self.send([self.sample(1,0,20)])
        rows=list(self.store.db.execute("SELECT day,seconds FROM activity_usage WHERE kind='site' ORDER BY day"))
        self.assertEqual([r[1] for r in rows],[10,10]);self.send([self.sample(1,0,20)])
        self.assertEqual(self.total('site'),20)
        self.assertEqual(self.app.focus.started_on,rows[0][0])
        self.assertEqual(Focus(self.store).started_on,rows[0][0])

    def test_large_catchup_with_repeated_pages_is_exactly_once(self):
        self.service.started=self.base+400;self.service.safe_until=self.base+500
        records=[self.sample(i+1,i,i+1) for i in range(300)]
        for offset in range(0,300,128):
            batch=records[offset:offset+128]
            self.assertEqual(self.send(batch)['ack'],batch[-1]['seq'])
            self.send(batch)
        self.assertEqual(self.total('site'),300)
        self.assertEqual(self.total('app'),300)

    def test_native_completion_and_checkpoint_commit_atomically(self):
        f=self.app.focus;f.configure(FocusSettings(work=1,rounds=0));f.start(0)
        f.remaining=1;f._dirty=True;f.flush()
        self.store.db.execute("CREATE TRIGGER reject_timer BEFORE INSERT ON settings WHEN NEW.key='focus_timer' BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError): f.advance(2)
        self.store.db.execute('DROP TRIGGER reject_timer');self.store.db.commit()
        restored=Focus(self.store)
        self.assertEqual(restored.completed_rounds,0);self.assertEqual(restored.remaining,1)

    def test_pomodoro_resumes_from_checkpoint_and_completes_once_across_replay(self):
        f=self.app.focus;f.configure(FocusSettings(work=1,rounds=0));f.start(0);f.remaining=25;f.flush()
        token=f.continuity_token;f.running=False
        records=[self.sample(1,0,10,active=False,timer=token),self.sample(2,10,30,active=False,timer=token)]
        self.send(records)
        self.assertTrue(f.finished);self.assertEqual(f.completed_rounds,1)
        self.send(records);self.send(records,stream='c'*32)
        self.assertEqual(f.completed_rounds,1)
        restored=Focus(self.store);self.assertEqual(restored.completed_rounds,1);self.assertTrue(restored.finished)

    def test_timer_native_overlap_is_subtracted_and_break_carries_overshoot(self):
        f=self.app.focus;f.configure(FocusSettings(work=1,short_break=1));f.start(0);f.remaining=5;f.flush();f.running=False
        token=f.continuity_token
        with self.store.db: cover(self.store.db,'timer:'+token,self.base,self.base+10)
        self.send([self.sample(1,0,30,active=False,timer=token)])
        self.assertEqual(f.phase,'short_break');self.assertEqual(f.remaining,45);self.assertEqual(f.completed_rounds,1)

    def test_stale_timer_cannot_resume_after_explicit_pause(self):
        f=self.app.focus;f.start(0);token=f.continuity_token;f.pause(0)
        self.send([self.sample(1,0,10,active=False,timer=token)])
        self.assertFalse(f.running);self.assertEqual(f.remaining,1500)

    def test_offline_controls_are_ordered_and_do_not_overwrite_new_desktop_timer(self):
        f=self.app.focus;old=f.continuity_token;token='d'*32
        records=[dict(seq=1,kind='focus.start',at=self.base,base=old,token=token),self.sample(2,0,10,active=False,timer=token),
                 dict(seq=3,kind='focus.pause',at=self.base+10,base=token,token='e'*32)]
        self.send(records);self.assertFalse(f.running);self.assertEqual(f.remaining,1490)
        self.send(records);self.assertEqual(f.remaining,1490)
        f.start(10000)
        result=self.send([dict(seq=4,kind='focus.stop',at=self.base+11,base='e'*32,token='f'*32)])
        self.assertTrue(result['rejected_commands']);self.assertTrue(f.running)

    def test_failed_timer_import_rolls_back_completion_and_can_retry_once(self):
        f=self.app.focus;f.configure(FocusSettings(work=1,rounds=0));f.start(0);f.remaining=5;f.flush();f.running=False
        records=[self.sample(1,0,10,active=False,timer=f.continuity_token)]
        self.store.db.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON browser_journals BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.send(records)
        self.assertEqual(f.remaining,5);self.assertEqual(f.completed_rounds,0)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM focus_completions').fetchone()[0],0)
        self.store.db.execute('DROP TRIGGER reject_receipt');self.store.db.commit()
        self.send(records);self.send(records);self.assertEqual(f.completed_rounds,1)

    def test_offline_warning_and_break_state_prevent_repeat_after_handoff(self):
        plan=new_plan();plan['steps']=[step('notify',10,popup=True,identity='warn',usage=True),step('break',20,identity='rest',usage=True,break_mode='cover',break_minutes=1)]
        self.app.settings=self.app.catalog.settings=replace(self.settings,restriction_plans={'web':plan})
        record=dict(seq=2,kind='budget.state',at=self.base+30,key='web',day=datetime.fromtimestamp(self.base).date().isoformat(),fingerprint=self.service.fingerprint(plan),
            state=dict(expired=None,used_extension=False,grant=None,delivered=['warn'],breaks={'rest':dict(next_at=20,until=self.base+90)}))
        self.send([self.sample(1,0,30),record]);self.send([self.sample(1,0,30),record])
        row=json.loads(self.store.db.execute("SELECT value FROM restriction_state WHERE budget='web'").fetchone()[0])
        self.assertEqual(row['delivered'],['warn']);self.assertEqual(row['breaks']['rest']['until'],self.base+90)
        self.assertEqual(row['breaks']['rest']['spec'],json.dumps(plan['steps'][1],sort_keys=True))

    def test_invalid_budget_receipt_rolls_back_the_whole_packet(self):
        plan=new_plan();self.app.settings=self.app.catalog.settings=replace(self.settings,restriction_plans={'web':plan})
        record=dict(seq=2,kind='budget.state',at=self.base+30,key='web',day=datetime.fromtimestamp(self.base).date().isoformat(),fingerprint=self.service.fingerprint(plan),
            state=dict(expired=None,used_extension=False,grant=None,delivered=['not-a-warning'],breaks={}))
        with self.assertRaises(ValueError): self.send([self.sample(1,0,30),record])
        self.assertEqual(self.total('app'),0)

    def test_inactive_weekday_budget_is_still_cached_for_the_next_day(self):
        self.app.settings=self.app.catalog.settings=replace(self.settings,budget_active_days={'web':[]})
        cached=self.service.snapshot('brave')['budgets'];self.assertEqual(len(cached),1);self.assertEqual(cached[0]['days'],[])
