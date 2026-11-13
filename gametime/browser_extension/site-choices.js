/* Active-tab visits and authenticated desktop choices. No page URLs leave the extension. */
class WebsiteChoices {
  constructor() { this.visit=null; this.loaded=false; this.pending=null; this.showing=new Map(); }
  async load() {
    if(this.loaded) return;
    this.loaded=true; this.visit=(await chrome.storage.session.get('websiteChoiceVisit')).websiteChoiceVisit || null;
    this.showing=new Map((await chrome.storage.session.get('websiteChoiceShowing')).websiteChoiceShowing || []);
  }
  async call(pairing,action,data) {
    const response=await fetch(`http://127.0.0.1:${pairing.port}/control`,{method:'POST',cache:'no-store',signal:AbortSignal.timeout(4000),
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+pairing.token},body:JSON.stringify({action,data})});
    if(!response.ok) throw Error('Choice connection unavailable');
    const reply=await response.json();if(!reply.ok) throw Error('Choice unavailable');return reply.result;
  }
  async send(tabId,value) {
    const message={action:'choice.overlay',value};
    try {return await chrome.tabs.sendMessage(tabId,message,{frameId:0});}
    catch {
      if(!value) return;
      await chrome.scripting.executeScript({target:{tabId},files:['site-choice-overlay.js']});
      return chrome.tabs.sendMessage(tabId,message,{frameId:0});
    }
  }
  rule(host,policy) {
    return host && (policy.choice_rules || []).find(r=>r.all || r.domains.some(h=>host===h || host.endsWith('.'+h)));
  }
  async hide(tabId) {
    if(!this.showing.has(tabId))return;
    await this.send(tabId,null).catch(()=>{});this.showing.delete(tabId);
    await chrome.storage.session.set({websiteChoiceShowing:[...this.showing]});
  }
  async sync(tab,host,policy,pairing,browser) {
    await this.load();
    // A parked document stays covered when another tab, extension popup or
    // application takes focus. Only a removed rule or this tab's own release
    // may dismiss its question; foreground visit accounting stays separate.
    for(const [tabId,coveredHost] of this.showing) if(!this.rule(coveredHost,policy))await this.hide(tabId);
    // Like desktop site sessions, tabs on the same domain share the current
    // uninterrupted visit; a different domain or application ends it.
    const key=tab && host && !tab.incognito ? `${browser}:${host}` : '';
    if(this.visit?.key!==key) {
      this.visit=key?{key,token:crypto.randomUUID().replaceAll('-','')}:null;
      await chrome.storage.session.set({websiteChoiceVisit:this.visit});
    }
    const relevant=key && this.rule(host,policy);
    const regular=host && siteDecision(host,policy,blockedTabs[tab?.id]?.token || '').kind;
    this.pending=null;
    if(!relevant || regular) {if(tab)await this.hide(tab.id);return;}
    const data={browser,domain:host,visit:this.visit.token};
    let result;
    // Choice/control failures do not mean the entire restriction connection
    // failed. Keep its valid policy and wait in this document without spending
    // an allowance or replacing the accepted visit token.
    try {if(!relevant.requires_desktop) result=await this.call(pairing,'choices.status',data);}
    catch { /* Retry on the next normal choice tick. */ }
    const current=await activeTab();
    if(!current || current.id!==tab.id || publicHost(current)!==host) return;
    if(result && !result.choice) {await this.hide(tab.id);return;}
    const value={...(result?.choice || {offline:true,name:relevant.name || '',options:[]}),visit:this.visit.token,language:policy.language || 'en'};
    this.pending={tabId:tab.id,host,data,value};
    // A content script caches unchanged renders; this also heals a full page navigation.
    // A closing/navigating tab or a protected document may reject injection.
    // That is local to this tab; it must never trigger global offline blocking.
    await this.send(tab.id,value).catch(()=>{});
    if(this.showing.get(tab.id)!==host){this.showing.set(tab.id,host);await chrome.storage.session.set({websiteChoiceShowing:[...this.showing]});}
  }
  async choose(message,sender,pairing) {
    const pending=this.pending,tab=await activeTab();
    if(!pending || pending.value.offline || sender.id!==chrome.runtime.id || sender.frameId!==0 || sender.tab?.incognito ||
      sender.tab?.id!==pending.tabId || tab?.id!==pending.tabId || publicHost(tab)!==pending.host ||
      publicHost({url:sender.url})!==pending.host || message.visit!==pending.data.visit ||
      message.budget!==pending.value.budget || message.step!==pending.value.step) return {ok:false};
    const result=await this.call(pairing,'choices.choose',{...pending.data,budget:message.budget,step:message.step,choice:message.choice});
    if(!result.accepted) return {ok:false};
    // Apply only if the response still belongs to the foreground visit.
    if(this.pending===pending) {
      if(result.choice) {
        const value={...result.choice,visit:pending.data.visit,language:pending.value.language};
        this.pending={...pending,value};await this.send(pending.tabId,value);
      } else {this.pending=null;await this.hide(pending.tabId);}
    }
    return {ok:true};
  }
}
