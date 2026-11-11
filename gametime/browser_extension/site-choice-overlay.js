/* Extension-isolated dialog. It leaves the site's DOM, scroll and viewport intact. */
(()=>{
  if(globalThis.keepImprovingChoices) return;
  globalThis.keepImprovingChoices=true;
  // A local extension upgrade invalidates the old listener, but can leave its
  // own injected element behind until this tab next becomes active.
  document.getElementById('keep-improving-opening-choice')?.remove();
  let host,root,dialog,signature='',current=null,busy=false,previousFocus;
  const node=(tag,text)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;return e;};
  function close() {
    if(dialog?.open) dialog.close();host?.remove();host=root=dialog=null;signature='';current=null;
    if(previousFocus?.isConnected) previousFocus.focus({preventScroll:true});previousFocus=null;
  }
  function render(value) {
    if(!value) {close();return;}
    const next=JSON.stringify(value);if(next===signature && host?.isConnected && dialog?.open) return;
    signature=next;current=value;
    const hu=value.language==='hu';
    if(!host) {
      previousFocus=document.activeElement;host=node('div');host.id='keep-improving-opening-choice';
      root=host.attachShadow({mode:'closed'});dialog=node('dialog');
      dialog.addEventListener('cancel',e=>e.preventDefault());
      const style=node('style',`:host{all:initial}dialog{box-sizing:border-box;position:fixed;inset:0;width:100vw;height:100dvh;max-width:none;max-height:none;margin:0;border:0;padding:24px;background:#101619;color:#edf4f2;font:16px/1.5 'Segoe UI',sans-serif;overflow:auto}dialog::backdrop{background:#101619}main{box-sizing:border-box;max-width:760px;margin:4vh auto;background:#192126;border:1px solid #304047;border-radius:20px;padding:32px}h1{font-size:30px;line-height:1.3;overflow-wrap:anywhere}p{color:#a7b9b9;overflow-wrap:anywhere}.brand{font-size:12px;letter-spacing:2px;color:#7de5bf}button{box-sizing:border-box;width:100%;display:block;margin:12px 0;padding:16px 20px;background:#7de5bf;color:#10291f;border:1px solid transparent;border-radius:12px;font:600 17px/1.4 'Segoe UI',sans-serif;text-align:left;cursor:pointer;overflow-wrap:anywhere}button:hover{background:#a1f3d5}button:focus-visible{outline:3px solid #edf4f2;outline-offset:3px}button:disabled{background:#243132;color:#93a3a7;cursor:default}small{display:block;font-size:14px;font-weight:400;margin-top:5px}.error{color:#f3a7a7}@media(max-width:520px){dialog{padding:12px}main{padding:20px}h1{font-size:25px}}`);
      root.append(style,dialog);document.documentElement.append(host);
    }
    const main=node('main');main.append(node('p','KEEP IMPROVING'));main.firstChild.className='brand';
    main.append(node('p',value.name));const heading=node('h1',value.question);heading.id='question';main.append(heading);
    dialog.setAttribute('aria-labelledby','question');dialog.setAttribute('lang',hu?'hu':'en');
    const controls=[];
    for(const option of value.options) {
      const pick=node('button',option.label);pick.type='button';pick.disabled=option.remaining===0;
      const detail=option.remaining==null?(hu?'Korlátlan':'Unlimited'):option.remaining===0?(hu?'Mára elfogyott':'No visits left today'):
        hu?`Ma még ${option.remaining} / ${option.limit} alkalom`:`${option.remaining} of ${option.limit} visits left today`;
      pick.append(node('small',detail));controls.push(pick);
      pick.addEventListener('click',async()=>{
        if(busy || current!==value)return;busy=true;controls.forEach(b=>b.disabled=true);
        try {
          const result=await chrome.runtime.sendMessage({action:'choice.accept',visit:value.visit,budget:value.budget,step:value.step,choice:option.id});
          if(!result?.ok) throw Error();
        } catch {error.textContent=hu?'Nem sikerült menteni a választ. Próbáld újra.':'Could not save your choice. Try again.';}
        finally {busy=false;controls.forEach((b,i)=>b.disabled=value.options[i].remaining===0);}
      });main.append(pick);
    }
    main.append(node('p',value.allocation==='activity'?(hu?'Erre az oldalra külön keret vonatkozik.':'This website has a separate allowance.'):
      (hu?'A keret tagjai közösen használják ezeket az alkalmakat.':'These visits are shared across the budget members.')));
    main.append(node('p',hu?'Válassz egy célt a folytatáshoz, vagy válts másik lapra.':'Choose a reason to continue, or switch to another tab.'));
    const error=node('p');error.className='error';error.setAttribute('role','status');main.append(error);
    const scroll=dialog.scrollTop;dialog.replaceChildren(main);if(!dialog.open)dialog.showModal();dialog.scrollTop=scroll;
  }
  chrome.runtime.onMessage.addListener((message,sender,reply)=>{
    if(sender.id!==chrome.runtime.id || message.action!=='choice.overlay')return;
    render(message.value);reply({ok:true});
  });
})();
