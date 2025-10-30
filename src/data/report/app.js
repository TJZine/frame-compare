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
  const viewerStage = document.getElementById("viewer-stage");
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

  const state = {
    data: null,
    framesByIndex: new Map(),
    currentFrame: null,
    leftEncode: null,
    rightEncode: null,
    mode: "slider",
  };

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

  function findFrame(frameIndex) {
    return state.framesByIndex.get(frameIndex) || null;
  }

  function updateImages() {
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
      state.mode = (data.viewer_mode || "slider") === "overlay" ? "overlay" : "slider";
      if (modeSelect) {
        modeSelect.value = state.mode;
      }
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
    updateImages();
  });

  rightSelect.addEventListener("change", (event) => {
    state.rightEncode = event.target.value;
    updateImages();
  });

  sliderControl.addEventListener("input", (event) => {
    setSlider(event.target.value);
    if (state.mode === "slider") {
      updateImages();
    }
  });
  setSlider(sliderControl.value);

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
    if (sliderGroup instanceof HTMLElement) {
      sliderGroup.style.display = state.mode === "overlay" ? "none" : "";
    }
    if (state.mode === "overlay") {
      const overlayActive = leftAvailable && rightAvailable;
      sliderControl.disabled = true;
      overlay.style.visibility = overlayActive ? "visible" : "hidden";
      overlay.style.clipPath = "inset(0 0 0 0)";
      divider.style.visibility = "hidden";
    } else {
      sliderControl.disabled = !sliderEnabled;
      const isVisible = sliderEnabled;
      overlay.style.visibility = isVisible ? "visible" : "hidden";
      divider.style.visibility = isVisible ? "visible" : "hidden";
      setSlider(sliderControl.value);
    }
    if (modeSelect) {
      modeSelect.value = state.mode;
    }
  }

  function cycleRightEncode(step) {
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
        updateImages();
        break;
      }
    }
  }

  function applyMode(mode) {
    state.mode = mode === "overlay" ? "overlay" : "slider";
    updateImages();
  }

  window.addEventListener("keydown", (event) => {
    if (!state.currentFrame) {
      return;
    }
    const ignoreTargets = [frameSelect, leftSelect, rightSelect, sliderControl, modeSelect];
    if (event.target && ignoreTargets.includes(event.target)) {
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

  viewerStage.addEventListener("click", () => {
    viewerStage.focus();
    if (state.mode === "overlay") {
      cycleRightEncode(1);
    }
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
