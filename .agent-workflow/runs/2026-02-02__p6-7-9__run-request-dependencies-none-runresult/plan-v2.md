---
RUN_ID: 2026-02-02__p6-7-9__run-request-dependencies-none-runresult
VERSION: v2
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement `run(request, dependencies=None) -> RunResult` entry point in `src/frame_compare/runner.py` (see `cli-module.md` §2.1)
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v1.md
  - .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - importlinter.ini
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v2.md
---

# Implementation Plan: `frame_compare.runner.run` Entry Point

## Changes Since plan-v1

- Specify the sync→async execution policy for `run`: use `asyncio.run` in sync contexts; detect an already-running event loop and raise a clear `RuntimeError` instructing callers to use the async entry point instead.
- Make the `execute_run` resolution and monkeypatch target explicit: call `execute_run` via the `frame_compare.orchestration.coordinator` module so tests can monkeypatch it even before it exists; define a clear `NotImplementedError` behavior when absent.
- Clarify “do not mutate caller-owned dependencies”: always build a new “effective” `RunDependencies` instance and avoid calling lazy getters as part of wrapper wiring.

## Context

**Phase:** 6
**Checklist Item:** 6.7 — Runner & Phase Orchestration
**Module:** `frame_compare.runner` (package-root)
**Goal in this slice:** Replace the current runner scaffold with the real `run` entry point behavior:

- normalize `dependencies=None` into a concrete `RunDependencies`
- apply default DI wiring for progress + HTTP client lifecycle
- delegate to the async orchestration entry point (`execute_run`) in a way that is testable before `execute_run` is implemented

## Contract Impact

**Contracts touched:** NO

No canonical contract files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` are modified by this slice.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "1.2 Module Structure"
  - Section: "2.1 Command Structure"
  - Section: "3.2 Public API"
  - Section: "3.4 RunDependencies"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "4.3 Progress Reporter Selection"
  - Section: "4.4.3 Execute Function"

## Scope

This plan covers:

- [ ] Implement `frame_compare.runner.run` as a sync wrapper around orchestration execution.
- [ ] Ensure `dependencies` defaulting and DI wiring matches SSOT expectations:
  - If `dependencies is None`, create a new `RunDependencies`.
  - If `deps.progress is None`, choose a default via orchestration progress selection (quiet/json aware).
  - If `deps.http_client is None`, create an `httpx.AsyncClient` for the duration of the call and close it on exit.
  - If `deps.http_client` is provided, do not close it (caller-owned lifecycle).
- [ ] Make the sync→async policy deterministic:
  - In a sync context (no running event loop), run orchestration via `asyncio.run`.
  - If an event loop is already running, raise `RuntimeError` with a clear message telling users to call the async entry point instead.
- [ ] Update unit tests to validate wrapper behavior (without requiring real pipeline phases).

This plan does NOT cover:

- Implementing `execute_run` or phase orchestration (separate checklist items under 6.7).
- Changing CLI command behavior in `src/frame_compare/cli_entry.py` (Phase 6 → Item 6.8).
- Error mapping / exit codes / JSON output formatting (Phase 6 → Item 6.8 and error-handling slices).

## Files to Create/Modify

### 1. [MODIFY] `src/frame_compare/runner.py`

**Purpose:** Provide the canonical package-root, synchronous runner entry point for CLI and programmatic API usage.

**Implementation requirements (spec-anchored):**

- Keep `frame_compare.runner` import-light: avoid importing large subpackages at module import time.

- Construct an “effective” `RunDependencies` instance for the call without mutating caller-owned dependencies:
  - Always create a new `RunDependencies` instance for the call (copy fields from `dependencies` if provided).
  - Do not call `RunDependencies.get_vs_loader` or `RunDependencies.get_ffmpeg_runner` as part of wrapper wiring; the wrapper should not trigger lazy initialization side effects.
  - Fill `progress` using `frame_compare.orchestration.progress.select_reporter` based on `request.quiet` and `request.json_output`, but only if the caller did not provide `progress`.

- `execute_run` lookup strategy (patchable before `execute_run` exists):
  - Resolve `execute_run` from the `frame_compare.orchestration.coordinator` module (not via `from ... import execute_run`).
  - If `frame_compare.orchestration.coordinator` does not define `execute_run` and it has not been monkeypatched in tests, raise `NotImplementedError` with a message that includes the missing symbol path: `frame_compare.orchestration.coordinator.execute_run`.

- Sync→async execution policy (eliminates “event loop runner” ambiguity):
  - If `run` is invoked while an event loop is already running, raise `RuntimeError` with a clear, deterministic message instructing programmatic callers to use the async entry point (for example: “Do not call frame_compare.runner.run from an async context; await frame_compare.orchestration.coordinator.execute_run instead.”).
  - Otherwise, use `asyncio.run` to execute the coroutine returned by `coordinator.execute_run`.

- HTTP client lifecycle:
  - If the effective dependencies include a client, pass it through unchanged (caller-owned; do not close it).
  - If the effective dependencies do not include a client, create an `httpx.AsyncClient` for the duration of the orchestration call and ensure it is closed on return or error.

### 2. [MODIFY] `tests/test_runner_import_smoke.py`

**Purpose:** Keep the runner surface import contract, and validate the new `run` wrapper behavior without requiring real external tools.

**Tests required:**

- Keep: module imports + expected public symbols exist.

- Replace the current scaffold-raises test with focused wrapper tests that monkeypatch the orchestration async entry point:
  - Monkeypatch `frame_compare.orchestration.coordinator.execute_run` with `raising=False` so the patch works even before the symbol exists.
  - Validate the returned `RunResult` is propagated.
  - Validate deps passed to `execute_run` are non-None and are not the same object as a caller-provided `RunDependencies` (copy semantics; no caller mutation).
  - Validate HTTP client lifecycle:
    - When `deps.http_client` is None, deps passed to `execute_run` include a client, and it is closed after `run` returns.
    - When a caller provides a client, `run` does not close it.

- Add a deterministic “event loop already running” behavior test:
  - Call `frame_compare.runner.run` from inside an `asyncio.run`-driven coroutine (so an event loop is running).
  - Assert it raises `RuntimeError` with the expected user-facing guidance about using the async entry point.

- Add a deterministic “missing execute_run” behavior test:
  - Ensure `frame_compare.orchestration.coordinator.execute_run` is absent (use monkeypatch deletion with `raising=False`).
  - Assert `frame_compare.runner.run` raises `NotImplementedError` mentioning the missing symbol path.

## Functions to implement

- `run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult` — synchronous wrapper that prepares dependencies, enforces the sync→async policy, and calls the async orchestration entry point per SSOT.

## Acceptance Criteria

- [ ] GIVEN `frame_compare.runner` WHEN importing THEN it exposes `RunRequest`, `RunResult`, `RunDependencies`, and `run`.
- [ ] GIVEN a monkeypatched orchestration `execute_run` WHEN calling `frame_compare.runner.run` with `dependencies=None` THEN it returns the patched `RunResult` and the deps passed to `execute_run` is not `None`.
- [ ] GIVEN a caller-provided `RunDependencies` with `progress=None` WHEN calling `run` THEN the deps passed to `execute_run` is a different object and the caller-provided `RunDependencies` instance remains unmodified.
- [ ] GIVEN `deps.http_client is None` WHEN calling `run` THEN the deps passed to `execute_run` includes an `httpx.AsyncClient`, and that client is closed after `run` returns.
- [ ] GIVEN a caller-provided `httpx.AsyncClient` WHEN calling `run` THEN the wrapper does not close it.
- [ ] GIVEN `run` is called while an event loop is already running WHEN invoking it THEN it raises `RuntimeError` with a clear message instructing callers to use `frame_compare.orchestration.coordinator.execute_run` instead.
- [ ] GIVEN the orchestration module does not define `execute_run` WHEN calling `run` (without monkeypatching) THEN it raises `NotImplementedError` mentioning `frame_compare.orchestration.coordinator.execute_run`.

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v2.md

.venv/bin/pyright --warnings src/frame_compare/runner.py tests/test_runner_import_smoke.py
.venv/bin/ruff check src/frame_compare/runner.py tests/test_runner_import_smoke.py
.venv/bin/pytest -v tests/test_runner_import_smoke.py

UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. This slice must remain a “sync wrapper + DI wiring” change only; do not implement orchestration phases or `execute_run` here.
2. Keep the `execute_run` call-site patchable for unit tests before `execute_run` exists by calling it via the module attribute on `frame_compare.orchestration.coordinator`.
3. Preserve caller ownership of injected resources: never close a user-provided HTTP client; do not mutate a caller-provided `RunDependencies` instance.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

You MUST follow FC2 STOP rules and templates from:
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md

## RUN_ID
2026-02-02__p6-7-9__run-request-dependencies-none-runresult

## Plan to Review
Read file: .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v2.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (templates + checklist)
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
5. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
6. Read file: importlinter.ini

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-review-v2.md
