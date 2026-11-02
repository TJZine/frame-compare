const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { domMechanics } = require('./dom_fixture');

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
            tonemap: null,
        },
        active_picture: null,
    }));
    return {
        version: '1.3',
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

function createElementFactory(documentFor) {
    return function makeElement() {
        const classes = new Set();
        const attributes = new Map();
        let definitionValues = null;
        const inspectorPrimary = { value: null };
        return {
            ...domMechanics(documentFor),
            value: '',
            textContent: '',
            disabled: false,
            hidden: false,
            inert: false,
            tabIndex: 0,
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
                // HTMLImageElement.src assignments reflect into the src attribute.
                if (name === 'src') return this.src ?? null;
                return attributes.has(name) ? attributes.get(name) : null;
            },
            removeAttribute(name) {
                attributes.delete(name);
                delete this[name];
            },
            closest() {
                return null;
            },
            scrollIntoView() {},
            querySelector(selector) {
                if (selector === '.rv-inspector-clip-primary') {
                    if (!inspectorPrimary.value) inspectorPrimary.value = makeElement();
                    return inspectorPrimary.value;
                }
                return null;
            },
            querySelectorAll(selector) {
                if (selector === '.rv-inspector-clip-heading span') {
                    return [makeElement(), makeElement()];
                }
                if (selector === 'dd') {
                    if (definitionValues === null) {
                        definitionValues = Array.from({ length: 7 }, () => makeElement());
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
    };
}

function renderedText(element) {
    if (element.children.length > 0) {
        return element.children.map(child => child.textContent).join('');
    }
    return element.textContent;
}

function loadViewer({ clipCount, savedState = null }) {
    const document = { activeElement: null };
    const makeElement = createElementFactory(() => document);
    const storage = new Map();
    const deferredImages = [];
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
        Image: class DeferredImage {
            constructor() {
                this.listeners = new Map();
                this._src = '';
                deferredImages.push(this);
            }

            get src() {
                return this._src;
            }

            set src(value) {
                this._src = String(value);
            }

            addEventListener(type, listener) {
                const registered = this.listeners.get(type) || [];
                registered.push(listener);
                this.listeners.set(type, registered);
            }

            trigger(type) {
                for (const listener of this.listeners.get(type) || []) listener();
            }
        },
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
        document: Object.assign(document, {
            body: makeElement(),
            addEventListener() {},
            createElement(tagName) {
                return { ...makeElement(), tagName: String(tagName || '').toUpperCase() };
            },
            createTextNode(text) {
                return { nodeType: 3, textContent: String(text) };
            },
        }),
        window: {
            localStorage: storageApi,
            matchMedia() {
                return { matches: false };
            },
            rafQueue: [],
            requestAnimationFrame(callback) {
                this.rafQueue.push(callback);
                return this.rafQueue.length;
            },
            cancelAnimationFrame(id) {
                this.rafQueue[id - 1] = null;
            },
            timeoutQueue: [],
            setTimeout(callback) {
                this.timeoutQueue.push(callback);
                return this.timeoutQueue.length;
            },
            clearTimeout(id) {
                this.timeoutQueue[id - 1] = null;
            },
        },
    };
    const script = `${fs.readFileSync(viewerFormatPath, 'utf8')}\n${fs.readFileSync(lensPath, 'utf8')}\n${fs.readFileSync(inspectorPath, 'utf8')}\n${fs.readFileSync(viewportPath, 'utf8')}\n${fs.readFileSync(viewerPath, 'utf8')}\nglobalThis.__ViewerFormat = ViewerFormat;\nglobalThis.__Lens = Lens;\nglobalThis.__Inspector = Inspector;\nglobalThis.__Viewport = Viewport;\nglobalThis.__ReportViewer = ReportViewer;`;
    vm.runInNewContext(script, context, { filename: viewerPath });
    assert.equal(typeof context.__Lens.create, 'function');

    const viewer = context.__ReportViewer;
    viewer.inspector = context.__Inspector.create(viewer);
    viewer.viewport = context.__Viewport.create(viewer);
    const payload = viewer.normalizePayload(payloadWithClipCount(clipCount));
    viewer.state.data = payload;
    viewer.state.mode = payload.default_mode;
    viewer.state.storageKey = viewer.viewerStorageKey();
    viewer.state.currentFrameIdx = 0;
    viewer.state.leftClipIdx = 0;
    viewer.state.rightClipIdx = 1;
    viewer.state.activeClipIdx = 0;
    viewer.state.fitMode = 'actual';
    viewer.state.zoom = 1;
    viewer.state.panX = 0;
    viewer.state.panY = 0;
    viewer.state.revealPercent = 50;

    viewer.state.pairAlignments = {};
    viewer.state.rawAlignX = null;
    viewer.state.rawAlignY = null;
    viewer.dom = {
        stage: {
            ...makeElement(),
            getBoundingClientRect() {
                return { width: 1920, height: 1080 };
            },
        },
        canvas: makeElement(),
        sizerImg: {
            naturalWidth: 1920,
            naturalHeight: 1080,
            ...makeElement(),
            getBoundingClientRect() {
                return { width: 1920, height: 1080 };
            },
        },
        leftImg: makeElement(),
        rightImg: makeElement(),
        labelLeft: makeElement(),
        labelRight: makeElement(),
        emptyState: makeElement(),
        status: makeElement(),
        leftLayer: makeElement(),
        rightLayer: makeElement(),
        zoomRange: makeElement(),
        zoomVal: makeElement(),
        modeBtns: ['slider', 'overlay', 'diff', 'blink'].map((mode) => ({
            ...makeElement(),
            dataset: { mode },
        })),
        pairControls: makeElement(),
        activeControls: makeElement(),
        leftSelect: makeElement(),
        rightSelect: makeElement(),
        activeSelect: makeElement(),
        btnSwapClips: makeElement(),
        fitBtns: ['actual', 'height'].map((fit) => ({
            ...makeElement(),
            dataset: { fit },
        })),
        alignmentPreset: makeElement(),
        alignX: makeElement(),
        alignY: makeElement(),
        btnAlignmentReset: makeElement(),
        btnAlignToggle: makeElement(),
        alignmentStatus: makeElement(),
        btnInfo: makeElement(),
        btnInspector: makeElement(),
        inspector: makeElement(),
        btnInspectorClose: makeElement(),
        inspectorTabs: ['frame', 'clips', 'align', 'review'].map((tab) => ({
            ...makeElement(),
            dataset: { inspectorTab: tab },
        })),
        inspectorPanels: ['frame', 'clips', 'align', 'review'].map((tab) => ({
            ...makeElement(),
            id: `inspector-panel-${tab}`,
        })),
        inspectorFrameIdentity: makeElement(),
        inspectorFrameDetailRow: makeElement(),
        inspectorFrameDetail: makeElement(),
        inspectorFramePosition: makeElement(),
        inspectorSourceFrames: makeElement(),
        inspectorClipsShared: makeElement(),
        inspectorClips: makeElement(),
        inspectorAlignPair: makeElement(),
        inspectorAlignPreset: makeElement(),
        inspectorAlignX: makeElement(),
        inspectorAlignY: makeElement(),
        btnInspectorResetCurrentAlign: makeElement(),
        btnInspectorResetAllAlign: makeElement(),
        modal: makeElement(),
        infoModal: makeElement(),
        btnHelp: makeElement(),
        btnCloseHelp: makeElement(),
        btnCloseInfo: makeElement(),
        blinkControls: makeElement(),
        btnBlinkPause: makeElement(),
        blinkSpeed: makeElement(),
        blinkStatus: makeElement(),
        viewportPalette: makeElement(),
        btnPaletteOrientation: makeElement(),
        bottomPanel: {
            ...makeElement(),
            dataset: { filmstripEnabled: 'true' },
        },
        btnFilmstripToggle: makeElement(),
        filmstripSizeBtns: ['compact', 'normal', 'large'].map((size) => ({
            ...makeElement(),
            dataset: { filmstripSize: size },
        })),
        filmstrip: makeElement(),
        activeFilterBadge: makeElement(),
        alignPopover: {
            ...makeElement(),
            hidden: true,
        },
        lensSettingsPopover: {
            ...makeElement(),
            hidden: true,
        },
    };
    viewer.bindDialogEvents();
    viewer.dom.btnInfo.setAttribute('aria-label', 'Report information');
    viewer.dom.btnInfo.setAttribute('title', 'Report information');
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
        this.persistViewerState();
    };

    if (savedState !== null) {
        storage.set(viewer.state.storageKey, JSON.stringify(savedState));
    }

    viewer.applyDefaultSelection();
    viewer.restorePersistedState();
    viewer.viewport.applyAlignment();
    return {
        viewer,
        element: makeElement,
        format: context.__ViewerFormat,
        lensFactory: context.__Lens,
        storage,
        storageKey: viewer.state.storageKey,
        document: context.document,
        window: context.window,
        deferredImages,
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

async function assertDeferredDiffCannotCommitAfterGridNavigation() {
    const { element: makeElement, viewer, window, deferredImages } = loadViewer({ clipCount: 2 });
    viewer.dom.currentFrameLabel = makeElement();
    viewer.dom.currentFrameCategoryDivider = makeElement();
    viewer.dom.currentFrameCategory = makeElement();

    const gridEvents = { active: false, renders: 0 };
    viewer.gridView = {
        setActive(active) {
            gridEvents.active = active;
        },
        render() {
            gridEvents.renders += 1;
            viewer.updateCurrentFrameMetadata(viewer.currentFrame());
        },
        clear() {},
    };
    viewer.render = function renderImageStateTest() {
        this.updateImages();
    };

    viewer.state.mode = 'diff';
    viewer.updateImages();
    assert.equal(deferredImages.length, 2);
    const oldFrameSources = deferredImages.map(image => image.src);

    viewer.setMode('grid');
    viewer.setFrame(1);
    assert.equal(gridEvents.active, true);
    assert.equal(gridEvents.renders, 2);
    assert.equal(viewer.dom.currentFrameLabel.textContent, 'Frame 20');
    assert.equal(viewer.dom.currentFrameCategory.textContent, 'Selected');

    deferredImages.forEach(image => image.trigger('load'));
    await new Promise(resolve => setImmediate(resolve));
    window.rafQueue.splice(0).forEach(callback => callback?.());

    assert.deepEqual(deferredImages.map(image => image.src), oldFrameSources);
    assert.equal(viewer.dom.leftImg.src, undefined);
    assert.equal(viewer.dom.rightImg.src, undefined);
    assert.deepEqual(viewer.dom.labelLeft.children, []);
    assert.deepEqual(viewer.dom.labelRight.children, []);
    assert.equal(viewer.dom.currentFrameLabel.textContent, 'Frame 20');
    assert.equal(viewer.dom.currentFrameCategory.textContent, 'Selected');

}

async function assertMainImageUnavailableState() {
    const modes = [
        { mode: 'slider', failedSide: 'right', clipIndex: 1 },
        { mode: 'overlay', failedSide: 'left', clipIndex: 0 },
        { mode: 'diff', failedSide: 'right', clipIndex: 1 },
        { mode: 'blink', failedSide: 'right', clipIndex: 1 },
    ];

    for (const { mode, failedSide, clipIndex } of modes) {
        const { viewer, deferredImages, window, document } = loadViewer({ clipCount: 2 });
        viewer.state.mode = mode;
        viewer.updateImages();
        if (mode === 'diff') {
            deferredImages.forEach(image => image.trigger('load'));
            await new Promise(resolve => setImmediate(resolve));
            window.rafQueue.splice(0).forEach(callback => callback?.());
        }

        const failedImage = viewer.dom[`${failedSide}Img`];
        const failedLayer = viewer.dom[`${failedSide}Layer`];
        const label = viewer.state.data.clips[clipIndex].display.micro;
        failedImage.dispatch('error');

        assert.equal(viewer.dom.emptyState.hidden, false);
        assert.equal(renderedText(viewer.dom.emptyState), `${label} image unavailableRetry`);
        assert.equal(viewer.dom.status.textContent, `${label} image unavailable`);
        assert.equal(viewer.dom.status.dataset.tone, 'error');
        assert.equal(failedImage.hidden, true);
        assert.equal(failedLayer.dataset.status, 'error');
        assert.equal(viewer.dom[`${failedSide === 'left' ? 'labelLeft' : 'labelRight'}`].children.length > 0, true);

        const retryButton = viewer.dom.emptyState.children.find(child => child.tagName === 'BUTTON');
        assert.equal(retryButton.textContent, 'Retry');
        assert.equal(retryButton.getAttribute('aria-label'), `Retry ${label} image`);
        if (mode === 'blink') {
            const failedRequest = viewer.state.mainImageRequests[failedSide];
            const staleError = failedRequest.onError;
            // Browser-complete failed images synchronously report failure on each install.
            viewer.dom.leftImg.complete = true;
            viewer.dom.leftImg.naturalWidth = 1;
            failedImage.complete = true;
            failedImage.naturalWidth = 0;
            failedImage.naturalHeight = 0;
            let statusWrites = 0;
            const statusText = viewer.dom.status.textContent;
            Object.defineProperty(viewer.dom.status, 'textContent', {
                get: () => statusText,
                set: () => { statusWrites += 1; },
                configurable: true,
            });
            retryButton.focus();
            viewer.startBlink();
            const before = viewer.state.activeClipIdx;
            viewer.state.blinkInterval.callback();
            assert.notEqual(viewer.state.activeClipIdx, before);
            assert.equal(viewer.dom.emptyState.children[1], retryButton);
            assert.equal(document.activeElement, retryButton);
            assert.equal(statusWrites, 0);
            assert.notEqual(viewer.state.mainImageRequests[failedSide], failedRequest);
            staleError();
            assert.equal(viewer.dom.emptyState.children[1], retryButton);
            viewer.setBlinkPaused(true);
            const paused = viewer.state.activeClipIdx;
            viewer.state.blinkInterval.callback();
            assert.equal(viewer.state.activeClipIdx, paused);
            Object.defineProperty(viewer.dom.status, 'textContent', {
                value: statusText, writable: true, configurable: true,
            });
            failedImage.complete = false;

        }
        retryButton.dispatch('click', { stopPropagation() {} });
        assert.equal(viewer.state.mainImageRequests[failedSide].attempt, 1);
        // Retrying resource I/O must not wait for a rendered animation frame.
        window.timeoutQueue.splice(0).forEach(callback => callback?.());
        assert.equal(failedImage.getAttribute('src'), viewer.state.mainImageRequests[failedSide].src);
        failedImage.dispatch('load');
        assert.equal(viewer.dom.emptyState.hidden, true);
        assert.equal(viewer.dom.status.hidden, true);
        assert.equal(failedImage.hidden, false);
        assert.equal(failedLayer.dataset.status, 'ready');

    }

    {
        const { viewer, window } = loadViewer({ clipCount: 2 });
        viewer.state.mode = 'blink';
        viewer.updateImages();
        viewer.dom.leftImg.dispatch('error');
        const oldButton = viewer.dom.emptyState.children[1];
        viewer.state.currentFrameIdx = 1;
        viewer.updateImages();
        viewer.dom.leftImg.dispatch('error');
        const newButton = viewer.dom.emptyState.children[1];
        assert.notEqual(newButton, oldButton);
        oldButton.dispatch('click', { stopPropagation() {} });
        assert.equal(viewer.state.mainImageRequests.left.attempt, 0);
        newButton.dispatch('click', { stopPropagation() {} });
        assert.equal(viewer.state.mainImageRequests.left.attempt, 1);
        assert.equal(viewer.dom.sizerImg.getAttribute('src'), null);
        window.timeoutQueue.splice(0).forEach(callback => callback?.());
        assert.equal(viewer.dom.sizerImg.src, viewer.state.data.frames[1].images[0].src);
        viewer.dom.leftImg.dispatch('error');
        viewer.dom.emptyState.children[1].dispatch('click', { stopPropagation() {} });
        viewer.state.currentFrameIdx = 0;
        viewer.updateImages();
        window.timeoutQueue.splice(0).forEach(callback => callback?.());
        assert.equal(viewer.dom.leftImg.src, viewer.state.data.frames[0].images[0].src);
        assert.equal(viewer.dom.sizerImg.src, viewer.state.data.frames[0].images[0].src);

    }

    {
        const { viewer } = loadViewer({ clipCount: 2 });
        viewer.state.mode = 'slider';
        viewer.updateImages();
        const staleError = viewer.dom.leftImg.listenerCallbacks('error')[0];
        viewer.state.currentFrameIdx = 1;
        viewer.updateImages();
        staleError();
        assert.equal(viewer.dom.emptyState.hidden, true);
        assert.equal(viewer.dom.status.hidden, true);

    }

    {
        const { viewer } = loadViewer({ clipCount: 2 });
        viewer.state.mode = 'slider';
        viewer.updateImages();
        viewer.dom.leftImg.dispatch('load');
        viewer.dom.rightImg.dispatch('load');
        const staleError = viewer.dom.leftImg.listenerCallbacks('error')[0];
        viewer.updateImages();
        staleError();
        assert.equal(viewer.dom.emptyState.hidden, true);
        assert.equal(viewer.dom.status.hidden, true);

    }

    {
        const { viewer } = loadViewer({ clipCount: 2 });
        viewer.gridView = { render() {} };
        viewer.state.mode = 'slider';
        viewer.updateImages();
        const staleError = viewer.dom.leftImg.listenerCallbacks('error')[0];
        viewer.state.mode = 'grid';
        viewer.updateImages();
        staleError();
        assert.equal(viewer.dom.emptyState.hidden, true);
        assert.equal(viewer.dom.status.hidden, true);

    }

    {
        const { viewer, deferredImages, window } = loadViewer({ clipCount: 2 });
        viewer.gridView = { render() {} };
        viewer.state.mode = 'slider';
        viewer.updateImages();
        const staleError = viewer.dom.leftImg.listenerCallbacks('error')[0];

        viewer.state.mode = 'diff';
        viewer.state.currentFrameIdx = 1;
        viewer.updateImages();
        assert.equal(deferredImages.length, 2);
        staleError();
        assert.equal(viewer.dom.emptyState.hidden, true);
        assert.equal(viewer.dom.status.hidden, true);

        viewer.state.mode = 'grid';
        viewer.updateImages();
        deferredImages.forEach(image => image.trigger('load'));
        await new Promise(resolve => setImmediate(resolve));
        window.rafQueue.splice(0).forEach(callback => callback?.());
        assert.equal(viewer.dom.emptyState.hidden, true);
        assert.equal(viewer.dom.status.hidden, true);

    }

    {
        const { viewer } = loadViewer({ clipCount: 2 });
        viewer.state.mode = 'slider';
        viewer.updateImages();
        viewer.dom.rightImg.dispatch('error');
        viewer.state.currentFrameIdx = 1;
        viewer.updateImages();
        viewer.dom.leftImg.dispatch('load');
        viewer.dom.rightImg.dispatch('load');
        assert.equal(viewer.dom.emptyState.hidden, true);
        assert.equal(viewer.dom.status.hidden, true);

    }

}

function fixtureIsolation() {
for (const fixture of [loadViewer({clipCount: 2}), loadViewer({clipCount: 2})]) {
    const other = loadViewer({clipCount: 2});
    const parent = fixture.element();
    const child = fixture.element();
    parent.append(child);
    other.viewer.dom.btnInspector.focus();
    child.focus();
    assert.equal(fixture.document.activeElement, child);
    assert.equal(other.document.activeElement, other.viewer.dom.btnInspector);
    child.remove();
    assert.equal(fixture.document.activeElement, null);
    assert.equal(other.document.activeElement, other.viewer.dom.btnInspector);
    parent.append(child);
    child.focus();
    parent.replaceChildren();
    assert.equal(fixture.document.activeElement, null);
    assert.equal(other.document.activeElement, other.viewer.dom.btnInspector);
}
}

function blinkGesturePause() {
// Exercise the production pointer handlers and interval callback, including cancellation.
for (const pauseCause of ['running', 'explicit', 'reduced-motion']) {
    for (const gesture of ['pan', 'pinch', 'lens', 'lens-pan', 'lens-pinch']) {
        for (const ending of ['pointerup', 'pointercancel']) {
            const fixture = loadViewer({ clipCount: 2 });
            const { viewer } = fixture;
            fixture.window.addEventListener = () => {};
            for (const name of ['btnZoomOut', 'btnZoomIn', 'btnZoomReset', 'btnFullscreen']) {
                viewer.dom[name] = fixture.element();
            }
            viewer.dom.stage.getBoundingClientRect = () => ({ left: 0, top: 0, width: 1920, height: 1080 });
            viewer.bindViewportEvents();
            if (pauseCause === 'reduced-motion') viewer.reducedMotionActive = () => true;
            viewer.setMode('blink');
            if (pauseCause === 'explicit') viewer.setBlinkPaused(true);
            if (gesture.startsWith('lens')) {
                const lensElement = { ...fixture.element(), style: { setProperty() {} } };
                fixture.document.getElementById = id => id === 'rv-lens' ? lensElement : null;
                fixture.document.querySelector = () => null;
                fixture.document.querySelectorAll = () => [];
                viewer.lens = fixture.lensFactory.create(viewer);
                viewer.lens.state.report.enabled = true;
                for (const image of [viewer.dom.leftImg, viewer.dom.rightImg]) {
                    image.getBoundingClientRect = viewer.dom.stage.getBoundingClientRect;
                }
            }
            const event = {
                pointerId: 1, pointerType: gesture === 'pan' ? 'mouse' : 'touch',
                button: 0, clientX: 100, clientY: 100, preventDefault() {},
            };
            viewer.dom.stage.dispatch('pointerdown', { ...event });
            if (gesture.endsWith('pinch')) viewer.dom.stage.dispatch('pointerdown', { ...event, pointerId: 2, clientX: 200 });
            if (gesture === 'lens-pan') viewer.dom.stage.dispatch('pointermove', { ...event, clientX: 120 });
            if (gesture.endsWith('pinch')) assert.equal(viewer.pointerInteraction.pinchActive, true);
            else if (gesture === 'lens') assert.equal(viewer.pointerInteraction.lensPointHandled, true);
            else assert.equal(viewer.pointerInteraction.isPanning, true);
            const during = viewer.state.activeClipIdx;
            viewer.state.blinkInterval.callback();
            assert.equal(viewer.state.activeClipIdx, during, `${pauseCause}/${gesture}: suspended timer`);
            assert.equal(viewer.dom.blinkStatus.textContent, 'Blink paused');
            assert.equal(viewer.dom.btnBlinkPause.disabled, true);
            viewer.dom.stage.dispatch(ending, { ...event });
            if (gesture.endsWith('pinch')) viewer.dom.stage.dispatch(ending, { ...event, pointerId: 2, clientX: 200 });
            if (gesture.startsWith('lens')) assert.equal(viewer.lens.state.touchPending, null);
            const before = viewer.state.activeClipIdx;
            viewer.state.blinkInterval.callback();
            const paused = pauseCause !== 'running';
            assert.equal(viewer.state.activeClipIdx === before, paused, `${pauseCause}/${gesture}/${ending}: pause intent`);
            assert.equal(viewer.dom.btnBlinkPause.disabled, false);
            assert.equal(viewer.dom.btnBlinkPause.textContent, paused ? 'Resume' : 'Pause');
            assert.equal(viewer.dom.btnBlinkPause.getAttribute('aria-pressed'), String(paused));
            assert.equal(viewer.dom.blinkStatus.textContent, paused ? 'Blink paused' : 'Blink 0.7s');
        }
    }
}
}

function viewerStorageKey() {
    const { viewer, format } = loadViewer({ clipCount: 4 });
    assert.equal(
        viewer.state.storageKey,
        'frame-compare:report-viewer:report_viewer_state_contract:viewport-v2',
    );

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
    assert.equal(format.clipDisplay(clip), 'Control descriptor');
    assert.equal(format.clipDisplay(clip, 'micro'), 'Micro descriptor');
    assert.equal(
        format.clipAccessibleName(clip),
        'Primary release identity — Exact.File.Name.mkv',
    );
    assert.equal(format.stableClipRole(0, viewer.referenceClipIndex()), 'Reference');
    assert.equal(format.stableClipRole(1, viewer.referenceClipIndex()), 'Comparison');
    viewer.state.data.default_selection.left_clip_index = 2;
    assert.equal(format.stableClipRole(0, viewer.referenceClipIndex()), 'Comparison');
    assert.equal(format.stableClipRole(1, viewer.referenceClipIndex()), 'Comparison');
    assert.equal(format.stableClipRole(2, viewer.referenceClipIndex()), 'Reference');
    assert.equal(format.stableClipRole(3, viewer.referenceClipIndex()), 'Comparison');
}

function defaultPairRule() {
    const { viewer: defaultViewer } = loadViewer({ clipCount: 4 });
    const pairIndexes = () => JSON.parse(JSON.stringify(defaultViewer.defaultPairIndexes()));
    assert.deepEqual(pairIndexes(), [0, 1]);
    defaultViewer.state.data.default_selection = { left_clip_index: 9, right_clip_index: 9 };
    assert.deepEqual(pairIndexes(), [0, 1]);
    const { viewer: singleViewer } = loadViewer({ clipCount: 1 });
    assert.deepEqual(JSON.parse(JSON.stringify(singleViewer.defaultPairIndexes())), [0, 0]);
}

function restoreFourClip() {
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
    assert.equal(viewer.viewport.currentAlignment().alignX, 5);
    assert.equal(viewer.viewport.currentAlignment().alignY, -2);
    assert.deepEqual(Object.keys(viewer.state.pairAlignments).sort(), ['0:1', '1:0']);
    assert.equal(renderedText(viewer.dom.alignmentStatus), 'Offset: custom +5x -2y');
}

function malformedAlignmentRestore() {
    const { viewer } = loadViewer({
        clipCount: 2,
        savedState: {
            alignmentPreset: 'custom',
            alignX: 77,
            alignY: -88,
        },
    });

    assert.deepEqual(Object.keys(viewer.state.pairAlignments), []);
    assert.equal(viewer.viewport.currentAlignment().alignmentPreset, 'none');
    assert.equal(viewer.viewport.currentAlignment().alignX, 0);
    assert.equal(viewer.viewport.currentAlignment().alignY, 0);

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
    assert.equal(malformedStorage.viewer.viewport.currentAlignment().alignmentPreset, 'custom');
    assert.equal(malformedStorage.viewer.viewport.currentAlignment().alignX, 6);
    assert.equal(malformedStorage.viewer.viewport.currentAlignment().alignY, -7);
}

function invalidSelectionRestore() {
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
    assert.equal(viewer.viewport.currentAlignment().alignX, 2);
    assert.equal(viewer.viewport.currentAlignment().alignY, 4);
    assert.deepEqual(Object.keys(viewer.state.pairAlignments), ['0:1']);
}

function filmstripState() {
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
}

function invalidFilmstripStateFallback() {
    const { viewer } = loadViewer({
        clipCount: 4,
        savedState: {
            filmstripCollapsed: 'yes',
            filmstripSize: 'huge',
            inspectorOpen: 'yes',
            inspectorTab: 'export',
            blinkIntervalMs: '700',
        },
    });

    assert.equal(viewer.state.filmstripCollapsed, false);
    assert.equal(viewer.state.filmstripSize, 'normal');
    assert.equal(viewer.state.inspectorOpen, false);
    // A persisted 'export' tab is the removed Inspector Export tab; it must fall
    // back to Frame through the same invalid-tab handling as any unknown value.
    assert.equal(viewer.state.inspectorTab, 'frame');
    assert.equal(viewer.state.blinkIntervalMs, 700);
    assert.equal(typeof viewer.state.blinkIntervalMs, 'number');
}

function inspectorBlinkKeyboardState() {
    const { element: makeElement, viewer, storage, storageKey, document, reviewMetrics } = loadViewer({
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
    assert.equal(viewer.state.blinkPauseRequested, false);
    viewer.dom.btnInspectorClose.setAttribute('tabindex', '0');
    viewer.inspector.setOpen(false, { focus: false, save: false });

    assert.equal(reviewMetrics.creates, 0);
    viewer.inspector.setTab('review');
    assert.equal(viewer.state.inspectorTab, 'review');
    assert.deepEqual(reviewMetrics, { creates: 0, binds: 0, renders: 0 });
    viewer.inspector.setTab('clips');
    viewer.inspector.setTab('review');
    assert.equal(reviewMetrics.creates, 0);
    viewer.inspector.setTab('clips');
    const focusables = viewer.dom.inspectorFocusables;
    const initiatingControl = makeElement();
    document.activeElement = initiatingControl;
    const infoLabel = viewer.dom.btnInfo.getAttribute('aria-label');
    const infoTitle = viewer.dom.btnInfo.getAttribute('title');
    viewer.inspector.setOpen(true);
    assert.equal(document.activeElement, viewer.dom.inspectorTabs[1]);
    const wrapEvent = keyboardEvent('ArrowRight');
    // Last tab (Review, index 3 in the 4-tab list) is the roving-tabindex wrap boundary.
    wrapEvent.currentTarget = viewer.dom.inspectorTabs[3];
    viewer.inspector.handleTabKey(wrapEvent);
    assert.equal(viewer.state.inspectorTab, 'frame');
    assert.equal(document.activeElement, viewer.dom.inspectorTabs[0]);
    viewer.inspector.setTab('clips');
    assert.equal(viewer.dom.inspector.inert, false);
    assert.equal(viewer.dom.btnInspectorClose.getAttribute('tabindex'), '0');
    assert.equal(viewer.dom.btnInspector.getAttribute('aria-expanded'), 'true');
    assert.equal(viewer.dom.btnInspector.classList.contains('active'), true);
    viewer.inspector.setOpen(false);
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
    viewer.inspector.setOpen(true);
    assert.equal(viewer.dom.inspector.inert, false);
    assert.equal(viewer.dom.btnInspectorClose.getAttribute('tabindex'), '0');
    viewer.dom.inspectorTabs.forEach((element, index) => {
        assert.equal(element.tabIndex, index === 1 ? 0 : -1);
    });
    viewer.inspector.setOpen(false);
    document.activeElement = document.body;
    viewer.inspector.setOpen(true);
    viewer.inspector.setOpen(false);
    assert.equal(document.activeElement, viewer.dom.btnInspector);
    viewer.setBlinkIntervalMs(300);
    viewer.setBlinkPaused(true);
    const saved = persisted(storage, storageKey);
    assert.equal(saved.currentFrameIdx, 1);
    assert.equal(saved.inspectorOpen, false);
    assert.equal(saved.inspectorTab, 'clips');
    assert.equal(saved.pixelLensEnabled, undefined);
    assert.equal(saved.blinkIntervalMs, 300);
    assert.equal(saved.blinkPaused, undefined);
    assert.equal(saved.blinkPauseRequested, undefined);
    assert.equal(viewer.dom.inspector.inert, true);
    assert.equal(viewer.dom.btnInspectorClose.getAttribute('tabindex'), '-1');
    assert.equal(restoredKeyboardFocusToOrigin, true);
    assert.equal(viewer.state.inspectorRestoreFocus, null);
}

function inspectorClipMetadata() {
    const { viewer } = loadViewer({ clipCount: 1 });
    viewer.inspector.setOpen(true, { focus: false, save: false });
    const card = viewer.dom.inspectorClips.children[0];
    const heading = card.children[0].children[0].textContent;
    const badge = card.children[0].children[1].textContent;
    const rows = card.children[3].children.map(
        row => [row.children[0].textContent, row.children[1].textContent],
    );
    assert.equal(heading, 'Reference · shown left');
    assert.equal(badge, 'SDR');
    assert.equal(card.children[1].textContent, 'Clip 1');
    assert.equal(card.children[2].textContent, 'clip-1.mkv');
    assert.deepEqual(rows, [
        ['Picture', '1920×1080 · full frame'],
        ['Length', '100 frames · 0:00:04'],
        ['Size', '17.00 GiB'],
        ['Signal', 'SDR · BT.709 / BT.709 / BT.2020c · Limited'],
    ]);
}

function inspectorFrameIdentity() {
    const { viewer } = loadViewer({ clipCount: 2 });
    viewer.state.activeCategoryKey = '__fc_all__';
    viewer.inspector.setOpen(true, { focus: false, save: false });
    assert.equal(viewer.dom.inspectorFrameIdentity.textContent, '10 · Selected');
    assert.equal(viewer.dom.inspectorFramePosition.textContent, '1 / 2 in All');
    assert.equal(viewer.dom.inspectorFrameDetailRow.hidden, true);
}

function inspectorFrameSources() {
    const { viewer } = loadViewer({ clipCount: 2 });
    viewer.inspector.setOpen(true, { focus: false, save: false });
    assert.deepEqual(JSON.parse(JSON.stringify(viewer.dom.inspectorSourceFrames.children.map(
        row => row.children.map(
            cell => cell.children.length > 0
                ? cell.children.map(child => child.textContent).join(' ')
                : cell.textContent,
        ).join(' | '),
    ))), ["Clip 1 Shown left | 10 / 100 | B \u00b7 DV RPU", "Clip 2 Shown right | 10 / 100 | B"]);
}

function modalKeyboardAccessibility() {
    const { element: makeElement, viewer, document } = loadViewer({ clipCount: 4 });
    const helpLast = makeElement();
    const infoLast = makeElement();
    viewer.dom.modal.querySelectorAll = () => [viewer.dom.btnCloseHelp, helpLast];
    viewer.dom.infoModal.querySelectorAll = () => [viewer.dom.btnCloseInfo, infoLast];

    document.activeElement = viewer.dom.btnHelp;
    viewer.dom.btnHelp.dispatch('click');
    document.activeElement = helpLast;
    const helpTab = keyboardEvent('Tab');
    viewer.dom.modal.dispatch('keydown', helpTab);
    assert.equal(document.activeElement, viewer.dom.btnCloseHelp);
    const helpShiftTab = keyboardEvent('Tab');
    helpShiftTab.shiftKey = true;
    viewer.dom.modal.dispatch('keydown', helpShiftTab);
    assert.equal(document.activeElement, helpLast);
    const helpEscape = keyboardEvent('Escape');
    viewer.dom.modal.dispatch('keydown', helpEscape);
    assert.equal(document.activeElement, viewer.dom.btnHelp);

    document.activeElement = viewer.dom.btnInfo;
    viewer.dom.btnInfo.dispatch('click');
    document.activeElement = infoLast;
    const infoTab = keyboardEvent('Tab');
    viewer.dom.infoModal.dispatch('keydown', infoTab);
    assert.equal(document.activeElement, viewer.dom.btnCloseInfo);
    const infoShiftTab = keyboardEvent('Tab');
    infoShiftTab.shiftKey = true;
    viewer.dom.infoModal.dispatch('keydown', infoShiftTab);
    assert.equal(document.activeElement, infoLast);
    const infoEscape = keyboardEvent('Escape');
    viewer.dom.infoModal.dispatch('keydown', infoEscape);
    assert.equal(document.activeElement, viewer.dom.btnInfo);

    // Exercise both dialogs through the same user event boundary, including
    // fallback focus and visibility rather than the lifecycle owner's shape.
    for (const [element, trigger, closeButton, close] of [
        [viewer.dom.modal, viewer.dom.btnHelp, viewer.dom.btnCloseHelp,
            options => viewer.closeHelpModal(options)],
        [viewer.dom.infoModal, viewer.dom.btnInfo, viewer.dom.btnCloseInfo,
            options => viewer.closeInfoModal(options)],
    ]) {
        const origin = makeElement();
        viewer.setAlignmentPopoverOpen(true, { restoreFocus: false });
        document.activeElement = origin;
        trigger.dispatch('click');
        assert.equal(viewer.isAlignmentPopoverOpen(), false);
        assert.equal(element.getAttribute('aria-hidden'), 'false');
        assert.equal(document.activeElement, closeButton);

        // Interior clicks retain the dialog; a backdrop click closes it.
        element.dispatch('click', { target: closeButton });
        assert.equal(element.classList.contains('open'), true);
        origin.isConnected = false;
        element.dispatch('click');
        assert.equal(element.classList.contains('open'), false);
        assert.equal(element.getAttribute('aria-hidden'), 'true');
        assert.equal(document.activeElement, trigger);

        document.activeElement = origin;
        trigger.dispatch('click');
        const disabled = makeElement();
        disabled.disabled = true;
        const hidden = makeElement();
        hidden.hidden = true;
        element.querySelectorAll = () => [disabled, hidden];
        const emptyTab = keyboardEvent('Tab');
        element.dispatch('keydown', emptyTab);
        assert.equal(emptyTab.defaultPrevented, true);
        assert.equal(document.activeElement, element);
        close({ restoreFocus: false });
        assert.equal(document.activeElement, element);

        document.activeElement = null;
        trigger.dispatch('click');
        closeButton.dispatch('click');
        assert.equal(document.activeElement, trigger);
    }
    assert.equal(helpEscape.propagationStopped, true);
    assert.equal(infoEscape.propagationStopped, true);

    for (const event of [helpTab, helpShiftTab, helpEscape, infoTab, infoShiftTab, infoEscape]) {
        assert.equal(event.defaultPrevented, true, `dialog ${event.key} default prevented`);
    }
}

function escapeOrder() {
    const { viewer } = loadViewer({ clipCount: 4 });

    viewer.bindAlignmentEvents();
    viewer.inspector.setOpen(true);
    viewer.setAlignmentPopoverOpen(true, { restoreFocus: false });
    const popoverEscape = keyboardEvent('Escape');
    viewer.dom.alignPopover.dispatch('keydown', popoverEscape);
    if (!popoverEscape.propagationStopped) viewer.handleKey(popoverEscape);
    assert.equal(popoverEscape.defaultPrevented, true);
    assert.equal(popoverEscape.propagationStopped, true);
    assert.equal(viewer.isAlignmentPopoverOpen(), false);
    assert.equal(viewer.state.inspectorOpen, true);

    viewer.inspector.setOpen(true);
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

    viewer.inspector.setOpen(true);
    viewer.setAlignmentPopoverOpen(true, { restoreFocus: false });
    viewer.dom.infoModal.classList.add('open');
    const infoEscape = keyboardEvent('Escape');
    viewer.handleKey(infoEscape);
    assert.equal(infoEscape.defaultPrevented, true);
    assert.equal(viewer.isInfoModalOpen(), false);
    assert.equal(viewer.state.inspectorOpen, true);
    assert.equal(viewer.isAlignmentPopoverOpen(), true);
}

function blinkControls() {
    const { viewer } = loadViewer({ clipCount: 4 });

    viewer.windowReducedMotion = true;
    const originalReducedMotionActive = viewer.reducedMotionActive;
    viewer.reducedMotionActive = () => true;
    viewer.setMode('blink');
    assert.equal(viewer.state.mode, 'blink');
    assert.equal(viewer.state.blinkPauseRequested, true);
    assert.equal(viewer.dom.blinkStatus.textContent, 'Blink paused');
    viewer.setBlinkPaused(false);
    viewer.stepBlinkInterval(1);
    assert.equal(viewer.state.blinkIntervalMs, 1200);
    viewer.stepBlinkInterval(-1);
    assert.equal(viewer.state.blinkIntervalMs, 700);
    viewer.reducedMotionActive = originalReducedMotionActive;
}

function blinkToggle() {
    const { format } = loadViewer({ clipCount: 2 });

    assert.equal(format.formatFileSize(1), '1.00 B');
    assert.equal(format.formatFileSize(1023), '1023.00 B');
    assert.equal(format.formatFileSize(1024), '1.00 KiB');
    assert.equal(format.formatFileSize(512 * 1024), '512.00 KiB');
    assert.equal(format.formatFileSize(1024 ** 2), '1.00 MiB');
    assert.equal(format.formatFileSize(1024 ** 3), '1.00 GiB');
    assert.equal(format.formatFileSize(1024 ** 4), '1.00 TiB');
    assert.equal(format.formatFileSize(0), '');
    assert.equal(format.formatFileSize(-1), '');
    assert.equal(format.formatFileSize(Number.NaN), '');
    assert.equal(
        format.formatSignal({
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

function blinkLabels() {
    const { viewer } = loadViewer({ clipCount: 4 });

    viewer.state.mode = 'blink';
    viewer.state.activeClipIdx = viewer.state.leftClipIdx;
    viewer.updateImages();
    assert.equal(renderedText(viewer.dom.labelLeft), 'Clip 1 · 1920×1080 · SDR · 17.00 GiB');
    assert.equal(renderedText(viewer.dom.labelRight), 'Clip 2 · 1920×1080 · SDR · 17.00 GiB');
    assert.equal(viewer.dom.labelLeft.classList.contains('rv-overlay-label--active'), true);
    assert.equal(viewer.dom.labelRight.classList.contains('rv-overlay-label--active'), false);
    viewer.state.activeClipIdx = viewer.state.rightClipIdx;
    viewer.updateImages();
    assert.equal(viewer.dom.labelLeft.classList.contains('rv-overlay-label--active'), false);
    assert.equal(viewer.dom.labelRight.classList.contains('rv-overlay-label--active'), true);
}

function keyboardGuard() {
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
}

function radioGroupKeyboard() {
    const { element: makeElement, viewer, document } = loadViewer({ clipCount: 4 });
    const buttons = ['first', 'second', 'third'].map(value => ({
        ...makeElement(),
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
}

function frameKeyboard() {
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
}

function filmstripKeyboard() {
    const { element: makeElement, viewer, document } = loadViewer({ clipCount: 4 });
    const items = [0, 1].map(idx => ({
        ...makeElement(),
        dataset: { idx: String(idx) },
        closest(selector) {
            return selector === '.rv-filmstrip-item' ? this : null;
        },
    }));
    const filmstrip = makeElement();
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
}

function pairSwitchFourClip() {
    const { viewer, storage, storageKey } = loadViewer({ clipCount: 4 });

    viewer.viewport.setManualAlignment(4, 5);
    assert.equal(renderedText(viewer.dom.alignmentStatus), 'Offset: custom +4x +5y');
    viewer.setRightClip(2);
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 2);
    assert.equal(viewer.viewport.currentAlignment().alignX, 0);
    assert.equal(viewer.viewport.currentAlignment().alignY, 0);
    assert.equal(renderedText(viewer.dom.alignmentStatus), 'Offset: none');

    viewer.viewport.setManualAlignment(-1, 8);
    viewer.setRightClip(1);
    assert.equal(viewer.viewport.currentAlignment().alignX, 4);
    assert.equal(viewer.viewport.currentAlignment().alignY, 5);
    assert.equal(renderedText(viewer.dom.alignmentStatus), 'Offset: custom +4x +5y');

    viewer.setRightClip(2);
    assert.equal(viewer.viewport.currentAlignment().alignX, -1);
    assert.equal(viewer.viewport.currentAlignment().alignY, 8);

    viewer.setRightClip(3);
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 3);
    assert.equal(viewer.viewport.currentAlignment().alignX, 0);
    assert.equal(viewer.viewport.currentAlignment().alignY, 0);

    viewer.viewport.setManualAlignment(21, -3);
    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 3);
    assert.equal(viewer.state.rightClipIdx, 0);
    assert.equal(viewer.viewport.currentAlignment().alignX, 0);
    assert.equal(viewer.viewport.currentAlignment().alignY, 0);

    viewer.viewport.setManualAlignment(-21, 3);
    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 3);
    assert.equal(viewer.viewport.currentAlignment().alignX, 21);
    assert.equal(viewer.viewport.currentAlignment().alignY, -3);

    viewer.setRightClip(2);
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 2);
    assert.equal(viewer.viewport.currentAlignment().alignX, -1);
    assert.equal(viewer.viewport.currentAlignment().alignY, 8);

    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 2);
    assert.equal(viewer.state.rightClipIdx, 0);
    assert.equal(viewer.viewport.currentAlignment().alignX, 0);
    assert.equal(viewer.viewport.currentAlignment().alignY, 0);

    viewer.viewport.setManualAlignment(12, 13);
    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 2);
    assert.equal(viewer.viewport.currentAlignment().alignX, -1);
    assert.equal(viewer.viewport.currentAlignment().alignY, 8);

    viewer.setRightClip(3);
    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 3);
    assert.equal(viewer.state.rightClipIdx, 0);
    assert.equal(viewer.viewport.currentAlignment().alignX, -21);
    assert.equal(viewer.viewport.currentAlignment().alignY, 3);

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
}

function alignmentStatus() {
    const { viewer } = loadViewer({ clipCount: 4 });

    assert.equal(renderedText(viewer.dom.alignmentStatus), 'Offset: none');
    viewer.viewport.setAlignmentPreset('left-1');
    assert.equal(viewer.viewport.currentAlignment().alignX, -1);
    assert.equal(viewer.viewport.currentAlignment().alignY, 0);
    assert.equal(renderedText(viewer.dom.alignmentStatus), 'Offset: preset left 1px');
    viewer.viewport.setAlignmentPreset('none');
    assert.equal(renderedText(viewer.dom.alignmentStatus), 'Offset: none');
}

function singleModeAlignment() {
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
    assert.equal(viewer.state.mode, 'overlay');
}

function directionalFourClip() {
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
    assert.equal(viewer.viewport.currentAlignment().alignX, -6);
    assert.equal(viewer.viewport.currentAlignment().alignY, -7);

    viewer.swapPairClips();
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 1);
    assert.equal(viewer.viewport.currentAlignment().alignX, 6);
    assert.equal(viewer.viewport.currentAlignment().alignY, 7);
}

function paletteOrientationState() {
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
    assert.equal(viewer.dom.btnPaletteOrientation.getAttribute('aria-label'), 'Switch to vertical orientation');

    viewer.setPaletteOrientation('vertical');
    assert.equal(viewer.state.paletteOrientation, 'vertical');
    assert.equal(viewer.dom.viewportPalette.getAttribute('data-orientation'), 'vertical');
    assert.equal(viewer.dom.btnPaletteOrientation.getAttribute('aria-label'), 'Switch to horizontal orientation');

    const { viewer: viewer2 } = loadViewer({
        clipCount: 4,
        savedState: {
            paletteOrientation: 'invalid_mode',
        },
    });
    assert.equal(viewer2.state.paletteOrientation, 'horizontal');

    const saved = persisted(storage, storageKey);
    assert.equal(saved.paletteOrientation, 'vertical');
}

function activeFilterBadge() {
    const { element: makeElement, viewer } = loadViewer({ clipCount: 4 });

    viewer.dom.filterChips = [
        { ...makeElement(), textContent: 'All (10)', dataset: { categoryKey: '__fc_all__' } },
        { ...makeElement(), textContent: 'Dark (3)', dataset: { categoryKey: 'dark' } },
        { ...makeElement(), textContent: 'Motion', dataset: { categoryKey: 'motion' } },
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
}

function lensPanIndependence() {
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
    viewer.persistViewerState = () => true;
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
}

function lensLayoutRefresh() {
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
}

function deferredTouchOwnership() {
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
}

function gridModeBoundary() {
    const { viewer } = loadViewer({
        clipCount: 4,
        savedState: { mode: 'grid' },
    });
    assert.equal(viewer.validPayloadMode('grid'), false);
    assert.equal(viewer.validMode('grid'), true);
    assert.equal(viewer.state.mode, 'grid');
}

function lazyReviewController() {
    const { viewer, reviewMetrics } = loadViewer({
        clipCount: 4,
        savedState: { inspectorOpen: false, inspectorTab: 'review' },
    });
    assert.equal(reviewMetrics.creates, 0);
    viewer.inspector.setOpen(true, { focus: false, save: false });
    assert.deepEqual(reviewMetrics, { creates: 1, binds: 1, renders: 1 });
}

function restoredWidthFitNoVisibleRadio() {
    const { viewer } = loadViewer({
        clipCount: 2,
        savedState: { fitMode: 'width' },
    });
    assert.equal(viewer.dom.fitBtns.length, 2);
    assert.deepEqual(viewer.dom.fitBtns.map((btn) => btn.dataset.fit), ['actual', 'height']);
    assert.equal(viewer.state.fitMode, 'width');

    viewer.dom.stage.getBoundingClientRect = () => ({ width: 800, height: 1080 });
    viewer.dom.sizerImg.naturalWidth = 1600;
    viewer.dom.sizerImg.naturalHeight = 1080;
    viewer.viewport.applyFitMode({ resetPan: true });
    assert.equal(viewer.state.zoom, 0.5);

    viewer.viewport.updateFitButtons();
    const checkedStates = viewer.dom.fitBtns.map((btn) => btn.getAttribute('aria-checked'));
    const tabIndexes = viewer.dom.fitBtns.map((btn) => btn.tabIndex);
    assert.ok(checkedStates.every(state => state === 'false'));
    assert.equal(tabIndexes.filter(value => value === 0).length, 1);
}

function gridShortcut() {
    const { viewer } = loadViewer({ clipCount: 4 });
    viewer.dom.modal.classList.remove('open');
    viewer.dom.infoModal.classList.remove('open');
    const keyEvent = key => ({
        key,
        target: { tagName: 'DIV', isContentEditable: false, closest() { return null; } },
        preventDefault() {},
    });
    viewer.setMode('slider');
    viewer.handleKey(keyEvent('g'));
    assert.equal(viewer.state.mode, 'grid');
    viewer.setMode('slider');
    viewer.handleKey(keyEvent('G'));
    assert.equal(viewer.state.mode, 'grid');
}

function proximityStateMachine() {
    const { viewer } = loadViewer({ clipCount: 2 });
    const viewport = viewer.viewport;
    const rect = {
        left: 100, top: 600, width: 300, height: 44, right: 400, bottom: 644,
    };
    assert.equal(viewport.proximityDistanceToRect(rect, 150, 622), 0);
    assert.equal(viewport.proximityDistanceToRect(rect, 100, 600), 0);
    assert.equal(viewport.proximityDistanceToRect(rect, 50, 622), 50);
    assert.equal(viewport.proximityDistanceToRect(rect, 150, 560), 40);
    assert.equal(
        Math.round(viewport.proximityDistanceToRect(rect, 40, 540)),
        85,
    );
    const base = {
        current: 'near',
        distance: 200,
        dragActive: false,
        popoverOpen: false,
        loadActive: false,
        finePointer: true,
    };
    const thresholds = (
        viewport.resolvePaletteProximity({ ...base, distance: 96 }) === 'near'
        && viewport.resolvePaletteProximity({ ...base, distance: 160 }) === 'far'
    );
    const hysteresis = (
        viewport.resolvePaletteProximity({ ...base, distance: 100 }) === 'near'
        && viewport.resolvePaletteProximity({ ...base, current: 'far', distance: 100 }) === 'far'
        && viewport.resolvePaletteProximity({ ...base, current: 'far', distance: 96 }) === 'near'
        && viewport.resolvePaletteProximity({ ...base, distance: 160 }) === 'far'
    );
    const overrides = (
        viewport.resolvePaletteProximity({ ...base, dragActive: true, distance: 0 }) === 'far'
        && viewport.resolvePaletteProximity({ ...base, popoverOpen: true, distance: 500 }) === 'near'
        && viewport.resolvePaletteProximity({ ...base, loadActive: true, distance: 500 }) === 'near'
        && viewport.resolvePaletteProximity({ ...base, finePointer: false, distance: 500 }) === 'near'
    );
    assert.ok(thresholds, 'proximity thresholds');
    assert.ok(hysteresis, 'proximity hysteresis');
    assert.ok(overrides, 'proximity overrides');
}

function paletteProximityWiring() {
    const { viewer, window } = loadViewer({ clipCount: 2 });
    const viewport = viewer.viewport;
    viewer.dom.viewportPalette.getBoundingClientRect = () => ({
        left: 100, top: 600, width: 300, height: 44, right: 400, bottom: 644,
    });
    viewport.initPaletteProximity();
    const startsNear = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    viewport.updatePaletteProximity(900, 100);
    const loadOverride = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    viewer.paletteProximity.loadUntil = Date.now() - 1;
    viewer.paletteProximity.finePointer = true;
    viewport.updatePaletteProximity(900, 100);
    const farWhenDistant = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'far';
    viewport.updatePaletteProximity(500, 622);
    const hysteresisHoldsFar = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'far';
    viewport.updatePaletteProximity(450, 622);
    const nearWhenClose = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    viewer.pointerInteraction = { isDragging: true, isPanning: false, pinchActive: false };
    viewport.updatePaletteProximity(150, 622);
    const dragOverride = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'far';
    viewer.pointerInteraction = { isDragging: false, isPanning: false, pinchActive: false };
    viewer.dom.alignPopover.hidden = false;
    viewport.updatePaletteProximity(900, 100);
    const alignPopoverOverride = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    viewer.dom.alignPopover.hidden = true;
    viewer.dom.lensSettingsPopover.hidden = false;
    viewport.updatePaletteProximity(900, 100);
    const lensPopoverOverride = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    viewer.dom.lensSettingsPopover.hidden = true;
    viewport.handleStagePointerLeave();
    const pointerLeaveSetsFar = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'far';
    viewer.paletteProximity.finePointer = false;
    viewport.updatePaletteProximity(900, 100);
    const coarseStaysNear = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    viewport.handleStagePointerLeave();
    const coarseLeaveStaysNear = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    const changes = [];
    window.matchMedia = () => ({
        matches: true,
        addEventListener(type, listener) {
            if (type === 'change') changes.push(listener);
        },
    });
    viewport.initPaletteProximity();
    const mediaInitFine = viewer.paletteProximity.finePointer === true;
    changes[0]({ matches: false });
    const mediaChangeGates = viewer.paletteProximity.finePointer === false
        && viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    const flushRaf = () => {
        window.rafQueue.splice(0).forEach(callback => callback && callback());
    };
    const flushTimeouts = () => {
        window.timeoutQueue.splice(0).forEach(callback => callback && callback());
    };
    viewport.initPaletteProximity();
    viewport.updatePaletteProximity(900, 100);
    const loadHoldsNear = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    viewer.paletteProximity.loadUntil = Date.now() - 1;
    flushTimeouts();
    const loadExpiryRecomputes = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'far';
    viewport.updatePaletteProximity(900, 100);
    viewport.schedulePaletteProximity(150, 622);
    const rafDefers = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'far';
    viewport.handleStagePointerLeave();
    flushRaf();
    const leaveCancelsQueuedFrame = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'far';
    viewport.updatePaletteProximity(900, 100);
    viewport.schedulePaletteProximity(150, 622);
    flushRaf();
    const rafFlushApplies = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    viewport.updatePaletteProximity(900, 100);
    viewport.updatePaletteProximity(Number.NaN, Number.NaN);
    const nanHoldsFar = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'far';
    viewport.schedulePaletteProximity(900, 100);
    viewport.initPaletteProximity();
    viewer.paletteProximity.loadUntil = Date.now() - 1;
    flushRaf();
    const reinitCancelsQueuedFrame = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    viewport.initPaletteProximity();
    viewport.updatePaletteProximity(150, 622);
    viewport.handleStagePointerLeave();
    const leaveDuringLoadHoldsNear = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'near';
    viewer.paletteProximity.loadUntil = Date.now() - 1;
    flushTimeouts();
    const leaveDuringLoadFadesAfterLoad = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'far';
    viewport.initPaletteProximity();
    viewer.paletteProximity.loadUntil = Date.now() - 1;
    flushTimeouts();
    const noPointerFadesAfterLoad = viewer.dom.viewportPalette.getAttribute('data-proximity') === 'far';
    assert.ok(startsNear, 'startsNear');
    assert.ok(loadOverride, 'loadOverride');
    assert.ok(farWhenDistant, 'farWhenDistant');
    assert.ok(hysteresisHoldsFar, 'hysteresisHoldsFar');
    assert.ok(nearWhenClose, 'nearWhenClose');
    assert.ok(dragOverride, 'dragOverride');
    assert.ok(alignPopoverOverride, 'alignPopoverOverride');
    assert.ok(lensPopoverOverride, 'lensPopoverOverride');
    assert.ok(pointerLeaveSetsFar, 'pointerLeaveSetsFar');
    assert.ok(coarseStaysNear, 'coarseStaysNear');
    assert.ok(coarseLeaveStaysNear, 'coarseLeaveStaysNear');
    assert.ok(mediaInitFine, 'mediaInitFine');
    assert.ok(mediaChangeGates, 'mediaChangeGates');
    assert.ok(loadHoldsNear, 'loadHoldsNear');
    assert.ok(loadExpiryRecomputes, 'loadExpiryRecomputes');
    assert.ok(rafDefers, 'rafDefers');
    assert.ok(leaveCancelsQueuedFrame, 'leaveCancelsQueuedFrame');
    assert.ok(rafFlushApplies, 'rafFlushApplies');
    assert.ok(nanHoldsFar, 'nanHoldsFar');
    assert.ok(reinitCancelsQueuedFrame, 'reinitCancelsQueuedFrame');
    assert.ok(leaveDuringLoadHoldsNear, 'leaveDuringLoadHoldsNear');
    assert.ok(leaveDuringLoadFadesAfterLoad, 'leaveDuringLoadFadesAfterLoad');
    assert.ok(noPointerFadesAfterLoad, 'noPointerFadesAfterLoad');
}

function pairOffsetModeTransitions() {
    for (const clipCount of [2, 3]) {
        for (const mode of ['diff', 'blink']) {
            for (const savedOffset of [false, true]) {
                for (const sameSourceOffset of [false, true]) {
                    const { viewer, storage, storageKey } = loadViewer({ clipCount });
                    viewer.setMode('slider');
                    if (savedOffset) viewer.viewport.setManualAlignment(7, 3);
                    viewer.setRightClip(0);
                    if (sameSourceOffset) viewer.viewport.setManualAlignment(2, 2);
                    viewer.viewport.setRawAlignmentInput('x', '99');
                    viewer.viewport.setRawAlignmentInput('y', '-');
                    viewer.setMode(mode);
                    const expected = savedOffset
                        ? { alignmentPreset: 'custom', alignX: 7, alignY: 3 }
                        : { alignmentPreset: 'none', alignX: 0, alignY: 0 };
                    assert.equal(viewer.viewport.currentPairAlignmentKey(), '0:1');
                    assert.deepEqual(JSON.parse(JSON.stringify(viewer.viewport.currentAlignment())), expected);
                    assert.equal(viewer.state.rawAlignX, null);
                    assert.equal(viewer.state.rawAlignY, null);
                    const saved = persisted(storage, storageKey);
                    assert.deepEqual(saved.pairAlignments['0:1'], savedOffset ? expected : undefined);
                    assert.deepEqual(saved.pairAlignments['0:0'], sameSourceOffset
                        ? { alignmentPreset: 'custom', alignX: 2, alignY: 2 } : undefined);
                    viewer.restorePersistedState();
                    assert.deepEqual(JSON.parse(JSON.stringify(viewer.viewport.currentAlignment())), expected);
                    const copy = viewer.viewport.currentAlignment();
                    copy.alignX = 999;
                    assert.equal(viewer.viewport.currentAlignment().alignX, expected.alignX);
                }
            }
        }
    }
}

function selectionDraftsAndActiveSource() {
    const { viewer, storage, storageKey } = loadViewer({ clipCount: 4 });
    viewer.state.activeClipIdx = 3;
    viewer.setLeftClip(0);
    assert.equal(viewer.state.activeClipIdx, 3);
    viewer.setMode('overlay');
    assert.equal(viewer.state.activeClipIdx, 3);
    viewer.setMode('diff');
    assert.equal(viewer.state.activeClipIdx, 3);
    viewer.setMode('blink');
    assert.equal(viewer.state.activeClipIdx, 0);
    viewer.setRightClip(2);
    assert.equal(viewer.state.activeClipIdx, 2);
    viewer.setRightClip(0); // Repair occurs before resolving the requested active side.
    assert.equal(viewer.state.activeClipIdx, 1);
    viewer.viewport.setRawAlignmentInput('x', '4.');
    viewer.setLeftClip(undefined);
    assert.equal(viewer.state.rawAlignX, null);
    viewer.viewport.setRawAlignmentInput('x', '4.');
    viewer.setMode('diff'); // An unchanged key preserves its draft.
    assert.equal(viewer.state.rawAlignX, '4.');
    viewer.viewport.setAlignmentPreset('custom');
    assert.equal(viewer.state.rawAlignX, '4.');
    viewer.viewport.setAlignmentPreset('left-1');
    assert.equal(viewer.state.rawAlignX, null);
    assert.equal(viewer.viewport.currentAlignment().alignX, -1);
    viewer.resetCurrentPairAlignment();
    assert.equal(viewer.viewport.currentAlignment().alignX, 0);
    assert.deepEqual(persisted(storage, storageKey).pairAlignments, {});
    viewer.viewport.setManualAlignment(2, 3);
    viewer.setRightClip(2);
    viewer.viewport.setManualAlignment(4, 5);
    viewer.resetAllPairAlignments();
    assert.deepEqual(persisted(storage, storageKey).pairAlignments, {});
    const single = loadViewer({ clipCount: 1 });
    single.viewer.setMode('blink');
    single.viewer.viewport.setManualAlignment(2, 2);
    assert.equal(single.viewer.viewport.currentPairAlignmentKey(), '0:0');
    assert.equal(single.viewer.viewport.currentAlignment().alignX, 2);
}

module.exports = {
    pairOffsetModeTransitions,
    selectionDraftsAndActiveSource,
    fixtureIsolation,
    blinkGesturePause,
    viewerStorageKey,
    defaultPairRule,
    restoreFourClip,
    malformedAlignmentRestore,
    invalidSelectionRestore,
    filmstripState,
    invalidFilmstripStateFallback,
    inspectorBlinkKeyboardState,
    inspectorClipMetadata,
    inspectorFrameIdentity,
    inspectorFrameSources,
    modalKeyboardAccessibility,
    escapeOrder,
    blinkControls,
    blinkToggle,
    blinkLabels,
    keyboardGuard,
    radioGroupKeyboard,
    frameKeyboard,
    filmstripKeyboard,
    pairSwitchFourClip,
    alignmentStatus,
    singleModeAlignment,
    directionalFourClip,
    paletteOrientationState,
    activeFilterBadge,
    lensPanIndependence,
    lensLayoutRefresh,
    deferredTouchOwnership,
    gridModeBoundary,
    lazyReviewController,
    restoredWidthFitNoVisibleRadio,
    gridShortcut,
    proximityStateMachine,
    paletteProximityWiring,
    deferredDiffGridNavigation: assertDeferredDiffCannotCommitAfterGridNavigation,
    mainImageUnavailable: assertMainImageUnavailableState,
};

if (require.main === module) require('./harness_runner').run(module.exports);
