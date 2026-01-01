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

- Contract: `contracts/phase_ordering.yaml` (frame_plan phase)
- Implementation: `scaffold/src/frame_compare/analysis/frame_plan.py`

The algorithm partitions frames into bins and selects one frame per bin using a blake2s hash for reproducibility. See the scaffold implementation for locked reference outputs.

**Key Properties:**

- **Frame indices:** 0-based, in `[0, num_frames - 1]`
- **Deterministic:** Same `(num_frames, count, seed)` → same frames
- **Contract enforced:** `FramePlan.frames` is always a concrete `list[int]`; render phase MUST NOT reselect frames

**Error Handling:**

- If video has fewer frames than `frame_count`: raise `InsufficientFramesError(FC-3004)`

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
    """

def render_batch(
    requests: list[RenderRequest],
    parallelism: int = 1,
    reporter: ProgressReporter | None = None,
) -> list[Path]:
    """
    Render multiple frames with progress reporting.

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

    Responsibilities:
    - Resolve labels for naming/overlays
    - Generate `RenderRequest`s for every (clip, frame) pair
    - Delegate actual rendering to `render_batch`
    - Return a mapping of label -> rendered image paths

    Notes:
    - This orchestration lives in `render/orchestrator.py` to keep `runner` thin.
    - The caller is responsible for applying audio offsets/trims at the VS layer.
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
    - fps is probed via ffprobe if not provided
    - For VFR content: use avg_frame_rate from ffprobe, log warning
    - Seek time = frame / fps (3 decimal places precision)
    - Rounding: floor for consistency with VS frame indexing
    - Errors: FC-2006 (FFMPEG_ERROR), FC-4015 (SOURCE_LOAD_ERROR)
    """
    from frame_compare.utils.subproc import run_subprocess

    # Calculate seek time (fps should be probed via ffprobe in real impl)
    fps = settings.fps or _probe_fps(video_path)  # FC-2006 if probe fails
    seek_time = f"{frame / fps:.3f}"

    run_subprocess(
        ["ffmpeg", "-ss", seek_time, "-i", str(video_path),
         "-vframes", "1", "-q:v", "1", str(output)],
        timeout_seconds=timeout,
    )
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

| Test Case | Input | Expected |
|-----------|-------|----------|
| Filename generation | "Source", 100 | "Source_00100.png" |
| Overlay position | top-left | (margin, margin) |
| Dimension calculation | 4K input | Within limits |

### 7.2 Integration Tests

| Test Case | Input | Expected |
|-----------|-------|----------|
| VS render | Sample clip | PNG file created |
| FFmpeg render | Video file | PNG file created |
| Overlay application | Image + config | Overlay visible |

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
- FFmpeg fallback when VS unavailable
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
