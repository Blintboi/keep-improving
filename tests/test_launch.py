import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
from gametime.hub import Hub
from gametime.launch import LaunchPlan, LaunchWorker, execute, prepare
from gametime.model import Game, Settings, norm
from gametime.store import Store


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'Game with spaces'
        self.root.mkdir()
        self.settings = Settings(games_root=str(self.base/'Shortcuts'), hub_enabled=False)
        self.bridge = Mock()
        self.bridge.inventory.return_value = []
        self.hub = Hub(self.base/'Profile', self.bridge, locations=[])

    def game(self, gid='games:fixture', source='Games'):
        return Game(gid,'Example',source,str(self.root))

    def file(self, name):
        path=self.base/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b'Fixture, never execute')
        return path

    def test_steam_and_ubisoft_use_product_launch_protocols_without_shortcut_sync(self):
        for source,gid,expected in [('Steam','steam:42','steam://rungameid/42'),
                                   ('Ubisoft','ubisoft:635','uplay://launch/635/0')]:
            with self.subTest(source=source):
                plan=prepare(self.game(gid,source),self.settings,{},self.hub)
                self.assertEqual(plan,LaunchPlan('uri',expected))
        self.bridge.create.assert_not_called()
        self.assertFalse(Path(self.settings.games_root).exists())

    def test_epic_uses_encoded_official_product_uri(self):
        metadata=self.base/'epic.item'
        metadata.write_text(json.dumps({'AppName':'example','CatalogNamespace':'ns','CatalogItemId':'catalog'}))
        game=Game('epic:example','Example','Epic',str(self.root),str(metadata))
        plan=prepare(game,self.settings,{},self.hub)
        self.assertEqual(plan.target,'com.epicgames.launcher://apps/ns%3Acatalog%3Aexample?action=launch&silent=true')

    def test_existing_epic_url_cannot_request_uninstall(self):
        path=self.base/'Game.url'
        contents='[InternetShortcut]\nURL=com.epicgames.launcher://apps/ns:catalog:example?action=uninstall\n'
        path.write_text(contents)
        self.bridge.inventory.return_value=[{'path':str(path),'contents':contents}]
        plan=prepare(self.game('epic:example','Epic'),self.settings,{},self.hub)
        self.assertIn('action=launch',plan.target)
        self.assertNotIn('uninstall',plan.target)

    def test_riot_uses_client_and_structured_product_arguments(self):
        client=self.file('Riot Client/RiotClientServices.exe')
        self.bridge.inventory.return_value=[{'path':str(self.base/'Riot.lnk'),'target':str(client),'arguments':''}]
        plan=prepare(self.game('riot:valorant.live','Riot'),self.settings,{},self.hub)
        self.assertEqual(plan.arguments,('--launch-product=valorant','--launch-patchline=live'))
        with patch('gametime.launch.subprocess.Popen') as popen:
            execute(plan)
            popen.assert_called_once_with([str(client),*plan.arguments],cwd=str(client.parent),shell=False)

    def test_single_standalone_executable_uses_its_working_folder(self):
        exe=self.root/'bin/play.exe'; exe.parent.mkdir(); exe.write_bytes(b'Fixture')
        plan=prepare(self.game(),self.settings,{},self.hub)
        self.assertEqual((plan.kind,plan.target,plan.working),('executable',str(exe),str(exe.parent)))

    def test_ambiguous_standalone_requires_explicit_choice(self):
        (self.root/'play.exe').touch(); (self.root/'play_dev.exe').touch()
        with self.assertRaisesRegex(ValueError,'Assign EXE'):
            prepare(self.game(),self.settings,{},self.hub)

    def test_preferred_executable_is_validated_and_resolves_ambiguity(self):
        exe=self.file('Another folder/selected.exe')
        (self.root/'a.exe').touch(); (self.root/'b.exe').touch()
        rules={norm(exe):self.game().id}
        plan=prepare(self.game(),self.settings,rules,self.hub,str(exe))
        self.assertEqual(plan.target,str(exe))
        with self.assertRaises(ValueError):
            prepare(self.game(),self.settings,{},self.hub,str(exe))
        browser=self.file('browser/chrome.exe')
        with self.assertRaises(ValueError):
            prepare(self.game(),self.settings,{norm(browser):self.game().id},self.hub,str(browser))

    def test_original_shortcut_keeps_arguments_and_changed_file_is_rejected(self):
        exe=self.file('Game with spaces/play.exe')
        link=self.file('original.lnk')
        self.bridge.inventory.return_value=[{'path':str(link),'target':str(exe),'arguments':'--profile "A B"'}]
        plan=prepare(self.game(),self.settings,{},self.hub)
        with patch('gametime.launch.os.startfile',create=True) as start:
            execute(plan)
            start.assert_called_once_with(str(link))
            link.write_bytes(b'Changed')
            with self.assertRaisesRegex(ValueError,'changed'):
                execute(plan)
            self.assertEqual(start.call_count,1)

    def test_minecraft_retains_original_launcher_shortcut(self):
        launcher=self.file('Minecraft/MinecraftLauncher.exe')
        link=self.file('Shortcuts/Inditas/Example.lnk')
        self.bridge.inventory.return_value=[{'path':str(link),'target':str(launcher),'arguments':'--special-profile'}]
        plan=prepare(self.game('minecraft:java','Minecraft'),self.settings,{},self.hub)
        self.assertEqual((plan.kind,plan.target),('shortcut',str(link)))

    def test_removed_game_and_deleted_executable_are_rejected(self):
        game=Game('x','Removed','Steam',str(self.root),installed=False)
        with self.assertRaisesRegex(ValueError,'no longer installed'):
            prepare(game,self.settings,{},self.hub)
        exe=self.file('Game with spaces/play.exe')
        plan=prepare(self.game(),self.settings,{},self.hub)
        exe.unlink()
        with patch('gametime.launch.subprocess.Popen') as popen,self.assertRaises(ValueError):
            execute(plan)
        popen.assert_not_called()

    def test_unrecognized_uri_scheme_is_rejected(self):
        with patch('gametime.launch.os.startfile',create=True) as start,self.assertRaises(ValueError):
            execute(LaunchPlan('uri','https://example.com'))
        start.assert_not_called()

    def test_worker_only_prepares_and_shutdown_never_executes(self):
        self.hub.launch_recipe=Mock(return_value={'kind':'url','url':'steam://rungameid/42'})
        worker=LaunchWorker(self.base,self.hub)
        with patch('gametime.launch.execute') as run:
            try:
                game=self.game('steam:42','Steam')
                worker.request(game,self.settings,{})
                returned,plan,error=worker.results.get(timeout=3)
                self.assertEqual(returned,game); self.assertIsNone(error)
                self.assertEqual(plan.kind,'uri')
            finally:
                worker.close()
            run.assert_not_called()
        self.assertFalse(worker.thread.is_alive())

    def test_explicit_executable_persists_and_follows_discovery_id_merge(self):
        path=self.base/'usage.sqlite3'; store=Store(path)
        old=self.game('manual:old','Kézi'); new=self.game('steam:42','Steam')
        store.upsert([old]); store.set_launch_executable(old.id,str(self.root/'play.exe'))
        store.close(); store=Store(path)
        self.assertEqual(store.launch_executable(old.id),str(self.root/'play.exe'))
        store.reconcile([new],lambda game:game.source=='Steam')
        self.assertEqual(store.launch_executable(new.id),str(self.root/'play.exe'))
        self.assertEqual(store.launch_executable(old.id),'')
        store.close()

    @unittest.skipUnless(os.name=='nt','Windows mutex required')
    def test_hub_shortcut_reuses_running_profile_and_requests_hub_page(self):
        from gametime.win32 import Instance
        data=self.base/'Profile with spaces'; data.mkdir()
        owner=Instance(data)
        try:
            self.assertTrue(owner.acquired)
            result=subprocess.run([sys.executable,'-B','main.py','--hub','--data-dir',str(data)],
                                  cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((data/'show-hub.request').is_file())
            self.assertFalse((data/'show.request').exists())
        finally:
            owner.close()

    def test_removing_or_reassigning_tracking_rule_clears_stale_launch_choice(self):
        store=Store(self.base/'usage.sqlite3')
        self.addCleanup(store.close)
        exe=str(self.root/'play.exe')
        for action in (lambda:store.delete_rule(exe),lambda:store.set_rule(exe,None),lambda:store.set_rule(exe,'other')):
            store.set_rule(exe,'game'); store.set_launch_executable('game',exe)
            action()
            self.assertEqual(store.launch_executable('game'),'')

    def test_failed_discovery_merge_does_not_commit_launch_choice_or_partial_history(self):
        store=Store(self.base/'usage.sqlite3')
        self.addCleanup(store.close)
        old=self.game('manual:old','Kézi'); new=self.game('steam:42','Steam')
        store.upsert([old]); store.set_launch_executable(old.id,str(self.root/'play.exe'))
        store.add_usage({('2026-10-18',old.id):60})
        with patch.object(store,'upsert',side_effect=RuntimeError('incomplete discovery')),self.assertRaises(RuntimeError):
            store.reconcile([new],lambda game:game.source=='Steam')
        self.assertEqual(store.launch_executable(new.id),'')
        self.assertEqual(store.launch_executable(old.id),str(self.root/'play.exe'))
        self.assertEqual(store.totals('2026-10-18'),{old.id:60})


if __name__=='__main__': unittest.main()
