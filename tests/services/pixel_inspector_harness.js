const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const repoRoot = path.resolve(__dirname, '..', '..');
const assetPath = path.join(
    repoRoot,
    'src',
    'frame_compare',
    'services',
    'report',
    'assets',
    'pixel_inspector.js',
);
const context = {};
const source = `${fs.readFileSync(assetPath, 'utf8')}\nglobalThis.__PixelInspector = PixelInspector;`;
vm.runInNewContext(source, context, { filename: assetPath });
const model = context.__PixelInspector;

function point(x, y, width, height) {
    return {
        x,
        y,
        width,
        height,
        u: (x + 0.5) / width,
        v: (y + 0.5) / height,
    };
}

const equalSource = point(959, 539, 1920, 1080);
assert.deepEqual(
    { ...model.mapNormalizedPoint(equalSource, 1920, 1080) },
    equalSource,
);
const mismatched = model.mapNormalizedPoint(equalSource, 1280, 720);
assert.deepEqual(
    { x: mismatched.x, y: mismatched.y, width: mismatched.width, height: mismatched.height },
    { x: 639, y: 359, width: 1280, height: 720 },
);
assert.equal(mismatched.u, (639 + 0.5) / 1280);
assert.equal(mismatched.v, (359 + 0.5) / 720);

const alignedImage = {
    naturalWidth: 100,
    naturalHeight: 50,
    getBoundingClientRect() {
        // The translation/alignment and stage scale are already represented here.
        return { left: 240, top: 120, width: 400, height: 200 };
    },
};
assert.deepEqual(
    { ...model.pointFromImageRect(alignedImage, 442, 222) },
    point(50, 25, 100, 50),
);
assert.equal(model.pointFromImageRect(alignedImage, -100, 1000), null);
assert.equal(model.pointFromImageRect(alignedImage, 640, 200), null);
assert.deepEqual(
    { ...model.pointFromImageRect(alignedImage, 639.99, 319.99) },
    point(99, 49, 100, 50),
);

const anchorOptions = {
    activeClipIdx: 3,
    leftClipIdx: 1,
    rightClipIdx: 2,
    blinkVisibleClipIdx: 2,
    sliderRect: { left: 100, width: 200 },
    revealPercent: 25,
    clientX: 250,
};
assert.equal(model.anchorIndexForMode('slider', anchorOptions), 1);
assert.equal(model.anchorIndexForMode('slider', { ...anchorOptions, clientX: 251 }), 2);
assert.equal(model.anchorIndexForMode('overlay', anchorOptions), 3);
assert.equal(model.anchorIndexForMode('diff', anchorOptions), 1);
assert.equal(model.anchorIndexForMode('blink', anchorOptions), 2);
assert.equal(model.anchorIndexForMode('grid', { ...anchorOptions, gridClipIdx: 3 }), 3);

assert.equal(model.gestureExceeded(0, 0, 6, 0), false);
assert.equal(model.gestureExceeded(0, 0, 6.01, 0), true);
assert.equal(model.gestureExceeded(1, 1, 4, 5), false);

const topLeft = point(0, 0, 20, 10);
assert.deepEqual(
    { ...model.nudgePoint(topLeft, -1, -1, 10) },
    topLeft,
);
assert.deepEqual(
    { ...model.nudgePoint(topLeft, 1, 1, 10) },
    point(10, 9, 20, 10),
);

assert.deepEqual(
    { ...model.lensImageGeometry(point(50, 25, 100, 50), 4) },
    { width: 400, height: 200, left: -146, top: -46 },
);
assert.deepEqual(
    { ...model.lensImageGeometry(point(0, 0, 100, 50), 8) },
    { width: 800, height: 400, left: 52, top: 52 },
);
assert.equal(model.lensImageGeometry(point(0, 0, 100, 50), 3), null);

let readCount = 0;
const successfulContext = {
    clearRect() {},
    drawImage() {},
    getImageData() {
        readCount += 1;
        return { data: new Uint8ClampedArray([12, 34, 56, 255]) };
    },
};
const successfulDocument = {
    createElement(tagName) {
        assert.equal(tagName, 'canvas');
        return {
            width: 0,
            height: 0,
            getContext() { return successfulContext; },
        };
    },
};
const sampler = model.createSampler(successfulDocument);
const decodedImage = { complete: true, naturalWidth: 20, naturalHeight: 10 };
assert.equal(sampler.canvas.width, 1);
assert.equal(sampler.canvas.height, 1);
assert.deepEqual([...sampler.sample(decodedImage, 2, 3)], [12, 34, 56, 255]);
assert.equal(readCount, 1);
assert.equal(sampler.sample({ ...decodedImage, complete: false }, 2, 3), null);
assert.equal(readCount, 1);

let poisoned = false;
let resetCount = 0;
const recoveringSampler = model.createSampler({
    createElement() {
        const recoveryCanvas = {
            _width: 0,
            _height: 0,
            set width(value) {
                this._width = value;
                poisoned = false;
                resetCount += 1;
            },
            get width() { return this._width; },
            set height(value) {
                this._height = value;
                poisoned = false;
                resetCount += 1;
            },
            get height() { return this._height; },
            getContext() {
                return {
                    clearRect() {},
                    drawImage(image) { poisoned = Boolean(image.tainted); },
                    getImageData() {
                        if (poisoned) throw new Error('tainted');
                        return { data: new Uint8ClampedArray([9, 8, 7, 255]) };
                    },
                };
            },
        };
        return recoveryCanvas;
    },
});
const resetsBeforeFailure = resetCount;
assert.equal(recoveringSampler.sample({ ...decodedImage, tainted: true }, 2, 3), null);
assert.equal(resetCount, resetsBeforeFailure + 2);
assert.deepEqual(
    [...recoveringSampler.sample(decodedImage, 2, 3)],
    [9, 8, 7, 255],
);

const staleState = {
    point: point(5, 5, 20, 10),
    anchorClipIdx: 1,
    locked: true,
    stagePress: { pointerId: 7 },
};
model.clearInspectionState(staleState);
assert.deepEqual(staleState, {
    point: null,
    anchorClipIdx: null,
    locked: false,
    stagePress: null,
});

const inactiveState = {
    locked: true,
    stagePress: { pointerId: 7 },
    roiDragPointerId: 8,
};
const inactiveRoi = {
    hidden: false,
    disabled: false,
    tabIndex: 0,
    attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
};
const inactiveLens = { hidden: false };
model.deactivateInspection(inactiveState, inactiveRoi, inactiveLens);
assert.deepEqual(inactiveState, {
    locked: false,
    stagePress: null,
    roiDragPointerId: null,
});
assert.equal(inactiveRoi.hidden, true);
assert.equal(inactiveRoi.disabled, true);
assert.equal(inactiveRoi.tabIndex, -1);
assert.equal(inactiveRoi.attributes['aria-pressed'], 'false');
assert.equal(inactiveLens.hidden, true);

function interactiveElement(rect = { left: 0, top: 0, width: 0, height: 0 }) {
    const listeners = new Map();
    const attributes = new Map();
    return {
        rect,
        hidden: false,
        disabled: false,
        complete: true,
        naturalWidth: 0,
        naturalHeight: 0,
        currentSrc: '',
        src: '',
        tabIndex: -1,
        textContent: '',
        dataset: {},
        children: [],
        style: {},
        classList: { toggle() {} },
        addEventListener(type, listener) {
            const entries = listeners.get(type) || [];
            entries.push(listener);
            listeners.set(type, entries);
        },
        dispatch(type, event = {}) {
            for (const listener of listeners.get(type) || []) listener(event);
        },
        setAttribute(name, value) { attributes.set(name, String(value)); },
        getAttribute(name) { return attributes.get(name) ?? null; },
        replaceChildren(...children) { this.children = children; },
        append(...children) { this.children.push(...children); },
        getBoundingClientRect() { return this.rect; },
        setPointerCapture() {},
        releasePointerCapture() {},
    };
}

const timers = new Map();
let nextTimer = 1;
const fakeWindow = {
    setTimeout(callback) {
        const id = nextTimer++;
        timers.set(id, callback);
        return id;
    },
    clearTimeout(id) { timers.delete(id); },
    requestAnimationFrame(callback) {
        const id = nextTimer++;
        timers.set(id, callback);
        return id;
    },
    cancelAnimationFrame(id) { timers.delete(id); },
    matchMedia() { return { matches: false }; },
    addEventListener() {},
};
function flushTimers() {
    while (timers.size > 0) {
        const pending = [...timers.entries()];
        timers.clear();
        pending.forEach(([, callback]) => callback());
    }
}

const inspectButton = interactiveElement();
const roi = interactiveElement();
const lens = interactiveElement();
const lensImage = interactiveElement();
const lensToggle = interactiveElement();
const rows = interactiveElement();
const anchorText = interactiveElement();
const live = interactiveElement();
const magnificationButtons = [2, 4, 8].map(value => ({
    ...interactiveElement(),
    dataset: { pixelMagnification: String(value) },
}));
const elementIds = new Map([
    ['btn-inspect', inspectButton],
    ['rv-inspection-point', roi],
    ['rv-pixel-lens', lens],
    ['pixel-lens-toggle', lensToggle],
    ['pixel-inspector-live', live],
]);
const integrationDocument = {
    getElementById(id) { return elementIds.get(id) || null; },
    querySelector(selector) {
        if (selector === '#rv-pixel-lens img') return lensImage;
        if (selector === '[data-pixel-rows]') return rows;
        if (selector === '[data-pixel-anchor]') return anchorText;
        return null;
    },
    querySelectorAll(selector) {
        return selector === '[data-pixel-magnification]' ? magnificationButtons : [];
    },
    createElement(tagName) {
        if (tagName !== 'canvas') return interactiveElement();
        return {
            width: 0,
            height: 0,
            getContext() {
                return {
                    clearRect() {},
                    drawImage() {},
                    getImageData() {
                        return { data: new Uint8ClampedArray([1, 2, 3, 255]) };
                    },
                };
            },
        };
    },
};
context.document = integrationDocument;
context.window = fakeWindow;

const leftImage = interactiveElement({ left: 20, top: 30, width: 100, height: 50 });
leftImage.naturalWidth = 100;
leftImage.naturalHeight = 50;
leftImage.currentSrc = 'left.png';
const rightImage = interactiveElement({ left: 200, top: 60, width: 0, height: 0 });
rightImage.naturalWidth = 200;
rightImage.naturalHeight = 100;
rightImage.currentSrc = 'right.png';
const stage = interactiveElement({ left: 0, top: 0, width: 500, height: 300 });
const integrationViewer = {
    state: {
        inspectorOpen: true,
        inspectorTab: 'pixel',
        mode: 'blink',
        activeClipIdx: 0,
        leftClipIdx: 0,
        rightClipIdx: 1,
        revealPercent: 50,
        pixelLensEnabled: false,
        data: {
            clips: [
                { label: 'Left', resolution: [100, 50] },
                { label: 'Right', resolution: [200, 100] },
            ],
        },
    },
    dom: {
        stage,
        leftImg: leftImage,
        rightImg: rightImage,
        labelLeft: interactiveElement(),
        labelRight: interactiveElement(),
    },
    sliderCanvasRect() { return { left: 20, width: 100 }; },
    modeLabel() { return 'Blink'; },
    persistViewportState() { return true; },
    setInspectorTab(tab) { this.state.inspectorTab = tab; },
    setInspectorOpen(open) { this.state.inspectorOpen = open; },
    focusElement() {},
};
const controller = model.create(integrationViewer);
controller.bind();

const pointer = (x, y) => ({
    button: 0,
    pointerId: 41,
    pointerType: 'touch',
    clientX: x,
    clientY: y,
    preventDefault() {},
    stopPropagation() {},
});
assert.equal(controller.beginStagePress(pointer(70, 55)), true);
controller.moveStagePress(pointer(76, 55));
assert.equal(controller.isStagePressPending(41), true);
controller.cancelStagePress();
assert.equal(controller.beginStagePress(pointer(70, 55)), true);
controller.moveStagePress(pointer(76.01, 55));
assert.equal(controller.isStagePressPending(41), false);
assert.equal(controller.endStagePress(pointer(76.01, 55)), false);
assert.equal(controller.beginStagePress(pointer(70, 55)), true);
assert.equal(controller.endStagePress(pointer(70, 55)), true);
assert.equal(controller.state.locked, true);
assert.equal(controller.state.anchorClipIdx, 0);

leftImage.rect = { left: 20, top: 30, width: 0, height: 0 };
rightImage.rect = { left: 200, top: 60, width: 200, height: 100 };
integrationViewer.state.activeClipIdx = 1;
controller.render();
assert.equal(roi.hidden, false);
assert.equal(roi.style.left, '301.5px');
assert.equal(roi.style.top, '111.5px');
assert.equal(controller.state.anchorClipIdx, 0);

roi.dispatch('pointerdown', pointer(301.5, 111.5));
roi.dispatch('pointermove', pointer(310, 110));
assert.equal(controller.state.anchorClipIdx, 0);
assert.equal(controller.state.point.x, 55);
const blinkPointBeforeCancel = { ...controller.state.point };
roi.dispatch('pointercancel', pointer(390, 150));
assert.deepEqual({ ...controller.state.point }, blinkPointBeforeCancel);
assert.equal(controller.state.roiDragPointerId, null);

const keyEvent = {
    key: 'ArrowRight',
    shiftKey: false,
    preventDefault() {},
    stopPropagation() {},
};
roi.dispatch('keydown', keyEvent);
controller.clearForContext('Frame changed; inspection unlocked.');
flushTimers();
assert.equal(controller.state.point, null);
const rightPointer = (x, y) => ({
    button: 0,
    pointerId: 77,
    pointerType: 'touch',
    clientX: x,
    clientY: y,
    preventDefault() {},
    stopPropagation() {},
});
assert.equal(controller.beginStagePress(rightPointer(300, 110)), true);
assert.equal(controller.endStagePress(rightPointer(300, 110)), true);
roi.dispatch('pointerdown', rightPointer(300, 110));
roi.dispatch('pointermove', rightPointer(310, 110));
const pointBeforeCancel = { ...controller.state.point };
roi.dispatch('pointercancel', rightPointer(390, 150));
assert.deepEqual({ ...controller.state.point }, pointBeforeCancel);
assert.equal(controller.state.roiDragPointerId, null);
integrationViewer.state.pixelLensEnabled = true;
controller.render();
assert.equal(lens.hidden, false);
assert.equal(lensImage.dataset.source, 'right.png');

integrationViewer.state.mode = 'grid';
integrationViewer.gridView = {
    entries() {
        return [{
            clipIdx: 1,
            image: rightImage,
            unavailable: false,
            width: 200,
            height: 100,
        }];
    },
    clipIndexFromTarget() { return 1; },
};
controller.state.point = point(50, 25, 100, 50);
controller.state.anchorClipIdx = 0;
controller.state.locked = true;
controller.render();
roi.dispatch('pointerdown', rightPointer(301.5, 111.5));
roi.dispatch('pointermove', rightPointer(310, 110));
assert.equal(controller.state.anchorClipIdx, 0);
assert.equal(controller.state.point.x, 55);
roi.dispatch('pointercancel', rightPointer(310, 110));
integrationViewer.state.inspectorOpen = false;
controller.render();
assert.equal(roi.hidden, true);
assert.equal(lens.hidden, true);

console.log(JSON.stringify({
    equalDimensions: true,
    mismatchedDimensions: true,
    renderedBoxBounds: true,
    anchors: ['slider-left', 'slider-right', 'single', 'diff', 'blink', 'grid-cell'],
    gestureThreshold: model.MAX_GESTURE_DISTANCE,
    decodedPixelLensGeometry: true,
    blinkForwardPlacement: true,
    composedGestureThreshold: true,
    contextTimerCancelled: true,
    directRoiCancelPreservedPoint: true,
    pagedGridDragRetainedAnchor: true,
    nudgeBounds: true,
    inactiveUiCleared: true,
    samplerRecoveredAfterTaint: true,
    unavailableSampling: true,
    staleStateCleared: true,
}));
