"""Authenticated loopback bridge. It accepts only domain observations, never URLs."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import re
import secrets
import threading
import time

from .focus import BROWSERS, BROWSER_IDLE, domain
from .secrets import protect, unprotect
from . import __version__
from .website_identity import is_local_site,compatible_local_policy


def compatible_policy(policy, version):
    """Keep cached pre-action workers blocking until their extension page reloads them."""
    if version == 1: return policy
    entries=[item for item in policy.get('restrictions',()) if not item.get('grant') and not item.get('grant_only')]
    if not entries: return policy
    active=policy.get('active',False); all_sites=any(item.get('all') for item in entries)
    return dict(policy,active=True,
                mode='allowlist' if all_sites else policy.get('mode','blocklist') if active else 'blocklist',
                allow=list(policy.get('allow',())) if active and not all_sites else [],
                block=list(dict.fromkeys([*(policy.get('block',()) if active else ()),
                                          *(host for item in entries for host in item.get('domains',()))])),
                remaining=max(policy.get('remaining',0) if active else 0,30))


class BrowserBridge:
    def __init__(self, store, port=47853, control=None):
        row = store.db.execute("SELECT value FROM settings WHERE key='browser_pairing'").fetchone()
        try: self.token = unprotect(row[0]) if row else ''
        except (OSError, ValueError): self.token = ''
        if not self.token:
            self.token = secrets.token_hex(32)
            with store.db:
                store.db.execute("INSERT OR REPLACE INTO settings VALUES ('browser_pairing',?)", (protect(self.token),))
        self.lock = threading.Lock()
        self.requests = []
        self.observation = {}
        self.media_observations={}
        self.last_seen = 0
        self.current_policy = {'active': False, 'tracking': True, 'mode': 'blocklist', 'allow': [], 'block': [], 'remaining': 0}
        self.server = None
        self.error = ''
        self.control = control
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass  # Never log pairing secrets or activity.

            def origin_ok(self):
                origin = self.headers.get('Origin', '')
                return not origin or bool(re.fullmatch(r'(?:chrome|moz)-extension://[a-zA-Z0-9-]+', origin))

            def reply(self, code, value):
                raw = json.dumps(value).encode('utf-8')
                self.send_response(code)
                if self.origin_ok() and self.headers.get('Origin'):
                    self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
                    self.send_header('Vary', 'Origin')
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_OPTIONS(self):
                if not self.origin_ok(): return self.reply(403, {})
                self.send_response(204)
                self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin', 'chrome-extension://invalid'))
                self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
                self.send_header('Access-Control-Allow-Private-Network', 'true')
                self.send_header('Content-Length', '0')
                self.end_headers()

            def do_GET(self):
                if self.headers.get('Host') != f'127.0.0.1:{bridge.port}' or not self.origin_ok():
                    return self.reply(403,{})
                if self.path != '/browser-update': return self.reply(404,{})
                # A neutral document keeps an existing covered tab alive while
                # Chromium unloads extension-owned pages. Tokens stay in the
                # URL fragment (never sent here); this page exposes no data.
                raw=b'<!doctype html><meta charset="utf-8"><title>Keep Improving</title><body style="background:#101719;color:#cfe5dd;font:16px sans-serif;padding:32px">Friss\xc3\xadt\xc3\xa9s / Updating\xe2\x80\xa6</body>'
                self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Cache-Control','no-store')
                self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
                self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)

            def do_POST(self):
                if self.headers.get('Host') != f'127.0.0.1:{bridge.port}' or not self.origin_ok():
                    return self.reply(403, {})
                if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + bridge.token):
                    return self.reply(401, {})
                if self.path not in ('/activity','/restriction-extension','/control','/continuity'): return self.reply(404, {})
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= (524288 if self.path in ('/control','/continuity') else 16384): raise ValueError()
                    data = json.loads(self.rfile.read(length))
                    if self.path in ('/control','/continuity'):
                        if not isinstance(data,dict): raise ValueError()
                        if bridge.control is None: return self.reply(503,{'ok':False,'error':'Desktop controls are not ready.'})
                        return self.reply(200,bridge.control({'action':'continuity.exchange','data':data} if self.path=='/continuity' else data))
                    if self.path == '/restriction-extension':
                        if not isinstance(data,dict) or set(data)!={'domain','token'}: raise ValueError()
                        domain(data['domain'])
                        if not isinstance(data['token'],str) or not re.fullmatch('[a-zA-Z0-9_-]{16,100}',data['token']): raise ValueError()
                        event=threading.Event(); answer={}
                        with bridge.lock:
                            if len(bridge.requests)>=16: return self.reply(429,{})
                            bridge.requests.append((data,answer,event))
                        event.wait(2.5)
                        return self.reply(200,answer or {'ok':False})
                    if set(data) - {'browser', 'domain', 'focused', 'private', 'idle', 'redirect_budget', 'restriction_version','choice_version','local_version','media'}: raise ValueError()
                    local_version=data.get('local_version',0)
                    if type(local_version) is not int or local_version not in (0,1):raise ValueError()
                    choice_version=data.get('choice_version',0)
                    if type(choice_version) is not int or choice_version not in (0,1): raise ValueError()
                    version=data.get('restriction_version',0)
                    if type(version) is not int or version not in (0,1): raise ValueError()
                    if data.get('browser') not in set(BROWSERS.values()): raise ValueError()
                    if type(data.get('focused')) is not bool or type(data.get('private')) is not bool: raise ValueError()
                    host = domain(data['domain']) if data.get('domain') else ''
                    idle=data.get('idle',False)
                    if type(idle) is not bool or idle and (data['browser']!='brave' or host): raise ValueError()
                    redirect=data.get('redirect_budget','')
                    if not isinstance(redirect,str) or len(redirect)>2100 or '\0' in redirect: raise ValueError()
                    if data['private']: host = ''; idle=False; redirect=''
                    media=data.get('media',[])
                    if not isinstance(media,list) or len(media)>16:raise ValueError()
                    records=[]
                    for item in media:
                        if not isinstance(item,dict) or set(item)-{'domain','redirect_budget'}:raise ValueError()
                        media_host=domain(item['domain']);media_redirect=item.get('redirect_budget','')
                        if not isinstance(media_redirect,str) or len(media_redirect)>2100 or '\0' in media_redirect:raise ValueError()
                        records.append((media_host,media_redirect))
                except (ValueError, TypeError, KeyError, AttributeError): return self.reply(400, {})
                with bridge.lock:
                    if is_local_site(host) and host not in bridge.current_policy.get('local_sites',()):host=''
                    now = time.monotonic()
                    bridge.last_seen = now
                    from .activity_identity import site_identity
                    wanted={site_identity(value) for value in bridge.current_policy.get('background_media_sites',())}
                    checked=[]
                    for media_host,media_redirect in records:
                        if not bridge.current_policy.get('tracking',True) or site_identity(media_host) not in wanted:continue
                        if is_local_site(media_host) and media_host not in bridge.current_policy.get('local_sites',()):continue
                        if media_redirect:
                            def media_destination(entry):
                                try:return domain(entry.get('redirect_url',''))
                                except ValueError:return ''
                            if not any(entry.get('key')==media_redirect and entry.get('kind')=='redirect' and media_destination(entry)==media_host for entry in bridge.current_policy.get('restrictions',())):media_redirect=''
                        checked.append((media_host,media_redirect))
                    bridge.media_observations[data['browser']]=(now,tuple(set(checked)))
                    # A background browser must not overwrite the foreground browser's observation.
                    if data['focused'] or data['browser'] == bridge.observation.get('browser'):
                        if redirect:
                            entries=bridge.current_policy.get('restrictions',())
                            def redirect_host(entry):
                                try:return domain(entry.get('redirect_url',''))
                                except ValueError:return ''
                            if not any(entry.get('key')==redirect and entry.get('kind')=='redirect'
                                       and (not host or redirect_host(entry)==host) for entry in entries):
                                redirect=''
                        bridge.observation = {'browser': data['browser'], 'domain': host, 'idle':idle,
                                              'focused': data['focused'] and not data['private'], 'at': now,
                                              'redirect_budget':redirect,'choice_version':choice_version}
                    policy = dict(bridge.current_policy)
                # The running desktop signals a completed upgrade; setup may
                # still be replacing extension files while the desktop is off.
                self.reply(200, dict(compatible_local_policy(compatible_policy(policy,version),local_version),extension_version=__version__,continuity_version=1))

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = False
            def get_request(self):
                connection, address = super().get_request()
                connection.settimeout(2)
                return connection, address
        try:
            self.server = Server(('127.0.0.1', port), Handler)
            self.port = self.server.server_port
            self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .5}, daemon=True)
            self.thread.start()
        except OSError as exc:
            self.error = str(exc)
            self.port = port

    def update(self, policy):
        with self.lock:self.current_policy=dict(policy,local_sites=[s for s in policy.get('local_sites',()) if s!=f'127.0.0.1:{self.port}'],bridge_port=self.port)

    def take_requests(self):
        with self.lock:
            requests,self.requests=self.requests,[]
            return requests

    def website(self, path):
        import ntpath
        with self.lock:
            item = self.observation
            if (item.get('focused') and time.monotonic() - item['at'] < 20
                    and BROWSERS.get(ntpath.basename(path).lower()) == item['browser']):
                return BROWSER_IDLE if item.get('idle',False) else item['domain']
        return ''

    def media(self):
        with self.lock:
            now=time.monotonic()
            return [(browser,records) for browser,(at,records) in self.media_observations.items() if now-at<4]

    def redirect_budget(self, path):
        import ntpath
        with self.lock:
            item=self.observation
            if (item.get('focused') and time.monotonic()-item['at']<20
                    and BROWSERS.get(ntpath.basename(path).lower())==item['browser']):
                return item.get('redirect_budget','')
        return ''

    def uses_site_choices(self,path):
        import ntpath
        with self.lock:
            item=self.observation
            return (item.get('choice_version')==1 and time.monotonic()-item.get('at',0)<20
                    and BROWSERS.get(ntpath.basename(path).lower())==item.get('browser'))

    @property
    def connected(self):
        with self.lock: return time.monotonic() - self.last_seen < 20

    def pairing(self):
        return json.dumps({'port': self.port, 'token': self.token}, separators=(',', ':'))

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
