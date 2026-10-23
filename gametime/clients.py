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
from .launcher_defs import CLIENTS,CLIENT_PATHS,client_id

@dataclass(frozen=True)
class Client:
    id:str
    name:str
    target:str
    kind:str='executable'
    icon:str=''

def decode_client_cache(value):
    """Read remembered launchers without searching the disk or registry."""
    if not isinstance(value,dict) or value.get('version')!=1: raise ValueError('Invalid launcher cache')
    rows=value.get('clients')
    if not isinstance(rows,list) or len(rows)>len(CLIENTS): raise ValueError('Invalid launcher cache')
    clients=[]; seen=set()
    for row in rows:
        client=Client(**row)
        if (not all(isinstance(field,str) for field in asdict(client).values())
                or client.id not in CLIENTS or client.id in seen): raise ValueError('Invalid launcher cache')
        if client.kind=='app':
            from .platforms import AUMID
            valid=client.id=='xbox' and AUMID.fullmatch(client.target)
        else:
            valid=(client.kind=='executable' and executable_path(client.target)
                   and ntpath.basename(client.target).lower() in CLIENTS[client.id][1])
        if not valid or (client.icon and not executable_path(client.icon)): raise ValueError('Invalid launcher cache')
        clients.append(Client(client.id,CLIENTS[client.id][0],client.target,client.kind,client.icon)); seen.add(client.id)
    return sorted(clients,key=lambda client:client.name.casefold())

def executable_path(value):
    return (isinstance(value,str) and not value.startswith(('\\\\','//')) and '\x00' not in value
            and Path(value).is_absolute() and Path(value).suffix.lower()=='.exe')

def local_executable(value):
    return executable_path(value) and Path(value).is_file()

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
            paths.extend(str(base/relative) for relative in CLIENT_PATHS)
        from .platforms import WindowsInstallRegistry,xbox_client
        snapshot=WindowsInstallRegistry().read()
        paths.extend(snapshot.get('clients',[]))
        xbox=xbox_client(snapshot.get('packages',[]))
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
        key=client_id(path)
        if key and key not in found: found[key]=Client(key,CLIENTS[key][0],str(Path(path)))
    if candidates is None and xbox:
        package=next(row for row in snapshot['packages'] if xbox.startswith(row['family']+'!'))
        icon=Path(package['root'])/'XboxPcApp.exe'
        found['xbox']=Client('xbox','Xbox',xbox,'app',str(icon) if icon.is_file() else '')
    return sorted(found.values(),key=lambda client:client.name.casefold())

def start_client(client):
    if client.kind=='app':
        from .platforms import AUMID,WindowsInstallRegistry,xbox_client
        if client.id!='xbox' or not AUMID.fullmatch(client.target) or client.target!=xbox_client(WindowsInstallRegistry().read().get('packages',[])):
            raise ValueError('This launcher is no longer available. Refresh the launcher list.')
        os.startfile('shell:AppsFolder\\'+client.target)
        return
    definition=CLIENTS.get(client.id)
    if (client.kind!='executable' or not definition or client_id(client.target)!=client.id
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
