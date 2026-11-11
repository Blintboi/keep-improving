from copy import deepcopy
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from gametime.store import Store
from gametime.focus import Focus
from gametime.model import Game
from gametime.statistics_sync import StatisticsData
from gametime import companion_commands as commands,companion_sync as companion

GROUP='a1'*16
class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'usage.sqlite3');self.addCleanup(self.store.close)
        self.store.save_settings(replace(self.store.settings(),statistics_sync_enabled=True,statistics_sync_group=GROUP))
        self.focus=Focus(self.store);self.data=StatisticsData(self.store,self.focus)
        self.store.upsert([Game('steam:1','A game','Steam','C:/Games/A')])
    def command(self,kind,key,value,base=None):
        return dict(id=uuid.uuid4().hex,target=self.data.device_id(),kind=kind,key=key,value=value,base=base or commands.digest(commands.resource(self.store,self.focus,kind,key)),created=int(time.time()*1000))
    def apply(self,items,group=GROUP):
        commands.stage(self.store,group,self.data.device_id(),'b'*32,items)
        return commands.apply_pending(self.store,group,self.focus)
    def test_focus_counts_are_origin_owned_and_replaced(self):
        day=date.today().isoformat()
        with self.store.db:self.store.db.execute('INSERT INTO focus_completions VALUES (?,?)',(day,2))
        snap=self.data.snapshot(GROUP,'PC');self.assertEqual(snap['focus_rounds'],[[day,2]])
        remote=deepcopy(snap);remote.update(device='b'*32,name='Phone',focus_rounds=[[day,3]],revision=snap['revision']+1)
        self.assertTrue(self.data.ingest(remote,GROUP));self.assertFalse(self.data.ingest(remote,GROUP))
        self.assertEqual(self.data.completed_focus_on(day,GROUP),5)
        self.assertEqual(self.data.snapshot(GROUP,'PC')['focus_rounds'],[[day,2]])
        self.assertEqual(self.data.completed_focus_on(day,'c'*32),2)
        remote['revision']+=1;remote['focus_rounds']=[[day,4]];self.data.ingest(remote,GROUP)
        self.assertEqual(self.data.completed_focus_on(day,GROUP),6)
    def test_targeted_idempotent_edit_preserves_credentials_and_history(self):
        raw=self.store.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0]
        encrypted=json.loads(raw)['statistics_sync_group']
        self.store.add_usage({(date.today().isoformat(),'steam:1'):120})
        item=self.command('setting','check_updates',False);self.assertTrue(self.apply([item]));self.assertFalse(self.apply([item]))
        self.assertFalse(self.store.settings().check_updates)
        self.assertEqual(json.loads(self.store.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0])['statistics_sync_group'],encrypted)
        self.assertEqual(self.store.totals(date.today().isoformat()),{'steam:1':120})
        self.assertEqual(commands.results(self.store,GROUP)[0]['status'],'applied')
    def test_wrong_target_and_group_do_not_apply(self):
        item=self.command('setting','check_updates',False);item['target']='c'*32
        self.assertFalse(self.apply([item]));self.assertTrue(self.store.settings().check_updates)
        item['target']=self.data.device_id();commands.stage(self.store,'c'*32,self.data.device_id(),'b'*32,[item])
        self.assertFalse(commands.apply_pending(self.store,GROUP,self.focus));self.assertTrue(self.store.settings().check_updates)
    def test_conflict_and_invalid_edit_keep_local_value(self):
        item=self.command('setting','overlay_font_size',35)
        self.store.save_settings(replace(self.store.settings(),overlay_font_size=30))
        self.assertFalse(self.apply([item]));self.assertEqual(self.store.settings().overlay_font_size,30)
        self.assertEqual(commands.results(self.store,GROUP)[0]['reason'],'conflict')
        bad=self.command('setting','overlay_font_size',-999);self.assertFalse(self.apply([bad]))
        self.assertEqual(self.store.settings().overlay_font_size,30)
    def test_budget_edit_new_members_and_advanced_plan_protection(self):
        key='phone-group';b=dict(id=key,name='Web time',scope='group',seconds=1800,enabled=True,members=[dict(kind='site',value='example.com')],days=[0,1,2,3,4],usage_limit=True,reset_minute=240,plan=None)
        self.assertTrue(self.apply([self.command('budget',key,b)]));self.assertEqual(self.store.settings().wellbeing_rules[0]['seconds'],1800)
        old=commands.resource(self.store,self.focus,'budget',key);changed={**old,'seconds':600};self.assertTrue(self.apply([self.command('budget',key,changed)]))
        illegal={**commands.resource(self.store,self.focus,'budget',key),'plan':{'close_confirmed':True}}
        self.assertFalse(self.apply([self.command('budget',key,illegal)]));self.assertEqual(self.store.settings().restriction_plans,{})
    def test_only_whitelisted_focus_fields_change(self):
        self.focus.configure(replace(self.focus.settings,excluded_apps=[r'C:\Private\kept.exe']))
        value=commands.resource(self.store,self.focus,'focus','');value['work']=42
        self.assertTrue(self.apply([self.command('focus','',value)]));self.assertEqual(self.focus.settings.work,42)
        self.assertEqual(self.focus.settings.excluded_apps,[r'c:\private\kept.exe'])
    def test_companion_excludes_secrets_and_no_new_executable_actions(self):
        snap=companion.snapshot(self.store,self.focus)
        self.assertFalse(companion.PRIVATE.intersection(snap['settings']))
        self.assertEqual(snap['empty_hash'],commands.digest(None))
        rule=dict(id='d'*32,title='Take a break',text='Rest',icon='preset:bell',enabled=True,minute=720,action=dict(kind='desktop_app',name='unsafe.exe'))
        self.assertFalse(self.apply([self.command('notification',rule['id'],rule)]))
        rule['action']={'kind':'pomodoro','work':25,'short_break':5,'long_break':15,'rounds':4}
        self.assertTrue(self.apply([self.command('notification',rule['id'],rule)]))
    def test_command_and_snapshot_revision_commit_together(self):
        item=self.command('setting','check_updates',False);snap=self.data.snapshot(GROUP,'Phone');snap.update(device='b'*32,remote_commands=[item])
        self.data.ingest(snap,GROUP)
        # Reopening can apply a pending command even though the snapshot is already known.
        self.assertFalse(self.data.ingest(snap,GROUP));self.assertTrue(commands.apply_pending(self.store,GROUP,self.focus))
        self.assertFalse(self.store.settings().check_updates)
    def test_bad_count_and_expired_command_rejected(self):
        with self.assertRaises(ValueError):companion.validate_focus([[date.today().isoformat(),True]])
        item=self.command('setting','check_updates',False);item['created']-=15*86400000
        self.assertFalse(self.apply([item]));self.assertEqual(commands.results(self.store,GROUP)[0]['reason'],'expired')

    def test_unplayed_local_activities_are_exported_without_imports_or_duplicates(self):
        with self.store.db:
            self.store.db.executemany('INSERT INTO activity_items VALUES (?,?,?)', [('app',r'c:\apps\tool.exe','Tool'),('app',r'c:\new\tool.exe','Tool'),('site','example.com','Example')])
        entries=companion.local_activities(self.store,self.store.settings(),self.focus)
        self.assertEqual({(v['kind'],v['key']) for v in entries},{('app','tool.exe'),('site','example.com')})
        self.assertEqual(len(entries),2)
    def test_usb_ciphertext_uses_the_same_group_and_preserves_cloud_cooldown(self):
        from types import SimpleNamespace
        from gametime.companion_transfer import export,receive
        from gametime.statistics_cloud import seal,unseal
        self.data.defer_sync(600)
        guard=self.store.db.execute("SELECT value FROM settings WHERE key='statistics_sync_not_before'").fetchone()[0]
        app=SimpleNamespace(settings=self.store.settings(),tracker=SimpleNamespace(flush=lambda:None),focus=self.focus,statistics_data=self.data)
        entry=export(app,{})
        snapshot=unseal(entry,GROUP);snapshot.update(device='b'*32,revision=snapshot['revision']+1)
        snapshot.pop('preferences',None)
        remote=dict(device=snapshot['device'],revision=str(snapshot['revision']),payload=seal(snapshot,GROUP))
        self.assertTrue(receive(app,{'entry':remote})['imported'])
        self.assertFalse(receive(app,{'entry':remote})['imported'])
        self.assertEqual(self.store.db.execute("SELECT value FROM settings WHERE key='statistics_sync_not_before'").fetchone()[0],guard)
        wrong={**remote,'payload':seal({**snapshot,'group':'c'*32},'c'*32)}
        with self.assertRaises(ValueError):receive(app,{'entry':wrong})

if __name__=='__main__':unittest.main()
