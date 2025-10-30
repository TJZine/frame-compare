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
  const encodeInfo = document.getElementById("encode-info");
  const frameMetadata = document.getElementById("frame-metadata");
  const subtitle = document.getElementById("report-subtitle");
  const footer = document.getElementById("report-footer");
  const linkContainer = document.getElementById("report-links");
  const sliderGroup = document.querySelector(".rc-slider-control");
  const viewerHelp = document.getElementById("viewer-help");

  const STORAGE_KEY = "frameCompareReportViewer.v2";
  const ZOOM_MIN = 25;
  const ZOOM_MAX = 400;
  const ZOOM_STEP = 10;
  const CUSTOM_ALIGNMENT = "custom";

  const state = {
    data: null,
    framesByIndex: new Map(),
    currentFrame: null,
    leftEncode: null,
    rightEncode: null,
    mode: "slider",
    zoom: 100,
    fitPreset: "fit-width",
    alignment: "center",
    prevAlignment: "center",
    pan: { x: 0, y: 0 },
    imageSize: null,
    pointer: null,
    panActive: false,
    panPointerId: null,
    panStart: null,
    panModifier: false,
    panAvailable: false,
    panHasMoved: false,
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
      };
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch (error) {
      // Ignore storage errors (private mode, etc.).
    }
  }

  const preferences = loadPreferences();
  const hasModePreference = typeof preferences.mode === "string";
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
  if (typeof preferences.mode === "string") {
    state.mode = preferences.mode === "overlay" ? "overlay" : "slider";
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
    if (state.mode === "overlay") {
      overlay.style.clipPath = "inset(0 0 0 0)";
      divider.style.visibility = "hidden";
      return;
    }
    const clipRight = 100 - percent;
    overlay.style.clipPath = `inset(0 ${clipRight}% 0 0)`;
    divider.style.left = `${percent}%`;
    divider.style.visibility = "visible";
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

  function renderFilmstrip(frames) {
    frameList.innerHTML = "";
    frames.forEach((frame) => {
      const li = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.frame = String(frame.index);
      const label = frame.label ? `${frame.index} · ${frame.label}` : String(frame.index);
      button.textContent = label;
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
    });
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
    const leftPath = fileMap.get(state.leftEncode) || null;
    const rightPath = fileMap.get(state.rightEncode) || null;

    if (leftPath) {
      leftImage.src = leftPath;
      leftImage.alt = `${state.leftEncode} at frame ${frame.index}`;
    } else {
      leftImage.removeAttribute("src");
      leftImage.alt = "";
    }

    if (rightPath) {
      rightImage.src = rightPath;
      rightImage.alt = `${state.rightEncode} at frame ${frame.index}`;
    } else {
      rightImage.removeAttribute("src");
      rightImage.alt = "";
    }

    const sliderEnabled = Boolean(leftPath && rightPath && state.leftEncode !== state.rightEncode);
    setSlider(sliderControl.value);
    updateModeUI(sliderEnabled, Boolean(leftPath), Boolean(rightPath));

    frameLabel.textContent = frame.label ? `Frame ${frame.index} — ${frame.label}` : `Frame ${frame.index}`;
    frameSelect.value = String(frame.index);
    updateFilmstripActive(frame.index);
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
    if (state.leftEncode) {
      leftSelect.value = state.leftEncode;
    }
    if (state.rightEncode) {
      rightSelect.value = state.rightEncode;
    }
  }

  function init(data) {
    state.data = data;
    const frames = Array.isArray(data.frames) ? data.frames : [];
    frames.forEach((frame) => {
      state.framesByIndex.set(frame.index, frame);
    });

    fillSelect(leftSelect, data.encodes || []);
    fillSelect(rightSelect, data.encodes || []);
    renderEncodes(data.encodes || []);
    renderFilmstrip(frames);
    renderSubtitle(data);
    renderFooter(data);

    frameSelect.innerHTML = "";
    frames.forEach((frame) => {
      const option = document.createElement("option");
      option.value = String(frame.index);
      option.textContent = frame.label ? `${frame.index} — ${frame.label}` : String(frame.index);
      frameSelect.appendChild(option);
    });

    applyDefaults(data);
    const firstFrame = frames.length ? frames[0].index : null;
    if (firstFrame !== null) {
      if (!hasModePreference) {
        state.mode = (data.viewer_mode || "slider") === "overlay" ? "overlay" : "slider";
      }
      if (modeSelect) {
        modeSelect.value = state.mode;
      }
      updateEncodeControlsForMode();
      selectFrame(firstFrame);
    } else {
      showError("No frames found in report data.");
    }
  }

  frameSelect.addEventListener("change", (event) => {
    const value = Number(event.target.value);
    selectFrame(value);
  });

  leftSelect.addEventListener("change", (event) => {
    state.leftEncode = event.target.value;
    updateImages(state.mode === "overlay");
  });

  rightSelect.addEventListener("change", (event) => {
    state.rightEncode = event.target.value;
    updateImages(state.mode === "overlay");
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

  function swapSelectedEncodes() {
    if (!state.leftEncode || !state.rightEncode) {
      return;
    }
    const temp = state.leftEncode;
    state.leftEncode = state.rightEncode;
    state.rightEncode = temp;
    if (leftSelect) {
      leftSelect.value = state.leftEncode;
    }
    if (rightSelect) {
      rightSelect.value = state.rightEncode;
    }
    updateImages(true);
  }

  function updateModeUI(sliderEnabled, leftAvailable, rightAvailable) {
    if (sliderGroup instanceof HTMLElement) {
      sliderGroup.style.display = state.mode === "overlay" ? "none" : "";
    }
    if (viewerStage instanceof HTMLElement) {
      viewerStage.dataset.mode = state.mode;
      viewerStage.classList.toggle("rc-mode-overlay", state.mode === "overlay");
      viewerStage.classList.toggle("rc-mode-slider", state.mode === "slider");
    }
    if (state.mode === "overlay") {
      const overlayActive = leftAvailable && rightAvailable;
      sliderControl.disabled = true;
      overlay.style.visibility = overlayActive ? "visible" : "hidden";
      overlay.style.clipPath = "inset(0 0 0 0)";
      divider.style.visibility = "hidden";
    } else {
      sliderControl.disabled = !sliderEnabled;
      if (sliderEnabled) {
        overlay.style.visibility = "visible";
        const percent = Math.min(100, Math.max(0, Number(sliderControl.value) || 0));
        const clipRight = 100 - percent;
        overlay.style.clipPath = `inset(0 ${clipRight}% 0 0)`;
        divider.style.visibility = "visible";
        divider.style.left = `${percent}%`;
      } else {
        overlay.style.visibility = "hidden";
        divider.style.visibility = "hidden";
      }
    }
    if (modeSelect) {
      modeSelect.value = state.mode;
    }
    updateEncodeControlsForMode();
    applyTransform();
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

  function cycleRightEncode(step) {
    if (state.mode === "overlay") {
      swapSelectedEncodes();
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
        updateImages(state.mode === "overlay");
        break;
      }
    }
  }

  function applyMode(mode) {
    state.mode = mode === "overlay" ? "overlay" : "slider";
    updateImages(state.mode === "overlay");
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
    if (event.key === "ArrowRight") {
      event.preventDefault();
      const frames = Array.from(state.framesByIndex.keys()).sort((a, b) => a - b);
      const index = frames.indexOf(state.currentFrame);
      if (index >= 0 && index + 1 < frames.length) {
        selectFrame(frames[index + 1]);
      }
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      const frames = Array.from(state.framesByIndex.keys()).sort((a, b) => a - b);
      const index = frames.indexOf(state.currentFrame);
      if (index > 0) {
        selectFrame(frames[index - 1]);
      }
    } else if (event.key === "ArrowUp") {
      if (state.mode === "overlay") {
        event.preventDefault();
        cycleRightEncode(-1);
      }
    } else if (event.key === "ArrowDown") {
      if (state.mode === "overlay") {
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
  });

  viewerStage.addEventListener("click", () => {
    viewerStage.focus();
    if (state.panHasMoved) {
      state.panHasMoved = false;
      return;
    }
    if (state.mode === "overlay" && !state.panActive) {
      cycleRightEncode(1);
    }
    state.panHasMoved = false;
  });

  viewerStage.addEventListener("pointerdown", (event) => {
    viewerStage.focus();
    state.pointer = { x: event.clientX, y: event.clientY };
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
  });

  viewerStage.addEventListener("pointercancel", (event) => {
    if (state.panActive) {
      endPan(event);
    }
    if (sliderDragActive) {
      endSliderDrag(event);
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
