import {el,button,card,note,t,clock,setLanguage} from './client.js';
const views=new WeakMap();
export function offlineView(root,state,command) {
  setLanguage(state.language);
  const f=state.focus,shape=JSON.stringify([state.language,f.running,f.phase,!!f.remaining,state.budgets.map(b=>[b.id,b.name])]);
  let view=views.get(root);
  if(!view || view.shape!==shape || !view.clock.isConnected) {
    if(view) clearTimeout(view.timer);
    const clockNode=el('div',{class:'timer',id:'offline-clock'}),rounds=el('p',{class:'hint'});
    const run=button(f.running?'Pause':'Start focus',async()=>{
      run.disabled=true;try {await command(f.running?'focus.pause':'focus.start');}finally{run.disabled=false;}
    },'primary');
    const stop=button('Stop',async()=>{stop.disabled=true;try{await command('focus.stop');}finally{stop.disabled=false;}},'quiet');
    const phase=f.phase==='focus'?'Focus':f.phase==='short_break'?'Short break':'Long break';
    const list=el('div',{class:'stack'}),rows=new Map();
    for(const budget of state.budgets) {const value=el('strong',{class:'large'});rows.set(budget.id,value);list.append(card(el('div',{class:'muted wrap'},budget.name),value));}
    const error=el('p',{class:'error',role:'alert'});
    root.replaceChildren(note('The desktop application is unavailable. Browser tracking, focus and saved website budgets continue here.'),
      card(el('div',{class:'row spread'},el('strong',{},t(phase)),el('span',{class:'pill'},t(f.running?'Running':f.phase==='focus'&&!f.remaining?'Completed':'Ready'))),
        clockNode,el('div',{class:'row'},run,stop),rounds),
      ...(state.budgets.length?[el('h2',{},t('Budgets')),list]:[]),
      note('Recorded time transfers automatically when the application returns, without counting it twice.'),
      note('Other applications and settings need the desktop application.'),error);
    view={shape,clock:clockNode,rounds,rows,error};views.set(root,view);
  }
  view.rounds.textContent=t('Today’s focus rounds')+': '+f.today;
  view.error.textContent=state.error?t(state.error):'';
  for(const budget of state.budgets) view.rows.get(budget.id).textContent=budget.remaining==null?'—':clock(budget.remaining);
  clearTimeout(view.timer);
  const paint=()=>{
    if(!view.clock.isConnected || document.hidden) return;
    view.clock.textContent=clock(Math.max(0,f.remaining-(f.running?Math.max(0,Date.now()/1000-state.at):0)));
    if(f.running) view.timer=setTimeout(paint,1000);
  };
  paint();
}
