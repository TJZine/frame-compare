---
RUN_ID: 2026-01-03__p6-1__orchestration-package-structure
VERSION: v1
TARGET: Phase 6 → Item 6.1
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-1__orchestration-package-structure/plan-v1.md
---

# Implementation Plan: Orchestration Package Scaffold

## Context
**Phase:** 6 (CLI & Orchestration)
**Module:** `frame_compare.orchestration`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
**Dependencies:** Existing `frame_compare.config`, `frame_compare.errors`, `frame_compare.utils`, `frame_compare.analysis`, `frame_compare.render`, `frame_compare.services`, `frame_compare.vs`.

## Scope
This plan covers:
- [ ] Create the `src/frame_compare/orchestration/` package directory and initial module files (no behavior yet)
- [ ] Update `importlinter.ini` to include `frame_compare.orchestration` as a first-class layer
- [ ] Add a minimal unit test to ensure the new package/modules import successfully

This plan does NOT cover:
- Implementing orchestration behavior (`prepare_preflight`, `run_doctor`, phase execution, async runner)
- Creating additional orchestration files listed in the spec (`coordinator.py`, `context.py`, `runner.py`)
- Adding `src/frame_compare/runner.py` or an import-linter layer for `frame_compare.runner` (deferred until it exists)

## Contract Impact
**Contracts touched:** NO

No changes to canonical contract files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: “1.2 Module Structure”
  - Section: “4.1 Preflight”
  - Section: “4.2 Doctor”
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`:
  - Section: “7. import-linter Configuration”
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: “2.1 Unit Tests”
- `docs/OPUS_REBUILD_FRAME_COMPARE/project_documentation.md`:
  - Section: “Documentation Inventory”

## Files to Create/Modify

### 1. `src/frame_compare/orchestration/__init__.py`
**Purpose:** Define the orchestration package and establish the canonical import path `frame_compare.orchestration`.

**Implementation notes (scaffold-only):**
- Keep module side-effect free on import.
- Do not export public API yet (defer until Phase 6.2+ implements real functions/types).

### 2. `src/frame_compare/orchestration/preflight.py`
**Purpose:** Placeholder module for preflight validation implementation (Phase 6.2).

**Functions to implement (stub-only in this slice; spec-anchored):**
- `prepare_preflight(root: Path | None = None, config_path: Path | None = None) -> PreflightResult` — define signature + docstring; raise `NotImplementedError`

**Implementation notes (scaffold-only):**
- Keep module side-effect free on import.
- Do not implement preflight behavior in this slice.

### 3. `src/frame_compare/orchestration/doctor.py`
**Purpose:** Placeholder module for doctor checks implementation (Phase 6.2).

**Functions to implement (stub-only in this slice; spec-anchored):**
- `collect_checks() -> list[DoctorCheck]` — define signature + docstring; raise `NotImplementedError`
- `run_doctor(checks: list[DoctorCheck] | None = None, reporter: ProgressReporter | None = None) -> DoctorReport` — define signature + docstring; raise `NotImplementedError`

**Implementation notes (scaffold-only):**
- Keep module side-effect free on import.
- Do not implement doctor behavior in this slice.

### 4. `src/frame_compare/orchestration/progress.py`
**Purpose:** Placeholder module for orchestration-owned progress reporter wiring (Phase 6.3).

**Implementation notes (scaffold-only):**
- Orchestration MUST use the canonical `ProgressReporter` protocol defined in `frame_compare.utils.progress`.
- Do not implement reporter selection logic in this slice.

### 5. `src/frame_compare/orchestration/phases.py`
**Purpose:** Placeholder module for phase definitions and execution wiring (later Phase 6 slices).

**Implementation notes (scaffold-only):**
- Keep module side-effect free on import.
- Do not implement phase execution in this slice.

### 6. `importlinter.ini` (MODIFY)
**Purpose:** Keep `lint-imports` deterministic by modeling the new top-level module `frame_compare.orchestration`.

**Change required (spec-anchored):**
- Update the `layers` contract to include `frame_compare.orchestration` immediately below `frame_compare.cli_entry`.
- Do NOT add a `frame_compare.runner` layer in this run (file does not exist yet; adding it would break `lint-imports`).

### 7. `tests/orchestration/test_import_smoke.py` (ADD)
**Purpose:** Unit-level smoke test ensuring the new modules import without errors or side effects.

**Tests required:**
- `test_orchestration_modules_importable` — imports `frame_compare.orchestration` and submodules (`preflight`, `doctor`, `progress`, `phases`)

### 8. `docs/DECISIONS.md` (MODIFY)
**Purpose:** Append a run decision entry (repo persistence).

**Required facts to record (bullets; do not prewrite exact prose):**
- RUN_ID + artifact versions (plan/plan-review/impl/verify/review)
- Scope: “Phase 6.1 scaffold only” + explicit out-of-scope items listed above
- Import contract decision: added `frame_compare.orchestration` to `importlinter.ini` layers; deferred `frame_compare.runner` layer until file exists
- Verification gates run + pass/fail (pyright, ruff, pytest, lint-imports)

### 9. `CHANGELOG.md` (MODIFY)
**Purpose:** Add a short entry noting the new orchestration package scaffold and import-contract update.

## Acceptance Criteria

- [ ] GIVEN the repo after this run WHEN importing `frame_compare.orchestration` THEN import succeeds with no side effects.
- [ ] GIVEN the repo after this run WHEN running `lint-imports` THEN the layered contract includes `frame_compare.orchestration` and passes.
- [ ] GIVEN the repo after this run WHEN running unit tests THEN the smoke import test passes.

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → Command Canon.

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Do not implement Phase 6.2+ behavior in this slice; keep new modules importable but empty/scaffold-only.
- Avoid adding import-linter layers for modules that do not exist yet (notably `frame_compare.runner`).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-01-03__p6-1__orchestration-package-structure

## Plan to Review
Read file: .agent-workflow/runs/2026-01-03__p6-1__orchestration-package-structure/plan-v1.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-01-03__p6-1__orchestration-package-structure/plan-review-v1.md
