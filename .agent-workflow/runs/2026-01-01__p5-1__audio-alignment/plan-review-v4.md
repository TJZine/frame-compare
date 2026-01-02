---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v4
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v4.md
---

# Plan Review Report: Audio Alignment Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v4.md

Notes:
- `scripts/validate_spec_anchors.py` passes for `plan-v4.md`.
- SSOT/spec decisions introduced earlier in this RUN_ID (ffprobe FPS sourcing, cache schema/versioning, error propagation, `load_cached_offsets` semantics) remain implementable and aligned with repo layering rules.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (5.1) plus explicit dependency implementation (utils progress). |
| 2 | Dependencies | PASS | Dependencies and layering are explicit; import-linter update aligns with architecture intent. |
| 3 | File List | FAIL | Adds new public utils module (`utils/progress.py`) but does not add any tests for it; test file list is incomplete for the scope. |
| 4 | Contract Impact | PASS | Explicit **NO**. |
| 5 | Types Complete | PASS | Public signatures are listed and SSOT-anchored; no TBDs. |
| 6 | Tests Complete | FAIL | No explicit test names/assertions for `ProgressReporter` implementations (Null/Rich/Log), despite adding them to public API surface via `utils/__init__.py`. |
| 7 | Verification Complete | FAIL | `pytest` command only runs `tests/services/`; it will not execute new `tests/utils/` coverage that must be added for `utils/progress.py`. |
| 8 | Decision-Minimizing | FAIL | Whether/how to test `utils/progress.py` is left to the Coding Agent; must be specified. |
| 9 | Determinism Defined | PASS | Alignment tests remain deterministic per plan-v3. |

## Additional Quality Checks

- Error Codes: OK (no new errors).
- Failure Modes: OK for audio alignment and cache; progress reporters need at least smoke coverage for “no crash” contract.
- Derived Outputs: OK (contracts not touched).
- Rollback Guidance: OK (STOP conditions included).
- SSOT Update Audit (if SSOT changed this loop): N/A (no new SSOT changes in plan-v4).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact unit test coverage for `src/frame_compare/utils/progress.py` (and how to run it in verification) is unspecified.

## Concrete Edits Required (plan-v5)

1. **Add deterministic unit tests for utils progress**
   - Section: Plan → “Files to Create/Modify”
   - Required Change: Add the following files (and list them explicitly):
     - `tests/utils/__init__.py` [NEW] (empty)
     - `tests/utils/test_progress.py` [NEW]
   - Required tests (exact names + assertions):
     - `test_null_progress_reporter_noops` — calling all methods raises no exception.
     - `test_rich_progress_reporter_smoke` — instantiate, call `start_phase/advance/set_description/complete_phase`, asserts no exception.
     - `test_log_progress_reporter_smoke` — same as above; asserts no exception (do not assert log output content in this slice).

2. **Update verification to run new tests**
   - Section: Plan → “Verification Commands”
   - Required Change: Replace `pytest -v tests/services/` with `pytest -v tests/services/ tests/utils/` (or `pytest -v tests/` if you want a single umbrella command).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v5.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p5-1__audio-alignment

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v4.md
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v4.md
Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v5.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
