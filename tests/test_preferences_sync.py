"""Settings share the existing encrypted exchange without changing local usage."""
from dataclasses import replace
from datetime import date
from pathlib import Path
import tempfile
import unittest

from gametime.focus import Focus
from gametime.model import Game
from gametime.preferences_sync import apply, key, read
from gametime.statistics_sync import StatisticsData, validate_snapshot
from gametime.store import Store

GROUP='ab'*16


class PreferenceSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.stores=[]; self.data=[]; self.focus=[]
        for name in ('one','two'):
            store=Store(Path(self.tmp.name)/(name+'.sqlite3')); self.addCleanup(store.close)
            store.upsert([Game('steam:42','Example','Steam',str(Path(self.tmp.name)/name))])
            store.save_settings(replace(store.settings(),statistics_sync_enabled=True,statistics_sync_group=GROUP))
            self.stores.append(store); self.data.append(StatisticsData(store)); self.focus.append(Focus(store))

    def transfer(self,source,target):
        snapshot=self.data[source].snapshot(GROUP,'Example computer')
        self.data[target].ingest(snapshot,GROUP)
        return apply(self.stores[target],GROUP,self.data[target].device_id(),self.focus[target])

    def test_fields_merge_and_unchanged_sync_does_not_write_preferences(self):
        self.stores[0].save_settings(replace(self.stores[0].settings(),limit_seconds=10800))
        self.stores[1].save_settings(replace(self.stores[1].settings(),language='hu'))
        self.transfer(0,1); self.transfer(1,0); self.transfer(0,1)
        for store in self.stores:
            self.assertEqual(store.settings().limit_seconds,10800)
            self.assertEqual(store.settings().language,'hu')
        before=self.stores[0].db.total_changes
        one=self.data[0].snapshot(GROUP,'Example computer')
        two=self.data[0].snapshot(GROUP,'Example computer')
        self.assertEqual(one,two); self.assertEqual(self.stores[0].db.total_changes,before)
        self.assertNotIn(GROUP,str(one.get('preferences',{})))

    def test_focus_and_per_game_preferences_follow_the_game_not_usage(self):
        self.focus[0].configure(replace(self.focus[0].settings,work=40,block_sites=['example.com']))
        self.stores[0].set_enabled('steam:42',False); self.stores[0].set_hidden('steam:42',True)
        self.stores[0].save_settings(replace(self.stores[0].settings(),game_limits={'steam:42':1200}))
        self.stores[0].add_usage({(date.today().isoformat(),'steam:42'):300})
        self.transfer(0,1)
        self.assertEqual(self.focus[1].settings.work,40)
        self.assertEqual(self.focus[1].settings.block_sites,['example.com'])
        self.assertFalse(self.stores[1].overrides()['steam:42'])
        self.assertIn('steam:42',self.stores[1].hidden_ids())
        self.assertEqual(self.stores[1].settings().game_limits,{'steam:42':1200})
        self.assertEqual(self.stores[1].totals(date.today()),{})
        self.stores[1].set_enabled('steam:42',True); self.stores[1].set_hidden('steam:42',False)
        self.transfer(1,0)
        self.assertTrue(self.stores[0].overrides()['steam:42'])
        self.assertNotIn('steam:42',self.stores[0].hidden_ids())

    def test_invalid_preferences_do_not_replace_local_values(self):
        snapshot=self.data[0].snapshot(GROUP,'Example computer')
        snapshot['preferences']={'settings.language':{'clock':1,'device':'0'*32,'value':'bad'},'unknown':{}}
        with self.assertRaises(ValueError): validate_snapshot(snapshot,GROUP)
        self.assertEqual(self.stores[1].settings().language,'en')
        self.assertEqual(read(self.stores[1],key(GROUP)),{})

    def test_invalid_remote_combination_is_rejected_without_changing_settings(self):
        from gametime.preferences_sync import stage
        invalid={'settings.play_window':{'clock':5,'device':'a'*32,
                  'value':{'limit_seconds':60,'warning_seconds':120}}}
        before=self.stores[1].settings(); stage(self.stores[1],GROUP,invalid)
        with self.assertRaises(ValueError): apply(self.stores[1],GROUP,self.data[1].device_id(),self.focus[1])
        self.assertEqual(self.stores[1].settings(),before)

    def test_future_preference_fields_do_not_break_statistics(self):
        snapshot=self.data[0].snapshot(GROUP,'Example computer')
        snapshot['preferences']={'settings.future_field':{'clock':1,'device':'a'*32,'value':'new'}}
        validate_snapshot(snapshot,GROUP)
        self.assertTrue(self.data[1].ingest(snapshot,GROUP))
        self.assertFalse(apply(self.stores[1],GROUP,self.data[1].device_id(),self.focus[1]))

    def test_conflicting_edits_converge_and_reset_to_default_propagates(self):
        self.focus[0].configure(replace(self.focus[0].settings,work=35))
        self.focus[1].configure(replace(self.focus[1].settings,work=40))
        self.transfer(0,1); self.transfer(1,0); self.transfer(0,1)
        self.assertEqual(self.focus[0].settings.work,self.focus[1].settings.work)
        self.focus[0].configure(replace(self.focus[0].settings,work=25))
        self.transfer(0,1); self.assertEqual(self.focus[1].settings.work,25)

    def test_manual_game_preferences_match_by_title_without_exporting_game_paths(self):
        for i,store in enumerate(self.stores):
            store.upsert([Game('manual:'+str(i),'Example Game','Kézi',str(Path(self.tmp.name)/str(i)))])
        self.stores[0].set_enabled('manual:0',False)
        self.stores[0].save_settings(replace(self.stores[0].settings(),game_limits={'manual:0':900}))
        snapshot=self.data[0].snapshot(GROUP,'Computer')
        self.assertNotIn(str(Path(self.tmp.name)),str(snapshot.get('preferences',{})))
        self.data[1].ingest(snapshot,GROUP); apply(self.stores[1],GROUP,self.data[1].device_id(),self.focus[1])
        self.assertFalse(self.stores[1].overrides()['manual:1'])
        self.assertEqual(self.stores[1].settings().game_limits['manual:1'],900)

    def test_preferences_are_encrypted_and_other_codes_cannot_read_them(self):
        import base64
        from gametime.statistics_cloud import seal,unseal
        self.focus[0].configure(replace(self.focus[0].settings,block_sites=['example.com']))
        snapshot=self.data[0].snapshot(GROUP,'Computer')
        payload=seal(snapshot,GROUP)
        self.assertNotIn(b'example.com',base64.b64decode(payload))
        entry={'device':snapshot['device'],'revision':str(snapshot['revision']),'payload':payload}
        self.assertEqual(unseal(entry,GROUP),snapshot)
        with self.assertRaises(ValueError): unseal(entry,'cd'*16)

    def test_machine_specific_paths_credentials_and_consents_remain_local(self):
        one,two=self.stores
        one_root=str(Path(self.tmp.name)/'source'); two_root=str(Path(self.tmp.name)/'target')
        one.save_settings(replace(one.settings(),games_root=one_root,overlay_screen='Source monitor',
                                  game_overlays={'steam:42':{'overlay_screen':'Source monitor','overlay_font_size':36}}))
        two.save_settings(replace(two.settings(),games_root=two_root,overlay_screen='Target monitor',
                                  game_overlays={'steam:42':{'overlay_screen':'Target monitor'}}))
        with two.db: two.db.execute("INSERT OR REPLACE INTO settings VALUES ('overlay_risk_consent:local','kept')")
        self.transfer(0,1)
        settings=two.settings()
        self.assertEqual(settings.games_root,two_root); self.assertEqual(settings.overlay_screen,'Target monitor')
        self.assertEqual(settings.statistics_sync_group,GROUP)
        self.assertEqual(settings.game_overlays['steam:42']['overlay_screen'],'Target monitor')
        self.assertEqual(settings.game_overlays['steam:42']['overlay_font_size'],36)
        self.assertEqual(two.db.execute("SELECT value FROM settings WHERE key='overlay_risk_consent:local'").fetchone()[0],'kept')

    def test_encrypted_exchange_reuses_existing_requests_and_unchanged_payload(self):
        import copy,json
        from gametime.statistics_cloud import CloudSyncWorker,CLOUD_FORMAT
        class Relay(CloudSyncWorker):
            def __init__(self): super().__init__(); self.rows={}; self.calls=[]
            def post(self,service,authorization,body):
                self.calls.append(copy.deepcopy(body))
                if body['payload'] is not None:
                    self.rows[body['device']]={k:body[k] for k in ('device','revision','payload')}
                return {'format':CLOUD_FORMAT,'need_upload':False,'snapshots':[copy.deepcopy(row) for device,row in self.rows.items()
                        if device!=body['device'] and body['known'].get(device)!=row['revision']]}
        relay=Relay(); self.addCleanup(relay.close)
        self.focus[0].configure(replace(self.focus[0].settings,block_sites=['example.com']))
        def exchange(index):
            snapshot=self.data[index].snapshot(GROUP,'Computer')
            values,_=relay.exchange(('https://fixture.example',GROUP,relay.generation),
                                    (snapshot,self.data[index].revisions(GROUP)))
            for value in values: self.data[index].ingest(value,GROUP)
            apply(self.stores[index],GROUP,self.data[index].device_id(),self.focus[index])
        exchange(0); exchange(1)
        self.assertEqual(self.focus[1].settings.block_sites,['example.com'])
        exchange(1); exchange(1)
        self.assertEqual(len(relay.calls),4)
        self.assertIsNone(relay.calls[-1]['payload'])
        self.assertNotIn('example.com',json.dumps(relay.calls))


if __name__=='__main__': unittest.main()
