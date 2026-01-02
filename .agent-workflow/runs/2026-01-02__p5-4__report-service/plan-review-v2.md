---
RUN_ID: 2026-01-02__p5-4__report-service
VERSION: v2
TARGET: Phase 5 → Item 5.4 (Report Generator)
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v2.md
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/data-contracts.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-review-v2.md
---

# Plan Review Report: Report Generator Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: `frame_compare.services.report` report generation. |
| 2 | Dependencies | PASS | Dependencies/imports are explicit and match module specs. |
| 3 | File List | PASS | File set is explicit and minimal. |
| 4 | Contract Impact | PASS | Canonical contracts not touched; `data-contracts.md` now explicitly marks v2 report contract as future for Phase 5.4. |
| 5 | Types Complete | PASS | Public signature is present as one-line backticked signature under `## Public API (Signatures)`. |
| 6 | Tests Complete | FAIL | Test-count label says “27 total” but the plan explicitly lists 31 tests; this creates an avoidable decision about expected test set size. |
| 7 | Verification Complete | PASS | Commands + pass criteria are explicit. |
| 8 | Decision-Minimizing | FAIL | The mismatch in test-count labeling leaves a minor (but real) decision point about “27 vs 31”. |
| 9 | Determinism Defined | PASS | SSOT + plan explicitly require preserving `data.clips`/`data.frames` order and a deterministic output-path fallback. |

## Additional Quality Checks

- Error Codes: OK (uses existing `ReportError` / FC-4017; no new errors introduced)
- Failure Modes: OK (SSOT now specifies screenshot mapping/length validation + I/O failure mapping)
- Derived Outputs: OK (no generated contract views involved)
- Rollback Guidance: OK (plan-only correction)
- SSOT Update Audit (this loop): OK (SSOT changes requested in `plan-review-v1.md` are present; v2 contract sections are explicitly marked future/out-of-scope for Phase 5.4)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether to implement 27 vs 31 tests (plan explicitly lists 31, but the label says 27).

## Concrete Edits Required (CHANGES REQUIRED)

1. **Fix test-count label (mechanical)**
   - Section: Plan → `tests/services/test_report.py` section
   - Problem: “Tests (27 total)” contradicts the enumerated 31 test cases.
   - Required Change: Update the label to “Tests (31 total)”.

## Ready for Implementation

Return to Planning Agent for a mechanical-only revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-4__report-service

## Revision Required
Read file: .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v2.md
Write file: .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
