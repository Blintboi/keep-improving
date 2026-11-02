"""Local executable choices, collected only when the user opens the picker."""
import ntpath
import os
from pathlib import Path
from .focus import app_key
from .notification_rules import executable,items as notification_items


def registered_applications():
    """Windows App Paths provides launchable programs without a disk scan."""
    import winreg
    root=r'Software\Microsoft\Windows\CurrentVersion\App Paths'
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive,root,0,winreg.KEY_READ|view) as key:
                    for index in range(min(1024,winreg.QueryInfoKey(key)[0])):
                        try:
                            name=winreg.EnumKey(key,index)
                            with winreg.OpenKey(key,name) as entry: value,kind=winreg.QueryValueEx(entry,'')
                            if kind not in (winreg.REG_SZ,winreg.REG_EXPAND_SZ) or not isinstance(value,str): continue
                            if kind==winreg.REG_EXPAND_SZ: value=os.path.expandvars(value)
                            yield value.strip().strip('"'),ntpath.splitext(name)[0]
                        except OSError: continue
            except OSError: continue


def choices(app,current=''):
    candidates=[]
    for kind,path,name in app.store.db.execute("SELECT kind,key,name FROM activity_items WHERE kind='app' ORDER BY key"):
        candidates.append((path,ntpath.splitext(ntpath.basename(name or path))[0]))
    for path,gid in app.catalog.rules.items():
        game=app.catalog.games.get(gid)
        if game: candidates.append((path,game.name))
    for client in getattr(app,'clients',[]):
        if getattr(client,'kind',None)=='executable': candidates.append((client.target,client.name))
    for rule in notification_items(app.settings):
        if rule['action']['kind']=='app': candidates.append((rule['action']['path'],''))
    candidates.extend((path,'') for path in [current,*app.focus.settings.block_apps,*app.focus.settings.excluded_apps])
    candidates.extend(registered_applications())
    found={}; checked=set()
    for path,name in candidates:
        try:
            executable(path); key=app_key(path)
            if key in checked: continue
            checked.add(key)
            if not Path(path).is_file(): continue
        except (ValueError,OSError): continue
        found[key]=(path,name or ntpath.splitext(ntpath.basename(path))[0])
    return sorted(found.values(),key=lambda item:(item[1].casefold(),app_key(item[0])))
