from dataclasses import replace
from datetime import datetime
import json,unittest,uuid
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import test_qt_ui as fixture
from gametime.wellbeing import target
from gametime.qt_budgets import new_rule
from gametime.browser_control import BrowserControl
from gametime.browser_activity import BrowserBridge
from gametime.restriction_policy import Budget,new_plan,step
from gametime.tracker import Sample


class MediaInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def test_native_and_browser_controls_save_same_local_choice(self):
        app=self.app;rule=new_rule('Music',[target('site','music.example.com')],'music');rule['enabled']=True
        app.settings=app.catalog.settings=replace(app.settings,wellbeing_rules=[rule]);self.store.save_settings(app.settings)
        app.open_activities('site');listing=app.activity_lists['site'];listing.list.setCurrentRow(0)
        self.assertFalse(listing.background_media.isChecked());listing.background_media.click()
        self.assertTrue(app.background_media.enabled(target('site','music.example.com')))
        for language in ('hu','en'):
            app.set_language(language);self.assertEqual(listing.background_media.text(),app.t('Count background playback'))
            self.assertTrue(listing.background_media.isChecked())
        control=BrowserControl(app)
        result=control.dispatch(dict(action='activity.media',data=dict(kind='site',key='music.example.com',enabled=False),id=uuid.uuid4().hex,revision=control.revision()))
        self.assertTrue(result['ok'],result);self.assertFalse(listing.background_media.isChecked())
        before=self.store.settings();bad=control.dispatch(dict(action='activity.media',data=dict(kind='game',key='x',enabled=True),id=uuid.uuid4().hex,revision=control.revision()))
        self.assertFalse(bad['ok']);self.assertEqual(self.store.settings(),before)

    def test_bridge_rejects_unselected_stale_and_invalid_media(self):
        bridge=BrowserBridge(self.store,port=0);self.addCleanup(bridge.close)
        bridge.update(dict(tracking=True,background_media_sites=['music.example.com','127.0.0.1:8766'],local_sites=['127.0.0.1:8766']))
        def post(media):
            data=dict(browser='brave',domain='',focused=False,private=False,local_version=1,media=media)
            req=Request(f'http://127.0.0.1:{bridge.port}/activity',data=json.dumps(data).encode(),headers={'Authorization':'Bearer '+bridge.token,'Content-Type':'application/json'})
            return json.loads(urlopen(req,timeout=2).read())
        post([dict(domain='www.music.example.com'),dict(domain='notselected.example.com'),dict(domain='127.0.0.1:8766'),dict(domain='127.0.0.1:8767')])
        self.assertEqual(set(bridge.media()[0][1]),{('www.music.example.com',''),('127.0.0.1:8766','')})
        with patch('gametime.browser_activity.time.monotonic',return_value=bridge.last_seen+5):self.assertEqual(bridge.media(),[])
        for media in ('bad',[dict(domain='music.example.com',url='secret')],[dict(domain='music.example.com')]*17):
            with self.assertRaises(HTTPError) as error:post(media)
            self.assertEqual(error.exception.code,400)
        bridge.update(dict(tracking=False,background_media_sites=['music.example.com']))
        post([dict(domain='music.example.com')]);self.assertFalse(any(rows for browser,rows in bridge.media()))

    def test_background_warning_and_cover_mute_are_applied_once(self):
        runtime=self.app.restrictions;wall=datetime.now().astimezone();path=r'C:\Apps\player.exe'
        member=target('app',path);plan=new_plan();plan['steps']=[step('notify',60,usage=True,popup=True),step('cover',60,usage=True)]
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_plans={'music':plan})
        runtime.state.update(str(wall.date()),wall.timestamp(),[Budget('music','Music',600,60,(member,))],{'music':plan})
        observed=Sample(wall,100,path,'123:1');atom=('',path.lower(),'')
        self.app.background_media.targets=[(observed,atom)];self.app.background_media.atoms=(atom,atom)
        current=Sample(wall,100,r'C:\Windows\explorer.exe','456:1')
        with patch.object(runtime,'prepare'),patch.object(runtime,'process_browser_requests'),patch.object(runtime,'show_save_counter'),patch.object(runtime.choices,'tick',return_value=False),patch('gametime.qt_restrictions.native.open_target',return_value=1),patch('gametime.qt_restrictions.win32.k.CloseHandle'),patch.object(runtime.audio,'update') as audio,patch.object(self.app,'popup',return_value=True) as popup:
            runtime.tick(current);popup.assert_called_once();audio.assert_called_with([{'path':path,'identity':'123:1'}])
            runtime.tick(current);popup.assert_called_once()
