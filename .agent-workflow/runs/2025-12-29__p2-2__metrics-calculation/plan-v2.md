---
RUN_ID: 2025-12-29__p2-2__metrics-calculation
VERSION: v2
TARGET: Phase 2 → Item 2.2 Metrics Calculation
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v2.md
---

# Implementation Plan: Metrics Calculation

## Changes Since plan-v1

- **SSOT Updated**: Added deterministic specs to `analysis-module.md`:
  - Section 3.1: Clip selection (reference only), metadata population, cache invariant, error classes
  - Section 4.1: Frame plane extraction API, bit-depth normalization formula, format conversion
  - Section 4.2: Motion algorithm with output length/invariants, same normalization rules
- **Scope Clarified**: Removed `__init__.py` export changes (deferred to Phase 2.5)
- **Tests Added**: Empty clip test, failure-mode test asserting FC-4002
- **Spec Anchors Updated**: Added error handling anchor

## Context

**Phase:** 2
**Module:** analysis
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
**Dependencies:** Phase 2.1 Types (complete), Phase 2.4 Cache I/O (complete), Phase 3.2 Video Loading (complete)

## Scope

This plan covers:

- [x] Create `src/frame_compare/analysis/metrics.py`
- [x] Implement `calculate_metrics(video_paths, config, cache_dir, reporter) -> FrameMetrics`
- [x] Implement `_calculate_luminance(clip, reporter) -> list[float]`
- [x] Implement `_calculate_motion(clip) -> list[float]`
- [x] Add progress reporting callbacks (optional reporter)
- [x] Write unit tests with mock frames
- [x] Write edge case tests (empty clip, single frame)
- [x] Write failure-mode test asserting MetricsCalculationError (FC-4002)

This plan does NOT cover:

- Frame selection algorithms (Phase 2.3 — complete)
- Cache persistence (Phase 2.4 — complete)
- Module integration/`__init__.py` exports (Phase 2.5)
- ProgressReporter full implementation (stub Protocol only)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`:
  - Section: "3.1 calculate_metrics"
  - Section: "4.1 Luminance Calculation"
  - Section: "4.2 Motion Scoring"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "3.4 Processing Errors (FC-4xxx) — Exit Code 5"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. `src/frame_compare/analysis/metrics.py` (NEW)

**Purpose:** Metric calculation logic for frame analysis.

**Functions to implement (spec-anchored):**

- `calculate_metrics(video_paths: list[Path], config: AnalysisConfig, cache_dir: Path, reporter: ProgressReporter | None = None) -> FrameMetrics`
- `_calculate_luminance(clip: vs.VideoNode, reporter: ProgressReporter | None = None) -> list[float]`
- `_calculate_motion(clip: vs.VideoNode) -> list[float]`

All signatures and behavior defined in SSOT 3.1, 4.1, 4.2 respectively.

**ProgressReporter Protocol (inline in TYPE_CHECKING block):**

```python
class ProgressReporter(Protocol):
    def start_phase(self, name: str, total: int) -> None: ...
    def advance(self, count: int = 1) -> None: ...
    def complete_phase(self) -> None: ...
```

### 2. `tests/analysis/test_metrics.py` (NEW)

**Purpose:** Unit tests for metrics calculation.

**Luminance tests:**

- `test_calculate_luminance_black_frames_returns_zeros` — Mock Y=0 frames, expect `[0.0, ...]`
- `test_calculate_luminance_white_frames_returns_ones` — Mock Y=255 (8-bit max), expect `[1.0, ...]`
- `test_calculate_luminance_single_frame` — 1-frame clip, returns single-element list
- `test_calculate_luminance_calls_progress_reporter` — Verify callbacks invoked

**Motion tests:**

- `test_calculate_motion_static_clip_returns_zeros` — Identical frames, expect `[0.0, 0.0, ...]`
- `test_calculate_motion_first_frame_is_zero` — Any clip, `motion[0] == 0.0`
- `test_calculate_motion_changing_frames_returns_positive` — Different frames, positive values
- `test_calculate_motion_single_frame_returns_single_zero` — 1-frame clip, `[0.0]`
- `test_calculate_motion_output_length_equals_num_frames` — Assert `len(motion) == clip.num_frames`

**Edge case tests:**

- `test_calculate_luminance_empty_clip_raises_error` — 0-frame clip raises `MetricsCalculationError`
- `test_calculate_motion_empty_clip_raises_error` — 0-frame clip raises `MetricsCalculationError`

**Failure mode tests:**

- `test_calculate_metrics_frame_access_failure_raises_fc4002` — Mock frame access exception, assert `MetricsCalculationError` raised with `code == "FC-4002"`

**Integration tests (calculate_metrics):**

- `test_calculate_metrics_uses_cache_on_hit` — Mock cache hit, verify no VS load
- `test_calculate_metrics_computes_on_cache_miss` — Mock miss, verify metrics computed
- `test_calculate_metrics_saves_to_cache` — Verify `save_metrics_cache` called
- `test_calculate_metrics_analyzes_reference_only` — Multiple paths, only `video_paths[0]` loaded

**Mocking strategy:**

- Mock `vapoursynth` module via `sys.modules` patching
- Mock `clip.get_frame(n)` to return mock with `__getitem__(0)` returning numpy array
- Mock `load_source()` from `frame_compare.vs`
- Mock `load_cached_metrics()` / `save_metrics_cache()` from `frame_compare.analysis.cache_io`

### 3. `docs/DECISIONS.md` (MODIFY)

**Required facts to record:**

- RUN_ID: `2025-12-29__p2-2__metrics-calculation`
- Artifact versions: plan-v1, plan-review-v1, plan-v2
- Scope: calculate_metrics,_calculate_luminance,_calculate_motion
- SSOT edits: Updated sections 3.1, 4.1, 4.2 in analysis-module.md
- Out-of-scope: `__init__.py` exports (Phase 2.5)

### 4. `CHANGELOG.md` (MODIFY)

**Entry format:**

```markdown
### Added
- `calculate_metrics()` function for per-frame luminance and motion analysis
```

## Acceptance Criteria

- [ ] GIVEN reference clip WHEN `_calculate_luminance(clip)` called THEN returns `list[float]` with `len == num_frames` and values in `[0.0, 1.0]`
- [ ] GIVEN static frames WHEN `_calculate_motion(clip)` called THEN returns near-zero scores with `motion[0] == 0.0`
- [ ] GIVEN changing frames WHEN `_calculate_motion(clip)` called THEN returns positive motion scores
- [ ] GIVEN 0-frame clip WHEN metrics calculated THEN raises `MetricsCalculationError (FC-4002)`
- [ ] GIVEN valid cache WHEN `calculate_metrics()` called THEN returns cached metrics without recomputing
- [ ] GIVEN cache miss WHEN `calculate_metrics()` called THEN computes and caches metrics
- [ ] GIVEN multiple video_paths WHEN `calculate_metrics()` called THEN only `video_paths[0]` is analyzed

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v2.md

# Quality gates
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- **STOP rule**: If any SSOT detail is missing or ambiguous, STOP and return to Planning.
- **Reference clip only**: Only load and analyze `video_paths[0]`. Other paths used for ClipIdentity.
- **Normalization formula**: `max_value = (1 << bits_per_sample) - 1` for int; `1.0` for float.
- **Format conversion**: If not YUV, use `clip.resize.Bicubic(format=vs.YUV420P8)`.
- **Empty clip handling**: Check `clip.num_frames == 0` and raise `MetricsCalculationError` early.
- **ProgressReporter is optional**: Skip callbacks if `reporter is None`.
- **Motion[0] invariant**: Always 0.0 (no predecessor frame).

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-2__metrics-calculation

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v2.md
