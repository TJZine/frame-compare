---
RUN_ID: 2025-12-29__p3-1__vs-environment
VERSION: v2
TARGET: Phase 3 → Item 3.1 Environment
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-review-v2.md
---

# Plan Review Report: VapourSynth Environment (Minimal Vertical Slice)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope is explicit. |
| 2 | Dependencies | PASS | SSOT anchors cover environment + loader protocol + plugin detection + typed errors. |
| 3 | File List | PASS | Exact file list; import-layers change is specified verbatim. |
| 4 | Contract Impact | PASS | Declares NO; includes contract check commands. |
| 5 | Types Complete | PASS | Public types and defaults are specified and SSOT-aligned. |
| 6 | Tests Complete | FAIL | Test setup details for plugin detection and VS import mocking are still ambiguous/internally inconsistent. |
| 7 | Verification Complete | PASS | Commands and explicit pass criteria are present. |
| 8 | Decision-Minimizing | FAIL | Implementation vs test strategy conflict on the VS import mechanism (direct import vs `importlib.import_module`), leaving decisions to Coding. |
| 9 | Determinism Defined | PASS | No nondeterministic outputs; plugin detection uses explicit attribute checks. |

## Additional Quality Checks

- Error Codes: OK — SSOT now specifies `VapourSynthNotFoundError` vs `VapourSynthError` and the plan aligns.
- Failure Modes: OK — loader stub uses typed `SourceLoadError`.
- Derived Outputs: OK — contract artifacts are check-only.
- Rollback Guidance: OK — STOP instruction exists.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. Whether `env.py` uses `import vapoursynth as vs` or `importlib.import_module("vapoursynth")` (tests currently patch the latter, notes show the former).
2. Exact mock core shape to exercise the SSOT plugin detection patterns deterministically (how to represent nested namespaces/attributes).

## Concrete Edits Required (plan-v3.md) — plan-only

1. **Make the VS import mechanism explicit and consistent**
   - Section: `src/frame_compare/vs/env.py` + `tests/vs/test_env.py` + plan notes
   - Problem: Tests specify patching `importlib.import_module`, but the plan’s Notes suggest direct import; Coding could choose either and break tests.
   - Required Change: Pick one mechanism and make it explicit in the plan text and tests.
     - Recommended: use `importlib.import_module("vapoursynth")` inside `frame_compare.vs.env` for both functions, so tests can patch `frame_compare.vs.env.importlib.import_module`.
     - Update `## Notes for Coding Agent` to match (remove/replace the direct-import snippet).

2. **Specify the exact mock core objects for plugin detection tests**
   - Section: `tests/vs/test_env.py`
   - Problem: Plan names tests but doesn’t define the mock Core shape needed to trigger `detect_plugins`’ SSOT attribute checks.
   - Required Change: Add a short code snippet specifying a deterministic mock core using `types.SimpleNamespace` (or equivalent), e.g.:
     - “lsmas present” core has either `core.lsmas.LWLibavSource` or `core.lw.LWLibavSource`
     - `libplacebo` present core has `core.placebo.Tonemap`
     - `bestsource` present core has `core.bs.VideoSource`
     - `ffms2` present core has `core.ffms2.Source`

## Ready for Implementation

Return to Planning Agent for a surgical revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-1__vs-environment

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-review-v2.md
Read file: .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v2.md
Write file: .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v3.md

## Hard Rules
- Include `## Changes Since plan-v2` listing only the deltas that address this review.
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
