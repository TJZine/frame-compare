---
RUN_ID: 2025-12-29__p2-3__frame-selection
VERSION: v4
TARGET: Phase 2 → Item 2.3
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v3.md
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md
---

# Implementation Plan: Frame Selection Algorithms

## Changes Since plan-v3

- **Fixed random-mode expected outputs**: Corrected to SSOT-derived values (seed=42, seed=123)
- **Removed all placeholders**: Error tests now have fully explicit configs and assertions
- **Made SelectionError assertions mechanically checkable**: Added `exc.value.code` and `exc.value.context.details` assertions

## Context

**Phase:** 2, **Module:** analysis
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
**Dependencies:** Phase 2.1 Types (complete), `frame_compare.config.SelectionMode`

## Scope

- [ ] `src/frame_compare/analysis/selection.py` — selection algorithms
- [ ] `tests/analysis/test_selection.py` — unit tests
- [ ] `src/frame_compare/analysis/__init__.py` — update exports (additive)
- [ ] `docs/DECISIONS.md` — append run decision entry
- [ ] `CHANGELOG.md` — add entry

**NOT covered:** Metrics calculation (Phase 2.2), Cache I/O (Phase 2.4), `save_frames_data`.

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

**Imports:**

```python
from __future__ import annotations
import random
from collections.abc import Sequence
from frame_compare.analysis.types import FrameMetrics, FrameSelection, SelectionBreakdown
from frame_compare.config import AnalysisConfig, SelectionMode
from frame_compare.errors import SelectionError
```

**Constants:** `MIN_GAP: int = 5`

**Functions:**

- `select_frames(metrics: FrameMetrics, config: AnalysisConfig) -> FrameSelection`
- `_select_by_quantile(luminance: Sequence[float], count: int) -> tuple[list[int], list[int]]`
- `_select_by_motion(motion: Sequence[float], count: int, exclude: set[int], min_gap: int) -> list[int]`
- `_select_random(total_frames: int, count: int, seed: int, exclude: set[int], min_gap: int) -> list[int]`

**Error handling:**

- Empty: `raise SelectionError(reason="empty_metrics", requested=config.frame_count, found=0)`
- Insufficient: `raise SelectionError(reason="insufficient_candidates", requested=config.frame_count, found=len(selected))`

### 2. `tests/analysis/test_selection.py` [NEW]

**Helpers:**

```python
from fractions import Fraction
from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.config import AnalysisConfig, SelectionMode

def make_metrics(luminance: list[float], motion: list[float]) -> FrameMetrics:
    return FrameMetrics(
        luminance=luminance, motion=motion,
        metadata=MetricsMetadata(
            frame_count=len(luminance), fps=Fraction(24), config_fingerprint="fp",
            clips=[ClipIdentity(path="video.mkv", size=1, mtime=1.0, sha1=None)], version=2))

def make_config(*, frame_count: int, selection_mode: SelectionMode, random_seed: int = 42) -> AnalysisConfig:
    return AnalysisConfig(frame_count=frame_count, selection_mode=selection_mode, random_seed=random_seed)
```

**Test Data:**

```python
LUMINANCE_100 = [i / 100.0 for i in range(100)]
MOTION_100 = [1.0 if i in {50, 60, 70, 80, 90} else 0.1 for i in range(100)]
```

**Tests (10 total):**

| # | Test Name | Input | Assert |
|---|-----------|-------|--------|
| 1 | `test_quantile_mode_returns_luminance_extremes` | `make_metrics(LUMINANCE_100, MOTION_100)`, `make_config(frame_count=10, selection_mode=SelectionMode.QUANTILE)` | `result.frames == [0,1,2,3,4,95,96,97,98,99]`; `result.breakdown.quantile_dark == [0,1,2,3,4]`; `result.breakdown.quantile_bright == [95,96,97,98,99]` |
| 2 | `test_motion_mode_returns_high_motion` | `make_metrics(LUMINANCE_100, MOTION_100)`, `make_config(frame_count=5, selection_mode=SelectionMode.MOTION)` | `result.frames == [50,60,70,80,90]` |
| 3 | `test_random_mode_same_seed_deterministic` | `make_config(frame_count=10, selection_mode=SelectionMode.RANDOM, random_seed=42)` | `select_frames(...) == select_frames(...)` (two calls) |
| 4 | `test_random_mode_different_seed_exact_outputs` | See below | seed=42: `frames==[1,9,15,42,50,55,65,70,78,91]`; seed=123: `frames==[1,7,24,29,44,50,63,75,87,93]` |
| 5 | `test_mixed_mode_allocation` | `make_config(frame_count=10, selection_mode=SelectionMode.MIXED)` | `len(breakdown.quantile_dark)+len(breakdown.quantile_bright)==4`; `len(breakdown.motion)==4`; `len(breakdown.random)==2` |
| 6 | `test_deduplication_skips_already_selected` | luminance extremes at 0,99 + motion peaks at 0,99 | motion skips 0,99; no duplicates in final `frames` |
| 7 | `test_insufficient_candidates_raises` | `make_metrics([0.1]*5, [0.1]*5)`, `make_config(frame_count=10, selection_mode=SelectionMode.QUANTILE, random_seed=42)` | `pytest.raises(SelectionError)`; `exc.value.code == "FC-4012"`; `exc.value.context.details == {"reason": "insufficient_candidates", "requested": 10, "found": 5}` |
| 8 | `test_empty_metrics_raises` | `make_metrics([], [])`, `make_config(frame_count=10, selection_mode=SelectionMode.QUANTILE, random_seed=42)` | `pytest.raises(SelectionError)`; `exc.value.code == "FC-4012"`; `exc.value.context.details == {"reason": "empty_metrics", "requested": 10, "found": 0}` |
| 9 | `test_motion_selection_respects_min_gap` | `make_config(selection_mode=SelectionMode.MOTION)` | `all(abs(frames[i]-frames[j]) >= 5 for i in range(len(frames)) for j in range(i+1, len(frames)))` |
| 10 | `test_random_selection_respects_min_gap` | `make_config(selection_mode=SelectionMode.RANDOM)` | `all(abs(frames[i]-frames[j]) >= 5 for i in range(len(frames)) for j in range(i+1, len(frames)))` |

### 3. `src/frame_compare/analysis/__init__.py` [MODIFY]

**After:**

```python
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.types import (CacheLoadResult, ClipIdentity, FrameMetrics, FrameSelection, MetricsMetadata, SelectionBreakdown)
__all__ = ["CacheLoadResult", "ClipIdentity", "FrameMetrics", "FrameSelection", "MetricsMetadata", "SelectionBreakdown", "select_frames"]
```

### 4. `docs/DECISIONS.md` & `CHANGELOG.md` [MODIFY]

As specified in plan-v3.

## Acceptance Criteria

- [ ] `select_frames(..., mode=QUANTILE, frame_count=10)` returns `frames==[0,1,2,3,4,95,96,97,98,99]`
- [ ] Same seed → identical results; Different seeds → SSOT-derived exact outputs
- [ ] `SelectionError` with `code=="FC-4012"` and correct `context.details` for error cases

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Notes for Coding Agent

- **Pure Python only** — `random.Random(seed)`, `sorted()`. No numpy.
- **MIN_GAP=5** applies to motion/random phases only.
- **Error assertions** — Use `exc.value.code` and `exc.value.context.details`.
- **STOP if ambiguous**.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-3__frame-selection

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v4.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v4.md
