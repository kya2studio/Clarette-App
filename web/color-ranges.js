// Selective color: a Master range (the existing global Hue/Saturation) plus
// six named ranges the eyedropper or the swatch row can target, each with
// its own Hue/Saturation/Lightness deltas blended in by imaging.py's/
// color-worker.js's shared triangular hue-falloff.
//
// Hue/Saturation/Tint and the Reset (discard draft) button used to live
// behind a click-to-open "Advanced color" popover -- removed outright
// (see v1.js) once these controls became core, always-visible parts of the
// panel rather than an aside worth hiding. v1.js parks their elements on
// <body> for this script to claim; grabbing them by id works the same
// regardless of which element currently holds them.
(() => {
'use strict';

// Global Reset (neutralColor)/Preview (previewColor)/Auto Color sat in
// their own header strip above .curveTabs's "Curves / RGB R G B" row --
// two separate lines for what's really one logical header, the second of
// which was otherwise empty since its only other content (the "Color"
// section label) is hidden. Moving them into .curveTabs itself, pinned
// right via their own wrapper's margin-left:auto while "Curves" + the
// channel tabs stay put on the left, merges that into the single row the
// panel has width for; the now-empty strip above just collapses away.
const curveTabs = document.querySelector('.curveTabs');
const colorHeaderActions = document.querySelector('.colorHeaderActions');
const curveTabsActions = document.createElement('div');
curveTabsActions.className = 'curveTabsActions';
curveTabsActions.append($('neutralColor'), $('previewColor'), $('autoColor'));
curveTabs.append(curveTabsActions);
colorHeaderActions.hidden = true;

const RANGES = [
  ['master', 'Master', '#8a8a8a'],
  ['red', 'Red', '#e5484d'],
  ['yellow', 'Yellow', '#e6c229'],
  ['green', 'Green', '#46a758'],
  ['cyan', 'Cyan', '#12a4c4'],
  ['blue', 'Blue', '#3b82f6'],
  ['magenta', 'Magenta', '#d6409f'],
];
const RANGE_HUE_CENTER = { red: 0, yellow: 60, green: 120, cyan: 180, blue: 240, magenta: 300 };
let selectedRange = 'master';

const colorSection = document.querySelector('.colorSection');
const hueRow = $('hue').closest('.sliderRow');
const saturationRow = $('saturation').closest('.sliderRow');

const selective = document.createElement('div');
selective.className = 'selectiveColor';

const swatches = document.createElement('div');
swatches.className = 'rangeSwatches';
for (const [id, label, color] of RANGES) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'rangeSwatch';
  b.dataset.range = id;
  b.style.setProperty('--swatch', color);
  b.title = label;
  b.setAttribute('aria-label', label);
  b.onclick = () => { selectedRange = id; syncColorRanges(); };
  swatches.append(b);
}

const eyedropper = document.createElement('button');
eyedropper.type = 'button';
eyedropper.id = 'colorEyedropper';
eyedropper.className = 'eyedropperButton';
eyedropper.title = 'Pick a color from Preview to select its range';
eyedropper.setAttribute('aria-label', 'Eyedropper: pick a color range from Preview');
eyedropper.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18.5 2.5a3 3 0 0 1 0 4.24L17 8.24l-4.24-4.24 1.5-1.5a3 3 0 0 1 4.24 0zM11.76 5l4.24 4.24-9.5 9.5-4.5 1 1-4.5z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

const header = document.createElement('div');
header.className = 'selectiveColorHeader';
// Eyedropper and resetColor are a single tool group -- appended together
// into their own wrapper so justify-content:space-between on the header
// (swatches vs. this group) can't also insert a gap *between the two of
// them*: with 3 direct flex children, space-between spaces every adjacent
// pair equally, which used to shove these two icons apart from each other
// by the same amount as the whole swatch row was shoved from them.
const rangeTools = document.createElement('div');
rangeTools.className = 'rangeTools';
rangeTools.append(eyedropper);
header.append(swatches, rangeTools);
// resetColor (Hue/Saturation Reset) is created and wired up further down,
// then moved into rangeTools next to the Eyedropper -- see below.

hueRow.classList.add('hueSpectrumRow');
// A wrapper around just the input, not a bare extra grid child: .sliderRow's
// 3 columns (label/input/output) are filled by auto-placement in DOM order,
// and a 4th child with its *own* explicit grid-column claims that cell
// before auto-placement runs -- bumping the real input into the output's
// column and wrapping output onto a second row entirely. Wrapping keeps the
// grid at exactly 3 auto-placed items; the overlay positions relative to
// the wrapper instead of fighting the grid for a column.
const hueInput = $('hue');
const hueWrap = document.createElement('div');
hueWrap.className = 'hueInputWrap';
hueInput.replaceWith(hueWrap);
hueWrap.append(hueInput);
const brackets = document.createElement('div');
brackets.className = 'hueBrackets';
hueWrap.append(brackets);

const lightnessRow = document.createElement('div');
lightnessRow.className = 'sliderRow';
lightnessRow.innerHTML = '<label for="lightness">Lightness</label><input id="lightness" type="range" min="-100" max="100" value="0"><output id="lightnessOut">0</output>';

// workflow.js also relocates Tint alongside Hue/Saturation into the same
// .advancedColor/#colorPopover group (out of layout.js's original White
// balance/Tint/Shadows/Highlights row) -- pull it out the same way.
const tintRow = $('tint').closest('.sliderRow');

selective.append(header, swatchLabel(), hueRow, saturationRow, lightnessRow, tintRow);
function swatchLabel() {
  // Purely visual: names the row of range buttons for screen readers/sighted
  // users alike without a redundant "Selective Color" section title (the
  // Color tab's own dockview tab already names this whole panel).
  const p = document.createElement('p');
  p.className = 'rangeSwatchLabel muted';
  p.textContent = 'Applies to:';
  return p;
}
colorSection.append(selective);

// Apply Color commits every pending edit in this panel, curves through
// Tint -- keeping it above the selective-color controls read as "this only
// covers what's above me". Moving .colorActions after .selective puts it
// back at the true bottom, following everything it actually applies.
const colorActions = document.querySelector('.colorActions');
colorSection.append(colorActions);

// resetColor belongs to *this* section specifically, not the panel as a
// whole -- app.js's original handler ("discard draft, revert to last
// applied") reverted every field, duplicating neutralColor/#autoColor's
// row at the top (the real global reset, wired to /api/color-reset
// server-side). Scoping it down to just Hue/Saturation/Lightness --
// Master's and every named range's, plus whichever range is currently
// selected -- is what actually makes it a *different* control instead of
// a second copy of the same one; overridden here (not in app.js) since it
// needs this closure's selectedRange/syncColorRanges to reset the range
// selector state too, not just the numbers. Placed in the header right
// next to the Eyedropper -- both are range-selection tools (one picks a
// range by sampling, this clears it) -- rather than at the bottom next to
// Apply Color, which is about committing the edit, not selecting a range.
const resetColor = $('resetColor');
resetColor.textContent = '';
resetColor.innerHTML = phosphor['arrow-counter-clockwise'];
resetColor.title = 'Reset Hue/Saturation';
resetColor.setAttribute('aria-label', 'Reset Hue/Saturation');
resetColor.classList.add('compactIcon', 'filledIcon');
resetColor.onclick = () => {
  if (!current) return;
  draft.hue = 0;
  draft.saturation = 0;
  draft.lightness = 0;
  draft.color_ranges = {};
  selectedRange = 'master';
  syncColor();
  updatePreview();
  schedule();
};
rangeTools.append(resetColor);

// Exposure and Grain: new global (Master-only, like White balance) adjustments,
// alongside the existing White balance/Shadows/Highlights group layout.js
// already built (Tint no longer lives there -- see above).
const balanceControls = document.querySelector('.balanceControls');
// app.js's own oninput loop (for hue/saturation/shadows/highlights/
// temperature/tint) was written before these two existed, so it never
// wired them -- draft.exposure/draft.grain updated on Auto Color, and
// syncColor() displayed whatever value was already there, but dragging
// either slider by hand did nothing at all: no draft write, no output-
// number update, no live preview, no schedule. Bound the same way here.
for (const [id, label, max] of [['exposure', 'Exposure', 100], ['grain', 'Grain', 100]]) {
  const row = document.createElement('div');
  row.className = 'sliderRow';
  row.innerHTML = `<label for="${id}">${label}</label><input id="${id}" type="range" min="${id === 'grain' ? 0 : -max}" max="${max}" value="0"><output id="${id}Out">0</output>`;
  balanceControls.append(row);
  $(id).oninput = () => { if (!current) return; draft[id] = Number($(id).value); syncColor(); queueLiveColor(); schedule(); };
}

function rangeValues() {
  if (selectedRange === 'master') return { hue: draft.hue || 0, saturation: draft.saturation || 0, lightness: draft.lightness || 0 };
  draft.color_ranges ??= {};
  draft.color_ranges[selectedRange] ??= { hue: 0, saturation: 0, lightness: 0 };
  return draft.color_ranges[selectedRange];
}

function syncColorRanges() {
  const values = rangeValues();
  for (const key of ['hue', 'saturation', 'lightness']) {
    $(key).value = values[key] || 0;
    $(key + 'Out').textContent = values[key] || 0;
  }
  for (const b of swatches.children) b.classList.toggle('active', b.dataset.range === selectedRange);
  drawRange();
}

// Bounds are unwrapped degrees relative to center, so a red range can
// cross 360 without changing marker order or losing its feathered edges.
function rangeGeometry(){const v=rangeValues();return {center:v.center??RANGE_HUE_CENTER[selectedRange], bounds:v.bounds||[-60,0,0,60]};}
function drawRange(){
 brackets.replaceChildren();if(selectedRange==='master')return;
 const {center,bounds}=rangeGeometry();
 function segment(a,b,falloff){
   for(let turn=-2;turn<=2;turn++){
     const start=Math.max(0,center+a+turn*360),end=Math.min(360,center+b+turn*360);if(end<=start)continue;
     const el=document.createElement('span');el.className='hueRangeSegment'+(falloff?' falloff':'');el.style.left=start/3.6+'%';el.style.width=(end-start)/3.6+'%';brackets.append(el);
   }
 }
 segment(bounds[0],bounds[1],true);segment(bounds[1],bounds[2],false);segment(bounds[2],bounds[3],true);
 bounds.forEach((offset,i)=>{
   const el=document.createElement('button');el.type='button';el.className='hueRangeMarker'+(i===0||i===3?' outer':'');el.dataset.marker=i;
   el.title=['Falloff Start','Full Effect Start','Full Effect End','Falloff End'][i];el.setAttribute('aria-label',el.title);el.style.left=((center+offset+360)%360)/3.6+'%';brackets.append(el);
 });
}
let rangeDrag=null;
function updateMarker(i,value){
 const v=rangeValues(),{center,bounds}=rangeGeometry();const next=bounds.slice();
 next[i]=Math.max(i?next[i-1]:-180,Math.min(i<3?next[i+1]:180,value));
 v.center=center;v.bounds=next;drawRange();queueLiveColor();schedule();
}
brackets.addEventListener('pointerdown',e=>{
 const marker=e.target.closest('[data-marker]');if(!marker||!current)return;e.preventDefault();e.stopPropagation();
 const {bounds}=rangeGeometry();rangeDrag={index:+marker.dataset.marker,x:e.clientX,start:bounds[+marker.dataset.marker],width:brackets.clientWidth};brackets.setPointerCapture(e.pointerId);
});
brackets.addEventListener('pointermove',e=>{if(rangeDrag)updateMarker(rangeDrag.index,rangeDrag.start+(e.clientX-rangeDrag.x)*360/rangeDrag.width)});
for(const event of ['pointerup','pointercancel','lostpointercapture'])brackets.addEventListener(event,()=>rangeDrag=null);
brackets.addEventListener('keydown',e=>{const marker=e.target.closest('[data-marker]');if(!marker||!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const i=+marker.dataset.marker;updateMarker(i,rangeGeometry().bounds[i]+(e.key==='ArrowRight'?1:-1));brackets.querySelector(`[data-marker="${i}"]`).focus()});

// hue/saturation/lightness already got a plain flat-field oninput from
// app.js's generic slider loop; a selected named range needs to write into
// draft.color_ranges[name] instead, so these three take over from there.
for (const key of ['hue', 'saturation', 'lightness']) {
  $(key).oninput = () => {
    if (!current) return;
    const values = rangeValues();
    values[key] = Number($(key).value);
    if (selectedRange === 'master') draft[key] = values[key];
    $(key + 'Out').textContent = values[key];
    queueLiveColor();
    schedule();
  };
}

const previousSyncColor = syncColor;
syncColor = function () { previousSyncColor(); syncColorRanges(); };

// Eyedropper (Photoshop-style): click the icon to arm it, then every click
// on Preview samples the rendered pixel under the pointer (what the user
// actually sees, including everything already applied) and selects the
// nearest of the six named ranges (or Master if the sample is close to
// gray/neutral, since no single hue owns a desaturated pixel) -- without
// disarming, so the next click can sample somewhere else right away. Only
// Escape or clicking the icon again exits. Every sample replaces the selected range.
let sampling = false;
const canvas = $('mainCanvas');
const viewport = document.querySelector('.viewport');

// A plain CSS crosshair doesn't read as "this tool samples a color" the
// way Photoshop's eyedropper glyph does -- reusing that same glyph (white
// fill, dark outline so it stays visible on both light and dark image
// content) as a custom cursor, hotspot at its drop-tip, makes the active
// tool obvious without a separate mode indicator anywhere near the canvas.
const EYEDROPPER_CURSOR = 'url("data:image/svg+xml;utf8,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">' +
  '<path d="M18.5 2.5a3 3 0 0 1 0 4.24L17 8.24l-4.24-4.24 1.5-1.5a3 3 0 0 1 4.24 0zM11.76 5l4.24 4.24-9.5 9.5-4.5 1 1-4.5z" ' +
  'fill="#fff" stroke="#000" stroke-width="1.2" stroke-linejoin="round"/></svg>'
) + '") 3 21, crosshair';

// Live color-preview loupe: follows the pointer whenever sampling is armed,
// offset to the upper-right so it never sits directly over the pixel about
// to be sampled. Fixed positioning + a viewport-edge nudge (below) keeps it
// fully visible even with the pointer near a window edge.
const loupe = document.createElement('div');
loupe.className = 'eyedropperLoupe';
loupe.hidden = true;
document.body.append(loupe);

// Sampled-area highlight ring: a plain positioned overlay *inside* .viewport
// (never drawn into #mainCanvas itself), so it can never end up in an
// export or the mask -- it just marks where the last sample was taken,
// until the tool is dismissed or a swatch is picked some other way.
const sampleRing = document.createElement('div');
sampleRing.className = 'eyedropperRing';
sampleRing.hidden = true;
viewport.append(sampleRing);
function hideSampleRing() { sampleRing.hidden = true; }

function startSampling() {
  if (sampling) return;
  sampling = true;
  canvas.dataset.colorSampling='true';
  eyedropper.classList.add('active');
  canvas.style.cursor = EYEDROPPER_CURSOR;
}
function stopSampling() {
  if (!sampling) return;
  sampling = false;
  delete canvas.dataset.colorSampling;
  eyedropper.classList.remove('active');
  canvas.style.cursor = '';
  updateBrushCursor();
  loupe.hidden = true;
  hideSampleRing();
}
eyedropper.onclick = () => sampling ? stopSampling() : startSampling();
document.addEventListener('keydown', e => { if (e.key === 'Escape' && sampling) stopSampling(); });

function samplePixel(clientX, clientY) {
  const rect = canvas.getBoundingClientRect();
  const x = Math.round((clientX - rect.left) * (canvas.width / rect.width));
  const y = Math.round((clientY - rect.top) * (canvas.height / rect.height));
  if (x < 0 || y < 0 || x >= canvas.width || y >= canvas.height) return null;
  const [r, g, b] = canvas.getContext('2d').getImageData(x, y, 1, 1).data;
  return { r, g, b };
}
canvas.addEventListener('pointermove', e => {
  if (!sampling) { return; }
  const px = samplePixel(e.clientX, e.clientY);
  if (!px) { loupe.hidden = true; return; }
  loupe.hidden = false;
  loupe.style.background = `rgb(${px.r}, ${px.g}, ${px.b})`;
  let left = e.clientX + 18, top = e.clientY - 34;
  if (left + 28 > window.innerWidth - 8) left = e.clientX - 46;
  if (top < 8) top = e.clientY + 18;
  loupe.style.left = left + 'px';
  loupe.style.top = top + 'px';
}, true);
canvas.addEventListener('pointerleave', () => { loupe.hidden = true; });

function nearestRange(r, g, b) {
  const max = Math.max(r, g, b), min = Math.min(r, g, b), delta = max - min;
  if (max === 0 || delta / max < 0.12) return null; // too gray/dark to belong to a hue range
  let h = 0;
  if (delta) h = max === r ? ((g - b) / delta) % 6 : max === g ? (b - r) / delta + 2 : (r - g) / delta + 4;
  h = ((h * 60) % 360 + 360) % 360;
  let best = null, bestDist = Infinity;
  for (const [name, center] of Object.entries(RANGE_HUE_CENTER)) {
    const dist = Math.abs(((h - center + 180) % 360 + 360) % 360 - 180);
    if (dist < bestDist) { bestDist = dist; best = name; }
  }
  return best;
}
canvas.addEventListener('pointerdown', (e) => {
  if (!sampling || !current || e.button !== 0) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  const px = samplePixel(e.clientX, e.clientY);
  if (!px) return;
  const picked = nearestRange(px.r / 255, px.g / 255, px.b / 255);
  selectedRange = picked || 'master';
  if(picked){
    const values=rangeValues();
    const max=Math.max(px.r,px.g,px.b), min=Math.min(px.r,px.g,px.b), d=max-min;
    let h=max===px.r?(px.g-px.b)/d:max===px.g?(px.b-px.r)/d+2:(px.r-px.g)/d+4;
    values.center=((h*60)%360+360)%360;
    values.bounds=[-45,-15,15,45];
    queueLiveColor();schedule();
  }
  syncColorRanges();
  const vpRect = viewport.getBoundingClientRect();
  sampleRing.style.left = (e.clientX - vpRect.left) + 'px';
  sampleRing.style.top = (e.clientY - vpRect.top) + 'px';
  sampleRing.hidden = false;
}, true);
// A swatch picked directly (not via sampling) no longer corresponds to
// where the ring is pointing.
swatches.addEventListener('click', hideSampleRing);

syncColorRanges();
})();
