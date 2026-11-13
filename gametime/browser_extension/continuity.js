/* Durable browser fallback. Pure model is shared by worker and regression tests. */
const CONTINUITY_LIMIT = 25000;
const copyContinuity = value => JSON.parse(JSON.stringify(value));
function localDay(stamp, minute) {
  const d = new Date(stamp * 1000);
  if (d.getHours() * 60 + d.getMinutes() < minute) d.setDate(d.getDate() - 1);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function localClock(day, minute, renewal = 0) {
  const [y,m,d] = day.split('-').map(Number), when = new Date(y,m-1,d,Math.floor(minute/60),minute%60);
  if (minute < renewal) when.setDate(when.getDate()+1);
  return when.getTime()/1000;
}
function browserMember(members, path, host) {
  const app = (path || '').split(/[\\/]/).at(-1).toLowerCase(), site = host.replace(/^www\./,'');
  return members.some(m => m.kind === 'app' && m.value.split(/[\\/]/).at(-1).toLowerCase() === app ||
    m.kind === 'site' && (site === m.value.replace(/^www\./,'') || site.endsWith('.'+m.value.replace(/^www\./,''))) ||
    m.kind === 'category' && (m.value === 'sites' && !!host || m.value === 'apps' && !!app));
}
function budgetActive(budget, stamp) {
  const day = localDay(stamp,budget.renewal), weekday = (new Date(day+'T12:00:00').getDay()+6)%7;
  return budget.days.includes(weekday);
}
function advanceFocus(focus, seconds, end, dayStart, notices) {
  let cursor = end-seconds;
  while (seconds>0 && focus.running) {
    const amount = Math.min(seconds,focus.remaining);
    focus.remaining = Math.max(0,focus.remaining-amount); seconds-=amount; cursor+=amount;
    if (focus.remaining>0) break;
    if (focus.phase==='focus') {
      focus.round++; focus.total++;
      const day=localDay(cursor,dayStart);
      if (focus.day!==day) {focus.day=day;focus.today=0;}
      focus.today++;
      notices.push({id:`focus:${focus.token}:${focus.round}`,text:'Focus complete. Time for a break.'});
      if (!focus.settings.rounds) {focus.running=false;notices.at(-1).text='Focus session complete.';}
      else {
        focus.phase=focus.round%focus.settings.rounds===0?'long_break':'short_break';
        focus.remaining=focus.settings[focus.phase]*60;
        if (!focus.remaining) {focus.phase='focus';focus.remaining=focus.settings.work*60;focus.running=false;}
      }
    } else {
      focus.phase='focus';focus.remaining=focus.settings.work*60;focus.running=false;
      notices.push({id:`break:${focus.token}:${focus.round}`,text:'Break complete. Start the next focus session when ready.'});
    }
    if (!amount && focus.running && !focus.remaining) break;
  }
}
function dueBudget(budget, now) {
  const row=budget.runtime, limit=budget.usage?budget.seconds:Infinity;
  return budget.steps.filter(s => !s.session_choice && (s.kind==='break' ? row.breaks?.[s.id]?.until>now :
    s.time_mode==='clock' ? now>=localClock(budget.day,s.clock_minute,budget.renewal) :
    s.time_mode==='sessions' ? (budget.sessions || 0)>s.offset :
    s.time_mode==='usage' ? budget.used>=s.offset : s.offset<=0 ? budget.used>=Math.max(0,limit+s.offset) :
    row.expired!=null && now>=row.expired+s.offset));
}
function updateBudget(budget, now, notices) {
  const day=localDay(now,budget.renewal);
  if (budget.day!==day) {
    const breaks=Object.fromEntries(Object.entries(budget.runtime.breaks || {}).filter(([,s])=>s.until>now));
    const grant=budget.runtime.grant?.until>now?budget.runtime.grant:null;
    budget.day=day;budget.used=0;budget.sessions=0;budget.runtime={expired:null,used_extension:false,grant,delivered:[],breaks};
  }
  if (!budgetActive(budget,now)) return;
  const row=budget.runtime, limit=budget.usage?budget.seconds:Infinity;
  row.delivered ||= []; row.breaks ||= {}; row.used_extension ||= false;
  if (budget.used<limit) row.expired=null;
  else if (row.expired==null) row.expired=now;
  for (const step of budget.steps.filter(s=>s.kind==='break' && !s.session_choice)) {
    const state=row.breaks[step.id] ||= {next_at:step.offset,until:null};
    if (step.time_mode==='clock') {
      const deadline=localClock(budget.day,step.clock_minute,budget.renewal);
      if (state.until!=null && now>=state.until) state.until=null;
      if (state.clock_day!==budget.day) {state.clock_day=budget.day;state.triggered=state.until!=null && state.until>=deadline;}
      if (!state.triggered && now>=deadline) {
        state.triggered=true;
        if (budget.used<limit && now<deadline+step.break_minutes*60) state.until=deadline+step.break_minutes*60;
      }
    } else {
      const sessions=step.time_mode==='sessions', measured=sessions?(budget.sessions || 0):budget.used;
      if (state.until!=null && now>=state.until) {state.until=null;state.next_at=measured+step.offset;}
      if (state.until==null && (sessions?measured>state.next_at:state.next_at<limit && state.next_at<=measured) && budget.used<limit)
        state.until=now+step.break_minutes*60;
    }
  }
  for (const step of dueBudget(budget,now).filter(s=>s.kind==='notify' && !row.delivered.includes(s.id))) {
    row.delivered.push(step.id);notices.push({id:`budget:${budget.id}:${budget.day}:${step.id}`,text:budget.name,sound:step.sound});
  }
}
function offlinePolicy(snapshot, now=Date.now()/1000) {
  const f=snapshot.focus;
  const policy={active:f.running && f.phase==='focus',tracking:snapshot.tracking,
    local_sites:snapshot.local_sites || [],bridge_port:snapshot.bridge_port,
    mode:f.all?'allowlist':'blocklist',block:f.domains,allow:[],remaining:f.remaining,
    lease_seconds:90,language:snapshot.language,restrictions:[],restriction_version:1,choice_rules:[]};
  for (const b of snapshot.budgets) {
    if (!budgetActive(b,now)) continue;
    const domains=b.members.filter(m=>m.kind==='site').map(m=>m.value);
    const all=b.members.some(m=>m.kind==='category' && m.value==='sites') || browserMember(b.members,snapshot.path,'');
    const due=dueBudget(b,now), regular=due.filter(s=>!['notify','break'].includes(s.kind));
    const selected=regular.length?regular:due.filter(s=>s.kind==='break');
    const zero=b.usage && b.seconds===0;
    let kinds=selected.map(s=>s.kind==='break'?s.break_mode:s.kind==='restrict'?'cover':s.kind);
    const legacyDue=b.enforce && b.usage && b.used>=b.seconds;
    if (zero || legacyDue) kinds.push('cover');
    const requiresDesktop = b.steps.some(s=>s.session_choice);
    // A disconnected choice is an in-page gate, never a navigation rule.
    // Otherwise each brief outage redirects every matching background tab,
    // then reconnect restores/reloads them and destroys the current visit.
    if (requiresDesktop) policy.choice_rules.push({domains,all,name:b.name,requires_desktop:true});
    if (!kinds.length) continue;
    const kind=kinds.includes('close')?'close':kinds.some(k=>k!=='redirect')?'cover':'redirect';
    const entry={key:b.id,name:b.name,all,domains,kind,
      minutes:zero || b.runtime.used_extension || !regular.length ? 0 : Math.min(...selected.map(s=>s.extension_minutes??b.extension_minutes)),
      grant:zero?null:b.runtime.grant || null,is_break:!zero && !regular.length && !legacyDue};
    if (kind==='redirect') entry.redirect_url=selected.find(s=>s.break_mode==='redirect'||s.kind==='redirect')?.redirect_url || '';
    if (entry.is_break) entry.break_until=Math.max(0,...Object.values(b.runtime.breaks || {}).map(s=>s.until || 0));
    policy.restrictions.push(entry);
  }
  return policy;
}

class BrowserJournal {
  constructor(value={},uuid=()=>crypto.randomUUID().replaceAll('-','')) {
    this.uuid=uuid;this.value={stream:uuid(),seq:0,ack:0,records:[],snapshot:null,checkpoint:null,notices:[],dirtyBudgets:[],...copyContinuity(value)};
  }
  append(record) {
    if (this.value.records.length>=CONTINUITY_LIMIT) throw Error('Browser storage is full. Reconnect the desktop application.');
    record.seq=++this.value.seq;this.value.records.push(record);return record;
  }
  observe(observation,stamp,session) {
    const v=this.value,previous=v.checkpoint,snapshot=v.snapshot;
    if(previous && stamp<=previous.at) return;
    if (previous && previous.session===session && stamp>previous.at && stamp-previous.at<=45) {
      const record={kind:'sample',start:previous.at,end:stamp,host:previous.host || '',
        active:!!(previous.active && !observation.locked && !observation.idle),redirect:previous.redirect || '',timer:snapshot?.focus.running?snapshot.focus.token:''};
      if (snapshot && (record.active && snapshot.tracking || record.timer)) {
        this.append(record);this.advance(record);
      }
    }
    v.checkpoint={...observation,at:stamp,session};
    // Wall-clock actions and renewal still run while another app is focused,
    // and after sleep; only observed active intervals add usage above.
    if(snapshot) for(const b of snapshot.budgets) {
      const before=JSON.stringify(b.runtime);
      updateBudget(b,stamp,v.notices);
      if(before!==JSON.stringify(b.runtime) && !v.dirtyBudgets.includes(b.id)) v.dirtyBudgets.push(b.id);
    }
  }
  advance(record) {
    const s=this.value.snapshot;if (!s) return;
    const start=Math.max(record.start,s.at),seconds=Math.max(0,record.end-start);
    if (!seconds) return;
    if (record.timer===s.focus.token) advanceFocus(s.focus,seconds,record.end,s.day_start,this.value.notices);
    for (const b of s.budgets) {
      const before=JSON.stringify(b.runtime);
      // Split renewal boundaries in local calendar time, including DST.
      let cursor=start;
      while (cursor<record.end) {
        updateBudget(b,cursor,[]);
        const d=new Date(localClock(b.day,b.renewal)*1000);d.setDate(d.getDate()+1);
        const end=Math.min(record.end,d.getTime()/1000);
        if (end<=cursor) break;
        if (record.active && s.tracking && record.redirect!==b.id && browserMember(b.members,s.path,record.host)) {
          b.used+=end-cursor;
          const key=browserMember(b.members,s.path,'')?'app:'+s.path:'site:'+record.host;
          const previous=b.session_visit;
          if (!previous || previous.key!==key || cursor>previous.finish+.002) b.sessions=(b.sessions || 0)+1;
          b.session_visit={key,finish:end};
        }
        cursor=end;
      }
      updateBudget(b,record.end,this.value.notices);
      if (before!==JSON.stringify(b.runtime) && !this.value.dirtyBudgets.includes(b.id)) this.value.dirtyBudgets.push(b.id);
    }
    s.at=record.end;
  }
  accept(result) {
    const v=this.value;
    if (!Number.isSafeInteger(result.ack) || result.ack<v.ack || result.ack>v.seq) throw Error('Invalid browser journal receipt.');
    v.ack=result.ack;v.records=v.records.filter(r=>r.seq>v.ack);
    // Do not overwrite the browser's unacknowledged offline actions/state.
    if (!v.records.length) {v.snapshot=copyContinuity(result.snapshot);v.notices=[];v.dirtyBudgets=[];}
  }
  effects(stamp) {
    const v=this.value;
    if(v.dirtyBudgets.length && v.checkpoint) v.checkpoint.at=stamp;
    for(const key of v.dirtyBudgets) {
      const b=v.snapshot.budgets.find(b=>b.id===key);if(!b) continue;
      const row=b.runtime;
      const breaks=Object.fromEntries(Object.entries(row.breaks || {}).filter(([id])=>b.steps.some(s=>s.id===id && s.kind==='break')).map(([id,value])=>{
        const {spec,...state}=value;return [id,state];
      }));
      this.append({kind:'budget.state',at:stamp,key,day:b.day,fingerprint:b.fingerprint,
        state:{expired:row.expired??null,used_extension:!!row.used_extension,grant:row.grant || null,
          delivered:(row.delivered || []).filter(id=>b.steps.some(s=>s.id===id && s.kind==='notify')),breaks}});
    }
    v.dirtyBudgets=[];
  }
  command(action,stamp) {
    const s=this.value.snapshot,f=s?.focus;
    if (!f || !['focus.start','focus.pause','focus.stop'].includes(action)) throw Error('This action needs the desktop application.');
    const token=this.uuid();this.append({kind:action,at:stamp,base:f.token,token});
    if (action==='focus.stop') {f.phase='focus';f.remaining=f.settings.work*60;f.round=0;}
    else if (action==='focus.start' && f.phase==='focus' && !f.remaining) {f.remaining=f.settings.work*60;f.round=0;}
    f.running=action==='focus.start';f.token=token;s.at=stamp;
    if(this.value.checkpoint) this.value.checkpoint.at=stamp;
  }
}

class BrowserContinuityWorker {
  constructor() {this.model=null;this.scope='';this.session='';this.connected=false;this.savedChunks=new Map();this.savedThrough=0;this.savedAck=0;this.error='';}
  async load(pairing,browser) {
    const scope=pairing?`${pairing.port}:${pairing.token}`:'';
    if (scope===this.scope && this.model) return;
    const stored=await chrome.storage.local.get('browserContinuity');
    const sessionData=await chrome.storage.session.get('continuitySession');
    this.session=sessionData.continuitySession || crypto.randomUUID();
    if (!sessionData.continuitySession) await chrome.storage.session.set({continuitySession:this.session});
    let value=stored.browserContinuity;
    if (!value || value.scope!==scope) value={scope,browser};
    const keys=[];for(let i=Math.floor((value.ack || 0)/128);i<=Math.floor((value.seq || 0)/128);i++) keys.push('continuityChunk:'+i);
    const chunks=value.seq?await chrome.storage.local.get(keys):{};
    value.records=keys.flatMap(key=>chunks[key] || []).filter(r=>r.seq>(value.ack || 0) && r.seq<=value.seq);
    this.scope=scope;this.browser=browser;this.model=new BrowserJournal(value);
    this.savedChunks=new Map(Object.entries(chunks).map(([key,records])=>[key,JSON.stringify(records)]));
    this.savedThrough=value.seq || 0;this.savedAck=value.ack || 0;
  }
  async save() {
    const v=this.model.value,touched=new Set(),writes={},updated=new Map();
    for(const r of v.records) if(r.seq>this.savedThrough) touched.add(Math.floor(r.seq/128));
    if(v.ack!==this.savedAck) touched.add(Math.floor(v.ack/128));
    for(const index of touched) {
      const records=v.records.filter(r=>Math.floor(r.seq/128)===index),key='continuityChunk:'+index,signature=JSON.stringify(records);
      if(records.length && this.savedChunks.get(key)!==signature) writes[key]=records;
      if(records.length) updated.set(key,signature);
    }
    const {records,...meta}=v;writes.browserContinuity={...meta,scope:this.scope,browser:this.browser};
    // Persist records and state together before requests, actions or receipts.
    await chrome.storage.local.set(writes);
    const obsolete=[...this.savedChunks.keys()].filter(key=>(Number(key.split(':')[1])+1)*128-1<=v.ack || !v.records.length);
    // Metadata already committed: obsolete chunks are ignored on load, so a
    // cleanup failure must not turn a durable command into a reported failure.
    if(obsolete.length && chrome.storage.local.remove) await chrome.storage.local.remove(obsolete).catch(()=>{});
    for(const key of obsolete) this.savedChunks.delete(key);
    for(const [key,value] of updated) this.savedChunks.set(key,value);
    this.savedThrough=v.seq;this.savedAck=v.ack;
  }
  async sample(tab,host,redirect) {
    const timeout=this.model.value.snapshot?.idle_timeout_seconds || 0;
    const state=chrome.idle?.queryState ? await chrome.idle.queryState(timeout || 60) : 'active';
    const now=Date.now()/1000,mediaEnabled=!!timeout && this.model.value.snapshot?.media_prevents_idle;
    let mediaAt=mediaEnabled?this.model.value.checkpoint?.mediaAt:null;
    if(mediaEnabled && chrome.tabs?.query) {
      const audible=await chrome.tabs.query({audible:true});
      if(audible.some(t=>!t.incognito && t.audible && !t.mutedInfo?.muted)) mediaAt=now;
    }
    const recentMedia=Number.isFinite(mediaAt) && mediaAt<=now && now-mediaAt<timeout;
    const locked=state==='locked',idle=!!timeout && state==='idle' && !recentMedia;
    const active=!!tab && !tab.incognito && !locked && !idle && !braveNewTab(tab,this.browser);
    const {records,...meta}=this.model.value,before={...copyContinuity(meta),records:[...records]};
    try {
      this.model.observe({active,host:active?host:'',redirect:active?redirect:'',locked,idle,mediaAt},now,this.session);
      await this.save();
    } catch(error) {this.model.value=before;throw error;}
  }
  async exchange(pairing) {
    for(let attempt=0;attempt<8;attempt++) {
      const v=this.model.value,records=v.records.slice(0,128);
      const response=await fetch(`http://127.0.0.1:${pairing.port}/continuity`,{method:'POST',cache:'no-store',signal:AbortSignal.timeout(3000),
        headers:{'Content-Type':'application/json','Authorization':'Bearer '+pairing.token},
        body:JSON.stringify({version:1,local_version:1,stream:v.stream,browser:this.browser,records})});
      if(response.status===404) return false;
      if(!response.ok) throw Error('Browser continuity unavailable');
      const reply=await response.json();if(!reply.ok) throw Error(reply.error || 'Browser continuity unavailable');
      const before=v.ack;this.model.accept(reply.result);await this.save();
      this.connected=!v.records.length;
      if(this.connected) {this.policy=reply.result.policy;this.error='';}
      if(!v.records.length || v.ack===before || records.length<128) break;
    }
    return true;
  }
  async offline() {
    this.connected=false;
    const s=this.model?.value.snapshot;if(!s) return null;
    this.model.effects(Date.now()/1000);
    const notices=this.model.value.notices.splice(0);
    // Consume identifiers durably before displaying, so worker restarts cannot repeat them.
    try {await this.save();} catch(error) {this.model.value.notices.unshift(...notices);throw error;}
    if(chrome.notifications?.create) for(const notice of notices) {
      const hu=s.language==='hu',texts={'Focus complete. Time for a break.':'Fókusz kész. Ideje szünetet tartani.',
        'Focus session complete.':'Fókuszszakasz befejezve.','Break complete. Start the next focus session when ready.':'A szünet véget ért. Indítsd a következő fókuszszakaszt, amikor készen állsz.'};
      await chrome.notifications.create(notice.id,{type:'basic',iconUrl:'icons/128.png',title:'Keep Improving',
        message:hu?(texts[notice.text] || notice.text):notice.text,silent:!s.sound || notice.sound===false}).catch(()=>{});
    }
    return offlinePolicy(s);
  }
  view() {
    const s=this.model?.value.snapshot;if(!s) return null;
    const focus=copyContinuity(s.focus);if(focus.day!==localDay(Date.now()/1000,s.day_start)) focus.today=0;
    return {offline:true,at:s.at,language:s.language,focus,budgets:s.budgets.filter(b=>budgetActive(b,Date.now()/1000)).map(b=>({id:b.id,name:b.name,remaining:b.usage?Math.max(0,b.seconds-b.used):null})),
      pending:this.model.value.records.length,error:this.error};
  }
  async control(action) {
    if(!this.model?.value.snapshot) return {ok:false};
    if(!['state','live'].includes(action)) {
      const tab=await activeTab();await this.sample(tab,publicHost(tab),'');
      const before=copyContinuity(this.model.value);
      try {this.model.command(action,Date.now()/1000);await this.save();}
      catch(error) {this.model.value=before;throw error;}
      await setPolicy(offlinePolicy(this.model.value.snapshot));await applyPolicyTabs(tab);
    }
    return {ok:true,result:this.view(),revision:'offline'};
  }
  async extend(host,token) {
    const s=this.model?.value.snapshot;if(!s) return false;
    const current=offlinePolicy(s),decision=siteDecision(host,current,token);
    if(!(decision.minutes>0)) return false;
    const now=Date.now()/1000,until=now+decision.minutes*60;
    let entries=current.restrictions.filter(e=>e.all || e.domains.some(h=>host===h || host.endsWith('.'+h)));
    if(entries.some(e=>!e.is_break)) entries=entries.filter(e=>!e.is_break);
    entries=entries.filter(e=>!(e.grant?.subject===`site:${host}:${token}` && e.grant.until>now));
    const budgets=entries.map(e=>s.budgets.find(b=>b.id===e.key));
    if(budgets.some(b=>!b || b.runtime.used_extension)) return false;
    const before=copyContinuity(this.model.value);
    try {
    for(const b of budgets) {
      b.runtime.used_extension=true;b.runtime.grant={subject:`site:${host}:${token}`,until};
      if(!this.model.value.dirtyBudgets.includes(b.id)) this.model.value.dirtyBudgets.push(b.id);
    }
    this.model.effects(now);await this.save();
    } catch(error) {this.model.value=before;throw error;}
    return true;
  }
}
if(typeof module!=='undefined') module.exports={BrowserJournal,BrowserContinuityWorker,offlinePolicy,advanceFocus,localDay,localClock,updateBudget,browserMember};
