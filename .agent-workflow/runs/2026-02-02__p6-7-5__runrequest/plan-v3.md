---
RUN_ID: 2026-02-02__p6-7-5__runrequest
VERSION: v3
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement `RunRequest` dataclass per spec
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v2.md
  - .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v3.md
---

# Implementation Plan: `RunRequest` (Runner & Phase Orchestration)

## Changes Since plan-v2

- Moved the single-line `RunRequest(...)` signature into the standard “Functions to implement” section and removed any other bullet-backticked parentheses elsewhere (to keep `validate_spec_anchors.py` signature parsing unambiguous).
- Kept all prior plan-v2 requirements intact (explicit field order, SSOT reconciliation note, explicit tests, public export coverage).

---

## Context

**Phase:** 6
**Checklist Item:** 6.7 — Runner & Phase Orchestration
**Module:** `frame_compare.orchestration`
**Spec Reference (SSOT):**
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` → "4.4 Run Coordination" → "4.4.1 Request Types"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md` → "3. Runner" → "3.1 Types"
**Dependencies (must already exist):**
- `src/frame_compare/orchestration/` package scaffold exists (including `__init__.py`)
- Phase 6.7 prerequisites already implemented (context/probe cache/probe props per checklist)

## Contract Impact

**Contracts touched:** NO

No canonical contract files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` are modified by this slice.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "4.4 Run Coordination"
  - Section: "4.4.1 Request Types" (authoritative `RunRequest` field order for `frame_compare.orchestration.coordinator`)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "3. Runner"
  - Section: "3.1 Types" (`RunRequest` names/types/defaults must match; ordering may differ)
  - Section: "9. Testing Strategy"
  - Section: "9.2 Runner Tests"

## Scope

This plan covers:
- [ ] Implement `RunRequest` as a frozen dataclass with the exact field names, types, and defaults from SSOT
- [ ] Export `RunRequest` from `frame_compare.orchestration` public API
- [ ] Add focused unit tests for `RunRequest` defaults and immutability

This plan does NOT cover:
- `RunResult`, `RunDependencies`, runner logic, phase orchestration logic, or CLI parsing
- Any behavior changes to mapping precedence, error codes, or external-tool invocation

## Files to Create/Modify

### 1. `src/frame_compare/orchestration/coordinator.py`

**Purpose:** Home for run-coordination types/functions (SSOT names this module as the owner of the run executor in a later slice). This slice adds only the `RunRequest` type.

**Types to define (spec-anchored):**
- `RunRequest` — frozen dataclass holding complete run configuration (fields map to CLI flags or config file sections)

**Functions to implement (spec-anchored):**

- `RunRequest(root: Path, config_path: Path | None = None, input_dir: Path | None = None, no_cache: bool = False, from_cache_only: bool = False, skip_analysis: bool = False, skip_metadata: bool = False, skip_dovi: bool = False, no_upload: bool = False, tm_preset: str | None = None, tm_target_nits: int | None = None, tm_curve: str | None = None, frame_count: int | None = None, seed: int | None = None, overlay_mode: str | None = None, no_color: bool = False, quiet: bool = False, verbose: bool = False, json_output: bool = False)` — public constructor signature implied by the dataclass fields; field order must match `orchestration-module.md` "4.4.1 Request Types"

**Fields (must match SSOT exactly; authoritative order is `orchestration-module.md` "4.4.1 Request Types"):**

- Core paths:
  - `root: Path`
  - `config_path: Path | None = None`
  - `input_dir: Path | None = None`
- Cache behavior:
  - `no_cache: bool = False`
  - `from_cache_only: bool = False`
- Skip flags:
  - `skip_analysis: bool = False`
  - `skip_metadata: bool = False`
  - `skip_dovi: bool = False`
  - `no_upload: bool = False`
- Tonemap overrides (highest priority):
  - `tm_preset: str | None = None`
  - `tm_target_nits: int | None = None`
  - `tm_curve: str | None = None`
- Frame selection overrides:
  - `frame_count: int | None = None`
  - `seed: int | None = None`
- Output behavior:
  - `overlay_mode: str | None = None`
  - `no_color: bool = False`
  - `quiet: bool = False`
  - `verbose: bool = False`
  - `json_output: bool = False`

**SSOT reconciliation (order drift):**

- Implement the `RunRequest` field order exactly as shown in the `orchestration-module.md` "4.4.1 Request Types" code block.
- The `cli-module.md` "3.1 Types" definition uses a different order for some fields; this ordering difference is non-semantic for Python keyword arguments.
- STOP only if any field name, type, or default differs from either SSOT spec; do not STOP for order-only differences.

**Key implementation notes:**

- Type-only slice: no path resolution, validation, or side effects in this dataclass.
- Keep the class docstring aligned with SSOT intent: “Complete configuration for a comparison run. All fields map to CLI flags or config file sections.”

### 2. `src/frame_compare/orchestration/__init__.py`

**Purpose:** Export `RunRequest` from the orchestration package public surface.

**Change (spec-anchored):**
- Import `RunRequest` from `frame_compare.orchestration.coordinator`
- Add `"RunRequest"` to `__all__`

### 3. `tests/orchestration/test_run_request.py`

**Tests required:**

- `test_run_request_defaults` — constructs `RunRequest(root=Path("x"))` and asserts:
  - request.root == Path("x")
  - Optionals default `None`:
    - request.config_path is None
    - request.input_dir is None
    - request.tm_preset is None
    - request.tm_target_nits is None
    - request.tm_curve is None
    - request.frame_count is None
    - request.seed is None
    - request.overlay_mode is None
  - Bool flags default `False`:
    - request.no_cache is False
    - request.from_cache_only is False
    - request.skip_analysis is False
    - request.skip_metadata is False
    - request.skip_dovi is False
    - request.no_upload is False
    - request.no_color is False
    - request.quiet is False
    - request.verbose is False
    - request.json_output is False
- `test_run_request_is_frozen` — verifies attempts to set an attribute raise `dataclasses.FrozenInstanceError`
- `test_run_request_exported_from_orchestration` — asserts `from frame_compare.orchestration import RunRequest as PublicRunRequest` works and `PublicRunRequest is RunRequest`

## Acceptance Criteria

- [ ] GIVEN `RunRequest(root=Path("x"))` WHEN inspecting fields THEN all defaults match SSOT (all bool flags default `False`, all optionals default `None`)
- [ ] GIVEN a constructed `RunRequest` WHEN attempting to mutate a field THEN `dataclasses.FrozenInstanceError` is raised (frozen dataclass)
- [ ] GIVEN `frame_compare.orchestration` WHEN importing `RunRequest` THEN it is available as a public export

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v3.md

.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q

UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. Implement `RunRequest` field order exactly as shown in `orchestration-module.md` "4.4.1 Request Types".
2. If `cli-module.md` "3.1 Types" ordering differs, do not STOP (order is non-semantic); STOP only for mismatched names/types/defaults.
3. Keep `RunRequest` free of side effects (no filesystem reads, no environment probing); validation belongs in later preflight/runner slices.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

You MUST follow FC2 STOP rules and templates from:
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md

## RUN_ID

2026-02-02__p6-7-5__runrequest

## Plan to Review

Read file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v3.md

## Context Files to Read

1. Read file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-review-v1.md
2. Read file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v2.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
5. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (templates + checklist)

## Your Task

Validate the plan using the 9-point checklist. Confirm Decision Points Remaining is NONE. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-review-v2.md
