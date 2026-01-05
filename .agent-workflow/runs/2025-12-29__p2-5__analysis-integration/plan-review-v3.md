---
RUN_ID: 2025-12-29__p2-5__analysis-integration
VERSION: v3
TARGET: Phase 2 → Item 2.5 (Module Integration)
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v3.md
---

# Plan Review Report: Analysis Module Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v3.md

Plan-v3 expands scope to include a behavior change (“import analysis without VapourSynth installed”) by refactoring `metrics.py` to use lazy `vapoursynth` imports. This requirement is not defined in the SSOT, and the plan does not provide a deterministic verification strategy for the “without VS” acceptance criterion. As written, the Coding Agent would be implementing and validating a non-SSOT requirement.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice, explicit scope/out-of-scope list, includes changes-since section. |
| 2 | Dependencies | FAIL | “Importable without VS installed” is a cross-module dependency/contract not defined in SSOT; lazy import ownership not anchored. |
| 3 | File List | PASS | Files are listed explicitly (`__init__.py`, `metrics.py`, docs). |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | PASS | `calculate_metrics(...) -> FrameMetrics` signature listed; spec anchors validate. |
| 6 | Tests Complete | FAIL | No deterministic test is specified to prove “no top-level `vapoursynth` import”; behavior depends on the environment having VS absent. |
| 7 | Verification Complete | FAIL | Commands do not deterministically validate the “without VS installed” acceptance criterion. |
| 8 | Decision-Minimizing | FAIL | Coding Agent must decide/justify a non-SSOT behavior (import-time optional dependency handling). |
| 9 | Determinism Defined | N/A | No algorithmic output in this slice. |

## Additional Quality Checks

- Error Codes: OK — no new errors.
- Failure Modes: Issue — SSOT does not state whether `frame_compare.analysis` must be importable without VS; plan introduces this as a requirement.
- Derived Outputs: OK — none required.
- Rollback Guidance: OK — STOP rule present, but SSOT update is required first.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether “import without VapourSynth installed” is a required invariant for `frame_compare.analysis` (must be SSOT-defined).
2. How to verify that invariant deterministically in tests/CI (must be specified).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT spec first: define import-time VapourSynth dependency behavior**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
   - Under heading: `### 1.3 Dependencies` add/change:
     - State whether `frame_compare.analysis` MUST be importable when `vapoursynth` is not installed.
     - If YES: specify the rule “do not import `vapoursynth` at module import time; only import inside functions that require it; use `TYPE_CHECKING` for type hints”.

2. **Then revise the plan to anchor and verify the new invariant**
   - Section: `## Spec Anchors (SSOT)`:
     - Add the new/updated SSOT heading from `analysis-module.md` that states the import-time rule.
   - Section: tests (add to file list):
     - Add a deterministic unit test (exact name + assertions) that proves `src/frame_compare/analysis/metrics.py` has no top-level `import vapoursynth` (e.g., `ast`-based check that any `vapoursynth` import occurs only under `if TYPE_CHECKING:` or inside function bodies).
   - Section: `## Verification Commands`:
     - Keep existing gates; ensure the new test runs under `tests/analysis/`.

## Ready for Implementation

Return to Planning Agent for SSOT update + plan revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-5__analysis-integration

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
- Under heading: "### 1.3 Dependencies" add/change:
  - Specify whether `frame_compare.analysis` MUST be importable when `vapoursynth` is not installed.
  - If yes, specify the deterministic implementation rule: do not import `vapoursynth` at module import time; only import inside functions that require it; use `TYPE_CHECKING` for type hints.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v3.md
Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v3.md
Write file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
