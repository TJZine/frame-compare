---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v5
TARGET: Phase 5 → Item 5.2
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v5.md
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v5.md
---

# Plan Review Report: Metadata Service (Design Fix)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v5.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Narrow slice: design fix from `review-v1.md` critical issues. |
| 2 | Dependencies | PASS | Spec update is present in `services-module.md` “3.2 Public API”; no new deps. |
| 3 | File List | FAIL | Plan omits a required implementation change in `src/frame_compare/services/metadata.py` (removing existing source normalization) needed to satisfy the updated SSOT + updated test expectation. |
| 4 | Contract Impact | PASS | Contracts touched: NO (spec-only update). |
| 5 | Types Complete | PASS | Public signature listed (`parse_filename(filename: str) -> ParsedMetadata`) and anchored. |
| 6 | Tests Complete | FAIL | Acceptance criteria includes “parser raises → fallback without raising”, but plan does not define an explicit test name/shape for that behavior. |
| 7 | Verification Complete | PASS | Canonical gates included with explicit pass criteria. |
| 8 | Decision-Minimizing | FAIL | Coding Agent would need to infer which normalization code to remove and whether to add a new test for parser exceptions. |
| 9 | Determinism Defined | PASS | Updated SSOT defines source verbatim and never-raises contract; plan must align implementation steps accordingly. |

## Additional Quality Checks

- Error Codes: OK (no new errors; uses existing `MetadataError`).
- Failure Modes: Issue — test coverage for parser-exception fallback is not concretely specified.
- Derived Outputs: OK (none).
- Rollback Guidance: OK (scope is minimal; if mismatch persists, STOP and return to Planning).
- SSOT Update Audit (if SSOT changed this loop): OK — `services-module.md` “3.2 Public API” additions (“Source representation”, “Exception handling”) are implementable and consistent with deterministic parsing rules.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Which existing “source normalization” logic in `parse_filename` must be removed to comply with “verbatim parser output”.
2. Whether to add a new unit test to assert the “parser raises → fallback” behavior, and what its assertions are.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Make the implementation steps match updated SSOT (remove normalization)**
   - Section: `### 1. src/frame_compare/services/metadata.py (MODIFY)`
   - Problem: Plan only adds try/except (already present in current implementation), but updated SSOT requires *no* `source` normalization; current code normalizes `"Blu-ray"` → `"BluRay"`.
   - Required Change (plan-v6):
     - Add an explicit step to remove any mapping/normalization for `ParsedMetadata.source` (specifically remove `"Blu-ray"` → `"BluRay"` conversion).
     - State the expected post-condition: if parser returns `"Blu-ray"`, the returned `ParsedMetadata.source` is exactly `"Blu-ray"`.

2. **Add a concrete test for parser exceptions**
   - Section: `### 2. tests/services/test_metadata.py (MODIFY)` and `## Acceptance Criteria`
   - Problem: Plan asserts “parser raises → fallback without raising” but does not specify a test, leaving a decision.
   - Required Change (plan-v6):
     - Add test: `test_parse_filename_parsers_raise_falls_back_to_stem`:
       - Arrange: monkeypatch `frame_compare.services.metadata.guessit` and `frame_compare.services.metadata.anitopy.parse` to raise.
       - Act: call `parse_filename("Movie.Name.2024.BluRay.1080p.mkv")`.
       - Assert: function does not raise; `title == "Movie Name 2024 BluRay 1080p"`; and `year/season/episode/release_group/source/resolution is None`.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v6.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-2__metadata-service

## Revision Required
Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v5.md
Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v5.md
Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v6.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
