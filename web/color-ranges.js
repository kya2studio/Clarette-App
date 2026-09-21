// Selective color: a Master range (the existing global Hue/Saturation) plus
// six named ranges the eyedropper or the swatch row can target, each with
// its own Hue/Saturation/Lightness deltas blended in by imaging.py's/
// color-worker.js's shared triangular hue-falloff.
//
// v1.js already pulls Hue/Saturation out of the "More color adjustments"
// <details> into a floating #colorPopover (a nicer take on the same
// disclosure UX) and removes the now-empty <details> outright -- by the
// time this script runs, .advancedColor is gone and Hue/Saturation live in
// that popover instead. This un-collapses them a second time, all the way
// into the always-visible panel instead of a click-to-open popover, since
// they're core to the new selective-color controls, not an aside.
// #colorPopover survives (v1.js also parks its own resetColor button there),
// just without these two rows.
(() => {
'use strict';

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
eyedropper.title = 'Pick a color from Preview to select its range (⌘-click to add another marker)';
eyedropper.setAttribute('aria-label', 'Eyedropper: pick a color range from Preview');
eyedropper.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18.5 2.5a3 3 0 0 1 0 4.24L17 8.24l-4.24-4.24 1.5-1.5a3 3 0 0 1 4.24 0zM11.76 5l4.24 4.24-9.5 9.5-4.5 1 1-4.5z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

const header = document.createElement('div');
header.className = 'selectiveColorHeader';
header.append(swatches, eyedropper);

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

// Exposure and Grain: new global (Master-only, like White balance) adjustments,
// alongside the existing White balance/Shadows/Highlights group layout.js
// already built (Tint no longer lives there -- see above).
const balanceControls = document.querySelector('.balanceControls');
for (const [id, label, max] of [['exposure', 'Exposure', 100], ['grain', 'Grain', 100]]) {
  const row = document.createElement('div');
  row.className = 'sliderRow';
  row.innerHTML = `<label for="${id}">${label}</label><input id="${id}" type="range" min="${id === 'grain' ? 0 : -max}" max="${max}" value="0"><output id="${id}Out">0</output>`;
  balanceControls.append(row);
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
  // The Hue spectrum's own thumb always shows Master's rotation (there's only
  // one physical slider); a selected named range gets a bracket marking
  // where its own hue center sits on that spectrum instead of moving the
  // thumb, since its Hue field edits a *delta*, not an absolute position.
  brackets.replaceChildren();
  if (selectedRange !== 'master') {
    const mark = document.createElement('div');
    mark.className = 'hueBracket';
    mark.style.left = (RANGE_HUE_CENTER[selectedRange] / 360 * 100) + '%';
    brackets.append(mark);
  }
}

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

// Eyedropper: click samples the rendered pixel under the pointer (what the
// user actually sees, including everything already applied), converts to
// HSV, and selects the nearest of the six named ranges (or Master if the
// sample is close to gray/neutral, since no single hue owns a desaturated
// pixel). Plain click replaces the selection; Cmd/Ctrl-click leaves a second
// reference bracket on the spectrum without changing which range is being
// edited, for comparing two sampled colors at once.
let sampling = false;
eyedropper.onclick = () => {
  sampling = !sampling;
  eyedropper.classList.toggle('active', sampling);
  $('mainCanvas').style.cursor = sampling ? 'crosshair' : '';
};
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
$('mainCanvas').addEventListener('pointerdown', (e) => {
  if (!sampling || !current) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  const canvas = $('mainCanvas'), rect = canvas.getBoundingClientRect();
  const x = Math.round((e.clientX - rect.left) * (canvas.width / rect.width));
  const y = Math.round((e.clientY - rect.top) * (canvas.height / rect.height));
  if (x < 0 || y < 0 || x >= canvas.width || y >= canvas.height) return;
  const [r, g, b] = canvas.getContext('2d').getImageData(x, y, 1, 1).data;
  const picked = nearestRange(r / 255, g / 255, b / 255);
  if (e.metaKey || e.ctrlKey) {
    if (picked) {
      const mark = document.createElement('div');
      mark.className = 'hueBracket hueBracketReference';
      mark.style.left = (RANGE_HUE_CENTER[picked] / 360 * 100) + '%';
      brackets.append(mark);
    }
    return;
  }
  selectedRange = picked || 'master';
  syncColorRanges();
  sampling = false;
  eyedropper.classList.remove('active');
  canvas.style.cursor = '';
}, true);

syncColorRanges();
})();
