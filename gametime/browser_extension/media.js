/* Only explicitly selected public sites leave the browser as media observations. */
(() => {
  const canonical=host=>host.replace(/^www\./,'');
  function select(tabs,sites) {
    const wanted=new Set((sites || []).map(canonical)),seen=new Set(),result=[];
    for(const tab of tabs) {
      if(!tab.audible || tab.mutedInfo?.muted || tab.incognito)continue;
      const host=SiteIdentity.key(tab.url || '');
      if(!host || !wanted.has(canonical(host)) || seen.has(host))continue;
      seen.add(host);result.push({tabId:tab.id,domain:host});
      if(result.length===16)break;
    }
    return result;
  }
  globalThis.BackgroundMediaTabs={select};
  if(typeof module!=='undefined')module.exports=globalThis.BackgroundMediaTabs;
})();
