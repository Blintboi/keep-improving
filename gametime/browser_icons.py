"""Visible browser requests reuse the desktop's bounded, cached icon pipeline."""
import time
from .qt_activity_icons import ActivityIcons
from .activity_identity import activity_key
from PySide6.QtCore import QTimer


class BrowserIcons(ActivityIcons):
    def __init__(self,app):
        super().__init__(app,app)
        self.leases={}
        self.expiry=QTimer(self); self.expiry.setSingleShot(True); self.expiry.timeout.connect(self.expire)

    def visible(self):
        return not self.closed and not self.app.closed and self.enabled and any(until>time.monotonic() for until,entries in self.leases.values())

    def eventFilter(self,watched,event):
        # Browser visibility is independent of the desktop Hub's window state.
        return False

    def request(self,client,entries):
        self.leases.pop(client,None)
        if entries: self.leases[client]=(time.monotonic()+5,entries)
        while len(self.leases)>32: self.leases.pop(next(iter(self.leases)))
        self.expire()

    def expire(self):
        now=time.monotonic()
        self.leases={key:value for key,value in self.leases.items() if value[0]>now}
        entries={activity_key(member):(member,name) for until,values in self.leases.values() for member,name in values}
        if entries:
            self.request_visible(list(entries.values())[:96])
            self.expiry.start(max(1,int(1000*(min(until for until,values in self.leases.values())-now))))
        else:
            self.pause(); self.expiry.stop()
        for key in list(self.cache):
            if len(self.cache)<=256: break
            if key not in entries: self.cache.pop(key,None); self.resolved.discard(key); self.image_keys.discard(key)

    def close(self):
        self.leases.clear(); self.expiry.stop(); super().close()
