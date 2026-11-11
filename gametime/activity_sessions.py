"""Count connected measured foreground intervals; keep legacy unknowns explicit."""
from collections import Counter
from datetime import date,datetime
import time

EPSILON=.002

def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS activity_sessions (kind TEXT NOT NULL,key TEXT NOT NULL,start REAL NOT NULL,finish REAL NOT NULL,day TEXT NOT NULL,PRIMARY KEY(kind,key,start))')
    db.execute('CREATE INDEX IF NOT EXISTS activity_sessions_finish ON activity_sessions(kind,key,finish)')
    db.execute('CREATE INDEX IF NOT EXISTS activity_sessions_period ON activity_sessions(finish)')
    db.execute("INSERT OR IGNORE INTO settings VALUES ('sessions_since',?)",(str(time.time()),))

def record(db,kind,key,start,finish,day):
    if finish<=start:return
    rows=list(db.execute('SELECT start,finish,day FROM activity_sessions WHERE kind=? AND key=? AND finish>=? AND start<=?',(kind,key,start-EPSILON,finish+EPSILON)))
    if rows:
        earliest=min(rows,key=lambda row:row[0])
        if earliest[0]<start:day=earliest[2]
        start=min(start,earliest[0]);finish=max(finish,max(row[1] for row in rows))
        db.executemany('DELETE FROM activity_sessions WHERE kind=? AND key=? AND start=?',[(kind,key,row[0]) for row in rows])
    db.execute('INSERT INTO activity_sessions VALUES (?,?,?,?,?)',(kind,key,start,finish,str(day)))
    db.execute("INSERT INTO settings VALUES ('session_revision','1') ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1")

class Sessions:
    def __init__(self,store):
        self.store=store;self.since=float(store.db.execute("SELECT value FROM settings WHERE key='sessions_since'").fetchone()[0]);self.pending=[]

    def credit(self,kind,key,start,finish,day):
        if float(start)<self.since:
            from .quota import current_day
            day=current_day(self.store.settings(),datetime.fromtimestamp(self.since).astimezone())
        start=max(float(start),self.since);finish=float(finish)
        if finish<=start:return
        for i in range(len(self.pending)-1,-1,-1):
            old=self.pending[i]
            if old[0:2]==(kind,key) and abs(old[3]-start)<=EPSILON:
                self.pending[i]=(kind,key,old[2],finish,old[4]);return
        self.pending.append((kind,key,start,finish,str(day)))

    def write(self):
        for row in self.pending:record(self.store.db,*row)

    def clear(self):self.pending.clear()

def local_snapshot(store,portable=False):
    from .quota import current_day
    from .statistics_sync import game_key
    settings=store.settings();since=float(store.db.execute("SELECT value FROM settings WHERE key='sessions_since'").fetchone()[0])
    # Use the same daily renewal boundary as measured usage.
    started=current_day(settings,datetime.fromtimestamp(since).astimezone()).isoformat()
    mapping={g.id:game_key(g.id,g.name,g.source) for g in store.games()} if portable else {}
    grouped=Counter()
    for day,kind,key,count in store.db.execute('SELECT day,kind,key,COUNT(*) FROM activity_sessions GROUP BY day,kind,key'):
        started=min(started,day)
        if kind=='game' and portable:
            if key not in mapping:continue
            key=mapping[key]
        grouped[day,kind,key]+=count
    return dict(since=started,rows=[[*key,count] for key,count in sorted(grouped.items())])

def validate(value):
    if not isinstance(value,dict) or set(value)!={'since','rows'}:raise ValueError('Invalid session counts.')
    since=value['since']
    if not isinstance(since,str) or date.fromisoformat(since).isoformat()!=since:raise ValueError('Invalid session start.')
    rows=value['rows'];seen=set()
    if not isinstance(rows,list) or len(rows)>100000:raise ValueError('Invalid session rows.')
    for row in rows:
        if not isinstance(row,(list,tuple)) or len(row)!=4:raise ValueError('Invalid session row.')
        day,kind,key,count=row
        if (not isinstance(day,str) or date.fromisoformat(day).isoformat()!=day or day<since or kind not in ('game','app','site','browser')
                or not isinstance(key,str) or not 1<=len(key)<=512 or '\0' in key or type(count) is not int or not 0<count<=1000000
                or (day,kind,key) in seen):raise ValueError('Invalid session row.')
        seen.add((day,kind,key))

def report_key(kind,key):return key if kind=='game' else 'activity:'+kind+':'+key

def display(count,partial=False):return str(count)

def index(snapshots):
    counts={};since={}
    for device,value in snapshots.items():
        if not value:continue
        since[device]=value['since']
        for day,kind,key,count in value['rows']:counts[day,report_key(kind,key),device]=count
    return counts,since

def count_rows(rows,snapshots,start):
    counts,since=index(snapshots);seen=set();total=0;partial=False
    for day,gid,name,source,seconds,device,*_ in rows:
        key=(day,gid,device)
        if key in seen or seconds<=0:continue
        seen.add(key);total+=counts.get(key,0)
        # Only days with actual usage can contribute unknown sessions. An empty
        # earlier part of the selected range does not make later records partial.
        partial |= device not in since or day<=since[device]
    return total,partial
