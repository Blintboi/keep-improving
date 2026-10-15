from datetime import datetime, timedelta, timezone
import json
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
from gametime.riot import RiotSource, WindowsRiotRegistry, install_fields
from gametime.service import DiscoveryService
from gametime.store import Store
from gametime.tracker import Tracker, Sample


class FakeRegistry:
    def __init__(self):
        self.data = {"games": [], "errors": []}

    def read(self):
        return self.data

    def watch_specs(self):
        return set()


class RiotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.registry = FakeRegistry()
        self.source = RiotSource(self.base / "Metadata", self.base / "RiotClientInstalls.json", self.registry)

    def metadata(self, product="valorant.live", folder="Riot Games/VALORANT/live", **fields):
        root = self.base / folder
        root.mkdir(parents=True, exist_ok=True)
        file = self.source.metadata_root / product / (product + ".product_settings.yaml")
        file.parent.mkdir(parents=True, exist_ok=True)
        data = {"product_install_full_path": str(root), "product_install_root": str(self.base / "Riot Games")}
        data.update(fields)
        file.write_text("\n".join(k + ": " + json.dumps(v) for k, v in data.items()), encoding="utf-8")
        return root, file

    def index(self, *roots):
        self.source.client_index.write_text(json.dumps({"associated_client": {
            str(root): "C:/Riot Games/Riot Client/RiotClientServices.exe" for root in roots}}), encoding="utf-8")

    def discovery(self):
        return Discovery(Settings(games_root=str(self.base / "Games")), [], [], self.base / "none.dat",
                         ubisoft=False, riot=self.source)

    def test_valorant_metadata_exact_live_root(self):
        root, file = self.metadata()
        game = self.source.scan()[0]
        self.assertEqual((game.id, game.name, game.source, game.root, game.metadata),
                         ("riot:valorant.live", "VALORANT", "Riot", str(root), str(file)))
        catalog = Catalog(Settings(), [game])
        self.assertEqual(catalog.resolve(str(root / "ShooterGame/Binaries/Win64/VALORANT-Win64-Shipping.exe")), game)

    def test_later_unknown_riot_product_is_supported(self):
        self.metadata()
        root, _ = self.metadata("future_game.live", "Other Drive/Future", shortcut_name="Future Game.lnk")
        games = {g.id: g for g in self.source.scan()}
        self.assertEqual(games["riot:future_game.live"].name, "Future Game")
        self.assertEqual(games["riot:future_game.live"].root, str(root))

    def test_preview_only_is_not_installed_game(self):
        folder = self.source.metadata_root / "league_of_legends.live"
        folder.mkdir(parents=True)
        (folder / "league_of_legends.live.preview.manifest").write_text("preview", encoding="utf-8")
        self.assertEqual(self.source.scan(), [])

    def test_registry_fallback_arbitrary_drive_and_patchline(self):
        root = self.base / "Custom Install"
        root.mkdir()
        self.registry.data["games"] = [{"id": "league_of_legends.pbe", "root": str(root), "name": "League PBE"}]
        game = self.source.scan()[0]
        self.assertEqual((game.id, game.name, game.root), ("riot:league_of_legends.pbe", "League PBE", str(root)))

    def test_metadata_wins_over_stale_registry_location(self):
        root, _ = self.metadata()
        stale = self.base / "Old"
        stale.mkdir()
        self.registry.data["games"] = [{"id": "valorant.live", "root": str(stale), "name": "VALORANT"}]
        games = self.source.scan()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].root, str(root))

    def test_move_and_remove(self):
        self.metadata()
        self.source.scan()
        root, file = self.metadata(folder="New Drive/VALORANT/live")
        self.assertEqual(self.source.scan()[0].root, str(root))
        file.unlink()
        self.assertEqual(self.source.scan(), [])

    def test_partial_metadata_cache_and_restart_preservation(self):
        _, file = self.metadata()
        saved = self.source.scan()
        file.write_text('product_install_full_path: "incomplete', encoding="utf-8")
        self.assertEqual(self.source.scan(), saved)
        fresh = RiotSource(self.source.metadata_root, self.source.client_index, self.registry)
        self.assertEqual(fresh.scan(), [])
        self.assertEqual(preserve_unreadable([], saved, fresh.errors), saved)

    def test_registry_permission_failure_preserves_saved_game(self):
        root = self.base / "Game"
        root.mkdir()
        self.registry.data["games"] = [{"id": "valorant.live", "root": str(root)}]
        saved = self.source.scan()
        self.registry.data = {"games": [], "errors": ["registry:Riot:HKLM\\Uninstall"]}
        self.assertEqual(preserve_unreadable(self.source.scan(), saved, self.source.errors), saved)

    def test_invalid_roots_client_and_vanguard_are_rejected(self):
        client = self.base / "Riot Client"
        client.mkdir()
        vanguard = self.base / "Riot Vanguard"
        vanguard.mkdir()
        self.registry.data["games"] = [
            {"id": "Riot_Client.", "root": str(client)}, {"id": "vanguard.live", "root": str(vanguard)},
            {"id": "fake.live", "root": str(client)}, {"id": "other.live", "root": str(vanguard)},
            {"id": "valorant.live", "root": "relative"}, {"id": "bad", "root": str(self.base)},
            {"id": "missing.live", "root": str(self.base / "missing")},
            {"id": "drive.live", "root": str(self.base.anchor)}]
        self.assertEqual(self.source.scan(), [])

    def test_yaml_plain_single_double_quotes_and_nested_fields(self):
        self.assertEqual(install_fields("product_install_full_path: 'E:/Riot Games/Player''s Game' # comment")
                         ["product_install_full_path"], "E:/Riot Games/Player's Game")
        self.assertEqual(install_fields('product_install_full_path: "E:/Riot Games/VALORANT/live" # comment')
                         ["product_install_full_path"], "E:/Riot Games/VALORANT/live")
        self.assertEqual(install_fields("settings:\n    product_install_full_path: C:/wrong\n"
                                       "product_install_full_path: E:/Riot Games/LoL # comment")
                         ["product_install_full_path"], "E:/Riot Games/LoL")
        for text in ("settings: {}", "product_install_full_path: ''", 'product_install_full_path: "broken',
                     "product_install_full_path: 'broken", 'product_install_full_path: "C:/Game" trailing'):
            with self.assertRaises(ValueError):
                install_fields(text)

    def test_client_index_fallback_and_invalid_index_cache(self):
        root = self.base / "New Product"
        root.mkdir()
        self.index(root)
        self.assertEqual(self.source.scan(), [])
        self.assertEqual(self.source.hints[0].root, str(root))
        self.source.client_index.write_text('{"associated_client":', encoding="utf-8")
        self.source.scan()
        self.assertEqual(self.source.hints[0].root, str(root))
        self.source.client_index.unlink()
        self.source.scan()
        self.assertEqual(self.source.hints, [])

    def test_client_executables_blocked_even_with_manual_rule(self):
        root, _ = self.metadata("league_of_legends.live", "Riot Games/League of Legends")
        game = self.source.scan()[0]
        catalog = Catalog(Settings(), [game])
        self.assertEqual(catalog.resolve(str(root / "Game/League of Legends.exe")), game)
        for name in ("RiotClientServices.exe", "RiotClientUx.exe", "RiotClientUxRender.exe", "vgc.exe", "vgtray.exe",
                     "LeagueClient.exe", "LeagueClientUx.exe", "LeagueClientUxRender.exe"):
            path = str(root / name)
            catalog.rules[norm(path)] = game.id
            self.assertIsNone(catalog.resolve(path), name)
        for path in (str(root / "Riot Client/unknown.exe"), str(root / "Riot Vanguard/unknown.exe")):
            catalog.rules[norm(path)] = game.id
            self.assertIsNone(catalog.resolve(path))

    def test_manual_migration_preserves_time_rules_exclusion_and_settings(self):
        root, _ = self.metadata()
        store = Store(self.base / "usage.sqlite3")
        self.addCleanup(store.close)
        settings = Settings(games_root=str(self.base / "Games"), limit_seconds=5400, warning_seconds=4800)
        store.save_settings(settings)
        prior = Game("manual:valorant", "VALORANT", "Kézi", str(root))
        store.upsert([prior])
        store.add_usage({("2026-10-15", prior.id): 321})
        store.set_enabled(prior.id, False)
        exe = str(root / "VALORANT.exe")
        store.set_rule(exe, prior.id)
        catalog = Catalog(settings, [prior], store.overrides(), store.rules())
        tracker = Tracker(store, catalog)
        tracker.reconcile(self.source.scan(), lambda g: g.source == "Riot")
        self.assertEqual(store.totals("2026-10-15"), {"riot:valorant.live": 321})
        self.assertFalse(store.overrides()["riot:valorant.live"])
        self.assertEqual(store.rules()[norm(exe)], "riot:valorant.live")
        self.assertEqual(store.settings(), settings)
        self.assertNotIn(prior.id, catalog.games)

    def test_first_launch_time_merges_from_client_index_to_product(self):
        root = self.base / "Riot Games/VALORANT/live"
        root.mkdir(parents=True)
        self.index(root)
        self.source.scan()
        store = Store(self.base / "usage.sqlite3")
        self.addCleanup(store.close)
        catalog = Catalog(Settings())
        catalog.riot_hints = list(self.source.hints)
        tracker = Tracker(store, catalog)
        start = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
        for sec in range(6):
            tracker.tick(Sample(start + timedelta(seconds=sec), sec, str(root / "VALORANT.exe"), "42:created"))
        self.metadata()
        tracker.reconcile(self.source.scan(), lambda g: g.source == "Riot")
        self.assertEqual(tracker.totals("2026-10-15"), {"riot:valorant.live": 5})

    def test_discovery_uses_only_small_installation_indexes(self):
        self.metadata()
        discovery = self.discovery()
        with patch("os.walk", side_effect=AssertionError("Do not walk Riot game content")):
            self.assertEqual([g.id for g in discovery.scan_launchers()], ["riot:valorant.live"])
        specs = discovery.watch_specs()
        self.assertIn((str(self.source.metadata_root), True, "riot"), specs)
        self.assertNotIn((str(self.base / "Riot Games"), True, "riot"), specs)

    def test_patch_payload_events_ignored_but_install_metadata_triggers(self):
        root, file = self.metadata()
        service = DiscoveryService(Settings(), discovery=self.discovery())
        requested = []
        service.request = lambda *args: requested.append(args)
        target = str(self.source.metadata_root)
        service._event("riot", target, str(file.with_suffix(".manifest")))
        service._event("riot", target, str(file.with_suffix(".db")))
        self.assertEqual(requested, [])
        service._event("riot", target, str(file))
        service._event("riot", target, str(file.parent))
        self.assertEqual(requested, [("launchers",), ("launchers",)])


@unittest.skipUnless(os.name == "nt", "Windows required")
class RiotNativeTests(unittest.TestCase):
    def await_games(self, service, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                result = service.results.get(timeout=.2)
            except Empty:
                continue
            if result[0] == "launchers" and predicate(result[1]):
                return result[1]
        self.fail("Riot discovery did not react to installation change")

    def test_native_metadata_create_move_remove_without_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = RiotSource(base / "Metadata", base / "RiotClientInstalls.json", FakeRegistry())
            settings = Settings(games_root=str(base / "Games"))
            discovery = Discovery(settings, [], [], base / "none.dat", ubisoft=False, riot=source)
            service = DiscoveryService(settings, discovery=discovery)
            service.start()
            try:
                self.await_games(service, lambda games: not games)
                for watcher, _ in list(service.watchers.values()):
                    self.assertTrue(watcher.ready.wait(3))
                    self.assertIsNone(watcher.error)
                root = base / "VALORANT/live"
                root.mkdir(parents=True)
                file = source.metadata_root / "valorant.live/valorant.live.product_settings.yaml"
                file.parent.mkdir(parents=True)
                file.write_text("product_install_full_path: " + json.dumps(str(root)), encoding="utf-8")
                self.await_games(service, lambda games: any(g.id == "riot:valorant.live" for g in games))
                moved = base / "Other Drive/live"
                moved.mkdir(parents=True)
                file.write_text("product_install_full_path: " + json.dumps(str(moved)), encoding="utf-8")
                self.await_games(service, lambda games: any(g.root == str(moved) for g in games))
                file.unlink()
                self.await_games(service, lambda games: not games)
            finally:
                service.close()
                self.assertFalse(service.thread.is_alive())

    def test_native_registry_install_remove_without_restart(self):
        import winreg
        from gametime import riot
        prefix = "SOFTWARE\\GameTimeMonitor.Riot.Tests." + uuid.uuid4().hex
        uninstall = prefix + "\\Uninstall"
        game_key = uninstall + "\\Riot Game league_of_legends.live"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, prefix):
            pass
        def cleanup():
            for path in (game_key, uninstall, prefix):
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
                except FileNotFoundError:
                    pass
        self.addCleanup(cleanup)
        with tempfile.TemporaryDirectory() as temp, patch.object(riot, "UNINSTALL_KEY", uninstall), \
                patch.object(riot, "SCOPES", (("HKCU", 0),)):
            base = Path(temp)
            source = RiotSource(base / "Metadata", base / "RiotClientInstalls.json", WindowsRiotRegistry())
            settings = Settings(games_root=str(base / "Games"))
            service = DiscoveryService(settings, discovery=Discovery(settings, [], [], base / "none.dat",
                                                                     ubisoft=False, riot=source))
            service.start()
            try:
                self.await_games(service, lambda games: not games)
                for watcher in list(service.registry_watchers.values()):
                    self.assertTrue(watcher.ready.wait(3))
                    self.assertIsNone(watcher.error)
                root = base / "LoL"
                root.mkdir()
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, game_key) as key:
                    winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(root))
                    winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "League of Legends")
                games = self.await_games(service, lambda games: any(g.id == "riot:league_of_legends.live" for g in games))
                self.assertEqual(games[0].root, str(root))
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, game_key)
                self.await_games(service, lambda games: not games)
            finally:
                service.close()
                self.assertFalse(service.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
