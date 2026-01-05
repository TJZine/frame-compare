---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v7
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v7.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v7.md
---

# Plan Review Report: Audio Alignment Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v7.md

Notes:
- `scripts/validate_spec_anchors.py` passes for `plan-v7.md`.
- Plan-v7 improves coverage by adding async cache tests, but it regresses determinism and “exactness” in file edits and sync test specs compared to plan-v6.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (5.1) + explicit utils progress dependency + import-linter update. |
| 2 | Dependencies | PASS | External deps explicit (ffmpeg/ffprobe); layering aligns with SSOT. |
| 3 | File List | PASS | All files are enumerated (services + utils + tests + docs + import-linter). |
| 4 | Contract Impact | PASS | Explicit **NO**. |
| 5 | Types Complete | PASS | Public signatures listed and SSOT-anchored. |
| 6 | Tests Complete | FAIL | Sync tests are not mechanically specified (vectors + exact assertions); async tests omit the exact cache TOML bodies required for both cached entries. |
| 7 | Verification Complete | PASS | Commands are explicit and run `tests/services/` + `tests/utils/`. |
| 8 | Decision-Minimizing | FAIL | Leaves decisions to Coding Agent: exact file edits for `utils/__init__.py` and exact sync test fixtures/assertions (“same as plan-v6” is not acceptable in an implementation-ready plan). |
| 9 | Determinism Defined | FAIL | Correlation input arrays and cache parsing expected shapes are not fully specified in this plan artifact. |

## Additional Quality Checks

- Error Codes: OK (no new errors).
- Failure Modes: OK at SSOT level; test enforcement is incomplete.
- Derived Outputs: OK (contracts not touched).
- Rollback Guidance: OK.
- SSOT Update Audit (if SSOT changed this loop): N/A (no new SSOT changes in plan-v7).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact deterministic unit test vectors + assertions for the sync test suite (correlation arrays, cache parse expected `AlignmentResult`).
2. Exact cache TOML fixtures for the two-entry “full cache hit” async test (all required fields beyond `frame_offset`).
3. Exact `src/frame_compare/utils/__init__.py` edit (`import` and `__all__` list) required to export progress types.

## Concrete Edits Required (plan-v8)

1. **Restore exact file-edit instructions for `utils/__init__.py`**
   - Section: Plan → `src/frame_compare/utils/__init__.py` [MODIFY]
   - Problem: Plan says “Add imports and __all entries…” but does not specify the exact import block and exact `__all__` list.
   - Required Change: Include the exact code block for the import and exact `__all__` list additions (as in plan-v6).

2. **Make sync tests fully deterministic inside plan-v8**
   - Section: Plan → `tests/services/test_alignment.py`
   - Problem: Plan-v7 references “same as plan-v6” instead of specifying concrete vectors and assertions.
   - Required Change: Inline the deterministic arrays and assertions for `_cross_correlate` tests and the concrete cache fixture + expected parsed `AlignmentResult` dict (as in plan-v6).

3. **Make async cache tests mechanically checkable**
   - Section: Plan → “Async cache semantics tests”
   - Problem: “write cache with BOTH keys … (offset=10/20)” is underspecified; cache entries require multiple fields.
   - Required Change: Include the exact TOML text to write for BOTH entries, including `reference_clip`, `comparison_clip`, `frame_offset`, `time_offset_seconds`, `correlation_score`, `method`, and `version = "1"`.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v8.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p5-1__audio-alignment

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v7.md
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v7.md
Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v8.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
