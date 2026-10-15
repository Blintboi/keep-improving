"""Offline Ubisoft Connect discovery from the launcher's local registry records."""
import os
from pathlib import Path
from .model import Game, norm

LAUNCHER_KEY = r"SOFTWARE\Ubisoft\Launcher"
UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
SCOPES = (("HKCU", 0), ("HKLM", 0x100), ("HKLM", 0x200))


class WindowsUbisoftRegistry:
    def __init__(self):
        self.errors = []

    @staticmethod
    def _hive(name):
        import winreg
        return winreg.HKEY_CURRENT_USER if name == "HKCU" else winreg.HKEY_LOCAL_MACHINE

    def _values(self, hive, path, view):
        import winreg
        try:
            with winreg.OpenKey(self._hive(hive), path, 0, winreg.KEY_READ | view) as key:
                return dict(winreg.EnumValue(key, i)[:2] for i in range(winreg.QueryInfoKey(key)[1]))
        except FileNotFoundError:
            return {}
        except OSError:
            self.errors.append("registry:Ubisoft:" + hive + "\\" + path)
            return {}

    def _children(self, hive, path, view):
        import winreg
        try:
            with winreg.OpenKey(self._hive(hive), path, 0, winreg.KEY_READ | view) as key:
                return [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
        except FileNotFoundError:
            return []
        except OSError:
            self.errors.append("registry:Ubisoft:" + hive + "\\" + path)
            return []

    def read(self):
        self.errors = []
        roots, records, names = [], {}, {}
        if os.name != "nt":
            return {"launchers": roots, "games": [], "errors": []}
        for hive, view in SCOPES:
            launcher = self._values(hive, LAUNCHER_KEY, view)
            location = launcher.get("InstallDir") or launcher.get("InstallPath")
            if isinstance(location, str) and location:
                roots.append(location)
            for subkey in self._children(hive, UNINSTALL_KEY, view):
                if not subkey.lower().startswith("uplay install "):
                    continue
                appid = subkey[len("Uplay Install "):].strip()
                if not appid.isdigit():
                    continue
                values = self._values(hive, UNINSTALL_KEY + "\\" + subkey, view)
                names[appid] = values.get("DisplayName", "")
                root = values.get("InstallLocation")
                if isinstance(root, str) and root:
                    records.setdefault(appid, {"id": appid, "root": root})
            for appid in self._children(hive, LAUNCHER_KEY + r"\Installs", view):
                if not appid.isdigit():
                    continue
                values = self._values(hive, LAUNCHER_KEY + "\\Installs\\" + appid, view)
                root = values.get("InstallDir") or values.get("InstallLocation")
                if isinstance(root, str) and root:
                    records[appid] = {"id": appid, "root": root}
        for appid, record in records.items():
            record["name"] = names.get(appid) or ""
        return {"launchers": list(dict.fromkeys(roots)), "games": list(records.values()),
                "errors": list(dict.fromkeys(self.errors))}

    def watch_specs(self):
        """Missing keys use a nonrecursive ancestor watch until their creation."""
        if os.name != "nt":
            return set()
        import winreg
        specs = set()
        for hive, view in SCOPES:
            for target, recursive in ((LAUNCHER_KEY, False), (LAUNCHER_KEY + r"\Installs", True),
                                      (UNINSTALL_KEY, True)):
                actual = target
                while actual:
                    try:
                        with winreg.OpenKey(self._hive(hive), actual, 0, winreg.KEY_READ | view):
                            specs.add((hive, actual, view, recursive and actual == target))
                        break
                    except OSError:
                        actual = actual.rpartition("\\")[0]
        return specs


class UbisoftSource:
    def __init__(self, extra_roots=(), registry=None):
        self.registry = registry or WindowsUbisoftRegistry()
        self.extra_roots = list(extra_roots)
        self.game_roots = []
        self.errors = []

    def scan(self):
        snapshot = self.registry.read()
        self.errors = list(snapshot.get("errors", []))
        launchers = list(snapshot.get("launchers", [])) + self.extra_roots
        launchers += [str(Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) /
                          "Ubisoft" / "Ubisoft Game Launcher")]
        launchers = list(dict.fromkeys(str(Path(p)) for p in launchers if isinstance(p, str) and p))
        self.game_roots = [str(Path(root) / "games") for root in launchers]
        games = {}
        for record in snapshot.get("games", []):
            appid, location = record.get("id"), record.get("root")
            if not isinstance(appid, str) or not appid.isdigit() or not isinstance(location, str) or not location:
                continue
            root = Path(location)
            if not root.is_absolute() or root.parent == root or not root.is_dir():
                continue
            if any(norm(root) == norm(launcher) for launcher in launchers):
                continue
            name = record.get("name")
            name = name.strip() if isinstance(name, str) else ""
            gid = "ubisoft:" + appid
            games[gid] = Game(gid, name or root.name, "Ubisoft", str(root), "registry:Ubisoft:" + appid)
        return list(games.values())

    def watch_specs(self):
        return self.registry.watch_specs()
