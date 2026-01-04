---
RUN_ID: 2026-01-04__p6-4__frame-plan-module
VERSION: v1
TARGET: Phase 6 → Item 6.4 (FramePlan Module)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v1.md
---

# Plan Review Report: FramePlan Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v1.md

Key blockers found:
- SSOT/spec mismatch for `InsufficientFramesError` usage in `frame-plan-module.md` (spec currently shows `count/available`; SSOT contracts and `errors-module.md` define `count/required` with a `path`).
- Spec-anchor STOP gate currently fails: `validate_spec_anchors.py` fails because `## 4. Algorithm Specification` is truncated by `# ...` lines inside fenced code blocks, so `_select_from_bin` is not visible in the anchored span.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Phase 6 → Item 6.4 is isolated; out-of-scope list is explicit. |
| 2 | Dependencies | FAIL | `InsufficientFramesError` contract/signature expectations are inconsistent across SSOT vs current `src/frame_compare/errors.py`; plan currently proposes updating SSOT to match code (wrong direction vs contracts). |
| 3 | File List | FAIL | SSOT correction must cover both `frame-plan-module.md` §4.3 and §5; plan lists only §5. If error drift is resolved in this run, `src/frame_compare/errors.py` (and targeted tests) must be listed explicitly. |
| 4 | Contract Impact | PASS | Contracts are not edited in this run. |
| 5 | Types Complete | FAIL | Signature coverage gate fails (`validate_spec_anchors.py`), so spec-anchor coverage is not implementation-ready. |
| 6 | Tests Complete | FAIL | Negative-case test needs to assert the intended error payload contract for this module boundary (at minimum: code FC-3004 + deterministic placeholder `path` handling). |
| 7 | Verification Complete | PASS | Commands + pass criteria are present, but plan must be updated so the Spec Anchors gate actually passes. |
| 8 | Decision-Minimizing | FAIL | Current plan leaves ambiguity about which `InsufficientFramesError` signature/message/details are authoritative and how to satisfy SSOT + validator simultaneously. |
| 9 | Determinism Defined | PASS | Cross-session determinism test is explicitly planned. |

## Additional Quality Checks

- Error Codes: **Issue** — Plan references FC-3004 but proposes SSOT usage that conflicts with `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml` (uses `{count}` / `{required}`) and `errors-module.md`.
- Failure Modes: OK — count > num_frames and count == 0 are explicitly handled in acceptance criteria.
- Derived Outputs: OK — no contract generators involved.
- Rollback Guidance: **Issue** — Add a hard STOP/return-to-planning note if SSOT alignment cannot be achieved without widening scope.
- SSOT Update Audit (required): **Issue** — Proposed SSOT edit must align to contracts + `errors-module.md`, and must fix both `§4.3` and `§5` (not just `§5`).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Authoritative `InsufficientFramesError` interface: align to SSOT contracts (`count/required` + `path`) vs current `src/frame_compare/errors.py` (`requested/available` + path in message).
2. FramePlan module behavior when `path` is unavailable: define the deterministic placeholder `Path("<frame-plan>")` usage in SSOT and tests.
3. Spec-anchor wiring: choose the SSOT/doc fix that makes `validate_spec_anchors.py` pass deterministically (avoid `# ...` at column 1 inside anchored code fences, or adjust plan anchors accordingly).

## Concrete Edits Required (plan-v2)

1. **Fix SSOT error usage in `frame-plan-module.md`**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md`
   - Problem: SSOT currently shows `InsufficientFramesError(count=..., available=...)` and omits required `path`; this conflicts with canonical SSOT (`contracts/error_codes.yaml` + `errors-module.md`) and forces Coding Agent design choices.
   - Required Change:
     - Under heading `"4.3 Complete Algorithm"`: update the raise example to use `path=Path("<frame-plan>")` and `count=num_frames`, `required=count`.
     - Under heading `"5. Error Handling"`: update the example similarly and ensure comments/examples match the `{count}` / `{required}` message template.

2. **Make Spec Anchors pass `validate_spec_anchors.py`**
   - Section: `## Spec Anchors (SSOT)` in the plan
   - Problem: Anchoring to `"4. Algorithm Specification"` currently truncates early because the spec file contains `# ...` lines at column 1 inside fenced code blocks, so `_select_from_bin` is not discoverable by the validator.
   - Required Change (choose exactly one approach and document it in plan-v2; no ambiguity):
     - **Preferred (SSOT fix):** In `frame-plan-module.md`, indent `# ...` lines inside fenced code blocks under `"4.1 Bin Partitioning"` / `"5. Error Handling"` so they no longer start at column 1.
     - **Alternative (plan-only):** Change plan Spec Anchors to target `"4.2 Frame Selection Per Bin"` and `"4.3 Complete Algorithm"` (instead of `"4. Algorithm Specification"`), and ensure `_select_from_bin` remains covered.

3. **Resolve `InsufficientFramesError` drift before FramePlan implementation**
   - Section: Dependencies + Files to Modify
   - Problem: Current `src/frame_compare/errors.py` does not match SSOT contracts/message template for FC-3004; FramePlan would institutionalize drift.
   - Required Change: Update plan-v2 to explicitly do one of:
     - Include a minimal fix to `src/frame_compare/errors.py` for `InsufficientFramesError` to match SSOT (`count/required` keys + message template) and add/extend a targeted unit test asserting `.context.details` keys and message template shape for FC-3004, OR
     - Explicitly block this run on a prior corrective run (new RUN_ID) that restores SSOT compliance for FC-3004 (do not proceed to coding until that run is completed).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-4__frame-plan-module

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/frame-plan-module.md
- Under heading: "4.3 Complete Algorithm" add/change:
  - Update the `InsufficientFramesError` raise example to use `Path("<frame-plan>")` and SSOT keys/semantics: `count=num_frames`, `required=count`.
- Under heading: "5. Error Handling" add/change:
  - Update the example to use `path=Path("<frame-plan>")`, `count=<available_frames>`, `required=<requested_frames>` and ensure the message/hint comments match FC-3004 `{count}` / `{required}` SSOT.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v1.md
Write file: .agent-workflow/runs/2026-01-04__p6-4__frame-plan-module/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
