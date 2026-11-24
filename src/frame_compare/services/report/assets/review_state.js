const ReviewState = (() => {
    'use strict';

    const FORMAT = 'frame-compare-review';
    const SCHEMA_VERSION = 1;
    const MAX_NOTE_SCALARS = 1000;
    const TAGS = new Set([null, 'artifact', 'detail', 'motion', 'color', 'other']);
    const PERSISTENCE_WARNING = 'Changes are kept only for this session. Export review JSON to keep them.';
    const REPORT_MISMATCH = 'This review belongs to a different report. No changes were made.';

    class ReviewStateError extends Error {}

    function requireObject(value, label) {
        if (!value || typeof value !== 'object' || Array.isArray(value)) {
            throw new ReviewStateError(`${label} must be an object.`);
        }
    }

    function normalizedNote(value) {
        return value.replace(/\r\n?/g, '\n');
    }

    function scalarLength(value) {
        return [...value].length;
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

    function validateRecord(record, context, allowDefault = false) {
        requireObject(record, 'Review record');
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
        const normalized = {
            frame_ordinal: record.frame_ordinal,
            bookmark: record.bookmark,
            tag: record.tag,
            note,
            preferred_clip_id: record.preferred_clip_id,
        };
        if (!allowDefault && isDefault(normalized)) {
            throw new ReviewStateError('All-default review records are not stored.');
        }
        return normalized;
    }

    function validateRecords(records, context) {
        if (!Array.isArray(records)) throw new ReviewStateError('Reviews must be an array.');
        const ordinals = new Set();
        return Array.from(records, record => {
            const validated = validateRecord(record, context);
            if (ordinals.has(validated.frame_ordinal)) {
                throw new ReviewStateError('Review frame ordinals must be unique.');
            }
            ordinals.add(validated.frame_ordinal);
            return validated;
        }).sort((left, right) => left.frame_ordinal - right.frame_ordinal);
    }

    function validateDocument(document, context) {
        requireObject(document, 'Review document');
        if (document.format !== FORMAT || document.schema_version !== SCHEMA_VERSION) {
            throw new ReviewStateError('Unsupported review format or schema version.');
        }
        requireObject(document.report, 'Review report identity');
        if (document.report.id !== context.reportId) throw new ReviewStateError(REPORT_MISMATCH);
        if (document.report.payload_version !== context.payloadVersion) {
            throw new ReviewStateError('Review payload version does not match this report.');
        }
        return validateRecords(document.reviews, context);
    }

    function storedDocument(context, records) {
        return {
            format: FORMAT,
            schema_version: SCHEMA_VERSION,
            report: { id: context.reportId, payload_version: context.payloadVersion },
            reviews: records,
        };
    }

    function serialize(document) {
        return `${JSON.stringify(document, null, 2)}\n`;
    }

    function mapFrom(records) {
        return new Map(records.map(record => [record.frame_ordinal, record]));
    }

    function create(options) {
        const context = {
            reportId: options.reportId,
            payloadVersion: options.payloadVersion,
            frameCount: options.frameCount,
            clipCount: options.clipCount,
        };
        if (!/^report_[0-9a-f]{32}$/.test(context.reportId) || context.payloadVersion !== '1.4') {
            throw new ReviewStateError('Current report identity is invalid.');
        }
        const storageKey = `frame-compare:report-review:v1:${context.reportId}`;
        const storage = options.storage;
        let records = new Map();
        let memoryOnly = !storage;
        let warning = memoryOnly ? PERSISTENCE_WARNING : '';

        function sortedRecords() {
            return [...records.values()].sort((left, right) => left.frame_ordinal - right.frame_ordinal);
        }

        let stored = null;
        if (storage) {
            try {
                stored = storage.getItem(storageKey);
            } catch {
                memoryOnly = true;
                warning = PERSISTENCE_WARNING;
            }
        }
        if (stored !== null) {
            try {
                records = mapFrom(validateDocument(JSON.parse(stored), context));
            } catch {
                warning = 'Stored review data is corrupt or unsupported; it was ignored and left untouched.';
            }
        }

        function save() {
            if (memoryOnly) return false;
            try {
                storage.setItem(storageKey, serialize(storedDocument(context, sortedRecords())));
                warning = '';
                return true;
            } catch {
                memoryOnly = true;
                warning = PERSISTENCE_WARNING;
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
            const validated = validateRecord(next, context, true);
            if (isDefault(validated)) records.delete(frameOrdinal);
            else records.set(frameOrdinal, validated);
            return save();
        }

        function exportText(now = new Date()) {
            return serialize({
                ...storedDocument(context, sortedRecords()),
                exported_at: now.toISOString(),
            });
        }

        function parseImport(text) {
            let parsed;
            try {
                parsed = JSON.parse(text);
            } catch (error) {
                if (!(error instanceof SyntaxError)) throw error;
                throw new ReviewStateError('Import is not valid JSON.');
            }
            return validateDocument(parsed, context);
        }

        function replaceAll(importedRecords) {
            records = mapFrom(validateRecords(importedRecords, context));
            return save();
        }

        return {
            storageKey,
            get: ordinal => canonicalRecord(records.get(ordinal) || defaultRecord(ordinal)),
            all: () => sortedRecords().map(canonicalRecord),
            mutate,
            exportText,
            parseImport,
            replaceAll,
            status: () => ({ memoryOnly, warning, count: records.size }),
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
        let importGeneration = 0;
        let renderedFrameOrdinal = null;
        let initialWarningPending = Boolean(model.status().warning);

        function showStatus({ action = '', error = false, announce = true } = {}) {
            const { warning, count } = model.status();
            const message = [action, warning].filter(Boolean).join(' ')
                || `${count} review record${count === 1 ? '' : 's'} saved in this browser.`;
            viewer.setText(viewer.dom.reviewStatus, message);
            viewer.dom.reviewStatus.dataset.tone = error || warning ? 'warning' : 'saved';
            if (announce) viewer.announce(message);
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
            showStatus({ announce: initialWarningPending });
            initialWarningPending = false;
        }

        function populatePreferredOptions() {
            const options = [new Option('No preferred clip', '')];
            viewer.state.data.clips.forEach((clip, index) => {
                options.push(new Option(ViewerFormat.clipDisplay(clip), `clip:${index}`));
            });
            viewer.dom.reviewPreferred.replaceChildren(...options);
        }

        function mutate(patch) {
            try {
                const saved = model.mutate(viewer.state.currentFrameIdx, patch);
                showStatus({ announce: !saved });
            } catch (error) {
                render({ force: true });
                showStatus({ action: error.message, error: true });
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
                showStatus({ action: 'Review JSON exported.' });
            } catch (error) {
                showStatus({ action: error.message, error: true });
            }
        }

        async function readImport(input) {
            const generation = ++importGeneration;
            try {
                const file = input.files?.[0];
                if (!file) return;
                if (!file.name.toLowerCase().endsWith('.json')) {
                    throw new ReviewStateError('Choose one .json review file.');
                }
                const text = await file.text();
                if (generation !== importGeneration) return;
                const imported = model.parseImport(text);
                const { count } = model.status();
                if (count > 0) {
                    const savedLabel = count === 1 ? 'record' : 'records';
                    const importedLabel = imported.length === 1 ? 'record' : 'records';
                    if (!window.confirm(
                        `Replace ${count} saved review ${savedLabel} with ${imported.length} imported ${importedLabel}?`,
                    )) {
                        showStatus({ action: 'Import cancelled. No changes were made.' });
                        return;
                    }
                }
                model.replaceAll(imported);
                render({ force: true });
                showStatus({ action: 'Review import applied.' });
            } catch (error) {
                if (generation !== importGeneration) return;
                const message = error.message || String(error);
                const suffix = message.includes('No changes were made.') ? '' : ' No changes were made.';
                showStatus({ action: message + suffix, error: true });
            } finally {
                if (generation === importGeneration) input.value = '';
            }
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
                const normalized = normalizedNote(event.target.value);
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
                event => readImport(event.target),
            );
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
            MAX_NOTE_SCALARS,
            PERSISTENCE_WARNING,
            REPORT_MISMATCH,
        },
    };
})();
