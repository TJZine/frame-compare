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

function element() {
    const attributes = new Map();
    const classes = new Set();
    return {
        attributes,
        children: [],
        dataset: {},
        hidden: false,
        tabIndex: 0,
        classList: {
            toggle(name, force) {
                if (force) classes.add(name);
                else classes.delete(name);
            },
        },
        setAttribute(name, value) { attributes.set(name, String(value)); },
        getAttribute(name) { return attributes.get(name) ?? null; },
        removeAttribute(name) { attributes.delete(name); },
        querySelectorAll() { return []; },
        replaceChildren(...children) { this.children = children; },
    };
}

context.document = {
    activeElement: null,
    body: element(),
    documentElement: element(),
    createElement(tagName) {
        const created = element();
        created.tagName = tagName.toUpperCase();
        return created;
    },
    createTextNode(text) { return { textContent: text }; },
};
const inspectorElement = element();
const inspectorButton = element();
const frameTab = element();
frameTab.dataset.inspectorTab = 'frame';
const framePanel = element();
framePanel.id = 'inspector-panel-frame';
const slowpics = element();
slowpics.replaceChildren({ textContent: 'sentinel' });
const textTargets = Array.from({ length: 10 }, element);
let renderingSummaryCalls = 0;
const viewer = {
    state: {
        inspectorOpen: false,
        inspectorTab: 'frame',
        alignmentPreset: 'default',
        alignX: 0,
        alignY: 0,
        mode: 'overlay',
        data: {
            title: 'Example report',
            report_id: 'report-1',
            generated_at: '2026-08-22T00:00:00Z',
            slowpics_url: 'https://slow.pics/c/example',
            stats: { frame_count: 1, clip_count: 2 },
            clips: [],
        },
    },
    dom: {
        inspector: inspectorElement,
        btnInspector: inspectorButton,
        inspectorTabs: [frameTab],
        inspectorPanels: [framePanel],
        inspectorFrameLabel: textTargets[0],
        inspectorFrameNumber: textTargets[1],
        inspectorFrameCategory: textTargets[2],
        inspectorFrameDetail: textTargets[3],
        inspectorFramePosition: textTargets[4],
        inspectorSourceFrames: null,
        inspectorClips: null,
        inspectorAlignPair: textTargets[5],
        inspectorAlignPreset: textTargets[6],
        inspectorAlignX: textTargets[7],
        inspectorAlignY: textTargets[8],
        inspectorExportTitle: textTargets[9],
        inspectorExportId: element(),
        inspectorExportGenerated: element(),
        inspectorExportSlowpics: slowpics,
        inspectorExportSummary: element(),
    },
    updateRenderingSummary() { renderingSummaryCalls += 1; },
    currentFrame() { return null; },
    setText(target, value) { target.textContent = String(value); },
    visibleFramePositionText() { return 'No frames'; },
    currentPairLabel() { return 'Reference ↔ Comparison'; },
    viewport: {
        currentPairAlignmentKey() { return '0:1'; },
        alignmentPresetLabel() { return 'Default'; },
        formatSignedPixels(value, axis) { return `${axis}:${value}`; },
    },
    persistViewportState() {},
    focusElement() {},
};
const inspector = context.__Inspector.create(viewer);
assert.equal(inspector.viewer, viewer);
assert.equal(inspector.validTab('review'), true);
assert.equal(inspector.validTab('unknown'), false);
assert.equal(inspector.safeHttpUrl('https://slow.pics/c/example'), 'https://slow.pics/c/example');
assert.equal(inspector.safeHttpUrl('javascript:alert(1)'), null);

inspector.render();
assert.equal(renderingSummaryCalls, 0);
assert.equal(slowpics.children[0].textContent, 'sentinel');
assert.equal(inspectorElement.getAttribute('aria-hidden'), 'true');

inspector.setOpen(true, { focus: false, save: false });
assert.equal(renderingSummaryCalls, 1);
assert.equal(slowpics.children[0].tagName, 'A');
assert.equal(slowpics.children[0].href, 'https://slow.pics/c/example');
assert.equal(inspectorElement.getAttribute('aria-hidden'), 'false');

inspector.setOpen(false, { focus: false, save: false });
viewer.state.data.slowpics_url = 'javascript:alert(1)';
inspector.setOpen(true, { focus: false, save: false });
assert.equal(renderingSummaryCalls, 2);
assert.equal(slowpics.children[0].textContent, 'javascript:alert(1)');
assert.equal(slowpics.children[0].tagName, undefined);

console.log(JSON.stringify({
    pureFormattingOwner: true,
    focusedInspectorOwner: renderingSummaryCalls === 2,
    safeSlowpicsBoundary: slowpics.children[0].tagName === undefined,
}));
