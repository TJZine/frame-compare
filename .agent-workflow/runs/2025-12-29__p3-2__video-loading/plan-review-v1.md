---
RUN_ID: 2025-12-29__p3-2__video-loading
VERSION: v1
TARGET: Phase 3 → Item 3.2 Video Loading
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-review-v1.md
---

# Plan Review Report: Video Source Loading

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v1.md

Primary blockers are (1) Spec Anchors are not verbatim headings (likely fails `scripts/validate_spec_anchors.py`), and (2) SSOT gaps leave `load_source()` raise behavior, HDRMetadata extraction, and `apply_trim()` semantics underspecified (Coding Agent would have to decide).

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: Phase 3 → Item 3.2 with explicit out-of-scope list. |
| 2 | Dependencies | PASS | Phase 3.1 artifacts referenced; VS core + lsmas plugin path identified. |
| 3 | File List | PASS | Files enumerated explicitly (no “and related files”). |
| 4 | Contract Impact | PASS | Explicit NO + includes freshness gates (check-only). |
| 5 | Types Complete | FAIL | Spec Anchors are not verbatim headings; coverage is not mechanically checkable. |
| 6 | Tests Complete | FAIL | HDRMetadata extraction + `apply_trim(end=...)` semantics are not specified in SSOT, so required assertions can’t be fixed deterministically. |
| 7 | Verification Complete | PASS | Commands + explicit “exit 0, no warnings” pass criteria provided. |
| 8 | Decision-Minimizing | FAIL | Multiple unresolved decisions (HDR metadata mapping, trim inclusive/exclusive, PluginNotFoundError propagation, extension handling). |
| 9 | Determinism Defined | FAIL | Deterministic rules for trim indexing + HDRMetadata fields/defaults not defined. |

## Additional Quality Checks

- Error Codes: Issue — plan conflicts on whether missing `lsmas` becomes `PluginNotFoundError (FC-2003)` or is wrapped into `SourceLoadError (FC-4015)`.
- Failure Modes: Issue — `load_source()` error propagation is inconsistent across docstring / acceptance criteria / tests.
- Derived Outputs: OK — contract-view/traceability check-only commands included.
- Rollback Guidance: OK — explicit STOP rule present, but must be applied to the SSOT gaps identified below.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. `load_source()` raises: whether `PluginNotFoundError` propagates or is wrapped (and exact wrapping rules).
2. HDRMetadata extraction: which `frame_props` keys map to `HDRMetadata` fields, parsing rules, and defaults when keys are missing/wrong type.
3. `apply_trim()` semantics: whether `end` is inclusive/exclusive, and how `end=None` is implemented.
4. “Support formats” scope: whether extensions are whitelisted/rejected vs “LWLibavSource accepts what it can”.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT: define `load_source()` raise contract**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
   - Heading: `### 3.2 Source Loading`
   - Problem: Spec currently lists only `SourceLoadError`; plan/tests expect `PluginNotFoundError` for missing `lsmas`.
   - Required Change: Update the `Raises:` contract to explicitly include `PluginNotFoundError` (and clarify whether it propagates or is wrapped).

2. **Update SSOT: define HDRMetadata extraction mapping + defaults**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
   - Heading: `### 5.1 HDR Detection`
   - Problem: Spec mentions some prop keys but does not define a deterministic mapping to `HDRMetadata` fields or behavior when props are missing.
   - Required Change: Specify the exact `frame_props` keys used for each `HDRMetadata` field, expected types/coercions, and required defaulting/None behavior.

3. **Update SSOT: define `apply_trim()` indexing semantics**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
   - Heading: `### 3.2 Source Loading`
   - Problem: Inclusive/exclusive semantics for `end` are undefined; `end=None` behavior is undefined.
   - Required Change: Specify whether `end` is inclusive/exclusive, and the exact rule for `end=None` (including whether it computes `last = num_frames - 1` or calls a VS API default).

4. **Revise plan after SSOT updates**
   - Section: `## Spec Anchors (SSOT)`
   - Problem: Anchors are not verbatim headings (e.g., “Section: 3.2 Source Loading”), and loader changes are not anchored to the `VSLoader` section.
   - Required Change: Replace with exact heading lines (verbatim) and add missing anchors, including `### 1.3 VSLoader Protocol` and the correct errors-module headings for `FC-2003` and `FC-4015`.

5. **Revise plan tests/acceptance criteria to match updated SSOT**
   - Sections: `tests/vs/test_source.py`, `tests/vs/test_loader.py`, `## Acceptance Criteria`
   - Problem: Test expectations conflict with the docstring and leave HDRMetadata/trim behavior untestable.
   - Required Change: Add/adjust test assertions to cover the SSOT-defined HDRMetadata fields + `apply_trim()` semantics, and explicitly assert error `.code` values where relevant.

## Ready for Implementation

Return to Planning Agent for SSOT updates + plan revision. Next version: `plan-v2.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-2__video-loading

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md

- Under heading: "### 3.2 Source Loading" add/change:
  - In `load_source(...)->SourceInfo` docstring `Raises:`, explicitly list the full raise contract (must resolve whether missing `lsmas` is `PluginNotFoundError` and whether it propagates or is wrapped).
  - Define `apply_trim(source: SourceInfo, start: int, end: int | None = None) -> vs.VideoNode` semantics: whether `end` is inclusive/exclusive and the exact `end=None` behavior.

- Under heading: "### 5.1 HDR Detection" add/change:
  - Define the deterministic mapping from `frame_props` keys to `HDRMetadata` fields (including required defaults/None behavior and type coercions).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-review-v1.md
Read file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v1.md
Write file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
