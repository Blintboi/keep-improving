// Only provisioning/management uses an account. Statistics remain E2EE capabilities.
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const CAPABILITY=/^[0-9a-f]{64}$/;
const HEADERS={'content-type':'application/json','cache-control':'no-store','x-content-type-options':'nosniff',
  'content-security-policy':"default-src 'none'; frame-ancestors 'none'",'referrer-policy':'no-referrer'};
function reply(status,body,retry=0){return new Response(JSON.stringify(body),{status,headers:{...HEADERS,...(retry?{'retry-after':String(retry)}:{})}});}
async function bodyJSON(request,timeout){
  const reader=request.body?.getReader(); if(!reader) throw Error('body');
  let timer;
  const read=async()=>{
    let size=0; const chunks=[];
    for(;;){const {value,done}=await reader.read();if(done)break;size+=value.byteLength;if(size>2048)throw Error('body');chunks.push(value);}
    const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
    return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
  };
  try{return await Promise.race([read(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('body')),timeout);})]);}
  finally{clearTimeout(timer);void reader.cancel().catch(()=>{});}
}
export function createAccountHandler({url,serviceKey,fetcher=fetch,clock=Date.now,bodyTimeoutMs=5000}){
  let active=0,minute=-1,total=0;
  const requests=new Map(),owners=new Map();
  const handle=async request=>{
    if(request.method!=='POST')return reply(405,{error:'method'});
    const authorization=request.headers.get('authorization')||'';
    if(authorization.length>16384||!/^Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(authorization))return reply(401,{error:'session'});
    if(!/^application\/json(?:\s*;|$)/i.test(request.headers.get('content-type')||'')
      ||!['','identity'].includes(request.headers.get('content-encoding')||''))return reply(415,{error:'content_type'});
    const length=request.headers.get('content-length');
    if(length&&(!/^[0-9]{1,9}$/.test(length)||Number(length)>2048))return reply(413,{error:'body'});
    if(!url||!serviceKey)return reply(503,{error:'configuration'},300);
    // Best-effort isolate-local throttle. Durable storage is never allocated here.
    // Provider invocation limits still apply before this code can execute.
    const bucket=Math.floor(clock()/60000);
    if(bucket!==minute){minute=bucket;total=0;requests.clear();owners.clear();}
    const ip=(request.headers.get('x-forwarded-for')||'unknown').split(',').at(-1).trim().slice(0,80);
    const hits=(requests.get(ip)||0)+1;
    if(requests.size<512||requests.has(ip))requests.set(ip,Math.min(hits,61));
    if(++total>120||hits>60)return reply(429,{error:'rate'},60);
    if(active>=4)return reply(503,{error:'busy'},60);
    active++;
    try{
      let body;
      try{
        body=await bodyJSON(request,bodyTimeoutMs);
        if(!body||typeof body!=='object'||Array.isArray(body)
          ||Object.keys(body).some(key=>!['action','capability'].includes(key))
          ||!['status','activate','rotate','revoke'].includes(body.action)
          ||!(body.action==='revoke'&&body.capability===null)&&!(typeof body.capability==='string'&&CAPABILITY.test(body.capability)))throw Error('body');
      }catch{return reply(400,{error:'body'});}
      const base=url.replace(/\/$/,'');
      const checked=await fetcher(base+'/auth/v1/user',{headers:{apikey:serviceKey,authorization},signal:AbortSignal.timeout(5000),redirect:'error'});
      if(!checked.ok)return reply(401,{error:'session'});
      const user=await checked.json();
      // Only the Auth server's verified identity is authoritative. Never metadata.
      if(!user||typeof user.id!=='string'||!UUID.test(user.id)||user.is_anonymous===true||!user.email_confirmed_at
        ||!Array.isArray(user.identities)||!user.identities.some(identity=>identity.provider==='github'))return reply(403,{error:'identity'});
      let claims;
      try{
        const encoded=authorization.slice(7).split('.')[1];
        claims=JSON.parse(atob(encoded.replace(/-/g,'+').replace(/_/g,'/')));
        if(claims.sub!==user.id||claims.role!=='authenticated'||claims.iss!==base+'/auth/v1'
          ||typeof claims.session_id!=='string'||!UUID.test(claims.session_id)||!Number.isSafeInteger(claims.exp)||claims.exp*1000<=clock())throw Error('claims');
      }catch{return reply(401,{error:'session'});}
      // The key comes only from Auth's checked user. Changing IP, JWT or the
      // requested capability cannot bypass this account's management throttle.
      const ownerHits=(owners.get(user.id)||0)+1;
      if(owners.size>=512&&!owners.has(user.id))return reply(429,{error:'rate'},60);
      owners.set(user.id,Math.min(ownerHits,13));
      if(ownerHits>12)return reply(429,{error:'rate'},60);
      let group=null;
      if(body.capability!==null)group=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(body.capability))),v=>v.toString(16).padStart(2,'0')).join('');
      const response=await fetcher(base+'/rest/v1/rpc/gametime_sync_account',{method:'POST',
        headers:{apikey:serviceKey,authorization:'Bearer '+serviceKey,'content-type':'application/json'},
        body:JSON.stringify({p_owner:user.id,p_session:claims.session_id,p_action:body.action,p_group:group}),
        signal:AbortSignal.timeout(5000),redirect:'error'});
      if(!response.ok)throw Error('storage');
      const result=await response.json();
      const allowed=['input','session','disabled','revoked','exists','other_group','closed','capacity','rotation_limit','rate'];
      if(result.error){
        if(!allowed.includes(result.error))throw Error('storage');
        const status=result.error==='session'?401:['other_group','exists'].includes(result.error)?409:
          ['rate','capacity','rotation_limit'].includes(result.error)?429:result.error==='closed'?503:403;
        return reply(status,{error:result.error},status===429?(result.error==='rate'?60:3600):status===503?300:0);
      }
      if(body.action==='status')return reply(200,{owned:result.owned===true,has_group:result.has_group===true});
      if(result.ok!==true)throw Error('storage');
      return reply(200,{ok:true,owned:result.owned===true});
    }catch{return reply(503,{error:'unavailable'},300);}finally{active--;}
  };
  return async request=>{try{return await handle(request);}finally{if(request.body&&!request.body.locked)void request.body.cancel().catch(()=>{});}};
}
