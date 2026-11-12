"""Per-activity local opt-in for audible background playback; no opening counts."""
from dataclasses import replace
import json
import ntpath
from .activity_identity import canonical_member,app_identity,site_identity
from .focus import BROWSERS,BROWSER_IDLE,app_key
from .wellbeing import target

KEY='background_media_tracking'


class BackgroundMedia:
    def __init__(self,app,audio=None):
        from .media_audio import AudioSampler
        self.app=app;self.audio=audio or AudioSampler();self.previous=None;self.targets=[];self.atoms=();self.browser_paths={}
        row=app.store.db.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone()
        try:
            value=json.loads(row[0]) if row else []
            if not isinstance(value,list) or len(value)>2000:raise ValueError()
            self.members=[canonical_member(target(item['kind'],item['value'])) for item in value]
            if any(item['kind'] not in ('app','site') for item in self.members):raise ValueError()
        except (ValueError,KeyError,TypeError):self.members=[]

    def enabled(self,member):
        member=canonical_member(member)
        return any(item['kind']==member['kind'] and item['value']==member['value'] for item in self.members)

    def set_enabled(self,member,enabled):
        if type(enabled) is not bool:raise ValueError('Invalid request.')
        member=canonical_member(target(member['kind'],member['value']))
        if member['kind'] not in ('app','site'):raise ValueError('Choose a valid activity.')
        updated=[item for item in self.members if item!=member]
        if enabled:updated.append(member)
        if len(updated)>2000:raise ValueError('Too many activities.')
        with self.app.store.db:self.app.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(KEY,json.dumps(updated)))
        self.members=updated;self.previous=None;self.app.update_focus_policy()

    def observations(self,sample):
        app=self.app;enabled=app.focus.settings.tracking and bool(self.members);media=[];self.targets=[]
        browser=BROWSERS.get(ntpath.basename(sample.path).lower())
        if browser:self.browser_paths[browser]=sample.path
        audible=self.audio.sample(enabled)
        audible_browsers={BROWSERS.get(ntpath.basename(path).lower()) for path,_ in audible}
        for path,identity in audible:
            if not self.enabled({'kind':'app','value':path}) or app.focus.settings.app_excluded(path):continue
            observed=replace(sample,path=path,identity=identity,interactive=True)
            atom=app.wellbeing.atom(observed)
            if atom and not atom[0]:media.append(atom);self.targets.append((observed,atom))
        bridge=getattr(app,'browser_bridge',None)
        if enabled and bridge:
            for browser,records in bridge.media():
                if browser not in audible_browsers:continue
                if browser not in self.browser_paths:self.browser_paths[browser]=app.browser_continuity.browser_path(browser)
                path=self.browser_paths[browser]
                if app.focus.settings.app_excluded(path):continue
                for host,redirect in records:
                    if self.enabled({'kind':'site','value':host}):media.append(('',app_key(path),host+('\0'+redirect if redirect else '')))
        self.atoms=tuple(sorted(set(media))) if enabled else ()
        return self.atoms

    def tick(self,sample,foreground,redirect=''):
        app=self.app;media=self.observations(sample);previous=self.previous
        tagged=foreground
        if tagged and redirect:tagged=(tagged[0],tagged[1],tagged[2]+'\0'+redirect)
        self.previous=(sample,tagged,media,app.focus.previous[1] if app.focus.previous else "")
        if not previous or not app.focus.settings.tracking:return
        prev,old,playing,prev_site=previous;seconds=sample.awake-prev.awake;wall=(sample.wall-prev.wall).total_seconds()
        if not playing or not 0<seconds<=3 or wall<=0 or abs(wall-seconds)>1.5:return
        # Settings changes/exclusion apply immediately to every outstanding observation.
        playing=tuple(atom for atom in playing if not app.focus.settings.app_excluded(atom[1]) and
                      (self.enabled({'kind':'site','value':atom[2].split('\0')[0]}) if atom[2] else self.enabled({'kind':'app','value':atom[1]})))
        if not playing:return
        if not sample.interactive or old and not app.wellbeing.atom(prev,old[2].split('\0',1)[0]):old=None
        measured=set()
        if sample.interactive and prev.interactive and prev.path and prev.identity and not app.focus.settings.app_excluded(prev.path):
            if not (prev_site==BROWSER_IDLE and ntpath.basename(prev.path).lower() in BROWSERS):
                measured.add(('app',app_identity(prev.path)))
                if prev_site and ntpath.basename(prev.path).lower() in BROWSERS:measured.add(('site',site_identity(prev_site)))
        for _,path,site in playing:
            for kind,key,name in [('app',path,ntpath.basename(path))]+([('site',site.split('\0')[0],site.split('\0')[0])] if site else []):
                identity=(kind,app_identity(key) if kind=='app' else site_identity(key))
                if identity in measured:continue
                measured.add(identity);app.focus._credit(kind,key,name,prev.wall,sample.wall,seconds,background=True)
        app.wellbeing.credit_media(prev.wall,sample.wall,seconds,old,playing)

    def close(self):self.audio.close();self.previous=None;self.targets=[];self.atoms=()
