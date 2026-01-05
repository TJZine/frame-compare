---
RUN_ID: 2025-12-29__p2-3__frame-selection
VERSION: v2
TARGET: Phase 2 → Item 2.3
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v1.md
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v2.md
---

# Implementation Plan: Frame Selection Algorithms

## Changes Since plan-v1

- **SSOT Updated**: Edited `analysis-module.md` sections 3.2 and 4.3:
  - Section 3.2: precise quantile selection (sort + dark/bright split), exact mixed allocation rounding, removed `save_frames_data` (deferred to Phase 2.4), explicit error reason strings
  - Section 4.3: updated helper signatures with `exclude: set[int]` and `min_gap: int` params
- **Removed numpy choice**: Committed to pure Python only for this slice
- **Removed `frame_count=0` edge case**: Config schema enforces `frame_count >= 1`
- **Specified `SelectionError` usage**: Exact constructor calls with reason/requested/found
- **Made tests fully deterministic**: Explicit input vectors and expected outputs
- **Specified `__init__.py` export change precisely**: Additive diff with exact `__all__` after modification

## Context

**Phase:** 2
**Module:** analysis
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
**Dependencies:** Phase 2.1 Types (complete), `frame_compare.config.SelectionMode`

> [!NOTE]
> Phase 2.2 (Metrics Calculation) is temporarily deferred — it requires `vs.VideoNode` which is unavailable until Phase 3 (VapourSynth). Frame Selection operates on pure Python data (`FrameMetrics`) and can proceed independently.

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
- Integration with VS module
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

- Empty metrics: `raise SelectionError(reason="empty_metrics", requested=config.frame_count, found=0)`
- Insufficient candidates: `raise SelectionError(reason="insufficient_candidates", requested=config.frame_count, found=len(selected))`

### 2. `tests/analysis/test_selection.py` [NEW]

**Purpose:** Deterministic unit tests for selection algorithms.

**Test data (100 frames):**

```python
# Luminance: 0.0, 0.01, 0.02, ..., 0.99 (ascending by index)
LUMINANCE_100 = [i / 100.0 for i in range(100)]
# Motion: peaks at indices 50, 60, 70, 80, 90 (value=1.0), others=0.1
MOTION_100 = [1.0 if i in {50, 60, 70, 80, 90} else 0.1 for i in range(100)]
```

**Tests required:**

| Test Name | Input | Expected |
|-----------|-------|----------|
| `test_select_frames_quantile_mode_returns_luminance_extremes` | luminance=LUMINANCE_100, frame_count=10, mode=QUANTILE | frames=[0,1,2,3,4,95,96,97,98,99], breakdown.quantile_dark=[0,1,2,3,4], breakdown.quantile_bright=[95,96,97,98,99] |
| `test_select_frames_motion_mode_returns_high_motion` | motion=MOTION_100, frame_count=5, mode=MOTION | frames=[50,60,70,80,90] (respecting min_gap=5) |
| `test_select_frames_random_mode_same_seed_deterministic` | seed=42, frame_count=10 | Two calls return identical sorted frame lists |
| `test_select_frames_random_mode_different_seed_different_results` | seed=42 vs seed=123 | Different frame lists |
| `test_select_frames_mixed_mode_allocation` | frame_count=10, mode=MIXED | len(dark)+len(bright)=4, len(motion)=4, len(random)=2 |
| `test_select_frames_deduplication_skips_already_selected` | Overlap scenario | No duplicates in final frames |
| `test_select_frames_insufficient_candidates_raises` | total_frames=5, frame_count=10 | `SelectionError` with reason="insufficient_candidates" |
| `test_select_frames_empty_metrics_raises` | luminance=[], motion=[] | `SelectionError` with reason="empty_metrics" |
| `test_select_frames_respects_min_gap` | Any selection | `all(abs(frames[i]-frames[j]) >= MIN_GAP for i,j in combinations(...) or i==j)` |
| `test_select_frames_breakdown_matches_frames` | Any selection | `sorted(frames) == sorted(set(breakdown.quantile_dark + breakdown.quantile_bright + breakdown.motion + breakdown.random))` |

### 3. `src/frame_compare/analysis/__init__.py` [MODIFY]

**Purpose:** Add exports for selection module.

**Current exports (Phase 2.1):**

```python
from frame_compare.analysis.types import (
    CacheLoadResult,
    ClipIdentity,
    FrameMetrics,
    FrameSelection,
    MetricsMetadata,
    SelectionBreakdown,
)
__all__ = ["CacheLoadResult", "ClipIdentity", "FrameMetrics", "FrameSelection", "MetricsMetadata", "SelectionBreakdown"]
```

**After modification (additive):**

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

**Required facts to record:**

- RUN_ID: 2025-12-29__p2-3__frame-selection
- Artifact versions: plan-v2, plan-review-v2, impl-v1, verify-v1, review-v1
- Scope: Frame selection algorithms only (Phase 2.2 deferred due to VS dependency)
- SSOT edits: analysis-module.md sections 3.2 and 4.3 clarified
- Verification gates: all passed

### 5. `CHANGELOG.md` [MODIFY]

Entry under `## [Unreleased]`:

```
### Added
- Frame selection algorithms (`select_frames`) with QUANTILE, MOTION, RANDOM, MIXED modes
```

## Acceptance Criteria

- [ ] GIVEN `FrameMetrics` with `LUMINANCE_100` and `MOTION_100` WHEN `select_frames(metrics, config)` with `frame_count=10, mode=MIXED` THEN returns `FrameSelection` with exactly 10 unique sorted frames and breakdown sums to 10
- [ ] GIVEN same seed=42 and metrics WHEN `select_frames` called twice THEN returns identical frame lists
- [ ] GIVEN `FrameMetrics` with only 5 frames WHEN `select_frames` with `frame_count=10` THEN raises `SelectionError(reason="insufficient_candidates", requested=10, found=<N>)`
- [ ] GIVEN `FrameMetrics` with empty luminance/motion arrays WHEN `select_frames` called THEN raises `SelectionError(reason="empty_metrics", ...)`

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v2.md
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- **Pure Python only** — Use `random.Random(seed)` for RNG, `sorted()` for sorting. No numpy.
- **`SelectionError` import** — `from frame_compare.errors import SelectionError` (already exists)
- **MIN_GAP constant** — Define as module-level `MIN_GAP: int = 5`
- **Sorted output** — `FrameSelection.frames` must always be sorted ascending
- **Mixed mode allocation** — `quantile_count = frame_count * 40 // 100; motion_count = frame_count * 40 // 100; random_count = frame_count - quantile_count - motion_count`
- **STOP if ambiguous** — Do not make design decisions; escalate

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-3__frame-selection

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v2.md
