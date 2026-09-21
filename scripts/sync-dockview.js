// Re-vendor the pinned dockview build into web/vendor/dockview. Run after
// bumping the "dockview" version in package.json + `npm install`.
// Clarette ships a checked-in copy (no bundler) so the packaged Mac app
// works fully offline; this script is only for refreshing that copy.
const fs = require('fs');
const path = require('path');

const root = __dirname + '/..';
const dest = path.join(root, 'web/vendor/dockview');
fs.mkdirSync(dest, { recursive: true });

const copies = [
    ['node_modules/dockview-core/dist/dockview-core.min.noStyle.js', 'dockview-core.min.js'],
    ['node_modules/dockview/dist/styles/dockview.css', 'dockview.css'],
    ['node_modules/dockview-core/LICENCE.md', 'LICENSE.md'],
];

for (const [from, to] of copies) {
    fs.copyFileSync(path.join(root, from), path.join(dest, to));
    console.log('synced', to);
}
