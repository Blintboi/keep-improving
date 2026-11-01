"""Next-event counters and tray break continuity use the real restriction state."""
from dataclasses import replace
from datetime import datetime,timedelta
import math
import unittest
from unittest.mock import patch,Mock
import test_restriction_steps as policy_fixture
import test_qt_ui as ui_fixture
from gametime.timer_view import project,TimerView,tooltip,ordered
from gametime.restriction_policy import Budget,new_plan,step
from gametime.qt_budgets import new_rule
from gametime.wellbeing import target
from gametime.tracker import Sample
from gametime.i18n import tr


class TimerProjectionTests(unittest.TestCase):
    setUp=policy_fixture.StepsTests.setUp
    tearDown=policy_fixture.StepsTests.tearDown

    def prepare(self,used,now=1000,limit=3600):
        self.budget=Budget('budget','YouTube',limit,used,(target('site','youtube.com'),))
        self.engine.update(self.day,now,[self.budget],self.plans)
        return project(self.budget,self.plan,self.engine.rows['budget'],now,'site:youtube.com')

    def test_repeating_break_then_daily_limit_is_the_next_event(self):
        self.plan['steps']=[step('break',1800,usage=True,break_minutes=5),step('cover',3600,usage=True)]
        first=self.prepare(0); self.assertEqual((first.event,first.seconds,first.total),('break',1800,3600))
        used=self.prepare(1700); self.assertEqual((used.event,used.seconds,used.total),('break',100,1900))
        pause=self.prepare(1800); self.assertEqual((pause.event,pause.seconds,pause.total),('break_active',300,1800))
        ended=self.prepare(1800,1300); self.assertEqual((ended.event,ended.seconds,ended.total),('limit',1800,1800))
        limit=self.prepare(3600,3100); self.assertEqual((limit.event,limit.seconds),('limit',0))

    def test_paused_usage_threshold_does_not_hide_an_ongoing_break(self):
        self.plan['steps']=[step('break',60,usage=True,break_minutes=5)]
        event=self.prepare(60,limit=120)
        self.assertEqual((event.event,event.seconds,event.total),('break_active',300,60))
        background=project(self.budget,self.plan,self.engine.rows['budget'],1001,'site:',running_only=True)
        self.assertEqual((background.event,background.seconds),('break_active',299))

    def test_wall_clock_cutoff_beats_later_use_event_and_has_no_fake_total(self):
        clock=step('cover',usage=True); clock.update(time_mode='clock',clock_minute=1320)
        self.plan['steps']=[step('break',1800,usage=True),clock]
        budget=Budget('budget','Clock',math.inf,0,(),clock_deadlines={1320:1600})
        event=project(budget,self.plan,{},1000,'site:')
        self.assertEqual((event.event,event.seconds),('clock_limit',600)); self.assertEqual(event.secondary(lambda s:s),'')

    def test_warning_disappears_after_delivery(self):
        warning=step('notify',600,usage=True,popup=True); self.plan['steps']=[warning,step('cover',3600,usage=True)]
        self.assertEqual(self.prepare(0).event,'warning')
        self.prepare(600); self.engine.delivered('budget',warning['id'])
        self.assertEqual(self.prepare(600).event,'limit')

    def test_expired_quota_does_not_hide_a_later_restriction_or_ongoing_break(self):
        self.plan['steps']=[step('minimize',300)]
        event=self.prepare(3600)
        self.assertEqual((event.event,event.seconds,event.total),('limit',300,0))
        later=project(self.budget,self.plan,self.engine.rows['budget'],1100,'site:')
        self.assertEqual((later.seconds,later.wall_clock),(200,True))
        pause=step('break',1800,usage=True)
        event=project(self.budget,dict(self.plan,steps=[pause]),{'breaks':{pause['id']:{'until':1300}}},1100,'site:')
        self.assertEqual((event.event,event.seconds),('break_active',200))

    def test_save_grant_and_zero_budget_take_precedence(self):
        self.plan['steps']=[step('cover',60,usage=True),step('break',60,usage=True)]
        self.prepare(60); self.engine.extend(['budget'],'site:youtube.com:fixturetoken')
        event=project(self.budget,self.plan,self.engine.rows['budget'],1000,'site:youtube.com')
        self.assertEqual(event.event,'save'); self.assertEqual(event.seconds,180)
        zero=project(replace(self.budget,limit=0),self.plan,self.engine.rows['budget'],1000,'site:youtube.com')
        self.assertEqual((zero.event,zero.seconds),('limit',0))

    def test_tray_prioritizes_foreground_then_earliest_break_and_fits_windows(self):
        events=ordered([TimerView('youtube','YouTube','break_active',272),TimerView('games','Games','limit',1500,1500,active=True),
                        TimerView('other','Other','break_active',120)])
        tip=tooltip(events,lambda s,**kw:s.format(**kw)); self.assertLess(tip.index('Games'),tip.index('Other'))
        self.assertIn('25:00',tip); self.assertIn('02:00',tip)
        long=tooltip([TimerView('long','😀'*80,'break',400,1000,active=True)],lambda s,**kw:s.format(**kw))
        self.assertLessEqual(len(long.encode('utf-16-le')),254)

    def test_restriction_beats_break(self):
        events=ordered([TimerView('break','Break','break_active',300,active=True),TimerView('limit','Limit','limit',0,active=True)])
        self.assertEqual(events[0].key,'limit')


class TimerInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(ui_fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=ui_fixture.QtInterfaceTests.setUp; tearDown=ui_fixture.QtInterfaceTests.tearDown; pump=ui_fixture.QtInterfaceTests.pump

    def setup_budget(self,member=None):
        rule=new_rule('YouTube',[member or target('site','youtube.com')],'youtube'); rule.update(enabled=True,seconds=3600)
        plan=new_plan(); plan['steps']=[step('break',1800,usage=True,break_mode='redirect',break_minutes=5),step('cover',3600,usage=True)]
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[rule],restriction_plans={'youtube':plan})
        self.now=datetime.now().astimezone().replace(microsecond=0)
        self.sample=Sample(self.now,100,r'C:\Apps\brave.exe','fixture:browser')
        self.app.browser_bridge=Mock(); self.app.browser_bridge.website.return_value='youtube.com'; self.app.browser_bridge.redirect_budget.return_value=''; self.app.browser_bridge.take_requests.return_value=[]
        self.app.wellbeing.tick(self.sample,'youtube.com'); self.app.restrictions.prepare(self.now)
        self.app.restrictions.current=self.sample
        return rule

    def test_desktop_shows_next_event_and_daily_total_then_redirect_hides_overlay_but_keeps_tray_break(self):
        self.setup_budget()
        with patch('gametime.qt_ui.win32.sample',return_value=self.sample): self.app.update_overlay()
        self.assertEqual(self.app.overlay.seconds,1800); self.assertEqual(self.app.overlay.caption,'Szünetig')
        self.assertIn('01:00:00',self.app.overlay.detail)
        self.app.wellbeing.totals['youtube']=1800; self.app.restrictions.prepare(self.now)
        self.app.browser_bridge.website.return_value=''; self.app.browser_bridge.redirect_budget.return_value='youtube'
        redirected=replace(self.sample,wall=self.now+timedelta(seconds=1),awake=101)
        self.app.wellbeing.tick(redirected,'',redirect_budget='youtube'); self.app.restrictions.current=redirected
        with patch('gametime.qt_ui.win32.sample',return_value=redirected): self.app.update_overlay()
        self.assertFalse(self.app.overlay.isVisible())
        events=self.app.timer_views(redirected)
        pause=next(event for event in events if event.key=='youtube')
        self.assertEqual((pause.event,round(pause.seconds)),('break_active',299)); self.assertFalse(pause.active)
        items=self.app.timer_menu_items(); self.assertTrue(any('Szünetből hátra' in str(caption) for _,caption in items))

    def test_live_site_counter_interpolates_usage_without_resizing_each_second(self):
        self.setup_budget()
        with patch('gametime.qt_ui.win32.sample',return_value=self.sample): self.app.update_overlay()
        later=replace(self.sample,wall=self.now+timedelta(seconds=1.25),awake=101.25)
        with patch('gametime.qt_ui.win32.sample',return_value=later),patch.object(self.app.overlay,'setFixedSize') as resize:
            self.app.update_overlay(); resize.assert_not_called()
        self.assertTrue(self.app.overlay.isVisible()); self.assertEqual(self.app.overlay.seconds,1799)
        self.assertIn('59:59',self.app.overlay.detail)

    def test_restriction_only_website_blocks_without_an_implicit_expiry_popup(self):
        self.setup_budget()
        plan=new_plan(legacy=True); plan['steps']=[step('cover',3600,usage=True)]
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_plans={'youtube':plan})
        self.app.wellbeing.totals['youtube']=3600
        with patch.object(self.app,'popup',return_value=True) as popup:
            self.app.restrictions.tick(self.sample)
            self.app.wellbeing_tick(self.sample)
            popup.assert_not_called()
        self.assertEqual(self.app.restrictions.state.action('youtube','site:youtube.com'),'cover')

    def test_game_rtss_has_same_next_event_and_smaller_total_line(self):
        self.setup_budget(target('game',self.games[0].id))
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_rtss_auto=True,
            counter_overlays={'youtube':{'overlay_rtss_auto':True}})
        current=replace(self.sample,path=str(self.exe),identity='fixture:game')
        self.app.tracker.active=self.games[0]; self.app.tracker.identity=current.identity
        self.app.wellbeing.tick(current); self.app.restrictions.prepare(self.now)
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch('gametime.qt_ui.foreground_screen_name',return_value=''), \
             patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app.rtss,'present',return_value=True) as present:
            self.app.update_overlay(); self.app._overlay_desktop_until=0; self.app.update_overlay()
        markup=present.call_args.args[2]
        from gametime import rtss_timer
        self.assertIn('<LI=',markup); self.assertTrue(markup.isascii())
        atlas=next(atlas for key,atlas in rtss_timer._cache.items() if key[-2:] == ('Szünetig','Napi keretből: '))
        self.assertGreater(atlas.height,atlas.small)
        self.assertEqual(markup.count('<I='),18)
        self.assertEqual(len(present.call_args.args[3]),6)

    def test_rtss_digits_tick_without_rebuilding_unicode_atlas(self):
        from gametime import rtss_timer
        from gametime.rtss import countdown
        from pathlib import Path
        rtss_timer.clear()
        first=countdown(1800,False,1,caption='Szünetig',detail='Napi keretből: 01:00:00')
        atlas=next(iter(rtss_timer._cache.values())); image=Path(atlas.directory.name)/'timer.png'
        stamp=image.stat().st_mtime_ns
        with patch.object(rtss_timer,'Atlas',side_effect=AssertionError('unchanged labels must reuse atlas')):
            second=countdown(1799,False,1,caption='Szünetig',detail='Napi keretből: 59:59')
        self.assertNotEqual(first,second); self.assertEqual(image.stat().st_mtime_ns,stamp)
        self.assertTrue(first.isascii()); self.assertLess(len(first),4096)
        rtss_timer.clear(); self.assertFalse(image.exists())

    def test_background_break_survives_another_activity_and_menu_keeps_standard_commands(self):
        self.setup_budget(); self.app.wellbeing.totals['youtube']=1800; self.app.restrictions.prepare(self.now)
        other=replace(self.sample,path=str(self.exe),identity='fixture:game')
        self.app.tracker.active=self.games[0]; self.app.tracker.identity=other.identity
        self.app.wellbeing.tick(other); self.app.restrictions.current=other
        events=self.app.timer_views(other)
        self.assertTrue(events[0].active); self.assertEqual(events[0].key,'shared-games')
        self.assertTrue(any(event.key=='youtube' and event.event=='break_active' for event in events))
        with patch.object(self.app.tray,'popup_menu',return_value=0) as menu:
            self.app.tray_menu()
        ids={item[0] for item in menu.call_args.args[0] if item}
        self.assertTrue({1,2,3,4,5,6}.issubset(ids)); self.assertTrue(any(identity>=1000 for identity in ids))


if __name__=='__main__': unittest.main()
