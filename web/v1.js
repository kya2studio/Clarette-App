async function openNative(kind,payload={}){await flush();const r=await api('/api/window',{kind,payload});if(r.url)window.open(r.url,'clarette-'+kind,'width=900,height=760')}
const toolbar=document.querySelector('.topbar nav');$('help').hidden=true;$('apiKeys').hidden=true;
const exportButton=makeButton('exportButton',(phosphor['export']||phosphor['upload-simple'])+'<span>Export</span>','Export Finals');toolbar.prepend(exportButton);exportButton.onclick=()=>openNative('export');
$('settings').onclick=()=>openNative('settings');$('newBatch').onclick=()=>openNative('new-batch');$('emptyImport').onclick=()=>chooseImport(true);$('saveFinals').onclick=()=>openNative('export');
const externalButtons={photoshop:$('photoshop')};const externalIcons={affinity:'<img src="assets/affinity.svg" alt="" class="appIcon">',photos:'<img src="photos-icon.png" alt="" class="appIcon">'};for(const name of ['affinity','photos']){const button=makeButton('external-'+name,externalIcons[name]+'<span>'+({affinity:'Affinity',photos:'Photos'}[name])+'</span>',name);toolbar.insertBefore(button,$('settings'));externalButtons[name]=button}
for(const [name,b] of Object.entries(externalButtons))b.onclick=guarded(async()=>{await flush();await api('/api/open',context({service:name}))});
const previewColor=makeButton('previewColor',phosphor.eye,'Preview Color Changes');previewColor.className='previewToggle';$('autoColor').before(previewColor);previewColor.onclick=guarded(async()=>{await api('/api/settings',{preview_color:app.settings.preview_color===false});await refresh();updatePreview()});
$('neutralColor').title='Reset Color';$('neutralColor').onclick=guarded(async()=>{await flush();await api('/api/color-reset',context());await refresh(true)});
const backgroundToggle=makeButton('previewBackground','<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/></svg>','Toggle transparency / solid preview background');backgroundToggle.className='previewToggle';document.querySelector('.editorHead').append(backgroundToggle);backgroundToggle.onclick=guarded(async()=>{await api('/api/settings',{solid_preview:!app.settings.solid_preview});await refresh();draw()});
checkers=function(ctx,w,h){if(app?.settings.solid_preview){ctx.fillStyle=app.settings.preview_background||'#00a84f';ctx.fillRect(0,0,w,h);return}const k=Math.round((app?.settings.checker_brightness??35)*1.5),tile=checkerTile.getContext('2d');tile.fillStyle=`rgb(${k},${k},${k+6})`;tile.fillRect(0,0,32,32);tile.fillStyle=`rgb(${k+13},${k+13},${k+19})`;tile.fillRect(16,0,16,16);tile.fillRect(0,16,16,16);ctx.fillStyle=ctx.createPattern(checkerTile,'repeat');ctx.fillRect(0,0,w,h)};
const rotateButton=makeButton('rotateTool',phosphor['arrow-counter-clockwise'],'Rotate (R)');rotateButton.dataset.brush='rotate';$('lockPosition').before(rotateButton);rotateButton.onclick=()=>{brush='rotate';document.querySelectorAll('[data-brush]').forEach(b=>b.classList.toggle('active',b===rotateButton));updateBrushCursor()};
const nativeSourcePoint=sourcePoint;sourcePoint=function(e){const p=nativeSourcePoint(e),angle=-(current.transform.rotation||0)*Math.PI/180,x=(p[0]-.5)*current.width,y=(p[1]-.5)*current.height;return [(x*Math.cos(angle)-y*Math.sin(angle))/current.width+.5,(x*Math.sin(angle)+y*Math.cos(angle))/current.height+.5]};
const outputActions=document.createElement('div');outputActions.className='outputPresetActions';
$('presetSelect').before(outputActions);outputActions.append($('presetSelect'));
const matchIcon='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M8 8h8v8H8z"/></svg>';
const saveIcon='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h12l4 4v14H3V3h2Zm2 0v6h10V3M7 21v-8h10v8"/></svg>';
for(const [id,icon,label] of [['matchSource',matchIcon,'Match Source Size'],['saveCurrentPreset',saveIcon,'Save Current as Preset']]){const b=makeButton(id,icon,label);b.className='compactIcon';outputActions.append(b)};
$('matchSource').onclick=guarded(async()=>{if(!current)return;await flush();await api('/api/output',{canvas:{...batch.canvas,width:current.width,height:current.height,preset_id:'custom',label:'Custom'}});await refresh(true)});$('saveCurrentPreset').onclick=()=>openNative('preset');
const passportNote=document.createElement('p');passportNote.className='passportNote';passportNote.textContent='2 × 2 in at 300 dpi. Chin-to-crown guide: 300–413 px. Framing aid only; not government validation.';// Passport guidance is documented, not displayed as editor prose.
$('cloudProvider').replaceChildren(...[['classical','Classical'],['edsr','EDSR']].map(([v,t])=>new Option(t,v)));$('cloudProvider').parentElement.firstChild.textContent='Enhance with ';
function availableProviders(){
 const list=[['classical','Classical'],['edsr','EDSR']];
 if(app.restore?.status==='Ready')list.push(['restore','Clarette Restore']);
 for(const [id,name] of [['hypir','HYPIR'],['osediff','OSEDiff'],['flowsr','FlowSR'],['seesr','SeeSR']])if(app.engines?.[id]?.status==='Ready')list.push([id,name]);
 for(const [id,name] of [['openai','ChatGPT'],['gemini','Gemini'],['seedream','Seedream']])if(app.settings[id+'_connected'])list.push([id,name]);
 return list;
}
function syncEnhanceProviders(){
 const providers=availableProviders(),signature=JSON.stringify(providers);
 if(syncEnhanceProviders.signature!==signature){syncEnhanceProviders.signature=signature;const previous=$('cloudProvider').value;$('cloudProvider').replaceChildren(...providers.map(([v,t])=>new Option(t,v)));if(providers.some(([v])=>v===previous))$('cloudProvider').value=previous}
 if(providers.some(([v])=>v===app.settings.enhancement_provider))$('cloudProvider').value=app.settings.enhancement_provider;
}
$('cloudProvider').onchange=guarded(async()=>{await api('/api/settings',{enhancement_provider:$('cloudProvider').value});await refresh()});
$('enhance').onclick=guarded(async()=>{
 if(!current)throw Error('Select a portrait first');await flush();
 const provider=$('cloudProvider').value;let scale=$('upscale').value;if(scale==='auto')scale=current.transform.scale>2.05?4:current.transform.scale>1.05?2:1;
 if(provider==='edsr'&&+scale===1){scale=2;$('upscale').value='2'}
 if(isDraft()){if(!confirm('Apply your pending color edits before enhancement?'))return;await api('/api/color-apply',context({color:draft}));await refresh(true)}
 if(provider==='restore'&&app.restore.status!=='Ready'){await openNative('settings',{section:'Presets & Models'});throw Error(app.restore.message)}
 if(['hypir','osediff','flowsr','seesr'].includes(provider)&&app.engines[provider].status!=='Ready'){await openNative('settings',{section:'Presets & Models'});throw Error(app.engines[provider].message)}
 if(['classical','restore','edsr','hypir','osediff','flowsr','seesr'].includes(provider)){await run('/api/enhance',{scale:+scale,amount:+$('detailAmount').value,enhancement_provider:provider});return}
 if(!app.settings[provider+'_connected']){await api('/api/open',context({service:provider==='openai'?'chatgpt':provider}));return}
 if(!confirm('Upload this working image and prompt to '+provider+'? API charges may apply.'))return;
 await run('/api/cloud-enhance',{provider,cloud_model:app.settings[provider+'_model'],prompt:app.prompt,confirmed_upload:true});
});
$('detailAmount').value=35;$('detailAmountOut').textContent='35';detailHelp.remove();
// Polygonal Lasso: persistent vertices; no mask mutation before Accept.
let polygon=null,polygonDrag=null;
const polygonActions=document.createElement('div');polygonActions.id='polygonActions';polygonActions.hidden=true;polygonActions.innerHTML='<span id="polygonHint">Click points; click the first vertex or Enter to close.</span><button id="polygonAccept" class="primary">Accept</button><button id="polygonCancel">Cancel</button>';document.querySelector('.editorHead').append(polygonActions);polygonActions.setAttribute('role','group');polygonActions.setAttribute('aria-label','Polygonal Lasso actions');polygonActions.title='Click to draw. Command-click adds a point; Option-click removes a point. Enter closes the polygon.';
const lassoKeys={add:false,remove:false};
function makeLassoCursor(symbol){
 const badge=symbol?`<circle cx="25" cy="7" r="6" fill="#17191f" stroke="#dfd0ff"/><path d="M22 7h6${symbol==='+'?'M25 4v6':''}" stroke="#ffffff" stroke-width="1.5"/>`:'';
 const path='M7 23C1 21 2 13 6 10C10 6 22 8 23 14C24 20 16 25 9 23C5 22 6 19 9 20C13 21 9 29 5 30';
 return `url("data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><path d="${path}" fill="none" stroke="#17191f" stroke-width="4"/><path d="${path}" fill="none" stroke="#e4d4ff" stroke-width="1.7"/>${badge}</svg>`)}") 7 23, crosshair`;
}
const lassoCursors={normal:makeLassoCursor(''),add:makeLassoCursor('+'),remove:makeLassoCursor('-')};
const previousBrushCursor=updateBrushCursor;
updateBrushCursor=function(){
 previousBrushCursor();
 const active=brush==='lasso'&&!!current&&!guideEditing;
 polygonActions.hidden=!active;
 $('polygonAccept').disabled=busy||!polygon?.closed;
 $('polygonCancel').disabled=busy;
 const c=$('mainCanvas');
 if(c.dataset.colorSampling)return;
 if(active&&!busy){c.style.cursor=lassoCursors[lassoKeys.remove?'remove':lassoKeys.add?'add':'normal'];c.dataset.lassoCursor=lassoKeys.remove?'remove':lassoKeys.add?'add':'normal'}
 else if(c.dataset.lassoCursor){c.style.cursor='';delete c.dataset.lassoCursor}
};
function updateLassoKeys(e){lassoKeys.add=e.metaKey;lassoKeys.remove=e.altKey;updateBrushCursor()}
document.addEventListener('keydown',updateLassoKeys);
document.addEventListener('keyup',updateLassoKeys);
window.addEventListener('blur',()=>{lassoKeys.add=false;lassoKeys.remove=false;updateBrushCursor()});
$('mainCanvas').addEventListener('pointermove',updateLassoKeys);

function cancelPolygon(){polygon=null;polygonDrag=null;stroke=null;polygonActions.hidden=true;draw()}
function closePolygon(){if(!polygon||polygon.points.length<3)return;polygon.closed=true;$('polygonAccept').disabled=false;$('polygonHint').textContent='Drag vertices; click a segment to insert. Delete removes the selected vertex.';draw()}
$('polygonCancel').onclick=cancelPolygon;$('polygonAccept').onclick=guarded(async()=>{if(!polygon?.closed)return;const points=clone(polygon.points);await flush();await api('/api/mask-paint',context({strokes:[{mode:$('lassoMode').value,shape:'polygon',points,feather:+$('lassoFeather').value}]}));cancelPolygon();await refresh()});
const downV1=$('mainCanvas').onpointerdown,moveV1=$('mainCanvas').onpointermove,upV1=$('mainCanvas').onpointerup;
$('mainCanvas').onpointerdown=e=>{
 if(!current||busy||guideEditing||e.button!==0)return downV1(e);
 if(brush==='rotate'){if(current.position_locked)return;const g=geometry($('mainCanvas'));drag={rotate:true,x:e.clientX,rotation:current.transform.rotation||0};$('mainCanvas').setPointerCapture(e.pointerId);return}
 if(brush!=='lasso')return downV1(e);
 e.preventDefault();const p=sourcePoint(e);if(p.some(v=>v<0||v>1))return;
 if(!polygon&&e.altKey)return;
 if(!polygon){polygon={points:[],closed:false,selected:null};polygonActions.hidden=false;$('polygonAccept').disabled=true}
 const g=geometry($('mainCanvas')),factor=current.transform.scale*g.k;
 const action=LassoGeometry.pointAction(polygon,p,current.width*factor,current.height*factor,{add:e.metaKey,remove:e.altKey});
 if(action.type==='close'){closePolygon();return}
 if(action.type==='remove'){
  polygon.points.splice(action.index,1);polygon.selected=null;polygonDrag=null;
  if(polygon.points.length<3)polygon.closed=false;
 }else if(action.type==='insert'){
  polygon.points.splice(action.index,0,p);polygon.selected=action.index;
 }else if(action.type==='drag'){
  polygon.selected=action.index;polygonDrag=action.index;$('mainCanvas').setPointerCapture(e.pointerId);
 }else polygon.selected=null;
 $('polygonAccept').disabled=!polygon.closed;

 draw();
};
$('mainCanvas').onpointermove=e=>{if(drag?.inspect)return moveV1(e);if(drag?.rotate){current.transform.rotation=drag.rotation+(e.clientX-drag.x)*.3;draw();return}if(brush==='lasso'&&polygonDrag!==null){polygon.points[polygonDrag]=sourcePoint(e).map(v=>Math.max(0,Math.min(1,v)));draw();return}if(brush==='lasso')return;return moveV1(e)};
$('mainCanvas').onpointerup=e=>{if(drag?.inspect)return upV1(e);if(drag?.rotate){drag=null;schedule();return}if(brush==='lasso'){polygonDrag=null;return}return upV1(e)};
const drawV1=draw;draw=function(){drawV1();if(!polygon||!current)return;const c=$('mainCanvas'),ctx=c.getContext('2d'),g=geometry(c),t=current.transform,iw=current.width*t.scale*g.k,ih=current.height*t.scale*g.k,x=g.ox+t.x*g.k,y=g.oy+t.y*g.k;ctx.save();ctx.translate(x+iw/2,y+ih/2);ctx.rotate((t.rotation||0)*Math.PI/180);ctx.translate(-iw/2,-ih/2);ctx.strokeStyle='#d9c8ff';ctx.fillStyle='#b69af533';ctx.lineWidth=1.5;ctx.beginPath();polygon.points.forEach(([px,py],i)=>i?ctx.lineTo(px*iw,py*ih):ctx.moveTo(px*iw,py*ih));if(polygon.closed){ctx.closePath();ctx.fill()}ctx.stroke();polygon.points.forEach(([px,py],i)=>{ctx.fillStyle=i===polygon.selected?'#ffffff':'#b69af5';ctx.fillRect(px*iw-4,py*ih-4,8,8)});ctx.restore()};
// The panel host/drag/resize/responsive-reflow system now lives in Dockview
// (see dockview-workspace.js, loaded after this file) -- it takes over
// .batch/.editor and the individual Adjustments sections directly.
const oldRenderV1=renderOutput;renderOutput=function(){oldRenderV1();if(!app)return;for(const name of ['chatgpt','gemini','prompt'])$(name==='prompt'?'copyPrompt':name).hidden=!app.settings.toolbar_tools.includes(name);$('batchCount').replaceChildren('Portraits',Object.assign(document.createElement('span'),{className:'batchMeta',textContent:' · '+(batch?.files.length||0)+(batch?' · '+batch.name:'')}));$('batchCount').title=batch?.name||'No active batch';for(const [name,b] of Object.entries(externalButtons))b.hidden=!(app.settings.toolbar_apps.includes(name)&&app.external_apps[name]);previewColor.classList.toggle('active',app.settings.preview_color!==false);backgroundToggle.classList.toggle('active',app.settings.solid_preview);backgroundToggle.style.setProperty('--solidPreviewColor',app.settings.preview_background||'#00a84f');syncEnhanceProviders();passportNote.hidden=batch?.canvas.preset_id!=='passport';$('saveCurrentPreset').disabled=!batch||Object.values(app.presets).some(p=>p.width===batch.canvas.width&&p.height===batch.canvas.height&&p.dpi===batch.canvas.dpi);$('matchSource').disabled=!current};
const oldLoadV1=loadSelected;loadSelected=async function(){cancelPolygon();await oldLoadV1();renderOutput()};
for(const [id,button] of Object.entries({'import':'importBtn','clear':'clearPortraits','working':'working','final':'openFinal','undo':'undo','redo':'redo','auto-fit':'autoFit','auto-color':'autoColor','enhance':'enhance','compare':'before','preview-color':'previewColor','transparency':'previewBackground','fit':'homeView','lock':'lockPosition','crop':'crop'}))registerCommand(id,()=>$(button).click());
for(const kind of ['settings','shortcuts','help','new-batch','rename-batch','export','updates'])registerCommand(kind,()=>openNative(kind));
for(const [id,tool] of [['brush','keep'],['erase','remove'],['move','move'],['lasso','lasso'],['rotate','rotate']])registerCommand(id,()=>document.querySelector('[data-brush="'+tool+'"]').click());
registerCommand('guides',()=>{$('guide').checked=!$('guide').checked;draw()});registerCommand('solid',async()=>{await api('/api/settings',{solid_preview:true});await refresh();draw()});
registerCommand('close-batch',async()=>{if(!batch)return;if(!confirm('Close this batch? Unsaved work remains recoverable for seven days.'))return;await flush();await api('/api/close-batch',{confirmed:true});selected=null;await refresh(true)});
registerCommand('import-zip',()=>{$('fileInput').accept='.zip';chooseImport(true)});
registerCommand('batch-folder',async()=>{const r=await api('/api/choose-path',{kind:'folder'});if(r.path){await api('/api/batch-folder',{path:r.path});await refresh()}});
for(const mode of ['rgb','cmyk'])registerCommand(mode,async()=>{await api('/api/color-mode',{mode:mode.toUpperCase()});await refresh()});
// Workspace preset/lifecycle commands (workspace-default, -tools2x2, -new, -lock, etc.)
// are registered by dockview-workspace.js, next to the layout code they drive.
registerCommand('fullscreen',()=>api('/api/fullscreen'));registerCommand('feedback',()=>api('/api/feedback'));
for(const [id,angle] of [['rotate-left',-90],['rotate-right',90]])registerCommand(id,async()=>{if(!current||current.position_locked)return;await flush();await api('/api/rotate',context({angle:((current.transform.rotation||0)+angle)%360}));await refresh(true)});

$('copyPrompt').onclick=guarded(async()=>{await navigator.clipboard.writeText(app.prompt);message('Enhancement prompt copied')});

// Keep the existing advanced tools reachable after replacing the old Settings overlay.
for(const [node,target] of [[advancedColor,colorSection]]){node.hidden=false;node.classList.remove('settingsAdvanced');target.append(node)}
$('before').title='Hold to view untouched original';$('before').setAttribute('aria-label','Hold to view original');
$('replaceInput').onchange=guarded(async e=>{const file=e.target.files[0];if(!file)return;if(!confirm('Import this enhanced image? Existing mask work is preserved where geometry matches; Undo is available.'))return;await flush();await api('/api/replace',context({data:await readBase64(file)}));e.target.value='';await refresh(true)});
const rotateActions=document.createElement('div');rotateActions.className='two';for(const [id,label] of [['rotate-left','Rotate Left'],['rotate-right','Rotate Right']]){const b=makeButton(id,label,label);b.onclick=()=>window.claretteCommand(id);rotateActions.append(b)}advancedPosition.append(rotateActions);

document.querySelector('[data-brush=move]').title='Move (M)';document.querySelector('[data-brush=move]').setAttribute('aria-label','Move (M)');$('lassoTool').title='Polygonal Lasso (L)';$('lassoTool').setAttribute('aria-label','Polygonal Lasso (L)');
for(const [id,button] of Object.entries({prompt:'copyPrompt',chatgpt:'chatgpt',gemini:'gemini',photoshop:'photoshop',affinity:'external-affinity',photos:'external-photos'}))registerCommand(id,()=>{if(!$(button).hidden)$(button).click()});

// The model selector and Refine hair & edges button already expose these controls.
maskOptions.hidden=true;

// Compact actions keep the main editor focused on the image.
const maskActionRow=$('detectMask').parentElement;maskActionRow.classList.add('compactMaskActions');maskActionRow.append($('edgeQuick'));
$('edgeQuick').innerHTML=phosphor['sliders-horizontal'];$('edgeQuick').classList.add('compactIcon','filledIcon');$('edgeQuick').title='Refine hair & edges';$('edgeQuick').setAttribute('aria-label','Refine hair & edges');
$('neutralColor').innerHTML=phosphor['arrow-counter-clockwise'];$('neutralColor').classList.add('compactIcon','filledIcon');
for(const id of ['undo','redo']){$(id).querySelector('span')?.remove();$(id).classList.add('compactIcon','filledIcon')}
$('enhanceDrop').innerHTML=phosphor['upload-simple']+'<span>Import enhanced image</span>';$('enhanceDrop').title='Import enhanced image · click or drop';
$('autoFit').querySelector('span').textContent='Auto Fit';
const portraitActionRow=$('importBtn').parentElement;portraitActionRow.append($('applyCutouts'));
for(const id of ['importBtn','clearPortraits']){$(id).querySelector('span')?.remove();$(id).classList.add('compactIcon','filledIcon')}

// Preview toolbar: shared compact controls for brushes, lasso and guides.
const previewBar=document.querySelector('.brushbar');previewBar.classList.add('compactPreviewBar');
const sizeControl=$('brushSize').closest('label');sizeControl.firstChild.textContent='Size ';sizeControl.classList.add('previewRange');
const hardnessControl=$('brushHardness').closest('label');hardnessControl.firstChild.textContent='Hardness ';hardnessControl.classList.add('previewRange');$('brushHardness').setAttribute('aria-label','Hardness');
for(const [id,delta,icon,label] of [['hardnessMinus',-5,'minus','Decrease hardness'],['hardnessPlus',5,'plus','Increase hardness']]){const b=makeButton(id,phosphor[icon],label);b.type='button';b.className='rangeStep';b.onclick=()=>{$('brushHardness').value=Math.max(0,Math.min(100,+$('brushHardness').value+delta));$('brushHardness').oninput()};if(delta<0)$('brushHardness').before(b);else $('brushHardness').after(b)}
const lassoLabel=$('lassoMode').closest('label');lassoLabel.hidden=true;
const lassoModes=document.createElement('div');lassoModes.className='lassoModes';lassoModes.setAttribute('role','group');lassoModes.setAttribute('aria-label','Lasso operation');lassoModes.innerHTML='<span>Lasso</span>';
function syncLassoButtons(){for(const b of lassoModes.querySelectorAll('button')){const active=b.dataset.mode===$('lassoMode').value;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active))}}
for(const [mode,icon,label] of [['keep','plus','Lasso: Add to mask'],['remove','minus','Lasso: Remove from mask']]){const b=makeButton('lasso-'+mode,phosphor[icon],label);b.className='compactIcon filledIcon';b.dataset.mode=mode;b.onclick=()=>{$('lassoMode').value=mode;syncLassoButtons()};lassoModes.append(b)}syncLassoButtons();
const featherControl=$('lassoFeather').closest('label');featherControl.classList.add('previewFeather');
for(const node of [hardnessControl,lassoModes,featherControl])previewBar.insertBefore(node,$('homeView'));
const hiddenMaskOptions=document.querySelector('.maskToolOptions');hiddenMaskOptions.hidden=true;
const guideIcon='<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="12" rx="6" ry="9"/><path d="M12 1v22M2 10h20"/></svg>';
const guideToggleButton=makeButton('guideToggleButton',guideIcon,'Show / hide guide');guideToggleButton.className='compactIcon guideIcon';document.querySelector('.guideToggle').before(guideToggleButton);document.querySelector('.guideToggle').hidden=true;
function syncGuideButton(){guideToggleButton.classList.toggle('active',$('guide').checked);guideToggleButton.setAttribute('aria-pressed',String($('guide').checked))}
guideToggleButton.onclick=()=>{$('guide').checked=!$('guide').checked;syncGuideButton();draw()};registerCommand('guides',()=>guideToggleButton.click());syncGuideButton();
const drawCompactPreview=draw;draw=function(){syncGuideButton();drawCompactPreview()};

const previewHeaderActions=document.createElement('div');previewHeaderActions.className='previewHeaderActions';previewHeaderActions.setAttribute('role','group');previewHeaderActions.setAttribute('aria-label','Preview display');document.querySelector('.editorHead').append(previewHeaderActions);for(const id of ['before','cutoutToggle','previewBackground'])previewHeaderActions.append($(id));

const restorePortrait=makeButton('restorePortrait',phosphor['arrow-counter-clockwise'],'Restore last removed portrait');restorePortrait.className='compactIcon filledIcon';restorePortrait.hidden=true;$('clearPortraits').after(restorePortrait);restorePortrait.onclick=guarded(async()=>{const r=await api('/api/restore-portrait',{batch:batch.id});selected=r.id;await refresh(true)});
const renderWithRemovedPortraits=renderOutput;renderOutput=function(){renderWithRemovedPortraits();restorePortrait.hidden=!batch?.removed_files?.length;restorePortrait.disabled=busy};

// Keep the editor free of duplicate advanced disclosure rows.
detailInfo.hidden=true;advancedPosition.hidden=true;

// Advanced color lives in an anchored floating panel, without duplicate actions.
// Hue/Saturation used to live in this <details>, popped out into a
// floating "Advanced color" popover for a nicer disclosure than a plain
// <details> twisty. color-ranges.js (loaded later) now un-collapses them a
// second time, straight into the always-visible selective-color controls --
// so the popover and its trigger button are dead weight: nothing is left
// worth hiding behind a click-to-open panel. advancedColor itself still
// needs emptying out (its children move on, unmoved ones would otherwise
// vanish with it) and resetColor still needs a home; color-ranges.js claims
// both directly instead of through this now-pointless middleman.
for(const child of [...advancedColor.children])if(child.tagName!=='SUMMARY')document.body.append(child);advancedColor.remove();
// Auto correction and committing manual adjustments are separate actions.
// Keep a single text Apply Color action; distinguish Auto with a compact magic-wand icon.
$('autoColor').innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 20 12-12 3 3L7 23zM4 3v6M1 6h6M17 1v4M15 3h4M21 16v6M18 19h6"/></svg>';$('autoColor').classList.add('compactIcon');$('autoColor').title='Auto Color · gentle white balance and levels';$('autoColor').setAttribute('aria-label','Auto Color');

// Live settings feedback across the native Settings and Preview windows.
const previewSettingsChannel=typeof BroadcastChannel==='function'?new BroadcastChannel('clarette-preview-settings'):null;
let livePreviewValues={},livePreviewUntil=0;
if(previewSettingsChannel)previewSettingsChannel.onmessage=event=>{
 const changes={};const data=event.data||{};
 if(Number.isFinite(data.checker_brightness)&&data.checker_brightness>=0&&data.checker_brightness<=100)changes.checker_brightness=data.checker_brightness;
 if(typeof data.preview_background==='string'&&/^#[0-9a-f]{6}$/i.test(data.preview_background))changes.preview_background=data.preview_background;
 livePreviewValues={...livePreviewValues,...changes};livePreviewUntil=Date.now()+3000;
 if(app){Object.assign(app.settings,changes);draw()}
};
const renderWithPreviewSettings=renderOutput;renderOutput=function(){if(app&&Date.now()<livePreviewUntil)Object.assign(app.settings,livePreviewValues);return renderWithPreviewSettings()};
