from dataclasses import replace
import unittest
from gametime.focus import domain,FocusSettings
from gametime.website_identity import is_local_site,configured_local_sites
from gametime.model import Settings
from gametime.wellbeing import target,applies


class LocalWebsiteTests(unittest.TestCase):
    def test_aliases_share_one_endpoint_and_paths_are_never_retained(self):
        for value in ('http://127.0.0.1:8766/stats?q=secret#fragment','http://localhost:8766/','http://[::1]:8766/','127.0.0.1:8766'):
            self.assertEqual(domain(value),'127.0.0.1:8766')
        for value,expected in [('localhost','127.0.0.1:80'),('http://localhost','127.0.0.1:80'),('https://[::1]','127.0.0.1:443'),('127.0.0.1:443','127.0.0.1:443')]:
            self.assertEqual(domain(value),expected);self.assertTrue(is_local_site(expected))
    def test_only_common_loopback_hosts_are_added_and_ports_are_validated(self):
        for value in ('192.168.1.2:8766','10.0.0.1','app.local','x.localhost','https://user:secret@localhost:8766','http://[fe80::1]:8766','localhost:0','localhost:65536','localhost:no','file:///localhost:8766'):
            with self.subTest(value=value),self.assertRaises(ValueError):domain(value)
        self.assertEqual(domain('https://example.com:8443/private'),'example.com')
    def test_ports_have_independent_budget_members(self):
        member=target('site','http://localhost:8766/path')
        self.assertTrue(applies([member],('','','127.0.0.1:8766')))
        self.assertFalse(applies([member],('','','127.0.0.1:8767')))
    def test_local_tracking_is_explicit_and_excludes_the_control_bridge(self):
        settings=replace(Settings(),wellbeing_rules=[dict(id='local',name='Local',members=[target('site','http://127.0.0.1:8766'),target('site','http://127.0.0.1:47853')],seconds=60,enabled=True,enforce=False,overlay=False)])
        focus=FocusSettings(block_sites=['127.0.0.1:9000'])
        self.assertEqual(configured_local_sites(settings,focus),['127.0.0.1:8766','127.0.0.1:9000'])
        self.assertEqual(configured_local_sites(Settings(),FocusSettings()),[])
    def test_local_icons_never_fetch_local_page_contents(self):
        from gametime.qt_activity_icons import icon_url
        for value in ('https://localhost/favicon.ico','https://127.0.0.1:8766/favicon.ico','https://[::1]/favicon.ico'):
            self.assertEqual(icon_url(value),'')
    def test_old_workers_receive_valid_public_rules_until_reload(self):
        from gametime.website_identity import compatible_local_policy
        local='127.0.0.1:8766';policy=dict(block=[local,'example.com'],local_sites=[local],restrictions=[dict(domains=[local],all=False),dict(domains=[local,'example.com'],all=False)])
        old=compatible_local_policy(policy,False)
        self.assertEqual(old['block'],['example.com']);self.assertEqual(old['local_sites'],[])
        self.assertEqual(old['restrictions'],[dict(domains=['example.com'],all=False)])
        self.assertEqual(policy['block'],[local,'example.com']);self.assertIs(compatible_local_policy(policy,True),policy)


class LocalWebsiteHistoryTests(unittest.TestCase):
    def setUp(self):
        from test_browser_continuity import BrowserContinuityTests
        BrowserContinuityTests.setUp(self)
        with self.store.db:self.store.db.execute("UPDATE settings SET value=? WHERE key='sessions_since'",(str(self.base-1),))
    def test_offline_usage_and_session_history_keep_ports_separate(self):
        from test_browser_continuity import BrowserContinuityTests
        host='127.0.0.1:8766'
        records=[BrowserContinuityTests.sample(self,1,0,10,host=host),BrowserContinuityTests.sample(self,2,10,20,host='127.0.0.1:8767')]
        answer=BrowserContinuityTests.send(self,records);self.assertEqual(answer['ack'],2)
        rows=dict(self.store.db.execute("SELECT key,seconds FROM activity_usage WHERE kind='site'"))
        self.assertEqual(rows,{host:10,'127.0.0.1:8767':10})
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM activity_sessions WHERE kind='site'").fetchone()[0],2)
    def test_old_worker_snapshot_omits_local_only_budgets(self):
        rule=dict(id='local',name='Local',members=[target('site','127.0.0.1:8766')],seconds=60,enabled=True,enforce=False,overlay=False)
        self.app.settings=replace(self.app.settings,wellbeing_rules=[rule])
        self.assertEqual(self.service.snapshot('brave',0)['budgets'],[])
        self.assertEqual(self.service.snapshot('brave',1)['budgets'][0]['members'],rule['members'])
