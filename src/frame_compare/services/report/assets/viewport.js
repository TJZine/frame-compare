const Viewport = {
    create(viewer) {
        return { viewer, ...this.controller };
    },

    controller: {
    capturePointer(pointerId) {
        this.viewer.pointerInteraction.capturedPointerIds.add(pointerId);
        this.viewer.dom.stage.setPointerCapture?.(pointerId);
    },

    releasePointer(pointerId) {
        if (!this.viewer.pointerInteraction.capturedPointerIds.has(pointerId)) return;
        if (this.viewer.dom.stage.hasPointerCapture?.(pointerId)) {
            this.viewer.dom.stage.releasePointerCapture(pointerId);
        }
        this.viewer.pointerInteraction.capturedPointerIds.delete(pointerId);
    },

    captureStagePointer(e) {
        this.viewer.pointerInteraction.activePointerId = e.pointerId;
        this.capturePointer(e.pointerId);
    },

    trackPointerPosition(e) {
        this.viewer.pointerInteraction.pointerPositions.set(e.pointerId, {
            x: e.clientX,
            y: e.clientY,
            type: e.pointerType,
        });
    },

    untrackPointer(pointerId) {
        this.viewer.pointerInteraction.pointerPositions.delete(pointerId);
    },

    trackedTouchPointers() {
        return Array.from(this.viewer.pointerInteraction.pointerPositions.values())
            .filter(pointer => pointer.type === 'touch');
    },

    shouldStartPinch(e) {
        return e.pointerType === 'touch' && this.trackedTouchPointers().length >= 2;
    },

    pinchMetricsFromTrackedPointers() {
        const [first, second] = this.trackedTouchPointers();
        if (!first || !second) return null;

        const dx = second.x - first.x;
        const dy = second.y - first.y;
        return {
            centerX: (first.x + second.x) / 2,
            centerY: (first.y + second.y) / 2,
            distance: Math.hypot(dx, dy),
        };
    },

    startPinchFromTrackedPointers() {
        const metrics = this.pinchMetricsFromTrackedPointers();
        if (!metrics) return;

        const pointer = this.viewer.pointerInteraction;
        const stageRect = this.viewer.dom.stage.getBoundingClientRect();
        const stageCenterX = stageRect.left + stageRect.width / 2;
        const stageCenterY = stageRect.top + stageRect.height / 2;

        pointer.pinchActive = true;
        pointer.isDragging = false;
        pointer.isPanning = false;
        pointer.activePointerId = null;
        pointer.panMoved = true;
        pointer.pinchStartDistance = Math.max(metrics.distance, 1);
        pointer.pinchStartZoom = this.viewer.state.zoom;
        pointer.pinchGridAnchor = this.viewer.state.mode === 'grid'
            ? this.viewer.gridView.zoomAnchorForPoint(metrics.centerX, metrics.centerY)
            : null;
        pointer.pinchContentX = (metrics.centerX - stageCenterX - this.viewer.state.panX) / this.viewer.state.zoom;
        pointer.pinchContentY = (metrics.centerY - stageCenterY - this.viewer.state.panY) / this.viewer.state.zoom;

        this.viewer.state.fitMode = 'custom';
        this.updateFitButtons();
        this.viewer.dom.stage.classList.add('is-panning');
    },

    updatePinchFromTrackedPointers() {
        const metrics = this.pinchMetricsFromTrackedPointers();
        if (!metrics) return;

        const pointer = this.viewer.pointerInteraction;
        if (pointer.pinchStartDistance <= 0) return;

        const nextZoom = this.clampZoom(
            pointer.pinchStartZoom * (metrics.distance / pointer.pinchStartDistance)
        );
        this.applyZoom(nextZoom, { clampPan: false });
        if (this.viewer.state.mode === 'grid' && pointer.pinchGridAnchor) {
            const pan = this.viewer.gridView.panForZoomAnchor(
                pointer.pinchGridAnchor,
                metrics.centerX,
                metrics.centerY,
                nextZoom,
            );
            if (pan) this.setPan(pan.x, pan.y, { save: false });
            return;
        }
        const stageRect = this.viewer.dom.stage.getBoundingClientRect();
        const stageCenterX = stageRect.left + stageRect.width / 2;
        const stageCenterY = stageRect.top + stageRect.height / 2;
        this.setPan(
            metrics.centerX - stageCenterX - pointer.pinchContentX * nextZoom,
            metrics.centerY - stageCenterY - pointer.pinchContentY * nextZoom,
            { save: false },
        );
    },

    finishPinchInteraction() {
        const pointer = this.viewer.pointerInteraction;
        if (!pointer.pinchActive) return;

        pointer.pinchActive = false;
        pointer.pinchStartDistance = 0;
        pointer.pinchGridAnchor = null;
        this.viewer.dom.stage.classList.remove('is-panning');
        this.viewer.persistViewerState();
        if (this.viewer.state.mode === 'blink') this.viewer.state.blinkPaused = false;
    },

    updateSliderFromPointer(e) {
        const rect = this.sliderCanvasRect();
        if (rect.width <= 0) return;
        const clampedClientX = Math.max(rect.left, Math.min(rect.right, e.clientX));
        const x = clampedClientX - rect.left;
        let percent = (1 - (x / rect.width)) * 100;
        percent = Math.max(0, Math.min(100, percent));

        this.viewer.state.revealPercent = percent;
        this.updateSlider();
    },

    shouldPanFromPointer(e) {
        return e.button === 1 || e.altKey || e.shiftKey || this.viewer.state.mode !== 'slider';
    },

    startPanFromPointer(e) {
        const pointer = this.viewer.pointerInteraction;
        pointer.isPanning = true;
        pointer.panMoved = false;
        pointer.lastPanX = e.clientX;
        pointer.lastPanY = e.clientY;
        pointer.panBasis = this.viewer.state.mode === 'grid'
            ? this.viewer.gridView.panBasisForPoint(e.clientX, e.clientY)
            : null;
        this.captureStagePointer(e);
        this.viewer.dom.stage.classList.add('is-panning');
    },

    updatePanFromPointer(e) {
        const pointer = this.viewer.pointerInteraction;
        if (!pointer.isPanning) return false;

        const dx = e.clientX - pointer.lastPanX;
        const dy = e.clientY - pointer.lastPanY;
        if (Math.abs(dx) > 1 || Math.abs(dy) > 1) pointer.panMoved = true;
        pointer.lastPanX = e.clientX;
        pointer.lastPanY = e.clientY;
        this.panByPixels(dx, dy, e.clientX, e.clientY, {
            save: false,
            basis: pointer.panBasis,
        });
        return true;
    },

    stopPointerInteraction(e, options = {}) {
        const pointer = this.viewer.pointerInteraction;
        this.untrackPointer(e.pointerId);
        this.releasePointer(e.pointerId);

        if (pointer.pinchActive) {
            if (this.trackedTouchPointers().length >= 2) {
                this.startPinchFromTrackedPointers();
                return;
            }
            this.finishPinchInteraction();
            return;
        }

        const wasLensTapPending = Boolean(
            pointer.lensPointHandled
            && pointer.lensTouchStart?.pointerId === e.pointerId
        );
        if (wasLensTapPending) {
            this.viewer.lens.endStagePointer(e, { cancelled: Boolean(options.cancelled) });
            pointer.lensPointHandled = false;
            pointer.lensTouchStart = null;
            pointer.isDragging = false;
            pointer.isPanning = false;
            pointer.panBasis = null;
            pointer.panMoved = false;
            if (pointer.activePointerId === e.pointerId) pointer.activePointerId = null;
            this.viewer.dom.stage.classList.remove('is-panning');
            if (this.viewer.state.mode === 'blink') this.viewer.state.blinkPaused = false;
            return;
        }

        if (pointer.activePointerId !== null && e.pointerId !== pointer.activePointerId) return;
        const completedDrag = pointer.isDragging;
        const completedPan = pointer.isPanning;
        if (!options.cancelled) {
            this.viewer.lens.handleStagePointerMove(e);
            this.updatePanFromPointer(e);
        }
        const completedPanMoved = pointer.panMoved;
        pointer.isDragging = false;
        pointer.isPanning = false;
        pointer.panBasis = null;
        if (pointer.activePointerId === e.pointerId) {
            pointer.activePointerId = null;
        }
        pointer.panMoved = false;
        this.viewer.dom.stage.classList.remove('is-panning');
        if (this.viewer.state.mode === 'blink') this.viewer.state.blinkPaused = false;
        if (completedDrag) this.updateSliderFromPointer(e);
        const acquiredLensPoint = pointer.lensPointHandled;
        pointer.lensPointHandled = false;
        pointer.lensTouchStart = null;
        if (completedPan) {
            this.viewer.persistViewerState();
            if (
                !acquiredLensPoint
                && !options.cancelled
                && !completedPanMoved
                && (this.viewer.state.mode === 'overlay' || this.viewer.state.mode === 'diff')
            ) {
                this.viewer.cycleClip();
            }
        }
        if (completedDrag) this.viewer.persistViewerState();
    },

    setZoom(level) {
        this.viewer.state.fitMode = 'custom';
        this.updateFitButtons();
        this.applyZoom(level);
        this.viewer.persistViewerState();
    },

    clampZoom(level) {
        return Math.max(0.25, Math.min(4.0, this.viewer.numberOrDefault(level, 1.0)));
    },

    applyZoom(level, options = {}) {
        this.viewer.state.zoom = this.clampZoom(level);
        this.viewer.dom.zoomRange.value = this.viewer.state.zoom;
        this.viewer.dom.zoomRange.setAttribute('aria-valuenow', this.viewer.state.zoom);
        this.viewer.dom.zoomVal.textContent = Math.round(this.viewer.state.zoom * 100) + '%';
        this.viewer.dom.canvas.classList.toggle('rv-canvas--pixelated', this.viewer.state.zoom > 1);
        this.viewer.dom.canvas.style.setProperty('--zoom-level', this.viewer.state.zoom);
        this.viewer.gridView?.syncViewport();
        if (options.clampPan !== false) this.clampPan();
        this.viewer.lens?.refresh();
    },

    resetViewport() {
        this.viewer.state.fitMode = 'custom';
        this.updateFitButtons();
        this.applyZoom(1.0, { clampPan: false });
        this.setPan(0, 0);
    },

    zoomAtPoint(clientX, clientY, factor) {
        const stageRect = this.viewer.dom.stage.getBoundingClientRect();
        if (stageRect.width <= 0 || stageRect.height <= 0) {
            this.setZoom(this.viewer.state.zoom * factor);
            return;
        }

        const oldZoom = this.viewer.state.zoom;
        const nextZoom = this.clampZoom(oldZoom * factor);
        if (nextZoom === oldZoom) return;

        if (this.viewer.state.mode === 'grid') {
            const anchor = this.viewer.gridView.zoomAnchorForPoint(clientX, clientY);
            this.viewer.state.fitMode = 'custom';
            this.updateFitButtons();
            this.applyZoom(nextZoom, { clampPan: false });
            const pan = this.viewer.gridView.panForZoomAnchor(anchor, clientX, clientY, nextZoom);
            if (pan) this.setPan(pan.x, pan.y);
            else this.clampPan();
            return;
        }

        const viewportCenter = {
            x: stageRect.left + stageRect.width / 2,
            y: stageRect.top + stageRect.height / 2,
        };
        const stageCenterX = viewportCenter.x;
        const stageCenterY = viewportCenter.y;
        const contentX = (clientX - stageCenterX - this.viewer.state.panX) / oldZoom;
        const contentY = (clientY - stageCenterY - this.viewer.state.panY) / oldZoom;

        this.viewer.state.fitMode = 'custom';
        this.updateFitButtons();
        this.applyZoom(nextZoom, { clampPan: false });
        this.setPan(
            clientX - stageCenterX - contentX * nextZoom,
            clientY - stageCenterY - contentY * nextZoom,
        );
    },

    panByPixels(dx, dy, clientX, clientY, options = {}) {
        if (this.viewer.state.mode !== 'grid') {
            this.setPan(this.viewer.state.panX + dx, this.viewer.state.panY + dy, options);
            return;
        }
        const basis = options.basis || this.viewer.gridView.panBasisForPoint(clientX, clientY);
        if (!basis || basis.width <= 0 || basis.height <= 0) return;
        this.setPan(
            this.viewer.state.panX + dx / basis.width,
            this.viewer.state.panY + dy / basis.height,
            options,
        );
    },

    setPan(x, y, options = {}) {
        this.viewer.state.panX = this.viewer.numberOrDefault(x, 0);
        this.viewer.state.panY = this.viewer.numberOrDefault(y, 0);
        this.clampPan();
        this.applyPan();
        if (options.save !== false) this.viewer.persistViewerState();
    },

    clampPan() {
        if (this.viewer.state.mode === 'grid' && this.viewer.gridView?.isActive()) {
            const bounds = this.viewer.gridView.panBounds();
            this.viewer.state.panX = Math.max(-bounds.x, Math.min(bounds.x, this.viewer.state.panX));
            this.viewer.state.panY = Math.max(-bounds.y, Math.min(bounds.y, this.viewer.state.panY));
            this.applyPan();
            return;
        }
        const stageRect = this.viewer.dom.stage.getBoundingClientRect();
        const base = this.baseCanvasSize();
        if (stageRect.width <= 0 || stageRect.height <= 0 || base.width <= 0 || base.height <= 0) {
            return;
        }

        const scaledWidth = base.width * this.viewer.state.zoom;
        const scaledHeight = base.height * this.viewer.state.zoom;
        const maxPanX = Math.max(0, (scaledWidth - stageRect.width) / 2);
        const maxPanY = Math.max(0, (scaledHeight - stageRect.height) / 2);
        this.viewer.state.panX = Math.max(-maxPanX, Math.min(maxPanX, this.viewer.state.panX));
        this.viewer.state.panY = Math.max(-maxPanY, Math.min(maxPanY, this.viewer.state.panY));
        this.applyPan();
    },

    applyPan() {
        this.viewer.dom.canvas.style.setProperty('--pan-x', `${this.viewer.state.panX}px`);
        this.viewer.dom.canvas.style.setProperty('--pan-y', `${this.viewer.state.panY}px`);
        this.viewer.gridView?.syncViewport();
        this.viewer.lens?.refresh();
    },

    setFitMode(mode, options = {}) {
        if (!['actual', 'width', 'height'].includes(mode)) return;

        this.viewer.state.fitMode = mode;
        this.updateFitButtons();

        if (options.updateZoom === false) return;
        this.applyFitMode({ resetPan: true });
        this.viewer.persistViewerState();
    },

    updateFitButtons() {
        this.viewer.dom.fitBtns.forEach(btn => {
            const isActive = btn.dataset.fit === this.viewer.state.fitMode;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-checked', isActive);
        });
        this.viewer.syncRadioGroupTabStops(this.viewer.dom.fitBtns);
    },

    baseCanvasSize() {
        const rect = this.viewer.dom.sizerImg.getBoundingClientRect();
        const zoom = this.viewer.state.zoom || 1.0;
        return {
            width: rect.width / zoom,
            height: rect.height / zoom
        };
    },

    sliderCanvasRect() {
        return this.viewer.dom.canvas.getBoundingClientRect();
    },

    applyFitMode(options = {}) {
        if (this.viewer.state.fitMode === 'custom') {
            this.clampPan();
            return;
        }

        if (this.viewer.state.mode === 'grid') {
            // Grid cells each establish their own contained baseline. The shared zoom
            // remains the single linked intent layered over those equal-weight cells.
            this.applyZoom(1.0, { clampPan: false });
            if (options.resetPan) this.setPan(0, 0, { save: false });
            else this.clampPan();
            return;
        }

        if (this.viewer.state.fitMode === 'actual') {
            this.applyZoom(1.0);
            if (options.resetPan) this.setPan(0, 0, { save: false });
            return;
        }

        const stageRect = this.viewer.dom.stage.getBoundingClientRect();
        const base = this.baseCanvasSize();
        if (stageRect.width <= 0 || stageRect.height <= 0 || base.width <= 0 || base.height <= 0) {
            return;
        }

        const fitWidthZoom = stageRect.width / base.width;
        const fitHeightZoom = stageRect.height / base.height;
        const nextZoom = this.viewer.state.fitMode === 'width'
            ? fitWidthZoom
            : fitHeightZoom;
        this.applyZoom(nextZoom, { clampPan: false });
        if (options.resetPan) {
            this.setPan(0, 0, { save: false });
        } else {
            this.clampPan();
        }
    },

    applyAlignmentPresetOffsets(preset) {
        const offset = this.presetAlignmentOffsets(preset);
        if (!offset) return;
        this.clearRawAlignmentInputs();
        this.viewer.state.alignX = offset[0];
        this.viewer.state.alignY = offset[1];
    },

    validAlignmentPreset(preset) {
        return ['none', 'left-1', 'right-1', 'up-1', 'down-1', 'custom'].includes(preset);
    },

    currentPairAlignmentKey() {
        return this.pairAlignmentKey(this.viewer.state.leftClipIdx, this.viewer.state.rightClipIdx);
    },

    pairAlignmentKey(leftIdx, rightIdx) {
        return `${leftIdx}:${rightIdx}`;
    },

    isValidPairAlignmentKey(key) {
        if (typeof key !== 'string') return false;
        const match = key.match(/^(\d+):(\d+)$/);
        if (!match) return false;
        const leftIdx = Number(match[1]);
        const rightIdx = Number(match[2]);
        const count = this.viewer.clipCount();
        return leftIdx >= 0 && rightIdx >= 0 && leftIdx < count && rightIdx < count;
    },

    neutralAlignmentState() {
        return {
            alignmentPreset: 'none',
            alignX: 0,
            alignY: 0
        };
    },

    presetAlignmentOffsets(preset) {
        const presets = {
            none: [0, 0],
            'left-1': [-1, 0],
            'right-1': [1, 0],
            'up-1': [0, -1],
            'down-1': [0, 1]
        };
        return presets[preset] || null;
    },

    currentAlignmentState() {
        return {
            alignmentPreset: this.viewer.state.alignmentPreset,
            alignX: this.viewer.state.alignX,
            alignY: this.viewer.state.alignY
        };
    },

    normalizedAlignmentState(value) {
        if (!value || typeof value !== 'object') return null;
        const preset = this.validAlignmentPreset(value.alignmentPreset)
            ? value.alignmentPreset
            : 'none';
        const alignment = {
            alignmentPreset: preset,
            alignX: this.viewer.numberOrDefault(value.alignX, 0),
            alignY: this.viewer.numberOrDefault(value.alignY, 0)
        };
        if (preset !== 'custom') {
            const offset = this.presetAlignmentOffsets(preset);
            if (offset) {
                alignment.alignX = offset[0];
                alignment.alignY = offset[1];
            }
        }
        return alignment;
    },

    normalizedPairAlignments(value) {
        if (!value || typeof value !== 'object') return {};
        const pairAlignments = {};
        Object.entries(value).forEach(([key, alignment]) => {
            if (!this.isValidPairAlignmentKey(key)) return;
            const normalized = this.normalizedAlignmentState(alignment);
            if (normalized) pairAlignments[key] = normalized;
        });
        return pairAlignments;
    },

    applyAlignmentState(alignment) {
        const normalized = this.normalizedAlignmentState(alignment) || this.neutralAlignmentState();
        this.clearRawAlignmentInputs();
        this.viewer.state.alignmentPreset = normalized.alignmentPreset;
        this.viewer.state.alignX = normalized.alignX;
        this.viewer.state.alignY = normalized.alignY;
    },

    storeCurrentPairAlignment() {
        if (this.viewer.clipCount() <= 0) return;
        const key = this.currentPairAlignmentKey();
        if (!this.isValidPairAlignmentKey(key)) return;
        this.viewer.state.pairAlignments[key] = this.currentAlignmentState();
    },

    loadCurrentPairAlignment() {
        const saved = this.viewer.state.pairAlignments[this.currentPairAlignmentKey()];
        this.applyAlignmentState(saved || this.neutralAlignmentState());
    },

    setAlignmentPreset(preset) {
        if (!this.validAlignmentPreset(preset)) {
            return;
        }
        this.viewer.state.alignmentPreset = preset;
        if (preset !== 'custom') {
            this.applyAlignmentPresetOffsets(preset);
        }
        this.applyAlignment();
        this.viewer.persistViewerState();
    },

    setManualAlignment(x, y) {
        this.clearRawAlignmentInputs();
        this.viewer.state.alignmentPreset = 'custom';
        this.viewer.state.alignX = this.viewer.numberOrDefault(x, 0);
        this.viewer.state.alignY = this.viewer.numberOrDefault(y, 0);
        this.applyAlignment();
        this.viewer.persistViewerState();
    },

    clearRawAlignmentInputs() {
        this.viewer.state.rawAlignX = null;
        this.viewer.state.rawAlignY = null;
    },

    rawAlignmentField(axis) {
        return axis === 'x' ? 'rawAlignX' : 'rawAlignY';
    },

    rawAlignmentElement(axis) {
        return axis === 'x' ? this.viewer.dom.alignX : this.viewer.dom.alignY;
    },

    setRawAlignmentInput(axis, rawValue) {
        this.viewer.state[this.rawAlignmentField(axis)] = rawValue;
    },

    isValidAlignmentNumber(rawValue) {
        const normalized = String(rawValue).trim();
        return /^-?(?:\d+\.?\d*|\.\d+)$/.test(normalized)
            && Number.isFinite(Number(normalized));
    },

    commitRawAlignmentInput(axis) {
        const field = this.rawAlignmentField(axis);
        const rawValue = this.viewer.state[field];
        if (rawValue === null) return;

        if (!this.isValidAlignmentNumber(rawValue)) {
            this.viewer.state[field] = null;
            this.applyAlignment();
            return;
        }

        const committedValue = Number(String(rawValue).trim());
        this.viewer.state[field] = null;
        this.setManualAlignment(
            axis === 'x' ? committedValue : this.viewer.state.alignX,
            axis === 'y' ? committedValue : this.viewer.state.alignY,
        );
        this.rawAlignmentElement(axis).value = committedValue;
    },

    applyAlignment() {
        this.viewer.dom.canvas.style.setProperty('--align-x', `${this.viewer.state.alignX}px`);
        this.viewer.dom.canvas.style.setProperty('--align-y', `${this.viewer.state.alignY}px`);
        this.viewer.dom.alignmentPreset.value = this.viewer.state.alignmentPreset;
        this.viewer.dom.alignX.value = this.viewer.state.rawAlignX ?? this.viewer.state.alignX;
        this.viewer.dom.alignY.value = this.viewer.state.rawAlignY ?? this.viewer.state.alignY;

        // Visual indicator on gear button if offset is non-zero
        const isOffset = this.viewer.state.alignX !== 0 || this.viewer.state.alignY !== 0;
        this.viewer.dom.btnAlignToggle.classList.toggle('has-offset', isOffset);
        this.updateAlignmentStatus();
        this.viewer.updateInspectorData();
        this.viewer.lens?.refresh();
    },

    formatSignedPixels(value, axis) {
        const numberValue = this.viewer.numberOrDefault(value, 0);
        const prefix = numberValue > 0 ? '+' : '';
        return `${prefix}${numberValue}${axis}`;
    },

    alignmentPresetLabel(preset) {
        const labels = {
            'left-1': 'left 1px',
            'right-1': 'right 1px',
            'up-1': 'up 1px',
            'down-1': 'down 1px'
        };
        return labels[preset] || preset;
    },

    alignmentStatusValue() {
        const xText = this.formatSignedPixels(this.viewer.state.alignX, 'x');
        const yText = this.formatSignedPixels(this.viewer.state.alignY, 'y');
        const hasOffset = this.viewer.state.alignX !== 0 || this.viewer.state.alignY !== 0;

        if (!hasOffset && this.viewer.state.alignmentPreset === 'none') return 'none';
        if (this.viewer.state.alignmentPreset === 'custom') return `custom ${xText} ${yText}`;
        if (this.viewer.state.alignmentPreset !== 'none') {
            return `preset ${this.alignmentPresetLabel(this.viewer.state.alignmentPreset)}`;
        }
        return `${xText} ${yText}`;
    },

    alignmentStatusText() {
        return `Offset: ${this.alignmentStatusValue()}`;
    },

    updateAlignmentStatus() {
        if (!this.viewer.dom.alignmentStatus) return;
        const label = document.createElement('span');
        label.className = 'rv-offset-label';
        label.textContent = 'Offset:';
        const value = document.createElement('span');
        value.className = 'rv-offset-value';
        value.textContent = ` ${this.alignmentStatusValue()}`;
        this.viewer.dom.alignmentStatus.replaceChildren(label, value);
    },

    updateSlider() {
        this.viewer.dom.leftLayer.style.setProperty('--reveal-percent', this.viewer.state.revealPercent + '%');
        this.viewer.dom.divider.style.setProperty('--reveal-percent', this.viewer.state.revealPercent + '%');
        this.viewer.dom.canvas.style.setProperty('--reveal-percent', this.viewer.state.revealPercent + '%');
    },

    paletteProximityNearPx: 96,
    paletteProximityFarPx: 160,
    paletteProximityLoadMs: 3000,

    proximityDistanceToRect(rect, clientX, clientY) {
        const left = Number(rect?.left) || 0;
        const top = Number(rect?.top) || 0;
        const width = Math.max(0, Number(rect?.width) || 0);
        const height = Math.max(0, Number(rect?.height) || 0);
        const dx = clientX < left
            ? left - clientX
            : Math.max(0, clientX - (left + width));
        const dy = clientY < top
            ? top - clientY
            : Math.max(0, clientY - (top + height));
        return Math.hypot(dx, dy);
    },

    resolvePaletteProximity({
        current,
        distance,
        dragActive,
        popoverOpen,
        loadActive,
        finePointer,
    }) {
        if (!finePointer) return 'near';
        if (loadActive) return 'near';
        if (popoverOpen) return 'near';
        if (dragActive) return 'far';
        if (distance <= this.paletteProximityNearPx) return 'near';
        if (distance >= this.paletteProximityFarPx) return 'far';
        return current === 'far' ? 'far' : 'near';
    },

    isPaletteDragActive() {
        const pointer = this.viewer.pointerInteraction;
        return Boolean(
            pointer && (pointer.isDragging || pointer.isPanning || pointer.pinchActive),
        );
    },

    isPalettePopoverOpen() {
        if (typeof this.viewer.isAlignmentPopoverOpen === 'function'
            && this.viewer.isAlignmentPopoverOpen()) return true;
        const lensPopover = this.viewer.dom.lensSettingsPopover;
        return Boolean(lensPopover && lensPopover.hidden === false);
    },

    applyPaletteProximity(next) {
        const proximity = this.viewer.paletteProximity || {};
        proximity.current = next;
        this.viewer.paletteProximity = proximity;
        this.viewer.dom.viewportPalette?.setAttribute?.('data-proximity', next);
    },

    updatePaletteProximity(clientX, clientY) {
        const palette = this.viewer.dom.viewportPalette;
        if (!palette) return;
        const proximity = this.viewer.paletteProximity || {};
        if (Number.isFinite(clientX) && Number.isFinite(clientY)) {
            proximity.lastX = clientX;
            proximity.lastY = clientY;
        }
        this.viewer.paletteProximity = proximity;
        const rect = palette.getBoundingClientRect?.();
        const x = proximity.lastX;
        const y = proximity.lastY;
        const distance = (Number.isFinite(x) && Number.isFinite(y) && rect)
            ? this.proximityDistanceToRect(rect, x, y)
            : 0;
        this.applyPaletteProximity(this.resolvePaletteProximity({
            current: proximity.current || 'near',
            distance,
            dragActive: this.isPaletteDragActive(),
            popoverOpen: this.isPalettePopoverOpen(),
            loadActive: Date.now() < (proximity.loadUntil || 0),
            finePointer: proximity.finePointer !== false,
        }));
    },

    schedulePaletteProximity(clientX, clientY) {
        const proximity = this.viewer.paletteProximity || {};
        this.viewer.paletteProximity = proximity;
        proximity.pendingX = clientX;
        proximity.pendingY = clientY;
        if (proximity.rafQueued) return;
        const apply = () => {
            proximity.rafQueued = 0;
            this.updatePaletteProximity(proximity.pendingX, proximity.pendingY);
        };
        if (typeof window !== 'undefined'
            && typeof window.requestAnimationFrame === 'function') {
            proximity.rafQueued = window.requestAnimationFrame(apply);
        } else {
            apply();
        }
    },

    cancelQueuedPaletteProximity() {
        const proximity = this.viewer.paletteProximity || {};
        if (proximity.rafQueued
            && typeof window !== 'undefined'
            && typeof window.cancelAnimationFrame === 'function') {
            window.cancelAnimationFrame(proximity.rafQueued);
        }
        proximity.rafQueued = 0;
        this.viewer.paletteProximity = proximity;
    },

    handleStagePointerLeave() {
        this.cancelQueuedPaletteProximity();
        const proximity = this.viewer.paletteProximity || {};
        this.applyPaletteProximity(this.resolvePaletteProximity({
            current: proximity.current || 'near',
            distance: Number.POSITIVE_INFINITY,
            dragActive: this.isPaletteDragActive(),
            popoverOpen: this.isPalettePopoverOpen(),
            loadActive: Date.now() < (proximity.loadUntil || 0),
            finePointer: proximity.finePointer !== false,
        }));
    },

    detachPaletteMediaListener(proximity) {
        const query = proximity.mediaQuery;
        const listener = proximity.mediaListener;
        if (!query || !listener) return;
        if (typeof query.removeEventListener === 'function') {
            query.removeEventListener('change', listener);
        } else if (typeof query.removeListener === 'function') {
            query.removeListener(listener);
        }
        proximity.mediaQuery = null;
        proximity.mediaListener = null;
    },

    initPaletteProximity() {
        const proximity = this.viewer.paletteProximity || {};
        this.cancelQueuedPaletteProximity();
        this.detachPaletteMediaListener(proximity);
        if (proximity.loadTimer
            && typeof window !== 'undefined'
            && typeof window.clearTimeout === 'function') {
            window.clearTimeout(proximity.loadTimer);
        }
        proximity.current = 'near';
        proximity.loadUntil = Date.now() + this.paletteProximityLoadMs;
        proximity.lastX = undefined;
        proximity.lastY = undefined;
        proximity.pendingX = undefined;
        proximity.pendingY = undefined;
        proximity.rafQueued = 0;
        proximity.loadTimer = 0;
        const query = (typeof window !== 'undefined' && typeof window.matchMedia === 'function')
            ? window.matchMedia('(hover: hover) and (pointer: fine)')
            : null;
        proximity.finePointer = query ? query.matches === true : false;
        proximity.mediaQuery = query;
        this.viewer.paletteProximity = proximity;
        this.applyPaletteProximity('near');
        const onMediaChange = event => {
            this.viewer.paletteProximity.finePointer = event.matches === true;
            this.updatePaletteProximity();
        };
        proximity.mediaListener = onMediaChange;
        if (query && typeof query.addEventListener === 'function') {
            query.addEventListener('change', onMediaChange);
        } else if (query && typeof query.addListener === 'function') {
            query.addListener(onMediaChange);
        }
        if (typeof window !== 'undefined' && typeof window.setTimeout === 'function') {
            proximity.loadTimer = window.setTimeout(() => {
                proximity.loadTimer = 0;
                this.updatePaletteProximity();
            }, this.paletteProximityLoadMs + 50);
        }
    },

    },
};
