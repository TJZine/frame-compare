---
RUN_ID: 2026-01-04__p6-6-1__vspreview-integration
VERSION: v1
TARGET: Phase 6 → Item 6.6 (VSPreview Integration)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-review-v1.md
---

# Plan Review Report: VSPreview Integration (Module + Manual Overrides)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | FAIL | Plan scope does not state whether `doctor` integration (vspreview spec §6.1) is in-scope or deferred. |
| 2 | Dependencies | FAIL | Missing required dependency wiring for doctor integration and explicit handling of optional external dependency detection (`shutil.which` + `find_spec`) in tests. |
| 3 | File List | FAIL | Missing `src/frame_compare/orchestration/doctor.py` update required by vspreview spec §6.1 / existing code already contains a `vspreview` doctor check that conflicts with the spec example. |
| 4 | Contract Impact | PASS | Canonical contracts not touched; import-linter SSOT update is already included and gated. |
| 5 | Types Complete | PASS | Public function signatures are listed and spec-anchored; dataclasses are referenced from SSOT. |
| 6 | Tests Complete | FAIL | Tests are named, but key assertions/mocking are underspecified (risk of flakiness if `vspreview` exists on PATH; precedence test does not specify how to prevent FFprobe/FFmpeg calls deterministically). |
| 7 | Verification Complete | PASS | Commands are specified and include `lint-imports`; pass criteria is explicit. |
| 8 | Decision-Minimizing | FAIL | Leaves unresolved decisions for Coding Agent: manual `AlignmentResult` fields (`time_offset_seconds`, `correlation_score`, clip name vs stem), and adapter behavior for `VSPreviewConfig.enabled` / launch telemetry printing. |
| 9 | Determinism Defined | FAIL | Determinism requirements are stated, but timestamp format and test strategy for deterministic behavior are not specified. |

## Additional Quality Checks

- Error Codes: OK (vspreview spec §9 defines FC-2008 / FC-4019); missing SSOT for `ErrorContext.name` / `hint` values for these new error types.
- Failure Modes: Issue — plan does not explicitly implement vspreview spec §3.2.3 “Always print script path + command” behavior (or explicitly defer it), and does not define behavior when `config.enabled` is `False`.
- Derived Outputs: OK (no contract views / traceability outputs required).
- Rollback Guidance: Issue — no “STOP and return to Planning” guidance if SSOT updates are needed (they are).
- SSOT Update Audit (if SSOT changed this loop): N/A (no SSOT edits in plan-v1).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Manual override `AlignmentResult` field semantics are not defined in SSOT (manual `time_offset_seconds`, `correlation_score`, and `reference_clip`/`comparison_clip` naming conventions).
2. Adapter behavior when `VSPreviewConfig.enabled` is `False` is not defined (generate script? launch? raise?).
3. Launch telemetry requirements (§3.2.3) are not concretely assigned (print/log location, exact command string, non-zero exit policy).
4. Test mocking strategy is underspecified (PATH vs import detection, preventing FFprobe/FFmpeg execution, TTY behavior).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT: define manual override `AlignmentResult` semantics**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` → `### 2.4 VSPreview Integration and Manual Overrides (Deterministic Contract)`
   - Problem: SSOT defines precedence but not how to construct `AlignmentResult` for manual overrides; Coding Agent would have to decide values for required fields.
   - Required Change: Add explicit rules for manual-override `AlignmentResult` construction:
     - Which clip identifiers are used for `reference_clip` / `comparison_clip` (stem vs filename).
     - Exact rule for `time_offset_seconds` when `method="manual"` (including whether FFprobe is allowed/required).
     - Exact rule for `correlation_score` when `method="manual"` (explicit constant or derived rule).

2. **Update SSOT: define VSPreviewConfig “enabled” behavior**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md` → `### 3.2 Launch Session for Verification (All Comparisons)`
   - Problem: `VSPreviewConfig.enabled` exists in the public API but the behavior is not specified; plan does not define it either.
   - Required Change: Specify what `launch_alignment_verification_session(...)` does when `config.enabled` is `False` (must be deterministic and not require external deps).

3. **Revise plan: add doctor integration file + behavior**
   - Section: `## Files to Create/Modify`
   - Problem: vspreview spec §6.1 defines doctor reporting, and `src/frame_compare/orchestration/doctor.py` already contains a `vspreview` check that does not match the SSOT example; plan does not include the required fix.
   - Required Change: Add `src/frame_compare/orchestration/doctor.py` to the file list with explicit behavior (use `frame_compare.vspreview.is_vspreview_available()` and ensure optional-vspreview semantics match SSOT).

4. **Revise plan: make adapter launch telemetry implementable**
   - Section: `src/frame_compare/vspreview/adapter.py` plan item
   - Problem: vspreview spec §3.2.3 requires always printing script path + command and non-zero exit warn/continue policy (or explicit exception mapping); plan currently doesn’t specify how these are satisfied.
   - Required Change: Add explicit requirements for where and how telemetry is emitted (print vs structlog), what the exact launch command string is, and how non-zero exit is handled (raise vs return, and caller responsibilities).

5. **Revise plan: de-flake availability tests + prevent external binaries in precedence test**
   - Section: `tests/vspreview/test_overrides.py`
   - Problem: `test_is_vspreview_available_returns_false_when_missing` can fail if `vspreview` is present on PATH; `test_manual_override_takes_precedence_over_computed` does not specify deterministic prevention of FFprobe/FFmpeg invocation.
   - Required Change: Specify exact mocks and assertions:
     - Patch both `importlib.util.find_spec` and `shutil.which` as needed to force the intended code path.
     - In precedence test, patch `_extract_audio` and `_probe_fps` (or the subprocess boundary) to raise if called, proving overrides short-circuit external deps.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-6-1__vspreview-integration

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
- Under heading: "### 2.4 VSPreview Integration and Manual Overrides (Deterministic Contract)" add/change:
  - Define the exact `AlignmentResult` field mapping when the source is a manual override (`method="manual"`), including: `reference_clip`/`comparison_clip` naming convention, `time_offset_seconds` rule, and `correlation_score` rule.

Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md
- Under heading: "### 3.2 Launch Session for Verification (All Comparisons)" add/change:
  - Specify deterministic behavior for `launch_alignment_verification_session(...)` when `config.enabled` is `False` (generate script? launch? return/raise?).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v1.md
Write file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
