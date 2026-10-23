from dataclasses import dataclass, field, replace
from pathlib import Path
import math
import ntpath
import os
import re
from .launcher_defs import CLIENT_PROCESSES, PLATFORM_SOURCES, client_id


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
CLIENTS.update(CLIENT_PROCESSES)
LAUNCHER_SOURCES = ("Steam", "Epic", "Ubisoft", "Riot", "Minecraft", *PLATFORM_SOURCES)
HELPERS = re.compile(r"unins|uninstall|(^|[-_ ])setup|^install|launcher|updater|crash|"
                     r"helper|config|redist|vcredist|dxsetup|benchmark|anticheat|easyanticheat", re.I)


def blocked(path):
    from .game_safety import anti_helper
    parts = norm(path).split("\\")
    return (anti_helper(path) or parts[-1] in BROWSERS | CLIENTS or client_id(path) == 'rockstar'
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


@dataclass
class Settings:
    games_root: str = r"C:\Games"
    warning_seconds: float = 6000
    limit_seconds: float = 7200
    steam_roots: list = field(default_factory=list)
    epic_manifest_dirs: list = field(default_factory=list)
    ubisoft_roots: list = field(default_factory=list)
    hub_enabled: bool = False
    language: str = "en"
    check_updates: bool = True
    overlay_enabled: bool = False
    overlay_replace_warning: bool = True
    limit_popup_enabled: bool = True
    overlay_opacity: float = .72
    overlay_font_size: int = 25
    overlay_color_normal: str = '#ffffff'
    overlay_color_warning: str = '#ff5c65'
    overlay_x: float = 1.0
    overlay_y: float = 0.0
    overlay_screen: str = ""
    overlay_rtss_auto: bool = False
    # Retained when reading older profiles; automatic mode needs no EXE list.
    overlay_rtss_paths: list = field(default_factory=list)
    restriction_enabled: bool = False
    restriction_seconds: float = 7500
    bedtime_enabled: bool = False
    bedtime_warning_minute: int = 1435
    bedtime_minute: int = 0
    bedtime_resume_minute: int = 360
    bedtime_minimize: bool = False
    bedtime_caps_budget: bool = False
    statistics_sync_enabled: bool = False
    statistics_sync_group: str = ""
    statistics_device_name: str = ""
    notification_messages: dict = field(default_factory=dict)
    notification_sound: str = 'default'
    notification_sound_path: str = ''
    weekend_enabled: bool = False
    weekend_schedule: dict = field(default_factory=dict)
    game_overlays: dict = field(default_factory=dict)
    daily_schedules: dict = field(default_factory=dict)

    def validate(self):
        from .schedule import SCHEDULE_FIELDS,DayScheduleError
        if not isinstance(self.check_updates, bool):
            raise ValueError('Automatic update checks must be on or off.')
        if (not isinstance(self.daily_schedules,dict) or any(key not in tuple(map(str,range(7))) or not isinstance(value,dict)
                or any(field not in SCHEDULE_FIELDS for field in value) for key,value in self.daily_schedules.items())):
            raise ValueError('Choose valid settings for the days of the week.')
        if (not isinstance(self.weekend_enabled,bool) or not isinstance(self.weekend_schedule,dict)
                or any(key not in SCHEDULE_FIELDS for key in self.weekend_schedule)):
            raise ValueError('Choose a valid weekend schedule.')
        if self.notification_sound not in ('default','information','error','silent','custom'):
            raise ValueError('Choose a valid notification sound.')
        if (not isinstance(self.notification_sound_path,str) or len(self.notification_sound_path)>32767 or '\0' in self.notification_sound_path
                or self.notification_sound=='custom' and (not ntpath.isabs(self.notification_sound_path) or not self.notification_sound_path.lower().endswith('.wav'))):
            raise ValueError('Choose a WAV sound file.')
        overlay_fields=('overlay_enabled','overlay_x','overlay_y','overlay_font_size','overlay_screen','overlay_color_normal','overlay_color_warning')
        if (not isinstance(self.game_overlays,dict) or any(not isinstance(gid,str) or not gid or '\0' in gid
                or not isinstance(value,dict) or any(key not in overlay_fields for key in value) for gid,value in self.game_overlays.items())):
            raise ValueError('Choose valid per-game countdown settings.')
        if self.weekend_schedule:
            replace(self,weekend_enabled=False,weekend_schedule={},daily_schedules={},game_overlays={},**self.weekend_schedule).validate()
        for day,value in self.daily_schedules.items():
            try: replace(self,weekend_enabled=False,weekend_schedule={},daily_schedules={},game_overlays={},**value).validate()
            except ValueError as exc: raise DayScheduleError(int(day),exc) from exc
        for value in self.game_overlays.values():
            replace(self,weekend_enabled=False,weekend_schedule={},daily_schedules={},game_overlays={},**value).validate()
        from .notification_text import KINDS,MAX_MESSAGE_LENGTH
        if (not isinstance(self.notification_messages,dict) or any(kind not in KINDS for kind in self.notification_messages)
                or any(not isinstance(value,str) or len(value)>MAX_MESSAGE_LENGTH or '\0' in value for value in self.notification_messages.values())):
            raise ValueError('Each reminder message must be text of at most 1000 characters.')
        for color in (self.overlay_color_normal,self.overlay_color_warning): hex_color(color)
        if any(not isinstance(value, bool) for value in (self.bedtime_enabled, self.bedtime_minimize, self.bedtime_caps_budget)):
            raise ValueError('Bedtime switches must be on or off.')
        for value in (self.bedtime_warning_minute, self.bedtime_minute, self.bedtime_resume_minute):
            if type(value) is not int or not 0 <= value < 1440:
                raise ValueError('Choose valid bedtime times.')
        warning_gap = (self.bedtime_minute-self.bedtime_warning_minute) % 1440
        sleep_gap = (self.bedtime_resume_minute-self.bedtime_minute) % 1440
        if not warning_gap or not sleep_gap or warning_gap+sleep_gap >= 1440:
            raise ValueError('Times must follow this order: reminder, bedtime, resume, then the next reminder.')
        if (not isinstance(self.statistics_sync_enabled, bool)
                or not isinstance(self.statistics_sync_group, str)
                or (self.statistics_sync_group and not re.fullmatch(r'(?:[0-9a-f]{12}|[0-9a-f]{32})', self.statistics_sync_group))
                or not isinstance(self.statistics_device_name, str) or len(self.statistics_device_name) > 80):
            raise ValueError('Invalid statistics sync settings.')
        if self.statistics_sync_enabled and not re.fullmatch(r'[0-9a-f]{32}', self.statistics_sync_group):
            raise ValueError('Use a connection code generated by the application.')
        if self.language not in ("en", "hu"):
            raise ValueError("Unsupported language")
        if (any(isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) for value in (self.warning_seconds,self.limit_seconds))
                or not (0 < self.warning_seconds < self.limit_seconds <= 86400)):
            raise ValueError("Thresholds must be: 0 < warning < daily limit ≤ 1440 minutes.")
        for value in (self.overlay_enabled, self.overlay_replace_warning, self.limit_popup_enabled, self.overlay_rtss_auto):
            if not isinstance(value, bool):
                raise ValueError("Overlay switches must be on or off.")
        for value, minimum, maximum in ((self.overlay_opacity,.25,1), (self.overlay_x,0,1), (self.overlay_y,0,1)):
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError("Invalid countdown opacity or position.")
        if type(self.overlay_font_size) is not int or not 8 <= self.overlay_font_size <= 72:
            raise ValueError("Choose a countdown text size between 8 and 72 pt.")
        if not isinstance(self.overlay_screen,str) or len(self.overlay_screen)>200:
            raise ValueError("Invalid countdown monitor.")
        if (not isinstance(self.overlay_rtss_paths, list) or len(self.overlay_rtss_paths) > 100
                or any(not isinstance(path, str) or len(path) > 32767 or "\0" in path
                       or not ntpath.isabs(path) or not path.lower().endswith('.exe')
                       or helper(path) for path in self.overlay_rtss_paths)):
            raise ValueError("Choose a game executable.")
        if not isinstance(self.restriction_enabled,bool):
            raise ValueError("Play restriction must be on or off.")
        if (isinstance(self.restriction_seconds,bool) or not isinstance(self.restriction_seconds,(int,float))
                or not math.isfinite(self.restriction_seconds) or not 0<self.restriction_seconds<=86400):
            raise ValueError("Play restriction must start between 0 and 1440 minutes.")
        root = Path(self.games_root)
        if not root.is_absolute() or root.parent == root:
            raise ValueError("The Gaming Hub needs an absolute folder path, not a drive root.")
        return self


def hex_color(value):
    if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):
        raise ValueError('Choose a valid countdown color.')
    return value.lower()


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
        return self.overrides.get(game.id, True)

    def resolve(self, path, fallback=True):
        if not path or blocked(path):
            return None
        key = norm(path)
        if key in self.rules:
            gid = self.rules[key]
            game = self.games.get(gid) if gid else None
            return game if game and game.installed and self.enabled(game) else None
        from .minecraft import is_runtime
        if is_runtime(path):
            game = next((g for g in self.games.values() if g.source == "Minecraft" and g.installed), None)
            if game:
                return game if self.enabled(game) else None
        if helper(path):
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
        if not path or helper(path):
            return True
        key = norm(path)
        if key in self.rules:
            game = self.games.get(self.rules[key])
            return not game or not game.installed or not self.enabled(game)
        from .minecraft import is_runtime
        if is_runtime(path) and any(g.source == "Minecraft" and not self.enabled(g) for g in self.games.values()):
            return True
        return any(g.source != "Kézi" and within(path, g.root) and not self.enabled(g)
                   for g in self.games.values())

    def _under(self, path, root, source):
        if not within(path, root):
            return None
        relative = norm(path)[len(norm(root)):].lstrip("\\")
        parts = relative.split("\\")
        if not parts or not parts[-1].endswith(".exe"):
            return None
        name = parts[0] if len(parts) > 1 else "Games (root)"
        game_root = os.path.join(root, parts[0]) if len(parts) > 1 else str(root)
        gid = ("games:" if source == "Games" else f"pending:{source.lower()}:") + norm(game_root)
        game = Game(gid, name, source, game_root)
        self.games[gid] = game
        return game if self.enabled(game) else None


def popup_required(settings, kind):
    if kind == "warning":
        return not (settings.overlay_enabled and settings.overlay_replace_warning)
    if kind in ("limit", "session"):
        return settings.limit_popup_enabled
    return True
