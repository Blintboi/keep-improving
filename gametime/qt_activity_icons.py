"""Lazy native application icons and bounded, cached website favicons."""
import hashlib
from html.parser import HTMLParser
import json
import ntpath
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import urljoin,urlsplit
from PySide6.QtCore import QObject,Signal,QTimer,Qt,QFileInfo,QUrl,QByteArray,QBuffer,QIODevice,QSaveFile,QEvent,QSize
from PySide6.QtGui import QIcon,QPixmap,QPainter,QColor,QFont,QImageReader,QImage
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFileIconProvider
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest,QNetworkReply
from .activities import activity_key
from .focus import domain,matches
from .activity_identity import site_identity
from .qt_widgets import normalize_icon

MAX_ICON=256*1024
MAX_PAGE=128*1024
SUCCESS_TTL=30*86400
FAILURE_TTL=86400
CACHE_VERSION=2


def icon_url(value):
    try:
        url=urlsplit(value)
        if (len(value)>2048 or url.scheme!='https' or url.username or url.password or url.port not in (None,443)
                or not url.hostname or domain(url.hostname)!=url.hostname.lower()): return ''
        return value
    except (ValueError,TypeError): return ''


class IconLinks(HTMLParser):
    def __init__(self,base): super().__init__(); self.base=base; self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()!='link' or len(self.links)>=8: return
        values=dict(attrs); rel=(values.get('rel') or '').lower().split()
        if not any(value in ('icon','apple-touch-icon','apple-touch-icon-precomposed') for value in rel): return
        url=icon_url(urljoin(self.base,values.get('href') or ''))
        if url and url not in self.links: self.links.append(url)


def decode_icon(data):
    if not data or len(data)>MAX_ICON: return None
    if b'<svg' in data[:4096].lower():
        # Only self-contained, static SVGs: no external files, entities or animations.
        lower=data.lower()
        if any(token in lower for token in (b'<!doctype',b'<!entity',b'<script',b'<foreignobject',b'<animate',b'<set',b'<image',b'@import')): return None
        if re.search(rb'(?:href\s*=\s*[\x22\x27]\s*(?!#)|url\(\s*[\x22\x27]?(?!#))',lower): return None
        renderer=QSvgRenderer(QByteArray(data))
        if not renderer.isValid() or renderer.animated(): return None
        size=renderer.defaultSize()
        if not size.isValid() or min(size.width(),size.height())<1: return None
        image=QImage(size.scaled(QSize(96,96),Qt.KeepAspectRatio),QImage.Format_ARGB32_Premultiplied); image.fill(Qt.transparent)
        painter=QPainter(image); renderer.render(painter); painter.end(); return image
    buffer=QBuffer(); buffer.setData(QByteArray(data)); buffer.open(QIODevice.ReadOnly)
    reader=QImageReader(buffer)
    if bytes(reader.format()).lower() not in (b'ico',b'png',b'jpeg',b'webp',b'gif'): return None
    if reader.imageCount()>1 and bytes(reader.format()).lower()==b'ico':
        best=0; area=0
        for index in range(min(reader.imageCount(),32)):
            if reader.jumpToImage(index):
                size=reader.size(); pixels=size.width()*size.height()
                if 0<pixels<=512*512 and pixels>area: best=index; area=pixels
        reader.jumpToImage(best)
    size=reader.size()
    if not size.isValid() or min(size.width(),size.height())<8 or size.width()*size.height()>4_000_000: return None
    if max(size.width(),size.height())>96: reader.setScaledSize(size.scaled(QSize(96,96),Qt.KeepAspectRatio))
    image=reader.read()
    return None if image.isNull() else image


def package_icon(executable):
    """Read the packaged app's logo when its executable has no useful shell icon."""
    path=Path(executable)
    for root in list(path.parents)[:6]:
        manifest=root/'AppxManifest.xml'
        try:
            if not manifest.is_file() or manifest.stat().st_size>512*1024: continue
            raw=manifest.read_bytes()
            if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper(): return None
            tree=ET.fromstring(raw); relative=str(path.relative_to(root)).replace('\\','/').casefold()
            for application in tree.iter():
                if application.tag.rsplit('}',1)[-1]!='Application': continue
                if application.get('Executable','').replace('\\','/').casefold()!=relative: continue
                for visual in application:
                    for key in ('Square44x44Logo','Square150x150Logo','Logo'):
                        value=visual.get(key)
                        if not value: continue
                        logo=root/Path(value.replace('\\','/'))
                        if not logo.resolve().is_relative_to(root.resolve()): continue
                        candidates=[logo]
                        if logo.parent.is_dir():
                            candidates+=sorted(logo.parent.glob(logo.stem+'.targetsize-*.png'),key=lambda p:('unplated' not in p.name,len(p.name),p.name))[:20]
                            candidates+=sorted(logo.parent.glob(logo.stem+'.scale-*.png'))[:8]
                        for candidate in candidates:
                            if candidate.is_file() and candidate.stat().st_size<=MAX_ICON:
                                if (image:=decode_icon(candidate.read_bytes())) is not None: return image
            return None
        except (OSError,ValueError,ET.ParseError): return None
    return None


def logo_background(image):
    small=image.scaled(24,24,Qt.KeepAspectRatio,Qt.SmoothTransformation)
    pixels=[small.pixelColor(x,y) for y in range(small.height()) for x in range(small.width())]
    pixels=[color for color in pixels if color.alpha()>128]
    bright=sum(min(color.red(),color.green(),color.blue())>210 for color in pixels)
    return QColor('#243c3b' if pixels and bright/len(pixels)>.8 else '#edf3f0')


def tile_icon(member,name,image=None):
    pix=QPixmap(96,96); pix.fill(Qt.transparent); painter=QPainter(pix); painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    seed=hashlib.sha256(activity_key(member).encode()).digest()
    painter.setBrush(logo_background(image) if image is not None else QColor.fromHsv(seed[0]*359//255,110,95))
    painter.drawRoundedRect(1,1,94,94,18,18)
    if image is not None:
        source=normalize_icon(QPixmap.fromImage(image)); source=source.scaled(76,76,Qt.KeepAspectRatio,Qt.SmoothTransformation)
        painter.drawPixmap((96-source.width())//2,(96-source.height())//2,source)
    else:
        title=ntpath.basename(member['value']) if member['kind']=='app' else member['value'].removeprefix('www.')
        painter.setPen(QColor('#eaf5f1')); painter.setFont(QFont('Segoe UI',36,QFont.DemiBold))
        painter.drawText(pix.rect(),Qt.AlignCenter,(title or name or '?')[0].upper())
    painter.end(); icon=QIcon()
    for mode in (QIcon.Normal,QIcon.Active,QIcon.Selected): icon.addPixmap(pix,mode)
    return icon


class ActivityIcons(QObject):
    changed=Signal(str)

    def __init__(self,app,owner):
        super().__init__(owner); self.app=app; self.owner=owner
        self.directory=Path(app.data_dir)/'cache'/'activity-icons'
        self.cache={}; self.resolved=set(); self.wanted={}; self.jobs={}; self.enabled=False; self.closed=False
        self.provider=QFileIconProvider(); self.network=None
        self.writes=0; self.sources={}
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.pump)
        app.installEventFilter(self)

    def visible(self): return not self.closed and self.enabled and self.owner.isVisible() and not self.app.isMinimized()

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Hide or event.type()==QEvent.WindowStateChange and self.app.isMinimized(): self.pause()
        elif event.type() in (QEvent.Show,QEvent.WindowStateChange): self.owner.schedule_icons()
        return False

    def cache_paths(self,member):
        digest=hashlib.sha256(activity_key(member).encode()).hexdigest()
        return self.directory/(digest+'.png'),self.directory/(digest+'.json')

    def set_sources(self,sources):
        updated={key:tuple(values) for key,values in sources.items()}
        for key,values in updated.items():
            if key.startswith('app:') and values!=self.sources.get(key): self.resolved.discard(key)
        self.sources=updated

    def source_hash(self,key): return hashlib.sha256('\n'.join(self.sources.get(key,())).encode()).hexdigest()

    def icon(self,member,name):
        key=activity_key(member)
        if key not in self.cache:
            self.cache[key]=tile_icon(member,name)
            if member['kind'] in ('site','app'):
                png,meta=self.cache_paths(member)
                try:
                    if meta.stat().st_size>256: raise ValueError()
                    record=json.loads(meta.read_text(encoding='utf-8'))
                    fresh=record.get('version')==CACHE_VERSION and 0<=time.time()-record['checked']<(SUCCESS_TTL if record['success'] else FAILURE_TTL)
                    if member['kind']=='app': fresh=fresh and record.get('sources')==self.source_hash(key)
                    if png.is_file() and png.stat().st_size<=MAX_ICON:
                        image=decode_icon(png.read_bytes())
                        if image is not None: self.cache[key]=tile_icon(member,name,image)
                        else: fresh=False
                    elif record['success']: fresh=False
                    if fresh: self.resolved.add(key)
                except (OSError,ValueError,TypeError,KeyError): pass
        return self.cache[key]

    def request_visible(self,entries):
        self.enabled=True; self.wanted={activity_key(member):(member,name) for member,name in entries}
        for key,job in list(self.jobs.items()):
            if key not in self.wanted: self.cancel(key,job)
        if self.visible(): self.timer.start(0)

    def pump(self):
        if not self.visible(): self.pause(); return
        for key,(member,name) in self.wanted.items():
            self.icon(member,name)
            if key in self.resolved or key in self.jobs: continue
            if member['kind']=='app':
                # One application per event-loop turn. Reuse a surviving installation.
                image=None
                paths=self.sources.get(key,())+(member['value'],)
                installer=re.sub(r'[- _]+(?:setup|installer)\.exe$','.exe',ntpath.basename(member['value']),flags=re.I)
                if installer!=ntpath.basename(member['value']): paths+=self.sources.get('app:'+installer.casefold(),())
                for path in sorted(set(paths),key=lambda p:(ntpath.basename(p).casefold()!=member['value'],
                                                           '\\temp\\' in p.casefold() or '\\build\\' in p.casefold(),p.casefold())):
                    if path.startswith(('\\\\','//')) or not ntpath.isabs(path) or not Path(path).is_file(): continue
                    image=package_icon(path)
                    if image is None:
                        pix=self.provider.icon(QFileInfo(path)).pixmap(96,96)
                        if not pix.isNull(): image=pix.toImage()
                    if image is not None: break
                if image is not None: self.cache[key]=tile_icon(member,name,image)
                self.finish(key,dict(member=member,cancelled=False),image); return
            if len(self.jobs)>=2: return
            hosts=[host for host in self.sources.get(key,()) if site_identity(host)==member['value'] and host!=member['value'] and icon_url('https://'+host+'/')]
            parents=[other[5:] for other in self.sources if other.startswith('site:') and other!=key and matches(member['value'],other[5:])]
            hosts+=sorted(parents,key=len,reverse=True)[:1]
            job=dict(member=member,name=name,seen=set(),alternatives=[],page=False,cancelled=False,host=member['value'],hosts=list(dict.fromkeys(hosts))[:2])
            self.jobs[key]=job; self.fetch(key,job,'https://'+member['value']+'/favicon.ico')

    def fetch(self,key,job,url,page=False):
        if not self.visible() or not icon_url(url): self.finish(key,job); return
        if self.network is None: self.network=QNetworkAccessManager(self)
        request=QNetworkRequest(QUrl(url)); request.setTransferTimeout(4000); request.setMaximumRedirectsAllowed(3)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        for attribute in (QNetworkRequest.Attribute.CookieLoadControlAttribute,QNetworkRequest.Attribute.CookieSaveControlAttribute,
                          QNetworkRequest.Attribute.AuthenticationReuseAttribute):
            request.setAttribute(attribute,QNetworkRequest.LoadControl.Manual)
        request.setRawHeader(b'User-Agent',b'KeepImproving/ActivityIcons')
        request.setRawHeader(b'Accept',b'text/html' if page else b'image/*')
        job.update(reply=self.network.get(request),data=bytearray(),limit=MAX_PAGE if page else MAX_ICON,is_page=page)
        job['seen'].add(url); reply=job['reply']
        reply.setReadBufferSize(MAX_ICON+1)
        deadline=QTimer(reply); deadline.setSingleShot(True); deadline.timeout.connect(reply.abort); deadline.start(6000)
        reply.readyRead.connect(lambda:self.read(job))
        reply.finished.connect(lambda:self.received(key,job,reply))

    def read(self,job):
        data=bytes(job['reply'].readAll()); remaining=job['limit']+1-len(job['data'])
        job['data'].extend(data[:max(0,remaining)])
        if len(job['data'])>job['limit']: job['reply'].abort()

    def received(self,key,job,reply):
        if job['cancelled'] or self.closed: reply.deleteLater(); return
        self.read(job); raw=bytes(job['data']); ok=reply.error()==QNetworkReply.NetworkError.NoError
        url=reply.url().toString(); reply.deleteLater(); job.pop('reply',None)
        if not self.visible(): self.jobs.pop(key,None); return
        if job['is_page']:
            parser=IconLinks(url)
            try: parser.feed(raw[:MAX_PAGE].decode('utf-8',errors='replace'))
            except (ValueError,AssertionError): pass
            job['alternatives']=[url for url in parser.links if url not in job['seen']][:3]
        elif ok and (image:=decode_icon(raw)) is not None:
            self.cache[key]=tile_icon(job['member'],job['name'],image); self.finish(key,job,image); return
        if job['alternatives']:
            self.fetch(key,job,job['alternatives'].pop(0)); return
        if not job['page']:
            job['page']=True; self.fetch(key,job,'https://'+job['host']+'/',page=True); return
        if job['hosts']:
            job['host']=job['hosts'].pop(0); job['page']=False
            self.fetch(key,job,'https://'+job['host']+'/favicon.ico'); return
        self.finish(key,job)

    def finish(self,key,job,image=None):
        self.jobs.pop(key,None)
        if job['cancelled'] or not self.visible(): return
        self.resolved.add(key)
        png,meta=self.cache_paths(job['member'])
        try:
            self.directory.mkdir(parents=True,exist_ok=True)
            if image is not None:
                output=QSaveFile(str(png))
                if output.open(QIODevice.WriteOnly):
                    if image.save(output,'PNG'): output.commit()
                    else: output.cancelWriting()
            output=QSaveFile(str(meta))
            if output.open(QIODevice.WriteOnly):
                output.write(json.dumps(dict(version=CACHE_VERSION,checked=time.time(),success=image is not None,
                                             sources=self.source_hash(key) if job['member']['kind']=='app' else '')).encode()); output.commit()
        except OSError: pass
        self.writes+=1
        if self.writes==1 or self.writes%64==0: self.trim_cache()
        self.changed.emit(key); self.timer.start(0)

    def trim_cache(self):
        try:
            files=[path for path in self.directory.glob('*.json') if re.fullmatch('[0-9a-f]{64}',path.stem)]
            if len(files)<=512: return
            for meta in sorted(files,key=lambda path:path.stat().st_mtime)[:-512]:
                meta.with_suffix('.png').unlink(missing_ok=True); meta.unlink(missing_ok=True)
        except OSError: pass

    def cancel(self,key,job):
        job['cancelled']=True; self.jobs.pop(key,None)
        if reply:=job.get('reply'): reply.abort()

    def pause(self):
        self.enabled=False; self.timer.stop()
        for key,job in list(self.jobs.items()): self.cancel(key,job)

    def close(self):
        self.closed=True; self.pause(); self.app.removeEventFilter(self)
