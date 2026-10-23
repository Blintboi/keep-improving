"""Event-driven Gaming Hub. Own only recorded shortcuts; never modify a game."""
from dataclasses import asdict
from contextlib import contextmanager
from collections import Counter
from datetime import datetime
import hashlib
import json
import logging
import ntpath
import os
from pathlib import Path
from queue import Queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import quote, unquote, urlsplit
import uuid
from .model import blocked, helper, norm, within
from .launcher_defs import PLATFORM_SOURCES, CLIENTS as LAUNCHER_CLIENTS, client_id

log = logging.getLogger(__name__)
MARKER = "GameTimeHub.v1"


@contextmanager
def hub_lock(root):
    path = Path(root) / ".gametime-hub.lock"
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def shortcut_locations():
    """Windows known folders also work when Desktop is redirected to OneDrive."""
    if os.name != "nt":
        return []
    import ctypes
    result = []
    for csidl, depth in ((0x10, 0), (0x19, 0), (0x02, 8), (0x17, 8)):
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buffer) == 0 and buffer.value:
            result.append({"path": buffer.value, "depth": depth})
    return result


def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " - ", value)
    value = re.sub(r"\s+", " ", value).strip().rstrip(". ")[:110].rstrip(". ") or "Jatek"
    if value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *("COM" + str(i) for i in range(1, 10)),
                                       *("LPT" + str(i) for i in range(1, 10))}:
        value = "_" + value
    return value


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def url_value(contents):
    match = re.search(r"^URL\s*=\s*(.+?)\s*$", contents or "", re.I | re.M)
    return match[1] if match else ""


def same_game_link(link, game, rules):
    """Match actual paths/product IDs, never a desktop shortcut's display name."""
    uri = url_value(link.get("contents"))
    gid = game.id
    if uri:
        parsed = urlsplit(uri)
        if game.source == "Steam":
            return (parsed.scheme == "steam" and parsed.netloc in {"rungameid", "run"}
                    and parsed.path.strip("/").split("/")[0] == gid.removeprefix("steam:"))
        if game.source == "Ubisoft":
            return parsed.scheme == "uplay" and parsed.netloc == "launch" and parsed.path.strip("/").split("/")[0] == gid.removeprefix("ubisoft:")
        if game.source == "Epic":
            return (parsed.scheme == "com.epicgames.launcher" and parsed.netloc == "apps"
                    and unquote(parsed.path).strip("/").split(":")[-1] == gid.removeprefix("epic:"))
        if game.source == 'Amazon':
            return parsed.scheme == 'amazon-games' and parsed.netloc == 'play' and parsed.path.strip('/') == gid.removeprefix('amazon:')
        if game.source == 'EA':
            from .platforms import ea_offer
            from urllib.parse import parse_qs
            offer = ea_offer(game.root)
            return bool(offer and parsed.scheme == 'origin2' and parsed.netloc == 'game' and parsed.path == '/launch'
                        and parse_qs(parsed.query).get('offerIds') == [offer])
        return False
    target = link.get("target", "")
    if not target or target.startswith("\\\\") or not Path(target).is_file():
        return False
    if game.source == "Riot" and ntpath.basename(target).lower() == "riotclientservices.exe":
        args = link.get("arguments", "")
        product = re.search(r"(?:^|\s)--launch-product=([a-z0-9_]+)(?:\s|$)", args, re.I)
        patchline = re.search(r"(?:^|\s)--launch-patchline=([a-z0-9_-]+)(?:\s|$)", args, re.I)
        return bool(product and patchline and gid.lower() == "riot:" + product[1].lower() + "." + patchline[1].lower())
    if Path(target).suffix.lower() != ".exe" or blocked(target):
        return False
    key = norm(target)
    if key in rules:
        return rules[key] == gid
    return not helper(target) and within(target, game.root) and game.source != "Kézi"


def game_executables(root):
    """Bounded lookup in one already recognized Games installation only."""
    pending, result, visited = [(Path(root), 0)], [], 0
    while pending and visited < 200 and len(result) < 64:
        folder, depth = pending.pop(0)
        visited += 1
        try:
            children = list(folder.iterdir())
        except OSError:
            continue
        for path in children:
            if path.is_symlink() or getattr(path.stat(), "st_file_attributes", 0) & 0x400:
                continue
            if path.is_dir() and depth < 4:
                pending.append((path, depth + 1))
            elif path.is_file() and path.suffix.lower() == ".exe" and not helper(path):
                result.append(str(path))
    return result


class PowerShellLinks:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.process = None
        self.lock = threading.Lock()
        self.closed = False

    def call(self, request):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="hub-stage-", dir=self.data_dir) as temp:
            request_path = Path(temp) / "request.json"
            request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            executable = str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe")
            command = [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                       "-File", str(Path(__file__).with_name("hub_links.ps1")), "-RequestPath", str(request_path)]
            with self.lock:
                if self.closed:
                    raise OSError("Gaming Hub stopped")
                process = self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                output, errors = process.communicate(timeout=30)
                if process.returncode:
                    raise OSError(errors.decode("utf-8", "replace")[-1500:])
                return json.loads(output.decode("utf-8-sig"))
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise OSError("Shortcut processing timed out")
            finally:
                with self.lock:
                    self.process = None

    def inventory(self, roots):
        return self.call({"action": "inventory", "roots": roots})

    def create(self, links):
        return self.call({"action": "create", "links": links})

    def close(self):
        with self.lock:
            self.closed = True
            if self.process and self.process.poll() is None:
                self.process.terminate()


class Hub:
    def __init__(self, data_dir, bridge=None, locations=None):
        self.data_dir = Path(data_dir)
        self.bridge = bridge or PowerShellLinks(data_dir)
        self.locations = shortcut_locations() if locations is None else locations
        self.state_path = self.data_dir / "hub-state.json"

    def _load(self, path=None):
        path = path or self.state_path
        if not path.exists():
            return {"marker": MARKER, "links": []}
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("marker") != MARKER or not isinstance(state.get("links"), list):
            raise ValueError("Gaming Hub ownership data is unreadable; existing files were preserved.")
        return state

    def _save(self, state):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.state_path)
        authority = Path(state["root"]) / ".gametime-hub.json"
        scratch = authority.with_suffix(".tmp")
        scratch.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(scratch, authority)
        if os.name == "nt":
            import ctypes
            for path in (authority, authority.with_name(".gametime-hub.lock")):
                ctypes.windll.kernel32.SetFileAttributesW(str(path), 2)

    @staticmethod
    def _safe(root, path):
        root, path = Path(root), Path(path)
        if norm(root) == norm(path) or not within(path, root) or not within(path.resolve(), root.resolve()):
            raise ValueError("Shortcut path is outside the Gaming Hub folder")
        current = path
        while within(current, root):
            if current.exists() and (current.is_symlink() or getattr(current.stat(), "st_file_attributes", 0) & 0x400):
                raise ValueError("Hub destination cannot be a directory junction")
            if current == root:
                break
            current = current.parent
        return path

    def _recipe(self, game, inventory, rules, root):
        candidates = [link for link in inventory if same_game_link(link, game, rules)]
        candidates += [link for link in inventory if (link.get("owned_game") == game.id or
                       (link.get("owned_game", "").startswith("manual:") and game.source in {"Minecraft", "Steam", "Epic", "Ubisoft", "Riot", *PLATFORM_SOURCES}))
                       and norm(link.get("owned_root", "")) == norm(game.root)
                       and (url_value(link.get("contents")) or Path(link.get("target", "")).is_file())]
        # Existing, explicitly collected special launchers (e.g. Minecraft or a
        # Store AppsFolder link) are retained with their original arguments.
        for link in inventory:
            path = Path(link["path"])
            if (within(path, root) and path.parent.name == "Inditas" and
                    safe_name(path.stem).casefold() == safe_name(game.name).casefold() and
                    link.get("target") and Path(link["target"]).is_file()):
                candidates.append(link)
        if candidates:
            link = candidates[0]
            return {"kind": "copy", "source": link["path"], "extension": Path(link["path"]).suffix.lower()}
        if game.source in PLATFORM_SOURCES:
            from .platforms import game_recipe
            recipe = game_recipe(game, inventory)
            if recipe:
                return recipe
        if game.source == "Minecraft":
            from .minecraft import launcher
            target = launcher()
            if target:
                return {"kind": "link", "extension": ".lnk", "target": target, "working": str(Path(target).parent)}
        appid = game.id.partition(":")[2]
        if game.source == "Steam" and appid.isdigit():
            return {"kind": "url", "url": "steam://rungameid/" + appid, "extension": ".url"}
        if game.source == "Ubisoft" and appid.isdigit():
            return {"kind": "url", "url": "uplay://launch/" + appid + "/0", "extension": ".url"}
        if game.source == "Epic" and Path(game.metadata).is_file():
            try:
                meta = json.loads(Path(game.metadata).read_text(encoding="utf-8-sig"))
                if meta.get("AppName") == appid:
                    parts = [meta.get("CatalogNamespace"), meta.get("CatalogItemId"), appid]
                    value = ":".join(parts) if all(isinstance(p, str) and p for p in parts) else appid
                    return {"kind": "url", "extension": ".url", "url":
                            "com.epicgames.launcher://apps/" + quote(value, safe="") + "?action=launch&silent=true"}
            except (ValueError, OSError, TypeError):
                pass
        if game.source == "Riot" and re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_-]+", appid):
            client = next((link.get("target") for link in inventory
                           if ntpath.basename(link.get("target", "")).lower() == "riotclientservices.exe"
                           and Path(link["target"]).is_file()), None)
            if client:
                product, patchline = appid.split(".", 1)
                return {"kind": "link", "extension": ".lnk", "target": client,
                        "arguments": f"--launch-product={product} --launch-patchline={patchline}",
                        "working": str(Path(client).parent)}
        executables = [p for p, gid in rules.items() if gid == game.id and within(p, game.root)
                       and Path(p).is_file() and not blocked(p)]
        if not executables and game.source in ("Games", *PLATFORM_SOURCES):
            executables = game_executables(game.root)
        if len(executables) == 1:
            target = executables[0]
            return {"kind": "link", "extension": ".lnk", "target": target, "working": str(Path(target).parent)}
        return {"kind": "link", "extension": ".lnk", "target": game.root, "folder": True}

    def sync(self, settings, games, rules, overrides):
        if not settings.hub_enabled:
            return {"enabled": False}
        root = Path(settings.games_root)
        self._safe(root, root / "probe.lnk")
        root.mkdir(parents=True, exist_ok=True)
        with hub_lock(root):
            return self._sync_locked(settings, tuple(games), rules, overrides, root)

    def _sync_locked(self, settings, games, rules, overrides, root):
        state = self._load()
        authority = root / ".gametime-hub.json"
        self._safe(root, authority)
        if authority.exists():
            state = self._load(authority)
            if norm(state.get("owner", "")) != norm(self.data_dir.resolve()):
                raise OSError("This Gaming Hub is managed by another profile. Open the installed monitor.")
        # Never mutate a previous Games root after the user changes the setting.
        prior = {norm(item["path"]): item for item in state["links"]
                 if within(item["path"], root) and norm(item["path"]) != norm(root)}
        inventory = self._inventory(root, prior)
        return self._write_links(settings, games, rules, overrides, root, prior, inventory)

    def launch_recipe(self, game, settings, rules):
        """Read launch information without creating or changing any shortcuts."""
        root = Path(settings.games_root)
        authority = root / ".gametime-hub.json"
        state = self._load(authority if authority.exists() else None)
        prior = {norm(item["path"]): item for item in state["links"] if within(item["path"], root)}
        return self._recipe(game, self._inventory(root, prior), rules, root)

    def _inventory(self, root, prior):
        locations = self.locations + [{"path": str(root), "depth": 0},
                     {"path": str(root / "Inditas"), "depth": 0}, {"path": str(root / "Sakk"), "depth": 2},
                     {"path": str(root / "Launcherek"), "depth": 0}, {"path": str(root / "Chess"), "depth": 2},
                     {"path": str(root / "Launchers"), "depth": 0}]
        inventory = self.bridge.inventory(locations)
        for link in inventory:
            old = prior.get(norm(link["path"]))
            if old and old.get("role") == "launch" and Path(link["path"]).is_file() and digest(link["path"]) == old.get("hash"):
                link["owned_game"], link["owned_root"] = old["gid"], old.get("game_root", "")
        return inventory

    def _write_links(self, settings, games, rules, overrides, root, prior, inventory):
        eligible = [g for g in games if g.installed and not g.id.startswith("pending:") and Path(g.root).is_dir()
                    and overrides.get(g.id, True)]
        recipes, names = [], set()
        name_counts = Counter(safe_name(game.name).casefold() for game in eligible)
        for game in sorted(eligible, key=lambda g: g.id):
            recipe = self._recipe(game, inventory, rules, root)
            for kind, folder, spec in [("launch", root, recipe),
                                       ("folder", root / "Folders", {"kind": "link", "extension": ".lnk", "target": game.root})]:
                if kind == "folder" and norm(game.root) == norm(root):
                    continue
                stem = safe_name(game.name)
                if name_counts[stem.casefold()] > 1:
                    stem += " (" + safe_name("Manual" if game.source == "Kézi" else game.source) + ")"
                suffix = hashlib.sha256(game.id.encode()).hexdigest()[:8]
                path = folder / (stem + spec["extension"])
                for attempt in range(100):
                    self._safe(root, path)
                    old = prior.get(norm(path))
                    owned = old and path.is_file() and digest(path) == old.get("hash")
                    if norm(path) not in names and (not path.exists() or owned):
                        break
                    path = folder / (stem + " (" + suffix + ("-" + str(attempt) if attempt else "") + ")" + spec["extension"])
                else:
                    raise OSError("Too many shortcuts with the same name")
                names.add(norm(path))
                recipes.append(dict(spec, path=str(path), gid=game.id, game_root=game.root,
                                    role=kind, fallback=bool(spec.get("folder"))))
        client_names = set()
        for link in inventory:
            identity = client_id(link.get('target', ''))
            name = LAUNCHER_CLIENTS[identity][0] if identity else None
            if not name or name in client_names or link.get("arguments") or not Path(link["target"]).is_file():
                continue
            client_names.add(name)
            path = root / "Launchers" / (name + ".lnk")
            self._safe(root, path)
            old = prior.get(norm(path))
            if path.exists() and (not old or digest(path) != old.get("hash")):
                continue
            names.add(norm(path))
            recipes.append({"kind": "copy", "source": link["path"], "extension": ".lnk", "path": str(path),
                            "gid": "launcher:" + name, "role": "launcher", "fallback": False})
        self.data_dir.mkdir(parents=True, exist_ok=True)
        backup = self.data_dir / "backups" / ("hub-links-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
        written, modified = [], 0
        with tempfile.TemporaryDirectory(prefix="hub-build-", dir=self.data_dir) as temp:
            staging, creates = [], []
            for index, recipe in enumerate(recipes):
                staged = Path(temp) / (str(index) + recipe["extension"])
                signature_fields = {k: v for k, v in recipe.items() if k not in {"path", "source"}}
                if recipe["kind"] == "copy":
                    signature_fields["source_hash"] = digest(recipe["source"])
                recipe["signature"] = hashlib.sha256(json.dumps(signature_fields, sort_keys=True).encode()).hexdigest()
                old = prior.get(norm(recipe["path"]))
                if (old and old.get("signature") == recipe["signature"] and Path(recipe["path"]).is_file()
                        and digest(recipe["path"]) == old.get("hash")):
                    shutil.copyfile(recipe["path"], staged)
                elif recipe["kind"] == "copy":
                    shutil.copyfile(recipe["source"], staged)
                elif recipe["kind"] == "url":
                    staged.write_text("[InternetShortcut]\nURL=" + recipe["url"] + "\n", encoding="utf-8")
                else:
                    creates.append({"path": str(staged), "target": recipe["target"],
                                    "arguments": recipe.get("arguments", ""), "working": recipe.get("working", ""),
                                    "icon": "", "description": MARKER + ":" + recipe["gid"]})
                staging.append((recipe, staged))
            if creates:
                self.bridge.create(creates)
            for recipe, staged in staging:
                path = self._safe(root, recipe["path"])
                expected = digest(staged)
                old = prior.get(norm(path))
                if path.exists():
                    if not old or digest(path) != old.get("hash"):
                        raise OSError("A shortcut changed while processing; it was preserved: " + str(path))
                    if digest(path) != expected:
                        backup.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, backup / (hashlib.sha256(str(path).encode()).hexdigest()[:8] + "-" + path.name))
                if not path.exists() or digest(path) != expected:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    scratch = path.with_name(".hub-" + uuid.uuid4().hex + path.suffix)
                    try:
                        shutil.copyfile(staged, scratch)
                        os.replace(scratch, path)
                    finally:
                        scratch.unlink(missing_ok=True)
                    modified += 1
                assert digest(path) == expected
                written.append({"path": str(path), "hash": expected, "gid": recipe["gid"],
                                "game_root": recipe.get("game_root", ""),
                                "role": recipe["role"], "fallback": recipe["fallback"], "signature": recipe["signature"]})
            # Retire only unchanged shortcuts from this hub's own ledger.
            for key, item in prior.items():
                path = self._safe(root, item["path"])
                if key not in names and path.is_file() and digest(path) == item.get("hash"):
                    backup.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, backup / (hashlib.sha256(str(path).encode()).hexdigest()[:8] + "-" + path.name))
                    path.unlink()
                    modified += 1
        state = {"marker": MARKER, "root": str(root), "owner": str(self.data_dir.resolve()), "links": written}
        self._save(state)
        return {"enabled": True, "games": len(eligible), "links": len(written), "changed": modified,
                "folder_fallbacks": sum(r["role"] == "launch" and r["fallback"] for r in recipes)}


class HubWorker:
    def __init__(self, data_dir, hub=None):
        self.hub = hub or Hub(data_dir)
        self.results = Queue()
        self.condition = threading.Condition()
        self.pending = None
        self.first_request = None
        self.failures = 0
        from .background import BackgroundFailures
        self.problems = BackgroundFailures()
        self.closed = False
        self.thread = threading.Thread(target=self._run, daemon=True, name="gaming-hub")
        self.thread.start()

    def request(self, settings, games, rules, overrides):
        from .model import Settings
        with self.condition:
            now = time.monotonic()
            if self.pending is None:
                self.first_request = now
            self.pending = (Settings(**asdict(settings)), tuple(games), dict(rules), dict(overrides))
            self.failures = 0
            self.due = min(now + 1, self.first_request + 5)
            self.condition.notify()

    def _run(self):
        while True:
            with self.condition:
                while not self.closed and (self.pending is None or time.monotonic() < self.due):
                    self.condition.wait(None if self.pending is None else max(.01, self.due - time.monotonic()))
                if self.closed:
                    return
                job, self.pending = self.pending, None
                self.first_request = None
            try:
                result = self.hub.sync(*job)
                self.failures = 0
                self.problems.update("shortcuts", False)
                if result.get("enabled"):
                    log.info("Gaming Hub updated: %d games, %d shortcuts, %d changes",
                             result["games"], result["links"], result["changed"])
                self.results.put(result)
            except Exception as exc:
                log.exception("Gaming Hub update failed")
                self.failures = self.problems.update("shortcuts", True)
                self.results.put({"error": str(exc), "persistent": bool(self.problems.reported)})
                with self.condition:
                    now = time.monotonic()
                    remaining = self.problems.failures["shortcuts"][0] + self.problems.PERSISTENT_SECONDS - now
                    if not self.closed and self.pending is None and (self.failures <= self.problems.MAX_RETRIES or remaining > 0):
                        self.pending = job
                        self.first_request = now
                        self.due = now + (self.problems.retry_delay(self.failures) if self.failures <= self.problems.MAX_RETRIES else remaining)

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify()
        self.hub.bridge.close()
        self.thread.join(timeout=4)
