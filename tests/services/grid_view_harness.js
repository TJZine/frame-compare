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
    'grid_view.js',
);
const context = {};
const source = `${fs.readFileSync(assetPath, 'utf8')}\nglobalThis.__GridView = GridView;`;
vm.runInNewContext(source, context, { filename: assetPath });
const grid = context.__GridView;

assert.equal(grid.layoutName(2, 769, 2), 'two');
assert.equal(grid.layoutName(3, 1200, 3), 'three-wide');
assert.equal(grid.layoutName(3, 1199, 3), 'three-wrap');
assert.equal(grid.layoutName(4, 768, 1), 'mobile');
assert.equal(grid.layoutName(6, 1600, 4), 'four');
assert.equal(grid.layoutName(6, 767, 1), 'mobile');

assert.deepEqual([...grid.visibleIndexes(0, 6, false)], [0, 1, 2, 3]);
assert.deepEqual([...grid.visibleIndexes(4, 6, false)], [4, 5]);
assert.deepEqual([...grid.visibleIndexes(3, 6, true)], [3]);
assert.equal(grid.visibleIndexes(0, 100, false).length, 4);
assert.equal(grid.visibleIndexes(0, 100, true).length, 1);
assert.equal(grid.normalizedStart(5, 6, false), 4);
assert.equal(grid.normalizedStart(5, 6, true), 5);
assert.equal(grid.positionText(0, 6, false), 'Clips 1\u20134 of 6');
assert.equal(grid.positionText(4, 6, false), 'Clips 5\u20136 of 6');
assert.equal(grid.positionText(3, 6, true), 'Clip 4 of 6');

function fakeElement(tagName = 'div', rect = { left: 0, top: 0, width: 400, height: 240 }) {
    const listeners = new Map();
    const attributes = new Map();
    const classes = new Set();
    const element = {
        tagName: tagName.toUpperCase(),
        rect,
        parentElement: null,
        children: [],
        dataset: {},
        hidden: false,
        disabled: false,
        textContent: '',
        className: '',
        naturalWidth: tagName === 'img' ? 1920 : 0,
        naturalHeight: tagName === 'img' ? 1080 : 0,
        style: {
            values: {},
            setProperty(name, value) { this.values[name] = value; },
        },
        classList: {
            toggle(name, force) {
                if (force) classes.add(name);
                else classes.delete(name);
            },
        },
        addEventListener(type, listener) {
            const entries = listeners.get(type) || [];
            entries.push(listener);
            listeners.set(type, entries);
        },
        dispatch(type, event = {}) {
            for (const listener of listeners.get(type) || []) listener(event);
        },
        append(...children) {
            children.forEach(child => { child.parentElement = this; });
            this.children.push(...children);
        },
        replaceChildren(...children) {
            if (this.contains?.(context.document?.activeElement)) {
                context.document.activeElement = null;
            }
            this.children.forEach(child => { child.parentElement = null; });
            this.children = [];
            this.append(...children);
        },
        remove() {
            if (!this.parentElement) return;
            this.parentElement.children = this.parentElement.children.filter(child => child !== this);
            this.parentElement = null;
        },
        setAttribute(name, value) { attributes.set(name, String(value)); },
        getAttribute(name) { return attributes.get(name) ?? null; },
        removeAttribute(name) {
            attributes.delete(name);
            if (name === 'src') this.src = '';
        },
        getBoundingClientRect() { return this.rect; },
        matches(selector) {
            if (selector.startsWith('.')) {
                return this.className.split(/\s+/).includes(selector.slice(1));
            }
            const dataMatch = selector.match(/^\[data-([a-z-]+)\]$/);
            if (!dataMatch) return false;
            const key = dataMatch[1].replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
            return Object.hasOwn(this.dataset, key);
        },
        closest(selector) {
            let current = this;
            while (current) {
                if (current.matches?.(selector)) return current;
                current = current.parentElement;
            }
            return null;
        },
        querySelector(selector) { return this.querySelectorAll(selector)[0] || null; },
        querySelectorAll(selector) {
            const found = [];
            const visit = node => {
                node.children.forEach(child => {
                    if (child.matches?.(selector)) found.push(child);
                    visit(child);
                });
            };
            visit(this);
            return found;
        },
        contains(candidate) {
            if (candidate === this) return true;
            return this.children.some(child => child.contains?.(candidate));
        },
        focus() {
            this.focused = true;
            if (context.document) context.document.activeElement = this;
            this.dispatch('focus');
        },
    };
    return element;
}

const gridRoot = fakeElement('section', { left: 0, top: 0, width: 1300, height: 700 });
const cells = fakeElement('div', { left: 0, top: 0, width: 1284, height: 684 });
const frameError = fakeElement();
const controls = fakeElement();
const previous = fakeElement('button');
const next = fakeElement('button');
const position = fakeElement('span');
gridRoot.append(frameError, cells);
const mediaQuery = {
    matches: false,
    listener: null,
    addEventListener(type, listener) {
        if (type === 'change') this.listener = listener;
    },
};
context.document = {
    activeElement: null,
    getElementById(id) {
        return {
            'rv-grid': gridRoot,
            'btn-grid-prev': previous,
            'btn-grid-next': next,
        }[id] || null;
    },
    querySelector(selector) {
        return {
            '[data-grid-cells]': cells,
            '[data-grid-frame-error]': frameError,
            '[data-control-scope="grid"]': controls,
            '[data-grid-position]': position,
        }[selector] || null;
    },
    createElement(tagName) { return fakeElement(tagName); },
};
context.window = {
    innerWidth: 1300,
    matchMedia() { return mediaQuery; },
    addEventListener(type, listener) {
        if (type === 'resize') this.resizeListener = listener;
    },
    requestAnimationFrame(callback) { callback(); },
};
context.ResizeObserver = undefined;

const announcements = [];
const clips = Array.from({ length: 6 }, (_, index) => ({
    label: `Clip ${index + 1}`,
    display: {
        primary: `Clip ${index + 1}`,
        release: '',
        control: `Clip ${index + 1}`,
        micro: `Clip ${index + 1}`,
        filename: `clip-${index + 1}.mkv`,
    },
    resolution: [1920, 1080],
    size_bytes: 17 * 1024 ** 3,
    signal: { is_hdr: false },
}));
clips[1].resolution = [1080, 1920];
clips[2].resolution = [2560, 1080];
const frame = {
    number: 12,
    images: clips.map((_, index) => ({ src: `clip-${index + 1}.png` })),
};
const viewer = {
    state: {
        data: { clips, default_selection: { left_clip_index: 0 } },
        currentFrameIdx: 0,
        zoom: 1,
        panX: 0,
        panY: 0,
        leftClipIdx: 3,
        activeClipIdx: 1,
    },
    dom: { stage: gridRoot },
    currentFrame() { return frame; },
    clipDisplay(clip, profile = 'control') { return clip.display[profile]; },
    sourceHudLabel(clip, profile = 'control') {
        return `${clip.display[profile]} • ${clip.resolution[0]}×${clip.resolution[1]} • SDR • 17.00 GiB`;
    },
    clipAccessibleName(clip) { return `${clip.display.primary} — ${clip.display.filename}`; },
    referenceClipIndex() { return 0; },
    clampPan() {},
    updateInspectorData() {},
    updateCurrentFrameMetadata() {},
    announce(message) { announcements.push(message); },
    lens: { refresh() {}, sync() {} },
};
const owner = grid.create(viewer);
owner.bind();
owner.setActive(true);
owner.render();
gridRoot.rect.width = 768;
context.window.resizeListener();
assert.equal(owner.state.mobile, true);
gridRoot.rect.width = 1300;
context.window.resizeListener();
assert.equal(owner.state.mobile, false);
assert.equal(cells.children.length, 4);
assert.deepEqual([...owner.indexes()], [0, 1, 2, 3]);
assert.equal(controls.hidden, false);
assert.equal(position.textContent, 'Clips 1–4 of 6');
assert.equal(cells.children[0].dataset.reference, 'true');
assert.match(cells.children[0].getAttribute('aria-label'), /Reference/);
assert.equal(cells.children[3].dataset.reference, 'false');
assert.doesNotMatch(cells.children[3].getAttribute('aria-label'), /Reference/);
assert.equal(cells.children[1].dataset.active, 'true');
assert.match(cells.children[1].getAttribute('aria-label'), /Active/);
assert.equal(
    cells.children[0].querySelector('.rv-grid-label-text').textContent,
    'Clip 1 • 1920×1080 • SDR • 17.00 GiB',
);

const mixedImages = cells.querySelectorAll('.rv-grid-image');
mixedImages.forEach((image, index) => {
    [image.naturalWidth, image.naturalHeight] = clips[index].resolution;
    image.dispatch('load');
});
viewer.state.zoom = 2;
viewer.state.panX = 0.1;
viewer.state.panY = -0.05;
owner.syncViewport();
const landscapePan = Number.parseFloat(mixedImages[0].style.values['--grid-pan-x']);
const portraitPan = Number.parseFloat(mixedImages[1].style.values['--grid-pan-x']);
assert.equal(landscapePan / Number.parseFloat(mixedImages[0].style.width), 0.1);
assert.equal(portraitPan / Number.parseFloat(mixedImages[1].style.width), 0.1);
assert.notEqual(landscapePan, portraitPan);
const zoomClient = { x: 300, y: 150 };
const zoomAnchor = owner.zoomAnchorForPoint(zoomClient.x, zoomClient.y);
const nextZoom = 3;
const zoomPan = owner.panForZoomAnchor(
    zoomAnchor,
    zoomClient.x,
    zoomClient.y,
    nextZoom,
);
const contentAfterZoom = (
    zoomClient.x - zoomAnchor.centerX - zoomPan.x * zoomAnchor.width
) / (zoomAnchor.width * nextZoom);
assert.ok(Math.abs(contentAfterZoom - zoomAnchor.contentX) < 1e-12);
const panBasis = owner.panBasisForPoint(zoomClient.x, zoomClient.y);
assert.equal(panBasis.width, Number.parseFloat(mixedImages[0].style.width));
assert.equal(panBasis.height, Number.parseFloat(mixedImages[0].style.height));

const focusedCell = cells.children[2];
focusedCell.focus();
assert.equal(viewer.state.activeClipIdx, 2);
owner.render();
assert.equal(context.document.activeElement.dataset.clipIndex, '2');
assert.equal(context.document.activeElement.dataset.active, 'true');
mediaQuery.matches = true;
mediaQuery.listener();
assert.deepEqual([...owner.indexes()], [2]);
assert.equal(context.document.activeElement.dataset.clipIndex, '2');
mediaQuery.matches = false;
mediaQuery.listener();
assert.deepEqual([...owner.indexes()], [0, 1, 2, 3]);
assert.equal(context.document.activeElement.dataset.clipIndex, '2');

const staleImage = cells.children[0].querySelector('.rv-grid-image');
owner.render();
const currentCell = cells.children[0];
const currentImage = currentCell.querySelector('.rv-grid-image');
const currentError = currentCell.querySelector('[data-grid-error]');
currentImage.dispatch('error');
assert.equal(owner.state.failed.has(0), true);
assert.equal(currentError.hidden, false);
staleImage.dispatch('load');
assert.equal(owner.state.failed.has(0), true);
currentImage.dispatch('load');
assert.equal(owner.state.failed.has(0), false);
assert.equal(currentError.hidden, true);

currentImage.dispatch('error');
const retry = currentCell.querySelector('[data-grid-retry]');
assert.ok(retry);
retry.dispatch('click', { stopPropagation() {} });
assert.equal(currentCell.dataset.status, 'loading');
assert.equal(currentCell.focused, true);

owner.render();
cells.children.forEach(cell => cell.querySelector('.rv-grid-image').dispatch('error'));
assert.equal(frameError.hidden, false);
cells.children[0].querySelector('.rv-grid-image').dispatch('load');
assert.equal(frameError.hidden, true);

next.dispatch('click');
assert.deepEqual([...owner.indexes()], [4, 5]);
assert.equal(cells.children.length, 2);
assert.equal(position.textContent, 'Clips 5–6 of 6');
assert.equal(announcements.at(-1), 'Clips 5–6 of 6 visible.');

mediaQuery.matches = true;
mediaQuery.listener();
assert.deepEqual([...owner.indexes()], [4]);
assert.equal(cells.children.length, 1);
assert.equal(position.textContent, 'Clip 5 of 6');
owner.clear();
assert.equal(cells.children.length, 0);

console.log(JSON.stringify({
    layouts: ['two', 'three-wide', 'three-wrap', 'four', 'mobile'],
    desktopPageLimit: grid.DESKTOP_PAGE_SIZE,
    desktopPages: [[0, 1, 2, 3], [4, 5]],
    mobilePageLimit: grid.pageSize(true),
    payloadOrderPreserved: true,
    realOwnerLifecycle: true,
    staleEventsIgnored: true,
    retryState: true,
    allFailedRecoverable: true,
    normalizedMixedAspectViewport: true,
    focusRetainedAcrossRenderAndReflow: true,
    referenceAndActiveCues: true,
}));
