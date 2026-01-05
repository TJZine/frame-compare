---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v3
TARGET: Phase 5 → Item 5.2
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v3.md
---

# Plan Review Report: Metadata Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 5.2 metadata) with clear out-of-scope. |
| 2 | Dependencies | PASS | Dependencies and DI rules anchored; SSOT matches plan signatures. |
| 3 | File List | FAIL | Plan introduces an `async_client` fixture but allows two placements (“`tests/services/conftest.py` or inline”) and does not list `tests/services/conftest.py` as a file to create/modify. |
| 4 | Contract Impact | PASS | Marked NO; no contract regen required. |
| 5 | Types Complete | PASS | Public signatures are explicit and spec-anchored. |
| 6 | Tests Complete | FAIL | Async test execution is specified, but fixture placement is ambiguous (Coding Agent would choose file layout). |
| 7 | Verification Complete | PASS | Canonical gates present and pass criteria explicit. |
| 8 | Decision-Minimizing | FAIL | Test fixture location remains a decision point. |
| 9 | Determinism Defined | PASS | Deterministic parsing + selection rules are specified and testable. |

## Additional Quality Checks

- Error Codes: OK (no new errors; uses existing typed errors).
- Failure Modes: OK (api_key None, invalid format, invalid callback index defined).
- Derived Outputs: OK (none).
- Rollback Guidance: OK (only remaining change is plan wiring).
- SSOT Update Audit (if SSOT changed this loop): N/A (no SSOT changes in this loop; SSOT was updated in prior loop and remains consistent).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Where the `async_client` fixture must live (inline in `tests/services/test_metadata.py` vs `tests/services/conftest.py`).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Fix async client fixture placement ambiguity**
   - Section: `## Files to Create/Modify` and `### 5. tests/services/test_metadata.py`
   - Problem: Plan permits two fixture locations, leaving a test file layout decision.
   - Required Change (plan-v4):
     - Choose exactly one fixture location:
       - Option A (preferred for minimal churn): define `async_client` fixture inside `tests/services/test_metadata.py`; do NOT introduce `tests/services/conftest.py`.
       - Option B: create `tests/services/conftest.py` containing only the `async_client` fixture; add it explicitly to the file list and state `tests/services/test_metadata.py` imports/uses it.
     - Remove the “or inline” wording so the Coding Agent has no choice to make.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v4.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-2__metadata-service

## Revision Required
Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v3.md
Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v3.md
Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
