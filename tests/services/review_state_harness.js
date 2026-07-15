'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const asset = path.join(__dirname, '..', '..', 'src', 'frame_compare', 'services', 'report', 'assets', 'review_state.js');
vm.runInThisContext(`${fs.readFileSync(asset, 'utf8')}\nglobalThis.__ReviewState = ReviewState;`, { filename: asset });
const R = globalThis.__ReviewState;
const reportId = `report_${'a'.repeat(32)}`;
const context = { reportId, payloadVersion: '1.0', frameCount: 1001, clipCount: 3 };

class Storage {
    constructor(initial = null) { this.value = initial; this.failRead = false; this.failWrite = false; this.writes = 0; }
    getItem() { if (this.failRead) throw new Error('denied'); return this.value; }
    setItem(_key, value) { if (this.failWrite) throw new Error('quota'); this.value = value; this.writes += 1; }
}

const bytes = (text) => new TextEncoder().encode(text);
const exported = (reviews, overrides = {}) => JSON.stringify({
    format: 'frame-compare-review', schema_version: 1,
    report: { id: reportId, payload_version: '1.0' }, reviews,
    exported_at: '2026-07-14T16:30:00.000Z', ...overrides,
});

const storage = new Storage();
const state = R.create({ ...context, storage });
assert.equal(state.storageKey, `frame-compare:report-review:v1:${reportId}`);
state.mutate(2, { bookmark: true, tag: 'artifact', note: 'line\r\n😀', preferred_clip_id: 'clip:1' });
assert.equal(state.get(2).note, 'line\n😀');
assert.equal(storage.writes, 1);
assert.equal(storage.value.includes('exported_at'), false);
const exact = state.exportText(new Date('2026-07-14T16:30:00.000Z'));
assert.ok(exact.endsWith('\n'));
assert.equal(exact, state.exportText(new Date('2026-07-14T16:30:00.000Z')));
assert.deepEqual(state.parseImport(bytes(exact)), state.all());
assert.ok(exact.indexOf('"format"') < exact.indexOf('"schema_version"'));
assert.ok(exact.indexOf('"report"') < exact.indexOf('"reviews"'));
assert.ok(exact.indexOf('"reviews"') < exact.indexOf('"exported_at"'));
for (const forbidden of ['"title"', '"label"', '"path"', '"image"', '"mode"']) {
    assert.equal(exact.includes(forbidden), false);
}

state.mutate(2, { bookmark: false, tag: null, note: '', preferred_clip_id: null });
assert.equal(state.all().length, 0);
assert.throws(() => state.mutate(1, { note: '😀'.repeat(1001) }), /too long/);
assert.throws(() => state.mutate(1, { note: '\ud800' }), /surrogate/);
assert.throws(() => state.mutate(1, { bookmark: 'true' }), /boolean/);
assert.throws(() => state.mutate(1, { bookmark: true, unexpected: true }), /unknown or missing/);
assert.throws(() => R.create({ ...context, payloadVersion: '2.0', storage: null }), /identity/);
assert.throws(
    () => state.parseImport(new Uint8Array(R.constants.MAX_BYTES + 1)),
    new RegExp(`exceeds ${R.constants.MAX_BYTES.toLocaleString('en-US')} bytes`),
);
assert.throws(() => state.parseImport(Uint8Array.from([0xff])), /strict UTF-8/);
assert.throws(() => state.parseImport(bytes(`\ufeff${exported([])}`)), /BOM/);

const record = (ordinal, note = '') => ({ frame_ordinal: ordinal, bookmark: true, tag: null, note, preferred_clip_id: null });
for (const bad of [
    exported([record(1), record(1)]),
    exported([record(2), record(1)]),
    exported([record(1001)]),
    exported([{ ...record(1), preferred_clip_id: 'clip:3' }]),
    exported([{ ...record(1), preferred_clip_id: 'clip:01' }]),
    exported([{ ...record(1), extra: true }]),
    exported([], { extra: true }),
    exported([]).replace('"reviews":[]', '"reviews":[],"__proto__":{}'),
    exported([]).replace('"payload_version":"1.0"', '"payload_version":"1.0","constructor":{}'),
    exported([record(1)]).replace('"bookmark":true', '"bookmark":true,"prototype":{}'),
    exported([]).replace('"schema_version":1', '"schema_version":0'),
    exported([]).replace('"schema_version":1', '"schema_version":2'),
    exported([record(1, '\ud800')]),
]) assert.throws(() => state.parseImport(bytes(bad)));

const maliciousText = '<img src=x onerror=alert(1)><script>alert(2)</script>';
assert.equal(state.parseImport(bytes(exported([record(7, maliciousText)])))[0].note, maliciousText);
assert.equal(state.parseImport(bytes(exported([record(7, 'one\r\ntwo\rthree')])))[0].note, 'one\ntwo\nthree');

const other = exported([]).replace(reportId, `report_${'b'.repeat(32)}`);
assert.throws(() => state.parseImport(bytes(other)), new RegExp(R.constants.REPORT_MISMATCH.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));

state.mutate(1, { bookmark: true });
state.mutate(2, { bookmark: true });
const incoming = state.parseImport(bytes(exported([record(2, 'changed'), record(3)])));
let preview = state.preview(incoming);
assert.deepEqual(preview.counts, { add: 1, change: 1, remove: 0, unchanged: 1 });
assert.equal(state.apply(preview), true);
assert.equal(state.get(2).note, '');
preview = state.preview(incoming, 'merge', 'use-imported');
assert.equal(state.apply(preview), true);
assert.equal(state.get(2).note, 'changed');
preview = state.preview(incoming, 'replace', 'keep-local');
assert.equal(preview.counts.remove, 1);
assert.equal(state.apply(preview), true);
assert.deepEqual(state.all().map((item) => item.frame_ordinal), [2, 3]);

const beforeMemory = state.all();
const beforeBytes = storage.value;
storage.failWrite = true;
const failedPreview = state.preview([record(4)], 'replace');
assert.equal(state.apply(failedPreview), false);
assert.deepEqual(state.all(), beforeMemory);
assert.equal(storage.value, beforeBytes);
assert.throws(
    () => state.apply({ ...failedPreview, importedRecords: [{ ...record(4), unexpected: true }] }),
    /unknown or missing/,
);

const quotaStorage = new Storage();
const quota = R.create({ ...context, storage: quotaStorage });
quota.mutate(5, { bookmark: true });
const quotaBytes = quotaStorage.value;
quotaStorage.failWrite = true;
quota.mutate(5, { note: 'kept in memory' });
assert.equal(quota.get(5).note, 'kept in memory');
assert.equal(quotaStorage.value, quotaBytes);
assert.equal(quota.status().unsaved, true);
assert.match(quota.status().warning, /could not be saved/);

const memory = R.create({ ...context, storage: null });
assert.equal(memory.apply(memory.preview([record(8)], 'replace')), true);
assert.equal(memory.get(8).bookmark, true);
assert.equal(memory.status().warning, R.constants.PERSISTENCE_WARNING);

const deniedStorage = new Storage();
deniedStorage.failRead = true;
const denied = R.create({ ...context, storage: deniedStorage });
assert.equal(denied.status().memoryOnly, true);
assert.equal(denied.status().warning, R.constants.PERSISTENCE_WARNING);

const corruptBytes = '{bad';
const corrupt = new Storage(corruptBytes);
const ignored = R.create({ ...context, storage: corrupt });
assert.equal(ignored.all().length, 0);
assert.equal(corrupt.value, corruptBytes);
assert.match(ignored.status().warning, /corrupt or unsupported/);

const ceiling = R.create({ ...context, storage: null });
for (let index = 0; index < 1000; index += 1) ceiling.mutate(index, { bookmark: true });
assert.throws(
    () => ceiling.mutate(1000, { bookmark: true }),
    new RegExp(`limit of ${R.constants.MAX_RECORDS.toLocaleString('en-US')} reached`),
);

const mergeCeiling = R.create({ ...context, storage: null });
for (let index = 0; index < 501; index += 1) mergeCeiling.mutate(index, { bookmark: true });
const disjointImport = Array.from({ length: 500 }, (_, index) => record(index + 501));
const mergeOverflow = mergeCeiling.preview(disjointImport, 'merge');
assert.throws(() => mergeCeiling.apply(mergeOverflow), /record count/);
assert.equal(mergeCeiling.all().length, 501);

console.log(JSON.stringify({ records: state.all().length, exactRoundTrip: true, atomicRollback: true, boundaryCases: true }));
