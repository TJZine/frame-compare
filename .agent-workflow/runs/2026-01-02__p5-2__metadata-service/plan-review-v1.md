---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v1
TARGET: Phase 5 → Item 5.2
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v1.md
---

# Plan Review Report: Metadata Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 5.2 metadata) with clear out-of-scope. |
| 2 | Dependencies | FAIL | SSOT conflict: `services-module.md` 3.2 defines `lookup_tmdb/resolve_metadata` without injected `httpx.AsyncClient`, but `async-semantics.md` 7.1 “Golden Rule” forbids services creating their own client; plan currently chooses a third signature not reflected in SSOT. |
| 3 | File List | PASS | Explicit file list; no “and related files”. |
| 4 | Contract Impact | PASS | Marked NO; no contract regen required. |
| 5 | Types Complete | FAIL | Planned public signatures do not match the SSOT signatures under `services-module.md` “### 3.2 Public API”, and several required edge behaviors are unspecified at the SSOT boundary (api_key missing, callback index validation). |
| 6 | Tests Complete | FAIL | Tests are named, but required fixtures/mocked TMDB payload shapes and callback error-case behavior are not specified, leaving the Coding Agent to choose. |
| 7 | Verification Complete | FAIL | Commands are partial/non-canonical (pyright/ruff scoped to paths); plan must list canonical gates and explicit pass criteria. |
| 8 | Decision-Minimizing | FAIL | Multiple design/behavior decisions remain (client ownership/API surface reconciliation; parser selection heuristic; api_key None; invalid callback index; title normalization rules). |
| 9 | Determinism Defined | FAIL | Deterministic parsing/normalization rules for `parse_filename` (extension stripping, separator normalization, parser selection) are implied by tests but not fully specified in SSOT. |

## Additional Quality Checks

- Error Codes: OK (no new errors proposed; references existing `TmdbError`/`TmdbRateLimitedError`/`MetadataError`).
- Failure Modes: Issue — behavior for `MetadataConfig.api_key is None` and for invalid `prompt_callback` return index is not defined.
- Derived Outputs: OK (no generated artifacts in this slice).
- Rollback Guidance: Issue — plan must state “STOP and return to Planning” if SSOT mismatch persists after updates.
- SSOT Update Audit (if SSOT changed this loop): N/A (no SSOT edits in this loop).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Whether `lookup_tmdb` / `resolve_metadata` accept an injected `httpx.AsyncClient` (and whether they are `async def`) vs the current SSOT signatures.
2. What `lookup_tmdb` does when `config.api_key` is `None` (skip vs error) and what constitutes an “invalid” key (format validation).
3. Exact parser-selection + title-normalization rules in `parse_filename` (extension stripping, separator normalization, when to prefer Anitopy).
4. What happens when `prompt_callback` returns an out-of-range index (raise vs clamp vs default).
5. Exact minimal mocked TMDB response payload shape required for unit tests (fields used for movie vs tv year extraction).

## Concrete Edits Required (CHANGES REQUIRED)

1. **Update SSOT to reconcile HTTP client DI with Metadata API**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`
   - Under heading: `### 3.2 Public API`
   - Required changes (minimal, SSOT-level):
     - Update the `lookup_tmdb` signature to include an injected client parameter: add `client: httpx.AsyncClient`.
     - Update the `resolve_metadata` signature to include an injected client parameter: add `client: httpx.AsyncClient`.
     - Add an explicit rule: these functions MUST NOT create an `httpx.AsyncClient` (client is injected; not owned).

2. **Define missing SSOT behaviors required by tests**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`
   - Under heading: `### 3.2 Public API`
   - Required additions (minimal bullets inside the existing docstring blocks):
     - `lookup_tmdb`: if `config.api_key is None`, return `None` without making a request.
     - `lookup_tmdb`: validate API key format before request (32 hex chars); invalid format raises `TmdbError` (message content may be asserted in tests).
     - `resolve_metadata`: if multiple results and `prompt_callback is None`, select index `0` (first result).
     - `resolve_metadata`: if `prompt_callback` returns an invalid index, raise `MetadataError` (specify error message substring for stable tests).
     - `parse_filename`: always returns `ParsedMetadata`; title falls back to the filename stem (strip extension) when parsers fail; specify the deterministic rule for when Anitopy is preferred for bracketed anime filenames (the plan’s current `test_parse_filename_anime_with_group` must be satisfiable without heuristic ambiguity).

3. **Revise the plan to match SSOT and remove remaining decision points**
   - File: `.agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v2.md`
   - Required plan edits:
     - Update the listed public function signatures to match the updated SSOT (including injected client parameters).
     - Specify the exact mocked TMDB JSON payload(s) used in tests (movie + tv examples) and which fields are required.
     - Add the missing negative test case for invalid callback index (matching the SSOT rule).
     - Replace verification commands with canonical gates and keep pass criteria explicit (per `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` “Command Canon”).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-2__metadata-service

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
- Under heading: "### 3.2 Public API" add/change:
  - Update `lookup_tmdb` signature to include `client: httpx.AsyncClient` and state the client is injected (not owned) and MUST NOT be created by services.
  - Update `resolve_metadata` signature to include `client: httpx.AsyncClient` and state the client is injected (not owned) and MUST NOT be created by services.
  - Define behavior for `lookup_tmdb` when `config.api_key is None` (return `None` without a request).
  - Define behavior for invalid API key format (32 hex chars) (raise `TmdbError`).
  - Define behavior for `resolve_metadata` when multiple results and `prompt_callback is None` (select index 0).
  - Define behavior for `resolve_metadata` when `prompt_callback` returns an invalid index (raise `MetadataError` with a stable message substring suitable for tests).
  - Define deterministic `parse_filename` fallback/normalization rules sufficient to satisfy the planned unit tests (stem stripping, and when to prefer Anitopy for bracketed anime filenames).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v1.md
Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
