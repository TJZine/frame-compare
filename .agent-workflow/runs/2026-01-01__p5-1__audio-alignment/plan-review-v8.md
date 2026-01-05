---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v8
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v8.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v8.md
---

# Plan Review Report: Audio Alignment Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v8.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (5.1) + explicit utils progress dependency + import-linter update. |
| 2 | Dependencies | PASS | SSOT-aligned ffprobe/ffmpeg usage; no cross-layer imports required. |
| 3 | File List | PASS | Explicit files + docs updates + import-linter edits listed. |
| 4 | Contract Impact | PASS | Explicit **NO**. |
| 5 | Types Complete | PASS | Public signatures listed and anchored; `validate_spec_anchors.py` passes. |
| 6 | Tests Complete | FAIL | Partial-cache-hit async test is underspecified: it “spies” `_extract_audio` but does not stub return values, so the test would attempt real FFmpeg extraction on dummy files. |
| 7 | Verification Complete | PASS | Commands listed and include `tests/services/` + `tests/utils/`. |
| 8 | Decision-Minimizing | FAIL | Missing explicit `_extract_audio` stubbing in async partial-hit test leaves the Coding Agent to choose a mocking strategy. |
| 9 | Determinism Defined | PASS | Sync vectors, tolerances, and full-cache TOML fixture are explicit. |

## Additional Quality Checks

- Error Codes: OK (no new errors).
- Failure Modes: OK at SSOT level; test enforcement needs one missing detail.
- Derived Outputs: OK (contracts not touched).
- Rollback Guidance: OK.
- SSOT Update Audit (if SSOT changed this loop): N/A

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. How `_extract_audio` is stubbed in `test_align_clips_partial_cache_hit_computes_only_missing_and_preserves_order` to avoid real FFmpeg calls.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Make the partial-cache-hit async test fully offline**
   - Section: Plan → `tests/services/test_alignment.py` → “Async Cache Semantics Tests”
   - Problem: `_extract_audio` is only “spied”, not stubbed; without a stub return value the test will attempt real FFmpeg I/O.
   - Required Change: Specify that `_extract_audio` is patched with a stub (returning deterministic `np.ndarray` values) while also recording call args so the test can assert comp_a is not extracted.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v9.md` (Mechanical Auto-Fix Mode is applicable).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p5-1__audio-alignment

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v8.md
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v8.md
Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v9.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
