---
RUN_ID: 2026-01-03__p6-3__progress-reporting
VERSION: v1
TARGET: Phase 6 → Item 6.3
INPUTS:
  - .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - src/frame_compare/utils/progress.py
  - src/frame_compare/orchestration/progress.py
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-review-v1.md
---

# Plan Review Report: Progress Reporting — Reporter Selection Logic

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** `.agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-v1.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Scoped to checklist item 6.3 (reporter selection) and explicitly excludes phase orchestration and JSON-lines reporter. |
| 2 | Dependencies | PASS | Uses existing `frame_compare.utils.progress` protocol + implementations; orchestration scaffold exists. |
| 3 | File List | PASS | All touched files are enumerated (orchestration progress, orchestration exports, tests, docs). |
| 4 | Contract Impact | PASS | No canonical contracts changed; import-linter gate included. |
| 5 | Types Complete | FAIL | Plan contradicts itself on introducing `OutputMode` (listed as a type to define, later explicitly “No OutputMode enum needed”), leaving a public-API decision to the Coding Agent. |
| 6 | Tests Complete | PASS | Test list matches SSOT `orchestration-module.md` §4.3.1 exactly and is deterministic (monkeypatch isatty). |
| 7 | Verification Complete | FAIL | Uses scoped commands (`pyright`/`ruff` per file, `pytest -v` per file) instead of the exact command canon required by workflow. |
| 8 | Decision-Minimizing | FAIL | Leaves implementation decisions: whether `OutputMode` exists, and how to update `orchestration/__init__.py` without clobbering existing exports. |
| 9 | Determinism Defined | PASS | Reporter precedence and TTY fallback are fully specified and test-covered. |

## Additional Quality Checks

- Error Codes: OK (no new errors).
- Failure Modes: OK (pure selection logic).
- Derived Outputs: OK (no derived contract views edited).
- Rollback Guidance: OK (not strictly required; keep STOP trigger optional).
- SSOT Update Audit (if SSOT changed this loop): OK (no SSOT edits claimed).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether to add a new `OutputMode` type at all (plan currently conflicts).
2. Whether `orchestration/__init__.py` updates should append vs replace existing `__all__` contents (plan does not specify; coding would need to decide).
3. Which verification commands are required vs optional (plan deviates from workflow canon).

## Concrete Edits Required (plan-v2.md)

1. **Remove the `OutputMode` type decision**
   - Section: `src/frame_compare/orchestration/progress.py` (MODIFY) → “Types to define”
   - Problem: Plan both proposes and rejects an `OutputMode` enum.
   - Required Change: Make this unambiguous by removing `OutputMode` entirely (preferred, matches SSOT signature) and stating “no new public types in this slice”.

2. **Make orchestration export change non-destructive**
   - Section: `src/frame_compare/orchestration/__init__.py` (MODIFY)
   - Problem: Plan does not say whether to append to existing `__all__` or replace it, risking churn/breakage given Phase 6.2 already added exports.
   - Required Change: Specify “append `select_reporter` to existing `__all__` list; do not remove existing entries”.

3. **Use exact command canon in Verification Commands**
   - Section: `Verification Commands`
   - Problem: Current commands are scoped and use `pytest -v`; workflow requires exact canon commands.
   - Required Change: Replace with (optionally followed by targeted runs):
     - `.venv/bin/pyright --warnings`
     - `.venv/bin/ruff check .`
     - `.venv/bin/pytest -q`
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`

4. **(Optional mechanical) Fix scope checkboxes**
   - Section: `Scope`
   - Problem: The plan uses `[x]` checkmarks in v1, which reads as “already done”.
   - Required Change: Use `[ ]` for planned work to avoid confusion.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-03__p6-3__progress-reporting

## Revision Required
Read file: .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-v1.md
Write file: .agent-workflow/runs/2026-01-03__p6-3__progress-reporting/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
