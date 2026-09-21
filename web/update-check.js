// Silent on-launch update prompt. app.py checks GitHub a few seconds after
// startup (packaged build only) and exposes the result as app.pending_update;
// this just asks once per session and, on Yes, starts the same
// /api/apply-update job the "Check for Updates" window's Install button
// uses -- its progress rides the existing job/toast machinery, so there's
// nothing bespoke to render here.
(() => {
'use strict';
let asked = false;
const previousRenderOutput = renderOutput;
renderOutput = function () {
  previousRenderOutput();
  if (asked || !app?.pending_update?.available) return;
  asked = true;
  const u = app.pending_update;
  if (!confirm(`Clarette ${u.version} is available (you have ${u.current}). Install it now?`)) return;
  if (!u.asset_url) { message('This release has no downloadable build attached.', true); return; }
  guarded(async () => {
    await api('/api/apply-update', { asset_url: u.asset_url, asset_name: u.asset_name });
    message('Installing update… Clarette will restart shortly.');
  })();
};
})();
