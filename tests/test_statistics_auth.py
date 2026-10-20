"""Native PKCE, token storage and worker lifecycle with local-only fixtures."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock
from urllib.parse import parse_qs,urlsplit
from urllib.request import urlopen
from urllib.request import Request
from urllib.error import HTTPError
from gametime.statistics_auth import AuthClient,AuthError,AuthWorker,pkce,session_response,validate_session
from gametime.store import Store

USER='11111111-1111-4111-8111-111111111111'
def session(): return dict(access_token='e30.cGF5bG9hZA.c2ln',refresh_token='private-refresh-fixture',expires_at=int(time.time())+3600,user_id=USER,name='<GitHub user>')
def response(): return dict(**session(),user={'id':USER,'user_metadata':{'user_name':'Fixture'}},provider_token='never-store-provider-token')

class AccountTests(unittest.TestCase):
    def test_pkce_is_random_and_challenge_matches(self):
        verifier,challenge=pkce();self.assertEqual(len(verifier),64)
        self.assertNotEqual(verifier,pkce()[0]);self.assertEqual(challenge,base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='))

    def test_session_whitelist_and_windows_encrypted_pending_recovery(self):
        value=session_response(response());self.assertNotIn('provider_token',value)
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'usage.sqlite3')
            try:
                store.save_account_session(value);store.pending_connection('a'*32)
                self.assertEqual(store.account_session(),value);self.assertEqual(store.pending_connection(),'a'*32)
                raw=str(store.db.execute('select * from settings').fetchall())
                for secret in [value['access_token'],value['refresh_token'],'a'*32]: self.assertNotIn(secret,raw)
                store.save_account_session(None);store.pending_connection(clear=True)
                self.assertIsNone(store.account_session());self.assertEqual(store.pending_connection(),'')
            finally: store.close()
        for changes in [{'extra':'key'},{'access_token':'invalid'},{'expires_at':True},{'user_id':'forged'},{'refresh_token':''}]:
            with self.assertRaises(ValueError): validate_session({**session(),**changes})

    def test_worker_preserves_rotated_refresh_on_rpc_failure_and_clears_invalid_session(self):
        client=Mock();rotated={**session(), 'refresh_token':'rotated-refresh-fixture'};client.refresh.return_value=rotated
        client.account.side_effect=AuthError('capacity');worker=AuthWorker(client)
        try:
            values,warning=worker.exchange(('activate',{**session(),'expires_at':1},0),'a'*32)
            self.assertEqual(values[0]['session'],rotated);self.assertEqual(values[0]['error'],'capacity')
            client.account.side_effect=AuthError('session');values,warning=worker.exchange(('activate',session(),0),'a'*32)
            self.assertIsNone(values[0]['session'])
            client.request.side_effect=OSError('private network failure');client.auth_url='https://fixture/auth'
            values,warning=worker.exchange(('logout',session(),0),'')
            self.assertIsNone(values[0]['session']);self.assertNotIn('private network failure',warning)
        finally: worker.close()

    def test_loopback_callback_nonce_pkce_and_no_provider_token_retention(self):
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                content=json.dumps({'external':{'github':True}}).encode();self.send_response(200);self.end_headers();self.wfile.write(content)
            def do_POST(self):
                calls.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                content=json.dumps(response()).encode();self.send_response(200);self.end_headers();self.wfile.write(content)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base='http://127.0.0.1:'+str(server.server_port)
            client=AuthClient(base+'/auth',base+'/account',allow_local_http=True)
            browser=[];callbacks=[]
            def open_browser(url,**kwargs):
                query=parse_qs(urlsplit(url).query);browser.append(query)
                def callback():
                    redirect=query['redirect_to'][0]
                    for target,headers in [(redirect.replace('/gametime/callback/','/wrong/'),{}),(redirect,{'Host':'attacker.test'}),(redirect,{'Origin':'https://attacker.test'})]:
                        try: urlopen(Request(target+'?code=fixture-code-123',headers=headers),timeout=2)
                        except HTTPError as error: callbacks.append(error.code);error.close()
                    with urlopen(query['redirect_to'][0]+'?code=fixture-code-123') as result:
                        callbacks.append((result.status,result.headers.get('Cache-Control'),result.read()))
                threading.Thread(target=callback,daemon=True).start();return True
            value=client.login(lambda:True,open_browser,timeout=2)
            self.assertEqual(value['name'],'Fixture');self.assertNotIn('provider_token',value)
            self.assertEqual(browser[0]['code_challenge_method'],['s256']);self.assertEqual(browser[0]['provider'],['github'])
            self.assertEqual(calls[0][0],'/auth/token?grant_type=pkce');self.assertEqual(calls[0][1]['auth_code'],'fixture-code-123')
            verifier=calls[0][1]['code_verifier'];self.assertEqual(browser[0]['code_challenge'][0],base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='))
            self.assertEqual(callbacks[:3],[404,404,404])
            self.assertEqual(callbacks[3][:2],(200,'no-store'));self.assertNotIn(b'fixture-code',callbacks[3][2])
            with self.assertRaisesRegex(AuthError,'cancelled'): client.login(lambda:False,lambda *a,**k:True,timeout=.1)
        finally: server.shutdown();server.server_close();thread.join()

    def test_credentials_are_not_forwarded_to_redirects_or_other_hosts(self):
        for url in ['https://attacker.test/auth','http://jtvdbqwmejrckjejjrdl.supabase.co/auth','https://jtvdbqwmejrckjejjrdl.supabase.co/auth?x=1']:
            with self.assertRaises(ValueError): AuthClient(auth_url=url)
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                calls.append(self.path)
                self.send_response(302);self.send_header('Location','http://127.0.0.1:'+str(self.server.server_port)+'/target');self.end_headers()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base='http://127.0.0.1:'+str(server.server_port);client=AuthClient(base+'/auth',base+'/account',allow_local_http=True)
            with self.assertRaises(AuthError): client.request(base+'/redirect',{},session()['access_token'])
            self.assertEqual(calls,['/redirect'])
        finally: server.shutdown();server.server_close();thread.join()

    def test_provider_callback_failure_is_sanitized_and_never_exchanges_a_code(self):
        client=AuthClient();client.request=Mock(return_value={'external':{'github':True}})
        bodies=[]
        def browser(url,**kwargs):
            redirect=parse_qs(urlsplit(url).query)['redirect_to'][0]
            def callback():
                with urlopen(redirect+'?error=access_denied&error_code=hook_error&error_description=PRIVATE-DETAIL') as result: bodies.append(result.read())
            threading.Thread(target=callback,daemon=True).start();return True
        with self.assertRaises(AuthError) as error: client.login(lambda:True,browser,timeout=2)
        self.assertEqual(error.exception.tag,'closed');self.assertEqual(client.request.call_count,1)
        self.assertNotIn(b'PRIVATE-DETAIL',b''.join(bodies))
        client=AuthClient();client.opener.open=Mock(side_effect=ConnectionAbortedError('PRIVATE-NETWORK-DETAIL'))
        with self.assertRaises(AuthError) as error: client.request(client.auth_url+'/settings',method='GET')
        self.assertNotIn('PRIVATE-NETWORK-DETAIL',str(error.exception))
