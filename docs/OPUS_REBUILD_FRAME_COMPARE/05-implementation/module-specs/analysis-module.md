# Analysis Module Implementation Spec

> **Module:** `frame_compare.analysis`
> **Version:** 1.0
> **Priority:** P0

---

## 1. Module Overview

The Analysis module is responsible for calculating frame-level metrics and selecting representative frames for comparison screenshots.

### 1.1 Responsibilities

- Calculate luminance values for all frames
- Calculate motion/difference scores between frames
- Persist metrics to cache for reuse
- Select frames based on configurable algorithms
- Manage cache invalidation

### 1.2 Module Structure

```text
src/frame_compare/analysis/
├── __init__.py          # Public exports
├── cache_io.py          # Cache persistence
├── metrics.py           # Metric calculation
├── selection.py         # Frame selection algorithms
└── types.py             # Module-specific types
```

---

### 1.3 Dependencies

| Dependency | Source | Types Imported |
|------------|--------|----------------|
| `frame_compare.config` | Parent | `AnalysisConfig`, `SelectionMode` |
| `frame_compare.utils` | Sibling | `ProgressReporter`, `Result` |
| `frame_compare.errors` | Leaf | `FrameCompareError` |
| `frame_compare.vs` | Sibling | `VSLoader` (for clip loading) |

> [!NOTE]
> **`SelectionMode`** is canonically defined in `frame_compare.config` and imported from there.

#### Import-Time VapourSynth Dependency (SSOT)

The `frame_compare.analysis` module **MUST** be importable when `vapoursynth` is not installed. This enables:

- Test collection on systems without VapourSynth
- Type checking without runtime dependency
- Import of types/cache utilities without video processing

**Implementation rules:**

1. Do **not** import `vapoursynth` at module import time (top-level)
2. Use `TYPE_CHECKING` blocks for type hints referencing `vs.VideoNode`
3. Import `vapoursynth` inside functions that require it (e.g., `_calculate_luminance`, `_calculate_motion`)

**Verification:** A deterministic `ast`-based test must confirm no top-level `import vapoursynth` statements exist outside `if TYPE_CHECKING:` blocks.

---

## 2. Key Types

### 2.1 FrameMetrics

```python
@dataclass(frozen=True, slots=True)
class FrameMetrics:
    """Analysis results for a video clip"""
    luminance: list[float]    # Per-frame Y channel mean
    motion: list[float]       # Per-frame difference score
    metadata: MetricsMetadata

@dataclass(frozen=True, slots=True)
class MetricsMetadata:
    frame_count: int
    fps: Fraction
    config_fingerprint: str   # For cache invalidation
    clips: list[ClipIdentity]
    version: int = 2          # Schema version (default last)

@dataclass(frozen=True, slots=True)
class ClipIdentity:
    path: str
    size: int
    mtime: float
    sha1: str | None = None
```

**Example construction:**

```python
clip = ClipIdentity(path="video.mkv", size=1024, mtime=1704067200.0)
```

### 2.2 FrameSelection

```python
@dataclass(frozen=True, slots=True)
class FrameSelection:
    """Selected frame numbers with reasoning"""
    frames: list[int]
    mode: SelectionMode
    seed: int
    breakdown: SelectionBreakdown

@dataclass(frozen=True, slots=True)
class SelectionBreakdown:
    quantile_dark: list[int]
    quantile_bright: list[int]
    motion: list[int]
    random: list[int]
```

### 2.3 CacheLoadResult

```python
@dataclass(frozen=True, slots=True)
class CacheLoadResult:
    """Result of attempting to load metrics from cache.

    Attributes:
        success: Whether cache was successfully loaded
        metrics: Loaded metrics if successful, None otherwise
        reason: Reason for failure if unsuccessful
    """
    success: bool
    metrics: FrameMetrics | None = None
    reason: str | None = None  # "not_found" | "corrupted" | "version_mismatch" | "fingerprint_mismatch"
```

---

## 3. Public API

### 3.1 calculate_metrics

```python
def calculate_metrics(
    video_paths: list[Path],
    config: AnalysisConfig,
    cache_dir: Path,
    reporter: ProgressReporter | None = None,
) -> FrameMetrics:
    """
    Calculate frame metrics for the given clips.

    Uses cached values if valid cache exists and config matches.

    Clip Selection:
        Metrics are computed for the REFERENCE clip only: `video_paths[0]`.
        Other paths in `video_paths` are used for ClipIdentity population
        but not analyzed (comparison clips share the reference metrics).

    MetricsMetadata Population:
        - frame_count: reference clip's num_frames
        - fps: reference clip's fps (Fraction)
        - config_fingerprint: equals the fingerprint passed to load_cached_metrics
          and written as `fingerprint` key in cache file
        - clips: list of ClipIdentity for all video_paths (reference + comparisons)
        - version: CACHE_VERSION constant

    Cache Invariant:
        MetricsMetadata.config_fingerprint == cache file's `fingerprint` field.
        This is computed via compute_cache_key(video_paths, config).

    Args:
        video_paths: Video file paths (first entry is the reference clip)
        config: Analysis configuration
        cache_dir: Directory for cache files (typically `paths.generated_dir`)
        reporter: Optional progress reporter

    Returns:
        FrameMetrics with luminance and motion arrays

    Raises:
        MetricsCalculationError (FC-4002): If frame extraction or metric
            computation fails (wraps underlying VS/numpy errors), OR if
            reference clip has 0 frames.
        PluginNotFoundError (FC-2003): If VapourSynth lsmas plugin unavailable.
        SourceLoadError (FC-4015): If video file cannot be loaded.
    """
```

### 3.2 select_frames

```python
def select_frames(
    metrics: FrameMetrics,
    config: AnalysisConfig,
) -> FrameSelection:
    """
    Select representative frames based on metrics.

    Constants:
        MIN_GAP: int = 5  # Minimum frame distance between selections

    Selection Algorithms by Mode:

    - **QUANTILE**: Selects frames at luminance extremes
      - dark_count = count // 2
      - bright_count = count - dark_count
      - Sort frame indices by luminance ascending
      - Take dark_count from start, bright_count from end

    - **MOTION**: Selects high-motion frames
      - Sort frames by motion score descending
      - Greedily select top frames respecting MIN_GAP from already-selected
      - Take up to frame_count frames

    - **RANDOM**: Seeded reproducible random selection
      - RNG: random.Random(config.random_seed)
      - Shuffle all frame indices, greedily pick respecting MIN_GAP + exclude set

    - **MIXED**: Combination allocation (DEFAULT)
      - quantile_count = frame_count * 40 // 100
      - motion_count = frame_count * 40 // 100
      - random_count = frame_count - quantile_count - motion_count
      - Selection order: quantile first, then motion (excludes quantile), then random (excludes both)
      - Each phase respects MIN_GAP and deduplication

    Duplicate Handling:
      - maintain exclude: set[int] accumulating selected frames
      - motion/random phases skip frames in exclude
      - MIN_GAP enforced per-phase: candidate valid if abs(candidate - any_selected) >= MIN_GAP

    Error Handling:
      - If insufficient candidates after deduplication, raise:
        SelectionError(reason="insufficient_candidates", requested=config.frame_count, found=len(selected))
      - Empty metrics (frame_count=0 in metadata): raise SelectionError with reason="empty_metrics"

    Args:
        metrics: Calculated frame metrics
        config: Selection configuration (frame_count >= 1 enforced by schema)

    Returns:
        FrameSelection with sorted frame list and breakdown

    Raises:
        SelectionError: If insufficient valid candidates for selection
    """
```

> [!NOTE]
> **save_frames_data** persistence is handled in cache_io phase (Phase 2.4), not in this function.

### 3.3 Cache Operations

```python
def load_cached_metrics(
    cache_dir: Path,
    fingerprint: str,
    clips: list[ClipIdentity],
) -> CacheLoadResult:
    """
    Attempt to load metrics from cache.

    Parameters:
        clips: Reserved for future validation; currently ignored.
              Fingerprint is authoritative; do not recompute from clips.

    Failure mapping:
        - Cache file not found → CacheLoadResult(success=False, reason="not_found")
        - Invalid JSON or missing required keys → CacheLoadResult(success=False, reason="corrupted")
        - version != CACHE_VERSION → CacheLoadResult(success=False, reason="version_mismatch")
        - fingerprint mismatch → CacheLoadResult(success=False, reason="fingerprint_mismatch")

    Returns:
        CacheLoadResult with success status and data or reason
    """

def save_metrics_cache(
    metrics: FrameMetrics,
    cache_dir: Path,
) -> None:
    """Persist metrics to cache file."""
```

---

## 4. Implementation Details

### 4.1 Luminance Calculation

```python
def _calculate_luminance(
    clip: vs.VideoNode,
    reporter: ProgressReporter | None = None,
) -> list[float]:
    """
    Calculate Y channel mean for each frame.

    Format Handling:
        - If clip.format.color_family != vs.YUV, convert first:
          `clip = clip.resize.Bicubic(format=vs.YUV420P8)`
        - Supported: Any YUV format (8-bit to 16-bit integer, or float)

    Frame Plane Extraction:
        For each frame n:
        1. frame = clip.get_frame(n)
        2. arr = np.asarray(frame[0])  # Y plane (index 0)
        3. mean_val = float(np.mean(arr))

    Normalization (deterministic):
        - Integer formats: max_value = (1 << clip.format.bits_per_sample) - 1
          luminance[n] = mean_val / max_value
        - Float formats (clip.format.sample_type == vs.FLOAT):
          luminance[n] = mean_val  # Already 0.0-1.0 range

    Output:
        len(luminance) == clip.num_frames
        All values in range [0.0, 1.0]

    Progress integration:
        - Call reporter.start_phase("Calculating luminance", clip.num_frames) before loop
        - Call reporter.advance(1) after processing each frame
        - Call reporter.complete_phase() after loop completes

    Empty Clip Handling:
        If clip.num_frames == 0, raise MetricsCalculationError (FC-4002)
        immediately before any progress callbacks. No values are returned.

    Raises:
        MetricsCalculationError: If frame access fails or clip has 0 frames.
    """
```

### 4.2 Motion Scoring

```python
def _calculate_motion(clip: vs.VideoNode) -> list[float]:
    """
    Calculate frame-to-frame difference scores.

    Format Handling:
        Same as _calculate_luminance: convert to YUV if needed.

    Frame Plane Extraction:
        Uses same API as luminance: np.asarray(frame[0]) for Y plane.

    Algorithm:
        motion = [0.0] * clip.num_frames  # Pre-allocate
        motion[0] = 0.0  # First frame has no predecessor

        For n in range(1, clip.num_frames):
            prev_arr = np.asarray(clip.get_frame(n-1)[0])
            curr_arr = np.asarray(clip.get_frame(n)[0])
            diff = np.abs(curr_arr.astype(np.float32) - prev_arr.astype(np.float32))
            motion[n] = float(np.sum(diff)) / (width * height * max_value)

    Normalization (deterministic):
        - width, height = clip.width, clip.height
        - max_value: same bit-depth rule as luminance
        - Output range: [0.0, 1.0] where 1.0 = every pixel changed by max_value

    Output:
        len(motion) == clip.num_frames
        motion[0] == 0.0 (invariant)

    Empty Clip Handling:
        If clip.num_frames == 0, raise MetricsCalculationError (FC-4002)
        immediately. No values are returned.

    Raises:
        MetricsCalculationError: If frame access fails or clip has 0 frames.
    """
```

### 4.3 Selection Algorithms

```python
def _select_by_quantile(
    luminance: Sequence[float],
    count: int,
) -> tuple[list[int], list[int]]:
    """
    Select frames at luminance extremes.

    Args:
        luminance: Per-frame luminance values (0.0-1.0)
        count: Total frames to select

    Returns:
        (dark_indices, bright_indices) as sorted lists

    Algorithm:
        n = len(luminance)
        dark_count = count // 2
        bright_count = count - dark_count
        # Sort frame indices by luminance ascending
        sorted_indices = sorted(range(n), key=lambda i: luminance[i])
        dark_indices = sorted_indices[:dark_count]
        bright_indices = sorted_indices[-(bright_count):]
        return (sorted(dark_indices), sorted(bright_indices))
    """

def _select_by_motion(
    motion: Sequence[float],
    count: int,
    exclude: set[int],
    min_gap: int,
) -> list[int]:
    """
    Select frames with high motion scores.

    Args:
        motion: Per-frame motion scores
        count: Number of frames to select
        exclude: Frame indices already selected (skip these)
        min_gap: Minimum distance from any already-selected frame

    Returns:
        List of selected frame indices (sorted ascending)

    Algorithm:
        1. Create list of (index, score) for indices not in exclude
        2. Sort by score descending
        3. Greedily pick top candidates where abs(idx - any_selected) >= min_gap
        4. Return sorted list of selected indices
    """

def _select_random(
    total_frames: int,
    count: int,
    seed: int,
    exclude: set[int],
    min_gap: int,
) -> list[int]:
    """
    Select random frames with seeded RNG.

    Args:
        total_frames: Total number of frames in source
        count: Number of frames to select
        seed: RNG seed for reproducibility
        exclude: Frame indices already selected (skip these)
        min_gap: Minimum distance from any already-selected frame

    Returns:
        List of selected frame indices (sorted ascending)

    Algorithm:
        1. rng = random.Random(seed)
        2. candidates = [i for i in range(total_frames) if i not in exclude]
        3. rng.shuffle(candidates)
        4. Greedily pick from shuffled list respecting min_gap
        5. Return sorted list of selected indices
    """
```

---

## 5. Cache Strategy

### 5.1 Cache Key Generation

**Cache file:** `cache_dir / "cache.compframes"` (v2 default). For parity/migration, the runner may also read/write the legacy `generated.compframes` filename at workspace root.

```python
def compute_cache_key(
    video_paths: list[Path],
    config: AnalysisConfig,
) -> str:
    """
    Generate cache key from clip identities and config.

    Components:
    - Clip paths, sizes, mtimes (reference + comparisons)
    - Config fingerprint (frame_count, mode, thresholds)
    - Schema version
    """
```

### 5.2 Cache File Schema (v2)

**Required top-level keys:**

| Key | Type | Description |
|-----|------|-------------|
| `version` | int | Schema version (must be 2) |
| `fingerprint` | str | Config fingerprint for invalidation |
| `luminance` | list[float] | Per-frame luminance values |
| `motion` | list[float] | Per-frame motion scores |
| `metadata` | object | MetricsMetadata object |

**Required `metadata` keys:**

| Key | Type | Description |
|-----|------|-------------|
| `frame_count` | int | Total frames analyzed |
| `fps` | str | Frame rate as `str(Fraction)`, e.g. `"24/1"` |
| `config_fingerprint` | str | Config hash for validation |
| `clips` | list[object] | ClipIdentity objects |
| `version` | int | Metadata schema version |

**`fps` serialization:**

- Serialize: `str(Fraction)` → `"24/1"` or `"30000/1001"`
- Deserialize: `Fraction(fps_str)` → `Fraction(24, 1)`

### 5.3 Invalidation Rules

| Trigger | Action |
|---------|--------|
| File path changed | Miss |
| File size changed | Miss |
| File mtime changed | Miss |
| Config changed | Miss |
| Schema version mismatch | Miss |
| Cache file corrupt | Miss (warn) |

---

## 6. Error Handling

> [!NOTE]
> All error classes are defined centrally in `frame_compare.errors` (see [errors-module.md](errors-module.md)).
> This module should import and use these classes, not define its own.

**Error classes used by this module:**

| Error Class | Code | Usage |
|-------------|------|-------|
| `AnalysisError` | (base) | Base for all analysis errors |
| `MetricsCalculationError` | FC-4002 | Failed to calculate metrics |
| `CacheCorruptionError` | FC-4006 | Cache file is corrupt |
| `SelectionError` | FC-4012 | Frame selection failed |

```python
# Import from central module
from frame_compare.errors import (
    AnalysisError,
    MetricsCalculationError,
    CacheCorruptionError,
    SelectionError,
)
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

| Test Case | Input | Expected |
|-----------|-------|----------|
| Luminance calculation | Sample clip | Values in 0-1 range |
| Motion scoring | Static clip | Low/zero motion |
| Motion scoring | Action clip | High motion peaks |
| Quantile selection | Known distribution | Correct frames |
| Random selection | Same seed twice | Identical results |
| Cache hit | Valid cache | Returns cached |
| Cache miss | Changed config | Recomputes |

### 7.2 Integration Tests

- Full analysis on sample video
- Cache round-trip
- Selection with real metrics

---

## 8. AI Agent Implementation Prompt

```markdown
# Task: Implement Analysis Module

## Context
Implement the frame analysis module for Frame Compare 2.0.
This module calculates per-frame metrics (luminance, motion)
and selects representative frames for comparison.

## Files to Create
1. `src/frame_compare/analysis/__init__.py` - Public exports
2. `src/frame_compare/analysis/types.py` - Dataclasses
3. `src/frame_compare/analysis/metrics.py` - Calculation logic
4. `src/frame_compare/analysis/selection.py` - Selection algorithms
5. `src/frame_compare/analysis/cache_io.py` - Cache persistence

## Key Requirements
- Luminance: Y channel mean per frame (0-1 normalized)
- Motion: Frame N vs N+1 absolute difference sum
- Selection modes: quantile, motion, random, mixed
- Cache invalidation on file or config change
- Deterministic selection with seeded RNG

## Testing
- Mock VapourSynth for unit tests
- Use @pytest.mark.vs_required for real VS tests
- Test cache hit/miss scenarios
- Verify reproducibility with same seed

## Dependencies
- VapourSynth via `vs` module
- numpy for array operations
- Standard library for caching

## Acceptance Criteria
- `.venv/bin/pyright --warnings src/frame_compare/analysis` passes
- `.venv/bin/pytest -q tests/analysis` passes
- Cache reuse verified
- Selection reproducible
```
