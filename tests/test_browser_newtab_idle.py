"""Explicit Brave new-tab state is idle; unknown pages remain measurable."""
from dataclasses import replace
from datetime import datetime,timedelta
import json,os
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from gametime.focus import Focus,BROWSER_IDLE
from gametime.model import Catalog,Settings
from gametime.store import Store
from gametime.tracker import Sample
from gametime.wellbeing import Wellbeing


class BraveNewTabTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'usage.sqlite3'); self.addCleanup(self.store.close)
        self.focus=Focus(self.store); self.when=datetime(2026,10,29,12).astimezone()
        rule={'id':'apps','name':'Applications','members':[{'kind':'category','value':'apps'}],
              'seconds':60,'enabled':True,'enforce':False,'overlay':False}
        self.settings=replace(Settings(),wellbeing_rules=[rule]); self.wellbeing=Wellbeing(self.store,Catalog(self.settings),self.focus)
        self.path=r'C:\Apps\brave.exe'
    def tick(self,n,website):
        sample=Sample(self.when+timedelta(seconds=n),n,self.path,'123:456')
        self.focus.tick(sample,website); self.wellbeing.tick(sample,website)
    def test_only_explicit_new_tab_skips_statistics_and_budgets(self):
        self.tick(0,BROWSER_IDLE); self.tick(1,BROWSER_IDLE)
        self.tick(2,'example.com'); self.tick(3,'example.com')
        self.tick(4,''); self.tick(5,''); self.tick(6,BROWSER_IDLE)
        self.focus.flush(); self.wellbeing.flush()
        rows=self.focus.usage(self.when.date())
        self.assertEqual(sum(row[3] for row in rows if row[0]=='app'),4)
        self.assertEqual(sum(row[3] for row in rows if row[0]=='site'),2)
        self.assertEqual(self.wellbeing.states(self.when)[0].used,4)
        self.assertFalse(any(BROWSER_IDLE in str(row) for row in rows))
    def test_idle_signal_never_reclassifies_non_browser_apps(self):
        sample=Sample(self.when,0,r'C:\Apps\editor.exe','123:456')
        self.assertIsNotNone(self.wellbeing.atom(sample,BROWSER_IDLE))


@unittest.skipUnless(os.name=='nt','Windows credential protection required')
class BridgeNewTabTests(BraveNewTabTests):
    def setUp(self):
        super().setUp()
        from gametime.browser_activity import BrowserBridge
        self.bridge=BrowserBridge(self.store,port=0); self.addCleanup(self.bridge.close)
    def post(self,payload):
        request=Request(f'http://127.0.0.1:{self.bridge.port}/activity',data=json.dumps(payload).encode(),
                        headers={'Authorization':'Bearer '+self.bridge.token,'Content-Type':'application/json','Origin':'chrome-extension://abcdefghijklmnop'})
        return json.loads(urlopen(request,timeout=2).read())
    def test_explicit_idle_old_extension_private_and_invalid_messages(self):
        base={'browser':'brave','domain':'','focused':True,'private':False}
        self.post(base|{'idle':True}); self.assertEqual(self.bridge.website(self.path),BROWSER_IDLE)
        self.post(base); self.assertEqual(self.bridge.website(self.path),'')
        self.post(base|{'private':True,'idle':True}); self.assertEqual(self.bridge.website(self.path),'')
        self.post(base|{'domain':'example.com'}); self.assertEqual(self.bridge.website(self.path),'example.com')
        for payload in (base|{'idle':'true'},base|{'idle':True,'domain':'example.com'},base|{'idle':True,'browser':'edge'},base|{'url':'brave://newtab/'}):
            with self.subTest(payload=payload),self.assertRaises(HTTPError): self.post(payload)
