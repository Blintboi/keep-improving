import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { createHandler } from '../supabase/functions/statistics-sync/handler.mjs';

const FORMAT = 'GameTimeMonitor.sync.v1', credential = 'a'.repeat(64), secret = 'server-administration-key';
const device = 'b'.repeat(32);
const data = () => ({ format: FORMAT, device, revision: '1792512345678901234', known: {},
  payload: Buffer.concat([Buffer.from('GTM1'), Buffer.alloc(60)]).toString('base64') });
const request = (body = data(), auth = 'Bearer '+credential, headers = {}) => new Request('https://example.com/statistics-sync', {
  method: 'POST', headers: { authorization: auth, 'content-type': 'application/json', ...headers }, body: JSON.stringify(body),
});
function fixture({ admission = true, exchange = () => ({ need_upload:false, snapshots:[] }), clock, bodyTimeoutMs } = {}) {
  const calls = [];
  const handle = createHandler({ url:'https://project.supabase.co', serviceKey:secret, clock, bodyTimeoutMs,
    fetcher:async (url, options) => {
      const args = JSON.parse(options.body); calls.push({url,options,args});
      return Response.json(url.endsWith('gametime_sync_authorize') ? admission : exchange(args));
    } });
  return { handle, calls };
}
test('only group/IP hashes reach SQL; exact revisions and server-only credentials', async () => {
  const {handle,calls} = fixture();
  const body=data(); body.known['c'.repeat(32)]='1792512345678901233';
  const response=await handle(request(body,undefined,{'x-forwarded-for':'192.0.2.5'}));
  assert.equal(response.status,200);
  assert.deepEqual(await response.json(),{format:FORMAT,need_upload:false,snapshots:[]});
  const exchange=calls.at(-1); assert.ok(exchange.url.endsWith('gametime_sync_exchange'));
  assert.equal(exchange.options.headers.apikey,secret);
  assert.equal(exchange.args.p_group,createHash('sha256').update(credential).digest('hex'));
  assert.equal(exchange.args.p_revision,body.revision); assert.deepEqual(exchange.args.p_known,body.known);
  assert.match(exchange.args.p_ip,/^[a-f0-9]{64}$/);
  assert.ok(!exchange.options.body.includes(credential)); assert.ok(!exchange.options.body.includes('192.0.2.5'));
  assert.equal(response.headers.get('cache-control'),'no-store');
});
test('different credentials remain isolated', async () => {
  const {handle,calls}=fixture();
  await handle(request()); await handle(request(data(),'Bearer '+'d'.repeat(64)));
  const groups=calls.filter(c=>c.url.endsWith('gametime_sync_exchange')).map(c=>c.args.p_group);
  assert.equal(groups.length,2); assert.notEqual(groups[0],groups[1]);
});
test('unknown keys are denied before body parsing or storage allocation', async () => {
  const {handle,calls}=fixture({admission:false});
  const bad=new Request('https://example.com/statistics-sync',{method:'POST',
    headers:{authorization:'Bearer '+credential,'content-type':'application/json'},body:'not JSON'});
  assert.equal((await handle(bad)).status,403);
  assert.equal((await handle(request())).status,403);
  assert.equal(calls.length,1); assert.ok(calls[0].url.endsWith('gametime_sync_authorize'));
});
test('strict envelope, canonical ciphertext and bounded revision/cache values', async () => {
  const {handle,calls}=fixture();
  assert.equal((await handle(request(data(),''))).status,401);
  assert.equal((await handle(request(data(),'Bearer pin'))).status,401);
  for (const fields of [{device:'../escape'},{device:[device]},{revision:1792512345678901234},{revision:'9223372036854775808'},
    {revision:'01'},{known:[]},{known:{invalid:'1'}},{payload:'a'.repeat(800000)},{payload:'???'},
    {payload:Buffer.alloc(64).toString('base64')},{group:'untrusted'},{payload:undefined}]) {
    assert.equal((await handle(request({...data(),...fields}))).status,400,JSON.stringify(Object.keys(fields)));
  }
  assert.equal(calls.filter(c=>c.url.endsWith('gametime_sync_exchange')).length,0);
});
test('oversized declared body and unsupported content are rejected before SQL', async () => {
  const {handle,calls}=fixture();
  assert.equal((await handle(request(data(),undefined,{'content-length':'750001'}))).status,413);
  assert.equal((await handle(request(data(),undefined,{'content-type':'application/jsonp'}))).status,415);
  assert.equal((await handle(request(data(),undefined,{'content-encoding':'gzip'}))).status,415);
  assert.equal(calls.length,0);
});

test('early rejections cancel unread uploads', async () => {
  let cancelled=false;
  const {handle,calls}=fixture();
  const body=new ReadableStream({cancel(){cancelled=true;}});
  const response=await handle(new Request('https://example.com/statistics-sync',{method:'POST',body,duplex:'half'}));
  assert.equal(response.status,401); assert.equal(cancelled,true); assert.equal(calls.length,0);
});
test('stream size and slow body deadline are enforced', async () => {
  const {handle}=fixture({bodyTimeoutMs:20});
  for (const body of [
    new ReadableStream({start(c){c.enqueue(new Uint8Array(750001));c.close();}}),
    new ReadableStream({start(){}}),
    new ReadableStream({start(){},cancel(){return new Promise(()=>{});}}),
  ]) {
    const response=await handle(new Request('https://example.com/statistics-sync',{method:'POST',
      headers:{authorization:'Bearer '+credential,'content-type':'application/json'},body,duplex:'half'}));
    assert.equal(response.status,400);
  }
  assert.equal((await handle(request())).status,200);
});
test('nearest proxy address is used only as an additional rate identity', async () => {
  const {handle,calls}=fixture();
  await handle(request(data(),undefined,{'x-forwarded-for':'spoofed, 192.0.2.5'}));
  await handle(request(data(),undefined,{'x-forwarded-for':'different, 192.0.2.5'}));
  const identities=calls.filter(c=>c.url.endsWith('gametime_sync_exchange')).map(c=>c.args.p_ip);
  assert.equal(identities[0],identities[1]);
});
test('admission cache expires and failed admission never enters storage', async () => {
  let now=100000;
  const {handle,calls}=fixture({clock:()=>now});
  await handle(request()); await handle(request()); now+=15001; await handle(request());
  assert.equal(calls.filter(c=>c.url.endsWith('gametime_sync_authorize')).length,2);
});
test('quota/rate failures carry bounded retry hints without provider error leakage', async () => {
  for (const [error,status] of [['quota',507],['rate',429],['admission',403],[secret,503]]) {
    const {handle}=fixture({exchange:()=>({error,retry_after:999999999})});
    const response=await handle(request()); assert.equal(response.status,status);
    assert.ok(!(await response.text()).includes(secret));
    assert.ok(Number(response.headers.get('retry-after'))<=86400);
  }
  const handle=createHandler({url:'https://project.supabase.co',serviceKey:secret,fetcher:async()=>{throw new Error(secret);}});
  const response=await handle(request()); assert.equal(response.status,503); assert.ok(!(await response.text()).includes(secret));
});
test('bounded concurrency fails closed and releases slots', async () => {
  const release=[];
  const handle=createHandler({url:'https://project.supabase.co',serviceKey:secret,
    fetcher:()=>new Promise(resolve=>release.push(resolve))});
  const running=Array.from({length:8},()=>handle(request()));
  assert.equal((await handle(request())).status,503);
  while(release.length<8) await new Promise(resolve=>setImmediate(resolve));
  release.forEach(resolve=>resolve(Response.json(false)));
  assert.deepEqual((await Promise.all(running)).map(r=>r.status),Array(8).fill(403));
  assert.equal((await handle(request())).status,403);
});
test('health exposes only status; writes require a configured backend', async () => {
  const handle=createHandler({});
  assert.equal((await handle(new Request('https://example.com/statistics-sync/health'))).status,200);
  assert.equal((await handle(new Request('https://example.com/statistics-sync'))).status,405);
  assert.equal((await handle(request())).status,503);
});

test('random invalid capabilities cannot cause unbounded SQL calls within one isolate', async () => {
  let now=100000;
  const {handle,calls}=fixture({admission:false,clock:()=>now});
  for(let i=0;i<60;i++) assert.equal((await handle(request(data(),'Bearer '+i.toString(16).padStart(64,'0')))).status,403);
  assert.equal((await handle(request(data(),'Bearer '+'f'.repeat(64)))).status,429);
  assert.equal(calls.length,60);
  now+=60000;
  assert.equal((await handle(request(data(),'Bearer '+'f'.repeat(64)))).status,403);
});

test('varying proxy addresses cannot bypass the isolate-wide database-work limit', async () => {
  const {handle,calls}=fixture({admission:false});
  for(let i=0;i<240;i++) assert.equal((await handle(request(data(),'Bearer '+i.toString(16).padStart(64,'0'),{'x-forwarded-for':'192.0.2.'+i}))).status,403);
  assert.equal((await handle(request(data(),undefined,{'x-forwarded-for':'198.51.100.1'}))).status,429);
  assert.equal(calls.length,240);
});

test('SQL rejection starts a short cooldown before another upload is read or queried', async () => {
  let now=100000;
  const {handle,calls}=fixture({clock:()=>now,exchange:()=>({error:'quota',retry_after:3600})});
  assert.equal((await handle(request())).status,507);
  const blocked=new Request('https://example.com/statistics-sync',{method:'POST',headers:{authorization:'Bearer '+credential,'content-type':'application/json'},body:'invalid JSON'});
  assert.equal((await handle(blocked)).status,507);
  assert.equal(calls.length,2);
  now+=60001;
  assert.equal((await handle(request())).status,507);
  assert.equal(calls.length,4);
});
