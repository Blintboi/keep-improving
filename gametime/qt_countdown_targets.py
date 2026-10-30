"""Activity-scoped drafts for the countdown appearance editor."""
from copy import deepcopy
from dataclasses import replace
from .activities import activity_key,activity_target,activity_settings,has_budget,known_activities,matching_rules
from .wellbeing import target

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
            destination[key]=dict(self.profiles[key])
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
