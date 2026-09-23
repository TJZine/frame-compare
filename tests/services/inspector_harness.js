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
assert.equal(format.formatFps(24000 / 1001), '23.976 fps');
assert.equal(format.formatFps(23.976023976023978), '23.976 fps');
assert.equal(format.formatFps(25), '25 fps');
assert.equal(format.formatFps(29.97), '29.97 fps');
assert.equal(format.formatFps(Number.NaN), '');
assert.equal(format.formatRuntime(100, 24), '0:00:04');
assert.equal(format.formatRuntime(2400, 24), '0:01:40');
assert.equal(format.formatRuntime(46656, 24), '0:32:24');
assert.equal(format.formatRuntime(0, 24), '0:00:00');
assert.equal(format.formatRuntime(100, 0), '');
assert.equal(format.signalCodeLabel('transfer', 999), null);
assert.equal(typeof format.formatTimestamp('2026-05-22T12:00:00+00:00'), 'string');
assert.notEqual(format.formatTimestamp('2026-05-22T12:00:00+00:00'), '');
assert.notEqual(format.formatTimestamp('2026-05-22T12:00:00+00:00'), '2026-05-22T12:00:00+00:00');
assert.ok(format.formatTimestamp('2026-05-22T12:00:00+00:00').includes('2026'));
assert.equal(format.formatTimestamp('not a date'), '');
assert.equal(format.formatTimestamp(''), '');
assert.equal(format.formatFileSize(1024 ** 3), '1.00 GiB');
assert.equal(format.formatResolution([1920, 1080]), '1920×1080');
assert.equal(format.formatResolution(undefined), '');
assert.equal(format.formatResolution([1920]), '');
assert.equal(format.formatResolution(['1920', 1080]), '');
assert.equal(format.formatResolution([0, 1080]), '');
assert.equal(format.sourceHudLabel(clip), 'Control identity · HDR');
assert.deepEqual(
    JSON.parse(JSON.stringify(format.stageLabelSegments(clip))),
    { name: 'Control identity', meta: 'HDR' },
);
const hdrNamedClip = {
    display: {
        primary: '2160p · AMZN WEB-DL · HDR · SCOPE',
        control: '2160p · AMZN WEB-DL · HDR · SCOPE',
        micro: 'AMZN WEB-DL · SCOPE',
        filename: 'show.mkv',
    },
    resolution: [3840, 1600],
    size_bytes: 1024 ** 3 * 10.83,
    signal: { is_hdr: true },
};
assert.equal(
    format.sourceHudLabel(hdrNamedClip),
    '2160p · AMZN WEB-DL · HDR · SCOPE · 3840×1600 · 10.83 GiB',
);
const dvNamedClip = {
    display: {
        primary: '2160p · iT WEB-DL · DV HDR · ThisBlockHasProblems',
        control: '2160p · iT WEB-DL · DV HDR · ThisBlockHasProblems',
        micro: 'iT WEB-DL · DV HDR · ThisBlockHasProblems',
        filename: 'show.mkv',
    },
    resolution: [3840, 1606],
    size_bytes: 1024 ** 3 * 17.49,
    signal: { is_hdr: true },
};
assert.equal(
    format.sourceHudLabel(dvNamedClip),
    '2160p · iT WEB-DL · DV HDR · ThisBlockHasProblems · 3840×1606 · 17.49 GiB',
);
const explicitClip = {
    display: {
        primary: 'My Explicit',
        control: 'My Explicit',
        micro: 'My Explicit',
        filename: 'explicit.mkv',
    },
    resolution: [1920, 1080],
    size_bytes: 1024 ** 3,
    signal: { is_hdr: false },
};
assert.equal(format.sourceHudLabel(explicitClip), 'My Explicit · 1920×1080 · SDR · 1.00 GiB');
assert.equal(format.stageLabelNeedsRangeWord('2160p · MA WEB-DL · DV HDR10+ · GRP'), false);
assert.equal(format.stageLabelNeedsRangeWord('2160p · HLG · GRP'), false);
assert.equal(format.stageLabelNeedsRangeWord('My Explicit'), true);
assert.equal(format.formatSignal({ is_hdr: true, transfer: 16, range: 'limited' }), 'HDR · PQ · Limited');
assert.equal(format.formatPresentation(clip), 'Tonemapped · BT.2390 → 203 nits');
assert.equal(format.formatActivePicture(null, [1920, 1080]), '1920×1080 · full frame');
assert.equal(
    format.formatActivePicture({ width: 1920, height: 800, x: 0, y: 140, provenance: 'dolby_vision_l5' }, [3840, 2160]),
    '3840×2160 · active 1920×800, 140 px top',
);
assert.equal(
    format.formatActivePicture({ width: 1920, height: 804, x: 10, y: 138 }, [3840, 2160]),
    '3840×2160 · active 1920×804, 138 px top, 10 px left',
);
assert.equal(format.formatActivePicture(null, undefined), '');
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
const textTargets = Array.from({ length: 9 }, element);
let renderingSummaryCalls = 0;
const viewer = {
    state: {
        inspectorOpen: false,
        inspectorTab: 'frame',
        alignmentPreset: 'default',
        alignX: 0,
        alignY: 0,
        mode: 'overlay',
        data: {},
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
    persistViewerState() {},
    focusElement() {},
};
const inspector = context.__Inspector.create(viewer);
let focusabilityUpdates = 0;
const setFocusable = inspector.setFocusable.bind(inspector);
inspector.setFocusable = enabled => {
    focusabilityUpdates += 1;
    setFocusable(enabled);
};
assert.equal(inspector.viewer, viewer);
assert.equal(inspector.validTab('review'), true);
assert.equal(inspector.validTab('unknown'), false);
assert.equal(inspector.validTab('export'), false);

inspector.render();
inspector.render();
assert.equal(renderingSummaryCalls, 0);
assert.equal(focusabilityUpdates, 1);
assert.equal(inspectorElement.getAttribute('aria-hidden'), 'true');

inspector.setOpen(true, { focus: false, save: false });
assert.equal(renderingSummaryCalls, 1);
inspector.updateVisibility();
assert.equal(focusabilityUpdates, 2);
assert.equal(inspectorElement.getAttribute('aria-hidden'), 'false');

inspector.setOpen(false, { focus: false, save: false });
assert.equal(focusabilityUpdates, 3);
inspector.setOpen(true, { focus: false, save: false });
assert.equal(focusabilityUpdates, 4);
assert.equal(renderingSummaryCalls, 2);

console.log(JSON.stringify({
    pureFormattingOwner: true,
    focusedInspectorOwner: renderingSummaryCalls === 2,
}));
