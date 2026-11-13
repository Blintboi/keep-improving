import {el, field, check, button, helpNote, t, uid} from './client.js';

export function defaultChoices() {
  return {question:t('Why are you opening this?'), allocation:'shared', remember_minutes:0, options:[
    {id:uid(),label:t('For work'),limit:null}, {id:uid(),label:t('Just checking'),limit:2}]};
}

export function choiceFields(step, changed, redraw) {
  const box = el('div', {class:'stack'});
  box.append(check('Ask why when opening', !!step.session_choice, enabled => {
    if (enabled) step.session_choice = defaultChoices();
    else delete step.session_choice;
    changed(); redraw();
  }));
  const value = step.session_choice;
  if (!value) return box;
  box.append(field('Session allowance',value.allocation || 'shared',allocation=>{value.allocation=allocation;changed();},
    {options:[['shared','Shared allowance'],['activity','Separate allowance per member']]}));
  box.append(field('Question', value.question, text => {value.question=text;changed();}, {required:true,maxLength:180}));
  box.append(field('Do not ask again for (minutes)',value.remember_minutes || 0,n=>{value.remember_minutes=n;changed();},
    {type:'number',min:0,max:1440,step:1,required:true}));
  for (const option of value.options) {
    const row = el('div', {class:'subcard stack'}), remove = button('Remove choice', () => {
      if (value.options.length <= 2) return;
      value.options = value.options.filter(item=>item.id!==option.id);changed();redraw();
    }, 'quiet');
    remove.disabled = value.options.length <= 2;
    row.append(el('div', {class:'row'},
      field('Choice name', option.label, text=>{option.label=text;changed();}, {required:true,maxLength:120}), remove),
      check('Unlimited', option.limit===null, unlimited=>{option.limit=unlimited?null:2;changed();redraw();}));
    if (option.limit!==null) row.append(field('Daily sessions',option.limit,n=>{option.limit=n;changed();},
      {type:'number',min:1,max:10000,step:1,required:true}));
    box.append(row);
  }
  const add = button('Add choice',()=>{
    if (value.options.length>=8) return;
    value.options.push({id:uid(),label:t('New choice'),limit:2});changed();redraw();
  },'quiet');
  add.disabled=value.options.length>=8;
  box.append(add,helpNote('Shared: all members use the same count for each answer. Separate: each application or website gets the full count for each answer.',
    'After answering, return to the same activity without another question for this many minutes. Returning does not use another allowance or extend the delay. Zero asks on every return. Other restrictions still apply.',
    'Each choice has its own allowance. Exhausted choices stay visible but cannot be selected. Other budget rules still apply.',
    'Choice allowances are counted on this computer and reset with this budget. Keep the desktop application running to show choices over applications and websites.'));
  for (const scope of ['app','site']) box.append(check(scope==='app'?'Ask for applications':'Ask for websites',step.targets?.[scope]?.enabled!==false,enabled=>{
    step.targets??={};(step.targets[scope]??={}).enabled=enabled;changed();
  }));
  return box;
}
