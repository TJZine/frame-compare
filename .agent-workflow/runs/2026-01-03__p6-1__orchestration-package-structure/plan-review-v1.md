---
RUN_ID: 2026-01-03__p6-1__orchestration-package-structure
VERSION: v1
TARGET: Phase 6 → Item 6.1
INPUTS:
  - .agent-workflow/runs/2026-01-03__p6-1__orchestration-package-structure/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - importlinter.ini
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-1__orchestration-package-structure/plan-review-v1.md
---

# Plan Review Report: Orchestration Package Scaffold

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** `.agent-workflow/runs/2026-01-03__p6-1__orchestration-package-structure/plan-v1.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Matches checklist 6.1; doc updates are acceptable. |
| 2 | Dependencies | PASS | No runtime behavior planned; imports can remain empty. |
| 3 | File List | PASS | Files are enumerated explicitly (plus docs/tests/importlinter). |
| 4 | Contract Impact | PASS | Canonical contracts not touched; `importlinter.ini` update is correctly included in plan scope. |
| 5 | Types Complete | FAIL | Plan introduces stub public functions that reference types not defined in this slice (`PreflightResult`, `DoctorCheck`, `DoctorReport`, `ProgressReporter`). This leaves coding choices about annotation strategy/type placement. |
| 6 | Tests Complete | PASS | One smoke test is appropriate for a scaffold slice; assertions are clear. |
| 7 | Verification Complete | PASS | Command canon listed with explicit pass criteria. |
| 8 | Decision-Minimizing | FAIL | Multiple unresolved implementation decisions (see “Decision Points Remaining”), notably how to keep imports working while defining stub signatures with missing types, and the exact `importlinter.ini` `layers` block outcome. |
| 9 | Determinism Defined | PASS | N/A for this scaffold slice (no deterministic algorithms/output). |

## Additional Quality Checks

- Error Codes: OK (no new errors introduced in this slice).
- Failure Modes: OK (not applicable; no runtime behavior planned).
- Derived Outputs: OK (no generated contract views modified).
- Rollback Guidance: Issue — plan should state “if any import-linter / pyright failure occurs due to layer placement or stub annotations, STOP and return to Planning” (plan-level guidance only).
- SSOT Update Audit (if SSOT changed this loop): OK (no SSOT edits claimed in the plan).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether to include stub functions in `preflight.py` / `doctor.py` in a 6.1 scaffold slice, despite checklist 6.1 not requiring them.
2. If stub functions remain: how to prevent runtime NameError/pyright issues from unresolved annotation types (e.g., add `from __future__ import annotations`, use quoted annotations, or define placeholder types now).
3. The exact final `importlinter.ini` `layers =` block after adding `frame_compare.orchestration` (plan currently describes intent, but not the exact resulting list).

## Concrete Edits Required (for plan-v2.md)

1. **Remove stub function API from the scaffold slice**
   - Section: `Files to Create/Modify` → `src/frame_compare/orchestration/preflight.py` and `src/frame_compare/orchestration/doctor.py`
   - Problem: Adding stub public functions introduces undefined type references and forces annotation/type-placement decisions not required by checklist 6.1.
   - Required Change: For 6.1, make these modules scaffold-only (module docstring + minimal `__all__` if desired) and explicitly defer *all* public functions and types to Phase 6.2 per the checklist.

2. **Make `importlinter.ini` update fully explicit**
   - Section: `importlinter.ini` (MODIFY)
   - Problem: “Immediately below `frame_compare.cli_entry`” is directionally correct but still leaves the exact resulting `layers =` content implicit.
   - Required Change: Include the complete intended `layers =` block (verbatim, with final ordering/indentation) showing insertion of `frame_compare.orchestration` and explicitly noting that `frame_compare.runner` remains absent until the file exists.

3. **Add rollback/stop guidance**
   - Section: `Notes for Coding Agent` (or add a small `Rollback Guidance` section)
   - Problem: No explicit “stop and return to Planning” trigger for spec/contract drift in this slice.
   - Required Change: Add a single bullet: if `.venv/bin/pyright --warnings` or `lint-imports` fails due to layer placement or scaffold imports, STOP and return to Planning (do not patch around).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-03__p6-1__orchestration-package-structure

## Revision Required
Read file: .agent-workflow/runs/2026-01-03__p6-1__orchestration-package-structure/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-03__p6-1__orchestration-package-structure/plan-v1.md
Write file: .agent-workflow/runs/2026-01-03__p6-1__orchestration-package-structure/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Keep scope aligned to checklist item 6.1 (package + import-linter + import-smoke test); defer all public APIs/types to 6.2 unless SSOT explicitly moves them earlier.
