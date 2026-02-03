---
RUN_ID: 2026-02-02__p6-7-9__run-request-dependencies-none-runresult
VERSION: v1
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement `run(request, dependencies=None) -> RunResult` entry point in `src/frame_compare/runner.py` (see `cli-module.md` §2.1)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - importlinter.ini
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v1.md
---

# Implementation Plan: `frame_compare.runner.run` Entry Point

## Context

**Phase:** 6
**Checklist Item:** 6.7 — Runner & Phase Orchestration
**Module:** `frame_compare.runner` (package-root)
**Goal in this slice:** Replace the current runner scaffold with the real `run(...)` entry point behavior:

- normalize `dependencies=None` into a concrete `RunDependencies`
- apply default DI wiring for progress + http client lifecycle
- delegate to the async orchestration entry point (`execute_run`) once it exists

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
- [ ] Update unit tests to validate the wrapper behavior (without requiring real pipeline phases).

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
  - Start from `dependencies` if provided, else a new `RunDependencies` instance.
  - Fill `progress` via `frame_compare.orchestration.progress.select_reporter` using `request.quiet` and `request.json_output`.
  - For `http_client`:
    - If present: call the orchestration async entry point directly.
    - If absent: use an async context manager around `httpx.AsyncClient`, and call the orchestration async entry point with a deps instance that includes the client.
- Delegate to `frame_compare.orchestration.coordinator.execute_run` passing `request` and `deps`, using an event loop runner.
  - Until `execute_run` is implemented, `run` may raise a clear `NotImplementedError` stating which symbol is missing.

### 2. [MODIFY] `tests/test_runner_import_smoke.py`

**Purpose:** Keep the runner surface import contract, and validate the new `run(...)` wrapper behavior without requiring real external tools.

**Tests required:**

- Keep: module imports + expected public symbols exist.
- Replace the current scaffold-raises test with focused wrapper tests that monkeypatch the orchestration async entry point:
  - `run` returns the `RunResult` produced by the patched `execute_run`.
  - When `dependencies=None`, the wrapper passes a non-None `RunDependencies` into `execute_run`.
  - When `deps.http_client is None`, the wrapper provides a client during execution and closes it after returning.
  - When `deps.http_client` is provided, the wrapper does not close it (caller-owned lifecycle).

## Functions to implement

- `run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult` — synchronous wrapper that prepares dependencies and calls the async orchestration entry point per SSOT.

## Acceptance Criteria

- [ ] GIVEN `frame_compare.runner` WHEN importing THEN it exposes `RunRequest`, `RunResult`, `RunDependencies`, and `run`.
- [ ] GIVEN a monkeypatched orchestration `execute_run` WHEN calling `frame_compare.runner.run` with `dependencies=None` THEN it returns the patched `RunResult` and the deps passed to `execute_run` is not `None`.
- [ ] GIVEN `deps.http_client is None` WHEN calling `run` THEN the deps passed to `execute_run` includes an `httpx.AsyncClient`, and that client is closed after `run` returns.
- [ ] GIVEN a caller-provided `httpx.AsyncClient` WHEN calling `run` THEN the wrapper does not close it.

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v1.md

.venv/bin/pyright --warnings src/frame_compare/runner.py tests/test_runner_import_smoke.py
.venv/bin/ruff check src/frame_compare/runner.py tests/test_runner_import_smoke.py
.venv/bin/pytest -v tests/test_runner_import_smoke.py

UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. Treat `execute_run` as the single async orchestration entry point (owned by `frame_compare.orchestration.coordinator`) and keep this slice to “sync wrapper + DI wiring” only.
2. Preserve caller ownership of injected resources: never close a user-provided HTTP client.
3. Avoid pulling in `frame_compare.orchestration` package-level exports from `runner.py`; import the specific modules needed to keep import side effects minimal.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

You MUST follow FC2 STOP rules and templates from:
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md

## RUN_ID
2026-02-02__p6-7-9__run-request-dependencies-none-runresult

## Plan to Review
Read file: .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v1.md

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
Write file: .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-review-v1.md
