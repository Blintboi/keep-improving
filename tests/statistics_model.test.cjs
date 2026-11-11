const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const model = import('data:text/javascript;base64,' + Buffer.from(fs.readFileSync('gametime/browser_extension/statistics-model.js')).toString('base64'));
const data = {
  computer_names: { local: 'Desktop', remote: 'Laptop' },
  games: [['a', 'Game'], ['b', 'Editor'], ['c', 'Game']],
  rows: [
    ['2026-11-01', 'a', 'Game', 'Steam', 60, 'local'],
    ['2026-11-01', 'a', 'Game', 'Steam', 120, 'remote'],
    ['2026-11-01', 'b', 'Editor', 'Application', 40, 'local'],
    ['2026-11-02', 'b', 'Editor', 'Application', 80, 'remote'],
    ['2026-11-02', 'c', 'Game', 'Epic', 90, 'remote'],
  ],
};
test('session counts aggregate by activity and device, sort measured counts numerically including legacy zeroes', async () => {
  const { detailRows, sessionText } = await model;
  const withCounts={...data,session_start:'2026-11-01',sessions:{local:{since:'2026-10-31',rows:[['2026-11-01','game','a',2],['2026-11-01','game','b',12]]}}};
  const descending=detailRows(withCounts,'','all',false,'sessions_desc');
  assert.deepEqual(descending.slice(0,2).map(r=>r.sessions),[12,2]);
  assert.equal(descending.at(-1).partial,true);
  assert.deepEqual(detailRows(withCounts,'','all',false,'sessions_asc').map(r=>r.sessions),[0,0,0,2,12]);
  assert.equal(detailRows(withCounts,'2026-11-02','local',false).length,0);
  const combined=detailRows(withCounts,'','all',true,'sessions_desc');
  assert.equal(combined[0].sessions,12);assert.equal(combined[0].partial,true);
  assert.equal(sessionText(12,true),'12');assert.equal(sessionText(0,true),'0');assert.equal(sessionText(0,false),'0');
});
test('chart keeps both computers and matching activity colors across days', async () => {
  const { chartGroups } = await model;
  const groups = chartGroups(data, '2026-11-01');
  assert.deepEqual(groups.map(g => [g.computer, g.total]), [['local',100],['remote',120]]);
  assert.deepEqual(groups[0].activities.map(a => a.id), ['a','b']);
  assert.equal(groups[1].activities[0].id, groups[0].activities[0].id);
  assert.deepEqual(chartGroups(data, '2026-11-03'), []);
});
test('chart session counts stay separate by day, device and activity; older data stays unknown', async () => {
  const { chartGroups } = await model;
  const withCounts={...data,sessions:{local:{since:'2026-10-31',rows:[['2026-11-01','game','a',2],['2026-11-01','game','b',12],['2026-11-02','game','a',99]]}}};
  const groups=chartGroups(withCounts,'2026-11-01');
  assert.deepEqual(groups.map(g=>[g.sessions,g.partial]),[[14,false],[0,true]]);
  assert.deepEqual(groups[0].activities.map(r=>r.sessions),[2,12]);
  assert.equal(chartGroups(withCounts,'2026-11-02').reduce((n,g)=>n+g.sessions,0),0);
  const counted=chartGroups(withCounts,'2026-11-01','sessions');
  assert.deepEqual(counted.map(g=>g.value),[14,0]);
  assert.deepEqual(counted[0].activities.map(r=>r.value),[2,12]);
  assert.equal(counted[0].total,100,'time remains available for tooltips');
});
test('empty earlier range does not make fully tracked usage partial', async () => {
  const { detailRows } = await model;
  const value={...data,session_start:'2026-10-01',sessions:{local:{since:'2026-10-31',rows:[['2026-11-01','game','a',2]]}}};
  const rows=detailRows(value,'','local',false);
  assert.equal(rows[0].partial,false);
  value.sessions.local.since='2026-11-01';
  assert.equal(detailRows(value,'','local',false)[0].partial,true);
});
test('details retain origins, combine deliberately, and filter day/computer independently', async () => {
  const { detailRows } = await model;
  const rows = detailRows(data, '', 'all', false);
  assert.equal(rows.length, 5);
  assert.equal(rows.reduce((sum,r) => sum+r.seconds,0),390);
  const combined = detailRows(data, '', 'all', true);
  assert.equal(combined.length,2);
  assert.equal(combined[0].seconds,270);
  assert.deepEqual([...combined[0].computers],['local','remote']);
  assert.equal(combined[0].ids.size,2);
  assert.deepEqual(detailRows(data,'2026-11-01','remote',true).map(r=>[r.name,r.seconds]),[['Game',120]]);
});
test('matching labels in different activity types stay separate', async () => {
  const { detailRows } = await model;
  const rows = detailRows({...data,rows:[...data.rows,['2026-11-01','site','Game','Website',30,'local']]},'','all',true);
  assert.equal(rows.length,3);
  assert.equal(rows.at(-1).type,'Website');
});
