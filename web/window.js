'use strict';
const $=id=>document.getElementById(id),query=new URLSearchParams(location.search),kind=query.get('kind')||'settings',sections=['General','Workspace & Preview','Output & Metadata','Cache & Performance','AI & APIs','Presets & Models','Toolbar & Apps','License','Keyboard Shortcuts'];
let state,section=query.get('section')||'General';
const previewChannel=typeof BroadcastChannel==='function'?new BroadcastChannel('clarette-preview-settings'):null;
let previewSaveQueue=Promise.resolve();
function livePreviewSetting(el){const key=el.dataset.setting,value=el.type==='range'?+el.value:el.value;state.settings[key]=value;previewChannel?.postMessage({[key]:value});clearTimeout(el.previewTimer);return {[key]:value}}
function savePreviewSetting(el){const values=livePreviewSetting(el);previewSaveQueue=previewSaveQueue.catch(()=>{}).then(()=>api('/api/settings',values));previewSaveQueue.catch(e=>status(e.message,true))}
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const status=(text,error=false)=>{$('status').textContent=text;$('status').className=error?'danger':''};
async function api(path,data={}){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Glass-Token':state.token},body:JSON.stringify(data)});const d=await r.json();if(!r.ok)throw Error(d.error);return d}
function safe(fn){return async(...args)=>{try{await fn(...args)}catch(e){status(e.message,true)}}}
async function refresh(){state=await(await fetch(kind==='settings'||kind==='shortcuts'?'/api/state?view=settings':'/api/state')).json()}
async function closeDialogWindow(){await api('/api/close-window',{kind});if(!state.native)window.close()}
function checkbox(key,label){return `<label>${esc(label)}<input type="checkbox" data-setting="${key}" ${state.settings[key]?'checked':''}></label>`}
function select(key,label,options){return `<label>${esc(label)}<select data-setting="${key}">${options.map(o=>{let [v,t]=Array.isArray(o)?o:[o,o];return `<option value="${esc(v)}" ${state.settings[key]===v?'selected':''}>${esc(t)}</option>`}).join('')}</select></label>`}
function input(key,label,type='text'){return `<label>${esc(label)}<input type="${type}" data-setting="${key}" value="${esc(state.settings[key])}"></label>`}
function button(id,label,primary=false){return `<button id="${id}" class="${primary?'primary':''}">${esc(label)}</button>`}
function pathField(key,label,folder=false){return `<p>${esc(label)}</p><div class="row"><input id="${key}" value="${esc(state.settings[key])}" aria-label="${esc(label)}">${button('choose-'+key,'Choose…')}</div>`}
function wireSettings(){document.querySelectorAll('[data-tool]').forEach(el=>el.onchange=safe(async()=>{await api('/api/settings',{toolbar_tools:[...document.querySelectorAll('[data-tool]:checked')].map(x=>x.dataset.tool)});status('Toolbar saved')}));document.querySelectorAll('[data-setting]').forEach(el=>el.onchange=safe(async()=>{let value=el.type==='checkbox'?el.checked:['number','range'].includes(el.type)?+el.value:el.value;await api('/api/settings',{[el.dataset.setting]:value});state.settings[el.dataset.setting]=value;status('Saved automatically')}));for(const key of ['final_folder','print_profile','restore_location','hypir_location','osediff_location','flowsr_location','seesr_location']){const field=$(key);if(!field)continue;field.onchange=safe(async()=>{await api('/api/settings',{[key]:field.value});state.settings[key]=field.value;status('Saved automatically')});$('choose-'+key).onclick=safe(async()=>{const r=await api('/api/choose-path',{kind:key==='final_folder'||(key.endsWith('_location')&&key!=='hypir_location')?'folder':'file'});if(r.path){field.value=r.path;await field.onchange()}})}}
async function downloadDocument(doc){const result=await api('/api/save-document',{document:doc});if(result.document){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(doc,null,2)],{type:'application/json'}));a.download=doc.format+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),5000)}status(result.cancelled?'Cancelled':'Exported')}
function importFile(onRead){const input=document.createElement('input');input.type='file';input.accept='.json';input.onchange=safe(async()=>{if(!input.files[0])return;if(input.files[0].size>262144)throw Error('Choose a JSON file smaller than 256 KB');await onRead(JSON.parse(await input.files[0].text()))});input.click()}
const settingsIcons={
 'General':'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z',
 'Workspace & Preview':'M3 4h18v16H3zM8 4v16M16 4v16',
 'Output & Metadata':'M12 3v12m-4-4 4 4 4-4M4 15v6h16v-6',
 'Cache & Performance':'M4 17a9 9 0 1 1 16 0M12 13l5-6M8 21h8',
 'AI & APIs':'m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3z',
 'Presets & Models':'M3 4h7v7H3zM14 4h7v7h-7zM3 15h7v7H3zM14 15h7v7h-7z',
 'Toolbar & Apps':'M3 5h18v14H3zM3 10h18M7 7h1m3 0h1',
 'Keyboard Shortcuts':'M2 5h20v14H2zM6 9h1m3 0h1m3 0h1m3 0h1M6 13h1m3 0h1m3 0h1m3 0h1M7 16h10',
 'License':'M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4'};
function settingsNavigation(){
 document.body.classList.add('settingsWindow');
 $('navigation').innerHTML='<div class="settingsNavTitle">Settings</div><input id="settingsSearch" type="search" placeholder="Search settings" aria-label="Search settings"><div class="settingsNavItems">'+sections.map(s=>`<button class="${s===section?'active':''}" data-section="${esc(s)}" ${s===section?'aria-current="page"':''}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${settingsIcons[s]}"/></svg><span>${esc(s)}</span></button>`).join('')+`</div><p id="noSettingsMatches" hidden>No matching sections</p><div class="settingsNavFooter">Clarette · ${esc(state.version)}</div>`;
 document.querySelectorAll('[data-section]').forEach(b=>b.onclick=safe(async()=>{section=b.dataset.section;await settings();document.querySelector('main').scrollTop=0}));
 const terms={'General':'notifications sound beep panel names siri shortcuts','Workspace & Preview':'background transparency guides saved batches','Output & Metadata':'file format jpeg png tiff dpi icc profile copyright folder','Cache & Performance':'storage models acceleration disk','AI & APIs':'prompt key openai chatgpt gemini seedream connection','Presets & Models':'restore hypir edsr osediff flowsr seesr import export','Toolbar & Apps':'photoshop affinity photos chatgpt gemini prompt','Keyboard Shortcuts':'keys commands keyboard'};
 $('settingsSearch').oninput=()=>{const q=$('settingsSearch').value.toLowerCase().trim();let found=false;document.querySelectorAll('[data-section]').forEach(b=>{b.hidden=!(b.dataset.section+' '+terms[b.dataset.section]).toLowerCase().includes(q);if(!b.hidden)found=true});$('noSettingsMatches').hidden=found};
}
function groupSettingsContent(){
 const content=$('content');let card=null;
 for(const el of [...content.children]){
  if(el.tagName==='SECTION'||el.classList.contains('hint')){card=null;continue}
  if(!card||el.tagName==='H2'){card=document.createElement('section');card.className='settingsCard';content.insertBefore(card,el)}
  card.append(el);
 }
 content.querySelectorAll('input[type=checkbox]').forEach(el=>el.setAttribute('role','switch'));
}
const providerVerified={};
const apiIcon=path=>`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"/></svg>`;
let settingsGeneration=0;
async function settings(){
 const generation=++settingsGeneration;
 $('content').classList.remove('shortcutPage');$('title').textContent=section;status('');settingsNavigation();
 if(section==='Keyboard Shortcuts'){await shortcuts();return}
 let html='';
 if(section==='General')html=`<section>${checkbox('notifications','Notification When Processing Finishes')}${checkbox('notification_sound','Beep When Done')}${checkbox('voice_commands','Enable Local Siri & Shortcuts Actions')}${button('resetGeneral','Reset General')}</section><h2>Clarette ${esc(state.version)}</h2><p>Build ${esc(state.build)} · Apple Silicon</p>${button('resetAll','Reset to Defaults…')}`;
 if(section==='Workspace & Preview'){
  const ws=state.workspace2||{active:'landscape',locked:false,custom:{}};
  html=`<section><label>Checker Brightness<span class="previewSettingControls"><input type="range" min="0" max="100" data-setting="checker_brightness" value="${state.settings.checker_brightness}"><button id="resetChecker" class="settingsReset" title="Reset Checker Background" aria-label="Reset Checker Background">${apiIcon('M3 4v6h6M3 10a9 9 0 1 1 1 8')}</button></span></label>${input('preview_background','Solid Preview Color','color')}</section><h2>Saved Batches</h2><div class="savedBatchRow"><select id="recoverBatch" aria-label="Saved Batches">${Object.values(state.batches).map(b=>`<option value="${esc(b.id)}" ${b.id===state.active?'selected':''}>${esc(b.name)}${b.closed_at?' · closed':''}</option>`).join('')}</select>${button('openBatch','Open Batch')}</div><h2>Workspace</h2><label>Drag Panels<input id="dragPanels" type="checkbox" ${ws.locked?'':'checked'}></label><p class="hint">Drag any panel by its tab to rearrange the workspace, drop on an edge to split, or drop in the center to combine panels into tabs. Layout presets, Save Workspace Layout, Reset Current Workspace and Restore Default Layout are in the Workspace menu.</p>`;
 }
 if(section==='Output & Metadata')html=`<section>${pathField('final_folder','Default Final Output location',true)}<p class="hint">Changing one batch’s destination does not change this default.</p></section><section>${select('cutout_format','With cutout / transparency',['PNG','TIFF'])}${select('photo_format','Without cutout',['JPEG','PNG','TIFF'])}${input('jpeg_quality','JPEG quality','number')}${select('tiff_compression','TIFF compression',[['tiff_lzw','LZW'],['tiff_adobe_deflate','ZIP'],['raw','None']])}${checkbox('embed_profile','Embed Color Profile')}<label>CMYK Print ICC Profile<select id="printProfileList" aria-label="CMYK Print ICC Profile"></select></label>${pathField('print_profile','Custom Profile')}<p class="hint">RGB exports use sRGB. PNG requires RGB. CMYK transparency is unavailable; flatten explicitly or use RGB.</p></section><section>${select('metadata_mode','Source metadata',[['preserve','Preserve source metadata'],['copyright','Copyright / creator only'],['strip','Strip metadata']])}${checkbox('processing_metadata','Embed Clarette processing information')}</section>`;
 if(section==='Cache & Performance'){html=`<section><h2>Temporary Cache Location</h2><p class="path"><span id="cacheLocation">…</span></p><p>Current Cache Size: <span id="cacheSize">…</span></p><p>AI Model Storage Size: <span id="modelSize">…</span></p>${button('emptyCache','Empty Cache…')}<p class="hint">Active work stays protected. Closed batches remain recoverable for seven days. Models, preferences and final exports are kept.</p></section>${checkbox('accelerate','Try Apple acceleration (CPU fallback)')}${select('upscale_method','Classical upscale',[['fast','Fast · Lanczos'],['neural','Neural · EDSR']])}`;}
 if(section==='AI & APIs')html=`<section><div class="apiCardHeading"><h2>Enhancement Prompt</h2>${button('resetPrompt','Reset')}</div><textarea id="prompt" aria-label="Enhancement Prompt" rows="5">${esc(state.settings.enhancement_prompt||state.prompt)}</textarea></section>`+['openai','gemini','seedream'].map(p=>`<section class="apiProvider"><div class="apiCardHeading"><h2>${{openai:'ChatGPT / OpenAI',gemini:'Gemini',seedream:'Seedream'}[p]}</h2><span id="${p}-status" class="apiConnection" role="status"></span></div><div class="apiKeyRow"><input id="${p}-key" type="password" autocomplete="off" spellcheck="false" placeholder="${state.settings[p+'_connected']?'Key saved · Enter a key to replace':'Enter API key'}" aria-label="${p} API key">${button(p+'-save','Save')}</div><div class="apiControlRow"><button id="${p}-test" class="apiTest">${apiIcon('m8 5 11 7-11 7z')}<span>Test</span></button><button id="${p}-refresh" class="apiIcon" title="Refresh Models" aria-label="Refresh ${p} Models">${apiIcon('M20 7v5h-5M4 17v-5h5M5 8a8 8 0 0 1 13-3l2 3M4 16l2 3a8 8 0 0 0 13-3')}</button><button id="${p}-remove" class="apiIcon" title="Remove Key" aria-label="Remove ${p} Key">${apiIcon('M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7')}</button><label class="apiModel">Model:<select id="${p}-model" aria-label="${p} model"></select></label></div><input id="${p}-custom-model" class="field" aria-label="${p} custom model ID" placeholder="Model ID" hidden></section>`).join('');
 if(section==='Presets & Models')html=`<section class="compactPresets"><div class="presetHeading"><h2>Output Presets</h2></div><select id="presetList" class="field" aria-label="Output Presets">${Object.entries(state.presets).map(([id,p])=>`<option value="${esc(id)}">${esc(p.label)} · ${p.width} × ${p.height}</option>`).join('')}</select><div class="presetFooter"><div class="presetActions">${['Create','Rename','Edit'].map(op=>button('preset'+op,op)).join('')}<button id="presetDuplicate" class="presetIcon" title="Duplicate Preset" aria-label="Duplicate Preset">${apiIcon('M8 8h13v13H8zM16 8V3H3v13h5')}</button><button id="presetDelete" class="presetIcon" title="Delete Preset" aria-label="Delete Preset">${apiIcon('M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7')}</button><button id="resetPresets" class="presetIcon" title="Reset Built-in Presets" aria-label="Reset Built-in Presets">${apiIcon('M3 4v6h6M3 10a9 9 0 1 1 1 8')}</button></div><div class="presetTransfers">${button('importPresets','Import')}${button('exportPresets','Export')}</div></div></section><section class="compactPreferences"><h2>Preferences</h2><div class="row">${button('exportPreferences','Export')}${button('importPreferences','Import')}</div></section><section class="compactModels"><h2>Enhancement Models</h2>${['restore','edsr','hypir','osediff','flowsr','seesr'].map(k=>{const info=k==='restore'?state.restore:state.engines[k],ready=info.status==='Ready',managed=['edsr','osediff','flowsr','seesr'].includes(k),external=info.external===true,name={restore:'Clarette Restore',edsr:'EDSR',hypir:'HYPIR',osediff:'OSEDiff',flowsr:'FlowSR',seesr:'SeeSR'}[k];return `<div class="modelRow"><strong>${name}</strong><span class="modelState" title="${esc(info.message||'')}">${external?'External · '+info.status:ready?(k==='flowsr'?'Installed · Noncommercial':'Installed'):managed?'Not Installed':k==='restore'?'Awaiting Model':'Mac Integration Pending'}</span><button data-model-engine="${k}" data-installed="${ready}" data-external="${external}" ${managed||external?'':'disabled'} title="${external?'Disconnect '+name:managed?(ready?'Uninstall '+name:'Install '+name):ready?'Managed installer and uninstaller not available yet':'Mac installer not available yet'}">${external?'Disconnect':ready?'Uninstall':'Install'}</button></div>`}).join('')}</section>`;
 if(section==='Toolbar & Apps')html=Object.entries({photoshop:'Adobe Photoshop',affinity:'Affinity',photos:'Apple Photos'}).map(([key,name])=>`<label>${name}${state.external_apps[key]?'':' · Not installed'}<input type="checkbox" data-app="${key}" ${state.settings.toolbar_apps.includes(key)?'checked':''} ${state.external_apps[key]?'':'disabled'}></label>`).join('')+Object.entries({chatgpt:'ChatGPT',gemini:'Gemini',prompt:'Prompt'}).map(([key,name])=>`<label>${name}<input type="checkbox" data-tool="${key}" ${state.settings.toolbar_tools.includes(key)?'checked':''}></label>`).join('');
 if(section==='License'){
  const lic=state.licensed||{licensed:false,email:null,issued:null,error:null},key=state.settings.license_key||'';
  const checkIcon='<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#4c9eff"/><path d="M8 12.5l2.6 2.6L16 9.3" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const lockIcon='<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2" fill="none" stroke="#9d94b3" stroke-width="1.6"/><path d="M8 11V7a4 4 0 0 1 8 0v4" fill="none" stroke="#9d94b3" stroke-width="1.6"/></svg>';
  const dateLabel=lic.issued?new Date(lic.issued+'T00:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}):'—';
  const masked=key.length>8?'•••• •••• '+key.slice(-4).toUpperCase():key;
  const typeLabel={gift:'Gift',personal:'Personal',purchased:'Purchased'}[lic.type]||'Purchased';
  html=lic.licensed
   ?`<section><div class="licenseHead">${checkIcon}<h2>Clarette Activated</h2></div><p style="color:#bdb3cf;font-size:12px;line-height:1.5;margin:0 0 16px">Your license is verified locally on this Mac and works fully offline.</p><div class="card licenseKeyCard"><span class="licenseKeyLabel">License Key</span><div class="licenseKeyRow"><span class="licenseKeyMasked">${esc(masked)}</span>${lockIcon}</div></div><div class="licenseRow"><span>Status</span><span>Active</span></div><div class="licenseRow"><span>License</span><span>${esc(typeLabel)}</span></div><div class="licenseRow"><span>Registered to</span><span>${esc(lic.email||"—")}</span></div><div class="licenseRow"><span>Activated</span><span>${esc(dateLabel)}</span></div><div class="row" style="margin-top:16px">${button('copyLicenseKey','Copy License Key')}${button('deactivateLicense','Deactivate This Mac')}</div><details class="licenseSwap"><summary>Use a Different Key</summary><label>License key<input id="settingsLicenseKey" type="text" autocomplete="off" spellcheck="false"></label><div class="row" style="justify-content:flex-end">${button('activateLicenseSettings','Activate',true)}</div></details><p class="licenseStatusLine">${checkIcon}Clarette is active on this Mac.</p></section>`
   :`<section><h2>Activate Clarette</h2><p style="color:#bdb3cf;font-size:12px;line-height:1.5;margin:0 0 16px">${esc(lic.error||'Enter the license key from your purchase confirmation email.')}</p><label>License key<input id="settingsLicenseKey" type="text" autocomplete="off" spellcheck="false" value="${esc(key)}"></label><div class="row" style="justify-content:flex-end">${button('activateLicenseSettings','Activate',true)}</div></section>`;
 }
 $('content').innerHTML=html;groupSettingsContent();wireSettings();
 if($('printProfileList'))api('/api/print-profiles').then(data=>{if(generation!==settingsGeneration)return;const list=$('printProfileList');list.replaceChildren(new Option('Select Profile',''),...data.profiles.map(p=>new Option(p.name,p.path)),new Option('Custom…','custom'));list.value=data.profiles.some(p=>p.path===state.settings.print_profile)?state.settings.print_profile:state.settings.print_profile?'custom':'';list.onchange=safe(async()=>{if(list.value==='custom'){$('choose-print_profile').click();return}await api('/api/settings',{print_profile:list.value});state.settings.print_profile=list.value;$('print_profile').value=list.value})}).catch(e=>{if(generation===settingsGeneration)status(e.message,true)});
 if(section==='Cache & Performance')api('/api/storage').then(data=>{if(generation!==settingsGeneration)return;$('cacheLocation').textContent=data.cache_location;$('cacheSize').textContent=bytes(data.cache_bytes);$('modelSize').textContent=bytes(data.model_bytes)}).catch(e=>{if(generation===settingsGeneration)status(e.message,true)});
 for(const key of ['checker_brightness','preview_background']){const el=document.querySelector(`[data-setting="${key}"]`);if(!el)continue;el.oninput=()=>{livePreviewSetting(el);el.previewTimer=setTimeout(()=>savePreviewSetting(el),100)};el.onchange=()=>savePreviewSetting(el)}
 if($('resetChecker'))$('resetChecker').onclick=()=>{const el=document.querySelector('[data-setting="checker_brightness"]');el.value=35;savePreviewSetting(el)};
 if($('dragPanels'))$('dragPanels').onchange=safe(async()=>{await api('/api/workspace',{operation:'lock',locked:!$('dragPanels').checked});await refresh();settings()});
 if($('openBatch'))$('openBatch').onclick=safe(async()=>{await api('/api/select-batch',{batch:$('recoverBatch').value});status('Batch opened in the main window')});
 if($('prompt'))$('prompt').onchange=safe(async()=>{await api('/api/settings',{enhancement_prompt:$('prompt').value});state.prompt=$('prompt').value;status('Prompt saved')});
 if($('activateLicenseSettings'))$('activateLicenseSettings').onclick=safe(async()=>{await api('/api/activate-license',{key:$('settingsLicenseKey').value.trim()});await refresh();settings();status('License activated')});
 if($('deactivateLicense'))$('deactivateLicense').onclick=safe(async()=>{if(confirm('Deactivate the license on this Mac?')){await api('/api/deactivate-license');await refresh();settings()}});
 if($('copyLicenseKey'))$('copyLicenseKey').onclick=()=>{navigator.clipboard.writeText(state.settings.license_key||'');status('License key copied')};
 if($('resetGeneral'))$('resetGeneral').onclick=safe(async()=>{await api('/api/reset-general');await refresh();settings()});
 if($('resetAll'))$('resetAll').onclick=safe(async()=>{if(confirm('Reset settings? Images, API keys and model files will remain.')){await api('/api/reset-settings',{confirmed:true});await refresh();settings()}});
 if($('emptyCache'))$('emptyCache').onclick=safe(async()=>{if(confirm('Remove unused cache files? Active work and models will be kept.')){const r=await api('/api/empty-cache',{confirmed:true});await refresh();await settings();status('Removed '+bytes(r.removed))}});
 if($('resetPrompt'))$('resetPrompt').onclick=safe(async()=>{await api('/api/settings',{enhancement_prompt:''});await refresh();$('prompt').value=state.prompt;status('')});
 if(section==='AI & APIs')for(const p of ['openai','gemini','seedream']){
  const keyField=$(p+'-key'),saveButton=$(p+'-save');let saved=!!state.settings[p+'_connected'],generation=0,timer,processing=false;
  const setSaved=value=>{saveButton.textContent=value?'Saved':'Save';saveButton.classList.toggle('saved',value);saveButton.disabled=value||processing};
  const connection=loading=>{const el=$(p+'-status');el.replaceChildren(document.createTextNode(loading||(providerVerified[p]?'Connected':'Not Connected')));const dot=document.createElement('span');dot.className=loading?'apiSpinner':'apiStatusDot '+(providerVerified[p]?'connected':'disconnected');dot.setAttribute('aria-hidden','true');el.append(dot)};
  const fill=models=>{const el=$(p+'-model'),current=state.settings[p+'_model'];const choices=[...new Set([...models,current].filter(Boolean))];el.replaceChildren(...choices.map(id=>new Option(id,id)),new Option('Custom…','__custom__'));el.value=current;$(p+'-custom-model').hidden=true};fill(state.provider_models?.[p]||[state.settings[p+'_model']]);
  setSaved(saved);connection();
  keyField.oninput=()=>{const version=++generation;clearTimeout(timer);setSaved(false);if(!keyField.value.trim()){setSaved(saved);return}timer=setTimeout(safe(async()=>{const r=await api('/api/credentials-match',{provider:p,key:keyField.value});if(version===generation)setSaved(r.matches)}),300)};
  const saveModel=safe(async value=>{value=value.trim();await api('/api/settings',{[p+'_model']:value});state.settings[p+'_model']=value;status('')});
  $(p+'-model').onchange=safe(async()=>{const value=$(p+'-model').value,custom=$(p+'-custom-model');custom.hidden=value!=='__custom__';if(value==='__custom__'){custom.value='';custom.focus()}else await saveModel(value)});
  $(p+'-custom-model').onchange=safe(async()=>{await saveModel($(p+'-custom-model').value)});
  saveButton.onclick=safe(async()=>{const entered=keyField.value;processing=true;saveButton.disabled=true;try{await api('/api/credentials',{provider:p,key:entered});saved=true;state.settings[p+'_connected']=true;providerVerified[p]=false;connection();generation++;clearTimeout(timer);if(keyField.value===entered){keyField.value='';keyField.placeholder='Key saved · Enter a key to replace';processing=false;setSaved(true)}else{processing=false;keyField.oninput()}status('')}finally{processing=false;if(saveButton.textContent!=='Saved')saveButton.disabled=false}});
  const discover=label=>safe(async()=>{connection(label);$(p+'-test').disabled=$(p+'-refresh').disabled=true;try{const r=await api('/api/provider-models',{provider:p});providerVerified[p]=r.ok===true;fill(r.models||[]);status(r.ok?'':r.status||'Connection could not be verified')}catch(e){providerVerified[p]=false;throw e}finally{connection();$(p+'-test').disabled=$(p+'-refresh').disabled=false}});
  $(p+'-test').onclick=discover('Testing...');$(p+'-refresh').onclick=discover('Refreshing...');
  $(p+'-remove').onclick=safe(async()=>{if(confirm('Remove this provider’s saved API key?')){generation++;clearTimeout(timer);await api('/api/credentials',{provider:p,remove:true});saved=false;state.settings[p+'_connected']=false;providerVerified[p]=false;keyField.value='';keyField.placeholder='Enter API key';setSaved(false);connection();status('')}});
 }
 if(section==='Toolbar & Apps')document.querySelectorAll('[data-app]').forEach(el=>el.onchange=safe(async()=>{await api('/api/settings',{toolbar_apps:[...document.querySelectorAll('[data-app]:checked')].map(x=>x.dataset.app)});status('Toolbar saved')}));
 if(section==='Presets & Models'){
  $('resetPresets').onclick=safe(async()=>{if(confirm('Reset the six built-in presets and their default guides? Custom presets remain.')){await api('/api/reset-presets',{confirmed:true});await refresh();settings()}});
  for(const op of ['Create','Rename','Edit','Duplicate','Delete'])$('preset'+op).onclick=safe(async()=>{const id=$('presetList').value,p=state.presets[id];if(op==='Delete'){if(confirm('Delete this custom preset?'))await api('/api/preset-manage',{id,operation:'delete'})}else if(op==='Edit'||op==='Create'){const r=await api('/api/window',{kind:'preset',payload:{operation:op.toLowerCase(),id:op==='Edit'?id:''}});if(r.url)window.open(r.url)}else{const name=prompt('Preset name',op==='Duplicate'?p.label+' Copy':p.label);if(name)await api('/api/preset-manage',{id,operation:op.toLowerCase(),name})}await refresh();settings()});
  $('exportPreferences').onclick=safe(async()=>downloadDocument((await api('/api/preferences-export')).document));$('importPreferences').onclick=()=>importFile(safe(async doc=>{if(confirm('Replace your preferences with this file? API keys remain unchanged.')){await api('/api/preferences-import',{document:doc,confirmed:true});await refresh();settings()}}));
  $('exportPresets').onclick=safe(async()=>downloadDocument((await api('/api/output-presets-export',{preview:true})).document));$('importPresets').onclick=()=>importFile(safe(async doc=>{const r=await api('/api/output-presets-preview',{document:doc});if(confirm('Import '+r.entries.length+' presets? Existing custom presets with matching names will be replaced.')){await api('/api/output-presets-import',{document:doc,replace_existing:r.entries.map(e=>e.existing_id).filter(Boolean)});await refresh();settings()}}));
  document.querySelectorAll('[data-model-engine]').forEach(button=>button.onclick=safe(async()=>{
   const engine=button.dataset.modelEngine;
   if(button.dataset.external==='true'){if(!confirm('Disconnect this external model? Its files will be kept.'))return;await api('/api/disconnect-model',{engine,confirmed:true});await refresh();await settings();return;}
   if(button.dataset.installed==='true'){
    if(!confirm('Uninstall '+engine.toUpperCase()+'? You can install it again here.'))return;
    await api('/api/remove-model',{engine,name:'EDSR_x2.pb',confirmed:true});await refresh();await settings();return;
   }
   if(engine==='flowsr'&&!confirm('FlowSR is licensed for noncommercial use only. Install for noncommercial evaluation?'))return;
   const result=await api('/api/install-model',{engine,noncommercial_confirmed:engine==='flowsr'});button.disabled=true;button.textContent='Installing…';
   const monitor=async()=>{await refresh();const job=state.jobs.find(j=>j.id===result.job);if(!job)throw Error('Installation status unavailable');if(job.status==='running'){if(button.isConnected)button.title=job.message;setTimeout(()=>safe(monitor)(),700);return}if(section==='Presets & Models')await settings();if(job.status!=='done')status(job.message,true)};
   await monitor();
  }));
 }
}
function bytes(n){return n>1024**3?(n/1024**3).toFixed(2)+' GB':(n/1024**2).toFixed(1)+' MB'}
async function updatesDialog(){
 const header=`<p>Clarette ${esc(state.version)} · Build ${esc(state.build)}</p>`;
 $('content').innerHTML=header+'<p id="updateStatus">Checking for updates…</p>'+`<div class="buttons">${button('cancel','Close')}</div>`;
 $('cancel').onclick=closeDialogWindow;
 let result;
 try{result=await api('/api/check-updates')}catch(e){$('updateStatus').textContent=e.message;return}
 if(result.error){$('updateStatus').textContent=result.error;return}
 if(!result.available){$('updateStatus').textContent=result.message||"You're up to date.";return}
 $('content').innerHTML=header+`<p>Clarette ${esc(result.version)} is available.</p>`+(result.notes?`<p class="hint">${esc(result.notes).slice(0,500)}</p>`:'')+`<div class="buttons">${button('cancel','Not Now')}${button('install','Update Now',true)}</div>`;
 $('cancel').onclick=closeDialogWindow;
 $('install').onclick=safe(async()=>{
  if(!result.asset_url){status('This release has no downloadable build attached.',true);return}
  $('install').disabled=true;$('install').textContent='Starting…';
  const r=await api('/api/apply-update',{asset_url:result.asset_url,asset_name:result.asset_name});
  const monitor=async()=>{
   await refresh();
   const job=state.jobs.find(j=>j.id===r.job);
   if(!job){status('Update status unavailable',true);return}
   if(job.status==='running'){$('install').textContent=job.message;setTimeout(()=>safe(monitor)(),600);return}
   if(job.status!=='done'){status(job.message,true);$('install').disabled=false;$('install').textContent='Update Now';return}
   $('content').innerHTML='<p>Installing the update. Clarette will quit and reopen automatically.</p>';
  };
  await monitor();
 });
}
async function dialog(){
 document.body.classList.add('compactWindow');document.body.dataset.kind=kind;const batch=state.batches[state.active];$('title').textContent={'new-batch':'New Batch','rename-batch':'Rename Batch','export':'Export Finals','preset':'Output Preset','workspace':'Workspace','updates':'Check for Updates'}[kind]||kind;
 if(kind==='updates'){await updatesDialog();return}
 let html='';
 if(kind==='new-batch'||kind==='rename-batch')html=`<label class="column">Batch Name<input id="name" class="field" value="${esc(kind==='rename-batch'?batch?.name:'CLA_'+new Date().toLocaleDateString('sv-SE'))}"></label>`+(kind==='new-batch'?`<p>Save To</p><div class="row"><input id="destination" value="${esc(state.settings.final_folder)}">${button('choose','Choose…')}</div>`:'');
 if(kind==='export')html=batch?`<p>${batch.files.length} images · ${esc(batch.name)}</p><p class="path">${esc((batch.output_folder||state.settings.final_folder)+'/'+batch.subfolder)}</p><label>Format<select id="format"><option value="default">Use Settings defaults</option><option>PNG</option><option>JPEG</option><option>TIFF</option></select></label><label>Color Mode<select id="exportColorMode"><option value="RGB" ${batch.color_mode!=='CMYK'?'selected':''}>RGB</option><option value="CMYK" ${batch.color_mode==='CMYK'?'selected':''}>CMYK</option></select></label><label>Apply pending color and masks<input type="checkbox" id="apply" checked></label><label>Flatten transparency onto white<input type="checkbox" id="flatten"></label><label>Replace existing files<input type="checkbox" id="overwrite"></label><p class="hint">JPEG/CMYK canvas margins use white for opaque photos. Source transparency and cutouts require explicit flattening. PNG requires RGB. Each item reports its own export errors.</p>`:'<p>Create a batch and add images first.</p>';
 if(kind==='preset'){const p=state.presets[query.get('id')]||batch?.canvas||{width:2048,height:1024,dpi:72};html=`<label>Preset Name<input id="name" value="${esc(query.get('id')?p.label:'')}"></label>`+['width','height','dpi'].map(k=>`<label>${k==='dpi'?'DPI':k[0].toUpperCase()+k.slice(1)}<input id="${k}" type="number" value="${p[k]}"></label>`).join('');}
 if(kind==='workspace'){const ws=state.workspace2||{active:'landscape',custom:{}};html=`<label>Workspace Name<input id="name" value="${esc(ws.custom[ws.active]?.name||'')}"></label><p class="hint">Renames the current saved workspace.</p>`;}
 $('content').innerHTML=html+`<div class="buttons">${button('cancel','Cancel')}${button('submit',kind==='export'?'Export':kind==='new-batch'?'OK':'Save',true)}</div>`;$('cancel').onclick=closeDialogWindow;
 if($('choose'))$('choose').onclick=safe(async()=>{const r=await api('/api/choose-path',{kind:'folder'});if(r.path)$('destination').value=r.path});
 if($('submit'))$('submit').onclick=safe(async()=>{
  if(kind==='new-batch')await api('/api/new-batch',{name:$('name').value,output:$('destination').value});
  if(kind==='rename-batch')await api('/api/rename-batch',{name:$('name').value});
  if(kind==='export'){if(!batch)throw Error('No active batch');await api('/api/color-mode',{mode:$('exportColorMode').value});await api('/api/export',{format:$('format').value,apply_all:$('apply').checked,flatten:$('flatten').checked,overwrite:$('overwrite').checked});}
  if(kind==='preset'){const p={label:$('name').value,width:+$('width').value,height:+$('height').value,dpi:+$('dpi').value,headW:.255,headTop:.035};await api('/api/preset-manage',{operation:query.get('operation')==='edit'?'edit':'create',id:query.get('id'),preset:p});}
  if(kind==='workspace')await api('/api/workspace',{operation:'rename',name:$('name').value});
  await closeDialogWindow();
 });
}
function shortcutDisplay(key){
 const names={Meta:'⌘',Control:'⌃',Alt:'⌥',Shift:'⇧',Backspace:'⌫',Delete:'⌦',Enter:'↩',Escape:'⎋',Home:'↖',End:'↘',ArrowLeft:'←',ArrowRight:'→',ArrowUp:'↑',ArrowDown:'↓',Tab:'⇥',Wheel:'Scroll', ' ':'Space'};
 if(!key)return '—';const parts=key.split('+');return ['Control','Alt','Shift','Meta'].filter(k=>parts.includes(k)).map(k=>names[k]).join('')+parts.filter(k=>!['Control','Alt','Shift','Meta'].includes(k)).map(k=>names[k]||k.toUpperCase()).join('');
}
async function shortcuts(){
 $('title').textContent='Keyboard Shortcuts';
 const values={...state.shortcut_defaults,...state.shortcuts};
 const groups=[['File & Batches',['new-batch','close-batch','import','import-zip','clear','rename-batch','batch-folder','working','final','export']],['Editing',['undo','redo','crop','auto-fit','auto-color','enhance']],['Preview & Tools',['brush','erase','move','lasso','lock','guides','rotate','transparency','fit','compare','preview-color','rotate-left','rotate-right','reset-rotation','brush-size','rotate-wheel']],['Workspace',['fullscreen','workspace-landscape','workspace-portrait','workspace-new','workspace-rename','workspace-delete','workspace-save','workspace-lock','workspace-reset','workspace-restore-default']],['Apps & Settings',['settings','shortcuts','prompt','chatgpt','gemini','photoshop','affinity','photos','help','feedback']]];
 const labels={'new-batch':'New Batch','close-batch':'Close Batch',import:'Add Images','import-zip':'Import ZIP',clear:'Clear Images','rename-batch':'Rename Batch','batch-folder':'Change Output Folder',working:'Open Working Folder',final:'Reveal Final Output',export:'Export Finals',undo:'Undo',redo:'Redo',crop:'Crop','auto-fit':'Auto Fit to Guide','auto-color':'Auto Color',enhance:'Enhance Portrait',brush:'Brush',erase:'Erase',move:'Move',lasso:'Lasso',lock:'Lock Position',guides:'Show Guides',rotate:'Rotate',transparency:'Toggle Transparency',fit:'Fit Output',compare:'View Original','preview-color':'Preview Color','rotate-left':'Rotate Left','rotate-right':'Rotate Right','reset-rotation':'Reset Rotation','brush-size':'Adjust Brush Size','rotate-wheel':'Rotate with Scroll',fullscreen:'Full Screen','workspace-landscape':'Landscape Mode','workspace-portrait':'Portrait Mode','workspace-new':'New Workspace','workspace-rename':'Rename Workspace','workspace-delete':'Delete Workspace','workspace-save':'Save Workspace Layout','workspace-lock':'Drag Panels','workspace-reset':'Reset Current Workspace','workspace-restore-default':'Restore Default Layout',settings:'Settings',shortcuts:'Keyboard Shortcuts',prompt:'Copy Enhancement Prompt',chatgpt:'Open ChatGPT',gemini:'Open Gemini',photoshop:'Open Photoshop',affinity:'Open Affinity',photos:'Open Photos',help:'Help',feedback:'Send Feedback'};
 $('content').classList.add('shortcutPage');
 $('content').innerHTML='<div class="shortcutToolbar"><input id="search" placeholder="Search commands" aria-label="Search shortcuts"><button id="resetShortcuts">Restore Defaults</button></div><div class="shortcutColumns" aria-hidden="true"><span>Command</span><span>Shortcut</span></div><div id="shortcutGroups"></div>';
 const render=()=>{
  $('shortcutGroups').replaceChildren();const search=$('search').value.trim().toLowerCase();
  for(const [name,ids] of groups){
   const matches=ids.filter(id=>labels[id].toLowerCase().includes(search)||name.toLowerCase().includes(search));if(!matches.length)continue;
   const group=document.createElement('details');group.className='shortcutGroup';group.open=true;
   const summary=document.createElement('summary');summary.textContent=name;group.append(summary);
   for(const id of matches){
    const row=document.createElement('label');row.className='shortcutRow';row.innerHTML=`<span>${esc(labels[id])}</span><input readonly aria-label="Shortcut for ${esc(labels[id])}" value="${esc(shortcutDisplay(values[id]))}" title="Press keys to change · Delete to clear · Escape to cancel">`;
    const field=row.querySelector('input');
    const save=safe(async key=>{try{await api('/api/shortcuts',{shortcuts:{...values,[id]:key}});values[id]=key;state.shortcuts={...values};status('')}finally{field.value=shortcutDisplay(values[id])}});
    field.onfocus=()=>{field.value='Press keys…';field.classList.add('recording')};
    field.onblur=()=>{field.value=shortcutDisplay(values[id]);field.classList.remove('recording')};
    field.onkeydown=e=>{
     if(e.key==='Tab')return;e.preventDefault();
     if(e.key==='Escape'){field.blur();return}
     if(['Meta','Control','Shift','Alt'].includes(e.key))return;
     if(['Backspace','Delete'].includes(e.key)&&!e.metaKey&&!e.ctrlKey&&!e.altKey&&!e.shiftKey){save('');return}
     const parts=[];if(e.metaKey||e.ctrlKey)parts.push('Meta');if(e.altKey)parts.push('Alt');if(e.shiftKey)parts.push('Shift');parts.push(e.key.length===1?e.key.toLowerCase():e.key);save(parts.join('+'));
    };
    field.addEventListener('pointerdown',e=>{if(e.button!==1)return;e.preventDefault();save([e.metaKey||e.ctrlKey?'Meta':'',e.altKey?'Alt':'',e.shiftKey?'Shift':'','MMB'].filter(Boolean).join('+'))});
    field.addEventListener('wheel',e=>{if(document.activeElement!==field)return;e.preventDefault();save([e.metaKey||e.ctrlKey?'Meta':'',e.altKey?'Alt':'',e.shiftKey?'Shift':'','Wheel'].filter(Boolean).join('+'))},{passive:false});
    group.append(row);
   }
   $('shortcutGroups').append(group);
  }
  if(!$('shortcutGroups').children.length)$('shortcutGroups').textContent='No matching commands';
 };
 $('search').oninput=render;render();
 $('resetShortcuts').onclick=safe(async()=>{if(confirm('Restore all default keyboard shortcuts?')){await api('/api/shortcuts',{shortcuts:{}});await refresh();shortcuts()}});
}
function helpContent(){
 const workspaceSvg=`<svg viewBox="0 0 700 210" role="img" aria-label="Workspace layout: toolbar across the top, Portraits panel on the left, Preview in the center, Adjustments on the right" style="width:100%;height:auto">
  <rect x="1" y="1" width="698" height="32" rx="6" fill="#2a2c38" stroke="#454759"/>
  <text x="350" y="21" text-anchor="middle" fill="#c9c3de" font-size="12">Toolbar — Export · AI tools · Settings</text>
  <rect x="1" y="43" width="150" height="150" rx="8" fill="#23252c" stroke="#454759"/>
  <text x="76" y="67" text-anchor="middle" fill="#e7e3f5" font-size="13" font-weight="600">Portraits</text>
  <text x="76" y="85" text-anchor="middle" fill="#9a95ad" font-size="10">Batch &amp; thumbnails</text>
  <rect x="163" y="43" width="374" height="150" rx="8" fill="#1c1e26" stroke="#454759"/>
  <text x="350" y="67" text-anchor="middle" fill="#e7e3f5" font-size="13" font-weight="600">Preview</text>
  <text x="350" y="85" text-anchor="middle" fill="#9a95ad" font-size="10">Canvas, brushes, notifications</text>
  <rect x="549" y="43" width="150" height="150" rx="8" fill="#23252c" stroke="#454759"/>
  <text x="624" y="67" text-anchor="middle" fill="#e7e3f5" font-size="13" font-weight="600">Adjustments</text>
  <text x="624" y="85" text-anchor="middle" fill="#9a95ad" font-size="10">Output, color, detail, mask tabs</text>
 </svg>`;
 const workflowSvg=`<svg viewBox="0 0 700 84" role="img" aria-label="Basic workflow: import, frame and color, enhance and mask, then export" style="width:100%;height:auto">
  <g fill="none" stroke="#635a78" stroke-width="2"><line x1="52" y1="28" x2="178" y2="28"/><line x1="232" y1="28" x2="358" y2="28"/><line x1="412" y1="28" x2="538" y2="28"/></g>
  <g font-size="12" text-anchor="middle">
   <circle cx="28" cy="28" r="22" fill="#ae91f2"/><text x="28" y="33" fill="#181423" font-weight="700">1</text><text x="28" y="70" fill="#c9c3de">Import</text>
   <circle cx="205" cy="28" r="22" fill="#ae91f2"/><text x="205" y="33" fill="#181423" font-weight="700">2</text><text x="205" y="70" fill="#c9c3de">Frame &amp; color</text>
   <circle cx="385" cy="28" r="22" fill="#ae91f2"/><text x="385" y="33" fill="#181423" font-weight="700">3</text><text x="385" y="70" fill="#c9c3de">Enhance &amp; mask</text>
   <circle cx="562" cy="28" r="22" fill="#ae91f2"/><text x="562" y="33" fill="#181423" font-weight="700">4</text><text x="562" y="70" fill="#c9c3de">Export</text>
  </g>
 </svg>`;
 const tiersSvg=`<svg viewBox="0 0 700 134" role="img" aria-label="Enhance engine tiers: fast local engines, the quality default, and experimental engines that need extra setup" style="width:100%;height:auto">
  <rect x="1" y="5" width="698" height="34" rx="8" fill="#1c3a2a" stroke="#2f6a4a"/><text x="16" y="27" fill="#bdf0d3" font-size="12" font-weight="600">Fast — Classical, EDSR</text><text x="684" y="27" text-anchor="end" fill="#8fd4ab" font-size="11">Light touch-ups</text>
  <rect x="1" y="49" width="698" height="34" rx="8" fill="#2a2440" stroke="#5b4a8a"/><text x="16" y="71" fill="#ddd2ff" font-size="12" font-weight="600">Quality — Clarette Restore (default)</text><text x="684" y="71" text-anchor="end" fill="#b6a4f5" font-size="11">Best for old or low-res photos</text>
  <rect x="1" y="93" width="698" height="34" rx="8" fill="#3a2a2a" stroke="#7a4a4a"/><text x="16" y="115" fill="#f5cccc" font-size="12" font-weight="600">Experimental — HYPIR, OSEDiff, FlowSR, SeeSR</text><text x="684" y="115" text-anchor="end" fill="#e0a0a0" font-size="11">Needs separate setup</text>
 </svg>`;
 const dot=(color,label)=>`<span style="color:${color};font-size:15px">●</span> ${label}`;
 return `<section><p>Clarette frames, colors, enhances and cuts out headshots — from a single portrait to a full batch.</p></section>
<section><h2>Your workspace</h2>${workspaceSvg}<p class="hint">Portraits: batch and thumbnails. Preview: canvas, brush tools, comparisons, and where progress/notifications appear. Output, Color, and Detail &amp; Mask are their own dockable panels (shown here as tabs in one group). Drag a panel by its grip handle to move it, drop on an edge to split the workspace, or drop in the center to combine panels into tabs. Layout presets and Drag Panels are under Workspace &amp; Preview in Settings and in the Workspace menu.</p></section>
<section><h2>Basic workflow</h2>${workflowSvg}<ol><li>Create a batch and import images or a ZIP. Your source files are never modified.</li><li>Auto Fit or Head Box to frame the shot, then adjust Color and click Apply Color.</li><li>Enhance detail if needed, then Detect Subject and refine the cutout (hair, edges, faces).</li><li>Review with Compare, then Export to your chosen folder.</li></ol></section>
<section><h2>Choosing an enhance engine</h2>${tiersSvg}<p class="hint">Detail-only sharpening never invents texture. Clarette Restore reconstructs real detail (skin, hair, clothing) rather than just sharpening — that's the difference to look for on an old or low-resolution photo. The experimental engines are optional and each need extra setup in Presets &amp; Models before they'll run.</p></section>
<section><h2>Masking &amp; faces</h2><p><b>Detect Subject</b> finds the person; brush Keep/Remove to correct it by hand. <b>Refine hair &amp; remove color fringes</b> (Mask section) and the separate <b>Refine Edges…</b> dialog do real edge-level hair matting, not a blur. <b>Restore faces</b> (Detail section) runs a dedicated face-restoration pass after Enhance — it's a generative model, so always review the result before exporting.</p></section>
<section><h2>Selective color &amp; the Eyedropper</h2><p>Hue, Saturation and Lightness normally edit <b>Master</b> — every color at once. Click one of the six range swatches (Red, Yellow, Green, Cyan, Blue, Magenta) first to edit just that range instead; the selected swatch shows a lilac ring.</p><p>The <b>Eyedropper</b> (next to the range swatches) picks a range by sampling the image instead of guessing which swatch to click:</p><ul><li>Click the Eyedropper icon to turn it on — the pointer becomes an eyedropper, and a small color-preview loupe appears near the upper-right of the pointer as you move it over Preview, showing the color about to be sampled.</li><li>Click anywhere on Preview to sample that pixel. A ring briefly marks exactly where you clicked (an on-screen guide only — it's never part of an export or the mask), and the closest matching range is selected automatically (or Master, if the color is too gray/neutral to belong to any one hue).</li><li>Hue, Saturation and Lightness stay fully editable right away — adjust them to shift or intensify just that sampled color, and the change previews live. Click Preview again to sample a different area at any time; the Eyedropper stays on until you turn it off.</li><li><b>⌘/Ctrl-click</b> instead adds a second reference mark on the Hue spectrum for comparison, without changing which range is selected.</li><li>Turn the Eyedropper off by pressing <b>Escape</b> or clicking its icon again. Every other tool (Brush, Erase, Move, Crop, Lasso, Mask editing, Zoom, Pan, Hold-to-View Original) is unaffected and works normally as soon as it's off — or even while it's on, since the Eyedropper only responds to clicks on Preview itself.</li></ul><p class="hint">The Color tab has two separate Reset controls: the one beside RGB/Preview/Auto Color at the top of Curves resets <i>everything</i> in the tab (curves, white balance, tint, exposure, shadows, highlights, and every Hue/Saturation range). The small round Reset beside the range swatches only clears Hue/Saturation/Lightness — Master's and every named range's, including anything picked with the Eyedropper — leaving curves, white balance, tint, shadows, highlights, and exposure exactly as they were.</p></section>
<section><h2>Portrait status colors</h2><p class="stageLegend">${dot('#529aff','Original')} &nbsp; ${dot('#ffda65','Editing')} &nbsp; ${dot('#ff6e87','Masking')} &nbsp; ${dot('#ffae64','Cutout')} &nbsp; ${dot('#60e594','Saved')}</p></section>
<section><h2>Handy shortcuts</h2><p><b>B</b> Brush · <b>E</b> Erase · <b>V</b> Move · <b>⌘ +</b> / <b>⌘ −</b> brush size. Scroll over any slider or number field to nudge its value. Hover a portrait thumbnail and press <b>Delete</b> to remove it. See Keyboard Shortcuts in Settings for the full list.</p></section>
<section><p class="hint">Clarette ${esc(state.version)} · Build ${esc(state.build)}</p></section>`;
}
async function start(){await refresh();$('releaseLabel').textContent=`CLARETTE ${state.version} · BUILD ${state.build}`;if(kind==='settings')return settings();if(kind==='shortcuts'){section='Keyboard Shortcuts';return settings();}if(kind==='help'){$('title').textContent='Documentation & Tutorials';$('content').innerHTML=helpContent();return}return dialog()}
start().then(()=>{
 if(['settings','shortcuts','help'].includes(kind)||!state.native)return;
 let last=0;
 const fit=()=>{const main=document.querySelector('main'),header=main.querySelector('header'),content=$('content'),notice=$('status'),style=getComputedStyle(main);
 const outer=e=>{const s=getComputedStyle(e);if(s.display==='none')return 0;return e.getBoundingClientRect().height+parseFloat(s.marginTop)+parseFloat(s.marginBottom)};
 const height=Math.min(screen.availHeight-80,Math.ceil(outer(header)+outer(content)+(notice.textContent?outer(notice):0)+parseFloat(style.paddingTop)+parseFloat(style.paddingBottom)+4));
 if(Math.abs(height-last)>2){last=height;api('/api/window-fit',{kind,height}).catch(()=>{})}};
 new ResizeObserver(fit).observe($('content'));new MutationObserver(fit).observe($('status'),{childList:true,subtree:true});requestAnimationFrame(fit);
}).catch(e=>status(e.message,true));

// The native red close button (native.py) is the only close control now --
// no custom in-page one, and the in-page header is hidden (window.css):
// it was only ever a stand-in title bar for the old fully-custom frameless
// window, and its CSS cursor:move looked draggable without actually being
// draggable on this platform, which is exactly the confusing bit removed.
