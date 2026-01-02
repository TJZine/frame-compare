---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v2
TARGET: Phase 5 → Item 5.2
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v2.md
---

# Plan Review Report: Metadata Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 5.2 metadata) with clear out-of-scope. |
| 2 | Dependencies | PASS | SSOT updated: `services-module.md` “### 3.2 Public API” now matches client injection requirement from `async-semantics.md`. |
| 3 | File List | PASS | Explicit file list; no ambiguous “related files”. |
| 4 | Contract Impact | PASS | Marked NO; no contract regen required. |
| 5 | Types Complete | PASS | Public API signatures listed and aligned with anchored SSOT headings. |
| 6 | Tests Complete | FAIL | Plan does not specify async test mechanics for `async def lookup_tmdb` / `async def resolve_metadata` (missing `@pytest.mark.anyio` and explicit `httpx.AsyncClient` fixture shape), leaving the Coding Agent to decide. |
| 7 | Verification Complete | PASS | Canonical gates present (`pyright`, `ruff`, `pytest`, `lint-imports`) with explicit pass criteria. |
| 8 | Decision-Minimizing | FAIL | Async test execution and injected client lifecycle in unit tests are not fully specified. |
| 9 | Determinism Defined | PASS | Deterministic parser selection + normalization rules specified in updated SSOT and reflected in the plan. |

## Additional Quality Checks

- Error Codes: OK (no new error types; uses existing `MetadataError`/`TmdbError`/`TmdbRateLimitedError`).
- Failure Modes: OK (api_key None, invalid format, invalid callback index all defined).
- Derived Outputs: OK (no generated outputs in this slice).
- Rollback Guidance: OK (plan routes behavior to SSOT; remaining issue is test wiring only).
- SSOT Update Audit (this loop): OK — `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` “### 3.2 Public API” changes are implementable and consistent with `async-semantics.md` Section 7 and deterministic testing requirements.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Which pytest async mechanism to use for `lookup_tmdb`/`resolve_metadata` tests (and how to structure the injected `httpx.AsyncClient` lifecycle inside tests).

## Concrete Edits Required (CHANGES REQUIRED)

1. **Specify async test contract for services**
   - Section: `tests/services/test_metadata.py` (NEW)
   - Problem: Tests for `lookup_tmdb` and `resolve_metadata` are listed, but plan does not specify that they are `async def` tests and how they are executed.
   - Required Change (plan-v3):
     - State: all `test_lookup_tmdb_*` and `test_resolve_metadata_*` tests are `async def` and decorated with `@pytest.mark.anyio` (per `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md` “### 3.1 Pytest Configuration”).
     - Add a concrete fixture shape for the injected client used in these tests, e.g.:
       - `@pytest.fixture` providing an `httpx.AsyncClient` via `async with httpx.AsyncClient() as client: yield client`.

2. **Anchor async test mechanism in Spec Anchors**
   - Section: `## Spec Anchors (SSOT)`
   - Problem: Plan anchors only to “1.3 Deterministic Test Vector Policy (SSOT)”; async test execution rules live elsewhere in SSOT.
   - Required Change (plan-v3):
     - Add `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md` Section: "3.1 Pytest Configuration" to Spec Anchors.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-2__metadata-service

## Revision Required
Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v2.md
Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
