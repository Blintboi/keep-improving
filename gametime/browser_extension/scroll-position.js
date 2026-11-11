// Preserve the actual scrolling surface, including narrow layouts using the body.
const pending = new WeakMap();
export function scrollRoot(node) {
  for (let current=node; current; current=current.parentElement)
    if (/auto|scroll/.test(getComputedStyle(current).overflowY)) return current;
  return document.scrollingElement;
}
export function keepScroll(node, change, top) {
  const root=scrollRoot(node), previous=pending.get(node);
  const saved={root,top:top??(previous?.moved?root.scrollTop:previous?.top)??root.scrollTop,left:root.scrollLeft,
    padding:previous?.padding??node.style.paddingBottom,moved:false};
  pending.set(node,saved);
  // Keep the old scroll range while an asynchronous view is being populated.
  node.style.paddingBottom=`${Math.max(node.scrollHeight,node.clientHeight)}px`;
  const moved=()=>{saved.moved=true;};
  for(const event of ['wheel','touchmove','keydown'])root.addEventListener(event,moved,{passive:true});
  const restore=()=>{if(!saved.moved){root.scrollTop=saved.top;root.scrollLeft=saved.left;}};
  const finish=()=>{
    for(const event of ['wheel','touchmove','keydown'])root.removeEventListener(event,moved);
    if(pending.get(node)!==saved)return;
    node.style.paddingBottom=saved.padding;pending.delete(node);restore();
  };
  try {
    const result=change();restore();
    if(result?.then)return Promise.resolve(result).finally(finish);
    finish();return result;
  }catch(error){finish();throw error;}
}
