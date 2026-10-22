"""Prepare game launches off the UI thread; execute only an explicit Play action."""
from dataclasses import asdict, dataclass
import os
from pathlib import Path
from queue import Queue
import subprocess
import threading
from urllib.parse import quote, unquote, urlsplit
from .hub import Hub, digest, same_game_link, url_value
from .model import Settings, blocked, norm


@dataclass(frozen=True)
class LaunchPlan:
    kind: str
    target: str
    arguments: tuple = ()
    working: str = ""
    fingerprint: str = ""


def launch_uri(game, uri):
    """Keep the matching product, but always request launch, never a URL action."""
    if not same_game_link({"contents": "URL=" + uri}, game, {}):
        raise ValueError("The game launch link is invalid. Refresh the library or assign its EXE.")
    appid = game.id.partition(":")[2]
    if game.source == "Steam":
        return "steam://rungameid/" + appid
    if game.source == "Ubisoft":
        return "uplay://launch/" + appid + "/0"
    if game.source in {'Amazon', 'EA'}:
        from .platforms import game_recipe
        return game_recipe(game)['url']
    product = unquote(urlsplit(uri).path).strip("/")
    return "com.epicgames.launcher://apps/" + quote(product, safe="") + "?action=launch&silent=true"


def prepare(game, settings, rules, hub, preferred=""):
    if not game.installed or not Path(game.root).is_dir():
        raise ValueError("This game is no longer installed. Refresh the library.")
    if preferred:
        target = Path(preferred)
        if (rules.get(norm(preferred)) != game.id or blocked(preferred) or
                target.suffix.lower() != ".exe" or not target.is_file()):
            raise ValueError("The game's executable is unavailable. Refresh the library or assign its EXE.")
        return LaunchPlan("executable", str(target), working=str(target.parent))
    recipe = hub.launch_recipe(game, settings, rules)
    if recipe.get("folder"):
        raise ValueError("Choose the game's executable with Assign EXE, then try Play again.")
    if recipe.get('app_id'):
        return LaunchPlan('app', recipe['app_id'])
    if recipe["kind"] == "url":
        return LaunchPlan("uri", launch_uri(game, recipe["url"]))
    if recipe["kind"] == "copy":
        source = Path(recipe["source"])
        if source.suffix.lower() == ".url":
            return LaunchPlan("uri", launch_uri(game, url_value(source.read_text(encoding="utf-8-sig", errors="replace"))))
        if source.suffix.lower() != ".lnk" or not source.is_file():
            raise ValueError("The game launch link is invalid. Refresh the library or assign its EXE.")
        return LaunchPlan("shortcut", str(source), fingerprint=digest(source))
    target = Path(recipe["target"])
    if target.suffix.lower() != ".exe" or not target.is_file():
        raise ValueError("The game's executable is unavailable. Refresh the library or assign its EXE.")
    # Publisher recipes supply argv directly, preserving paths containing spaces.
    arguments = tuple(recipe.get('argument_list', recipe.get("arguments", "").split()))
    return LaunchPlan("executable", str(target), arguments, recipe.get("working") or str(target.parent))


def execute(plan):
    if plan.kind == 'app':
        from .platforms import AUMID
        if not AUMID.fullmatch(plan.target):
            raise ValueError('Unsupported game launcher')
        os.startfile('shell:AppsFolder\\' + plan.target)
    elif plan.kind == "uri":
        if urlsplit(plan.target).scheme not in {"steam", "uplay", "com.epicgames.launcher", "amazon-games", "origin2"}:
            raise ValueError("Unsupported game launcher")
        os.startfile(plan.target)
    elif plan.kind == "shortcut":
        path = Path(plan.target)
        if path.suffix.lower() != ".lnk" or not plan.fingerprint or digest(path) != plan.fingerprint:
            raise ValueError("The launch shortcut changed. Try Play again.")
        os.startfile(str(path))
    elif plan.kind == "executable":
        path = Path(plan.target)
        if path.suffix.lower() != ".exe" or not path.is_file():
            raise ValueError("The game's executable is unavailable. Refresh the library or assign its EXE.")
        subprocess.Popen([str(path), *plan.arguments], cwd=plan.working or str(path.parent), shell=False)
    else:
        raise ValueError("Unsupported game launcher")


class LaunchWorker:
    def __init__(self, data_dir, hub=None):
        self.hub = hub or Hub(data_dir)
        self.jobs, self.results = Queue(), Queue()
        self.closed = False
        self.thread = threading.Thread(target=self._run, daemon=True, name="game-launch")
        self.thread.start()

    def request(self, game, settings, rules, preferred=""):
        if not self.closed:
            self.jobs.put((game, Settings(**asdict(settings)), dict(rules), preferred))

    def _run(self):
        while not self.closed:
            job = self.jobs.get()
            if job is None or self.closed:
                return
            game, settings, rules, preferred = job
            try:
                self.results.put((game, prepare(game, settings, rules, self.hub, preferred), None))
            except Exception as exc:
                self.results.put((game, None, str(exc)))

    def close(self):
        self.closed = True
        self.jobs.put(None)
        self.hub.bridge.close()
        self.thread.join(timeout=4)
