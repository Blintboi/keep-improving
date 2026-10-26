"""Native GitHub/Supabase PKCE sign-in; project tokens stay in Windows DPAPI."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
import select
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener
import webbrowser

from .statistics_cloud import NoRedirect, keys
from .statistics_sync import SyncWorker

PROJECT_URL='https://jtvdbqwmejrckjejjrdl.supabase.co'
AUTH_URL=PROJECT_URL+'/auth/v1'
ACCOUNT_URL=PROJECT_URL+'/functions/v1/statistics-account'
PUBLIC_KEY='sb_publishable_xgANeSGUAdfkXf61-w8Bmw_s97HysVg'
JWT=re.compile(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
UUID=re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
MESSAGES={
    'unavailable':'Account sign-in is unavailable. Try again later.',
    'provider':'GitHub sign-in has not been configured on the service yet.',
    'session':'Sign in with GitHub again to manage this group.',
    'identity':'A verified GitHub account is required.',
    'closed':'New cloud registrations are temporarily closed.',
    'capacity':'Cloud capacity is currently full. Local statistics are kept.',
    'rotation_limit':'The monthly code replacement limit was reached. Local statistics are kept.',
    'other_group':'This account already manages another code. Replace it to use this new code.',
    'revoked':'This connection code has been revoked. Use your current code.',
    'disabled':'Cloud access for this account is disabled. Local statistics are kept.',
    'exists':'This code cannot replace the current group. Generate a new code.',
    'rate':'Too many account requests. Try again later.',
    'cancelled':'Sign-in was cancelled.',
    'timeout':'Sign-in timed out. Try again.',
}

class AuthError(OSError):
    def __init__(self,tag='unavailable'):
        self.tag=tag if tag in MESSAGES else 'unavailable'
        super().__init__(MESSAGES[self.tag])

def validate_session(value):
    if not isinstance(value,dict): raise ValueError('Invalid saved account session.')
    expected={'access_token','refresh_token','expires_at','user_id','name'}
    if set(value)!=expected: raise ValueError('Invalid saved account session.')
    token=value['access_token']; refresh=value['refresh_token']; expires=value['expires_at']
    if (not isinstance(token,str) or len(token)>16384 or not JWT.fullmatch(token)
        or not isinstance(refresh,str) or not 8<=len(refresh)<=4096
        or not isinstance(expires,int) or isinstance(expires,bool) or not 0<expires<4102444800
        or not isinstance(value['user_id'],str) or not UUID.fullmatch(value['user_id'])
        or not isinstance(value['name'],str) or len(value['name'])>80):
        raise ValueError('Invalid saved account session.')
    return dict(value)

def session_response(value):
    try:
        user=value['user']; name=user.get('user_metadata',{}).get('user_name','')
        session=dict(access_token=value['access_token'],refresh_token=value['refresh_token'],
            expires_at=int(value.get('expires_at') or time.time()+int(value['expires_in'])),
            user_id=user['id'],name=name[:80] if isinstance(name,str) else '')
        return validate_session(session)
    except (KeyError,TypeError,ValueError,OverflowError): raise AuthError() from None

def pkce():
    verifier=base64.urlsafe_b64encode(os.urandom(48)).decode('ascii').rstrip('=')
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).decode('ascii').rstrip('=')
    return verifier,challenge

class AuthClient:
    def __init__(self,auth_url=AUTH_URL,account_url=ACCOUNT_URL,public_key=PUBLIC_KEY,*,allow_local_http=False):
        for url in (auth_url,account_url):
            parsed=urlsplit(url)
            local=allow_local_http and parsed.scheme=='http' and parsed.hostname=='127.0.0.1'
            if not local and (parsed.scheme!='https' or parsed.netloc!=urlsplit(PROJECT_URL).netloc): raise ValueError('Invalid account service.')
            if parsed.username or parsed.password or parsed.query or parsed.fragment: raise ValueError('Invalid account service.')
        self.auth_url=auth_url; self.account_url=account_url; self.public_key=public_key
        self.opener=build_opener(NoRedirect())

    def request(self,url,body=None,token=None,method='POST'):
        headers={'apikey':self.public_key,'Accept':'application/json','Content-Type':'application/json','User-Agent':'GameTimeMonitor/account-v1'}
        if token: headers['Authorization']='Bearer '+token
        request=Request(url,data=json.dumps(body,separators=(',',':')).encode() if body is not None else None,headers=headers,method=method)
        try:
            with self.opener.open(request,timeout=12) as response:
                chunks=[]; size=0; deadline=time.monotonic()+20
                while True:
                    chunk=response.read1(min(16384,65537-size))
                    if time.monotonic()>deadline: raise AuthError()
                    if not chunk: break
                    size+=len(chunk)
                    if size>65536: raise AuthError()
                    chunks.append(chunk)
                return json.loads(b''.join(chunks).decode('utf-8')) if chunks else {}
        except HTTPError as error:
            try:
                raw=error.read(2049)
                value=json.loads(raw.decode()) if len(raw)<=2048 else {}
                tag=value.get('error') if isinstance(value,dict) else None
                if tag not in MESSAGES: tag='session' if error.code in (400,401,403) else 'unavailable'
                raise AuthError(tag) from None
            except (ValueError,UnicodeError): raise AuthError() from None
            finally: error.close()
        except (OSError,UnicodeError,ValueError,RecursionError): raise AuthError() from None

    def refresh(self,session):
        return session_response(self.request(self.auth_url+'/token?grant_type=refresh_token',{'refresh_token':session['refresh_token']}))

    def account(self,action,session,code):
        return self.request(self.account_url,{'action':action,'capability':None if action=='revoke' else keys(code)[1]},session['access_token'])

    def login(self,current,open_browser=webbrowser.open,timeout=180):
        settings=self.request(self.auth_url+'/settings',method='GET')
        if not isinstance(settings,dict) or settings.get('external',{}).get('github') is not True: raise AuthError('provider')
        verifier,challenge=pkce(); nonce=os.urandom(24).hex(); path='/gametime/callback/'+nonce
        class Callback(BaseHTTPRequestHandler):
            def setup(self):
                self.request.settimeout(2); super().setup()
            def log_message(self,*args): pass
            def do_GET(self):
                parsed=urlsplit(self.path)
                try: query=parse_qs(parsed.query,keep_blank_values=True,max_num_fields=8)
                except ValueError: query={}
                valid=(self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
                    and self.headers.get('Origin') is None and parsed.path==path and len(self.path)<4096)
                code=query.get('code',[])
                if valid and len(code)==1 and re.fullmatch(r'[A-Za-z0-9._-]{8,2048}',code[0]):
                    self.server.outcome=code[0]
                elif valid and 'error' in query:
                    error_code=query.get('error_code',[''])[0]
                    self.server.outcome=AuthError('closed' if error_code.startswith('hook_') else
                        'cancelled' if query.get('error')==['access_denied'] and not error_code else 'unavailable')
                else: self.send_error(404); return
                content=('<!doctype html><html lang="hu"><meta charset="utf-8"><title>Keep Improving</title>'
                    '<h1>Keep Improving</h1><p>Visszatérhetsz a Játékfigyelő alkalmazásba.</p>'
                    '<p>Return to the application to finish signing in.</p></html>').encode('utf-8')
                self.send_response(200)
                for key,value in {'Content-Type':'text/html; charset=utf-8','Content-Length':str(len(content)),
                    'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
                    'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'"}.items(): self.send_header(key,value)
                self.end_headers(); self.wfile.write(content)
        with HTTPServer(('127.0.0.1',0),Callback) as server:
            server.outcome=None; server.timeout=.5
            redirect='http://127.0.0.1:'+str(server.server_port)+path
            url=self.auth_url+'/authorize?'+urlencode(dict(provider='github',redirect_to=redirect,
                code_challenge=challenge,code_challenge_method='s256',scopes='user:email'))
            if not open_browser(url,new=2): raise AuthError()
            deadline=time.monotonic()+timeout
            while current() and time.monotonic()<deadline and server.outcome is None:
                if select.select([server],[],[],.5)[0]: server.handle_request()
            if not current(): raise AuthError('cancelled')
            if isinstance(server.outcome,AuthError): raise server.outcome
            if server.outcome is None: raise AuthError('timeout')
            return session_response(self.request(self.auth_url+'/token?grant_type=pkce',{'auth_code':server.outcome,'code_verifier':verifier}))

class AuthWorker(SyncWorker):
    failure_message=MESSAGES['unavailable']
    def __init__(self,client=None):
        super().__init__(); self.client=client or AuthClient()
    def request(self,action,session=None,code=''):
        return super().request(action,dict(session) if session else None,code)
    def failure_warning(self,error): return str(error) if isinstance(error,AuthError) else self.failure_message
    def exchange(self,token,code):
        action,session,generation=token
        if action=='login':
            return [dict(session=self.client.login(lambda:self.current(token)),code=code,ok=True)],''
        session=validate_session(session)
        if action=='logout':
            warning=''
            try:
                if session['expires_at']<time.time()+120: session=self.client.refresh(session)
                self.client.request(self.client.auth_url+'/logout?scope=local',token=session['access_token'])
            except OSError: warning='Signed out locally. The server session could not be revoked while offline.'
            return [dict(session=None,code=code,ok=True)],warning
        try:
            if session['expires_at']<time.time()+120: session=self.client.refresh(session)
            result=self.client.account(action,session,code)
            if not isinstance(result,dict) or (action!='status' and result.get('ok') is not True): raise AuthError()
            return [dict(session=session,code=code,ok=True,result=result)],''
        except AuthError as error:
            # Preserve rotated refresh tokens even when the following RPC failed.
            return [dict(session=None if error.tag in ('session','identity') else session,code=code,error=error.tag)],str(error)
