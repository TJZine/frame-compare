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
assert.equal(format.stageLabelNeedsRangeWord('Cut (HDR) · GRP'), false);
assert.equal(format.formatSignal({ is_hdr: true, transfer: 16, range: 'limited' }), 'HDR · PQ · Limited');
assert.equal(format.formatPresentation(clip), 'Tonemapped · BT.2390 → 203 nits');
assert.equal(format.formatActivePicture(null, [1920, 1080]), '1920×1080 · full frame');
assert.equal(
    format.formatActivePicture({ width: 1920, height: 800, x: 0, y: 140, provenance: 'dolby_vision_l5' }, [3840, 2160]),
    '3840×2160 · active 1920×800, 140 px top · DV L5',
);
assert.equal(format.clipBadge({ is_hdr: true, dolby_vision_rpu: true }), 'DV HDR');
assert.equal(format.clipBadge({ is_hdr: true, dolby_vision_rpu: false }), 'HDR');
assert.equal(format.clipBadge({ is_hdr: false }), 'SDR');
assert.equal(
    format.clipLengthText({ frame_count: 143487, fps: 23.976 }),
    '143,487 frames · 1:39:44',
);
assert.equal(format.clipFpsText({ fps: 23.976 }), '23.976 fps');
assert.equal(
    format.clipFpsText({ fps: 23.976, fps_num: 24000, fps_den: 1001 }),
    '23.976 fps (24000/1001)',
);
assert.deepEqual(
    JSON.parse(JSON.stringify(format.sharedClipValues([
        { fps: 24, presentation: { state: 'passthrough' } },
        { fps: 24, presentation: { state: 'passthrough' } },
    ]))),
    { fps: '24 fps', presentation: 'SDR' },
);
assert.deepEqual(
    JSON.parse(JSON.stringify(format.sharedClipValues([
        { fps: 23.976, presentation: { state: 'passthrough' } },
        { fps: 24, presentation: { state: 'passthrough' } },
    ]))),
    { fps: null, presentation: 'SDR' },
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
            contains(name) { return classes.has(name); },
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
const frameDetailRow = element();
let renderingSummaryCalls = 0;
const viewer = {
    state: {
        inspectorOpen: false,
        inspectorTab: 'frame',
        alignmentPreset: 'default',
        alignX: 0,
        alignY: 0,
        mode: 'overlay',
        data: { clips: [] },
    },
    dom: {
        inspector: inspectorElement,
        btnInspector: inspectorButton,
        inspectorTabs: [frameTab],
        inspectorPanels: [framePanel],
        inspectorFrameIdentity: textTargets[0],
        inspectorFrameDetailRow: frameDetailRow,
        inspectorFrameDetail: textTargets[1],
        inspectorFramePosition: textTargets[2],
        inspectorSourceFrames: element(),
        inspectorClipsShared: element(),
        inspectorClips: element(),
        inspectorAlignPair: textTargets[3],
        inspectorAlignPreset: textTargets[4],
        inspectorAlignX: textTargets[5],
        inspectorAlignY: textTargets[6],
    },
    updateRenderingSummary() { renderingSummaryCalls += 1; },
    currentFrame() { return null; },
    setText(target, value) { if (target) target.textContent = String(value); },
    humanizeCategory(category) { return category === 'random' ? 'Random' : category; },
    visibleFrameIndexes() { return []; },
    visibleFramePosition() { return -1; },
    frameFilterName() { return 'All'; },
    referenceClipIndex() { return 0; },
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

const tonemappedClip = {
    display: {
        primary: 'Example (2026) · 2160p · ATV WEB-DL · DV HDR10+ · Kitsune',
        release: '2160p · ATV WEB-DL · DV HDR10+ · Kitsune',
        control: '2160p · ATV WEB-DL · DV HDR10+ · Kitsune',
        micro: 'ATV WEB-DL · DV HDR10+ · Kitsune',
        filename: 'example.mkv',
    },
    resolution: [3840, 2160],
    size_bytes: 17 * 1024 ** 3,
    fps: 23.976,
    frame_count: 143487,
    signal: {
        is_hdr: true,
        primaries: 9,
        transfer: 16,
        matrix: 9,
        range: 'limited',
        dolby_vision_rpu: true,
        hdr_static: null,
    },
    active_picture: {
        x: 0,
        y: 0,
        width: 3840,
        height: 1600,
        provenance: 'dolby_vision_l5',
        is_full_frame: false,
    },
    presentation: { state: 'hdr_tonemapped', tone_curve: 'bt2390', target_nits: 100 },
};
const cardExplicitClip = {
    display: {
        primary: 'My Explicit',
        release: '1080p · WEB-DL · GRP',
        control: 'My Explicit',
        micro: 'My Explicit',
        filename: 'explicit.mkv',
    },
    resolution: [1920, 1080],
    size_bytes: 1024 ** 3,
    fps: 24,
    frame_count: 100,
    signal: {
        is_hdr: false,
        primaries: 1,
        transfer: 1,
        matrix: 1,
        range: 'limited',
        dolby_vision_rpu: false,
        hdr_static: null,
    },
    active_picture: null,
    presentation: { state: 'passthrough' },
};
const mixedClips = [tonemappedClip, cardExplicitClip];
const uniformClips = [cardExplicitClip, { ...cardExplicitClip, display: { ...cardExplicitClip.display } }];
const tableFrame = {
    number: 8987,
    label: 'Frame 8987',
    category: 'random',
    detail: '',
    images: [
        { source_frame: 8987, picture_type: 'B', dolby_vision_rpu: true },
        { source_frame: 5, picture_type: 'P' },
    ],
};
function tableViewer(clips, frame, mode, position = 0) {
    const dom = {
        inspector: element(),
        btnInspector: element(),
        inspectorTabs: [],
        inspectorPanels: [],
        inspectorFrameIdentity: element(),
        inspectorFrameDetailRow: element(),
        inspectorFrameDetail: element(),
        inspectorFramePosition: element(),
        inspectorSourceFrames: element(),
        inspectorClipsShared: element(),
        inspectorClips: element(),
    };
    const tableStub = {
        state: {
            inspectorOpen: true,
            inspectorTab: 'frame',
            mode,
            leftClipIdx: 0,
            rightClipIdx: 1,
            activeClipIdx: 0,
            activeCategoryKey: '__fc_all__',
            data: { clips },
        },
        dom,
        humanizeCategory(category) { return category === 'random' ? 'Random' : category; },
        visibleFrameIndexes() { return [0]; },
        visibleFramePosition() { return position; },
        frameFilterName() { return 'All'; },
        referenceClipIndex() { return 0; },
        gridView: { indexes() { return [0, 1]; } },
        currentFrame() { return frame; },
        setText(target, value) { if (target) target.textContent = String(value); },
        updateRenderingSummary() {},
        currentPairLabel() { return 'Reference ↔ Comparison'; },
        viewport: {
            currentPairAlignmentKey() { return '0:1'; },
            alignmentPresetLabel() { return 'Default'; },
            formatSignedPixels(value, axis) { return `${axis}:${value}`; },
        },
    };
    const tableInspector = context.__Inspector.create(tableStub);
    tableInspector.render();
    return { tableStub, tableInspector };
}

{
    const { tableStub } = tableViewer(mixedClips, tableFrame, 'slider');
    assert.equal(tableStub.dom.inspectorFrameIdentity.textContent, '8987 · Random');
    assert.equal(tableStub.dom.inspectorFramePosition.textContent, '1 / 1 in All');
    assert.equal(tableStub.dom.inspectorFrameDetailRow.hidden, true);
    const rows = tableStub.dom.inspectorSourceFrames.children;
    assert.equal(rows.length, 2);
    assert.equal(rows[0].children[0].children[0].textContent, 'ATV WEB-DL · DV HDR10+ · Kitsune');
    assert.equal(rows[0].children[0].children[1].textContent, 'Shown left');
    assert.equal(rows[0].children[1].textContent, '8987 / 143487');
    assert.equal(rows[0].children[2].textContent, 'B · DV RPU');
    assert.equal(rows[0].classList.contains('is-visible'), true);
    assert.equal(rows[1].children[0].children[1].textContent, 'Shown right');
    assert.equal(rows[1].children[0].children[0].textContent, 'My Explicit');
    assert.equal(rows[1].children[1].textContent, '5 / 100');
    assert.equal(rows[1].children[2].textContent, 'P');
    assert.equal(rows[1].classList.contains('is-visible'), true);
    const cards = tableStub.dom.inspectorClips.children;
    assert.equal(cards.length, 2);
    assert.equal(cards[0].children[0].children[0].textContent, 'Reference · shown left');
    assert.equal(cards[0].children[0].children[1].textContent, 'DV HDR');
    assert.equal(cards[0].children[1].textContent, '2160p · ATV WEB-DL · DV HDR10+ · Kitsune');
    assert.equal(cards[0].children[2].textContent, 'example.mkv');
    const cardRows = cards[0].children[3].children.map(row => ([
        row.children[0].textContent,
        row.children[1].textContent,
    ]));
    assert.deepEqual(cardRows, [
        ['Picture', '3840×2160 · active 3840×1600, 0 px top · DV L5'],
        ['Length', '143,487 frames · 1:39:44'],
        ['Size', '17.00 GiB'],
        ['FPS', '23.976 fps'],
        ['Presentation', 'Tonemapped · BT.2390 → 100 nits'],
        ['Signal', 'HDR · BT.2020 / PQ / BT.2020nc · Limited · DV RPU'],
    ]);
    assert.equal(tableStub.dom.inspectorClipsShared.hidden, true);
    assert.equal(tableStub.dom.inspectorClipsShared.textContent, '');
}

{
    const { tableStub } = tableViewer(mixedClips, { ...tableFrame, label: 'My Pick' }, 'overlay');
    assert.equal(tableStub.dom.inspectorFrameIdentity.textContent, 'My Pick');
    const rows = tableStub.dom.inspectorSourceFrames.children;
    assert.equal(rows[0].children[0].children[1].textContent, 'Shown');
    assert.equal(rows[0].classList.contains('is-visible'), true);
    assert.equal(rows[1].children[0].children.length, 1);
    assert.equal(rows[1].classList.contains('is-visible'), false);
}

{
    const notedFrame = { ...tableFrame, detail: 'Selected comparison frame' };
    const { tableStub: defaultDetail } = tableViewer(mixedClips, notedFrame, 'slider');
    assert.equal(defaultDetail.dom.inspectorFrameDetailRow.hidden, true);
    const customFrame = { ...tableFrame, detail: 'Check the grain' };
    const { tableStub: customDetail } = tableViewer(mixedClips, customFrame, 'slider');
    assert.equal(customDetail.dom.inspectorFrameDetailRow.hidden, false);
    assert.equal(customDetail.dom.inspectorFrameDetail.textContent, 'Check the grain');
}

{
    const missingFrame = {
        number: 3,
        label: 'Frame 3',
        category: 'random',
        detail: '',
        images: [{ picture_type: 'B' }, {}],
    };
    const { tableStub } = tableViewer(mixedClips, missingFrame, 'grid');
    const rows = tableStub.dom.inspectorSourceFrames.children;
    assert.equal(rows[0].children[1].textContent, 'Unknown');
    assert.equal(rows[0].children[2].textContent, 'B');
    assert.equal(rows[1].children[1].textContent, 'Unknown');
    assert.equal(rows[1].children[2].textContent, 'unknown');
    assert.equal(rows[0].children[0].children[1].textContent, 'Shown');
}

{
    const { tableStub } = tableViewer(mixedClips, tableFrame, 'slider', -1);
    assert.equal(tableStub.dom.inspectorFramePosition.textContent, 'Not shown in All');
}

{
    const { tableStub } = tableViewer(uniformClips, tableFrame, 'slider');
    assert.equal(
        tableStub.dom.inspectorClipsShared.textContent,
        'All sources: 24 fps · SDR',
    );
    assert.equal(tableStub.dom.inspectorClipsShared.hidden, false);
    const cardRows = tableStub.dom.inspectorClips.children[0].children[3].children
        .map(row => row.children[0].textContent);
    assert.deepEqual(cardRows, ['Picture', 'Length', 'Size', 'Signal']);
}

console.log(JSON.stringify({
    pureFormattingOwner: true,
    focusedInspectorOwner: renderingSummaryCalls === 2,
    frameTabRows: true,
    sourceTable: true,
    clipCards: true,
    sharedLine: true,
    dvL5Provenance: true,
}));
