const ReviewState = (() => {
    'use strict';

    const FORMAT = 'frame-compare-review';
    const SCHEMA_VERSION = 1;
    const MAX_BYTES = 8388608;
    const MAX_RECORDS = 1000;
    const MAX_NOTE_SCALARS = 1000;
    const MAX_BYTES_LABEL = MAX_BYTES.toLocaleString('en-US');
    const MAX_RECORDS_LABEL = MAX_RECORDS.toLocaleString('en-US');
    const TAGS = new Set([null, 'artifact', 'detail', 'motion', 'color', 'other']);
    const DANGEROUS_KEYS = new Set(['__proto__', 'prototype', 'constructor']);
    const PERSISTENCE_WARNING = 'Review changes will not persist in this browser; export to keep them.';
    const REPORT_MISMATCH = 'This review belongs to a different report. No changes were made.';
    const encoder = new TextEncoder();

    class ReviewStateError extends Error {}

    function ownKeys(value, expected, label) {
        if (!value || typeof value !== 'object' || Array.isArray(value)) {
            throw new ReviewStateError(`${label} must be an object.`);
        }
        const keys = Object.keys(value);
        if (keys.length !== expected.length || keys.some((key) => !expected.includes(key))) {
            throw new ReviewStateError(`${label} has unknown or missing keys.`);
        }
    }

    function rejectDangerousKeys(value) {
        if (!value || typeof value !== 'object') return;
        for (const key of Object.keys(value)) {
            if (DANGEROUS_KEYS.has(key)) throw new ReviewStateError('Import contains a dangerous key.');
            rejectDangerousKeys(value[key]);
        }
    }

    function normalizedNote(value) {
        return value.replace(/\r\n?/g, '\n');
    }

    function scalarLength(value) {
        let length = 0;
        for (const character of value) {
            const codePoint = character.codePointAt(0);
            if (codePoint >= 0xd800 && codePoint <= 0xdfff) {
                throw new ReviewStateError('Review note contains an invalid Unicode surrogate.');
            }
            length += 1;
        }
        return length;
    }

    function defaultRecord(frameOrdinal) {
        return { frame_ordinal: frameOrdinal, bookmark: false, tag: null, note: '', preferred_clip_id: null };
    }

    function isDefault(record) {
        return !record.bookmark && record.tag === null && record.note === '' && record.preferred_clip_id === null;
    }

    function canonicalRecord(record) {
        return {
            frame_ordinal: record.frame_ordinal,
            bookmark: record.bookmark,
            tag: record.tag,
            note: record.note,
            preferred_clip_id: record.preferred_clip_id,
        };
    }

    function sameRecord(left, right) {
        return JSON.stringify(left) === JSON.stringify(right);
    }

    function validateRecord(record, context, allowDefault = false) {
        ownKeys(record, ['frame_ordinal', 'bookmark', 'tag', 'note', 'preferred_clip_id'], 'Review record');
        if (!Number.isInteger(record.frame_ordinal) || record.frame_ordinal < 0 || record.frame_ordinal >= context.frameCount) {
            throw new ReviewStateError('Review frame ordinal is out of range.');
        }
        if (typeof record.bookmark !== 'boolean') throw new ReviewStateError('Review bookmark must be boolean.');
        if (!TAGS.has(record.tag)) throw new ReviewStateError('Review tag is invalid.');
        if (typeof record.note !== 'string') {
            throw new ReviewStateError('Review note is invalid or too long.');
        }
        const note = normalizedNote(record.note);
        if (scalarLength(note) > MAX_NOTE_SCALARS) {
            throw new ReviewStateError('Review note is invalid or too long.');
        }
        if (record.preferred_clip_id !== null) {
            if (typeof record.preferred_clip_id !== 'string' || !/^clip:\d+$/.test(record.preferred_clip_id)) {
                throw new ReviewStateError('Preferred clip is invalid.');
            }
            const clipOrdinal = Number(record.preferred_clip_id.slice(5));
            if (
                !Number.isInteger(clipOrdinal)
                || clipOrdinal < 0
                || clipOrdinal >= context.clipCount
                || record.preferred_clip_id !== `clip:${clipOrdinal}`
            ) {
                throw new ReviewStateError('Preferred clip is out of range.');
            }
        }
        const normalized = canonicalRecord({ ...record, note });
        if (!allowDefault && isDefault(normalized)) {
            throw new ReviewStateError('All-default review records are not stored.');
        }
        return normalized;
    }

    function validateRecords(records, context) {
        if (!Array.isArray(records) || records.length > MAX_RECORDS) {
            throw new ReviewStateError('Review record count is invalid.');
        }
        let previous = -1;
        return records.map((record) => {
            const validated = validateRecord(record, context);
            if (validated.frame_ordinal <= previous) {
                throw new ReviewStateError('Review frame ordinals must be unique and sorted.');
            }
            previous = validated.frame_ordinal;
            return validated;
        });
    }

    function validateDocument(document, context, exported) {
        rejectDangerousKeys(document);
        ownKeys(
            document,
            exported ? ['format', 'schema_version', 'report', 'reviews', 'exported_at'] : ['format', 'schema_version', 'report', 'reviews'],
            'Review document',
        );
        if (document.format !== FORMAT || document.schema_version !== SCHEMA_VERSION) {
            throw new ReviewStateError('Unsupported review format or schema version.');
        }
        ownKeys(document.report, ['id', 'payload_version'], 'Review report identity');
        if (typeof document.report.id !== 'string' || !/^report_[0-9a-f]{32}$/.test(document.report.id)) {
            throw new ReviewStateError('Review report ID is invalid.');
        }
        if (document.report.id !== context.reportId) throw new ReviewStateError(REPORT_MISMATCH);
        if (document.report.payload_version !== context.payloadVersion) {
            throw new ReviewStateError('Review payload version does not match this report.');
        }
        const reviews = validateRecords(document.reviews, context);
        if (exported) {
            if (typeof document.exported_at !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(document.exported_at)) {
                throw new ReviewStateError('Export timestamp is invalid.');
            }
            const timestamp = new Date(document.exported_at);
            if (!Number.isFinite(timestamp.getTime()) || timestamp.toISOString() !== document.exported_at) {
                throw new ReviewStateError('Export timestamp is invalid.');
            }
        }
        return reviews;
    }

    function storedDocument(context, records) {
        return {
            format: FORMAT,
            schema_version: SCHEMA_VERSION,
            report: { id: context.reportId, payload_version: context.payloadVersion },
            reviews: records.map(canonicalRecord),
        };
    }

    function serialize(document) {
        const text = `${JSON.stringify(document, null, 2)}\n`;
        if (encoder.encode(text).byteLength > MAX_BYTES) throw new ReviewStateError(`Review JSON exceeds ${MAX_BYTES_LABEL} bytes.`);
        return text;
    }

    function mapFrom(records) {
        return new Map(records.map((record) => [record.frame_ordinal, canonicalRecord(record)]));
    }

    function create(options) {
        const context = {
            reportId: options.reportId,
            payloadVersion: options.payloadVersion,
            frameCount: options.frameCount,
            clipCount: options.clipCount,
        };
        if (!/^report_[0-9a-f]{32}$/.test(context.reportId) || context.payloadVersion !== '1.0') {
            throw new ReviewStateError('Current report identity is invalid.');
        }
        const storageKey = `frame-compare:report-review:v1:${context.reportId}`;
        let storage = options.storage ?? null;
        let records = new Map();
        let memoryOnly = !storage;
        let unsaved = false;
        let warning = memoryOnly ? PERSISTENCE_WARNING : '';

        function sortedRecords(source = records) {
            return [...source.values()].sort((left, right) => left.frame_ordinal - right.frame_ordinal);
        }

        if (storage) {
            try {
                const bytes = storage.getItem(storageKey);
                if (bytes !== null) {
                    if (encoder.encode(bytes).byteLength > MAX_BYTES) throw new ReviewStateError(`Stored review JSON exceeds ${MAX_BYTES_LABEL} bytes.`);
                    const parsed = JSON.parse(bytes);
                    records = mapFrom(validateDocument(parsed, context, false));
                }
            } catch (error) {
                warning = 'Stored review data is corrupt or unsupported; it was ignored and left untouched.';
                if (!(error instanceof ReviewStateError || error instanceof SyntaxError)) {
                    memoryOnly = true;
                    storage = null;
                    warning = PERSISTENCE_WARNING;
                }
            }
        }

        function persistMutation() {
            if (!storage) {
                unsaved = true;
                warning = PERSISTENCE_WARNING;
                return false;
            }
            try {
                storage.setItem(storageKey, serialize(storedDocument(context, sortedRecords())));
                unsaved = false;
                warning = '';
                return true;
            } catch {
                unsaved = true;
                warning = 'Review changes could not be saved; export to keep them.';
                return false;
            }
        }

        function mutate(frameOrdinal, patch) {
            if (!Number.isInteger(frameOrdinal) || frameOrdinal < 0 || frameOrdinal >= context.frameCount) {
                throw new ReviewStateError('Review frame ordinal is out of range.');
            }
            if (!patch || typeof patch !== 'object' || Array.isArray(patch)) {
                throw new ReviewStateError('Review mutation must be an object.');
            }
            const next = { ...(records.get(frameOrdinal) || defaultRecord(frameOrdinal)), ...patch, frame_ordinal: frameOrdinal };
            if (typeof next.note === 'string') next.note = normalizedNote(next.note);
            const validated = validateRecord(next, context, true);
            if (isDefault(validated)) records.delete(frameOrdinal);
            else {
                if (!records.has(frameOrdinal) && records.size >= MAX_RECORDS) throw new ReviewStateError(`Review record limit of ${MAX_RECORDS_LABEL} reached.`);
                records.set(frameOrdinal, validated);
            }
            persistMutation();
            return records.get(frameOrdinal) || defaultRecord(frameOrdinal);
        }

        function exportText(now = new Date()) {
            const timestamp = now.toISOString();
            const document = { ...storedDocument(context, sortedRecords()), exported_at: timestamp };
            const text = serialize(document);
            validateDocument(JSON.parse(text), context, true);
            return text;
        }

        function parseImport(bytes) {
            const byteArray = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
            if (byteArray.byteLength > MAX_BYTES) throw new ReviewStateError(`Import exceeds ${MAX_BYTES_LABEL} bytes.`);
            if (byteArray.length >= 3 && byteArray[0] === 0xef && byteArray[1] === 0xbb && byteArray[2] === 0xbf) {
                throw new ReviewStateError('Import must not contain a UTF-8 BOM.');
            }
            let text;
            try { text = new TextDecoder('utf-8', { fatal: true }).decode(byteArray); }
            catch { throw new ReviewStateError('Import must be strict UTF-8.'); }
            let parsed;
            try { parsed = JSON.parse(text); }
            catch { throw new ReviewStateError('Import is not valid JSON.'); }
            return validateDocument(parsed, context, true);
        }

        function preview(importedRecords, mode = 'merge', conflict = 'keep-local') {
            if (!['merge', 'replace'].includes(mode) || !['keep-local', 'use-imported'].includes(conflict)) {
                throw new ReviewStateError('Import preview options are invalid.');
            }
            const imported = mapFrom(validateRecords(importedRecords, context));
            const ordinals = new Set([...records.keys(), ...imported.keys()]);
            const counts = { add: 0, change: 0, remove: 0, unchanged: 0 };
            for (const ordinal of ordinals) {
                const local = records.get(ordinal);
                const incoming = imported.get(ordinal);
                if (!local && incoming) counts.add += 1;
                else if (local && !incoming) {
                    if (mode === 'replace') counts.remove += 1;
                    else counts.unchanged += 1;
                }
                else if (sameRecord(local, incoming)) counts.unchanged += 1;
                else counts.change += 1;
            }
            return { mode, conflict, counts, importedRecords: sortedRecords(imported) };
        }

        function candidateFor(previewValue) {
            const imported = mapFrom(previewValue.importedRecords);
            if (previewValue.mode === 'replace') return imported;
            const candidate = new Map(records);
            for (const [ordinal, incoming] of imported) {
                if (!candidate.has(ordinal) || previewValue.conflict === 'use-imported') candidate.set(ordinal, incoming);
            }
            return candidate;
        }

        function apply(previewValue) {
            const confirmedPreview = preview(
                previewValue?.importedRecords,
                previewValue?.mode,
                previewValue?.conflict,
            );
            const candidateRecords = validateRecords(
                sortedRecords(candidateFor(confirmedPreview)),
                context,
            );
            const candidate = mapFrom(candidateRecords);
            const serialized = serialize(storedDocument(context, candidateRecords));
            if (memoryOnly) {
                records = candidate;
                unsaved = true;
                warning = PERSISTENCE_WARNING;
                return true;
            }
            try { storage.setItem(storageKey, serialized); }
            catch {
                warning = 'Import could not be saved; no changes were made.';
                return false;
            }
            records = candidate;
            unsaved = false;
            warning = '';
            return true;
        }

        return {
            storageKey,
            get: (ordinal) => canonicalRecord(records.get(ordinal) || defaultRecord(ordinal)),
            all: () => sortedRecords().map(canonicalRecord),
            mutate,
            exportText,
            parseImport,
            preview,
            apply,
            status: () => ({ memoryOnly, unsaved, warning, count: records.size }),
        };
    }

    function createController(viewer) {
        const model = create({
            reportId: viewer.state.data.report_id,
            payloadVersion: viewer.state.data.version,
            frameCount: viewer.state.data.frames.length,
            clipCount: viewer.state.data.clips.length,
            storage: viewer.localStorage(),
        });
        let importRecords = null;
        let importPreview = null;
        let importToken = 0;
        let renderedFrameOrdinal = null;
        let initialWarningPending = Boolean(model.status().warning);

        function showMessage(message, warning = false, announce = true) {
            viewer.setText(viewer.dom.reviewStatus, message);
            viewer.dom.reviewStatus.dataset.tone = warning ? 'warning' : 'saved';
            if (announce) viewer.pixelInspector?.announce?.(message);
        }

        function messageWithPersistence(message) {
            const status = model.status();
            return status.warning ? `${message} ${status.warning}` : message;
        }

        function updateStatus(announce = false) {
            const status = model.status();
            const saved = status.unsaved
                ? 'Unsaved changes.'
                : `${status.count} review record${status.count === 1 ? '' : 's'} saved locally.`;
            showMessage(status.warning || saved, Boolean(status.warning), announce);
        }

        function render(options = {}) {
            if (!options.force && renderedFrameOrdinal === viewer.state.currentFrameIdx) return;
            const record = model.get(viewer.state.currentFrameIdx);
            renderedFrameOrdinal = viewer.state.currentFrameIdx;
            viewer.setText(
                viewer.dom.reviewFrame,
                `Frame ${viewer.state.currentFrameIdx + 1} of ${viewer.state.data.frames.length}`,
            );
            viewer.dom.reviewBookmark.checked = record.bookmark;
            viewer.dom.reviewTag.value = record.tag || '';
            viewer.dom.reviewNote.value = record.note;
            viewer.setText(viewer.dom.reviewNoteCount, `${scalarLength(record.note)} / ${MAX_NOTE_SCALARS}`);
            viewer.dom.reviewPreferred.value = record.preferred_clip_id || '';
            updateStatus(initialWarningPending);
            initialWarningPending = false;
        }

        function populatePreferredOptions() {
            const options = [new Option('No preferred clip', '')];
            viewer.state.data.clips.forEach((clip, index) => {
                options.push(new Option(clip.label || `Clip ${index + 1}`, `clip:${index}`));
            });
            viewer.dom.reviewPreferred.replaceChildren(...options);
        }

        function mutate(patch) {
            try {
                model.mutate(viewer.state.currentFrameIdx, patch);
                updateImportPreview();
                updateStatus(Boolean(model.status().warning));
            } catch (error) {
                render({ force: true });
                showMessage(error.message, true);
            }
        }

        function exportReview() {
            try {
                const text = model.exportText(new Date());
                const url = URL.createObjectURL(new Blob([text], { type: 'application/json;charset=utf-8' }));
                const link = document.createElement('a');
                link.href = url;
                link.download = `${viewer.state.data.report_id}-review.json`;
                link.click();
                window.setTimeout(() => URL.revokeObjectURL(url), 0);
                const message = messageWithPersistence('Review JSON exported.');
                showMessage(message, Boolean(model.status().warning));
            } catch (error) {
                showMessage(error.message, true);
            }
        }

        function importChoice(name, fallback) {
            return viewer.dom.reviewPreview
                .querySelector(`input[name="${name}"]:checked`)
                ?.value || fallback;
        }

        function resetImportChoices() {
            viewer.dom.reviewPreview
                .querySelectorAll('input[name="review-import-mode"]')
                .forEach(input => { input.checked = input.value === 'merge'; });
            viewer.dom.reviewPreview
                .querySelectorAll('input[name="review-import-conflict"]')
                .forEach(input => { input.checked = input.value === 'keep-local'; });
        }

        function updateImportPreview(announce = false) {
            if (!importRecords) return;
            importPreview = model.preview(
                importRecords,
                importChoice('review-import-mode', 'merge'),
                importChoice('review-import-conflict', 'keep-local'),
            );
            const { add, change, remove, unchanged } = importPreview.counts;
            viewer.setText(
                viewer.dom.reviewPreviewCounts,
                `Add ${add} · Change ${change} · Remove ${remove} · Unchanged ${unchanged}`,
            );
            if (announce) {
                showMessage(
                    `Import preview: add ${add}, change ${change}, remove ${remove}, unchanged ${unchanged}.`,
                );
            }
        }

        function cancelImport() {
            importToken += 1;
            importRecords = null;
            importPreview = null;
            viewer.dom.reviewPreview.hidden = true;
            viewer.dom.reviewImport.value = '';
            resetImportChoices();
        }

        async function readImport(file) {
            if (!file) return;
            cancelImport();
            const token = ++importToken;
            if (!file.name.toLowerCase().endsWith('.json')) {
                cancelImport();
                showMessage('Choose one .json review file. No changes were made.', true);
                return;
            }
            if (file.size > MAX_BYTES) {
                cancelImport();
                showMessage(`Import exceeds ${MAX_BYTES_LABEL} bytes. No changes were made.`, true);
                return;
            }
            try {
                const bytes = await file.arrayBuffer();
                if (token !== importToken) return;
                importRecords = model.parseImport(bytes);
                resetImportChoices();
                viewer.dom.reviewPreview.hidden = false;
                updateImportPreview();
                const { add, change, remove, unchanged } = importPreview.counts;
                showMessage(
                    `Import ready: add ${add}, change ${change}, remove ${remove}, unchanged ${unchanged}. Review choices before applying.`,
                );
            } catch (error) {
                if (token !== importToken) return;
                cancelImport();
                showMessage(error.message, true);
            }
        }

        function applyImport() {
            if (!importPreview) return;
            try {
                if (!model.apply(importPreview)) {
                    showMessage('Import could not be saved; no changes were made.', true);
                    return;
                }
            } catch (error) {
                showMessage(`${error.message} No changes were made.`, true);
                return;
            }
            cancelImport();
            render({ force: true });
            const message = messageWithPersistence('Review import applied.');
            showMessage(message, Boolean(model.status().warning));
        }

        function bind() {
            viewer.dom.reviewBookmark.addEventListener(
                'change',
                event => mutate({ bookmark: event.target.checked }),
            );
            viewer.dom.reviewTag.addEventListener(
                'change',
                event => mutate({ tag: event.target.value || null }),
            );
            viewer.dom.reviewNote.addEventListener('input', event => {
                const normalized = event.target.value.replace(/\r\n?/g, '\n');
                const scalars = [...normalized];
                if (scalars.length > MAX_NOTE_SCALARS) {
                    event.target.value = scalars.slice(0, MAX_NOTE_SCALARS).join('');
                }
                mutate({ note: event.target.value });
                viewer.setText(
                    viewer.dom.reviewNoteCount,
                    `${[...event.target.value].length} / ${MAX_NOTE_SCALARS}`,
                );
            });
            viewer.dom.reviewPreferred.addEventListener(
                'change',
                event => mutate({ preferred_clip_id: event.target.value || null }),
            );
            viewer.dom.reviewExport.addEventListener('click', exportReview);
            viewer.dom.reviewImportTrigger.addEventListener(
                'click',
                () => viewer.dom.reviewImport.click(),
            );
            viewer.dom.reviewImport.addEventListener(
                'change',
                event => readImport(event.target.files?.[0]),
            );
            viewer.dom.reviewPreview.addEventListener('change', () => updateImportPreview(true));
            viewer.dom.reviewImportApply.addEventListener('click', applyImport);
            viewer.dom.reviewImportCancel.addEventListener('click', cancelImport);
        }

        populatePreferredOptions();
        return { bind, model, render };
    }

    return {
        create,
        createController,
        Error: ReviewStateError,
        constants: {
            FORMAT,
            SCHEMA_VERSION,
            MAX_BYTES,
            MAX_RECORDS,
            MAX_NOTE_SCALARS,
            PERSISTENCE_WARNING,
            REPORT_MISMATCH,
        },
    };
})();
