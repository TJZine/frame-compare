---
RUN_ID: 2025-12-29__p2-2__metrics-calculation
VERSION: v1
TARGET: Phase 2 → Item 2.2 Metrics Calculation
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v1.md
---

# Plan Review Report: Metrics Calculation

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v1.md

The plan passes the mechanical Spec Anchors gate (`scripts/validate_spec_anchors.py`), but it is not implementation-ready because SSOT does not specify key deterministic details required to compute luminance/motion from VapourSynth frames (plane access + bit-depth normalization + format handling), and the plan contradicts itself on scope (`__init__.py` exports). Tests also omit the promised “empty clip” edge case and do not cover error behavior.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | FAIL | Plan says module integration/exports are out-of-scope, but includes `src/frame_compare/analysis/__init__.py` export changes. |
| 2 | Dependencies | FAIL | Required runtime/typing dependencies for metrics extraction are underspecified (numpy/plane access API; error classes used on failure). |
| 3 | File List | PASS | File list is explicit and bounded. |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | PASS | Planned signatures are listed and SSOT-anchored; `validate_spec_anchors.py` passes. |
| 6 | Tests Complete | FAIL | Edge cases promised in scope aren’t fully enumerated (missing “empty clip” test); failure-mode tests are missing. |
| 7 | Verification Complete | PASS | Commands + explicit “exit 0” pass criteria provided; includes plan anchor validation. |
| 8 | Decision-Minimizing | FAIL | Coding Agent must decide plane extraction API, normalization rules, format conversion/unsupported handling, and which video in `video_paths` is analyzed. |
| 9 | Determinism Defined | FAIL | Normalization is “255 (or max bit depth)” and motion normalization is “for 8-bit” without a deterministic SSOT rule. |

## Additional Quality Checks

- Error Codes: Issue — SSOT indicates `MetricsCalculationError (FC-4002)` is used by analysis, but plan doesn’t specify when/what is raised or test it.
- Failure Modes: Issue — missing/invalid inputs, empty clips, and frame access errors are not specified.
- Derived Outputs: OK — no contract-derived outputs required.
- Rollback Guidance: Issue — plan lacks an explicit STOP/rollback rule when SSOT gaps are hit.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. How to access pixel/plane data from `vs.VideoFrame` deterministically for luminance/motion.
2. How to normalize for bit depth and/or float formats.
3. What to do when the clip is not YUV / has unexpected format.
4. Whether `calculate_metrics(video_paths, ...)` analyzes only `video_paths[0]` (reference) or combines multiple clips.
5. Which exception type/code is raised for empty clips and frame-access failures.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT spec first: define deterministic frame-plane extraction + normalization**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
   - Under heading: `### 4.1 Luminance Calculation` add/change:
     - Specify the exact API used to read luma samples (e.g., `frame.get_read_array(0)` with `np.asarray(...)`).
     - Specify normalization factor deterministically (e.g., `max_value = (1 << clip.format.bits_per_sample) - 1` for integer formats; `max_value = 1.0` for float formats).
     - Specify format handling rules (supported/unsupported; if conversion is required, name the exact conversion call and target format).
   - Under heading: `### 4.2 Motion Scoring` add/change:
     - Specify the exact per-frame data used (same luma plane extraction as luminance).
     - Specify output length (`len(motion) == clip.num_frames`) and `motion[0] == 0.0`.
     - Specify deterministic normalization for motion (per-pixel max_value and plane size).

2. **Update SSOT spec first: remove ambiguity in `calculate_metrics` clip selection + metadata/caching invariants**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
   - Under heading: `### 3.1 calculate_metrics` add/change:
     - Specify which clip(s) are analyzed when `video_paths` contains multiple paths (e.g., analyze reference only: `video_paths[0]`).
     - Specify how `MetricsMetadata` is populated (fps source, frame_count, clips list contents).
     - Specify that `MetricsMetadata.config_fingerprint` equals the cache fingerprint passed to `load_cached_metrics` and persisted by `save_metrics_cache`.
     - Specify failure behavior and error class for analysis failures (tie to `MetricsCalculationError (FC-4002)` vs other errors).

3. **Revise plan-v2 after SSOT updates (plan-only)**
   - Section: `## Scope`
     - Resolve the `__init__.py` contradiction: either remove export changes from this slice or remove “out-of-scope: module integration/exports”.
   - Section: `## Spec Anchors (SSOT)`
     - Add anchors for the error handling requirements you expect to implement/test (e.g., `## 6. Error Handling` in analysis-module and the relevant error-class section in `errors-module.md`) if errors are part of acceptance.
   - Section: `tests/analysis/test_metrics.py`
     - Add explicit edge-case test names for “empty clip” (and specify expected behavior per updated SSOT).
     - Add at least one deterministic failure-mode test that asserts `MetricsCalculationError.code == "FC-4002"` for a defined failure mode.
   - Add a STOP rule mirroring the workflow (if SSOT is missing a detail, stop and return to Planning).

## Ready for Implementation

Return to Planning Agent for SSOT updates + plan revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-2__metrics-calculation

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md

- Under heading: "### 3.1 calculate_metrics" add/change:
  - Specify whether metrics are computed for `video_paths[0]` only (reference) or for multiple clips, and how that maps to returning a single `FrameMetrics`.
  - Specify how `MetricsMetadata` is populated (fps source, frame_count, clips list contents).
  - Specify the cache invariant: `MetricsMetadata.config_fingerprint` equals the fingerprint passed to `load_cached_metrics` and written as `fingerprint` in cache.
  - Specify failure behavior: which error class is raised for analysis failures (tie to `MetricsCalculationError (FC-4002)` or update the Raises contract accordingly).

- Under heading: "### 4.1 Luminance Calculation" add/change:
  - Specify the exact per-frame luma sample extraction API (e.g., `frame.get_read_array(0)` + `np.asarray(...)`), including any required format conversion and the exact conversion call/target format if needed.
  - Specify deterministic normalization rules across bit depths / float formats (no “255 or …” ambiguity).

- Under heading: "### 4.2 Motion Scoring" add/change:
  - Specify the exact motion computation (arrays used, `motion[0] == 0.0`, output length, deterministic normalization).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-review-v1.md
Read file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v1.md
Write file: .agent-workflow/runs/2025-12-29__p2-2__metrics-calculation/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
