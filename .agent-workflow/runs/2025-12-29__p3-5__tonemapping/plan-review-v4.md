---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v4
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v4.md
---

# Plan Review Report: HDR Tonemapping

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v4.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope list explicit. |
| 2 | Dependencies | PASS | Dependencies and imports are pinned; SSOT now fully specifies RGBS conversion + post-processing. |
| 3 | File List | PASS | Explicit list includes spec edits + code + tests + docs. |
| 4 | Contract Impact | PASS | Canonical contracts untouched. |
| 5 | Types Complete | PASS | Public signatures are listed and covered by SSOT anchors. |
| 6 | Tests Complete | FAIL | Test list is present, but required assertions/expected calls are not specified per test; Coding Agent would need to decide what to assert for `_to_rgbs()` and path-selection tests. |
| 7 | Verification Complete | PASS | Commands and pass criteria are explicit. |
| 8 | Decision-Minimizing | PASS | Core acquisition, RGBS conversion, post-processing, fallback formula, and unsupported curve behavior are pinned in SSOT; plan-level implementation helpers are specified. |
| 9 | Determinism Defined | PASS | Determinism + clamping specified; no RNG. |

## Additional Quality Checks

- Error Codes: OK — no new errors; `TonemapError (FC-4003)` is consistently specified.
- Failure Modes: OK — RGBS conversion failure wrapping and unsupported curve behavior are defined in SSOT.
- Derived Outputs: OK — no generated outputs in this slice.
- Rollback Guidance: OK — STOP guidance present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. For each listed test, the exact assertions (calls/args/raised error code/hint content) are not specified, leaving test contract decisions to the Coding Agent.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Make unit tests mechanically checkable**
   - Section: `tests/vs/test_tonemap.py` (NEW) in `.agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v4.md`
   - Problem: Tests are listed by name only; expected assertions and mocked call shapes are not specified.
   - Required Change (plan only): for each test, add 1–3 bullets that specify *exactly* what is asserted. Minimum required additions:
     - `test_to_rgbs_no_op_when_already_rgbs`: assert returned object is the same clip and `clip.resize.Bicubic` is not called.
     - `test_to_rgbs_converts_non_rgbs`: assert `clip.resize.Bicubic` is called once with `format=vs.RGBS` and `matrix_in_s="709"`, and returned clip is used.
     - `test_apply_tonemap_uses_libplacebo_when_available`: assert `_apply_libplacebo` called once with `(clip, settings, core)` where `core == clip.std.core`.
     - `test_apply_tonemap_uses_fallback_when_libplacebo_missing`: assert `_fallback_tonemap` called once with `(clip, settings, hdr_metadata)` and `_apply_libplacebo` not called.
     - `test_apply_tonemap_unsupported_tone_curve_raises_error`: assert `TonemapError.code == "FC-4003"` and error message/hint contains the supported curve list.
     - `test_apply_tonemap_wraps_exception_in_tonemap_error`: assert `TonemapError.code == "FC-4003"` and original exception is chained (or explicitly state “no chaining” if that’s required).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v5.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-5__tonemapping

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v4.md
Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v4.md
Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Address every item marked FAIL with minimal churn; do not change SSOT unless required by this report.
