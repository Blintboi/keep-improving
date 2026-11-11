"""Explicit encrypted USB exchange with a paired Android phone and running desktop.

Uses the authenticated local desktop bridge and adb; never resets cloud guards or
prints the connection code, local API token, payload or user settings.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gametime.secrets import unprotect

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb',type=Path,default=Path(os.environ.get('LOCALAPPDATA',''))/'Android/Sdk/platform-tools/adb.exe')
    parser.add_argument('--data-dir',type=Path,default=Path.home()/'Documents/GameTimeMonitor/data')
    parser.add_argument('--serial')
    args=parser.parse_args()
    with sqlite3.connect((args.data_dir/'usage.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute("SELECT value FROM settings WHERE key='browser_pairing'").fetchone()
        if not row:raise ValueError('The local desktop bridge is not paired yet.')
        token=unprotect(row[0])
    def call(action,data=None,revision=None):
        body={'action':action,'data':data or {}}
        if revision:body.update(revision=revision,id=uuid.uuid4().hex)
        request=urllib.request.Request('http://127.0.0.1:47853/control',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=12) as response:result=json.load(response)
        if not result.get('ok'):raise ValueError(result.get('error','Desktop request failed.'))
        return result
    adb=[str(args.adb)]+(['-s',args.serial] if args.serial else [])
    def run(*arguments,check=True):return subprocess.run([*adb,*arguments],capture_output=True,check=check,timeout=30)
    remote='/sdcard/Android/data/hu.keepimproving.android/files/usb'
    run('get-state');run('shell','mkdir','-p',remote)
    # Exchange twice so any applied command receipt also returns to the phone.
    for cycle in range(2):
        entry=call('companion.export')['result']
        body=dict(format='GameTimeMonitor.sync.v2',need_upload=False,snapshots=[entry])
        raw=json.dumps(body).encode()
        if len(raw)>512*1024:raise ValueError('USB snapshot exceeds the bounded transfer size.')
        handle,path=tempfile.mkstemp(prefix='keep-improving-usb-',suffix='.json')
        try:
            with os.fdopen(handle,'wb') as stream:stream.write(raw)
            run('push',path,remote+'/request.json')
            run('shell','rm','-f',remote+'/response.json')
            run('shell','am','start','-n','hu.keepimproving.android/.MainActivity','-a','hu.keepimproving.android.USB_SYNC')
            deadline=time.monotonic()+25
            while True:
                response=run('exec-out','cat',remote+'/response.json',check=False)
                if response.returncode==0:
                    try:phone=json.loads(response.stdout);break
                    except (ValueError,UnicodeError):pass
                if time.monotonic()>=deadline:raise TimeoutError('Open and unlock the paired phone, then retry USB synchronization.')
                time.sleep(.4)
            revision=call('live')['revision']
            result=call('companion.import',{'entry':phone},revision)
            print(json.dumps(dict(cycle=cycle+1,encrypted_usb_exchange=True,phone_imported=result['result']['imported'])))
        finally:
            Path(path).unlink(missing_ok=True)
            run('shell','rm','-f',remote+'/request.json',remote+'/response.json',check=False)
    print('USB synchronization completed. Cloud quotas and cooldowns were preserved.')

if __name__=='__main__':main()
