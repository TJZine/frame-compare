const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const assets = path.join(__dirname, '..', '..', 'src', 'frame_compare', 'services', 'report', 'assets');
const context = { URL };
vm.runInNewContext(
    `${fs.readFileSync(path.join(assets, 'viewer_format.js'), 'utf8')}\n`
    + `${fs.readFileSync(path.join(assets, 'inspector.js'), 'utf8')}\n`
    + 'globalThis.__ViewerFormat = ViewerFormat; globalThis.__Inspector = Inspector;',
    context,
);

const format = context.__ViewerFormat;
const clip = {
    display: {
        primary: 'Primary identity',
        release: '2160p | WEB-DL',
        control: 'Control identity',
        micro: 'Micro identity',
        filename: 'exact.release.name.mkv',
    },
    signal: { is_hdr: true },
    presentation: { state: 'hdr_tonemapped', tone_curve: 'bt2390', target_nits: 203 },
};

assert.equal(format.clipDisplay(clip), 'Control identity');
assert.equal(format.clipAccessibleName(clip), 'Primary identity — exact.release.name.mkv');
assert.equal(format.formatFps(24000 / 1001), `${24000 / 1001} fps`);
assert.equal(format.formatFileSize(1024 ** 3), '1.00 GiB');
assert.equal(format.formatSignal({ is_hdr: true, transfer: 16, range: 'limited' }), 'HDR · PQ · Limited');
assert.equal(format.formatPresentation(clip), 'Tonemapped · BT.2390 → 203 nits');
assert.equal(format.formatActivePicture({ width: 1920, height: 800, x: 0, y: 140, provenance: 'dolby_vision_l5' }), '1920×800 @ 0,140 · DV L5');
assert.equal(format.modeLabel('overlay'), 'Single');
assert.equal(format.stableClipRole(0, 0), 'Reference');
assert.equal(format.stableClipRole(2, 0), 'Comparison 2');

const viewer = {};
const inspector = context.__Inspector.create(viewer);
assert.equal(inspector.viewer, viewer);
assert.equal(inspector.validTab('review'), true);
assert.equal(inspector.validTab('unknown'), false);
assert.equal(inspector.safeHttpUrl('https://slow.pics/c/example'), 'https://slow.pics/c/example');
assert.equal(inspector.safeHttpUrl('javascript:alert(1)'), null);

console.log(JSON.stringify({
    pureFormattingOwner: true,
    focusedInspectorOwner: true,
    safeSlowpicsBoundary: true,
}));
