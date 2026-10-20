import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { createAccountHandler } from '../supabase/functions/statistics-account/handler.mjs';
const owner='11111111-1111-4111-8111-111111111111',session='22222222-2222-4222-8222-222222222222';
const base='https://project.supabase.co',capability='c'.repeat(64),service='SERVER-ONLY-SECRET';
const user=()=>({id:owner,email_confirmed_at:'2026-10-20T00:00:00Z',is_anonymous:false,identities:[{provider:'github'}]});
const jwt=(changes={})=>'e30.'+Buffer.from(JSON.stringify({sub:owner,session_id:session,role:'authenticated',iss:base+'/auth/v1',exp:2000000000,...changes})).toString('base64url')+'.c2ln';
const request=(body={action:'activate',capability},token=jwt(),headers={})=>new Request(base+'/functions/v1/statistics-account',{
  method:'POST',headers:{authorization:'Bearer '+token,'content-type':'application/json',...headers},body:JSON.stringify(body)});
function fixture({identity=user(),result={ok:true,owned:true},checked=true,bodyTimeoutMs=5000,fetcher}={}){
  const calls=[];
  const handler=createAccountHandler({url:base,serviceKey:service,clock:()=>1792540000000,bodyTimeoutMs,
    fetcher:fetcher|| (async(url,options)=>{calls.push({url,options});return url.endsWith('/user')?Response.json(identity,{status:checked?200:401}):Response.json(result);})});
  return {handler,calls};
}
test('account identity comes from verified Auth; only hashed capability reaches SQL',async()=>{
  const {handler,calls}=fixture();const response=await handler(request());assert.equal(response.status,200);
  assert.deepEqual(await response.json(),{ok:true,owned:true});assert.equal(calls.length,2);
  assert.equal(calls[0].options.headers.authorization,'Bearer '+jwt());
  assert.deepEqual(JSON.parse(calls[1].options.body),{p_owner:owner,p_session:session,p_action:'activate',p_group:createHash('sha256').update(capability).digest('hex')});
  assert.equal(calls[1].options.headers.authorization,'Bearer '+service);
  assert.ok(!calls[1].options.body.includes(capability));assert.equal(response.headers.get('cache-control'),'no-store');
});
test('spoofed metadata, anonymous, unverified or non-GitHub identities cannot provision',async()=>{
  for(const identity of [{...user(),identities:[],user_metadata:{provider:'github'}},{...user(),is_anonymous:true},{...user(),email_confirmed_at:null},{...user(),identities:[{provider:'email'}]}]){
    const {handler,calls}=fixture({identity});assert.equal((await handler(request())).status,403);assert.equal(calls.length,1);
  }
});
test('JWT sub/session/issuer/role/expiration are bound to checked Auth user',async()=>{
  for(const changes of [{sub:session},{session_id:null},{session_id:[]},{iss:'https://attacker.test/auth/v1'},{role:'service_role'},{exp:1},{exp:'2000000000'}]){
    const {handler,calls}=fixture();assert.equal((await handler(request(undefined,jwt(changes)))).status,401);assert.equal(calls.length,1);
  }
  const {handler,calls}=fixture({checked:false});assert.equal((await handler(request())).status,401);assert.equal(calls.length,1);
});
test('ownership and arbitrary RPC parameters cannot be supplied by clients',async()=>{
  const {handler,calls}=fixture();
  for(const body of [{action:'activate',capability,owner},{action:'delete',capability},{action:'activate',capability:null},{action:'status',capability:[]},[],null])assert.equal((await handler(request(body))).status,400);
  assert.equal(calls.length,0);
  assert.equal((await handler(request(undefined,'invalid'))).status,401);
  assert.equal((await handler(request(undefined,undefined,{'content-length':'2049'}))).status,413);
  assert.equal((await handler(request(undefined,undefined,{'content-type':'application/jsonp'}))).status,415);
});
test('revocation uses authenticated owner; sanitized status and errors only',async()=>{
  const {handler,calls}=fixture();assert.equal((await handler(request({action:'revoke',capability:null}))).status,200);
  assert.equal(JSON.parse(calls[1].options.body).p_group,null);
  for(const [error,status] of [['session',401],['other_group',409],['closed',503],['capacity',429],['rotation_limit',429],['database secret '+service,503]]){
    const {handler}=fixture({result:{error}});const response=await handler(request());assert.equal(response.status,status);
    assert.ok(!(await response.text()).includes(service));
  }
  const status=await fixture({result:{owned:true,has_group:true,server_secret:service}}).handler(request({action:'status',capability}));
  assert.deepEqual(await status.json(),{owned:true,has_group:true});
});
test('bounded streams/timeouts/concurrency and local request throttle',async()=>{
  const {handler}=fixture({bodyTimeoutMs:10});
  for(const body of [new ReadableStream({start(c){c.enqueue(new Uint8Array(2049));c.close();}}),new ReadableStream({})]){
    const response=await handler(new Request(base,{method:'POST',headers:{authorization:'Bearer '+jwt(),'content-type':'application/json'},body,duplex:'half'}));assert.equal(response.status,400);
  }
  let release;const blocked=new Promise(resolve=>release=resolve);
  const busy=fixture({fetcher:async()=>{await blocked;return Response.json(user(),{status:401});}}).handler;
  const pending=Array.from({length:4},()=>busy(request()));await new Promise(resolve=>setTimeout(resolve,10));
  assert.equal((await busy(request())).status,503);release();await Promise.all(pending);
  const throttled=fixture({checked:false});
  for(let i=0;i<60;i++)assert.equal((await throttled.handler(request())).status,401);
  assert.equal((await throttled.handler(request())).status,429);assert.equal(throttled.calls.length,60);
});
