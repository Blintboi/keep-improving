from copy import deepcopy
from dataclasses import replace
from datetime import datetime,date
from pathlib import Path
import tempfile
import unittest
from gametime.store import Store
from gametime.statistics_sync import StatisticsData
from gametime import device_sharing as sharing,device_scopes as scopes

CODE='ab'*16
class SharedDeviceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.stores=[]
        for i in range(3):
            s=Store(Path(self.tmp.name)/f'{i}.db');self.addCleanup(s.close)
            s.save_settings(replace(s.settings(),statistics_sync_enabled=True,statistics_sync_group=CODE));self.stores.append(s)
        self.a,self.b,self.c=self.stores;self.data=[StatisticsData(s) for s in self.stores]
    def share(self,mode='all',group=None):
        s=self.a.settings();scope=dict(mode=mode,connection=scopes.connection(CODE),accounting='shared')
        if group:scope['group']=group
        self.a.save_settings(replace(s,budget_devices={'shared-games':scope},game_budget_enabled=True,limit_seconds=3600,warning_seconds=3000))
    def transfer(self,source,target):
        snapshot=self.data[source].snapshot(CODE,'Test')
        self.data[target].ingest(snapshot,CODE);sharing.observe(self.stores[target],self.stores[target].settings());sharing.apply(self.stores[target]);return snapshot
    def test_origin_usage_never_republished_and_no_duplicate_projection(self):
        self.a.add_usage({(date.today().isoformat(),'game'):600});self.share()
        snap=self.transfer(0,1);self.assertEqual(len(self.b.settings().wellbeing_rules),1)
        self.transfer(0,1);self.assertEqual(len(self.b.settings().wellbeing_rules),1)
        key=self.b.settings().wellbeing_rules[0]['id']
        self.assertEqual(sharing.remote_seconds(self.b,self.b.settings(),key,datetime.now()),600)
        returned=self.transfer(1,0);self.assertEqual(returned['scoped_rules']['usage'],[])
        self.assertEqual(sharing.remote_seconds(self.a,self.a.settings(),'shared-games',datetime.now()),0)
        self.assertEqual(snap['scoped_rules']['usage'][0][3],600)
    def test_group_phone_membership_and_unselected_device(self):
        id='d'*32;conn=scopes.connection(CODE);a,b,c=[s.settings().scope_device for s in self.stores]
        self.a.save_settings(replace(self.a.settings(),device_groups={id:dict(name='Home',devices=[a,b],connection=conn)}));self.share('group',id)
        self.transfer(0,1);self.transfer(0,2)
        self.assertEqual(self.b.settings().device_groups[id]['devices'],[a,b])
        self.assertTrue(scopes.applies(self.b.settings().budget_devices[next(iter(self.b.settings().budget_devices))],self.b.settings()))
        self.assertFalse(scopes.applies(self.c.settings().budget_devices[next(iter(self.c.settings().budget_devices))],self.c.settings()))
        self.assertIsNotNone(sharing.state(self.b,conn)[id]['value'])
    def test_edit_and_delete_converge(self):
        self.share();self.transfer(0,1);s=self.b.settings();rules=deepcopy(s.wellbeing_rules);rules[0]['seconds']=1200
        self.b.save_settings(replace(s,wellbeing_rules=rules));self.transfer(1,0)
        self.assertEqual(self.a.settings().limit_seconds,1200)
        self.b.save_settings(replace(self.b.settings(),wellbeing_rules=[]));self.transfer(1,0)
        self.assertFalse(self.a.settings().game_budget_enabled)
    def test_shared_session_counts_are_origin_owned_and_replace_on_reimport(self):
        from gametime.activity_sessions import record
        now=datetime.now().astimezone();start=now.timestamp()-2
        with self.a.db:record(self.a.db,'game','game',start,start+1,str(date.today()))
        self.share();snap=self.transfer(0,1);self.transfer(0,1)
        key=self.b.settings().wellbeing_rules[0]['id']
        self.assertEqual(sharing.remote_sessions(self.b,self.b.settings(),key,now),1)
        self.assertEqual(self.transfer(1,0)['scoped_rules']['session_usage'],[])
        self.assertEqual(sharing.remote_sessions(self.a,self.a.settings(),'shared-games',now),0)
        bad=deepcopy(snap['scoped_rules']);bad['session_usage'][0][3]=1.5
        with self.assertRaises(ValueError):sharing.validate(bad)

    def test_wrong_connection_and_malformed_usage(self):
        self.share();snapshot=self.data[0].snapshot(CODE,'A');bad=deepcopy(snapshot['scoped_rules']);bad['usage']=[['a'*32,str(date.today()),0,float('nan')]]
        with self.assertRaises(ValueError):sharing.validate(bad)
        s=self.a.settings();self.assertFalse(scopes.applies(s.budget_devices['shared-games'],replace(s,statistics_sync_group='cd'*16)))

if __name__=='__main__':unittest.main()
