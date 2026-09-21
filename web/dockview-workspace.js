/* Dockable workspace: turns the six panels (Portraits, Preview, Output Size,
 * Color, Detail, Mask) into real Dockview panels -- drag-to-dock, tabs,
 * resizable splits, layout persistence and presets. Runs last, once every
 * other script has finished building the sections it re-parents.
 * See dockview-theme.css for the Clarette-matched Dockview theme and the
 * per-panel responsive (container-query) rules. */
(() => {
'use strict';
const DV = window['dockview-core'];

const PANEL_TITLES = {
  portraits: 'Portraits', preview: 'Preview',
  outputSize: 'Output', color: 'Color', detailMask: 'Detail & Mask',
};
const PANEL_CONSTRAINTS = {
  // Minimums are the point at which content starts scrolling
  // (.dockPanelBody{overflow:auto}) instead of clipping or overlapping --
  // raised versions of the originals to fit each tab's content without
  // scrolling at typical panel sizes, scroll is just the fallback for
  // anyone who drags a panel narrower/shorter still.
  // Height can't go much above 200: Landscape's own filmstrip preset asks
  // for a *short* 220px-tall Portraits bar (buildPreset() below), and
  // dockview clamps that initialHeight up to whatever minimumHeight is set
  // here -- raising this to comfortably clear the sideways/narrow
  // orientation's fixed-height filmstrip cards (dockview-theme.css's
  // max-aspect-ratio container query) would silently make every Landscape
  // workspace's filmstrip taller than designed. That orientation's actual
  // available height is the whole sidebar's height in practice (never
  // realistically this constrained), and its own overflow-y:auto is the
  // real safety net if it ever is -- scrolling, not clipping.
  portraits: { minimumWidth: 260, minimumHeight: 200 },
  preview: { minimumWidth: 400, minimumHeight: 320 },
  outputSize: { minimumWidth: 280, minimumHeight: 260 },
  color: { minimumWidth: 328, minimumHeight: 420 },
  detailMask: { minimumWidth: 280, minimumHeight: 420 },
};
const PRESET_KEYS = ['landscape', 'portrait'];

// ---- Re-home the existing DOM into Dockview panel bodies -----------------
// Every element below is *moved*, never cloned or recreated: all IDs, classes
// and the listeners layout.js/reference-layout.js/app.js/v1.js/etc. already
// attached to them survive untouched.

const layoutEl = document.querySelector('.layout');
const deliveryEl = document.querySelector('.delivery');
if (deliveryEl) { deliveryEl.hidden = true; document.body.appendChild(deliveryEl); }

const batchEl = document.querySelector('.batch');
const editorEl = document.querySelector('.editor');
batchEl.classList.remove('panel');
editorEl.classList.remove('panel');
batchEl.dataset.panel = 'portraits';
editorEl.dataset.panel = 'preview';

function wrap(id, ...nodes) {
  const div = document.createElement('div');
  div.className = 'dockPanelBody';
  div.dataset.panel = id;
  for (const node of nodes) if (node) div.append(node);
  return div;
}

function divider() {
  const hr = document.createElement('hr');
  hr.className = 'tabDivider';
  return hr;
}

const outputWrap = wrap('outputSize', document.querySelector('.outputSection'), divider(), document.querySelector('.framingSection'));
const colorWrap = wrap('color', document.querySelector('.colorSection'));
// Detail and Mask share one tab (see Settings > Workspace mockups): Detail's
// controls first, a divider, then Mask's -- Mask keeps its own enable
// checkbox and graying (compact-controls.js's syncMaskControls), which key
// off the `.maskSection` class and are unaffected by which dockview panel
// it's wrapped in.
const detailMaskWrap = wrap('detailMask', document.querySelector('.detailSection'), divider(), document.querySelector('.maskSection'));
document.querySelector('.inspector')?.remove();

const PANEL_ELEMENTS = {
  portraits: batchEl, preview: editorEl,
  outputSize: outputWrap, color: colorWrap, detailMask: detailMaskWrap,
};

// Dockview's addPanel()/clear() reparent a panel's content element on a
// deferred frame, not synchronously -- calling addPanel() and then
// immediately checking document.getElementById() on a child of that panel
// proves the element is *not yet* attached to the document at that point.
// Every other script (app.js, editor-tools.js, compact-controls.js, ...)
// looks its controls up by ID assuming they're always in the live document,
// so that gap made every one of those lookups throw during the window
// between a dv.clear() and Dockview's next deferred mount -- on first load
// *and* on every workspace/preset switch. Keeping every panel element
// permanently parented under <body> (hidden) instead of ever fully
// detaching it closes that gap: Dockview just reparents it in and out of
// this staging area, so it's always reachable via getElementById.
function stageAll() {
  for (const el of Object.values(PANEL_ELEMENTS)) {
    el.style.display = 'none';
    document.body.appendChild(el);
  }
}
stageAll();

// ---- Dockview instance -----------------------------------------------

// Every tab leads with a small grip icon -- a visible "this can be dragged"
// affordance, since the tab itself is dockview's native drag handle (no
// custom drag-initiation code needed).
//
// Portraits/Preview are always alone in their group, so a tab there used to
// just repeat "Portraits"/"Preview" right above their own in-content
// heading ("Portraits · N", "Preview 2048x1024...") -- a second header-height
// strip for no new information. Rather than drop the tab back to
// grip-only (which was the previous fix, but wastes that whole strip) or
// hide it again (losing the drag handle, the complaint that led to grip-only
// in the first place), those two headings move *into* the tab itself: one
// header row does both jobs, and the panel body starts right under it.
// Their own elements move (not clones), so app.js's/v1.js's existing
// listeners and the code that keeps them updated on every render
// (`$('batchCount').replaceChildren(...)`, etc.) keep working untouched.
const GRIP_SVG = '<svg class="clarette-tab-grip" viewBox="0 0 10 16" aria-hidden="true"><circle cx="2.5" cy="2.5" r="1.3"/><circle cx="7.5" cy="2.5" r="1.3"/><circle cx="2.5" cy="8" r="1.3"/><circle cx="7.5" cy="8" r="1.3"/><circle cx="2.5" cy="13.5" r="1.3"/><circle cx="7.5" cy="13.5" r="1.3"/></svg>';
const SOLO_HEADING = {
  portraits: () => document.getElementById('batchCount'),
  preview: () => document.querySelector('.previewHeading'),
};
function createTab() {
  const element = document.createElement('div');
  element.className = 'clarette-tab';
  element.insertAdjacentHTML('afterbegin', GRIP_SVG);
  const span = document.createElement('span');
  element.append(span);
  let movedHeading = null;
  return {
    element,
    init(params) {
      const soloHeading = SOLO_HEADING[params.api.id]?.();
      if (soloHeading) {
        element.classList.add('clarette-tab-heading');
        span.remove();
        movedHeading = soloHeading;
        element.append(movedHeading);
      } else {
        span.textContent = params.title || '';
      }
    },
    dispose() {
      // The heading is the live element other scripts keep updating by ID
      // (`$('batchCount').replaceChildren(...)`, etc.) -- a preset rebuild
      // disposes every current tab before the next buildPreset() creates
      // fresh ones, so parking it under <body> (same staging trick as
      // stageAll() below) keeps it connected and findable by the next tab's
      // init() in between, rather than vanishing with this disposed tab.
      if (movedHeading) document.body.appendChild(movedHeading);
    },
  };
}

// Minimize/restore chevron for the tools edge group. group.api.collapse()/
// expand() are dockview's built-in edge-group behavior -- clicking the
// already-active tab already toggles this for free; this button just makes
// it a discoverable, explicit control instead of a hidden tab-click gesture.
// createRightHeaderActionComponent runs for every group, so groups other
// than the tools edge (Portraits, Preview -- which have their header hidden
// entirely anyway) get an empty, non-interactive placeholder.
function createCollapseToggle(group) {
  if (group.api.location.type !== 'edge') {
    return { element: document.createElement('span'), init() {}, dispose() {} };
  }
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'clarette-collapse-toggle';
  button.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const sync = () => {
    const collapsed = group.api.isCollapsed();
    button.classList.toggle('collapsed', collapsed);
    button.setAttribute('aria-label', collapsed ? 'Expand tools' : 'Minimize tools');
    button.title = collapsed ? 'Expand tools' : 'Minimize tools';
  };
  button.onclick = () => { group.api.isCollapsed() ? group.api.expand() : group.api.collapse(); };
  let subscription;
  return {
    element: button,
    init() { sync(); subscription = group.api.onDidCollapsedChange(sync); },
    dispose() { subscription?.dispose(); },
  };
}

const dv = DV.createDockview(layoutEl, {
  // Several existing scripts poll their controls by ID every render cycle
  // regardless of which tab is active (color curves, preset sync, mask
  // toggles, ...); keep every panel's DOM mounted even while its tab isn't
  // the visible one, rather than Dockview's default lazy unmount.
  defaultRenderer: 'always',
  theme: {
    name: 'clarette',
    className: 'dockview-theme-clarette',
    colorScheme: 'dark',
    gap: 8,
    dndOverlayMounting: 'absolute',
    dndPanelOverlay: 'content',
    dndTabIndicator: 'fill',
    dndOverlayBorder: '2px solid var(--dv-active-sash-color)',
  },
  disableFloatingGroups: true,
  // A name has to be supplied here *and* resolved by createTabComponent below --
  // dockview only swaps in a custom tab (ours has no close button, since
  // closing a panel with no way to bring it back is exactly what the user
  // doesn't want) when a name it can resolve is present; without
  // defaultTabComponent every panel silently falls back to Dockview's own
  // built-in tab, close button and all.
  defaultTabComponent: 'clarette',
  createTabComponent: () => createTab(),
  createRightHeaderActionComponent: (group) => createCollapseToggle(group),
  createLeftHeaderActionComponent: (group) => createMoveToggle(group),
  createComponent: (options) => ({
    element: PANEL_ELEMENTS[options.id],
    init() { PANEL_ELEMENTS[options.id].style.display = ''; },
    dispose() {},
  }),
});
window.ClaretteDockview = dv;

let applyingRemote = false;

// ---- Presets ------------------------------------------------------------
// Each preset is built fresh from these declarative steps rather than stored
// as data, so the five built-ins stay protected simply by never being
// persisted (see preferences.WORKSPACE_PRESETS). A live edit while a preset
// is active forks it into a saved custom workspace instead of mutating it.

function addPanel(id, extra) {
  return dv.addPanel(Object.assign({
    id, component: 'section', title: PANEL_TITLES[id],
  }, PANEL_CONSTRAINTS[id], extra));
}

// The tools group docks to a layout edge (a real Dockview "edge group", the
// same primitive VS Code's collapsible sidebars use) rather than living in
// the regular grid. That's what makes minimizing it a single built-in
// group.api.collapse() instead of hand-rolled constraint/size hacking -- and
// it comes with a free bonus: clicking the already-active tab toggles
// collapse/expand on its own, on top of the explicit chevron button added
// via createRightHeaderActionComponent below.
//
// The tradeoff: an edge group is anchored to whichever edge it was created
// on, not freely draggable there the way a regular grid panel is (this is
// also how VS Code's own sidebar works -- moved via a command/setting, not
// by dragging it across the window). "Move to the other side" is therefore
// its own explicit action (the swap-sides button below), not a drag gesture.
const TOOLS_EDGE_ID = 'tools';
let toolsEdgePosition = 'right';

function addToolsEdgeGroup() {
  dv.addEdgeGroup(toolsEdgePosition, { id: TOOLS_EDGE_ID, initialSize: 368, minimumSize: 368 });
  addPanel('outputSize', { position: { referenceGroup: TOOLS_EDGE_ID, direction: 'within' } });
  addPanel('color', { position: { referenceGroup: TOOLS_EDGE_ID, direction: 'within' } });
  addPanel('detailMask', { position: { referenceGroup: TOOLS_EDGE_ID, direction: 'within' } });
}

function buildPreset(key) {
  dv.clear();
  stageAll();
  // dv.clear() empties the grid but does not remove edge groups -- without
  // this, the next addEdgeGroup() throws "edge group already exists at
  // position '...'". Removing *both* positions rather than just the one
  // toolsEdgePosition currently claims is deliberate: if a caller changes
  // toolsEdgePosition before calling buildPreset() (restore-default resets
  // it to 'right' before rebuilding), the group that's actually still
  // registered may be at the *other* position, and the tracked variable is
  // no longer a reliable pointer to it -- removing whichever one(s) really
  // exist avoids ending up with two.
  try { dv.removeEdgeGroup('left'); } catch (e) { /* none registered */ }
  try { dv.removeEdgeGroup('right'); } catch (e) { /* none registered */ }
  if (key === 'landscape') {
    // Portraits as a wide, short filmstrip across the top (see the
    // min-aspect-ratio container query in dockview-theme.css), Preview below it.
    // dockview's initialHeight/initialWidth sizes whichever panel is the *new*
    // split-off group (position.referencePanel is the one already placed) --
    // so Preview goes in first, full-size, and Portraits splits off *from* it
    // with the explicit size; giving the size to Portraits while it was the
    // one being added first (with no position yet to split) had no effect at
    // all, leaving both sides an even 50/50 default instead of this filmstrip.
    addPanel('preview', {});
    addPanel('portraits', { position: { referencePanel: 'preview', direction: 'above' }, initialHeight: 220 });
  } else {
    // 'portrait', and the fallback for anything unrecognised: Portraits as
    // a narrow list on the left, Preview centered -- three columns overall
    // once the tools edge group is added below. Same reasoning as above:
    // Preview first (full width), Portraits splits off to its left with the
    // explicit width.
    addPanel('preview', {});
    addPanel('portraits', { position: { referencePanel: 'preview', direction: 'left' }, initialWidth: 260 });
  }
  addToolsEdgeGroup();
}

// Swap-sides button for the tools edge group: tears it down at its current
// edge and rebuilds it at the other one, keeping Portraits/Preview as they
// are. Registered as a *left* header action so it doesn't collide with the
// collapse chevron's right-header slot.
function moveToolsEdge() {
  try { dv.removeEdgeGroup(toolsEdgePosition); } catch (e) { /* none registered */ }
  toolsEdgePosition = toolsEdgePosition === 'right' ? 'left' : 'right';
  addToolsEdgeGroup();
}
function createMoveToggle(group) {
  if (group.api.location.type !== 'edge') {
    return { element: document.createElement('span'), init() {}, dispose() {} };
  }
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'clarette-move-toggle';
  button.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 3h12M2 8h8M2 13h12M11 5.5 13.5 8 11 10.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  button.title = 'Move to the other side';
  button.setAttribute('aria-label', 'Move tools panel to the other side');
  button.onclick = moveToolsEdge;
  return { element: button, init() {}, dispose() {} };
}

// dockview aggregates panel/group mutations into onDidLayoutChange via its
// own buffered emitter -- so a single addPanel() call's event doesn't arrive
// synchronously, and building a whole preset is several of those calls, plus
// an edge group's own tab-strip ResizeObserver settling its collapsed size
// afterward. Each can land on its own, differently-delayed callback, so
// there's no single fixed delay guaranteed to outlast all of them -- a
// one-shot timer that fires too early sees the *next* one with
// applyingRemote already false and treats it as a real local edit, silently
// forking a new custom workspace (this is where the phantom "Custom Layout"
// entries came from). Instead: every layout-change event that arrives while
// still "settling" extends the quiet window instead of triggering a save;
// only once events actually stop for a whole `settleMs` does the guard lift,
// so a genuinely-user-initiated drag (which keeps the events flowing while
// it's happening) is the only thing that can still end up saving.
let settleTimer = null;
function withRemoteGuard(fn) {
  applyingRemote = true;
  clearTimeout(settleTimer);
  try { fn(); } finally { armSettle(); }
}
function armSettle(settleMs = 400) {
  clearTimeout(settleTimer);
  settleTimer = setTimeout(() => { applyingRemote = false; }, settleMs);
}

// Something visible immediately, before the first /api/state round-trip
// resolves and tells us which workspace was actually saved. Guarded the same
// way a remote-driven layout swap is: constructing the initial panels is
// itself a layout change, and must not auto-fork 'landscape' into a saved
// custom workspace before the real active workspace is even known.
withRemoteGuard(() => buildPreset('landscape'));

// ---- Persistence ----------------------------------------------------
// Local edits debounce-save to the server; server-driven changes (a preset
// picked from the Settings window or native Workspace menu, arriving through
// the existing 1.5s /api/state poll) apply back here. `signature` guards
// both directions against re-triggering each other in a loop.

let signature = '';

function debounce(fn, ms) {
  let timer = null;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

const saveLayout = debounce(guarded(async () => {
  if (applyingRemote) return;
  const layout = dv.toJSON();
  const result = await api('/api/workspace', { operation: 'save', layout });
  signature = JSON.stringify([result.active, !!app?.workspace2?.locked]);
}), 700);

dv.onDidLayoutChange(() => {
  if (applyingRemote) { armSettle(); return; }
  saveLayout();
});

function applyWorkspaceState(ws, force) {
  const next = JSON.stringify([ws.active, !!ws.locked]);
  if (!force && next === signature) return;
  signature = next;
  withRemoteGuard(() => {
    dv.updateOptions({ disableDnd: !!ws.locked });
    layoutEl.classList.toggle('layoutLocked', !!ws.locked);
    if (PRESET_KEYS.includes(ws.active)) {
      buildPreset(ws.active);
      return;
    }
    const custom = ws.custom && ws.custom[ws.active];
    if (!custom) { buildPreset('landscape'); return; }
    stageAll();
    try { const saved=structuredClone(custom.layout);
      for(const edge of Object.values(saved.edgeGroups||{})){if(edge&&typeof edge==='object'){edge.minimumSize=368;if(edge.size)edge.size=Math.max(368,edge.size)}}
      dv.fromJSON(saved);
      for(const panel of dv.panels)if(PANEL_CONSTRAINTS[panel.id])panel.api.setConstraints(PANEL_CONSTRAINTS[panel.id]); }
    catch (e) {
      console.error('Clarette: saved workspace layout could not be restored, falling back to Landscape Mode', e);
      buildPreset('landscape');
    }
  });
}

const previousRenderOutput = renderOutput;
renderOutput = function () {
  previousRenderOutput();
  if (app?.workspace2) applyWorkspaceState(app.workspace2, false);
};

// ---- Workspace commands (native Workspace menu + Settings window) -------

for (const key of PRESET_KEYS) {
  const command = 'workspace-' + key.replace(/[A-Z]/g, m => '-' + m.toLowerCase());
  registerCommand(command, guarded(async () => {
    await api('/api/workspace', { operation: 'select', id: key });
    await refresh();
  }));
}
registerCommand('workspace-save', guarded(async () => {
  const layout = dv.toJSON();
  const result = await api('/api/workspace', { operation: 'save', layout, name: 'Custom Layout' });
  signature = JSON.stringify([result.active, !!app?.workspace2?.locked]);
  await refresh();
  message('Workspace layout saved');
}));
registerCommand('workspace-new', guarded(async () => {
  const layout = dv.toJSON();
  await api('/api/workspace', { operation: 'create', layout, name: 'New Workspace' });
  await refresh();
  message('New workspace created from the current layout');
}));
registerCommand('workspace-rename', () => openNative('workspace', { operation: 'rename' }));
registerCommand('workspace-delete', guarded(async () => {
  if (!confirm('Delete this custom workspace?')) return;
  await api('/api/workspace', { operation: 'delete' });
  await refresh();
}));
registerCommand('workspace-lock', guarded(async () => {
  await api('/api/workspace', { operation: 'lock', locked: !app.workspace2.locked });
  await refresh();
}));
registerCommand('workspace-reset', guarded(async () => {
  if (!confirm('Reset the current workspace layout?')) return;
  await api('/api/workspace', { operation: 'reset' });
  signature = '';
  await refresh();
}));
registerCommand('workspace-restore-default', guarded(async () => {
  // toolsEdgePosition is client-side-only state (a move-to-the-other-side
  // click, not something the saved layout tracks), so a plain preset
  // rebuild wouldn't reset it on its own -- and if the active workspace id
  // isn't actually changing, applyWorkspaceState's signature check would
  // skip rebuilding at all (see 'workspace-reset' above for the same fix).
  toolsEdgePosition = 'right';
  await api('/api/workspace', { operation: 'restore-default' });
  signature = '';
  await refresh();
}));

})();
