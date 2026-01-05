---
RUN_ID: 2025-12-29__p2-3__frame-selection
VERSION: v1
TARGET: Phase 2 → Item 2.3
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v1.md
---

# Implementation Plan: Frame Selection Algorithms

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
- [ ] `src/frame_compare/analysis/__init__.py` — update exports
- [ ] `docs/DECISIONS.md` — append run decision entry
- [ ] `CHANGELOG.md` — add entry

This plan does NOT cover:

- Metrics calculation (Phase 2.2, blocked on VS)
- Cache I/O (Phase 2.4)
- Integration with VS module
- `save_frames_data` JSON persistence (deferred to caching phase)

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

**Purpose:** Pure Python/numpy frame selection algorithms.

**Imports:**

```python
from frame_compare.analysis.types import FrameMetrics, FrameSelection, SelectionBreakdown
from frame_compare.config import AnalysisConfig, SelectionMode
```

**Functions to implement (spec-anchored):**

- `select_frames(metrics: FrameMetrics, config: AnalysisConfig) -> FrameSelection`
- `_select_by_quantile(luminance: Sequence[float], count: int, dark_quantile: float, bright_quantile: float) -> tuple[list[int], list[int]]`
- `_select_by_motion(motion: Sequence[float], count: int, exclude: set[int], min_gap: int) -> list[int]`
- `_select_random(frame_count: int, count: int, seed: int, exclude: set[int], min_gap: int) -> list[int]`

**Algorithm details (from spec section 3.2):**

| Mode | Allocation |
|------|------------|
| `QUANTILE` | 100% luminance-based (dark+bright) |
| `MOTION` | 100% high-motion frames |
| `RANDOM` | 100% seeded RNG |
| `MIXED` | 40% quantile + 40% motion + 20% random |

**Determinism:**

- RNG uses `random.Random(seed)` for reproducibility
- Frame lists are always sorted ascending
- Minimum gap of 5 frames between any two selections (configurable via constant `MIN_GAP = 5`)

**Edge cases:**

- Insufficient candidates after deduplication: raise `SelectionError` with available count
- Empty metrics: raise `SelectionError`
- `frame_count=0` in config: raise `SelectionError`

### 2. `tests/analysis/test_selection.py` [NEW]

**Purpose:** Unit tests for selection algorithms.

**Tests required:**

- `test_select_frames_quantile_mode_returns_luminance_extremes` — Given 100-frame metrics with known luminance distribution, select 10 frames in QUANTILE mode, assert 5 darkest + 5 brightest
- `test_select_frames_motion_mode_returns_high_motion` — Given metrics with known motion peaks, select 10 in MOTION mode, assert top 10 motion frames (respecting min gap)
- `test_select_frames_random_mode_same_seed_deterministic` — Run twice with seed=42, assert identical results
- `test_select_frames_random_mode_different_seed_different_results` — seed=42 vs seed=123, assert different
- `test_select_frames_mixed_mode_allocation` — 10 frames in MIXED mode: expect 4 quantile + 4 motion + 2 random
- `test_select_frames_deduplication_skips_already_selected` — Mock scenario where motion/random candidates overlap with quantile
- `test_select_frames_insufficient_candidates_raises` — Only 5 unique frames available, request 10, expect `SelectionError`
- `test_select_frames_empty_metrics_raises` — Empty luminance/motion arrays, expect `SelectionError`
- `test_select_frames_respects_min_gap` — Selection respects MIN_GAP=5 between any two frames
- `test_select_frames_breakdown_matches_frames` — sum of breakdown lists equals len(frames)

**Test fixtures (use testing-strategy SSOT values):**

- Use `tmp_path` for any Path arguments (not applicable here)
- Use `count=10` for frame counts
- Use consistent seed=42 for determinism tests

### 3. `src/frame_compare/analysis/__init__.py` [MODIFY]

**Purpose:** Export `select_frames` and related symbols.

Add exports:

```python
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.types import FrameSelection, SelectionBreakdown
```

### 4. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: 2025-12-29__p2-3__frame-selection
- Artifact versions: plan-v1, plan-review-v1, impl-v1, verify-v1, review-v1
- Scope: Frame selection algorithms only (Phase 2.2 deferred)
- Explicit out-of-scope: Metrics calculation, VS integration, cache I/O
- SSOT edits: none
- Verification gates: all passed

### 5. `CHANGELOG.md` [MODIFY]

**Purpose:** Add entry for frame selection feature.

Entry format (under `## [Unreleased]`):

```
### Added
- Frame selection algorithms (`select_frames`) with QUANTILE, MOTION, RANDOM, MIXED modes
```

## Acceptance Criteria

- [ ] GIVEN `FrameMetrics` with 100 frames WHEN `select_frames(metrics, config)` with `frame_count=10, mode=MIXED` THEN returns `FrameSelection` with exactly 10 unique sorted frames
- [ ] GIVEN same seed and metrics WHEN `select_frames` called twice THEN returns identical frame lists
- [ ] GIVEN fewer available frames than requested WHEN `select_frames` called THEN raises `SelectionError` with descriptive message
- [ ] GIVEN MIXED mode WHEN selection completes THEN `breakdown` sums match: `len(quantile_dark) + len(quantile_bright) + len(motion) + len(random) == frame_count`

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v1.md
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- **No numpy dependency needed** — Pure Python `statistics` module and `random.Random` are sufficient for percentile/RNG operations. If numpy is preferred for performance, use it for quantile calculation only.
- **`SelectionError` must be imported from `frame_compare.errors`** — Verify this error class exists; if not, create a stub or escalate.
- **MIN_GAP constant** — Define as module-level `MIN_GAP: int = 5`. This ensures minimum spacing between selected frames.
- **Sorted output** — `FrameSelection.frames` must always be sorted ascending.
- **Mixed mode allocation** — Use integer division: `quantile_count = frame_count * 40 // 100`, then adjust final bucket to hit exact total.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-3__frame-selection

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v1.md
