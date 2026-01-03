# Render Module Implementation Spec

> **Module:** `frame_compare.render`
> **Version:** 1.0
> **Priority:** P0

---

## 1. Module Overview

The Render module handles screenshot generation from video frames, including image encoding, overlay rendering, and file naming.

### 1.1 Responsibilities

- Extract individual frames as images
- Apply overlay text/graphics
- Encode to PNG format
- Manage output file naming
- Coordinate with FFmpeg fallback

### 1.2 Module Structure

```text
src/frame_compare/render/
├── __init__.py          # Public exports
├── encoders.py          # Image encoding (PNG)
├── geometry.py          # Dimension calculations
├── naming.py            # File naming conventions
├── overlay.py           # Text overlay rendering
└── orchestrator.py      # Multi-clip screenshot workflow
```

### 1.3 Screenshots-Only Mode (--skip-analysis)

> [!IMPORTANT]
> When analysis is skipped via `--skip-analysis`, frame selection uses the canonical **FramePlan** contract with deterministic blake2s-based selection.

**Canonical Algorithm Reference:**

The `FramePlan` contract and `select_uniform_seeded_frames()` algorithm are defined in:

- Spec: `frame-plan-module.md` §4 (Algorithm Specification)
- Target implementation path: `src/frame_compare/analysis/frame_plan.py`

The algorithm partitions frames into bins and selects one frame per bin using a blake2s hash for reproducibility.

**Key Properties:**

- **Frame indices:** 0-based, in `[0, num_frames - 1]`
- **Deterministic:** Same `(num_frames, count, seed)` → same frames
- **Contract enforced:** `FramePlan.frames` is always a concrete `list[int]`; render phase MUST NOT reselect frames

**Error Handling:**

- If video has fewer frames than `frame_count`: raise `InsufficientFramesError(FC-3004)`

### 1.4 HDR Tonemap Wiring (Auto-Tonemap for HDR → SDR)

> [!IMPORTANT]
> When an HDR source is detected and tonemapping is enabled, the render pipeline MUST apply tonemapping
> before frame extraction. This ensures SDR screenshots are produced for fair visual comparisons.

**Canonical Reference:**

- Tonemap implementation: [vs-module.md §3.3](vs-module.md#33-tonemapping)
- Settings resolution: [vs-module.md §4](vs-module.md#4-tonemap-presets)

#### 1.4.1 Gating Rule (Deterministic)

Tonemapping is applied if and only if **ALL** of the following conditions are true:

```python
def should_tonemap(source_info: SourceInfo, config: ConfigSchema) -> bool:
    """Determine if tonemap MUST be applied.

    Args:
        source_info: Loaded source metadata from VSLoader
        config: Resolved configuration

    Returns:
        True if tonemap MUST be applied
    """
    return (
        source_info.is_hdr                    # Source is HDR (PQ/HLG + BT.2020)
        and config.color.enable_tonemap       # User has not disabled tonemapping
    )
```

**Gating inputs:**

| Input | Source | Type | Description |
|:------|:-------|:-----|:------------|
| `source_info.is_hdr` | `vs.SourceInfo` after load | `bool` | True if `_Transfer in (16, 18) AND _Primaries == 9` |
| `config.color.enable_tonemap` | Config schema | `bool` | Default `True`; user override via config (CLI override supported once Phase 6 wiring consumes CLI flags) |

#### 1.4.2 Settings Resolution

When tonemapping is triggered, resolve `TonemapSettings` using this priority order:

1. **CLI overrides** (`--tm-preset`, `--tm-target`, `--tm-curve`) → highest priority
2. **Config file** (`config.color.preset`, `config.color.target_nits`, `config.color.tone_curve`)
3. **Preset defaults** via `get_preset_settings(preset_name)`

```python
def resolve_tonemap_settings(config: ConfigSchema, cli_overrides: dict | None = None) -> TonemapSettings:
    """Resolve tonemap settings from config and CLI overrides.

    Args:
        config: Resolved configuration
        cli_overrides: Optional CLI flag overrides (tm_preset, tm_target, tm_curve)

    Returns:
        Complete TonemapSettings ready for apply_tonemap()
    """
    # Start with preset
    preset_name = (cli_overrides or {}).get("tm_preset") or config.color.preset or "reference"
    settings = get_preset_settings(preset_name)

    # Apply config overrides
    if config.color.target_nits is not None:
        settings = replace(settings, target_nits=config.color.target_nits)
    if config.color.tone_curve is not None:
        settings = replace(settings, tone_curve=config.color.tone_curve)

    # Apply CLI overrides (highest priority)
    if cli_overrides:
        if cli_overrides.get("tm_target") is not None:
            settings = replace(settings, target_nits=cli_overrides["tm_target"])
        if cli_overrides.get("tm_curve") is not None:
            settings = replace(settings, tone_curve=cli_overrides["tm_curve"])

    return settings
```

#### 1.4.3 Integration Point

Tonemapping is applied **after loading, before any frame extraction or encoding**.

**Pipeline position:**

```
Load Source → Detect HDR → Apply Tonemap (if gated) → Extract Frames → Apply Overlay → Encode PNG
```

**Exact integration in `render_screenshots`:**

```python
def render_screenshots(
    clips: list[Path],
    frames: list[int],
    output_dir: Path,
    config: ConfigSchema,  # ADDED: config required for tonemap gating
    label_map: dict[Path, str] | None = None,
    renderer: Renderer = "auto",
    overlay_mode: OverlayMode = OverlayMode.STANDARD,
    reporter: ProgressReporter | None = None,
) -> dict[str, list[Path]]:
    for clip_path in clips:
        label = (label_map or {}).get(clip_path, clip_path.stem)
        source_info = loader.load(clip_path)
        clip = source_info.clip

        # === TONEMAP INTEGRATION POINT ===
        if should_tonemap(source_info, config):
            settings = resolve_tonemap_settings(config)
            clip = apply_tonemap(clip, settings, source_info.hdr_metadata)
            # Mark that tonemap was applied for overlay
            tonemapped = True
        else:
            tonemapped = False

        # Continue with frame extraction using (possibly tonemapped) clip
        for frame in frames:
            overlay = OverlayConfig(
                mode=overlay_mode,
                label=label,
                frame_number=frame,
                resolution=(source_info.width, source_info.height),
                hdr_info=hdr_info,
                font_path=None,
            )
            request = RenderRequest(
                clip=clip,
                frame_number=frame,
                output_path=generate_screenshot_path(output_dir, label, frame),
                overlay=overlay,
                encoder_settings=EncoderSettings(),
            )
            render_frame(request)
```

#### 1.4.4 Failure Policy

**HDR source + tonemap required + VS unavailable:**

> [!CAUTION]
> If an HDR source requires tonemapping but VapourSynth is not available,
> the renderer MUST fail fast. Do NOT silently fall back to FFmpeg for HDR sources
> as this produces incorrect SDR conversions.

| Scenario | Renderer | Behavior |
|:---------|:---------|:---------|
| HDR source, `enable_tonemap=True`, VS available | vapoursynth/auto | Apply tonemap, render |
| HDR source, `enable_tonemap=True`, VS available but libplacebo missing/unusable | vapoursynth/auto | Apply tonemap via fallback path inside `apply_tonemap()`, render |
| HDR source, `enable_tonemap=True`, VS unavailable | auto | Raise `RenderError(FC-4004)` with hint |
| HDR source, `enable_tonemap=True`, VS unavailable | ffmpeg | Raise `RenderError(FC-4004)` with hint |
| HDR source, `enable_tonemap=False` | any | Render without tonemap (user accepts wrong colors) |
| SDR source | any | No tonemap, render normally |

**Exception specification:**

```python
raise RenderError(
    code="FC-4004",
    message="Cannot tonemap HDR source: VapourSynth is required but not available",
    hint="Install VapourSynth with libplacebo, or set enable_tonemap=false to skip tonemapping (not recommended for accurate comparisons)",
)
```

**Tonemap function failure:**

- If `apply_tonemap()` raises `TonemapError`, propagate it to the caller. Do not catch and continue.
- If libplacebo is unavailable or fails at runtime, `apply_tonemap()` MUST use its deterministic fallback algorithm
  (no silent bypass of tonemap for HDR sources when tonemap is required).

#### 1.4.5 Determinism Guarantee

Given identical inputs, tonemapping MUST produce identical outputs:

- Same `SourceInfo` (same file, same frame props)
- Same `TonemapSettings` (same preset, nits, curve)
- Same VapourSynth environment (same libplacebo version)

**Testing assertion:**

```python
def test_tonemap_determinism():
    # Marker policy: this test MUST be gated with @pytest.mark.vs_required
    clip1 = apply_tonemap(source.clip, settings)
    clip2 = apply_tonemap(source.clip, settings)
    # Frame N from clip1 == Frame N from clip2 (byte-identical)
```

#### 1.4.6 Overlay/HDR Info Policy

When rendering overlays, the `OverlayConfig.hdr_info` field MUST reflect the source and tonemap state:

| Scenario | `hdr_info` Value |
|:---------|:-----------------|
| HDR source, tonemapped | `"HDR (tonemapped: {preset}, {target_nits} nits)"` |
| HDR source, tonemap disabled | `"HDR (native, no tonemap)"` |
| SDR source | `None` or `"SDR"` |

**Format string (SSOT):**

```python
if source_info.is_hdr and tonemapped:
    hdr_info = f"HDR (tonemapped: {settings.preset}, {settings.target_nits} nits)"
elif source_info.is_hdr:
    hdr_info = "HDR (native, no tonemap)"
else:
    hdr_info = None  # or "SDR" in DIAGNOSTIC mode
```

This information appears in `DIAGNOSTIC` overlay mode only.

---

## 2. Key Types

### 2.0 OverlayMode

```python
class OverlayMode(str, Enum):
    """Overlay verbosity level."""
    MINIMAL = "minimal"      # Label only
    STANDARD = "standard"    # Label + frame + resolution
    DIAGNOSTIC = "diagnostic" # Standard + HDR info
```

### 2.1 RenderRequest

```python
@dataclass
class RenderRequest:
    """Single frame render job"""
    clip: vs.VideoNode | Path  # VS clip or file path (FFmpeg)
    frame_number: int
    output_path: Path
    overlay: OverlayConfig | None
    encoder_settings: EncoderSettings

@dataclass
class EncoderSettings:
    format: str = "png"
    compression: int = 6  # PNG compression 0-9
    bit_depth: int = 8
```

**Example construction:**

```python
settings = EncoderSettings()
settings = EncoderSettings(format="png", compression=9, bit_depth=16)

request = RenderRequest(
    clip=Path("video.mkv"),
    frame_number=0,
    output_path=Path("frame_00000.png"),
    overlay=None,
    encoder_settings=EncoderSettings(),
)
```

### 2.2 OverlayConfig

```python
@dataclass
class OverlayConfig:
    mode: OverlayMode  # minimal, standard, diagnostic
    label: str         # Video label
    frame_number: int
    resolution: tuple[int, int]
    hdr_info: str | None
    font_path: Path | None
    font_size: int = 24
    position: str = "top-left"  # top-left, top-right, bottom-left, bottom-right

Renderer = Literal["vapoursynth", "ffmpeg", "auto"]
```

**Example construction:**

```python
overlay = OverlayConfig(
    mode=OverlayMode.STANDARD,
    label="Reference",
    frame_number=100,
    resolution=(1920, 1080),
    hdr_info=None,
    font_path=None,
)

overlay = OverlayConfig(
    mode=OverlayMode.DIAGNOSTIC,
    label="Encode",
    frame_number=100,
    resolution=(3840, 2160),
    hdr_info="PQ / BT.2020",
    font_path=Path("/fonts/mono.ttf"),
    font_size=32,
    position="bottom-right",
)
```

### 2.3 ScreenshotResult

```python
@dataclass(frozen=True)
class ScreenshotResult:
    """Result of a batch screenshot operation."""
    label: str              # Video label
    paths: list[Path]       # List of generated screenshot paths
    frame_count: int        # Number of frames rendered
```

**Example construction:**

```python
result = ScreenshotResult(
    label="Reference",
    paths=[Path("Reference_00100.png"), Path("Reference_00200.png")],
    frame_count=2,
)
```

### 2.4 ProgressReporter

```python
class ProgressReporter(Protocol):
    """Protocol for reporting progress."""
    def start_phase(self, name: str, total: int) -> None:
        raise NotImplementedError

    def set_description(self, text: str) -> None:
        raise NotImplementedError

    def advance(self, count: int = 1) -> None:
        raise NotImplementedError

    def complete_phase(self) -> None:
        raise NotImplementedError
```

---

## 3. Public API

### 3.1 Frame Rendering

```python
def render_frame(
    request: RenderRequest,
    renderer: Renderer = "auto",
) -> Path:
    """
    Render a single frame to image file.

    Args:
        request: Render configuration
        renderer: "vapoursynth", "ffmpeg", or "auto"

    Returns:
        Path to rendered image

    Raises:
        RenderError: If rendering fails
        FrameExtractionError: If renderer requires vs.VideoNode but Path usage detected (or vice versa)

    Behavior:
    - Dispatch based on `renderer` and `request.clip` type:
      - `vapoursynth`: Requires `vs.VideoNode`; calls `_render_vs`. Raises `FrameExtractionError` if `request.clip` is Path.
      - `ffmpeg`: Requires `Path`; calls `_render_ffmpeg`. Raises `FrameExtractionError` if `request.clip` is VideoNode.
      - `auto`: Inspects `request.clip`. If `vs.VideoNode` → `_render_vs`. If `Path` → `_render_ffmpeg`.
    - Overlay Integration:
      - If `request.overlay` is not None, `apply_overlay` is called before final save in both render paths.
    """

```python
def render_batch(
    requests: list[RenderRequest],
    parallelism: int = 1,
    reporter: ProgressReporter | None = None,
) -> list[Path]:
    """
    Render multiple frames with progress reporting.

    ordering contract: Result list matches input `requests` order.
    exception contract: Fail-fast. Raises the first encountered exception immediately; no new tasks MUST be started after the first exception is observed.

    Progress integration:
    - Call reporter.start_phase("Rendering", len(requests)) before loop
    - Call reporter.set_description(f"Frame {req.frame_number}") for current frame
    - Call reporter.advance(1) after each frame completes
    - Call reporter.complete_phase() after all frames rendered
    """

def render_screenshots(
    clips: list[Path],
    frames: list[int],
    output_dir: Path,
    label_map: dict[Path, str] | None = None,
    renderer: Renderer = "auto",
    overlay_mode: OverlayMode = OverlayMode.STANDARD,
    reporter: ProgressReporter | None = None,
) -> dict[str, list[Path]]:
    """
    Render the full screenshot set for multiple clips and frames.

    Determinism:
    - Process clips in provided list order.
    - Process frames in provided list order (ascending or otherwise).
    - Result dict keys strictly match input clips' resolved labels.

    Overlay Policy:
    - If `overlay_mode` is MINIMAL/STANDARD/DIAGNOSTIC:
      - Construct `OverlayConfig` for each request.
      - For VideoNode clips: use `clip.width`, `clip.height`.
      - For Path clips: use `(0, 0)` for resolution (unless probed).
    - If `overlay_mode` is None (conceptually, though enum implies always set):
      - Pass `overlay=None`.

    Loading Strategy (Auto/VS):
    - If `renderer="vapoursynth"` or `"auto"`, attempt to load clip using `frame_compare.vs.loader.DefaultVSLoader`.
    - If loading fails and renderer="auto", fallback to FFmpeg Path-based rendering (log warning; no exception raised).
    - If renderer="vapoursynth" and loading fails:
      - Propagate `VapourSynthNotFoundError (FC-2001)` if vapoursynth module is missing.
      - Propagate `PluginNotFoundError (FC-2003)` if required VS plugin is missing.
      - Propagate `SourceLoadError (FC-4015)` if loader fails (e.g. invalid script).
      - Wrap any other exception into `RenderError (FC-4004)` with original exception as `__cause__`.

    Responsibilities:
    - Resolve labels for naming/overlays
    - Generate `RenderRequest`s for every (clip, frame) pair
    - Delegate actual rendering to `render_batch`
    - Return a mapping of label -> rendered image paths
    """
```

### 3.2 Overlay

```python
def apply_overlay(
    image: PIL.Image | np.ndarray,
    config: OverlayConfig,
) -> PIL.Image:
    """
    Apply text overlay to image.

    Renders semi-transparent background with text.
    """
```

#### 3.2.1 `apply_overlay` Behavior

**Algorithm:**

1. Convert input to `PIL.Image.Image` if numpy array is provided.
2. Generate text string based on `config.mode`:
   - `MINIMAL`: `"{label}"`
   - `STANDARD`: `"{label} | Frame {frame_number:05d} | {width}x{height}"`
   - `DIAGNOSTIC`: `"{label} | Frame {frame_number:05d} | {width}x{height} | {hdr_info or 'SDR'}"`
3. Load font from `config.font_path` with size `config.font_size`. If `font_path` is `None`, use PIL default font.
4. Measure text bounding box to determine overlay dimensions.
5. Calculate overlay position using `calculate_overlay_position(image.size, (text_width + padding*2, text_height + padding*2), config.position)`.
6. Draw semi-transparent background rectangle (RGBA: 0, 0, 0, 180) at calculated position.
7. Draw text with shadow (1px offset, black) then white foreground.
8. Return composited image as `PIL.Image.Image`.

**Constants:**

- `padding: int = 8` (pixels around text inside background)

**Invalid inputs:**

- Input image is `None`: raise `ValueError("image must not be None")`.
- `config.mode` not in `OverlayMode`: raise `ValueError("invalid overlay mode")`.

### 3.3 Naming

```python
def generate_screenshot_name(
    label: str,
    frame_number: int,
    extension: str = "png",
) -> str:
    """
    Generate consistent screenshot filename.

    Format: {label}_{frame:05d}.{ext}
    Example: "Source_00100.png"
    """

def generate_screenshot_path(
    output_dir: Path,
    label: str,
    frame_number: int,
) -> Path:
    """Generate full output path."""
```

#### 3.3.1 `generate_screenshot_name` Behavior

**Algorithm:**

1. Sanitize `label`: replace any character not in `[A-Za-z0-9_-]` with `_`.
2. Collapse consecutive underscores to a single underscore.
3. Strip leading/trailing underscores.
4. If sanitized label is empty, use `"unnamed"`.
5. Format: `f"{sanitized_label}_{frame_number:05d}.{extension}"`.

**Invalid inputs:**

- `frame_number < 0`: raise `ValueError("frame_number must be non-negative")`.
- `extension` is empty string: raise `ValueError("extension must not be empty")`.

#### 3.3.2 `generate_screenshot_path` Behavior

**Algorithm:**

1. Call `generate_screenshot_name(label, frame_number)` to get filename.
2. Return `output_dir / filename`.

**Invalid inputs:**

- Same as `generate_screenshot_name`.

---

## 4. Implementation Details

### 4.1 VapourSynth Rendering

```python
def _render_vs(
    clip: vs.VideoNode,
    frame: int,
    output: Path,
    settings: EncoderSettings,
) -> None:
    """
    Render frame via VapourSynth.

    Pipeline:
    1. Get frame from clip: clip.get_frame(frame)
    2. Convert to numpy array
    3. Apply color conversion if needed
    4. Encode to PNG via PIL or cv2
    5. Save image to output path
    """
```

### 4.2 FFmpeg Rendering

```python
def _render_ffmpeg(
    video_path: Path,
    frame: int,
    output: Path,
    settings: EncoderSettings,
    timeout: int = 30,
) -> None:
    """
    Render frame via FFmpeg.

    Security: Uses run_subprocess() which enforces shell=False per FC-3010/3011.
    All arguments are passed as a list, never interpolated into a shell command.

    Command (as list):
    ["ffmpeg", "-ss", time, "-i", input, "-vframes", "1", "-q:v", "1", output]

    Uses time-based seeking for efficiency.

    FFmpeg Frame Seeking Policy:
    - fps is probed via ffprobe (required); never inferred
    - For VFR content: use avg_frame_rate from ffprobe, log warning
    - Seek time calculation (deterministic):
      `seek_seconds = floor((frame / fps) * 1000) / 1000` (e.g. 4.170s)
    - Errors:
      - `FileNotFoundError` (missing binary) → `FFmpegNotFoundError (FC-2005)`
      - `subprocess.CalledProcessError` (exit!=0) → `FFmpegError (FC-2006)` details from stderr
      - `subprocess.CalledProcessError` (ffprobe fail) → `SourceLoadError (FC-4015)`
    - **Note:** `render_frame()` wraps these dependency errors into `RenderError (FC-4004)` (or `FrameExtractionError`) to maintain a clean public API contract. The original cause is preserved in `DEBUG` logs.
    """

def _probe_fps(video_path: Path) -> float:
    """
    Probe video FPS using ffprobe.

    Steps:
    1. Run ffprobe to get r_frame_rate.
    2. Parse num/den format.
    3. Return float.

    Raises:
        SourceLoadError: If probe fails or output is invalid.
        FFmpegNotFoundError: If ffprobe is missing.
    """
```

### 4.3 Overlay Rendering

```python
def _render_overlay(
    image: PIL.Image,
    config: OverlayConfig,
) -> PIL.Image:
    """
    Composite overlay onto image.

    Layers:
    1. Semi-transparent background rectangle
    2. Text with shadow for readability

    Text content by mode:
    - minimal: "{label}"
    - standard: "{label} | Frame {frame} | {resolution}"
    - diagnostic: standard + HDR info
    """
```

---

## 5. Geometry Utilities

```python
def calculate_dimensions(
    source_width: int,
    source_height: int,
    max_width: int | None = None,
    max_height: int | None = None,
) -> tuple[int, int]:
    """Calculate output dimensions preserving aspect ratio."""

def calculate_overlay_position(
    image_size: tuple[int, int],
    overlay_size: tuple[int, int],
    position: str,
    margin: int = 10,
) -> tuple[int, int]:
    """Calculate overlay top-left corner."""

def ensure_mod2(width: int, height: int) -> tuple[int, int]:
    """Round dimensions up to nearest even values for video encoding compatibility."""
```

### 5.1 `calculate_dimensions` Behavior

**Algorithm:**

1. If both `max_width` and `max_height` are `None`, return `(source_width, source_height)`.
2. Compute aspect ratio: `ratio = source_width / source_height`.
3. If only `max_width` is set: `new_width = min(source_width, max_width)`, `new_height = int(new_width / ratio)`.
4. If only `max_height` is set: `new_height = min(source_height, max_height)`, `new_width = int(new_height * ratio)`.
5. If both are set: compute width-constrained and height-constrained sizes; pick the one that fits within *both* constraints.
6. Round down (truncate) to integer; never exceed constraints.

**Invalid inputs:**

- `source_width <= 0` or `source_height <= 0`: raise `ValueError("source dimensions must be positive")`.
- `max_width <= 0` or `max_height <= 0` (when not `None`): raise `ValueError("max dimensions must be positive")`.

### 5.2 `calculate_overlay_position` Behavior

**Valid positions:** `{"top-left", "top-right", "bottom-left", "bottom-right"}`.

**Algorithm:**

- `top-left`: `(margin, margin)`
- `top-right`: `(image_width - overlay_width - margin, margin)`
- `bottom-left`: `(margin, image_height - overlay_height - margin)`
- `bottom-right`: `(image_width - overlay_width - margin, image_height - overlay_height - margin)`

**Invalid inputs:**

- `position not in {"top-left", "top-right", "bottom-left", "bottom-right"}`: raise `ValueError(f"invalid position: {position}")`.
- `image_size` or `overlay_size` contains non-positive values: raise `ValueError("dimensions must be positive")`.
- Overlay + margin exceeds image dimensions: clamp coordinates to 0 (overlay anchored to edge).

### 5.3 `ensure_mod2` Behavior

**Algorithm:**

- Round each dimension up to the nearest even number: `(width + width % 2, height + height % 2)`.

**Invalid inputs:**

- `width <= 0` or `height <= 0`: raise `ValueError("dimensions must be positive")`.

---

## 6. Error Handling

> [!NOTE]
> All error classes are defined centrally in `frame_compare.errors` (see [errors-module.md](errors-module.md)).

**Error classes used by this module:**

| Error Class | Code | Usage |
|-------------|------|-------|
| `RenderError` | FC-4004 | Base for render errors |
| `FrameExtractionError` | FC-4001 | Failed to extract frame |
| `EncodingError` | FC-4013 | Failed to encode image |
| `OverlayError` | FC-4014 | Failed to apply overlay |
| `FFmpegNotFoundError` | FC-2005 | FFmpeg binary missing (internal) |
| `FFmpegError` | FC-2006 | FFmpeg process failed (internal) |
| `SourceLoadError` | FC-4015 | Failed to probe/load video (internal) |

```python
from frame_compare.errors import (
    RenderError,
    FrameExtractionError,
    EncodingError,
    OverlayError,
)
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

All unit tests MUST be pure-Python and MUST NOT require VapourSynth, FFmpeg, or network.

| Test | Validates |
|---|---|
| `tests/render/test_naming.py` | Deterministic naming (`{label}_{frame:05d}.png`) |
| `tests/render/test_geometry.py` | Deterministic geometry helpers |
| `tests/render/test_overlay.py` | Overlay layout and text composition (no VS required) |

### 7.2 Integration Tests

Integration tests MUST be explicitly marker-gated.

| Test | Marker(s) | Validates |
|---|---|---|
| PLANNED: `tests/render/test_tonemap_wiring.py::test_hdr_enable_tonemap_requires_vs_when_renderer_auto` | `@pytest.mark.vs_required` | HDR + enable_tonemap=True + VS missing → fail fast (`RenderError(FC-4004)`) |
| PLANNED: `tests/render/test_tonemap_wiring.py::test_hdr_enable_tonemap_requires_vs_when_renderer_ffmpeg` | `@pytest.mark.vs_required` | HDR + enable_tonemap=True + renderer="ffmpeg" → fail fast (`RenderError(FC-4004)`) |
| PLANNED: `tests/render/test_tonemap_wiring.py::test_hdr_disable_tonemap_allows_ffmpeg_when_vs_missing` | `@pytest.mark.integration` | HDR + enable_tonemap=False + VS missing → FFmpeg path allowed |
| PLANNED: `tests/render/test_tonemap_wiring.py::test_sdr_allows_ffmpeg_fallback_when_vs_missing` | `@pytest.mark.integration` | SDR source + VS missing → renderer="auto" falls back to FFmpeg |

---

## 8. AI Agent Implementation Prompt

```markdown
# Task: Implement Render Module

## Context
Implement the screenshot rendering module for Frame Compare 2.0.
This module extracts frames from video and saves as PNG images.

## Files to Create
1. `src/frame_compare/render/__init__.py` - Public exports
2. `src/frame_compare/render/encoders.py` - PNG encoding
3. `src/frame_compare/render/geometry.py` - Dimensions
4. `src/frame_compare/render/naming.py` - File naming
5. `src/frame_compare/render/overlay.py` - Text overlay
6. `src/frame_compare/render/orchestrator.py` - Multi-clip screenshot workflow

## Key Requirements
- VapourSynth primary renderer
- FFmpeg fallback is allowed only when tonemap is not required (SDR source or `enable_tonemap=false`)
- PNG output with configurable compression
- Overlay modes: minimal, standard, diagnostic
- Consistent naming: {label}_{frame:05d}.png

## Testing
- Mock VS for unit tests
- Real render tests with sample video
- Overlay visual verification

## Dependencies
- vapoursynth (vs) - optional
- PIL/Pillow for image operations (required for overlays/PNG verification)
- ffmpeg subprocess calls

## Acceptance Criteria
- Both renderers produce valid PNGs
- Overlay renders correctly
- Naming follows convention
- Fallback works when VS missing
```
