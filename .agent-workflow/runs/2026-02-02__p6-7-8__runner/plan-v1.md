---
RUN_ID: 2026-02-02__p6-7-8__runner
VERSION: v1
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Create `src/frame_compare/runner.py` at package root (see `cli-module.md` §1.2)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - importlinter.ini
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v1.md
---

# Implementation Plan: runner.py Package-Root Scaffold

## Context

**Phase:** 6 (CLI & Orchestration)
**Checklist slice:** Phase 6 → Item 6.7 — Runner & Phase Orchestration
**Goal in this slice:** Add the canonical `frame_compare.runner` module at package root (file exists at the expected path), without implementing pipeline execution yet.

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "1.2 Module Structure"
  - Section: "3.2 Public API"

## Scope

This plan covers:

- [ ] Create `src/frame_compare/runner.py` at package root per SSOT module layout.
- [ ] Export the already-defined orchestration request/result/DI types from `frame_compare.runner` to establish the public import path (`RunRequest`, `RunResult`, `RunDependencies`).
- [ ] Define the `run(...) -> RunResult` callable surface (scaffold only; implementation lands in the dedicated “implement run entry point” slice).
- [ ] Add a small import smoke test to ensure `frame_compare.runner` remains importable (no side effects).

This plan does NOT cover:

- Implementing `run(request, dependencies=None) -> RunResult` behavior (separate 6.7 checklist item).
- Implementing `execute_run(...)` or phase orchestration (separate 6.7 checklist items).
- Any CLI command wiring in `cli_entry.py` (Phase 6 → Item 6.8).

## Files to Create/Modify

### 1. [NEW] `src/frame_compare/runner.py`

**Purpose:** Canonical package-root module for the runner surface, per SSOT module layout.

**Types to export (re-exports):**

- `RunRequest` — currently defined in `src/frame_compare/orchestration/coordinator.py`
- `RunResult` — currently defined in `src/frame_compare/orchestration/coordinator.py`
- `RunDependencies` — currently defined in `src/frame_compare/orchestration/coordinator.py`

**Implementation notes:**

- Keep the module import-light: re-export directly from `frame_compare.orchestration.coordinator` (avoid importing `frame_compare.orchestration` package `__init__`, which fans out to many submodules).
- Include a scaffold `run(...)` with the correct signature that fails loudly (e.g., NotImplementedError) until the dedicated “implement run entry point” checklist item lands with full behavior.

### 2. [NEW] `tests/test_runner_import_smoke.py`

**Purpose:** Ensure `frame_compare.runner` is importable and exposes the expected public types.

**Tests required (names are suggestions; exact names can vary):**

- Import `frame_compare.runner` and assert the module loads.
- Assert `RunRequest`, `RunResult`, and `RunDependencies` are present on `frame_compare.runner`.

## Functions to implement

- `run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult` — scaffold only; raises a clear NotImplementedError until the dedicated runner implementation slice lands.

## Acceptance Criteria

- [ ] `src/frame_compare/runner.py` exists at package root and `import frame_compare.runner` succeeds.
- [ ] `frame_compare.runner` exposes `RunRequest`, `RunResult`, and `RunDependencies` as public symbols.
- [ ] Calling `frame_compare.runner.run(...)` fails loudly with a clear NotImplementedError (until runner orchestration lands).
- [ ] Unit test verifies the import + symbol presence without invoking external tools or network.

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → Command Canon.

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Notes for Coding Agent

- Keep this slice narrowly focused on SSOT module layout + re-export surface; do not implement runner orchestration yet.
- Avoid importing `frame_compare.orchestration` package-level exports from `runner.py`; import only from `frame_compare.orchestration.coordinator` to keep `frame_compare.runner` lightweight.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-02-02__p6-7-8__runner

## Plan to Review
Read file: .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v1.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates/checklist only)
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
5. Read file: importlinter.ini

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-review-v1.md
