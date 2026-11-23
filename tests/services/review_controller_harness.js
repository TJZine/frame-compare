async function reviewControllerContracts() {
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
            textContent: '',
            value: '',
            addEventListener(type, handler) { handlers.set(type, handler); },
            fire(type) { return handlers.get(type)?.({ target: this }); },
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
    const confirmations = [];
    let confirmed = false;
    const context = {
        Blob: FakeBlob,
        Date,
        Map,
        Option: class Option {
            constructor(text, value) { this.text = text; this.value = value; }
        },
        Set,
        URL: {
            createObjectURL(blob) {
                const url = `blob:review-${++nextUrl}`;
                objectUrls.set(url, blob);
                return url;
            },
            revokeObjectURL(url) { revoked.push(url); },
        },
        document: documentObject,
        window: {
            setTimeout(callback) { timers.push(callback); },
            confirm(message) {
                confirmations.push(message);
                return confirmed;
            },
        },
    };
    context.globalThis = context;

    const assets = path.join(__dirname, '..', '..', 'src', 'frame_compare', 'services', 'report', 'assets');
    const formatAsset = path.join(assets, 'viewer_format.js');
    const asset = path.join(assets, 'review_state.js');
    vm.runInNewContext(`${fs.readFileSync(formatAsset, 'utf8')}\n${fs.readFileSync(asset, 'utf8')}\nglobalThis.__ReviewState = ReviewState;`, context, { filename: asset });
    const ReviewState = context.__ReviewState;
    const reportId = `report_${'c'.repeat(32)}`;

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
            report: { id: reportId, payload_version: '1.4' },
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
        return { name, async text() { return text; } };
    }

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
    };
    dom.reviewImport.click = () => { dom.reviewImport.opened = true; };

    let storage = new Storage();
    const announcements = [];
    const viewer = {
        dom,
        state: {
            currentFrameIdx: 0,
            data: {
                report_id: reportId,
                version: '1.4',
                frames: [{}, {}, {}],
                clips: [clipDisplay('Reference'), clipDisplay('Encode')],
            },
        },
        clipDisplay(clip) { return clip.display.control; },
        localStorage: () => storage,
        announce(message) { announcements.push(message); },
        setText(target, text) { target.textContent = String(text); },
    };

    const controller = ReviewState.createController(viewer);
    controller.bind();
    controller.render();

    const { model } = controller;
    const status = () => dom.reviewStatus.textContent;
    function selectFile(selected) {
        dom.reviewImport.value = selected.name;
        dom.reviewImport.files = [selected];
        return dom.reviewImport.fire('change');
    }

    async function chooseFile(selected) {
        assert.equal(dom.reviewImport.value, '');
        await selectFile(selected);
        assert.equal(dom.reviewImport.value, '');
    }

    function deferredFile(name) {
        let resolve;
        let reject;
        const pending = new Promise((resolveRead, rejectRead) => {
            resolve = resolveRead;
            reject = rejectRead;
        });
        return { file: { name, text: () => pending }, resolve, reject };
    }

    assert.equal(dom.reviewPreferred.replaceCount, 1);
    assert.equal(announcements.length, 0);
    assert.equal(status(), '0 review records saved in this browser.');
    dom.reviewImportTrigger.click();
    assert.equal(dom.reviewImport.opened, true);
    const initial = record(1, 'initial 😀');
    await chooseFile(file('initial.json', exported([initial])));
    assert.deepEqual(confirmations, []);
    assert.equal(status(), 'Review import applied.');
    assert.deepEqual(JSON.parse(storage.value).reviews, [initial]);

    viewer.state.currentFrameIdx = 1;
    controller.render();
    assert.equal(dom.reviewFrame.textContent, 'Frame 2 of 3');
    assert.equal(dom.reviewBookmark.checked, true);
    assert.equal(dom.reviewTag.value, '');
    assert.equal(dom.reviewNote.value, initial.note);
    assert.equal(dom.reviewNoteCount.textContent, '9 / 1000');
    assert.equal(dom.reviewPreferred.value, '');
    assert.equal(status(), '1 review record saved in this browser.');

    const savedRecord = () => JSON.parse(storage.value).reviews[0];
    dom.reviewBookmark.checked = false;
    dom.reviewBookmark.fire('change');
    assert.equal(savedRecord().bookmark, false);
    dom.reviewTag.value = 'detail';
    dom.reviewTag.fire('change');
    assert.equal(savedRecord().tag, 'detail');
    dom.reviewPreferred.value = 'clip:1';
    dom.reviewPreferred.fire('change');
    assert.equal(savedRecord().preferred_clip_id, 'clip:1');
    const note = '😀'.repeat(1000);
    dom.reviewNote.value = note + 'x';
    dom.reviewNote.fire('input');
    assert.equal(dom.reviewNote.value, note);
    assert.equal(savedRecord().note, note);
    assert.equal(dom.reviewNoteCount.textContent, '1000 / 1000');

    const literalNote = '<img src=x onerror=alert(1)>';
    dom.reviewNote.value = literalNote;
    dom.reviewNote.fire('input');
    assert.equal(savedRecord().note, literalNote);
    viewer.announce('Lens on.');
    controller.render();
    assert.equal(dom.reviewNote.value, literalNote);
    assert.equal(dom.reviewPreferred.replaceCount, 1);
    assert.equal(announcements.at(-1), 'Lens on.');

    dom.reviewExport.click();
    const download = downloads.at(-1);
    assert.equal(download.download, `${reportId}-review.json`);
    const downloadedBlob = objectUrls.get(download.href);
    assert.equal(downloadedBlob.type, 'application/json;charset=utf-8');
    assert.equal(downloadedBlob.parts.length, 1);
    assert.equal(downloadedBlob.parts[0].endsWith('\n'), true);
    const downloaded = JSON.parse(downloadedBlob.parts[0]);
    assert.equal(downloaded.report.id, reportId);
    assert.deepEqual(downloaded.reviews, [savedRecord()]);
    assert.equal(revoked.includes(download.href), false);
    timers.splice(0).forEach(callback => callback());
    assert.equal(revoked.includes(download.href), true);
    assert.equal(status(), 'Review JSON exported.');

    const incoming = [record(0, 'first note'), record(2, 'second note')];
    const replacement = file('replacement.json', exported(incoming));
    const originalBytes = storage.value;
    await chooseFile(replacement);
    const question = 'Replace 1 saved review record with 2 imported records?';
    assert.deepEqual(confirmations, [question]);
    assert.equal(status(), 'Import cancelled. No changes were made.');
    assert.equal(model.get(1).note, literalNote);
    assert.equal(storage.value, originalBytes);

    confirmed = true;
    await chooseFile(replacement);
    assert.deepEqual(confirmations, [question, question]);
    assert.equal(status(), 'Review import applied.');
    assert.equal(model.get(1).note, '');
    assert.equal(dom.reviewNote.value, '');
    assert.deepEqual(JSON.parse(storage.value).reviews, incoming);

    const replacedBytes = storage.value;
    await chooseFile(file('invalid.json', '{bad'));
    assert.equal(status(), 'Import is not valid JSON. No changes were made.');
    await chooseFile({
        name: 'review.txt',
        async text() { assert.fail('a refused extension must not be read'); },
    });
    assert.equal(status(), 'Choose one .json review file. No changes were made.');
    await chooseFile({
        name: 'unreadable.json',
        async text() { throw new Error('File could not be read.'); },
    });
    assert.equal(status(), 'File could not be read. No changes were made.');
    assert.equal(confirmations.length, 2);
    assert.equal(storage.value, replacedBytes);
    assert.deepEqual(JSON.parse(JSON.stringify(model.all())), incoming);
    assert.equal(dom.reviewStatus.dataset.tone, 'warning');

    const refusedStatus = 'Choose one .json review file. No changes were made.';
    const stale = deferredFile('slow.json');
    const staleImport = selectFile(stale.file);
    await selectFile(file('newer.txt', exported(incoming)));
    assert.equal(dom.reviewImport.value, '');
    assert.equal(status(), refusedStatus);
    stale.resolve(exported([initial]));
    await staleImport;
    assert.equal(confirmations.length, 2);
    assert.equal(storage.value, replacedBytes);
    assert.deepEqual(JSON.parse(JSON.stringify(model.all())), incoming);
    assert.equal(status(), refusedStatus);

    const staleFailure = deferredFile('slow-error.json');
    const staleFailedImport = selectFile(staleFailure.file);
    const latest = deferredFile('latest.json');
    const latestImport = selectFile(latest.file);
    staleFailure.reject(new Error('Superseded read failed.'));
    await staleFailedImport;
    assert.equal(confirmations.length, 2);
    assert.equal(status(), refusedStatus);
    assert.equal(dom.reviewImport.value, latest.file.name);
    latest.resolve(exported(incoming));
    await latestImport;
    assert.equal(confirmations.length, 3);
    assert.equal(status(), 'Review import applied.');
    assert.equal(dom.reviewImport.value, '');
    assert.equal(storage.value, replacedBytes);

    const warning = ReviewState.constants.PERSISTENCE_WARNING;
    storage.failWrite = true;
    await chooseFile(file('memory.json', exported([initial])));
    assert.equal(confirmations.at(-1), 'Replace 2 saved review records with 1 imported record?');
    assert.equal(status(), `Review import applied. ${warning}`);
    assert.equal(dom.reviewStatus.dataset.tone, 'warning');
    assert.equal(model.get(1).note, initial.note);
    assert.equal(dom.reviewNote.value, initial.note);
    assert.equal(storage.value, replacedBytes);
    dom.reviewBookmark.checked = false;
    dom.reviewBookmark.fire('change');
    assert.equal(model.get(1).bookmark, false);
    assert.equal(status(), warning);
    assert.equal(announcements.at(-1), warning);
    dom.reviewExport.click();
    assert.equal(status(), `Review JSON exported. ${warning}`);

    for (const [unavailableStorage, expected] of [
        [null, warning],
        [Object.assign(new Storage(), { value: '{bad' }),
            'Stored review data is corrupt or unsupported; it was ignored and left untouched.'],
    ]) {
        storage = unavailableStorage;
        const starting = ReviewState.createController(viewer);
        const before = announcements.length;
        starting.render();
        starting.render({ force: true });
        assert.deepEqual(announcements.slice(before), [expected]);
        assert.equal(status(), expected);
    }
}

module.exports = { reviewControllerContracts };
if (require.main === module) require('./harness_runner').run(module.exports);
