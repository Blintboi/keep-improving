from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from queue import Empty
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from gametime.discovery import Discovery, preserve_unreadable
from gametime.model import Catalog, Game, Settings, norm
from gametime.service import DiscoveryService
from gametime.store import Store
from gametime.tracker import Sample, Tracker
from gametime.ubisoft import UbisoftSource, WindowsUbisoftRegistry


class FakeRegistry:
    def __init__(self):
        self.data = {"launchers": [], "games": [], "errors": []}
    def read(self):
        return self.data
    def watch_specs(self):
        return set()


class UbisoftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.registry = FakeRegistry()
        self.source = UbisoftSource(registry=self.registry)

    def record(self, gid="635", name="Rainbow Six", folder="CustomDrive/Game"):
        root = self.base / folder
        root.mkdir(parents=True, exist_ok=True)
        record = {"id": gid, "root": str(root), "name": name}
        self.registry.data["games"].append(record)
        return record

    def test_game_name_id_and_arbitrary_install_location(self):
        record = self.record()
        game = self.source.scan()[0]
        self.assertEqual((game.id, game.name, game.source, game.root), ("ubisoft:635", "Rainbow Six", "Ubisoft", record["root"]))

    def test_multiple_library_locations(self):
        self.record("1", folder="DriveA/A")
        self.record("2", folder="DriveB/B")
        self.assertEqual({g.id for g in self.source.scan()}, {"ubisoft:1", "ubisoft:2"})

    def test_move_and_uninstall(self):
        record = self.record()
        self.source.scan()
        moved = self.base / "NewLocation"
        moved.mkdir()
        record["root"] = str(moved)
        self.assertEqual(self.source.scan()[0].root, str(moved))
        self.registry.data["games"].clear()
        self.assertEqual(self.source.scan(), [])

    def test_missing_directory_and_invalid_registry_records_ignored(self):
        self.registry.data["games"] = [{"id": "635", "root": str(self.base / "missing")},
                                      {"id": "launcher", "root": str(self.base)},
                                      {"id": "1", "root": "relative"}, {"id": "2", "root": 7}]
        self.assertEqual(self.source.scan(), [])

    def test_launcher_root_is_not_registered_as_game(self):
        self.registry.data["launchers"] = [str(self.base)]
        self.registry.data["games"] = [{"id": "1", "root": str(self.base)}]
        self.assertEqual(self.source.scan(), [])
        self.assertIn(str(self.base / "games"), self.source.game_roots)

    def test_missing_name_uses_install_folder(self):
        self.record(name="")
        self.assertEqual(self.source.scan()[0].name, "Game")

    def test_partial_registry_read_preserves_saved_games(self):
        self.record()
        saved = self.source.scan()
        errors = ["registry:Ubisoft:HKLM\\SOFTWARE\\Ubisoft\\Launcher"]
        self.registry.data["games"] = []
        self.registry.data["errors"] = errors
        self.assertEqual(preserve_unreadable(self.source.scan(), saved, self.source.errors), saved)

    def test_discovery_combines_ubisoft_without_walking_game_files(self):
        self.record()
        discovery = Discovery(Settings(games_root=str(self.base / "Games")), [], [], self.base / "none.dat", ubisoft=self.source, riot=False)
        with patch("os.walk", side_effect=AssertionError("Don't scan Ubisoft game content")):
            result = discovery.scan_launchers()
        self.assertEqual(result[0].source, "Ubisoft")

    def test_first_launch_fallback_and_no_launcher_counting(self):
        catalog = Catalog(Settings())
        catalog.ubisoft_libraries = [r"E:\Ubisoft Connect\games"]
        game = catalog.resolve(r"E:\Ubisoft Connect\games\NewGame\bin\game.exe")
        self.assertEqual(game.source, "Ubisoft")
        self.assertTrue(game.id.startswith("pending:ubisoft:"))
        for exe in ("UbisoftConnect.exe", "upc.exe", "UplayWebCore.exe", "UbisoftGameLauncher.exe", "UbisoftExtension.exe"):
            path = r"E:\Ubisoft Connect\games\NewGame" + "\\" + exe
            catalog.rules[norm(path)] = game.id
            self.assertIsNone(catalog.resolve(path))

    def test_manual_to_ubisoft_merge_preserves_time_rules_and_exclusion(self):
        record = self.record()
        old = Game("manual:prior", "Rainbow Six", "Kézi", record["root"])
        store = Store(self.base / "test.sqlite3")
        self.addCleanup(store.close)
        store.upsert([old])
        store.add_usage({("2026-10-15", old.id): 123})
        store.set_enabled(old.id, False)
        exe = str(Path(old.root) / "game.exe")
        store.set_rule(exe, old.id)
        catalog = Catalog(Settings(), [old], store.overrides(), store.rules())
        tracker = Tracker(store, catalog)
        tracker.reconcile(self.source.scan(), lambda g: g.source == "Ubisoft")
        self.assertEqual(store.totals("2026-10-15"), {"ubisoft:635": 123})
        self.assertFalse(store.overrides()["ubisoft:635"])
        self.assertEqual(store.rules()[norm(exe)], "ubisoft:635")
        self.assertNotIn(old.id, catalog.games)
        self.assertIsNone(catalog.resolve(exe))

    def test_ubisoft_first_launch_time_migrates_without_loss(self):
        store = Store(self.base / "test.sqlite3")
        self.addCleanup(store.close)
        catalog = Catalog(Settings())
        catalog.ubisoft_libraries = [str(self.base / "Connect" / "games")]
        root = self.base / "Connect" / "games" / "New"
        root.mkdir(parents=True)
        exe = str(root / "game.exe")
        tracker = Tracker(store, catalog)
        start = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
        for sec in range(6):
            tracker.tick(Sample(start + timedelta(seconds=sec), sec, exe, "42:created"))
        self.registry.data["games"] = [{"id": "42", "root": str(root), "name": "New"}]
        tracker.reconcile(self.source.scan(), lambda g: g.source == "Ubisoft")
        self.assertEqual(tracker.totals("2026-10-15"), {"ubisoft:42": 5})


@unittest.skipUnless(os.name == "nt", "Windows required")
class RegistryNotificationTests(unittest.TestCase):
    def test_real_registry_notification_and_ubisoft_install_move_remove(self):
        import winreg
        from gametime import win32
        from gametime import ubisoft
        prefix = "SOFTWARE\\GameTimeMonitor.Tests." + uuid.uuid4().hex
        launcher_key, uninstall_key = prefix + "\\Launcher", prefix + "\\Uninstall"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, prefix):
            pass
        def delete_owned(path):
            assert path.startswith(prefix)
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ) as key:
                    children = [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
                for child in children:
                    delete_owned(path + "\\" + child)
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
            except FileNotFoundError:
                pass
        self.addCleanup(delete_owned, prefix)
        with tempfile.TemporaryDirectory() as temp, patch.object(ubisoft, "LAUNCHER_KEY", launcher_key), \
                patch.object(ubisoft, "UNINSTALL_KEY", uninstall_key), patch.object(ubisoft, "SCOPES", (("HKCU", 0),)):
            base = Path(temp)
            settings = Settings(games_root=str(base / "Games"))
            source = UbisoftSource(registry=WindowsUbisoftRegistry())
            discovery = Discovery(settings, [], [], base / "none.dat", ubisoft=source, riot=False)
            service = DiscoveryService(settings, discovery=discovery)
            def await_source(predicate, timeout=10):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    try:
                        result = service.results.get(timeout=.2)
                    except Empty:
                        continue
                    if result[0] == "launchers" and predicate(result[1]):
                        return result
                self.fail("Ubisoft registry discovery did not update")
            service.start()
            try:
                await_source(lambda games: not games)
                for watcher in list(service.registry_watchers.values()):
                    self.assertTrue(watcher.ready.wait(3))
                    self.assertIsNone(watcher.error)
                root = base / "Game"
                root.mkdir()
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, launcher_key + r"\Installs\42") as key:
                    winreg.SetValueEx(key, "InstallDir", 0, winreg.REG_SZ, str(root))
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_key + r"\Uplay Install 42") as key:
                    winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(root))
                    winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Fixture Ubisoft Game")
                result = await_source(lambda games: any(g.id == "ubisoft:42" and g.name == "Fixture Ubisoft Game" for g in games))
                self.assertEqual(Path(result[1][0].root), root)
                moved = base / "Moved"
                moved.mkdir()
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, launcher_key + r"\Installs\42", 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, "InstallDir", 0, winreg.REG_SZ, str(moved))
                await_source(lambda games: any(g.root == str(moved) for g in games))
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, launcher_key + r"\Installs\42")
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, uninstall_key + r"\Uplay Install 42")
                await_source(lambda games: not games)
            finally:
                service.close()
                self.assertFalse(service.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
