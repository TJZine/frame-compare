---
RUN_ID: 2026-02-02__p6-7-8__runner
VERSION: v2
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Create `src/frame_compare/runner.py` at package root (see `cli-module.md` §1.2)
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v1.md
  - .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
  - importlinter.ini
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v2.md
---

# Implementation Plan: runner.py Package-Root Scaffold

## Changes Since plan-v1

1. **Import layering made explicit:** Add a required `importlinter.ini` edit to insert `frame_compare.runner` as a top-level layer immediately after `frame_compare.cli_entry`.
2. **Tests fully specified:** Replace “suggestions” with an exact test file path, test function names, and required assertions (including the scaffold failure negative case).
3. **Stable scaffold failure behavior:** Specify the exact `NotImplementedError` message raised by `frame_compare.runner.run(...)` until the real runner implementation slice lands.
4. **Verification pass criteria explicit:** State that all verification commands must exit with code 0.

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
- [ ] Re-export the already-defined orchestration request/result/DI types from `frame_compare.runner` to establish the public import path (`RunRequest`, `RunResult`, `RunDependencies`).
- [ ] Add a scaffold `run(...)` callable with the correct signature that raises a stable `NotImplementedError` (implementation lands in the dedicated “implement run entry point” slice).
- [ ] Update `importlinter.ini` layering to include `frame_compare.runner`.
- [ ] Add a small import smoke test to ensure `frame_compare.runner` is importable and exposes the public surface.

This plan does NOT cover:

- Implementing `run(request, dependencies=None) -> RunResult` behavior (separate 6.7 checklist item).
- Implementing `execute_run(...)` or phase orchestration (separate 6.7 checklist items).
- Any CLI command wiring in `cli_entry.py` (Phase 6 → Item 6.8).

## Files to Create/Modify

### 1. [NEW] `src/frame_compare/runner.py`

**Purpose:** Canonical package-root module for the runner surface, per SSOT module layout.

**Public surface (exports):**

- `RunRequest` — re-export from `frame_compare.orchestration.coordinator`
- `RunResult` — re-export from `frame_compare.orchestration.coordinator`
- `RunDependencies` — re-export from `frame_compare.orchestration.coordinator`
- `run` — scaffold callable; raises `NotImplementedError` until runner implementation slice lands

**Implementation notes:**

- Keep the module import-light: import/re-export directly from `frame_compare.orchestration.coordinator` (avoid importing `frame_compare.orchestration` package `__init__`, which fans out to many submodules).
- `run(...)` MUST raise `NotImplementedError` with the exact message:

```text
frame_compare.runner.run is not implemented yet (scaffold)
```

### 2. [MODIFY] `importlinter.ini`

**Purpose:** Keep `lint-imports` passing by adding `frame_compare.runner` to the layered architecture contract.

**Required edit (exact position):**

- In `[importlinter:contract:layers]` → `layers =`, insert `frame_compare.runner` immediately after `frame_compare.cli_entry` and before `frame_compare.orchestration`.

Resulting top-of-list snippet:

```ini
layers =
    frame_compare.cli_entry
    frame_compare.runner
    frame_compare.orchestration
```

**Layering rule to preserve:**

- `frame_compare.runner` may import `frame_compare.orchestration.*`
- `frame_compare.orchestration.*` must not import `frame_compare.runner`

### 3. [NEW] `tests/test_runner_import_smoke.py`

**Purpose:** Ensure `frame_compare.runner` is importable and exposes the expected public symbols, including the scaffold `run`.

**Tests required (exact names and assertions):**

1. `def test_runner_exports_public_symbols() -> None:`
   - `import frame_compare.runner as runner`
   - Assert `hasattr(runner, "RunRequest")`
   - Assert `hasattr(runner, "RunResult")`
   - Assert `hasattr(runner, "RunDependencies")`
   - Assert `hasattr(runner, "run")`

2. `def test_runner_run_is_scaffold_raises() -> None:`
   - `import frame_compare.runner as runner`
   - Construct a minimal request: `runner.RunRequest(root=Path("."))`
   - Assert `runner.run(...)` raises `NotImplementedError` with a stable message:
     - Use `pytest.raises(NotImplementedError, match=r"^frame_compare\\.runner\\.run is not implemented yet \\(scaffold\\)$")`

## Functions to implement

- `run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult` — scaffold only; MUST raise `NotImplementedError` with the exact message specified above.

## Acceptance Criteria

- [ ] `src/frame_compare/runner.py` exists at package root and `import frame_compare.runner` succeeds.
- [ ] `frame_compare.runner` exposes `RunRequest`, `RunResult`, `RunDependencies`, and `run` as public symbols.
- [ ] `frame_compare.runner.run(...)` raises `NotImplementedError` with the exact message `frame_compare.runner.run is not implemented yet (scaffold)`.
- [ ] `importlinter.ini` includes `frame_compare.runner` immediately after `frame_compare.cli_entry` in the layer list.
- [ ] Unit tests verify import + symbol presence + scaffold failure behavior without invoking external tools or network.

## Verification Commands

Pass criteria: all commands exit with code 0.

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → Command Canon.

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Notes for Coding Agent

- Keep this slice narrowly focused on SSOT module layout + import-layer wiring + re-export surface; do not implement runner orchestration yet.
- Avoid importing `frame_compare.orchestration` package-level exports from `runner.py`; import only from `frame_compare.orchestration.coordinator` to keep `frame_compare.runner` lightweight.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-02-02__p6-7-8__runner

## Plan to Review
Read file: .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v2.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates/checklist only)
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
5. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
6. Read file: importlinter.ini
7. Read file: .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-review-v1.md

## Your Task
Validate the plan using the 9-point checklist. Confirm all decision points are removed.

## Output
Write file: .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-review-v2.md
