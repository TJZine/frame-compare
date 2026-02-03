---
RUN_ID: 2026-02-02__p6-7-6__runresult
VERSION: v14
TARGET: Phase 6 → Item 6.7
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-6__runresult/plan-v13.md
  - .agent-workflow/runs/2026-02-02__p6-7-6__runresult/plan-review-v13.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-6__runresult/plan-v14.md
---

# Implementation Plan: `RunResult` (Runner & Phase Orchestration)

## Changes Since plan-v13

- No scope or behavioral changes; re-issued plan to refresh artifact versioning and NEXT block wiring for the Plan Review Agent.
- Keeps run-directory hygiene as a required must-pass gate.

## Context

**Phase:** 6
**Checklist Item:** 6.7 — Runner & Phase Orchestration
**Module:** `frame_compare.orchestration`
**Spec Reference:**
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` → §4.4.2
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md` → §3.1
**Dependencies (must already exist):**
- `src/frame_compare/orchestration/` package scaffold exists (incl. `__init__.py`)
- `src/frame_compare/orchestration/coordinator.py` exists and already defines `RunRequest` from the prior slice (Phase 6 → Item 6.7.5)

## Run-Directory Hygiene (Required Gate)

Before advancing phases, the run directory must pass:

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2026-02-02__p6-7-6__runresult
```

## Contract Impact

**Contracts touched:** NO

No canonical contract files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` are modified by this slice.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "4.4 Run Coordination"
  - Section: "4.4.2 Result Types"
  - Section: "4.4.4 Phase Ordering (SSOT)"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "3.1 Types"
  - Section: "9. Testing Strategy"
  - Section: "9.2 Runner Tests"

## Scope

This plan covers:

- [ ] Implement `RunResult` as a frozen dataclass with the exact field set, types, and defaults from SSOT
- [ ] Export `RunResult` from `frame_compare.orchestration` public API
- [ ] Add focused unit tests for `RunResult` defaults, distinct default factories, and immutability

This plan does NOT cover:

- `RunDependencies`, `runner.py`, the `run` entry point, the `execute_run` orchestration entry point, or any phase orchestration logic
- CLI behavior changes (argument parsing, config overrides mapping, exit codes)

## Files to Create/Modify

### 1. `src/frame_compare/orchestration/coordinator.py`

**Purpose:** Home for run-coordination types/functions. This slice adds **only** the `RunResult` type.

**Types to define (spec-anchored):**

- `RunResult` — complete result from a comparison run (see SSOT anchors)

**Functions to implement (spec-anchored):**

- `RunResult(success: bool, screenshot_dir: Path | None = None, slowpics_url: str | None = None, report_path: Path | None = None, frame_count: int = 0, clips_processed: int = 0, duration_seconds: float = 0.0, cache_hit: bool = False, errors: list[str] = ..., warnings: list[str] = ..., phase_timings: dict[str, float] = ...)` — constructor signature implied by SSOT field list

**Fields (must match SSOT exactly):**

- Outputs:
  - `success: bool`
  - `screenshot_dir: Path | None = None`
  - `slowpics_url: str | None = None`
  - `report_path: Path | None = None`
- Metrics:
  - `frame_count: int = 0`
  - `clips_processed: int = 0`
  - `duration_seconds: float = 0.0`
  - `cache_hit: bool = False`
- Diagnostics:
  - errors: list[str] = field(default_factory=list)
  - warnings: list[str] = field(default_factory=list)
  - phase_timings: dict[str, float] = field(default_factory=dict)

**Key implementation notes:**

- Keep `RunResult` a pure data container: no filesystem reads, no implicit path creation, no network calls.
- Use dataclasses.field(default_factory=...) for container defaults to avoid shared mutable defaults across instances.
- Keep the type as @dataclass(frozen=True) per SSOT; tests should assert attribute reassignment fails.

### 2. `src/frame_compare/orchestration/__init__.py`

**Purpose:** Export `RunResult` from the orchestration package public surface.

**Change (spec-anchored):**

- Import `RunResult` from `frame_compare.orchestration.coordinator`
- Add `"RunResult"` to `__all__`

### 3. `tests/orchestration/test_run_result.py`

**Tests required:**

- `test_run_result_defaults` — constructs RunResult with success=True and asserts default values for all optional/bool/container fields
- `test_run_result_default_factories_are_distinct` — verifies `errors`, `warnings`, and `phase_timings` are not shared between instances
- `test_run_result_is_frozen` — verifies attempts to reassign an attribute raise (frozen dataclass)
- `test_run_result_is_public_export` — verifies `frame_compare.orchestration.RunResult` is the same type as defined in `coordinator.py`

## Acceptance Criteria

- [ ] GIVEN a `RunResult` constructed with `success=True` WHEN inspecting fields THEN optional outputs default to `None`, numeric counters default to `0`/`0.0`, `cache_hit` defaults to `False`, and containers default empty
- [ ] GIVEN two RunResult instances constructed with success=True WHEN mutating one instance’s `errors`/`warnings`/`phase_timings` contents THEN the other instance remains unchanged (distinct default factories)
- [ ] GIVEN a constructed `RunResult` WHEN attempting to reassign a field THEN an exception is raised (frozen dataclass)
- [ ] GIVEN `frame_compare.orchestration` WHEN importing `RunResult` THEN it is available as a public export

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-02__p6-7-6__runresult/plan-v14.md

.venv/bin/pyright --warnings src/frame_compare/orchestration/coordinator.py src/frame_compare/orchestration/__init__.py tests/orchestration/test_run_result.py
.venv/bin/ruff check src/frame_compare/orchestration/coordinator.py src/frame_compare/orchestration/__init__.py tests/orchestration/test_run_result.py
.venv/bin/pytest -v tests/orchestration/test_run_result.py

UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2026-02-02__p6-7-6__runresult
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. Keep the `RunResult` field set identical to SSOT (orchestration-module §4.4.2 and cli-module §3.1). If drift is discovered, STOP and escalate (SSOT mismatch is not a coding-time decision).
2. Avoid additional helper methods or computed properties in `RunResult` in this slice; those belong to later orchestration/reporting slices if required by SSOT.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

You MUST follow FC2 STOP rules and templates from:
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md

## RUN_ID

2026-02-02__p6-7-6__runresult

## Plan to Review

Read file: .agent-workflow/runs/2026-02-02__p6-7-6__runresult/plan-v14.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (templates + checklist)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-02-02__p6-7-6__runresult/plan-review-v14.md
