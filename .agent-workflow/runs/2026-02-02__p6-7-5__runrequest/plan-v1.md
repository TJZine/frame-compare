---
RUN_ID: 2026-02-02__p6-7-5__runrequest
VERSION: v1
TARGET: Phase 6 → Item 6.7
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v1.md
---

# Implementation Plan: `RunRequest` (Runner & Phase Orchestration)

## Context

**Phase:** 6
**Checklist Item:** 6.7 — Runner & Phase Orchestration
**Module:** `frame_compare.orchestration`
**Spec Reference:**
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` → §4.4.1
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md` → §3.1
**Dependencies (must already exist):**
- `src/frame_compare/orchestration/` package scaffold exists (incl. `__init__.py`)
- Phase 6.7 prerequisites already implemented (context/probe cache/probe props per checklist)

## Contract Impact

**Contracts touched:** NO

No canonical contract files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` are modified by this slice.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "4.4 Run Coordination"
  - Section: "4.4.1 Request Types"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "3. Runner"
  - Section: "3.1 Types"
  - Section: "9. Testing Strategy"
  - Section: "9.2 Runner Tests"

## Scope

This plan covers:

- [ ] Implement `RunRequest` as a frozen dataclass with the exact field set, types, and defaults from SSOT
- [ ] Export `RunRequest` from `frame_compare.orchestration` public API
- [ ] Add focused unit tests for `RunRequest` defaults and immutability

This plan does NOT cover:

- `RunResult`, `RunDependencies`, `runner.py`, `run(...)`, `execute_run(...)`, or any phase orchestration logic
- CLI behavior changes (argument parsing, config overrides mapping, exit codes)

## Files to Create/Modify

### 1. [NEW] `src/frame_compare/orchestration/coordinator.py`

**Purpose:** Home for run-coordination types/functions (SSOT names this module as the owner of `execute_run(...)` in a later slice). This slice adds **only** the `RunRequest` type.

**Types to define (spec-anchored):**

- `class RunRequest:`

**Constructor call form (spec-anchored):**

- `RunRequest(root: Path, config_path: Path | None = None, input_dir: Path | None = None, ...)`

**Fields (must match SSOT exactly):**

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
- Tonemap overrides:
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

**Key implementation notes:**

- Type-only slice: no path resolution/validation logic here (those belong to preflight + runner wiring later).
- Keep the docstring aligned with SSOT intent: “Complete configuration for a comparison run; fields map to CLI flags or config sections”.

### 2. [MODIFY] `src/frame_compare/orchestration/__init__.py`

**Purpose:** Export `RunRequest` from the orchestration package public surface.

**Change (spec-anchored):**

- Import `RunRequest` from `frame_compare.orchestration.coordinator`
- Add `"RunRequest"` to `__all__`

### 3. [NEW] `tests/orchestration/test_run_request.py`

**Tests required:**

- `test_run_request_defaults` — constructs `RunRequest(root=Path(...))` and asserts default values for all optional/bool fields
- `test_run_request_is_frozen` — verifies attempts to set an attribute raise (frozen dataclass)

## Acceptance Criteria

- [ ] GIVEN `RunRequest(root=Path("x"))` WHEN inspecting fields THEN all defaults match SSOT (all bool flags default `False`, all optionals default `None`)
- [ ] GIVEN a constructed `RunRequest` WHEN attempting to mutate a field THEN an exception is raised (frozen dataclass)
- [ ] GIVEN `frame_compare.orchestration` WHEN importing `RunRequest` THEN it is available as a public export

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v1.md

.venv/bin/pyright --warnings src/frame_compare/orchestration/coordinator.py src/frame_compare/orchestration/__init__.py tests/orchestration/test_run_request.py
.venv/bin/ruff check src/frame_compare/orchestration/coordinator.py src/frame_compare/orchestration/__init__.py tests/orchestration/test_run_request.py
.venv/bin/pytest -v tests/orchestration/test_run_request.py

UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. Keep the `RunRequest` field set identical across both SSOT specs (orchestration-module + cli-module); if drift is discovered, STOP and escalate to Plan Review (SSOT mismatch is not a coding-time decision).
2. Keep `RunRequest` free of side effects (no filesystem reads, no environment probing); validation belongs in preflight/runner phases.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

You MUST follow FC2 STOP rules and templates from:
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md

## RUN_ID

2026-02-02__p6-7-5__runrequest

## Plan to Review

Read file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (templates + checklist)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-review-v1.md
