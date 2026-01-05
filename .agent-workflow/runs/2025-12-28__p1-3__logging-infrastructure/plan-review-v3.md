---
RUN_ID: 2025-12-28__p1-3__logging-infrastructure
VERSION: v3
TARGET: Phase 1 → Item 1.3 Logging Infrastructure
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-review-v3.md
---

# Plan Review Report: Logging Infrastructure (Phase 1.3)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v3.md

The plan is close to implementation-ready (tests + determinism + rollback are now concrete), but it fails the workflow’s SSOT anchor validation gate due to how Spec Anchor headings are written. This must be fixed before Coding proceeds.

Evidence (workflow gate):
- Ran: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v3.md`
- Result: `ERROR: ... missing heading '### 4.3 Logging + Correlation IDs' ...`

Root cause: `scripts/validate_spec_anchors.py` matches SSOT headings by title text (without the leading `###`), so Spec Anchor “Section” entries must use the heading title (e.g., `4.3 Logging + Correlation IDs`), not the full Markdown heading token (e.g., `### 4.3 ...`).

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice with explicit out-of-scope list. |
| 2 | Dependencies | PASS | Dependencies and import constraints are explicit. |
| 3 | File List | PASS | Complete and minimal; rollback is file-specific. |
| 4 | Contract Impact | PASS | “Contracts touched: NO” present. |
| 5 | Types Complete | PASS | Public signatures are listed and spec-anchored. |
| 6 | Tests Complete | PASS | Exact test names, assertions, negative cases, and isolation steps specified. |
| 7 | Verification Complete | FAIL | Missing required spec-anchor validation command for the plan artifact (must pass before implementation). |
| 8 | Decision-Minimizing | FAIL | Spec Anchors currently do not pass the gate; Coding Agent would have to interpret/repair anchors. |
| 9 | Determinism Defined | PASS | Deterministic assertions and test isolation are specified. |

## Additional Quality Checks

- Error Codes: OK (explicit “no new FC-xxxx codes”).
- Failure Modes: OK (fallback behavior anchored to SSOT).
- Derived Outputs: OK (none).
- Rollback Guidance: OK (file-specific).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
- NONE once Spec Anchors are corrected to satisfy `validate_spec_anchors.py` and the plan includes the required gate command.

## Concrete Edits Required (CHANGES REQUIRED)

1. **Fix Spec Anchors to satisfy `validate_spec_anchors.py`**
   - Section: `## Spec Anchors (SSOT)`
   - Problem: “Section” entries include Markdown hashes (`### ...`), but the validator expects the heading *title text* only.
   - Required Change: Update Section entries to remove the leading hashes and match the SSOT heading title exactly:
     - For `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`:
       - `Section: "4.3 Logging + Correlation IDs"`
       - `Section: "1.2 Import Constraints"`
     - For `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
       - `Section: "1.3 Deterministic Test Vector Policy (SSOT)"`
   - Success check: `scripts/validate_spec_anchors.py` must print `OK: Spec Anchors valid ...`.

2. **Add the required spec-anchor validation to the plan’s Verification Commands**
   - Section: `## Verification Commands`
   - Problem: Plan doesn’t include the workflow’s required anchor validation command for this plan artifact.
   - Required Change: Add:
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v4.md`

3. **Update DECISIONS artifact reference to the current plan review**
   - Section: `docs/DECISIONS.md` required facts
   - Problem: Plan instructs recording `plan-review-v2`.
   - Required Change: Update to `plan-review-v3` (or if producing plan-v4, `plan-review-v4` once approved).

4. **Remove ambiguity in filtering test imports**
   - Section: `tests/utils/test_logging.py` filtering tests snippet
   - Problem: Uses `structlog.testing.ReturnLogger()` without specifying an import of `structlog.testing`.
   - Required Change: Specify one deterministic import form in the plan (choose one):
     - `from structlog.testing import ReturnLogger` and use `ReturnLogger()`; or
     - `import structlog.testing` before using `structlog.testing.ReturnLogger()`.

## Ready for Implementation

Return to Planning Agent for revision. Next version: plan-v4.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-3__logging-infrastructure

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-review-v3.md
Read file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v3.md
Write file: .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v4.md

## Hard Rules
- Spec Anchors must pass: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-28__p1-3__logging-infrastructure/plan-v4.md`
