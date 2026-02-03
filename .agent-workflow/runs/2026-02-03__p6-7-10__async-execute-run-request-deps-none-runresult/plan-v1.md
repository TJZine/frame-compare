---
RUN_ID: 2026-02-03__p6-7-10__async-execute-run-request-deps-none-runresult
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Runner & Phase Orchestration) — execute_run entry point
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
  - src/frame_compare/orchestration/coordinator.py
  - src/frame_compare/orchestration/preflight.py
  - src/frame_compare/orchestration/progress.py
  - src/frame_compare/runner.py
OUTPUTS:
  - .agent-workflow/runs/2026-02-03__p6-7-10__async-execute-run-request-deps-none-runresult/plan-v1.md
---

# Implementation Plan: `execute_run` Orchestration Entry Point

## Context

**Phase:** 6
**Module:** `frame_compare.orchestration`
**Target File:** `src/frame_compare/orchestration/coordinator.py`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` §4.4.3
**Dependencies (already present in repo):**

- `RunRequest`, `RunResult`, `RunDependencies` dataclasses (already implemented)
- Preflight validation: `frame_compare.orchestration.preflight.prepare_preflight`
- Progress selection: `frame_compare.orchestration.progress.select_reporter`
- Sync wrapper: `frame_compare.runner.run` (already creates/owns `httpx.AsyncClient` when needed)

## Contract Impact

**Contracts touched:** NO

---

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: “4.4.3 Execute Function”
  - Section: “4.4.2 Result Types”
  - Section: “5.3 Resource Management”
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md`:
  - Section: “7. HTTP Client Lifecycle Rules”

---

## Scope

This plan covers:

- [ ] Implement the async orchestration entry point in `src/frame_compare/orchestration/coordinator.py` with:
  - Dependency defaulting (`deps is None`), and safe DI usage
  - Per-run HTTP client lifecycle when `deps.http_client` is not provided
  - Progress reporter defaulting when `deps.progress` is not provided
  - Basic preflight execution + timing capture into `RunResult`

This plan does NOT cover (explicitly out of scope for this slice):

- Phase 1–10 orchestration beyond preflight (LoadSources / FramePlan / Analyze / Align / Render / Metadata / Dovi / Publish / Report)
- Consolidated FPS report (§5.4)
- Any contract updates under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`
- CLI wiring for `frame-compare run` (currently stubbed in `src/frame_compare/cli_entry.py`)

---

## Rollback Guidance

### STOP Triggers

The Coding Agent MUST stop and return to Planning if any of these occur:

1. Implementing this entry point requires choosing phase ordering behavior beyond preflight (that belongs to later checklist sub-items).
2. Any mismatch is discovered between the spec signature/raises contract and the existing `RunRequest`/`RunDependencies` usage patterns in `src/frame_compare/runner.py`.

### Rollback Steps

If implementation needs to be reverted:

1. Revert edits to `src/frame_compare/orchestration/coordinator.py`.
2. Remove the new `tests/orchestration/test_execute_run.py` file (if created).

---

## Files to Create/Modify

### 1. `src/frame_compare/orchestration/coordinator.py` [MODIFY]

**Purpose:** Provide the async, DI-friendly run entry point required by Phase 6.7.

**Functions to implement (spec-anchored):**

- `async def execute_run(request: RunRequest, deps: RunDependencies | None = None) -> RunResult`

**Key implementation notes (decision-free):**

1. **Deps defaulting**
   - If `deps is None`, create a new `RunDependencies()` instance.
2. **Progress reporter**
   - If `deps.progress is None`, select a default reporter using `select_reporter(quiet=request.quiet, json_output=request.json_output)`.
   - Do not print directly; keep `ProgressReporter` handling internal and optional.
3. **HTTP client lifecycle**
   - If `deps.http_client` is provided, do not close it.
   - If `deps.http_client` is missing, create one inside `execute_run` and ensure it is closed before returning (use `async with httpx.AsyncClient() as client:`).
   - When creating the client internally, assign it to `deps.http_client` for the duration of the call.
4. **Preflight execution**
   - Run preflight via `prepare_preflight(root=request.root, config_path=request.config_path)`.
   - This slice does not use `request.input_dir` yet (keep that for later orchestration work).
5. **Timing + RunResult**
   - Use `deps.clock()` for start/end timestamps.
   - Populate:
     - `success=True` when preflight succeeds
     - `duration_seconds` (total wall time)
     - `phase_timings` with at least `{"preflight": <seconds>}`
     - `warnings` from `PreflightResult.warnings`
   - Do not invent phase timings for phases not executed in this slice.
6. **Error behavior**
   - Let `FrameCompareError` subclasses raised by preflight propagate (do not translate into `RunResult` here).

---

### 2. `tests/orchestration/test_execute_run.py` [NEW]

**Purpose:** Unit tests for the `execute_run` entry point behavior in this slice (preflight-only, DI + lifecycle).

**Tests required:**

- `test_execute_run_returns_success_and_records_preflight_timing`
  - Create a minimal workspace (reuse the same minimal TOML config pattern as `tests/orchestration/test_preflight.py`).
  - Create an empty video file under the configured input dir so `prepare_preflight` succeeds.
  - Call the async entry point and assert:
    - `result.success is True`
    - `result.warnings` equals the preflight warnings (expected empty list in the default case)
    - `result.duration_seconds >= 0.0`
    - `result.phase_timings` contains key `preflight` with a non-negative float
- `test_execute_run_propagates_config_not_found_error`
  - Create a workspace root without `config/config.toml` and assert the same preflight error type is raised.
- `test_execute_run_creates_and_closes_http_client_when_missing`
  - Call the async entry point with `deps=RunDependencies(http_client=None)` and `request.quiet=True` to avoid output.
  - Assert `deps.http_client` is an `httpx.AsyncClient` instance after the call and `deps.http_client.is_closed is True`.

**Test constraints:**

- No network calls (creating `httpx.AsyncClient` is allowed; do not send requests).
- No reliance on VapourSynth or FFmpeg.

---

## Acceptance Criteria

- [ ] GIVEN a valid workspace (config file + at least one matching “video” file) WHEN calling the async entry point THEN it returns a `RunResult` with `success=True` and records a `preflight` timing.
- [ ] GIVEN a workspace missing `config/config.toml` WHEN calling the async entry point THEN the preflight error is raised (not swallowed into `RunResult`).
- [ ] GIVEN no injected `httpx.AsyncClient` WHEN calling the async entry point THEN it creates and closes a client before returning.

---

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/orchestration
.venv/bin/ruff check src/frame_compare/orchestration
.venv/bin/pytest -q tests/orchestration -k execute_run
```

**Pass criteria:** All commands exit 0 with no errors; tests are deterministic and do not require external binaries.

---

## Notes for Coding Agent

- Keep this slice strictly “entry point + lifecycle + preflight + timing”. Do not begin implementing phase 2+ orchestration here.
- Avoid creating new public APIs unless required to satisfy the spec-anchored signature above.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-02-03__p6-7-10__async-execute-run-request-deps-none-runresult

## Plan to Review

Read file: .agent-workflow/runs/2026-02-03__p6-7-10__async-execute-run-request-deps-none-runresult/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Ensure Decision Points Remaining is NONE. Produce a Plan Review Report with a clear APPROVED or CHANGES REQUIRED verdict.

## Output

Write file: .agent-workflow/runs/2026-02-03__p6-7-10__async-execute-run-request-deps-none-runresult/plan-review-v1.md
