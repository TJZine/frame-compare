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
        pairAlignments: {},
        blinkInterval: null,
        blinkPaused: false,
        blinkIntervalMs: 700,
        focusMode: false,
        storageKey: null,
        activeCategoryKey: ALL_CATEGORY_FILTER_KEY,
        overlaysHidden: false,
        filmstripCollapsed: false,
        filmstripSize: 'normal',
        inspectorOpen: false,
        inspectorTab: 'frame',
        categoryFilterKeys: new Map(),
        imageLoadPromises: new Map(),
        imageRequestToken: 0,
        helpRestoreFocus: null,
        infoRestoreFocus: null,
        inspectorRestoreFocus: null,
        rawAlignX: null,
        rawAlignY: null,
        paletteOrientation: 'horizontal'
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
            this.updateOverlayVisibility();
            this.updateInspectorTabs();
            this.updateInspectorVisibility();

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
            viewportPalette: document.querySelector('.rv-viewport-palette'),
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
            btnSwapClips: document.getElementById('btn-swap-clips'),
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
            alignmentStatus: document.getElementById('alignment-status'),
            btnFullscreen: document.getElementById('btn-fullscreen'),
            btnFocusMode: document.getElementById('btn-focus-mode'),
            btnPaletteOrientation: document.getElementById('btn-palette-orientation'),
            palette: document.querySelector('.rv-viewport-palette'),
            blinkControls: document.querySelector('[data-control-scope="blink"]'),
            btnBlinkPause: document.getElementById('btn-blink-pause'),
            blinkSpeed: document.getElementById('blink-speed'),
            blinkStatus: document.getElementById('blink-status'),
            focusHudFrame: document.querySelector('[data-focus-frame]'),
            focusHudMode: document.querySelector('[data-focus-mode]'),
            focusHudPair: document.querySelector('[data-focus-pair]'),
            bottomPanel: document.querySelector('.rv-bottom-panel'),
            btnFilmstripToggle: document.getElementById('btn-filmstrip-toggle'),
            filmstripSizeBtns: document.querySelectorAll('[data-filmstrip-size]'),
            filmstrip: document.querySelector('.rv-filmstrip'),
            filterChips: document.querySelectorAll('[data-frame-filter]'),
            activeFilterBadge: document.getElementById('active-filter-badge'),
            status: document.getElementById('viewer-status'),
            emptyState: document.querySelector('[data-empty-state]'),
            currentFrameLabel: document.querySelector('[data-current-frame-label]'),
            currentFrameCategoryDivider: document.querySelector('[data-current-frame-category-divider]'),
            currentFrameCategory: document.querySelector('[data-current-frame-category]'),
            labelLeft: document.getElementById('label-left'),
            labelRight: document.getElementById('label-right'),
            modal: document.getElementById('help-modal'),
            btnHelp: document.getElementById('btn-help'),
            btnCloseHelp: document.getElementById('btn-close-help'),
            infoModal: document.getElementById('info-modal'),
            btnInfo: document.getElementById('btn-info'),
            btnCloseInfo: document.getElementById('btn-close-info'),
            inspector: document.getElementById('rv-inspector'),
            btnInspectorClose: document.getElementById('btn-inspector-close'),
            inspectorTabs: document.querySelectorAll('[data-inspector-tab]'),
            inspectorPanels: document.querySelectorAll('.rv-inspector-panel'),
            inspectorFrameLabel: document.querySelector('[data-inspector-frame-label]'),
            inspectorFrameNumber: document.querySelector('[data-inspector-frame-number]'),
            inspectorFrameCategory: document.querySelector('[data-inspector-frame-category]'),
            inspectorFrameDetail: document.querySelector('[data-inspector-frame-detail]'),
            inspectorFramePosition: document.querySelector('[data-inspector-frame-position]'),
            inspectorClips: document.querySelector('[data-inspector-clips]'),
            inspectorAlignPair: document.querySelector('[data-inspector-align-pair]'),
            inspectorAlignPreset: document.querySelector('[data-inspector-align-preset]'),
            inspectorAlignX: document.querySelector('[data-inspector-align-x]'),
            inspectorAlignY: document.querySelector('[data-inspector-align-y]'),
            btnInspectorResetCurrentAlign: document.getElementById('btn-inspector-reset-current-align'),
            btnInspectorResetAllAlign: document.getElementById('btn-inspector-reset-all-align'),
            inspectorExportTitle: document.querySelector('[data-inspector-export-title]'),
            inspectorExportId: document.querySelector('[data-inspector-export-id]'),
            inspectorExportGenerated: document.querySelector('[data-inspector-export-generated]'),
            inspectorExportSlowpics: document.querySelector('[data-inspector-export-slowpics]'),
            inspectorExportSummary: document.querySelector('[data-inspector-export-summary]'),
            btnAlignToggle: document.getElementById('btn-align-toggle'),
            alignPopover: document.getElementById('align-popover'),
            btnOverlays: document.getElementById('btn-overlays'),
        };
    },

    hasRequiredDOM() {
        const requiredElements = [
            this.dom.stage,
            this.dom.viewportPalette,
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
            this.dom.btnSwapClips,
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
            this.dom.alignmentStatus,
            this.dom.btnFullscreen,
            this.dom.btnFocusMode,
            this.dom.blinkControls,
            this.dom.btnBlinkPause,
            this.dom.blinkSpeed,
            this.dom.blinkStatus,
            this.dom.bottomPanel,
            this.dom.btnFilmstripToggle,
            this.dom.filmstrip,
            this.dom.emptyState,
            this.dom.labelLeft,
            this.dom.labelRight,
            this.dom.modal,
            this.dom.btnHelp,
            this.dom.btnCloseHelp,
            this.dom.infoModal,
            this.dom.btnInfo,
            this.dom.btnCloseInfo,
            this.dom.inspector,
            this.dom.btnInspectorClose,
            this.dom.inspectorClips,
            this.dom.btnInspectorResetCurrentAlign,
            this.dom.btnInspectorResetAllAlign,
            this.dom.btnAlignToggle,
            this.dom.alignPopover,
            this.dom.btnOverlays
        ];
        return requiredElements.every(Boolean)
            && this.dom.modeBtns.length > 0
            && this.dom.filmstripSizeBtns.length > 0
            && this.dom.inspectorTabs.length > 0
            && this.dom.inspectorPanels.length > 0
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

    validPaletteOrientation(orientation) {
        return ['horizontal', 'vertical'].includes(orientation);
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
    },

    disableViewerControls(disabled) {
        document.querySelectorAll(
            '.rv-controls button, .rv-controls select, .rv-controls input, .rv-viewport-palette button, .rv-viewport-palette select, .rv-viewport-palette input, .rv-bottom-panel button, .rv-bottom-panel select, .rv-bottom-panel input, .rv-inspector button, .rv-inspector select, .rv-inspector input'
        ).forEach(control => {
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
        this.closeAlignmentPopover({ restoreFocus: false });
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

    isInfoModalOpen() {
        return this.dom.infoModal.classList.contains('open');
    },

    openInfoModal() {
        this.closeAlignmentPopover({ restoreFocus: false });
        const activeElement = document.activeElement;
        this.state.infoRestoreFocus = activeElement && typeof activeElement.focus === 'function'
            ? activeElement
            : this.dom.btnInfo;
        this.dom.infoModal.classList.add('open');
        this.dom.infoModal.setAttribute('aria-hidden', 'false');
        this.focusElement(this.dom.btnCloseInfo);
    },

    closeInfoModal(options = {}) {
        if (!this.isInfoModalOpen()) return;
        this.dom.infoModal.classList.remove('open');
        this.dom.infoModal.setAttribute('aria-hidden', 'true');

        const shouldRestoreFocus = options.restoreFocus !== false;
        const restoreTarget = this.state.infoRestoreFocus?.isConnected
            ? this.state.infoRestoreFocus
            : this.dom.btnInfo;
        this.state.infoRestoreFocus = null;
        if (shouldRestoreFocus) this.focusElement(restoreTarget);
    },

    infoModalFocusableElements() {
        return Array.from(
            this.dom.infoModal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
        ).filter(element => !element.disabled && !element.hidden);
    },

    handleInfoModalKey(e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            e.stopPropagation();
            this.closeInfoModal();
            return;
        }
        if (e.key !== 'Tab') return;

        const focusable = this.infoModalFocusableElements();
        if (focusable.length === 0) {
            e.preventDefault();
            this.focusElement(this.dom.infoModal);
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

    isAlignmentPopoverOpen() {
        return !this.dom.alignPopover.hidden;
    },

    setAlignmentPopoverOpen(isOpen, options = {}) {
        this.dom.alignPopover.hidden = !isOpen;
        this.dom.btnAlignToggle.classList.toggle('active', isOpen);
        this.dom.btnAlignToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        this.dom.alignPopover.setAttribute('aria-hidden', isOpen ? 'false' : 'true');

        if (isOpen) {
            this.focusElement(this.dom.alignmentPreset);
            return;
        }
        if (options.restoreFocus !== false) {
            this.focusElement(this.dom.btnAlignToggle);
        }
    },

    bindInteractionEvents() {
        this.bindModeEvents();
        this.bindFrameNavigationEvents();
        this.bindClipSelectionEvents();
        this.bindViewportEvents();
        this.bindAlignmentEvents();
        this.bindInspectorEvents();
        this.bindBlinkEvents();
        this.bindFilmstripEvents();
        this.bindKeyboardEvents();
    },

    bindModeEvents() {
        this.dom.modeBtns.forEach(btn => {
            btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
        });
        this.dom.btnOverlays.addEventListener('click', () => {
            this.setOverlaysHidden(!this.state.overlaysHidden);
        });
        this.dom.btnFocusMode.addEventListener('click', () => {
            this.setFocusMode(!this.state.focusMode);
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
        this.dom.btnSwapClips.addEventListener('click', () => this.swapPairClips());
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
            panMoved: false,
            pointerPositions: new Map(),
            capturedPointerIds: new Set(),
            pinchActive: false,
            pinchStartDistance: 0,
            pinchStartZoom: 1.0,
            pinchContentX: 0,
            pinchContentY: 0
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

        if (this.dom.btnPaletteOrientation) {
            this.dom.btnPaletteOrientation.addEventListener('click', () => {
                const nextOrientation = this.state.paletteOrientation === 'horizontal' ? 'vertical' : 'horizontal';
                this.setPaletteOrientation(nextOrientation);
            });
        }

        this.dom.stage.addEventListener('pointerdown', (e) => {
            if (this.isViewportPaletteEvent(e)) return;
            this.trackPointerPosition(e);
            this.capturePointer(e.pointerId);
            if (this.shouldStartPinch(e)) {
                this.startPinchFromTrackedPointers();
                if (this.state.mode === 'blink') this.state.blinkPaused = true;
                e.preventDefault();
                return;
            }
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
            this.trackPointerPosition(e);
            const pointer = this.pointerInteraction;
            if (pointer.pinchActive) {
                this.updatePinchFromTrackedPointers();
                e.preventDefault();
                return;
            }
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
        this.dom.stage.addEventListener('dblclick', (e) => {
            if (this.isViewportPaletteEvent(e)) return;
            if (this.state.mode === 'overlay' || this.state.mode === 'diff') return;
            e.preventDefault();
            this.resetViewport();
        });
        this.dom.stage.addEventListener('wheel', (e) => {
            if (this.isViewportPaletteEvent(e)) return;
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

    isViewportPaletteEvent(e) {
        return Boolean(e.target?.closest?.('.rv-viewport-palette'));
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
            this.setAlignmentPopoverOpen(!this.isAlignmentPopoverOpen());
        });

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (
                this.isAlignmentPopoverOpen()
                && !this.dom.alignPopover.contains(e.target)
                && e.target !== this.dom.btnAlignToggle
            ) {
                this.closeAlignmentPopover({ restoreFocus: false });
            }
        });

        // Close on Escape key
        this.dom.alignPopover.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                e.stopPropagation();
                if (this.isHelpModalOpen()) {
                    this.closeHelpModal();
                    return;
                }
                if (this.isInfoModalOpen()) {
                    this.closeInfoModal();
                    return;
                }
                if (this.isInspectorVisible()) {
                    this.setInspectorOpen(false);
                    return;
                }
                this.closeAlignmentPopover();
            }
        });
    },

    closeAlignmentPopover(options = {}) {
        if (!this.isAlignmentPopoverOpen()) return;
        this.setAlignmentPopoverOpen(false, options);
    },

    bindHelpEvents() {
        this.dom.btnHelp.addEventListener('click', () => this.openHelpModal());
        this.dom.btnCloseHelp.addEventListener('click', () => this.closeHelpModal());
        this.dom.modal.addEventListener('click', (e) => {
            if (e.target === this.dom.modal) this.closeHelpModal();
        });
        this.dom.modal.addEventListener('keydown', (e) => this.handleModalKey(e));

        // The legacy info modal remains in markup as fallback content; the main Info
        // surface is the non-modal inspector drawer to avoid duplicate focus traps.
        this.dom.btnInfo.addEventListener('click', () => this.setInspectorOpen(!this.state.inspectorOpen));
        this.dom.btnCloseInfo.addEventListener('click', () => this.closeInfoModal());
        this.dom.infoModal.addEventListener('click', (e) => {
            if (e.target === this.dom.infoModal) this.closeInfoModal();
        });
        this.dom.infoModal.addEventListener('keydown', (e) => this.handleInfoModalKey(e));
    },

    bindInspectorEvents() {
        this.dom.btnInspectorClose.addEventListener('click', () => this.setInspectorOpen(false));
        this.dom.inspectorTabs.forEach(tab => {
            tab.addEventListener('click', () => this.setInspectorTab(tab.dataset.inspectorTab));
        });
        this.dom.btnInspectorResetCurrentAlign.addEventListener('click', () => this.resetCurrentPairAlignment());
        this.dom.btnInspectorResetAllAlign.addEventListener('click', () => this.resetAllPairAlignments());
        this.dom.inspector.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape') return;
            e.preventDefault();
            e.stopPropagation();
            this.setInspectorOpen(false);
        });
    },

    bindBlinkEvents() {
        this.dom.btnBlinkPause.addEventListener('click', () => this.setBlinkPaused(!this.state.blinkPaused));
        this.dom.blinkSpeed.addEventListener('change', (e) => this.setBlinkIntervalMs(Number(e.target.value)));
    },

    bindFilmstripEvents() {
        this.dom.btnFilmstripToggle.addEventListener('click', () => {
            this.setFilmstripCollapsed(!this.state.filmstripCollapsed);
        });
        this.dom.filmstripSizeBtns.forEach(btn => {
            btn.addEventListener('click', () => this.setFilmstripSize(btn.dataset.filmstripSize));
        });
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
        const stageRect = this.dom.stage.getBoundingClientRect();
        const stageCenterX = stageRect.left + stageRect.width / 2;
        const stageCenterY = stageRect.top + stageRect.height / 2;

        this.applyZoom(nextZoom, { clampPan: false });
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
        this.captureStagePointer(e);
        this.dom.stage.classList.add('is-panning');
    },

    stopPointerInteraction(e) {
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

        if (pointer.activePointerId !== null && e.pointerId !== pointer.activePointerId) return;
        const completedDrag = pointer.isDragging;
        const completedPan = pointer.isPanning;
        const completedPanMoved = pointer.panMoved;
        pointer.isDragging = false;
        pointer.isPanning = false;
        if (pointer.activePointerId === e.pointerId) {
            pointer.activePointerId = null;
        }
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

    modeUsesDistinctPair(mode = this.state.mode) {
        return mode === 'diff' || mode === 'blink';
    },

    nextDistinctClipIndex(startIdx, excludedIdx, direction = 1) {
        const count = this.clipCount();
        if (count <= 1) return this.clipIndexOrDefault(startIdx, 0);

        let idx = this.clipIndexOrDefault(startIdx, 0);
        for (let attempts = 0; attempts < count; attempts += 1) {
            idx = (idx + direction + count) % count;
            if (idx !== excludedIdx) return idx;
        }
        return idx;
    },

    ensureDistinctPairSelection(mode = this.state.mode) {
        if (!this.modeUsesDistinctPair(mode) || this.clipCount() <= 1) return;
        if (this.state.leftClipIdx !== this.state.rightClipIdx) return;

        this.state.rightClipIdx = this.nextDistinctClipIndex(
            this.state.rightClipIdx,
            this.state.leftClipIdx,
        );
    },

    applyDefaultSelection() {
        const selection = this.state.data.default_selection || {};
        const left = this.clipIndexOrDefault(selection.left_clip_index, 0);
        const rightFallback = this.clipCount() > 1 ? 1 : left;
        const right = this.clipIndexOrDefault(selection.right_clip_index, rightFallback);

        this.state.leftClipIdx = left;
        this.state.rightClipIdx = right;
        this.state.activeClipIdx = left;
        this.ensureDistinctPairSelection();
    },

    setLeftClip(idx) {
        this.storeCurrentPairAlignment();
        this.state.leftClipIdx = this.clipIndexOrDefault(idx, this.state.leftClipIdx);
        this.ensureDistinctPairSelection();
        this.loadCurrentPairAlignment();
        if (this.state.mode === 'blink') this.keepBlinkActiveInPair();
        this.render();
    },

    setRightClip(idx) {
        this.storeCurrentPairAlignment();
        this.state.rightClipIdx = this.clipIndexOrDefault(idx, this.state.rightClipIdx);
        this.ensureDistinctPairSelection();
        this.loadCurrentPairAlignment();
        if (this.state.mode === 'blink') {
            this.state.activeClipIdx = this.state.rightClipIdx;
        }
        if (this.state.mode === 'blink') this.keepBlinkActiveInPair();
        this.render();
    },

    swapPairClips() {
        if (this.state.mode === 'overlay' || this.clipCount() <= 1) return;

        this.storeCurrentPairAlignment();
        const previousLeft = this.state.leftClipIdx;
        this.state.leftClipIdx = this.state.rightClipIdx;
        this.state.rightClipIdx = previousLeft;
        this.loadCurrentPairAlignment();
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
        if (typeof saved.overlaysHidden === 'boolean') {
            this.state.overlaysHidden = saved.overlaysHidden;
        }
        if (typeof saved.filmstripCollapsed === 'boolean') {
            this.state.filmstripCollapsed = saved.filmstripCollapsed;
        }
        if (this.validFilmstripSize(saved.filmstripSize)) {
            this.state.filmstripSize = saved.filmstripSize;
        }
        if (typeof saved.inspectorOpen === 'boolean') {
            this.state.inspectorOpen = saved.inspectorOpen;
        }
        if (this.validInspectorTab(saved.inspectorTab)) {
            this.state.inspectorTab = saved.inspectorTab;
        }
        if (this.validBlinkIntervalMs(saved.blinkIntervalMs)) {
            this.state.blinkIntervalMs = saved.blinkIntervalMs;
        }
        if (this.validPaletteOrientation(saved.paletteOrientation)) {
            this.state.paletteOrientation = saved.paletteOrientation;
        }
        this.ensureDistinctPairSelection();
        this.state.pairAlignments = this.normalizedPairAlignments(saved.pairAlignments);
        if (!this.state.pairAlignments[this.currentPairAlignmentKey()]) {
            const legacyAlignment = this.normalizedAlignmentState(saved);
            if (legacyAlignment) {
                this.state.pairAlignments[this.currentPairAlignmentKey()] = legacyAlignment;
            }
        }
        this.loadCurrentPairAlignment();
        if (this.state.mode === 'blink') this.keepBlinkActiveInPair();
    },

    persistViewportState() {
        const storage = this.localStorage();
        if (!this.state.storageKey || !storage) return;
        this.storeCurrentPairAlignment();

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
            overlaysHidden: this.state.overlaysHidden,
            filmstripCollapsed: this.state.filmstripCollapsed,
            filmstripSize: this.state.filmstripSize,
            inspectorOpen: this.state.inspectorOpen,
            inspectorTab: this.state.inspectorTab,
            blinkIntervalMs: this.state.blinkIntervalMs,
            paletteOrientation: this.state.paletteOrientation,
            pairAlignments: this.state.pairAlignments
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

    hasFilmstripThumbnails() {
        return this.dom.bottomPanel?.dataset.filmstripEnabled === 'true';
    },

    validFilmstripSize(size) {
        return ['compact', 'normal', 'large'].includes(size);
    },

    validInspectorTab(tab) {
        return ['frame', 'clips', 'align', 'export'].includes(tab);
    },

    validBlinkIntervalMs(intervalMs) {
        return typeof intervalMs === 'number' && [300, 700, 1200].includes(intervalMs);
    },

    blinkIntervalOptions() {
        return [300, 700, 1200];
    },

    setFilmstripCollapsed(collapsed, options = {}) {
        if (!this.hasFilmstripThumbnails()) {
            this.state.filmstripCollapsed = false;
            this.updateFilmstripPanel();
            return;
        }
        this.state.filmstripCollapsed = Boolean(collapsed);
        this.updateFilmstripPanel();
        if (options.save !== false) this.persistViewportState();
    },

    setFilmstripSize(size, options = {}) {
        if (!this.validFilmstripSize(size)) return;
        this.state.filmstripSize = size;
        this.updateFilmstripPanel();
        if (options.save !== false) this.persistViewportState();
    },

    updateFilmstripPanel() {
        const hasThumbnails = this.hasFilmstripThumbnails();
        if (!hasThumbnails) this.state.filmstripCollapsed = false;
        const collapsed = hasThumbnails && this.state.filmstripCollapsed;
        this.dom.bottomPanel.classList.toggle('rv-bottom-panel--collapsed', collapsed);
        this.dom.bottomPanel.classList.toggle('rv-bottom-panel--disabled', !hasThumbnails);
        ['compact', 'normal', 'large'].forEach(size => {
            this.dom.bottomPanel.classList.toggle(`rv-filmstrip-size-${size}`, this.state.filmstripSize === size);
        });

        this.dom.btnFilmstripToggle.disabled = !hasThumbnails;
        this.dom.btnFilmstripToggle.textContent = hasThumbnails
            ? (collapsed ? 'Show timeline' : 'Hide timeline')
            : 'Filmstrip disabled';
        this.dom.btnFilmstripToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        this.dom.btnFilmstripToggle.setAttribute(
            'aria-label',
            hasThumbnails
                ? `${collapsed ? 'Expand' : 'Collapse'} timeline controls`
                : 'Filmstrip disabled'
        );
        this.dom.btnFilmstripToggle.setAttribute(
            'title',
            hasThumbnails ? 'Toggle timeline (F)' : 'Filmstrip disabled'
        );

        this.dom.filmstripSizeBtns.forEach(btn => {
            const isActive = btn.dataset.filmstripSize === this.state.filmstripSize;
            btn.disabled = !hasThumbnails;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-checked', isActive ? 'true' : 'false');
        });
    },

    setPaletteOrientation(orientation, options = {}) {
        if (!this.validPaletteOrientation(orientation)) return;
        this.state.paletteOrientation = orientation;
        this.updatePaletteOrientation();
        if (options.save !== false) this.persistViewportState();
    },

    updatePaletteOrientation() {
        if (!this.dom.viewportPalette) return;
        this.dom.viewportPalette.setAttribute('data-orientation', this.state.paletteOrientation);

        if (this.dom.btnPaletteOrientation) {
            const isVertical = this.state.paletteOrientation === 'vertical';
            this.dom.btnPaletteOrientation.textContent = isVertical ? '↕' : '↔';
            this.dom.btnPaletteOrientation.setAttribute('aria-label', `Switch to ${isVertical ? 'horizontal' : 'vertical'} orientation`);
            this.dom.btnPaletteOrientation.setAttribute('title', `Switch to ${isVertical ? 'horizontal' : 'vertical'} orientation`);
        }
    },

    setInspectorOpen(open, options = {}) {
        const nextOpen = Boolean(open);
        const wasOpen = this.state.inspectorOpen;
        if (nextOpen && !wasOpen && options.focus !== false) {
            const activeElement = document.activeElement;
            this.state.inspectorRestoreFocus = activeElement && typeof activeElement.focus === 'function'
                ? activeElement
                : this.dom.btnInfo;
        }

        this.state.inspectorOpen = nextOpen;
        if (this.state.inspectorOpen && this.state.focusMode) {
            this.setFocusMode(false);
        }
        this.updateInspectorVisibility();
        if (options.save !== false) this.persistViewportState();
        if (this.state.inspectorOpen && options.focus !== false) {
            this.focusElement(this.dom.inspectorTabs[0]);
        } else if (!this.state.inspectorOpen && wasOpen) {
            const shouldRestoreFocus = options.focus !== false;
            const restoreTarget = this.state.inspectorRestoreFocus?.isConnected
                ? this.state.inspectorRestoreFocus
                : this.dom.btnInfo;
            this.state.inspectorRestoreFocus = null;
            if (shouldRestoreFocus) this.focusElement(restoreTarget);
        }
    },

    isInspectorVisible() {
        return this.state.inspectorOpen && !this.state.focusMode;
    },

    updateInspectorVisibility() {
        const visible = this.isInspectorVisible();
        document.body?.classList?.toggle('rv-inspector-open', visible);
        this.dom.inspector.classList.toggle('open', visible);
        this.dom.inspector.setAttribute('aria-hidden', visible ? 'false' : 'true');
        this.setInspectorFocusable(visible);
        this.dom.btnInfo.classList.toggle('active', visible);
        this.dom.btnInfo.setAttribute('aria-pressed', visible ? 'true' : 'false');
        this.dom.btnInfo.setAttribute(
            'aria-label',
            visible ? 'Close inspector' : 'Open inspector'
        );
        this.dom.btnInfo.setAttribute(
            'title',
            visible ? 'Close inspector (I)' : 'Open inspector (I)'
        );
    },

    inspectorFocusableElements() {
        return Array.from(
            this.dom.inspector.querySelectorAll('button, [href], input, select, textarea, [tabindex]')
        );
    },

    setInspectorFocusable(enabled) {
        this.dom.inspector.inert = !enabled;
        this.inspectorFocusableElements().forEach(element => {
            if (enabled) {
                if (Object.hasOwn(element.dataset, 'inspectorPreviousTabindex')) {
                    const previous = element.dataset.inspectorPreviousTabindex;
                    if (previous === '') {
                        element.removeAttribute('tabindex');
                    } else {
                        element.setAttribute('tabindex', previous);
                    }
                    delete element.dataset.inspectorPreviousTabindex;
                } else if (element.getAttribute('tabindex') === '-1') {
                    element.removeAttribute('tabindex');
                }
                return;
            }

            if (!Object.hasOwn(element.dataset, 'inspectorPreviousTabindex')) {
                element.dataset.inspectorPreviousTabindex = element.getAttribute('tabindex') ?? '';
            }
            element.setAttribute('tabindex', '-1');
        });
    },

    safeHttpUrl(url) {
        if (typeof url !== 'string' || url.length === 0) return null;
        try {
            const parsed = new URL(url);
            return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : null;
        } catch {
            return null;
        }
    },

    updateInspectorSlowpics() {
        if (!this.dom.inspectorExportSlowpics) return;
        const slowpicsUrl = this.state.data.slowpics_url;
        const safeUrl = this.safeHttpUrl(slowpicsUrl);
        if (!safeUrl) {
            this.dom.inspectorExportSlowpics.replaceChildren(
                document.createTextNode(slowpicsUrl || 'Not uploaded')
            );
            return;
        }

        const link = document.createElement('a');
        link.href = safeUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.className = 'rv-link';
        link.textContent = slowpicsUrl;
        this.dom.inspectorExportSlowpics.replaceChildren(link);
    },

    setInspectorTab(tab, options = {}) {
        if (!this.validInspectorTab(tab)) tab = 'frame';
        this.state.inspectorTab = tab;
        this.updateInspectorTabs();
        if (options.save !== false) this.persistViewportState();
    },

    updateInspectorTabs() {
        this.dom.inspectorTabs.forEach(tab => {
            const isActive = tab.dataset.inspectorTab === this.state.inspectorTab;
            tab.classList.toggle('active', isActive);
            tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });
        this.dom.inspectorPanels.forEach(panel => {
            panel.hidden = panel.id !== `inspector-panel-${this.state.inspectorTab}`;
        });
    },

    setText(element, text) {
        if (element) element.textContent = String(text ?? '');
    },

    currentFrame() {
        return this.state.data?.frames?.[this.state.currentFrameIdx] || null;
    },

    currentClipRole(index) {
        const roles = [];
        if (index === this.state.leftClipIdx && this.state.mode !== 'overlay') roles.push('Left');
        if (index === this.state.rightClipIdx && this.state.mode !== 'overlay') roles.push('Right');
        if (index === this.state.activeClipIdx && (this.state.mode === 'overlay' || this.state.mode === 'blink')) {
            roles.push(this.state.mode === 'overlay' ? 'Active' : 'Visible');
        }
        return roles.length > 0 ? roles.join(', ') : 'Available';
    },

    modeLabel(mode = this.state.mode) {
        const labels = {
            slider: 'Slider',
            overlay: 'Single',
            diff: 'Diff',
            blink: 'Blink'
        };
        return labels[mode] || mode;
    },

    formatFps(value) {
        const fps = Number(value);
        if (!Number.isFinite(fps)) return '';
        return `${Number.isInteger(fps) ? fps : fps.toString()} fps`;
    },

    currentPairLabel() {
        const left = this.state.data.clips[this.state.leftClipIdx]?.label || `Clip ${this.state.leftClipIdx + 1}`;
        const right = this.state.data.clips[this.state.rightClipIdx]?.label || `Clip ${this.state.rightClipIdx + 1}`;
        return `${left} vs ${right}`;
    },

    visibleFramePositionText() {
        const visibleIndexes = this.visibleFrameIndexes();
        const position = this.visibleFramePosition(visibleIndexes);
        if (position === -1) return `Not shown of ${visibleIndexes.length}`;
        return `${position + 1} of ${visibleIndexes.length} shown`;
    },

    updateInspectorData() {
        if (!this.dom.inspector) return;
        const frame = this.currentFrame();
        this.setText(this.dom.inspectorFrameLabel, frame?.label || 'No frame selected');
        this.setText(this.dom.inspectorFrameNumber, frame?.number ?? '');
        this.setText(this.dom.inspectorFrameCategory, frame?.category ? this.humanizeCategory(frame.category) : '');
        this.setText(this.dom.inspectorFrameDetail, frame?.detail || '');
        this.setText(this.dom.inspectorFramePosition, this.visibleFramePositionText());

        if (this.dom.inspectorClips) {
            this.dom.inspectorClips.replaceChildren(...this.state.data.clips.map((clip, index) => {
                const item = document.createElement('li');
                item.className = 'rv-inspector-clip';
                item.dataset.clipIndex = String(index);
                const role = this.currentClipRole(index);
                const hdrTag = clip.hdr ? 'HDR' : 'SDR';
                item.innerHTML = `
                    <div class="rv-inspector-clip-heading">
                        <span></span>
                        <span></span>
                    </div>
                    <dl class="rv-inspector-list">
                        <div><dt>Role</dt><dd></dd></div>
                        <div><dt>Source</dt><dd></dd></div>
                        <div><dt>Resolution</dt><dd></dd></div>
                        <div><dt>FPS</dt><dd></dd></div>
                    </dl>
                `;
                const heading = item.querySelectorAll('.rv-inspector-clip-heading span');
                heading[0].textContent = clip.label || `Clip ${index + 1}`;
                heading[1].textContent = hdrTag;
                const values = item.querySelectorAll('dd');
                values[0].textContent = role;
                values[1].textContent = clip.name || '';
                values[2].textContent = Array.isArray(clip.resolution) ? `${clip.resolution[0]}x${clip.resolution[1]}` : '';
                values[3].textContent = this.formatFps(clip.fps);
                return item;
            }));
        }

        this.setText(this.dom.inspectorAlignPair, `${this.currentPairLabel()} (${this.currentPairAlignmentKey()})`);
        this.setText(this.dom.inspectorAlignPreset, this.alignmentPresetLabel(this.state.alignmentPreset));
        this.setText(this.dom.inspectorAlignX, this.formatSignedPixels(this.state.alignX, 'x'));
        this.setText(this.dom.inspectorAlignY, this.formatSignedPixels(this.state.alignY, 'y'));

        this.setText(this.dom.inspectorExportTitle, this.state.data.title || '');
        this.setText(this.dom.inspectorExportId, this.state.data.report_id || '');
        this.setText(this.dom.inspectorExportGenerated, this.state.data.generated_at || '');
        this.updateInspectorSlowpics();
        this.setText(
            this.dom.inspectorExportSummary,
            `${this.state.data.title || 'Report'} • ${this.state.data.stats.frame_count} frames • ${this.state.data.stats.clip_count} clips • ${this.modeLabel()}`
        );

        this.updateInspectorTabs();
        this.updateInspectorVisibility();
    },

    resetCurrentPairAlignment() {
        delete this.state.pairAlignments[this.currentPairAlignmentKey()];
        this.applyAlignmentState(this.neutralAlignmentState());
        this.applyAlignment();
        this.persistViewportState();
    },

    resetAllPairAlignments() {
        this.state.pairAlignments = {};
        this.applyAlignmentState(this.neutralAlignmentState());
        this.applyAlignment();
        this.persistViewportState();
    },

    setOverlaysHidden(hidden, options = {}) {
        this.state.overlaysHidden = Boolean(hidden);
        this.updateOverlayVisibility();
        if (options.save !== false) this.persistViewportState();
    },

    updateOverlayVisibility() {
        const overlaysVisible = !this.state.overlaysHidden;
        this.dom.stage.classList.toggle('rv-overlays-hidden', !overlaysVisible);
        this.dom.btnOverlays.classList.toggle('active', overlaysVisible);
        this.dom.btnOverlays.setAttribute('aria-pressed', overlaysVisible ? 'true' : 'false');
        this.dom.btnOverlays.setAttribute(
            'aria-label',
            overlaysVisible ? 'Hide HUD' : 'Show HUD'
        );
        this.dom.btnOverlays.setAttribute(
            'title',
            `${overlaysVisible ? 'Hide' : 'Show'} HUD (H)`
        );
    },

    reducedMotionActive() {
        return Boolean(
            window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
        );
    },

    setBlinkIntervalMs(intervalMs, options = {}) {
        const normalized = Number(intervalMs);
        if (!this.validBlinkIntervalMs(normalized)) return;
        this.state.blinkIntervalMs = normalized;
        this.updateBlinkControls();
        if (this.state.mode === 'blink') this.restartBlink();
        if (options.save !== false) this.persistViewportState();
    },

    setBlinkPaused(paused) {
        this.state.blinkPaused = Boolean(paused);
        this.updateBlinkControls();
    },

    stepBlinkInterval(direction) {
        const options = this.blinkIntervalOptions();
        const currentIndex = Math.max(0, options.indexOf(this.state.blinkIntervalMs));
        const nextIndex = Math.max(0, Math.min(options.length - 1, currentIndex + direction));
        this.setBlinkIntervalMs(options[nextIndex]);
    },

    updateBlinkControls() {
        const isBlink = this.state.mode === 'blink';
        this.dom.blinkControls.hidden = !isBlink;
        this.dom.btnBlinkPause.disabled = !isBlink;
        this.dom.blinkSpeed.disabled = !isBlink;
        this.dom.blinkSpeed.value = String(this.state.blinkIntervalMs);
        this.dom.btnBlinkPause.textContent = this.state.blinkPaused ? 'Resume' : 'Pause';
        this.dom.btnBlinkPause.setAttribute('aria-pressed', this.state.blinkPaused ? 'true' : 'false');
        this.dom.btnBlinkPause.setAttribute(
            'aria-label',
            this.state.blinkPaused ? 'Resume blink' : 'Pause blink'
        );
        this.dom.blinkStatus.textContent = isBlink
            ? (this.state.blinkPaused ? 'Blink paused' : `Blink ${this.state.blinkIntervalMs / 1000}s`)
            : '';
    },

    restartBlink() {
        if (this.state.blinkInterval) {
            clearInterval(this.state.blinkInterval);
            this.state.blinkInterval = null;
        }
        if (this.state.mode === 'blink') this.startBlink();
    },

    setFocusMode(enabled) {
        const nextFocusMode = Boolean(enabled);
        if (nextFocusMode && this.state.inspectorOpen) {
            this.setInspectorOpen(false, { focus: false });
        }
        this.state.focusMode = nextFocusMode;
        document.body?.classList?.toggle('rv-focus-mode', this.state.focusMode);
        this.dom.btnFocusMode.classList.toggle('active', this.state.focusMode);
        this.dom.btnFocusMode.setAttribute('aria-pressed', this.state.focusMode ? 'true' : 'false');
        this.dom.btnFocusMode.setAttribute(
            'aria-label',
            this.state.focusMode ? 'Exit focus mode' : 'Enter focus mode'
        );
        this.dom.btnFocusMode.textContent = this.state.focusMode ? 'Exit focus' : 'Focus';
        this.updateInspectorVisibility();
        this.updateFocusHud();
        this.applyFitMode();
    },

    updateFocusHud() {
        if (!this.dom.focusHudFrame) return;
        const frame = this.currentFrame();
        this.setText(this.dom.focusHudFrame, frame?.label || 'No frame');
        this.setText(this.dom.focusHudMode, this.modeLabel());
        this.setText(
            this.dom.focusHudPair,
            this.state.mode === 'overlay'
                ? (this.state.data.clips[this.state.activeClipIdx]?.label || '')
                : this.currentPairLabel()
        );
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

        if (this.dom.activeFilterBadge) {
            const isFiltered = this.state.activeCategoryKey !== ALL_CATEGORY_FILTER_KEY;
            if (isFiltered) {
                const activeBtn = Array.from(this.dom.filterChips)
                    .find(btn => btn.dataset.categoryKey === this.state.activeCategoryKey);
                const label = activeBtn
                    ? activeBtn.textContent.replace(/\s*\(\d+\)\s*$/, '')
                    : this.state.activeCategoryKey;
                this.dom.activeFilterBadge.textContent = `Filtered: ${label}`;
                this.dom.activeFilterBadge.hidden = false;
            } else {
                this.dom.activeFilterBadge.hidden = true;
                this.dom.activeFilterBadge.textContent = '';
            }
        }
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
            if (this.isInfoModalOpen()) {
                e.preventDefault();
                this.closeInfoModal();
                return;
            }
            if (this.isInspectorVisible()) {
                e.preventDefault();
                this.setInspectorOpen(false);
                return;
            }
            if (this.isAlignmentPopoverOpen()) {
                e.preventDefault();
                this.closeAlignmentPopover();
                return;
            }
            if (this.state.focusMode) {
                e.preventDefault();
                this.setFocusMode(false);
                return;
            }
            if (document.fullscreenElement) {
                e.preventDefault();
                document.exitFullscreen?.();
                return;
            }
        }

        if (this.dom.modal.classList.contains('open') || this.dom.infoModal.classList.contains('open')) return;
        if (this.isAlignmentPopoverOpen()) return;
        if (this.isShortcutEditableTarget(e.target)) return;

        if (e.key === 'i' || e.key === 'I') {
            e.preventDefault();
            this.setInspectorOpen(!this.state.inspectorOpen);
            return;
        }

        if (this.state.mode === 'blink') {
            if (e.key === ' ') {
                e.preventDefault();
                this.setBlinkPaused(!this.state.blinkPaused);
                return;
            }
            if (e.key === '[') {
                e.preventDefault();
                this.stepBlinkInterval(1);
                return;
            }
            if (e.key === ']') {
                e.preventDefault();
                this.stepBlinkInterval(-1);
                return;
            }
        }

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
            case 'x': case 'X': this.swapPairClips(); break;
            case 'h': case 'H': this.setOverlaysHidden(!this.state.overlaysHidden); break;
            case 'f': case 'F': this.setFilmstripCollapsed(!this.state.filmstripCollapsed); break;
            case 'z': case 'Z': this.setFocusMode(!this.state.focusMode); break;

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
        this.ensureDistinctPairSelection(mode);
        if (mode === 'blink') this.keepBlinkActiveInPair();

        // Stop blink if leaving blink mode
        if (this.state.blinkInterval && mode !== 'blink') {
            clearInterval(this.state.blinkInterval);
            this.state.blinkInterval = null;
        }
        // Start blink if entering
        if (mode === 'blink' && !this.state.blinkInterval) {
            if (this.reducedMotionActive()) {
                this.state.blinkPaused = true;
            }
            this.startBlink();
        } else if (mode !== 'blink') {
            this.state.blinkPaused = false;
        }

        this.dom.modeBtns.forEach(btn => {
            const isActive = btn.dataset.mode === mode;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-checked', isActive);
        });

        this.dom.stage.classList.remove(
            'rv-mode-slider',
            'rv-mode-overlay',
            'rv-mode-diff',
            'rv-mode-blink',
        );
        this.dom.stage.classList.add(`rv-mode-${mode}`);
        this.updateModeControls();
        this.updateBlinkControls();
        this.updateFocusHud();
        this.render();
    },

    startBlink() {
        this.state.blinkInterval = setInterval(() => {
            if (this.state.blinkPaused) return;

            this.state.activeClipIdx = this.state.activeClipIdx === this.state.leftClipIdx
                ? this.state.rightClipIdx
                : this.state.leftClipIdx;
            this.updateImages();

        }, this.state.blinkIntervalMs);
        this.updateBlinkControls();
    },

    updateModeControls() {
        const mode = this.state.mode;
        const isOverlay = mode === 'overlay';
        this.dom.pairControls.hidden = isOverlay;
        this.dom.activeControls.hidden = !isOverlay;
        this.dom.leftSelect.disabled = isOverlay;
        this.dom.rightSelect.disabled = isOverlay;
        this.dom.btnSwapClips.disabled = isOverlay || this.clipCount() <= 1;
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
        this.dom.activeSelect.setAttribute('aria-label', 'Single clip');
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
            this.setRightClip(
                this.nextDistinctClipIndex(this.state.rightClipIdx, this.state.leftClipIdx, direction)
            );
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
        this.dom.canvas.classList.toggle('rv-canvas--pixelated', this.state.zoom > 1);
        this.dom.canvas.style.setProperty('--zoom-level', this.state.zoom);
        if (options.clampPan !== false) this.clampPan();
        this.updateSmartStageLabels();
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
        this.updateSmartStageLabels();
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
        this.updateFocusHud();
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
        this.dom.canvas.style.setProperty('--reveal-percent', this.state.revealPercent + '%');
        this.updateSmartStageLabels();
    },

    isShortcutEditableTarget(target) {
        if (!target) return false;
        if (target.isContentEditable) return true;

        const tagName = String(target.tagName || '').toUpperCase();
        if (['INPUT', 'SELECT', 'BUTTON', 'TEXTAREA'].includes(tagName)) return true;

        const closestEditable = target.closest?.(
            'input, select, button, textarea, [contenteditable=""], [contenteditable="true"]'
        );
        return Boolean(closestEditable);
    },

    untransformedCanvasWidth() {
        const offsetWidth = this.dom.canvas.offsetWidth;
        if (Number.isFinite(offsetWidth) && offsetWidth > 0) return offsetWidth;

        const clientWidth = this.dom.canvas.clientWidth;
        if (Number.isFinite(clientWidth) && clientWidth > 0) return clientWidth;

        const rectWidth = this.dom.canvas.getBoundingClientRect().width;
        if (rectWidth <= 0) return 0;
        return rectWidth / this.clampZoom(this.state.zoom);
    },

    smartLabelPositions(canvasWidth, leftLabelWidth, rightLabelWidth) {
        if (canvasWidth <= 0) return null;

        const edgePadding = 8;
        const dividerX = canvasWidth * (1 - (this.state.revealPercent / 100));
        const leftX = Math.max(
            edgePadding + leftLabelWidth,
            Math.min(canvasWidth - edgePadding, dividerX - 10)
        );
        const rightX = Math.max(
            edgePadding,
            Math.min(canvasWidth - rightLabelWidth - edgePadding, dividerX + 10)
        );

        return { leftX, rightX };
    },

    updateSmartStageLabels() {
        if (!this.dom.canvas || !this.dom.labelLeft || !this.dom.labelRight) return;

        if (this.state.mode !== 'slider') {
            this.dom.canvas.style.removeProperty('--label-left-x');
            this.dom.canvas.style.removeProperty('--label-right-x');
            return;
        }

        const positions = this.smartLabelPositions(
            this.untransformedCanvasWidth(),
            this.dom.labelLeft.offsetWidth || 0,
            this.dom.labelRight.offsetWidth || 0,
        );
        if (!positions) return;

        this.dom.canvas.style.setProperty('--label-left-x', `${positions.leftX}px`);
        this.dom.canvas.style.setProperty('--label-right-x', `${positions.rightX}px`);
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

    normalizedDisplayToken(value) {
        return String(value || '')
            .trim()
            .toLowerCase()
            .replace(/[_-]+/g, ' ')
            .replace(/\s+/g, ' ');
    },

    shouldShowFrameCategory(label, categoryText) {
        return Boolean(categoryText)
            && this.normalizedDisplayToken(label) !== this.normalizedDisplayToken(categoryText);
    },

    updateCurrentFrameMetadata(frameData) {
        const frame = frameData || this.state.data?.frames?.[this.state.currentFrameIdx] || null;
        const label = frame?.label || 'No frame selected';
        const categoryText = frame?.category ? this.humanizeCategory(frame.category) : '';
        const showCategory = this.shouldShowFrameCategory(label, categoryText);

        if (this.dom.currentFrameLabel) this.dom.currentFrameLabel.textContent = label;
        if (this.dom.currentFrameCategoryDivider) {
            this.dom.currentFrameCategoryDivider.hidden = !showCategory;
        }
        if (this.dom.currentFrameCategory) {
            this.dom.currentFrameCategory.hidden = !showCategory;
            this.dom.currentFrameCategory.textContent = showCategory ? categoryText : '';
        }
    },

    blinkStageLabels(leftClipLabel, rightClipLabel) {
        if (this.state.activeClipIdx === this.state.rightClipIdx) {
            return {
                left: '',
                right: rightClipLabel,
            };
        }
        return {
            left: leftClipLabel,
            right: '',
        };
    },

    commitImageState(imageState) {
        const requestToken = ++this.state.imageRequestToken;
        const commit = () => {
            if (requestToken !== this.state.imageRequestToken) return;
            this.applyImageState(imageState);
        };

        if (!this.shouldAwaitAtomicDiffSwap(imageState)) {
            commit();
            return;
        }

        Promise.all([
            this.ensureImageReady(imageState.leftSrc),
            this.ensureImageReady(imageState.rightSrc),
        ]).then(() => {
            if (typeof window.requestAnimationFrame === 'function') {
                window.requestAnimationFrame(() => commit());
                return;
            }
            commit();
        });
    },

    shouldAwaitAtomicDiffSwap(imageState) {
        return this.state.mode === 'diff'
            && (
                this.dom.leftImg.getAttribute('src') !== imageState.leftSrc
                || this.dom.rightImg.getAttribute('src') !== imageState.rightSrc
            );
    },

    applyImageState(imageState) {
        const {
            frameData,
            leftSrc,
            rightSrc,
            leftAlt,
            rightAlt,
            leftLabelTxt,
            rightLabelTxt,
            isOverlay,
            isBlink,
        } = imageState;

        if (this.dom.leftImg.getAttribute('src') !== leftSrc) {
            if (this.dom.sizerImg && this.dom.sizerImg.getAttribute('src') !== leftSrc) {
                this.dom.sizerImg.src = leftSrc;
            }
            this.dom.leftImg.src = leftSrc;
        }
        if (this.dom.rightImg.getAttribute('src') !== rightSrc) {
            this.dom.rightImg.src = rightSrc;
        }

        this.dom.leftImg.alt = leftAlt;
        this.dom.rightImg.alt = rightAlt;
        this.dom.labelLeft.textContent = leftLabelTxt;
        this.dom.labelRight.textContent = rightLabelTxt;
        this.updateSmartStageLabels();
        this.updateCurrentFrameMetadata(frameData);

        this.dom.leftLayer.classList.toggle(
            'active',
            isOverlay || (isBlink && this.state.activeClipIdx === this.state.leftClipIdx)
        );
        this.dom.leftLayer.classList.toggle(
            'rv-layer--aligned-active',
            isOverlay && this.state.activeClipIdx === this.state.rightClipIdx
        );
        this.dom.rightLayer.classList.toggle(
            'active',
            isBlink && this.state.activeClipIdx === this.state.rightClipIdx
        );
    },

    updateImages() {
        const frameData = this.state.data.frames[this.state.currentFrameIdx];
        if (!frameData) {
            this.showStageMessage('Selected frame data is unavailable.');
            this.showStatus('Selected frame data is unavailable.', 'error');
            this.clearFrameImages();
            return;
        }

        let leftSrc, rightSrc;
        let leftLabelTxt, rightLabelTxt;
        let leftAlt, rightAlt;
        const isOverlay = this.state.mode === 'overlay';
        const isBlink = this.state.mode === 'blink';

        if (this.state.mode === 'slider' || this.state.mode === 'diff' || this.state.mode === 'blink') {
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

            if (this.state.mode === 'blink') {
                const blinkLabels = this.blinkStageLabels(leftClip.label, rightClip.label);
                leftLabelTxt = blinkLabels.left;
                rightLabelTxt = blinkLabels.right;
            } else {
                leftLabelTxt = `${leftClip.label} (Left)`;
                rightLabelTxt = `${rightClip.label} (Right)`;
            }
            leftAlt = `${leftClip.label} - Frame ${frameData.number}`;
            rightAlt = `${rightClip.label} - Frame ${frameData.number}`;

            // For Diff mode, right layer is the "compare" one which gets difference blend
            // Left layer is base.

        } else {
            // Overlay uses the left layer as the single visible layer.
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
            leftAlt = `${activeClip.label} - Frame ${frameData.number}`;
            rightAlt = `${rightClip.label} - Frame ${frameData.number}`;
        }

        this.hideStageMessage();
        this.clearStatus();
        this.commitImageState({
            frameData,
            leftSrc,
            rightSrc,
            leftAlt,
            rightAlt,
            leftLabelTxt,
            rightLabelTxt,
            isOverlay,
            isBlink,
        });
    },

    clearFrameImages() {
        this.state.imageRequestToken += 1;
        if (this.dom.sizerImg) this.dom.sizerImg.src = EMPTY_IMAGE_SRC;
        if (this.dom.leftImg) {
            this.dom.leftImg.src = EMPTY_IMAGE_SRC;
            this.dom.leftImg.alt = '';
        }
        if (this.dom.rightImg) {
            this.dom.rightImg.src = EMPTY_IMAGE_SRC;
            this.dom.rightImg.alt = '';
        }
        this.dom.leftLayer?.classList?.remove('active', 'rv-layer--aligned-active');
        this.dom.rightLayer?.classList?.remove('active');
        if (this.dom.labelLeft) this.dom.labelLeft.textContent = '';
        if (this.dom.labelRight) this.dom.labelRight.textContent = '';
        this.updateCurrentFrameMetadata(null);
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
        this.updateOverlayVisibility();
        this.updateFilmstripPanel();
        this.updatePaletteOrientation();
        this.updateBlinkControls();
        this.updateInspectorData();
        this.updateFocusHud();

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
        void this.ensureImageReady(src);
    },

    ensureImageReady(src) {
        if (!src || src.startsWith('data:')) return Promise.resolve();

        const existingPromise = this.state.imageLoadPromises.get(src);
        if (existingPromise) return existingPromise;

        const promise = new Promise(resolve => {
            const image = new Image();
            let settled = false;
            const finish = () => {
                if (settled) return;
                settled = true;
                resolve();
            };
            const decodeAndFinish = () => {
                if (typeof image.decode === 'function') {
                    image.decode().catch(() => undefined).finally(finish);
                    return;
                }
                finish();
            };

            image.addEventListener('load', decodeAndFinish, { once: true });
            image.addEventListener('error', finish, { once: true });
            image.decoding = 'async';
            image.src = src;
            if (image.complete) {
                if (image.naturalWidth > 0 || image.naturalHeight > 0) {
                    decodeAndFinish();
                } else {
                    finish();
                }
            }
        });

        this.state.imageLoadPromises.set(src, promise);
        return promise;
    }
};

document.addEventListener('DOMContentLoaded', () => ReportViewer.init());
