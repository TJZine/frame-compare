---
RUN_ID: 2026-01-04__p6-7-1__orchestration-context
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Runtime Context Types)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-1__orchestration-context/plan-v1.md
---

# Implementation Plan: Orchestration Runtime Context Types (ClipState / RunContext)

## Context
**Phase:** 6
**Module:** `frame_compare.orchestration`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
**Dependencies:**
- Existing `frame_compare.vs.types.HDRMetadata` type (referenced by `ClipProbeSnapshot`)
- Existing `frame_compare.utils.types.WorkspacePaths` type (referenced by `RunContext`)
- Existing `frame_compare.config.schema.ConfigSchema` type (referenced by `RunContext`)

## Scope
This plan covers:
- [ ] Create `src/frame_compare/orchestration/context.py` with immutable, canonical per-clip state types per SSOT
- [ ] Implement `ClipState.effective_num_frames()` and `ClipState.with_trim(...)` invariants per SSOT
- [ ] Add unit tests for `ClipState.effective_num_frames()` clamping/non-negativity per SSOT test table

This plan does NOT cover:
- Probe snapshot cache file format and read/write (`generated/clip_probe.toml`) or keying (`compute_probe_cache_key`) — separate Phase 6.7 item
- Runner entry points (`src/frame_compare/runner.py`) or orchestration coordinator/phase execution — separate Phase 6.7 items
- Any integration tests requiring VapourSynth/FFmpeg — deferred to later Phase 6.7 slices

## Contract Impact
**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "3.5 Runtime Context Types (SSOT)"
  - Section: "7. Testing Strategy"
  - Section: "7.1 Unit Tests"

## Files to Create/Modify

### 1. `src/frame_compare/orchestration/context.py`
**Purpose:** Define canonical, immutable per-clip state and run context used across orchestration phases.

**Types to define (spec-anchored):**
- `ClipFingerprint` — stable fingerprint for cache invalidation
- `ClipProbeSnapshot` — cached metadata about a clip (pre-trim)
- `ClipTrimState` — applied trim window (trim-first invariant)
- `ClipAlignmentState` — signed relative alignment offset and source
- `ClipState` — canonical per-clip state (legacy ClipPlan analogue)
- `RunContext` — shared per-run context (reference + comparisons)

**Methods to implement (spec-anchored):**
- `effective_num_frames(self) -> int` — clamps to `[0, num_frames]` domain and never returns negative
- `with_trim(self, *, trim_start_frames: int, trim_end_frame_inclusive: int | None) -> "ClipState"` — enforces `trim_start_frames >= 0`, returns a new instance (no mutation)

**Invariants (must hold, spec-anchored):**
- `ClipState.trim.trim_start_frames >= 0`
- `ClipState.probe` always describes the untrimmed source
- `ClipState.effective_num_frames()` reflects applied trims without re-probing

### 2. `tests/orchestration/test_context.py`
**Purpose:** Unit tests for `ClipState` trim invariants and frame-count clamping.

**Tests required (spec-anchored, orchestration spec §7.1):**
- `test_clip_state_effective_num_frames_clamps_and_never_negative`
  - Cover representative combinations of:
    - `num_frames` in `{0, 1, 10}`
    - `trim_start_frames` in `{0, 1, num_frames-1, num_frames, num_frames+5}`
    - `trim_end_frame_inclusive` as `{None, -1, 0, num_frames-1, num_frames+10}`
  - Assertions:
    - return value is an `int`
    - return value is `>= 0`
    - return value is `<= num_frames`
- `test_clip_state_with_trim_rejects_negative_trim_start_frames`
  - Assert `ValueError` on `trim_start_frames < 0` (trim-first invariant)

## Acceptance Criteria

- [ ] GIVEN `num_frames=10` WHEN trim window is `start=0,end=None` THEN `effective_num_frames()==10`
- [ ] GIVEN `num_frames=10` WHEN trim window is `start=9,end=None` THEN `effective_num_frames()==1`
- [ ] GIVEN `num_frames=10` WHEN trim window is `start>=num_frames` THEN `effective_num_frames()==0`
- [ ] GIVEN `num_frames=10` WHEN trim window has `end_inclusive < start` THEN `effective_num_frames()==0`
- [ ] GIVEN any trim settings THEN `effective_num_frames()` returns an `int` and is never negative
- [ ] GIVEN `trim_start_frames < 0` WHEN calling `with_trim(...)` THEN it raises `ValueError`

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → **Command Canon**.

```bash
.venv/bin/pyright --warnings src/frame_compare/orchestration/context.py tests/orchestration/test_context.py
.venv/bin/ruff check src/frame_compare/orchestration/context.py tests/orchestration/test_context.py
.venv/bin/pytest -q tests/orchestration/test_context.py
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Keep this slice purely in-memory and unit-test-only; do not read/write `clip_probe.toml` in this run.
- Prefer constructing `ClipProbeSnapshot` instances directly in tests (no filesystem fingerprinting needed).
- Ensure `effective_num_frames()` exactly matches the SSOT formula: it must clamp to valid frame indices and return 0 on invalid windows.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-7-1__orchestration-context

## Plan to Review
Read file: .agent-workflow/runs/2026-01-04__p6-7-1__orchestration-context/plan-v1.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-7-1__orchestration-context/plan-review-v1.md
