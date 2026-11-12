"""Parallel media intervals supplement, but never duplicate, foreground budgets."""
from collections import defaultdict
import json
import ntpath


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS media_budget_usage (day TEXT NOT NULL,item TEXT NOT NULL,seconds REAL NOT NULL,PRIMARY KEY(day,item))')
    db.execute('CREATE TABLE IF NOT EXISTS media_activity_usage (day TEXT NOT NULL,kind TEXT NOT NULL,key TEXT NOT NULL,seconds REAL NOT NULL,PRIMARY KEY(day,kind,key))')


def budget_items(db,day):
    return dict(db.execute('SELECT item,seconds FROM media_budget_usage WHERE day=?',(day,)))


def combined_history(apps,sites,background):
    """Retain legacy foreground reconciliation and full opted-in media time."""
    from .focus import BROWSERS
    browsers=defaultdict(float);media_browsers=defaultdict(float);foreground_sites=defaultdict(float);media_sites=defaultdict(float);output=[]
    for row in apps:
        day,key,name,source,seconds=row;bg=background.get((day,'app',key[len('activity:app:'):]),0)
        if ntpath.basename(key[len('activity:app:'):]) in BROWSERS:
            browsers[day]+=max(0,seconds-bg);media_browsers[day]+=bg
        else:output.append(row)
    for day,key,name,source,seconds in sites:
        bg=min(seconds,background.get((day,'site',key[len('activity:site:'):]),0))
        foreground_sites[day]+=seconds-bg;media_sites[day]+=bg
    for day,key,name,source,seconds in sites:
        bg=min(seconds,background.get((day,'site',key[len('activity:site:'):]),0))
        scale=min(1,browsers[day]/foreground_sites[day]) if foreground_sites[day] else 0
        value=(seconds-bg)*scale+bg
        if value:output.append((day,key,name,source,value))
    for day in set(browsers)|set(media_browsers):
        remaining=max(0,browsers[day]-foreground_sites[day])+max(0,media_browsers[day]-media_sites[day])
        if remaining:output.append((day,'activity:browser:other','Other browser time','Browser',remaining))
    return output


def background_rows(db,start='0001-01-01',end='9999-12-31'):
    return {(day,kind,key):seconds for day,kind,key,seconds in db.execute('SELECT day,kind,key,seconds FROM media_activity_usage WHERE day>=? AND day<=?',(str(start),str(end)))}


def validate_background(rows,activity):
    import math
    if not isinstance(rows,list) or len(rows)>100000:raise ValueError('Invalid background activity.')
    measured={(day,kind,key):seconds for day,kind,key,name,seconds in activity};seen=set()
    for row in rows:
        if not isinstance(row,(tuple,list)) or len(row)!=4:raise ValueError('Invalid background activity.')
        day,kind,key,seconds=row
        if not all(isinstance(value,str) for value in (day,kind,key)):raise ValueError('Invalid background activity.')
        identity=(day,kind,key)
        if identity in seen or identity not in measured or type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=measured[identity]+.001:
            raise ValueError('Invalid background activity.')
        seen.add(identity)


def remap_item(item,old,new):
    try:atom=json.loads(item)
    except (ValueError,TypeError):return item
    parts=([atom.get('foreground')]+list(atom.get('media',()))) if isinstance(atom,dict) else [atom]
    changed=False
    for part in parts:
        if isinstance(part,list) and len(part)==3 and part[0]==old:part[0]=new;changed=True
    return json.dumps(atom,ensure_ascii=False) if changed else item
