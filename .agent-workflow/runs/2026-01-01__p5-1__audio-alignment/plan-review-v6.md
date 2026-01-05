---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v6
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v6.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v6.md
---

# Plan Review Report: Audio Alignment Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v6.md

Notes:
- `scripts/validate_spec_anchors.py` passes for `plan-v6.md`.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (5.1) + explicit utils progress dependency. |
| 2 | Dependencies | PASS | External deps explicit (ffmpeg/ffprobe); layering stays within services/utils/errors. |
| 3 | File List | PASS | Files + docs + import-linter updates are fully enumerated. |
| 4 | Contract Impact | PASS | Explicit **NO**. |
| 5 | Types Complete | PASS | Public signatures listed and SSOT-anchored; no TBDs. |
| 6 | Tests Complete | FAIL | `align_clips` cache semantics and output ordering are in SSOT and acceptance criteria, but missing explicit tests (full-hit skips ffprobe + partial-hit computes only missing + preserves order). |
| 7 | Verification Complete | PASS | Commands are explicit and include `tests/services/` and `tests/utils/`. |
| 8 | Decision-Minimizing | FAIL | Without the missing async tests, the Coding Agent must decide how to validate cache semantics/order. |
| 9 | Determinism Defined | PASS | Deterministic vectors + tolerances are explicit for correlation and cache I/O. |

## Additional Quality Checks

- Error Codes: OK (no new errors).
- Failure Modes: OK for ffprobe/ffmpeg missing/fail, empty audio, zero-norm, cache corruption/version mismatch.
- Derived Outputs: OK (contracts not touched).
- Rollback Guidance: OK.
- SSOT Update Audit (this run): OK
  - New SSOT behavior for `align_clips` (ordering + full/partial/miss cache semantics) is clear, implementable, and performance-aligned (full hit skips external tooling).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. How to validate `align_clips` full-cache-hit behavior (must skip both ffprobe and ffmpeg).
2. How to validate `align_clips` partial-cache-hit behavior (must compute only missing comparisons and preserve input ordering).

## Concrete Edits Required (plan-v7)

1. **Add explicit async tests for `align_clips` cache semantics and ordering**
   - Section: Plan → `tests/services/test_alignment.py`
   - Problem: `align_clips` cache behavior and ordering are specified in SSOT but not covered by tests.
   - Required Change: Add these exact tests (names + assertions):
     - `test_align_clips_full_cache_hit_skips_probe_and_extract` (async; `@pytest.mark.anyio`)
       - Setup: `reference = tmp_path / "ref.mkv"`, `comparisons = [tmp_path / "comp_a.mkv", tmp_path / "comp_b.mkv"]`
       - Write `{cache_dir}/audio_offsets.toml` with **both** keys: `"ref:comp_a"` and `"ref:comp_b"` using distinct `frame_offset` values.
       - Patch/spy `_probe_fps` and `_extract_audio` to fail if called (or assert call count is zero).
       - Assert: returned list length equals `len(comparisons)` and `result[i].comparison_clip` corresponds to `comparisons[i].name` (ordering), with offsets matching cached values.
     - `test_align_clips_partial_cache_hit_computes_only_missing_and_preserves_order` (async; `@pytest.mark.anyio`)
       - Setup: same paths, but cache file contains **only** `"ref:comp_a"`.
       - Patch `_probe_fps` to return `Fraction(24, 1)`.
       - Patch `_extract_audio` so it is called for `reference` and `comp_b` but **not** for cached `comp_a` (assert via spy call args).
       - Patch `_cross_correlate` / `_samples_to_frames` (or patch a single internal helper if you define one) so the computed result for `comp_b` is deterministic.
       - Assert: result list is `[cached(comp_a), computed(comp_b)]` in that exact order and `len(result) == len(comparisons)`.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v7.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p5-1__audio-alignment

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v6.md
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v6.md
Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v7.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
