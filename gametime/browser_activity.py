"""Authenticated loopback bridge. It accepts only domain observations, never URLs."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import re
import secrets
import threading
import time

from .focus import BROWSERS, domain
from .secrets import protect, unprotect


class BrowserBridge:
    def __init__(self, store, port=47853):
        row = store.db.execute("SELECT value FROM settings WHERE key='browser_pairing'").fetchone()
        try: self.token = unprotect(row[0]) if row else ''
        except (OSError, ValueError): self.token = ''
        if not self.token:
            self.token = secrets.token_hex(32)
            with store.db:
                store.db.execute("INSERT OR REPLACE INTO settings VALUES ('browser_pairing',?)", (protect(self.token),))
        self.lock = threading.Lock()
        self.observation = {}
        self.last_seen = 0
        self.current_policy = {'active': False, 'tracking': True, 'mode': 'blocklist', 'allow': [], 'block': [], 'remaining': 0}
        self.server = None
        self.error = ''
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

            def do_POST(self):
                if self.headers.get('Host') != f'127.0.0.1:{bridge.port}' or not self.origin_ok():
                    return self.reply(403, {})
                if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + bridge.token):
                    return self.reply(401, {})
                if self.path != '/activity': return self.reply(404, {})
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 2048: raise ValueError()
                    data = json.loads(self.rfile.read(length))
                    if set(data) - {'browser', 'domain', 'focused', 'private'}: raise ValueError()
                    if data.get('browser') not in set(BROWSERS.values()): raise ValueError()
                    if type(data.get('focused')) is not bool or type(data.get('private')) is not bool: raise ValueError()
                    host = domain(data['domain']) if data.get('domain') else ''
                    if data['private']: host = ''
                except (ValueError, TypeError, KeyError, AttributeError): return self.reply(400, {})
                with bridge.lock:
                    now = time.monotonic()
                    bridge.last_seen = now
                    # A background browser must not overwrite the foreground browser's observation.
                    if data['focused'] or data['browser'] == bridge.observation.get('browser'):
                        bridge.observation = {'browser': data['browser'], 'domain': host,
                                              'focused': data['focused'] and not data['private'], 'at': now}
                    policy = dict(bridge.current_policy)
                self.reply(200, policy)

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
        with self.lock: self.current_policy = policy

    def website(self, path):
        import ntpath
        with self.lock:
            item = self.observation
            if (item.get('focused') and time.monotonic() - item['at'] < 20
                    and BROWSERS.get(ntpath.basename(path).lower()) == item['browser']):
                return item['domain']
        return ''

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
