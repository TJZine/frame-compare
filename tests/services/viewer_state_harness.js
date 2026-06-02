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
    return {
        value: '',
        classList: {
            toggle() {},
        },
        style: {
            values: {},
            setProperty(name, value) {
                this.values[name] = value;
            },
        },
    };
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
        document: {
            addEventListener() {},
        },
        window: {
            localStorage: storageApi,
        },
    };
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
        rightLayer: fakeElement(),
        alignmentPreset: fakeElement(),
        alignX: fakeElement(),
        alignY: fakeElement(),
        btnAlignToggle: fakeElement(),
    };
    viewer.render = function renderStateOnly() {
        this.persistViewportState();
    };

    if (savedState !== null) {
        storage.set(viewer.state.storageKey, JSON.stringify(savedState));
    }

    viewer.applyDefaultSelection();
    viewer.restorePersistedState();
    return { viewer, storage, storageKey: viewer.state.storageKey };
}

function persisted(storage, storageKey) {
    return JSON.parse(storage.get(storageKey));
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
    assert.equal(viewer.state.alignX, 5);
    assert.equal(viewer.state.alignY, -2);
    assert.deepEqual(Object.keys(viewer.state.pairAlignments).sort(), ['0:1', '1:0']);
    summary.restoreFourClip = {
        clipCount: viewer.clipCount(),
        leftClipIdx: viewer.state.leftClipIdx,
        rightClipIdx: viewer.state.rightClipIdx,
        activeClipIdx: viewer.state.activeClipIdx,
        restoredPairKeys: Object.keys(viewer.state.pairAlignments).sort(),
        currentAlignment: [viewer.state.alignX, viewer.state.alignY],
    };
}

{
    const { viewer } = loadViewer({
        clipCount: 2,
        savedState: {
            mode: 'diff',
            leftClipIdx: 3,
            rightClipIdx: 9,
            activeClipIdx: 9,
            pairAlignments: {
                '0:1': { alignmentPreset: 'custom', alignX: 2, alignY: 4 },
                '3:9': { alignmentPreset: 'custom', alignX: 99, alignY: 99 },
            },
        },
    });

    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 1);
    assert.equal(viewer.state.activeClipIdx, 0);
    assert.equal(viewer.state.alignX, 2);
    assert.equal(viewer.state.alignY, 4);
    assert.deepEqual(Object.keys(viewer.state.pairAlignments), ['0:1']);
}

{
    const { viewer, storage, storageKey } = loadViewer({ clipCount: 4 });

    viewer.setManualAlignment(4, 5);
    viewer.setRightClip(2);
    assert.equal(viewer.state.leftClipIdx, 0);
    assert.equal(viewer.state.rightClipIdx, 2);
    assert.equal(viewer.state.alignX, 0);
    assert.equal(viewer.state.alignY, 0);

    viewer.setManualAlignment(-1, 8);
    viewer.setRightClip(1);
    assert.equal(viewer.state.alignX, 4);
    assert.equal(viewer.state.alignY, 5);

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

console.log(JSON.stringify(summary));
