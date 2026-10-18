"""Installed launcher clients, independent of game launch commands and budgets."""
from dataclasses import asdict,dataclass
import json
import ntpath
import os
from pathlib import Path
from queue import Queue
import subprocess
import threading
from .discovery import steam_roots
from .hub import PowerShellLinks,shortcut_locations
from .model import Settings,norm

CLIENTS={
    'steam':('Steam',{'steam.exe'}),
    'epic':('Epic Games Launcher',{'epicgameslauncher.exe'}),
    'riot':('Riot Client',{'riotclientservices.exe'}),
    'ubisoft':('Ubisoft Connect',{'ubisoftconnect.exe','upc.exe'}),
    'minecraft':('Minecraft Launcher',{'minecraftlauncher.exe'}),
}

@dataclass(frozen=True)
class Client:
    id:str
    name:str
    target:str

def local_executable(value):
    if not isinstance(value,str) or value.startswith(('\\\\','//')) or '\x00' in value:
        return False
    path=Path(value)
    return path.is_absolute() and path.suffix.lower()=='.exe' and path.is_file()

def find_clients(settings,inventory=(),candidates=None):
    paths=[]
    for row in inventory:
        if isinstance(row,dict) and not row.get('arguments'):
            paths.append(row.get('target',''))
    if candidates is None:
        paths.extend(str(Path(root)/'steam.exe') for root in steam_roots()+settings.steam_roots)
        for key in ('ProgramFiles','ProgramFiles(x86)','LOCALAPPDATA'):
            if not os.environ.get(key): continue
            base=Path(os.environ[key])
            paths.extend(str(base/relative) for relative in (
                'Epic Games/Launcher/Portal/Binaries/Win64/EpicGamesLauncher.exe',
                'Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe',
                'Ubisoft/Ubisoft Game Launcher/UbisoftConnect.exe',
                'Minecraft Launcher/MinecraftLauncher.exe'))
        from .ubisoft import WindowsUbisoftRegistry
        paths.extend(str(Path(root)/'UbisoftConnect.exe') for root in
                     WindowsUbisoftRegistry().read().get('launchers',[])+settings.ubisoft_roots)
        index=Path(os.environ.get('PROGRAMDATA',r'C:\ProgramData'))/'Riot Games/RiotClientInstalls.json'
        try:
            if index.stat().st_size<=1024*1024:
                value=json.loads(index.read_text(encoding='utf-8-sig'))
                if isinstance(value,dict): paths.extend(value.get(key,'') for key in ('rc_default','rc_live','rc_beta'))
        except (OSError,ValueError,TypeError): pass
    else:
        paths.extend(candidates)
    found={}
    for path in paths:
        try:
            if not local_executable(path): continue
        except (OSError,ValueError): continue
        basename=ntpath.basename(path).lower()
        for key,(name,names) in CLIENTS.items():
            if key not in found and basename in names: found[key]=Client(key,name,str(Path(path)))
    return sorted(found.values(),key=lambda client:client.name.casefold())

def start_client(client):
    definition=CLIENTS.get(client.id)
    if (not definition or ntpath.basename(client.target).lower() not in definition[1]
            or not local_executable(client.target)):
        raise ValueError('This launcher is no longer available. Refresh the launcher list.')
    subprocess.Popen([client.target],cwd=str(Path(client.target).parent),shell=False)

class ClientWorker:
    def __init__(self,data_dir,bridge=None):
        self.bridge=bridge or PowerShellLinks(data_dir)
        self.jobs,self.results=Queue(),Queue(); self.closed=False
        self.thread=threading.Thread(target=self._run,daemon=True,name='launcher-clients'); self.thread.start()
    def request(self,settings):
        if not self.closed: self.jobs.put(Settings(**asdict(settings)))
    def _run(self):
        while not self.closed:
            settings=self.jobs.get()
            if settings is None or self.closed: return
            try:
                warning=''
                try: inventory=self.bridge.inventory(shortcut_locations())
                except Exception: inventory=[]; warning='Some launcher shortcuts could not be read. Refresh to try again.'
                clients=find_clients(settings,inventory)
                if not self.closed: self.results.put((clients,warning))
            except Exception:
                if not self.closed: self.results.put((None,'Could not refresh launchers. Try again.'))
    def close(self):
        self.closed=True; self.jobs.put(None); self.bridge.close(); self.thread.join(timeout=4)
