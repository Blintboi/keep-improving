"""The same 01:00 boundary governs each measured activity and daily allowance."""
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from gametime.model import Settings,Catalog,Game
from gametime.store import Store
from gametime.tracker import Tracker,Sample
from gametime.focus import Focus
from gametime.wellbeing import Wellbeing,target
from gametime.quota import current_day
from gametime.schedule import bedtime_occurrence
from gametime.budget import remaining_budget
from gametime.scheduled_notifications import tick


class UniversalDayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'usage.sqlite3'); self.addCleanup(self.store.close)
        rule=dict(id='web',name='Web',members=[target('category','sites')],seconds=60,enabled=True,enforce=False,overlay=False)
        self.settings=replace(Settings(),budget_reset_minute=60,wellbeing_rules=[rule])
        self.store.save_settings(self.settings)
        self.catalog=Catalog(self.settings); self.focus=Focus(self.store)
        self.engine=Wellbeing(self.store,self.catalog,self.focus); self.tracker=Tracker(self.store,self.catalog)
        self.browser=r'C:\Apps\brave.exe'
        self.game=Game('game','Game','Games',r'C:\Games\Game')

    def test_games_apps_sites_and_budgets_split_at_one_not_midnight(self):
        for hour,minute,day,split in [(23,59,'2026-10-30',False),(0,59,'2026-10-31',True)]:
            start=datetime(2026,10,30 if hour==23 else 31,hour,minute,59,500000)
            end=start+timedelta(seconds=2)
            self.tracker._credit(self.game,start,end,2)
            self.focus._credit('app',self.browser,'Browser',start,end,2)
            self.focus._credit('site','example.com','example.com',start,end,2)
            self.engine.tick(Sample(start,0,self.browser,'fixture'),'example.com')
            self.engine.tick(Sample(end,2,self.browser,'fixture'),'example.com')
        self.tracker.flush(); self.focus.flush(); self.engine.flush()
        self.assertEqual(self.store.totals('2026-10-30'),{'game':2.5})
        self.assertEqual(self.store.totals('2026-10-31'),{'game':1.5})
        for day,seconds in [('2026-10-30',2.5),('2026-10-31',1.5)]:
            self.assertEqual({(k,v) for k,_,_,v in self.focus.usage(day)},{('app',seconds),('site',seconds)})
            self.assertEqual(self.store.db.execute('SELECT SUM(seconds) FROM wellbeing_usage WHERE day=?',(day,)).fetchone()[0],seconds)
        self.assertEqual(self.engine.states(end)[0].used,1.5)
        restored=Wellbeing(self.store,self.catalog,Focus(self.store))
        self.assertEqual(restored.states(end)[0].used,1.5)

    def test_changing_clock_preserves_spent_shared_budget_and_history(self):
        wall=datetime(2026,10,31,0,30)
        self.catalog.settings=replace(self.settings,budget_reset_minute=0)
        self.focus.configure_day_start(0)
        for i in (0,1,2):
            sample=Sample(wall+timedelta(seconds=i),i,self.browser,'fixture')
            self.focus.tick(sample,'example.com'); self.engine.tick(sample,'example.com')
        self.focus.flush(); history=list(self.focus.usage('2026-10-31'))
        self.store.mark_alert('2026-10-31',('wellbeing:web:60',))
        self.catalog.settings=self.settings; self.focus.configure_day_start(60)
        self.assertEqual(self.engine.states(wall)[0].used,2)
        self.assertIn('wellbeing:web:60',self.store.alert_keys('2026-10-30'))
        self.assertEqual(self.focus.usage('2026-10-31'),history)
        self.assertEqual(self.engine.states(wall.replace(hour=1))[0].used,0)

    def test_focus_completion_and_scheduled_notification_use_shared_day(self):
        wall=datetime(2026,10,31,0,30)
        self.focus.running=True; self.focus.remaining=1; self.focus.last_awake=0
        self.focus.advance(1,wall)
        self.assertEqual(list(self.store.db.execute('SELECT day,rounds FROM focus_completions')),[('2026-10-30',1)])
        item=dict(id='a'*32,title='Night',text='Time',icon='',minute=30,enabled=True)
        settings=replace(self.settings,scheduled_notifications=[item]); alerts=[]
        app=SimpleNamespace(settings=settings,store=self.store,popup_window=None,notification_mode=lambda:'normal',popup=lambda alert:alerts.append(alert) or True)
        tick(app,Sample(wall,1)); tick(app,Sample(wall,2))
        self.assertEqual([alert.day for alert in alerts],['2026-10-30'])
        tick(app,Sample(wall+timedelta(days=1),3))
        self.assertEqual([alert.day for alert in alerts],['2026-10-30','2026-10-31'])

    def test_after_midnight_bedtime_uses_previous_weekday_but_keeps_wall_clock(self):
        settings=replace(self.settings,bedtime_enabled=True,bedtime_caps_budget=True,bedtime_warning_minute=30,bedtime_minute=45,bedtime_resume_minute=480,
                         daily_schedules={'5':{'bedtime_enabled':False}})
        state,day,plan=bedtime_occurrence(settings,datetime(2026,10,31,0,35))
        self.assertEqual((state,day),('warning','2026-10-30'))
        self.assertEqual(remaining_budget(settings,datetime(2026,10,31,0,35),0).remaining,600)
        self.assertEqual(remaining_budget(settings,datetime(2026,10,31,1),0).remaining,0)
        self.assertEqual(bedtime_occurrence(settings,datetime(2026,10,31,8))[0],'off')

    def test_month_year_and_dst_boundaries_keep_the_selected_day(self):
        self.assertEqual(str(current_day(self.settings,datetime(2027,1,1,0,59,59))),'2026-12-31')
        self.assertEqual(str(current_day(self.settings,datetime(2027,1,1,1))),'2027-01-01')
        self.assertEqual(str(current_day(self.settings,datetime(2026,10,25,0,59).astimezone())),'2026-10-24')
        self.assertEqual(str(current_day(self.settings,datetime(2026,10,25,1).astimezone())),'2026-10-25')

    def test_activity_budgets_renew_independently_and_preserve_spent_time(self):
        rule2=dict(self.settings.wellbeing_rules[0],id='other',name='Other')
        self.catalog.settings=replace(self.settings,wellbeing_rules=[self.settings.wellbeing_rules[0],rule2],
                                      budget_reset_overrides={'web':120,'other':180})
        start=datetime(2026,10,31,1,59,59)
        for i in (0,1,2):
            self.engine.tick(Sample(start+timedelta(seconds=i),i,self.browser,'fixture'),'example.com')
        self.assertEqual([state.used for state in self.engine.states(start+timedelta(seconds=2))],[1,2])
        self.engine.flush()
        restored=Wellbeing(self.store,self.catalog,self.focus)
        self.assertEqual([state.used for state in restored.states(start+timedelta(seconds=2))],[1,2])
        self.catalog.settings=replace(self.catalog.settings,budget_reset_overrides={'web':240,'other':180})
        self.assertEqual([state.used for state in restored.states(start+timedelta(seconds=2))],[1,2])
        self.assertEqual([state.used for state in restored.states(start.replace(hour=4,minute=1))],[0,0])

    def test_game_and_shared_quota_renew_independently_without_changing_history(self):
        self.store.upsert([self.game]); self.catalog.games[self.game.id]=self.game
        self.catalog.settings=replace(self.settings,game_limits={self.game.id:600},
                                      budget_reset_overrides={'shared-games':120,'game:'+self.game.id:180})
        start=datetime(2026,10,31,1,59,59); end=start+timedelta(seconds=2)
        self.tracker._credit(self.game,start,end,2); self.tracker.flush()
        self.assertEqual(self.tracker.quota_totals(end)[self.game.id],1)
        self.assertEqual(self.tracker.game_quota_total(end,self.game.id),2)
        self.assertEqual(self.store.totals('2026-10-31')[self.game.id],2)
        restored=Tracker(self.store,self.catalog)
        self.assertEqual(restored.quota_totals(end)[self.game.id],1)
        self.assertEqual(restored.game_quota_total(end,self.game.id),2)

    def test_disabled_activity_rule_keeps_counting_for_later_reenable(self):
        rule=dict(self.settings.wellbeing_rules[0],enabled=False)
        self.catalog.settings=replace(self.settings,wellbeing_rules=[rule],budget_reset_overrides={'web':120})
        start=datetime(2026,10,31,2,0)
        for i in (0,1,2):
            self.engine.tick(Sample(start+timedelta(seconds=i),i,self.browser,'fixture'),'example.com')
        self.assertEqual(self.engine.states(start+timedelta(seconds=2)),[])
        self.catalog.settings=replace(self.catalog.settings,wellbeing_rules=[dict(rule,enabled=True)])
        self.assertEqual(self.engine.states(start+timedelta(seconds=2))[0].used,2)

    def test_break_landing_is_still_in_statistics_but_not_its_own_budget(self):
        other=dict(self.settings.wellbeing_rules[0],id='other',name='Other')
        self.catalog.settings=replace(self.settings,wellbeing_rules=[self.settings.wellbeing_rules[0],other],
                                      budget_reset_overrides={'web':120})
        start=datetime(2026,10,31,3,0)
        for i in (0,1,2):
            sample=Sample(start+timedelta(seconds=i),i,self.browser,'fixture')
            self.focus.tick(sample,'rest.example.com'); self.engine.tick(sample,'rest.example.com','web')
        self.focus.flush(); self.engine.flush()
        self.assertEqual([state.used for state in self.engine.states(sample.wall)],[0,2])
        self.assertEqual([state.rule['id'] for state in self.engine.states(sample.wall,self.engine.current[1],exclude='web')],['other'])
        self.assertEqual(sum(row[3] for row in self.focus.usage('2026-10-31') if row[0]=='site'),2)
        restored=Wellbeing(self.store,self.catalog,self.focus)
        self.assertEqual([state.used for state in restored.states(sample.wall)],[0,2])


if __name__=='__main__': unittest.main()
