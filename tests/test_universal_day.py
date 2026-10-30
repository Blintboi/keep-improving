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


if __name__=='__main__': unittest.main()
