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

    clipDisplay(clip, profile = 'control') {
        return ViewerFormat.clipDisplay(clip, profile);
    },

    clipFilename(clip) {
        return ViewerFormat.clipFilename(clip);
    },

    clipAccessibleName(clip) {
        return ViewerFormat.clipAccessibleName(clip);
    },

    init() {
        this.inspector = Inspector.create(this);
        this.viewport = Viewport.create(this);
        this.cacheDOM();
        if (!this.hasRequiredDOM()) {
            this.showStatus('Report viewer markup is incomplete.', 'error');
            return;
        }

        try {
            this.state.data = this.normalizePayload(this.readPayload());
            this.state.mode = this.validPayloadMode(this.state.data.default_mode)
                ? this.state.data.default_mode
                : 'slider';
            this.state.storageKey = this.viewportStorageKey();
            this.state.categoryFilterKeys = this.buildCategoryFilterKeys();
            this.applyDefaultSelection();
            this.restorePersistedState();
            this.lens = Lens.create(this);
            this.gridView = GridView.create(this);
            this.reviewController = null;
            if (this.state.inspectorOpen && this.state.inspectorTab === 'review') {
                this.ensureReviewController();
            }
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
            btnPaletteOrientation: document.getElementById('btn-palette-orientation'),
            palette: document.querySelector('.rv-viewport-palette'),
            blinkControls: document.querySelector('[data-control-scope="blink"]'),
            btnBlinkPause: document.getElementById('btn-blink-pause'),
            blinkSpeed: document.getElementById('blink-speed'),
            blinkStatus: document.getElementById('blink-status'),
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
            live: document.getElementById('viewer-live'),
            grid: document.getElementById('rv-grid'),
            gridCells: document.querySelector('[data-grid-cells]'),
            gridControls: document.querySelector('[data-control-scope="grid"]'),
            btnGridPrev: document.getElementById('btn-grid-prev'),
            btnGridNext: document.getElementById('btn-grid-next'),
            btnCloseInfo: document.getElementById('btn-close-info'),
            reviewFrame: document.querySelector('[data-review-frame]'),
            reviewBookmark: document.querySelector('[data-review-bookmark]'),
            reviewTag: document.querySelector('[data-review-tag]'),
            reviewNote: document.querySelector('[data-review-note]'),
            reviewNoteCount: document.querySelector('[data-review-note-count]'),
            reviewPreferred: document.querySelector('[data-review-preferred]'),
            reviewStatus: document.querySelector('[data-review-status]'),
            reviewExport: document.querySelector('[data-review-export]'),
            reviewImportTrigger: document.querySelector('[data-review-import-trigger]'),
            reviewImport: document.querySelector('[data-review-import]'),
            reviewPreview: document.querySelector('[data-review-preview]'),
            reviewPreviewCounts: document.querySelector('[data-review-preview-counts]'),
            reviewImportApply: document.querySelector('[data-review-import-apply]'),
            reviewImportCancel: document.querySelector('[data-review-import-cancel]'),
            btnAlignToggle: document.getElementById('btn-align-toggle'),
            alignPopover: document.getElementById('align-popover'),
            btnOverlays: document.getElementById('btn-overlays'),
            ...this.inspector.cacheDOM(),
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
            this.dom.btnInspector,
            this.dom.live,
            this.dom.grid,
            this.dom.gridCells,
            this.dom.gridControls,
            this.dom.btnGridPrev,
            this.dom.btnGridNext,
            this.dom.btnCloseInfo,
            this.dom.inspector,
            this.dom.btnInspectorClose,
            this.dom.inspectorClips,
            this.dom.btnInspectorResetCurrentAlign,
            this.dom.btnInspectorResetAllAlign,
            this.dom.reviewFrame,
            this.dom.reviewBookmark,
            this.dom.reviewTag,
            this.dom.reviewNote,
            this.dom.reviewNoteCount,
            this.dom.reviewPreferred,
            this.dom.reviewStatus,
            this.dom.reviewExport,
            this.dom.reviewImportTrigger,
            this.dom.reviewImport,
            this.dom.reviewPreview,
            this.dom.reviewPreviewCounts,
            this.dom.reviewImportApply,
            this.dom.reviewImportCancel,
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
        return ['slider', 'overlay', 'diff', 'blink', 'grid'].includes(mode);
    },

    validPayloadMode(mode) {
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

    announce(message) {
        if (!this.dom?.live || !message) return;
        this.dom.live.textContent = '';
        window.setTimeout(() => {
            this.dom.live.textContent = message;
        }, 0);
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
        this.gridView.bind();
        this.lens.bind();
    },

    bindModeEvents() {
        this.dom.modeBtns.forEach(btn => {
            btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
        });
        this.dom.btnOverlays.addEventListener('click', () => {
            this.setOverlaysHidden(!this.state.overlaysHidden);
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
            const nextIndex = this.clipIndexOrDefault(e.target.value, this.state.activeClipIdx);
            this.state.activeClipIdx = nextIndex;
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
            pinchContentY: 0,
            pinchGridAnchor: null,
            panBasis: null,
            lensPointHandled: false,
            lensTouchStart: null,
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
            if (this.isViewerChromeEvent(e)) return;
            this.pointerInteraction.lensPointHandled = this.lens.handleStagePointerDown(e);
            this.trackPointerPosition(e);
            this.capturePointer(e.pointerId);
            if (this.shouldStartPinch(e)) {
                this.lens.cancelTouchPending();
                this.pointerInteraction.lensPointHandled = false;
                this.pointerInteraction.lensTouchStart = null;
                this.startPinchFromTrackedPointers();
                if (this.state.mode === 'blink') this.state.blinkPaused = true;
                e.preventDefault();
                return;
            }
            if (this.pointerInteraction.lensPointHandled) {
                this.pointerInteraction.lensTouchStart = {
                    pointerId: e.pointerId,
                    clientX: e.clientX,
                    clientY: e.clientY,
                };
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
            if (this.isViewerChromeEvent(e)) return;
            const lensMove = this.lens.handleStagePointerMove(e);
            this.trackPointerPosition(e);
            const pointer = this.pointerInteraction;
            if (pointer.lensPointHandled && pointer.lensTouchStart?.pointerId === e.pointerId) {
                if (lensMove === 'pending') {
                    e.preventDefault();
                    return;
                }
                if (lensMove === 'released') {
                    pointer.lensPointHandled = false;
                    this.startDeferredViewportGesture(e, pointer.lensTouchStart);
                    pointer.lensTouchStart = null;
                }
            }
            if (pointer.pinchActive) {
                this.updatePinchFromTrackedPointers();
                e.preventDefault();
                return;
            }
            if (pointer.activePointerId !== null && e.pointerId !== pointer.activePointerId) return;
            if (this.updatePanFromPointer(e)) {
                e.preventDefault();
                return;
            }
            if (pointer.isDragging) {
                this.updateSliderFromPointer(e);
                e.preventDefault();
            }
        });
        this.dom.stage.addEventListener('pointerup', (e) => this.stopPointerInteraction(e));
        this.dom.stage.addEventListener('pointercancel', (e) => {
            this.stopPointerInteraction(e, { cancelled: true });
        });
        this.dom.stage.addEventListener('dblclick', (e) => this.handleViewportDoubleClick(e));
        this.dom.stage.addEventListener('wheel', (e) => this.handleViewportWheel(e), { passive: false });
    },

    isViewerChromeEvent(e) {
        return Boolean(e.target?.closest?.('.rv-viewport-palette, .rv-lens, .rv-lens-settings'));
    },

    handleViewportDoubleClick(e) {
        if (this.isViewerChromeEvent(e)) return;
        if (this.state.mode === 'overlay' || this.state.mode === 'diff') return;
        e.preventDefault();
        this.resetViewport();
    },

    handleViewportWheel(e) {
        if (this.isViewerChromeEvent(e)) return;
        e.preventDefault();
        if (e.shiftKey) {
            this.panByPixels(-e.deltaX, -e.deltaY, e.clientX, e.clientY);
            return;
        }
        this.zoomAtPoint(e.clientX, e.clientY, e.deltaY < 0 ? 1.1 : 1 / 1.1);
    },

    startDeferredViewportGesture(e, start) {
        const origin = {
            pointerId: e.pointerId,
            pointerType: e.pointerType,
            button: e.button,
            altKey: e.altKey,
            shiftKey: e.shiftKey,
            clientX: start.clientX,
            clientY: start.clientY,
        };
        if (this.state.mode === 'blink') this.state.blinkPaused = true;
        if (this.shouldPanFromPointer(e)) {
            this.startPanFromPointer(origin);
            this.updatePanFromPointer(e);
            return;
        }
        if (this.state.mode === 'slider') {
            this.pointerInteraction.isDragging = true;
            this.captureStagePointer(e);
            this.updateSliderFromPointer(e);
        }
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

        this.dom.btnInfo.addEventListener('click', () => this.openInfoModal());
        this.dom.btnCloseInfo.addEventListener('click', () => this.closeInfoModal());
        this.dom.infoModal.addEventListener('click', (e) => {
            if (e.target === this.dom.infoModal) this.closeInfoModal();
        });
        this.dom.infoModal.addEventListener('keydown', (e) => this.handleInfoModalKey(e));
    },

    bindInspectorEvents() {
        this.inspector.bind();
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

    capturePointer(...args) {
        return this.viewport.capturePointer(...args);
    },

    releasePointer(...args) {
        return this.viewport.releasePointer(...args);
    },

    captureStagePointer(...args) {
        return this.viewport.captureStagePointer(...args);
    },

    trackPointerPosition(...args) {
        return this.viewport.trackPointerPosition(...args);
    },

    untrackPointer(...args) {
        return this.viewport.untrackPointer(...args);
    },

    trackedTouchPointers(...args) {
        return this.viewport.trackedTouchPointers(...args);
    },

    shouldStartPinch(...args) {
        return this.viewport.shouldStartPinch(...args);
    },

    pinchMetricsFromTrackedPointers(...args) {
        return this.viewport.pinchMetricsFromTrackedPointers(...args);
    },

    startPinchFromTrackedPointers(...args) {
        return this.viewport.startPinchFromTrackedPointers(...args);
    },

    updatePinchFromTrackedPointers(...args) {
        return this.viewport.updatePinchFromTrackedPointers(...args);
    },

    finishPinchInteraction(...args) {
        return this.viewport.finishPinchInteraction(...args);
    },

    updateSliderFromPointer(...args) {
        return this.viewport.updateSliderFromPointer(...args);
    },

    shouldPanFromPointer(...args) {
        return this.viewport.shouldPanFromPointer(...args);
    },

    startPanFromPointer(...args) {
        return this.viewport.startPanFromPointer(...args);
    },

    updatePanFromPointer(...args) {
        return this.viewport.updatePanFromPointer(...args);
    },

    stopPointerInteraction(...args) {
        return this.viewport.stopPointerInteraction(...args);
    },

    clipCount() {
        return this.state.data?.clips?.length || 0;
    },

    referenceClipIndex() {
        return this.clipIndexOrDefault(
            this.state.data?.default_selection?.left_clip_index,
            0,
        );
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
        const nextIndex = this.clipIndexOrDefault(idx, this.state.leftClipIdx);
        this.storeCurrentPairAlignment();
        this.state.leftClipIdx = nextIndex;
        this.ensureDistinctPairSelection();
        this.loadCurrentPairAlignment();
        if (this.state.mode === 'blink') this.keepBlinkActiveInPair();
        this.render();
    },

    setRightClip(idx) {
        const nextIndex = this.clipIndexOrDefault(idx, this.state.rightClipIdx);
        this.storeCurrentPairAlignment();
        this.state.rightClipIdx = nextIndex;
        this.ensureDistinctPairSelection();
        this.loadCurrentPairAlignment();
        if (this.state.mode === 'blink') {
            this.state.activeClipIdx = this.state.rightClipIdx;
        }
        if (this.state.mode === 'blink') this.keepBlinkActiveInPair();
        this.render();
    },

    swapPairClips() {
        if (this.state.mode === 'overlay' || this.state.mode === 'grid' || this.clipCount() <= 1) return;

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

        if (['slider', 'overlay', 'diff', 'blink', 'grid'].includes(saved.mode)) {
            this.state.mode = saved.mode;
        }
        if (['actual', 'width', 'height', 'custom'].includes(saved.fitMode)) {
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
        if (
            Number.isInteger(saved.currentFrameIdx) &&
            saved.currentFrameIdx >= 0 &&
            saved.currentFrameIdx < (this.state.data?.frames?.length || 0)
        ) {
            this.state.currentFrameIdx = saved.currentFrameIdx;
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
        this.normalizeCurrentFrameForFilter();
        if (this.state.mode === 'blink') this.keepBlinkActiveInPair();
    },

    persistViewportState() {
        const storage = this.localStorage();
        if (!this.state.storageKey || !storage) return false;
        this.storeCurrentPairAlignment();

        const payload = {
            currentFrameIdx: this.state.currentFrameIdx,
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
            return true;
        } catch {
            // localStorage can be unavailable for file:// reports in hardened browser modes.
            return false;
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
        return this.inspector.validTab(tab);
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
        this.dom.btnFilmstripToggle.setAttribute(
            'aria-expanded',
            hasThumbnails && !collapsed ? 'true' : 'false'
        );
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

    ensureReviewController() {
        if (this.reviewController) return this.reviewController;
        this.reviewController = ReviewState.createController(this);
        this.reviewController.bind();
        this.reviewController.render();
        return this.reviewController;
    },

    setInspectorOpen(open, options = {}) {
        this.inspector.setOpen(open, options);
    },

    isInspectorVisible() {
        return this.inspector.isVisible();
    },

    updateInspectorVisibility() {
        this.inspector.updateVisibility();
    },

    inspectorFocusableElements() {
        return this.inspector.focusableElements();
    },

    setInspectorFocusable(enabled) {
        this.inspector.setFocusable(enabled);
    },

    safeHttpUrl(url) {
        return this.inspector.safeHttpUrl(url);
    },

    updateInspectorSlowpics() {
        this.inspector.renderSlowpics();
    },

    setInspectorTab(tab, options = {}) {
        this.inspector.setTab(tab, options);
    },

    handleInspectorTabKey(e) {
        this.inspector.handleTabKey(e);
    },

    updateInspectorTabs() {
        this.inspector.updateTabs();
    },

    setText(element, text) {
        if (element) element.textContent = String(text ?? '');
    },

    currentFrame() {
        return this.state.data?.frames?.[this.state.currentFrameIdx] || null;
    },

    currentClipRole(index) {
        return this.inspector.currentClipRole(index);
    },

    stableClipRole(index) {
        return ViewerFormat.stableClipRole(index, this.referenceClipIndex());
    },

    modeLabel(mode = this.state.mode) {
        return ViewerFormat.modeLabel(mode);
    },

    formatFps(value) {
        return ViewerFormat.formatFps(value);
    },

    formatFileSize(value) {
        return ViewerFormat.formatFileSize(value);
    },

    signalCodeLabel(kind, value) {
        return ViewerFormat.signalCodeLabel(kind, value);
    },

    formatSignal(signal) {
        return ViewerFormat.formatSignal(signal);
    },

    formatPresentation(clip) {
        return ViewerFormat.formatPresentation(clip);
    },

    formatToneCurve(value) {
        return ViewerFormat.formatToneCurve(value);
    },

    formatActivePicture(active) {
        return ViewerFormat.formatActivePicture(active);
    },

    formatTonemapSummary() {
        return ViewerFormat.formatTonemapSummary(this.state.data?.rendering?.tonemap);
    },

    updateRenderingSummary() {
        if (typeof document?.querySelector !== 'function') return;
        const summary = document.querySelector('[data-rendering-tonemap-summary]');
        if (summary) this.setText(summary, this.formatTonemapSummary());
    },

    visibleSourceIndexes() {
        const indexes = [];
        if (this.state.mode === 'overlay') {
            indexes.push(this.state.activeClipIdx);
        } else if (this.state.mode === 'grid') {
            indexes.push(...(this.gridView?.indexes?.() || []));
        } else {
            indexes.push(this.state.leftClipIdx, this.state.rightClipIdx);
        }
        return indexes.filter((index, position) => (
            Number.isInteger(index)
            && index >= 0
            && index < this.clipCount()
            && indexes.indexOf(index) === position
        ));
    },

    currentPairLabel() {
        const left = this.clipDisplay(this.state.data.clips[this.state.leftClipIdx]);
        const right = this.clipDisplay(this.state.data.clips[this.state.rightClipIdx]);
        return `${left} vs ${right}`;
    },

    visibleFramePositionText() {
        const visibleIndexes = this.visibleFrameIndexes();
        const position = this.visibleFramePosition(visibleIndexes);
        if (position === -1) return `Not shown of ${visibleIndexes.length}`;
        return `${position + 1} of ${visibleIndexes.length} shown`;
    },

    updateInspectorData() {
        this.inspector.render();
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
            if (this.isAlignmentPopoverOpen()) {
                e.preventDefault();
                this.closeAlignmentPopover();
                return;
            }
            if (this.isInspectorVisible()) {
                e.preventDefault();
                this.setInspectorOpen(false);
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

        if (e.key === 'l' || e.key === 'L') {
            e.preventDefault();
            this.lens.setEnabled(!this.lens.state.report.enabled);
            return;
        }

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
            case '=': case '+': this.setZoom(this.state.zoom + 0.1); break;
            case '-': this.setZoom(this.state.zoom - 0.1); break;
            case 'r': case 'R': this.resetViewport(); break;

            default:
                if (e.key >= '1' && e.key <= '9') {
                    const idx = parseInt(e.key) - 1;
                    if (idx < this.state.data.clips.length) {
                         if (this.state.mode === 'slider') this.setLeftClip(idx);
                         else if (this.state.mode === 'diff' || this.state.mode === 'blink') this.setRightClip(idx);
                         else if (this.state.mode === 'overlay') {
                             this.state.activeClipIdx = idx;
                             this.render();
                         }
                    }
                }
        }
    },

    setMode(mode) {
        if (!this.validMode(mode)) return;
        const previousMode = this.state.mode;
        if (previousMode !== 'grid' && mode === 'grid') {
            const base = this.baseCanvasSize();
            this.state.panX = base.width > 0 ? this.state.panX / base.width : 0;
            this.state.panY = base.height > 0 ? this.state.panY / base.height : 0;
        }
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
            'rv-mode-grid',
        );
        this.dom.stage.classList.add(`rv-mode-${mode}`);
        this.gridView?.setActive(mode === 'grid');
        if (previousMode === 'grid' && mode !== 'grid') {
            const base = this.baseCanvasSize();
            this.state.panX = base.width > 0 ? this.state.panX * base.width : 0;
            this.state.panY = base.height > 0 ? this.state.panY * base.height : 0;
        }
        this.updateModeControls();
        this.updateBlinkControls();
        this.render();
    },

    startBlink() {
        this.state.blinkInterval = setInterval(() => {
            if (this.state.blinkPaused) return;

            this.state.activeClipIdx = this.state.activeClipIdx === this.state.leftClipIdx
                ? this.state.rightClipIdx
                : this.state.leftClipIdx;
            this.dom.activeSelect.value = String(this.state.activeClipIdx);
            this.updateInspectorData();
            this.updateImages();

        }, this.state.blinkIntervalMs);
        this.updateBlinkControls();
    },

    updateModeControls() {
        const mode = this.state.mode;
        const isOverlay = mode === 'overlay';
        const isGrid = mode === 'grid';
        this.dom.pairControls.hidden = isOverlay || isGrid;
        this.dom.activeControls.hidden = !isOverlay;
        this.dom.leftSelect.disabled = isOverlay || isGrid;
        this.dom.rightSelect.disabled = isOverlay || isGrid;
        this.dom.btnSwapClips.disabled = isOverlay || isGrid || this.clipCount() <= 1;
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
        if (this.state.mode === 'grid') return;
        if (this.state.mode === 'slider') {
            // Cycle left clip
            this.setLeftClip((this.state.leftClipIdx + direction + count) % count);
        } else if (this.state.mode === 'diff' || this.state.mode === 'blink') {
            // Cycle the comparison side of the explicit pair.
            this.setRightClip(
                this.nextDistinctClipIndex(this.state.rightClipIdx, this.state.leftClipIdx, direction)
            );
        } else {
            const nextIndex = (this.state.activeClipIdx + direction + count) % count;
            this.state.activeClipIdx = nextIndex;
            this.dom.activeSelect.value = this.state.activeClipIdx;
            this.render();
        }
    },

    setZoom(...args) {
        return this.viewport.setZoom(...args);
    },

    clampZoom(...args) {
        return this.viewport.clampZoom(...args);
    },

    applyZoom(...args) {
        return this.viewport.applyZoom(...args);
    },

    resetViewport(...args) {
        return this.viewport.resetViewport(...args);
    },

    zoomAtPoint(...args) {
        return this.viewport.zoomAtPoint(...args);
    },

    panByPixels(...args) {
        return this.viewport.panByPixels(...args);
    },

    setPan(...args) {
        return this.viewport.setPan(...args);
    },

    clampPan(...args) {
        return this.viewport.clampPan(...args);
    },

    applyPan(...args) {
        return this.viewport.applyPan(...args);
    },

    setFitMode(...args) {
        return this.viewport.setFitMode(...args);
    },

    updateFitButtons(...args) {
        return this.viewport.updateFitButtons(...args);
    },

    baseCanvasSize(...args) {
        return this.viewport.baseCanvasSize(...args);
    },

    sliderCanvasRect(...args) {
        return this.viewport.sliderCanvasRect(...args);
    },

    applyFitMode(...args) {
        return this.viewport.applyFitMode(...args);
    },

    applyAlignmentPresetOffsets(...args) {
        return this.viewport.applyAlignmentPresetOffsets(...args);
    },

    validAlignmentPreset(...args) {
        return this.viewport.validAlignmentPreset(...args);
    },

    currentPairAlignmentKey(...args) {
        return this.viewport.currentPairAlignmentKey(...args);
    },

    pairAlignmentKey(...args) {
        return this.viewport.pairAlignmentKey(...args);
    },

    isValidPairAlignmentKey(...args) {
        return this.viewport.isValidPairAlignmentKey(...args);
    },

    neutralAlignmentState(...args) {
        return this.viewport.neutralAlignmentState(...args);
    },

    presetAlignmentOffsets(...args) {
        return this.viewport.presetAlignmentOffsets(...args);
    },

    currentAlignmentState(...args) {
        return this.viewport.currentAlignmentState(...args);
    },

    normalizedAlignmentState(...args) {
        return this.viewport.normalizedAlignmentState(...args);
    },

    normalizedPairAlignments(...args) {
        return this.viewport.normalizedPairAlignments(...args);
    },

    applyAlignmentState(...args) {
        return this.viewport.applyAlignmentState(...args);
    },

    storeCurrentPairAlignment(...args) {
        return this.viewport.storeCurrentPairAlignment(...args);
    },

    loadCurrentPairAlignment(...args) {
        return this.viewport.loadCurrentPairAlignment(...args);
    },

    setAlignmentPreset(...args) {
        return this.viewport.setAlignmentPreset(...args);
    },

    setManualAlignment(...args) {
        return this.viewport.setManualAlignment(...args);
    },

    clearRawAlignmentInputs(...args) {
        return this.viewport.clearRawAlignmentInputs(...args);
    },

    rawAlignmentField(...args) {
        return this.viewport.rawAlignmentField(...args);
    },

    rawAlignmentElement(...args) {
        return this.viewport.rawAlignmentElement(...args);
    },

    setRawAlignmentInput(...args) {
        return this.viewport.setRawAlignmentInput(...args);
    },

    isValidAlignmentNumber(...args) {
        return this.viewport.isValidAlignmentNumber(...args);
    },

    commitRawAlignmentInput(...args) {
        return this.viewport.commitRawAlignmentInput(...args);
    },

    applyAlignment(...args) {
        return this.viewport.applyAlignment(...args);
    },

    formatSignedPixels(...args) {
        return this.viewport.formatSignedPixels(...args);
    },

    alignmentPresetLabel(...args) {
        return this.viewport.alignmentPresetLabel(...args);
    },

    alignmentStatusText(...args) {
        return this.viewport.alignmentStatusText(...args);
    },

    updateAlignmentStatus(...args) {
        return this.viewport.updateAlignmentStatus(...args);
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
        this.dom.btnFullscreen.setAttribute(
            'aria-label',
            isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'
        );
        this.dom.btnFullscreen.setAttribute(
            'title',
            isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'
        );
        this.dom.btnFullscreen.setAttribute('aria-pressed', isFullscreen ? 'true' : 'false');
    },

    updateSlider(...args) {
        return this.viewport.updateSlider(...args);
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

    clipOverlayLabel(clip, role = '') {
        const identity = ViewerFormat.sourceHudLabel(clip);
        return role ? `${role.toUpperCase()}: ${identity}` : identity;
    },

    sourceHudLabel(clip, profile = 'control') {
        return ViewerFormat.sourceHudLabel(clip, profile);
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
        return {
            left: `FIRST: ${leftClipLabel}`,
            right: `SECOND: ${rightClipLabel}`,
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
        this.dom.labelLeft.classList.toggle(
            'rv-overlay-label--active',
            isBlink && this.state.activeClipIdx === this.state.leftClipIdx,
        );
        this.dom.labelRight.classList.toggle(
            'rv-overlay-label--active',
            isBlink && this.state.activeClipIdx === this.state.rightClipIdx,
        );
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
        this.lens?.sync();
    },

    updateImages() {
        const frameData = this.state.data.frames[this.state.currentFrameIdx];
        if (!frameData) {
            this.showStageMessage('Selected frame data is unavailable.');
            this.showStatus('Selected frame data is unavailable.', 'error');
            this.clearFrameImages();
            return;
        }

        if (this.state.mode === 'grid') {
            this.hideStageMessage();
            this.clearStatus();
            this.gridView.render();
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
                const blinkLabels = this.blinkStageLabels(
                    this.clipOverlayLabel(leftClip),
                    this.clipOverlayLabel(rightClip),
                );
                leftLabelTxt = blinkLabels.left;
                rightLabelTxt = blinkLabels.right;
            } else if (this.state.mode === 'diff') {
                leftLabelTxt = this.clipOverlayLabel(leftClip, 'Base');
                rightLabelTxt = this.clipOverlayLabel(rightClip, 'Compare');
            } else {
                leftLabelTxt = this.clipOverlayLabel(leftClip, 'Left');
                rightLabelTxt = this.clipOverlayLabel(rightClip, 'Right');
            }
            leftAlt = `${this.clipAccessibleName(leftClip)} - Frame ${frameData.number}`;
            rightAlt = `${this.clipAccessibleName(rightClip)} - Frame ${frameData.number}`;

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

            leftLabelTxt = this.clipOverlayLabel(activeClip);
            rightLabelTxt = "";
            leftAlt = `${this.clipAccessibleName(activeClip)} - Frame ${frameData.number}`;
            rightAlt = `${this.clipAccessibleName(rightClip)} - Frame ${frameData.number}`;
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
        this.gridView?.clear();
        this.lens?.clearTransient?.();
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
        this.dom.leftSelect.title = this.clipAccessibleName(this.state.data.clips[this.state.leftClipIdx]);
        this.dom.rightSelect.title = this.clipAccessibleName(this.state.data.clips[this.state.rightClipIdx]);
        this.dom.activeSelect.title = this.clipAccessibleName(this.state.data.clips[this.state.activeClipIdx]);
        this.updateOverlayVisibility();
        this.updateFilmstripPanel();
        this.updatePaletteOrientation();
        this.updateBlinkControls();
        this.updateInspectorData();
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
        if (this.state.mode === 'grid') return indexes;
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
