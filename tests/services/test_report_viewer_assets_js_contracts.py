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
        "pixelLensEnabled: this.state.pixelLensEnabled",
        "blinkIntervalMs: this.state.blinkIntervalMs",
        "paletteOrientation: this.state.paletteOrientation",
        "pairAlignments: this.state.pairAlignments",
    ):
        assert persisted_field in persist_block
    assert "blinkPaused" not in persist_block
    assert "alignmentPreset: this.state.alignmentPreset" not in persist_block
    assert "alignX: this.state.alignX" not in persist_block
    assert "alignY: this.state.alignY" not in persist_block


def test_viewer_js_composes_focused_pixel_owner_before_viewer() -> None:
    js = get_js()

    assert js.index("const PixelInspector =") < js.index("const ReportViewer =")
    assert "this.pixelInspector = PixelInspector.create(this);" in js
    assert "this.pixelInspector.bind();" in js
    assert "pointFromImageRect(image, clientX, clientY)" in js
    assert "mapNormalizedPoint(point, targetWidth, targetHeight)" in js
    assert "anchorIndexForMode(mode, options)" in js
    assert "gestureExceeded(startX, startY, clientX, clientY)" in js
    assert "Math.hypot(clientX - startX, clientY - startY) > MAX_GESTURE_DISTANCE" in js
    assert "const MAX_GESTURE_DISTANCE = 6;" in js
    assert "canvas.width = 1;" in js
    assert "canvas.height = 1;" in js
    assert js.count("documentObject.createElement('canvas')") == 1
    assert "sampler ||= createSampler(document);" in js
    assert "context.getImageData(0, 0, 1, 1).data" in js
    assert "Pixel value unavailable" in js
    assert "querySelectorAll('img')" not in js


def test_viewer_js_uses_pixel_roving_tabs_shortcut_and_escape_priority() -> None:
    js = get_js()
    tabs = js_method_block(js, "handleInspectorTabKey(e)")
    update_tabs = js_method_block(js, "updateInspectorTabs()")
    handle_key = js_method_block(js, "handleKey(e)")
    viewport = js_method_block(js, "bindViewportEvents()")

    assert "['pixel', 'frame', 'clips', 'align', 'export']" in js
    assert "if (e.key === 'ArrowLeft')" in tabs
    assert "if (e.key === 'ArrowRight')" in tabs
    assert "if (e.key === 'Home')" in tabs
    assert "if (e.key === 'End')" in tabs
    assert "e.stopPropagation();" in tabs
    assert "tab.tabIndex = this.state.inspectorOpen && isActive ? 0 : -1;" in update_tabs
    assert "panel.tabIndex = this.state.inspectorOpen && isActive ? 0 : -1;" in update_tabs
    assert "if (e.key === 'm' || e.key === 'M')" in handle_key
    assert_in_order(
        handle_key,
        [
            "if (this.isAlignmentPopoverOpen()) {",
            "if (this.pixelInspector?.unlock()) {",
            "if (this.isInspectorVisible()) {",
            "if (document.fullscreenElement) {",
        ],
    )
    assert "this.pixelInspector.beginStagePress(e);" in viewport
    assert "this.pixelInspector.moveStagePress(e);" in viewport
    assert "this.pixelInspector.scheduleHover(e);" in viewport
    assert "this.pixelInspector.endStagePress(e)" in js


def test_viewer_js_keeps_pointer_zoom_and_alignment_hooks_behavioral() -> None:
    js = get_js()
    viewport_block = js_method_block(js, "bindViewportEvents()")
    commit_image_state_block = js_method_block(js, "commitImageState(imageState)")
    update_slider_block = js_method_block(js, "updateSliderFromPointer(e)")
    pinch_update_block = js_method_block(js, "updatePinchFromTrackedPointers()")
    start_pinch_block = js_method_block(js, "startPinchFromTrackedPointers()")
    finish_pinch_block = js_method_block(js, "finishPinchInteraction()")
    pan_pointer_block = js_method_block(js, "updatePanFromPointer(e)")

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
        "if (this.state.mode === 'overlay' || this.state.mode === 'diff') return;" in viewport_block
    )
    assert "this.zoomAtPoint(e.clientX, e.clientY, e.deltaY < 0 ? 1.1 : 1 / 1.1);" in viewport_block
    assert (
        "this.setPan(this.state.panX + dx, this.state.panY + dy, { save: false });"
        in pan_pointer_block
    )
    assert "this.pixelInspector.isStagePressPending(e.pointerId)" in pan_pointer_block
    assert "trackedTouchPointers()" in js
    assert "Math.hypot(dx, dy)" in js
    assert "this.state.fitMode = 'custom';" in start_pinch_block
    assert "this.dom.stage.classList.add('is-panning');" in start_pinch_block
    assert "this.clampZoom(" in pinch_update_block
    assert "this.applyZoom(nextZoom, { clampPan: false });" in pinch_update_block
    assert "this.persistViewportState();" in finish_pinch_block
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
    assert "this.dom.pairControls.hidden = isOverlay;" in mode_block
    assert "this.dom.activeControls.hidden = !isOverlay;" in mode_block
    assert "this.dom.leftSelect.disabled = isOverlay;" in mode_block
    assert "this.dom.activeSelect.disabled = !isOverlay;" in mode_block
    assert "this.dom.leftSelect.setAttribute('aria-label', 'Base clip');" in mode_block
    assert "this.dom.leftSelect.setAttribute('aria-label', 'First blink clip');" in mode_block


def test_viewer_js_keeps_empty_state_metadata_and_preload_contracts() -> None:
    js = get_js()
    render_empty_block = js_method_block(js, "renderEmptyState(message)")
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
