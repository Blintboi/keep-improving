"""Activity identities and countdown appearance, independent of time budgets."""
from dataclasses import replace
import ntpath
from .wellbeing import target,applies,counter_settings
from .focus import matches
from .activity_identity import activity_key,canonical_member,site_identity,is_idle_app


def activity_target(key):
    kind,separator,value=key.partition(':')
    if not separator or kind not in ('game','app','site'): raise ValueError('Choose a valid activity.')
    return canonical_member(target(kind,value))


def matching_rules(settings,member):
    atom=tuple(member['value'] if member['kind']==kind else '' for kind in ('game','app','site'))
    return [rule for rule in settings.wellbeing_rules if rule['enabled'] and applies(rule['members'],atom)]


def has_budget(settings,member):
    return bool(member['kind']=='game' and (settings.game_budget_enabled or member['value'] in settings.game_limits)
                or matching_rules(settings,member))


def activity_settings(settings,member,rule=None):
    # Old budget styles remain the fallback until this activity is customized.
    if rule is None:
        rules=matching_rules(settings,member)
        rule=min(rules,key=lambda r:r['seconds']) if rules else None
    effective=counter_settings(settings,rule) if rule else settings
    profiles=settings.game_overlays if member['kind']=='game' else settings.activity_overlays
    key=member['value'] if member['kind']=='game' else activity_key(member)
    if member['kind'] in ('app','site') and key not in profiles:
        # Read old path-based profiles without rewriting or losing saved settings.
        aliases=sorted(old for old in profiles if activity_key(activity_target(old))==key)
        if aliases: key=aliases[0]
    if member['kind']=='site' and key not in profiles:
        parents=[key for key in profiles if key.startswith('site:') and matches(site_identity(member['value']),site_identity(key[5:]))]
        if parents: key=max(parents,key=len)
    return replace(effective,**profiles.get(key,{}))


def foreground_target(settings,atom):
    game,app,site=atom
    if game: return target('game',game)
    if site and has_budget(settings,target('site',site)): return target('site',site)
    return target('app',app)


def known_activities(store,settings,catalog=None,sources=None):
    """Read only on navigation or an explicit refresh, never on countdown ticks."""
    items={}; candidates=list(store.db.execute('SELECT kind,key,name FROM activity_items ORDER BY kind,key'))
    if settings.statistics_sync_enabled and settings.statistics_sync_group:
        from .statistics_sync import local_group
        if store.db.execute("SELECT 1 FROM sqlite_master WHERE name='statistics_activity'").fetchone():
            candidates.extend(store.db.execute('SELECT DISTINCT kind,item_key,name FROM statistics_activity WHERE group_id=? ORDER BY kind,item_key',
                                                (local_group(settings.statistics_sync_group),)))
    for kind,value,name in candidates:
        if kind=='app' and is_idle_app(value): continue
        try: member=target(kind,value)
        except ValueError: continue
        if kind=='app' and catalog and catalog.resolve(value,fallback=False): continue
        key=activity_key(member)
        if sources is not None:
            values=sources.setdefault(key,[])
            if value not in values: values.append(value)
        member=canonical_member(member)
        name=member['value'] if kind=='site' or ntpath.basename(value).casefold()!=member['value'] else ntpath.basename(name)
        if key not in items or items[key][1]==member['value']: items[key]=(member,name)
    for rule in settings.wellbeing_rules:
        for member in rule['members']:
            if member['kind'] in ('app','site'):
                if member['kind']=='app' and is_idle_app(member['value']): continue
                key=activity_key(member)
                if sources is not None and member['value'] not in sources.setdefault(key,[]): sources[key].append(member['value'])
                member=canonical_member(member)
                items.setdefault(key,(member,member['value']))
    for key in settings.activity_overlays:
        member=activity_target(key)
        if member['kind']=='app' and is_idle_app(member['value']): continue
        canonical=activity_key(member)
        if sources is not None and key.partition(':')[2] not in sources.setdefault(canonical,[]): sources[canonical].append(key.partition(':')[2])
        items.setdefault(canonical,(member,member['value']))
    return sorted(items.values(),key=lambda item:(item[1].casefold(),activity_key(item[0])))
