function refIcon(id,name,label,only=false){const target=el(id);target.innerHTML=phosphor[name]+(only?'':'<span>'+label+'</span>');target.title=label;target.setAttribute('aria-label',label)}
for(const [id,asset,label] of [['chatgpt','openai','ChatGPT'],['gemini','gemini','Gemini'],['photoshop','photoshop','Photoshop']]){el(id).innerHTML=`<img class="providerIcon ${asset}" src="assets/${asset}.svg" alt=""><span>${label}</span>`}
refIcon('copyPrompt','copy','Prompt');refIcon('help','question','Help');refIcon('settings','gear','Settings');
refIcon('crop','crop','Crop',true);const order=['keep','remove','move'];for(const mode of order){const b=el('brushTools').querySelector(`[data-brush="${mode}"]`);el('brushTools').append(b);b.innerHTML=phosphor[{keep:'paint-brush',remove:'eraser',move:'arrows-out-cardinal'}[mode]]}
const refineButton=el('brushTools').querySelector('[data-brush="refine"]');refineButton.hidden=true;
refIcon('importBtn','images','Add images');refIcon('clearPortraits','broom','Clear');refIcon('applyCutouts','squares-four','Apply to All…');el('applyCutouts').classList.add('primary');
refIcon('autoFit','sliders-horizontal','Auto Fit to Guide');refIcon('headBox','selection','Manual Fit');refIcon('before','eye','Hold for original');refIcon('cutoutToggle','checkerboard','Cutout preview');
refIcon('openFinal','folder','Open final folder',true);refIcon('undo','arrow-counter-clockwise','Undo',true);
// Framing belongs at the top of the inspector; all preview controls stay below the canvas.
const inspector=document.querySelector('.inspector');const framing=document.createElement('section');framing.className='framingSection';framing.innerHTML='<div class="sectionTitle"><span>Framing</span></div><div class="two"></div>';framing.querySelector('.two').append(el('autoFit'),el('headBox'));inspector.prepend(framing);
document.querySelector('.inspectorTabs').hidden=true;const oldFit=document.querySelector('.fitControls');oldFit.remove();
// Guide was a child of oldFit: recreate the established checkbox with the same ID.
const guideLabel=document.createElement('label');guideLabel.className='guideToggle check';guideLabel.innerHTML='Guide <input id="guide" type="checkbox" checked role="switch">';
const brushbar=document.querySelector('.brushbar');brushbar.append(el('viewZoom'),guideLabel);el('viewZoom').before(Object.assign(document.createElement('span'),{className:'zoomIcon',innerHTML:phosphor['magnifying-glass-plus']}));
el('brushSize').setAttribute('aria-label','Brush size');el('brushSize').before(Object.assign(document.createElement('button'),{id:'brushMinus',innerHTML:phosphor.minus,title:'Decrease brush size'}));el('brushSize').after(Object.assign(document.createElement('button'),{id:'brushPlus',innerHTML:phosphor.plus,title:'Increase brush size'}));
el('loupeToggle').closest('label').hidden=true;el('loupeToggle').checked=false;el('undo').hidden=false;
// Preview heading and two comparison controls on a single line.
const eh=document.querySelector('.editorHead');eh.querySelector('.fileHeading').hidden=true;eh.querySelector('.pixelInfo').hidden=true;eh.prepend(Object.assign(document.createElement('strong'),{className:'previewHeading',textContent:'Preview'}));eh.append(el('before'),el('cutoutToggle'));document.querySelector('.viewbar').hidden=true;
// Session selection and advanced position controls remain accessible from Settings.
const sessions=document.createElement('section');sessions.innerHTML='<h3>Saved batches</h3>';sessions.append(el('batchSelect'));el('settingsDialog').querySelector('hr').before(sessions);
const advancedPosition=inspector.querySelector('details');advancedPosition.hidden=true;document.body.append(advancedPosition);
// Curves channel selector becomes the compact RGB / R / G / B tab row.
const curveHeader=document.querySelector('.curveHeader');curveHeader.hidden=true;el('curveChannel').hidden=true;
const curveTabs=document.createElement('div');curveTabs.className='curveTabs';curveTabs.innerHTML='<span>Curves</span><div role="tablist" aria-label="Curve channels">'+[['rgb','RGB'],['red','R'],['green','G'],['blue','B']].map(([value,label])=>`<button data-channel="${value}" role="tab" aria-selected="${value==='rgb'}" class="${value==='rgb'?'active':''}">${label}</button>`).join('')+'</div>';document.querySelector('.colorGrid').before(curveTabs);
// Full-width Apply Color, matching the approved panel.
el('colorStatus').hidden=true;el('resetColor').hidden=true;document.querySelector('.advancedColor').append(el('resetColor'));el('resetColor').hidden=false;
// Detail area: upload, scale, strength, enhance action.
el('enhanceDrop').innerHTML=phosphor['upload-simple']+'<span><strong>Drop enhanced image</strong><small>or click to browse</small></span>';
const ds=document.querySelector('.detailSection');const scaleRow=el('upscale').closest('.two');const enhanceAction=el('enhance');scaleRow.before(el('upscale'));scaleRow.remove();ds.querySelector('.sliderRow label').textContent='Strength';ds.querySelector('.sliderRow').after(enhanceAction); // button removed with scaleRow, restore below
// Move rather than duplicate controls retained by the legacy logic.
ds.querySelector('details').prepend(document.querySelector('.cloudControls'));ds.querySelector('.sectionTitle').lastElementChild.hidden=true;
const maskSectionRef=el('detectMask').closest('section');maskSectionRef.className='maskSection';const maskOptions=document.createElement('details');maskOptions.innerHTML='<summary>Mask options & edge refinement</summary>';maskOptions.append(el('detectionProfile'),el('edgeOptions'));maskSectionRef.append(maskOptions);
const outputSection=document.createElement('section');outputSection.className='outputSection';outputSection.innerHTML='<div class="sectionTitle"><span>Output size</span></div><div class="outputDimensions"></div>';maskSectionRef.after(outputSection);outputSection.querySelector('.sectionTitle').after(el('presetSelect'));
for(const [id,label] of [['canvasWidth','Width'],['canvasHeight','Height'],['dpi','DPI']]){const input=el(id);input.setAttribute('aria-label',label);outputSection.querySelector('.outputDimensions').append(input);if(id==='canvasWidth')outputSection.querySelector('.outputDimensions').insertAdjacentHTML('beforeend','<span>×</span>');if(id==='canvasHeight')outputSection.querySelector('.outputDimensions').insertAdjacentHTML('beforeend','<span>px</span>');if(id==='dpi')outputSection.querySelector('.outputDimensions').insertAdjacentHTML('beforeend','<span>dpi</span>')}
// Folder path is the selector: the small folder button at its end opens the chooser.
el('finalFolder').parentElement.firstChild.textContent='Save to ';el('subfolder').parentElement.firstChild.textContent='Folder name ';el('chooseFolder').innerHTML=phosphor.folder;el('chooseFolder').title='Choose output location';el('chooseFolder').setAttribute('aria-label','Choose output location');el('finalFolder').after(el('chooseFolder'));el('saveFinals').textContent='Save final';el('savedCount').hidden=true;

el('brushMinus').setAttribute('aria-label','Decrease brush size');el('brushPlus').setAttribute('aria-label','Increase brush size');
// Secondary controls stay in Settings so the five primary sections fit together.
for(const [selector,title] of [['.advancedColor','Advanced color'],['.detailSection>details','Enhancement engine and options'],['.maskSection>details','Mask model and edge refinement']]){const section=document.querySelector(selector);section.querySelector('summary').textContent=title;section.classList.add('settingsAdvanced');el('settingsDialog').append(section)}

el('viewZoom').querySelector('option[value="fill"]').remove();el('viewZoom').querySelector('option[value="fit"]').textContent='Fit output';el('viewZoom').value='fit';
// canvasSizeBadge lives in .editorHead itself (not nested inside .previewHeading):
// the heading text moves into the tab (see dockview-workspace.js's SOLO_HEADING),
// but the pixel-dimensions line stays in the panel body, wrapping onto its own
// row at the bottom of the header, right above the vertical toolbar/canvas.
document.querySelector('.editorHead').insertAdjacentHTML('beforeend','<small id="canvasSizeBadge"></small>');

const historyTools=document.createElement('div');historyTools.className='historyTools';const redoButton=document.createElement('button');redoButton.id='redo';redoButton.setAttribute('data-mutation','');redoButton.innerHTML=phosphor['arrow-counter-clockwise']+'<span>Redo</span>';redoButton.title='Redo (⌘Y or ⌘⇧Z)';redoButton.setAttribute('aria-label','Redo');el('undo').innerHTML=phosphor['arrow-counter-clockwise']+'<span>Undo</span>';el('undo').title='Undo (⌘Z)';historyTools.append(el('undo'),redoButton);document.querySelector('.editorHead').after(historyTools);
