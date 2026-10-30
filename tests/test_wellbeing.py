"""Shared digital budgets conserve real foreground time and stay local."""
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
import tempfile
import unittest
from gametime.model import Settings,Catalog,Game
from gametime.store import Store
from gametime.focus import Focus,app_key
from gametime.tracker import Sample
from gametime.wellbeing import Wellbeing,target,validate_rules


def rule(identity,members,seconds=60,**values):
    return dict(id=identity,name=identity,members=members,seconds=seconds,enabled=True,enforce=False,overlay=True,**values)


class WellbeingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.base=Path(self.tmp.name)
        self.store=Store(self.base/'usage.sqlite3'); self.settings=Settings(games_root=str(self.base/'Games'))
        self.focus=Focus(self.store); self.catalog=Catalog(self.settings)
        self.engine=Wellbeing(self.store,self.catalog,self.focus); self.start=datetime(2026,10,28,12)
        self.browser=r'C:\Apps\brave.exe'; self.editor=r'C:\Apps\editor.exe'

    def tearDown(self):
        self.engine.flush(); self.focus.close(); self.store.close(); self.tmp.cleanup()

    def tick(self,second,path=None,host='',interactive=True,wall=None):
        sample=Sample(wall or self.start+timedelta(seconds=second),second,path or self.editor,'fixture',interactive)
        self.engine.tick(sample,host); return sample

    def configure(self,rules):
        self.settings=replace(self.settings,wellbeing_rules=rules).validate(); self.catalog.settings=self.settings

    def totals(self,wall=None): return {s.rule['id']:s.used for s in self.engine.states(wall or self.start)}

    def test_browser_and_website_use_one_shared_second_with_independent_caps(self):
        members=[target('app',self.browser),target('site','youtube.com')]
        self.configure([rule('mixed',members),rule('app',[members[0]]),rule('site',[members[1]]),rule('all-sites',[target('category','sites')])])
        self.tick(0,self.browser,'www.youtube.com'); self.tick(1,self.browser,'www.youtube.com')
        self.assertEqual(self.totals(),dict(mixed=1,app=1,site=1,**{'all-sites':1}))
        self.tick(2,self.browser,'example.com'); self.tick(3,self.browser,'example.com')
        self.assertEqual(self.totals(),dict(mixed=3,app=3,site=2,**{'all-sites':3}))

    def test_mixed_group_spends_across_games_apps_and_sites_without_counting_games_as_apps(self):
        game=Game('game','Example','Steam',r'C:\Games\Example'); self.catalog.games={game.id:game}
        game_path=game.root+r'\game.exe'
        members=[target('game',game.id),target('app',game_path),target('app',self.editor),target('site','example.com')]
        self.configure([rule('group',members),rule('games',[target('category','games')]),rule('apps',[target('category','apps')])])
        self.tick(0,game_path); self.tick(1,self.editor); self.tick(2,self.browser,'example.com'); self.tick(3,self.browser,'example.com')
        self.assertEqual(self.totals(),{'group':3,'games':1,'apps':2})

    def test_creating_or_editing_a_rule_keeps_already_measured_time(self):
        self.tick(0); self.tick(1); self.tick(2)
        self.configure([rule('editor',[target('app',self.editor)],1)])
        state=self.engine.states(self.start)[0]; self.assertEqual((state.used,state.remaining),(2,0))
        self.configure([rule('editor',[target('app',self.editor)],120)])
        self.assertEqual(self.engine.states(self.start)[0].remaining,118)
        self.engine.flush(); restored=Wellbeing(self.store,self.catalog,self.focus)
        self.assertEqual(restored.states(self.start)[0].used,2)
        restored.tick(Sample(self.start+timedelta(hours=3),10800,self.editor,'fixture'))
        self.assertEqual(restored.states(self.start)[0].used,2)

    def test_all_installations_of_an_application_spend_the_same_budget_once(self):
        self.configure([rule('editor',[target('app',self.editor),target('app',r'D:\Older\editor.exe')],120)])
        self.tick(0,self.editor); self.tick(1,r'D:\Updated\Editor.exe'); self.tick(2,r'E:\Portable\EDITOR.EXE')
        self.assertEqual(self.totals()['editor'],2)
        self.engine.flush(); restored=Wellbeing(self.store,self.catalog,self.focus)
        self.assertEqual(restored.states(self.start)[0].used,2)

    def test_sleep_lock_clock_jump_and_disabled_tracking_are_not_charged(self):
        self.configure([rule('apps',[target('category','apps')])])
        self.tick(0); self.tick(30); self.tick(31,interactive=False); self.tick(32)
        self.assertEqual(self.totals()['apps'],0)
        self.tick(33,wall=self.start+timedelta(seconds=80)); self.assertEqual(self.totals()['apps'],0)
        self.focus.settings.tracking=False; self.tick(34); self.tick(35)
        self.assertEqual(self.totals()['apps'],0)
        self.focus.settings.tracking=True; self.focus.settings.excluded_apps=[app_key(self.editor)]
        self.tick(36); self.tick(37); self.assertEqual(self.totals()['apps'],0)

    def test_midnight_split_is_conserved_and_next_day_has_its_own_limit(self):
        self.start=datetime(2026,10,28,23,59,59)
        self.configure([rule('apps',[target('category','apps')])])
        self.tick(0); current=self.tick(2)
        self.assertEqual(self.totals(current.wall)['apps'],1)
        self.engine.flush()
        rows=list(self.store.db.execute('SELECT day,SUM(seconds) FROM wellbeing_usage GROUP BY day ORDER BY day'))
        self.assertEqual(rows,[('2026-10-28',1),('2026-10-29',1)])

    def test_browser_policy_preserves_focus_and_blocks_only_exhausted_site_rules(self):
        site=rule('site',[target('site','example.com')],1); site['enforce']=True
        self.configure([site]); base={'active':True,'tracking':True,'mode':'blocklist','allow':[],'block':['social.example'],'remaining':80}
        self.tick(0,self.browser,'example.com'); self.tick(1,self.browser,'example.com')
        policy=self.engine.policy(base,self.start)
        self.assertEqual(policy['block'],['social.example','example.com']); self.assertEqual(policy['remaining'],80)
        self.configure([rule('site',[target('site','example.com')],1)])
        self.assertEqual(self.engine.policy(base,self.start),base)
        all_sites=rule('sites',[target('category','sites')],1); all_sites['enforce']=True
        self.configure([all_sites]); self.assertEqual(self.engine.policy(base,self.start)['mode'],'allowlist')

    def test_rules_and_raw_activity_never_enter_statistics_sync(self):
        from gametime.preferences_sync import values
        self.configure([rule('private',[target('app',self.editor),target('site','example.com')])])
        self.store.save_settings(self.settings)
        self.assertNotIn('settings.wellbeing_rules',values(self.store))

    def test_invalid_members_limits_duplicates_and_nonfinite_values_are_rejected(self):
        base=rule('valid',[target('site','example.com')])
        for change in ({'seconds':float('nan')},{'seconds':0},{'seconds':True},{'members':[]},
                       {'members':[target('site','example.com')]*2},{'members':[{'kind':'category','value':'everything'}]},
                       {'enabled':'yes'},{'name':''}):
            with self.subTest(change=change),self.assertRaises(ValueError): validate_rules([base|change])
        with self.assertRaises(ValueError): validate_rules([base,base])
        self.assertEqual(target('site','https://WWW.Example.com/path?q=secret'),{'kind':'site','value':'www.example.com'})
