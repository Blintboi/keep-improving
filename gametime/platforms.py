"""Local installation indexes for additional publishers, read on discovery events.

No account calls, library downloads, drive walks, registry command execution or
changes to publisher data. Missing clients do not create placeholder entries.
"""
import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
from urllib.parse import quote
import xml.etree.ElementTree as ET
from .launcher_defs import CLIENTS, CLIENT_PATHS, PLATFORM_SOURCES, SOURCE_CLIENT, client_id
from .model import Game, blocked, helper, norm, within

UNINSTALL = r'Software\Microsoft\Windows\CurrentVersion\Uninstall'
PACKAGES = r'Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages'
GAME_KEYS = {
    'GOG': (r'Software\GOG.com\Games',),
    'EA': (r'Software\EA Games', r'Software\Origin Games', r'Software\EA SPORTS',
           r'Software\Electronic Arts\EA Games', r'Software\Maxis'),
}
SCOPES = (('HKCU', 0x100), ('HKCU', 0x200), ('HKLM', 0x100), ('HKLM', 0x200))
FIELDS = ('DisplayName', 'InstallLocation', 'DisplayIcon', 'UninstallString', 'Publisher',
          'Install Dir', 'InstallDir', 'PATH', 'path', 'gameID', 'gameName', 'GOGGAMEID',
          'PackageRootFolder')
AUMID = re.compile(r'[A-Za-z0-9.\-]+_[a-z0-9]{13}![A-Za-z0-9.\-_]+')


def local_root(value):
    if not isinstance(value, str) or not value or '\0' in value or value.startswith(('\\\\', '//')):
        return None
    root = Path(value.strip('" '))
    protected = {norm(os.environ[key]) for key in ('USERPROFILE', 'WINDIR', 'ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA') if os.environ.get(key)}
    if not root.is_absolute() or root.parent == root or norm(root) in protected or not root.is_dir():
        return None
    return root.resolve()


def read_xml(path):
    with Path(path).open('rb') as handle:
        raw = handle.read(2 * 1024 * 1024 + 1)
    declarations = raw.replace(b'\0', b'').upper()
    if len(raw) > 2 * 1024 * 1024 or b'<!DOCTYPE' in declarations or b'<!ENTITY' in declarations:
        raise ValueError('Invalid installation manifest')
    return ET.fromstring(raw)


def nodes(tree, name):
    return [item for item in tree.iter() if item.tag.rsplit('}', 1)[-1].lower() == name.lower()]


class WindowsInstallRegistry:
    """Read only installation fields, in user/machine and both registry views."""
    def __init__(self):
        self.errors = []

    def _read(self, hive, key, view, source, children=False):
        if os.name != 'nt':
            return [] if children else {}
        import winreg
        try:
            with winreg.OpenKey(getattr(winreg, 'HKEY_CURRENT_USER' if hive == 'HKCU' else 'HKEY_LOCAL_MACHINE'),
                                key, 0, winreg.KEY_READ | view) as handle:
                if children:
                    return [winreg.EnumKey(handle, index) for index in range(min(10000, winreg.QueryInfoKey(handle)[0]))]
                result = {}
                for name in FIELDS:
                    try:
                        result[name] = winreg.QueryValueEx(handle, name)[0]
                    except FileNotFoundError:
                        pass
                return result
        except FileNotFoundError:
            return [] if children else {}
        except OSError:
            self.errors.append('registry:' + source + ':' + hive + '\\' + key)
            return [] if children else {}

    def read(self):
        self.errors = []
        games, clients, packages = [], [], []
        for hive, view in SCOPES:
            for source, parents in GAME_KEYS.items():
                for parent in parents:
                    for child in self._read(hive, parent, view, source, True):
                        values = self._read(hive, parent + '\\' + child, view, source)
                        games.append(dict(values, source=source, key=child, dedicated=True))
            for child in self._read(hive, UNINSTALL, view, 'Publishers', True):
                values = self._read(hive, UNINSTALL + '\\' + child, view, 'Publishers')
                values['key'] = child
                command = values.get('UninstallString', '')
                publisher = str(values.get('Publisher', '')).casefold()
                key = child.casefold()
                source = None
                if key.endswith('_is1') and key[:-4].isdigit() and 'gog' in publisher:
                    source = 'GOG'
                elif isinstance(command, str) and re.search(r'Battle\.net.*--uid=', command, re.I):
                    source = 'Battle.net'
                elif isinstance(command, str) and re.search(r'(?:Launcher|uninstall)\.exe.*uninstall=', command, re.I) and 'rockstar' in publisher:
                    source = 'Rockstar'
                elif publisher in {'electronic arts', 'electronic arts, inc.', 'ea games', 'ea sports'}:
                    source = 'EA'
                if source:
                    games.append(dict(values, source=source))
                location = values.get('InstallLocation')
                label = str(values.get('DisplayName', '')).casefold()
                if isinstance(location, str):
                    for client, (title, names) in CLIENTS.items():
                        if label == title.casefold() or (client == 'ea' and label in {'ea app', 'ea desktop', 'origin'}):
                            clients.extend(str(Path(location.strip('" ')) / name) for name in names)
            for parent, value, filename in ((r'Software\GOG.com\GalaxyClient\paths', 'client', 'GalaxyClient.exe'),
                                             (r'Software\Electronic Arts\EA Desktop', 'InstallLocation', 'EADesktop.exe'),
                                             (r'Software\Rockstar Games\Launcher', 'InstallFolder', 'Launcher.exe')):
                # A few launcher registrations have fields outside the game schema.
                if os.name == 'nt':
                    import winreg
                    try:
                        with winreg.OpenKey(getattr(winreg, 'HKEY_CURRENT_USER' if hive == 'HKCU' else 'HKEY_LOCAL_MACHINE'), parent, 0, winreg.KEY_READ | view) as handle:
                            location = winreg.QueryValueEx(handle, value)[0]
                            if isinstance(location, str):
                                clients.append(str(Path(location) / filename))
                    except OSError:
                        pass
        for package in self._read('HKCU', PACKAGES, 0, 'Xbox', True):
            root = self._read('HKCU', PACKAGES + '\\' + package, 0, 'Xbox').get('PackageRootFolder')
            parts = package.split('_')
            if len(parts) >= 5 and isinstance(root, str):
                packages.append({'name': parts[0], 'family': parts[0] + '_' + parts[-1], 'root': root})
        return {'games': games, 'clients': clients, 'packages': packages, 'errors': list(dict.fromkeys(self.errors))}

    def watch_specs(self):
        if os.name != 'nt':
            return set()
        import winreg
        result = set()
        for hive, view in SCOPES:
            for target in (UNINSTALL, *(key for keys in GAME_KEYS.values() for key in keys)):
                actual = target
                while actual:
                    try:
                        with winreg.OpenKey(getattr(winreg, 'HKEY_CURRENT_USER' if hive == 'HKCU' else 'HKEY_LOCAL_MACHINE'), actual, 0, winreg.KEY_READ | view):
                            result.add((hive, actual, view, actual == target))
                        break
                    except OSError:
                        actual = actual.rpartition('\\')[0]
        actual = PACKAGES
        while actual:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, actual):
                    result.add(('HKCU', actual, 0, actual == PACKAGES))
                break
            except OSError:
                actual = actual.rpartition('\\')[0]
        return result


def package_app(package):
    root = local_root(package.get('root'))
    family = package.get('family', '')
    if root is None or not isinstance(family, str):
        return None
    tree = read_xml(root / 'AppxManifest.xml')
    identities = nodes(tree, 'Identity')
    if not identities or identities[0].get('Name') != package.get('name') or not family.startswith(package.get('name', '') + '_'):
        return None
    applications = nodes(tree, 'Application')
    applications = [item for item in applications if not any(node.get('AppListEntry', '').lower() == 'none' for node in item.iter())]
    if not applications:
        return None
    config = root / 'MicrosoftGame.config'
    if config.is_file():
        primary = [item.get('Id') for item in nodes(read_xml(config), 'Executable') if item.get('IsDevOnly', '').lower() != 'true']
        applications.sort(key=lambda item: item.get('Id') not in primary)
    appid = family + '!' + applications[0].get('Id', '')
    return (root, tree, appid) if AUMID.fullmatch(appid) else None


def xbox_client(packages):
    for package in packages:
        if package.get('name') != 'Microsoft.GamingApp':
            continue
        try:
            value = package_app(package)
            if value:
                return value[2]
        except (OSError, ValueError, ET.ParseError):
            pass
    return ''


class PlatformSources:
    def __init__(self, registry=None, amazon_db=None, battle_db=None):
        self.registry = registry or WindowsInstallRegistry()
        self.amazon_db = Path(amazon_db) if amazon_db is not None else Path(os.environ.get('LOCALAPPDATA', r'C:\Users\Default\AppData\Local')) / 'Amazon Games/Data/Games/Sql/GameInstallInfo.sqlite'
        self.battle_db = Path(battle_db) if battle_db is not None else Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'Battle.net/Agent/product.db'
        self.errors = []

    def scan(self):
        snapshot = self.registry.read()
        self.errors = list(snapshot.get('errors', []))
        found = {}
        for row in snapshot.get('games', []):
            source = row.get('source')
            root = local_root(row.get('InstallLocation') or row.get('Install Dir') or row.get('InstallDir') or row.get('PATH') or row.get('path'))
            if root is None or source not in PLATFORM_SOURCES:
                continue
            name = row.get('gameName') or row.get('DisplayName') or row.get('key')
            if not isinstance(name, str) or not name.strip() or name.casefold() in {'ea app', 'ea desktop', 'origin', 'gog galaxy', 'battle.net', 'rockstar games launcher'}:
                continue
            if re.search(r'anti.?cheat|\b(?:updater|service|redistributable|helper|launcher)\b', name, re.I):
                continue
            if any(client_id(root / filename) and (root / filename).is_file() for filename in ('EADesktop.exe', 'GalaxyClient.exe', 'Battle.net.exe', 'Launcher.exe', 'Origin.exe')):
                continue
            if source == 'GOG':
                identity = str(row.get('gameID') or row.get('GOGGAMEID') or row.get('key', '').removesuffix('_is1'))
                if not identity.isdigit():
                    continue
            elif source == 'Battle.net':
                match = re.search(r'--uid=([a-z0-9_]+)(?:\s|$)', str(row.get('UninstallString', '')), re.I)
                if not match:
                    continue
                identity = match[1].lower()
            elif source == 'Rockstar':
                match = re.search(r'uninstall=([a-z0-9_]+)(?:\s|$)', str(row.get('UninstallString', '')), re.I)
                if not match:
                    continue
                identity = match[1].lower()
            else:
                identity = ea_offer(root) or hashlib.sha256(str(row.get('key') or name).casefold().strip().encode()).hexdigest()[:24]
            prefix = {'Battle.net': 'battlenet'}.get(source, source.lower())
            game = Game(prefix + ':' + identity, name.strip(), source, str(root), 'registry:' + source + ':' + identity)
            # Dedicated publisher registrations take priority over uninstall labels.
            found.setdefault((source, norm(root)), game)
        self._battle(found)
        self._amazon(found)
        self._xbox(snapshot.get('packages', []), found)
        return list({game.id: game for game in found.values()}.values())

    def _battle(self, found):
        if not self.battle_db.exists():
            return
        try:
            from .battlenet import installations
            for identity, product, location in installations(self.battle_db):
                root = local_root(location)
                identity, product = identity.lower(), product.lower()
                if root is None or not re.fullmatch(r'[a-z0-9_]{1,80}', identity) or product not in BATTLE_PRODUCTS:
                    continue
                name = BATTLE_NAMES.get(product, root.name)
                found.setdefault(('Battle.net', norm(root)), Game('battlenet:' + identity, name, 'Battle.net', str(root), str(self.battle_db)))
        except (OSError, ValueError, TypeError, AttributeError):
            self.errors.append(str(self.battle_db))

    def _amazon(self, found):
        if not self.amazon_db.exists():
            return
        try:
            with closing(sqlite3.connect(self.amazon_db.resolve().as_uri() + '?mode=ro', uri=True, timeout=.2)) as db:
                rows = db.execute('SELECT Id,ProductTitle,InstallDirectory FROM DbSet WHERE Installed=1 LIMIT 10001').fetchall()
                if len(rows) > 10000:
                    raise ValueError('Too many installation entries')
            for identity, name, location in rows:
                root = local_root(location)
                if root is not None and isinstance(identity, str) and re.fullmatch(r'[a-zA-Z0-9_-]{1,160}', identity) and isinstance(name, str) and name.strip():
                    found[('Amazon', norm(root))] = Game('amazon:' + identity, name.strip(), 'Amazon', str(root), str(self.amazon_db))
        except (OSError, sqlite3.Error, ValueError):
            self.errors.append(str(self.amazon_db))

    def _xbox(self, packages, found):
        for package in packages:
            if package.get('name') in {'Microsoft.GamingApp', 'Microsoft.GamingServices'} or package.get('name', '').startswith('Microsoft.Xbox'):
                continue
            try:
                value = package_app(package)
                if not value:
                    continue
                root, tree, appid = value
                applications = nodes(tree, 'Application')
                if applications and all(blocked(root / node.get('Executable', '')) for node in applications if node.get('Executable')) and any(node.get('Executable') for node in applications):
                    continue
                config = root / 'MicrosoftGame.config'
                # GDK games identify themselves; ordinary Store applications do not.
                is_game = config.is_file() or any('xboxlive' in (node.tag + ' '.join(node.attrib.values())).lower() for node in tree.iter())
                if not is_game:
                    continue
                title = package['name']
                if config.is_file():
                    visuals = nodes(read_xml(config), 'ShellVisuals')
                    if visuals:
                        title = visuals[0].get('DefaultDisplayName') or title
                else:
                    visuals = nodes(tree, 'VisualElements')
                    if visuals:
                        title = visuals[0].get('DisplayName') or title
                if title.lower().startswith('ms-resource:'):
                    title = package['name']
                found[('Xbox', norm(root))] = Game('xbox:' + appid, title, 'Xbox', str(root), str(root / 'AppxManifest.xml'))
            except (OSError, ValueError, ET.ParseError):
                root = package.get('root', '')
                if root and (Path(root) / 'MicrosoftGame.config').is_file():
                    self.errors.append(str(Path(root) / 'AppxManifest.xml'))

    def watch_specs(self):
        return self.registry.watch_specs()

    def directory_specs(self):
        return [(str(self.amazon_db.parent), False, 'publishers'), (str(self.battle_db.parent), False, 'publishers')]


def ea_offer(root):
    path = Path(root) / '__Installer/installerdata.xml'
    if not path.is_file():
        return ''
    try:
        tree = read_xml(path)
        for node in nodes(tree, 'contentID') + nodes(tree, 'offerId'):
            value = (node.text or '').strip()
            if re.fullmatch(r'[A-Za-z0-9.:_-]{1,180}', value):
                return value
    except (OSError, ValueError, ET.ParseError):
        pass
    return ''


BATTLE_PRODUCTS = {'wow': 'WoW', 'diablo3': 'D3', 's2': 'S2', 's1': 'S1',
                   'hs_beta': 'WTCG', 'heroes': 'Hero', 'prometheus': 'Pro',
                   'w3': 'W3', 'fenris': 'Fen', 'fen': 'Fen', 'osi': 'OSI', 'viper': 'VIPR',
                   'odin': 'ODIN', 'lazarus': 'LAZR', 'zeus': 'ZEUS', 'pro': 'Pro', 'wtcg': 'WTCG',
                   'hero': 'Hero', 'd3': 'D3', 'anbs': 'ANBS', 'auks': 'AUKS', 'd1': 'D1',
                   'w1r': 'W1R', 'w2r': 'W2R'}
BATTLE_NAMES = {'wow': 'World of Warcraft', 'diablo3': 'Diablo III', 'd3': 'Diablo III',
                's2': 'StarCraft II', 's1': 'StarCraft', 'hs_beta': 'Hearthstone', 'wtcg': 'Hearthstone',
                'heroes': 'Heroes of the Storm', 'hero': 'Heroes of the Storm',
                'prometheus': 'Overwatch', 'pro': 'Overwatch', 'w3': 'Warcraft III',
                'fenris': 'Diablo IV', 'fen': 'Diablo IV', 'osi': 'Diablo II: Resurrected',
                'anbs': 'Diablo Immortal', 'auks': 'Call of Duty', 'd1': 'Diablo',
                'w1r': 'Warcraft: Remastered', 'w2r': 'Warcraft II: Remastered'}


def game_recipe(game, inventory=()):
    """Known product launch operations only; never execute uninstall/registry text."""
    identity = game.id.partition(':')[2]
    if game.source == 'Amazon' and re.fullmatch(r'[A-Za-z0-9_-]{1,160}', identity):
        return {'kind': 'url', 'url': 'amazon-games://play/' + identity, 'extension': '.url'}
    if game.source == 'EA':
        offer = ea_offer(game.root)
        if offer:
            return {'kind': 'url', 'url': 'origin2://game/launch?offerIds=' + quote(offer, safe=''), 'extension': '.url'}
    if game.source == 'Xbox' and AUMID.fullmatch(identity):
        root = Path(game.root)
        tree = read_xml(root / 'AppxManifest.xml')
        names = nodes(tree, 'Identity')
        if names and identity.startswith(names[0].get('Name', '') + '_') and any(identity.endswith('!' + node.get('Id', '')) for node in nodes(tree, 'Application')):
            return {'kind': 'link', 'extension': '.lnk', 'target': str(Path(os.environ.get('WINDIR', r'C:\Windows')) / 'explorer.exe'),
                    'arguments': 'shell:AppsFolder\\' + identity, 'app_id': identity}
    client = SOURCE_CLIENT.get(game.source)
    paths = [row.get('target', '') for row in inventory]
    paths += [str(Path(os.environ[env]) / relative) for env in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA')
              if os.environ.get(env) for relative in CLIENT_PATHS]
    target = next((value for value in paths if client_id(value) == client and Path(value).is_file()), '') if client else ''
    arguments = None
    if target and game.source == 'GOG' and identity.isdigit():
        arguments = ['/command=runGame', '/gameId=' + identity, '/path=' + game.root]
    elif target and game.source == 'Rockstar' and re.fullmatch(r'[a-z0-9_]+', identity):
        arguments = ['-launchTitleInFolder', game.root]
    elif target and game.source == 'Battle.net' and identity in BATTLE_PRODUCTS:
        arguments = ['--exec=launch ' + BATTLE_PRODUCTS[identity]]
    if arguments is not None:
        return {'kind': 'link', 'extension': '.lnk', 'target': target,
                'argument_list': arguments, 'arguments': subprocess.list2cmdline(arguments), 'working': str(Path(target).parent)}
    if game.source == 'GOG' and identity.isdigit():
        return gog_recipe(game)
    return None


def gog_recipe(game):
    """Offline GOG installs expose their primary play task without Galaxy."""
    path = Path(game.root) / ('goggame-' + game.id.partition(':')[2] + '.info')
    try:
        with path.open('rb') as handle:
            raw = handle.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            return None
        data = json.loads(raw.decode('utf-8-sig'))
        if str(data.get('gameId')) != game.id.partition(':')[2]:
            return None
        for task in data.get('playTasks', [])[:100]:
            if not isinstance(task, dict) or not task.get('isPrimary') or task.get('type') != 'FileTask':
                continue
            relative = task.get('path')
            if not isinstance(relative, str) or not relative:
                continue
            target = (Path(game.root) / relative).resolve()
            working = (Path(game.root) / (task.get('workingDir') or '')).resolve()
            if (not within(target, Path(game.root).resolve()) or not within(working, Path(game.root).resolve())
                    or target.suffix.lower() != '.exe' or helper(target) or not target.is_file()):
                continue
            arguments = task.get('arguments') or ''
            if not isinstance(arguments, str) or len(arguments) > 8192 or '\0' in arguments:
                continue
            argv = []
            if arguments:
                if os.name != 'nt':
                    continue
                import ctypes
                from ctypes import wintypes
                splitter = ctypes.windll.shell32.CommandLineToArgvW
                splitter.argtypes = (wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int))
                splitter.restype = ctypes.POINTER(wintypes.LPWSTR)
                count = ctypes.c_int()
                pointer = splitter('game.exe ' + arguments, ctypes.byref(count))
                if not pointer:
                    continue
                try:
                    argv = list(pointer[:count.value])[1:]
                finally:
                    ctypes.windll.kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
                    ctypes.windll.kernel32.LocalFree(pointer)
            return {'kind': 'link', 'extension': '.lnk', 'target': str(target), 'working': str(working),
                    'argument_list': argv, 'arguments': subprocess.list2cmdline(argv)}
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return None
