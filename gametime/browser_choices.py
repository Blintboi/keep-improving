"""Purpose choices for a browser visit, using the desktop's durable allowance."""
from datetime import datetime
import re
from .focus import BROWSERS,domain,matches
from .session_choices import allowance_activity


def rules(runtime):
    result=[]
    for key,budget in runtime.state.budgets.items():
        plan=runtime.state.plans.get(key,{})
        if not any(s.get('session_choice') and s.get('targets',{}).get('site',{}).get('enabled',True) for s in plan.get('steps',())): continue
        domains=[m['value'] for m in budget.members if m['kind']=='site']
        all_sites={'kind':'category','value':'sites'} in budget.members
        if domains or all_sites: result.append(dict(domains=domains,all=all_sites))
    return result


def request(app,data,choose=False):
    allowed={'browser','domain','visit'}|({'budget','step','choice'} if choose else set())
    if set(data)!=allowed or data.get('browser') not in BROWSERS.values(): raise ValueError('Invalid opening choice.')
    host=domain(data['domain']); token=data['visit']
    if not isinstance(token,str) or not re.fullmatch('[a-f0-9]{32}',token): raise ValueError('Invalid opening choice.')
    runtime=app.restrictions;runtime.prepare(datetime.now().astimezone());ledger=runtime.choices.ledger
    atom=('','',host);keys=runtime.matching(atom)
    base=app.wellbeing.policy(app.focus.policy(app.settings.wellbeing_rules),datetime.now().astimezone(),runtime.delegated_website_rules())
    blocked=base['active'] and (any(matches(host,h) for h in base['block']) or base['mode']=='allowlist' and not any(matches(host,h) for h in base['allow']))
    if blocked or any(runtime.state.action(key,'site:'+host) for key in keys):
        return dict(accepted=False,choice=None,blocked=True)
    pending=[];accepted=False
    for key in keys:
        budget=runtime.state.budgets[key]
        activity=allowance_activity(budget.members,atom,'site')
        visit='web:'+data['browser']+':'+host+':'+budget.day+':'+token
        for step in runtime.state.plans[key]['steps']:
            value=step.get('session_choice')
            if not value or not step.get('targets',{}).get('site',{}).get('enabled',True): continue
            if choose and key==data['budget'] and step['id']==data['step']:
                accepted=ledger.choose(key,step['id'],budget.day,visit,value,data['choice'],runtime.state.now,activity)
            existing=ledger.db.execute('SELECT 1 FROM session_choices WHERE budget=? AND step=? AND visit=?',(key,step['id'],visit)).fetchone()
            if not existing:
                pending.append(dict(budget=key,step=step['id'],name=budget.name,question=value['question'],
                    allocation=value.get('allocation','shared'),options=ledger.options(key,step['id'],budget.day,value,activity)))
    return dict(accepted=accepted,choice=pending[0] if pending else None,blocked=False)
