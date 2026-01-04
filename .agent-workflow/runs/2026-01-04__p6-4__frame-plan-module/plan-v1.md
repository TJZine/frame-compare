---
RUN_ID: 2026-01-04__p6-4__frame-plan-module
VERSION: v1
TARGET: Phase 6 → Item 6.4 (FramePlan Module)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v1.md
---

# Implementation Plan: FramePlan Module

## Context

**Phase:** 6
**Module:** `frame_compare.analysis.frame_plan`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md`
**Dependencies:** `frame_compare.errors.InsufficientFramesError` exists (FC-3004)

## Scope

This plan covers:

- [x] Create `src/frame_compare/analysis/frame_plan.py`
- [x] Implement `FramePlan` dataclass with invariants
- [x] Implement `select_uniform_seeded_frames(num_frames, count, seed) -> FramePlan`
- [x] Implement `_select_from_bin()` helper with blake2s hash
- [x] Implement `create_frame_plan(num_frames, count, seed=None) -> FramePlan`
- [x] Raise `InsufficientFramesError` when count > num_frames
- [x] Write unit tests including cross-session determinism test (subprocess)
- [x] Update `analysis/__init__.py` exports

This plan does NOT cover:

- VSPreview integration (Phase 6.6)
- Metric-based selection (existing in `selection.py`)
- CLI flag wiring for `--skip-analysis` (Phase 6.7+)

## Contract Impact

**Contracts touched:** NO

## SSOT Update Required

> [!IMPORTANT]
> The spec shows `InsufficientFramesError(count=count, available=num_frames)` but the actual
> implementation in `errors.py` is `InsufficientFramesError(path, requested, available)`.
>
> **Resolution:** The frame_plan module operates on in-memory frame counts, not video paths.
> We will pass a placeholder `Path("<frame-plan>")` to satisfy the existing signature.
> This is consistent with the error's purpose (FC-3004: video too short for requested frames).
>
> The spec `frame-plan-module.md` §5 will be updated to show the correct usage pattern.

**SSOT edit required (before implementation):**

- File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md`
- Section: "5. Error Handling"
- Change: Update the example to use the actual error signature:

  ```python
  raise InsufficientFramesError(
      path=Path("<frame-plan>"),
      requested=count,
      available=num_frames,
  )
  ```

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md`:
  - Section: "2. Key Types"
  - Section: "3. Public API"
  - Section: "4. Algorithm Specification"
  - Section: "5. Error Handling"
  - Section: "6. Invariants and Guarantees"
  - Section: "8. Testing Strategy"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md` (MODIFY)

**Purpose:** Fix SSOT error signature mismatch.

**Change:** Update §5 Error Handling example to use actual `InsufficientFramesError(path, requested, available)` signature with `Path("<frame-plan>")` placeholder.

---

### 2. `src/frame_compare/analysis/frame_plan.py` (NEW)

**Purpose:** Deterministic frame selection for `--skip-analysis` path.

**Types to define:**

- `FramePlan` — frozen dataclass per spec §2.1

**Functions to implement (spec-anchored):**

- `select_uniform_seeded_frames(num_frames: int, count: int, seed: int) -> FramePlan` — §3.1
- `create_frame_plan(num_frames: int, count: int, seed: int | None = None) -> FramePlan` — §3.2
- `_select_from_bin(bin_start: int, bin_end: int, seed: int, bin_index: int) -> int` — §4.2

**Algorithm:** Exact implementation per spec §4.3 (bin partitioning + blake2s hash).

---

### 3. `src/frame_compare/analysis/__init__.py` (MODIFY)

**Purpose:** Export new public API.

**Add exports:**

- `FramePlan`
- `select_uniform_seeded_frames`
- `create_frame_plan`

---

### 4. `tests/analysis/test_frame_plan.py` (NEW)

**Purpose:** Unit tests for FramePlan module.

**Tests required:**

| Test Function | Description |
|---------------|-------------|
| `test_select_uniform_seeded_frames_deterministic` | Same inputs twice → identical frames |
| `test_select_uniform_seeded_frames_cross_session` | Subprocess test verifies determinism |
| `test_select_uniform_seeded_frames_single_frame` | count=1 returns valid frame |
| `test_select_uniform_seeded_frames_all_frames` | count=num_frames returns all indices |
| `test_select_uniform_seeded_frames_count_exceeds_available` | Raises InsufficientFramesError |
| `test_select_uniform_seeded_frames_zero_count` | Returns empty FramePlan |
| `test_create_frame_plan_uses_default_seed_when_none` | seed=None uses 42 |
| `test_create_frame_plan_uses_default_seed_when_omitted` | Default arg uses 42 |
| `test_frame_plan_invariants` | Property-based test (Hypothesis) |

**Cross-session test approach:** Use `subprocess.run()` to execute a Python snippet that calls `select_uniform_seeded_frames()` and prints JSON output. Compare against in-process result.

---

### 5. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry.

**Required facts:**

- RUN_ID: `2026-01-04__p6-4__frame-plan-module`
- Scope: FramePlan module implementation for `--skip-analysis` path
- SSOT edit: `frame-plan-module.md` §5 — corrected `InsufficientFramesError` usage
- Out of scope: CLI wiring, VSPreview integration, metric-based selection
- Verification gates: Pyright, Ruff, Pytest, Import-linter

---

### 6. `CHANGELOG.md` (MODIFY)

**Purpose:** Add entry for new feature.

**Entry:** Add `FramePlan` module for deterministic frame selection (skip-analysis mode)

## Acceptance Criteria

- [ ] GIVEN valid inputs WHEN `select_uniform_seeded_frames(1000, 10, 42)` is called THEN returns FramePlan with exactly 10 unique, sorted frames in [0, 1000)
- [ ] GIVEN same inputs WHEN called twice in same process THEN returns identical frames
- [ ] GIVEN same inputs WHEN called in subprocess THEN returns identical frames (cross-session determinism)
- [ ] GIVEN count > num_frames WHEN `select_uniform_seeded_frames(5, 10, 42)` is called THEN raises `InsufficientFramesError` with code FC-3004
- [ ] GIVEN count=0 WHEN `select_uniform_seeded_frames(100, 0, 42)` is called THEN returns FramePlan with empty frames list
- [ ] GIVEN seed=None WHEN `create_frame_plan(100, 10, None)` is called THEN uses seed=42 (SSOT default)
- [ ] GIVEN Hypothesis random inputs WHEN invariants are checked THEN all hold (unique, sorted, in-range, correct count)

## Verification Commands

```bash
# 1. Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v1.md

# 2. Quality gates
.venv/bin/pyright --warnings src/frame_compare/analysis/frame_plan.py
.venv/bin/ruff check src/frame_compare/analysis/frame_plan.py
.venv/bin/pytest -v tests/analysis/test_frame_plan.py

# 3. Import-linter (layer contracts)
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# 4. Full test suite (catch regressions)
.venv/bin/pytest -q
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **blake2s digest_size=8** — Use exactly 8 bytes for hash; convert with `int.from_bytes(digest, "little")`
2. **Bin edge handling** — Last bin must clamp to `num_frames` to avoid off-by-one
3. **Sorted output** — Always sort frames before returning (even if bins are sequential)
4. **Default seed 42** — Must match `ConfigSchema.analysis.random_seed` SSOT default
5. **Subprocess test** — Use `sys.executable` for Python path, pass inputs as CLI args, parse JSON output
6. **Hypothesis test** — Import from `hypothesis` and `hypothesis.strategies`, use `@given` decorator
7. **Error placeholder path** — Use `Path("<frame-plan>")` for InsufficientFramesError

---

> **Proposed RUN_ID:** 2026-01-04__p6-4__frame-plan-module
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2026-01-04__p6-4__frame-plan-module` before running Plan Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-04__p6-4__frame-plan-module

## Plan to Review

Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v1.md
