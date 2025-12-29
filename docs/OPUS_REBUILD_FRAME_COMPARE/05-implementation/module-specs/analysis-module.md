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

    Args:
        video_paths: Video file paths (first entry is the reference clip)
        config: Analysis configuration
        cache_dir: Directory for cache files (typically `paths.generated_dir`)
        reporter: Optional progress reporter

    Returns:
        FrameMetrics with luminance and motion arrays

    Raises:
        AnalysisError: If video cannot be analyzed
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

    Selection Algorithms by Mode:

    - **quantile**: Selects frames at luminance percentiles
      - Darkest frames: 0th, 10th, 20th percentiles
      - Brightest frames: 80th, 90th, 100th percentiles
      - Divides frame_count evenly between dark/bright

    - **motion**: Selects high-motion frames
      - Sort frames by motion score descending
      - Take top frame_count with minimum gap of 5 frames

    - **random**: Seeded reproducible random selection
      - Uses config.random_seed for reproducibility
      - Applies minimum gap of 5 frames between selections

    - **mixed**: Combination allocation (DEFAULT)
      - 40% quantile (luminance extremes)
      - 40% motion (high-action scenes)
      - 20% random (variety)
      - Example: frame_count=10 -> 4 quantile + 4 motion + 2 random

    Duplicate Handling:
    - If motion/random selects frame already chosen by quantile, skip to next candidate
    - Final selection guaranteed to have frame_count unique frames
    - If insufficient candidates after deduplication, raises SelectionError

    save_frames_data Behavior:
    - If True: Write FrameSelection to {cache_dir}/frame_selection.json
    - Contains: frame_numbers, mode, seed, selection_reason per frame
    - Used for reproducibility and debugging

    Args:
        metrics: Calculated frame metrics
        config: Selection configuration

    Returns:
        FrameSelection with chosen frame numbers and metadata

    Raises:
        SelectionError: If insufficient valid candidates for selection
    """
```

### 3.3 Cache Operations

```python
def load_cached_metrics(
    cache_dir: Path,
    fingerprint: str,
    clips: list[ClipIdentity],
) -> CacheLoadResult:
    """
    Attempt to load metrics from cache.

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

    Algorithm:
    1. Convert to YUV if needed
    2. reporter.start_phase("luminance", frame_count) if reporter
    3. For each frame:
       a. Get Y plane
       b. Calculate mean value
       c. Normalize to 0-1 range
       d. reporter.advance() if reporter
    4. reporter.complete_phase() if reporter

    Progress integration:
    - Call start_phase("Calculating luminance", clip.num_frames) before loop
    - Call advance(1) after processing each frame
    - Call complete_phase() after loop completes
    """
```

### 4.2 Motion Scoring

```python
def _calculate_motion(clip: vs.VideoNode) -> list[float]:
    """
    Calculate frame-to-frame difference scores.

    Algorithm:
    1. For each frame pair (N, N+1):
       a. Calculate absolute difference
       b. Sum difference values
       c. Normalize by frame size
    2. First frame motion = 0
    """
```

### 4.3 Selection Algorithms

```python
def _select_by_quantile(
    luminance: list[float],
    count: int,
    dark_quantile: float,
    bright_quantile: float,
) -> tuple[list[int], list[int]]:
    """
    Select frames at luminance quantiles.

    Algorithm:
    1. Calculate percentile thresholds
    2. Find frames below dark threshold
    3. Find frames above bright threshold
    4. Take count/2 from each end
    """

def _select_by_motion(
    motion: list[float],
    count: int,
) -> list[int]:
    """
    Select frames with high motion scores.

    Algorithm:
    1. Sort frames by motion score (descending)
    2. Take top N frames
    3. Resort by frame number
    """

def _select_random(
    frame_count: int,
    count: int,
    seed: int,
    exclude: set[int],
) -> list[int]:
    """
    Select random frames with seed.

    Algorithm:
    1. Initialize RNG with seed
    2. Generate candidate frames
    3. Exclude already-selected frames
    4. Return sorted list
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

### 5.2 Invalidation Rules

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
