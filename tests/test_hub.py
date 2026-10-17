import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from gametime.hub import Hub, HubWorker, MARKER, PowerShellLinks, digest, safe_name, same_game_link, url_value
from gametime.model import Game, Settings, norm


class FakeLinks:
    def __init__(self):
        self.links = []
        self.created = 0

    def inventory(self, roots):
        result = list(self.links)
        for root in roots:
            path = Path(root["path"])
            if path.is_dir():
                for file in path.glob("*.lnk"):
                    try:
                        data = json.loads(file.read_text(encoding="utf-8"))
                        result.append(dict(data, path=str(file)))
                    except (ValueError, UnicodeError):
                        pass
        return result

    def create(self, links):
        for link in links:
            self.created += 1
            Path(link["path"]).write_text(json.dumps({k: v for k, v in link.items() if k != "path"}), encoding="utf-8")

    def close(self):
        pass


class HubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "Games"
        self.bridge = FakeLinks()
        self.hub = Hub(self.base / "data", self.bridge, [])
        self.settings = Settings(games_root=str(self.root), hub_enabled=True)

    def game(self, gid="steam:123", name="Game", source="Steam", folder="Installed Game"):
        root = self.base / folder
        root.mkdir(exist_ok=True, parents=True)
        return Game(gid, name, source, str(root))

    def state(self):
        return json.loads(self.hub.state_path.read_text(encoding="utf-8"))

    def launch(self, gid):
        return next(Path(row["path"]) for row in self.state()["links"] if row["gid"] == gid and row["role"] == "launch")

    def test_steam_and_ubisoft_use_product_protocols(self):
        games = [self.game(), self.game("ubisoft:456", "Other", "Ubisoft", "Ubisoft Game")]
        report = self.hub.sync(self.settings, games, {}, {})
        self.assertEqual(report["games"], 2)
        self.assertEqual(url_value(self.launch("steam:123").read_text()), "steam://rungameid/123")
        self.assertEqual(url_value(self.launch("ubisoft:456").read_text()), "uplay://launch/456/0")

    def test_epic_metadata_keeps_namespace_and_catalog_id(self):
        game = self.game("epic:app_name", "Epic Game", "Epic")
        metadata = self.base / "game.item"
        metadata.write_text(json.dumps({"AppName": "app_name", "CatalogNamespace": "namespace", "CatalogItemId": "catalog"}))
        game = Game(game.id, game.name, game.source, game.root, str(metadata))
        self.hub.sync(self.settings, [game], {}, {})
        self.assertIn("namespace%3Acatalog%3Aapp_name?action=launch", self.launch(game.id).read_text())

    def test_original_shortcut_arguments_icon_and_working_directory_kept(self):
        game = self.game("manual:1", "Portable", "Kézi")
        exe = Path(game.root) / "game.exe"
        exe.write_bytes(b"MZ fixture")
        original = self.base / "original.lnk"
        original.write_bytes(b"original binary link, arguments, icon and working directory")
        self.bridge.links = [{"path": str(original), "target": str(exe), "arguments": "--profile game", "working": game.root}]
        self.hub.sync(self.settings, [game], {norm(exe): game.id}, {})
        self.assertEqual(self.launch(game.id).read_bytes(), original.read_bytes())

    def test_riot_game_specific_client_arguments(self):
        game = self.game("riot:valorant.live", "VALORANT", "Riot")
        client = self.base / "RiotClientServices.exe"
        client.write_bytes(b"MZ fixture")
        original = self.base / "Riot Client.lnk"
        original.write_bytes(b"client link")
        self.bridge.links = [{"path": str(original), "target": str(client), "arguments": ""}]
        self.hub.sync(self.settings, [game], {}, {})
        link = json.loads(self.launch(game.id).read_text())
        self.assertEqual(link["arguments"], "--launch-product=valorant --launch-patchline=live")
        self.assertEqual(link["target"], str(client))

    def test_owned_special_launcher_survives_original_shortcut_removal(self):
        game = self.game("manual:minecraft", "Minecraft", "Kézi", ".minecraft")
        launcher = self.base / "MinecraftLauncher.exe"
        launcher.write_bytes(b"MZ fixture")
        original = self.root / "Inditas/Minecraft.lnk"
        original.parent.mkdir(parents=True)
        original.write_text(json.dumps({"target": str(launcher), "arguments": "--profile original"}))
        self.hub.sync(self.settings, [game], {}, {})
        created = self.launch(game.id)
        before = created.read_bytes()
        original.unlink()
        self.hub.sync(self.settings, [game], {}, {})
        self.assertEqual(self.launch(game.id).read_bytes(), before)
        self.assertFalse(next(r["fallback"] for r in self.state()["links"] if r["role"] == "launch"))

    def test_other_games_including_nested_games_directory(self):
        game = self.game("games:portable", "Standalone", "Games", "Games/Standalone")
        exe = Path(game.root) / "bin/game.exe"
        exe.parent.mkdir()
        exe.write_bytes(b"MZ fixture")
        self.hub.sync(self.settings, [game], {}, {})
        self.assertEqual(json.loads(self.launch(game.id).read_text())["target"], str(exe))
        self.assertEqual(exe.read_bytes(), b"MZ fixture")

    def test_chess_separate_and_excluded_utility_omitted(self):
        chess = self.game("manual:chess", "BanksiaGUI (sakk)", "Kézi", "Chess")
        utility = self.game("steam:228980", "Steamworks Common Redistributables", "Steam", "Redist")
        self.hub.sync(self.settings, [chess, utility], {}, {chess.id: False, utility.id: False})
        self.assertEqual(self.launch(chess.id).parent, self.root / "Sakk")
        self.assertFalse(any(row["gid"] == utility.id for row in self.state()["links"]))

    def test_reserved_path_characters_and_same_named_games(self):
        games = [self.game("steam:1", "CON"), self.game("steam:2", "A:/B?*"), self.game("steam:3", "A:/B?*")]
        self.hub.sync(self.settings, games, {}, {})
        paths = [self.launch(g.id) for g in games]
        self.assertEqual(len(set(paths)), 3)
        self.assertEqual(paths[0].stem, "_CON")
        self.assertNotIn("?", paths[1].name)
        for path in paths:
            self.assertEqual(path.parent, self.root)

    def test_user_file_with_same_name_is_preserved(self):
        self.root.mkdir()
        user_file = self.root / "Game.url"
        user_file.write_text("user's bookmark")
        game = self.game()
        self.hub.sync(self.settings, [game], {}, {})
        self.assertEqual(user_file.read_text(), "user's bookmark")
        self.assertNotEqual(self.launch(game.id), user_file)

    def test_user_edited_managed_shortcut_is_preserved(self):
        game = self.game()
        self.hub.sync(self.settings, [game], {}, {})
        old = self.launch(game.id)
        old.write_text("user edit")
        self.hub.sync(self.settings, [game], {}, {})
        self.assertEqual(old.read_text(), "user edit")
        self.assertNotEqual(self.launch(game.id), old)

    def test_uninstall_backs_up_only_unchanged_owned_links(self):
        game = self.game()
        marker = Path(game.root) / "save.dat"
        marker.write_text("save")
        self.hub.sync(self.settings, [game], {}, {})
        old = self.launch(game.id)
        old_bytes = old.read_bytes()
        foreign = self.root / "my own file.txt"
        foreign.write_text("keep")
        self.hub.sync(self.settings, [], {}, {})
        self.assertFalse(old.exists())
        self.assertTrue(any(p.read_bytes() == old_bytes for p in (self.base / "data/backups").rglob("*.url")))
        self.assertEqual(marker.read_text(), "save")
        self.assertEqual(foreign.read_text(), "keep")

    def test_same_input_does_not_rewrite_shortcuts(self):
        game = self.game("manual:1", "Portable", "Kézi")
        self.hub.sync(self.settings, [game], {}, {})
        path = self.launch(game.id)
        before = path.stat().st_mtime_ns
        created = self.bridge.created
        report = self.hub.sync(self.settings, [game], {}, {})
        self.assertEqual(report["changed"], 0)
        self.assertEqual(path.stat().st_mtime_ns, before)
        self.assertEqual(self.bridge.created, created)

    def test_changed_games_root_does_not_mutate_old_root(self):
        game = self.game()
        self.hub.sync(self.settings, [game], {}, {})
        old = self.launch(game.id)
        before = digest(old)
        self.settings.games_root = str(self.base / "New Games")
        self.hub.sync(self.settings, [game], {}, {})
        self.assertEqual(digest(old), before)
        self.assertEqual(self.launch(game.id).parent, self.base / "New Games")

    def test_disabled_hub_does_not_create_any_folder(self):
        self.settings.hub_enabled = False
        self.assertFalse(self.hub.sync(self.settings, [], {}, {})["enabled"])
        self.assertFalse(self.root.exists())
        self.assertFalse(self.hub.state_path.exists())

    def test_shortcut_name_cannot_override_another_product_id(self):
        game = self.game()
        self.assertFalse(same_game_link({"path": "Game.url", "contents": "URL=steam://rungameid/999"}, game, {}))
        self.assertFalse(same_game_link({"path": "Game.url", "contents": "URL=https://example.com"}, game, {}))

    def test_unknown_external_game_gets_folder_fallback(self):
        game = self.game("other:game", "Unusual", "Other")
        result = self.hub.sync(self.settings, [game], {}, {})
        self.assertEqual(result["folder_fallbacks"], 1)
        self.assertEqual(json.loads(self.launch(game.id).read_text())["target"], game.root)

    def test_ambiguous_executables_are_not_guessed(self):
        game = self.game("games:ambiguous", "Ambiguous", "Games", "Games/Ambiguous")
        for name in ("first.exe", "second.exe"):
            (Path(game.root) / name).write_bytes(b"MZ fixture")
        report = self.hub.sync(self.settings, [game], {}, {})
        self.assertEqual(report["folder_fallbacks"], 1)

    def test_reparse_destination_refused(self):
        self.root.mkdir()
        real = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda path: norm(path) == norm(self.root) or real(path)):
            with self.assertRaises(ValueError):
                self.hub.sync(self.settings, [self.game()], {}, {})
        self.assertFalse(list(self.root.glob("*.url")))

    def test_corrupt_ownership_ledger_keeps_existing_files(self):
        self.root.mkdir()
        existing = self.root / "Game.url"
        existing.write_text("keep")
        self.hub.state_path.parent.mkdir()
        self.hub.state_path.write_text('{"marker":"unexpected","links":[]}')
        with self.assertRaises(ValueError):
            self.hub.sync(self.settings, [self.game()], {}, {})
        self.assertEqual(existing.read_text(), "keep")

    def test_continuous_requests_cannot_postpone_hub_indefinitely(self):
        worker = HubWorker.__new__(HubWorker)
        worker.condition = threading.Condition()
        worker.pending = None
        worker.first_request = None
        for now in (0, .8, 1.6, 2.4, 3.2, 4, 4.8):
            with patch("gametime.hub.time.monotonic", return_value=now):
                worker.request(self.settings, [], {}, {})
        self.assertEqual(worker.due, 5)

    def test_another_data_directory_cannot_duplicate_the_same_hub(self):
        game = self.game()
        self.hub.sync(self.settings, [game], {}, {})
        original = self.launch(game.id)
        before = digest(original)
        other = Hub(self.base / "other-data", FakeLinks(), [])
        with self.assertRaisesRegex(OSError, "másik adatbázis"):
            other.sync(self.settings, [game], {}, {})
        self.assertEqual(digest(original), before)
        self.assertEqual(len(list(self.root.glob("*.url"))), 1)

    def test_same_named_separate_installations_have_clear_source_labels(self):
        games = [self.game("steam:123", "Same Game", "Steam", "Steam Game"),
                 self.game("manual:1", "Same Game", "Kézi", "Standalone Game")]
        self.hub.sync(self.settings, games, {}, {})
        self.assertEqual(self.launch("steam:123").name, "Same Game (Steam).url")
        self.assertEqual(self.launch("manual:1").name, "Same Game (Kézi).lnk")

    def test_minecraft_migration_preserves_owned_special_launcher(self):
        manual = self.game("manual:minecraft", "Minecraft", "Kézi", ".minecraft")
        launcher = self.base / "MinecraftLauncher.exe"
        launcher.write_bytes(b"MZ fixture")
        original = self.root / "Inditas/Minecraft.lnk"
        original.parent.mkdir(parents=True)
        original.write_text(json.dumps({"target": str(launcher), "arguments": "--profile original"}))
        self.hub.sync(self.settings, [manual], {}, {})
        before = self.launch(manual.id).read_bytes()
        original.unlink()
        automatic = Game("minecraft:java", manual.name, "Minecraft", manual.root)
        self.hub.sync(self.settings, [automatic], {}, {})
        self.assertEqual(self.launch(automatic.id).read_bytes(), before)
        self.assertEqual(len(list(self.root.glob("Minecraft*.lnk"))), 1)


@unittest.skipUnless(os.name == "nt", "Windows required")
class HubNativeTests(unittest.TestCase):
    def test_native_link_readback_preserves_literal_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            data = base / "data"
            bridge = PowerShellLinks(data)
            self.addCleanup(bridge.close)
            exe = base / "Game with spaces.exe"
            exe.write_bytes(b"MZ fixture")
            link = base / "Jatek.lnk"
            arguments = '--profile "my profile" --literal "$() ` echo & test"'
            bridge.create([{"path": str(link), "target": str(exe), "arguments": arguments,
                            "working": str(base), "description": "fixture", "icon": ""}])
            saved = bridge.inventory([{"path": str(base), "depth": 0}])[0]
            self.assertEqual(saved["target"], str(exe))
            self.assertEqual(saved["arguments"], arguments)
            self.assertEqual(saved["working"], str(base))

    def test_native_background_app_adds_first_steam_and_manual_game(self):
        import tkinter as tk
        from gametime.discovery import Discovery
        from gametime.service import DiscoveryService
        from gametime.store import Store
        from gametime.ui import App
        with tempfile.TemporaryDirectory() as temp, patch("gametime.hub.shortcut_locations", return_value=[]):
            base = Path(temp)
            games = base / "Gaming Hub"
            steam = base / "Steam"
            (steam / "steamapps/common").mkdir(parents=True)
            epic = base / "Epic Manifests"
            epic.mkdir()
            settings = Settings(games_root=str(games), hub_enabled=True)
            store = Store(base / "usage.sqlite3")
            store.save_settings(settings)
            store.add_usage({("2000-01-01", "fixture:prior"): 123})
            discovery = Discovery(settings, [str(steam)], [str(epic)], base / "none.dat", ubisoft=False, riot=False)
            service = DiscoveryService(settings, discovery=discovery)
            hub = Hub(base / "data", locations=[])
            worker = HubWorker(base / "data", hub)
            root = tk.Tk()
            app = App(root, store, base / "data", background=True, service=service, hub=worker)
            def await_path(path, timeout=14, exists=True):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    root.update()
                    if path.exists() == exists:
                        return
                    time.sleep(.025)
                self.fail("Hub shortcut did not appear while the app was running: " + str(path))
            try:
                deadline = time.monotonic() + 3
                while not service.watchers and time.monotonic() < deadline:
                    root.update()
                    time.sleep(.025)
                installed = steam / "steamapps/common/Fixture"
                installed.mkdir()
                (steam / "steamapps/appmanifest_123.acf").write_text(
                    '"AppState" { "appid" "123" "name" "Fixture Steam" "installdir" "Fixture" }')
                await_path(games / "Fixture Steam.url")
                self.assertIn("steam://rungameid/123", (games / "Fixture Steam.url").read_text())
                manual_root = base / "Standalone"
                manual_root.mkdir()
                exe = manual_root / "Other.exe"
                exe.write_bytes(b"MZ fixture")
                game = Game("manual:other", "Other Source", "Kézi", str(manual_root))
                store.upsert([game])
                store.set_rule(str(exe), game.id)
                app.catalog.games[game.id] = game
                app.refresh_rules()
                await_path(games / "Other Source.lnk")
                records = hub.bridge.inventory([{"path": str(games), "depth": 0}])
                saved = next(r for r in records if Path(r["path"]).name == "Other Source.lnk")
                self.assertEqual(norm(saved["target"]), norm(exe))
                self.assertEqual(store.totals("2000-01-01"), {"fixture:prior": 123})
                store.add_usage({("2000-01-01", game.id): 45, ("2000-01-01", "steam:123"): 30})
                # A real metadata deletion retires a managed platform shortcut.
                (steam / "steamapps/appmanifest_123.acf").unlink()
                await_path(games / "Fixture Steam.url", exists=False)
                # A manual uninstall can leave its folder and saves behind.
                exe.unlink()
                await_path(games / "Other Source.lnk", exists=False)
                self.assertTrue(manual_root.is_dir())
                self.assertFalse(next(g.installed for g in store.games() if g.id == game.id))
                self.assertEqual(store.totals("2000-01-01"), {"fixture:prior": 123, game.id: 45, "steam:123": 30})
                exe.write_bytes(b"MZ fixture")
                await_path(games / "Other Source.lnk")
                self.assertTrue(next(g.installed for g in store.games() if g.id == game.id))
                # A direct removal of an Epic installation is noticed even while
                # its launcher index remains, including dots in the folder name.
                epic_root = base / "Another Drive/Epic.Game.1"
                epic_root.mkdir(parents=True)
                (epic / "fixture.item").write_text(json.dumps({"AppName": "fixture_app", "DisplayName": "Fixture Epic",
                                                              "InstallLocation": str(epic_root)}))
                await_path(games / "Fixture Epic.url")
                epic_root.rmdir()  # This test's empty synthetic installation only.
                await_path(games / "Fixture Epic.url", exists=False)
                epic_root.mkdir()
                await_path(games / "Fixture Epic.url")
                self.assertFalse(any(r.get("error") for r in list(worker.results.queue)))
            finally:
                app.close()
                store.close()


if __name__ == "__main__":
    unittest.main()
