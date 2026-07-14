const PixelInspector = (() => {
    const MAX_GESTURE_DISTANCE = 6;
    const NUDGE_ANNOUNCE_DELAY_MS = 250;
    const RESIZE_DELAY_MS = 80;

    function clamp(value, minimum, maximum) {
        return Math.max(minimum, Math.min(maximum, value));
    }

    function validDimensions(width, height) {
        return Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0;
    }

    function pointFromImageRect(image, clientX, clientY) {
        const rect = image?.getBoundingClientRect?.();
        const width = Number(image?.naturalWidth);
        const height = Number(image?.naturalHeight);
        if (!rect || !validDimensions(rect.width, rect.height) || !validDimensions(width, height)) {
            return null;
        }
        if (
            clientX < rect.left
            || clientX >= rect.left + rect.width
            || clientY < rect.top
            || clientY >= rect.top + rect.height
        ) {
            return null;
        }
        const x = clamp(Math.floor(((clientX - rect.left) / rect.width) * width), 0, width - 1);
        const y = clamp(Math.floor(((clientY - rect.top) / rect.height) * height), 0, height - 1);
        return {
            x,
            y,
            width,
            height,
            u: (x + 0.5) / width,
            v: (y + 0.5) / height,
        };
    }

    function mapNormalizedPoint(point, targetWidth, targetHeight) {
        if (!point || !validDimensions(targetWidth, targetHeight)) return null;
        const x = clamp(Math.floor(point.u * targetWidth), 0, targetWidth - 1);
        const y = clamp(Math.floor(point.v * targetHeight), 0, targetHeight - 1);
        return {
            x,
            y,
            width: targetWidth,
            height: targetHeight,
            u: (x + 0.5) / targetWidth,
            v: (y + 0.5) / targetHeight,
        };
    }

    function anchorIndexForMode(mode, options) {
        if (mode === 'grid' && Number.isInteger(options.gridClipIdx)) return options.gridClipIdx;
        if (mode === 'overlay') return options.activeClipIdx;
        if (mode === 'diff') return options.leftClipIdx;
        if (mode === 'blink') return options.blinkVisibleClipIdx;
        if (mode === 'slider') {
            const rect = options.sliderRect;
            if (!rect || rect.width <= 0) return options.leftClipIdx;
            const dividerX = rect.left + rect.width * (1 - options.revealPercent / 100);
            return options.clientX <= dividerX ? options.leftClipIdx : options.rightClipIdx;
        }
        return options.leftClipIdx;
    }

    function gestureExceeded(startX, startY, clientX, clientY) {
        return Math.hypot(clientX - startX, clientY - startY) > MAX_GESTURE_DISTANCE;
    }

    function nudgePoint(point, dx, dy, multiplier = 1) {
        if (!point || !validDimensions(point.width, point.height)) return null;
        const x = clamp(point.x + dx * multiplier, 0, point.width - 1);
        const y = clamp(point.y + dy * multiplier, 0, point.height - 1);
        return {
            ...point,
            x,
            y,
            u: (x + 0.5) / point.width,
            v: (y + 0.5) / point.height,
        };
    }

    function lensImageGeometry(point, magnification, lensSize = 112) {
        if (
            !point
            || !validDimensions(point.width, point.height)
            || ![2, 4, 8].includes(magnification)
            || !Number.isFinite(lensSize)
            || lensSize <= 0
        ) {
            return null;
        }
        return {
            width: point.width * magnification,
            height: point.height * magnification,
            left: lensSize / 2 - (point.x + 0.5) * magnification,
            top: lensSize / 2 - (point.y + 0.5) * magnification,
        };
    }

    function clearInspectionState(state) {
        state.point = null;
        state.anchorClipIdx = null;
        state.locked = false;
        state.stagePress = null;
        return state;
    }

    function deactivateInspection(state, roi, lens) {
        state.stagePress = null;
        state.locked = false;
        state.roiDragPointerId = null;
        if (roi) {
            roi.hidden = true;
            roi.tabIndex = -1;
            roi.disabled = true;
            roi.setAttribute?.('aria-pressed', 'false');
        }
        if (lens) lens.hidden = true;
    }

    function createSampler(documentObject = document) {
        const canvas = documentObject.createElement('canvas');
        canvas.width = 1;
        canvas.height = 1;
        const context = canvas.getContext('2d', { willReadFrequently: true });

        return {
            canvas,
            sample(image, x, y) {
                if (
                    !context
                    || !image?.complete
                    || !validDimensions(image.naturalWidth, image.naturalHeight)
                    || x < 0
                    || y < 0
                    || x >= image.naturalWidth
                    || y >= image.naturalHeight
                ) {
                    return null;
                }
                try {
                    context.clearRect(0, 0, 1, 1);
                    context.drawImage(image, x, y, 1, 1, 0, 0, 1, 1);
                    const rgba = context.getImageData(0, 0, 1, 1).data;
                    return [rgba[0], rgba[1], rgba[2], rgba[3]];
                } catch {
                    // Reset origin-clean state after a tainted draw without ever growing
                    // the bounded sampling surface.
                    canvas.width = 1;
                    canvas.height = 1;
                    return null;
                }
            },
        };
    }

    function create(viewer) {
        const dom = {
            inspectButton: document.getElementById('btn-inspect'),
            roi: document.getElementById('rv-inspection-point'),
            lens: document.getElementById('rv-pixel-lens'),
            lensImage: document.querySelector('#rv-pixel-lens img'),
            lensToggle: document.getElementById('pixel-lens-toggle'),
            magnificationButtons: document.querySelectorAll('[data-pixel-magnification]'),
            rows: document.querySelector('[data-pixel-rows]'),
            anchor: document.querySelector('[data-pixel-anchor]'),
            live: document.getElementById('pixel-inspector-live'),
        };
        let sampler = null;
        const state = {
            point: null,
            anchorClipIdx: null,
            locked: false,
            magnification: 4,
            stagePress: null,
            hoverFrame: null,
            pendingHover: null,
            resizeTimer: null,
            nudgeTimer: null,
            roiDragPointerId: null,
        };

        function isActive() {
            return Boolean(viewer.state.inspectorOpen && viewer.state.inspectorTab === 'pixel');
        }

        function clipLabel(index) {
            return viewer.state.data?.clips?.[index]?.label || `Clip ${index + 1}`;
        }

        function currentEntries() {
            if (viewer.state.mode === 'grid') {
                return viewer.gridView?.entries?.() || [];
            }
            if (viewer.state.mode === 'overlay') {
                return [{ clipIdx: viewer.state.activeClipIdx, image: viewer.dom.leftImg }];
            }
            const entries = [
                { clipIdx: viewer.state.leftClipIdx, image: viewer.dom.leftImg },
                { clipIdx: viewer.state.rightClipIdx, image: viewer.dom.rightImg },
            ];
            return entries.filter((entry, index) => (
                entries.findIndex(candidate => candidate.clipIdx === entry.clipIdx) === index
            ));
        }

        function entryForClip(index) {
            return currentEntries().find(entry => entry.clipIdx === index) || null;
        }

        function entryWidth(entry) {
            return Number(entry?.image?.naturalWidth) || Number(entry?.width);
        }

        function entryHeight(entry) {
            return Number(entry?.image?.naturalHeight) || Number(entry?.height);
        }

        function clipDimensions(index) {
            const resolution = viewer.state.data?.clips?.[index]?.resolution;
            return {
                width: Number(resolution?.[0]),
                height: Number(resolution?.[1]),
            };
        }

        function placementEntry() {
            if (!state.point || state.anchorClipIdx === null) return null;
            const clipIdx = viewer.state.mode === 'blink'
                ? viewer.state.activeClipIdx
                : state.anchorClipIdx;
            const visibleEntries = viewer.state.mode === 'grid' ? currentEntries() : [];
            const entry = entryForClip(clipIdx) || (
                viewer.state.mode === 'grid'
                    ? visibleEntries.find(candidate => !candidate.unavailable) || visibleEntries[0]
                    : null
            );
            const placementClipIdx = entry?.clipIdx ?? clipIdx;
            const point = placementClipIdx === state.anchorClipIdx
                ? state.point
                : mapNormalizedPoint(
                    state.point,
                    entryWidth(entry),
                    entryHeight(entry),
                );
            return entry && point ? { ...entry, point } : null;
        }

        function currentAnchorIndex(
            clientX,
            blinkVisibleClipIdx = viewer.state.activeClipIdx,
            gridClipIdx = null,
        ) {
            return anchorIndexForMode(viewer.state.mode, {
                activeClipIdx: viewer.state.activeClipIdx,
                leftClipIdx: viewer.state.leftClipIdx,
                rightClipIdx: viewer.state.rightClipIdx,
                blinkVisibleClipIdx,
                sliderRect: viewer.sliderCanvasRect(),
                revealPercent: viewer.state.revealPercent,
                clientX,
                gridClipIdx,
            });
        }

        function announce(message) {
            if (!dom.live || !message) return;
            dom.live.textContent = '';
            window.setTimeout(() => {
                dom.live.textContent = message;
            }, 0);
        }

        function setRoiAvailability(available) {
            if (!dom.roi) return;
            dom.roi.hidden = !available;
            dom.roi.tabIndex = available && isActive() ? 0 : -1;
            dom.roi.disabled = !available || !isActive();
        }

        function updateRoiName() {
            if (!dom.roi) return;
            if (!state.point || state.anchorClipIdx === null) {
                dom.roi.setAttribute(
                    'aria-label',
                    'Inspection point; press Enter or Space to inspect image center',
                );
                dom.roi.setAttribute('aria-pressed', 'false');
                dom.roi.dataset.locked = 'false';
                return;
            }
            const lockText = state.locked ? 'locked' : 'unlocked';
            dom.roi.setAttribute(
                'aria-label',
                `Inspection point, ${lockText} at x ${state.point.x} y ${state.point.y} in ${clipLabel(state.anchorClipIdx)}`,
            );
            dom.roi.setAttribute('aria-pressed', state.locked ? 'true' : 'false');
            dom.roi.dataset.locked = state.locked ? 'true' : 'false';
        }

        function mappedRows() {
            if (!state.point) return [];
            return currentEntries().map(entry => {
                const width = entryWidth(entry);
                const height = entryHeight(entry);
                const mapped = mapNormalizedPoint(state.point, width, height);
                return { ...entry, mapped };
            });
        }

        function renderRows() {
            if (!dom.rows) return;
            if (!state.point) {
                const empty = document.createElement('li');
                empty.className = 'rv-pixel-empty';
                empty.textContent = 'Move over the image or select a point to inspect.';
                dom.rows.replaceChildren(empty);
                if (dom.anchor) dom.anchor.textContent = 'Anchor: not selected';
                return;
            }

            const rows = mappedRows().map(row => {
                const item = document.createElement('li');
                item.className = 'rv-pixel-row';
                if (!row.mapped) {
                    item.setAttribute(
                        'aria-label',
                        `Clip ${row.clipIdx + 1}, ${clipLabel(row.clipIdx)}, pixel value unavailable`,
                    );
                    const heading = document.createElement('strong');
                    heading.textContent = clipLabel(row.clipIdx);
                    const unavailable = document.createElement('span');
                    unavailable.textContent = 'Pixel value unavailable';
                    item.append(heading, unavailable);
                    return item;
                }

                sampler ||= createSampler(document);
                const rgba = row.unavailable
                    ? null
                    : sampler.sample(row.image, row.mapped.x, row.mapped.y);
                const valueText = rgba
                    ? `R ${rgba[0]} G ${rgba[1]} B ${rgba[2]} A ${rgba[3]}`
                    : 'Pixel value unavailable';
                item.setAttribute(
                    'aria-label',
                    `Clip ${row.clipIdx + 1}, ${clipLabel(row.clipIdx)}, mapped x ${row.mapped.x} y ${row.mapped.y}, ${rgba ? valueText : 'pixel value unavailable'}`,
                );
                const heading = document.createElement('strong');
                heading.textContent = clipLabel(row.clipIdx);
                const coordinates = document.createElement('span');
                coordinates.className = 'rv-pixel-coordinates';
                coordinates.textContent = `x ${row.mapped.x} · y ${row.mapped.y} · ${row.mapped.width}×${row.mapped.height}`;
                const sample = document.createElement('span');
                sample.className = 'rv-pixel-sample';
                sample.textContent = valueText;
                item.append(heading, coordinates, sample);
                return item;
            });
            dom.rows.replaceChildren(...rows);
            if (dom.anchor) {
                dom.anchor.textContent = `Anchor: ${clipLabel(state.anchorClipIdx)} · ${viewer.modeLabel()}`;
            }
        }

        function placeRoi() {
            if (!dom.roi) return;
            if (!isActive()) {
                setRoiAvailability(false);
                return;
            }
            if (!state.point || state.anchorClipIdx === null) {
                const stageRect = viewer.dom.stage.getBoundingClientRect();
                const centerX = stageRect.left + stageRect.width / 2;
                const anchor = entryForClip(currentAnchorIndex(centerX));
                const imageRect = anchor?.image?.getBoundingClientRect?.();
                if (!imageRect || imageRect.width <= 0 || imageRect.height <= 0) {
                    setRoiAvailability(false);
                    return;
                }
                dom.roi.style.left = `${imageRect.left - stageRect.left + imageRect.width / 2}px`;
                dom.roi.style.top = `${imageRect.top - stageRect.top + imageRect.height / 2}px`;
                setRoiAvailability(true);
                return;
            }
            const placement = placementEntry();
            const imageRect = placement?.image?.getBoundingClientRect?.();
            const stageRect = viewer.dom.stage.getBoundingClientRect();
            if (!imageRect || imageRect.width <= 0 || imageRect.height <= 0) {
                setRoiAvailability(false);
                return;
            }
            dom.roi.style.left = `${imageRect.left - stageRect.left + placement.point.u * imageRect.width}px`;
            dom.roi.style.top = `${imageRect.top - stageRect.top + placement.point.v * imageRect.height}px`;
            setRoiAvailability(true);
        }

        function coarsePointerActive() {
            return Boolean(window.matchMedia?.('(pointer: coarse)')?.matches);
        }

        function placeLens() {
            if (
                !dom.lens
                || !dom.lensImage
                || !isActive()
                || !viewer.state.pixelLensEnabled
                || !state.point
                || state.anchorClipIdx === null
                || coarsePointerActive()
            ) {
                if (dom.lens) dom.lens.hidden = true;
                return;
            }
            const placement = placementEntry();
            const imageRect = placement?.image?.getBoundingClientRect?.();
            const stageRect = viewer.dom.stage.getBoundingClientRect();
            const lensSize = 112;
            const geometry = lensImageGeometry(placement?.point, state.magnification, lensSize);
            if (
                !placement?.image?.complete
                || !imageRect
                || imageRect.width <= 0
                || imageRect.height <= 0
                || !geometry
                || stageRect.width < 128
                || stageRect.height < 128
            ) {
                dom.lens.hidden = true;
                return;
            }
            const gap = 28;
            const pointX = imageRect.left - stageRect.left + placement.point.u * imageRect.width;
            const pointY = imageRect.top - stageRect.top + placement.point.v * imageRect.height;
            const right = pointX + gap;
            const leftOfPoint = pointX - lensSize - gap;
            const below = pointY + gap;
            const above = pointY - lensSize - gap;
            const horizontal = pointX < stageRect.width / 2
                ? [right, leftOfPoint]
                : [leftOfPoint, right];
            const vertical = pointY < stageRect.height / 2
                ? [below, above]
                : [above, below];
            const activeLabel = placement.image === viewer.dom.rightImg
                ? viewer.dom.labelRight
                : viewer.dom.labelLeft;
            const labelRect = activeLabel?.getBoundingClientRect?.();
            const overlapsLabel = candidate => (
                labelRect
                && labelRect.width > 0
                && labelRect.height > 0
                && candidate.left < labelRect.right - stageRect.left
                && candidate.left + lensSize > labelRect.left - stageRect.left
                && candidate.top < labelRect.bottom - stageRect.top
                && candidate.top + lensSize > labelRect.top - stageRect.top
            );
            const candidates = vertical.flatMap(top => horizontal.map(left => ({ left, top })));
            const candidate = candidates.find(item => (
                item.left >= 8
                && item.top >= 8
                && item.left + lensSize <= stageRect.width - 8
                && item.top + lensSize <= stageRect.height - 8
                && !overlapsLabel(item)
            )) || candidates[0];
            const left = clamp(candidate.left, 8, Math.max(8, stageRect.width - lensSize - 8));
            const top = clamp(candidate.top, 8, Math.max(8, stageRect.height - lensSize - 8));
            dom.lens.style.left = `${left}px`;
            dom.lens.style.top = `${top}px`;
            dom.lens.dataset.magnification = String(state.magnification);
            const lensSource = placement.image.currentSrc || placement.image.src;
            if (!lensSource) {
                dom.lens.hidden = true;
                return;
            }
            if (dom.lensImage.dataset.source !== lensSource) {
                dom.lensImage.src = lensSource;
                dom.lensImage.dataset.source = lensSource;
            }
            dom.lensImage.alt = '';
            dom.lensImage.style.width = `${geometry.width}px`;
            dom.lensImage.style.height = `${geometry.height}px`;
            dom.lensImage.style.left = `${geometry.left}px`;
            dom.lensImage.style.top = `${geometry.top}px`;
            dom.lens.hidden = false;
        }

        function render() {
            updateRoiName();
            renderRows();
            placeRoi();
            placeLens();
        }

        function acquire(clientX, clientY, options = {}) {
            if (!isActive()) return false;
            const anchorClipIdx = options.anchorClipIdx ?? currentAnchorIndex(clientX);
            const sourceClipIdx = options.sourceClipIdx ?? anchorClipIdx;
            const source = entryForClip(sourceClipIdx);
            let point = pointFromImageRect(source?.image, clientX, clientY);
            if (point && sourceClipIdx !== anchorClipIdx) {
                const anchor = entryForClip(anchorClipIdx);
                const fallback = clipDimensions(anchorClipIdx);
                point = mapNormalizedPoint(
                    point,
                    entryWidth(anchor) || fallback.width,
                    entryHeight(anchor) || fallback.height,
                );
            }
            if (!point) {
                if (options.announce) announce('Pixel value unavailable.');
                return false;
            }
            state.anchorClipIdx = anchorClipIdx;
            state.point = point;
            if (options.lock !== undefined) state.locked = Boolean(options.lock);
            render();
            if (options.announce) {
                announce(
                    `${state.locked ? 'Locked' : 'Inspection point'} at x ${point.x}, y ${point.y}. Anchor ${clipLabel(anchorClipIdx)}.`,
                );
            }
            return true;
        }

        function unlock(options = {}) {
            if (!state.locked) return false;
            state.locked = false;
            render();
            if (options.announce !== false) announce('Inspection point unlocked.');
            return true;
        }

        function cancelScheduledInteractions() {
            if (state.hoverFrame !== null) {
                window.cancelAnimationFrame?.(state.hoverFrame);
                state.hoverFrame = null;
            }
            state.pendingHover = null;
            window.clearTimeout(state.nudgeTimer);
            state.nudgeTimer = null;
            window.clearTimeout(state.resizeTimer);
            state.resizeTimer = null;
            if (state.roiDragPointerId !== null) {
                dom.roi?.releasePointerCapture?.(state.roiDragPointerId);
                state.roiDragPointerId = null;
            }
        }

        function clearForContext(message) {
            const hadPoint = Boolean(state.point);
            cancelScheduledInteractions();
            clearInspectionState(state);
            render();
            if (hadPoint && message) announce(message);
        }

        function scheduleHover(event) {
            if (!isActive() || state.locked || state.stagePress || event.pointerType !== 'mouse') return;
            state.pendingHover = {
                clientX: event.clientX,
                clientY: event.clientY,
                gridClipIdx: viewer.gridView?.clipIndexFromTarget?.(event.target) ?? null,
            };
            if (state.hoverFrame !== null) return;
            state.hoverFrame = window.requestAnimationFrame(() => {
                state.hoverFrame = null;
                const hover = state.pendingHover;
                state.pendingHover = null;
                if (hover && !state.locked) acquire(hover.clientX, hover.clientY, {
                    anchorClipIdx: currentAnchorIndex(
                        hover.clientX,
                        viewer.state.activeClipIdx,
                        hover.gridClipIdx,
                    ),
                    lock: false,
                });
            });
        }

        function beginStagePress(event) {
            if (!isActive() || event.button !== 0) return false;
            state.stagePress = {
                pointerId: event.pointerId,
                startX: event.clientX,
                startY: event.clientY,
                moved: false,
                blinkVisibleClipIdx: viewer.state.activeClipIdx,
                gridClipIdx: viewer.gridView?.clipIndexFromTarget?.(event.target) ?? null,
            };
            return true;
        }

        function moveStagePress(event) {
            const press = state.stagePress;
            if (!press || press.pointerId !== event.pointerId) return;
            if (gestureExceeded(press.startX, press.startY, event.clientX, event.clientY)) {
                press.moved = true;
            }
        }

        function isStagePressPending(pointerId) {
            return Boolean(
                state.stagePress
                && state.stagePress.pointerId === pointerId
                && !state.stagePress.moved
            );
        }

        function endStagePress(event) {
            const press = state.stagePress;
            if (!press || press.pointerId !== event.pointerId) return false;
            state.stagePress = null;
            if (press.moved || gestureExceeded(press.startX, press.startY, event.clientX, event.clientY)) {
                return false;
            }
            const anchorClipIdx = currentAnchorIndex(
                event.clientX,
                press.blinkVisibleClipIdx,
                press.gridClipIdx,
            );
            return acquire(event.clientX, event.clientY, {
                anchorClipIdx,
                lock: true,
                announce: true,
            });
        }

        function cancelStagePress() {
            state.stagePress = null;
        }

        function schedulePlacement() {
            window.clearTimeout(state.resizeTimer);
            state.resizeTimer = window.setTimeout(() => {
                state.resizeTimer = null;
                placeRoi();
                placeLens();
            }, RESIZE_DELAY_MS);
        }

        function setMagnification(value) {
            const magnification = Number(value);
            if (![2, 4, 8].includes(magnification)) return;
            state.magnification = magnification;
            dom.magnificationButtons.forEach(button => {
                const active = Number(button.dataset.pixelMagnification) === magnification;
                button.classList.toggle('active', active);
                button.setAttribute('aria-checked', active ? 'true' : 'false');
            });
            placeLens();
        }

        function setLensEnabled(enabled, options = {}) {
            viewer.state.pixelLensEnabled = Boolean(enabled);
            if (dom.lensToggle) {
                dom.lensToggle.setAttribute('aria-pressed', enabled ? 'true' : 'false');
                dom.lensToggle.textContent = enabled ? 'Lens on' : 'Lens off';
            }
            placeLens();
            if (options.save !== false && !viewer.persistViewportState()) {
                announce('Lens preference could not be saved in this browser.');
            }
        }

        function focusGridCell(clipIdx, image) {
            if (!isActive() || viewer.state.mode !== 'grid' || !Number.isInteger(clipIdx)) return;
            const entry = entryForClip(clipIdx);
            const width = entryWidth(entry);
            const height = entryHeight(entry);
            if (state.point && validDimensions(width, height)) {
                state.point = mapNormalizedPoint(state.point, width, height);
                state.anchorClipIdx = clipIdx;
                render();
                return;
            }
            const rect = image?.getBoundingClientRect?.();
            if (!rect || rect.width <= 0 || rect.height <= 0) return;
            acquire(rect.left + rect.width / 2, rect.top + rect.height / 2, {
                anchorClipIdx: clipIdx,
                lock: false,
            });
        }

        function ensurePointAtCenter() {
            if (state.point) return true;
            const anchorClipIdx = currentAnchorIndex(
                viewer.dom.stage.getBoundingClientRect().left + viewer.dom.stage.getBoundingClientRect().width / 2,
            );
            const anchor = entryForClip(anchorClipIdx);
            const rect = anchor?.image?.getBoundingClientRect?.();
            if (!rect) return false;
            return acquire(rect.left + rect.width / 2, rect.top + rect.height / 2, {
                anchorClipIdx,
                lock: false,
            });
        }

        function handleRoiKey(event) {
            const key = event.key;
            if (key === 'Escape' && state.locked) {
                event.preventDefault();
                event.stopPropagation();
                unlock();
                return;
            }
            if (key === 'Enter' || key === ' ') {
                event.preventDefault();
                event.stopPropagation();
                if (!ensurePointAtCenter()) return;
                state.locked = !state.locked;
                render();
                announce(state.locked ? 'Inspection point locked.' : 'Inspection point unlocked.');
                return;
            }
            const deltas = {
                ArrowLeft: [-1, 0],
                ArrowRight: [1, 0],
                ArrowUp: [0, -1],
                ArrowDown: [0, 1],
            };
            if (!state.locked || !deltas[key]) return;
            event.preventDefault();
            event.stopPropagation();
            const [dx, dy] = deltas[key];
            state.point = nudgePoint(state.point, dx, dy, event.shiftKey ? 10 : 1);
            render();
            window.clearTimeout(state.nudgeTimer);
            const announcedPoint = { x: state.point.x, y: state.point.y };
            state.nudgeTimer = window.setTimeout(() => {
                state.nudgeTimer = null;
                announce(`Inspection point x ${announcedPoint.x}, y ${announcedPoint.y}.`);
            }, NUDGE_ANNOUNCE_DELAY_MS);
        }

        function bindRoiDrag() {
            if (!dom.roi) return;
            dom.roi.addEventListener('pointerdown', event => {
                if (!isActive() || event.button !== 0) return;
                event.preventDefault();
                event.stopPropagation();
                state.roiDragPointerId = event.pointerId;
                state.locked = true;
                dom.roi.setPointerCapture?.(event.pointerId);
            });
            dom.roi.addEventListener('pointermove', event => {
                if (state.roiDragPointerId !== event.pointerId) return;
                event.preventDefault();
                event.stopPropagation();
                acquire(event.clientX, event.clientY, {
                    anchorClipIdx: state.anchorClipIdx,
                    sourceClipIdx: viewer.state.mode === 'grid'
                        ? placementEntry()?.clipIdx
                        : viewer.state.mode === 'blink'
                        ? viewer.state.activeClipIdx
                        : state.anchorClipIdx,
                    lock: true,
                });
            });
            const release = event => {
                if (state.roiDragPointerId !== event.pointerId) return;
                event.preventDefault();
                event.stopPropagation();
                dom.roi.releasePointerCapture?.(event.pointerId);
                state.roiDragPointerId = null;
            };
            const finish = event => {
                if (state.roiDragPointerId !== event.pointerId) return;
                acquire(event.clientX, event.clientY, {
                    anchorClipIdx: state.anchorClipIdx,
                    sourceClipIdx: viewer.state.mode === 'grid'
                        ? placementEntry()?.clipIdx
                        : viewer.state.mode === 'blink'
                        ? viewer.state.activeClipIdx
                        : state.anchorClipIdx,
                    lock: true,
                    announce: true,
                });
                release(event);
            };
            dom.roi.addEventListener('pointerup', finish);
            dom.roi.addEventListener('pointercancel', release);
            dom.roi.addEventListener('keydown', handleRoiKey);
        }

        function open() {
            viewer.setInspectorTab('pixel', { save: false });
            viewer.setInspectorOpen(true);
            viewer.focusElement(document.getElementById('inspector-tab-pixel'));
            render();
        }

        function syncVisibility() {
            if (!isActive()) {
                cancelScheduledInteractions();
                deactivateInspection(state, dom.roi, dom.lens);
                return;
            }
            render();
        }

        function bind() {
            dom.inspectButton?.addEventListener('click', open);
            dom.lensToggle?.addEventListener('click', () => {
                setLensEnabled(!viewer.state.pixelLensEnabled);
            });
            dom.magnificationButtons.forEach(button => {
                button.addEventListener('click', () => setMagnification(button.dataset.pixelMagnification));
            });
            bindRoiDrag();
            viewer.dom.leftImg?.addEventListener('load', render);
            viewer.dom.rightImg?.addEventListener('load', render);
            window.addEventListener('resize', schedulePlacement);
            setMagnification(4);
            setLensEnabled(Boolean(viewer.state.pixelLensEnabled), { save: false });
            syncVisibility();
        }

        return {
            bind,
            open,
            isActive,
            syncVisibility,
            beginStagePress,
            focusGridCell,
            moveStagePress,
            isStagePressPending,
            endStagePress,
            cancelStagePress,
            scheduleHover,
            schedulePlacement,
            clearForContext,
            unlock,
            render,
            announce,
            state,
        };
    }

    return {
        MAX_GESTURE_DISTANCE,
        anchorIndexForMode,
        clearInspectionState,
        create,
        createSampler,
        deactivateInspection,
        gestureExceeded,
        lensImageGeometry,
        mapNormalizedPoint,
        nudgePoint,
        pointFromImageRect,
    };
})();
