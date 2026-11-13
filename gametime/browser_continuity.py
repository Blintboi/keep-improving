"""Import a browser's durable journal on the GUI thread, exactly once.

Native counters remain authoritative over their recorded intervals. Browser
records fill only uncovered time; receipts and imported counters commit together.
No provider credentials, URLs, titles or cross-device budgets enter this protocol.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import date,datetime
import hashlib
import json
import math
import ntpath
import re
import time

from .continuity_ledger import cover,uncovered
from .focus import BROWSERS,app_key,domain
from .website_identity import is_local_site,compatible_local_policy
from .tracker import day_slices
from .quota import budget_day,budget_minute
from .restriction_policy import target_steps,new_plan,legacy_active
from .wellbeing import applies,BudgetState
from .budget_access import usage_enabled
from . import __version__

IDENTITY=re.compile(r'[a-f0-9]{32}')


def identity(value): return isinstance(value,str) and bool(IDENTITY.fullmatch(value))
def instant(value): return type(value) in (int,float) and math.isfinite(value) and 0<value<4102444800
def wall(value): return datetime.fromtimestamp(value).astimezone()


class BrowserContinuity:
    def __init__(self,app):
        self.app=app; self.db=app.store.db; self.started=time.time(); self.safe_until=self.started
        self.db.execute('CREATE TABLE IF NOT EXISTS browser_journals (stream TEXT PRIMARY KEY,browser TEXT NOT NULL,seq INTEGER NOT NULL,end REAL NOT NULL)')
        self.paths={}; self.path_revision=None

    def sampled(self,sample): self.safe_until=max(self.safe_until,sample.wall.timestamp())

    def browser_path(self,browser):
        focus=self.app.focus; previous=focus.previous
        if previous and BROWSERS.get(ntpath.basename(previous[0].path).lower())==browser:
            self.paths[browser]=app_key(previous[0].path)
        if browser not in self.paths:
            paths=[r[0] for r in self.db.execute("SELECT key FROM activity_items WHERE kind='app'")]
            paths+=list(self.app.catalog.rules)
            self.paths[browser]=next((app_key(p) for p in paths if BROWSERS.get(ntpath.basename(p).lower())==browser),'')
        return self.paths[browser]

    def validate(self,data):
        if not isinstance(data,dict) or set(data)-{'local_version'}!={'version','stream','browser','records'} or data['version']!=1:
            raise ValueError('Invalid browser journal.')
        if type(data.get('local_version',0)) is not int or data.get('local_version',0) not in (0,1):raise ValueError('Invalid browser journal.')
        if not identity(data['stream']) or data['browser'] not in BROWSERS.values(): raise ValueError('Invalid browser journal.')
        records=data['records']
        if not isinstance(records,list) or len(records)>128: raise ValueError('Invalid browser journal.')
        prior_seq=None; prior_end=0
        for r in records:
            if not isinstance(r,dict) or type(r.get('seq')) is not int or r['seq']<1 or r['seq']>2**53-1: raise ValueError('Invalid browser journal.')
            if prior_seq is not None and r['seq']!=prior_seq+1: raise ValueError('Invalid browser journal order.')
            kind=r.get('kind')
            if kind=='sample':
                if set(r)!={'seq','kind','start','end','host','active','redirect','timer'}: raise ValueError('Invalid browser journal.')
                if not instant(r['start']) or not instant(r['end']) or not 0<r['end']-r['start']<=45.01: raise ValueError('Invalid browser journal interval.')
                if type(r['active']) is not bool or not isinstance(r['host'],str) or r['host'] and domain(r['host'])!=r['host']: raise ValueError('Invalid browser journal host.')
                if not isinstance(r['redirect'],str) or len(r['redirect'])>2100 or '\0' in r['redirect']: raise ValueError('Invalid browser journal.')
                if not isinstance(r['timer'],str) or r['timer'] and not identity(r['timer']): raise ValueError('Invalid browser timer.')
                start,end=r['start'],r['end']
            elif kind in ('focus.start','focus.pause','focus.stop'):
                if set(r)!={'seq','kind','at','base','token'} or not identity(r['base']) or not identity(r['token']) or not instant(r['at']): raise ValueError('Invalid browser timer command.')
                start=end=r['at']
            elif kind=='budget.state':
                if set(r)!={'seq','kind','at','key','day','fingerprint','state'} or not instant(r['at']): raise ValueError('Invalid browser budget state.')
                if not isinstance(r['key'],str) or len(r['key'])>64 or not isinstance(r['fingerprint'],str) or not re.fullmatch('[a-f0-9]{64}',r['fingerprint']): raise ValueError('Invalid browser budget state.')
                date.fromisoformat(r['day'])
                if not isinstance(r['state'],dict) or len(json.dumps(r['state']))>32768: raise ValueError('Invalid browser budget state.')
                start=end=r['at']
            else: raise ValueError('Invalid browser journal record.')
            if start<prior_end-.002 or end>time.time()+5: raise ValueError('Invalid browser journal time.')
            prior_seq,prior_end=r['seq'],end
        return records

    def exchange(self,data):
        records=self.validate(data); app=self.app; focus=app.focus; wellbeing=app.wellbeing
        stream,browser=data['stream'],data['browser']
        row=self.db.execute('SELECT browser,seq,end FROM browser_journals WHERE stream=?',(stream,)).fetchone()
        if row and row[0]!=browser: raise ValueError('Browser journal identity changed.')
        if not row and self.db.execute('SELECT COUNT(*) FROM browser_journals').fetchone()[0]>=64: raise ValueError('Too many paired browser journals.')
        seq,end=(row[1],row[2]) if row else (0,0)
        fresh=[r for r in records if r['seq']>seq]
        if fresh and fresh[0]['seq']!=seq+1: raise ValueError('Browser journal has a missing record.')
        if fresh and fresh[0].get('start',fresh[0].get('at'))<end-.002: raise ValueError('Browser journal time moved backwards.')
        # Flush both native ledgers before acknowledging their covered time.
        # A record extending beyond the most recent native sample stays queued.
        focus.flush(); wellbeing.configure(wall(self.safe_until)); wellbeing.flush()
        path=self.browser_path(browser); rejected=False; imported=0; timer_changed=False; budgets_changed=set()
        saved={key:deepcopy(getattr(focus,key)) for key in ('phase','remaining','round','running','continuity_running','continuity_token','completed_rounds','_daily_completed','last_awake','timer_last_wall','notice','_dirty','started_on')}
        try:
            with self.db:
                for r in fresh:
                    finish=r.get('end',r.get('at'))
                    if finish>self.safe_until: break
                    if r['kind']=='sample':
                        if path and r['active'] and focus.settings.tracking and not focus.settings.app_excluded(path):
                            imported+=self.credit_activity(r,path)
                        timer_changed=self.credit_timer(r) or timer_changed
                    elif r['kind']=='budget.state':
                        if self.import_budget(r): budgets_changed.add(r['key'])
                    elif r['base']==focus.continuity_token:
                        if r['kind']=='focus.stop':
                            focus.phase='focus'; focus.remaining=focus.settings.work*60; focus.round=0
                        elif r['kind']=='focus.start' and focus.finished:
                            focus.remaining=focus.settings.work*60; focus.round=0
                        focus.running=focus.continuity_running=r['kind']=='focus.start'
                        focus.continuity_token=r['token']; focus.notice=''; focus._dirty=True
                        timer_changed=True
                    else: rejected=True
                    seq,end=r['seq'],finish
                focus.save_timer()
                self.db.execute('INSERT OR REPLACE INTO browser_journals VALUES (?,?,?,?)',(stream,browser,seq,end))
        except Exception:
            for key,value in saved.items(): setattr(focus,key,value)
            raise
        focus.timer_coverage.kind='timer:'+focus.continuity_token
        for key in budgets_changed:
            app.restrictions.state.rows.pop(key,None);app.restrictions.state.days.pop(key,None)
        if focus.running and timer_changed:
            focus.last_awake=app.focus_awake(); focus.timer_last_wall=datetime.now().astimezone()
        focus._dirty=False
        if imported:
            focus.revision+=1; wellbeing.day=None; wellbeing.source=None
            wellbeing.periods.cache.clear(); wellbeing.custom_markers.clear()
            app.store.statistics_revision=getattr(app.store,'statistics_revision',0)+1
            if hasattr(app,'schedule_statistics_event'): app.schedule_statistics_event(60)
        # Browser has already presented natural timer transitions while offline.
        if focus.notice and focus.notice!=saved['notice']: app._focus_notice=focus.notice
        local_version=data.get('local_version',0)
        snapshot=self.snapshot(browser,local_version)
        app.update_focus_policy()
        bridge=getattr(app,'browser_bridge',None)
        if bridge:
            with bridge.lock: policy=deepcopy(bridge.current_policy)
        else: policy=None
        return dict(ack=seq,rejected_commands=rejected,snapshot=snapshot,policy=compatible_local_policy(policy,local_version))

    def credit_activity(self,r,path):
        focus=self.app.focus; settings=self.app.settings
        total=0; reserve=[(self.started,self.safe_until)]
        for kind in ('activity','wellbeing'):
            for start,end in uncovered(self.db,kind,r['start'],r['end'],reserve):
                host=r['host']; seconds=end-start
                if kind=='activity':
                    from .activity_sessions import record
                    since=float(self.db.execute("SELECT value FROM settings WHERE key='sessions_since'").fetchone()[0])
                    session_start=max(start,since)
                    for category,key,name in [('app',path,ntpath.basename(path))]+([('site',host,host)] if host else []):
                        record(self.db,category,key,session_start,end,focus.day(wall(session_start)))
                        self.db.execute('INSERT OR IGNORE INTO activity_items VALUES (?,?,?)',(category,key,name))
                        for day,amount in day_slices(wall(start),wall(end),seconds,focus.day_start_minute):
                            self.db.execute('INSERT INTO activity_usage VALUES (?,?,?,?) ON CONFLICT(day,kind,key) DO UPDATE SET seconds=seconds+excluded.seconds',(day,category,key,amount))
                            if day<focus.started_on:
                                focus.started_on=day;focus._save('activity_started_on',day)
                    total+=seconds
                    if not host:record(self.db,'browser','other',session_start,end,focus.day(wall(session_start)))
                else:
                    redirect=r['redirect']
                    # A redirect exclusion is accepted only for an existing
                    # configured redirect rule, never an arbitrary budget key.
                    plan=settings.restriction_plans.get(redirect,{})
                    valid=any(s.get('break_mode')=='redirect' or any(o.get('break_mode')=='redirect' for o in s.get('targets',{}).values()) for s in plan.get('steps',()))
                    atom=('',path,host+('\0'+redirect if redirect and valid else ''))
                    for day,amount in day_slices(wall(start),wall(end),seconds,settings.budget_reset_minute):
                        self.db.execute('INSERT INTO wellbeing_usage VALUES (?,?,?,?,?) ON CONFLICT(day,game_id,app,site) DO UPDATE SET seconds=seconds+excluded.seconds',(day,*atom,amount))
                    for key,minute in settings.budget_reset_overrides.items():
                        if key not in self.app.wellbeing.periods.clocks: continue
                        for day,amount in day_slices(wall(start),wall(end),seconds,minute):
                            self.db.execute('INSERT INTO independent_budget_usage VALUES (?,?,?,?) ON CONFLICT(budget,day,item) DO UPDATE SET seconds=seconds+excluded.seconds',(key,day,json.dumps(atom,ensure_ascii=False),amount))
                cover(self.db,kind,start,end)
        return total

    def credit_timer(self,r):
        focus=self.app.focus
        if r['timer']!=focus.continuity_token or not (focus.running or focus.continuity_running): return
        kind='timer:'+focus.continuity_token
        # A live desktop already advances this timer; a restarted desktop has
        # a paused checkpoint until the browser returns its missing intervals.
        changed=False
        for start,end in uncovered(self.db,kind,r['start'],r['end']):
            if not focus.continuity_running: break
            focus.running=True
            cursor=start
            while cursor<end and focus.running:
                amount=min(end-cursor,focus.remaining) if focus.remaining>0 else end-cursor
                focus.last_awake=0
                focus.advance(amount,wall(cursor+amount),persist=False,record=False)
                cursor+=amount
                if amount<=0: break
            focus.continuity_running=focus.running
            cover(self.db,kind,start,end)
            changed=True
        return changed

    def import_budget(self,r):
        settings=self.app.settings;key=r['key']
        if not any(rule['id']==key for rule in settings.wellbeing_rules): return False
        plan=settings.restriction_plans.get(key,new_plan())
        if self.fingerprint(plan)!=r['fingerprint']: return False
        incoming=r['state'];steps={s['id']:s for s in target_steps(plan,'site:')}
        if set(incoming)-{'expired','used_extension','grant','delivered','breaks'}: raise ValueError('Invalid browser budget state.')
        if type(incoming.get('used_extension')) is not bool or not isinstance(incoming.get('delivered'),list) or len(incoming['delivered'])>44: raise ValueError('Invalid browser budget state.')
        if any(key not in steps or steps[key]['kind']!='notify' for key in incoming['delivered']): raise ValueError('Invalid browser warning receipt.')
        raw=self.db.execute('SELECT value FROM restriction_state WHERE day=? AND budget=?',(r['day'],key)).fetchone()
        row=json.loads(raw[0]) if raw else dict(expired=None,used_extension=False,grant=None,delivered=[],plan=json.dumps(plan,sort_keys=True))
        expired=incoming.get('expired')
        if expired is not None and (not instant(expired) or expired>r['at']): raise ValueError('Invalid browser expiry.')
        if expired is not None: row['expired']=min(row.get('expired') or expired,expired)
        row['delivered']=sorted(set(row['delivered'])|set(incoming['delivered']))
        breaks=incoming.get('breaks',{})
        if not isinstance(breaks,dict) or len(breaks)>44: raise ValueError('Invalid browser breaks.')
        for step_id,state in breaks.items():
            spec=steps.get(step_id)
            if not spec or spec['kind']!='break' or not isinstance(state,dict) or set(state)-{'next_at','until','clock_day','triggered'}: raise ValueError('Invalid browser break.')
            until=state.get('until');next_at=state.get('next_at')
            if until is not None and (not instant(until) or until>r['at']+spec['break_minutes']*60+1): raise ValueError('Invalid browser break deadline.')
            if type(next_at) not in (int,float) or not math.isfinite(next_at) or not 0<=next_at<=86400*8: raise ValueError('Invalid browser break threshold.')
            if 'triggered' in state and type(state['triggered']) is not bool: raise ValueError('Invalid browser break.')
            if 'clock_day' in state: date.fromisoformat(state['clock_day'])
            old=row.setdefault('breaks',{}).get(step_id,{})
            # Newer acknowledged states may finish a break; an old packet cannot
            # replace a currently later deadline from the desktop.
            if (old.get('until') or 0)>r['at'] and (old.get('until') or 0)>(until or 0): continue
            row['breaks'][step_id]=dict(state,spec=json.dumps(spec,sort_keys=True))
        grant=incoming.get('grant')
        if grant is not None:
            if not isinstance(grant,dict) or set(grant)-{'subject','until','carried','prior_used'} or not isinstance(grant.get('subject'),str): raise ValueError('Invalid browser allowance.')
            kind,_,tail=grant['subject'].partition(':');host,_,token=tail.rpartition(':')
            if kind!='site' or domain(host)!=host or not identity(token): raise ValueError('Invalid browser allowance.')
            minutes=max((s.get('extension_minutes',plan['extension_minutes']) for s in steps.values()),default=0)
            if not instant(grant.get('until')) or grant['until']>r['at']+minutes*60+1: raise ValueError('Invalid browser allowance deadline.')
            if incoming['used_extension'] and not row['used_extension']: row['grant']={'subject':grant['subject'],'until':grant['until']}
        row['used_extension'] |= incoming['used_extension']
        self.db.execute('INSERT OR REPLACE INTO restriction_state VALUES (?,?,?)',(r['day'],key,json.dumps(row,separators=(',',':'))))
        return True

    @staticmethod
    def fingerprint(plan): return hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()

    def snapshot(self,browser,local_version=1):
        app=self.app; f=app.focus; now=datetime.now().astimezone(); path=self.browser_path(browser)
        app.restrictions.prepare(now); budgets=[]
        app.wellbeing.configure(now)
        from .device_sharing import remote_seconds
        from .device_scopes import applies as selected
        states=[BudgetState(rule,app.wellbeing.totals.get(rule['id'],0)+remote_seconds(app.store,app.settings,rule['id'],now),usage_enabled(app.settings,rule['id'])) for rule in app.settings.wellbeing_rules if rule['enabled'] and selected(app.settings.budget_devices.get(rule['id']),app.settings)]
        for state in states:
            rule=state.rule; key=rule['id']; plan=deepcopy(app.settings.restriction_plans.get(key,new_plan()))
            members=[m for m in rule['members'] if local_version or m['kind']!='site' or not is_local_site(m['value'])]
            if not any(m['kind']=='site' or m=={'kind':'category','value':'sites'} for m in members) and not applies(members,('',path,'')): continue
            runtime=deepcopy(app.restrictions.state.rows.get(key,{}))
            budget=app.restrictions.state.budgets.get(key)
            visit=None
            if budget and any(s.get('time_mode')=='sessions' and not s.get('session_choice') for s in plan['steps']):
                # Seed the last measured visit so handing over to the browser
                # does not manufacture a new session in the same foreground tab.
                rows=list(self.db.execute("SELECT kind,key,start,finish FROM activity_sessions WHERE finish>=? AND kind IN ('app','site')",(now.timestamp()-3,)))
                rows+=list(f.sessions.pending)
                app_member=applies(members,('',path,''))
                candidates=[r for r in rows if (r[0]=='app' and r[1]==path if app_member else r[0]=='site' and applies(members,('','',r[1])))]
                if candidates:
                    last=max(candidates,key=lambda r:r[3]);finish=last[3]
                    if f.previous and app_key(f.previous[0].path)==path and (app_member or f.previous[1]==last[1]) and f.previous[0].interactive:
                        finish=now.timestamp()
                    visit=dict(key=last[0]+':'+last[1],finish=finish)
            budgets.append(dict(id=key,name=rule['name'],members=members,seconds=rule['seconds'],used=state.used,
                sessions=budget.sessions if budget else 0,session_visit=visit,
                usage=state.usage_limit,days=app.settings.budget_active_days.get(key,list(range(7))),
                renewal=budget_minute(app.settings,key),day=budget_day(app.settings,key,now).isoformat(),
                enforce=rule['enforce'] and legacy_active(app.settings.restriction_plans,key),
                steps=target_steps(plan,'site:'),extension_minutes=plan['extension_minutes'],fingerprint=self.fingerprint(plan),runtime=runtime))
        all_sites,sites=f.settings.site_rules(app.settings.wellbeing_rules)
        if not local_version:sites=[s for s in sites if not is_local_site(s)]
        from .website_identity import configured_local_sites
        port=getattr(getattr(app,'browser_bridge',None),'port',47853)
        return dict(version=1,app_version=__version__,at=now.timestamp(),language=app.settings.language,
            local_sites=configured_local_sites(app.settings,f.settings,port) if local_version else [],bridge_port=port,
            browser=browser,path=path,tracking=f.settings.tracking and bool(path) and not f.settings.app_excluded(path),
            idle_timeout_seconds=app.settings.idle_timeout_seconds if app.settings.pause_when_idle else 0,
            media_prevents_idle=app.settings.media_prevents_idle,
            day_start=app.settings.budget_reset_minute,sound=app.settings.notification_sound!='silent',budgets=budgets,
            focus=dict(token=f.continuity_token,running=f.running,phase=f.phase,remaining=f.remaining,round=f.round,
                total=f.completed_rounds,today=f.completed_on(f.day(now)),day=f.day(now).isoformat(),settings=asdict(f.settings),
                all=all_sites or bool(path and f.settings.app_blocked(path,'',app.settings.wellbeing_rules)),domains=sites))
