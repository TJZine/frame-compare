---
RUN_ID: 2025-12-29__p2-3__frame-selection
VERSION: v3
TARGET: Phase 2 → Item 2.3
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v2.md
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v3.md
---

# Implementation Plan: Frame Selection Algorithms

## Changes Since plan-v2

- **Added explicit test fixtures**: `make_metrics()` and `make_config()` helpers with deterministic metadata
- **Separated min-gap tests**: `test_motion_selection_respects_min_gap` and `test_random_selection_respects_min_gap` (QUANTILE has no min-gap requirement per SSOT)
- **Exact expected outputs for different-seed test**: Pre-computed frame lists for seed=42 and seed=123
- **Concrete inputs for edge-case tests**: Explicit arrays and expected `found` values for dedup, insufficient, and empty tests
- **Clarified "empty" definition**: Both `luminance` and `motion` arrays empty

## Context

**Phase:** 2
**Module:** analysis
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
**Dependencies:** Phase 2.1 Types (complete), `frame_compare.config.SelectionMode`

## Scope

This plan covers:

- [ ] `src/frame_compare/analysis/selection.py` — selection algorithms
- [ ] `tests/analysis/test_selection.py` — unit tests
- [ ] `src/frame_compare/analysis/__init__.py` — update exports (additive)
- [ ] `docs/DECISIONS.md` — append run decision entry
- [ ] `CHANGELOG.md` — add entry

This plan does NOT cover:

- Metrics calculation (Phase 2.2, blocked on VS)
- Cache I/O (Phase 2.4)
- `save_frames_data` JSON persistence (deferred to Phase 2.4)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`:
  - Section: "2.2 FrameSelection"
  - Section: "3.2 select_frames"
  - Section: "4.3 Selection Algorithms"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. `src/frame_compare/analysis/selection.py` [NEW]

**Purpose:** Pure Python frame selection algorithms.

**Imports:**

```python
from __future__ import annotations
import random
from collections.abc import Sequence
from frame_compare.analysis.types import FrameMetrics, FrameSelection, SelectionBreakdown
from frame_compare.config import AnalysisConfig, SelectionMode
from frame_compare.errors import SelectionError
```

**Constants:**

```python
MIN_GAP: int = 5
```

**Functions to implement (spec-anchored):**

- `select_frames(metrics: FrameMetrics, config: AnalysisConfig) -> FrameSelection`
- `_select_by_quantile(luminance: Sequence[float], count: int) -> tuple[list[int], list[int]]`
- `_select_by_motion(motion: Sequence[float], count: int, exclude: set[int], min_gap: int) -> list[int]`
- `_select_random(total_frames: int, count: int, seed: int, exclude: set[int], min_gap: int) -> list[int]`

**Error handling:**

- Empty metrics (`len(metrics.luminance) == 0` AND `len(metrics.motion) == 0`): `raise SelectionError(reason="empty_metrics", requested=config.frame_count, found=0)`
- Insufficient candidates: `raise SelectionError(reason="insufficient_candidates", requested=config.frame_count, found=len(selected))`

### 2. `tests/analysis/test_selection.py` [NEW]

**Purpose:** Deterministic unit tests for selection algorithms.

**Test Helpers (define at top of file):**

```python
from fractions import Fraction
from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.config import AnalysisConfig, SelectionMode

def make_metrics(luminance: list[float], motion: list[float]) -> FrameMetrics:
    """Create FrameMetrics with deterministic metadata."""
    return FrameMetrics(
        luminance=luminance,
        motion=motion,
        metadata=MetricsMetadata(
            frame_count=len(luminance),
            fps=Fraction(24),
            config_fingerprint="fp",
            clips=[ClipIdentity(path="video.mkv", size=1, mtime=1.0, sha1=None)],
            version=2,
        ),
    )

def make_config(
    *,
    frame_count: int,
    selection_mode: SelectionMode,
    random_seed: int = 42,
) -> AnalysisConfig:
    """Create AnalysisConfig with selection-relevant fields."""
    return AnalysisConfig(frame_count=frame_count, selection_mode=selection_mode, random_seed=random_seed)
```

**Test Data:**

```python
# 100 frames: luminance ascending 0.00..0.99, motion peaks at 50,60,70,80,90
LUMINANCE_100 = [i / 100.0 for i in range(100)]
MOTION_100 = [1.0 if i in {50, 60, 70, 80, 90} else 0.1 for i in range(100)]
```

**Tests (10 total):**

| # | Test Name | Input | Expected Output |
|---|-----------|-------|-----------------|
| 1 | `test_quantile_mode_returns_luminance_extremes` | `make_metrics(LUMINANCE_100, MOTION_100)`, `make_config(frame_count=10, selection_mode=QUANTILE)` | `frames=[0,1,2,3,4,95,96,97,98,99]`, `breakdown.quantile_dark=[0,1,2,3,4]`, `breakdown.quantile_bright=[95,96,97,98,99]` |
| 2 | `test_motion_mode_returns_high_motion` | `make_metrics(LUMINANCE_100, MOTION_100)`, `make_config(frame_count=5, selection_mode=MOTION)` | `frames=[50,60,70,80,90]` (all peaks, min_gap=5 satisfied) |
| 3 | `test_random_mode_same_seed_deterministic` | `make_config(random_seed=42, frame_count=10, selection_mode=RANDOM)` | Two calls return identical `frames` |
| 4 | `test_random_mode_different_seed_exact_outputs` | seed=42 vs seed=123, `total_frames=100`, `count=10`, MIN_GAP=5 | seed=42: `frames=[2,11,16,40,50,60,72,79,90,97]`; seed=123: `frames=[5,17,24,35,44,53,62,75,84,98]` |
| 5 | `test_mixed_mode_allocation` | `make_config(frame_count=10, selection_mode=MIXED)` | `len(breakdown.quantile_dark)+len(breakdown.quantile_bright)==4`, `len(breakdown.motion)==4`, `len(breakdown.random)==2` |
| 6 | `test_deduplication_skips_already_selected` | luminance where indices 0,99 are extremes + motion peaks at 0,99 | motion phase skips 0,99 (already in quantile); final `frames` has no duplicates |
| 7 | `test_insufficient_candidates_raises` | `make_metrics([0.1]*5, [0.1]*5)`, `make_config(frame_count=10, ...)` | `SelectionError(reason="insufficient_candidates", requested=10, found=5)` |
| 8 | `test_empty_metrics_raises` | `make_metrics([], [])` | `SelectionError(reason="empty_metrics", requested=..., found=0)` |
| 9 | `test_motion_selection_respects_min_gap` | mode=MOTION, check all pairs | `all(abs(frames[i]-frames[j]) >= 5 for i<j)` |
| 10 | `test_random_selection_respects_min_gap` | mode=RANDOM, check all pairs | `all(abs(frames[i]-frames[j]) >= 5 for i<j)` |

**Note:** QUANTILE mode does NOT require min-gap (SSOT: min-gap applies to motion/random phases only).

### 3. `src/frame_compare/analysis/__init__.py` [MODIFY]

**After modification:**

```python
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.types import (
    CacheLoadResult,
    ClipIdentity,
    FrameMetrics,
    FrameSelection,
    MetricsMetadata,
    SelectionBreakdown,
)
__all__ = ["CacheLoadResult", "ClipIdentity", "FrameMetrics", "FrameSelection", "MetricsMetadata", "SelectionBreakdown", "select_frames"]
```

### 4. `docs/DECISIONS.md` [MODIFY]

**Required facts:** RUN_ID, artifact versions, scope, SSOT edits (sections 3.2+4.3), verification gates passed.

### 5. `CHANGELOG.md` [MODIFY]

```
### Added
- Frame selection algorithms (`select_frames`) with QUANTILE, MOTION, RANDOM, MIXED modes
```

## Acceptance Criteria

- [ ] GIVEN `FrameMetrics` with LUMINANCE_100/MOTION_100 WHEN `select_frames(..., mode=QUANTILE, frame_count=10)` THEN `frames==[0,1,2,3,4,95,96,97,98,99]`
- [ ] GIVEN same seed=42 WHEN `select_frames` called twice THEN identical frame lists
- [ ] GIVEN 5-frame metrics WHEN `frame_count=10` THEN `SelectionError` with `reason="insufficient_candidates", found=5`
- [ ] GIVEN empty metrics WHEN `select_frames` called THEN `SelectionError` with `reason="empty_metrics", found=0`

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v3.md
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- **Pure Python only** — `random.Random(seed)`, `sorted()`. No numpy.
- **MIN_GAP=5** applies to motion/random phases, NOT quantile.
- **SelectionError** — `from frame_compare.errors import SelectionError`
- **Empty metrics** — Both `len(luminance)==0` AND `len(motion)==0`
- **STOP if ambiguous** — Escalate, do not guess.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-3__frame-selection

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v3.md
