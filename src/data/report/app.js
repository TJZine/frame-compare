(function () {
  const DATA_URL = "data.json";

  const root = document.querySelector("[data-report-root]");
  if (!root) {
    return;
  }

  const frameSelect = document.getElementById("frame-select");
  const leftSelect = document.getElementById("left-select");
  const rightSelect = document.getElementById("right-select");
  const sliderControl = document.getElementById("slider-control");
  const modeSelect = document.getElementById("mode-select");
  const zoomControl = document.getElementById("zoom-control");
  const zoomOutButton = document.getElementById("zoom-out");
  const zoomInButton = document.getElementById("zoom-in");
  const zoomResetButton = document.getElementById("zoom-reset");
  const zoomReadout = document.getElementById("zoom-readout");
  const fitButtons = Array.from(document.querySelectorAll("[data-fit]"));
  const alignmentSelect = document.getElementById("alignment-select");
  const leftControl = document.getElementById("left-control");
  const rightControl = document.getElementById("right-control");
  const leftLabel = document.getElementById("left-label");
  const rightLabel = document.getElementById("right-label");
  const viewerStage = document.getElementById("viewer-stage");
  const canvas = document.getElementById("viewer-canvas");
  const overlay = document.getElementById("overlay");
  const divider = document.getElementById("divider");
  const leftImage = document.getElementById("left-image");
  const rightImage = document.getElementById("right-image");
  const frameLabel = document.getElementById("frame-label");
  const frameList = document.getElementById("frame-list");
  const filterContainer = document.getElementById("category-filter");
  const encodeInfo = document.getElementById("encode-info");
  const frameMetadata = document.getElementById("frame-metadata");
  const subtitle = document.getElementById("report-subtitle");
  const footer = document.getElementById("report-footer");
  const linkContainer = document.getElementById("report-links");
  const sliderGroup = document.querySelector(".rc-slider-control");
  const viewerHelp = document.getElementById("viewer-help");
  const fullscreenButton = document.getElementById("fullscreen-toggle");

  const STORAGE_KEY = "frameCompareReportViewer.v3";
  const ZOOM_MIN = 25;
  const ZOOM_MAX = 400;
  const ZOOM_STEP = 10;
  const CUSTOM_ALIGNMENT = "custom";
  const BLINK_INTERVAL_MS = 700;
  const VIEWER_MODES = new Set(["slider", "overlay", "difference", "blink"]);

  const state = {
    data: null,
    framesByIndex: new Map(),
    sortedFrameIndexes: [],
    allFrameIndexes: [],
    currentFrame: null,
    leftEncode: null,
    rightEncode: null,
    mode: "slider",
    zoom: 100,
    fitPreset: "fit-width",
    alignment: "center",
    prevAlignment: "center",
    overlayEncode: null,
    overlayIndex: -1,
    overlayOrder: [],
    pan: { x: 0, y: 0 },
    imageSize: null,
    pointer: null,
    panActive: false,
    panPointerId: null,
    panStart: null,
    panModifier: false,
    panAvailable: false,
    panHasMoved: false,
    categories: [],
    activeCategories: new Set(),
    blinkTimerId: null,
    blinkVisible: true,
    blinkPaused: false,
    fullscreenActive: false,
    fullscreenReturnFocus: null,
  };

  function clampZoom(value) {
    const numeric = Number(value) || 100;
    return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, numeric));
  }

  function loadPreferences() {
    try {
      const raw = window.localStorage ? window.localStorage.getItem(STORAGE_KEY) : null;
      if (!raw) {
        return {};
      }
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        return parsed;
      }
    } catch (error) {
      console.warn("Unable to load report viewer preferences", error);
    }
    return {};
  }

  function savePreferences() {
    try {
      if (!window.localStorage) {
        return;
      }
      const payload = {
        zoom: state.zoom,
        fitPreset: state.fitPreset,
        alignment: state.alignment === CUSTOM_ALIGNMENT ? (state.prevAlignment || "center") : state.alignment,
        mode: state.mode,
        overlayEncode: state.overlayEncode,
        activeCategories: Array.from(state.activeCategories),
        currentFrame: state.currentFrame,
      };
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch (error) {
      // Ignore storage errors (private mode, etc.).
    }
  }

  function stopBlink() {
    if (state.blinkTimerId !== null) {
      window.clearInterval(state.blinkTimerId);
      state.blinkTimerId = null;
    }
    state.blinkPaused = false;
    state.blinkVisible = true;
  }

  function startBlink() {
    stopBlink();
    state.blinkVisible = true;
    state.blinkPaused = false;
    applyBlinkVisibility();
    state.blinkTimerId = window.setInterval(() => {
      if (state.blinkPaused) {
        return;
      }
      state.blinkVisible = !state.blinkVisible;
      applyBlinkVisibility();
    }, BLINK_INTERVAL_MS);
  }

  function pauseBlink(setVisibleLeft = false) {
    state.blinkPaused = true;
    if (setVisibleLeft) {
      state.blinkVisible = true;
      applyBlinkVisibility();
    }
  }

  function resumeBlink() {
    const wasPaused = state.blinkPaused;
    state.blinkPaused = false;
    if (wasPaused) {
      applyBlinkVisibility();
    }
  }

  function applyBlinkVisibility() {
    if (state.mode !== "blink" || !overlay || !rightImage) {
      return;
    }
    const showLeft = state.blinkVisible;
    overlay.style.visibility = showLeft ? "visible" : "hidden";
    rightImage.style.visibility = showLeft ? "hidden" : "visible";
  }

  function getFullscreenElement() {
    if (typeof document === "undefined") {
      return null;
    }
    return (
      document.fullscreenElement ||
      document.webkitFullscreenElement ||
      document.mozFullScreenElement ||
      document.msFullscreenElement ||
      null
    );
  }

  function isFullscreenSupported() {
    if (!viewerStage || typeof document === "undefined") {
      return false;
    }
    return Boolean(
      document.fullscreenEnabled ||
        document.webkitFullscreenEnabled ||
        document.mozFullScreenEnabled ||
        document.msFullscreenEnabled ||
        viewerStage.requestFullscreen ||
        viewerStage.webkitRequestFullscreen ||
        viewerStage.mozRequestFullScreen ||
        viewerStage.msRequestFullscreen
    );
  }

  function isFullscreenActive() {
    return Boolean(getFullscreenElement());
  }

  function syncFullscreenState() {
    const active = isFullscreenActive();
    state.fullscreenActive = active;
    if (fullscreenButton) {
      fullscreenButton.setAttribute("aria-pressed", active ? "true" : "false");
      fullscreenButton.title = active ? "Exit fullscreen (F)" : "Toggle fullscreen (F)";
    }
    if (document.body) {
      document.body.classList.toggle("rc-fullscreen-active", active);
    }
    if (active) {
      if (viewerStage && typeof viewerStage.focus === "function") {
        viewerStage.focus({ preventScroll: true });
      }
    } else {
      const returnFocus = state.fullscreenReturnFocus;
      state.fullscreenReturnFocus = null;
      if (returnFocus && typeof returnFocus.focus === "function") {
        try {
          returnFocus.focus({ preventScroll: true });
        } catch (error) {
          // Swallow focus errors.
        }
      } else if (fullscreenButton && typeof fullscreenButton.focus === "function") {
        fullscreenButton.focus({ preventScroll: true });
      }
    }
    applyBlinkVisibility();
    window.requestAnimationFrame(() => {
      applyTransform();
      if (state.imageSize) {
        updatePanAvailability(
          state.imageSize.width * currentScale(),
          state.imageSize.height * currentScale(),
          getStageSize(),
        );
      } else {
        updatePanAvailability(0, 0, getStageSize());
      }
    });
  }

  function enterFullscreen() {
    if (!viewerStage || !isFullscreenSupported()) {
      return;
    }
    const focusTarget = document.activeElement;
    if (focusTarget && focusTarget instanceof HTMLElement) {
      state.fullscreenReturnFocus = focusTarget;
    } else {
      state.fullscreenReturnFocus = fullscreenButton instanceof HTMLElement ? fullscreenButton : null;
    }
    const request =
      viewerStage.requestFullscreen?.bind(viewerStage) ||
      viewerStage.webkitRequestFullscreen?.bind(viewerStage) ||
      viewerStage.mozRequestFullScreen?.bind(viewerStage) ||
      viewerStage.msRequestFullscreen?.bind(viewerStage);
    if (!request) {
      syncFullscreenState();
      return;
    }
    try {
      const result = request();
      if (result && typeof result.then === "function") {
        result.catch(() => {
          syncFullscreenState();
        });
      }
    } catch (error) {
      syncFullscreenState();
    }
  }

  function exitFullscreen() {
    if (typeof document === "undefined") {
      return;
    }
    if (!state.fullscreenReturnFocus && fullscreenButton instanceof HTMLElement) {
      state.fullscreenReturnFocus = fullscreenButton;
    }
    const exit =
      document.exitFullscreen?.bind(document) ||
      document.webkitExitFullscreen?.bind(document) ||
      document.mozCancelFullScreen?.bind(document) ||
      document.msExitFullscreen?.bind(document);
    if (!exit) {
      syncFullscreenState();
      return;
    }
    try {
      const result = exit();
      if (result && typeof result.then === "function") {
        result.catch(() => {
          syncFullscreenState();
        });
      }
    } catch (error) {
      syncFullscreenState();
    }
  }

  function toggleFullscreen() {
    if (!isFullscreenSupported()) {
      return;
    }
    if (isFullscreenActive()) {
      exitFullscreen();
    } else {
      enterFullscreen();
    }
  }

  function handleFullscreenChange() {
    syncFullscreenState();
  }

  const fullscreenEvents = [
    "fullscreenchange",
    "webkitfullscreenchange",
    "mozfullscreenchange",
    "MSFullscreenChange",
  ];
  fullscreenEvents.forEach((eventName) => {
    document.addEventListener(eventName, handleFullscreenChange, false);
  });

  const preferences = loadPreferences();
  const storedMode = typeof preferences.mode === "string" && VIEWER_MODES.has(preferences.mode)
    ? preferences.mode
    : null;
  const hasModePreference = Boolean(storedMode);
  const storedCategoryKeys = Array.isArray(preferences.activeCategories)
    ? preferences.activeCategories.filter((value) => typeof value === "string" && value.length > 0)
    : [];
  const hasCategoryPreference = storedCategoryKeys.length > 0;
  const storedOverlayEncode =
    typeof preferences.overlayEncode === "string" && preferences.overlayEncode.length > 0
      ? preferences.overlayEncode
      : null;
  const hasOverlayPreference = Boolean(storedOverlayEncode);
  const storedFrameIndex =
    typeof preferences.currentFrame === "number" && Number.isFinite(preferences.currentFrame)
      ? preferences.currentFrame
      : null;
  if (preferences.zoom) {
    state.zoom = clampZoom(preferences.zoom);
  }
  if (typeof preferences.fitPreset === "string") {
    state.fitPreset = preferences.fitPreset;
  }
  if (typeof preferences.alignment === "string") {
    const storedAlignment = preferences.alignment === CUSTOM_ALIGNMENT ? "center" : preferences.alignment;
    state.alignment = storedAlignment;
    if (state.alignment !== CUSTOM_ALIGNMENT) {
      state.prevAlignment = state.alignment;
    }
  }
  if (storedMode) {
    state.mode = storedMode;
  }

  function showError(message) {
    root.innerHTML = "";
    const error = document.createElement("p");
    error.className = "rc-error";
    error.textContent = message;
    root.appendChild(error);
  }

  function setSlider(value) {
    const percent = Math.min(100, Math.max(0, Number(value) || 0));
    sliderControl.value = String(percent);
    if (state.mode === "overlay" || state.mode === "difference" || state.mode === "blink") {
      overlay.style.clipPath = "inset(0 0 0 0)";
      divider.style.visibility = "hidden";
      divider.style.display = "none";
      return;
    }
    const clipRight = 100 - percent;
    overlay.style.clipPath = `inset(0 ${clipRight}% 0 0)`;
    divider.style.left = `${percent}%`;
    divider.style.visibility = "visible";
    divider.style.display = "";
  }

  function currentScale() {
    return Number.isFinite(state.zoom) ? state.zoom / 100 : 1;
  }

  function getStageSize() {
    if (!viewerStage) {
      return { width: 0, height: 0 };
    }
    return {
      width: viewerStage.clientWidth || viewerStage.offsetWidth || 0,
      height: viewerStage.clientHeight || viewerStage.offsetHeight || 0,
    };
  }

  function computeFitScale(preset) {
    if (!state.imageSize) {
      return 1;
    }
    const stage = getStageSize();
    if (!stage.width || !stage.height) {
      return 1;
    }
    const widthScale = stage.width / state.imageSize.width;
    const heightScale = stage.height / state.imageSize.height;
    switch (preset) {
      case "actual":
        return 1;
      case "fit-height":
        return heightScale;
      case "fill":
        return Math.max(widthScale, heightScale);
      case "fit-width":
      default:
        return widthScale;
    }
  }

  function computeAlignmentOffset(stage, content) {
    const gapX = stage.width - content.width;
    const gapY = stage.height - content.height;
    const alignment = state.alignment || "center";
    let offsetX = 0;
    let offsetY = 0;
    switch (alignment) {
      case CUSTOM_ALIGNMENT:
        return { x: 0, y: 0 };
      case "top-left":
        offsetX = 0;
        offsetY = 0;
        break;
      case "top-right":
        offsetX = gapX;
        offsetY = 0;
        break;
      case "bottom-left":
        offsetX = 0;
        offsetY = gapY;
        break;
      case "bottom-right":
        offsetX = gapX;
        offsetY = gapY;
        break;
      case "center":
      default:
        offsetX = gapX / 2;
        offsetY = gapY / 2;
        break;
    }
    return { x: offsetX, y: offsetY };
  }

  function updatePanAvailability(contentWidth, contentHeight, stage) {
    if (!viewerStage) {
      return;
    }
    const canPanFromScale = contentWidth > stage.width + 1 || contentHeight > stage.height + 1;
    const available = canPanFromScale || state.panModifier;
    state.panAvailable = available;
    viewerStage.classList.toggle("rc-pan-available", available);
    viewerStage.dataset.pan = available ? "enabled" : "disabled";
    if (viewerHelp) {
      viewerHelp.hidden = false;
    }
  }

  function applyTransform() {
    if (!canvas) {
      return;
    }
    const scale = currentScale();
    if (!state.imageSize) {
      canvas.style.transform = `scale(${scale})`;
      viewerStage.classList.remove("rc-pan-available");
      viewerStage.dataset.pan = "disabled";
      return;
    }

    const stage = getStageSize();
    const contentWidth = state.imageSize.width * scale;
    const contentHeight = state.imageSize.height * scale;
    const baseOffset = computeAlignmentOffset(stage, { width: contentWidth, height: contentHeight });

    let translationX = baseOffset.x + state.pan.x;
    let translationY = baseOffset.y + state.pan.y;

    const minX = Math.min(0, stage.width - contentWidth);
    const maxX = Math.max(0, stage.width - contentWidth);
    if (translationX < minX) {
      state.pan.x += minX - translationX;
      translationX = minX;
    } else if (translationX > maxX) {
      state.pan.x += maxX - translationX;
      translationX = maxX;
    }

    const minY = Math.min(0, stage.height - contentHeight);
    const maxY = Math.max(0, stage.height - contentHeight);
    if (translationY < minY) {
      state.pan.y += minY - translationY;
      translationY = minY;
    } else if (translationY > maxY) {
      state.pan.y += maxY - translationY;
      translationY = maxY;
    }

    canvas.style.transform = `translate(${translationX}px, ${translationY}px) scale(${scale})`;
    updatePanAvailability(contentWidth, contentHeight, stage);
  }

  function updateZoomUI() {
    const rounded = Math.round(state.zoom);
    if (zoomControl) {
      zoomControl.value = String(rounded);
    }
    if (zoomReadout) {
      zoomReadout.textContent = `${rounded}%`;
    }
  }

  function updateFitButtons() {
    fitButtons.forEach((button) => {
      const preset = button.dataset.fit;
      const pressed = preset && preset === state.fitPreset;
      button.setAttribute("aria-pressed", pressed ? "true" : "false");
    });
  }

  function updateAlignmentSelect() {
    if (!alignmentSelect) {
      return;
    }
    let customOption = alignmentSelect.querySelector(`option[value="${CUSTOM_ALIGNMENT}"]`);
    if (state.alignment === CUSTOM_ALIGNMENT) {
      if (!customOption) {
        customOption = document.createElement("option");
        customOption.value = CUSTOM_ALIGNMENT;
        customOption.textContent = "Custom (manual)";
        customOption.dataset.dynamic = "true";
        alignmentSelect.appendChild(customOption);
      }
      alignmentSelect.value = CUSTOM_ALIGNMENT;
    } else {
      if (customOption && customOption.dataset.dynamic === "true") {
        customOption.remove();
      }
      if (Array.from(alignmentSelect.options).some((option) => option.value === state.alignment)) {
        alignmentSelect.value = state.alignment;
      } else if (alignmentSelect.options.length > 0) {
        alignmentSelect.value = alignmentSelect.options[0].value;
      }
    }
  }

  function updateEncodeControlsForMode() {
    if (!leftControl || !rightControl || !leftLabel) {
      return;
    }
    const sliderLabel = leftLabel.dataset.sliderLabel || "Left encode";
    const overlayLabel = leftLabel.dataset.overlayLabel || "Displayed encode";
    if (state.mode === "overlay") {
      leftControl.style.display = "";
      leftLabel.textContent = overlayLabel;
      rightControl.style.display = "none";
    } else {
      leftControl.style.display = "";
      leftLabel.textContent = sliderLabel;
      rightControl.style.display = "";
    }
    if (leftSelect) {
      if (state.mode === "overlay") {
        if (state.overlayEncode && leftSelect.value !== state.overlayEncode) {
          leftSelect.value = state.overlayEncode;
        }
      } else if (state.leftEncode && leftSelect.value !== state.leftEncode) {
        leftSelect.value = state.leftEncode;
      }
    }
  }

  function setZoom(newZoom, focusPoint, options = {}) {
    const clamped = clampZoom(newZoom);
    const fromPreset = Boolean(options.fromPreset);
    const previousZoom = state.zoom;
    state.zoom = clamped;
    if (!fromPreset) {
      state.fitPreset = null;
      updateFitButtons();
    }
    updateZoomUI();

    if (focusPoint && previousZoom !== clamped && state.imageSize) {
      const stageRect = viewerStage.getBoundingClientRect();
      const stageX = focusPoint.x - stageRect.left;
      const stageY = focusPoint.y - stageRect.top;
      const prevScale = previousZoom / 100;
      const nextScale = clamped / 100;
      if (prevScale > 0 && nextScale > 0) {
        const stage = getStageSize();
        const prevAlignment = computeAlignmentOffset(stage, {
          width: state.imageSize.width * prevScale,
          height: state.imageSize.height * prevScale,
        });
        const contentX = (stageX - state.pan.x - prevAlignment.x) / prevScale;
        const contentY = (stageY - state.pan.y - prevAlignment.y) / prevScale;
        if (Number.isFinite(contentX) && Number.isFinite(contentY)) {
          const nextAlignment = computeAlignmentOffset(stage, {
            width: state.imageSize.width * nextScale,
            height: state.imageSize.height * nextScale,
          });
          const targetX = stageX - (contentX * nextScale) - nextAlignment.x;
          const targetY = stageY - (contentY * nextScale) - nextAlignment.y;
          state.pan.x = targetX;
          state.pan.y = targetY;
          if (!fromPreset) {
            state.panHasMoved = true;
            if (state.alignment !== CUSTOM_ALIGNMENT) {
              state.prevAlignment = state.alignment;
              state.alignment = CUSTOM_ALIGNMENT;
              updateAlignmentSelect();
            }
          }
        }
      }
    }

    applyTransform();
    savePreferences();
  }

  function applyFitPreset(preset) {
    state.fitPreset = preset;
    state.pan = { x: 0, y: 0 };
    state.panHasMoved = false;
    if (state.alignment === CUSTOM_ALIGNMENT) {
      state.alignment = state.prevAlignment || "center";
      updateAlignmentSelect();
    }
    updateFitButtons();
    const scale = computeFitScale(preset);
    const percent = clampZoom(scale * 100);
    setZoom(percent, null, { fromPreset: true });
  }

  function renderFooter(data) {
    const generated = data.generated_at ? new Date(data.generated_at) : null;
    const generatedLabel = generated && !Number.isNaN(generated.valueOf())
      ? generated.toLocaleString()
      : "unknown";
    footer.textContent = `Generated ${generatedLabel} • Frames: ${data.stats.frames} • Encodes: ${data.stats.encodes}`;
  }

  function renderSubtitle(data) {
    const generated = data.generated_at ? new Date(data.generated_at) : null;
    const generatedLabel = generated && !Number.isNaN(generated.valueOf())
      ? generated.toLocaleString()
      : "unknown";
    subtitle.textContent = `Interactive report • Generated ${generatedLabel}`;
    if (data.slowpics_url && linkContainer) {
      linkContainer.innerHTML = "";
      const link = document.createElement("a");
      link.href = data.slowpics_url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = "Open slow.pics collection";
      linkContainer.appendChild(link);
    }
  }

  function fillSelect(selectNode, items) {
    selectNode.innerHTML = "";
    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.label;
      option.textContent = item.label;
      selectNode.appendChild(option);
    });
  }

  function renderEncodes(encodes) {
    encodeInfo.innerHTML = "";
    encodes.forEach((encode) => {
      const wrapper = document.createElement("div");
      wrapper.className = "rc-encode-card";
      const heading = document.createElement("h3");
      heading.textContent = encode.label;
      wrapper.appendChild(heading);

      const metadata = encode.metadata || null;
      if (metadata && Object.keys(metadata).length > 0) {
        const list = document.createElement("dl");
        Object.keys(metadata).forEach((key) => {
          const term = document.createElement("dt");
          term.textContent = key;
          const value = document.createElement("dd");
          value.textContent = metadata[key];
          list.appendChild(term);
          list.appendChild(value);
        });
        wrapper.appendChild(list);
      }
      encodeInfo.appendChild(wrapper);
    });
  }

  function renderFrameSelectOptions(frames) {
    if (!frameSelect) {
      return;
    }
    const desiredValue = state.currentFrame != null ? String(state.currentFrame) : null;
    frameSelect.innerHTML = "";
    frames.forEach((frame) => {
      const option = document.createElement("option");
      option.value = String(frame.index);
      option.textContent = frame.label ? `${frame.index} — ${frame.label}` : String(frame.index);
      frameSelect.appendChild(option);
    });
    if (desiredValue && frames.some((frame) => String(frame.index) === desiredValue)) {
      frameSelect.value = desiredValue;
    } else if (frames.length) {
      frameSelect.value = String(frames[0].index);
    } else {
      frameSelect.value = "";
    }
  }

  function getVisibleFrames() {
    if (!state.data || !Array.isArray(state.data.frames)) {
      return [];
    }
    if (state.activeCategories.size === 0) {
      return state.data.frames;
    }
    return state.data.frames.filter((frame) => {
      if (!frame || typeof frame !== "object") {
        return false;
      }
      if (typeof frame.category_key !== "string") {
        return false;
      }
      return state.activeCategories.has(frame.category_key);
    });
  }

  function applyCategoryFilters() {
    const frames = getVisibleFrames();
    if (!Array.isArray(frames) || frames.length === 0) {
      state.sortedFrameIndexes = [];
      renderFilmstrip([]);
      renderFrameSelectOptions([]);
      state.currentFrame = null;
      updateImages();
      return;
    }
    const currentVisible = frames.some((frame) => frame.index === state.currentFrame);
    if (!currentVisible) {
      state.currentFrame = frames[0].index;
    }
    state.sortedFrameIndexes = frames.map((frame) => frame.index).sort((a, b) => a - b);
    renderFilmstrip(frames);
    renderFrameSelectOptions(frames);
    selectFrame(state.currentFrame);
  }

  function renderCategoryFilters(categories) {
    if (!filterContainer) {
      return;
    }
    filterContainer.innerHTML = "";
    if (!Array.isArray(categories) || categories.length === 0) {
      filterContainer.hidden = true;
      return;
    }
    filterContainer.hidden = false;

    const toolbar = document.createElement("div");
    toolbar.className = "rc-category-filter";

    const showAllActive = state.activeCategories.size === 0;
    const allButton = document.createElement("button");
    allButton.type = "button";
    allButton.className = "rc-category-filter__chip";
    allButton.textContent = "All";
    allButton.setAttribute("aria-pressed", showAllActive ? "true" : "false");
    allButton.addEventListener("click", () => {
      if (state.activeCategories.size === 0) {
        return;
      }
      state.activeCategories.clear();
      savePreferences();
      renderCategoryFilters(state.categories);
      applyCategoryFilters();
    });
    toolbar.appendChild(allButton);

    categories.forEach((category) => {
      if (!category || typeof category !== "object") {
        return;
      }
      const key = typeof category.key === "string" ? category.key : "";
      const label = typeof category.label === "string" ? category.label : "";
      const count = typeof category.count === "number" ? category.count : null;
      if (!key || !label) {
        return;
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className = "rc-category-filter__chip";
      button.dataset.key = key;
      button.textContent = count != null ? `${label} (${count})` : label;
      const isActive = state.activeCategories.has(key);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
      button.addEventListener("click", () => {
        if (state.activeCategories.has(key)) {
          state.activeCategories.delete(key);
        } else {
          state.activeCategories.add(key);
        }
        if (state.activeCategories.size === state.categories.length) {
          state.activeCategories.clear();
        }
        savePreferences();
        renderCategoryFilters(state.categories);
        applyCategoryFilters();
      });
      toolbar.appendChild(button);
    });

    filterContainer.appendChild(toolbar);
  }

  function renderFilmstrip(frames) {
    frameList.innerHTML = "";
    frames.forEach((frame) => {
      const li = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.frame = String(frame.index);
      button.className = "rc-frame-thumb";
      const frameLabelText = frame.label ? `${frame.index} · ${frame.label}` : String(frame.index);
      button.setAttribute("aria-label", frameLabelText);

      const thumbnailPath = typeof frame.thumbnail === "string" ? frame.thumbnail : null;
      if (thumbnailPath) {
        const figure = document.createElement("figure");
        figure.className = "rc-frame-thumb__figure";
        const image = document.createElement("img");
        image.className = "rc-frame-thumb__image";
        image.src = thumbnailPath;
        image.loading = "lazy";
        image.decoding = "async";
        image.alt = frame.label ? `Frame ${frame.index} — ${frame.label}` : `Frame ${frame.index}`;
        figure.appendChild(image);
        button.appendChild(figure);
      } else {
        const placeholder = document.createElement("div");
        placeholder.className = "rc-frame-thumb__placeholder";
        placeholder.textContent = frame.index;
        button.appendChild(placeholder);
      }

      const categoryLabel = typeof frame.category === "string" && frame.category ? frame.category : null;
      if (categoryLabel) {
        const badge = document.createElement("span");
        badge.className = "rc-frame-thumb__badge";
        badge.textContent = categoryLabel;
        button.appendChild(badge);
      }

      const caption = document.createElement("span");
      caption.className = "rc-frame-thumb__caption";
      caption.textContent = frameLabelText;
      button.appendChild(caption);

      button.addEventListener("click", () => {
        selectFrame(frame.index, true);
      });
      li.appendChild(button);
      frameList.appendChild(li);
    });
  }

  function updateFilmstripActive(frameIndex) {
    frameList.querySelectorAll("button").forEach((button) => {
      const isActive = Number(button.dataset.frame) === frameIndex;
      button.setAttribute("aria-current", isActive ? "true" : "false");
      button.classList.toggle("rc-frame-thumb--active", isActive);
    });
  }

  function ensureActiveThumbnailVisible(frameIndex) {
    const activeButton = frameList.querySelector(`button[data-frame="${frameIndex}"]`);
    if (!activeButton) {
      return;
    }
    const scroller = frameList.closest(".rc-filmstrip");
    if (!(scroller instanceof HTMLElement)) {
      return;
    }
    // Keep the active thumbnail visible without altering the page scroll position.
    const scrollerRect = scroller.getBoundingClientRect();
    const buttonRect = activeButton.getBoundingClientRect();
    const overflowLeft = buttonRect.left - scrollerRect.left;
    const overflowRight = buttonRect.right - scrollerRect.right;
    if (overflowLeft < 0) {
      scroller.scrollLeft = Math.max(0, scroller.scrollLeft + overflowLeft);
    } else if (overflowRight > 0) {
      const maxScrollLeft = Math.max(0, scroller.scrollWidth - scroller.clientWidth);
      scroller.scrollLeft = Math.min(maxScrollLeft, scroller.scrollLeft + overflowRight);
    }
  }

  function updateFrameMetadata(frame, data) {
    if (!frame || data.include_metadata !== "full") {
      frameMetadata.hidden = true;
      frameMetadata.innerHTML = "";
      return;
    }
    const detail = frame.detail || null;
    if (!detail || Object.keys(detail).length === 0) {
      frameMetadata.hidden = true;
      frameMetadata.innerHTML = "";
      return;
    }
    const table = document.createElement("table");
    const tbody = document.createElement("tbody");
    Object.entries(detail).forEach(([key, value]) => {
      const row = document.createElement("tr");
      const th = document.createElement("th");
      th.textContent = key;
      const td = document.createElement("td");
      td.textContent = String(value);
      row.appendChild(th);
      row.appendChild(td);
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    frameMetadata.innerHTML = "";
    frameMetadata.appendChild(table);
    frameMetadata.hidden = false;
  }

  function syncImageMetrics() {
    if (!canvas) {
      return;
    }
    const candidates = [];
    if (rightImage && rightImage.naturalWidth && rightImage.naturalHeight) {
      candidates.push({ width: rightImage.naturalWidth, height: rightImage.naturalHeight });
    }
    if (leftImage && leftImage.naturalWidth && leftImage.naturalHeight) {
      candidates.push({ width: leftImage.naturalWidth, height: leftImage.naturalHeight });
    }
    if (!candidates.length) {
      return;
    }
    const primary = candidates.reduce((best, candidate) => {
      const bestArea = best.width * best.height;
      const candidateArea = candidate.width * candidate.height;
      return candidateArea > bestArea ? candidate : best;
    });
    state.imageSize = primary;
    canvas.style.setProperty("--rc-canvas-width", `${primary.width}px`);
    canvas.style.setProperty("--rc-canvas-height", `${primary.height}px`);
    if (state.fitPreset) {
      const target = clampZoom(computeFitScale(state.fitPreset) * 100);
      state.zoom = target;
      updateZoomUI();
    }
    applyTransform();
  }

  function handleImageLoad() {
    window.requestAnimationFrame(() => {
      syncImageMetrics();
    });
  }

  [leftImage, rightImage].forEach((image) => {
    if (!image) {
      return;
    }
    image.addEventListener("load", handleImageLoad);
    if (image.complete && image.naturalWidth && image.naturalHeight) {
      handleImageLoad();
    }
  });

  function findFrame(frameIndex) {
    return state.framesByIndex.get(frameIndex) || null;
  }

  function updateImages(preservePan = false) {
    const frame = findFrame(state.currentFrame);
    if (!frame) {
      leftImage.removeAttribute("src");
      rightImage.removeAttribute("src");
      frameLabel.textContent = "No frame selected.";
      viewerStage.setAttribute("aria-busy", "true");
      return;
    }
    viewerStage.removeAttribute("aria-busy");
    const fileMap = new Map();
    (frame.files || []).forEach((entry) => {
      fileMap.set(entry.encode, entry.path);
    });
    const overlayLabelForMode = state.mode === "overlay" ? state.overlayEncode : null;
    const leftLabelForMode = overlayLabelForMode || state.leftEncode;
    const rightLabelForMode = state.rightEncode;
    const leftPath = leftLabelForMode ? fileMap.get(leftLabelForMode) || null : null;
    const rightPath = rightLabelForMode ? fileMap.get(rightLabelForMode) || null : null;

    if (leftPath) {
      leftImage.src = leftPath;
      leftImage.alt = `${leftLabelForMode} at frame ${frame.index}`;
    } else {
      leftImage.removeAttribute("src");
      leftImage.alt = "";
    }

    if (rightPath) {
      rightImage.src = rightPath;
      rightImage.alt = `${rightLabelForMode} at frame ${frame.index}`;
    } else {
      rightImage.removeAttribute("src");
      rightImage.alt = "";
    }

    const sliderLeftPath = state.leftEncode ? fileMap.get(state.leftEncode) || null : null;
    const sliderEnabled = Boolean(
      sliderLeftPath && rightPath && state.leftEncode && state.leftEncode !== state.rightEncode,
    );
    setSlider(sliderControl.value);
    updateModeUI(sliderEnabled, Boolean(leftPath), Boolean(rightPath));

    frameLabel.textContent = frame.label ? `Frame ${frame.index} — ${frame.label}` : `Frame ${frame.index}`;
    frameSelect.value = String(frame.index);
    updateFilmstripActive(frame.index);
    ensureActiveThumbnailVisible(frame.index);
    updateFrameMetadata(frame, state.data);
    if (!preservePan) {
      state.pan = { x: 0, y: 0 };
      state.panHasMoved = false;
      if (state.alignment === CUSTOM_ALIGNMENT) {
        state.alignment = state.prevAlignment || "center";
        updateAlignmentSelect();
      }
    }
    window.requestAnimationFrame(() => {
      syncImageMetrics();
    });
    applyTransform();
  }

  function selectFrame(frameIndex, focusFilmstrip = false) {
    if (!state.framesByIndex.has(frameIndex)) {
      return;
    }
    state.currentFrame = frameIndex;
    savePreferences();
    updateImages();
    if (focusFilmstrip) {
      const button = frameList.querySelector(`button[data-frame="${frameIndex}"]`);
      if (button) {
        button.focus();
      }
    }
  }

  function applyDefaults(data) {
    const encodes = data.encodes || [];
    const defaults = data.defaults || {};
    const leftDefault = defaults.left && encodes.find((encode) => encode.label === defaults.left);
    const rightDefault = defaults.right && encodes.find((encode) => encode.label === defaults.right);
    state.leftEncode = leftDefault ? leftDefault.label : (encodes[0] ? encodes[0].label : null);
    state.rightEncode = rightDefault ? rightDefault.label : (encodes[1] ? encodes[1].label : state.leftEncode);
    let overlayLabel = null;
    if (hasOverlayPreference && storedOverlayEncode && state.overlayOrder.includes(storedOverlayEncode)) {
      overlayLabel = storedOverlayEncode;
    }
    if (!overlayLabel) {
      overlayLabel = state.leftEncode || (state.overlayOrder.length > 0 ? state.overlayOrder[0] : null);
    }
    state.overlayEncode = overlayLabel;
    state.overlayIndex = overlayLabel ? state.overlayOrder.indexOf(overlayLabel) : -1;
    if (state.mode === "overlay") {
      if (state.overlayEncode) {
        leftSelect.value = state.overlayEncode;
      }
    } else if (state.leftEncode) {
      leftSelect.value = state.leftEncode;
    }
    if (state.rightEncode) {
      rightSelect.value = state.rightEncode;
    }
  }

  function init(data) {
    state.data = data;
    state.overlayOrder = Array.isArray(data.encodes)
      ? data.encodes
          .map((encode) =>
            encode && typeof encode.label === "string" && encode.label.length > 0 ? encode.label : null,
          )
          .filter((label) => typeof label === "string")
      : [];
    const frames = Array.isArray(data.frames) ? data.frames : [];
    state.framesByIndex.clear();
    frames.forEach((frame) => {
      state.framesByIndex.set(frame.index, frame);
    });
    state.allFrameIndexes = frames.map((frame) => frame.index).sort((a, b) => a - b);
    if (storedFrameIndex !== null && state.framesByIndex.has(storedFrameIndex)) {
      state.currentFrame = storedFrameIndex;
    } else {
      state.currentFrame = null;
    }

    state.categories = Array.isArray(data.categories)
      ? data.categories.filter(
        (category) =>
          category &&
          typeof category === "object" &&
          typeof category.key === "string" &&
          category.key.length > 0 &&
          typeof category.label === "string" &&
          category.label.length > 0,
      )
      : [];
    state.activeCategories.clear();
    if (hasCategoryPreference && state.categories.length > 0) {
      storedCategoryKeys.forEach((key) => {
        if (state.categories.some((category) => category.key === key)) {
          state.activeCategories.add(key);
        }
      });
    }

    fillSelect(leftSelect, data.encodes || []);
    fillSelect(rightSelect, data.encodes || []);
    renderEncodes(data.encodes || []);
    renderCategoryFilters(state.categories);

    applyDefaults(data);

    if (!hasModePreference) {
      const defaultMode = typeof data.viewer_mode === "string" ? data.viewer_mode : "slider";
      state.mode = VIEWER_MODES.has(defaultMode) ? defaultMode : defaultMode === "overlay" ? "overlay" : "slider";
    }
    if (modeSelect) {
      modeSelect.value = state.mode;
    }
    updateEncodeControlsForMode();

    applyCategoryFilters();

    if (state.currentFrame == null && state.sortedFrameIndexes.length === 0) {
      showError("No frames found in report data.");
      return;
    }
    renderSubtitle(data);
    renderFooter(data);

    if (fullscreenButton) {
      const supported = isFullscreenSupported();
      fullscreenButton.disabled = !supported;
      fullscreenButton.setAttribute("aria-pressed", "false");
      if (supported) {
        fullscreenButton.addEventListener("click", () => {
          toggleFullscreen();
        });
      }
    }
    syncFullscreenState();
  }

  frameSelect.addEventListener("change", (event) => {
    const value = Number(event.target.value);
    selectFrame(value);
  });

  leftSelect.addEventListener("change", (event) => {
    const selected = event.target.value;
    if (state.mode === "overlay") {
      setOverlayEncode(selected);
    } else {
      const previousLeft = state.leftEncode;
      state.leftEncode = selected;
      if (
        selected &&
        typeof selected === "string" &&
        state.overlayOrder.includes(selected) &&
        (!state.overlayEncode || state.overlayEncode === previousLeft)
      ) {
        state.overlayEncode = selected;
        state.overlayIndex = state.overlayOrder.indexOf(selected);
      }
      updateImages(state.mode !== "slider");
      savePreferences();
    }
  });

  rightSelect.addEventListener("change", (event) => {
    state.rightEncode = event.target.value;
    updateImages(state.mode !== "slider");
  });

  sliderControl.addEventListener("input", (event) => {
    setSlider(event.target.value);
    if (state.mode === "slider") {
      updateImages();
    }
  });
  setSlider(sliderControl.value);

  if (zoomControl) {
    zoomControl.addEventListener("input", (event) => {
      const value = Number(event.target.value) || state.zoom;
      const focusPoint = state.pointer;
      setZoom(value, focusPoint);
    });
    zoomControl.value = String(state.zoom);
  }

  if (zoomOutButton) {
    zoomOutButton.addEventListener("click", () => {
      const stageRect = viewerStage.getBoundingClientRect();
      const focus = state.pointer || { x: stageRect.left + stageRect.width / 2, y: stageRect.top + stageRect.height / 2 };
      setZoom(state.zoom - ZOOM_STEP, focus);
    });
  }

  if (zoomInButton) {
    zoomInButton.addEventListener("click", () => {
      const stageRect = viewerStage.getBoundingClientRect();
      const focus = state.pointer || { x: stageRect.left + stageRect.width / 2, y: stageRect.top + stageRect.height / 2 };
      setZoom(state.zoom + ZOOM_STEP, focus);
    });
  }

  if (zoomResetButton) {
    zoomResetButton.addEventListener("click", () => {
      state.pan = { x: 0, y: 0 };
      state.panHasMoved = false;
      state.fitPreset = null;
      updateFitButtons();
      setZoom(100);
    });
  }

  fitButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const preset = button.dataset.fit || "fit-width";
      state.panHasMoved = false;
      applyFitPreset(preset);
    });
  });

  if (alignmentSelect) {
    alignmentSelect.addEventListener("change", (event) => {
      const selected = event.target.value || "center";
      if (selected === CUSTOM_ALIGNMENT) {
        alignmentSelect.value = state.alignment;
        return;
      }
      state.alignment = selected;
      state.prevAlignment = selected;
      state.pan = { x: 0, y: 0 };
      state.panHasMoved = false;
      updateAlignmentSelect();
      applyTransform();
      savePreferences();
    });
    updateAlignmentSelect();
  }

  updateZoomUI();
  updateFitButtons();
  applyTransform();

  if (modeSelect) {
    modeSelect.addEventListener("change", (event) => {
      applyMode(event.target.value);
    });
  }

  function encodeLabels() {
    if (!state.data || !Array.isArray(state.data.encodes)) {
      return [];
    }
    return state.data.encodes.map((encode) => encode.label);
  }

  function updateModeUI(sliderEnabled, leftAvailable, rightAvailable) {
    const hasBoth = leftAvailable && rightAvailable;
    const previousMode = state.mode;
    let mode = state.mode;

    if ((mode === "difference" || mode === "blink") && !hasBoth) {
      mode = leftAvailable ? "overlay" : "slider";
    } else if (mode === "overlay" && !leftAvailable) {
      mode = sliderEnabled ? "slider" : (hasBoth ? "difference" : "slider");
    }

    if (!VIEWER_MODES.has(mode)) {
      mode = "slider";
    }

    if (mode !== state.mode) {
      state.mode = mode;
    }
    if (previousMode === "blink" && state.mode !== "blink") {
      stopBlink();
    }

    if (modeSelect) {
      modeSelect.value = state.mode;
    }

    if (viewerStage instanceof HTMLElement) {
      viewerStage.dataset.mode = state.mode;
      viewerStage.classList.toggle("rc-mode-overlay", state.mode === "overlay");
      viewerStage.classList.toggle("rc-mode-slider", state.mode === "slider");
      viewerStage.classList.toggle("rc-mode-difference", state.mode === "difference");
      viewerStage.classList.toggle("rc-mode-blink", state.mode === "blink");
    }

    const hideSlider = state.mode !== "slider";
    if (sliderGroup instanceof HTMLElement) {
      sliderGroup.style.display = hideSlider ? "none" : "";
    }
    sliderControl.disabled = hideSlider || !sliderEnabled;

    if (state.mode === "slider") {
      stopBlink();
      if (sliderEnabled) {
        overlay.style.visibility = "visible";
        const percent = Math.min(100, Math.max(0, Number(sliderControl.value) || 0));
        const clipRight = 100 - percent;
        overlay.style.clipPath = `inset(0 ${clipRight}% 0 0)`;
        divider.style.display = "";
        divider.style.visibility = "visible";
        divider.style.left = `${percent}%`;
      } else {
        overlay.style.visibility = "hidden";
        divider.style.visibility = "hidden";
        divider.style.display = "none";
      }
      rightImage.style.visibility = rightAvailable ? "visible" : "hidden";
    } else if (state.mode === "overlay") {
      stopBlink();
      overlay.style.visibility = leftAvailable ? "visible" : "hidden";
      overlay.style.clipPath = "inset(0 0 0 0)";
      divider.style.visibility = "hidden";
      divider.style.display = "none";
      rightImage.style.visibility = rightAvailable ? "visible" : "hidden";
    } else if (state.mode === "difference") {
      stopBlink();
      overlay.style.visibility = hasBoth ? "visible" : "hidden";
      overlay.style.clipPath = "inset(0 0 0 0)";
      divider.style.visibility = "hidden";
      divider.style.display = "none";
      rightImage.style.visibility = hasBoth ? "visible" : "hidden";
    } else if (state.mode === "blink") {
      overlay.style.clipPath = "inset(0 0 0 0)";
      divider.style.visibility = "hidden";
      divider.style.display = "none";
      if (hasBoth) {
        startBlink();
      } else {
        stopBlink();
        overlay.style.visibility = leftAvailable ? "visible" : "hidden";
        rightImage.style.visibility = rightAvailable ? "visible" : "hidden";
      }
    }

    if (modeSelect) {
      modeSelect.value = state.mode;
    }
    updateEncodeControlsForMode();
    applyBlinkVisibility();
    applyTransform();
    if (previousMode !== state.mode) {
      savePreferences();
    }
  }

  let sliderDragActive = false;
  let sliderPointerId = null;
  let sliderCaptureElement = null;

  function setSliderFromClientX(clientX) {
    if (!canvas) {
      return;
    }
    const rect = canvas.getBoundingClientRect();
    if (rect.width <= 0) {
      return;
    }
    const percent = ((clientX - rect.left) / rect.width) * 100;
    setSlider(percent);
    if (state.mode === "slider") {
      updateImages();
    }
  }

  function setOverlayEncode(label) {
    if (!label || typeof label !== "string") {
      state.overlayEncode = null;
      state.overlayIndex = -1;
      savePreferences();
      return;
    }
    if (!state.overlayOrder.includes(label)) {
      return;
    }
    if (state.overlayEncode === label) {
      return;
    }
    state.overlayEncode = label;
    state.overlayIndex = state.overlayOrder.indexOf(label);
    if (state.mode === "overlay" && leftSelect && leftSelect.value !== label) {
      leftSelect.value = label;
    }
    updateImages(true);
    savePreferences();
  }

  function cycleOverlayEncode(step) {
    const labels = state.overlayOrder;
    if (!labels.length) {
      return;
    }
    let index = state.overlayIndex;
    if (index < 0) {
      index = state.overlayEncode ? labels.indexOf(state.overlayEncode) : -1;
    }
    if (index < 0) {
      index = 0;
    }
    const total = labels.length;
    index = (index + step + total) % total;
    const candidate = labels[index];
    if (candidate) {
      setOverlayEncode(candidate);
    }
  }

  function cycleRightEncode(step) {
    if (state.mode === "overlay") {
      cycleOverlayEncode(step);
      return;
    }
    const labels = encodeLabels();
    if (!labels.length) {
      return;
    }
    let index = labels.indexOf(state.rightEncode || "");
    if (index < 0) {
      index = 0;
    }
    const total = labels.length;
    for (let i = 0; i < total; i += 1) {
      index = (index + step + total) % total;
      const candidate = labels[index];
      if (candidate !== state.leftEncode || total === 1) {
        state.rightEncode = candidate;
        rightSelect.value = candidate;
        updateImages(state.mode !== "slider");
        break;
      }
    }
  }

  function applyMode(mode) {
    const normalized = VIEWER_MODES.has(mode) ? mode : "slider";
    const preservePan = normalized !== "slider";
    if (normalized === "overlay") {
      if (!state.overlayEncode || !state.overlayOrder.includes(state.overlayEncode)) {
        let fallback = null;
        if (state.leftEncode && state.overlayOrder.includes(state.leftEncode)) {
          fallback = state.leftEncode;
        } else if (state.overlayOrder.length > 0) {
          fallback = state.overlayOrder[0];
        }
        if (fallback) {
          state.overlayEncode = fallback;
        }
      }
      if (state.overlayEncode && state.overlayIndex < 0) {
        state.overlayIndex = state.overlayOrder.indexOf(state.overlayEncode);
      }
    }
    state.mode = normalized;
    updateImages(preservePan);
    if (modeSelect) {
      modeSelect.value = state.mode;
    }
    savePreferences();
  }

  function shouldStartPan(event) {
    if (event.button !== 0 || !state.imageSize) {
      return false;
    }
    if (state.panModifier) {
      return true;
    }
    if (state.mode === "slider") {
      return false;
    }
    const stage = getStageSize();
    const scale = currentScale();
    return (
      state.imageSize.width * scale > stage.width + 1 ||
      state.imageSize.height * scale > stage.height + 1
    );
  }

  function startPan(event) {
    state.panActive = true;
    state.panPointerId = event.pointerId;
    state.panStart = {
      x: state.pan.x,
      y: state.pan.y,
      clientX: event.clientX,
      clientY: event.clientY,
    };
    state.panHasMoved = false;
    viewerStage.classList.add("rc-pan-active");
    try {
      viewerStage.setPointerCapture(event.pointerId);
    } catch (error) {
      // ignore capture errors
    }
    event.preventDefault();
  }

  function endPan(event) {
    const pointerId = event ? event.pointerId : state.panPointerId;
    if (!state.panActive || (typeof pointerId === "number" && pointerId !== state.panPointerId)) {
      return;
    }
    state.panActive = false;
    state.panPointerId = null;
    state.panStart = null;
    viewerStage.classList.remove("rc-pan-active");
    if (typeof pointerId === "number") {
      try {
        viewerStage.releasePointerCapture(pointerId);
      } catch (error) {
        // ignore release errors
      }
    }
    applyTransform();
  }

  window.addEventListener("keydown", (event) => {
    if (state.currentFrame == null) {
      return;
    }
    const ignoreTargets = [frameSelect, leftSelect, rightSelect, sliderControl, modeSelect, alignmentSelect];
    if (event.target && ignoreTargets.includes(event.target)) {
      return;
    }
    if (event.code === "Space") {
      state.panModifier = true;
      updatePanAvailability(
        state.imageSize ? state.imageSize.width * currentScale() : 0,
        state.imageSize ? state.imageSize.height * currentScale() : 0,
        getStageSize(),
      );
      event.preventDefault();
      return;
    }
    if (event.key === "r" || event.key === "R") {
      event.preventDefault();
      state.pan = { x: 0, y: 0 };
      state.fitPreset = null;
      updateFitButtons();
      setZoom(100);
      return;
    }
    if (event.key === "f" || event.key === "F") {
      event.preventDefault();
      toggleFullscreen();
      return;
    }
    if (event.key === "d" || event.key === "D") {
      event.preventDefault();
      applyMode("difference");
      return;
    }
    if (event.key === "b" || event.key === "B") {
      event.preventDefault();
      applyMode("blink");
      return;
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      const frames = state.sortedFrameIndexes;
      const index = frames.indexOf(state.currentFrame);
      if (index >= 0 && index + 1 < frames.length) {
        selectFrame(frames[index + 1]);
      }
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      const frames = state.sortedFrameIndexes;
      const index = frames.indexOf(state.currentFrame);
      if (index > 0) {
        selectFrame(frames[index - 1]);
      }
    } else if (event.key === "ArrowUp") {
      if (state.mode === "overlay" || state.mode === "difference" || state.mode === "blink") {
        event.preventDefault();
        cycleRightEncode(-1);
      }
    } else if (event.key === "ArrowDown") {
      if (state.mode === "overlay" || state.mode === "difference" || state.mode === "blink") {
        event.preventDefault();
        cycleRightEncode(1);
      }
    }
  });

  window.addEventListener("keyup", (event) => {
    if (event.code === "Space") {
      state.panModifier = false;
      if (!state.panActive) {
        updatePanAvailability(
          state.imageSize ? state.imageSize.width * currentScale() : 0,
          state.imageSize ? state.imageSize.height * currentScale() : 0,
          getStageSize(),
        );
      }
    }
  });

  window.addEventListener("blur", () => {
    state.panModifier = false;
    endPan({ pointerId: state.panPointerId });
    updatePanAvailability(
      state.imageSize ? state.imageSize.width * currentScale() : 0,
      state.imageSize ? state.imageSize.height * currentScale() : 0,
      getStageSize(),
    );
    if (state.mode === "blink") {
      resumeBlink();
    }
  });

  viewerStage.addEventListener("click", () => {
    viewerStage.focus();
    if (state.panHasMoved) {
      state.panHasMoved = false;
      return;
    }
    if ((state.mode === "overlay" || state.mode === "difference") && !state.panActive) {
      cycleRightEncode(1);
    }
    state.panHasMoved = false;
  });

  viewerStage.addEventListener("pointerdown", (event) => {
    viewerStage.focus();
    state.pointer = { x: event.clientX, y: event.clientY };
    if (state.mode === "blink") {
      pauseBlink(true);
    }
    if (event.target === divider && state.mode === "slider" && !sliderControl.disabled) {
      sliderDragActive = true;
      sliderPointerId = event.pointerId;
      sliderCaptureElement = divider;
      try {
        sliderCaptureElement.setPointerCapture(event.pointerId);
      } catch (error) {
        // ignore capture errors
      }
      event.preventDefault();
      setSliderFromClientX(event.clientX);
      return;
    }
    if (shouldStartPan(event)) {
      startPan(event);
      return;
    }
    if (state.mode === "slider" && !sliderControl.disabled) {
      sliderDragActive = true;
      sliderPointerId = event.pointerId;
      sliderCaptureElement = viewerStage;
      try {
        viewerStage.setPointerCapture(event.pointerId);
      } catch (error) {
        // ignore capture errors
      }
      event.preventDefault();
      setSliderFromClientX(event.clientX);
    }
  });

  viewerStage.addEventListener("pointermove", (event) => {
    state.pointer = { x: event.clientX, y: event.clientY };
    if (state.panActive && event.pointerId === state.panPointerId) {
      if (state.panStart) {
        const deltaX = event.clientX - state.panStart.clientX;
        const deltaY = event.clientY - state.panStart.clientY;
        state.pan.x = state.panStart.x + deltaX;
        state.pan.y = state.panStart.y + deltaY;
        if (
          !state.panHasMoved &&
          (Math.abs(deltaX) > 1 || Math.abs(deltaY) > 1)
        ) {
          state.panHasMoved = true;
          if (state.alignment !== CUSTOM_ALIGNMENT) {
            state.prevAlignment = state.alignment;
            state.alignment = CUSTOM_ALIGNMENT;
            updateAlignmentSelect();
          }
        }
        applyTransform();
      }
      event.preventDefault();
      return;
    }
    if (sliderDragActive && event.pointerId === sliderPointerId) {
      event.preventDefault();
      setSliderFromClientX(event.clientX);
    }
  });

  function endSliderDrag(event) {
    if (!sliderDragActive || (event && event.pointerId !== sliderPointerId)) {
      return;
    }
    sliderDragActive = false;
    if (sliderCaptureElement && event) {
      try {
        sliderCaptureElement.releasePointerCapture(event.pointerId);
      } catch (error) {
        // ignore release errors
      }
    }
    sliderCaptureElement = null;
  }

  viewerStage.addEventListener("pointerup", (event) => {
    if (state.panActive) {
      endPan(event);
    }
    if (sliderDragActive) {
      endSliderDrag(event);
    }
    if (state.mode === "blink") {
      resumeBlink();
    }
  });

  viewerStage.addEventListener("pointercancel", (event) => {
    if (state.panActive) {
      endPan(event);
    }
    if (sliderDragActive) {
      endSliderDrag(event);
    }
    if (state.mode === "blink") {
      resumeBlink();
    }
  });

  viewerStage.addEventListener(
    "wheel",
    (event) => {
      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }
      event.preventDefault();
      const stepMultiplier = Math.max(1, Math.round(Math.abs(event.deltaY) / 120));
      const direction = event.deltaY > 0 ? -1 : 1;
      const delta = direction * stepMultiplier * (ZOOM_STEP / 2);
      const stageRect = viewerStage.getBoundingClientRect();
      const focus = { x: event.clientX, y: event.clientY };
      setZoom(state.zoom + delta, focus);
    },
    { passive: false },
  );

  window.addEventListener("resize", () => {
    if (state.fitPreset) {
      const target = clampZoom(computeFitScale(state.fitPreset) * 100);
      state.zoom = target;
      updateZoomUI();
    }
    applyTransform();
  });

  (function loadData() {
    const script = document.getElementById("report-data");
    if (script && script.textContent) {
      try {
        const parsed = JSON.parse(script.textContent);
        init(parsed);
        return;
      } catch (error) {
        console.error("Failed to parse embedded report data", error);
      }
    }
    fetch(DATA_URL)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load ${DATA_URL}: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => init(data))
      .catch((error) => {
        console.error(error);
        showError("Unable to load report data. Ensure data.json is present alongside index.html.");
      });
  })();
})();
