"""User-initiated verified downloads and an external installer handoff.

The running application remains available until the complete installer passes
its manifest size/hash checks and a separate setup process has been launched.
"""
import hashlib
import json
import os
from pathlib import Path
from queue import Queue
import struct
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler,Request,build_opener
from .updates import DOWNLOAD_URL,Release

HOSTS={'github.com','raw.githubusercontent.com','media.githubusercontent.com','objects.githubusercontent.com','release-assets.githubusercontent.com'}


def location(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in HOSTS or parsed.port not in (None,443) or parsed.username or parsed.password:raise ValueError('Unexpected installer location.')
    return url


class InstallerRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        location(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def verify(path,release):
    if path.stat().st_size!=release.size:raise ValueError('Installer size does not match the published version.')
    with path.open('rb') as stream:
        if stream.read(2)!=b'MZ':raise ValueError('Invalid installer.')
        stream.seek(0);digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=release.sha256:raise ValueError('Installer checksum does not match the published version.')


def download(release,directory,cancel,progress,opener=None):
    Release.parse(dict(schema=release.schema,version=release.version,installer_url=release.installer_url,sha256=release.sha256,size=release.size))
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    target=directory/f'GameTimeMonitor-{release.version}-{release.sha256[:12]}-Setup.exe'
    if target.is_file():
        try:verify(target,release);return target
        except (ValueError,OSError):pass
    fd,name=tempfile.mkstemp(prefix='download-',suffix='.part',dir=directory);partial=Path(name)
    try:
        opener=opener or build_opener(InstallerRedirect())
        with os.fdopen(fd,'wb') as output,opener.open(Request(DOWNLOAD_URL,headers={'User-Agent':'KeepImproving/updates-v2','Accept':'application/octet-stream'}),timeout=20) as response:
            location(response.geturl());length=response.headers.get('Content-Length')
            if length is not None and (not length.isdigit() or int(length)!=release.size):raise ValueError('Installer size changed. Check for updates again.')
            total=0;deadline=time.monotonic()+600
            while True:
                if cancel.is_set():raise InterruptedError('Download cancelled.')
                if time.monotonic()>deadline:raise TimeoutError('Installer download timed out.')
                block=response.read1(min(1024*1024,release.size+1-total))
                if not block:break
                total+=len(block)
                if total>release.size:raise ValueError('Installer is larger than the published version.')
                output.write(block);progress(total,release.size)
            output.flush();os.fsync(output.fileno())
        verify(partial,release)
        if cancel.is_set():raise InterruptedError('Download cancelled.')
        partial.replace(target);return target
    finally:partial.unlink(missing_ok=True)


def prepare(installer,release):
    verify(installer,release)
    raw=installer.read_bytes();offset=raw.find(b'MSCF')
    if offset<0 or offset+36>len(raw):raise ValueError('Installer archive is missing.')
    size=struct.unpack_from('<I',raw,offset+8)[0]
    if size<36 or offset+size>len(raw):raise ValueError('Invalid installer archive.')
    stage=Path(tempfile.mkdtemp(prefix='install-',dir=installer.parent));cab=stage/'installer.cab';cab.write_bytes(raw[offset:offset+size])
    expand=Path(os.environ['SystemRoot'])/'System32'/'expand.exe'
    subprocess.run([str(expand),'-F:*',str(cab),str(stage)],check=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if any(not (stage/name).is_file() for name in ('setup.ps1','setup.cmd','payload.zip')):raise ValueError('Installer files are missing.')
    cab.unlink();return stage/'setup.ps1'


def installed_directory():
    if not getattr(sys,'frozen',False):raise ValueError('Run the installed application to install an update.')
    directory=Path(sys.executable).resolve().parent
    manifest=json.loads((directory/'bundle-install.json').read_text(encoding='utf-8-sig'))
    if manifest.get('Marker')!='GameTimeMonitor.bundle.v1' or Path(manifest.get('InstallDir','')).resolve()!=directory:raise ValueError('Invalid installation folder.')
    return directory


def launch(setup,install_dir,data_dir):
    powershell=Path(os.environ['SystemRoot'])/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe'
    # Literal argv, never a generated shell expression. The verified setup waits
    # for graceful shutdown, backs up the profile and resumes in the tray.
    return subprocess.Popen([str(powershell),'-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',str(setup),'-InstallDir',str(install_dir),'-DataDir',str(Path(data_dir).resolve())],cwd=setup.parent,creationflags=subprocess.CREATE_NO_WINDOW)


class DownloadWorker:
    def __init__(self,fetch=download,stage=prepare):
        self.fetch,self.stage=fetch,stage;self.results=Queue();self.cancel=threading.Event();self.progress=(0,0);self.busy=False
    def request(self,release,directory):
        if self.busy or self.cancel.is_set():return False
        self.busy=True
        def run():
            result=None;error=None
            try:
                installer=self.fetch(release,directory,self.cancel,lambda used,total:setattr(self,'progress',(used,total)))
                if not self.cancel.is_set():result=self.stage(installer,release)
            except Exception as exc:error=exc
            finally:
                if not self.cancel.is_set():self.results.put((result,error))
                self.busy=False
        try:threading.Thread(target=run,name='update-download',daemon=True).start()
        except RuntimeError:self.busy=False;return False
        return True
    def close(self):self.cancel.set()
