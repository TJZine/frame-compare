"""Report generation service."""

from __future__ import annotations

# ruff: noqa: W291, W293
import base64
import html
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from frame_compare.config.schema import ReportConfig
from frame_compare.errors import ReportError
from frame_compare.services.types import TmdbMetadata

REPORT_VERSION = "1.0"


@dataclass(frozen=True)
class ClipInfo:
    """Information about a video clip for report generation."""

    name: str  # Display name (filename or custom label)
    path: Path  # Source video path (for reference, not embedded)
    frame_count: int  # Total frames in source
    resolution: tuple[int, int]  # (width, height)
    fps: float  # Frames per second
    hdr: bool  # True if HDR source
    label: str | None = None  # Short label for UI (e.g., "REF", "ENC")


@dataclass(frozen=True)
class ReportData:
    """Data for report generation."""

    clips: list[ClipInfo]  # At least 2 clips for comparison
    frames: list[int]  # Selected frame numbers
    screenshots: dict[str, list[Path]]  # clip_name → [frame_paths] in order
    metadata: TmdbMetadata | None = None  # Optional TMDB info
    slowpics_url: str | None = None  # Link if uploaded


def generate_report(
    data: ReportData, config: ReportConfig, output_path: Path | None = None
) -> Path:
    """Generate HTML comparison report.

    Args:
        data: The report data containing clips, frames, and screenshot paths.
        config: Report configuration.
        output_path: Optional custom output path. If None, derived from config or data.

    Returns:
        Path to the generated HTML file.

    Raises:
        ReportError: If validation fails or IO operations fail.
    """
    # 1. VALIDATE INPUT
    if len(data.clips) == 0:
        raise ReportError("no clips provided")
    if len(data.clips) < 2:
        raise ReportError("at least 2 clips required for comparison")
    if len(data.frames) == 0:
        raise ReportError("no frames provided")
    if len(data.screenshots) == 0:
        raise ReportError("no screenshots provided")

    for clip in data.clips:
        if clip.name not in data.screenshots:
            raise ReportError(f"no screenshots for clip: {clip.name}")
        if len(data.screenshots[clip.name]) == 0:
            raise ReportError(f"no screenshots for clip: {clip.name}")
        if len(data.screenshots[clip.name]) != len(data.frames):
            raise ReportError(
                f"screenshot count mismatch for {clip.name}: "
                f"expected {len(data.frames)}, got {len(data.screenshots[clip.name])}"
            )

    # 2. DETERMINE OUTPUT PATH
    final_output_path: Path
    if output_path is not None:
        final_output_path = output_path
    elif config.output_dir:
        final_output_path = Path(config.output_dir) / "report.html"
    else:
        # Fallback: first clip, first frame's parent dir
        first_clip_name = data.clips[0].name
        first_screenshot = data.screenshots[first_clip_name][0]
        final_output_path = first_screenshot.parent / "report.html"

    # 3. PREPARE IMAGES & 4. BUILD JSON DATA
    # Structure defined in spec Section 2.2
    json_clips: list[dict[str, object]] = []
    for clip in data.clips:
        json_clips.append(
            {
                "name": clip.name,
                "label": clip.label or clip.name,
                "resolution": clip.resolution,
                "fps": clip.fps,
                "hdr": clip.hdr,
            }
        )

    json_frames: list[dict[str, object]] = []
    for i, frame_num in enumerate(data.frames):
        frame_images: list[dict[str, str]] = []
        for clip in data.clips:
            screenshot_path = data.screenshots[clip.name][i]

            if not screenshot_path.exists():
                raise ReportError(f"screenshot not found: {screenshot_path}")

            image_src: str
            if config.embed_images:
                try:
                    image_bytes = screenshot_path.read_bytes()
                    b64_str = base64.b64encode(image_bytes).decode("ascii")
                    image_src = f"data:image/png;base64,{b64_str}"
                except OSError as e:
                    raise ReportError(f"failed to encode image: {screenshot_path}") from e
            else:
                try:
                    # Use relative path for portability if possible
                    image_src = str(
                        Path(os_path_relpath(screenshot_path, final_output_path.parent)).as_posix()
                    )
                except ValueError:
                    # Fallback to absolute if on different drives (Windows)
                    image_src = str(screenshot_path.as_posix())

            frame_images.append(
                {
                    "clip": clip.name,
                    "src": image_src,
                }
            )

        json_frames.append(
            {
                "number": frame_num,
                "images": frame_images,
            }
        )

    embedded_data: dict[str, object] = {
        "version": REPORT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "title": data.metadata.title if data.metadata else data.clips[0].name,
        "slowpics_url": data.slowpics_url,
        "default_mode": config.default_mode.value,
        "stats": {
            "frame_count": len(data.frames),
            "clip_count": len(data.clips),
        },
        "clips": json_clips,
        "frames": json_frames,
    }

    # 5. GENERATE HTML
    html_content = _build_html(embedded_data, include_filmstrip=config.include_filmstrip)

    # 6. WRITE FILE
    try:
        final_output_path.parent.mkdir(parents=True, exist_ok=True)
        final_output_path.write_text(html_content, encoding="utf-8")
    except OSError as e:
        raise ReportError(f"failed to write report: {e}") from e

    return final_output_path


def os_path_relpath(path: Path, start: Path) -> str:
    """Wrapper for os.path.relpath to handle Path objects."""
    return os.path.relpath(path, start)


def _esc_text(value: object) -> str:
    """Escape dynamic text for safe HTML interpolation."""
    return html.escape(str(value), quote=False)


def _esc_attr(value: object) -> str:
    """Escape dynamic values for safe HTML attribute interpolation."""
    return html.escape(str(value), quote=True)


def _safe_http_href(url: str | None) -> str | None:
    """Return an escaped http(s) URL suitable for href, else None."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    return _esc_attr(url)


def _json_for_script_tag(data: dict[str, object]) -> str:
    """Serialize JSON safely for embedding inside a <script> tag.

    Escapes characters that can terminate the script tag or trigger HTML parsing.
    """
    raw = json.dumps(data)
    # Prevent </script> and other HTML parsing hazards inside the script element.
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _build_html(data: dict[str, object], include_filmstrip: bool = True) -> str:
    """Construct the full HTML string."""
    json_str = _json_for_script_tag(data)

    # CSS Content based on Spec Section 3
    css = """
    :root {
        --bg-primary: #0f1115;
        --bg-surface: #1a1d24;
        --bg-elevated: #242830;
        --bg-overlay: rgba(0, 0, 0, 0.7);
        --accent: #5ba4e6;
        --accent-hover: #7ab8f0;
        --accent-muted: rgba(91, 164, 230, 0.15);
        --text-primary: #f0f2f5;
        --text-secondary: rgba(240, 242, 245, 0.7);
        --text-muted: rgba(240, 242, 245, 0.5);
        --border: rgba(255, 255, 255, 0.08);
        --border-active: rgba(91, 164, 230, 0.5);
        --danger: #e55353;
        --success: #4caf50;
        --divider: #5ba4e6;

        --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif;
        --font-mono: "SF Mono", Monaco, "Cascadia Code", Consolas, monospace;
        --text-xs: 0.75rem;
        --text-sm: 0.875rem;
        --text-base: 1rem;
        --text-lg: 1.125rem;
        --text-xl: 1.5rem;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
        background: var(--bg-primary);
        color: var(--text-primary);
        font-family: var(--font-sans);
        height: 100vh;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    /* Layout */
    .rv-header {
        padding: 0.75rem 1.5rem;
        background: var(--bg-surface);
        border-bottom: 1px solid var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .rv-title { font-size: var(--text-lg); font-weight: 600; }
    .rv-meta { font-size: var(--text-sm); color: var(--text-secondary); }
    .rv-link { color: var(--accent); text-decoration: none; margin-left: 1rem; }
    .rv-link:hover { text-decoration: underline; }

    .rv-controls {
        padding: 0.5rem 1.5rem;
        background: var(--bg-surface);
        border-bottom: 1px solid var(--border);
        display: flex;
        gap: 1rem;
        align-items: center;
        flex-wrap: wrap;
    }

    .rv-control-group {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding-right: 1rem;
        border-right: 1px solid var(--border);
    }
    .rv-control-group:last-child { border-right: none; }

    button, select, input {
        background: var(--bg-elevated);
        border: 1px solid var(--border);
        color: var(--text-primary);
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-family: inherit;
        font-size: var(--text-sm);
        cursor: pointer;
    }

    button:hover, select:hover { background: var(--bg-elevated); border-color: var(--border-active); }
    button:active { background: var(--accent-muted); }
    button.active { background: var(--accent); color: white; border-color: var(--accent); }
    button:disabled { opacity: 0.5; cursor: not-allowed; }

    /* Viewer Stage */
    .rv-viewer-stage {
        flex: 1;
        position: relative;
        overflow: hidden;
        background: #000;
        display: flex;
        align-items: center;
        justify-content: center;
        user-select: none;
    }

    .rv-canvas {
        position: relative;
        display: inline-block;
        transform-origin: center center;
        transform: scale(var(--zoom-level, 1));
        box-shadow: 0 0 20px rgba(0,0,0,0.5);
    }

    /* The sizer image establishes canvas dimensions (layers are absolutely positioned). */
    .rv-sizer {
        display: block;
        max-width: 96vw;
        max-height: 100%;
        width: auto;
        height: auto;
        opacity: 0;
        pointer-events: none;
    }

    .rv-image {
        display: block;
        width: 100%;
        height: auto;
        pointer-events: none;
    }

    /* Viewer Modes */
    .rv-layer { position: absolute; inset: 0; }

    /* Slider Mode */
    .rv-mode-slider .rv-left {
        clip-path: inset(0 var(--reveal-percent, 50%) 0 0);
        z-index: 2;
    }
    .rv-mode-slider .rv-right { z-index: 1; }

    .rv-divider {
        display: none;
        position: absolute;
        top: 0; bottom: 0;
        left: calc(100% - var(--reveal-percent, 50%));
        width: 2px;
        background: var(--divider);
        cursor: ew-resize;
        z-index: 3;
        box-shadow: 0 0 4px rgba(0,0,0,0.5);
    }
    .rv-mode-slider .rv-divider { display: block; }

    /* Overlay Mode */
    .rv-mode-overlay .rv-layer { display: none; }
    .rv-mode-overlay .rv-layer.active { display: block; z-index: 2; }

    /* Difference Mode */
    .rv-mode-diff .rv-left { z-index: 1; }
    .rv-mode-diff .rv-right { z-index: 2; mix-blend-mode: difference; }

    /* Blink Mode */
    .rv-mode-blink .rv-layer { display: none; }
    .rv-mode-blink .rv-layer.active { display: block; z-index: 2; }

    /* Labels overlay */
    .rv-overlay-label {
        position: absolute;
        top: 10px; left: 10px;
        background: rgba(0, 0, 0, 0.7);
        padding: 4px 8px;
        border-radius: 4px;
        font-size: var(--text-sm);
        pointer-events: none;
        z-index: 10;
        border: 1px solid var(--border);
    }
    .rv-overlay-label.right { left: auto; right: 10px; text-align: right; }

    /* Modal */
    .rv-modal {
        display: none;
        position: fixed;
        inset: 0;
        background: var(--bg-overlay);
        z-index: 100;
        align-items: center;
        justify-content: center;
    }
    .rv-modal.open { display: flex; }

    .rv-modal-content {
        background: var(--bg-surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 2rem;
        max-width: 600px;
        width: 90%;
        box-shadow: 0 4px 24px rgba(0,0,0,0.5);
    }

    .rv-modal-title { font-size: var(--text-lg); font-weight: 600; margin-bottom: 1rem; }

    .rv-shortcuts-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 1rem;
    }

    .rv-shortcut-row {
        display: flex;
        justify-content: space-between;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border);
    }

    .rv-key {
        background: var(--bg-elevated);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 2px 6px;
        font-family: var(--font-mono);
        font-size: var(--text-xs);
    }

    /* Filmstrip */
    .rv-filmstrip {
        height: 100px;
        background: var(--bg-surface);
        border-top: 1px solid var(--border);
        display: flex;
        overflow-x: auto;
        padding: 10px;
        gap: 10px;
    }

    .rv-filmstrip-item {
        flex: 0 0 auto;
        width: 80px;
        border: 2px solid transparent;
        border-radius: 4px;
        overflow: hidden;
        position: relative;
        cursor: pointer;
        background: black;
        padding: 0;
    }

    .rv-filmstrip-item.active { border-color: var(--accent); }
    .rv-filmstrip-item img { width: 100%; height: 100%; object-fit: cover; opacity: 0.7; }
    .rv-filmstrip-item.active img { opacity: 1; }

    .rv-filmstrip-label {
        position: absolute;
        bottom: 0; left: 0; right: 0;
        background: rgba(0,0,0,0.7);
        color: white;
        font-size: var(--text-xs);
        padding: 2px 4px;
        text-align: center;
    }

    /* Footer */
    .rv-footer {
        padding: 0.5rem 1.5rem;
        background: var(--bg-surface);
        border-top: 1px solid var(--border);
        font-size: var(--text-xs);
        color: var(--text-muted);
        display: flex;
        justify-content: space-between;
    }

    /* Responsive */
    @media (max-width: 768px) {
        .rv-controls { flex-direction: column; align-items: stretch; }
        .rv-control-group { border-right: none; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
        .rv-control-group:last-child { border-bottom: none; }
    }
    """

    # JS Content based on Spec Section 4-11 & Appendix B
    js = """
    const ReportViewer = {
        state: {
            data: null,
            currentFrameIdx: 0,
            leftClipIdx: 0,
            rightClipIdx: 1,
            activeClipIdx: 0, // For overlay/blink
            mode: 'slider',
            zoom: 1.0,
            revealPercent: 50,
            blinkInterval: null,
            blinkPaused: false
        },

                init() {
                    try {
                        const scriptTag = document.getElementById('report-data');
                        this.state.data = JSON.parse(scriptTag.textContent);
                        this.state.mode = this.state.data.default_mode || 'slider';

                        this.cacheDOM();
                        this.bindEvents();
                        this.setMode(this.state.mode); // Apply default mode UI state
                        this.render();
                        this.preloadImages();
                    } catch (e) {
                        console.error("Failed to initialize viewer:", e);
                        alert("Failed to load report data.");
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
                        zoomRange: document.getElementById('zoom-range'),
                        zoomVal: document.getElementById('zoom-val'),
                        filmstrip: document.querySelector('.rv-filmstrip'),
                        labelLeft: document.getElementById('label-left'),
                        labelRight: document.getElementById('label-right'),
                        modal: document.getElementById('help-modal'),
                        btnHelp: document.getElementById('btn-help'),
                        btnCloseHelp: document.getElementById('btn-close-help'),
                    };
                },

                bindEvents() {
                    // Mode switching
                    this.dom.modeBtns.forEach(btn => {
                        btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
                    });

                    // Frame Navigation
                    this.dom.btnPrev.addEventListener('click', () => this.prevFrame());
                    this.dom.btnNext.addEventListener('click', () => this.nextFrame());
                    this.dom.frameSelect.addEventListener('change', (e) => this.setFrame(parseInt(e.target.value)));

                    // Clip Selection
                    this.dom.leftSelect.addEventListener('change', (e) => {
                        this.state.leftClipIdx = parseInt(e.target.value);
                        this.state.activeClipIdx = this.state.leftClipIdx; // For overlay sync
                        this.render();
                    });
                    this.dom.rightSelect.addEventListener('change', (e) => {
                        this.state.rightClipIdx = parseInt(e.target.value);
                        this.render();
                    });

                    // Zoom
                    this.dom.zoomRange.addEventListener('input', (e) => this.setZoom(parseFloat(e.target.value)));
                    document.getElementById('btn-zoom-out').addEventListener('click', () => this.setZoom(this.state.zoom - 0.1));
                    document.getElementById('btn-zoom-in').addEventListener('click', () => this.setZoom(this.state.zoom + 0.1));
                    document.getElementById('btn-zoom-reset').addEventListener('click', () => this.setZoom(1.0));

                    // Help Modal
                    const openModal = () => {
                        this.dom.modal.classList.add('open');
                        this.dom.modal.setAttribute('aria-hidden', 'false');
                        this.dom.btnCloseHelp.focus();
                    };
                    const closeModal = () => {
                        this.dom.modal.classList.remove('open');
                        this.dom.modal.setAttribute('aria-hidden', 'true');
                        this.dom.btnHelp.focus();
                    };

                    this.dom.btnHelp.addEventListener('click', openModal);
                    this.dom.btnCloseHelp.addEventListener('click', closeModal);
                    this.dom.modal.addEventListener('click', (e) => {
                        if (e.target === this.dom.modal) closeModal();
                    });

                    // Focus Trap
                    this.dom.modal.addEventListener('keydown', (e) => {
                        if (e.key === 'Tab') {
                            // Simple trap since only one button is interactive in MVP modal
                            e.preventDefault();
                            this.dom.btnCloseHelp.focus();
                        }
                        if (e.key === 'Escape') {
                            closeModal();
                        }
                    });

                    // Slider Drag
                    let isDragging = false;
                    const handleMove = (e) => {
                        if (!isDragging && this.state.mode !== 'slider') return;

                        // Allow click-to-set for slider even if not dragging divider
                        if (!isDragging && e.type === 'mousemove') return;

                        const rect = this.dom.stage.getBoundingClientRect();
                        const x = (e.clientX || e.touches[0].clientX) - rect.left;
                        let percent = (1 - (x / rect.width)) * 100;
                        percent = Math.max(0, Math.min(100, percent));

                        this.state.revealPercent = percent;
                        this.updateSlider();
                    };

                    this.dom.divider.addEventListener('mousedown', () => isDragging = true);
                    this.dom.stage.addEventListener('mousedown', (e) => {
                        if (this.state.mode === 'slider') {
                            isDragging = true;
                            handleMove(e);
                        } else if (this.state.mode === 'overlay' || this.state.mode === 'diff') {
                             // Click to swap/cycle in overlay/diff
                             this.cycleClip();
                        } else if (this.state.mode === 'blink') {
                             // Pause blink on hold
                             this.state.blinkPaused = true;
                        }
                    });

                    window.addEventListener('mouseup', () => {
                        isDragging = false;
                        if (this.state.mode === 'blink') this.state.blinkPaused = false;
                    });
                    window.addEventListener('mousemove', (e) => {
                        if (isDragging) handleMove(e);
                    });

                    // Filmstrip
                    this.dom.filmstrip.addEventListener('click', (e) => {
                        const item = e.target.closest('.rv-filmstrip-item');
                        if (item) this.setFrame(parseInt(item.dataset.idx));
                    });

                    // Keyboard
                    document.addEventListener('keydown', (e) => this.handleKey(e));
                },

                handleKey(e) {
                    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

                    // Modal handling via global keydown if not caught by focus trap
                    if (this.dom.modal.classList.contains('open')) return;

                    if (e.key === '?' || (e.key === '/' && e.shiftKey)) {
                        this.dom.btnHelp.click();
                        return;
                    }
                            switch(e.key) {
                        case 'ArrowLeft': this.prevFrame(); break;
                        case 'ArrowRight': this.nextFrame(); break;
                        case 'Home': this.setFrame(0); break;
                        case 'End': this.setFrame(this.state.data.frames.length - 1); break;

                        case 'ArrowUp': this.cycleClip(1); break;
                        case 'ArrowDown': this.cycleClip(-1); break;

                        case 's': case 'S': this.setMode('slider'); break;
                        case 'o': case 'O': this.setMode('overlay'); break;
                        case 'd': case 'D': this.setMode('diff'); break;
                        case 'b': case 'B': this.setMode('blink'); break;

                        case '=': case '+': this.setZoom(this.state.zoom + 0.1); break;
                        case '-': this.setZoom(this.state.zoom - 0.1); break;
                        case 'r': case 'R': this.setZoom(1.0); break;

                        default:
                            if (e.key >= '1' && e.key <= '9') {
                                const idx = parseInt(e.key) - 1;
                                if (idx < this.state.data.clips.length) {
                                     if (this.state.mode === 'slider') this.state.leftClipIdx = idx;
                                     else if (this.state.mode === 'diff') this.state.rightClipIdx = idx;
                                     else this.state.activeClipIdx = idx;
                                     this.render();
                                }
                            }
                    }
                },

                setMode(mode) {
                    this.state.mode = mode;

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
                    this.render();
                },

                startBlink() {
                    this.state.blinkInterval = setInterval(() => {
                        if (this.state.blinkPaused) return;

                        // Toggle between left and right clip indices for blink
                        // Usually blink compares two, but can cycle. Spec says:
                        // "activeClipIndex: number", "cycle through clips"
                        // Let's cycle activeClip between left and right selected for MVP simplicity
                        // or cycle through all? Spec 4.4 says "activeIndex = (activeIndex + 1) % clipCount"

                        this.state.activeClipIdx = (this.state.activeClipIdx + 1) % this.state.data.clips.length;
                        this.updateImages();

                    }, 700);
                },

                setFrame(idx) {
                    if (idx < 0 || idx >= this.state.data.frames.length) return;
                    this.state.currentFrameIdx = idx;
                    this.render();

                    // Scroll filmstrip
                    const item = this.dom.filmstrip.children[idx];
                    if (item) item.scrollIntoView({ behavior: 'smooth', inline: 'center' });
                },

                nextFrame() { this.setFrame(this.state.currentFrameIdx + 1); },
                prevFrame() { this.setFrame(this.state.currentFrameIdx - 1); },

                cycleClip(direction = 1) {
                    const count = this.state.data.clips.length;
                    if (this.state.mode === 'slider') {
                        // Cycle left clip
                        this.state.leftClipIdx = (this.state.leftClipIdx + direction + count) % count;
                        this.dom.leftSelect.value = this.state.leftClipIdx;
                    } else if (this.state.mode === 'diff') {
                        // Cycle right (compare) clip
                        this.state.rightClipIdx = (this.state.rightClipIdx + direction + count) % count;
                        this.dom.rightSelect.value = this.state.rightClipIdx;
                    } else {
                        this.state.activeClipIdx = (this.state.activeClipIdx + direction + count) % count;
                    }
                    this.render();
                },

                setZoom(level) {
                    this.state.zoom = Math.max(0.25, Math.min(2.0, level));
                    this.dom.zoomRange.value = this.state.zoom;
                    this.dom.zoomRange.setAttribute('aria-valuenow', this.state.zoom);
                    this.dom.zoomVal.textContent = Math.round(this.state.zoom * 100) + '%';
                    this.dom.canvas.style.setProperty('--zoom-level', this.state.zoom);
                },

                updateSlider() {
                    this.dom.leftLayer.style.setProperty('--reveal-percent', this.state.revealPercent + '%');
                    this.dom.divider.style.setProperty('--reveal-percent', this.state.revealPercent + '%');
                },

                updateImages() {
                    const frameData = this.state.data.frames[this.state.currentFrameIdx];
                    if (!frameData) return;

                    let leftSrc, rightSrc;
                    let leftLabelTxt, rightLabelTxt;

                    if (this.state.mode === 'slider' || this.state.mode === 'diff') {
                        leftSrc = frameData.images[this.state.leftClipIdx].src;
                        rightSrc = frameData.images[this.state.rightClipIdx].src;

                        const leftClip = this.state.data.clips[this.state.leftClipIdx];
                        const rightClip = this.state.data.clips[this.state.rightClipIdx];
                        leftLabelTxt = `${leftClip.label} (Left)`;
                        rightLabelTxt = `${rightClip.label} (Right)`;

                        // For Diff mode, right layer is the "compare" one which gets difference blend
                        // Left layer is base.

                    } else {
                        // Overlay or Blink - show activeClip
                        // We use left layer as the main visible one for these modes
                        leftSrc = frameData.images[this.state.activeClipIdx].src;
                        // Right unused/hidden
                        rightSrc = frameData.images[(this.state.activeClipIdx + 1) % this.state.data.clips.length].src; // Preload next?

                        const activeClip = this.state.data.clips[this.state.activeClipIdx];
                        leftLabelTxt = activeClip.label;
                        rightLabelTxt = "";
                    }

                    if (this.dom.leftImg.getAttribute('src') !== leftSrc) {
                        if (this.dom.sizerImg && this.dom.sizerImg.getAttribute('src') !== leftSrc) {
                            this.dom.sizerImg.src = leftSrc;
                        }
                        this.dom.leftImg.src = leftSrc;
                        // Alt text update
                        const clipName = (this.state.mode === 'overlay' || this.state.mode === 'blink')
                            ? this.state.data.clips[this.state.activeClipIdx].label
                            : this.state.data.clips[this.state.leftClipIdx].label;
                        this.dom.leftImg.alt = `${clipName} - Frame ${frameData.number}`;
                    }
                    if (this.dom.rightImg.getAttribute('src') !== rightSrc) {
                        this.dom.rightImg.src = rightSrc;
                        // Alt text update for right image (only relevant in split modes)
                        const clipName = this.state.data.clips[this.state.rightClipIdx].label;
                        this.dom.rightImg.alt = `${clipName} - Frame ${frameData.number}`;
                    }

                    this.dom.labelLeft.textContent = leftLabelTxt;
                    this.dom.labelRight.textContent = rightLabelTxt;

                    // Toggle visibility classes based on mode logic in CSS
                    if (this.state.mode === 'overlay' || this.state.mode === 'blink') {
                         this.dom.leftLayer.classList.add('active');
                         this.dom.rightLayer.classList.remove('active');
                    }
                },
                render() {
            // Update controls
            this.dom.frameSelect.value = this.state.currentFrameIdx;
            this.dom.btnPrev.disabled = this.state.currentFrameIdx === 0;
            this.dom.btnNext.disabled = this.state.currentFrameIdx === this.state.data.frames.length - 1;

            this.dom.leftSelect.value = this.state.leftClipIdx;
            this.dom.rightSelect.value = this.state.rightClipIdx;

            // Update images and labels
            this.updateImages();
            this.updateSlider();
            this.setZoom(this.state.zoom);

            // Update filmstrip active state
            Array.from(this.dom.filmstrip.children).forEach((el, idx) => {
                el.classList.toggle('active', idx === this.state.currentFrameIdx);
                el.setAttribute('aria-current', idx === this.state.currentFrameIdx);
            });
        },

        preloadImages() {
             // Basic preload of next few frames
             // Implementation omitted for MVP brevity, browser handles lazy loading
        }
    };

    document.addEventListener('DOMContentLoaded', () => ReportViewer.init());
    """

    # Assemble HTML
    # Note: We trust the data structure matches spec, but for Pyright strictness
    # we would need deeper typing. For now, we assume the dict structure is correct.
    # To satisfy strict mode without massive TypedDict definitions, we cast where needed.
    title = cast(str, data["title"])
    generated_at = cast(str, data["generated_at"])
    stats = cast(dict[str, int], data["stats"])
    slowpics_url = cast(str | None, data.get("slowpics_url"))
    frames = cast(list[dict[str, object]], data["frames"])
    clips = cast(list[dict[str, object]], data["clips"])
    safe_href = _safe_http_href(slowpics_url)

    return f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{_esc_text(title)} - Frame Compare Report</title>
        <style>{css}</style>
    </head>
    <body>
        <header class="rv-header">
            <div>
                <div class="rv-title">{_esc_text(title)}</div>
                <div class="rv-meta">Generated {_esc_text(generated_at)} • {
        stats["frame_count"]
    } frames • {stats["clip_count"]} clips</div>
            </div>
            <div>
                {
        f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer" class="rv-link">View on slow.pics ↗</a>'
        if safe_href
        else ""
    }
            </div>
        </header>

    <div class="rv-controls" role="toolbar" aria-label="Viewer controls">
        <div class="rv-control-group">
                <button id="btn-prev" aria-label="Previous frame">←</button>
                <select id="frame-select" aria-label="Select frame">
                    {
        "".join(
            f'<option value="{_esc_attr(i)}">Frame {_esc_text(f["number"])}</option>'
            for i, f in enumerate(frames)
        )
    }
                </select>
                <button id="btn-next" aria-label="Next frame">→</button>
            </div>

            <div class="rv-control-group">
                <select id="left-select" aria-label="Left clip">
                    {
        "".join(
            f'<option value="{_esc_attr(i)}">{_esc_text(c["label"])}</option>'
            for i, c in enumerate(clips)
        )
    }
                </select>
                <select id="right-select" aria-label="Right clip">
                    {
        "".join(
            f'<option value="{_esc_attr(i)}" {"selected" if i == 1 else ""}>{_esc_text(c["label"])}</option>'
            for i, c in enumerate(clips)
        )
    }
                </select>
            </div>

        <div class="rv-control-group" role="radiogroup" aria-label="View mode">
            <button data-mode="slider" class="active" role="radio" aria-checked="true" aria-label="Slider mode" title="Slider (S)">⊟</button>
            <button data-mode="overlay" role="radio" aria-checked="false" aria-label="Overlay mode" title="Overlay (O)">◐</button>
            <button data-mode="diff" role="radio" aria-checked="false" aria-label="Difference mode" title="Difference (D)">◑</button>
            <button data-mode="blink" role="radio" aria-checked="false" aria-label="Blink mode" title="Blink (B)">◫</button>
        </div>

        <div class="rv-control-group">
            <button id="btn-zoom-out" aria-label="Zoom out">-</button>
            <input type="range" id="zoom-range" min="0.25" max="2.0" step="0.1" value="1.0" aria-label="Zoom level" aria-valuemin="0.25" aria-valuemax="2.0" aria-valuenow="1.0">
            <button id="btn-zoom-in" aria-label="Zoom in">+</button>
            <button id="btn-zoom-reset" aria-label="Reset zoom">R</button>
            <span id="zoom-val" style="font-size: var(--text-xs); width: 3ch">100%</span>
        </div>

        <div class="rv-control-group">
             <button id="btn-help" aria-label="Keyboard shortcuts" title="Help (?)">?</button>
        </div>
    </div>

    <div class="rv-viewer-stage rv-mode-slider" role="img" aria-label="Comparison viewer">
        <div class="rv-canvas">
            <img src="" alt="" class="rv-sizer" aria-hidden="true">
            <div class="rv-layer rv-left">
                <img src="" alt="" class="rv-image">
                <div id="label-left" class="rv-overlay-label"></div>
            </div>
            <div class="rv-layer rv-right">
                <img src="" alt="" class="rv-image">
                <div id="label-right" class="rv-overlay-label right"></div>
            </div>
            <div class="rv-divider"></div>
        </div>
    </div>

    <div id="help-modal" class="rv-modal" aria-hidden="true" role="dialog" aria-label="Keyboard Shortcuts">
        <div class="rv-modal-content">
            <div class="rv-modal-title">Keyboard Shortcuts</div>
            <div class="rv-shortcuts-grid">
                <div class="rv-shortcut-row"><span>Previous Frame</span><span class="rv-key">←</span></div>
                <div class="rv-shortcut-row"><span>Next Frame</span><span class="rv-key">→</span></div>
                <div class="rv-shortcut-row"><span>First / Last Frame</span><span class="rv-key">Home / End</span></div>
                <div class="rv-shortcut-row"><span>Cycle Clip</span><span class="rv-key">↑ / ↓</span></div>
                <div class="rv-shortcut-row"><span>Direct Clip Select</span><span class="rv-key">1 - 9</span></div>
                <div class="rv-shortcut-row"><span>Modes (Slider/Overlay/Diff/Blink)</span><span class="rv-key">S / O / D / B</span></div>
                <div class="rv-shortcut-row"><span>Zoom In / Out</span><span class="rv-key">+ / -</span></div>
                <div class="rv-shortcut-row"><span>Reset Zoom</span><span class="rv-key">R</span></div>
                <div class="rv-shortcut-row"><span>Close Help</span><span class="rv-key">Esc</span></div>
            </div>
            <div style="margin-top: 1rem; text-align: right;">
                <button id="btn-close-help">Close</button>
            </div>
        </div>
    </div>

        {
        f'''
        <nav class="rv-filmstrip" role="navigation" aria-label="Frame thumbnails">
            {
            "".join(
                f"""
            <button class="rv-filmstrip-item" data-idx="{_esc_attr(i)}" aria-label="Frame {_esc_attr(f["number"])}">
                <img src="{_esc_attr(cast(list[dict[str, object]], f["images"])[0]["src"])}" loading="lazy" alt="{_esc_attr(cast(str, clips[0]["label"]))} - Frame {_esc_attr(f["number"])}">
                <span class="rv-filmstrip-label">{_esc_text(f["number"])}</span>
            </button>
            """
                for i, f in enumerate(frames)
            )
        }
        </nav>
        '''
        if include_filmstrip
        else ""
    }

    <footer class="rv-footer">
        <div>Frame Compare v{REPORT_VERSION}</div>
        <div>Use arrow keys to navigate • S/O/D/B to change mode</div>
    </footer>

    <script type="application/json" id="report-data">{json_str}</script>
    <script>{js}</script>
</body>
</html>"""
