const ALL_CATEGORY_FILTER_KEY = '__fc_all__';
const DEFAULT_FRAME_CATEGORY = 'selected';
const EMPTY_IMAGE_SRC = 'data:image/gif;base64,R0lGODlhAQABAAAAACwAAAAAAQABAAA=';

const ReportViewer = {
    state: {
        data: null,
        currentFrameIdx: 0,
        leftClipIdx: 0,
        rightClipIdx: 1,
        activeClipIdx: 0, // For overlay/blink
        mode: 'slider',
        zoom: 1.0,
        fitMode: 'actual',
        panX: 0,
        panY: 0,
        revealPercent: 50,
        alignmentPreset: 'none',
        alignX: 0,
        alignY: 0,
        blinkInterval: null,
        blinkPaused: false,
        storageKey: null,
        activeCategoryKey: ALL_CATEGORY_FILTER_KEY,
        categoryFilterKeys: new Map(),
        preloadedSrcs: new Set(),
        helpRestoreFocus: null,
        rawAlignX: null,
        rawAlignY: null
    },

    init() {
        this.cacheDOM();
        if (!this.hasRequiredDOM()) {
            this.showStatus('Report viewer markup is incomplete.', 'error');
            return;
        }

        try {
            this.state.data = this.normalizePayload(this.readPayload());
            this.state.mode = this.validMode(this.state.data.default_mode)
                ? this.state.data.default_mode
                : 'slider';
            this.state.storageKey = this.viewportStorageKey();
            this.state.categoryFilterKeys = this.buildCategoryFilterKeys();
            this.applyDefaultSelection();
            this.restorePersistedState();
            this.bindHelpEvents();

            if (!this.hasRenderableData()) {
                this.renderEmptyState(this.emptyStateMessage());
                return;
            }

            this.bindInteractionEvents();
            this.setMode(this.state.mode); // Apply default mode UI state
            this.preloadImages();
        } catch (e) {
            console.error("Failed to initialize viewer:", e);
            this.renderInitializationError('Failed to load report data.');
        }
    },

    cacheDOM() {
        this.dom = {
            stage: document.querySelector('.rv-viewer-stage'),
            canvas: document.querySelector('.rv-canvas'),
            sizerImg: document.querySelector('.rv-sizer'),
            leftLayer: document.querySelector('.rv-left'),
            rightLayer: document.querySelector('.rv-right'),
            divider: document.querySelector('.rv-divider'),
            leftImg: document.querySelector('.rv-left img'),
            rightImg: document.querySelector('.rv-right img'),
            frameSelect: document.getElementById('frame-select'),
            btnPrev: document.getElementById('btn-prev'),
            btnNext: document.getElementById('btn-next'),
            modeBtns: document.querySelectorAll('[data-mode]'),
            leftSelect: document.getElementById('left-select'),
            rightSelect: document.getElementById('right-select'),
            activeSelect: document.getElementById('active-select'),
            pairControls: document.querySelector('[data-control-scope="pair"]'),
            activeControls: document.querySelector('[data-control-scope="active"]'),
            zoomRange: document.getElementById('zoom-range'),
            zoomVal: document.getElementById('zoom-val'),
            btnZoomOut: document.getElementById('btn-zoom-out'),
            btnZoomIn: document.getElementById('btn-zoom-in'),
            btnZoomReset: document.getElementById('btn-zoom-reset'),
            fitBtns: document.querySelectorAll('[data-fit]'),
            alignmentPreset: document.getElementById('alignment-preset'),
            alignX: document.getElementById('align-x'),
            alignY: document.getElementById('align-y'),
            btnAlignmentReset: document.getElementById('btn-alignment-reset'),
            btnFullscreen: document.getElementById('btn-fullscreen'),
            filmstrip: document.querySelector('.rv-filmstrip'),
            filterChips: document.querySelectorAll('[data-frame-filter]'),
            status: document.getElementById('viewer-status'),
            emptyState: document.querySelector('[data-empty-state]'),
            currentFrameSummary: document.querySelector('[data-current-frame-summary]'),
            currentFrameLabel: document.querySelector('[data-current-frame-label]'),
            currentFrameDetail: document.querySelector('[data-current-frame-detail]'),
            currentFrameCategory: document.querySelector('[data-current-frame-category]'),
            labelLeft: document.getElementById('label-left'),
            labelRight: document.getElementById('label-right'),
            modal: document.getElementById('help-modal'),
            btnHelp: document.getElementById('btn-help'),
            btnCloseHelp: document.getElementById('btn-close-help'),
            btnAlignToggle: document.getElementById('btn-align-toggle'),
            alignPopover: document.getElementById('align-popover'),
        };
    },

    hasRequiredDOM() {
        const requiredElements = [
            this.dom.stage,
            this.dom.canvas,
            this.dom.sizerImg,
            this.dom.leftLayer,
            this.dom.rightLayer,
            this.dom.divider,
            this.dom.leftImg,
            this.dom.rightImg,
            this.dom.frameSelect,
            this.dom.btnPrev,
            this.dom.btnNext,
            this.dom.leftSelect,
            this.dom.rightSelect,
            this.dom.activeSelect,
            this.dom.pairControls,
            this.dom.activeControls,
            this.dom.zoomRange,
            this.dom.zoomVal,
            this.dom.btnZoomOut,
            this.dom.btnZoomIn,
            this.dom.btnZoomReset,
            this.dom.alignmentPreset,
            this.dom.alignX,
            this.dom.alignY,
            this.dom.btnAlignmentReset,
            this.dom.btnFullscreen,
            this.dom.filmstrip,
            this.dom.emptyState,
            this.dom.labelLeft,
            this.dom.labelRight,
            this.dom.modal,
            this.dom.btnHelp,
            this.dom.btnCloseHelp,
            this.dom.btnAlignToggle,
            this.dom.alignPopover
        ];
        return requiredElements.every(Boolean)
            && this.dom.modeBtns.length > 0
            && this.dom.fitBtns.length > 0;
    },

    readPayload() {
        const scriptTag = document.getElementById('report-data');
        if (!scriptTag) {
            throw new Error('Missing report data script tag.');
        }
        return JSON.parse(scriptTag.textContent || '{}');
    },

    normalizePayload(payload) {
        if (!payload || typeof payload !== 'object') {
            throw new Error('Report data payload is not an object.');
        }

        const frames = Array.isArray(payload.frames) ? payload.frames : [];
        const clips = Array.isArray(payload.clips) ? payload.clips : [];
        const defaultSelection = payload.default_selection && typeof payload.default_selection === 'object'
            ? payload.default_selection
            : {};
        return {
            ...payload,
            frames,
            clips,
            stats: payload.stats && typeof payload.stats === 'object'
                ? payload.stats
                : { frame_count: frames.length, clip_count: clips.length },
            default_selection: defaultSelection,
            default_mode: typeof payload.default_mode === 'string' ? payload.default_mode : 'slider',
            report_id: typeof payload.report_id === 'string' ? payload.report_id : 'unknown-report'
        };
    },

    validMode(mode) {
        return ['slider', 'overlay', 'diff', 'blink'].includes(mode);
    },

    hasRenderableData() {
        return this.state.data.frames.length > 0 && this.state.data.clips.length > 0;
    },

    emptyStateMessage() {
        if (this.state.data.clips.length === 0 && this.state.data.frames.length === 0) {
            return 'This report has no clips or frames to display.';
        }
        if (this.state.data.clips.length === 0) {
            return 'This report has no clips to display.';
        }
        return 'This report has no frames to display.';
    },

    renderInitializationError(message) {
        this.showStatus(message, 'error');
        this.disableViewerControls(true);
        this.showStageMessage(message);
        this.clearFrameImages();
        this.updateCurrentFrameMetadata(null);
    },

    showStatus(message, tone = 'info') {
        let status = this.dom?.status || document.getElementById('viewer-status');
        if (!status) {
            status = document.createElement('div');
            status.id = 'viewer-status';
            status.className = 'rv-status';
            document.body.prepend(status);
            if (this.dom) this.dom.status = status;
        }
        status.textContent = message;
        status.dataset.tone = tone;
        status.setAttribute('role', tone === 'error' ? 'alert' : 'status');
        status.hidden = false;
    },

    clearStatus() {
        if (!this.dom.status) return;
        this.dom.status.textContent = '';
        delete this.dom.status.dataset.tone;
        this.dom.status.setAttribute('role', 'status');
        this.dom.status.hidden = true;
    },

    showStageMessage(message) {
        if (!this.dom.emptyState || !this.dom.stage) return;
        this.dom.emptyState.textContent = message;
        this.dom.emptyState.hidden = false;
        this.dom.stage.classList.add('rv-viewer-stage--empty');
    },

    hideStageMessage() {
        if (!this.dom.emptyState || !this.dom.stage) return;
        this.dom.emptyState.textContent = '';
        this.dom.emptyState.hidden = true;
        this.dom.stage.classList.remove('rv-viewer-stage--empty');
    },

    renderEmptyState(message) {
        this.showStatus(message, 'warning');
        this.disableViewerControls(true);
        this.showStageMessage(message);
        this.clearFrameImages();
        this.updateCurrentFrameMetadata(null);
    },

    disableViewerControls(disabled) {
        document.querySelectorAll('.rv-controls button, .rv-controls select, .rv-controls input').forEach(control => {
            if (control === this.dom.btnHelp) return;
            control.disabled = disabled;
        });
    },

    focusElement(element) {
        if (element && typeof element.focus === 'function') {
            element.focus({ preventScroll: true });
        }
    },

    isHelpModalOpen() {
        return this.dom.modal.classList.contains('open');
    },

    openHelpModal() {
        const activeElement = document.activeElement;
        this.state.helpRestoreFocus = activeElement && typeof activeElement.focus === 'function'
            ? activeElement
            : this.dom.btnHelp;
        this.dom.modal.classList.add('open');
        this.dom.modal.setAttribute('aria-hidden', 'false');
        this.focusElement(this.dom.btnCloseHelp);
    },

    closeHelpModal(options = {}) {
        if (!this.isHelpModalOpen()) return;
        this.dom.modal.classList.remove('open');
        this.dom.modal.setAttribute('aria-hidden', 'true');

        const shouldRestoreFocus = options.restoreFocus !== false;
        const restoreTarget = this.state.helpRestoreFocus?.isConnected
            ? this.state.helpRestoreFocus
            : this.dom.btnHelp;
        this.state.helpRestoreFocus = null;
        if (shouldRestoreFocus) this.focusElement(restoreTarget);
    },

    modalFocusableElements() {
        return Array.from(
            this.dom.modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
        ).filter(element => !element.disabled && !element.hidden);
    },

    handleModalKey(e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            e.stopPropagation();
            this.closeHelpModal();
            return;
        }
        if (e.key !== 'Tab') return;

        const focusable = this.modalFocusableElements();
        if (focusable.length === 0) {
            e.preventDefault();
            this.focusElement(this.dom.modal);
            return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            this.focusElement(last);
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            this.focusElement(first);
        }
    },

    bindInteractionEvents() {
        this.bindModeEvents();
        this.bindFrameNavigationEvents();
        this.bindClipSelectionEvents();
        this.bindViewportEvents();
        this.bindAlignmentEvents();
        this.bindFilmstripEvents();
        this.bindKeyboardEvents();
    },

    bindModeEvents() {
        this.dom.modeBtns.forEach(btn => {
            btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
        });
    },

    bindFrameNavigationEvents() {
        this.dom.btnPrev.addEventListener('click', () => this.prevFrame());
        this.dom.btnNext.addEventListener('click', () => this.nextFrame());
        this.dom.frameSelect.addEventListener('change', (e) => this.setFrame(parseInt(e.target.value)));
    },

    bindClipSelectionEvents() {
        this.dom.leftSelect.addEventListener('change', (e) => {
            this.setLeftClip(parseInt(e.target.value));
        });
        this.dom.rightSelect.addEventListener('change', (e) => {
            this.setRightClip(parseInt(e.target.value));
        });
        this.dom.activeSelect.addEventListener('change', (e) => {
            this.state.activeClipIdx = this.clipIndexOrDefault(e.target.value, this.state.activeClipIdx);
            this.render();
        });
    },

    bindViewportEvents() {
        this.pointerInteraction = {
            isDragging: false,
            isPanning: false,
            activePointerId: null,
            lastPanX: 0,
            lastPanY: 0,
            panMoved: false
        };

        this.dom.zoomRange.addEventListener('input', (e) => this.setZoom(parseFloat(e.target.value)));
        this.dom.btnZoomOut.addEventListener('click', () => this.setZoom(this.state.zoom - 0.1));
        this.dom.btnZoomIn.addEventListener('click', () => this.setZoom(this.state.zoom + 0.1));
        this.dom.btnZoomReset.addEventListener('click', () => this.resetViewport());

        this.dom.fitBtns.forEach(btn => {
            btn.addEventListener('click', () => this.setFitMode(btn.dataset.fit));
        });
        this.dom.sizerImg.addEventListener('load', () => this.applyFitMode());
        window.addEventListener('resize', () => this.applyFitMode());
        document.addEventListener('fullscreenchange', () => {
            this.applyFitMode();
            this.updateFullscreenButton();
        });
        this.dom.btnFullscreen.addEventListener('click', () => this.toggleFullscreen());
        this.updateFullscreenButton();

        this.dom.stage.addEventListener('pointerdown', (e) => {
            if (this.shouldPanFromPointer(e)) {
                this.startPanFromPointer(e);
                if (this.state.mode === 'blink') this.state.blinkPaused = true;
                e.preventDefault();
            } else if (this.state.mode === 'slider') {
                this.pointerInteraction.isDragging = true;
                this.captureStagePointer(e);
                this.updateSliderFromPointer(e);
                e.preventDefault();
            }
        });

        this.dom.stage.addEventListener('pointermove', (e) => {
            const pointer = this.pointerInteraction;
            if (pointer.activePointerId !== null && e.pointerId !== pointer.activePointerId) return;
            if (pointer.isPanning) {
                const dx = e.clientX - pointer.lastPanX;
                const dy = e.clientY - pointer.lastPanY;
                if (Math.abs(dx) > 1 || Math.abs(dy) > 1) pointer.panMoved = true;
                pointer.lastPanX = e.clientX;
                pointer.lastPanY = e.clientY;
                this.setPan(this.state.panX + dx, this.state.panY + dy, { save: false });
                e.preventDefault();
                return;
            }
            if (pointer.isDragging) {
                this.updateSliderFromPointer(e);
                e.preventDefault();
            }
        });
        this.dom.stage.addEventListener('pointerup', (e) => this.stopPointerInteraction(e));
        this.dom.stage.addEventListener('pointercancel', (e) => this.stopPointerInteraction(e));
        this.dom.stage.addEventListener('wheel', (e) => {
            e.preventDefault();
            if (e.shiftKey) {
                this.setPan(
                    this.state.panX - e.deltaX,
                    this.state.panY - e.deltaY,
                );
                return;
            }
            this.zoomAtPoint(e.clientX, e.clientY, e.deltaY < 0 ? 1.1 : 1 / 1.1);
        }, { passive: false });
    },

    bindAlignmentEvents() {
        this.dom.alignmentPreset.addEventListener('change', (e) => {
            this.setAlignmentPreset(e.target.value);
        });
        this.dom.alignX.addEventListener('input', (e) => {
            this.setRawAlignmentInput('x', e.target.value);
        });
        this.dom.alignY.addEventListener('input', (e) => {
            this.setRawAlignmentInput('y', e.target.value);
        });
        this.dom.alignX.addEventListener('blur', () => this.commitRawAlignmentInput('x'));
        this.dom.alignY.addEventListener('blur', () => this.commitRawAlignmentInput('y'));
        this.dom.alignX.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            this.commitRawAlignmentInput('x');
        });
        this.dom.alignY.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            this.commitRawAlignmentInput('y');
        });
        this.dom.btnAlignmentReset.addEventListener('click', () => this.setAlignmentPreset('none'));

        // Toggle popover visibility
        this.dom.btnAlignToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const isHidden = this.dom.alignPopover.hidden;
            this.dom.alignPopover.hidden = !isHidden;
            this.dom.btnAlignToggle.classList.toggle('active', isHidden);
            this.dom.btnAlignToggle.setAttribute('aria-expanded', isHidden ? 'true' : 'false');
            this.dom.alignPopover.setAttribute('aria-hidden', isHidden ? 'false' : 'true');
            if (isHidden) {
                this.dom.alignmentPreset.focus();
            }
        });

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!this.dom.alignPopover.contains(e.target) && e.target !== this.dom.btnAlignToggle) {
                this.closeAlignmentPopover();
            }
        });

        // Close on Escape key
        this.dom.alignPopover.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                this.closeAlignmentPopover();
                this.dom.btnAlignToggle.focus();
            }
        });
    },

    closeAlignmentPopover() {
        this.dom.alignPopover.hidden = true;
        this.dom.btnAlignToggle.classList.remove('active');
        this.dom.btnAlignToggle.setAttribute('aria-expanded', 'false');
        this.dom.alignPopover.setAttribute('aria-hidden', 'true');
    },

    bindHelpEvents() {
        this.dom.btnHelp.addEventListener('click', () => this.openHelpModal());
        this.dom.btnCloseHelp.addEventListener('click', () => this.closeHelpModal());
        this.dom.modal.addEventListener('click', (e) => {
            if (e.target === this.dom.modal) this.closeHelpModal();
        });
        this.dom.modal.addEventListener('keydown', (e) => this.handleModalKey(e));
    },

    bindFilmstripEvents() {
        this.dom.filmstrip.addEventListener('click', (e) => {
            const item = e.target.closest('.rv-filmstrip-item');
            if (item) this.setFrame(parseInt(item.dataset.idx));
        });
        this.dom.filterChips.forEach(btn => {
            btn.addEventListener('click', () => this.setFrameFilter(btn.dataset.categoryKey));
        });
    },

    bindKeyboardEvents() {
        document.addEventListener('keydown', (e) => this.handleKey(e));
    },

    captureStagePointer(e) {
        this.pointerInteraction.activePointerId = e.pointerId;
        this.dom.stage.setPointerCapture?.(e.pointerId);
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
        this.captureStagePointer(e);
        this.dom.stage.classList.add('is-panning');
    },

    stopPointerInteraction(e) {
        const pointer = this.pointerInteraction;
        if (pointer.activePointerId !== null && e.pointerId !== pointer.activePointerId) return;
        if (this.dom.stage.hasPointerCapture?.(e.pointerId)) {
            this.dom.stage.releasePointerCapture(e.pointerId);
        }
        const completedDrag = pointer.isDragging;
        const completedPan = pointer.isPanning;
        const completedPanMoved = pointer.panMoved;
        pointer.isDragging = false;
        pointer.isPanning = false;
        pointer.activePointerId = null;
        pointer.panMoved = false;
        this.dom.stage.classList.remove('is-panning');
        if (this.state.mode === 'blink') this.state.blinkPaused = false;
        if (completedPan) {
            this.persistViewportState();
            if (!completedPanMoved && (this.state.mode === 'overlay' || this.state.mode === 'diff')) {
                this.cycleClip();
            }
        }
        if (completedDrag) this.persistViewportState();
    },

    clipCount() {
        return this.state.data?.clips?.length || 0;
    },

    clipIndexOrDefault(value, fallback) {
        const count = this.clipCount();
        if (count <= 0) return 0;

        const idx = parseInt(value);
        const fallbackIdx = Number.isInteger(fallback) ? fallback : 0;
        if (Number.isInteger(idx) && idx >= 0 && idx < count) return idx;
        if (fallbackIdx >= 0 && fallbackIdx < count) return fallbackIdx;
        return 0;
    },

    applyDefaultSelection() {
        const selection = this.state.data.default_selection || {};
        const left = this.clipIndexOrDefault(selection.left_clip_index, 0);
        const rightFallback = this.clipCount() > 1 ? 1 : left;
        const right = this.clipIndexOrDefault(selection.right_clip_index, rightFallback);

        this.state.leftClipIdx = left;
        this.state.rightClipIdx = right;
        this.state.activeClipIdx = left;
    },

    setLeftClip(idx) {
        this.state.leftClipIdx = this.clipIndexOrDefault(idx, this.state.leftClipIdx);
        if (this.state.mode === 'blink') this.keepBlinkActiveInPair();
        this.render();
    },

    setRightClip(idx) {
        this.state.rightClipIdx = this.clipIndexOrDefault(idx, this.state.rightClipIdx);
        if (this.state.mode === 'blink') {
            this.state.activeClipIdx = this.state.rightClipIdx;
        }
        if (this.state.mode === 'blink') this.keepBlinkActiveInPair();
        this.render();
    },

    keepBlinkActiveInPair() {
        if (
            this.state.activeClipIdx !== this.state.leftClipIdx &&
            this.state.activeClipIdx !== this.state.rightClipIdx
        ) {
            this.state.activeClipIdx = this.state.leftClipIdx;
        }
    },

    viewportStorageKey() {
        const reportId = this.state.data?.report_id || 'unknown-report';
        return `frame-compare:report-viewer:${reportId}:viewport`;
    },

    restorePersistedState() {
        const storage = this.localStorage();
        if (!this.state.storageKey || !storage) return;

        let saved;
        try {
            saved = JSON.parse(storage.getItem(this.state.storageKey) || '{}');
        } catch {
            return;
        }

        if (!saved || typeof saved !== 'object') return;

        if (['slider', 'overlay', 'diff', 'blink'].includes(saved.mode)) {
            this.state.mode = saved.mode;
        }
        if (['actual', 'width', 'height', 'fill', 'custom'].includes(saved.fitMode)) {
            this.state.fitMode = saved.fitMode;
        }
        this.state.leftClipIdx = this.clipIndexOrDefault(saved.leftClipIdx, this.state.leftClipIdx);
        this.state.rightClipIdx = this.clipIndexOrDefault(saved.rightClipIdx, this.state.rightClipIdx);
        this.state.activeClipIdx = this.clipIndexOrDefault(saved.activeClipIdx, this.state.activeClipIdx);
        this.state.zoom = this.clampZoom(saved.zoom);
        this.state.panX = this.numberOrDefault(saved.panX, 0);
        this.state.panY = this.numberOrDefault(saved.panY, 0);
        this.state.revealPercent = Math.max(0, Math.min(100, this.numberOrDefault(saved.revealPercent, 50)));
        if (['none', 'left-1', 'right-1', 'up-1', 'down-1', 'custom'].includes(saved.alignmentPreset)) {
            this.state.alignmentPreset = saved.alignmentPreset;
        }
        this.state.alignX = this.numberOrDefault(saved.alignX, 0);
        this.state.alignY = this.numberOrDefault(saved.alignY, 0);
        if (this.state.alignmentPreset !== 'custom') {
            this.applyAlignmentPresetOffsets(this.state.alignmentPreset);
        }
        if (this.state.mode === 'blink') this.keepBlinkActiveInPair();
    },

    persistViewportState() {
        const storage = this.localStorage();
        if (!this.state.storageKey || !storage) return;

        const payload = {
            mode: this.state.mode,
            leftClipIdx: this.state.leftClipIdx,
            rightClipIdx: this.state.rightClipIdx,
            activeClipIdx: this.state.activeClipIdx,
            fitMode: this.state.fitMode,
            zoom: this.state.zoom,
            panX: this.state.panX,
            panY: this.state.panY,
            revealPercent: this.state.revealPercent,
            alignmentPreset: this.state.alignmentPreset,
            alignX: this.state.alignX,
            alignY: this.state.alignY
        };
        try {
            storage.setItem(this.state.storageKey, JSON.stringify(payload));
        } catch {
            // localStorage can be unavailable for file:// reports in hardened browser modes.
        }
    },

    localStorage() {
        try {
            return window.localStorage;
        } catch {
            return null;
        }
    },

    numberOrDefault(value, fallback) {
        const numberValue = Number(value);
        return Number.isFinite(numberValue) ? numberValue : fallback;
    },

    frameCategoryText(frame) {
        return frame?.category ?? DEFAULT_FRAME_CATEGORY;
    },

    buildCategoryFilterKeys() {
        const keys = new Map();
        const frames = this.state.data?.frames || [];
        frames.forEach(frame => {
            const category = this.frameCategoryText(frame);
            if (!keys.has(category)) keys.set(category, `cat-${keys.size}`);
        });
        return keys;
    },

    categoryKeyForCategory(category) {
        return this.state.categoryFilterKeys.get(category ?? DEFAULT_FRAME_CATEGORY) || null;
    },

    frameCategoryKey(frame) {
        return this.categoryKeyForCategory(this.frameCategoryText(frame));
    },

    isCategoryKeyVisible(categoryKey) {
        return this.state.activeCategoryKey === ALL_CATEGORY_FILTER_KEY
            || categoryKey === this.state.activeCategoryKey;
    },

    visibleFrameIndexes() {
        const frames = this.state.data?.frames || [];
        if (this.state.activeCategoryKey === ALL_CATEGORY_FILTER_KEY) {
            return frames.map((_, idx) => idx);
        }
        return frames
            .map((frame, idx) => this.frameCategoryKey(frame) === this.state.activeCategoryKey ? idx : -1)
            .filter(idx => idx >= 0);
    },

    isFrameVisible(idx) {
        const frame = this.state.data.frames[idx];
        return this.isCategoryKeyVisible(this.frameCategoryKey(frame));
    },

    nearestVisibleFrameIndex(targetIdx, visibleIndexes = this.visibleFrameIndexes()) {
        if (visibleIndexes.length === 0) return null;

        const clampedTarget = Math.max(0, Math.min(this.state.data.frames.length - 1, targetIdx));
        let best = visibleIndexes[0];
        let bestDistance = Math.abs(best - clampedTarget);
        for (const idx of visibleIndexes) {
            const distance = Math.abs(idx - clampedTarget);
            if (distance < bestDistance) {
                best = idx;
                bestDistance = distance;
            }
        }
        return best;
    },

    normalizeCurrentFrameForFilter() {
        if (this.isFrameVisible(this.state.currentFrameIdx)) return;

        const nextIdx = this.nearestVisibleFrameIndex(this.state.currentFrameIdx);
        if (nextIdx !== null) this.state.currentFrameIdx = nextIdx;
    },

    setFrameFilter(categoryKey) {
        const nextKey = categoryKey || ALL_CATEGORY_FILTER_KEY;
        if (this.state.activeCategoryKey === nextKey) return;

        this.state.activeCategoryKey = nextKey;
        this.normalizeCurrentFrameForFilter();
        this.render();
        this.scrollActiveFilmstripItem({ behavior: 'smooth', inline: 'center' });
    },

    updateFilterChips() {
        this.dom.filterChips.forEach(btn => {
            const isActive = btn.dataset.categoryKey === this.state.activeCategoryKey;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', isActive);
        });
    },

    updateFrameOptionVisibility() {
        Array.from(this.dom.frameSelect.options).forEach(option => {
            const idx = parseInt(option.value);
            const categoryKey = option.dataset.categoryKey
                || this.frameCategoryKey(this.state.data.frames[idx]);
            const isVisible = this.isCategoryKeyVisible(categoryKey);
            option.hidden = !isVisible;
            option.disabled = !isVisible;
        });
    },

    visibleFramePosition(visibleIndexes = this.visibleFrameIndexes()) {
        return visibleIndexes.indexOf(this.state.currentFrameIdx);
    },

    updateFrameNavigationControls() {
        const visibleIndexes = this.visibleFrameIndexes();
        const position = this.visibleFramePosition(visibleIndexes);
        this.dom.btnPrev.disabled = position <= 0;
        this.dom.btnNext.disabled = position === -1 || position >= visibleIndexes.length - 1;
    },

    scrollActiveFilmstripItem(options = {}) {
        const item = this.dom.filmstrip.querySelector(
            `.rv-filmstrip-item[data-idx="${this.state.currentFrameIdx}"]`
        );
        item?.scrollIntoView({
            behavior: options.behavior || 'auto',
            block: 'nearest',
            inline: options.inline || 'nearest'
        });
    },

    handleKey(e) {
        if (e.key === 'Escape') {
            if (this.isHelpModalOpen()) {
                e.preventDefault();
                this.closeHelpModal();
                return;
            }
            if (document.fullscreenElement) {
                e.preventDefault();
                document.exitFullscreen?.();
                return;
            }
        }

        if (this.dom.modal.classList.contains('open')) return;
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

        if (e.key === '?' || (e.key === '/' && e.shiftKey)) {
            e.preventDefault();
            this.openHelpModal();
            return;
        }
        switch(e.key) {
            case 'ArrowLeft': this.prevFrame(); break;
            case 'ArrowRight': this.nextFrame(); break;
            case 'Home': {
                const visible = this.visibleFrameIndexes();
                if (visible.length > 0) this.setFrame(visible[0]);
                break;
            }
            case 'End': {
                const visible = this.visibleFrameIndexes();
                if (visible.length > 0) this.setFrame(visible[visible.length - 1]);
                break;
            }

            case 'ArrowUp': this.cycleClip(1); break;
            case 'ArrowDown': this.cycleClip(-1); break;

            case 's': case 'S': this.setMode('slider'); break;
            case 'o': case 'O': this.setMode('overlay'); break;
            case 'd': case 'D': this.setMode('diff'); break;
            case 'b': case 'B': this.setMode('blink'); break;

            case '=': case '+': this.setZoom(this.state.zoom + 0.1); break;
            case '-': this.setZoom(this.state.zoom - 0.1); break;
            case 'r': case 'R': this.resetViewport(); break;

            default:
                if (e.key >= '1' && e.key <= '9') {
                    const idx = parseInt(e.key) - 1;
                    if (idx < this.state.data.clips.length) {
                         if (this.state.mode === 'slider') this.setLeftClip(idx);
                         else if (this.state.mode === 'diff' || this.state.mode === 'blink') this.setRightClip(idx);
                         else {
                             this.state.activeClipIdx = idx;
                             this.render();
                         }
                    }
                }
        }
    },

    setMode(mode) {
        if (!this.validMode(mode)) return;
        this.state.mode = mode;
        if (mode === 'blink') this.keepBlinkActiveInPair();

        // Stop blink if leaving blink mode
        if (this.state.blinkInterval && mode !== 'blink') {
            clearInterval(this.state.blinkInterval);
            this.state.blinkInterval = null;
        }
        // Start blink if entering
        if (mode === 'blink' && !this.state.blinkInterval) {
            this.startBlink();
        }

        this.dom.modeBtns.forEach(btn => {
            const isActive = btn.dataset.mode === mode;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-checked', isActive);
        });

        this.dom.stage.className = `rv-viewer-stage rv-mode-${mode}`;
        this.updateModeControls();
        this.render();
    },

    startBlink() {
        this.state.blinkInterval = setInterval(() => {
            if (this.state.blinkPaused) return;

            this.state.activeClipIdx = this.state.activeClipIdx === this.state.leftClipIdx
                ? this.state.rightClipIdx
                : this.state.leftClipIdx;
            this.updateImages();

        }, 700);
    },

    updateModeControls() {
        const mode = this.state.mode;
        const isOverlay = mode === 'overlay';
        this.dom.pairControls.hidden = isOverlay;
        this.dom.activeControls.hidden = !isOverlay;
        this.dom.leftSelect.disabled = isOverlay;
        this.dom.rightSelect.disabled = isOverlay;
        this.dom.activeSelect.disabled = !isOverlay;

        if (mode === 'diff') {
            this.dom.leftSelect.setAttribute('aria-label', 'Base clip');
            this.dom.rightSelect.setAttribute('aria-label', 'Compare clip');
            return;
        }
        if (mode === 'blink') {
            this.dom.leftSelect.setAttribute('aria-label', 'First blink clip');
            this.dom.rightSelect.setAttribute('aria-label', 'Second blink clip');
            return;
        }

        this.dom.leftSelect.setAttribute('aria-label', 'Left clip');
        this.dom.rightSelect.setAttribute('aria-label', 'Right clip');
        this.dom.activeSelect.setAttribute('aria-label', 'Overlay clip');
    },

    setFrame(idx) {
        if (idx < 0 || idx >= this.state.data.frames.length) return;
        const visibleIndexes = this.visibleFrameIndexes();
        const nextIdx = this.isFrameVisible(idx)
            ? idx
            : this.nearestVisibleFrameIndex(idx, visibleIndexes);
        if (nextIdx === null) return;

        this.state.currentFrameIdx = nextIdx;
        this.render();

        this.scrollActiveFilmstripItem({ behavior: 'smooth', inline: 'center' });
    },

    nextFrame() {
        const visibleIndexes = this.visibleFrameIndexes();
        const position = this.visibleFramePosition(visibleIndexes);
        if (position === -1) {
            const nextIdx = this.nearestVisibleFrameIndex(this.state.currentFrameIdx, visibleIndexes);
            if (nextIdx !== null) this.setFrame(nextIdx);
            return;
        }
        if (position < visibleIndexes.length - 1) {
            this.setFrame(visibleIndexes[position + 1]);
        }
    },

    prevFrame() {
        const visibleIndexes = this.visibleFrameIndexes();
        const position = this.visibleFramePosition(visibleIndexes);
        if (position === -1) {
            const nextIdx = this.nearestVisibleFrameIndex(this.state.currentFrameIdx, visibleIndexes);
            if (nextIdx !== null) this.setFrame(nextIdx);
            return;
        }
        if (position > 0) {
            this.setFrame(visibleIndexes[position - 1]);
        }
    },

    cycleClip(direction = 1) {
        const count = this.state.data.clips.length;
        if (count <= 0) return;
        if (this.state.mode === 'slider') {
            // Cycle left clip
            this.setLeftClip((this.state.leftClipIdx + direction + count) % count);
        } else if (this.state.mode === 'diff' || this.state.mode === 'blink') {
            // Cycle the comparison side of the explicit pair.
            this.setRightClip((this.state.rightClipIdx + direction + count) % count);
        } else {
            this.state.activeClipIdx = (this.state.activeClipIdx + direction + count) % count;
            this.dom.activeSelect.value = this.state.activeClipIdx;
            this.render();
        }
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
        this.dom.canvas.style.setProperty('--zoom-level', this.state.zoom);
        if (options.clampPan !== false) this.clampPan();
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

        const stageCenterX = stageRect.left + stageRect.width / 2;
        const stageCenterY = stageRect.top + stageRect.height / 2;
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

    setPan(x, y, options = {}) {
        this.state.panX = this.numberOrDefault(x, 0);
        this.state.panY = this.numberOrDefault(y, 0);
        this.clampPan();
        this.applyPan();
        if (options.save !== false) this.persistViewportState();
    },

    clampPan() {
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
    },

    setFitMode(mode, options = {}) {
        if (!['actual', 'width', 'height', 'fill'].includes(mode)) return;

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
            : this.state.fitMode === 'height'
                ? fitHeightZoom
                : Math.max(fitWidthZoom, fitHeightZoom);
        this.applyZoom(nextZoom, { clampPan: false });
        if (options.resetPan) {
            this.setPan(0, 0, { save: false });
        } else {
            this.clampPan();
        }
    },

    applyAlignmentPresetOffsets(preset) {
        const presets = {
            none: [0, 0],
            'left-1': [-1, 0],
            'right-1': [1, 0],
            'up-1': [0, -1],
            'down-1': [0, 1]
        };
        const offset = presets[preset];
        if (!offset) return;
        this.clearRawAlignmentInputs();
        this.state.alignX = offset[0];
        this.state.alignY = offset[1];
    },

    setAlignmentPreset(preset) {
        if (!['none', 'left-1', 'right-1', 'up-1', 'down-1', 'custom'].includes(preset)) {
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
        this.dom.rightLayer.style.setProperty('--align-x', `${this.state.alignX}px`);
        this.dom.rightLayer.style.setProperty('--align-y', `${this.state.alignY}px`);
        this.dom.alignmentPreset.value = this.state.alignmentPreset;
        this.dom.alignX.value = this.state.rawAlignX ?? this.state.alignX;
        this.dom.alignY.value = this.state.rawAlignY ?? this.state.alignY;

        // Visual indicator on gear button if offset is non-zero
        const isOffset = this.state.alignX !== 0 || this.state.alignY !== 0;
        this.dom.btnAlignToggle.classList.toggle('has-offset', isOffset);
    },

    toggleFullscreen() {
        if (document.fullscreenElement) {
            document.exitFullscreen?.();
            return;
        }
        this.dom.stage.requestFullscreen?.();
    },

    updateFullscreenButton() {
        const isFullscreen = Boolean(document.fullscreenElement);
        this.dom.btnFullscreen.textContent = isFullscreen ? 'Exit fullscreen' : 'Fullscreen';
        this.dom.btnFullscreen.setAttribute(
            'aria-label',
            isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'
        );
        this.dom.btnFullscreen.setAttribute('aria-pressed', isFullscreen ? 'true' : 'false');
    },

    updateSlider() {
        this.dom.leftLayer.style.setProperty('--reveal-percent', this.state.revealPercent + '%');
        this.dom.divider.style.setProperty('--reveal-percent', this.state.revealPercent + '%');
    },

    humanizeCategory(cat) {
        const mapping = {
            'quantile_bright': 'Bright',
            'quantile_dark': 'Dark',
            'scene-cut': 'Scene Cuts',
            'scene_cut': 'Scene Cuts',
            'selected': 'Selected'
        };
        if (mapping[cat]) return mapping[cat];
        return cat.replace(/_/g, ' ').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    },

    updateCurrentFrameMetadata(frameData) {
        const frame = frameData || this.state.data?.frames?.[this.state.currentFrameIdx] || null;
        const label = frame?.label || 'No frame selected';
        const detail = frame?.detail || 'No frame detail available.';
        const category = frame?.category || 'none';

        if (this.dom.currentFrameSummary) this.dom.currentFrameSummary.textContent = label;
        if (this.dom.currentFrameLabel) this.dom.currentFrameLabel.textContent = label;
        if (this.dom.currentFrameDetail) this.dom.currentFrameDetail.textContent = detail;
        if (this.dom.currentFrameCategory) {
            this.dom.currentFrameCategory.textContent = this.humanizeCategory(category);
        }
    },

    updateImages() {
        const frameData = this.state.data.frames[this.state.currentFrameIdx];
        if (!frameData) {
            this.showStageMessage('Selected frame data is unavailable.');
            this.showStatus('Selected frame data is unavailable.', 'error');
            this.clearFrameImages();
            this.updateCurrentFrameMetadata(null);
            return;
        }

        let leftSrc, rightSrc;
        let leftLabelTxt, rightLabelTxt;
        this.updateCurrentFrameMetadata(frameData);

        if (this.state.mode === 'slider' || this.state.mode === 'diff') {
            const leftImage = frameData.images?.[this.state.leftClipIdx];
            const rightImage = frameData.images?.[this.state.rightClipIdx];
            const leftClip = this.state.data.clips[this.state.leftClipIdx];
            const rightClip = this.state.data.clips[this.state.rightClipIdx];
            if (!leftImage?.src || !rightImage?.src || !leftClip || !rightClip) {
                this.showStageMessage('Selected frame image data is unavailable.');
                this.showStatus('Selected frame image data is unavailable.', 'error');
                this.clearFrameImages();
                return;
            }
            leftSrc = leftImage.src;
            rightSrc = rightImage.src;

            leftLabelTxt = `${leftClip.label} (Left)`;
            rightLabelTxt = `${rightClip.label} (Right)`;

            // For Diff mode, right layer is the "compare" one which gets difference blend
            // Left layer is base.

        } else {
            // Overlay or Blink - show activeClip
            // We use left layer as the main visible one for these modes
            const activeImage = frameData.images?.[this.state.activeClipIdx];
            const rightImage = frameData.images?.[this.state.rightClipIdx];
            const activeClip = this.state.data.clips[this.state.activeClipIdx];
            const rightClip = this.state.data.clips[this.state.rightClipIdx];
            if (!activeImage?.src || !rightImage?.src || !activeClip || !rightClip) {
                this.showStageMessage('Selected frame image data is unavailable.');
                this.showStatus('Selected frame image data is unavailable.', 'error');
                this.clearFrameImages();
                return;
            }
            leftSrc = activeImage.src;
            // Right layer remains hidden; keep its source tied to the comparison pair.
            rightSrc = rightImage.src;

            leftLabelTxt = activeClip.label;
            rightLabelTxt = "";
        }

        this.hideStageMessage();
        this.clearStatus();

        if (this.dom.leftImg.getAttribute('src') !== leftSrc) {
            if (this.dom.sizerImg && this.dom.sizerImg.getAttribute('src') !== leftSrc) {
                this.dom.sizerImg.src = leftSrc;
            }
            this.dom.leftImg.src = leftSrc;
            // Alt text update
            const clip = (this.state.mode === 'overlay' || this.state.mode === 'blink')
                ? this.state.data.clips[this.state.activeClipIdx]
                : this.state.data.clips[this.state.leftClipIdx];
            const clipName = clip?.label || 'Clip';
            this.dom.leftImg.alt = `${clipName} - Frame ${frameData.number}`;
        }
        if (this.dom.rightImg.getAttribute('src') !== rightSrc) {
            this.dom.rightImg.src = rightSrc;
            // Alt text update for right image (only relevant in split modes)
            const clipName = this.state.data.clips[this.state.rightClipIdx]?.label || 'Clip';
            this.dom.rightImg.alt = `${clipName} - Frame ${frameData.number}`;
        }

        this.dom.labelLeft.textContent = leftLabelTxt;
        this.dom.labelRight.textContent = rightLabelTxt;

        // Toggle visibility classes based on mode logic in CSS
        const singleClipMode = this.state.mode === 'overlay' || this.state.mode === 'blink';
        this.dom.leftLayer.classList.toggle('active', singleClipMode);
        this.dom.rightLayer.classList.toggle('active', false);
    },

    clearFrameImages() {
        if (this.dom.sizerImg) this.dom.sizerImg.src = EMPTY_IMAGE_SRC;
        if (this.dom.leftImg) {
            this.dom.leftImg.src = EMPTY_IMAGE_SRC;
            this.dom.leftImg.alt = '';
        }
        if (this.dom.rightImg) {
            this.dom.rightImg.src = EMPTY_IMAGE_SRC;
            this.dom.rightImg.alt = '';
        }
        if (this.dom.labelLeft) this.dom.labelLeft.textContent = '';
        if (this.dom.labelRight) this.dom.labelRight.textContent = '';
    },

    render() {
        if (!this.hasRenderableData()) {
            this.renderEmptyState(this.emptyStateMessage());
            return;
        }
        this.normalizeCurrentFrameForFilter();

        // Update controls
        this.dom.frameSelect.value = this.state.currentFrameIdx;
        this.updateFrameNavigationControls();
        this.updateFrameOptionVisibility();
        this.updateFilterChips();

        this.dom.leftSelect.value = this.state.leftClipIdx;
        this.dom.rightSelect.value = this.state.rightClipIdx;
        this.dom.activeSelect.value = this.state.activeClipIdx;

        // Update images and labels
        this.updateImages();
        this.updateSlider();
        this.applyFitMode();
        this.applyAlignment();
        this.applyPan();

        // Update filmstrip active state
        Array.from(this.dom.filmstrip.children).forEach((el, idx) => {
            const frameIdx = parseInt(el.dataset.idx);
            const categoryKey = el.dataset.categoryKey
                || this.frameCategoryKey(this.state.data.frames[frameIdx]);
            const isVisible = this.isCategoryKeyVisible(categoryKey);
            const isActive = frameIdx === this.state.currentFrameIdx;
            el.hidden = !isVisible;
            el.classList.toggle('active', isActive);
            el.setAttribute('aria-current', isActive ? 'true' : 'false');
        });
        this.scrollActiveFilmstripItem();
        this.preloadImages();
        this.persistViewportState();
    },

    preloadImages() {
        const frameIndexes = this.preloadFrameIndexes();
        const clipIndexes = this.preloadClipIndexes();

        frameIndexes.forEach(frameIdx => {
            const frame = this.state.data.frames[frameIdx];
            if (!frame) return;
            const images = Array.isArray(frame.images) ? frame.images : [];
            clipIndexes.forEach(clipIdx => {
                const src = images[clipIdx]?.src;
                this.preloadImage(src);
            });
        });
    },

    preloadFrameIndexes() {
        const visibleIndexes = this.visibleFrameIndexes();
        const position = this.visibleFramePosition(visibleIndexes);
        if (position === -1) {
            const nearest = this.nearestVisibleFrameIndex(this.state.currentFrameIdx, visibleIndexes);
            return nearest === null ? [] : [nearest];
        }

        const indexes = [visibleIndexes[position]];
        if (position > 0) indexes.push(visibleIndexes[position - 1]);
        if (position < visibleIndexes.length - 1) indexes.push(visibleIndexes[position + 1]);
        return indexes;
    },

    preloadClipIndexes() {
        const indexes = new Set();
        if (this.state.mode === 'overlay') {
            indexes.add(this.state.activeClipIdx);
        } else {
            indexes.add(this.state.leftClipIdx);
            indexes.add(this.state.rightClipIdx);
        }
        return indexes;
    },

    preloadImage(src) {
        if (!src || src.startsWith('data:') || this.state.preloadedSrcs.has(src)) return;

        this.state.preloadedSrcs.add(src);
        const image = new Image();
        image.src = src;
    }
};

document.addEventListener('DOMContentLoaded', () => ReportViewer.init());
