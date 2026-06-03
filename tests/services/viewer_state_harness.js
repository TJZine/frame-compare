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

let activeDocument = null;

function payloadWithClipCount(clipCount) {
    const clips = Array.from({ length: clipCount }, (_, idx) => ({
        name: `clip-${idx + 1}`,
        label: `Clip ${idx + 1}`,
        frame_count: 100,
        resolution: [1920, 1080],
        fps: 24,
        hdr: false,
    }));
    return {
        version: '1.0',
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
            detail: `Source frame ${number}`,
            category: 'selected',
            images: clips.map((clip) => ({
                clip: clip.name,
                src: `${clip.name}/${number}.png`,
            })),
        })),
    };
}

function fakeElement() {
    const classes = new Set();
    const attributes = new Map();
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
        focus() {
            if (activeDocument) activeDocument.activeElement = this;
        },
        replaceChildren(...children) {
            this.children = children;
        },
        querySelectorAll(selector) {
            if (selector === '.rv-inspector-clip-heading span') {
                return [fakeElement(), fakeElement()];
            }
            if (selector === 'dd') {
                return [fakeElement(), fakeElement(), fakeElement(), fakeElement()];
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
    const script = `${fs.readFileSync(viewerPath, 'utf8')}\nglobalThis.__ReportViewer = ReportViewer;`;
    vm.runInNewContext(script, context, { filename: viewerPath });

    const viewer = context.__ReportViewer;
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
        fitBtns: ['actual', 'width', 'height', 'fill'].map((fit) => ({
            ...fakeElement(),
            dataset: { fit },
        })),
        alignmentPreset: fakeElement(),
        alignX: fakeElement(),
        alignY: fakeElement(),
        btnAlignToggle: fakeElement(),
        alignmentStatus: fakeElement(),
        btnInfo: fakeElement(),
        inspector: fakeElement(),
        btnInspectorClose: fakeElement(),
        inspectorTabs: ['frame', 'clips', 'align', 'export'].map((tab) => ({
            ...fakeElement(),
            dataset: { inspectorTab: tab },
        })),
        inspectorPanels: ['frame', 'clips', 'align', 'export'].map((tab) => ({
            ...fakeElement(),
            id: `inspector-panel-${tab}`,
        })),
        inspectorFrameLabel: fakeElement(),
        inspectorFrameNumber: fakeElement(),
        inspectorFrameCategory: fakeElement(),
        inspectorFrameDetail: fakeElement(),
        inspectorFramePosition: fakeElement(),
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
        btnFocusMode: fakeElement(),
        focusHudFrame: fakeElement(),
        focusHudMode: fakeElement(),
        focusHudPair: fakeElement(),
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
        activeFilterBadge: fakeElement(),
        alignPopover: {
            ...fakeElement(),
            hidden: true,
        },
    };
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
    viewer.render = function renderStateOnly() {
        this.applyAlignment();
        this.persistViewportState();
    };

    if (savedState !== null) {
        storage.set(viewer.state.storageKey, JSON.stringify(savedState));
    }

    viewer.applyDefaultSelection();
    viewer.restorePersistedState();
    viewer.applyAlignment();
    return { viewer, storage, storageKey: viewer.state.storageKey, document: context.document };
}

function persisted(storage, storageKey) {
    return JSON.parse(storage.get(storageKey));
}

function keyboardEvent(key) {
    return {
        key,
        target: { tagName: 'DIV', isContentEditable: false, closest() { return null; } },
        defaultPrevented: false,
        preventDefault() {
            this.defaultPrevented = true;
        },
        stopPropagation() {},
    };
}

const summary = {};

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
    const { viewer, storage, storageKey, document } = loadViewer({
        clipCount: 4,
        savedState: {
            currentFrameIdx: 1,
            inspectorOpen: true,
            inspectorTab: 'align',
            blinkIntervalMs: 1200,
            blinkPaused: true,
            focusMode: true,
        },
    });

    assert.equal(viewer.state.currentFrameIdx, 1);
    assert.equal(viewer.state.inspectorOpen, true);
    assert.equal(viewer.state.inspectorTab, 'align');
    assert.equal(viewer.state.blinkIntervalMs, 1200);
    assert.equal(viewer.state.blinkPaused, false);
    assert.equal(viewer.state.focusMode, false);

    viewer.setInspectorTab('export');
    const focusables = viewer.dom.inspectorFocusables;
    viewer.dom.btnInspectorClose.setAttribute('tabindex', '0');
    document.activeElement = viewer.dom.btnInfo;
    viewer.setInspectorOpen(true);
    assert.equal(document.activeElement, viewer.dom.inspectorTabs[0]);
    assert.equal(viewer.dom.inspector.inert, false);
    assert.equal(viewer.dom.btnInspectorClose.getAttribute('tabindex'), '0');
    viewer.setInspectorOpen(false);
    assert.equal(document.activeElement, viewer.dom.btnInfo);
    assert.equal(viewer.state.inspectorRestoreFocus, null);
    assert.equal(viewer.dom.inspector.inert, true);
    focusables.forEach((element) => {
        assert.equal(element.getAttribute('tabindex'), '-1');
    });
    viewer.setInspectorOpen(true);
    assert.equal(viewer.dom.inspector.inert, false);
    assert.equal(viewer.dom.btnInspectorClose.getAttribute('tabindex'), '0');
    viewer.dom.inspectorTabs.forEach((element) => {
        assert.equal(element.getAttribute('tabindex'), null);
    });
    viewer.setInspectorOpen(false);
    viewer.setBlinkIntervalMs(300);
    viewer.setBlinkPaused(true);
    viewer.setFocusMode(true);
    const saved = persisted(storage, storageKey);
    assert.equal(saved.currentFrameIdx, 1);
    assert.equal(saved.inspectorOpen, false);
    assert.equal(saved.inspectorTab, 'export');
    assert.equal(saved.blinkIntervalMs, 300);
    assert.equal(saved.blinkPaused, undefined);
    assert.equal(saved.focusMode, undefined);
    summary.inspectorBlinkFocusState = {
        currentFrameIdx: saved.currentFrameIdx,
        inspectorOpen: saved.inspectorOpen,
        inspectorTab: saved.inspectorTab,
        blinkIntervalMs: saved.blinkIntervalMs,
        blinkPausedPersisted: Object.hasOwn(saved, 'blinkPaused'),
        focusModePersisted: Object.hasOwn(saved, 'focusMode'),
        focusModeActive: viewer.state.focusMode,
        closedInspectorInert: viewer.dom.inspector.inert,
        closedInspectorTabIndex: viewer.dom.btnInspectorClose.getAttribute('tabindex'),
        restoredFocusToInfo: document.activeElement === viewer.dom.btnInfo,
        clearedRestoreFocus: viewer.state.inspectorRestoreFocus === null,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });

    viewer.setInspectorOpen(true);
    viewer.setAlignmentPopoverOpen(true, { restoreFocus: false });
    const firstEscape = keyboardEvent('Escape');
    viewer.handleKey(firstEscape);
    assert.equal(firstEscape.defaultPrevented, true);
    assert.equal(viewer.state.inspectorOpen, false);
    assert.equal(viewer.isAlignmentPopoverOpen(), true);

    const secondEscape = keyboardEvent('Escape');
    viewer.handleKey(secondEscape);
    assert.equal(secondEscape.defaultPrevented, true);
    assert.equal(viewer.isAlignmentPopoverOpen(), false);

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
        inspectorClosedBeforeAlignment: true,
        legacyInfoModalWins: true,
        alignmentStillOpenAfterInspectorEscape: true,
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });

    viewer.setInspectorOpen(true);
    assert.equal(viewer.state.inspectorOpen, true);
    assert.equal(viewer.dom.inspector.inert, false);
    viewer.setFocusMode(true);
    assert.equal(viewer.state.focusMode, true);
    assert.equal(viewer.state.inspectorOpen, false);
    assert.equal(viewer.dom.inspector.inert, true);

    const escape = keyboardEvent('Escape');
    viewer.handleKey(escape);
    assert.equal(escape.defaultPrevented, true);
    assert.equal(viewer.state.focusMode, false);
    assert.equal(viewer.state.inspectorOpen, false);
    assert.equal(viewer.isInspectorVisible(), false);

    summary.focusModeInspectorClose = {
        inspectorClosedOnEntry: true,
        inspectorStayedClosedAfterEscape: true,
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
    const { viewer } = loadViewer({ clipCount: 4 });
    viewer.state.mode = 'slider';
    viewer.state.zoom = 2;
    viewer.state.revealPercent = 25;
    viewer.dom.canvas.offsetWidth = 0;
    viewer.dom.canvas.clientWidth = 0;
    viewer.dom.canvas.getBoundingClientRect = () => ({ width: 800 });
    viewer.dom.labelLeft.offsetWidth = 90;
    viewer.dom.labelRight.offsetWidth = 80;

    assert.equal(viewer.untransformedCanvasWidth(), 400);
    const positions = viewer.smartLabelPositions(400, 90, 80);
    assert.equal(positions.leftX, 290);
    assert.equal(positions.rightX, 310);
    viewer.updateSmartStageLabels();
    assert.equal(viewer.dom.canvas.style.values['--label-left-x'], '290px');
    assert.equal(viewer.dom.canvas.style.values['--label-right-x'], '310px');
    summary.smartLabelGeometry = {
        untransformedWidth: viewer.untransformedCanvasWidth(),
        labelLeftX: viewer.dom.canvas.style.values['--label-left-x'],
        labelRightX: viewer.dom.canvas.style.values['--label-right-x'],
    };
}

{
    const { viewer } = loadViewer({ clipCount: 4 });

    viewer.state.activeClipIdx = viewer.state.leftClipIdx;
    const leftActiveLabels = viewer.blinkStageLabels('Clip 1', 'Clip 2');
    assert.equal(leftActiveLabels.left, 'Clip 1');
    assert.equal(leftActiveLabels.right, '');

    viewer.state.activeClipIdx = viewer.state.rightClipIdx;
    const rightActiveLabels = viewer.blinkStageLabels('Clip 1', 'Clip 2');
    assert.equal(rightActiveLabels.left, '');
    assert.equal(rightActiveLabels.right, 'Clip 2');
    summary.blinkLabels = {
        leftActive: leftActiveLabels,
        rightActive: rightActiveLabels,
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
    const { viewer, storage, storageKey } = loadViewer({ clipCount: 4 });

    viewer.setManualAlignment(4, 5);
    assert.equal(viewer.dom.alignmentStatus.textContent, 'Aligned: custom +4x +5y');
    viewer.setRightClip(2);
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 2);
    assert.equal(viewer.state.alignX, 0);
    assert.equal(viewer.state.alignY, 0);
    assert.equal(viewer.dom.alignmentStatus.textContent, 'Aligned: none');

    viewer.setManualAlignment(-1, 8);
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

    viewer.setManualAlignment(21, -3);
    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 3);
    assert.equal(viewer.state.rightClipIdx, 0);
    assert.equal(viewer.state.alignX, 0);
    assert.equal(viewer.state.alignY, 0);

    viewer.setManualAlignment(-21, 3);
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

    viewer.setManualAlignment(12, 13);
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
    viewer.setAlignmentPreset('left-1');
    assert.equal(viewer.state.alignX, -1);
    assert.equal(viewer.state.alignY, 0);
    assert.equal(viewer.dom.alignmentStatus.textContent, 'Aligned: preset left 1px');
    viewer.setAlignmentPreset('none');
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
    viewer.setManualAlignment(9, -4);
    viewer.updateImages();
    assert.equal(viewer.dom.canvas.style.values['--align-x'], '9px');
    assert.equal(viewer.dom.canvas.style.values['--align-y'], '-4px');
    assert.equal(viewer.dom.leftLayer.classList.contains('rv-layer--aligned-active'), true);
    viewer.clearFrameImages();
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

console.log(JSON.stringify(summary));
