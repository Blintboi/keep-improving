"""Publisher integration fixtures: no installed games, account or real launches."""
from dataclasses import replace
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from gametime.battlenet import installations
from gametime.clients import Client, find_clients, start_client
from gametime.discovery import Discovery, preserve_unreadable
from gametime.hub import Hub
from gametime.launch import execute, prepare
from gametime.model import Catalog, Game, Settings, norm
from gametime.platforms import PlatformSources, WindowsInstallRegistry, PACKAGES, UNINSTALL, xbox_client
from gametime.removal import APPS, plan_removal
from gametime.service import DiscoveryService
from gametime.store import Store
from gametime.tracker import Tracker


class Registry:
    def __init__(self):
        self.data = {'games': [], 'clients': [], 'packages': [], 'errors': []}
    def read(self): return self.data
    def watch_specs(self): return set()


def wire(field, value):
    def varint(number):
        result = bytearray()
        while number >= 128:
            result.append((number & 127) | 128)
            number >>= 7
        return bytes(result) + bytes([number])
    if isinstance(value, str): value = value.encode()
    if isinstance(value, bytes): return varint(field * 8 + 2) + varint(len(value)) + value
    return varint(field * 8) + varint(value)


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.registry = Registry()
        self.amazon = self.base / 'Amazon/index.sqlite'
        self.battle = self.base / 'Battle.net/product.db'
        self.source = PlatformSources(self.registry, self.amazon, self.battle)
        self.settings = Settings(games_root=str(self.base / 'Hub'))
        self.bridge = Mock(); self.bridge.inventory.return_value = []
        self.hub = Hub(self.base / 'Profile', self.bridge, locations=[])

    def folder(self, name):
        root = self.base / name; root.mkdir(parents=True, exist_ok=True); return root

    def exe(self, name):
        path = self.base / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'MZ fixture, never execute'); return path

    def record(self, source, key, **extra):
        row = dict(source=source, key=key, DisplayName=key, InstallLocation=str(self.folder('Drive D/' + key)))
        row.update(extra); self.registry.data['games'].append(row); return row

    def package(self, name='Fixture.Game', game=True, classic=False):
        root = self.folder(name)
        extension = '<Extensions><Extension Name="XboxLive"/></Extensions>' if classic else ''
        (root / 'AppxManifest.xml').write_text(f'<Package><Identity Name="{name}"/><Applications><Application Id="Game"><VisualElements DisplayName="Classic Game"/>{extension}</Application></Applications></Package>')
        if game:
            (root / 'MicrosoftGame.config').write_text('<Game><Identity Name="Fixture.Game"/><ShellVisuals DefaultDisplayName="Fixture Xbox Game"/><ExecutableList><Executable Name="Game.exe" Id="Game"/></ExecutableList></Game>')
        row = {'name': name, 'family': name + '_abc1234567890', 'root': str(root)}
        self.registry.data['packages'].append(row); return row

    def test_all_new_clients_are_installed_only_and_deduplicated(self):
        paths = [self.exe(value) for value in ('EA/EADesktop.exe', 'GOG/GalaxyClient.exe', 'Battle.net/Battle.net.exe',
                 'Rockstar Games/Launcher/Launcher.exe', 'Amazon/Amazon Games.exe', 'Xbox/XboxPcApp.exe')]
        rows = [{'target': str(path), 'arguments': ''} for path in paths]
        found = find_clients(self.settings, rows + rows, candidates=[])
        self.assertEqual({client.id for client in found}, {'ea', 'gog', 'battlenet', 'rockstar', 'amazon', 'xbox'})
        self.assertEqual(find_clients(self.settings, [], candidates=[]), [])
        wrong = self.exe('Other game/Launcher.exe')
        self.assertEqual(find_clients(self.settings, [{'target': str(wrong)}], candidates=[]), [])
        self.assertEqual(find_clients(self.settings, [{'target': str(paths[0]), 'arguments': '--game=fixture'}], candidates=[]), [])

    def test_new_client_start_revalidates_and_never_passes_game_arguments(self):
        for identity, filename in [('ea', 'EADesktop.exe'), ('gog', 'GalaxyClient.exe'), ('battlenet', 'Battle.net.exe'),
                                    ('rockstar', 'Rockstar Games/Launcher/Launcher.exe'), ('amazon', 'Amazon Games.exe')]:
            path = self.exe(filename)
            with self.subTest(client=identity), patch('gametime.clients.subprocess.Popen') as launch:
                start_client(Client(identity, identity, str(path)))
                launch.assert_called_once_with([str(path)], cwd=str(path.parent), shell=False)
                path.unlink()
                with self.assertRaises(ValueError): start_client(Client(identity, identity, str(path)))

    def test_custom_rockstar_client_requires_its_service_marker(self):
        path = self.exe('Custom client folder/Launcher.exe')
        self.assertEqual(find_clients(self.settings, candidates=[str(path)]), [])
        self.exe('Custom client folder/RockstarService.exe')
        found = find_clients(self.settings, candidates=[str(path)])
        self.assertEqual([client.id for client in found], ['rockstar'])

    def test_registered_games_work_on_custom_drives_and_deduplicate_views(self):
        self.record('EA', 'The Sims 4')
        self.record('GOG', '1207658691', gameName='GOG fixture')
        self.record('Battle.net', 'World of Warcraft', UninstallString='"D:\\Battle.net\\Battle.net.exe" --uid=wow --uninstall')
        self.record('Rockstar', 'Grand Theft Auto V', UninstallString='"D:\\Rockstar Games\\Launcher\\Launcher.exe" -uninstall=gta5', Publisher='Rockstar Games')
        self.registry.data['games'] *= 2
        with patch('os.walk', side_effect=AssertionError('No publisher content walk')):
            games = self.source.scan()
        self.assertEqual({game.source for game in games}, {'EA', 'GOG', 'Battle.net', 'Rockstar'})
        self.assertEqual(len(games), 4)
        self.assertIn('gog:1207658691', {game.id for game in games})
        self.assertIn('battlenet:wow', {game.id for game in games})

    def test_clients_helpers_missing_and_unsafe_installations_are_not_games(self):
        self.record('EA', 'EA app')
        self.record('EA', 'EA anticheat')
        self.record('GOG', 'GalaxyClient')
        self.record('Rockstar', 'Rockstar Games Launcher', UninstallString='uninstall.exe -uninstall=launcher')
        self.record('EA', 'Missing', InstallLocation=str(self.base / 'absent'))
        self.record('EA', 'Drive', InstallLocation=self.base.anchor)
        self.record('EA', 'Relative', InstallLocation='relative')
        self.record('EA', 'Network', InstallLocation=r'\\server\game')
        self.assertEqual(self.source.scan(), [])

    def test_move_and_uninstall_keep_id_but_retire_missing_games(self):
        row = self.record('GOG', '42')
        old = self.source.scan()[0]
        row['InstallLocation'] = str(self.folder('Other drive/Game'))
        new = self.source.scan()[0]
        self.assertEqual(old.id, new.id); self.assertNotEqual(old.root, new.root)
        self.registry.data['games'].clear(); self.assertEqual(self.source.scan(), [])

    def test_amazon_sqlite_is_read_only_and_partial_writes_preserve_prior_game(self):
        self.amazon.parent.mkdir()
        game_root = self.folder('Amazon/Game')
        with closing(sqlite3.connect(self.amazon)) as db:
            db.execute('CREATE TABLE DbSet (Id TEXT, ProductTitle TEXT, InstallDirectory TEXT, Installed INTEGER)')
            db.executemany('INSERT INTO DbSet VALUES (?,?,?,?)', [('fixture-id', 'Amazon fixture', str(game_root), 1),
                            ('removed', 'Uninstalled', str(game_root), 0)])
            db.commit()
        before = self.amazon.read_bytes(); games = self.source.scan()
        self.assertEqual(self.amazon.read_bytes(), before)
        self.assertEqual([game.id for game in games], ['amazon:fixture-id'])
        self.amazon.write_bytes(b'partial publisher write')
        result = preserve_unreadable(self.source.scan(), games, self.source.errors)
        self.assertEqual(result, games)

    def test_battlenet_product_index_including_classic_layout_and_partial_write(self):
        root = self.folder('Blizzard/Overwatch')
        product = wire(1, 'prometheus') + wire(2, 'pro') + wire(3, wire(1, str(root)))
        agent = wire(1, 'battle.net') + wire(2, 'bna') + wire(3, wire(1, str(root)))
        removed = wire(1, 'wow') + wire(2, 'wow') + wire(3, wire(1, str(root))) + wire(4, wire(1, wire(1, 0)))
        self.battle.parent.mkdir(); self.battle.write_bytes(wire(1, product) + wire(1, agent) + wire(1, removed))
        games = self.source.scan()
        self.assertEqual([(game.id, game.name) for game in games], [('battlenet:prometheus', 'Overwatch')])
        self.battle.write_bytes(product)
        self.assertEqual(self.source.scan(), games)
        self.battle.write_bytes(b'\x0a\xff')
        self.assertEqual(preserve_unreadable(self.source.scan(), games, self.source.errors), games)
        for malformed in (b'\x80' * 12, b'\x00', b'\x0f', b'\x0a\xff'):
            self.battle.write_bytes(malformed)
            with self.assertRaises(ValueError): installations(self.battle)

    def test_xbox_games_use_gdk_or_xboxlive_metadata_not_all_store_apps(self):
        package = self.package()
        self.package('Fixture.Calculator', game=False)
        self.package('Fixture.Classic', game=False, classic=True)
        self.package('Microsoft.GamingApp', game=False)
        self.package('Microsoft.XboxGamingOverlay', game=False, classic=True)
        games = self.source.scan()
        self.assertEqual({game.name for game in games}, {'Fixture Xbox Game', 'Classic Game'})
        self.assertEqual({game.source for game in games}, {'Xbox'})
        game = next(game for game in games if 'Fixture.Game_' in game.id)
        plan = prepare(game, self.settings, {}, self.hub)
        self.assertEqual((plan.kind, plan.target), ('app', package['family'] + '!Game'))
        with patch('gametime.launch.os.startfile', create=True) as launch:
            execute(plan); launch.assert_called_once_with('shell:AppsFolder\\' + plan.target)
        with self.assertRaises(ValueError): prepare(replace(game, id='xbox:Other.Package_abc1234567890!Game'), self.settings, {}, self.hub)

    def test_xbox_chooses_the_registered_game_app_over_a_hidden_package_helper(self):
        package = self.package()
        manifest = Path(package['root']) / 'AppxManifest.xml'
        manifest.write_text('<Package><Identity Name="Fixture.Game"/><Applications>'
                            '<Application Id="Hidden"><VisualElements AppListEntry="none"/></Application>'
                            '<Application Id="Game"><VisualElements DisplayName="Game"/></Application>'
                            '</Applications></Package>')
        self.assertEqual(self.source.scan()[0].id, 'xbox:' + package['family'] + '!Game')

    def test_store_installations_do_not_add_watches_on_the_protected_container(self):
        package = self.package()
        root = self.folder('WindowsApps/Fixture.Game')
        for filename in ('AppxManifest.xml', 'MicrosoftGame.config'):
            (root / filename).write_bytes((Path(package['root']) / filename).read_bytes())
        package['root'] = str(root)
        discovery = Discovery(self.settings, [], [], self.base / 'none.dat', ubisoft=False, riot=False, platforms=self.source)
        self.assertTrue(discovery.scan_launchers())
        self.assertFalse(any(Path(path).name.lower() == 'windowsapps' for path, recursive, kind in discovery.watch_specs()))

    def test_packaged_xbox_client_must_exist_and_is_revalidated_on_open(self):
        package = self.package('Microsoft.GamingApp', game=False)
        appid = xbox_client(self.registry.data['packages'])
        self.assertEqual(appid, package['family'] + '!Game')
        client = Client('xbox', 'Xbox', appid, 'app')
        with patch('gametime.platforms.WindowsInstallRegistry', return_value=self.registry), patch('gametime.clients.os.startfile', create=True) as launch:
            start_client(client); launch.assert_called_once_with('shell:AppsFolder\\' + appid)
            self.registry.data['packages'].clear()
            with self.assertRaises(ValueError): start_client(client)
            with self.assertRaises(ValueError): start_client(replace(client, target=''))

    @unittest.skipUnless(os.name == 'nt', 'Windows registry adapter')
    def test_windows_registry_adapter_reads_publisher_records_in_both_views(self):
        import winreg
        roots = {name: str(self.folder('Registry fixture/' + name)) for name in ('GOG', 'EA', 'Blizzard', 'Rockstar', 'Client')}
        records = {
            (UNINSTALL, 'Blizzard'): {'DisplayName': 'Blizzard fixture', 'InstallLocation': roots['Blizzard'], 'UninstallString': 'Battle.net.exe --uid=prometheus --uninstall'},
            (UNINSTALL, 'Rockstar'): {'DisplayName': 'Rockstar fixture', 'InstallLocation': roots['Rockstar'], 'UninstallString': 'Launcher.exe -uninstall=gta5', 'Publisher': 'Rockstar Games'},
            (UNINSTALL, 'EA'): {'DisplayName': 'EA fixture', 'InstallLocation': roots['EA'], 'Publisher': 'Electronic Arts'},
            (UNINSTALL, 'Client'): {'DisplayName': 'EA app', 'InstallLocation': roots['Client']},
            (r'Software\GOG.com\Games', '42'): {'gameName': 'GOG fixture', 'PATH': roots['GOG']},
            (PACKAGES, 'Fixture.Game_1.0.0.0_x64__abc1234567890'): {'PackageRootFolder': roots['GOG']},
        }
        flattened = {parent + '\\' + child: values for (parent, child), values in records.items()}
        parents = {parent: [child for owner, child in records if owner == parent] for parent, child in records}
        def open_key(hive, key, *args):
            if key not in flattened and key not in parents: raise FileNotFoundError(key)
            handle = Mock(); handle.__enter__ = Mock(return_value=key); handle.__exit__ = Mock(return_value=False); return handle
        def value(key, name):
            if name not in flattened.get(key, {}): raise FileNotFoundError(name)
            return flattened[key][name], 1
        with patch('winreg.OpenKey', side_effect=open_key), patch('winreg.QueryInfoKey', side_effect=lambda key: (len(parents.get(key, [])), 0, 0)), \
             patch('winreg.EnumKey', side_effect=lambda key, index: parents[key][index]), patch('winreg.QueryValueEx', side_effect=value):
            snapshot = WindowsInstallRegistry().read()
        self.assertFalse(snapshot['errors'])
        self.assertEqual({row['source'] for row in snapshot['games']}, {'GOG', 'EA', 'Battle.net', 'Rockstar'})
        self.assertTrue(any(path.endswith('eadesktop.exe') for path in snapshot['clients']))
        self.assertEqual(snapshot['packages'][0]['family'], 'Fixture.Game_abc1234567890')

    def test_registry_failure_retains_only_affected_publishers(self):
        games = [Game(source.lower() + ':1', source, source, str(self.base), 'registry:' + source + ':1')
                 for source in ('GOG', 'EA', 'Battle.net', 'Rockstar', 'Steam')]
        self.assertEqual(preserve_unreadable([], games, ['registry:GOG:HKLM\\Software']), [games[0]])
        self.assertEqual(preserve_unreadable([], games, ['registry:Publishers:HKCU\\Uninstall']), games[:-1])

    def test_launcher_processes_never_count_even_with_exact_game_assignments(self):
        game = Game('gog:42', 'Fixture', 'GOG', str(self.base))
        catalog = Catalog(self.settings, [game])
        for path in ('EADesktop.exe', 'EALauncher.exe', 'EABackgroundService.exe', 'EACefSubProcess.exe',
                     'GalaxyClient.exe', 'GalaxyCommunication.exe', 'Battle.net.exe', 'Battle.net Helper.exe',
                     'Rockstar Games/Launcher/Launcher.exe', 'SocialClubHelper.exe', 'Amazon Games.exe',
                     'Amazon Games UI.exe', 'XboxPcApp.exe', 'GamingServices.exe'):
            target = str(self.base / path); catalog.rules[norm(target)] = game.id
            with self.subTest(executable=path): self.assertIsNone(catalog.resolve(target))
        real = str(self.base / 'bin/actual-game.exe'); self.assertEqual(catalog.resolve(real), game)

    def test_manual_history_exclusions_hidden_state_and_assignments_migrate(self):
        self.record('GOG', '42')
        new = self.source.scan()[0]; old = replace(new, id='manual:prior', source='Kézi')
        store = Store(self.base / 'profile.sqlite3'); self.addCleanup(store.close)
        store.upsert([old]); store.add_usage({('2026-10-22', old.id): 123})
        store.set_enabled(old.id, False); store.set_rule(str(Path(old.root) / 'game.exe'), old.id)
        store.set_hidden(old.id, True)
        tracker = Tracker(store, Catalog(self.settings, [old], store.overrides(), store.rules()))
        tracker.reconcile([new], lambda game: game.source == 'GOG')
        self.assertEqual(store.totals('2026-10-22'), {'gog:42': 123})
        self.assertFalse(store.overrides()['gog:42']); self.assertIn('gog:42', store.hidden_ids())
        self.assertEqual(set(store.rules().values()), {'gog:42'})

    def test_discovery_prefers_existing_steam_source_for_same_installation(self):
        row = self.record('EA', 'Shared')
        apps = self.folder('Steam/steamapps')
        root = Path(row['InstallLocation'])
        (apps / 'appmanifest_42.acf').write_text('"AppState" {"appid" "42" "name" "Shared" "installdir" "Shared"}')
        # Root equality is the de-duplication criterion, not the game's title.
        row['InstallLocation'] = str(self.folder('Steam/steamapps/common/Shared'))
        discovery = Discovery(self.settings, [str(apps.parent)], [], self.base / 'none.dat', ubisoft=False, riot=False, platforms=self.source)
        self.assertEqual([game.id for game in discovery.scan_launchers()], ['steam:42'])

    def test_existing_folder_and_reidentified_publisher_preserve_per_game_preferences(self):
        self.record('EA', 'Fixture')
        new = self.source.scan()[0]
        for previous_source in ('Games', 'EA'):
            with self.subTest(previous_source=previous_source):
                store = Store(self.base / (previous_source + '.sqlite3')); self.addCleanup(store.close)
                old = replace(new, id='old:' + previous_source, source=previous_source)
                store.upsert([old]); store.add_usage({('2026-10-22', old.id): 321}); store.set_enabled(old.id, False)
                store.set_hidden(old.id, True)
                store.reconcile([new], lambda game: game.source == 'EA')
                self.assertEqual(store.totals('2026-10-22'), {new.id: 321})
                self.assertFalse(store.overrides()[new.id]); self.assertIn(new.id, store.hidden_ids())

    def test_publisher_launches_keep_quoted_paths_and_only_explicit_launch_operations(self):
        gog = self.exe('GOG Galaxy/GalaxyClient.exe')
        rockstar = self.exe('Rockstar Games/Launcher/Launcher.exe')
        battle = self.exe('Battle.net/Battle.net.exe')
        self.bridge.inventory.return_value = [{'path': str(path.with_suffix('.lnk')), 'target': str(path), 'arguments': ''} for path in (gog, rockstar, battle)]
        root = self.folder('Games with spaces/Title')
        for game, target, arguments in [
            (Game('gog:42', 'GOG', 'GOG', str(root)), gog, ('/command=runGame', '/gameId=42', '/path=' + str(root))),
            (Game('rockstar:gta5', 'GTA', 'Rockstar', str(root)), rockstar, ('-launchTitleInFolder', str(root))),
            (Game('battlenet:prometheus', 'Overwatch', 'Battle.net', str(root)), battle, ('--exec=launch Pro',)),
        ]:
            with self.subTest(source=game.source), patch('gametime.launch.subprocess.Popen') as launch:
                plan = prepare(game, self.settings, {}, self.hub)
                self.assertEqual(plan.arguments, arguments); execute(plan)
                launch.assert_called_once_with([str(target), *arguments], cwd=str(target.parent), shell=False)
                self.assertEqual(plan_removal(game).target, APPS)

    def test_ea_and_amazon_uris_cannot_be_changed_into_uninstall_actions(self):
        root = self.folder('EA/Game'); installer = self.folder('EA/Game/__Installer')
        (installer / 'installerdata.xml').write_text('<DiPManifest><contentIDs><contentID>Origin.OFR.50.123</contentID></contentIDs></DiPManifest>')
        for game, url in [(Game('ea:fixture', 'EA', 'EA', str(root)), 'origin2://game/launch?offerIds=Origin.OFR.50.123&action=uninstall'),
                          (Game('amazon:fixture-id', 'Amazon', 'Amazon', str(root)), 'amazon-games://play/fixture-id?action=uninstall')]:
            shortcut = self.base / 'fixture.url'; shortcut.write_text('URL=' + url)
            self.bridge.inventory.return_value = [{'path': str(shortcut), 'contents': 'URL=' + url}]
            plan = prepare(game, self.settings, {}, self.hub)
            self.assertEqual(plan.kind, 'uri'); self.assertNotIn('uninstall', plan.target)

    def test_gog_offline_primary_task_preserves_arguments_and_rejects_path_escape(self):
        root = self.folder('Offline GOG game')
        exe = self.exe('Offline GOG game/bin/play.exe')
        game = Game('gog:42', 'Offline', 'GOG', str(root))
        manifest = root / 'goggame-42.info'
        task = {'isPrimary': True, 'type': 'FileTask', 'path': 'bin/play.exe', 'workingDir': 'bin',
                'arguments': '--profile "A profile with spaces"'}
        manifest.write_text(json.dumps({'gameId': '42', 'playTasks': [task]}))
        with patch.dict(os.environ, {'ProgramFiles': str(self.base / 'absent'), 'ProgramFiles(x86)': str(self.base / 'absent'), 'LOCALAPPDATA': str(self.base / 'absent')}):
            plan = prepare(game, self.settings, {}, self.hub)
            self.assertEqual(plan.target, str(exe)); self.assertEqual(plan.arguments, ('--profile', 'A profile with spaces'))
            other = self.exe('outside.exe'); task['path'] = str(other)
            manifest.write_text(json.dumps({'gameId': '42', 'playTasks': [task]}))
            # The one genuine EXE in the game's directory remains the fallback.
            plan = prepare(game, self.settings, {}, self.hub)
            self.assertEqual(plan.target, str(exe)); self.assertFalse(plan.arguments)

    def test_publisher_file_events_request_one_debounced_scan(self):
        discovery = Discovery(self.settings, [], [], self.base / 'none.dat', ubisoft=False, riot=False, platforms=self.source)
        service = DiscoveryService(self.settings, discovery=discovery, watcher_factory=Mock())
        service._event('publishers', (str(self.amazon.parent),), str(self.amazon) + '-wal')
        self.assertIn(('launchers', ''), service.debounce.jobs)
        service.debounce.jobs.clear()
        service._event('publishers', (str(self.amazon.parent),), str(self.amazon.parent / 'unrelated.log'))
        self.assertFalse(service.debounce.jobs)


if __name__ == '__main__': unittest.main()
