---
RUN_ID: 2025-12-29__p3-2__video-loading
VERSION: v3
TARGET: Phase 3 → Item 3.2 Video Loading
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-review-v3.md
---

# Plan Review Report: Video Source Loading

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v3.md

The plan is close and now passes the mechanical SSOT anchor gate (`scripts/validate_spec_anchors.py`). One remaining test requirement is internally inconsistent with the SSOT behavior for `_detect_hdr()` (defaults cannot be asserted when `hdr_metadata` is required to be `None` for non-HDR), leaving a decision to the Coding Agent.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope clearly listed. |
| 2 | Dependencies | PASS | Phase 3.1 dependencies and plugin expectations specified. |
| 3 | File List | PASS | Complete, minimal, explicit. |
| 4 | Contract Impact | PASS | Contracts touched: NO; check-only gates included. |
| 5 | Types Complete | PASS | All planned function signatures listed; anchor validation passes. |
| 6 | Tests Complete | FAIL | One test case cannot be implemented as specified without changing SSOT behavior. |
| 7 | Verification Complete | PASS | Commands + explicit pass criteria included; plan artifact validation present. |
| 8 | Decision-Minimizing | FAIL | `_detect_hdr` defaults test forces an implementation choice (metadata None vs defaults exposure). |
| 9 | Determinism Defined | PASS | Trim semantics and HDR detection rules are explicit and stable. |

## Additional Quality Checks

- Error Codes: OK — asserts `.code == "FC-2003"` / `.code == "FC-4015"` where relevant.
- Failure Modes: OK — missing plugin vs corrupt file differentiated per SSOT.
- Derived Outputs: OK — contract-view/traceability check-only commands included.
- Rollback Guidance: OK — STOP rule present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether `_detect_hdr({})` should return defaults in `HDRMetadata` despite `is_hdr=False` (SSOT says `hdr_metadata is None if is_hdr is False`).

## Concrete Edits Required (plan-only)

1. **Fix the “defaults for missing props” HDR test to match SSOT**
   - Section: `tests/vs/test_source.py` → “HDR Detection Tests”
   - Problem: Plan requires `test_detect_hdr_uses_defaults_for_missing_props — Empty props → color_primaries=2, transfer=2, matrix=2, is_hdr=False`, but with `is_hdr=False` the SSOT requires `hdr_metadata=None`, so defaults are not observable.
   - Required Change: Replace with two deterministic tests that match SSOT:
     - `test_detect_hdr_empty_props_returns_false_and_none` — `{}` → `is_hdr is False` and `hdr_metadata is None`
     - `test_detect_hdr_defaults_matrix_when_missing` — `{_Transfer: 16, _Primaries: 9}` (no `_Matrix`) → `is_hdr is True` and `hdr_metadata.matrix == 2` (and `mastering_display/max_cll/max_fall is None` if those keys are absent)

## Ready for Implementation

Return to Planning Agent for a plan-only revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-2__video-loading

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-review-v3.md
Read file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v3.md
Write file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v4.md

## Hard Rules
- Spec Anchors must pass `validate_spec_anchors.py`.
