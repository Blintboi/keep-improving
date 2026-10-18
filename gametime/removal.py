"""Plan user initiated removals. Never delete a game or run registry command text."""
from dataclasses import dataclass, replace
import os
from pathlib import Path
import re
import subprocess
from .model import norm, within
from .i18n import tr

APPS = "ms-settings:appsfeatures"
GUID = re.compile(r"\{[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\}", re.I)
UNINSTALLER = re.compile(r"(?:unins\d*|uninstall|uninstaller)\.exe", re.I)


@dataclass(frozen=True)
class RemovalPlan:
    title: str
    instructions: str
    kind: str  # uri, exe, or folder
    target: str
    arguments: tuple = ()


def registrations():
    """Read installation fields only, across user, 32 bit and 64 bit entries."""
    if os.name != "nt":
        return []
    import winreg
    result = []
    for hive, view in ((winreg.HKEY_CURRENT_USER, 0), (winreg.HKEY_LOCAL_MACHINE, 0x100),
                       (winreg.HKEY_LOCAL_MACHINE, 0x200)):
        try:
            with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", 0,
                                winreg.KEY_READ | view) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    child = winreg.EnumKey(key, index)
                    try:
                        with winreg.OpenKey(key, child) as entry:
                            row = {"key": child}
                            for name in ("DisplayName", "InstallLocation", "WindowsInstaller", "UninstallString"):
                                try:
                                    row[name] = winreg.QueryValueEx(entry, name)[0]
                                except OSError:
                                    pass
                            result.append(row)
                    except OSError:
                        continue
        except OSError:
            continue
    return result


def apps_plan(game):
    return RemovalPlan("Open Windows Installed apps",
                       f'Find "{game.name}" in Settings → Apps → Installed apps. Open its menu and choose Uninstall. '
                       "For Riot games, close Riot Client and the game first. Windows or the publisher may ask for confirmation.",
                       "uri", APPS)


def _client(game):
    candidates = []
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates.extend([Path(base) / "Epic Games/Launcher/Portal/Binaries/Win64/EpicGamesLauncher.exe",
                               Path(base) / "Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe"]
                              if game.source == "Epic" else
                              [Path(base) / "Ubisoft/Ubisoft Game Launcher/UbisoftConnect.exe"])
    if game.source == "Ubisoft":
        # Read the same registered client roots as discovery, including custom
        # drives. Game metadata is an ID, not an executable command.
        from .ubisoft import WindowsUbisoftRegistry
        candidates.extend(Path(root) / "UbisoftConnect.exe"
                          for root in WindowsUbisoftRegistry().read().get("launchers", []))
    return next((str(path) for path in candidates if path.is_file()), None)


def plan_removal(game, entries=None):
    if not game.installed:
        return apps_plan(game)
    if game.source == "Steam" and re.fullmatch(r"steam:[0-9]+", game.id):
        return RemovalPlan("Open Steam uninstall",
                           f'Steam will open the uninstall flow for "{game.name}". Confirm the removal in Steam. '
                           "Back up any saves that are not synced to Steam Cloud first.",
                           "uri", "steam://uninstall/" + game.id.split(":", 1)[1])
    if game.source in ("Epic", "Ubisoft"):
        client = _client(game)
        if client:
            steps = ("Library → the game's ⋯ menu → Uninstall" if game.source == "Epic" else
                     "Games → the game → Manage → Uninstall")
            return RemovalPlan(f"Open {game.source} launcher",
                               f'In the launcher, find "{game.name}" and choose {steps}. '
                               "Finish the publisher's confirmation there. Back up local saves first.", "exe", client)
        return apps_plan(game)
    if game.source in ("Riot", "Minecraft"):
        return apps_plan(game)
    root = Path(game.root)
    # Avoid treating a drive, home, or shared system folder as a portable game.
    protected = {norm(value) for value in (os.environ.get("USERPROFILE", ""), os.environ.get("WINDIR", ""),
                                          os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")) if value}
    if not root.is_absolute() or root.parent == root or norm(root) in protected or not root.is_dir():
        return apps_plan(game)
    matching = [entry for entry in (registrations() if entries is None else entries)
                if entry.get("InstallLocation") and norm(entry["InstallLocation"].strip('" ')) == norm(root)]
    for entry in matching:
        if entry.get("WindowsInstaller") == 1 and GUID.fullmatch(entry.get("key", "")):
            return RemovalPlan("Open Windows Installer",
                               f'Windows Installer will ask to remove "{game.name}". Back up local saves first.',
                               "exe", str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/msiexec.exe"),
                               ("/x", entry["key"]))
        # Use only an executable inside this exact installation. Drop all registry
        # flags, including silent flags; command strings are never sent to a shell.
        command = entry.get("UninstallString", "").strip()
        candidate = command.split('"')[1] if command.startswith('"') and '"' in command[1:] else command.split(" ", 1)[0]
        path = Path(candidate)
        if (path.is_absolute() and UNINSTALLER.fullmatch(path.name) and within(path, root)
                and path.is_file() and within(path.resolve(), root.resolve())):
            return RemovalPlan("Open game uninstaller", f'The publisher\'s uninstaller for "{game.name}" will open. '
                               "Review its confirmation and back up local saves first.", "exe", str(path))
    for filename in ("unins000.exe", "uninstall.exe", "Uninstall.exe", "uninstaller.exe"):
        path = root / filename
        if path.is_file() and not path.is_symlink() and within(path.resolve(), root.resolve()):
            return RemovalPlan("Open game uninstaller", f'The uninstaller in "{root}" will open. '
                               "Review the publisher's confirmation and back up local saves first.", "exe", str(path))
    return RemovalPlan("Open game folder",
                       f'No supported uninstaller was found for "{game.name}". First check Installed apps or the publisher\'s '
                       f'launcher. For a portable game, close it, back up saves, then delete only its game folder manually: {root}. '
                       "The monitor will not delete these files for you.", "folder", str(root))


def execute(plan):
    """Called only after the user confirms the displayed plan."""
    if plan.kind == "uri":
        if plan.target != APPS and not re.fullmatch(r"steam://uninstall/[0-9]+", plan.target):
            raise ValueError("Unsupported removal link")
        os.startfile(plan.target)
    elif plan.kind == "folder":
        if not Path(plan.target).is_dir():
            raise FileNotFoundError(plan.target)
        os.startfile(plan.target)
    elif plan.kind == "exe":
        if not Path(plan.target).is_absolute() or not Path(plan.target).is_file():
            raise FileNotFoundError(plan.target)
        # Let Windows handle elevation if the publisher requires it. No shell
        # command text, quiet flags, recursive deletes, or guessed URI actions.
        if plan.arguments:
            subprocess.Popen([plan.target, *plan.arguments], shell=False)
        else:
            os.startfile(plan.target)
    else:
        raise ValueError("Unsupported removal action")


def localize_plan(plan, game, language):
    """Translate presentation only; the approved target/arguments remain identical."""
    if language != "hu":
        return plan
    title = tr(plan.title, language)
    if plan.title.endswith(" launcher"):
        title = tr("Open {source} launcher", language, source=game.source)
    if plan.title == "Open Steam uninstall":
        instructions = f'A Steam megnyitja a(z) „{game.name}” eltávolítását. A törlést a Steamben erősítsd meg. Előtte készíts másolatot a felhőbe nem szinkronizált mentésekről.'
    elif plan.title.endswith(" launcher"):
        steps = "Könyvtár → a játék ⋯ menüje → Eltávolítás" if game.source == "Epic" else "Játékok → a játék → Kezelés → Eltávolítás"
        instructions = f'A {game.source} kliensben keresd a(z) „{game.name}” játékot. Lépések: {steps}. Az eltávolítást a kiadó felületén fejezd be. Előtte mentsd a helyi játékállásokat.'
    elif plan.target == APPS:
        instructions = f'A Gépház → Alkalmazások → Telepített alkalmazások oldalon keresd: „{game.name}”. A menüjében válaszd az Eltávolítást. Riot-játék előtt zárd be a Riot klienst is. Minecraftnál a Minecraft Launcher bejegyzését keresd; a világok és játékfájlok megmaradhatnak.'
    elif plan.kind == "folder":
        instructions = f'A(z) „{game.name}” játékhoz nem találtunk támogatott eltávolítót. Előbb ellenőrizd a Telepített alkalmazásokat vagy a kiadó kliensét. Hordozható játéknál zárd be a játékot, mentsd a játékállásokat, majd kézzel töröld kizárólag a játékmappát: {game.root}. A figyelő nem törli helyetted ezeket a fájlokat.'
    else:
        instructions = f'Megnyílik a(z) „{game.name}” saját eltávolítója. Ellenőrizd a kiadó megerősítését, és előtte mentsd a helyi játékállásokat. Telepítési hely: {game.root}.'
    return replace(plan, title=title, instructions=instructions)
