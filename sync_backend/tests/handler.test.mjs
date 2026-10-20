import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { createHandler } from '../supabase/functions/statistics-sync/handler.mjs';

const FORMAT = 'GameTimeMonitor.sync.v1';
const credential = 'a'.repeat(64);
const secret = 'server-administration-key';
const device = 'b'.repeat(32);
const data = () => ({ format: FORMAT, device, revision: '1792512345678901234', known: {}, payload: Buffer.alloc(64).toString('base64') });
const request = (body = data(), auth = 'Bearer '+credential, headers = {}) => new Request('https://example.com/statistics-sync', {
  method: 'POST', headers: { authorization: auth, 'content-type': 'application/json', ...headers }, body: JSON.stringify(body),
});

test('only group hash reaches SQL; provider secret stays on server; revisions stay exact', async () => {
  let received;
  const handle = createHandler({ url: 'https://project.supabase.co', serviceKey: secret,
    fetcher: async (url, options) => { received = { url, options }; return Response.json({ need_upload: false, snapshots: [] }); } });
  const body = data(); body.group = 'untrusted-group'; body.known['c'.repeat(32)] = '1792512345678901233';
  const response = await handle(request(body, undefined, { 'x-forwarded-for': '192.0.2.5' }));
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { format: FORMAT, need_upload: false, snapshots: [] });
  assert.equal(received.url, 'https://project.supabase.co/rest/v1/rpc/gametime_sync_exchange');
  assert.equal(received.options.headers.apikey, secret);
  const sql = JSON.parse(received.options.body);
  assert.equal(sql.p_group, createHash('sha256').update(credential).digest('hex'));
  assert.equal(sql.p_revision, body.revision); assert.deepEqual(sql.p_known, body.known);
  assert.match(sql.p_ip, /^[a-f0-9]{64}$/);
  assert.ok(!received.options.body.includes(credential));
  assert.ok(!received.options.body.includes('192.0.2.5')); assert.ok(!received.options.body.includes('untrusted-group'));
});

test('different user credentials derive different SQL groups', async () => {
  const groups = [];
  const handle = createHandler({ url: 'https://project.supabase.co', serviceKey: secret,
    fetcher: async (_, options) => { groups.push(JSON.parse(options.body).p_group); return Response.json({ need_upload: false, snapshots: [] }); } });
  await handle(request()); await handle(request(data(), 'Bearer '+'d'.repeat(64)));
  assert.notEqual(groups[0], groups[1]);
});

test('reject malformed, missing and oversized requests before contacting storage', async () => {
  let calls = 0;
  const handle = createHandler({ url: 'https://project.supabase.co', serviceKey: secret,
    fetcher: () => { calls++; throw new Error('unexpected'); } });
  assert.equal((await handle(request(data(), ''))).status, 401);
  assert.equal((await handle(request(data(), 'Bearer pin'))).status, 401);
  for (const fields of [{ device: '../escape' }, { revision: 1792512345678901234 }, { revision: '9223372036854775808' },
    { revision: '01' }, { known: [] }, { known: { invalid: '1' } }, { payload: 'a'.repeat(800_000) }, { payload: '???' }]) {
    assert.equal((await handle(request({ ...data(), ...fields }))).status, 400, JSON.stringify(Object.keys(fields)));
  }
  assert.equal(calls, 0);
});

test('propagate bounded quota/rate failures and never return provider errors/secrets', async () => {
  for (const [result, expected] of [[{ error: 'quota' }, 507], [{ error: 'rate' }, 429], [{ error: secret }, 503]]) {
    const handle = createHandler({ url: 'https://project.supabase.co', serviceKey: secret,
      fetcher: async () => Response.json(result) });
    const response = await handle(request()); assert.equal(response.status, expected); assert.ok(!(await response.text()).includes(secret));
  }
  const handle = createHandler({ url: 'https://project.supabase.co', serviceKey: secret,
    fetcher: async () => { throw new Error(secret); } });
  const response = await handle(request()); assert.equal(response.status, 503); assert.ok(!(await response.text()).includes(secret));
});

test('health endpoint is public, writes require configured backend and POST', async () => {
  const handle = createHandler({});
  assert.equal((await handle(new Request('https://example.com/statistics-sync/health'))).status, 200);
  assert.equal((await handle(new Request('https://example.com/statistics-sync'))).status, 405);
  assert.equal((await handle(request())).status, 503);
});
