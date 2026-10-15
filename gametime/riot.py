"""Offline Riot discovery. Read installation indexes, never client account data."""
import json
import logging
import ntpath
import os
from pathlib import Path
import re
from .model import Game, norm, within

log = logging.getLogger(__name__)
UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
SCOPES = (("HKCU", 0), ("HKLM", 0x100), ("HKLM", 0x200))
PRODUCT = re.compile(r"[a-z0-9_]+\.[a-z0-9_-]+", re.I)
NAMES = {"valorant": "VALORANT", "league_of_legends": "League of Legends",
         "bacon": "Legends of Runeterra", "lor": "Legends of Runeterra"}


def game_product(value):
    return (isinstance(value, str) and PRODUCT.fullmatch(value) is not None
            and value.partition(".")[0].lower() not in {"riot_client", "riotclient", "vanguard"})


def install_fields(text):
    """Read only Riot's top-level installation scalars, without a YAML interpreter."""
    result = {}
    for line in text.lstrip("\ufeff").splitlines():
        match = re.match(r"^(product_install_full_path|product_install_root|shortcut_name):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        if value.startswith('"'):
            value, end = json.JSONDecoder().raw_decode(value)
            tail = match[2].strip()[end:].strip()
            if tail and not tail.startswith("#"):
                raise ValueError("Incomplete Riot installation field")
        elif value.startswith("'"):
            quoted = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", value)
            if not quoted:
                raise ValueError("Incomplete Riot installation field")
            value = quoted[1].replace("''", "'")
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        if not isinstance(value, str) or not value:
            raise ValueError("Empty Riot installation field")
        result[key] = value
    if "product_install_full_path" not in result:
        raise ValueError("Riot installation path not yet available")
    return result


class WindowsRiotRegistry:
    def read(self):
        games, errors = {}, []
        if os.name != "nt":
            return {"games": [], "errors": []}
        import winreg
        for hive_name, view in SCOPES:
            hive = winreg.HKEY_CURRENT_USER if hive_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE
            try:
                with winreg.OpenKey(hive, UNINSTALL_KEY, 0, winreg.KEY_READ | view) as key:
                    children = [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
            except FileNotFoundError:
                continue
            except OSError:
                errors.append("registry:Riot:" + hive_name + "\\" + UNINSTALL_KEY)
                continue
            for child in children:
                if not child.lower().startswith("riot game "):
                    continue
                product = child[len("Riot Game "):].lower()
                if not game_product(product):
                    continue
                try:
                    with winreg.OpenKey(hive, UNINSTALL_KEY + "\\" + child, 0, winreg.KEY_READ | view) as key:
                        values = dict(winreg.EnumValue(key, i)[:2] for i in range(winreg.QueryInfoKey(key)[1]))
                    if not isinstance(values.get("InstallLocation"), str) or not values["InstallLocation"]:
                        errors.append("registry:Riot:" + hive_name + "\\" + UNINSTALL_KEY + "\\" + child)
                        continue
                    games[product] = {"id": product, "root": values.get("InstallLocation"),
                                      "name": values.get("DisplayName", "")}
                except FileNotFoundError:
                    pass  # Uninstalled between enumeration and read.
                except OSError:
                    errors.append("registry:Riot:" + hive_name + "\\" + UNINSTALL_KEY + "\\" + child)
        return {"games": list(games.values()), "errors": errors}

    def watch_specs(self):
        if os.name != "nt":
            return set()
        import winreg
        specs = set()
        for hive_name, view in SCOPES:
            hive = winreg.HKEY_CURRENT_USER if hive_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE
            actual = UNINSTALL_KEY
            while actual:
                try:
                    with winreg.OpenKey(hive, actual, 0, winreg.KEY_READ | view):
                        specs.add((hive_name, actual, view, actual == UNINSTALL_KEY))
                    break
                except OSError:
                    actual = actual.rpartition("\\")[0]
        return specs


class RiotSource:
    def __init__(self, metadata_root=None, client_index=None, registry=None):
        base = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Riot Games"
        self.metadata_root = Path(metadata_root) if metadata_root is not None else base / "Metadata"
        self.client_index = Path(client_index) if client_index is not None else base / "RiotClientInstalls.json"
        self.registry = registry or WindowsRiotRegistry()
        self.cache = {}
        self.errors = []
        self.hints = []
        self.game_roots = []

    def _read(self, path, reader):
        try:
            value = reader(path.read_text(encoding="utf-8-sig"))
            self.cache[norm(path)] = value
            return value
        except (OSError, ValueError, TypeError) as exc:
            if not isinstance(exc, FileNotFoundError):
                self.errors.append(str(path))
                log.warning("Riot telepítési index átmenetileg nem olvasható: %s: %s", path, exc)
            return self.cache.get(norm(path))

    @staticmethod
    def _root(value):
        if not isinstance(value, str) or not value:
            return None
        root = Path(value)
        if (not root.is_absolute() or root.parent == root or not root.is_dir()
                or any(p.lower() in {"riot client", "riot vanguard", "vanguard"} for p in root.parts)):
            return None
        return root

    def scan(self):
        snapshot = self.registry.read()
        self.errors = list(snapshot.get("errors", []))
        games, roots = {}, set()
        for record in snapshot.get("games", []):
            product, root = record.get("id"), self._root(record.get("root"))
            if not game_product(product) or root is None:
                continue
            product = product.lower()
            gid = "riot:" + product
            name = record.get("name")
            name = name.strip() if isinstance(name, str) else ""
            games[gid] = Game(gid, name or NAMES.get(product.partition(".")[0], root.name),
                              "Riot", str(root), "registry:Riot:" + product)
            roots.add(str(root.parent))
        try:
            files = list(self.metadata_root.glob("*/*.product_settings.yaml")) if self.metadata_root.is_dir() else []
        except OSError:
            files = []
            self.errors.append(str(self.metadata_root))
        for file in files:
            product = file.name.removesuffix(".product_settings.yaml").lower()
            if not game_product(product) or file.parent.name.lower() != product:
                continue
            fields = self._read(file, install_fields)
            if not fields:
                continue
            root = self._root(fields.get("product_install_full_path"))
            if root is None:
                continue
            gid = "riot:" + product
            prior = games.get(gid)
            shortcut = ntpath.basename(fields.get("shortcut_name", ""))
            name = prior.name if prior else NAMES.get(product.partition(".")[0], "")
            name = name or (shortcut[:-4] if shortcut.lower().endswith(".lnk") else root.name)
            games[gid] = Game(gid, name, "Riot", str(root), str(file))
            roots.add(str(root.parent))
            library = self._root(fields.get("product_install_root"))
            if library and within(root, library):
                roots.add(str(library))
        def index_reader(text):
            value = json.loads(text)
            if not isinstance(value, dict) or not isinstance(value.get("associated_client", {}), dict):
                raise ValueError("Invalid Riot installation index")
            return value.get("associated_client", {})
        associated = self._read(self.client_index, index_reader) if self.client_index.is_file() else {}
        self.hints = []
        for location in associated or {}:
            root = self._root(location)
            if root is not None:
                # The index explicitly associates this installation with Riot.
                # Keep its exact root so measured time can merge into the product ID.
                self.hints.append(Game("pending:riot:" + norm(root), root.name, "Riot", str(root), str(self.client_index)))
                roots.add(str(root.parent))
        self.game_roots = sorted(roots)
        return list(games.values())

    def watch_specs(self):
        return self.registry.watch_specs()

    def directory_specs(self):
        return [(str(self.metadata_root), True, "riot"), (str(self.client_index.parent), False, "riot")] + [
            (root, False, "riot") for root in self.game_roots]
