"""Activity-scoped drafts for the countdown appearance editor."""
from copy import deepcopy
from dataclasses import replace
from .activities import activity_key,activity_target,activity_settings,has_budget,known_activities,matching_rules
from .wellbeing import target,applies

FIELDS=('overlay_enabled','overlay_x','overlay_y','overlay_font_size','overlay_screen','overlay_color_normal','overlay_color_warning','overlay_opacity')


class CountdownTargets:
    def __init__(self,app):
        self.app=app; self.profiles={}; self.edited=set(); self.refresh()

    def refresh(self):
        app=self.app
        games=sorted((g for g in app.catalog.games.values() if g.installed and has_budget(app.settings,target('game',g.id))),key=lambda g:(g.name.casefold(),g.id))
        self._rows=[(g.name,g.id) for g in games]
        for member,name in known_activities(app.store,app.settings,app.catalog):
            if has_budget(app.settings,member):
                kind=app.t('Application' if member['kind']=='app' else 'Website')
                self._rows.append((app.t('{kind} · {name}',kind=kind,name=name),activity_key(member)))

    def rows(self): return self._rows
    def member(self,key): return activity_target(key) if key and key.startswith(('app:','site:')) else target('game',key)
    def rule(self,key):
        if not key or not key.startswith(('app:','site:')): return None
        rules=matching_rules(self.app.settings,self.member(key))
        return min(rules,key=lambda r:r['seconds']) if rules else None

    def profile(self,key):
        if not key: return {}
        if key in self.profiles: return dict(self.profiles[key])
        effective=activity_settings(self.app.settings,self.member(key))
        return {field:getattr(effective,field) for field in FIELDS}

    def set_profile(self,key,value):
        if key: self.profiles[key]=dict(value); self.edited.add(key)

    def candidate(self,key,value):
        self.set_profile(key,value)
        games=deepcopy(self.app.settings.game_overlays); activities=deepcopy(self.app.settings.activity_overlays)
        for key in self.edited:
            destination=activities if key.startswith(('app:','site:')) else games
            if destination is activities:
                for old in list(destination):
                    if activity_key(activity_target(old))==key: destination.pop(old)
            destination[key]={**destination.get(key,{}),**self.profiles[key]}
        return replace(self.app.settings,game_overlays=games,activity_overlays=activities).validate()

    def effective(self,settings,key):
        result=activity_settings(settings,self.member(key)); rule=self.rule(key)
        if rule:
            result=replace(result,limit_seconds=rule['seconds'],warning_seconds=rule['seconds']*.8,
                           weekend_enabled=False,weekend_schedule={},daily_schedules={})
        return result

    def saved(self,settings):
        self.app.budget_editor.game_overlays=deepcopy(settings.game_overlays)
        self.app.budget_editor.game_overlay_changed.clear()
        self.app.budget_editor.refresh_rows()
        self.app.refresh_activity_lists()


class BudgetCountdownTargets:
    """Edit one budget's style in its existing, cancellable budget draft."""
    budget=True

    def __init__(self,editor,key):
        self.editor=editor; self.app=editor.app; self.key=key; self.profiles={}; self.edited=set()
        self.refresh()

    def refresh(self):
        editor=self.editor; app=self.app; t=app.t
        self._rows=[(t('Budget default · {name}',name=editor.selector.itemText(editor.selector.findData(self.key))),self.key)]
        if self.key.startswith('game:'): return
        rule=editor.rule(self.key)
        members=rule['members'] if rule else [target('category','games')]
        choices={activity_key(m):(m,editor.member_name(m)) for m in members if m['kind']!='category'}
        candidates=[(target('game',g.id),g.name) for g in app.catalog.games.values() if g.installed and app.catalog.enabled(g)]
        candidates.extend(known_activities(app.store,app.settings,app.catalog))
        for member,name in candidates:
            atom=tuple(member['value'] if member['kind']==kind else '' for kind in ('game','app','site'))
            if applies(members,atom): choices.setdefault(activity_key(member),(member,name))
        for key,(member,name) in sorted(choices.items(),key=lambda item:(str(item[1][1]).casefold(),item[0])):
            kind=t({'game':'Game','app':'Application','site':'Website'}[member['kind']])
            self._rows.append((t('{kind} · {name}',kind=kind,name=name),key))

    def rows(self): return self._rows
    def game_id(self,key): return key[5:] if key.startswith('game:') else None
    def rule(self,key): return self.editor.rule(self.key) or {'seconds':self.editor.steps.base_limit()}
    def supports_rtss(self,key=None):
        if key and key!=self.key: return key.startswith('game:')
        rule=self.editor.rule(self.key)
        return self.key=='shared-games' or self.key.startswith('game:') or bool(rule and any(
            m['kind']=='game' or m=={'kind':'category','value':'games'} for m in rule['members']))

    def profile(self,key):
        if key in self.profiles: return dict(self.profiles[key])
        settings=self.editor.countdown_settings(self.app.settings)
        if key!=self.key:
            member=target(*key.split(':',1)); parent=self.profile(self.key)
            counters={**settings.counter_overlays,self.key:{k:v for k,v in parent.items() if k!='overlay_enabled'}}
            settings=replace(settings,counter_overlays=counters)
            effective=activity_settings(settings,member,{'id':self.key,'overlay':parent['overlay_enabled']})
            fields=(*FIELDS,'overlay_rtss_auto') if member['kind']=='game' else FIELDS
            return {field:getattr(effective,field) for field in fields}
        if key=='shared-games': values=self.editor.shared_overlay
        elif key.startswith('game:'): values=settings.game_overlays.get(key[5:],{})
        else:
            values={**self.editor.counter_overlays.get(key,{}),'overlay_enabled':self.editor.rule(key)['overlay']}
        return {field:values.get(field,getattr(settings,field)) for field in (*FIELDS,'overlay_rtss_auto')}

    def set_profile(self,key,value):
        self.profiles[key]=dict(value); self.edited.add(key)

    def candidate(self,key,value):
        self.set_profile(key,value)
        # Preview validates only the appearance, not unfinished restriction cards.
        for edited in self.edited: replace(self.app.settings,**self.profiles[edited]).validate()
        return replace(self.app.settings,**value).validate()

    def effective(self,settings,key):
        seconds=self.rule(key)['seconds']
        return replace(settings,limit_seconds=seconds,warning_seconds=seconds*.8,
                       weekend_enabled=False,weekend_schedule={},daily_schedules={})

    def saved(self,settings):
        editor=self.editor
        for key in self.edited:
            value=dict(self.profiles[key])
            if key!=self.key or key.startswith('game:'):
                profiles=editor.member_overlay_drafts.pop(self.key,{})
                profiles[key]=value; editor.member_overlay_drafts[self.key]=profiles
            elif self.key=='shared-games': editor.shared_overlay.update(value)
            else:
                editor.rule(self.key)['overlay']=value.pop('overlay_enabled')
                editor.counter_overlays[self.key]=value; editor.counter_overlay_changed.add(self.key)
        editor.refresh_rows()
