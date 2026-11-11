"""Real desktop icon pipeline over the local browser API; isolated profiles only."""
import os,time,uuid,unittest
from pathlib import Path
from unittest.mock import patch
from dataclasses import replace
import test_qt_ui as fixture
import test_activity_icons as assets
from gametime.browser_control import BrowserControl
from gametime.qt_activity_icons import ActivityIcons
ICON_FETCH=ActivityIcons.fetch


class BrowserIconTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def setUp(self):
        fixture.QtInterfaceTests.setUp(self)
        self.enterContext(patch('gametime.browser_icons.BrowserIcons.fetch',ICON_FETCH))
        self.control=BrowserControl(self.app);self.app.browser_control=self.control
        self.client=uuid.uuid4().hex;self.requests=[];self.replies=[]
        self.path=str(Path(os.environ['WINDIR'])/'System32/notepad.exe')
        self.control.library.activity_add(dict(kind='app',value=self.path))
        self.control.library.activity_add(dict(kind='site',value='example.com'))

    def icons(self,ids,client=None):
        result=self.control.dispatch(dict(action='library.icons',data=dict(ids=ids,client=client or self.client)))
        self.assertTrue(result['ok'],result);return result['result']

    def test_browser_loads_native_icons_while_hub_hidden_and_reuses_cache(self):
        self.app.hide()
        with assets.IconTests.network(self,{'https://example.com/favicon.ico':(assets.png_bytes(),False)}):
            self.control.state({});self.assertIsNone(self.control.library.icons)
            ids=['app:notepad.exe','site:example.com'];first=self.icons(ids)
            self.assertTrue(all(row['pending'] for row in first.values()))
            pipeline=self.control.library.icons
            with patch.object(pipeline.provider,'icon',wraps=pipeline.provider.icon) as native:
                self.pump(.25);loaded=self.icons(ids)
                self.assertTrue(all(row['has_image'] and not row['pending'] for row in loaded.values()))
                self.assertTrue(all(row['image'].startswith('data:image/png;base64,') for row in loaded.values()))
                again=self.icons(ids);self.pump(.05)
                self.assertEqual(loaded,again);self.assertEqual(native.call_count,1)
                self.assertEqual(len(self.requests),1)
            self.icons([]);self.assertFalse(pipeline.enabled)

    def test_known_focus_sites_load_but_unknown_paths_and_sites_cannot_start_reads(self):
        self.app.focus.configure(replace(self.app.focus.settings,block_sites=['focus.example.com']))
        self.control.state({})
        with assets.IconTests.network(self,{},automatic=False):
            self.icons(['site:focus.example.com']);self.pump(.05)
            self.assertEqual(len(self.requests),1)
            pipeline=self.control.library.icons
            with patch.object(pipeline.provider,'icon') as provider:
                result=self.icons(['app:C:\\private\\unknown.exe','site:unknown.example.com']);self.pump(.05)
                self.assertTrue(all(not row['image'] and not row['pending'] for row in result.values()))
                provider.assert_not_called();self.assertEqual(len(self.requests),1)
            self.assertTrue(self.replies[0].aborted)

    def test_each_browser_view_has_an_expiring_lease_and_cancels_without_failure_cache(self):
        self.control.state({})
        with assets.IconTests.network(self,{},automatic=False):
            self.icons(['site:example.com']);self.pump(.05)
            other=uuid.uuid4().hex;self.icons(['site:example.com'],other)
            self.icons([]);self.assertFalse(self.replies[0].aborted)
            pipeline=self.control.library.icons
            pipeline.leases[other]=(time.monotonic()-1,pipeline.leases[other][1]);pipeline.expire()
            self.assertTrue(self.replies[0].aborted);self.assertFalse(pipeline.jobs)
            self.assertNotIn('site:example.com',pipeline.resolved)
            self.assertFalse(pipeline.cache_paths(dict(kind='site',value='example.com'))[1].exists())
        for data in ({'ids':['site:example.com']*25,'client':self.client},{'ids':[{}],'client':self.client},{'ids':[],'client':'bad'}):
            self.assertFalse(self.control.dispatch(dict(action='library.icons',data=data))['ok'])

    def test_budget_list_only_offers_save_for_a_draft(self):
        app=self.app;editor=app.budget_editor;app.switch_page(5);editor.show_list();editor.drafts.flush()
        self.assertTrue(app.budget_save.isHidden())
        editor.show_editor('shared-games');self.assertFalse(app.budget_save.isHidden())
        app.schedule_editor.limit.setValue(173);editor.show_list();editor.drafts.flush()
        self.assertFalse(app.budget_save.isHidden())
        app.save_budgets();self.assertTrue(app.budget_save.isHidden())
        self.assertEqual(self.control.library.summary()['remaining'],173*60)
        self.assertEqual(self.control.budgets()[0]['seconds'],173*60)
