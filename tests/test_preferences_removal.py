from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from gametime.model import Catalog, Game, Settings
from gametime.store import Store
from gametime.removal import APPS, RemovalPlan, plan_removal, execute


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.store = Store(self.path)
        self.addCleanup(lambda: self.store.close())

    def test_hidden_persists_without_changing_tracking_or_totals(self):
        game = Game('manual:one', 'One', 'Kézi', r'C:\Games\One')
        self.store.upsert([game])
        self.store.add_usage({('2026-10-18', game.id): 123})
        self.store.set_hidden(game.id, True)
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.hidden_ids(), {game.id})
        self.assertTrue(Catalog(Settings(), [game]).enabled(game))
        self.assertEqual(self.store.totals('2026-10-18'), {game.id: 123})
        self.assertEqual(self.store.overrides(), {})
        self.store.set_hidden(game.id, False)
        self.assertFalse(self.store.hidden_ids())

    def test_hidden_follows_manual_to_launcher_migration(self):
        old = Game('manual:one', 'One', 'Kézi', r'C:\Games\One')
        new = replace(old, id='steam:42', source='Steam')
        self.store.upsert([old])
        self.store.set_hidden(old.id, True)
        self.store.reconcile([new], lambda game: game.source == 'Steam')
        self.assertIn(new.id, self.store.hidden_ids())

    def test_fresh_profile_counts_chess_legacy_profile_preserves_exclusion(self):
        game = Game('chess', 'Chess', 'Games', r'C:\Games\Chess')
        self.assertFalse(self.store.settings().exclude_chess)
        self.assertEqual(Catalog(self.store.settings(), [game]).resolve(game.root + r'\chess.exe'), game)
        with self.store.db:
            self.store.db.execute("INSERT INTO settings VALUES ('config',?)", (json.dumps({'games_root': r'C:\Games'}),))
        self.assertTrue(self.store.settings().exclude_chess)
        self.store.save_settings(self.store.settings())
        self.assertTrue(self.store.settings().exclude_chess)


class RemovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'Portable'
        self.root.mkdir()
        self.game = Game('manual:one', 'One', 'Kézi', str(self.root))

    def test_steam_only_uses_numeric_validated_id(self):
        plan = plan_removal(replace(self.game, source='Steam', id='steam:42'))
        self.assertEqual(plan.target, 'steam://uninstall/42')
        self.assertNotIn('steam://', plan_removal(replace(self.game, source='Steam', id='steam:42&malicious'), []).target)

    def test_launchers_fallback_to_settings_when_client_missing(self):
        with patch('gametime.removal._client', return_value=None):
            for source in ('Epic', 'Ubisoft', 'Riot', 'Minecraft'):
                self.assertEqual(plan_removal(replace(self.game, source=source)).target, APPS)

    def test_publisher_client_has_manual_steps_no_guessed_uninstall_flags(self):
        with patch('gametime.removal._client', return_value=r'C:\Epic\EpicGamesLauncher.exe'):
            plan = plan_removal(replace(self.game, source='Epic'))
        self.assertIn('Uninstall', plan.instructions)
        self.assertFalse(plan.arguments)

    def test_portable_opens_folder_without_deleting_anything(self):
        save = self.root / 'save.dat'
        save.write_text('precious save')
        plan = plan_removal(self.game, [])
        self.assertEqual(plan.kind, 'folder')
        with patch('os.startfile', create=True) as launch:
            execute(plan)
        launch.assert_called_once_with(str(self.root))
        self.assertEqual(save.read_text(), 'precious save')

    def test_exact_root_msi_uses_interactive_product_removal(self):
        guid = '{12345678-1234-1234-1234-123456789abc}'
        entry = {'InstallLocation': str(self.root), 'WindowsInstaller': 1, 'key': guid}
        plan = plan_removal(self.game, [entry])
        self.assertEqual(plan.arguments, ('/x', guid))
        entry['InstallLocation'] = str(self.root.parent)
        self.assertEqual(plan_removal(self.game, [entry]).kind, 'folder')

    def test_registry_shell_text_cannot_run_or_escape_installation(self):
        bad = {'InstallLocation': str(self.root), 'UninstallString': 'cmd.exe /c del C:\\*'}
        self.assertEqual(plan_removal(self.game, [bad]).kind, 'folder')
        foreign = self.root.parent / 'uninstall.exe'
        foreign.touch()
        bad['UninstallString'] = f'"{foreign}" /silent'
        self.assertEqual(plan_removal(self.game, [bad]).kind, 'folder')

    def test_local_uninstaller_runs_without_silent_flags(self):
        uninstaller = self.root / 'unins000.exe'
        uninstaller.touch()
        entry = {'InstallLocation': str(self.root), 'UninstallString': f'"{uninstaller}" /VERYSILENT'}
        plan = plan_removal(self.game, [entry])
        self.assertEqual(plan.target, str(uninstaller))
        self.assertEqual(plan.arguments, ())
        with patch('os.startfile', create=True) as launch:
            execute(plan)
        launch.assert_called_once_with(str(uninstaller))

    def test_rejects_arbitrary_uri_and_missing_program(self):
        for plan in (RemovalPlan('bad', '', 'uri', 'powershell:bad'), RemovalPlan('bad', '', 'exe', 'bad.exe')):
            with self.assertRaises((ValueError, FileNotFoundError)):
                execute(plan)


if __name__ == '__main__':
    unittest.main()
