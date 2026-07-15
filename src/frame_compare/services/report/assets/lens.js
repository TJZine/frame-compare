const Lens = (() => {
    const PREFERENCES_KEY = 'frame-compare:lens-preferences:v2';
    const REPORT_KEY_PREFIX = 'frame-compare:report-lens:v1:';
    const TOUCH_GESTURE_THRESHOLD = 6;
    const MAGNIFICATIONS = [2, 3, 4, 6, 8, 12];
    const SIZES = { small: 160, medium: 240, large: 320 };
    // Mirrors the identity rail CSS: single/Diff subtract 8px insets + 10px padding
    // + 2px borders; split subtracts 8px + 6px + 2px and its 1px pane divider.
    // Character widths are conservative for the 12px and 10px mono rail fonts.
    const CAPTION_METRICS = Object.freeze({
        single: Object.freeze({ paneFraction: 1, horizontalChrome: 20, characterWidth: 8 }),
        split: Object.freeze({ paneFraction: 0.5, horizontalChrome: 17, characterWidth: 7 }),
        diff: Object.freeze({ paneFraction: 1, horizontalChrome: 20, characterWidth: 8 }),
    });
    const DEFAULT_PREFERENCES = Object.freeze({
        magnification: 4,
        size: 'medium',
        markerStyle: 'off',
    });
    const DEFAULT_REPORT_STATE = Object.freeze({
        enabled: false,
        parkedPosition: { u: 0.82, v: 0.12 },
        comparisonEnabled: false,
        comparisonTarget: null,
    });

    function clamp(value, minimum = 0, maximum = 1) {
        return Math.max(minimum, Math.min(maximum, value));
    }

    function middleEllipsis(value, maxCharacters) {
        const characters = Array.from(String(value ?? ''));
        const limit = Math.max(0, Math.floor(Number(maxCharacters) || 0));
        if (characters.length <= limit) return characters.join('');
        if (limit === 0) return '';
        if (limit === 1) return characters.at(-1);
        if (limit === 2) return `…${characters.at(-1)}`;
        const available = limit - 1;
        const trailing = Math.min(
            available - 1,
            Math.max(1, Math.ceil(available * 0.4), Math.min(4, available - 1)),
        );
        const leading = available - trailing;
        return `${characters.slice(0, leading).join('')}…${characters.slice(-trailing).join('')}`;
    }

    function captionCharacterCapacity(lensPixels, context = 'single') {
        const metrics = CAPTION_METRICS[context] || CAPTION_METRICS.single;
        const pixels = Number(lensPixels);
        if (!Number.isFinite(pixels) || pixels <= 0) return 0;
        const paneWidth = pixels * metrics.paneFraction;
        const contentWidth = Math.max(0, paneWidth - metrics.horizontalChrome);
        return Math.max(0, Math.floor(contentWidth / metrics.characterWidth));
    }

    function sourceNumber(index) {
        return `#${Number.isInteger(index) && index >= 0 ? index + 1 : '?'}`;
    }

    function compactSourceCaption(label, index, totalCapacity, options = {}) {
        const capacity = Math.max(0, Math.floor(Number(totalCapacity) || 0));
        const prefix = options.compactStructure
            ? `${sourceNumber(index)}·`
            : `${sourceNumber(index)} · `;
        const prefixCharacters = Array.from(prefix);
        if (prefixCharacters.length >= capacity) {
            return prefixCharacters.slice(0, capacity).join('');
        }
        return `${prefix}${middleEllipsis(label, capacity - prefixCharacters.length)}`;
    }

    function compactDiffCaption(leftLabel, leftIndex, rightLabel, rightIndex, totalCapacity) {
        const capacity = Math.max(0, Math.floor(Number(totalCapacity) || 0));
        const leftNumber = sourceNumber(leftIndex);
        const rightNumber = sourceNumber(rightIndex);
        const minimalStructure = `${leftNumber}↔${rightNumber}`;
        if (Array.from(minimalStructure).length > capacity) {
            return middleEllipsis(minimalStructure, capacity);
        }
        const dottedStructureLength = Array.from(`${leftNumber}·↔${rightNumber}·`).length;
        const useDots = dottedStructureLength <= capacity;
        const leftPrefix = `${leftNumber}${useDots ? '·' : ''}`;
        const rightPrefix = `${rightNumber}${useDots ? '·' : ''}`;
        const structureLength = Array.from(`${leftPrefix}↔${rightPrefix}`).length;
        const filenameCapacity = capacity - structureLength;
        const leftCapacity = Math.ceil(filenameCapacity / 2);
        const rightCapacity = filenameCapacity - leftCapacity;
        return `${leftPrefix}${middleEllipsis(leftLabel, leftCapacity)}↔${rightPrefix}${middleEllipsis(rightLabel, rightCapacity)}`;
    }

    function validDimensions(width, height) {
        return Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0;
    }

    function normalizedPoint(image, clientX, clientY) {
        const rect = image?.getBoundingClientRect?.();
        if (!rect || !validDimensions(rect.width, rect.height)) return null;
        const right = Number.isFinite(rect.right) ? rect.right : rect.left + rect.width;
        const bottom = Number.isFinite(rect.bottom) ? rect.bottom : rect.top + rect.height;
        if (
            clientX < rect.left
            || clientX > right
            || clientY < rect.top
            || clientY > bottom
        ) return null;
        return {
            u: clamp((clientX - rect.left) / rect.width),
            v: clamp((clientY - rect.top) / rect.height),
        };
    }

    function compositionPoint(image, clientX, clientY) {
        const rect = image?.getBoundingClientRect?.();
        if (!rect || !validDimensions(rect.width, rect.height)) return null;
        return {
            u: (clientX - rect.left) / rect.width,
            v: (clientY - rect.top) / rect.height,
        };
    }

    function normalizedPosition(value, fallback = DEFAULT_REPORT_STATE.parkedPosition) {
        const u = value?.u;
        const v = value?.v;
        if (typeof u !== 'number' || typeof v !== 'number' || !Number.isFinite(u) || !Number.isFinite(v)) {
            return { ...fallback };
        }
        return { u: clamp(u), v: clamp(v) };
    }

    function normalizePreferences(value) {
        const source = value && typeof value === 'object' ? value : {};
        return {
            magnification: MAGNIFICATIONS.includes(source.magnification)
                ? source.magnification
                : DEFAULT_PREFERENCES.magnification,
            size: Object.hasOwn(SIZES, source.size) ? source.size : DEFAULT_PREFERENCES.size,
            markerStyle: ['off', 'ring', 'brackets'].includes(source.markerStyle)
                ? source.markerStyle
                : DEFAULT_PREFERENCES.markerStyle,
        };
    }

    function normalizeReportState(value, clipCount = 0) {
        const source = value && typeof value === 'object' ? value : {};
        const target = source.comparisonTarget;
        return {
            enabled: typeof source.enabled === 'boolean'
                ? source.enabled
                : DEFAULT_REPORT_STATE.enabled,
            parkedPosition: normalizedPosition(source.parkedPosition),
            comparisonEnabled: typeof source.comparisonEnabled === 'boolean'
                ? source.comparisonEnabled
                : DEFAULT_REPORT_STATE.comparisonEnabled,
            comparisonTarget: Number.isInteger(target) && target >= 0 && target < clipCount
                ? target
                : null,
        };
    }

    function lensImageGeometry(
        point,
        width,
        height,
        magnification,
        lensSize,
        viewportWidth = lensSize,
    ) {
        if (
            !point
            || !Number.isFinite(point.u)
            || !Number.isFinite(point.v)
            || !validDimensions(width, height)
            || !MAGNIFICATIONS.includes(magnification)
            || !Number.isFinite(lensSize)
            || lensSize <= 0
        ) return null;
        return {
            width: width * magnification,
            height: height * magnification,
            left: viewportWidth / 2 - point.u * width * magnification,
            top: lensSize / 2 - point.v * height * magnification,
        };
    }

    function boundedPopoverPosition(
        stageRect,
        anchorRect,
        popoverRect,
        margin = 8,
        anchorOffset = 36,
    ) {
        const availableWidth = Math.max(1, stageRect.width - margin * 2);
        const availableHeight = Math.max(1, stageRect.height - margin * 2);
        const width = Math.min(popoverRect.width || 260, availableWidth);
        const height = Math.min(popoverRect.height || 320, availableHeight);
        const minimumLeft = stageRect.left + margin;
        const maximumLeft = stageRect.left + stageRect.width - margin - width;
        const preferredLeft = anchorRect.left + anchorRect.width - width;
        const globalLeft = clamp(preferredLeft, minimumLeft, Math.max(minimumLeft, maximumLeft));
        const below = anchorRect.top + anchorOffset;
        const above = anchorRect.top - height - 4;
        const preferredTop = below + height <= stageRect.top + stageRect.height - margin
            ? below
            : above;
        const minimumTop = stageRect.top + margin;
        const maximumTop = stageRect.top + stageRect.height - margin - height;
        const globalTop = clamp(preferredTop, minimumTop, Math.max(minimumTop, maximumTop));
        return {
            left: globalLeft - anchorRect.left,
            top: globalTop - anchorRect.top,
            maxWidth: availableWidth,
            maxHeight: availableHeight,
        };
    }

    function create(viewer) {
        const dom = {
            toggle: document.getElementById('btn-lens'),
            group: document.querySelector('[data-lens-palette-group]'),
            activeControls: document.querySelector('[data-lens-active-controls]'),
            lens: document.getElementById('rv-lens'),
            marker: document.getElementById('rv-lens-target'),
            grip: document.querySelector('[data-lens-drag-handle]'),
            zoomOut: document.getElementById('btn-lens-zoom-out'),
            zoomIn: document.getElementById('btn-lens-zoom-in'),
            zoomValue: document.querySelector('[data-lens-zoom]'),
            settings: document.getElementById('btn-lens-settings'),
            orientation: document.getElementById('btn-palette-orientation'),
            popover: document.getElementById('lens-settings-popover'),
            sizeButtons: document.querySelectorAll('[data-lens-size]'),
            markerButtons: document.querySelectorAll('[data-lens-marker]'),
            comparisonToggle: document.getElementById('lens-comparison-enabled'),
            comparisonTarget: document.getElementById('lens-comparison-target'),
            comparisonSettings: document.querySelector('[data-lens-comparison-settings]'),
            reset: document.getElementById('btn-lens-reset'),
            persistence: document.querySelector('[data-lens-persistence]'),
            activeImage: document.querySelector('[data-lens-image="active"]'),
            differenceImage: document.querySelector('[data-lens-image="difference"]'),
            comparisonImage: document.querySelector('[data-lens-image="comparison"]'),
            activeRole: document.querySelector('[data-lens-role="active"]'),
            activeStatus: document.querySelector('[data-lens-status="active"]'),
            activeIdentity: document.querySelector('[data-lens-identity="active"]'),
            comparisonRole: document.querySelector('[data-lens-role="comparison"]'),
            comparisonStatus: document.querySelector('[data-lens-status="comparison"]'),
            comparisonIdentity: document.querySelector('[data-lens-identity="comparison"]'),
            currentSource: document.querySelector('[data-lens-current-source]'),
        };
        const storage = viewer.localStorage();
        const reportKey = `${REPORT_KEY_PREFIX}${viewer.state.data?.report_id || 'unknown-report'}`;
        let storageReadFailed = false;
        function readStored(key) {
            if (!storage) return null;
            try {
                return JSON.parse(storage.getItem(key) || 'null');
            } catch {
                storageReadFailed = true;
                return null;
            }
        }
        const storedPreferences = readStored(PREFERENCES_KEY);
        const storedReportState = readStored(reportKey);
        const state = {
            preferences: normalizePreferences(storedPreferences),
            report: normalizeReportState(
                storedReportState,
                viewer.state.data?.clips?.length || 0,
            ),
            point: null,
            activeClipIdx: null,
            activeImage: null,
            pointer: null,
            touchPending: null,
            drag: null,
            memoryOnly: !storage || storageReadFailed,
            settingsRestoreFocus: null,
        };
        const imageRequests = {
            active: { token: 0, source: null, status: 'empty', loader: null, onLoad: null, onError: null },
            difference: { token: 0, source: null, status: 'empty', loader: null, onLoad: null, onError: null },
            comparison: { token: 0, source: null, status: 'empty', loader: null, onLoad: null, onError: null },
        };

        function cloneImage(slot) {
            return {
                active: dom.activeImage,
                difference: dom.differenceImage,
                comparison: dom.comparisonImage,
            }[slot] || null;
        }

        function clipCount() {
            return viewer.state.data?.clips?.length || 0;
        }

        function clipLabel(index) {
            return viewer.state.data?.clips?.[index]?.label || `Clip ${index + 1}`;
        }

        function fullSourceIdentity(index) {
            if (!Number.isInteger(index) || index < 0 || index >= clipCount()) {
                return 'Source unavailable.';
            }
            return `#${index + 1} · ${clipLabel(index)}`;
        }

        function compactSourceIdentity(index, size, context = 'single') {
            return compactSourceCaption(
                clipLabel(index),
                index,
                captionCharacterCapacity(size, context),
                { compactStructure: context === 'split' },
            );
        }

        function diffIdentity(leftIndex, rightIndex, size) {
            return compactDiffCaption(
                clipLabel(leftIndex),
                leftIndex,
                clipLabel(rightIndex),
                rightIndex,
                captionCharacterCapacity(size, 'diff'),
            );
        }

        function setCaption(slot, role, identity, status = '', fullIdentity = identity) {
            const roleElement = slot === 'comparison' ? dom.comparisonRole : dom.activeRole;
            const statusElement = slot === 'comparison' ? dom.comparisonStatus : dom.activeStatus;
            const identityElement = slot === 'comparison' ? dom.comparisonIdentity : dom.activeIdentity;
            if (roleElement) roleElement.textContent = role;
            if (identityElement) {
                identityElement.textContent = identity;
                identityElement.setAttribute?.('aria-label', fullIdentity);
            }
            if (statusElement) {
                statusElement.textContent = status;
                statusElement.hidden = !status;
            }
        }

        function renderCurrentSource() {
            const identity = state.report.enabled
                ? fullSourceIdentity(state.activeClipIdx)
                : 'Lens is off.';
            if (dom.currentSource) {
                dom.currentSource.textContent = identity;
                dom.currentSource.setAttribute?.('aria-label', `Current source: ${identity}`);
            }
            let lensContext = `Current source: ${identity}`;
            if (state.report.enabled && viewer.state.mode === 'diff') {
                lensContext = `Difference: ${fullSourceIdentity(viewer.state.leftClipIdx)} versus ${fullSourceIdentity(viewer.state.rightClipIdx)}`;
            } else if (state.report.enabled && comparisonShowing()) {
                lensContext = `Active: ${identity}. Comparison: ${fullSourceIdentity(state.report.comparisonTarget)}`;
            }
            dom.lens?.setAttribute?.('aria-label', `Image magnification lens. ${lensContext}`);
        }

        function sourceFor(index) {
            return viewer.currentFrame()?.images?.[index]?.src || '';
        }

        function save(key, payload) {
            if (!storage) {
                state.memoryOnly = true;
                renderPersistenceStatus();
                return false;
            }
            try {
                storage.setItem(key, JSON.stringify(payload));
                return true;
            } catch {
                state.memoryOnly = true;
                renderPersistenceStatus();
                return false;
            }
        }

        function savePreferences() {
            return save(PREFERENCES_KEY, state.preferences);
        }

        function saveReportState() {
            return save(reportKey, state.report);
        }

        function renderPersistenceStatus() {
            if (!dom.persistence) return;
            dom.persistence.textContent = state.memoryOnly
                ? 'Settings are available for this session only.'
                : 'Settings are saved locally in this browser.';
            dom.persistence.dataset.tone = state.memoryOnly ? 'quiet-warning' : 'quiet';
        }

        function referenceIndex() {
            return viewer.referenceClipIndex?.() ?? 0;
        }

        function comparisonFallback(activeIndex) {
            const reference = referenceIndex();
            if (activeIndex !== reference && reference >= 0 && reference < clipCount()) {
                return reference;
            }
            for (let index = 0; index < clipCount(); index += 1) {
                if (index !== activeIndex && index !== reference) return index;
            }
            for (let index = 0; index < clipCount(); index += 1) {
                if (index !== activeIndex) return index;
            }
            return null;
        }

        function validComparisonTarget(activeIndex, candidate = state.report.comparisonTarget) {
            return Number.isInteger(candidate)
                && candidate >= 0
                && candidate < clipCount()
                && candidate !== activeIndex;
        }

        function ensureComparisonTarget(activeIndex) {
            if (!validComparisonTarget(activeIndex)) {
                state.report.comparisonTarget = comparisonFallback(activeIndex);
            }
            return state.report.comparisonTarget;
        }

        function entryForPointer(clientX, clientY) {
            if (viewer.state.mode === 'grid') {
                const entries = viewer.gridView?.entries?.() || [];
                return entries.find(entry => normalizedPoint(entry.image, clientX, clientY)) || null;
            }
            if (viewer.state.mode === 'overlay') {
                return { clipIdx: viewer.state.activeClipIdx, image: viewer.dom.leftImg };
            }
            if (viewer.state.mode === 'blink') {
                const image = viewer.state.activeClipIdx === viewer.state.rightClipIdx
                    ? viewer.dom.rightImg
                    : viewer.dom.leftImg;
                return { clipIdx: viewer.state.activeClipIdx, image };
            }
            if (viewer.state.mode === 'slider') {
                const rect = viewer.sliderCanvasRect?.();
                const divider = rect?.left + rect?.width * (1 - viewer.state.revealPercent / 100);
                return clientX <= divider
                    ? { clipIdx: viewer.state.leftClipIdx, image: viewer.dom.leftImg }
                    : { clipIdx: viewer.state.rightClipIdx, image: viewer.dom.rightImg };
            }
            return { clipIdx: viewer.state.leftClipIdx, image: viewer.dom.leftImg };
        }

        function centerEntry() {
            if (viewer.state.mode === 'grid') {
                const entries = viewer.gridView?.entries?.() || [];
                return entries.find(entry => entry.clipIdx === viewer.state.activeClipIdx)
                    || entries.find(entry => !entry.unavailable)
                    || entries[0]
                    || null;
            }
            if (viewer.state.mode === 'overlay') {
                return { clipIdx: viewer.state.activeClipIdx, image: viewer.dom.leftImg };
            }
            if (viewer.state.mode === 'blink') {
                const image = viewer.state.activeClipIdx === viewer.state.rightClipIdx
                    ? viewer.dom.rightImg
                    : viewer.dom.leftImg;
                return { clipIdx: viewer.state.activeClipIdx, image };
            }
            if (viewer.state.mode === 'slider') {
                const rect = viewer.sliderCanvasRect?.();
                if (rect && validDimensions(rect.width, rect.height)) {
                    return entryForPointer(
                        rect.left + rect.width / 2,
                        rect.top + rect.height / 2,
                    );
                }
            }
            return { clipIdx: viewer.state.leftClipIdx, image: viewer.dom.leftImg };
        }

        function seedCenterPoint() {
            const entry = centerEntry();
            const rect = entry?.image?.getBoundingClientRect?.();
            if (!entry || !rect || !validDimensions(rect.width, rect.height)) return false;
            state.pointer = {
                clientX: rect.left + rect.width / 2,
                clientY: rect.top + rect.height / 2,
                pointerType: 'keyboard',
            };
            state.point = { u: 0.5, v: 0.5 };
            state.activeClipIdx = entry.clipIdx;
            state.activeImage = entry.image;
            ensureComparisonTarget(entry.clipIdx);
            return true;
        }

        function coarsePointerActive() {
            return Boolean(window.matchMedia?.('(pointer: coarse)')?.matches);
        }

        function lensSize() {
            const stageRect = viewer.dom.stage.getBoundingClientRect();
            const available = Math.max(1, Math.floor(Math.min(stageRect.width, stageRect.height) - 16));
            return Math.min(SIZES[state.preferences.size], available);
        }

        function setImageGeometry(image, point, size, viewportWidth = size) {
            if (image?.complete === false) return null;
            const width = Number(image?.naturalWidth);
            const height = Number(image?.naturalHeight);
            const geometry = lensImageGeometry(
                point,
                width,
                height,
                state.preferences.magnification,
                size,
                viewportWidth,
            );
            return geometry;
        }

        function clearCloneDom(element) {
            if (!element) return;
            element.removeAttribute?.('src');
            delete element.dataset.source;
            delete element.dataset.requestSource;
            element.hidden = true;
            element.style.width = '';
            element.style.height = '';
            element.style.left = '';
            element.style.top = '';
        }

        function discardRequestLoader(request) {
            if (!request?.loader) return;
            if (request.onLoad) request.loader.removeEventListener?.('load', request.onLoad);
            if (request.onError) request.loader.removeEventListener?.('error', request.onError);
            request.loader.removeAttribute?.('src');
            request.loader = null;
            request.onLoad = null;
            request.onError = null;
        }

        function clearLensImage(slot) {
            const request = imageRequests[slot];
            if (request) {
                discardRequestLoader(request);
                request.token += 1;
                request.source = null;
                request.status = 'empty';
            }
            clearCloneDom(cloneImage(slot));
        }

        function finishLensImageRequest(slot, loader, token, source, succeeded, rerender = true) {
            const request = imageRequests[slot];
            const element = cloneImage(slot);
            if (
                !request
                || !element
                || request.token !== token
                || request.source !== source
                || request.status !== 'loading'
                || request.loader !== loader
            ) return false;
            discardRequestLoader(request);
            request.status = succeeded ? 'loaded' : 'failed';
            delete element.dataset.requestSource;
            if (succeeded) {
                element.src = source;
                element.dataset.source = source;
                element.hidden = false;
            } else {
                clearCloneDom(element);
            }
            if (rerender) render();
            return true;
        }

        function applyLensImage(slot, source, geometry) {
            const element = cloneImage(slot);
            const request = imageRequests[slot];
            if (!element || !request) return false;
            if (!source || !geometry) {
                clearLensImage(slot);
                return false;
            }
            element.style.width = `${geometry.width}px`;
            element.style.height = `${geometry.height}px`;
            element.style.left = `${geometry.left}px`;
            element.style.top = `${geometry.top}px`;
            if (request.source === source) {
                if (request.status === 'loaded') element.hidden = false;
                return request.status === 'loaded';
            }
            const token = request.token + 1;
            discardRequestLoader(request);
            request.token = token;
            request.source = source;
            request.status = 'loading';
            clearCloneDom(element);
            element.style.width = `${geometry.width}px`;
            element.style.height = `${geometry.height}px`;
            element.style.left = `${geometry.left}px`;
            element.style.top = `${geometry.top}px`;
            element.dataset.requestSource = source;
            element.hidden = true;
            const loader = document.createElement('img');
            const onLoad = () => {
                finishLensImageRequest(slot, loader, token, source, true);
            };
            const onError = () => {
                finishLensImageRequest(slot, loader, token, source, false);
            };
            request.loader = loader;
            request.onLoad = onLoad;
            request.onError = onError;
            loader.addEventListener?.('load', onLoad);
            loader.addEventListener?.('error', onError);
            loader.src = source;
            if (loader.complete === true) {
                finishLensImageRequest(
                    slot,
                    loader,
                    token,
                    source,
                    Number(loader.naturalWidth) > 0,
                    false,
                );
            }
            return request.status === 'loaded';
        }

        function requestStatus(slot) {
            return imageRequests[slot]?.status || 'empty';
        }

        function lensPosition(size) {
            const stageRect = viewer.dom.stage.getBoundingClientRect();
            const maxLeft = Math.max(8, stageRect.width - size - 8);
            const maxTop = Math.max(8, stageRect.height - size - 8);
            return {
                left: 8 + clamp(state.report.parkedPosition.u) * Math.max(0, maxLeft - 8),
                top: 8 + clamp(state.report.parkedPosition.v) * Math.max(0, maxTop - 8),
            };
        }

        function placeTargetMarker() {
            if (
                !dom.marker
                || !state.point
                || !state.activeImage
                || state.preferences.markerStyle === 'off'
            ) {
                if (dom.marker) dom.marker.hidden = true;
                return;
            }
            const imageRect = state.activeImage.getBoundingClientRect?.();
            const stageRect = viewer.dom.stage.getBoundingClientRect();
            if (!imageRect || !validDimensions(imageRect.width, imageRect.height)) {
                dom.marker.hidden = true;
                return;
            }
            dom.marker.style.left = `${imageRect.left - stageRect.left + state.point.u * imageRect.width}px`;
            dom.marker.style.top = `${imageRect.top - stageRect.top + state.point.v * imageRect.height}px`;
            dom.marker.dataset.markerStyle = state.preferences.markerStyle;
            dom.marker.hidden = false;
        }

        function comparisonShowing() {
            return viewer.state.mode === 'overlay'
                && state.report.comparisonEnabled
                && clipCount() > 1;
        }

        function renderComparison(activeIndex, point, size) {
            const showing = comparisonShowing();
            dom.lens.dataset.comparison = showing ? 'true' : 'false';
            if (!showing) {
                clearLensImage('comparison');
                setCaption('comparison', 'COMPARE', '', '');
                return;
            }
            const target = ensureComparisonTarget(activeIndex);
            const source = sourceFor(target);
            const comparisonClip = viewer.state.data?.clips?.[target];
            const width = Number(comparisonClip?.resolution?.[0]);
            const height = Number(comparisonClip?.resolution?.[1]);
            const geometry = lensImageGeometry(
                point,
                width,
                height,
                state.preferences.magnification,
                size,
                size / 2,
            );
            const available = applyLensImage('comparison', source, geometry);
            const status = available
                ? ''
                : requestStatus('comparison') === 'loading' ? 'LOADING' : 'UNAVAILABLE';
            setCaption(
                'comparison',
                'COMPARE',
                compactSourceIdentity(target, size, 'split'),
                status,
                fullSourceIdentity(target),
            );
        }

        function renderDiff(point, size) {
            const showing = viewer.state.mode === 'diff';
            dom.lens.dataset.renderMode = showing ? 'diff' : 'source';
            if (!showing) {
                clearLensImage('difference');
                return true;
            }
            const activeRect = state.activeImage?.getBoundingClientRect?.();
            const sample = activeRect && validDimensions(activeRect.width, activeRect.height)
                ? {
                    clientX: activeRect.left + point.u * activeRect.width,
                    clientY: activeRect.top + point.v * activeRect.height,
                }
                : null;
            const differencePoint = compositionPoint(
                viewer.dom.rightImg,
                sample?.clientX,
                sample?.clientY,
            );
            const geometry = setImageGeometry(viewer.dom.rightImg, differencePoint, size);
            const source = viewer.dom.rightImg.currentSrc
                || viewer.dom.rightImg.src
                || sourceFor(viewer.state.rightClipIdx);
            return applyLensImage('difference', source, geometry);
        }

        function positionSettingsPopover() {
            if (!dom.popover || dom.popover.hidden || !dom.group) return;
            const stageRect = viewer.dom.stage.getBoundingClientRect();
            const groupRect = dom.group.getBoundingClientRect();
            const popoverRect = dom.popover.getBoundingClientRect();
            if (!validDimensions(stageRect.width, stageRect.height)) return;
            const position = boundedPopoverPosition(
                stageRect,
                groupRect,
                popoverRect,
                8,
                groupRect.height + 4,
            );
            dom.popover.style.left = `${groupRect.left + position.left - stageRect.left}px`;
            dom.popover.style.right = 'auto';
            dom.popover.style.top = `${groupRect.top + position.top - stageRect.top}px`;
            dom.popover.style.bottom = 'auto';
            dom.popover.style.maxWidth = `${position.maxWidth}px`;
            dom.popover.style.maxHeight = `${position.maxHeight}px`;
        }

        function render() {
            const visible = Boolean(state.report.enabled && state.point && state.activeImage);
            dom.toggle?.classList?.toggle('active', state.report.enabled);
            dom.toggle?.setAttribute?.('aria-pressed', state.report.enabled ? 'true' : 'false');
            dom.toggle?.setAttribute?.('aria-label', state.report.enabled ? 'Turn lens off' : 'Turn lens on');
            if (dom.activeControls) dom.activeControls.hidden = !state.report.enabled;
            viewer.dom.stage.classList?.toggle?.('rv-lens-active', state.report.enabled);
            renderCurrentSource();
            if (!visible) {
                if (dom.lens) dom.lens.hidden = true;
                if (dom.marker) dom.marker.hidden = true;
                return;
            }
            const size = lensSize();
            const source = state.activeImage.currentSrc || state.activeImage.src || sourceFor(state.activeClipIdx);
            const geometry = setImageGeometry(
                state.activeImage,
                state.point,
                size,
                comparisonShowing() ? size / 2 : size,
            );
            const activeAvailable = applyLensImage('active', source, geometry);
            const differenceAvailable = renderDiff(state.point, size);
            const position = lensPosition(size);
            dom.lens.style.left = `${position.left}px`;
            dom.lens.style.top = `${position.top}px`;
            dom.lens.style.setProperty('--lens-size', `${size}px`);
            dom.lens.dataset.size = state.preferences.size;
            const activeState = requestStatus('active') === 'loading' ? 'loading' : 'unavailable';
            const differenceState = requestStatus('difference') === 'loading' ? 'loading' : 'unavailable';
            if (viewer.state.mode === 'diff') {
                const status = activeAvailable && differenceAvailable
                    ? ''
                    : `${!activeAvailable ? activeState : differenceState}`.toUpperCase();
                setCaption(
                    'active',
                    'DIFF',
                    diffIdentity(viewer.state.leftClipIdx, viewer.state.rightClipIdx, size),
                    status,
                    `${fullSourceIdentity(viewer.state.leftClipIdx)} ↔ ${fullSourceIdentity(viewer.state.rightClipIdx)}`,
                );
            } else {
                const status = activeAvailable ? '' : activeState.toUpperCase();
                setCaption(
                    'active',
                    'ACTIVE',
                    compactSourceIdentity(
                        state.activeClipIdx,
                        size,
                        comparisonShowing() ? 'split' : 'single',
                    ),
                    status,
                    fullSourceIdentity(state.activeClipIdx),
                );
            }
            renderComparison(state.activeClipIdx, state.point, size);
            dom.lens.hidden = false;
            placeTargetMarker();
            renderControls();
            positionSettingsPopover();
        }

        function updatePoint(event) {
            if (!state.report.enabled || !event) return false;
            const entry = entryForPointer(event.clientX, event.clientY);
            const point = normalizedPoint(entry?.image, event.clientX, event.clientY);
            if (!entry || !point) return false;
            state.pointer = {
                clientX: event.clientX,
                clientY: event.clientY,
                pointerType: event.pointerType || 'mouse',
            };
            state.point = point;
            state.activeClipIdx = entry.clipIdx;
            state.activeImage = entry.image;
            ensureComparisonTarget(entry.clipIdx);
            render();
            return true;
        }

        function setEnabled(enabled, options = {}) {
            const restoreToggleFocus = !enabled && Boolean(
                dom.lens?.contains?.(document.activeElement)
                || dom.group?.contains?.(document.activeElement)
                || dom.popover?.contains?.(document.activeElement)
            );
            state.report.enabled = Boolean(enabled);
            if (state.report.enabled) {
                if (!state.point || !state.activeImage) seedCenterPoint();
            } else {
                if (state.drag && dom.grip?.hasPointerCapture?.(state.drag.pointerId)) {
                    dom.grip.releasePointerCapture?.(state.drag.pointerId);
                }
                state.drag = null;
                dom.grip?.classList?.toggle?.('is-dragging', false);
                state.point = null;
                state.activeImage = null;
                state.pointer = null;
                state.touchPending = null;
                closeSettings({ restoreFocus: false });
            }
            render();
            if (restoreToggleFocus) dom.toggle?.focus?.();
            if (options.save !== false) saveReportState();
            viewer.announce?.(`Lens ${state.report.enabled ? 'on' : 'off'}.`);
            if (state.report.enabled && dom.lens && !dom.lens.hidden) dom.settings?.focus?.();
        }

        function setMagnification(value) {
            if (!MAGNIFICATIONS.includes(value)) return;
            state.preferences.magnification = value;
            savePreferences();
            render();
        }

        function stepMagnification(direction) {
            const index = MAGNIFICATIONS.indexOf(state.preferences.magnification);
            setMagnification(MAGNIFICATIONS[clamp(index + direction, 0, MAGNIFICATIONS.length - 1)]);
        }

        function setSize(value) {
            if (!Object.hasOwn(SIZES, value)) return;
            state.preferences.size = value;
            savePreferences();
            render();
        }

        function setMarkerStyle(value) {
            if (!['off', 'ring', 'brackets'].includes(value)) return;
            state.preferences.markerStyle = value;
            savePreferences();
            render();
        }

        function setComparisonEnabled(enabled) {
            state.report.comparisonEnabled = Boolean(enabled);
            ensureComparisonTarget(state.activeClipIdx ?? viewer.state.activeClipIdx);
            saveReportState();
            render();
        }

        function setComparisonTarget(value) {
            const target = Number(value);
            const active = state.activeClipIdx ?? viewer.state.activeClipIdx;
            if (!validComparisonTarget(active, target)) return;
            state.report.comparisonTarget = target;
            saveReportState();
            render();
        }

        function populateComparisonTargets() {
            if (!dom.comparisonTarget) return;
            const active = state.activeClipIdx ?? viewer.state.activeClipIdx;
            const target = ensureComparisonTarget(active);
            const options = viewer.state.data.clips
                .map((clip, index) => {
                    const option = document.createElement('option');
                    option.value = String(index);
                    option.textContent = clip.label || `Clip ${index + 1}`;
                    option.disabled = index === active;
                    option.selected = index === target;
                    return option;
                });
            dom.comparisonTarget.replaceChildren(...options);
        }

        function renderControls() {
            if (dom.zoomValue) dom.zoomValue.textContent = `${state.preferences.magnification}×`;
            if (dom.zoomOut) dom.zoomOut.disabled = state.preferences.magnification === MAGNIFICATIONS[0];
            if (dom.zoomIn) dom.zoomIn.disabled = state.preferences.magnification === MAGNIFICATIONS.at(-1);
            dom.sizeButtons.forEach(button => {
                const active = button.dataset.lensSize === state.preferences.size;
                button.classList.toggle('active', active);
                button.setAttribute('aria-checked', active ? 'true' : 'false');
            });
            dom.markerButtons.forEach(button => {
                const active = button.dataset.lensMarker === state.preferences.markerStyle;
                button.classList.toggle('active', active);
                button.setAttribute('aria-checked', active ? 'true' : 'false');
            });
            if (dom.comparisonToggle) dom.comparisonToggle.checked = state.report.comparisonEnabled;
            if (dom.comparisonSettings) {
                const available = viewer.state.mode === 'overlay' && clipCount() > 1;
                dom.comparisonSettings.hidden = !available;
            }
            populateComparisonTargets();
            renderPersistenceStatus();
        }

        function openSettings() {
            if (!dom.popover || !dom.settings) return;
            state.settingsRestoreFocus = document.activeElement;
            dom.popover.hidden = false;
            dom.settings.setAttribute('aria-expanded', 'true');
            renderControls();
            positionSettingsPopover();
            dom.popover.querySelector('[aria-checked="true"], input, select, button')?.focus?.();
        }

        function closeSettings(options = {}) {
            if (!dom.popover || dom.popover.hidden) return;
            dom.popover.hidden = true;
            dom.settings?.setAttribute('aria-expanded', 'false');
            const restore = state.settingsRestoreFocus || dom.settings;
            state.settingsRestoreFocus = null;
            if (options.restoreFocus !== false) restore?.focus?.();
        }

        function reset() {
            state.preferences = { ...DEFAULT_PREFERENCES };
            state.report.parkedPosition = { ...DEFAULT_REPORT_STATE.parkedPosition };
            state.report.comparisonEnabled = false;
            state.report.comparisonTarget = null;
            savePreferences();
            saveReportState();
            render();
            viewer.announce?.('Lens settings reset.');
        }

        function setPositionFromPixels(left, top, size = lensSize()) {
            const stageRect = viewer.dom.stage.getBoundingClientRect();
            const maxLeft = Math.max(8, stageRect.width - size - 8);
            const maxTop = Math.max(8, stageRect.height - size - 8);
            const boundedLeft = clamp(left, 8, maxLeft);
            const boundedTop = clamp(top, 8, maxTop);
            state.report.parkedPosition = {
                u: maxLeft > 8 ? clamp((boundedLeft - 8) / (maxLeft - 8)) : 0,
                v: maxTop > 8 ? clamp((boundedTop - 8) / (maxTop - 8)) : 0,
            };
        }

        function announcePosition() {
            const horizontal = Math.round(state.report.parkedPosition.u * 100);
            const vertical = Math.round(state.report.parkedPosition.v * 100);
            viewer.announce?.(`Lens position ${horizontal}% across, ${vertical}% down.`);
        }

        function startDrag(event) {
            if (!state.report.enabled) return;
            if (event.button !== undefined && event.button !== 0) return;
            const rect = dom.lens.getBoundingClientRect();
            state.drag = {
                pointerId: event.pointerId,
                offsetX: event.clientX - rect.left,
                offsetY: event.clientY - rect.top,
            };
            dom.grip?.classList?.toggle?.('is-dragging', true);
            dom.grip?.setPointerCapture?.(event.pointerId);
            event.preventDefault();
            event.stopPropagation();
        }

        function moveDrag(event) {
            if (!state.drag || event.pointerId !== state.drag.pointerId) return;
            const stageRect = viewer.dom.stage.getBoundingClientRect();
            setPositionFromPixels(
                event.clientX - stageRect.left - state.drag.offsetX,
                event.clientY - stageRect.top - state.drag.offsetY,
            );
            render();
            event.preventDefault();
            event.stopPropagation();
        }

        function finishDrag(event, options = {}) {
            if (!state.drag || event.pointerId !== state.drag.pointerId) return;
            state.drag = null;
            dom.grip?.classList?.toggle?.('is-dragging', false);
            if (options.releaseCapture !== false && dom.grip?.hasPointerCapture?.(event.pointerId)) {
                dom.grip.releasePointerCapture?.(event.pointerId);
            }
            saveReportState();
            announcePosition();
            event.stopPropagation?.();
        }

        function moveFromKeyboard(event) {
            const directions = {
                ArrowLeft: [-1, 0],
                ArrowRight: [1, 0],
                ArrowUp: [0, -1],
                ArrowDown: [0, 1],
            };
            const direction = directions[event.key];
            if (!direction || !state.report.enabled) return;
            const step = event.shiftKey ? 24 : 4;
            const position = lensPosition(lensSize());
            setPositionFromPixels(
                position.left + direction[0] * step,
                position.top + direction[1] * step,
            );
            render();
            saveReportState();
            announcePosition();
            event.preventDefault();
            event.stopPropagation();
        }

        function bind() {
            dom.toggle?.addEventListener('click', () => setEnabled(!state.report.enabled));
            dom.zoomOut?.addEventListener('click', () => stepMagnification(-1));
            dom.zoomIn?.addEventListener('click', () => stepMagnification(1));
            dom.settings?.addEventListener('click', () => {
                if (dom.popover.hidden) openSettings();
                else closeSettings();
            });
            dom.sizeButtons.forEach(button => button.addEventListener('click', () => {
                setSize(button.dataset.lensSize);
            }));
            dom.markerButtons.forEach(button => button.addEventListener('click', () => {
                setMarkerStyle(button.dataset.lensMarker);
            }));
            dom.comparisonToggle?.addEventListener('change', event => setComparisonEnabled(event.target.checked));
            dom.comparisonTarget?.addEventListener('change', event => setComparisonTarget(event.target.value));
            dom.reset?.addEventListener('click', reset);
            dom.orientation?.addEventListener('click', () => {
                window.setTimeout?.(positionSettingsPopover, 0);
            });
            dom.grip?.addEventListener('pointerdown', startDrag);
            dom.grip?.addEventListener('pointermove', moveDrag);
            dom.grip?.addEventListener('pointerup', finishDrag);
            dom.grip?.addEventListener('pointercancel', finishDrag);
            dom.grip?.addEventListener('lostpointercapture', event => {
                finishDrag(event, { releaseCapture: false });
            });
            dom.grip?.addEventListener('keydown', moveFromKeyboard);
            dom.popover?.addEventListener('keydown', event => {
                if (event.key !== 'Escape') return;
                event.preventDefault();
                event.stopPropagation();
                closeSettings();
            });
            viewer.dom.leftImg?.addEventListener?.('load', sync);
            viewer.dom.rightImg?.addEventListener?.('load', sync);
            document.addEventListener('pointerdown', event => {
                if (dom.popover?.hidden || dom.popover?.contains(event.target) || event.target === dom.settings) return;
                closeSettings({ restoreFocus: false });
            });
            renderControls();
            if (state.report.enabled) seedCenterPoint();
            render();
        }

        function handleStagePointerDown(event) {
            if (!state.report.enabled) return false;
            if (event.pointerType === 'touch' || coarsePointerActive()) {
                const entry = entryForPointer(event.clientX, event.clientY);
                const point = normalizedPoint(entry?.image, event.clientX, event.clientY);
                if (!entry || !point) return false;
                state.touchPending = {
                    pointerId: event.pointerId,
                    startX: event.clientX,
                    startY: event.clientY,
                };
                return true;
            }
            return false;
        }

        function handleStagePointerMove(event) {
            if (!state.report.enabled || state.drag) return false;
            if (state.touchPending && event.pointerId === state.touchPending.pointerId) {
                const distance = Math.hypot(
                    event.clientX - state.touchPending.startX,
                    event.clientY - state.touchPending.startY,
                );
                if (distance <= TOUCH_GESTURE_THRESHOLD) return 'pending';
                state.touchPending = null;
                return 'released';
            }
            if (event.pointerType === 'touch' || coarsePointerActive()) return false;
            return updatePoint(event);
        }

        function endStagePointer(event, options = {}) {
            if (!state.touchPending || event.pointerId !== state.touchPending.pointerId) return false;
            const pending = state.touchPending;
            state.touchPending = null;
            if (options.cancelled) return false;
            return updatePoint({
                clientX: event.clientX ?? pending.startX,
                clientY: event.clientY ?? pending.startY,
                pointerType: event.pointerType || 'touch',
            });
        }

        function cancelTouchPending() {
            state.touchPending = null;
        }

        function clearTransient() {
            state.point = null;
            state.activeClipIdx = null;
            state.activeImage = null;
            state.pointer = null;
            state.touchPending = null;
            clearLensImage('active');
            clearLensImage('difference');
            clearLensImage('comparison');
            setCaption('active', 'ACTIVE', '', '');
            setCaption('comparison', 'COMPARE', '', '');
            dom.lens.dataset.comparison = 'false';
            dom.lens.dataset.renderMode = 'source';
            render();
        }

        function sync() {
            if (!state.report.enabled) return;
            if (state.pointer && updatePoint(state.pointer)) return;
            state.point = null;
            state.activeClipIdx = null;
            state.activeImage = null;
            state.pointer = null;
            if (seedCenterPoint()) render();
            else clearTransient();
        }

        function refresh() {
            render();
        }

        return {
            bind,
            setEnabled,
            handleStagePointerDown,
            handleStagePointerMove,
            endStagePointer,
            cancelTouchPending,
            clearTransient,
            refresh,
            sync,
            render,
            state,
        };
    }

    return {
        PREFERENCES_KEY,
        REPORT_KEY_PREFIX,
        MAGNIFICATIONS,
        SIZES,
        CAPTION_METRICS,
        middleEllipsis,
        captionCharacterCapacity,
        compactSourceCaption,
        compactDiffCaption,
        normalizePreferences,
        normalizeReportState,
        normalizedPoint,
        compositionPoint,
        normalizedPosition,
        lensImageGeometry,
        boundedPopoverPosition,
        create,
    };
})();
