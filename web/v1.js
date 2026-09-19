async function openNative(kind,payload={}){await flush();const r=await api('/api/window',{kind,payload});if(r.url)window.open(r.url,'clarette-'+kind,'width=900,height=760')}
const toolbar=document.querySelector('.topbar nav');$('help').hidden=true;$('apiKeys').hidden=true;
const exportButton=makeButton('exportButton',(phosphor['export']||phosphor['upload-simple'])+'<span>Export</span>','Export Finals');toolbar.prepend(exportButton);exportButton.onclick=()=>openNative('export');
$('settings').onclick=()=>openNative('settings');$('newBatch').onclick=()=>openNative('new-batch');$('emptyImport').onclick=()=>chooseImport(true);$('saveFinals').onclick=()=>openNative('export');
const externalButtons={photoshop:$('photoshop')};for(const name of ['affinity','photos']){const button=makeButton('external-'+name,(name==='photos'?'<img src="photos-icon.png" alt="" class="appIcon">':phosphor.images)+'<span>'+({affinity:'Affinity',photos:'Photos'}[name])+'</span>',name);toolbar.insertBefore(button,$('settings'));externalButtons[name]=button}
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
const polygonActions=document.createElement('div');polygonActions.id='polygonActions';polygonActions.hidden=true;polygonActions.innerHTML='<span id="polygonHint">Click points; click the first vertex or Enter to close.</span><button id="polygonAccept" class="primary">Accept</button><button id="polygonCancel">Cancel</button>';document.querySelector('.maskToolOptions').after(polygonActions);
function cancelPolygon(){polygon=null;polygonDrag=null;stroke=null;polygonActions.hidden=true;draw()}
function closePolygon(){if(!polygon||polygon.points.length<3)return;polygon.closed=true;$('polygonAccept').disabled=false;$('polygonHint').textContent='Drag vertices; click a segment to insert. Delete removes the selected vertex.';draw()}
$('polygonCancel').onclick=cancelPolygon;$('polygonAccept').onclick=guarded(async()=>{if(!polygon?.closed)return;const points=clone(polygon.points);await flush();await api('/api/mask-paint',context({strokes:[{mode:$('lassoMode').value,shape:'polygon',points,feather:+$('lassoFeather').value}]}));cancelPolygon();await refresh()});
const downV1=$('mainCanvas').onpointerdown,moveV1=$('mainCanvas').onpointermove,upV1=$('mainCanvas').onpointerup;
$('mainCanvas').onpointerdown=e=>{
 if(!current||busy||guideEditing||e.button!==0)return downV1(e);
 if(brush==='rotate'){if(current.position_locked)return;const g=geometry($('mainCanvas'));drag={rotate:true,x:e.clientX,rotation:current.transform.rotation||0};$('mainCanvas').setPointerCapture(e.pointerId);return}
 if(brush!=='lasso')return downV1(e);
 e.preventDefault();const p=sourcePoint(e);if(p.some(v=>v<0||v>1))return;
 if(!polygon){polygon={points:[],closed:false,selected:null};polygonActions.hidden=false;$('polygonAccept').disabled=true}
 const g=geometry($('mainCanvas')),factor=current.transform.scale*g.k;
 const distance=(a,b)=>Math.hypot((a[0]-b[0])*current.width*factor,(a[1]-b[1])*current.height*factor);
 const hit=polygon.points.findIndex(q=>distance(q,p)<10);
 if(hit===0&&!polygon.closed&&polygon.points.length>=3){closePolygon();return}
 if(hit>=0){polygon.selected=hit;polygonDrag=hit;$('mainCanvas').setPointerCapture(e.pointerId)}
 else if(polygon.closed){
  let inserted=false;
  for(let i=0;i<polygon.points.length;i++){const a=polygon.points[i],b=polygon.points[(i+1)%polygon.points.length],vx=b[0]-a[0],vy=b[1]-a[1],u=Math.max(0,Math.min(1,((p[0]-a[0])*vx+(p[1]-a[1])*vy)/(vx*vx+vy*vy||1)));if(distance(p,[a[0]+u*vx,a[1]+u*vy])<9){polygon.points.splice(i+1,0,p);polygon.selected=i+1;inserted=true;break}}
  if(!inserted)polygon.selected=null;
 }else{polygon.points.push(p);polygon.selected=polygon.points.length-1}
 draw();
};
$('mainCanvas').onpointermove=e=>{if(drag?.inspect)return moveV1(e);if(drag?.rotate){current.transform.rotation=drag.rotation+(e.clientX-drag.x)*.3;draw();return}if(brush==='lasso'&&polygonDrag!==null){polygon.points[polygonDrag]=sourcePoint(e).map(v=>Math.max(0,Math.min(1,v)));draw();return}if(brush==='lasso')return;return moveV1(e)};
$('mainCanvas').onpointerup=e=>{if(drag?.inspect)return upV1(e);if(drag?.rotate){drag=null;schedule();return}if(brush==='lasso'){polygonDrag=null;return}return upV1(e)};
const drawV1=draw;draw=function(){drawV1();if(!polygon||!current)return;const c=$('mainCanvas'),ctx=c.getContext('2d'),g=geometry(c),t=current.transform,iw=current.width*t.scale*g.k,ih=current.height*t.scale*g.k,x=g.ox+t.x*g.k,y=g.oy+t.y*g.k;ctx.save();ctx.translate(x+iw/2,y+ih/2);ctx.rotate((t.rotation||0)*Math.PI/180);ctx.translate(-iw/2,-ih/2);ctx.strokeStyle='#d9c8ff';ctx.fillStyle='#b69af533';ctx.lineWidth=1.5;ctx.beginPath();polygon.points.forEach(([px,py],i)=>i?ctx.lineTo(px*iw,py*ih):ctx.moveTo(px*iw,py*ih));if(polygon.closed){ctx.closePath();ctx.fill()}ctx.stroke();polygon.points.forEach(([px,py],i)=>{ctx.fillStyle=i===polygon.selected?'#ffffff':'#b69af5';ctx.fillRect(px*iw-4,py*ih-4,8,8)});ctx.restore()};
// Workspace layout replaces the old fixed-column separators, retaining the panels themselves.
separators.forEach(el=>el.remove());layoutPanels=()=>{};
const panels={portraits:document.querySelector('.batch'),preview:document.querySelector('.editor'),adjustments:document.querySelector('.inspector')};
for(const [id,panel] of Object.entries(panels)){panel.dataset.panel=id;const handle=document.createElement('div');handle.className='panelDrag';handle.setAttribute('aria-label','Drag to move '+id);handle.draggable=true;panel.prepend(handle);handle.ondragstart=e=>{if(app.workspaces[app.workspace].locked){e.preventDefault();message('Unlock the workspace (Workspace menu) to rearrange panels',true);return}e.dataTransfer.setData('text/clarette-panel',id)};panel.ondragover=e=>{if(!app.workspaces[app.workspace].locked)e.preventDefault()};panel.ondrop=guarded(async e=>{e.preventDefault();const id=e.dataTransfer.getData('text/clarette-panel');if(!panels[id])return;const ws=clone(app.workspaces[app.workspace]);if(ws.locked)return;const from=ws.order.indexOf(id),to=ws.order.indexOf(panel.dataset.panel);ws.order.splice(from,1);ws.order.splice(to,0,id);await api('/api/workspace',{workspace:ws});workspaceSignature='';await refresh()})}
// In Portrait Mode's nested layout, the Portraits and Adjustments panels share one
// resizable column. Past a width threshold each reflows for the extra room: Portraits
// becomes a horizontal filmstrip, Adjustments spreads its sections into outlined columns.
const nestedResize=new ResizeObserver(entries=>{const nested=app?.workspaces?.[app.workspace]?.orientation==='nested';for(const entry of entries){if(entry.target===panels.portraits)panels.portraits.classList.toggle('filmstrip',nested&&entry.contentRect.width>440);if(entry.target===panels.adjustments)panels.adjustments.classList.toggle('wide',nested&&entry.contentRect.width>680)}});
nestedResize.observe(panels.portraits);nestedResize.observe(panels.adjustments);
// One set of limits for pointer, keyboard and restored workspace sizes.
function panelMinimum(id,vertical){return (vertical?{portraits:220,preview:480,adjustments:320}:{portraits:250,preview:400,adjustments:330})[id]}
function panelMaximum(id,vertical){return vertical?Infinity:({portraits:400,preview:Infinity,adjustments:520})[id]}
function resizePanelPair(p,neighbor,vertical,first,total){const minimum=panelMinimum(p.dataset.panel,vertical),otherMinimum=panelMinimum(neighbor.dataset.panel,vertical);total=Math.max(total,minimum+otherMinimum);const low=Math.max(minimum,total-panelMaximum(neighbor.dataset.panel,vertical)),high=Math.min(total-otherMinimum,panelMaximum(p.dataset.panel,vertical));const value=Math.max(low,Math.min(high,first));p.style.flex=`0 0 ${value}px`;neighbor.style.flex=`0 0 ${total-value}px`;if(vertical){p.style.height=value+'px';neighbor.style.height=(total-value)+'px'}return value}
let workspaceSignature='';function syncWorkspace(){if(!app?.workspaces)return;const ws=app.workspaces[app.workspace],signature=JSON.stringify([app.workspace,ws]);if(signature===workspaceSignature)return;workspaceSignature=signature;
 const nested=ws.orientation==='nested';
 panelLayout.classList.toggle('vertical',ws.orientation==='vertical');panelLayout.classList.toggle('nested',nested);panelLayout.classList.toggle('layoutLocked',ws.locked);panelLayout.querySelectorAll('.workspaceDivider,.nestedDivider').forEach(el=>el.remove());
 for(const id of ws.order)panels[id].hidden=ws.visible?.[id]===false;const visibleOrder=ws.order.filter(id=>ws.visible?.[id]!==false);
 // Portrait Mode's nested arrangement: Preview spans the full height on one side,
 // Portraits stacks above Adjustments on the other, sharing one resizable column
 // (--nestedCol). Dragging it wider crosses thresholds (see the ResizeObserver
 // above) that switch Portraits to a filmstrip and Adjustments to outlined columns.
 if(nested){
  for(const id of visibleOrder){panelLayout.append(panels[id]);panels[id].style.flex='';panels[id].style.width='';panels[id].style.height=''}
  const colIndex=ws.order.indexOf('portraits');
  panelLayout.style.setProperty('--nestedCol',Math.max(300,Math.min(900,ws.sizes[colIndex]))+'px');
  if(!ws.locked){
   const div=document.createElement('div');div.className='nestedDivider';div.tabIndex=0;div.setAttribute('role','separator');div.setAttribute('aria-orientation','vertical');div.setAttribute('aria-label','Resize Portraits and Adjustments column');panelLayout.append(div);
   let start=null;
   div.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();start={x:e.clientX,width:panels.portraits.offsetWidth};div.classList.add('dragging');div.setPointerCapture(e.pointerId)};
   div.onpointermove=e=>{if(!start)return;panelLayout.style.setProperty('--nestedCol',Math.max(300,Math.min(900,start.width-(e.clientX-start.x)))+'px')};
   div.onpointerup=guarded(async()=>{if(!start)return;start=null;div.classList.remove('dragging');const width=Math.round(panels.portraits.offsetWidth);ws.sizes=ws.order.map((id,i)=>id==='portraits'||id==='adjustments'?width:ws.sizes[i]);await api('/api/workspace',{workspace:ws});await refresh()});
   div.onpointercancel=div.onpointerup;
   div.onkeydown=guarded(async e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const width=Math.max(300,Math.min(900,panels.portraits.offsetWidth+(e.key==='ArrowLeft'?16:-16)));panelLayout.style.setProperty('--nestedCol',width+'px');ws.sizes=ws.order.map((id,i)=>id==='portraits'||id==='adjustments'?width:ws.sizes[i]);await api('/api/workspace',{workspace:ws});await refresh()});
  }
  draw();return;
 }
 visibleOrder.forEach((id,visibleIndex)=>{const index=ws.order.indexOf(id),p=panels[id];panelLayout.append(p);p.style.flex=`${id==='preview'?'1 1':'0 0'} ${Math.min(panelMaximum(id,ws.orientation==='vertical'),Math.max(panelMinimum(id,ws.orientation==='vertical'),ws.sizes[index]))}px`;p.style.width=ws.orientation==='vertical'?'100%':'';p.style.height=ws.orientation==='vertical'?ws.sizes[index]+'px':'';
 if(visibleIndex===visibleOrder.length-1||ws.locked)return;const div=document.createElement('div');div.className='workspaceDivider';div.style.flexBasis='3px';div.tabIndex=0;div.setAttribute('role','separator');div.setAttribute('aria-label','Resize '+id);panelLayout.append(div);let start=null;
 div.onpointerdown=e=>{if(ws.locked)return;const neighbor=panels[visibleOrder[visibleIndex+1]];if(e.button!==0)return;e.preventDefault();start={x:e.clientX,y:e.clientY,size:ws.orientation==='vertical'?p.offsetHeight:p.offsetWidth,neighbor,otherSize:ws.orientation==='vertical'?neighbor.offsetHeight:neighbor.offsetWidth};div.setPointerCapture(e.pointerId)};
 div.onpointermove=e=>{if(!start)return;resizePanelPair(p,start.neighbor,ws.orientation==='vertical',start.size+(ws.orientation==='vertical'?e.clientY-start.y:e.clientX-start.x),start.size+start.otherSize);draw()};
 div.onpointerup=guarded(async()=>{if(!start)return;start=null;ws.sizes=ws.order.map(key=>Math.round(ws.orientation==='vertical'?panels[key].offsetHeight||ws.sizes[ws.order.indexOf(key)]:panels[key].offsetWidth||ws.sizes[ws.order.indexOf(key)]));await api('/api/workspace',{workspace:ws});await refresh()});
 div.onpointercancel=div.onpointerup;
 div.onkeydown=guarded(async e=>{const vertical=ws.orientation==='vertical';if(ws.locked||!(vertical?['ArrowUp','ArrowDown']:['ArrowLeft','ArrowRight']).includes(e.key))return;e.preventDefault();const neighbor=panels[visibleOrder[visibleIndex+1]],size=vertical?p.offsetHeight:p.offsetWidth,other=vertical?neighbor.offsetHeight:neighbor.offsetWidth;resizePanelPair(p,neighbor,vertical,size+(['ArrowLeft','ArrowUp'].includes(e.key)?-16:16),size+other);ws.sizes=ws.order.map(key=>Math.round((vertical?panels[key].offsetHeight:panels[key].offsetWidth)||ws.sizes[ws.order.indexOf(key)]));await api('/api/workspace',{workspace:ws});await refresh()});
 div.setAttribute('aria-orientation',ws.orientation==='vertical'?'horizontal':'vertical');

 });draw();}
const oldRenderV1=renderOutput;renderOutput=function(){oldRenderV1();if(!app)return;syncWorkspace();$('batchCount').replaceChildren('Portraits',Object.assign(document.createElement('span'),{className:'batchMeta',textContent:' · '+(batch?.files.length||0)+(batch?' · '+batch.name:'')}));$('batchCount').title=batch?.name||'No active batch';for(const [name,b] of Object.entries(externalButtons))b.hidden=!(app.settings.toolbar_apps.includes(name)&&app.external_apps[name]);previewColor.classList.toggle('active',app.settings.preview_color!==false);backgroundToggle.classList.toggle('active',app.settings.solid_preview);backgroundToggle.querySelector('svg').style.fill=app.settings.preview_background||'#00a84f';syncEnhanceProviders();passportNote.hidden=batch?.canvas.preset_id!=='passport';$('saveCurrentPreset').disabled=!batch||Object.values(app.presets).some(p=>p.width===batch.canvas.width&&p.height===batch.canvas.height&&p.dpi===batch.canvas.dpi);$('matchSource').disabled=!current};
const oldLoadV1=loadSelected;loadSelected=async function(){cancelPolygon();await oldLoadV1();renderOutput()};
for(const [id,button] of Object.entries({'import':'importBtn','clear':'clearPortraits','working':'working','final':'openFinal','undo':'undo','redo':'redo','auto-fit':'autoFit','auto-color':'autoColor','enhance':'enhance','compare':'before','preview-color':'previewColor','transparency':'previewBackground','fit':'homeView','lock':'lockPosition','crop':'crop'}))registerCommand(id,()=>$(button).click());
for(const kind of ['settings','shortcuts','help','new-batch','rename-batch','export','updates'])registerCommand(kind,()=>openNative(kind));
for(const [id,tool] of [['brush','keep'],['erase','remove'],['move','move'],['lasso','lasso'],['rotate','rotate']])registerCommand(id,()=>document.querySelector('[data-brush="'+tool+'"]').click());
registerCommand('guides',()=>{$('guide').checked=!$('guide').checked;draw()});registerCommand('solid',async()=>{await api('/api/settings',{solid_preview:true});await refresh();draw()});
registerCommand('close-batch',async()=>{if(!batch)return;if(!confirm('Close this batch? Unsaved work remains recoverable for seven days.'))return;await flush();await api('/api/close-batch',{confirmed:true});selected=null;await refresh(true)});
registerCommand('import-zip',()=>{$('fileInput').accept='.zip';chooseImport(true)});
registerCommand('batch-folder',async()=>{const r=await api('/api/choose-path',{kind:'folder'});if(r.path){await api('/api/batch-folder',{path:r.path});await refresh()}});
for(const mode of ['rgb','cmyk'])registerCommand(mode,async()=>{await api('/api/color-mode',{mode:mode.toUpperCase()});await refresh()});
for(const id of ['landscape','portrait'])registerCommand(id,async()=>{await api('/api/workspace',{id,operation:'select'});await refresh()});
for(const op of ['new','rename'])registerCommand('workspace-'+op,()=>openNative('workspace',{operation:op}));
registerCommand('workspace-delete',async()=>{if(confirm('Delete this custom workspace?')){await api('/api/workspace',{operation:'delete'});await refresh()}});
registerCommand('workspace-lock',async()=>{await api('/api/workspace',{operation:'lock',locked:!app.workspaces[app.workspace].locked});await refresh()});
registerCommand('workspace-reset',async()=>{if(confirm('Reset the current workspace layout?')){await api('/api/workspace',{operation:'reset'});await refresh()}});
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

const restorePortrait=makeButton('restorePortrait',phosphor['arrow-counter-clockwise'],'Restore last removed portrait');restorePortrait.className='compactIcon filledIcon';restorePortrait.hidden=true;$('batchCount').after(restorePortrait);restorePortrait.onclick=guarded(async()=>{const r=await api('/api/restore-portrait',{batch:batch.id});selected=r.id;await refresh(true)});
const renderWithRemovedPortraits=renderOutput;renderOutput=function(){renderWithRemovedPortraits();restorePortrait.hidden=!batch?.removed_files?.length;restorePortrait.disabled=busy};

// Keep the editor free of duplicate advanced disclosure rows.
detailInfo.hidden=true;advancedPosition.hidden=true;

// Keep the adjustment sequence consistent with the workflow.
for(const node of [outputSection,framing,colorSection,document.querySelector('.detailSection'),maskSectionRef])panels.adjustments.append(node);
// Advanced color lives in an anchored floating panel, without duplicate actions.
const advancedColorButton=makeButton('advancedColorButton',phosphor['sliders-horizontal'],'Advanced color');advancedColorButton.className='compactIcon filledIcon';advancedColorButton.setAttribute('aria-expanded','false');$('previewColor').before(advancedColorButton);
const colorPopover=document.createElement('div');colorPopover.id='colorPopover';colorPopover.hidden=true;colorPopover.setAttribute('role','dialog');colorPopover.setAttribute('aria-label','Advanced color');colorPopover.innerHTML='<div class="colorPopoverHead"><span>Color adjustments</span><button type="button" id="closeAdvancedColor" aria-label="Close color adjustments">×</button></div>';document.body.append(colorPopover);
for(const child of [...advancedColor.children])if(child.tagName!=='SUMMARY')colorPopover.append(child);advancedColor.remove();
function closeColorPopover(){colorPopover.hidden=true;advancedColorButton.setAttribute('aria-expanded','false')}
advancedColorButton.onclick=()=>{const opening=colorPopover.hidden;closeColorPopover();if(opening){colorPopover.hidden=false;const r=advancedColorButton.getBoundingClientRect();colorPopover.style.left=Math.max(8,Math.min(window.innerWidth-colorPopover.offsetWidth-8,r.right-colorPopover.offsetWidth))+'px';colorPopover.style.top=Math.max(8,Math.min(window.innerHeight-colorPopover.offsetHeight-8,r.bottom+6))+'px';advancedColorButton.setAttribute('aria-expanded','true')}};
$('closeAdvancedColor').onclick=closeColorPopover;document.addEventListener('pointerdown',e=>{if(!colorPopover.contains(e.target)&&!advancedColorButton.contains(e.target))closeColorPopover()});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!colorPopover.hidden){e.stopPropagation();closeColorPopover();advancedColorButton.focus()}},true);window.addEventListener('resize',closeColorPopover);
// Auto correction and committing manual adjustments are separate actions.
// Keep a single text Apply Color action; distinguish Auto with a compact magic-wand icon.
$('autoColor').innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 20 12-12 3 3L7 23zM4 3v6M1 6h6M17 1v4M15 3h4M21 16v6M18 19h6"/></svg>';$('autoColor').classList.add('compactIcon');$('autoColor').title='Auto Color · gentle white balance and levels';$('autoColor').setAttribute('aria-label','Auto Color');
colorPopover.append($('resetColor'));

const renderPanelNames=renderOutput;renderOutput=function(){renderPanelNames();
 // Dragging reorders panels within a single row/column; Portrait Mode's nested
 // layout (see syncWorkspace) is fixed by position instead, so dragging there
 // wouldn't do anything yet -- hide the handles rather than ship a dead control.
 const nested=app?.workspaces?.[app.workspace]?.orientation==='nested';
 document.querySelectorAll('.panelDrag').forEach(el=>{el.hidden=nested||app?.settings.show_panel_names===false})};

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
