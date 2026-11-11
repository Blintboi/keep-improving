"""Versioned, local restriction plans and a durable once-per-period save allowance.

No Windows or UI dependencies. Notifications are events; restrictions are states.
"""
from dataclasses import dataclass
from datetime import date,timedelta
from urllib.parse import urlsplit
import json
import math
import re

KINDS = ('notify', 'minimize', 'cover', 'close', 'break', 'restrict')
RANK = {'redirect': 0, 'minimize': 1, 'cover': 2, 'close': 3}


def target_steps(plan, subject=None):
    """Project independently configured targets; old steps keep their identity."""
    scopes=('app','site') if subject is None else ('site',) if subject.startswith('site:') else ('app',)
    result=[]
    for original in plan['steps']:
        if 'targets' not in original:
            result.append(original); continue
        for scope in scopes:
            options=original['targets'].get(scope,{})
            if not options.get('enabled',True): continue
            item={k:v for k,v in original.items() if k!='targets'}
            item['id']=scope+':'+item['id']
            item.update({k:v for k,v in options.items() if k not in ('enabled','mode')})
            if original['kind'] not in ('notify','break') and 'mode' in options: item['kind']=options['mode']
            if scope=='site':
                if item['kind'] in ('minimize','restrict'): item['kind']='cover'
                if item.get('break_mode')=='minimize': item['break_mode']='cover'
            elif item.get('break_mode')=='redirect': item['break_mode']='cover'
            if item.get('break_mode')!='redirect' and item['kind']!='redirect': item.pop('redirect_url',None)
            else: item.setdefault('redirect_url','')
            result.append(item)
    return result


def validate_targets(item):
    targets=item['targets']
    if not isinstance(targets,dict) or not targets or set(targets)-{'app','site'}: raise ValueError('Invalid restriction plan.')
    for scope,options in targets.items():
        allowed={'enabled','extension_minutes'}
        if item['kind']=='notify': allowed={'enabled','sound','popup'}
        elif item['kind']=='break': allowed|={'break_mode','break_minutes','redirect_url'}
        else: allowed|={'mode','redirect_url'}
        if not isinstance(options,dict) or set(options)-allowed: raise ValueError('Invalid restriction plan.')
        for key in ('enabled','sound','popup'):
            if key in options and type(options[key]) is not bool: raise ValueError('Invalid restriction plan.')
        for key,low,high in (('extension_minutes',0,60),('break_minutes',1,1440)):
            if key in options and (type(options[key]) is not int or not low<=options[key]<=high): raise ValueError('Invalid restriction plan.')
        mode=options.get('break_mode',options.get('mode'))
        modes={'minimize','cover','close'} if scope=='app' else {'cover','close','redirect'}
        if item['kind']!='break' and scope=='app': modes.add('restrict')
        if mode is not None and (not isinstance(mode,str) or mode not in modes): raise ValueError('Invalid restriction plan.')
        if 'redirect_url' in options: redirect_url(options['redirect_url'])
        if options.get('enabled',True) and item['kind']=='notify' and not any(options.get(k,item[k]) for k in ('sound','popup')):
            raise ValueError('Choose a sound or popup for each warning.')


def redirect_url(value):
    if value == '': return value
    if not isinstance(value,str) or not value or len(value.encode('utf-8',errors='replace'))>400 or value!=value.strip() or '\\' in value or any(ord(c)<32 for c in value):
        raise ValueError('Enter a valid http or https address for the break.')
    try:
        url=urlsplit(value)
        if url.scheme.lower() not in ('http','https') or not url.hostname or url.username is not None or url.password is not None:
            raise ValueError()
        url.port
        host=url.hostname.encode('idna').decode('ascii')
        if any(c in host for c in ' %/#?'): raise ValueError()
    except (ValueError,UnicodeError):
        raise ValueError('Enter a valid http or https address for the break.') from None
    return value


def validate_plans(plans):
    if not isinstance(plans, dict) or len(plans) > 2200:
        raise ValueError('Invalid restriction plan.')
    for key, plan in plans.items():
        if not isinstance(key, str) or not key or len(key) > 2100 or '\0' in key:
            raise ValueError('Invalid restriction plan.')
        required={'version', 'steps', 'extension_minutes', 'close_confirmed'}
        if (not isinstance(plan, dict) or set(plan) not in (required, required|{'legacy','legacy_warning'}, required|{'legacy','legacy_warning','legacy_enforce'})
                or type(plan['version']) is not int or plan['version'] != 1
                or ('legacy' in plan and (plan['legacy'] is not True or type(plan['legacy_warning']) is not bool))
                or ('legacy_enforce' in plan and type(plan['legacy_enforce']) is not bool)
                or type(plan['extension_minutes']) is not int or not 0 <= plan['extension_minutes'] <= 60
                or type(plan['close_confirmed']) is not bool
                or not isinstance(plan['steps'], list) or len(plan['steps']) > 22
                or sum(not isinstance(s,dict) or s.get('id') not in ('legacy-warning','legacy-limit') for s in plan['steps'])>20):
            raise ValueError('Invalid restriction plan.')
        seen = set()
        for step in plan['steps']:
            if (not isinstance(step, dict) or set(step)-{'targets','clock_minute','session_choice','allow_early_break'} not in ({'id', 'kind', 'offset', 'sound', 'popup'}, {'id', 'kind', 'offset', 'sound', 'popup', 'time_mode'}, {'id', 'kind', 'offset', 'sound', 'popup', 'time_mode', 'break_mode', 'break_minutes'}, {'id', 'kind', 'offset', 'sound', 'popup', 'time_mode', 'break_mode', 'break_minutes', 'redirect_url'})
                    or not isinstance(step['id'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', step['id'])
                    or step['id'] in seen or step['kind'] not in KINDS
                    or type(step['offset']) not in (float, int) or not math.isfinite(step['offset'])
                    or not -86400 <= step['offset'] <= 86400
                    or ('time_mode' in step and (step['time_mode'] not in ('usage','clock','sessions') or step['offset'] < 0))
                    or any(type(step[k]) is not bool for k in ('sound', 'popup'))):
                raise ValueError('Invalid restriction plan.')
            if step.get('time_mode')=='sessions' and (type(step['offset']) is not int or not 1<=step['offset']<=10000):
                raise ValueError('Choose a session limit between 1 and 10000.')
            if 'allow_early_break' in step and (type(step['allow_early_break']) is not bool or step['kind']!='break' or step.get('time_mode')!='usage'):
                raise ValueError('Early breaks require a repeating usage interval.')
            if 'session_choice' in step:
                from .session_choices import validate
                if step.get('time_mode') != 'sessions': raise ValueError('Opening choices require a daily session limit.')
                validate(step['session_choice'])
            if step.get('time_mode')=='clock':
                if type(step.get('clock_minute')) is not int or not 0<=step['clock_minute']<1440:
                    raise ValueError('Choose a valid daily action time.')
            elif 'clock_minute' in step: raise ValueError('Invalid restriction plan.')
            if step['kind']=='break':
                if (set(step)-{'targets','clock_minute','session_choice','allow_early_break'} not in ({'id','kind','offset','sound','popup','time_mode','break_mode','break_minutes'}, {'id','kind','offset','sound','popup','time_mode','break_mode','break_minutes','redirect_url'})
                        or step['time_mode'] not in ('usage','clock','sessions') or step['time_mode']=='usage' and step['offset']<=0
                        or not isinstance(step['break_mode'],str) or step['break_mode'] not in RANK or type(step['break_minutes']) is not int
                        or not 1<=step['break_minutes']<=1440):
                    raise ValueError('Invalid restriction plan.')
                if step['break_mode']=='redirect': redirect_url(step.get('redirect_url'))
                elif 'redirect_url' in step: raise ValueError('Invalid restriction plan.')
            elif 'break_mode' in step or 'break_minutes' in step or 'redirect_url' in step:
                raise ValueError('Invalid restriction plan.')
            if 'targets' in step: validate_targets(step)
            seen.add(step['id'])
            if step['kind'] == 'notify' and not (step['sound'] or step['popup']):
                raise ValueError('Choose a sound or popup for each warning.')
            if step.get('time_mode') != 'usage' and step['kind'] != 'notify' and step['offset'] < 0:
                raise ValueError('Restrictions start at or after the limit.')
        closing=any(s['kind'] in ('close','restrict') or s['kind']=='break' and s['break_mode']=='close'
                    or s['kind'] in ('cover','minimize') and s.get('extension_minutes',plan['extension_minutes'])>0
                    for s in target_steps(plan) if not s.get('session_choice'))
        if closing and not plan['close_confirmed']:
            raise ValueError('Confirm that unsaved work may be lost.')
    return plans


def new_plan(*,legacy=False):
    value={'version': 1, 'steps': [], 'extension_minutes': 0, 'close_confirmed': False}
    if legacy: value.update(legacy=True,legacy_warning=True)
    return value


def legacy_active(plans,key):
    return key not in plans or plans[key].get('legacy') is True


def legacy_warning_active(plans,key):
    return legacy_active(plans,key) and plans.get(key,{}).get('legacy_warning',True)


def legacy_restriction_active(plans,key):
    return legacy_active(plans,key) and plans.get(key,{}).get('legacy_enforce',True)


def merge_breaks(current,previous):
    for identity,value in previous.get('breaks',{}).items():
        states=current.setdefault('breaks',{}); existing=states.get(identity)
        if existing is None or (value.get('until') or 0)>(existing.get('until') or 0):
            states[identity]=value
        elif value.get('until') is None and existing.get('until') is None:
            existing['next_at']=max(existing.get('next_at',0),value.get('next_at',0))


def remap_state(db, old, new):
    """Keep one-time rights consumed when discovery merges a manual game."""
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_choices'").fetchone():
        activity='activity' in {r[1] for r in db.execute('PRAGMA table_info(session_choices)')}
        db.execute('INSERT OR IGNORE INTO session_choices SELECT ?,step,day,visit,choice,at'+(',activity' if activity else '')+' FROM session_choices WHERE budget=?',(new,old))
        db.execute('DELETE FROM session_choices WHERE budget=?',(old,))
        if activity: db.execute('UPDATE session_choices SET activity=? WHERE activity=?',(new,old))
    for day, raw in db.execute('SELECT day,value FROM restriction_state WHERE budget=?',(old,)).fetchall():
        value=json.loads(raw)
        existing=db.execute('SELECT value FROM restriction_state WHERE day=? AND budget=?',(day,new)).fetchone()
        if existing:
            current=json.loads(existing[0])
            current['used_extension'] |= value['used_extension']
            merge_breaks(current,value)
            current['delivered']=sorted(set(current['delivered'])|set(value['delivered']))
            if value['grant'] and (not current['grant'] or value['grant']['until']<current['grant']['until']):
                current['grant']=value['grant']
            value=current
        db.execute('INSERT OR REPLACE INTO restriction_state VALUES (?,?,?)',(day,new,json.dumps(value)))
    db.execute('DELETE FROM restriction_state WHERE budget=?',(old,))


def step(kind, offset=0, *, sound=False, popup=False, identity=None, usage=False, break_mode='minimize', break_minutes=5):
    import uuid
    result=dict(id=identity or uuid.uuid4().hex, kind=kind, offset=offset, sound=sound, popup=popup)
    if usage: result['time_mode']='usage'
    if kind=='break': result.update(time_mode='usage',break_mode=break_mode,break_minutes=break_minutes)
    return result


@dataclass(frozen=True)
class Budget:
    key: str
    name: str
    limit: float
    used: float
    members: tuple
    breaks_allowed: bool = True
    day: str | None = None
    clock_deadlines: dict | None = None
    sessions: int = 0


class RestrictionState:
    def __init__(self, store):
        self.db = store.db
        self.db.execute('CREATE TABLE IF NOT EXISTS restriction_state (day TEXT NOT NULL, '
                        'budget TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(day,budget))')
        self.day = None
        self.days = {}
        self.rows = {}
        self.budgets = {}
        self.plans = {}
        self.now = 0

    def _save(self, key):
        self.db.execute('INSERT OR REPLACE INTO restriction_state VALUES (?,?,?)',
                        (self.days.get(key, self.day), key, json.dumps(self.rows[key], separators=(',', ':'))))

    def update(self, day, now, budgets, plans):
        self.day = day
        self.now = now
        budgets = tuple(budgets)
        plans = dict(plans)
        # Zero is an explicit access block, even without configured actions.
        # Keep this implicit plan out of the user's saved action list.
        for budget in budgets:
            if budget.limit == 0: plans.setdefault(budget.key, new_plan())
        self.budgets = {b.key: b for b in budgets if b.key in plans}
        self.plans = plans
        with self.db:
            for key in self.rows.keys() | self.budgets.keys():
                budget = self.budgets.get(key)
                budget_day = budget.day if budget and budget.day else day
                changed_day = self.days.get(key) != budget_day
                if changed_day:
                    self.days[key] = budget_day
                    raw = self.db.execute('SELECT value FROM restriction_state WHERE day=? AND budget=?',
                                          (budget_day,key)).fetchone()
                    if raw: self.rows[key] = json.loads(raw[0])
                    else: self.rows.pop(key,None)
                before = json.dumps(self.rows.get(key))
                if changed_day and key in self.budgets:
                    # An explicitly granted save interval may cross renewal;
                    # application grants identify the exact original process.
                    today=date.fromisoformat(budget_day)
                    low=(today-timedelta(days=2)).isoformat(); high=(today+timedelta(days=2)).isoformat()
                    prior=self.db.execute('SELECT day,value FROM restriction_state WHERE day>=? AND day<=? AND day!=? AND budget=? ORDER BY day DESC',
                                          (low,high,budget_day,key)).fetchall()
                    for old_day,raw in prior:
                        previous=json.loads(raw); grant=previous.get('grant')
                        if not isinstance(grant,dict): continue
                        subject=grant.get('subject',''); until=grant.get('until',0)
                        app_grant=bool(grant.get('identity') and subject.startswith('app:') and until>=now-86400)
                        site_grant=bool(subject.startswith('site:') and until>now)
                        if not (app_grant or site_grant) or previous.get('plan')!=json.dumps(plans.get(key),sort_keys=True): continue
                        row=self.rows.setdefault(key,{'expired':None,'used_extension':False,'grant':None,'delivered':[]})
                        if not row.get('grant'):
                            grant=dict(grant,carried=True,prior_used=row['used_extension'])
                            row['grant']=grant; row['used_extension']=True
                            row['plan']=previous['plan']
                            previous['grant']=None
                            self.db.execute('UPDATE restriction_state SET value=? WHERE day=? AND budget=?',
                                            (json.dumps(previous,separators=(',',':')),old_day,key))
                        break
                if (changed_day and key in self.budgets
                        and any(s['kind']=='break' for s in plans[key]['steps'])):
                    # A break lasts at most 24 hours; include two neighboring
                    # logical days for DST and clock corrections while closed.
                    today=date.fromisoformat(budget_day)
                    low=(today-timedelta(days=2)).isoformat(); high=(today+timedelta(days=2)).isoformat()
                    prior=self.db.execute('SELECT value FROM restriction_state WHERE day>=? AND day<=? AND day!=? AND budget=?',
                                          (low,high,budget_day,key)).fetchall()
                    specs={item['id']:json.dumps(item,sort_keys=True) for item in target_steps(plans[key]) if item['kind']=='break'}
                    for raw, in prior:
                        carried={identity:state for identity,state in json.loads(raw).get('breaks',{}).items()
                                 if state.get('until') is not None and state['until']>now and state.get('spec')==specs.get(identity)}
                        if carried:
                            row=self.rows.setdefault(key,{'expired':None,'used_extension':False,'grant':None,'delivered':[]})
                            merge_breaks(row,{'breaks':carried})
                row = self.rows.setdefault(key, {'expired': None, 'used_extension': False,
                                                'grant': None, 'delivered': []})
                signature = json.dumps(plans.get(key), sort_keys=True)
                if row.get('plan') != signature:
                    row['grant'] = None
                    row['plan'] = signature
                saved=row.get('grant') or {}
                if saved.get('carried') and saved.get('subject','').startswith('site:') and now>=saved.get('until',0):
                    row['used_extension']=saved.get('prior_used',False); row['grant']=None
                if not budget or budget.used < budget.limit:
                    row['expired'] = None
                elif row['expired'] is None:
                    row['expired'] = now
                if budget:
                    self.update_breaks(key,budget,now)
                else:
                    row.pop('breaks',None)
                # Absolute-use restrictions can start before the budget limit.
                # A regular restriction has priority over a simultaneous break.
                grant=row.get('grant') or {}
                promised=bool(grant.get('carried') or grant.get('break_close'))
                if not budget or budget.limit == 0 or not promised and not any(s['kind'] in ('cover','minimize','restrict','close') for s in self.due(key)):
                    row['grant'] = None
                if before != json.dumps(row): self._save(key)

    def update_breaks(self,key,budget,now):
        row=self.rows[key]; steps=[s for s in target_steps(self.plans[key]) if s['kind']=='break' and not s.get('session_choice')]
        if not steps:
            row.pop('breaks',None); return
        states=row.setdefault('breaks',{})
        valid={s['id'] for s in steps}
        for identity in list(states):
            if identity not in valid: states.pop(identity)
        for item in steps:
            spec=json.dumps(item,sort_keys=True); state=states.get(item['id'])
            if not state or state.get('spec')!=spec:
                state={'spec':spec,'next_at':item['offset'],'until':None}; states[item['id']]=state
            if item.get('time_mode')=='clock':
                deadline=(budget.clock_deadlines or {}).get(item['clock_minute'])
                if state.get('until') is not None and now>=state['until']: state['until']=None
                if deadline is not None and state.get('clock_day')!=self.days[key]:
                    state['clock_day']=self.days[key]; state['triggered']=False
                    if state.get('until') is not None and state['until']>=deadline: state['triggered']=True
                if deadline is not None and not state.get('triggered') and now>=deadline:
                    state['triggered']=True
                    until=deadline+item['break_minutes']*60
                    if budget.breaks_allowed and budget.used<budget.limit and now<until:
                        state['until']=max(state.get('until') or 0,until)
                continue
            if state['until'] is not None and now>=state['until']:
                state.update(until=None,next_at=(budget.sessions if item.get('time_mode')=='sessions' else budget.used)+item['offset'])
            if item.get('time_mode')=='sessions':
                if state['until'] is None and budget.breaks_allowed and budget.used<budget.limit and budget.sessions>state['next_at']:
                    state['until']=now+item['break_minutes']*60
                continue
            # A scheduled break belongs inside the allowance: expiry wins
            # when the next threshold is at or beyond the budget limit.
            if (state['until'] is None and budget.breaks_allowed and state['next_at']<budget.limit
                    and state['next_at']<=budget.used<budget.limit):
                state['until']=now+item['break_minutes']*60

    def break_remaining(self,key,subject=None):
        row=self.rows.get(key,{})
        selected={s['id'] for s in target_steps(self.plans[key],subject)} if subject is not None and key in self.plans else None
        return max((state['until']-self.now for identity,state in row.get('breaks',{}).items() if selected is None or identity in selected
                    if state.get('until') is not None and state['until']>self.now),default=0)

    def early_break_steps(self,key):
        """Available saved breaks, independent of the foreground application."""
        budget=self.budgets.get(key);row=self.rows.get(key,{})
        if (not budget or not budget.breaks_allowed or budget.used>=budget.limit
                or self.break_remaining(key)>0 or self.has_restriction(key)
                or (row.get('grant') or {}).get('until',0)>self.now): return []
        return [s for s in target_steps(self.plans[key])
                if s['kind']=='break' and s.get('time_mode')=='usage' and s.get('allow_early_break')]

    def start_early_break(self,key,identity):
        """Start the whole configured break; its normal expiry resets the interval."""
        selected=[s for s in self.early_break_steps(key) if s['id'].split(':')[-1]==identity]
        if not selected: return False
        row=self.rows[key]
        with self.db:
            for item in selected:
                state=row['breaks'][item['id']]
                state['until']=self.now+item['break_minutes']*60
            self._save(key)
        return True

    def due(self, key, subject=None):
        budget = self.budgets.get(key)
        if not budget: return []
        row = self.rows[key]
        return [s for s in target_steps(self.plans[key],subject) if not s.get('session_choice') and (
                (s['kind']=='break' and row.get('breaks',{}).get(s['id'],{}).get('until') is not None and row['breaks'][s['id']]['until']>self.now) or
                (s['kind']!='break' and s.get('time_mode')=='clock' and self.now >= (budget.clock_deadlines or {}).get(s['clock_minute'],math.inf)) or
                (s['kind']!='break' and s.get('time_mode')=='usage' and budget.used >= s['offset']) or
                (s['kind']!='break' and s.get('time_mode')=='sessions' and budget.sessions > s['offset']) or
                (s['kind']!='break' and 'time_mode' not in s and s['offset'] <= 0 and budget.used >= max(0, budget.limit + s['offset'])) or
                (s['kind']!='break' and 'time_mode' not in s and s['offset'] > 0 and row['expired'] is not None and self.now >= row['expired'] + s['offset']))]

    def grant(self, key, subject, identity=None):
        row = self.rows.get(key, {})
        grant = row.get('grant')
        return grant if grant and grant['subject'] == subject and key in self.budgets and (identity is None or not grant.get('identity') or grant['identity']==identity) else None

    def action(self, key, subject, identity=None):
        if key not in self.budgets: return ''
        if self.zero_budget(key): return 'cover'
        grant = self.grant(key, subject, identity)
        if grant:
            if self.now < grant['until']: return ''
            return 'cover' if subject.startswith('site:') else 'close'
        due=self.due(key,subject)
        regular=[s for s in due if s['kind'] not in ('notify','break')]
        selected=regular if regular else [s for s in due if s['kind']=='break']
        minutes=self.save_minutes(key,subject)
        restrict_mode=('close' if subject.startswith('app:') and
                       (not minutes or self.rows[key]['used_extension']) else 'cover')
        kinds = [s['break_mode'] if s['kind']=='break' else restrict_mode if s['kind']=='restrict' else s['kind'] for s in selected]
        # A mixed budget pauses native applications too; only browser tabs can
        # navigate. Resolve per-target behavior before comparing overlapping breaks.
        if subject.startswith('app:'):
            kinds = ['cover' if kind=='redirect' else kind for kind in kinds]
            if minutes and not self.rows[key]['used_extension']:
                kinds = ['cover' if kind=='close' else kind for kind in kinds]
        return max(kinds, key=RANK.get) if kinds else ''

    def has_restriction(self,key,subject=None,identity=None):
        if self.zero_budget(key): return True
        if any(step['kind'] not in ('notify','break') for step in self.due(key,subject)): return True
        grant=self.grant(key,subject,identity) if subject is not None else None
        return bool(grant and (grant.get('carried') or grant.get('break_close')))

    def closing_break(self,key):
        return any(s['kind']=='break' and s['break_mode']=='close' for s in self.due(key,'app:'))

    def save_minutes(self,key,subject):
        if self.zero_budget(key): return 0
        due=self.due(key,subject)
        regular=[s for s in due if s['kind'] not in ('notify','break')]
        selected=regular or [s for s in due if s['kind']=='break']
        return min((s.get('extension_minutes',self.plans[key]['extension_minutes']) for s in selected),default=0)

    def dominant(self,keys,subject,identity=None):
        keys=list(keys)
        regular=[key for key in keys if self.has_restriction(key,subject,identity)]
        return regular or keys

    def warnings(self, key, subject=None):
        if self.zero_budget(key): return []
        return [s for s in self.due(key,subject) if s['kind'] == 'notify' and s['id'] not in self.rows[key]['delivered']]

    def zero_budget(self, key):
        budget = self.budgets.get(key)
        return budget is not None and budget.limit == 0

    def delivered(self, key, identity):
        with self.db:
            if identity not in self.rows[key]['delivered']:
                self.rows[key]['delivered'].append(identity)
                self._save(key)

    def allowance(self, keys, subject):
        if not keys: return 0
        minutes = []
        for key in keys:
            eligible=self.has_restriction(key,subject) or subject.startswith('app:') and self.closing_break(key)
            if (key not in self.budgets or not eligible or self.rows[key]['used_extension']
                    or self.action(key, subject) not in ('cover','minimize')):
                return 0
            minutes.append(self.save_minutes(key,subject))
        return min(minutes)

    def extend(self, keys, subject, identity=''):
        keys = sorted(set(keys))
        minutes = self.allowance(keys, subject)
        if not minutes: return None
        until = self.now + minutes * 60
        # SQLite is the authority, not a GUI button's cached enabled state.
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            for key in keys:
                raw = self.db.execute('SELECT value FROM restriction_state WHERE day=? AND budget=?',
                                      (self.days.get(key,self.day), key)).fetchone()
                if raw and json.loads(raw[0])['used_extension']: return None
            for key in keys:
                grant={'subject':subject,'until':until}
                if identity and subject.startswith('app:'): grant['identity']=identity
                if subject.startswith('app:') and not self.has_restriction(key,subject) and self.closing_break(key):
                    # Keep the explicitly requested save-and-close promise even
                    # if this short break ends before the save interval does.
                    grant['break_close']=True
                self.rows[key].update(used_extension=True, grant=grant)
                self._save(key)
        return until

    def finish_grant(self,key,subject,identity):
        grant=self.grant(key,subject,identity)
        if not grant: return
        with self.db:
            for day,raw in self.db.execute('SELECT day,value FROM restriction_state WHERE budget=?',(key,)).fetchall():
                if day==self.days.get(key,self.day): continue
                previous=json.loads(raw); other=previous.get('grant') or {}
                if (other.get('subject')==subject and other.get('identity')==grant.get('identity')
                        and other.get('until')==grant.get('until')):
                    previous['grant']=None
                    self.db.execute('UPDATE restriction_state SET value=? WHERE day=? AND budget=?',
                                    (json.dumps(previous,separators=(',',':')),day,key))
            if grant.get('carried'): self.rows[key]['used_extension']=grant.get('prior_used',False)
            self.rows[key]['grant']=None
            self._save(key)

    def move_day(self, old, new, exclude=()):
        if old == new: return
        with self.db:
            for key, raw in self.db.execute('SELECT budget,value FROM restriction_state WHERE day=?', (old,)).fetchall():
                if key in exclude: continue
                previous = json.loads(raw)
                target = self.db.execute('SELECT value FROM restriction_state WHERE day=? AND budget=?', (new, key)).fetchone()
                if target:
                    merged = json.loads(target[0])
                    merged['used_extension'] |= previous['used_extension']
                    merge_breaks(merged,previous)
                    merged['delivered'] = sorted(set(merged['delivered']) | set(previous['delivered']))
                    if previous['grant'] and (not merged['grant'] or previous['grant']['until'] < merged['grant']['until']):
                        merged['grant'] = previous['grant']
                    previous = merged
                self.db.execute('INSERT OR REPLACE INTO restriction_state VALUES (?,?,?)', (new, key, json.dumps(previous)))
        self.day = None
        self.days.clear()
