(()=>{
'use strict';
const historyTools=document.createElement('div');historyTools.className='railHistory';historyTools.append($('undo'),$('redo'));document.querySelector('.canvasTools').append(historyTools);
$('rotateTool').innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3.4 14a8.7 8.7 0 0 1 14-8.7M15 2l3 3-3.5 2M20.6 10a8.7 8.7 0 0 1-14 8.7M9 22l-3-3 3.5-2"/></svg>';
for(const [id,text] of [['detectMask','Detect Subject'],['applyMask','Apply Cutout'],['headBox','Manual Fit']]){const b=$(id);const span=b.querySelector('span');if(span)span.textContent=text;else b.textContent=text}
for(const selector of ['#edgesDialog p','#headDialog p','#headDialog .dialogFoot>.muted','.inspector .hint','.inspector .muted','.inspector .qualityHelp','.inspector .passportNote','#imageHint','#fitStatus'])document.querySelectorAll(selector).forEach(e=>e.hidden=true);
$('useHead').textContent='Use Face Box';$('headDialog').querySelector('h2').textContent='Fit Face';
const toast=$('toast');document.querySelector('.editor').append(toast,$('jobbar'));
const maskTitle=document.querySelector('.maskSection .sectionTitle');
const maskSwitch=document.createElement('input');maskSwitch.type='checkbox';maskSwitch.id='maskEnabled';maskSwitch.setAttribute('aria-label','Enable Mask');maskSwitch.checked=true;maskTitle.append(maskSwitch);
maskSwitch.onchange=guarded(async()=>{await flush();await api('/api/settings',{masking_enabled:maskSwitch.checked});await refresh();if(!maskSwitch.checked){brush='move';setMode('image');cancelPolygon()}if(preview)finishPreview()});
function syncMaskControls(){if(!app)return;const enabled=app.settings.masking_enabled!==false;maskSwitch.checked=enabled;maskSwitch.disabled=busy;document.querySelector('.maskSection').classList.toggle('maskDisabled',!enabled);document.querySelectorAll('.maskSection button,.maskSection select,.maskSection input:not(#maskEnabled)').forEach(el=>el.disabled=!enabled||busy||!current);for(const el of document.querySelectorAll('#brushTools [data-brush]'))if(['keep','remove','lasso'].includes(el.dataset.brush))el.disabled=!enabled||busy||!current;if(!enabled&&['mask','compare'].includes(mode))setMode('image')}
const renderCompact=renderOutput;renderOutput=function(){renderCompact();syncMaskControls()};
const jobsCompact=renderJobs;renderJobs=function(){jobsCompact();syncMaskControls()};
// Floating HTML tools move by their title bar and keep their compact dimensions.
for(const dialog of document.querySelectorAll('dialog')){
 const head=dialog.querySelector('.dialogHead');if(!head||head.classList.contains('dragHandle'))continue;
 let dragWindow=null;
 head.addEventListener('pointerdown',e=>{if(e.target.closest('button,input')||e.button!==0)return;const r=dialog.getBoundingClientRect();dragWindow={x:e.clientX,y:e.clientY,left:r.left,top:r.top};head.setPointerCapture(e.pointerId);e.preventDefault()});
 head.addEventListener('pointermove',e=>{if(!dragWindow)return;dialog.style.margin='0';dialog.style.left=Math.max(0,Math.min(innerWidth-dialog.offsetWidth,dragWindow.left+e.clientX-dragWindow.x))+'px';dialog.style.top=Math.max(0,Math.min(innerHeight-dialog.offsetHeight,dragWindow.top+e.clientY-dragWindow.y))+'px'});
 head.addEventListener('pointerup',()=>dragWindow=null);head.addEventListener('pointercancel',()=>dragWindow=null);
}

})();

// Progress and completion share one notification surface, centered in the
// top toolbar rather than floating over Preview -- visible regardless of
// which panel is docked where.
(()=>{
 const stack=document.createElement('div');stack.id='notificationStack';stack.setAttribute('aria-live','polite');
 document.querySelector('.topbar').append(stack);stack.append($('jobbar'),$('toast'));
 let notes=[];
 // renderJobs() runs on every 1.5s poll tick regardless of whether
 // anything changed, and this wrapper's own paint() call after message()'s
 // own (message() -> paint() already happens synchronously) means a single
 // notification could get torn down and rebuilt 2-3 times over its
 // lifetime for no visible reason. A signature guard (same pattern as
 // renderBatch.signature elsewhere) skips the replaceChildren() unless
 // `notes` or busy/jobbar-visibility actually changed since the last paint.
 function paint(){
  const toast=$('toast'),jobbarHidden=$('jobbar').hidden;
  const signature=JSON.stringify([notes,busy,jobbarHidden]);
  if(paint.signature===signature)return;
  paint.signature=signature;
  toast.replaceChildren();
  for(const note of notes){const row=document.createElement('div');row.className=note.error?'notice error':'notice';row.textContent=note.text;toast.append(row)}
  toast.hidden=!notes.length||busy;
  stack.hidden=jobbarHidden&&toast.hidden;
 }
 message=function(text,error=false){const note={text,error};notes=notes.filter(n=>n.text!==text);notes.push(note);notes=notes.slice(-3);paint();setTimeout(()=>{notes=notes.filter(n=>n!==note);paint()},error?7000:2600)};
 const previous=renderJobs;renderJobs=function(){previous();paint()};paint();
})();

(()=>{const seen=new Map(),previous=renderOutput;renderOutput=function(){previous();for(const f of batch?.files||[]){if(f.photos_error&&seen.get(f.id)!==f.photos_error){seen.set(f.id,f.photos_error);message(f.photos_error,true)}}}})();
