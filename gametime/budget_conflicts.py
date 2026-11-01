"""Explain overlapping budget coverage without rejecting intentional combinations."""
from .focus import matches


def member_overlap(left,right):
    a,b=left['kind'],right['kind']; x,y=left['value'],right['value']
    if a=='computer' or b=='computer': return True
    if a=='category':
        return (b=='category' and x==y) or (x,b) in (('games','game'),('apps','app'),('sites','site'))
    if b=='category': return member_overlap(right,left)
    if a!=b: return False
    if a=='site': return matches(x,y) or matches(y,x)
    from .activity_identity import activity_key
    return activity_key(left)==activity_key(right)


def intervals(editor,key):
    days=editor.access.active_days.get(key,range(7)); renewal=editor.reset_overrides.get(key,editor.app.settings.budget_reset_minute)
    if editor.periods.is_computer(key):
        plan=next((p['values'] for p in editor.periods.items if p['id']==key),editor.schedule._plans[0])
        start=plan['bedtime_warning_minute']+(plan['bedtime_minute']-plan['bedtime_warning_minute'])%1440
        start+=1440*(plan['bedtime_warning_minute']<renewal)
        length=(plan['bedtime_resume_minute']-plan['bedtime_minute'])%1440
    else: start=renewal; length=1440
    return [(d*1440+start+shift,d*1440+start+length+shift) for d in days for shift in (-10080,0,10080)]


def overlaps(editor):
    rows=[]
    for key,name,_,_,enabled,_ in editor.list_rows():
        if not enabled: continue
        if editor.periods.is_computer(key): members=[{'kind':'computer','value':'period'}]
        elif key=='shared-games': members=[{'kind':'category','value':'games'}]
        elif key.startswith('game:'): members=[{'kind':'game','value':key[5:]}]
        else: members=editor.rule(key)['members']
        rows.append((key,str(name),members,intervals(editor,key)))
    result=[]
    for index,(key,name,members,times) in enumerate(rows):
        for other,title,targets,periods in rows[index+1:]:
            if not any(member_overlap(a,b) for a in members for b in targets): continue
            if any(max(start,a)<min(end,b) for start,end in times for a,b in periods): result.append((key,name,other,title))
    return result


def warning(editor):
    key=editor.current
    names=[title if left==key else name for left,name,right,title in overlaps(editor) if key in (left,right)]
    if not names: return ''
    return str(editor.app.t('Overlapping budgets: {names}. They cover common activities at the same time; all restrictions apply, so the stricter limit takes precedence.',names=', '.join(dict.fromkeys(names))))
