"""Explicit library operations shared with the desktop's discovery and launch code."""
from pathlib import Path
from dataclasses import asdict
import base64,hashlib,ntpath,uuid


class LibraryControl:
    def __init__(self,app): self.app=app

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
        return dict(pending=self.app.updates.pending,version=release.version if release else '',message=str(self.app.t(self.app.updates.message)))

    def display_consent(self,data):
        enabled=data.get('enabled')
        if type(enabled) is not bool or enabled and data.get('accepted') is not True: raise ValueError('Confirm the display notice.')
        self.app.overlay_consents.set_display_enabled(enabled);self.app.apply_display_settings();return True
