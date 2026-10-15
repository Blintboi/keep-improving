"""Launcher manifests are the index: never walk Steam/Epic game content."""
import json
import logging
import os
from pathlib import Path
import re
from .model import Game, helper, norm, within

log = logging.getLogger(__name__)
TOKEN = re.compile(r'\s+|//[^\n]*|"((?:\\.|[^"\\])*)"|([{}])|([^\s{}"]+)')


def reparse(path):
    try:
        return path.is_symlink() or bool(getattr(path.stat(), "st_file_attributes", 0) & 0x400)
    except OSError:
        return True


def parse_vdf(text):
    tokens = []
    for match in TOKEN.finditer(text.lstrip("\ufeff")):
        if match[1] is not None:
            # Only VDF escapes; never decode Windows paths using unicode_escape.
            tokens.append(re.sub(r'\\([\\"])', r'\1', match[1]))
        elif match[2] or match[3]:
            tokens.append(match[2] or match[3])
    index = 0

    def block(nested=False):
        nonlocal index
        result = {}
        while index < len(tokens):
            key = tokens[index]
            index += 1
            if key == "}":
                if not nested:
                    raise ValueError("Unexpected VDF closing brace")
                return result
            if key == "{" or index >= len(tokens):
                raise ValueError("Incomplete VDF")
            value = tokens[index]
            index += 1
            if value == "}":
                raise ValueError("VDF value missing")
            result[key.lower()] = block(True) if value == "{" else value
        if nested:
            raise ValueError("Unclosed VDF block")
        return result
    return block()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def preserve_unreadable(games, previous, errors):
    found = {g.id: g for g in games}
    for game in previous:
        if game.id in found:
            continue
        if any(within(game.metadata, error) or (game.source == "Steam" and Path(error).name == "libraryfolders.vdf")
               or (game.source == "Ubisoft" and error.startswith("registry:Ubisoft:"))
               or (game.source == "Riot" and error.startswith("registry:Riot:"))
               for error in errors):
            found[game.id] = game
    return list(found.values())


def steam_roots():
    result = []
    if os.name == "nt":
        import winreg
        for hive, key, value in [(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                 (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")]:
            for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
                try:
                    with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as handle:
                        result.append(winreg.QueryValueEx(handle, value)[0])
                except OSError:
                    pass
    for var in ("ProgramFiles(x86)", "ProgramFiles"):
        result.append(os.path.join(os.environ.get(var, "C:\\Program Files"), "Steam"))
    return list(dict.fromkeys(str(Path(p)) for p in result))


def epic_dirs():
    base = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    return [str(base / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests")]


class Discovery:
    def __init__(self, settings, steam=None, epic=None, launcher_dat=None, ubisoft=True, riot=True):
        self.settings = settings
        self.roots = steam if steam is not None else list(dict.fromkeys(steam_roots() + settings.steam_roots))
        self.epic_dirs = epic if epic is not None else list(dict.fromkeys(epic_dirs() + settings.epic_manifest_dirs))
        self.launcher_dat = Path(launcher_dat or Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) /
                                 "Epic" / "UnrealEngineLauncher" / "LauncherInstalled.dat")
        self.libraries = list(self.roots)
        self.hints = []
        self.cache = {}  # Preserve last complete metadata during partial writes.
        self.errors = []
        from .ubisoft import UbisoftSource
        self.ubisoft = UbisoftSource(settings.ubisoft_roots) if ubisoft is True else ubisoft or None
        self.ubisoft_game_roots = []
        from .riot import RiotSource
        self.riot = RiotSource() if riot is True else riot or None
        self.riot_hints = []
        self.install_roots = set()

    def _read_vdf(self, path):
        try:
            value = parse_vdf(path.read_text(encoding="utf-8-sig"))
            self.cache[norm(path)] = value
            return value
        except (OSError, ValueError) as exc:
            if path.exists():
                self.errors.append(str(path))
                log.warning("Átmenetileg nem olvasható jegyzék: %s: %s", path, exc)
            return self.cache.get(norm(path), {})

    def libraries_from_metadata(self):
        libs = list(self.roots)
        # Both layouts have existed; also accept legacy numbered string values.
        for root in self.roots:
            for sub in ("steamapps", "config"):
                file = Path(root) / sub / "libraryfolders.vdf"
                if file.is_file():
                    folders = self._read_vdf(file).get("libraryfolders", {})
                    if not isinstance(folders, dict):
                        self.errors.append(str(file))
                        continue
                    for key, val in folders.items():
                        if key.isdigit():
                            location = val.get("path") if isinstance(val, dict) else val
                            if isinstance(location, str) and location:
                                libs.append(str(Path(location)))
        self.libraries = list(dict.fromkeys(libs))
        return self.libraries

    def scan_launchers(self):
        self.errors = []
        games = []
        for lib in self.libraries_from_metadata():
            apps = Path(lib) / "steamapps"
            try:
                files = list(apps.glob("appmanifest_*.acf")) if apps.is_dir() else []
            except OSError:
                self.errors.append(str(apps))
                continue
            for file in files:
                data = self._read_vdf(file).get("appstate", {})
                if not isinstance(data, dict):
                    self.errors.append(str(file))
                    continue
                appid, folder = data.get("appid"), data.get("installdir")
                if appid and folder and isinstance(appid, str) and isinstance(folder, str):
                    root = apps / "common" / folder
                    # Disallow a malformed manifest escaping the known library.
                    if within(root.resolve(), (apps / "common").resolve()) and root.is_dir():
                        games.append(Game("steam:" + appid, str(data.get("name", folder)), "Steam", str(root), str(file)))
        for directory in self.epic_dirs:
            folder = Path(directory)
            try:
                files = list(folder.glob("*.item")) if folder.is_dir() else []
            except OSError:
                self.errors.append(str(folder))
                continue
            for file in files:
                try:
                    data = load_json(file)
                    if not isinstance(data, dict):
                        raise ValueError("Epic manifest must be an object")
                    self.cache[norm(file)] = data
                except (OSError, ValueError) as exc:
                    self.errors.append(str(file))
                    log.warning("Epic jegyzék átmenetileg nem olvasható: %s: %s", file, exc)
                    data = self.cache.get(norm(file), {})
                root, app = data.get("InstallLocation"), data.get("AppName")
                if isinstance(root, str) and isinstance(app, str) and Path(root).is_absolute() and Path(root).is_dir():
                    games.append(Game("epic:" + app, str(data.get("DisplayName", app)), "Epic", root, str(file)))
        hints = []
        if self.launcher_dat.is_file():
            try:
                data = load_json(self.launcher_dat)
                if not isinstance(data, dict) or not isinstance(data.get("InstallationList", []), list):
                    raise ValueError("Invalid Epic launcher index")
                self.cache[norm(self.launcher_dat)] = data
            except (OSError, ValueError):
                self.errors.append(str(self.launcher_dat))
                data = self.cache.get(norm(self.launcher_dat), {})
            for item in data.get("InstallationList", []):
                if not isinstance(item, dict):
                    continue
                root, app = item.get("InstallLocation"), item.get("AppName")
                if isinstance(root, str) and isinstance(app, str) and Path(root).is_absolute() and Path(root).is_dir():
                    hints.append(Game("epic:" + app, app, "Epic", root, str(self.launcher_dat)))
        self.hints = hints
        # .item names take precedence over the launcher-wide fallback index.
        found = {g.id: g for g in hints}
        found.update((g.id, g) for g in games)
        if self.ubisoft:
            found.update((g.id, g) for g in self.ubisoft.scan())
            self.ubisoft_game_roots = list(self.ubisoft.game_roots)
            self.errors.extend(self.ubisoft.errors)
        if self.riot:
            found.update((g.id, g) for g in self.riot.scan())
            self.riot_hints = list(self.riot.hints)
            self.errors.extend(self.riot.errors)
        self.install_roots.update(game.root for game in found.values())
        return list(found.values())

    def scan_games(self, group=None):
        base = Path(self.settings.games_root)
        if group is None:
            if not base.is_dir():
                return []
            roots = [base] + [p for p in base.iterdir() if p.is_dir() and not reparse(p)]
        else:
            roots = [Path(group)]
        result = []
        for root in roots:
            if not root.is_dir():
                continue
            shallow = norm(root) == norm(base)
            if self._has_exe(root, shallow):
                result.append(Game("games:" + norm(root), "Games (gyökér)" if shallow else root.name,
                                   "Games", str(root)))
        return result

    @staticmethod
    def _has_exe(root, shallow=False):
        def fail(error):
            raise error
        for folder, dirs, files in os.walk(root, followlinks=False, onerror=fail):
            dirs[:] = [] if shallow else [d for d in dirs if not reparse(Path(folder, d))]
            if any(f.lower().endswith(".exe") and not helper(f) for f in files):
                return True
        return False

    def watch_specs(self):
        """Missing folders use their nearest existing ancestor, without recursive drive scans."""
        wanted = [(str(Path(self.settings.games_root)), True, "games")]
        for root in self.roots:
            wanted += [(str(Path(root) / "config"), False, "launchers"), (root, False, "launchers")]
        for lib in self.libraries:
            wanted += [(str(Path(lib) / "steamapps"), False, "launchers"),
                       (str(Path(lib) / "steamapps" / "common"), False, "launchers")]
        wanted += [(p, False, "launchers") for p in self.epic_dirs]
        wanted += [(str(self.launcher_dat.parent), False, "launchers")]
        wanted += [(root, False, "launchers") for root in self.ubisoft_game_roots]
        if self.riot:
            wanted += self.riot.directory_specs()
        if self.settings.hub_enabled:
            from .hub import shortcut_locations
            wanted += [(item["path"], bool(item["depth"]), "shortcuts") for item in shortcut_locations()]
        specs = {}
        for target, recursive, kind in wanted:
            existing = Path(target)
            while not existing.is_dir() and existing.parent != existing:
                existing = existing.parent
            if existing.is_dir():
                actual_recursive = recursive and norm(existing) == norm(target)
                # Multiple missing targets may share an ancestor.
                specs.setdefault((str(existing), actual_recursive, kind), []).append(target)
        for target in self.install_roots:
            existing = Path(target).parent
            while not existing.is_dir() and existing.parent != existing:
                existing = existing.parent
            if existing.is_dir():
                specs.setdefault((str(existing), False, "installs"), []).append(target)
        return {key: tuple(dict.fromkeys(targets)) for key, targets in specs.items()}

    def registry_watch_specs(self):
        return ((self.ubisoft.watch_specs() if self.ubisoft else set()) |
                (self.riot.watch_specs() if self.riot else set()))
