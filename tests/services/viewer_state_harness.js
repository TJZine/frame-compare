const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const repoRoot = path.resolve(__dirname, '..', '..');
const viewerPath = path.join(
    repoRoot,
    'src',
    'frame_compare',
    'services',
    'report',
    'assets',
    'viewer.js',
);
const lensPath = path.join(
    repoRoot,
    'src',
    'frame_compare',
    'services',
    'report',
    'assets',
    'lens.js',
);
const viewerFormatPath = path.join(repoRoot, 'src', 'frame_compare', 'services', 'report', 'assets', 'viewer_format.js');
const inspectorPath = path.join(repoRoot, 'src', 'frame_compare', 'services', 'report', 'assets', 'inspector.js');
const viewportPath = path.join(repoRoot, 'src', 'frame_compare', 'services', 'report', 'assets', 'viewport.js');

let activeDocument = null;

function payloadWithClipCount(clipCount) {
    const clips = Array.from({ length: clipCount }, (_, idx) => ({
        name: `clip-${idx + 1}`,
        label: `Clip ${idx + 1}`,
        display: {
            primary: `Clip ${idx + 1}`,
            release: '',
            control: `Clip ${idx + 1}`,
            micro: `Clip ${idx + 1}`,
            filename: `clip-${idx + 1}.mkv`,
        },
        frame_count: 100,
        resolution: [1920, 1080],
        fps: 24,
        size_bytes: 17 * 1024 * 1024 * 1024,
        signal: {
            is_hdr: false,
            primaries: 1,
            transfer: 1,
            matrix: 10,
            range: 'limited',
            dolby_vision_rpu: false,
        },
        presentation: {
            state: 'sdr',
            tone_curve: null,
            target_nits: null,
        },
        active_picture: null,
    }));
    return {
        version: '1.2',
        report_id: 'report_viewer_state_contract',
        generated_at: '2026-06-02T12:00:00+00:00',
        title: 'Viewer State Contract',
        slowpics_url: null,
        default_mode: 'diff',
        default_selection: {
            left_clip_index: 0,
            right_clip_index: clipCount > 1 ? 1 : 0,
        },
        stats: {
            frame_count: 2,
            clip_count: clipCount,
        },
        clips,
        frames: [10, 20].map((number) => ({
            number,
            label: `Frame ${number}`,
            detail: 'Selected comparison frame',
            category: 'selected',
            images: clips.map((clip, clipIndex) => ({
                clip: clip.name,
                src: `${clip.name}/${number}.png`,
                source_frame: number,
                picture_type: 'B',
                dolby_vision_rpu: number === 10 && clipIndex === 0,
            })),
        })),
    };
}

function fakeElement() {
    const classes = new Set();
    const attributes = new Map();
    const listeners = new Map();
    let definitionValues = null;
    const inspectorPrimary = { value: null };
    const inspectorRelease = { value: null };
    return {
        value: '',
        textContent: '',
        disabled: false,
        hidden: false,
        inert: false,
        tabIndex: 0,
        children: [],
        dataset: {},
        tagName: 'DIV',
        isContentEditable: false,
        isConnected: true,
        classList: {
            toggle(name, force) {
                const enabled = force === undefined ? !classes.has(name) : Boolean(force);
                if (enabled) classes.add(name);
                else classes.delete(name);
                return enabled;
            },
            contains(name) {
                return classes.has(name);
            },
            add(...names) {
                names.forEach((name) => classes.add(name));
            },
            remove(...names) {
                names.forEach((name) => classes.delete(name));
            },
        },
        setAttribute(name, value) {
            attributes.set(name, String(value));
            this[name] = value;
        },
        getAttribute(name) {
            return attributes.has(name) ? attributes.get(name) : null;
        },
        removeAttribute(name) {
            attributes.delete(name);
            delete this[name];
        },
        closest() {
            return null;
        },
        contains(target) {
            return target === this;
        },
        addEventListener(type, listener) {
            const registered = listeners.get(type) || [];
            registered.push(listener);
            listeners.set(type, registered);
        },
        dispatch(type, event = {}) {
            if (!Object.hasOwn(event, 'target')) event.target = this;
            for (const listener of listeners.get(type) || []) {
                listener(event);
            }
        },
        focus() {
            if (activeDocument) activeDocument.activeElement = this;
        },
        scrollIntoView() {},
        replaceChildren(...children) {
            this.children = children;
        },
        querySelector(selector) {
            if (selector === '.rv-inspector-clip-primary') {
                if (!inspectorPrimary.value) inspectorPrimary.value = fakeElement();
                return inspectorPrimary.value;
            }
            if (selector === '.rv-inspector-clip-release') {
                if (!inspectorRelease.value) inspectorRelease.value = fakeElement();
                return inspectorRelease.value;
            }
            return null;
        },
        querySelectorAll(selector) {
            if (selector === '.rv-inspector-clip-heading span') {
                return [fakeElement(), fakeElement()];
            }
            if (selector === 'dd') {
                if (definitionValues === null) {
                    definitionValues = Array.from({ length: 7 }, () => fakeElement());
                }
                return definitionValues;
            }
            return [];
        },
        style: {
            values: {},
            setProperty(name, value) {
                this.values[name] = value;
            },
            removeProperty(name) {
                delete this.values[name];
            },
        },
    };
}

function fakeBody() {
    return fakeElement();
}

function loadViewer({ clipCount, savedState = null }) {
    const storage = new Map();
    const reviewMetrics = { creates: 0, binds: 0, renders: 0 };
    const storageApi = {
        getItem(key) {
            return storage.has(key) ? storage.get(key) : null;
        },
        setItem(key, value) {
            storage.set(key, value);
        },
    };
    const context = {
        console,
        setInterval(callback) {
            return { callback };
        },
        clearInterval() {},
        URL,
        ReviewState: {
            createController() {
                reviewMetrics.creates += 1;
                return {
                    bind() { reviewMetrics.binds += 1; },
                    render() { reviewMetrics.renders += 1; },
                };
            },
        },
        document: {
            activeElement: null,
            body: fakeBody(),
            addEventListener() {},
            createElement(tagName) {
                return { ...fakeElement(), tagName: String(tagName || '').toUpperCase() };
            },
            createTextNode(text) {
                return { nodeType: 3, textContent: String(text) };
            },
        },
        window: {
            localStorage: storageApi,
            matchMedia() {
                return { matches: false };
            },
        },
    };
    activeDocument = context.document;
    const script = `${fs.readFileSync(viewerFormatPath, 'utf8')}\n${fs.readFileSync(lensPath, 'utf8')}\n${fs.readFileSync(inspectorPath, 'utf8')}\n${fs.readFileSync(viewportPath, 'utf8')}\n${fs.readFileSync(viewerPath, 'utf8')}\nglobalThis.__Lens = Lens;\nglobalThis.__Inspector = Inspector;\nglobalThis.__Viewport = Viewport;\nglobalThis.__ReportViewer = ReportViewer;`;
    vm.runInNewContext(script, context, { filename: viewerPath });
    assert.equal(typeof context.__Lens.create, 'function');

    const viewer = context.__ReportViewer;
    viewer.inspector = context.__Inspector.create(viewer);
    viewer.viewport = context.__Viewport.create(viewer);
    const payload = viewer.normalizePayload(payloadWithClipCount(clipCount));
    viewer.state.data = payload;
    viewer.state.mode = payload.default_mode;
    viewer.state.storageKey = viewer.viewportStorageKey();
    viewer.state.currentFrameIdx = 0;
    viewer.state.leftClipIdx = 0;
    viewer.state.rightClipIdx = 1;
    viewer.state.activeClipIdx = 0;
    viewer.state.fitMode = 'actual';
    viewer.state.zoom = 1;
    viewer.state.panX = 0;
    viewer.state.panY = 0;
    viewer.state.revealPercent = 50;
    viewer.state.alignmentPreset = 'none';
    viewer.state.alignX = 0;
    viewer.state.alignY = 0;
    viewer.state.pairAlignments = {};
    viewer.state.rawAlignX = null;
    viewer.state.rawAlignY = null;
    viewer.dom = {
        stage: {
            ...fakeElement(),
            getBoundingClientRect() {
                return { width: 1920, height: 1080 };
            },
        },
        canvas: fakeElement(),
        sizerImg: {
            ...fakeElement(),
            getBoundingClientRect() {
                return { width: 1920, height: 1080 };
            },
        },
        leftImg: fakeElement(),
        rightImg: fakeElement(),
        labelLeft: fakeElement(),
        labelRight: fakeElement(),
        leftLayer: fakeElement(),
        rightLayer: fakeElement(),
        zoomRange: fakeElement(),
        zoomVal: fakeElement(),
        modeBtns: ['slider', 'overlay', 'diff', 'blink'].map((mode) => ({
            ...fakeElement(),
            dataset: { mode },
        })),
        pairControls: fakeElement(),
        activeControls: fakeElement(),
        leftSelect: fakeElement(),
        rightSelect: fakeElement(),
        activeSelect: fakeElement(),
        btnSwapClips: fakeElement(),
        fitBtns: ['actual', 'width', 'height'].map((fit) => ({
            ...fakeElement(),
            dataset: { fit },
        })),
        alignmentPreset: fakeElement(),
        alignX: fakeElement(),
        alignY: fakeElement(),
        btnAlignmentReset: fakeElement(),
        btnAlignToggle: fakeElement(),
        alignmentStatus: fakeElement(),
        btnInfo: fakeElement(),
        btnInspector: fakeElement(),
        inspector: fakeElement(),
        btnInspectorClose: fakeElement(),
        inspectorTabs: ['frame', 'clips', 'align', 'review', 'export'].map((tab) => ({
            ...fakeElement(),
            dataset: { inspectorTab: tab },
        })),
        inspectorPanels: ['frame', 'clips', 'align', 'review', 'export'].map((tab) => ({
            ...fakeElement(),
            id: `inspector-panel-${tab}`,
        })),
        inspectorFrameLabel: fakeElement(),
        inspectorFrameNumber: fakeElement(),
        inspectorFrameCategory: fakeElement(),
        inspectorFrameDetail: fakeElement(),
        inspectorFramePosition: fakeElement(),
        inspectorSourceFrames: fakeElement(),
        inspectorClips: fakeElement(),
        inspectorAlignPair: fakeElement(),
        inspectorAlignPreset: fakeElement(),
        inspectorAlignX: fakeElement(),
        inspectorAlignY: fakeElement(),
        btnInspectorResetCurrentAlign: fakeElement(),
        btnInspectorResetAllAlign: fakeElement(),
        inspectorExportTitle: fakeElement(),
        inspectorExportId: fakeElement(),
        inspectorExportGenerated: fakeElement(),
        inspectorExportSlowpics: fakeElement(),
        inspectorExportSummary: fakeElement(),
        modal: fakeElement(),
        infoModal: fakeElement(),
        btnHelp: fakeElement(),
        btnCloseHelp: fakeElement(),
        btnCloseInfo: fakeElement(),
        blinkControls: fakeElement(),
        btnBlinkPause: fakeElement(),
        blinkSpeed: fakeElement(),
        blinkStatus: fakeElement(),
        viewportPalette: fakeElement(),
        btnPaletteOrientation: fakeElement(),
        bottomPanel: {
            ...fakeElement(),
            dataset: { filmstripEnabled: 'true' },
        },
        btnFilmstripToggle: fakeElement(),
        filmstripSizeBtns: ['compact', 'normal', 'large'].map((size) => ({
            ...fakeElement(),
            dataset: { filmstripSize: size },
        })),
        filmstrip: fakeElement(),
        activeFilterBadge: fakeElement(),
        alignPopover: {
            ...fakeElement(),
            hidden: true,
        },
    };
    viewer.dom.btnInfo.setAttribute('aria-label', 'Report information');
    viewer.dom.btnInfo.setAttribute('title', 'Report Info');
    viewer.dom.btnInspector.setAttribute('aria-controls', 'rv-inspector');
    viewer.dom.btnInspector.setAttribute('aria-expanded', 'false');
    viewer.dom.btnInspector.setAttribute('aria-label', 'Open Inspector');
    viewer.dom.btnInspector.setAttribute('title', 'Inspector (I)');
    viewer.dom.inspectorFocusables = [
        viewer.dom.btnInspectorClose,
        ...viewer.dom.inspectorTabs,
        viewer.dom.btnInspectorResetCurrentAlign,
        viewer.dom.btnInspectorResetAllAlign,
    ];
    viewer.dom.inspector.inert = true;
    viewer.dom.inspectorFocusables.forEach((element) => {
        element.setAttribute('tabindex', '-1');
    });
    viewer.dom.inspector.querySelectorAll = () => viewer.dom.inspectorFocusables;
    viewer.lens = {
        state: { report: { enabled: false }, point: null },
        transientClears: 0,
        refreshes: 0,
        syncs: 0,
        cancelTouchPending() {},
        clearTransient() { this.transientClears += 1; },
        endStagePointer() { return true; },
        handleStagePointerDown() { return false; },
        handleStagePointerMove() { return false; },
        refresh() { this.refreshes += 1; },
        render() {},
        setEnabled(enabled) { this.state.report.enabled = Boolean(enabled); },
        sync() { this.syncs += 1; },
    };
    viewer.reviewController = null;
    viewer.render = function renderStateOnly() {
        this.viewport.applyAlignment();
        this.persistViewportState();
    };

    if (savedState !== null) {
        storage.set(viewer.state.storageKey, JSON.stringify(savedState));
    }

    viewer.applyDefaultSelection();
    viewer.restorePersistedState();
    viewer.viewport.applyAlignment();
    return {
        viewer,
        storage,
        storageKey: viewer.state.storageKey,
        document: context.document,
        reviewMetrics,
    };
}

function persisted(storage, storageKey) {
    return JSON.parse(storage.get(storageKey));
}

function keyboardEvent(key) {
    return {
        key,
        target: { tagName: 'DIV', isContentEditable: false, closest() { return null; } },
        defaultPrevented: false,
        propagationStopped: false,
        preventDefault() {
            this.defaultPrevented = true;
        },
        stopPropagation() {
            this.propagationStopped = true;
        },
    };
}

const summary = {};

{
    const { viewer } = loadViewer({ clipCount: 4 });
    const clip = {
        name: 'canonical-name',
        label: 'Canonical label',
        display: {
            primary: 'Primary release identity',
            release: 'Release descriptor',
            control: 'Control descriptor',
            micro: 'Micro descriptor',
            filename: 'Exact.File.Name.mkv',
        },
    };
    assert.equal(viewer.clipDisplay(clip), 'Control descriptor');
    assert.equal(viewer.clipDisplay(clip, 'micro'), 'Micro descriptor');
    assert.equal(
        viewer.clipAccessibleName(clip),
        'Primary release identity — Exact.File.Name.mkv',
    );
    assert.equal(viewer.stableClipRole(0), 'Reference');
    assert.equal(viewer.stableClipRole(1), 'Comparison 1');
    viewer.state.data.default_selection.left_clip_index = 2;
    assert.equal(viewer.stableClipRole(0), 'Comparison 1');
    assert.equal(viewer.stableClipRole(1), 'Comparison 2');
    assert.equal(viewer.stableClipRole(2), 'Reference');
    assert.equal(viewer.stableClipRole(3), 'Comparison 3');
    summary.clipDisplayProfiles = {
        requiredPayloadProfiles: true,
        stableInspectorRoles: true,
    };
}

{
    const { viewer } = loadViewer({
        clipCount: 4,
        savedState: {
            mode: 'diff',
            leftClipIdx: 0,
            rightClipIdx: 1,
            activeClipIdx: 3,
            fitMode: 'custom',
            zoom: 8,
            panX: 12,
            panY: -5,
            revealPercent: 120,
            alignmentPreset: 'custom',
            alignX: 77,
            alignY: -88,
            pairAlignments: {
                '0:1': { alignmentPreset: 'custom', alignX: 5, alignY: -2 },
                '1:0': { alignmentPreset: 'custom', alignX: -7, alignY: 3 },
                '0:9': { alignmentPreset: 'custom', alignX: 99, alignY: 99 },
            },
        },
    });

    assert.equal(viewer.state.mode, 'diff');
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 1);
    assert.equal(viewer.state.activeClipIdx, 3);
    assert.equal(viewer.state.zoom, 4);
    assert.equal(viewer.state.revealPercent, 100);
    assert.equal(viewer.state.filmstripCollapsed, false);
    assert.equal(viewer.state.filmstripSize, 'normal');
    assert.equal(viewer.state.alignX, 5);
    assert.equal(viewer.state.alignY, -2);
    assert.deepEqual(Object.keys(viewer.state.pairAlignments).sort(), ['0:1', '1:0']);
    assert.equal(viewer.dom.alignmentStatus.textContent, 'Aligned: custom +5x -2y');
    summary.restoreFourClip = {
        clipCount: viewer.clipCount(),
        leftClipIdx: viewer.state.leftClipIdx,
        rightClipIdx: viewer.state.rightClipIdx,
        activeClipIdx: viewer.state.activeClipIdx,
        restoredPairKeys: Object.keys(viewer.state.pairAlignments).sort(),
        currentAlignment: [viewer.state.alignX, viewer.state.alignY],
        alignmentStatus: viewer.dom.alignmentStatus.textContent,
    };
}

{
    const { viewer } = loadViewer({
        clipCount: 2,
        savedState: {
            alignmentPreset: 'custom',
            alignX: 77,
            alignY: -88,
        },
    });

    assert.deepEqual(Object.keys(viewer.state.pairAlignments), []);
    assert.equal(viewer.state.alignmentPreset, 'none');
    assert.equal(viewer.state.alignX, 0);
    assert.equal(viewer.state.alignY, 0);

    const malformedStorage = loadViewer({
        clipCount: 2,
        savedState: {
            pairAlignments: {
                '0:1': { alignmentPreset: 'custom', alignX: 6, alignY: -7 },
            },
        },
    });
    malformedStorage.storage.set(malformedStorage.storageKey, '{malformed');
    malformedStorage.viewer.restorePersistedState();
    assert.deepEqual(Object.keys(malformedStorage.viewer.state.pairAlignments), ['0:1']);
    assert.equal(malformedStorage.viewer.state.alignmentPreset, 'custom');
    assert.equal(malformedStorage.viewer.state.alignX, 6);
    assert.equal(malformedStorage.viewer.state.alignY, -7);
}

{
    const { viewer } = loadViewer({
        clipCount: 2,
        savedState: {
            mode: 'diff',
            currentFrameIdx: 99,
            leftClipIdx: 3,
            rightClipIdx: 9,
            activeClipIdx: 9,
            pairAlignments: {
                '0:1': { alignmentPreset: 'custom', alignX: 2, alignY: 4 },
                '3:9': { alignmentPreset: 'custom', alignX: 99, alignY: 99 },
            },
        },
    });

    assert.equal(viewer.state.currentFrameIdx, 0);
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 1);
    assert.equal(viewer.state.activeClipIdx, 0);
    assert.equal(viewer.state.alignX, 2);
    assert.equal(viewer.state.alignY, 4);
    assert.deepEqual(Object.keys(viewer.state.pairAlignments), ['0:1']);
}

{
    const { viewer, storage, storageKey } = loadViewer({
        clipCount: 4,
        savedState: {
            filmstripCollapsed: true,
            filmstripSize: 'large',
        },
    });

    assert.equal(viewer.state.filmstripCollapsed, true);
    assert.equal(viewer.state.filmstripSize, 'large');
    viewer.setFilmstripCollapsed(true);
    assert.equal(viewer.dom.bottomPanel.classList.contains('rv-bottom-panel--collapsed'), true);
    viewer.setFilmstripCollapsed(false);
    assert.equal(viewer.dom.bottomPanel.classList.contains('rv-bottom-panel--collapsed'), false);
    viewer.setFilmstripSize('compact');

    const saved = persisted(storage, storageKey);
    assert.equal(saved.filmstripCollapsed, false);
    assert.equal(saved.filmstripSize, 'compact');
    summary.filmstripState = {
        collapsed: saved.filmstripCollapsed,
        size: saved.filmstripSize,
        collapsedClassRemoved: !viewer.dom.bottomPanel.classList.contains('rv-bottom-panel--collapsed'),
    };
}

{
    const { viewer } = loadViewer({
        clipCount: 4,
        savedState: {
            filmstripCollapsed: 'yes',
            filmstripSize: 'huge',
            inspectorOpen: 'yes',
            inspectorTab: 'bad',
            blinkIntervalMs: '700',
        },
    });

    assert.equal(viewer.state.filmstripCollapsed, false);
    assert.equal(viewer.state.filmstripSize, 'normal');
    assert.equal(viewer.state.inspectorOpen, false);
    assert.equal(viewer.state.inspectorTab, 'frame');
    assert.equal(viewer.state.blinkIntervalMs, 700);
    assert.equal(typeof viewer.state.blinkIntervalMs, 'number');
    summary.invalidFilmstripStateFallback = {
        collapsed: viewer.state.filmstripCollapsed,
        size: viewer.state.filmstripSize,
        stringBlinkIntervalFallback: viewer.state.blinkIntervalMs,
    };
}

{
    const { viewer, storage, storageKey, document, reviewMetrics } = loadViewer({
        clipCount: 4,
        savedState: {
            currentFrameIdx: 1,
            inspectorOpen: true,
            inspectorTab: 'align',
            blinkIntervalMs: 1200,
            blinkPaused: true,
        },
    });

    assert.equal(viewer.state.currentFrameIdx, 1);
    assert.equal(viewer.state.inspectorOpen, true);
    assert.equal(viewer.state.inspectorTab, 'align');
    assert.equal(viewer.state.blinkIntervalMs, 1200);
    assert.equal(viewer.state.blinkPaused, false);
    viewer.dom.btnInspectorClose.setAttribute('tabindex', '0');
    viewer.setInspectorOpen(false, { focus: false, save: false });

    assert.equal(reviewMetrics.creates, 0);
    viewer.setInspectorTab('review');
    assert.equal(viewer.state.inspectorTab, 'review');
    assert.deepEqual(reviewMetrics, { creates: 0, binds: 0, renders: 0 });
    viewer.setInspectorTab('export');
    viewer.setInspectorTab('review');
    assert.equal(reviewMetrics.creates, 0);
    viewer.setInspectorTab('export');
    const focusables = viewer.dom.inspectorFocusables;
    const initiatingControl = fakeElement();
    document.activeElement = initiatingControl;
    const infoLabel = viewer.dom.btnInfo.getAttribute('aria-label');
    const infoTitle = viewer.dom.btnInfo.getAttribute('title');
    viewer.setInspectorOpen(true);
    assert.equal(document.activeElement, viewer.dom.inspectorTabs[4]);
    const wrapEvent = keyboardEvent('ArrowRight');
    wrapEvent.currentTarget = viewer.dom.inspectorTabs[4];
    viewer.handleInspectorTabKey(wrapEvent);
    assert.equal(viewer.state.inspectorTab, 'frame');
    assert.equal(document.activeElement, viewer.dom.inspectorTabs[0]);
    viewer.setInspectorTab('export');
    assert.equal(viewer.dom.inspector.inert, false);
    assert.equal(viewer.dom.btnInspectorClose.getAttribute('tabindex'), '0');
    assert.equal(viewer.dom.btnInspector.getAttribute('aria-expanded'), 'true');
    assert.equal(viewer.dom.btnInspector.classList.contains('active'), true);
    viewer.setInspectorOpen(false);
    assert.equal(document.activeElement, initiatingControl);
    assert.equal(viewer.dom.btnInspector.getAttribute('aria-expanded'), 'false');
    assert.equal(viewer.dom.btnInspector.classList.contains('active'), false);
    assert.equal(viewer.dom.btnInfo.getAttribute('aria-label'), infoLabel);
    assert.equal(viewer.dom.btnInfo.getAttribute('title'), infoTitle);
    assert.equal(viewer.dom.btnInfo.getAttribute('aria-pressed'), null);
    const restoredKeyboardFocusToOrigin = document.activeElement === initiatingControl;
    assert.equal(viewer.state.inspectorRestoreFocus, null);
    assert.equal(viewer.dom.inspector.inert, true);
    focusables.forEach((element) => {
        assert.equal(element.getAttribute('tabindex'), '-1');
    });
    viewer.setInspectorOpen(true);
    assert.equal(viewer.dom.inspector.inert, false);
    assert.equal(viewer.dom.btnInspectorClose.getAttribute('tabindex'), '0');
    viewer.dom.inspectorTabs.forEach((element, index) => {
        assert.equal(element.tabIndex, index === 4 ? 0 : -1);
    });
    viewer.setInspectorOpen(false);
    document.activeElement = document.body;
    viewer.setInspectorOpen(true);
    viewer.setInspectorOpen(false);
    assert.equal(document.activeElement, viewer.dom.btnInspector);
    viewer.setBlinkIntervalMs(300);
    viewer.setBlinkPaused(true);
    const saved = persisted(storage, storageKey);
    assert.equal(saved.currentFrameIdx, 1);
    assert.equal(saved.inspectorOpen, false);
    assert.equal(saved.inspectorTab, 'export');
    assert.equal(saved.pixelLensEnabled, undefined);
    assert.equal(saved.blinkIntervalMs, 300);
    assert.equal(saved.blinkPaused, undefined);
    summary.inspectorBlinkKeyboardState = {
        currentFrameIdx: saved.currentFrameIdx,
        inspectorOpen: saved.inspectorOpen,
        inspectorTab: saved.inspectorTab,
        lensExcludedFromViewport: !Object.hasOwn(saved, 'pixelLensEnabled'),
        rovingTabWrapped: true,
        blinkIntervalMs: saved.blinkIntervalMs,
        blinkPausedPersisted: Object.hasOwn(saved, 'blinkPaused'),
        closedInspectorInert: viewer.dom.inspector.inert,
        closedInspectorTabIndex: viewer.dom.btnInspectorClose.getAttribute('tabindex'),
        restoredKeyboardFocusToOrigin,
        clearedKeyboardFocusRestoreTarget: viewer.state.inspectorRestoreFocus === null,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 1 });
    viewer.setInspectorOpen(true, { focus: false, save: false });
    const values = viewer.dom.inspectorClips.children[0].querySelectorAll('dd');
    assert.equal(values.length, 7);
    assert.equal(values[4].textContent, '17.00 GiB');
    assert.equal(values[5].textContent, 'SDR · BT.709 / BT.709 / BT.2020c · Limited');
    assert.equal(values[6].textContent, 'SDR');
    summary.inspectorClipMetadata = {
        valueCount: values.length,
        fileSize: values[4].textContent,
        signal: values[5].textContent,
        presentation: values[6].textContent,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 2 });
    const release = '2160p | WEB-DL | GROUP';
    viewer.state.data.clips[0].display = {
        primary: `Example (2026) | ${release}`,
        release,
    };
    viewer.state.data.clips[1].display = {
        primary: 'Explicit comparison label',
        release,
    };
    viewer.setInspectorOpen(true, { focus: false, save: false });
    const automaticRelease = viewer.dom.inspectorClips.children[0]
        .querySelector('.rv-inspector-clip-release');
    const explicitRelease = viewer.dom.inspectorClips.children[1]
        .querySelector('.rv-inspector-clip-release');
    assert.equal(automaticRelease.hidden, true);
    assert.equal(automaticRelease.textContent, '');
    assert.equal(explicitRelease.hidden, false);
    assert.equal(explicitRelease.textContent, release);
    summary.inspectorReleasePresentation = {
        automaticIdentityNotDuplicated: automaticRelease.hidden,
        explicitLabelKeepsReleaseDifferentiator: !explicitRelease.hidden,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 2 });
    viewer.setInspectorOpen(true, { focus: false, save: false });
    summary.inspectorFrameSources = viewer.dom.inspectorSourceFrames.children.map(
        item => item.textContent,
    );
}

{
    const { viewer, document } = loadViewer({ clipCount: 4 });
    const helpLast = fakeElement();
    const infoLast = fakeElement();
    viewer.dom.modal.querySelectorAll = () => [viewer.dom.btnCloseHelp, helpLast];
    viewer.dom.infoModal.querySelectorAll = () => [viewer.dom.btnCloseInfo, infoLast];

    document.activeElement = viewer.dom.btnHelp;
    viewer.openHelpModal();
    document.activeElement = helpLast;
    const helpTab = keyboardEvent('Tab');
    viewer.handleModalKey(helpTab);
    assert.equal(document.activeElement, viewer.dom.btnCloseHelp);
    const helpShiftTab = keyboardEvent('Tab');
    helpShiftTab.shiftKey = true;
    viewer.handleModalKey(helpShiftTab);
    assert.equal(document.activeElement, helpLast);
    const helpEscape = keyboardEvent('Escape');
    viewer.handleModalKey(helpEscape);
    assert.equal(document.activeElement, viewer.dom.btnHelp);

    document.activeElement = viewer.dom.btnInfo;
    viewer.openInfoModal();
    document.activeElement = infoLast;
    const infoTab = keyboardEvent('Tab');
    viewer.handleInfoModalKey(infoTab);
    assert.equal(document.activeElement, viewer.dom.btnCloseInfo);
    const infoShiftTab = keyboardEvent('Tab');
    infoShiftTab.shiftKey = true;
    viewer.handleInfoModalKey(infoShiftTab);
    assert.equal(document.activeElement, infoLast);
    const infoEscape = keyboardEvent('Escape');
    viewer.handleInfoModalKey(infoEscape);
    assert.equal(document.activeElement, viewer.dom.btnInfo);

    summary.modalKeyboardAccessibility = {
        helpFocusTrappedAndRestored: (
            helpTab.defaultPrevented
            && helpShiftTab.defaultPrevented
            && helpEscape.defaultPrevented
        ),
        infoFocusTrappedAndRestored: (
            infoTab.defaultPrevented
            && infoShiftTab.defaultPrevented
            && infoEscape.defaultPrevented
        ),
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });

    viewer.bindAlignmentEvents();
    viewer.setInspectorOpen(true);
    viewer.setAlignmentPopoverOpen(true, { restoreFocus: false });
    const popoverEscape = keyboardEvent('Escape');
    viewer.dom.alignPopover.dispatch('keydown', popoverEscape);
    if (!popoverEscape.propagationStopped) viewer.handleKey(popoverEscape);
    assert.equal(popoverEscape.defaultPrevented, true);
    assert.equal(popoverEscape.propagationStopped, true);
    assert.equal(viewer.isAlignmentPopoverOpen(), false);
    assert.equal(viewer.state.inspectorOpen, true);

    viewer.setInspectorOpen(true);
    viewer.setAlignmentPopoverOpen(true, { restoreFocus: false });
    const firstEscape = keyboardEvent('Escape');
    viewer.handleKey(firstEscape);
    assert.equal(firstEscape.defaultPrevented, true);
    assert.equal(viewer.state.inspectorOpen, true);
    assert.equal(viewer.isAlignmentPopoverOpen(), false);

    const secondEscape = keyboardEvent('Escape');
    viewer.handleKey(secondEscape);
    assert.equal(secondEscape.defaultPrevented, true);
    assert.equal(viewer.state.inspectorOpen, false);

    viewer.setInspectorOpen(true);
    viewer.setAlignmentPopoverOpen(true, { restoreFocus: false });
    viewer.dom.infoModal.classList.add('open');
    const infoEscape = keyboardEvent('Escape');
    viewer.handleKey(infoEscape);
    assert.equal(infoEscape.defaultPrevented, true);
    assert.equal(viewer.isInfoModalOpen(), false);
    assert.equal(viewer.state.inspectorOpen, true);
    assert.equal(viewer.isAlignmentPopoverOpen(), true);

    summary.escapeOrder = {
        popoverHandlerPreventedGlobalShortcut: (
            popoverEscape.defaultPrevented
            && popoverEscape.propagationStopped
            && viewer.state.inspectorOpen
        ),
        alignmentClosedBeforeInspector: true,
        legacyInfoModalWins: true,
        inspectorStillOpenAfterAlignmentEscape: true,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });

    viewer.state.data.slowpics_url = 'https://slow.pics/c/abc?x=1&y=2';
    viewer.updateInspectorSlowpics();
    assert.equal(viewer.dom.inspectorExportSlowpics.children.length, 1);
    const link = viewer.dom.inspectorExportSlowpics.children[0];
    assert.equal(link.tagName, 'A');
    assert.equal(link.href, 'https://slow.pics/c/abc?x=1&y=2');
    assert.equal(link.rel, 'noopener noreferrer');
    assert.equal(link.target, '_blank');
    assert.equal(link.textContent, 'https://slow.pics/c/abc?x=1&y=2');

    viewer.state.data.slowpics_url = 'javascript:alert(1)';
    viewer.updateInspectorSlowpics();
    assert.equal(viewer.dom.inspectorExportSlowpics.children.length, 1);
    assert.equal(viewer.dom.inspectorExportSlowpics.children[0].nodeType, 3);
    assert.equal(viewer.dom.inspectorExportSlowpics.children[0].textContent, 'javascript:alert(1)');

    viewer.state.data.slowpics_url = null;
    viewer.updateInspectorSlowpics();
    assert.equal(viewer.dom.inspectorExportSlowpics.children[0].textContent, 'Not uploaded');

    summary.inspectorSlowpics = {
        safeLinkTag: 'A',
        unsafeAsText: true,
        missingStatus: 'Not uploaded',
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });

    viewer.windowReducedMotion = true;
    const originalReducedMotionActive = viewer.reducedMotionActive;
    viewer.reducedMotionActive = () => true;
    viewer.setMode('blink');
    assert.equal(viewer.state.mode, 'blink');
    assert.equal(viewer.state.blinkPaused, true);
    assert.equal(viewer.dom.blinkStatus.textContent, 'Blink paused');
    viewer.setBlinkPaused(false);
    viewer.stepBlinkInterval(1);
    assert.equal(viewer.state.blinkIntervalMs, 1200);
    viewer.stepBlinkInterval(-1);
    assert.equal(viewer.state.blinkIntervalMs, 700);
    viewer.reducedMotionActive = originalReducedMotionActive;
    summary.blinkControls = {
        reducedMotionPaused: true,
        status: 'Blink paused',
        intervalAfterSteps: viewer.state.blinkIntervalMs,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 2 });
    const clip = {
        label: 'Title.2160p.WEB-DL.Service-GROUP',
        display: {
            primary: 'Title.2160p.WEB-DL.Service-GROUP',
            release: '2160p | Service WEB-DL | GROUP',
            control: 'Title.2160p.WEB-DL.Service-GROUP',
            micro: 'Service WEB-DL',
            filename: 'Title.2160p.WEB-DL.Service-GROUP.mkv',
        },
        resolution: [3840, 2160],
        size_bytes: 17 * 1024 ** 3,
        signal: { is_hdr: true },
    };
    assert.equal(
        viewer.clipOverlayLabel(clip),
        'Title.2160p.WEB-DL.Service-GROUP • 3840×2160 • HDR • 17.00 GiB',
    );
    assert.equal(
        viewer.clipOverlayLabel(clip, 'Left'),
        'LEFT: Title.2160p.WEB-DL.Service-GROUP • 3840×2160 • HDR • 17.00 GiB',
    );
    summary.sourceOverlayLabels = {
        single: viewer.clipOverlayLabel(clip),
        slider: viewer.clipOverlayLabel(clip, 'Left'),
        diff: viewer.clipOverlayLabel(clip, 'Base'),
    };

    assert.equal(viewer.formatFileSize(1), '1.00 B');
    assert.equal(viewer.formatFileSize(1023), '1023.00 B');
    assert.equal(viewer.formatFileSize(1024), '1.00 KiB');
    assert.equal(viewer.formatFileSize(512 * 1024), '512.00 KiB');
    assert.equal(viewer.formatFileSize(1024 ** 2), '1.00 MiB');
    assert.equal(viewer.formatFileSize(1024 ** 3), '1.00 GiB');
    assert.equal(viewer.formatFileSize(1024 ** 4), '1.00 TiB');
    assert.equal(viewer.formatFileSize(0), '');
    assert.equal(viewer.formatFileSize(-1), '');
    assert.equal(viewer.formatFileSize(Number.NaN), '');
    assert.equal(
        viewer.formatSignal({
            is_hdr: true,
            primaries: 9,
            transfer: 16,
            matrix: 10,
            range: 'limited',
            dolby_vision_rpu: true,
        }),
        'HDR · BT.2020 / PQ / BT.2020c · Limited · DV RPU',
    );
}

{
    const { viewer } = loadViewer({ clipCount: 4 });

    const labels = viewer.blinkStageLabels('Clip 1', 'Clip 2');
    assert.equal(labels.left, 'FIRST: Clip 1');
    assert.equal(labels.right, 'SECOND: Clip 2');

    viewer.state.mode = 'blink';
    viewer.state.activeClipIdx = viewer.state.leftClipIdx;
    viewer.updateImages();
    assert.equal(viewer.dom.labelLeft.textContent, 'FIRST: Clip 1 • 1920×1080 • SDR • 17.00 GiB');
    assert.equal(viewer.dom.labelRight.textContent, 'SECOND: Clip 2 • 1920×1080 • SDR • 17.00 GiB');
    assert.equal(viewer.dom.labelLeft.classList.contains('rv-overlay-label--active'), true);
    assert.equal(viewer.dom.labelRight.classList.contains('rv-overlay-label--active'), false);
    viewer.state.activeClipIdx = viewer.state.rightClipIdx;
    viewer.updateImages();
    assert.equal(viewer.dom.labelLeft.classList.contains('rv-overlay-label--active'), false);
    assert.equal(viewer.dom.labelRight.classList.contains('rv-overlay-label--active'), true);
    summary.blinkLabels = {
        labels,
        activeLabelMoved: false,
        activeStateMoved: true,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });
    const button = { tagName: 'BUTTON', isContentEditable: false };
    const textarea = { tagName: 'TEXTAREA', isContentEditable: false };
    const contentEditable = { tagName: 'DIV', isContentEditable: true };
    const nestedInButton = {
        tagName: 'SPAN',
        isContentEditable: false,
        closest(selector) {
            return selector.includes('button') ? button : null;
        },
    };
    const plain = { tagName: 'DIV', isContentEditable: false, closest() { return null; } };

    assert.equal(viewer.isShortcutEditableTarget(button), true);
    assert.equal(viewer.isShortcutEditableTarget(textarea), true);
    assert.equal(viewer.isShortcutEditableTarget(contentEditable), true);
    assert.equal(viewer.isShortcutEditableTarget(nestedInButton), true);
    assert.equal(viewer.isShortcutEditableTarget(plain), false);
    summary.keyboardGuard = {
        button: viewer.isShortcutEditableTarget(button),
        textarea: viewer.isShortcutEditableTarget(textarea),
        contentEditable: viewer.isShortcutEditableTarget(contentEditable),
        nestedInButton: viewer.isShortcutEditableTarget(nestedInButton),
        plain: viewer.isShortcutEditableTarget(plain),
    };
}

{
    const { viewer, document } = loadViewer({ clipCount: 4 });
    const buttons = ['first', 'second', 'third'].map(value => ({
        ...fakeElement(),
        dataset: { value },
    }));
    buttons[0].setAttribute('aria-checked', 'true');
    buttons[1].setAttribute('aria-checked', 'false');
    buttons[2].setAttribute('aria-checked', 'false');
    let selected = 'first';
    viewer.bindRadioGroup(buttons, button => {
        selected = button.dataset.value;
        buttons.forEach(item => item.setAttribute('aria-checked', item === button ? 'true' : 'false'));
        viewer.syncRadioGroupTabStops(buttons);
    });
    viewer.syncRadioGroupTabStops(buttons);

    let prevented = false;
    let stopped = false;
    buttons[0].dispatch('keydown', {
        key: 'ArrowLeft',
        preventDefault() { prevented = true; },
        stopPropagation() { stopped = true; },
    });

    assert.equal(selected, 'third');
    assert.equal(document.activeElement, buttons[2]);
    assert.deepEqual(buttons.map(button => button.tabIndex), [-1, -1, 0]);
    assert.equal(prevented, true);
    assert.equal(stopped, true);
    summary.radioGroupKeyboard = {
        wrapsAndSelects: selected === 'third',
        rovingTabStop: buttons[2].tabIndex === 0,
        preventsNativeScroll: prevented,
        stopsGlobalShortcut: stopped,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });
    let prevented = false;
    viewer.dom.modal.classList.remove('open');
    viewer.dom.infoModal.classList.remove('open');
    viewer.handleKey({
        key: 'ArrowRight',
        target: { tagName: 'DIV', isContentEditable: false, closest() { return null; } },
        preventDefault() { prevented = true; },
    });
    assert.equal(viewer.state.currentFrameIdx, 1);
    assert.equal(prevented, true);
    summary.frameKeyboard = {
        selectedNextFrame: viewer.state.currentFrameIdx === 1,
        preventsNativeScroll: prevented,
    };
}

{
    const { viewer, document } = loadViewer({ clipCount: 4 });
    const items = [0, 1].map(idx => ({
        ...fakeElement(),
        dataset: { idx: String(idx) },
        closest(selector) {
            return selector === '.rv-filmstrip-item' ? this : null;
        },
    }));
    const filmstrip = fakeElement();
    filmstrip.children = items;
    filmstrip.querySelector = selector => {
        const match = selector.match(/data-idx="(\d+)"/);
        return match ? items[Number(match[1])] : null;
    };
    viewer.dom.filmstrip = filmstrip;
    viewer.dom.filterChips = [];
    viewer.bindFilmstripEvents();

    let prevented = false;
    let stopped = false;
    filmstrip.dispatch('keydown', {
        key: 'ArrowRight',
        target: items[0],
        preventDefault() { prevented = true; },
        stopPropagation() { stopped = true; },
    });

    assert.equal(viewer.state.currentFrameIdx, 1);
    assert.equal(document.activeElement, items[1]);
    assert.equal(prevented, true);
    assert.equal(stopped, true);
    summary.filmstripKeyboard = {
        selectedNextFrame: viewer.state.currentFrameIdx === 1,
        focusedSelection: document.activeElement === items[1],
        preventsNativeScroll: prevented,
        stopsGlobalShortcut: stopped,
    };
}

{
    const { viewer, storage, storageKey } = loadViewer({ clipCount: 4 });

    viewer.viewport.setManualAlignment(4, 5);
    assert.equal(viewer.dom.alignmentStatus.textContent, 'Aligned: custom +4x +5y');
    viewer.setRightClip(2);
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 2);
    assert.equal(viewer.state.alignX, 0);
    assert.equal(viewer.state.alignY, 0);
    assert.equal(viewer.dom.alignmentStatus.textContent, 'Aligned: none');

    viewer.viewport.setManualAlignment(-1, 8);
    viewer.setRightClip(1);
    assert.equal(viewer.state.alignX, 4);
    assert.equal(viewer.state.alignY, 5);
    assert.equal(viewer.dom.alignmentStatus.textContent, 'Aligned: custom +4x +5y');

    viewer.setRightClip(2);
    assert.equal(viewer.state.alignX, -1);
    assert.equal(viewer.state.alignY, 8);

    viewer.setRightClip(3);
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 3);
    assert.equal(viewer.state.alignX, 0);
    assert.equal(viewer.state.alignY, 0);

    viewer.viewport.setManualAlignment(21, -3);
    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 3);
    assert.equal(viewer.state.rightClipIdx, 0);
    assert.equal(viewer.state.alignX, 0);
    assert.equal(viewer.state.alignY, 0);

    viewer.viewport.setManualAlignment(-21, 3);
    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 3);
    assert.equal(viewer.state.alignX, 21);
    assert.equal(viewer.state.alignY, -3);

    viewer.setRightClip(2);
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 2);
    assert.equal(viewer.state.alignX, -1);
    assert.equal(viewer.state.alignY, 8);

    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 2);
    assert.equal(viewer.state.rightClipIdx, 0);
    assert.equal(viewer.state.alignX, 0);
    assert.equal(viewer.state.alignY, 0);

    viewer.viewport.setManualAlignment(12, 13);
    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 2);
    assert.equal(viewer.state.alignX, -1);
    assert.equal(viewer.state.alignY, 8);

    viewer.setRightClip(3);
    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 3);
    assert.equal(viewer.state.rightClipIdx, 0);
    assert.equal(viewer.state.alignX, -21);
    assert.equal(viewer.state.alignY, 3);

    const saved = persisted(storage, storageKey);
    assert.deepEqual(saved.pairAlignments['0:1'], {
        alignmentPreset: 'custom',
        alignX: 4,
        alignY: 5,
    });
    assert.deepEqual(saved.pairAlignments['0:2'], {
        alignmentPreset: 'custom',
        alignX: -1,
        alignY: 8,
    });
    assert.deepEqual(saved.pairAlignments['0:3'], {
        alignmentPreset: 'custom',
        alignX: 21,
        alignY: -3,
    });
    assert.deepEqual(saved.pairAlignments['2:0'], {
        alignmentPreset: 'custom',
        alignX: 12,
        alignY: 13,
    });
    assert.deepEqual(saved.pairAlignments['3:0'], {
        alignmentPreset: 'custom',
        alignX: -21,
        alignY: 3,
    });
    assert.equal(saved.alignX, undefined);
    assert.equal(saved.alignmentPreset, undefined);
    summary.pairSwitchFourClip = {
        finalPair: `${viewer.state.leftClipIdx}:${viewer.state.rightClipIdx}`,
        finalAlignment: [viewer.state.alignX, viewer.state.alignY],
        finalAlignmentStatus: viewer.dom.alignmentStatus.textContent,
        persistedPairKeys: Object.keys(saved.pairAlignments).sort(),
        persistedAlignments: {
            '0:1': [saved.pairAlignments['0:1'].alignX, saved.pairAlignments['0:1'].alignY],
            '0:2': [saved.pairAlignments['0:2'].alignX, saved.pairAlignments['0:2'].alignY],
            '0:3': [saved.pairAlignments['0:3'].alignX, saved.pairAlignments['0:3'].alignY],
            '2:0': [saved.pairAlignments['2:0'].alignX, saved.pairAlignments['2:0'].alignY],
            '3:0': [saved.pairAlignments['3:0'].alignX, saved.pairAlignments['3:0'].alignY],
        },
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });

    assert.equal(viewer.dom.alignmentStatus.textContent, 'Aligned: none');
    viewer.viewport.setAlignmentPreset('left-1');
    assert.equal(viewer.state.alignX, -1);
    assert.equal(viewer.state.alignY, 0);
    assert.equal(viewer.dom.alignmentStatus.textContent, 'Aligned: preset left 1px');
    viewer.viewport.setAlignmentPreset('none');
    assert.equal(viewer.dom.alignmentStatus.textContent, 'Aligned: none');
    summary.alignmentStatus = {
        neutral: 'Aligned: none',
        preset: 'Aligned: preset left 1px',
        reset: viewer.dom.alignmentStatus.textContent,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });

    viewer.setMode('overlay');
    viewer.state.activeClipIdx = viewer.state.rightClipIdx;
    viewer.viewport.setManualAlignment(9, -4);
    viewer.updateImages();
    assert.equal(viewer.dom.canvas.style.values['--align-x'], '9px');
    assert.equal(viewer.dom.canvas.style.values['--align-y'], '-4px');
    assert.equal(viewer.dom.leftLayer.classList.contains('rv-layer--aligned-active'), true);
    viewer.clearFrameImages();
    assert.equal(viewer.lens.transientClears, 1);
    assert.equal(viewer.dom.leftLayer.classList.contains('rv-layer--aligned-active'), false);
    assert.equal(viewer.dom.leftLayer.classList.contains('active'), false);
    viewer.state.activeClipIdx = viewer.state.leftClipIdx;
    viewer.updateImages();
    assert.equal(viewer.dom.leftLayer.classList.contains('rv-layer--aligned-active'), false);
    summary.singleModeAlignment = {
        mode: viewer.state.mode,
        canvasAlignX: viewer.dom.canvas.style.values['--align-x'],
        canvasAlignY: viewer.dom.canvas.style.values['--align-y'],
        alignedComparisonActive: true,
        baseClipUnshifted: true,
        emptyStateClearsAlignment: true,
        emptyStateClearsLensTransient: true,
    };
}

{
    const { viewer } = loadViewer({
        clipCount: 4,
        savedState: {
            mode: 'diff',
            leftClipIdx: 1,
            rightClipIdx: 0,
            pairAlignments: {
                '0:1': { alignmentPreset: 'custom', alignX: 6, alignY: 7 },
                '1:0': { alignmentPreset: 'custom', alignX: -6, alignY: -7 },
            },
        },
    });

    assert.equal(viewer.state.leftClipIdx, 1);
    assert.equal(viewer.state.rightClipIdx, 0);
    assert.equal(viewer.state.alignX, -6);
    assert.equal(viewer.state.alignY, -7);

    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 1);
    assert.equal(viewer.state.alignX, 6);
    assert.equal(viewer.state.alignY, 7);
    summary.directionalFourClip = {
        swappedPair: `${viewer.state.leftClipIdx}:${viewer.state.rightClipIdx}`,
        swappedAlignment: [viewer.state.alignX, viewer.state.alignY],
        reversePairAlignment: [-6, -7],
    };
}

{
    const { viewer, storage, storageKey } = loadViewer({
        clipCount: 4,
        savedState: {
            paletteOrientation: 'vertical',
        },
    });

    assert.equal(viewer.state.paletteOrientation, 'vertical');
    viewer.setPaletteOrientation('horizontal');
    assert.equal(viewer.state.paletteOrientation, 'horizontal');
    assert.equal(viewer.dom.viewportPalette.getAttribute('data-orientation'), 'horizontal');
    assert.equal(viewer.dom.btnPaletteOrientation.textContent, '↔');

    viewer.setPaletteOrientation('vertical');
    assert.equal(viewer.state.paletteOrientation, 'vertical');
    assert.equal(viewer.dom.viewportPalette.getAttribute('data-orientation'), 'vertical');
    assert.equal(viewer.dom.btnPaletteOrientation.textContent, '↕');

    const { viewer: viewer2 } = loadViewer({
        clipCount: 4,
        savedState: {
            paletteOrientation: 'invalid_mode',
        },
    });
    assert.equal(viewer2.state.paletteOrientation, 'horizontal');

    const saved = persisted(storage, storageKey);
    summary.paletteOrientationState = {
        restoredOrientation: 'vertical',
        savedOrientation: saved.paletteOrientation,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });

    viewer.dom.filterChips = [
        { ...fakeElement(), textContent: 'All (10)', dataset: { categoryKey: '__fc_all__' } },
        { ...fakeElement(), textContent: 'Dark (3)', dataset: { categoryKey: 'dark' } },
        { ...fakeElement(), textContent: 'Motion', dataset: { categoryKey: 'motion' } },
    ];

    viewer.updateFilterChips();
    assert.equal(viewer.dom.activeFilterBadge.hidden, true);

    viewer.state.activeCategoryKey = 'dark';
    viewer.updateFilterChips();
    assert.equal(viewer.dom.activeFilterBadge.hidden, false);
    assert.equal(viewer.dom.activeFilterBadge.textContent, 'Filtered: Dark');

    viewer.state.activeCategoryKey = 'motion';
    viewer.updateFilterChips();
    assert.equal(viewer.dom.activeFilterBadge.hidden, false);
    assert.equal(viewer.dom.activeFilterBadge.textContent, 'Filtered: Motion');

    viewer.state.activeCategoryKey = '__fc_all__';
    viewer.updateFilterChips();
    assert.equal(viewer.dom.activeFilterBadge.hidden, true);
    assert.equal(viewer.dom.activeFilterBadge.textContent, '');

    summary.activeFilterBadge = {
        badgeHiddenByDefault: true,
        badgeTextFilteredDark: 'Filtered: Dark',
        badgeTextFilteredMotion: 'Filtered: Motion',
        badgeClearedToHidden: true,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 2 });
    viewer.pointerInteraction = {
        isPanning: true,
        activePointerId: 7,
        lastPanX: 10,
        lastPanY: 20,
        panMoved: false,
        panBasis: null,
    };
    viewer.state.panX = 3;
    viewer.state.panY = 4;
    viewer.viewport.setPan = function setPanWithoutLayout(x, y) {
        this.viewer.state.panX = x;
        this.viewer.state.panY = y;
    };

    assert.equal(
        viewer.viewport.updatePanFromPointer({ pointerId: 7, clientX: 16, clientY: 20 }),
        true,
    );
    assert.deepEqual([viewer.state.panX, viewer.state.panY], [9, 4]);
    assert.equal(viewer.state.panY, 4);
    assert.equal(viewer.pointerInteraction.panMoved, true);
    let cycleCount = 0;
    viewer.cycleClip = () => { cycleCount += 1; };
    viewer.persistViewportState = () => true;
    viewer.state.mode = 'overlay';
    viewer.pointerInteraction = {
        isDragging: false,
        isPanning: true,
        activePointerId: 8,
        lastPanX: 20,
        lastPanY: 30,
        panMoved: false,
        panBasis: null,
        pointerPositions: new Map([[8, { x: 20, y: 30, type: 'touch' }]]),
        capturedPointerIds: new Set(),
        pinchActive: false,
        lensPointHandled: true,
        lensTouchStart: { pointerId: 8, clientX: 20, clientY: 30 },
    };
    viewer.viewport.stopPointerInteraction({ pointerId: 8, clientX: 20, clientY: 30 });
    assert.equal(cycleCount, 0);
    summary.lensPanIndependence = {
        panAppliedWithoutInspectorGestureGate: true,
        panMovedRecorded: true,
        touchLensTapDidNotCycle: true,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 2 });
    viewer.lens.state.report.enabled = true;
    viewer.lens.state.point = { u: 0.25, v: 2 / 9 };
    viewer.lens.refreshes = 0;
    viewer.lens.syncs = 0;
    const touchSample = { ...viewer.lens.state.point };
    viewer.state.panX = 12;
    viewer.state.panY = -7;
    viewer.viewport.applyPan();
    viewer.viewport.applyZoom(1.75, { clampPan: false });
    viewer.viewport.applyAlignment();
    assert.deepEqual(viewer.lens.state.point, touchSample);
    assert.equal(viewer.lens.refreshes, 3);
    assert.equal(viewer.lens.syncs, 0);
    summary.lensLayoutRefresh = {
        touchPanPreservedSample: true,
        pinchZoomPreservedSample: true,
        alignmentPreservedSample: true,
        contextSyncNotUsed: true,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });
    const routed = {};
    for (const mode of ['slider', 'overlay', 'diff', 'blink', 'grid']) {
        let panStarts = 0;
        let panMoves = 0;
        let sliderMoves = 0;
        viewer.state.mode = mode;
        viewer.pointerInteraction = {
            isDragging: false,
            isPanning: false,
            capturedPointerIds: new Set(),
        };
        viewer.viewport.startPanFromPointer = () => { panStarts += 1; };
        viewer.viewport.updatePanFromPointer = () => { panMoves += 1; return true; };
        viewer.viewport.updateSliderFromPointer = () => { sliderMoves += 1; };
        viewer.viewport.captureStagePointer = () => {};
        viewer.startDeferredViewportGesture(
            { pointerId: 1, pointerType: 'touch', button: 0, clientX: 30, clientY: 40 },
            { clientX: 10, clientY: 20 },
        );
        routed[mode] = { panStarts, panMoves, sliderMoves };
    }
    assert.deepEqual(routed.slider, { panStarts: 0, panMoves: 0, sliderMoves: 1 });
    for (const mode of ['overlay', 'diff', 'blink', 'grid']) {
        assert.deepEqual(routed[mode], { panStarts: 1, panMoves: 1, sliderMoves: 0 });
    }
    assert.equal(viewer.isViewerChromeEvent({
        target: { closest(selector) { return selector.includes('.rv-lens') ? this : null; } },
    }), true);
    assert.equal(viewer.isViewerChromeEvent({
        target: {
            closest(selector) {
                return selector.split(', ').includes('.rv-lens-settings') ? this : null;
            },
        },
    }), true);
    assert.equal(viewer.isViewerChromeEvent({ target: { closest() { return null; } } }), false);
    let resets = 0;
    let zooms = 0;
    let pans = 0;
    const chromeTarget = {
        closest(selector) {
            return selector.split(', ').includes('.rv-lens-settings') ? this : null;
        },
    };
    viewer.viewport.resetViewport = () => { resets += 1; };
    viewer.viewport.zoomAtPoint = () => { zooms += 1; };
    viewer.viewport.panByPixels = () => { pans += 1; };
    viewer.state.mode = 'slider';
    viewer.handleViewportDoubleClick({ target: chromeTarget, preventDefault() {} });
    viewer.handleViewportWheel({
        target: chromeTarget,
        preventDefault() {},
        shiftKey: false,
        deltaX: 0,
        deltaY: -1,
        clientX: 10,
        clientY: 10,
    });
    assert.deepEqual([resets, zooms, pans], [0, 0, 0]);
    viewer.handleViewportDoubleClick({ target: { closest() { return null; } }, preventDefault() {} });
    viewer.handleViewportWheel({
        target: { closest() { return null; } },
        preventDefault() {},
        shiftKey: false,
        deltaX: 0,
        deltaY: -1,
        clientX: 10,
        clientY: 10,
    });
    assert.deepEqual([resets, zooms, pans], [1, 1, 0]);
    summary.deferredTouchOwnership = {
        sliderRetainsRevealDrag: true,
        allPanModesRetainPanDrag: true,
        viewerChromeRecognized: true,
        chromeWheelAndDoubleClickIsolated: true,
    };
}

{
    const { viewer } = loadViewer({
        clipCount: 4,
        savedState: { mode: 'grid' },
    });
    assert.equal(viewer.validPayloadMode('grid'), false);
    assert.equal(viewer.validMode('grid'), true);
    assert.equal(viewer.state.mode, 'grid');
    summary.gridModeBoundary = {
        publicPayloadRejected: true,
        internalStoredModeRestored: true,
    };
}

{
    const { viewer, reviewMetrics } = loadViewer({
        clipCount: 4,
        savedState: { inspectorOpen: false, inspectorTab: 'review' },
    });
    assert.equal(reviewMetrics.creates, 0);
    viewer.setInspectorOpen(true, { focus: false, save: false });
    assert.deepEqual(reviewMetrics, { creates: 1, binds: 1, renders: 1 });
    summary.lazyReviewController = { opensOnFirstVisibleUse: true, createsOnce: true };
}

console.log(JSON.stringify(summary));
