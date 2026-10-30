"""Explicit, versioned, local per-game risk consent; no provider data or sync."""
from datetime import datetime,timezone
import hashlib
import json
import ntpath
import re
from .game_safety import policy

NOTICE_VERSION=1
PREFIX='overlay_risk_consent:'
MINIMIZE_PREFIX='minimize_risk_consent:'
DISPLAY_KEY='protected_game_display_consent'
DISPLAY_NOTICE_VERSION=1
DISPLAY_NOTICE='Anti-cheat may block the display or restrict your game account. Enable countdowns and notifications in all protected games at your own risk.'
MINIMIZE_NOTICE='Automatic minimization can interrupt an online match without pausing or closing the game. Inactivity, disconnection or abandoning a match may cause penalties, cooldowns or account restrictions. Fullscreen transitions may also cause compatibility problems, freezes or crashes in some games. You allow automatic minimization for this game at your own risk. The developer does not accept responsibility for resulting penalties, lost progress or other damage. This permission is separate from overlay consent and never permits automatic Escape or anti-cheat bypasses.'
NOTICE='An anti-cheat system or the game publisher may block overlays, disconnect you, or suspend or permanently ban your account. Keep Improving and RTSS are not approved by every publisher, and compatibility cannot be guaranteed. You use the overlay and game-image preview at your own risk. The developer does not accept responsibility for resulting sanctions, account loss or other damage. Consent does not disable or bypass anti-cheat protection. Automatic Escape remains disabled for protected games.'


def token(game):
    return hashlib.sha256((game.id+'\0'+ntpath.normcase(ntpath.normpath(game.root))).encode('utf-8')).hexdigest()


class Consents:
    def __init__(self,store,*,prefix=PREFIX,notice_version=None):
        self.store=store; self.prefix=prefix; self.notice_version=NOTICE_VERSION if notice_version is None else notice_version
        self.accepted=frozenset(); self.reload()

    def reload(self):
        self.display_enabled=False
        if self.prefix==PREFIX:
            row=self.store.db.execute('SELECT value FROM settings WHERE key=?',(DISPLAY_KEY,)).fetchone()
            try:
                record=json.loads(row[0]) if row else {}
                self.display_enabled=bool(isinstance(record,dict) and type(record.get('notice_version')) is int
                    and record['notice_version']==DISPLAY_NOTICE_VERSION and record.get('accepted') is True
                    and isinstance(record.get('accepted_at'),str)
                    and datetime.fromisoformat(record['accepted_at']).tzinfo is not None)
            except (ValueError,TypeError): pass
        accepted=set()
        for key,value in self.store.db.execute('SELECT key,value FROM settings WHERE key GLOB ?', (self.prefix+'*',)):
            try:
                record=json.loads(value)
                if (isinstance(record,dict) and type(record.get('notice_version')) is int
                        and record['notice_version']==self.notice_version and record.get('accepted') is True
                        and re.fullmatch('[a-f0-9]{64}',key[len(self.prefix):])
                        and isinstance(record.get('accepted_at'),str)
                        and datetime.fromisoformat(record['accepted_at']).tzinfo is not None):
                    accepted.add(key[len(self.prefix):])
            except (ValueError,TypeError): pass
        self.accepted=frozenset(accepted)

    def allows(self,game):
        return bool(game and token(game) in self.accepted)

    def set(self,game,accepted):
        if type(accepted) is not bool: raise ValueError('Consent must be on or off.')
        key=self.prefix+token(game)
        with self.store.db:
            if accepted:
                value={'notice_version':self.notice_version,'accepted':True,'accepted_at':datetime.now(timezone.utc).isoformat()}
                self.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,json.dumps(value)))
            else: self.store.db.execute('DELETE FROM settings WHERE key=?',(key,))
        self.reload()

    def reason(self,path='',game=None):
        return policy.overlay_reason(path,game,consented=self.allows(game))

    def set_display_enabled(self,enabled):
        if self.prefix!=PREFIX or type(enabled) is not bool: raise ValueError('Display consent must be on or off.')
        with self.store.db:
            if enabled:
                record={'notice_version':DISPLAY_NOTICE_VERSION,'accepted':True,'accepted_at':datetime.now(timezone.utc).isoformat()}
                self.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(DISPLAY_KEY,json.dumps(record)))
            else: self.store.db.execute('DELETE FROM settings WHERE key=?',(DISPLAY_KEY,))
        self.reload()


class MinimizeConsents(Consents):
    def __init__(self,store): super().__init__(store,prefix=MINIMIZE_PREFIX,notice_version=1)


def overlay_reason(catalog,path='',game=None):
    consent=getattr(catalog,'overlay_consents',None)
    return consent.reason(path,game) if isinstance(consent,Consents) else policy.reason(path,game)


def display_reason(catalog,path='',game=None):
    """The page switch controls every protected-game countdown and notification.

    Legacy per-game image-preview consent stays separate and is preserved.
    Unknown installations and anti-cheat helper processes remain blocked.
    """
    consent=getattr(catalog,'overlay_consents',None)
    return policy.overlay_reason(path,game,consented=bool(game and isinstance(consent,Consents) and consent.display_enabled))
