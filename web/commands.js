/* All application keyboard/menu actions share this registry. */
const commands=new Map();
function registerCommand(id,action){commands.set(id,action)}
window.claretteCommand=async id=>{try{if(['undo','redo'].includes(id)&&document.activeElement?.closest('input,textarea,[contenteditable=true]')){document.execCommand(id);return}const fn=commands.get(id);if(fn)await fn()}catch(e){message(e.message,true)}};
function keyChord(e){const parts=[];if(e.metaKey||e.ctrlKey)parts.push('Meta');if(e.altKey)parts.push('Alt');if(e.shiftKey)parts.push('Shift');parts.push(e.key.length===1?e.key.toLowerCase():e.key);return parts.join('+')}
function editableTarget(e){return e.target.closest('input,textarea,select,[contenteditable=true]')}
document.addEventListener('keydown',e=>{
 if(editableTarget(e)||document.querySelector('dialog[open]'))return;
 if(e.key==='Escape'){cancelPolygon();if(stroke){stroke=null;draw()}return}
 if(polygon?.points.length&&['Backspace','Delete'].includes(e.key)){e.preventDefault();if(polygon.selected!==null){polygon.points.splice(polygon.selected,1);polygon.selected=null;if(polygon.points.length<3){polygon.closed=false;$('polygonAccept').disabled=true}draw()}return}
 if(hoveredPortraitId&&['Backspace','Delete'].includes(e.key)){const trash=document.getElementById('remove-'+hoveredPortraitId);if(trash&&!trash.disabled){e.preventDefault();trash.click()}return}
 if(polygon?.points.length&&e.key==='Enter'){e.preventDefault();closePolygon();return}
 const shortcuts={...app?.shortcut_defaults,...app?.shortcuts},chord=keyChord(e);
 const entry=Object.entries(shortcuts).find(([,key])=>key&&key===chord);
 if(entry){e.preventDefault();window.claretteCommand(entry[0])}
});
$('mainCanvas').addEventListener('wheel',e=>{
 if(!current||busy||guideEditing)return;
 const prefix=[e.metaKey||e.ctrlKey?'Meta':'',e.altKey?'Alt':'',e.shiftKey?'Shift':'','Wheel'].filter(Boolean).join('+');
 const shortcuts={...app?.shortcut_defaults,...app?.shortcuts};
 if(prefix===shortcuts['brush-size']){
  if(!['keep','remove'].includes(brush))return;
  e.preventDefault();$('brushSize').value=Math.max(2,Math.min(400,+$('brushSize').value+(e.deltaY<0?3:-3)));$('brushSize').oninput();return;
 }
 if(prefix===shortcuts['rotate-wheel']){e.preventDefault();if(current.position_locked)return;current.transform.rotation=(current.transform.rotation||0)+(Math.abs(e.deltaX)>Math.abs(e.deltaY)?Math.sign(e.deltaX):-Math.sign(e.deltaY));draw();schedule();return}
 if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
 e.preventDefault();const c=$('mainCanvas'),r=c.getBoundingClientRect(),g=geometry(c),factor=Math.exp(-Math.max(-120,Math.min(120,e.deltaY))*.0025);
 if(current.position_locked){setInspectionZoom(g.k*factor,{x:e.clientX-r.left,y:e.clientY-r.top});return}
 if(stroke||drag)return;const t=current.transform,px=(e.clientX-r.left-g.ox)/g.k,py=(e.clientY-r.top-g.oy)/g.k,scale=Math.max(.001,Math.min(100,t.scale*factor)),ratio=scale/t.scale;
 current.transform={...t,scale,x:px-(px-t.x)*ratio,y:py-(py-t.y)*ratio};syncPosition();draw();schedule();
},{passive:false});

registerCommand('reset-rotation',()=>{if(!current||busy||current.position_locked)return;current.transform.rotation=0;draw();schedule()});
$('mainCanvas').addEventListener('pointerdown',e=>{
 if(e.button!==1)return;
 e.preventDefault();
 const chord=[e.metaKey||e.ctrlKey?'Meta':'',e.altKey?'Alt':'',e.shiftKey?'Shift':'','MMB'].filter(Boolean).join('+');
 const entry=Object.entries({...app?.shortcut_defaults,...app?.shortcuts}).find(([,key])=>key===chord);
 if(entry){e.stopImmediatePropagation();window.claretteCommand(entry[0]);return}
 // MMB pans independently of the selected brush, rotation tool, or guide editor.
 e.stopImmediatePropagation();if(!current)return;
 $('mainCanvas').setPointerCapture(e.pointerId);drag={inspect:true,x:e.clientX,y:e.clientY,shift:{...viewShift}};
},true);
$('mainCanvas').addEventListener('pointermove',e=>{if(!drag?.inspect)return;e.stopImmediatePropagation();viewShift={x:drag.shift.x+e.clientX-drag.x,y:drag.shift.y+e.clientY-drag.y};draw()},true);
for(const type of ['pointerup','pointercancel'])$('mainCanvas').addEventListener(type,e=>{if(!drag?.inspect)return;e.stopImmediatePropagation();drag=null},true);
$('mainCanvas').addEventListener('auxclick',e=>{if(e.button===1)e.preventDefault()});
