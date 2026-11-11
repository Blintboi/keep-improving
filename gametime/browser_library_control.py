"""Explicit library operations shared with the desktop's discovery and launch code."""
from pathlib import Path
from dataclasses import asdict
import base64,hashlib,ntpath,uuid


class LibraryControl:
    def __init__(self,app):
        self.app=app; self.images={}; self.icons=None; self.icon_entries={}; self.icon_sources={}; self.notification_images={}

    def register_icons(self,entries,sources=None,reset=False):
        from .activity_identity import activity_key,canonical_member
        if reset: self.icon_entries={}; self.icon_sources={}
        for key,values in (sources or {}).items(): self.icon_sources[key]=list(values)
        for member,name in entries:
            if member['kind'] not in ('app','site'): continue
            key=activity_key(member); self.icon_entries[key]=(canonical_member(member),name)
            values=self.icon_sources.setdefault(key,[])
            if member['value'] not in values: values.append(member['value'])
        if self.icons: self.icons.set_sources(self.icon_sources)

    def encode(self,identity,pix,size=96):
        from PySide6.QtCore import QBuffer,QIODevice,Qt
        if pix is None or pix.isNull(): return None
        key=(identity,pix.cacheKey(),size); value=self.images.get(key)
        if value is None:
            buffer=QBuffer(); buffer.open(QIODevice.WriteOnly)
            pix.scaled(size,size,Qt.KeepAspectRatio,Qt.SmoothTransformation).save(buffer,'PNG')
            value='data:image/png;base64,'+base64.b64encode(bytes(buffer.data())).decode(); self.images[key]=value
            while len(self.images)>128: self.images.pop(next(iter(self.images)))
        return value

    def activity_icons(self,data):
        from .activities import activity_target
        from .activity_identity import activity_key
        import re
        ids=data.get('ids',[]); client=data.get('client','')
        if (not isinstance(ids,list) or len(ids)>24 or any(not isinstance(key,str) or len(key)>2100 for key in ids)
                or not isinstance(client,str) or not re.fullmatch('[a-zA-Z0-9-]{16,80}',client)):
            raise ValueError('Invalid request.')
        if self.icons is None:
            if not ids: return {}
            from .browser_icons import BrowserIcons
            self.icons=BrowserIcons(self.app); self.icons.set_sources(self.icon_sources)
        entries={}; result={}
        games=self.games() if any(key.startswith('game:') for key in ids) else {}
        for key in dict.fromkeys(ids):
            if key.startswith('notification:'):
                value=self.notification_images.get(key[len('notification:'):]); image=None
                if value:
                    from .qt_notification_options import notification_icon
                    image=self.encode(key,notification_icon(value,size=96).pixmap(96,96))
                result[key]=dict(image=image,pending=False); continue
            if key.startswith('game:'):
                value=self.artwork({'ids':[key[5:]]}).get(key[5:]) if key[5:] in games else None
                result[key]=value or dict(image=None,pending=False); continue
            try: identity=activity_key(activity_target(key))
            except ValueError: raise ValueError('Invalid request.') from None
            entry=self.icon_entries.get(identity)
            if entry is None:
                result[key]=dict(image=None,pending=False); continue
            entries[identity]=entry
            icon=self.icons.icon(*entry)
            result[key]=dict(image=self.encode(identity,icon.pixmap(96,96)),pending=identity not in self.icons.resolved,has_image=identity in self.icons.image_keys)
        self.icons.request(client,list(entries.values()))
        return result

    def close(self):
        if self.icons: self.icons.close()

    def games(self):
        # Use the desktop inventory: current discovery overrides persisted rows.
        games={game.id:game for game in self.app.store.games()}
        games.update(self.app.catalog.games)
        return games

    def summary(self):
        from datetime import datetime
        from .quota import current_day
        from .budget import quota_plan
        from . import budget_access
        from .activity_identity import activity_key
        app=self.app;now=datetime.now().astimezone();day=current_day(app.settings,now).isoformat()
        games=app.tracker.totals(day);used=sum(app.tracker.quota_totals(now).values());plan=quota_plan(app.settings,now)
        limited=app.settings.game_budget_enabled and budget_access.active(app.settings,'shared-games',now) and budget_access.usage_enabled(app.settings,'shared-games')
        activities={}
        for kind,key,name,seconds in app.focus.usage(day):
            identity=activity_key({'kind':kind,'value':key});activities[identity]=activities.get(identity,0)+seconds
        return dict(games=games,activities=activities,total=sum(games.values()),remaining=max(0,plan.limit_seconds-used) if limited else None,
                    ratio=min(1,used/plan.limit_seconds) if limited and plan.limit_seconds else int(bool(limited)))

    def artwork(self,data):
        ids=data.get('ids',[])
        if not isinstance(ids,list) or len(ids)>24 or any(not isinstance(k,str) for k in ids):raise ValueError('Invalid request.')
        games=self.games()
        if any(k not in games for k in ids):raise ValueError('Invalid request.')
        self.app.art.refresh_links(self.app.settings.games_root)
        result={}
        for identity in dict.fromkeys(ids):
            game=games[identity];poster,icon=self.app.art.artwork(game,self.app.catalog.rules)
            use_icon=icon is not None and not icon.isNull() and (poster is None or poster.isNull() or max(poster.width(),poster.height())<128 or not .5<=poster.width()/poster.height()<=2.5)
            pix=icon if use_icon else poster;value=self.encode(identity,pix,192)
            result[identity]=dict(image=value,cover=not use_icon,pending=self.app.art.key(game) in self.app.art.pending,
                hue=hashlib.sha256(game.name.encode()).digest()[0]*359/255)
        return result

    def activity_add(self,data):
        from .wellbeing import target
        member=target(data['kind'],data['value'])
        if member['kind'] not in ('app','site'): raise ValueError('Choose a valid activity.')
        name=ntpath.basename(member['value']) if member['kind']=='app' else member['value']
        with self.app.store.db: self.app.store.db.execute('INSERT OR IGNORE INTO activity_items VALUES (?,?,?)',(member['kind'],member['value'],name))
        self.app.refresh_activity_lists(); return True

    def game_add(self,data):
        from .model import blocked,Game
        from .notification_rules import executable
        path=executable(data['path']); name=data['name']
        if not isinstance(name,str) or not name.strip() or len(name)>120: raise ValueError('Enter a game name.')
        if not Path(path).is_file(): raise ValueError('Application file was not found.')
        if blocked(path): raise ValueError('Browsers and launcher clients cannot be assigned to a game.')
        game=Game('manual:'+uuid.uuid4().hex,name.strip(),'Kézi',str(Path(path).parent))
        self.app.store.upsert([game]);self.app.catalog.games[game.id]=game
        self.app.store.set_rule(path,game.id);self.app.store.set_launch_executable(game.id,path);self.app.refresh_rules()
        return game.id

    def rule_save(self,data):
        from .notification_rules import executable
        from .model import blocked
        path=executable(data['path']); game=data.get('game')
        if game is not None and game not in self.app.catalog.games: raise ValueError('Select a game in the list first.')
        if game is not None and blocked(path): raise ValueError('Browsers and launcher clients cannot be assigned to a game.')
        if game is not None and not Path(path).is_file(): raise ValueError('Application file was not found.')
        self.app.store.set_rule(path,game)
        if game is not None:self.app.store.set_launch_executable(game,path)
        self.app.refresh_rules();return True

    def rule_delete(self,data):
        if data['path'] not in self.app.catalog.rules: raise ValueError('Invalid request.')
        self.app.store.delete_rule(data['path']);self.app.refresh_rules();return True

    def refresh(self,data): self.app.refresh_sources();return True

    def removal(self,data):
        from .removal import plan_removal,localize_plan,execute
        game=self.app.catalog.games.get(data['id'])
        if not game: raise ValueError('Select a game in the list first.')
        plan=localize_plan(plan_removal(game),game,self.app.settings.language)
        fingerprint=hashlib.sha256(repr(plan).encode()).hexdigest()
        if data.get('confirm') is not None:
            if data['confirm']!=fingerprint: raise ValueError('The uninstall plan changed. Open it again.')
            execute(plan);return True
        return dict(title=plan.title,instructions=plan.instructions,confirm=fingerprint)

    def upload_icon(self,data):
        from PySide6.QtCore import QByteArray,QBuffer,QIODevice
        from PySide6.QtGui import QImageReader
        from PySide6.QtCore import Qt
        encoded=data.get('image')
        if not isinstance(encoded,str) or len(encoded)>450000: raise ValueError('Choose an image smaller than 330 KB.')
        try: raw=base64.b64decode(encoded,validate=True)
        except ValueError: raise ValueError('Choose a valid PNG, JPEG or WebP image.') from None
        source=QBuffer();source.setData(QByteArray(raw));source.open(QIODevice.ReadOnly)
        reader=QImageReader(source);size=reader.size()
        if bytes(reader.format()).lower() not in (b'png',b'jpeg',b'jpg',b'webp') or not size.isValid() or size.width()*size.height()>16000000:
            raise ValueError('Choose a valid PNG, JPEG or WebP image.')
        reader.setScaledSize(size.scaled(256,256,Qt.KeepAspectRatio));picture=reader.read()
        if picture.isNull(): raise ValueError('Choose a valid PNG, JPEG or WebP image.')
        destination=QBuffer();destination.open(QIODevice.WriteOnly);picture.save(destination,'PNG');value=bytes(destination.data())
        folder=self.app.data_dir/'notification-icons';folder.mkdir(exist_ok=True)
        path=folder/(hashlib.sha256(value).hexdigest()+'.png')
        if not path.exists(): path.write_bytes(value)
        return dict(path=str(path),image='data:image/png;base64,'+base64.b64encode(value).decode())

    def update(self,data):
        if data.get('action')=='check':self.app.updates.request(manual=True)
        elif data.get('action')=='download':self.app.updates.download()
        elif data.get('action')!='status':raise ValueError('Invalid request.')
        release=self.app.updates.available
        updates=self.app.updates;message=str(self.app.t(updates.message))
        if updates.downloading and updates.download_worker:
            used,total=updates.download_worker.progress
            if total:message=str(self.app.t('Downloading update: {percent}%',percent=used*100//total))
        return dict(pending=updates.pending or updates.downloading,version=release.version if release else '',message=message)

    def display_consent(self,data):
        enabled=data.get('enabled')
        if type(enabled) is not bool or enabled and data.get('accepted') is not True: raise ValueError('Confirm the display notice.')
        self.app.overlay_consents.set_display_enabled(enabled);self.app.apply_display_settings();return True
