// Shared URL normalization. Paths, queries and titles never enter activity keys.
(() => {
  const local=value=>typeof value==='string' && /^127\.0\.0\.1:[1-9][0-9]{0,4}$/.test(value) && Number(value.split(':')[1])<=65535;
  function key(value) {
    try {
      const explicit=value.includes('://'),url=new URL(explicit?value:'http://'+value);
      if(!['http:','https:'].includes(url.protocol)||url.username||url.password)return '';
      const host=url.hostname.toLowerCase().replace(/\.+$/,'');
      if(['localhost','127.0.0.1','[::1]'].includes(host)) {
        const port=Number(url.port || (explicit&&url.protocol==='https:'?443:80));
        return port>0?`127.0.0.1:${port}`:'';
      }
      if(!host.includes('.') || /^[\d.]+$/.test(host) || host.includes(':') || /\.(local|localhost|internal|test|invalid)$/.test(host))return '';
      return host;
    } catch{return '';}
  }
  const escape=value=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  function pattern(value) {
    if(!local(value))return '^https?://'+escape(value)+'(?::[0-9]+)?/';
    const port=value.split(':')[1],host='(?:localhost\\.?|127\\.0\\.0\\.1\\.?|\\[::1\\])';
    const explicit='https?://'+host+':'+port+'(?:/|$)';
    return '^(?:'+explicit+(port==='80'?'|http://'+host+'(?:/|$)':port==='443'?'|https://'+host+'(?:/|$)':'')+')';
  }
  const api={key,local,pattern};globalThis.SiteIdentity=api;
  if(typeof module!=='undefined')module.exports=api;
})();
