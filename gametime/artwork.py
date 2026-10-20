"""Bounded read-only asset discovery; decoding uses QImage on a worker, never widgets."""
from dataclasses import dataclass
import os
from pathlib import Path
from queue import Queue
import re
import threading
import time
import zipfile
from .discovery import reparse
from .model import helper,norm,within

EXTENSIONS={'.png','.jpg','.jpeg','.webp','.bmp','.ico'}
SKIP={'saves','save','screenshots','logs','backups','mods','workshop','engine','redist','_redist',
      '_commonredist','node_modules','licenses','crashes','shadercache','monobleedingedge','localization'}
GOOD=('splash','artwork','images','icons','assets','resources','content','graphics')
MAX_BYTES=20*1024*1024

@dataclass(frozen=True)
class Asset:
    path:str
    score:int
    icon:bool=False
    member:str=''

def score_name(path,game):
    stem=path.stem.lower(); flat=re.sub('[^a-z0-9]','',stem)
    name=re.sub('[^a-z0-9]','',game.name.lower())
    if any(word in stem for word in ('unity','unreal','placeholder','anticheat','eosbootstrap','nvidia','generic')): return 0
    if any(word in stem for word in ('cover','header','library_hero','600x900','poster','banner','splash')): return 110
    if stem in ('screenselector','title','logo','minecraft','pack') or any(word in stem for word in ('game_logo','gamelogo','storelogo','wide310','square150','largeapp','capsule')): return 90
    if name and len(name)>=4 and (name in flat or flat==name): return 85
    if path.suffix.lower()=='.ico' or stem in ('icon','appicon','gameicon','applicationicon'): return 60
    return 0

def candidates(game,roots,rules,stopped=lambda:False):
    """Never scan a drive, follow reparse points, read accounts/saves or unpack content."""
    assets=[]; executables=[]; base=Path(game.root)
    if not base.is_absolute() or base.parent==base or reparse(base): return assets,executables
    for path,gid in rules.items():
        if gid==game.id and Path(path).is_file() and Path(path).suffix.lower()=='.exe' and not helper(path): executables.append(path)
    preferred=set(executables)
    appid=game.id.partition(':')[2] if game.source=='Steam' else ''
    if not appid:
        try:
            marker=base/'steam_appid.txt'
            if marker.stat().st_size<=32: appid=marker.read_text().strip()
        except (OSError,ValueError): pass
    if re.fullmatch('[0-9]{1,12}',appid or ''):
        for root in roots:
            cache=Path(root)/'appcache/librarycache'
            for suffix in ('_header.jpg','_library_hero.jpg','_library_600x900.jpg','_library_600x900_2x.jpg','_header.png'):
                assets.append(Asset(str(cache/(appid+suffix)),200))
            nested=cache/appid
            if not reparse(nested):
                try:
                    for path in list(nested.iterdir())[:160]:
                        if path.suffix.lower() in EXTENSIONS:
                            assets.append(Asset(str(path),190 if score_name(path,game) else 170))
                except OSError: pass
    # Breadth first with artwork directories first. Hard bounds also cover very
    # large/odd installations; personal Minecraft/user-content folders are skipped.
    pending=[(base,0)]; entries=0; folders=0; deadline=time.monotonic()+.75
    while pending and entries<6000 and folders<80 and time.monotonic()<deadline and not stopped():
        folder,depth=pending.pop(0); folders+=1
        try:
            with os.scandir(folder) as scan:
                children=[]
                for entry in scan:
                    entries+=1
                    if entries>6000: break
                    children.append(entry)
                children.sort(key=lambda entry:(not any(word in entry.name.lower() for word in GOOD),entry.name.casefold()))
            for entry in children:
                if time.monotonic()>=deadline or stopped(): break
                path=Path(entry.path)
                if entry.is_symlink() or reparse(path): continue
                if entry.is_dir(follow_symlinks=False):
                    if depth<4 and path.name.lower() not in SKIP and not path.name.startswith('.'):
                        pending.append((path,depth+1))
                elif entry.is_file(follow_symlinks=False):
                    if path.suffix.lower() in EXTENSIONS:
                        score=score_name(path,game)
                        if score and 0<entry.stat().st_size<=MAX_BYTES:
                            assets.append(Asset(str(path),score-depth,path.suffix.lower()=='.ico' or score==60))
                    elif path.suffix.lower()=='.exe' and not helper(path) and 'bootstrap' not in path.stem.lower() and len(executables)<12:
                        executables.append(str(path))
        except (OSError,ValueError): continue
    if game.source=='Minecraft':
        try:
            versions=base/'versions'
            folders=[path for path in versions.iterdir() if path.is_dir() and not reparse(path)][:64]
            jars=[path/(path.name+'.jar') for path in folders]
            jars=sorted((p for p in jars if p.is_file() and not reparse(p)),key=lambda p:p.stat().st_mtime,reverse=True)[:4]
            for jar in jars:
                if jar.stat().st_size<128*1024*1024:
                    assets.append(Asset(str(jar),100,True,'pack.png'))
                    assets.append(Asset(str(jar),95,False,'assets/minecraft/textures/gui/title/minecraft.png'))
        except (OSError,ValueError): pass
    assets=sorted(assets,key=lambda item:(-item.score,item.path.casefold()))
    seen=set(); unique=[]
    for item in assets:
        key=(norm(item.path),item.member)
        if key not in seen: unique.append(item); seen.add(key)
    title=re.sub('[^a-z0-9]','',game.name.lower())
    executables=sorted(dict.fromkeys(executables),key=lambda p:(p not in preferred,
                       title not in re.sub('[^a-z0-9]','',Path(p).stem.lower()),len(Path(p).parts),p.casefold()))
    return unique[:48],executables

def decode(asset):
    from PySide6.QtCore import QByteArray,QBuffer,QIODevice,QSize,Qt
    from PySide6.QtGui import QImageReader
    path=Path(asset.path)
    try:
        if reparse(path) or not path.is_file(): return None
        buffer=None
        if asset.member:
            if path.stat().st_size>128*1024*1024: return None
            with path.open('rb') as source:
                source.seek(max(0,path.stat().st_size-65557)); tail=source.read(65557)
            end=tail.rfind(b'PK\x05\x06')
            if end<0 or len(tail)-end<22: return None
            # Reject ZIP64/huge central directories before ZipFile allocates
            # directory entries. Normal Minecraft version JARs fit these bounds.
            if (int.from_bytes(tail[end+10:end+12],'little')>50000 or
                    int.from_bytes(tail[end+12:end+16],'little')>8*1024*1024): return None
            with zipfile.ZipFile(path) as archive:
                info=archive.getinfo(asset.member)
                if not 0<info.file_size<=8*1024*1024 or info.flag_bits&1: return None
                data=archive.read(info)
            buffer=QBuffer(); buffer.setData(QByteArray(data)); buffer.open(QIODevice.ReadOnly)
            reader=QImageReader(buffer)
        else:
            if not 0<path.stat().st_size<=MAX_BYTES: return None
            reader=QImageReader(str(path))
        if asset.icon and reader.imageCount()>1:
            best=0; area=0
            for index in range(min(reader.imageCount(),128)):
                if reader.jumpToImage(index):
                    current=reader.size(); pixels=current.width()*current.height()
                    if pixels>area and max(current.width(),current.height())<=2048: best=index; area=pixels
            reader.jumpToImage(best)
        size=reader.size()
        if not size.isValid() or min(size.width(),size.height())<24 or size.width()*size.height()>32_000_000: return None
        reader.setAutoTransform(True)
        if size.width()>640 or size.height()>420: reader.setScaledSize(size.scaled(QSize(640,420),Qt.KeepAspectRatio))
        image=reader.read()
        if image.isNull(): return None
        image.setDevicePixelRatio(1); return image
    except (OSError,ValueError,KeyError,zipfile.BadZipFile,RuntimeError): return None

class ArtworkWorker:
    def __init__(self):
        self.jobs,self.results=Queue(),Queue(); self.stopped=threading.Event()
        self.generation=0
        self.thread=threading.Thread(target=self._run,daemon=True,name='local-artwork'); self.thread.start()
    def request(self,token,key,game,roots,rules):
        if not self.stopped.is_set(): self.jobs.put((self.generation,token,key,game,list(roots),dict(rules)))
    def _run(self):
        from PySide6.QtGui import QImageReader
        QImageReader.setAllocationLimit(64)
        while not self.stopped.is_set():
            job=self.jobs.get()
            if job is None or self.stopped.is_set(): return
            generation,token,key,game,roots,rules=job
            if generation!=self.generation: continue
            poster=icon=None; origin=''; icon_origin=''; executables=[]
            try:
                found,executables=candidates(game,roots,rules,self.stopped.is_set)
                for asset in found:
                    if self.stopped.is_set() or generation!=self.generation: break
                    if (asset.icon and icon is not None) or (not asset.icon and poster is not None): continue
                    image=decode(asset)
                    if image is not None:
                        if asset.icon: icon=image; icon_origin=asset.path
                        else: poster=image; origin=asset.path+('!'+asset.member if asset.member else '')
                    if poster is not None and icon is not None: break
            except Exception:
                pass  # Optional artwork never stops tracking/discovery.
            if not self.stopped.is_set() and generation==self.generation:
                self.results.put((token,key,poster,icon,executables,origin,icon_origin))
    def close(self):
        self.stopped.set(); self.jobs.put(None); self.thread.join(timeout=2)
