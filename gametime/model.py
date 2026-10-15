from dataclasses import dataclass, field
from pathlib import Path
import ntpath
import os
import re


def norm(path):
    # Windows paths remain comparable in fixture tests on other operating systems.
    return ntpath.normcase(ntpath.normpath(str(path))).rstrip("\\")


def within(path, root):
    p, r = norm(path), norm(root)
    return p == r or p.startswith(r + "\\")


BROWSERS = {"chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe",
            "vivaldi.exe", "iexplore.exe", "librewolf.exe", "waterfox.exe", "browser.exe"}
CLIENTS = {"steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe", "epicwebhelper.exe"}
CLIENTS.update({"ubisoftconnect.exe", "ubisoftgamelauncher.exe", "ubisoftgamelauncher64.exe", "upc.exe",
                "uplay.exe", "uplaywebcore.exe", "uplayservice.exe", "ubisoftextension.exe", "upcelevationservice.exe"})
CLIENTS.update({"riotclientservices.exe", "riotclientux.exe", "riotclientuxrender.exe",
                "riotclientcrashhandler.exe", "riotclientcrashhandler64.exe", "riotclientcrashhandler32.exe",
                "vgc.exe", "vgtray.exe", "leagueclient.exe", "leagueclientux.exe", "leagueclientuxrender.exe"})
LAUNCHER_SOURCES = ("Steam", "Epic", "Ubisoft", "Riot")
HELPERS = re.compile(r"unins|uninstall|(^|[-_ ])setup|^install|launcher|updater|crash|"
                     r"helper|config|redist|vcredist|dxsetup|benchmark|anticheat|easyanticheat", re.I)
CHESS = re.compile(r"chess|sakk|stockfish|(^|[\W_])(lc0|fritz|houdini|komodo)([\W_]|$)", re.I)


def blocked(path):
    parts = norm(path).split("\\")
    return (parts[-1] in BROWSERS | CLIENTS
            or any(part in {"riot client", "riot vanguard"} for part in parts[:-1]))


def helper(path):
    return blocked(path) or bool(HELPERS.search(ntpath.basename(str(path))))


@dataclass(frozen=True)
class Game:
    id: str
    name: str
    source: str
    root: str
    metadata: str = ""
    installed: bool = True

    @property
    def default_enabled(self):
        return not CHESS.search(self.name + " " + ntpath.basename(self.root))


@dataclass
class Settings:
    games_root: str = r"C:\Games"
    warning_seconds: float = 6000
    limit_seconds: float = 7200
    steam_roots: list = field(default_factory=list)
    epic_manifest_dirs: list = field(default_factory=list)
    ubisoft_roots: list = field(default_factory=list)

    def validate(self):
        if not (0 < self.warning_seconds < self.limit_seconds <= 86400):
            raise ValueError("A küszöbök sorrendje: 0 < előzetes figyelmeztetés < napi keret ≤ 1440 perc.")
        root = Path(self.games_root)
        if not root.is_absolute() or root.parent == root:
            raise ValueError("A Games mappa teljes útvonal legyen, és ne legyen meghajtógyökér.")
        return self


class Catalog:
    def __init__(self, settings, games=(), overrides=None, rules=None):
        self.settings = settings
        self.games = {g.id: g for g in games}
        self.overrides = overrides or {}
        self.rules = rules or {}  # exact executable -> game ID; None excludes
        self.steam_libraries = []
        self.epic_hints = []
        self.ubisoft_libraries = []
        self.riot_hints = []

    def apply(self, games, scope):
        for key, game in list(self.games.items()):
            if scope(game):
                del self.games[key]
        self.games.update((g.id, g) for g in games)

    def enabled(self, game):
        return self.overrides.get(game.id, game.default_enabled)

    def resolve(self, path, fallback=True):
        if not path or blocked(path):
            return None
        key = norm(path)
        if key in self.rules:
            gid = self.rules[key]
            game = self.games.get(gid) if gid else None
            return game if game and self.enabled(game) else None
        if helper(path) or CHESS.search(ntpath.basename(path)):
            return None
        # A more specific installation wins over a containing custom Games folder.
        candidates = sorted((g for g in self.games.values() if g.installed and g.source != "Kézi" and within(path, g.root)
                             and not (g.source == "Games" and norm(g.root) == norm(self.settings.games_root)
                                      and norm(ntpath.dirname(path)) != norm(g.root))),
                            key=lambda g: len(norm(g.root)), reverse=True)
        if candidates:
            game = candidates[0]
            return game if self.enabled(game) else None
        if not fallback:
            return None
        for lib in self.steam_libraries:
            common = os.path.join(lib, "steamapps", "common")
            game = self._under(path, common, "Steam")
            if game:
                return game
        for game in self.epic_hints:
            if within(path, game.root):
                self.games[game.id] = game
                return game if self.enabled(game) else None
        for root in self.ubisoft_libraries:
            game = self._under(path, root, "Ubisoft")
            if game:
                return game
        for game in self.riot_hints:
            if within(path, game.root):
                self.games[game.id] = game
                return game if self.enabled(game) else None
        return self._under(path, self.settings.games_root, "Games")

    def explicitly_ignored(self, path):
        if not path or helper(path) or CHESS.search(ntpath.basename(path)):
            return True
        key = norm(path)
        if key in self.rules:
            game = self.games.get(self.rules[key])
            return not game or not self.enabled(game)
        return any(g.source != "Kézi" and within(path, g.root) and not self.enabled(g)
                   for g in self.games.values())

    def _under(self, path, root, source):
        if not within(path, root):
            return None
        relative = norm(path)[len(norm(root)):].lstrip("\\")
        parts = relative.split("\\")
        if not parts or not parts[-1].endswith(".exe"):
            return None
        name = parts[0] if len(parts) > 1 else "Games (gyökér)"
        game_root = os.path.join(root, parts[0]) if len(parts) > 1 else str(root)
        gid = ("games:" if source == "Games" else f"pending:{source.lower()}:") + norm(game_root)
        game = Game(gid, name, source, game_root)
        self.games[gid] = game
        return game if self.enabled(game) else None
