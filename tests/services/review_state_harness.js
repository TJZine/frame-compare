function reviewStateContracts() {
    'use strict';

    const assert = require('node:assert/strict');
    const fs = require('node:fs');
    const path = require('node:path');
    const vm = require('node:vm');

    const asset = path.join(__dirname, '..', '..', 'src', 'frame_compare', 'services', 'report', 'assets', 'review_state.js');
    vm.runInThisContext(`${fs.readFileSync(asset, 'utf8')}\nglobalThis.__ReviewState = ReviewState;`, { filename: asset });
    const R = globalThis.__ReviewState;
    const reportId = 'report_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
    const context = { reportId, payloadVersion: '1.4', frameCount: 5, clipCount: 3 };
    const storageKey = `frame-compare:report-review:v1:${reportId}`;
    const { PERSISTENCE_WARNING, REPORT_MISMATCH } = R.constants;

    class Storage {
        constructor(value = null) {
            this.value = value;
            this.writes = 0;
            this.failWrite = false;
        }
        getItem(key) {
            assert.equal(key, storageKey);
            return this.value;
        }
        setItem(key, value) {
            assert.equal(key, storageKey);
            this.writes += 1;
            if (this.failWrite) throw new Error('quota');
            this.value = value;
        }
    }

    const create = storage => R.create({ ...context, storage });
    const record = (frame_ordinal, note = '') => ({
        frame_ordinal, bookmark: false, tag: null, note, preferred_clip_id: null,
    });
    const document = (reviews, overrides = {}) => ({
        format: 'frame-compare-review', schema_version: 1,
        report: { id: reportId, payload_version: '1.4' }, reviews, ...overrides,
    });

    // Stored notes load without writing, and the payload guard stays at 1.4.
    const initial = record(2, 'stored note');
    const existing = new Storage(JSON.stringify(document([initial])));
    const loaded = create(existing);
    assert.equal(loaded.storageKey, storageKey);
    assert.deepEqual(loaded.get(2), initial);
    assert.deepEqual(loaded.all(), [initial]);
    assert.deepEqual(loaded.status(), { memoryOnly: false, warning: '', count: 1 });
    assert.equal(existing.writes, 0);
    assert.throws(() => R.create({ ...context, payloadVersion: '1.3', storage: existing }), /identity/);

    // Corrupt bytes are untouched until the next successful mutation.
    const corrupt = new Storage('{bad');
    const recovered = create(corrupt);
    assert.deepEqual(recovered.all(), []);
    assert.equal(corrupt.value, '{bad');
    assert.equal(corrupt.writes, 0);
    assert.deepEqual(recovered.status(), {
        memoryOnly: false,
        warning: 'Stored review data is corrupt or unsupported; it was ignored and left untouched.',
        count: 0,
    });
    assert.equal(recovered.mutate(2, { note: initial.note }), true);
    assert.deepEqual(JSON.parse(corrupt.value), document([initial]));
    assert.equal(recovered.status().warning, '');

    // A storage read exception enters memory-only mode before any write.
    let deniedWrites = 0;
    const denied = create({
        getItem() { throw new SyntaxError('browser denied storage'); },
        setItem() { deniedWrites += 1; },
    });
    assert.deepEqual(denied.status(), { memoryOnly: true, warning: PERSISTENCE_WARNING, count: 0 });
    assert.equal(denied.mutate(2, { note: initial.note }), false);
    assert.equal(deniedWrites, 0);
    assert.deepEqual(denied.status(), { memoryOnly: true, warning: PERSISTENCE_WARNING, count: 1 });
    assert.deepEqual(denied.all(), [initial]);

    // Writes are synchronous, canonical, sorted and have the stored shape.
    const storage = new Storage();
    const state = create(storage);
    assert.equal(state.mutate(2, { note: initial.note }), true);
    const first = record(0, 'line\n😀');
    assert.equal(state.mutate(0, { note: 'line\r\n😀' }), true);
    assert.equal(storage.writes, 2);
    assert.deepEqual(JSON.parse(storage.value), document([first, initial]));

    // An all-default patch deletes the persisted record.
    assert.equal(state.mutate(2, { note: '' }), true);
    assert.deepEqual(state.get(2), record(2));
    assert.deepEqual(JSON.parse(storage.value), document([first]));

    // The limit is measured after normalization and accepts supplementary scalars.
    const limit = '😀'.repeat(1000);
    assert.equal(state.mutate(2, { note: limit }), true);
    assert.throws(() => state.mutate(2, { note: limit + '😀' }), /too long/);
    assert.equal(state.get(2).note, limit);
    assert.equal(JSON.parse(storage.value).reviews[1].note, limit);

    // A failed write keeps the new record in memory and disables later writes.
    const quota = new Storage(JSON.stringify(document([initial])));
    const limited = create(quota);
    quota.failWrite = true;
    assert.equal(limited.mutate(0, { note: first.note }), false);
    assert.deepEqual(limited.all(), [first, initial]);
    assert.deepEqual(JSON.parse(quota.value), document([initial]));
    assert.deepEqual(limited.status(), { memoryOnly: true, warning: PERSISTENCE_WARNING, count: 2 });
    quota.failWrite = false;
    assert.equal(limited.replaceAll([first]), false);
    assert.deepEqual(limited.all(), [first]);
    assert.equal(quota.writes, 1);

    // Export adds a deterministic ISO timestamp, with the same report identity and records.
    const timestamp = '2026-07-14T16:30:00.000Z';
    const text = state.exportText(new Date(timestamp));
    assert.equal(text.endsWith('\n'), true);
    assert.deepEqual(JSON.parse(text), document([first, record(2, limit)], { exported_at: timestamp }));

    // Every rejected document leaves both current records and storage intact.
    const badImports = [
        ['bad JSON', '{bad', /Import is not valid JSON/],
        ['non-object document', 'null', /Review document must be an object/],
        ['non-object report', document([], { report: [] }), /Review report identity must be an object/],
        ['wrong format', document([], { format: 'wrong' }), /Unsupported review format/],
        ['wrong schema version', document([], { schema_version: 2 }), /Unsupported review format/],
        ['different report ID', document([], { report: { id: 'report_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', payload_version: '1.4' } }), REPORT_MISMATCH],
        ['wrong payload version', document([], { report: { id: reportId, payload_version: '1.3' } }), /payload version/],
        ['non-array reviews', document({}), /Reviews must be an array/],
        ['out-of-range frame', document([record(5, 'bad')]), /frame ordinal is out of range/],
        ['bad bookmark', document([{ ...initial, bookmark: 'true' }]), /bookmark must be boolean/],
        ['bad tag', document([{ ...initial, tag: 'bad' }]), /tag is invalid/],
        ['bad preferred clip', document([{ ...initial, preferred_clip_id: 'clip:3' }]), /Preferred clip is out of range/],
        ['oversize note', document([record(2, limit + 'x')]), /too long/],
        ['repeated frame', document([initial, initial]), /ordinals must be unique/],
        ['all-default record', document([record(2)]), /All-default review records are not stored/],
    ];
    const before = state.all();
    const saved = storage.value;
    for (const [label, input, expected] of badImports) {
        const json = typeof input === 'string' ? input : JSON.stringify(input);
        assert.throws(() => state.parseImport(json), error => (
            error instanceof R.Error && (typeof expected === 'string'
                ? error.message === expected
                : expected.test(error.message))
        ), label);
        assert.deepEqual(state.all(), before, label);
        assert.equal(storage.value, saved, label);
    }

    // Unknown fields and timestamps are ignored, and unsorted imports are canonicalized.
    const later = record(4, 'later\nline');
    const imported = state.parseImport(JSON.stringify(document([
        { ...later, note: 'later\rline', extra_record_key: true },
        { ...initial },
    ], {
        report: { id: reportId, payload_version: '1.4', extra_report_key: true },
        extra_document_key: true,
        exported_at: false,
    })));
    assert.deepEqual(imported, [initial, later]);
    assert.deepEqual(state.all(), before);
    assert.equal(state.replaceAll(imported), true);
    assert.deepEqual(state.all(), [initial, later]);
    assert.deepEqual(JSON.parse(storage.value), document([initial, later]));

    // I6: A literal export from the previous schema-1 exporter.
    const baseExport = `{
  "format": "frame-compare-review",
  "schema_version": 1,
  "report": {
    "id": "report_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "payload_version": "1.4"
  },
  "reviews": [
    {
      "frame_ordinal": 1,
      "bookmark": true,
      "tag": "detail",
      "note": "base review",
      "preferred_clip_id": "clip:1"
    }
  ],
  "exported_at": "2026-07-14T16:30:00.000Z"
}
`;
    const baseRecords = state.parseImport(baseExport);
    assert.deepEqual(baseRecords, [{
        frame_ordinal: 1, bookmark: true, tag: 'detail', note: 'base review', preferred_clip_id: 'clip:1',
    }]);
    assert.equal(state.replaceAll(baseRecords), true);
    assert.equal(state.exportText(new Date(timestamp)), baseExport);
}

module.exports = { reviewStateContracts };
if (require.main === module) require('./harness_runner').run(module.exports);
