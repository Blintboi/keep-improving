"""Conservative local compatibility policy, never an anti-cheat bypass.

Only names and installation-file presence are inspected. No game memory,
modules, command lines, drivers or anti-cheat services are queried/modified.
"""
import ntpath
import os
from pathlib import Path
import re
import threading
import time

PROTECTED = 'Anti-cheat protection: overlays, game images and automatic Escape are disabled for this game.'
UNCHECKED = 'Game safety could not be checked. Overlays and game images are disabled.'
ANTI_HELPERS = frozenset({'beservice.exe','beservice_x64.exe','battleye.exe',
    'easyanticheat.exe','easyanticheat_eos.exe','easyanticheat_launcher.exe',
    'eaanticheat.gameservice.exe','eaanticheat.gameservice.launcher.exe','eaanticheat.installer.exe',
    'vgc.exe','vgtray.exe','ace-bootstrap.exe','anticheatexpert.exe'})
PROTECTED_EXES = frozenset({'cs2.exe','csgo.exe','csgo_legacy_app.exe','destiny2.exe',
    'valorant.exe','valorant-win64-shipping.exe','league of legends.exe',
    'rainbowsix.exe','rainbowsix_vulkan.exe','rainbowsix_dx11.exe','rainbowsix_be.exe',
    'fortniteclient-win64-shipping.exe','fortniteclient-win64-shipping_eac.exe',
    'fortniteclient-win64-shipping_be.exe','tslgame.exe','rustclient.exe','rust.exe',
    'r5apex.exe','r5apex_dx12.exe','escapefromtarkov.exe','cod.exe','cod22-cod.exe',
    'overwatch.exe','rocketleague.exe','fallguys_client.exe','robloxplayerbeta.exe'}) | ANTI_HELPERS
TITLE = re.compile(r'\b(?:counter[- ]strike|valorant|league of legends|teamfight tactics|destiny 2|'
    r'rainbow six|fortnite|pubg|rust|apex legends|escape from tarkov|call of duty|warzone|'
    r'overwatch|rocket league|fall guys|battlefield|ea sports fc|fifa|madden|f1(?: 20\d\d| \d\d)?|'
    r'ea sports wrc|plants vs\.? zombies)\b',re.I)
# Folder/file markers also cover games outside the built-in examples. Presence
# is sufficient: never try to determine or force an unprotected online mode.
MARKERS = ('EasyAntiCheat','EasyAntiCheat_EOS','BattlEye','AntiCheat','AntiCheatExpert',
    'EA AntiCheat','EAanticheat','ACE','GameGuard','XignCode','XignCode3','EQU8',
    'easyanticheat_x64.dll','easyanticheat_x86.dll',
    'easyanticheat_eos.exe','BEClient_x64.dll','BEClient.dll','BEService.exe',
    'BEService_x64.exe','EAAntiCheat.GameServiceLauncher.exe','start_protected_game.exe')
SUBDIRS = ('','Binaries','Binaries/Win64','Binaries/Win32','Game',
    'Game/Binaries/Win64','Engine/Binaries/ThirdParty','__Installer','__Installer/EAAntiCheat','_CommonRedist')


def anti_helper(path):
    return ntpath.basename(str(path)).casefold() in ANTI_HELPERS


def known_reason(path='',game=None):
    name=ntpath.basename(str(path)).casefold()
    if (name in PROTECTED_EXES or name.endswith(('_eac.exe','_be.exe'))
            or any(part.casefold() in {'easyanticheat','easyanticheat_eos','battleye','riot vanguard','anticheatexpert'}
                   for part in ntpath.normpath(str(path)).split('\\'))):
        return PROTECTED
    if game and (game.id in {'steam:730','steam:1085660'} or game.source=='Riot'
                 or TITLE.search(game.name) or TITLE.search(ntpath.basename(game.root))):
        return PROTECTED
    return ''


class SafetyPolicy:
    def __init__(self):
        self.cache={}; self.lock=threading.Lock()

    def reason(self,path='',game=None):
        reason=known_reason(path,game)
        if reason: return reason
        return self.inspection(path,game)

    def overlay_reason(self,path='',game=None,*,consented=False):
        reason=self.reason(path,game)
        if reason==PROTECTED and not anti_helper(path):
            if self.inspection(path,game)==UNCHECKED: return UNCHECKED
            if consented: return ''
        return reason

    def inspection(self,path='',game=None):
        """Cached installation check, including already known protected games."""
        root=str(game.root) if game else ''
        key=(ntpath.normcase(str(path)),ntpath.normcase(root))
        now=time.monotonic()
        with self.lock:
            cached=self.cache.get(key)
            if cached and now-cached[0]<60: return cached[1]
        reason=self.inspect(path,root)
        with self.lock:
            if len(self.cache)>=2048: self.cache.clear()
            self.cache[key]=(now,reason)
        return reason

    @staticmethod
    def inspect(path,root):
        # Fixed shallow probes, no recursive catalog/asset scan during gameplay.
        # Unavailable installations fail closed rather than claiming compatibility.
        bases=[]
        if any(ntpath.splitdrive(str(value))[0].startswith('\\\\') for value in (path,root) if value): return UNCHECKED
        if root:
            folder=Path(root)
            try:
                if not folder.is_dir() or folder.parent==folder: return UNCHECKED
            except OSError: return UNCHECKED
            bases.extend(folder/subdir for subdir in SUBDIRS)
        if path:
            folder=Path(path).parent
            bases.append(folder)
            for _ in range(4):
                if folder.parent==folder or root and (not folder.is_relative_to(Path(root)) or folder==Path(root)): break
                if not root and folder.name.casefold() not in {'bin','binaries','win64','win32','x64','x86','game'}: break
                folder=folder.parent
                bases.append(folder)
        for base in dict.fromkeys(bases):
            try:
                # Enumerate bounded shallow directories once, not one disk probe
                # per marker. Incomplete inspection must not allow an overlay.
                with os.scandir(base) as entries:
                    for count,entry in enumerate(entries):
                        name=entry.name.casefold()
                        if name in MARKER_NAMES or name.startswith(('easyanticheat','eaanticheat','battleye','beservice','anticheatexpert')): return PROTECTED
                        if count>=511: return UNCHECKED
            except (FileNotFoundError,NotADirectoryError): continue
            except OSError: return UNCHECKED
        return ''


MARKER_NAMES=frozenset(name.casefold() for name in MARKERS)
policy=SafetyPolicy()
