/* Number and slider controls respond to the wheel only under the pointer. */
document.addEventListener('wheel',event=>{
 const field=event.target.closest('input[type="number"],input[type="range"]');
 if(!field||field.disabled||field.readOnly||event.ctrlKey||event.metaKey)return;
 const delta=Math.abs(event.deltaX)>Math.abs(event.deltaY)?event.deltaX:-event.deltaY;if(!delta)return;
 event.preventDefault();event.stopPropagation();
 const before=field.value;
 try{delta>0?field.stepUp():field.stepDown()}catch{const step=Number(field.step)||1;field.value=Number(field.value||0)+Math.sign(delta)*step}
 if(field.min!==''&&+field.value<+field.min)field.value=field.min;
 if(field.max!==''&&+field.value>+field.max)field.value=field.max;
 if(field.value===before)return;
 field.dispatchEvent(new Event('input',{bubbles:true}));
 clearTimeout(field.wheelCommit);field.wheelCommit=setTimeout(()=>field.dispatchEvent(new Event('change',{bubbles:true})),120);
},{passive:false,capture:true});

/* Dropdowns use the same hover-to-scroll interaction in every app window. */
(()=>{
 const gestures=new WeakMap();
 document.addEventListener('wheel',event=>{
  const field=event.target.closest('select');
  if(!field||field.matches(':disabled')||field.multiple||event.ctrlKey||event.metaKey)return;
  const delta=Math.abs(event.deltaX)>Math.abs(event.deltaY)?event.deltaX:event.deltaY;
  if(!delta)return;
  event.preventDefault();event.stopPropagation();
  const now=performance.now(),direction=Math.sign(delta),previous=gestures.get(field);
  // Trackpads emit many tiny events; advance at a controlled repeat rate.
  if(previous&&previous.direction===direction&&now-previous.time<140)return;
  gestures.set(field,{time:now,direction});
  for(let index=field.selectedIndex+direction;index>=0&&index<field.options.length;index+=direction){
   const option=field.options[index];
   if(option.disabled||option.hidden||option.parentElement?.disabled)continue;
   field.selectedIndex=index;
   field.dispatchEvent(new Event('input',{bubbles:true}));
   field.dispatchEvent(new Event('change',{bubbles:true}));
   break;
  }
 },{passive:false,capture:true});
})();
