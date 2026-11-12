/* Feedback for explicit user actions. Background polling stays quiet. */
import {el,t} from './client.js';
export class OperationFeedback {
  constructor(parent) {
    this.busy=false;this.timer=null;
    this.node=el('div',{class:'operation-feedback',role:'status','aria-live':'polite'});
    parent.append(this.node);
    for(const type of ['click','keydown','beforeinput'])document.addEventListener(type,event=>{
      if(this.busy && !event.ctrlKey && !event.metaKey){event.preventDefault();event.stopImmediatePropagation();}
    },true);
  }
  async run(title,work,{button=null,success=''}={}) {
    if(this.busy)return;
    clearTimeout(this.timer);this.busy=true;
    this.node.textContent=t(title);this.node.classList.add('busy');
    this.node.setAttribute('aria-busy','true');
    const old=button?.textContent;if(button){button.disabled=true;button.textContent=t(title);}
    try {
      const result=await work();
      this.node.textContent=success?t(success):'';
      if(success)this.timer=setTimeout(()=>this.node.textContent='',4000);
      return result;
    } catch(error) {
      this.node.textContent=error.message || t('Could not save changes. Try again.');throw error;
    } finally {
      this.busy=false;this.node.classList.remove('busy');this.node.setAttribute('aria-busy','false');
      if(button){button.disabled=false;button.textContent=old;}
    }
  }
}
