const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const viewportPath = path.join(
    __dirname, '..', '..', 'src', 'frame_compare', 'services', 'report', 'assets', 'viewport.js'
);
const context = {};
vm.runInNewContext(
    `${fs.readFileSync(viewportPath, 'utf8')}\nglobalThis.__Viewport = Viewport;`,
    context,
    { filename: viewportPath },
);

function element(rect = { left: 0, top: 0, width: 200, height: 100, right: 200 }) {
    return {
        value: '',
        textContent: '',
        dataset: {},
        attributes: {},
        classes: new Set(),
        style: {
            values: {},
            setProperty(name, value) { this.values[name] = value; },
        },
        classList: {
            toggle(name, enabled) {
                if (enabled) this.owner?.classes.add(name);
                else this.owner?.classes.delete(name);
            },
            add() {},
            remove() {},
        },
        setAttribute(name, value) { this.attributes[name] = String(value); },
        getBoundingClientRect() { return rect; },
    };
}

function makeViewer() {
    const canvas = element({ left: 0, top: 0, width: 200, height: 100, right: 200 });
    const stage = element({ left: 0, top: 0, width: 100, height: 50, right: 100 });
    const sizer = element({ left: 0, top: 0, width: 200, height: 100, right: 200 });
    const refresh = { grid: 0, lens: 0 };
    const viewer = {
        state: {
            data: { clips: [{}, {}, {}] },
            mode: 'slider',
            zoom: 1,
            fitMode: 'actual',
            panX: 0,
            panY: 0,
            revealPercent: 50,
            alignmentPreset: 'none',
            alignX: 0,
            alignY: 0,
            pairAlignments: {},
            leftClipIdx: 0,
            rightClipIdx: 1,
            rawAlignX: null,
            rawAlignY: null,
        },
        dom: {
            stage,
            canvas,
            sizerImg: sizer,
            zoomRange: element(),
            zoomVal: element(),
            fitBtns: ['actual', 'width', 'height'].map(fit => ({ ...element(), dataset: { fit } })),
            leftLayer: element(),
            divider: element(),
            alignmentPreset: element(),
            alignX: element(),
            alignY: element(),
            btnAlignToggle: element(),
            alignmentStatus: element(),
        },
        gridView: {
            isActive() { return false; },
            syncViewport() { refresh.grid += 1; },
            panBasisForPoint() { return { width: 200, height: 100 }; },
            panBounds() { return { x: 0.5, y: 0.25 }; },
        },
        lens: { refresh() { refresh.lens += 1; } },
        numberOrDefault(value, fallback) {
            const number = Number(value);
            return Number.isFinite(number) ? number : fallback;
        },
        clipCount() { return this.state.data.clips.length; },
        persistViewportState() { this.viewport.storeCurrentPairAlignment(); },
        updateInspectorData() {},
        updateFitButtons() { return this.viewport.updateFitButtons(); },
        updateAlignmentStatus() { return this.viewport.updateAlignmentStatus(); },
    };
    viewer.viewport = context.__Viewport.create(viewer);
    return { viewer, viewport: viewer.viewport, refresh };
}

const { viewer, viewport, refresh } = makeViewer();

viewport.setZoom(10);
assert.equal(viewer.state.zoom, 4);
viewport.setZoom(0);
assert.equal(viewer.state.zoom, 0.25);

viewer.state.zoom = 1;
viewer.state.panX = 0;
viewer.state.panY = 0;
viewport.zoomAtPoint(75, 25, 2);
assert.equal(viewer.state.zoom, 2);
assert.equal(viewer.state.panX, -25);
assert.equal(viewer.state.panY, 0);

viewer.state.panX = 999;
viewer.state.panY = -999;
viewport.clampPan();
assert.deepEqual([viewer.state.panX, viewer.state.panY], [50, -25]);

viewer.state.zoom = 1;
viewer.state.fitMode = 'width';
viewport.applyFitMode({ resetPan: true });
assert.equal(viewer.state.zoom, 0.5);
assert.deepEqual([viewer.state.panX, viewer.state.panY], [0, 0]);

viewer.state.mode = 'grid';
viewer.gridView.isActive = () => true;
viewer.state.panX = 0;
viewer.state.panY = 0;
viewport.panByPixels(20, -10, 0, 0, { save: false });
assert.deepEqual([viewer.state.panX, viewer.state.panY], [0.1, -0.1]);

viewer.state.mode = 'slider';
viewer.state.zoom = 2;
viewer.state.panX = 12;
viewer.state.panY = -8;
viewport.resetViewport();
assert.equal(viewer.state.zoom, 1);
assert.deepEqual([viewer.state.panX, viewer.state.panY], [0, 0]);

viewer.state.pairAlignments = {
    '0:1': { alignmentPreset: 'custom', alignX: 4, alignY: -3 },
    '1:0': { alignmentPreset: 'right-1', alignX: 99, alignY: 99 },
    '0:9': { alignmentPreset: 'custom', alignX: 9, alignY: 9 },
};
viewer.state.pairAlignments = viewport.normalizedPairAlignments(viewer.state.pairAlignments);
assert.deepEqual(Object.keys(viewer.state.pairAlignments).sort(), ['0:1', '1:0']);
viewer.state.leftClipIdx = 1;
viewer.state.rightClipIdx = 0;
viewport.loadCurrentPairAlignment();
assert.deepEqual([viewer.state.alignX, viewer.state.alignY], [1, 0]);

viewport.setManualAlignment(-7, 5);
assert.equal(viewer.state.pairAlignments['1:0'].alignmentPreset, 'custom');
assert.deepEqual(
    [viewer.state.pairAlignments['1:0'].alignX, viewer.state.pairAlignments['1:0'].alignY],
    [-7, 5],
);

viewer.state.revealPercent = 37;
viewport.updateSlider();
assert.equal(viewer.dom.canvas.style.values['--reveal-percent'], '37%');
assert.ok(refresh.grid > 0);
assert.ok(refresh.lens > 0);

console.log(JSON.stringify({
    canonicalStateShared: !Object.hasOwn(viewport, 'state') && viewport.state === viewer.state,
    zoomBounds: true,
    pointerAnchor: true,
    panClampAndGridConversion: true,
    fitAndReset: true,
    directionalAlignment: true,
    revealAndRefresh: true,
}));
