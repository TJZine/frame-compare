'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element() {
    const handlers = new Map();
    return {
        checked: false,
        children: [],
        dataset: {},
        hidden: false,
        textContent: '',
        value: '',
        addEventListener(type, handler) { handlers.set(type, handler); },
        fire(type, target = this) { return handlers.get(type)?.({ target }); },
        click() { return this.fire('click'); },
        replaceChildren(...children) {
            this.children = children;
            this.replaceCount = (this.replaceCount || 0) + 1;
        },
    };
}

class Storage {
    constructor() { this.value = null; this.failWrite = false; }
    getItem() { return this.value; }
    setItem(_key, value) {
        if (this.failWrite) throw new Error('quota');
        this.value = value;
    }
}

class FakeBlob {
    constructor(parts, options) { this.parts = parts; this.type = options.type; }
}

const timers = [];
const downloads = [];
const revoked = [];
const objectUrls = new Map();
let nextUrl = 0;
const documentObject = {
    createElement(tag) {
        assert.equal(tag, 'a');
        const link = element();
        link.click = () => downloads.push({ href: link.href, download: link.download });
        return link;
    },
};
const context = {
    Blob: FakeBlob,
    Date,
    Map,
    Option: class Option {
        constructor(text, value) { this.text = text; this.value = value; }
    },
    Set,
    TextDecoder,
    TextEncoder,
    Uint8Array,
    URL: {
        createObjectURL(blob) {
            const url = `blob:review-${++nextUrl}`;
            objectUrls.set(url, blob);
            return url;
        },
        revokeObjectURL(url) { revoked.push(url); },
    },
    document: documentObject,
    window: { setTimeout(callback) { timers.push(callback); } },
};
context.globalThis = context;

const asset = path.join(__dirname, '..', '..', 'src', 'frame_compare', 'services', 'report', 'assets', 'review_state.js');
vm.runInNewContext(`${fs.readFileSync(asset, 'utf8')}\nglobalThis.__ReviewState = ReviewState;`, context, { filename: asset });
const ReviewState = context.__ReviewState;
const reportId = `report_${'c'.repeat(32)}`;
const encoder = new TextEncoder();

function clipDisplay(label) {
    return {
        label,
        display: {
            primary: label,
            release: '',
            control: label,
            micro: label,
            filename: `${label}.mkv`,
        },
    };
}

function exported(reviews) {
    return JSON.stringify({
        format: 'frame-compare-review',
        schema_version: 1,
        report: { id: reportId, payload_version: '1.2' },
        reviews,
        exported_at: '2026-07-14T16:30:00.000Z',
    });
}

function record(ordinal, note = '') {
    return {
        frame_ordinal: ordinal,
        bookmark: true,
        tag: null,
        note,
        preferred_clip_id: null,
    };
}

function file(name, text) {
    const data = encoder.encode(text);
    return {
        name,
        size: data.byteLength,
        async arrayBuffer() { return data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength); },
    };
}

function deferredFile(name, text) {
    const data = encoder.encode(text);
    let resolve;
    const pending = new Promise((done) => { resolve = done; });
    return {
        file: {
            name,
            size: data.byteLength,
            arrayBuffer() { return pending; },
        },
        resolve() { resolve(data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength)); },
    };
}

const modeMerge = { ...element(), name: 'review-import-mode', value: 'merge', checked: true };
const modeReplace = { ...element(), name: 'review-import-mode', value: 'replace' };
const conflictLocal = { ...element(), name: 'review-import-conflict', value: 'keep-local', checked: true };
const conflictImported = { ...element(), name: 'review-import-conflict', value: 'use-imported' };
const radios = [modeMerge, modeReplace, conflictLocal, conflictImported];
const preview = element();
preview.hidden = true;
preview.querySelectorAll = selector => radios.filter(input => selector.includes(input.name));
preview.querySelector = selector => radios.find(input => selector.includes(input.name) && input.checked) || null;

const dom = {
    reviewFrame: element(),
    reviewBookmark: element(),
    reviewTag: element(),
    reviewNote: element(),
    reviewNoteCount: element(),
    reviewPreferred: element(),
    reviewStatus: element(),
    reviewExport: element(),
    reviewImportTrigger: element(),
    reviewImport: element(),
    reviewPreview: preview,
    reviewPreviewCounts: element(),
    reviewImportApply: element(),
    reviewImportCancel: element(),
};
dom.reviewImport.click = () => { dom.reviewImport.opened = true; };

const storage = new Storage();
const announcements = [];
const viewer = {
    dom,
    state: {
        currentFrameIdx: 0,
        data: {
            report_id: reportId,
            version: '1.2',
            frames: [{}, {}, {}, {}],
            clips: [clipDisplay('Reference'), clipDisplay('Encode')],
        },
    },
    clipDisplay(clip) { return clip.display.control; },
    localStorage: () => storage,
    announce(message) { announcements.push(message); },
    setText(target, text) { target.textContent = String(text); },
};

function warningViewer(storageApi) {
    const warningAnnouncements = [];
    const warningDom = {
        reviewFrame: element(),
        reviewBookmark: element(),
        reviewTag: element(),
        reviewNote: element(),
        reviewNoteCount: element(),
        reviewPreferred: element(),
        reviewStatus: element(),
    };
    return {
        announcements: warningAnnouncements,
        viewer: {
            dom: warningDom,
            state: {
                currentFrameIdx: 0,
                data: {
                    report_id: reportId,
                    version: '1.2',
                    frames: [{}],
                    clips: [clipDisplay('Reference')],
                },
            },
            clipDisplay(clip) { return clip.display.control; },
            localStorage: () => storageApi,
            announce(message) { warningAnnouncements.push(message); },
            setText(target, text) { target.textContent = String(text); },
        },
    };
}

async function main() {
    const controller = ReviewState.createController(viewer);
    controller.bind();
    controller.render();
    assert.equal(dom.reviewPreferred.replaceCount, 1);
    assert.equal(announcements.length, 0);

    dom.reviewNote.value = 'working note';
    dom.reviewNote.fire('input');
    const replacementCount = dom.reviewPreferred.replaceCount;
    viewer.announce('Lens on.');
    controller.render();
    assert.equal(dom.reviewNote.value, 'working note');
    assert.equal(dom.reviewPreferred.replaceCount, replacementCount);
    assert.equal(announcements.at(-1), 'Lens on.');

    await dom.reviewImport.fire('change', { files: [file('empty.json', exported([]))] });
    modeMerge.checked = false;
    modeReplace.checked = true;
    dom.reviewPreview.fire('change');
    dom.reviewBookmark.checked = true;
    dom.reviewBookmark.fire('change');
    assert.match(dom.reviewPreviewCounts.textContent, /Remove 1/);
    dom.reviewImportApply.click();
    assert.equal(controller.model.all().length, 0);

    await dom.reviewImport.fire('change', { files: [file('a.json', exported([record(1, 'A')]))] });
    const delayed = deferredFile('b.json', exported([record(2, 'B')]));
    const pendingRead = dom.reviewImport.fire('change', { files: [delayed.file] });
    assert.equal(dom.reviewPreview.hidden, true);
    dom.reviewImportApply.click();
    assert.equal(controller.model.all().length, 0);
    delayed.resolve();
    await pendingRead;
    assert.equal(dom.reviewPreview.hidden, false);
    assert.equal(modeMerge.checked, true);
    assert.equal(conflictLocal.checked, true);
    dom.reviewImportApply.click();
    assert.equal(controller.model.all().map(item => item.frame_ordinal).join(','), '2');

    viewer.state.currentFrameIdx = 3;
    controller.model.mutate(3, { note: '<img src=x onerror=alert(1)>' });
    controller.render();
    assert.equal(dom.reviewNote.value, '<img src=x onerror=alert(1)>');

    storage.failWrite = true;
    dom.reviewBookmark.checked = true;
    dom.reviewBookmark.fire('change');
    assert.match(dom.reviewStatus.textContent, /could not be saved/);
    assert.match(announcements.at(-1), /could not be saved/);
    storage.failWrite = false;

    dom.reviewExport.click();
    assert.equal(downloads.at(-1).download, `${reportId}-review.json`);
    const downloadUrl = downloads.at(-1).href;
    const downloadedBlob = objectUrls.get(downloadUrl);
    assert.equal(downloadedBlob.type, 'application/json;charset=utf-8');
    assert.equal(downloadedBlob.parts.length, 1);
    assert.ok(downloadedBlob.parts[0].endsWith('\n'));
    assert.equal(JSON.parse(downloadedBlob.parts[0]).report.id, reportId);
    assert.equal(revoked.includes(downloadUrl), false);
    timers.splice(0).forEach(callback => callback());
    assert.equal(revoked.includes(downloadUrl), true);

    const unavailable = warningViewer(null);
    const unavailableController = ReviewState.createController(unavailable.viewer);
    unavailableController.render();
    unavailableController.render({ force: true });
    assert.deepEqual(unavailable.announcements, [ReviewState.constants.PERSISTENCE_WARNING]);

    const corruptStorage = new Storage();
    corruptStorage.value = '{bad';
    const corrupt = warningViewer(corruptStorage);
    const corruptController = ReviewState.createController(corrupt.viewer);
    corruptController.render();
    corruptController.render({ force: true });
    assert.equal(corrupt.announcements.length, 1);
    assert.match(corrupt.announcements[0], /corrupt or unsupported/);

    console.log(JSON.stringify({
        stalePreviewRefreshed: true,
        replacementReadIsolated: true,
        stableRender: true,
        singleAnnouncements: true,
        downloadLifecycle: true,
        initialWarningsAnnouncedOnce: true,
    }));
}

main().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
