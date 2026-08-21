const Viewport = {
    create(viewer) {
        return Object.assign(Object.create(viewer), this.controller);
    },

    controller: {
    capturePointer(pointerId) {
        this.pointerInteraction.capturedPointerIds.add(pointerId);
        this.dom.stage.setPointerCapture?.(pointerId);
    },

    releasePointer(pointerId) {
        if (!this.pointerInteraction.capturedPointerIds.has(pointerId)) return;
        if (this.dom.stage.hasPointerCapture?.(pointerId)) {
            this.dom.stage.releasePointerCapture(pointerId);
        }
        this.pointerInteraction.capturedPointerIds.delete(pointerId);
    },

    captureStagePointer(e) {
        this.pointerInteraction.activePointerId = e.pointerId;
        this.capturePointer(e.pointerId);
    },

    trackPointerPosition(e) {
        this.pointerInteraction.pointerPositions.set(e.pointerId, {
            x: e.clientX,
            y: e.clientY,
            type: e.pointerType,
        });
    },

    untrackPointer(pointerId) {
        this.pointerInteraction.pointerPositions.delete(pointerId);
    },

    trackedTouchPointers() {
        return Array.from(this.pointerInteraction.pointerPositions.values())
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

        const pointer = this.pointerInteraction;
        const stageRect = this.dom.stage.getBoundingClientRect();
        const stageCenterX = stageRect.left + stageRect.width / 2;
        const stageCenterY = stageRect.top + stageRect.height / 2;

        pointer.pinchActive = true;
        pointer.isDragging = false;
        pointer.isPanning = false;
        pointer.activePointerId = null;
        pointer.panMoved = true;
        pointer.pinchStartDistance = Math.max(metrics.distance, 1);
        pointer.pinchStartZoom = this.state.zoom;
        pointer.pinchGridAnchor = this.state.mode === 'grid'
            ? this.gridView.zoomAnchorForPoint(metrics.centerX, metrics.centerY)
            : null;
        pointer.pinchContentX = (metrics.centerX - stageCenterX - this.state.panX) / this.state.zoom;
        pointer.pinchContentY = (metrics.centerY - stageCenterY - this.state.panY) / this.state.zoom;

        this.state.fitMode = 'custom';
        this.updateFitButtons();
        this.dom.stage.classList.add('is-panning');
    },

    updatePinchFromTrackedPointers() {
        const metrics = this.pinchMetricsFromTrackedPointers();
        if (!metrics) return;

        const pointer = this.pointerInteraction;
        if (pointer.pinchStartDistance <= 0) return;

        const nextZoom = this.clampZoom(
            pointer.pinchStartZoom * (metrics.distance / pointer.pinchStartDistance)
        );
        this.applyZoom(nextZoom, { clampPan: false });
        if (this.state.mode === 'grid' && pointer.pinchGridAnchor) {
            const pan = this.gridView.panForZoomAnchor(
                pointer.pinchGridAnchor,
                metrics.centerX,
                metrics.centerY,
                nextZoom,
            );
            if (pan) this.setPan(pan.x, pan.y, { save: false });
            return;
        }
        const stageRect = this.dom.stage.getBoundingClientRect();
        const stageCenterX = stageRect.left + stageRect.width / 2;
        const stageCenterY = stageRect.top + stageRect.height / 2;
        this.setPan(
            metrics.centerX - stageCenterX - pointer.pinchContentX * nextZoom,
            metrics.centerY - stageCenterY - pointer.pinchContentY * nextZoom,
            { save: false },
        );
    },

    finishPinchInteraction() {
        const pointer = this.pointerInteraction;
        if (!pointer.pinchActive) return;

        pointer.pinchActive = false;
        pointer.pinchStartDistance = 0;
        pointer.pinchGridAnchor = null;
        this.dom.stage.classList.remove('is-panning');
        this.persistViewportState();
        if (this.state.mode === 'blink') this.state.blinkPaused = false;
    },

    updateSliderFromPointer(e) {
        const rect = this.sliderCanvasRect();
        if (rect.width <= 0) return;
        const clampedClientX = Math.max(rect.left, Math.min(rect.right, e.clientX));
        const x = clampedClientX - rect.left;
        let percent = (1 - (x / rect.width)) * 100;
        percent = Math.max(0, Math.min(100, percent));

        this.state.revealPercent = percent;
        this.updateSlider();
    },

    shouldPanFromPointer(e) {
        return e.button === 1 || e.altKey || e.shiftKey || this.state.mode !== 'slider';
    },

    startPanFromPointer(e) {
        const pointer = this.pointerInteraction;
        pointer.isPanning = true;
        pointer.panMoved = false;
        pointer.lastPanX = e.clientX;
        pointer.lastPanY = e.clientY;
        pointer.panBasis = this.state.mode === 'grid'
            ? this.gridView.panBasisForPoint(e.clientX, e.clientY)
            : null;
        this.captureStagePointer(e);
        this.dom.stage.classList.add('is-panning');
    },

    updatePanFromPointer(e) {
        const pointer = this.pointerInteraction;
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
        const pointer = this.pointerInteraction;
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
            this.lens.endStagePointer(e, { cancelled: Boolean(options.cancelled) });
            pointer.lensPointHandled = false;
            pointer.lensTouchStart = null;
            pointer.isDragging = false;
            pointer.isPanning = false;
            pointer.panBasis = null;
            pointer.panMoved = false;
            if (pointer.activePointerId === e.pointerId) pointer.activePointerId = null;
            this.dom.stage.classList.remove('is-panning');
            if (this.state.mode === 'blink') this.state.blinkPaused = false;
            return;
        }

        if (pointer.activePointerId !== null && e.pointerId !== pointer.activePointerId) return;
        const completedDrag = pointer.isDragging;
        const completedPan = pointer.isPanning;
        if (!options.cancelled) {
            this.lens.handleStagePointerMove(e);
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
        this.dom.stage.classList.remove('is-panning');
        if (this.state.mode === 'blink') this.state.blinkPaused = false;
        if (completedDrag) this.updateSliderFromPointer(e);
        const acquiredLensPoint = pointer.lensPointHandled;
        pointer.lensPointHandled = false;
        pointer.lensTouchStart = null;
        if (completedPan) {
            this.persistViewportState();
            if (
                !acquiredLensPoint
                && !options.cancelled
                && !completedPanMoved
                && (this.state.mode === 'overlay' || this.state.mode === 'diff')
            ) {
                this.cycleClip();
            }
        }
        if (completedDrag) this.persistViewportState();
    },

    setZoom(level) {
        this.state.fitMode = 'custom';
        this.updateFitButtons();
        this.applyZoom(level);
        this.persistViewportState();
    },

    clampZoom(level) {
        return Math.max(0.25, Math.min(4.0, this.numberOrDefault(level, 1.0)));
    },

    applyZoom(level, options = {}) {
        this.state.zoom = this.clampZoom(level);
        this.dom.zoomRange.value = this.state.zoom;
        this.dom.zoomRange.setAttribute('aria-valuenow', this.state.zoom);
        this.dom.zoomVal.textContent = Math.round(this.state.zoom * 100) + '%';
        this.dom.canvas.classList.toggle('rv-canvas--pixelated', this.state.zoom > 1);
        this.dom.canvas.style.setProperty('--zoom-level', this.state.zoom);
        this.gridView?.syncViewport();
        if (options.clampPan !== false) this.clampPan();
        this.lens?.refresh();
    },

    resetViewport() {
        this.state.fitMode = 'custom';
        this.updateFitButtons();
        this.applyZoom(1.0, { clampPan: false });
        this.setPan(0, 0);
    },

    zoomAtPoint(clientX, clientY, factor) {
        const stageRect = this.dom.stage.getBoundingClientRect();
        if (stageRect.width <= 0 || stageRect.height <= 0) {
            this.setZoom(this.state.zoom * factor);
            return;
        }

        const oldZoom = this.state.zoom;
        const nextZoom = this.clampZoom(oldZoom * factor);
        if (nextZoom === oldZoom) return;

        if (this.state.mode === 'grid') {
            const anchor = this.gridView.zoomAnchorForPoint(clientX, clientY);
            this.state.fitMode = 'custom';
            this.updateFitButtons();
            this.applyZoom(nextZoom, { clampPan: false });
            const pan = this.gridView.panForZoomAnchor(anchor, clientX, clientY, nextZoom);
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
        const contentX = (clientX - stageCenterX - this.state.panX) / oldZoom;
        const contentY = (clientY - stageCenterY - this.state.panY) / oldZoom;

        this.state.fitMode = 'custom';
        this.updateFitButtons();
        this.applyZoom(nextZoom, { clampPan: false });
        this.setPan(
            clientX - stageCenterX - contentX * nextZoom,
            clientY - stageCenterY - contentY * nextZoom,
        );
    },

    panByPixels(dx, dy, clientX, clientY, options = {}) {
        if (this.state.mode !== 'grid') {
            this.setPan(this.state.panX + dx, this.state.panY + dy, options);
            return;
        }
        const basis = options.basis || this.gridView.panBasisForPoint(clientX, clientY);
        if (!basis || basis.width <= 0 || basis.height <= 0) return;
        this.setPan(
            this.state.panX + dx / basis.width,
            this.state.panY + dy / basis.height,
            options,
        );
    },

    setPan(x, y, options = {}) {
        this.state.panX = this.numberOrDefault(x, 0);
        this.state.panY = this.numberOrDefault(y, 0);
        this.clampPan();
        this.applyPan();
        if (options.save !== false) this.persistViewportState();
    },

    clampPan() {
        if (this.state.mode === 'grid' && this.gridView?.isActive()) {
            const bounds = this.gridView.panBounds();
            this.state.panX = Math.max(-bounds.x, Math.min(bounds.x, this.state.panX));
            this.state.panY = Math.max(-bounds.y, Math.min(bounds.y, this.state.panY));
            this.applyPan();
            return;
        }
        const stageRect = this.dom.stage.getBoundingClientRect();
        const base = this.baseCanvasSize();
        if (stageRect.width <= 0 || stageRect.height <= 0 || base.width <= 0 || base.height <= 0) {
            return;
        }

        const scaledWidth = base.width * this.state.zoom;
        const scaledHeight = base.height * this.state.zoom;
        const maxPanX = Math.max(0, (scaledWidth - stageRect.width) / 2);
        const maxPanY = Math.max(0, (scaledHeight - stageRect.height) / 2);
        this.state.panX = Math.max(-maxPanX, Math.min(maxPanX, this.state.panX));
        this.state.panY = Math.max(-maxPanY, Math.min(maxPanY, this.state.panY));
        this.applyPan();
    },

    applyPan() {
        this.dom.canvas.style.setProperty('--pan-x', `${this.state.panX}px`);
        this.dom.canvas.style.setProperty('--pan-y', `${this.state.panY}px`);
        this.gridView?.syncViewport();
        this.lens?.refresh();
    },

    setFitMode(mode, options = {}) {
        if (!['actual', 'width', 'height'].includes(mode)) return;

        this.state.fitMode = mode;
        this.updateFitButtons();

        if (options.updateZoom === false) return;
        this.applyFitMode({ resetPan: true });
        this.persistViewportState();
    },

    updateFitButtons() {
        this.dom.fitBtns.forEach(btn => {
            const isActive = btn.dataset.fit === this.state.fitMode;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-checked', isActive);
        });
    },

    baseCanvasSize() {
        const rect = this.dom.sizerImg.getBoundingClientRect();
        const zoom = this.state.zoom || 1.0;
        return {
            width: rect.width / zoom,
            height: rect.height / zoom
        };
    },

    sliderCanvasRect() {
        return this.dom.canvas.getBoundingClientRect();
    },

    applyFitMode(options = {}) {
        if (this.state.fitMode === 'custom') {
            this.clampPan();
            return;
        }

        if (this.state.mode === 'grid') {
            // Grid cells each establish their own contained baseline. The shared zoom
            // remains the single linked intent layered over those equal-weight cells.
            this.applyZoom(1.0, { clampPan: false });
            if (options.resetPan) this.setPan(0, 0, { save: false });
            else this.clampPan();
            return;
        }

        if (this.state.fitMode === 'actual') {
            this.applyZoom(1.0);
            if (options.resetPan) this.setPan(0, 0, { save: false });
            return;
        }

        const stageRect = this.dom.stage.getBoundingClientRect();
        const base = this.baseCanvasSize();
        if (stageRect.width <= 0 || stageRect.height <= 0 || base.width <= 0 || base.height <= 0) {
            return;
        }

        const fitWidthZoom = stageRect.width / base.width;
        const fitHeightZoom = stageRect.height / base.height;
        const nextZoom = this.state.fitMode === 'width'
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
        this.state.alignX = offset[0];
        this.state.alignY = offset[1];
    },

    validAlignmentPreset(preset) {
        return ['none', 'left-1', 'right-1', 'up-1', 'down-1', 'custom'].includes(preset);
    },

    currentPairAlignmentKey() {
        return this.pairAlignmentKey(this.state.leftClipIdx, this.state.rightClipIdx);
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
        const count = this.clipCount();
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
            alignmentPreset: this.state.alignmentPreset,
            alignX: this.state.alignX,
            alignY: this.state.alignY
        };
    },

    normalizedAlignmentState(value) {
        if (!value || typeof value !== 'object') return null;
        const preset = this.validAlignmentPreset(value.alignmentPreset)
            ? value.alignmentPreset
            : 'none';
        const alignment = {
            alignmentPreset: preset,
            alignX: this.numberOrDefault(value.alignX, 0),
            alignY: this.numberOrDefault(value.alignY, 0)
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
        this.state.alignmentPreset = normalized.alignmentPreset;
        this.state.alignX = normalized.alignX;
        this.state.alignY = normalized.alignY;
    },

    storeCurrentPairAlignment() {
        if (this.clipCount() <= 0) return;
        const key = this.currentPairAlignmentKey();
        if (!this.isValidPairAlignmentKey(key)) return;
        this.state.pairAlignments[key] = this.currentAlignmentState();
    },

    loadCurrentPairAlignment() {
        const saved = this.state.pairAlignments[this.currentPairAlignmentKey()];
        this.applyAlignmentState(saved || this.neutralAlignmentState());
    },

    setAlignmentPreset(preset) {
        if (!this.validAlignmentPreset(preset)) {
            return;
        }
        this.state.alignmentPreset = preset;
        if (preset !== 'custom') {
            this.applyAlignmentPresetOffsets(preset);
        }
        this.applyAlignment();
        this.persistViewportState();
    },

    setManualAlignment(x, y) {
        this.clearRawAlignmentInputs();
        this.state.alignmentPreset = 'custom';
        this.state.alignX = this.numberOrDefault(x, 0);
        this.state.alignY = this.numberOrDefault(y, 0);
        this.applyAlignment();
        this.persistViewportState();
    },

    clearRawAlignmentInputs() {
        this.state.rawAlignX = null;
        this.state.rawAlignY = null;
    },

    rawAlignmentField(axis) {
        return axis === 'x' ? 'rawAlignX' : 'rawAlignY';
    },

    rawAlignmentElement(axis) {
        return axis === 'x' ? this.dom.alignX : this.dom.alignY;
    },

    setRawAlignmentInput(axis, rawValue) {
        this.state[this.rawAlignmentField(axis)] = rawValue;
    },

    isValidAlignmentNumber(rawValue) {
        const normalized = String(rawValue).trim();
        return /^-?(?:\d+\.?\d*|\.\d+)$/.test(normalized)
            && Number.isFinite(Number(normalized));
    },

    commitRawAlignmentInput(axis) {
        const field = this.rawAlignmentField(axis);
        const rawValue = this.state[field];
        if (rawValue === null) return;

        if (!this.isValidAlignmentNumber(rawValue)) {
            this.state[field] = null;
            this.applyAlignment();
            return;
        }

        const committedValue = Number(String(rawValue).trim());
        this.state[field] = null;
        this.setManualAlignment(
            axis === 'x' ? committedValue : this.state.alignX,
            axis === 'y' ? committedValue : this.state.alignY,
        );
        this.rawAlignmentElement(axis).value = committedValue;
    },

    applyAlignment() {
        this.dom.canvas.style.setProperty('--align-x', `${this.state.alignX}px`);
        this.dom.canvas.style.setProperty('--align-y', `${this.state.alignY}px`);
        this.dom.alignmentPreset.value = this.state.alignmentPreset;
        this.dom.alignX.value = this.state.rawAlignX ?? this.state.alignX;
        this.dom.alignY.value = this.state.rawAlignY ?? this.state.alignY;

        // Visual indicator on gear button if offset is non-zero
        const isOffset = this.state.alignX !== 0 || this.state.alignY !== 0;
        this.dom.btnAlignToggle.classList.toggle('has-offset', isOffset);
        this.updateAlignmentStatus();
        this.updateInspectorData();
        this.lens?.refresh();
    },

    formatSignedPixels(value, axis) {
        const numberValue = this.numberOrDefault(value, 0);
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

    alignmentStatusText() {
        const xText = this.formatSignedPixels(this.state.alignX, 'x');
        const yText = this.formatSignedPixels(this.state.alignY, 'y');
        const hasOffset = this.state.alignX !== 0 || this.state.alignY !== 0;

        if (!hasOffset && this.state.alignmentPreset === 'none') return 'Aligned: none';
        if (this.state.alignmentPreset === 'custom') return `Aligned: custom ${xText} ${yText}`;
        if (this.state.alignmentPreset !== 'none') {
            return `Aligned: preset ${this.alignmentPresetLabel(this.state.alignmentPreset)}`;
        }
        return `Aligned: ${xText} ${yText}`;
    },

    updateAlignmentStatus() {
        if (!this.dom.alignmentStatus) return;
        this.dom.alignmentStatus.textContent = this.alignmentStatusText();
    },

    updateSlider() {
        this.dom.leftLayer.style.setProperty('--reveal-percent', this.state.revealPercent + '%');
        this.dom.divider.style.setProperty('--reveal-percent', this.state.revealPercent + '%');
        this.dom.canvas.style.setProperty('--reveal-percent', this.state.revealPercent + '%');
    },

    },
};
