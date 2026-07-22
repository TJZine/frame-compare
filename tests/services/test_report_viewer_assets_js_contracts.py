"""JavaScript asset contracts for the report viewer."""

from __future__ import annotations

from frame_compare.services.report.viewer import get_js
from tests.services.report_viewer_contracts import assert_in_order, js_method_block


def test_viewer_js_preserves_modal_escape_and_focus_restore_contracts() -> None:
    js = get_js()
    help_key_block = js_method_block(js, "handleModalKey(e)")
    bind_help_block = js_method_block(js, "bindHelpEvents()")
    close_help_block = js_method_block(js, "closeHelpModal(options = {})")
    close_info_block = js_method_block(js, "closeInfoModal(options = {})")

    assert "helpRestoreFocus: null" in js
    assert "infoRestoreFocus: null" in js
    assert "this.state.helpRestoreFocus = activeElement" in js_method_block(js, "openHelpModal()")
    assert "this.state.infoRestoreFocus = activeElement" in js_method_block(js, "openInfoModal()")
    assert "if (shouldRestoreFocus) this.focusElement(restoreTarget);" in close_help_block
    assert "if (shouldRestoreFocus) this.focusElement(restoreTarget);" in close_info_block
    assert "document.exitFullscreen?.();" in js
    assert (
        "this.dom.modal.addEventListener('keydown', (e) => this.handleModalKey(e));"
        in bind_help_block
    )
    assert (
        "this.dom.infoModal.addEventListener('keydown', (e) => this.handleInfoModalKey(e));"
        in bind_help_block
    )

    assert "this.closeHelpModal();" in help_key_block
    assert "const focusable = this.modalFocusableElements();" in help_key_block
    assert "this.focusElement(last);" in help_key_block
    assert "this.focusElement(first);" in help_key_block


def test_viewer_js_closes_alignment_popover_before_global_escape_shortcuts() -> None:
    js = get_js()
    bind_interaction_block = js_method_block(js, "bindInteractionEvents()")
    alignment_block = js_method_block(js, "bindAlignmentEvents()")
    bind_keyboard_block = js_method_block(js, "bindKeyboardEvents()")
    handle_key_block = js_method_block(js, "handleKey(e)")

    assert "isAlignmentPopoverOpen()" in js
    assert "setAlignmentPopoverOpen(isOpen, options = {})" in js
    assert "this.closeAlignmentPopover({ restoreFocus: false });" in js
    assert "document.addEventListener('keydown', (e) => this.handleKey(e));" in bind_keyboard_block
    assert_in_order(
        bind_interaction_block,
        ["this.bindAlignmentEvents();", "this.bindKeyboardEvents();"],
    )
    assert_in_order(
        alignment_block,
        [
            "this.dom.alignPopover.addEventListener('keydown', (e) => {",
            "if (e.key === 'Escape') {",
            "e.preventDefault();",
            "e.stopPropagation();",
            "this.closeAlignmentPopover();",
        ],
    )
    assert_in_order(
        handle_key_block,
        [
            "if (this.isAlignmentPopoverOpen()) {",
            "this.closeAlignmentPopover();",
        ],
    )


def test_viewer_js_persists_report_scoped_viewport_state() -> None:
    js = get_js()
    storage_key_block = js_method_block(js, "viewportStorageKey()")
    restore_block = js_method_block(js, "restorePersistedState()")
    persist_block = js_method_block(js, "persistViewportState()")

    assert "frame-compare:report-viewer:${reportId}:viewport" in storage_key_block
    assert "this.state.data?.report_id || 'unknown-report'" in storage_key_block
    assert "JSON.parse(storage.getItem(this.state.storageKey) || '{}')" in restore_block
    assert "this.state.leftClipIdx = this.clipIndexOrDefault" in restore_block
    assert "this.state.rightClipIdx = this.clipIndexOrDefault" in restore_block
    assert "this.state.activeClipIdx = this.clipIndexOrDefault" in restore_block
    assert "this.state.overlaysHidden = saved.overlaysHidden;" in restore_block
    assert "this.state.filmstripCollapsed = saved.filmstripCollapsed;" in restore_block
    assert "this.state.inspectorOpen = saved.inspectorOpen;" in restore_block
    assert "this.state.inspectorTab = saved.inspectorTab;" in restore_block
    assert "this.state.blinkIntervalMs = saved.blinkIntervalMs;" in restore_block
    assert "this.state.paletteOrientation = saved.paletteOrientation;" in restore_block
    assert "this.state.currentFrameIdx = saved.currentFrameIdx;" in restore_block
    assert (
        "this.state.pairAlignments = this.normalizedPairAlignments(saved.pairAlignments);"
        in restore_block
    )
    assert "this.loadCurrentPairAlignment();" in restore_block
    assert "this.normalizeCurrentFrameForFilter();" in restore_block
    for persisted_field in (
        "currentFrameIdx: this.state.currentFrameIdx",
        "mode: this.state.mode",
        "panX: this.state.panX",
        "panY: this.state.panY",
        "overlaysHidden: this.state.overlaysHidden",
        "filmstripCollapsed: this.state.filmstripCollapsed",
        "filmstripSize: this.state.filmstripSize",
        "inspectorOpen: this.state.inspectorOpen",
        "inspectorTab: this.state.inspectorTab",
        "blinkIntervalMs: this.state.blinkIntervalMs",
        "paletteOrientation: this.state.paletteOrientation",
        "pairAlignments: this.state.pairAlignments",
    ):
        assert persisted_field in persist_block
    assert "blinkPaused" not in persist_block
    assert "alignmentPreset: this.state.alignmentPreset" not in persist_block
    assert "alignX: this.state.alignX" not in persist_block
    assert "alignY: this.state.alignY" not in persist_block


def test_viewer_js_composes_focused_lens_owner_before_viewer() -> None:
    js = get_js()

    assert_in_order(js, ["const Lens =", "const ReportViewer ="])
    assert "this.lens = Lens.create(this);" in js
    assert "this.lens.bind();" in js
    assert "frame-compare:lens-preferences:v2" in js
    assert "frame-compare:report-lens:v1:" in js
    assert "this.pixelInspector" not in js


def test_viewer_js_composes_focused_grid_owner_without_public_default_drift() -> None:
    js = get_js()
    update_images = js_method_block(js, "updateImages()")
    preload_indexes = js_method_block(js, "preloadClipIndexes()")
    set_mode = js_method_block(js, "setMode(mode)")
    valid_payload_mode = js_method_block(js, "validPayloadMode(mode)")
    pinch_update = js_method_block(js, "updatePinchFromTrackedPointers()")

    assert_in_order(js, ["const GridView =", "const ReportViewer ="])
    assert "this.gridView = GridView.create(this);" in js
    assert "this.gridView.bind();" in js
    assert "this.gridView?.setActive(mode === 'grid');" in set_mode
    assert "if (this.state.mode === 'grid')" in update_images
    assert "this.gridView.render();" in update_images
    assert "if (this.state.mode === 'grid') return indexes;" in preload_indexes
    assert "const DESKTOP_PAGE_SIZE = 4;" in js
    assert "const MOBILE_QUERY = '(max-width: 767px)';" in js
    assert "indexes().map(index => buildCell(index, generation))" in js
    assert "querySelectorAll('.rv-grid-image')" in js
    assert "viewer.state.panX * metrics.width" in js
    assert "viewer.state.panY * metrics.height" in js
    assert "this.gridView.panForZoomAnchor(" in pinch_update
    assert "this.state.panX / base.width" in set_mode
    assert "this.state.panX * base.width" in set_mode
    assert "const focusedClipIdx = clipIndexFromTarget(document.activeElement);" in js
    assert "if (index === viewer.referenceClipIndex()) roles.push('Reference');" in js
    assert "if (index === viewer.state.activeClipIdx) roles.push('Active');" in js
    assert "default_mode: 'grid'" not in js
    assert "'grid'" not in valid_payload_mode
    assert "this.validPayloadMode(this.state.data.default_mode)" in js


def test_viewer_js_uses_lens_shortcut_and_preserves_inspector_roving_tabs() -> None:
    js = get_js()
    tabs = js_method_block(js, "handleInspectorTabKey(e)")
    update_tabs = js_method_block(js, "updateInspectorTabs()")
    handle_key = js_method_block(js, "handleKey(e)")
    viewport = js_method_block(js, "bindViewportEvents()")

    assert "['frame', 'clips', 'align', 'review', 'export']" in js
    assert "if (e.key === 'ArrowLeft')" in tabs
    assert "if (e.key === 'ArrowRight')" in tabs
    assert "if (e.key === 'Home')" in tabs
    assert "if (e.key === 'End')" in tabs
    assert "e.stopPropagation();" in tabs
    assert "tab.tabIndex = this.state.inspectorOpen && isActive ? 0 : -1;" in update_tabs
    assert "panel.tabIndex = this.state.inspectorOpen && isActive ? 0 : -1;" in update_tabs
    assert "if (e.key === 'l' || e.key === 'L')" in handle_key
    assert "if (e.key === 'm' || e.key === 'M')" not in handle_key
    assert_in_order(
        handle_key,
        [
            "if (this.isAlignmentPopoverOpen()) {",
            "if (this.isInspectorVisible()) {",
            "if (document.fullscreenElement) {",
        ],
    )
    assert "this.lens.handleStagePointerDown(e);" in viewport
    assert "this.lens.handleStagePointerMove(e);" in viewport
    assert "this.lens.endStagePointer(e" in js


def test_viewer_js_isolates_lens_chrome_and_arbitrates_touch_gestures() -> None:
    js = get_js()
    viewport = js_method_block(js, "bindViewportEvents()")
    guard = js_method_block(js, "isViewerChromeEvent(e)")
    wheel = js_method_block(js, "handleViewportWheel(e)")
    double_click = js_method_block(js, "handleViewportDoubleClick(e)")
    deferred = js_method_block(js, "startDeferredViewportGesture(e, start)")
    stop = js_method_block(js, "stopPointerInteraction(e, options = {})")

    assert ".rv-viewport-palette, .rv-lens, .rv-lens-settings" in guard
    assert viewport.count("if (this.isViewerChromeEvent(e)) return;") == 2
    assert "if (this.isViewerChromeEvent(e)) return;" in wheel
    assert "if (this.isViewerChromeEvent(e)) return;" in double_click
    assert "lensTouchStart" in viewport
    assert "lensMove === 'pending'" in viewport
    assert "lensMove === 'released'" in viewport
    assert "this.lens.cancelTouchPending();" in viewport
    assert "this.startDeferredViewportGesture(e, pointer.lensTouchStart);" in viewport
    assert "this.startPanFromPointer(origin);" in deferred
    assert "this.updateSliderFromPointer(e);" in deferred
    assert "this.lens.endStagePointer(e" in stop
    assert "if (wasLensTapPending)" in stop


def test_viewer_js_composes_focused_review_owner_before_viewer() -> None:
    js = get_js()
    assert_in_order(js, ["const ReviewState =", "const ReportViewer ="])
    assert "const MAX_BYTES_LABEL = MAX_BYTES.toLocaleString('en-US');" in js
    assert "const MAX_RECORDS_LABEL = MAX_RECORDS.toLocaleString('en-US');" in js
    for limit_message in (
        "`Review JSON exceeds ${MAX_BYTES_LABEL} bytes.`",
        "`Stored review JSON exceeds ${MAX_BYTES_LABEL} bytes.`",
        "`Review record limit of ${MAX_RECORDS_LABEL} reached.`",
        "`Import exceeds ${MAX_BYTES_LABEL} bytes.`",
        "`Import exceeds ${MAX_BYTES_LABEL} bytes. No changes were made.`",
    ):
        assert limit_message in js
    assert "frame-compare:report-review:v1:${context.reportId}" in js
    assert "this.reviewController = null;" in js
    assert "ensureReviewController()" in js
    assert "this.reviewController = ReviewState.createController(this);" in js
    assert "this.reviewController.bind();" in js
    assert "this.reviewController?.render();" in js
    assert "const model = create({" in js
    assert "model.parseImport(bytes)" in js
    assert "model.apply(importPreview)" in js
    assert "token !== importToken" in js
    assert "importToken += 1;" in js
    assert "resetImportChoices();" in js
    assert "viewer.announce?.(message);" in js
    assert "viewer-live" in js
    assert "messageWithPersistence(message)" in js
    assert "renderedFrameOrdinal === viewer.state.currentFrameIdx" in js
    assert "updateImportPreview();" in js
    assert "window.setTimeout(() => URL.revokeObjectURL(url), 0);" in js
    assert "bindReviewEvents" not in js
    assert "reviewImportToken" not in js


def test_viewer_js_keeps_pointer_zoom_and_alignment_hooks_behavioral() -> None:
    js = get_js()
    viewport_block = js_method_block(js, "bindViewportEvents()")
    commit_image_state_block = js_method_block(js, "commitImageState(imageState)")
    apply_image_state_block = js_method_block(js, "applyImageState(imageState)")
    update_slider_block = js_method_block(js, "updateSliderFromPointer(e)")
    pinch_update_block = js_method_block(js, "updatePinchFromTrackedPointers()")
    start_pinch_block = js_method_block(js, "startPinchFromTrackedPointers()")
    finish_pinch_block = js_method_block(js, "finishPinchInteraction()")
    pan_pointer_block = js_method_block(js, "updatePanFromPointer(e)")
    wheel_block = js_method_block(js, "handleViewportWheel(e)")
    double_click_block = js_method_block(js, "handleViewportDoubleClick(e)")
    apply_zoom_block = js_method_block(js, "applyZoom(level, options = {})")
    apply_pan_block = js_method_block(js, "applyPan()")
    apply_alignment_block = js_method_block(js, "applyAlignment()")

    assert "panX: 0" in js
    assert "panY: 0" in js
    assert "pointerPositions: new Map()" in js
    assert "capturedPointerIds: new Set()" in js
    assert "pinchStartDistance: 0" in js
    assert "rawAlignX: null" in js
    assert "rawAlignY: null" in js
    assert "alignmentPreset: 'none'" in js
    assert "this.dom.stage.addEventListener('wheel'" in viewport_block
    assert "this.dom.stage.addEventListener('dblclick'" in viewport_block
    assert "this.dom.stage.addEventListener('pointerdown'" in viewport_block
    assert "this.dom.stage.addEventListener('pointermove'" in viewport_block
    assert "this.dom.stage.addEventListener('pointercancel'" in viewport_block
    assert "document.addEventListener('fullscreenchange', () => {" in viewport_block
    assert "window.addEventListener('resize', () => this.applyFitMode())" in viewport_block
    assert "addEventListener('load', () => this.applyFitMode())" in viewport_block
    assert (
        "if (this.state.mode === 'overlay' || this.state.mode === 'diff') return;"
        in double_click_block
    )
    assert "this.zoomAtPoint(e.clientX, e.clientY, e.deltaY < 0 ? 1.1 : 1 / 1.1);" in wheel_block
    assert "this.panByPixels(dx, dy, e.clientX, e.clientY" in pan_pointer_block
    assert "basis: pointer.panBasis" in pan_pointer_block
    assert "pixelInspector" not in pan_pointer_block
    assert "trackedTouchPointers()" in js
    assert "Math.hypot(dx, dy)" in js
    assert "this.state.fitMode = 'custom';" in start_pinch_block
    assert "this.dom.stage.classList.add('is-panning');" in start_pinch_block
    assert "this.clampZoom(" in pinch_update_block
    assert "this.applyZoom(nextZoom, { clampPan: false });" in pinch_update_block
    assert "this.persistViewportState();" in finish_pinch_block
    assert "this.lens?.refresh();" in apply_zoom_block
    assert "this.lens?.refresh();" in apply_pan_block
    assert "this.lens?.refresh();" in apply_alignment_block
    assert "this.lens?.sync();" in apply_image_state_block
    assert "const rect = this.sliderCanvasRect();" in update_slider_block
    assert (
        "const clampedClientX = Math.max(rect.left, Math.min(rect.right, e.clientX));"
        in update_slider_block
    )
    assert "setAlignmentPreset(preset)" in js
    assert "setManualAlignment(x, y)" in js
    assert "setRawAlignmentInput('x', e.target.value);" in js
    assert "setRawAlignmentInput('y', e.target.value);" in js
    assert "commitRawAlignmentInput('x')" in js
    assert "commitRawAlignmentInput('y')" in js
    assert "Promise.all([" in commit_image_state_block
    assert "this.ensureImageReady(imageState.leftSrc)" in commit_image_state_block
    assert "this.ensureImageReady(imageState.rightSrc)" in commit_image_state_block
    assert "window.requestAnimationFrame(() => commit());" in commit_image_state_block


def test_viewer_js_keeps_overlay_blink_filtering_and_navigation_contracts() -> None:
    js = get_js()
    default_selection_block = js_method_block(js, "applyDefaultSelection()")
    filter_block = js_method_block(js, "setFrameFilter(categoryKey)")
    normalize_filter_block = js_method_block(js, "normalizeCurrentFrameForFilter()")
    mode_block = js_method_block(js, "updateModeControls()")
    render_block = js_method_block(js, "render()")

    assert "const selection = this.state.data.default_selection || {};" in default_selection_block
    assert "this.state.leftClipIdx = left;" in default_selection_block
    assert "this.state.rightClipIdx = right;" in default_selection_block
    assert "this.state.activeClipIdx = left;" in default_selection_block
    assert "ensureDistinctPairSelection(mode = this.state.mode)" in js
    assert "nextDistinctClipIndex(startIdx, excludedIdx, direction = 1)" in js
    assert "this.state.rightClipIdx = this.nextDistinctClipIndex(" in js
    assert "const ALL_CATEGORY_FILTER_KEY = '__fc_all__';" in js
    assert "activeCategoryKey: ALL_CATEGORY_FILTER_KEY" in js
    assert "buildCategoryFilterKeys()" in js
    assert "keys.set(category, `cat-${keys.size}`);" in js
    assert "visibleFrameIndexes()" in js
    assert "nearestVisibleFrameIndex(targetIdx" in js
    assert "this.normalizeCurrentFrameForFilter();" in filter_block
    assert "this.render();" in filter_block
    assert (
        "this.scrollActiveFilmstripItem({ behavior: 'smooth', inline: 'center' });" in filter_block
    )
    assert (
        "const nextIdx = this.nearestVisibleFrameIndex(this.state.currentFrameIdx);"
        in normalize_filter_block
    )
    assert "this.updateFrameNavigationControls();" in render_block
    assert "this.updateFrameOptionVisibility();" in render_block
    assert "this.updateFilterChips();" in render_block
    assert "this.updateInspectorData();" in render_block
    assert "this.scrollActiveFilmstripItem();" in render_block
    assert "this.setFrame(visibleIndexes[position + 1]);" in js
    assert "this.setFrame(visibleIndexes[position - 1]);" in js
    assert "this.dom.pairControls.hidden = isOverlay || isGrid;" in mode_block
    assert "this.dom.activeControls.hidden = !isOverlay;" in mode_block
    assert "this.dom.leftSelect.disabled = isOverlay || isGrid;" in mode_block
    assert "this.dom.activeSelect.disabled = !isOverlay;" in mode_block
    assert "this.dom.leftSelect.setAttribute('aria-label', 'Base clip');" in mode_block
    assert "this.dom.leftSelect.setAttribute('aria-label', 'First blink clip');" in mode_block


def test_viewer_js_keeps_empty_state_metadata_and_preload_contracts() -> None:
    js = get_js()
    render_empty_block = js_method_block(js, "renderEmptyState(message)")
    clear_frame_block = js_method_block(js, "clearFrameImages()")
    disable_controls_block = js_method_block(js, "disableViewerControls(disabled)")
    update_metadata_block = js_method_block(js, "updateCurrentFrameMetadata(frameData)")
    preload_block = js_method_block(js, "preloadImages()")
    preload_image_block = js_method_block(js, "preloadImage(src)")
    preload_frame_indexes_block = js_method_block(js, "preloadFrameIndexes()")
    preload_clip_indexes_block = js_method_block(js, "preloadClipIndexes()")

    assert "showStatus(message, tone = 'info')" in js
    assert "this.showStatus(message, 'warning');" in render_empty_block
    assert "this.disableViewerControls(true);" in render_empty_block
    assert "this.showStageMessage(message);" in render_empty_block
    assert "this.clearFrameImages();" in render_empty_block
    assert "this.lens?.clearTransient?.();" in clear_frame_block
    assert "if (control === this.dom.btnHelp) return;" in disable_controls_block
    assert "hasRenderableData()" in js
    assert "this.dom.currentFrameCategoryDivider.hidden = !showCategory;" in update_metadata_block
    assert "normalizedDisplayToken(value)" in js
    assert "Selected frame image data is unavailable." in js
    assert "imageLoadPromises: new Map()" in js
    assert "preloadFrameIndexes()" in js
    assert "preloadClipIndexes()" in js
    assert "const images = Array.isArray(frame.images) ? frame.images : [];" in preload_block
    assert "const src = images[clipIdx]?.src;" in preload_block
    assert "this.preloadImage(src);" in preload_block
    assert (
        "if (position > 0) indexes.push(visibleIndexes[position - 1]);"
        in preload_frame_indexes_block
    )
    assert (
        "if (position < visibleIndexes.length - 1) indexes.push(visibleIndexes[position + 1]);"
        in preload_frame_indexes_block
    )
    assert "indexes.add(this.state.activeClipIdx);" in preload_clip_indexes_block
    assert "indexes.add(this.state.leftClipIdx);" in preload_clip_indexes_block
    assert "indexes.add(this.state.rightClipIdx);" in preload_clip_indexes_block
    assert "void this.ensureImageReady(src);" in preload_image_block
