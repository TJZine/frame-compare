const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const lensPath = path.resolve(
    __dirname,
    '..',
    '..',
    'src',
    'frame_compare',
    'services',
    'report',
    'assets',
    'lens.js',
);

let focusDocument = null;

function fakeElement(rect = { left: 0, top: 0, width: 0, height: 0 }) {
    const listeners = new Map();
    const attributes = new Map();
    const classes = new Set();
    let currentRect = { ...rect };
    let srcValue = '';
    const element = {
        hidden: false,
        disabled: false,
        checked: false,
        value: '',
        textContent: '',
        dataset: {},
        children: [],
        naturalWidth: 1920,
        naturalHeight: 1080,
        complete: true,
        srcAssignments: 0,
        currentSrc: '',
        style: {
            values: {},
            setProperty(name, value) { this.values[name] = value; },
        },
        classList: {
            toggle(name, force) {
                if (force) classes.add(name);
                else classes.delete(name);
            },
            contains(name) { return classes.has(name); },
        },
        addEventListener(type, callback, options = {}) {
            const entries = listeners.get(type) || [];
            entries.push({ callback, once: Boolean(options?.once) });
            listeners.set(type, entries);
        },
        removeEventListener(type, callback) {
            const entries = listeners.get(type) || [];
            listeners.set(type, entries.filter(entry => entry.callback !== callback));
        },
        listenerCount(type) { return (listeners.get(type) || []).length; },
        listenerCallbacks(type) {
            return (listeners.get(type) || []).map(entry => entry.callback);
        },
        dispatch(type, values = {}) {
            const event = {
                target: this,
                currentTarget: this,
                preventDefault() {},
                stopPropagation() {},
                ...values,
            };
            const entries = [...(listeners.get(type) || [])];
            entries.forEach(entry => {
                entry.callback(event);
                if (entry.once) {
                    const current = listeners.get(type) || [];
                    listeners.set(type, current.filter(candidate => candidate !== entry));
                }
            });
        },
        setAttribute(name, value) { attributes.set(name, String(value)); },
        getAttribute(name) { return attributes.get(name) ?? null; },
        removeAttribute(name) {
            attributes.delete(name);
            if (name === 'src') srcValue = '';
        },
        getBoundingClientRect() {
            return {
                ...currentRect,
                right: currentRect.left + currentRect.width,
                bottom: currentRect.top + currentRect.height,
            };
        },
        setRect(nextRect) { currentRect = { ...nextRect }; },
        replaceChildren(...children) { this.children = children; },
        contains(target) { return target === this; },
        closest() { return null; },
        focus() { if (focusDocument) focusDocument.activeElement = this; },
        querySelector() { return this.children[0] || null; },
        setPointerCapture() {},
    };
    Object.defineProperty(element, 'src', {
        configurable: true,
        get() { return srcValue; },
        set(value) {
            srcValue = String(value ?? '');
            element.srcAssignments += 1;
        },
    });
    return element;
}

function makeEnvironment({ failingWrites = false, coarse = false, autoLoadClones = true } = {}) {
    const stage = fakeElement({ left: 0, top: 0, width: 1000, height: 700 });
    const activeImage = fakeElement({ left: 100, top: 100, width: 800, height: 450 });
    activeImage.src = 'clip-2/frame.png';
    activeImage.currentSrc = activeImage.src;
    const rightImage = fakeElement({ left: 120, top: 110, width: 800, height: 450 });
    rightImage.src = 'clip-1/frame.png';
    rightImage.currentSrc = rightImage.src;
    const lens = fakeElement({ left: 600, top: 80, width: 240, height: 272 });
    const popover = fakeElement({ left: 580, top: 112, width: 260, height: 320 });
    popover.hidden = true;
    const firstSetting = fakeElement();
    popover.querySelector = () => firstSetting;
    const sizeButtons = ['small', 'medium', 'large'].map(size => {
        const button = fakeElement();
        button.dataset.lensSize = size;
        return button;
    });
    const behaviorButtons = ['follow', 'park'].map(behavior => {
        const button = fakeElement();
        button.dataset.lensBehavior = behavior;
        return button;
    });
    const elements = {
        'btn-lens': fakeElement(),
        'rv-lens': lens,
        'rv-lens-target': fakeElement(),
        'btn-lens-zoom-out': fakeElement(),
        'btn-lens-zoom-in': fakeElement(),
        'btn-lens-behavior': fakeElement(),
        'btn-lens-settings': fakeElement(),
        'btn-lens-close': fakeElement(),
        'lens-settings-popover': popover,
        'lens-target-marker': fakeElement(),
        'lens-comparison-enabled': fakeElement(),
        'lens-comparison-target': fakeElement(),
        'btn-lens-reset': fakeElement(),
    };
    const selectors = {
        '[data-lens-drag-handle]': fakeElement({ left: 600, top: 80, width: 240, height: 32 }),
        '[data-lens-zoom]': fakeElement(),
        '[data-lens-comparison-settings]': fakeElement(),
        '[data-lens-persistence]': fakeElement(),
        '[data-lens-image="active"]': fakeElement(),
        '[data-lens-image="difference"]': fakeElement(),
        '[data-lens-image="comparison"]': fakeElement(),
        '[data-lens-label="active"]': fakeElement(),
        '[data-lens-label="comparison"]': fakeElement(),
    };
    const storageValues = new Map();
    const detachedLoaders = [];
    const storage = {
        getItem(key) { return storageValues.get(key) ?? null; },
        setItem(key, value) {
            if (failingWrites) throw new Error('blocked');
            storageValues.set(key, value);
        },
    };
    const document = {
        activeElement: null,
        getElementById(id) { return elements[id] || null; },
        querySelector(selector) { return selectors[selector] || null; },
        querySelectorAll(selector) {
            if (selector === '[data-lens-size]') return sizeButtons;
            if (selector === '[data-lens-behavior]') return behaviorButtons;
            return [];
        },
        createElement(tagName) {
            const element = fakeElement();
            element.tagName = tagName.toUpperCase();
            if (element.tagName === 'IMG') {
                element.complete = autoLoadClones;
                detachedLoaders.push(element);
            }
            return element;
        },
        addEventListener() {},
    };
    focusDocument = document;
    lens.contains = target => [
        lens,
        elements['btn-lens-zoom-out'],
        elements['btn-lens-zoom-in'],
        elements['btn-lens-behavior'],
        elements['btn-lens-settings'],
        elements['btn-lens-close'],
        popover,
        firstSetting,
    ].includes(target);
    const context = {
        console,
        document,
        window: {
            matchMedia() { return { matches: coarse }; },
            setTimeout(callback) { callback(); },
        },
    };
    vm.runInNewContext(
        `${fs.readFileSync(lensPath, 'utf8')}\nglobalThis.__Lens = Lens;`,
        context,
        { filename: lensPath },
    );
    const frame = {
        images: [
            { src: 'clip-1/frame.png' },
            { src: 'clip-2/frame.png' },
            { src: 'clip-3/frame.png' },
        ],
    };
    const viewer = {
        state: {
            data: {
                report_id: 'lens-report',
                clips: [
                    { label: 'Reference', resolution: [1920, 1080] },
                    { label: 'Active', resolution: [1920, 1080] },
                    { label: 'Alternate', resolution: [1280, 720] },
                ],
            },
            mode: 'overlay',
            activeClipIdx: 1,
            leftClipIdx: 0,
            rightClipIdx: 1,
            revealPercent: 50,
        },
        dom: { stage, leftImg: activeImage, rightImg: rightImage },
        localStorage() { return storage; },
        currentFrame() { return frame; },
        referenceClipIndex() { return 0; },
        sliderCanvasRect() { return activeImage.getBoundingClientRect(); },
        announce() {},
        gridView: { entries() { return []; } },
    };
    return {
        Lens: context.__Lens,
        viewer,
        elements,
        selectors,
        sizeButtons,
        behaviorButtons,
        storageValues,
        frame,
        document,
        detachedLoaders,
    };
}

const pure = makeEnvironment();
const Lens = pure.Lens;

assert.deepEqual(
    JSON.parse(JSON.stringify(Lens.normalizePreferences({}))),
    { magnification: 4, size: 'medium', behavior: 'follow', targetMarker: true },
);
assert.deepEqual(
    JSON.parse(JSON.stringify(Lens.normalizePreferences({
        magnification: 12,
        size: 'large',
        behavior: 'park',
        targetMarker: false,
    }))),
    { magnification: 12, size: 'large', behavior: 'park', targetMarker: false },
);
assert.deepEqual(
    JSON.parse(JSON.stringify(Lens.normalizePreferences({
        magnification: 5,
        size: 'huge',
        behavior: 'float',
        targetMarker: 'yes',
    }))),
    { magnification: 4, size: 'medium', behavior: 'follow', targetMarker: true },
);

const bounded = Lens.normalizedPosition({ u: -4, v: 2 });
assert.equal(bounded.u, 0);
assert.equal(bounded.v, 1);
const mapped = Lens.normalizedPoint(
    fakeElement({ left: 10, top: 20, width: 200, height: 100 }),
    110,
    45,
);
assert.deepEqual(JSON.parse(JSON.stringify(mapped)), { u: 0.5, v: 0.25 });
assert.equal(Lens.normalizedPoint(fakeElement({ left: 0, top: 0, width: 0, height: 0 }), 0, 0), null);
const splitGeometry = Lens.lensImageGeometry(mapped, 200, 100, 4, 240, 120);
assert.deepEqual(JSON.parse(JSON.stringify(splitGeometry)), {
    width: 800,
    height: 400,
    left: -340,
    top: 20,
});
const rightBound = Lens.boundedPopoverPosition(
    { left: 0, top: 0, width: 1000, height: 700 },
    { left: 760, top: 80, width: 240, height: 272 },
    { width: 260, height: 320 },
);
assert.ok(760 + rightBound.left + 260 <= 992);
const leftBound = Lens.boundedPopoverPosition(
    { left: 0, top: 0, width: 1000, height: 700 },
    { left: 0, top: 400, width: 240, height: 272 },
    { width: 260, height: 320 },
);
assert.ok(leftBound.left >= 8);
const tinyBound = Lens.boundedPopoverPosition(
    { left: 0, top: 0, width: 180, height: 180 },
    { left: 8, top: 8, width: 160, height: 128 },
    { width: 260, height: 320 },
);
assert.equal(tinyBound.maxWidth, 164);
assert.equal(tinyBound.maxHeight, 164);

const environment = makeEnvironment();
const controller = environment.Lens.create(environment.viewer);
controller.bind();
assert.equal(controller.state.report.enabled, false);
controller.setEnabled(true);
assert.equal(controller.state.report.enabled, true);
assert.equal(environment.elements['btn-lens'].getAttribute('aria-pressed'), 'true');
assert.equal(environment.elements['rv-lens'].hidden, false);
assert.equal(controller.state.point.u, 0.5);
assert.equal(controller.state.point.v, 0.5);
controller.handleStagePointerMove({ clientX: 500, clientY: 325, pointerType: 'mouse' });
assert.equal(environment.elements['rv-lens'].hidden, false);
assert.equal(environment.elements['btn-lens'].hidden, true);
assert.equal(controller.state.point.u, 0.5);
assert.equal(controller.state.point.v, 0.5);
assert.equal(environment.elements['rv-lens'].dataset.behavior, 'follow');

environment.viewer.state.mode = 'diff';
controller.sync();
assert.equal(environment.elements['rv-lens'].dataset.renderMode, 'diff');
assert.equal(environment.selectors['[data-lens-image="difference"]'].dataset.source, 'clip-1/frame.png');
assert.notEqual(
    environment.selectors['[data-lens-image="difference"]'].style.left,
    environment.selectors['[data-lens-image="active"]'].style.left,
);
environment.viewer.state.mode = 'overlay';
controller.sync();

const gridImage = fakeElement({ left: 8, top: 12, width: 200, height: 100 });
gridImage.src = 'clip-3/frame.png';
gridImage.currentSrc = gridImage.src;
environment.viewer.gridView.entries = () => [{ clipIdx: 2, image: gridImage, unavailable: false }];
environment.viewer.state.mode = 'grid';
controller.sync();
assert.equal(controller.state.activeClipIdx, 2);
assert.equal(controller.state.point.u, 0.5);
assert.equal(controller.state.point.v, 0.5);
assert.equal(
    environment.selectors['[data-lens-image="active"]'].dataset.source,
    'clip-3/frame.png',
);
assert.equal(environment.elements['rv-lens'].dataset.renderMode, 'source');
environment.viewer.state.mode = 'overlay';
controller.sync();
assert.equal(controller.state.activeClipIdx, 1);
assert.equal(
    environment.selectors['[data-lens-image="active"]'].dataset.source,
    'clip-2/frame.png',
);

environment.elements['lens-comparison-enabled'].checked = true;
environment.elements['lens-comparison-enabled'].dispatch('change');
assert.equal(controller.state.report.comparisonEnabled, true);
assert.equal(controller.state.report.comparisonTarget, 0);
assert.equal(environment.elements['rv-lens'].dataset.comparison, 'true');
assert.notEqual(controller.state.report.comparisonTarget, controller.state.activeClipIdx);

environment.frame.images[0].src = '';
controller.sync();
assert.equal(environment.selectors['[data-lens-image="comparison"]'].dataset.source, undefined);
assert.equal(environment.selectors['[data-lens-image="comparison"]'].hidden, true);
assert.match(environment.selectors['[data-lens-label="comparison"]'].textContent, /unavailable/);
assert.equal(controller.state.report.comparisonEnabled, true);
environment.frame.images[0].src = 'clip-1/frame.png';
controller.sync();
assert.equal(
    environment.selectors['[data-lens-image="comparison"]'].dataset.source,
    'clip-1/frame.png',
);
assert.equal(environment.selectors['[data-lens-image="comparison"]'].hidden, false);

controller.clearTransient();
assert.equal(controller.state.report.enabled, true);
assert.equal(controller.state.point, null);
assert.equal(environment.elements['rv-lens'].hidden, true);
assert.equal(environment.selectors['[data-lens-image="active"]'].dataset.source, undefined);
controller.sync();
assert.equal(controller.state.report.enabled, true);
assert.equal(controller.state.point.u, 0.5);
assert.equal(controller.state.point.v, 0.5);
assert.equal(environment.elements['rv-lens'].hidden, false);
assert.equal(
    environment.selectors['[data-lens-image="active"]'].dataset.source,
    'clip-2/frame.png',
);

environment.behaviorButtons[1].dispatch('click');
assert.equal(controller.state.preferences.behavior, 'park');
assert.equal(environment.elements['rv-lens'].dataset.behavior, 'park');
environment.sizeButtons[2].dispatch('click');
assert.equal(controller.state.preferences.size, 'large');
assert.equal(environment.elements['rv-lens'].style.values['--lens-size'], '320px');

environment.behaviorButtons[0].dispatch('click');
assert.equal(controller.state.preferences.behavior, 'follow');
const beforeTap = { ...controller.state.point };
assert.equal(
    controller.handleStagePointerDown({ pointerId: 7, clientX: 300, clientY: 200, pointerType: 'touch' }),
    true,
);
assert.equal(
    controller.handleStagePointerMove({ pointerId: 7, clientX: 304, clientY: 202, pointerType: 'touch' }),
    'pending',
);
assert.deepEqual(JSON.parse(JSON.stringify(controller.state.point)), beforeTap);
assert.equal(
    controller.endStagePointer({ pointerId: 7, clientX: 300, clientY: 200, pointerType: 'touch' }),
    true,
);
assert.equal(controller.state.preferences.behavior, 'follow');
assert.equal(environment.elements['rv-lens'].dataset.behavior, 'park');
assert.equal(controller.state.point.u, 0.25);
assert.equal(controller.state.point.v, 2 / 9);
const tapPoint = { ...controller.state.point };
controller.handleStagePointerDown({ pointerId: 8, clientX: 300, clientY: 200, pointerType: 'touch' });
assert.equal(
    controller.handleStagePointerMove({ pointerId: 8, clientX: 320, clientY: 220, pointerType: 'touch' }),
    'released',
);
assert.deepEqual(JSON.parse(JSON.stringify(controller.state.point)), tapPoint);
assert.equal(controller.endStagePointer({ pointerId: 8, clientX: 320, clientY: 220 }), false);

environment.viewer.state.mode = 'diff';
controller.sync();
const touchSample = { ...controller.state.point };
const differenceBeforeLayout = environment.selectors['[data-lens-image="difference"]'].style.left;
environment.viewer.dom.leftImg.setRect({ left: 350, top: 250, width: 400, height: 225 });
environment.viewer.dom.rightImg.setRect({ left: 375, top: 260, width: 400, height: 225 });
controller.refresh();
assert.deepEqual(JSON.parse(JSON.stringify(controller.state.point)), touchSample);
assert.equal(controller.state.activeClipIdx, environment.viewer.state.leftClipIdx);
assert.notEqual(
    environment.selectors['[data-lens-image="difference"]'].style.left,
    differenceBeforeLayout,
);
environment.viewer.dom.leftImg.setRect({ left: 100, top: 100, width: 800, height: 450 });
environment.viewer.dom.rightImg.setRect({ left: 120, top: 110, width: 800, height: 450 });
environment.viewer.state.mode = 'overlay';
controller.sync();

const dragHandle = environment.selectors['[data-lens-drag-handle]'];
dragHandle.dispatch('pointerdown', { pointerId: 9, button: 0, clientX: 620, clientY: 100 });
dragHandle.dispatch('pointermove', { pointerId: 9, clientX: 990, clientY: 690 });
dragHandle.dispatch('pointerup', { pointerId: 9, clientX: 990, clientY: 690 });
assert.ok(controller.state.report.parkedPosition.u >= 0 && controller.state.report.parkedPosition.u <= 1);
assert.ok(controller.state.report.parkedPosition.v >= 0 && controller.state.report.parkedPosition.v <= 1);

environment.viewer.state.mode = 'slider';
controller.sync();
assert.equal(environment.elements['rv-lens'].dataset.comparison, 'false');
assert.equal(controller.state.report.comparisonEnabled, true);
assert.equal(controller.state.report.enabled, true);

const reportPayload = JSON.parse(
    environment.storageValues.get('frame-compare:report-lens:v1:lens-report'),
);
assert.equal(reportPayload.enabled, true);
assert.equal(reportPayload.comparisonEnabled, true);
assert.equal(Object.hasOwn(reportPayload, 'point'), false);
assert.equal(Object.hasOwn(reportPayload, 'pointer'), false);

const failing = makeEnvironment({ failingWrites: true, coarse: true });
const memoryController = failing.Lens.create(failing.viewer);
memoryController.bind();
memoryController.setEnabled(true);
memoryController.handleStagePointerDown({ pointerId: 1, clientX: 300, clientY: 200, pointerType: 'touch' });
memoryController.endStagePointer({ pointerId: 1, clientX: 300, clientY: 200, pointerType: 'touch' });
assert.equal(memoryController.state.memoryOnly, true);
assert.match(failing.selectors['[data-lens-persistence]'].textContent, /session only/);
assert.equal(failing.elements['rv-lens'].hidden, false);

const focusEnvironment = makeEnvironment();
const focusController = focusEnvironment.Lens.create(focusEnvironment.viewer);
focusController.bind();
focusController.setEnabled(true);
focusEnvironment.document.activeElement = focusEnvironment.elements['btn-lens-close'];
focusEnvironment.elements['btn-lens-close'].dispatch('click');
assert.equal(focusController.state.report.enabled, false);
assert.equal(focusEnvironment.elements['btn-lens'].hidden, false);
assert.equal(focusEnvironment.document.activeElement, focusEnvironment.elements['btn-lens']);
focusController.setEnabled(true);
const externalFocus = fakeElement();
focusEnvironment.document.activeElement = externalFocus;
focusController.setEnabled(false);
assert.equal(focusEnvironment.document.activeElement, externalFocus);

const activeFailure = makeEnvironment({ autoLoadClones: false });
const activeClone = activeFailure.selectors['[data-lens-image="active"]'];
const activeFailureController = activeFailure.Lens.create(activeFailure.viewer);
activeFailureController.bind();
activeFailureController.setEnabled(true);
const sourceALoader = activeFailure.detachedLoaders.at(-1);
const queuedSourceACallbacks = [
    ...sourceALoader.listenerCallbacks('load'),
    ...sourceALoader.listenerCallbacks('error'),
];
activeFailure.viewer.dom.leftImg.src = 'clip-2/new-frame.png';
activeFailure.viewer.dom.leftImg.currentSrc = activeFailure.viewer.dom.leftImg.src;
activeFailureController.sync();
const sourceBLoader = activeFailure.detachedLoaders.at(-1);
assert.notEqual(sourceBLoader, sourceALoader);
assert.equal(sourceALoader.listenerCount('load'), 0);
assert.equal(sourceALoader.listenerCount('error'), 0);
assert.equal(activeClone.dataset.requestSource, 'clip-2/new-frame.png');
assert.equal(activeClone.dataset.source, undefined);
assert.equal(activeClone.src, '');
queuedSourceACallbacks.forEach(callback => callback({
    target: sourceALoader,
    currentTarget: sourceALoader,
}));
assert.equal(activeClone.dataset.requestSource, 'clip-2/new-frame.png');
assert.equal(activeClone.dataset.source, undefined);
assert.equal(activeClone.hidden, true);
sourceBLoader.dispatch('load');
assert.equal(activeClone.dataset.source, 'clip-2/new-frame.png');
assert.equal(activeClone.hidden, false);
assert.equal(sourceBLoader.listenerCount('load'), 0);
assert.equal(sourceBLoader.listenerCount('error'), 0);
activeFailure.viewer.dom.leftImg.src = 'clip-2/failed-frame.png';
activeFailure.viewer.dom.leftImg.currentSrc = activeFailure.viewer.dom.leftImg.src;
activeFailureController.sync();
const failedActiveLoader = activeFailure.detachedLoaders.at(-1);
failedActiveLoader.dispatch('error');
assert.equal(activeClone.hidden, true);
assert.equal(activeClone.dataset.source, undefined);
assert.match(activeFailure.selectors['[data-lens-label="active"]'].textContent, /unavailable/);
assert.equal(failedActiveLoader.listenerCount('load'), 0);
assert.equal(failedActiveLoader.listenerCount('error'), 0);
const failedActiveLoaderCount = activeFailure.detachedLoaders.length;
activeFailureController.refresh();
assert.equal(activeFailure.detachedLoaders.length, failedActiveLoaderCount);
activeFailure.viewer.dom.leftImg.src = 'clip-2/recovered-frame.png';
activeFailure.viewer.dom.leftImg.currentSrc = activeFailure.viewer.dom.leftImg.src;
activeFailureController.sync();
const recoveredActiveLoader = activeFailure.detachedLoaders.at(-1);
assert.equal(activeFailure.detachedLoaders.length, failedActiveLoaderCount + 1);
recoveredActiveLoader.dispatch('load');
assert.equal(activeClone.hidden, false);
assert.equal(activeClone.dataset.source, 'clip-2/recovered-frame.png');
assert.equal(recoveredActiveLoader.listenerCount('load'), 0);
assert.equal(recoveredActiveLoader.listenerCount('error'), 0);
assert.equal(
    activeFailure.detachedLoaders.every(loader => (
        loader.listenerCount('load') === 0 && loader.listenerCount('error') === 0
    )),
    true,
);

const comparisonFailure = makeEnvironment({ autoLoadClones: false });
const comparisonClone = comparisonFailure.selectors['[data-lens-image="comparison"]'];
const comparisonFailureController = comparisonFailure.Lens.create(comparisonFailure.viewer);
comparisonFailureController.bind();
comparisonFailureController.setEnabled(true);
comparisonFailure.detachedLoaders.at(-1).dispatch('load');
comparisonFailure.elements['lens-comparison-enabled'].checked = true;
comparisonFailure.elements['lens-comparison-enabled'].dispatch('change');
const failedComparisonLoader = comparisonFailure.detachedLoaders.at(-1);
failedComparisonLoader.dispatch('error');
assert.equal(comparisonClone.hidden, true);
assert.match(
    comparisonFailure.selectors['[data-lens-label="comparison"]'].textContent,
    /unavailable/,
);
assert.equal(failedComparisonLoader.listenerCount('load'), 0);
assert.equal(failedComparisonLoader.listenerCount('error'), 0);
const failedComparisonLoaderCount = comparisonFailure.detachedLoaders.length;
comparisonFailureController.refresh();
assert.equal(comparisonFailure.detachedLoaders.length, failedComparisonLoaderCount);
comparisonFailure.frame.images[0].src = 'clip-1/recovered-frame.png';
comparisonFailureController.sync();
const recoveredComparisonLoader = comparisonFailure.detachedLoaders.at(-1);
recoveredComparisonLoader.dispatch('load');
assert.equal(comparisonClone.dataset.source, 'clip-1/recovered-frame.png');
assert.equal(recoveredComparisonLoader.listenerCount('load'), 0);
assert.equal(recoveredComparisonLoader.listenerCount('error'), 0);
comparisonFailure.frame.images[0].src = 'clip-1/superseded-frame.png';
comparisonFailureController.sync();
const supersededComparisonLoader = comparisonFailure.detachedLoaders.at(-1);
const staleComparisonCallbacks = [
    ...supersededComparisonLoader.listenerCallbacks('load'),
    ...supersededComparisonLoader.listenerCallbacks('error'),
];
comparisonFailureController.clearTransient();
assert.equal(supersededComparisonLoader.listenerCount('load'), 0);
assert.equal(supersededComparisonLoader.listenerCount('error'), 0);
staleComparisonCallbacks.forEach(callback => callback({
    target: supersededComparisonLoader,
    currentTarget: supersededComparisonLoader,
}));
assert.equal(comparisonClone.dataset.source, undefined);
assert.equal(comparisonClone.hidden, true);
assert.equal(comparisonFailureController.state.report.enabled, true);

console.log(JSON.stringify({
    defaultsNormalized: true,
    strictOptionsNormalized: true,
    mappingAndClamping: true,
    splitGeometry: true,
    boundedPopover: true,
    diffCompositionAndAlignment: true,
    staleContextReseeds: true,
    immediateActivation: true,
    toggleAndFollow: true,
    parkAndTouch: true,
    touchDragReleasesWithoutSampling: true,
    touchLayoutRefreshStable: true,
    focusedDisableRestoresToggle: true,
    programmaticDisablePreservesFocus: true,
    cloneFailuresAreSourceMatched: true,
    detachedLoadersAreIsolated: true,
    detachedLoaderHandlersCleaned: true,
    cloneSourceChangeRetries: true,
    staleCloneCallbacksIgnored: true,
    comparisonFallback: true,
    unavailableComparisonClears: true,
    comparisonSingleOnly: true,
    clearTransientRetainsEnabled: true,
    enabledAcrossContextChange: true,
    reportPersistenceExcludesPointer: true,
    storageFailureIsSessionOnly: true,
}));
