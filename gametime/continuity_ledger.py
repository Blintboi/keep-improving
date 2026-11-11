"""Durable time coverage, committed with the counters it protects from replay."""
import math


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS continuity_coverage (kind TEXT NOT NULL,start REAL NOT NULL,end REAL NOT NULL,PRIMARY KEY(kind,start))')
    db.execute('CREATE INDEX IF NOT EXISTS continuity_coverage_end ON continuity_coverage(kind,end)')


def uncovered(db,kind,start,end,extra=()):
    spans=[(start,end)]
    covered=list(db.execute('SELECT start,end FROM continuity_coverage WHERE kind=? AND end>? AND start<?',(kind,start,end)))+list(extra)
    for left,right in covered:
        spans=[part for a,b in spans for part in ((a,min(b,left)),(max(a,right),b)) if part[1]>part[0]]
    return spans


def cover(db,kind,start,end):
    if not end>start: return
    rows=list(db.execute('SELECT start,end FROM continuity_coverage WHERE kind=? AND end>=? AND start<=?',(kind,start-.001,end+.001)))
    if rows:
        start=min(start,min(a for a,b in rows)); end=max(end,max(b for a,b in rows))
        db.executemany('DELETE FROM continuity_coverage WHERE kind=? AND start=?',[(kind,a) for a,b in rows])
    db.execute('INSERT INTO continuity_coverage VALUES (?,?,?)',(kind,start,end))


class Coverage:
    def __init__(self,db,kind):
        self.db,self.kind=db,kind; self.pending=[]; initialize(db)

    def record(self,start,end):
        if not all(math.isfinite(v) for v in (start,end)) or not end>start: return
        if self.pending and 0<=start-self.pending[-1][1]<.002:
            self.pending[-1]=(self.pending[-1][0],end)
        else: self.pending.append((start,end))

    def write(self):
        for start,end in self.pending: cover(self.db,self.kind,start,end)

    def clear(self): self.pending.clear()
