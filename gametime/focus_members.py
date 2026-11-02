"""Display the live members of focus groups without copying them into blocklists."""
import ntpath
from .activity_identity import app_identity
from .focus import domain,SHELLS


def categories(focus,rules):
    result=set(focus.block_groups)&{'games','apps','sites'}
    for rule in rules:
        if 'budget:'+rule['id'] in focus.block_groups:
            result.update(member['value'] for member in rule['members'] if member['kind']=='category')
    return result


def rows(focus,rules,catalog,inventory,names,t):
    result={'site':{},'app':{},'group':{}}
    def add(kind,key,name,detail,direct=False,group=None):
        row=result[kind].setdefault(key,dict(key=key,name=str(name),detail=detail,direct=direct,groups=[]))
        if group and group not in row['groups']: row['groups'].append(group)
        return row
    for site in focus.block_sites: add('site',site,site,site,True)
    for path in focus.block_apps: add('app',path,ntpath.basename(path),path,True)
    direct_games={}
    if focus.block_groups:
        for path in focus.block_apps:
            game=catalog.resolve(path,fallback=False)
            if game: direct_games.setdefault(game.id,[]).append(path)
    def application(value,group):
        identity=app_identity(value)
        direct=[row for row in result['app'].values() if row['direct'] and app_identity(row['key'])==identity]
        if direct:
            for row in direct:
                if group not in row['groups']: row['groups'].append(group)
        else: add('app','member:app:'+identity,ntpath.basename(value),value,group=group)
    def game_member(gid,group):
        game=catalog.games.get(gid)
        if gid in direct_games:
            for path in direct_games[gid]: add('app',path,ntpath.basename(path),path,group=group)
        else:
            name=game.name if game else gid
            detail=game.root if game else str(t('Removed game'))
            if game and not catalog.enabled(game): detail+='\n'+str(t('Excluded from group blocking.'))
            add('app','member:game:'+gid,name,detail,group=group)
    def site_member(value,group):
        try: value=domain(value)
        except ValueError: return
        add('site',value,value,value,group=group)
    def category(value,group):
        if value=='games':
            for game in catalog.games.values():
                if game.installed: game_member(game.id,group)
        elif value=='apps':
            for (kind,path),name in inventory.items():
                if (kind!='app' or ntpath.basename(path) in SHELLS or focus.app_excluded(path)
                        or catalog.explicitly_ignored(path) or catalog.resolve(path,fallback=False)): continue
                application(path,group)
        else:
            for (kind,value),name in inventory.items():
                if kind=='site': site_member(value,group)
            for rule in rules:
                for member in rule['members']:
                    if member['kind']=='site': site_member(member['value'],group)
            for value in focus.block_sites: site_member(value,group)
    by_id={rule['id']:rule for rule in rules}
    for key in focus.block_groups:
        group=str(names.get(key,t('Removed group')))
        add('group',key,group,group,True)
        if key in ('games','apps','sites'): category(key,group); continue
        rule=by_id.get(key.removeprefix('budget:'))
        if not rule: continue
        for member in rule['members']:
            kind,value=member['kind'],member['value']
            if kind=='category': category(value,group)
            elif kind=='game': game_member(value,group)
            elif kind=='app': application(value,group)
            else: site_member(value,group)
    return {kind:tuple((row['key'],row['name'],row['detail'],row['direct'],tuple(row['groups']))
                      for row in sorted(entries.values(),key=lambda row:(row['name'].casefold(),row['key'])))
            for kind,entries in result.items()}
