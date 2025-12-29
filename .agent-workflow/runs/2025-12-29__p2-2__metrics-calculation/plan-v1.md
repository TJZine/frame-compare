---
RUN_ID: 2025-12-29__p2-2__metrics-calculation
VERSION: v1
TARGET: Phase 2 → Item 2.2 Metrics Calculation
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v1.md
---

# Implementation Plan: Metrics Calculation

## Context

**Phase:** 2
**Module:** analysis
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
**Dependencies:** Phase 2.1 Types (complete), Phase 3.1 Environment (complete), Phase 3.2 Video Loading (complete)

## Scope

This plan covers:

- [x] Create `src/frame_compare/analysis/metrics.py`
- [x] Implement `calculate_metrics(video_paths, config, cache_dir, reporter) -> FrameMetrics`
- [x] Implement `_calculate_luminance(clip, reporter) -> list[float]`
- [x] Implement `_calculate_motion(clip) -> list[float]`
- [x] Add progress reporting callbacks (optional reporter)
- [x] Write unit tests with mock frames
- [x] Write edge case tests (empty, single frame)

This plan does NOT cover:

- Frame selection algorithms (Phase 2.3 — complete)
- Cache persistence (Phase 2.4 — complete)
- Module integration/`__init__.py` exports (Phase 2.5)
- ProgressReporter implementation (assumed to be a Protocol/stub for now)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`:
  - Section: "3.1 calculate_metrics"
  - Section: "4.1 Luminance Calculation"
  - Section: "4.2 Motion Scoring"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. `src/frame_compare/analysis/metrics.py` (NEW)

**Purpose:** Metric calculation logic for frame analysis.

**Functions to implement (spec-anchored):**

- `calculate_metrics(video_paths: list[Path], config: AnalysisConfig, cache_dir: Path, reporter: ProgressReporter | None = None) -> FrameMetrics` — signature + behavior in **SSOT 3.1 calculate_metrics**
- `_calculate_luminance(clip: vs.VideoNode, reporter: ProgressReporter | None = None) -> list[float]` — signature + behavior in **SSOT 4.1 Luminance Calculation**
- `_calculate_motion(clip: vs.VideoNode) -> list[float]` — signature + behavior in **SSOT 4.2 Motion Scoring**

**Implementation notes:**

- Uses `frame_compare.vs.load_source()` to load clips
- Uses `frame_compare.analysis.cache_io.load_cached_metrics()` and `save_metrics_cache()` for cache
- Uses `frame_compare.analysis.cache_io.compute_cache_key()` for fingerprinting
- `ProgressReporter` is a Protocol with `.start_phase()`, `.advance()`, `.complete_phase()` methods (stub if not yet implemented)
- Luminance: Y channel mean normalized to 0-1
- Motion: First frame = 0, subsequent = absolute difference sum normalized by frame size

**ProgressReporter Protocol (for metrics.py TYPE_CHECKING block):**

```python
class ProgressReporter(Protocol):
    def start_phase(self, name: str, total: int) -> None: ...
    def advance(self, count: int = 1) -> None: ...
    def complete_phase(self) -> None: ...
```

### 2. `src/frame_compare/analysis/__init__.py` (MODIFY)

**Purpose:** Export `calculate_metrics` function.

**Changes:**

- Import `calculate_metrics` from `metrics`
- Add `"calculate_metrics"` to `__all__`

### 3. `tests/analysis/test_metrics.py` (NEW)

**Purpose:** Unit tests for metrics calculation.

**Tests required:**

Per SSOT 1.3 Deterministic Test Vector Policy, use mock VapourSynth clips:

**Luminance tests:**

- `test_calculate_luminance_black_frames_returns_zeros` — Mock Y=0 frames, expect `[0.0, 0.0, ...]`
- `test_calculate_luminance_white_frames_returns_ones` — Mock Y=255 frames, expect `[1.0, 1.0, ...]`
- `test_calculate_luminance_mixed_frames_returns_normalized` — Mock mixed Y values, verify 0-1 range
- `test_calculate_luminance_single_frame` — Mock 1-frame clip, returns single-element list
- `test_calculate_luminance_calls_progress_reporter` — Verify `.start_phase()`, `.advance()`, `.complete_phase()` called

**Motion tests:**

- `test_calculate_motion_static_clip_returns_zeros` — Mock identical frames, expect `[0.0, 0.0, ...]`
- `test_calculate_motion_first_frame_is_zero` — Any clip, first motion value is 0.0
- `test_calculate_motion_changing_frames_returns_positive` — Mock different frames, expect positive values
- `test_calculate_motion_single_frame_returns_single_zero` — 1-frame clip, returns `[0.0]`

**Integration tests (calculate_metrics):**

- `test_calculate_metrics_uses_cache_on_hit` — Mock cache hit, verify no VS calls
- `test_calculate_metrics_computes_on_cache_miss` — Mock cache miss, verify VS used
- `test_calculate_metrics_saves_to_cache` — Mock computation, verify `save_metrics_cache` called

**Mocking strategy:**

- Mock `vapoursynth` module and `vs.VideoNode`
- Mock `clip.get_frame(n)` to return frames with `.props` and Y plane array
- Mock `load_source()` to return `SourceInfo` with mock clip
- Mock `load_cached_metrics()` and `save_metrics_cache()` for cache tests

### 4. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2025-12-29__p2-2__metrics-calculation`
- Artifact versions: plan-v1
- Scope: calculate_metrics,_calculate_luminance,_calculate_motion
- SSOT edits: none
- Out-of-scope: ProgressReporter implementation (used as Protocol)

### 5. `CHANGELOG.md` (MODIFY)

**Purpose:** Add short entry for user-visible changes.

**Entry format:**

```markdown
### Added
- `calculate_metrics()` function for per-frame luminance and motion analysis
```

## Acceptance Criteria

- [ ] GIVEN a video clip WHEN `_calculate_luminance(clip)` is called THEN returns list[float] with values in 0-1 range
- [ ] GIVEN identical frames WHEN `_calculate_motion(clip)` is called THEN returns near-zero motion scores
- [ ] GIVEN changing frames WHEN `_calculate_motion(clip)` is called THEN returns positive motion scores
- [ ] GIVEN a valid cache WHEN `calculate_metrics()` is called THEN returns cached metrics without recomputing
- [ ] GIVEN no cache WHEN `calculate_metrics()` is called THEN computes and caches metrics
- [ ] GIVEN a ProgressReporter WHEN calculating luminance THEN reporter callbacks are invoked

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v1.md

# Quality gates
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- **ProgressReporter is optional**: If not provided, skip all progress callbacks. Define the Protocol inline in TYPE_CHECKING block.
- **First frame motion = 0**: The algorithm computes frame-to-frame difference, so frame 0 has no predecessor → motion[0] = 0.0.
- **Normalization for luminance**: Y channel mean divided by 255 (or max bit depth) to get 0-1 range.
- **Normalization for motion**: Sum of absolute pixel differences divided by (width × height × 255) for 8-bit.
- **Use lazy VS import**: `if TYPE_CHECKING: import vapoursynth as vs` pattern.
- **Cache integration**: Call `load_cached_metrics()` first. If hit, return early. If miss, compute and call `save_metrics_cache()`.
- **ClipIdentity construction**: Use `Path.stat()` for size/mtime. SHA1 is optional (None for now).

---

> **Proposed RUN_ID:** 2025-12-29__p2-2__metrics-calculation
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2025-12-29__p2-2__metrics-calculation` before running Plan Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-2__metrics-calculation

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v1.md
