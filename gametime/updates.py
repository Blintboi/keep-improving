"""Small public release checks. Installers are opened only in the user's browser."""
from dataclasses import asdict, dataclass
import json
import logging
from queue import Queue
import re
import threading
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

log = logging.getLogger(__name__)
REPOSITORY = 'https://github.com/Blintboi/windows-game-time-monitor'
DOWNLOAD_URL = REPOSITORY + '/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe'
MANIFEST_URL = 'https://raw.githubusercontent.com/Blintboi/windows-game-time-monitor/refs/heads/main/downloads/latest.json'
CHECK_INTERVAL = 86400
MAX_MANIFEST = 8192
MAX_INSTALLER = 250 * 1024 * 1024
STATE_KEY = 'public_update_state_v1'


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,5})(?:\.(?:0|[1-9][0-9]{0,5})){2}', value):
        raise ValueError('Invalid public release version.')
    return tuple(map(int, value.split('.')))


@dataclass(frozen=True)
class Release:
    version: str
    installer_url: str
    sha256: str
    size: int
    schema: int = 1

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict) or set(value) != {'schema', 'version', 'installer_url', 'sha256', 'size'}:
            raise ValueError('Invalid public release record.')
        version_tuple(value['version'])
        if (type(value['schema']) is not int or value['schema'] != 1
                or value['installer_url'] != DOWNLOAD_URL
                or not isinstance(value['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', value['sha256'])
                or type(value['size']) is not int or not 0 < value['size'] <= MAX_INSTALLER):
            raise ValueError('Invalid public release record.')
        return cls(**value)

    def newer_than(self, current):
        return version_tuple(self.version) > version_tuple(current)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_release(opener=None):
    opener = opener or build_opener(NoRedirect())
    request = Request(MANIFEST_URL, headers={'Accept': 'application/json', 'User-Agent': 'GameTimeMonitor/updates-v1'})
    try:
        with opener.open(request, timeout=8) as response:
            if response.geturl() != MANIFEST_URL:
                raise ValueError('Unexpected public release location.')
            length = response.headers.get('Content-Length')
            if length is not None and (not re.fullmatch('[0-9]{1,10}', length) or int(length) > MAX_MANIFEST):
                raise ValueError('Public release record is too large.')
            deadline = time.monotonic() + 15
            raw = bytearray()
            while True:
                chunk = response.read1(min(4096, MAX_MANIFEST + 1 - len(raw)))
                if time.monotonic() > deadline:
                    raise TimeoutError('Public release check timed out.')
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > MAX_MANIFEST:
                    raise ValueError('Public release record is too large.')
            return Release.parse(json.loads(raw.decode('utf-8')))
    except HTTPError as error:
        try:
            if error.code == 404:
                return None  # The first release manifest has not been published yet.
            raise OSError('Public release check failed.') from error
        finally:
            error.close()


class UpdateWorker:
    """No resident thread: one bounded request, returning data through a queue."""
    def __init__(self, fetch=fetch_release):
        self.fetch = fetch
        self.results = Queue()
        self.closed = threading.Event()
        self.lock = threading.Lock()
        self.busy = False

    def request(self):
        with self.lock:
            if self.busy or self.closed.is_set():
                return False
            self.busy = True
        try:
            threading.Thread(target=self._run, daemon=True, name='public-update-check').start()
        except RuntimeError:
            with self.lock: self.busy = False
            log.warning('Could not start public update check', exc_info=True)
            return False
        return True

    def _run(self):
        release, error = None, False
        try:
            release = self.fetch()
        except Exception:
            error = True
            log.warning('Public update check unavailable', exc_info=True)
        finally:
            if not self.closed.is_set():
                self.results.put((release, error))
            with self.lock:
                self.busy = False

    def close(self):
        self.closed.set()


class UpdateState:
    """Public metadata only; SQLite stays on the GUI thread."""
    def __init__(self, store):
        self.store = store
        self.attempted = 0
        self.release = None
        self.dismissed = ''
        try:
            row = store.db.execute('SELECT value FROM settings WHERE key=?', (STATE_KEY,)).fetchone()
            value = json.loads(row[0]) if row else {}
            attempted = value.get('attempted', 0)
            if type(attempted) in (int, float) and 0 <= attempted <= time.time() + 300:
                self.attempted = attempted
            if value.get('release') is not None:
                self.release = Release.parse(value['release'])
            if value.get('dismissed'):
                version_tuple(value['dismissed']); self.dismissed = value['dismissed']
        except (ValueError, TypeError, AttributeError, RecursionError):
            log.warning('Invalid cached public update information ignored')

    def save(self):
        value = {'attempted': self.attempted, 'release': asdict(self.release) if self.release else None, 'dismissed': self.dismissed}
        with self.store.db:
            self.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (STATE_KEY, json.dumps(value)))
