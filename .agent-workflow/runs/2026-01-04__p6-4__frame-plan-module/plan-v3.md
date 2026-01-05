---
RUN_ID: 2026-01-04__p6-4__frame-plan-module
VERSION: v3
TARGET: Phase 6 → Item 6.4 (FramePlan Module)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v2.md
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md
---

# Implementation Plan: FramePlan Module

## Changes Since plan-v2

- Added the SSOT-edited spec file to “Files to Create/Modify” with exact headings changed.
- Added required one-line backticked public signature for the FC-3004 constructor update.
- Named the new targeted FC-3004 payload-shape test in `tests/test_errors.py` with minimum required assertions.
- Updated plan validation + NEXT prompt wiring from `plan-v2` → `plan-v3`.

## Context

**Phase:** 6
**Module:** `frame_compare.analysis.frame_plan`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md`
**Dependencies (SSOT):**
- `InsufficientFramesError` (FC-3004) contract is defined in `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml` and `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md` (signature + message template).

## Scope

This plan covers:

- [ ] Restore FC-3004 (`InsufficientFramesError`) implementation in `src/frame_compare/errors.py` to SSOT shape (`path`, `count`, `required`) and SSOT message/hint template.
- [ ] Implement `frame_compare.analysis.frame_plan` per SSOT (binning + blake2s-based selection).
- [ ] Add unit + property-based tests per SSOT, including cross-session determinism.
- [ ] Export public API from `src/frame_compare/analysis/__init__.py`.

This plan does NOT cover:

- VSPreview integration (Phase 6.6)
- Metric-based selection (existing in `selection.py`)
- CLI wiring for `--skip-analysis` (Phase 6.7+)
- Any other error-code drift beyond FC-3004

## Contract Impact

**Contracts touched:** NO

> [!IMPORTANT]
> This plan restores runtime code to match existing canonical SSOT contracts for FC-3004. It does not change the contracts.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md`:
  - Section: "2. Key Types"
  - Section: "3. Public API"
  - Section: "4.1 Bin Partitioning"
  - Section: "4.2 Frame Selection Per Bin"
  - Section: "4.3 Complete Algorithm"
  - Section: "5. Error Handling"
  - Section: "6. Invariants and Guarantees"
  - Section: "8. Testing Strategy"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "3.3 Input Errors (FC-3xxx) — Exit Code 4"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md` (MODIFY)

**Purpose:** Keep FramePlan SSOT aligned with FC-3004 contracts and ensure spec-anchor validators can traverse the algorithm examples deterministically.

**SSOT edits already made (headings; copy/paste exact):**
- "4.1 Bin Partitioning" (code-fence formatting: avoid `# ...` at column 1)
- "4.3 Complete Algorithm" (FC-3004 raise example uses `Path("<frame-plan>")` and SSOT keys `count`/`required`)
- "5. Error Handling" (FC-3004 example uses `Path("<frame-plan>")` and SSOT keys `count`/`required`)
- "7. Integration with Render Module" (code-fence formatting: avoid `# ...` at column 1)
- "9. AI Agent Implementation Prompt" (code-fence formatting: avoid `# ...` at column 1)

### 2. `src/frame_compare/errors.py` (MODIFY)

**Purpose:** Restore FC-3004 implementation to match SSOT contracts (avoid institutionalizing drift in FramePlan).

**Public signature (required):**
- `InsufficientFramesError(path: Path, count: int, required: int) -> None`

**Change (spec-anchored):**
- Update `InsufficientFramesError.__init__` signature to match `errors-module.md` “3.3 Input Errors (FC-3xxx) — Exit Code 4”.
- Update `ErrorContext.message`, `ErrorContext.hint`, and `ErrorContext.details` keys to match SSOT for FC-3004.

### 3. `tests/test_errors.py` (MODIFY)

**Purpose:** Keep the error contract test aligned with FC-3004 signature and assert SSOT payload shape.

**Tests required:**
- Update the parametrized constructor call for `InsufficientFramesError` to the (path, count, required) signature.
- Add targeted test:
  - `test_insufficient_frames_error_details_shape`
  - Minimum assertions:
    - `.code == "FC-3004"`
    - `.context.details` has keys `{"path", "count", "required"}` (and does not use `requested` / `available`)

### 4. `src/frame_compare/analysis/frame_plan.py` (NEW)

**Purpose:** Deterministic frame selection for `--skip-analysis` path.

**Types to define (spec-anchored):**
- `FramePlan` — frozen dataclass per `frame-plan-module.md` “2.1 FramePlan”

**Functions to implement (spec-anchored):**
- `select_uniform_seeded_frames(num_frames: int, count: int, seed: int) -> FramePlan` — `frame-plan-module.md` “3.1 Frame Selection”
- `create_frame_plan(num_frames: int, count: int, seed: int | None = None) -> FramePlan` — `frame-plan-module.md` “3.2 FramePlan Creation Helper”
- `_select_from_bin(bin_start: int, bin_end: int, seed: int, bin_index: int) -> int` — `frame-plan-module.md` “4.2 Frame Selection Per Bin”

**Error behavior (spec-anchored):**
- If `count > num_frames`, raise `InsufficientFramesError(path=Path("<frame-plan>"), count=num_frames, required=count)` per `frame-plan-module.md` “4.3 Complete Algorithm” and “5. Error Handling”.

### 5. `src/frame_compare/analysis/__init__.py` (MODIFY)

**Purpose:** Export new public API.

**Add exports:**
- `FramePlan`
- `select_uniform_seeded_frames`
- `create_frame_plan`

### 6. `tests/analysis/test_frame_plan.py` (NEW)

**Purpose:** Unit tests for FramePlan module.

**Tests required (spec-anchored):**
- Implement unit test list in `frame-plan-module.md` “8.1 Unit Tests”.
- Implement property-based invariants test in `frame-plan-module.md` “8.2 Property-Based Tests”.

**Negative-case contract assertion (required by this plan):**
- In the `count > num_frames` test, assert:
  - `excinfo.value.code == "FC-3004"`
  - `excinfo.value.context.details["count"] == num_frames`
  - `excinfo.value.context.details["required"] == count`
  - `excinfo.value.context.details["path"] == "<frame-plan>"` (string form of the placeholder path)

### 7. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append a run decision entry (repo persistence).

**Required facts to record (bullets; do not prewrite exact prose):**
- RUN_ID + artifact versions (plan/plan-review/impl/verify/review)
- Scope clarifications and explicit out-of-scope items
- SSOT edits made this run (spec file path + exact headings changed)
- FC-3004 drift resolution: restored runtime implementation to match SSOT
- Verification gates run + pass/fail

### 8. `CHANGELOG.md` (MODIFY)

**Purpose:** Add a short entry for user-visible changes.

**Entry:** Add `FramePlan` module for deterministic frame selection (skip-analysis mode)

## Acceptance Criteria

- [ ] GIVEN valid inputs WHEN `select_uniform_seeded_frames(1000, 10, 42)` is called THEN returns `FramePlan` with exactly 10 unique, sorted frames in `[0, 1000)`
- [ ] GIVEN same inputs WHEN called twice in the same process THEN returns identical frames
- [ ] GIVEN same inputs WHEN called in a subprocess THEN returns identical frames (cross-session determinism)
- [ ] GIVEN `count > num_frames` WHEN called THEN raises `InsufficientFramesError` with code FC-3004 and details keys `path`, `count`, `required`
- [ ] GIVEN `count=0` WHEN called THEN returns `FramePlan(frames=[])` with `count=0`
- [ ] GIVEN `seed=None` WHEN `create_frame_plan(...)` is called THEN uses seed `42`
- [ ] GIVEN Hypothesis-generated inputs WHEN invariants are checked THEN all invariants hold (unique, sorted, in-range, correct count)

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → Command Canon.

```bash
# 1. Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md

# 2. Quality gates (targeted first)
.venv/bin/pyright --warnings src/frame_compare/analysis/frame_plan.py src/frame_compare/errors.py
.venv/bin/ruff check src/frame_compare/analysis/frame_plan.py src/frame_compare/errors.py tests/test_errors.py tests/analysis/test_frame_plan.py
.venv/bin/pytest -v tests/test_errors.py tests/analysis/test_frame_plan.py

# 3. Import-linter (layer contracts)
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# 4. Full suite (regressions)
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Use `hashlib.blake2s(..., digest_size=8)` and `int.from_bytes(digest, "little")` exactly as specified in `frame-plan-module.md` “4.2 Frame Selection Per Bin”.
- Ensure last bin clamps `bin_end = num_frames` (off-by-one prevention) per `frame-plan-module.md` “4.3 Complete Algorithm”.
- Always `frames.sort()` before returning per `frame-plan-module.md` “4.3 Complete Algorithm”.
- For FC-3004 in FramePlan, always use deterministic placeholder `Path("<frame-plan>")` per `frame-plan-module.md` “5. Error Handling”.
- **STOP/escale:** If any runtime callers exist that depend on the old `InsufficientFramesError(path, requested, available)` signature, stop and return to Planning to either update all call sites in-scope or split into a dedicated corrective run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-4__frame-plan-module

## Plan to Review
Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v3.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v3.md
