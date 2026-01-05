---
RUN_ID: 2025-12-29__p2-3__frame-selection
VERSION: v2
TARGET: Phase 2 → Item 2.3
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v2.md
---

# Plan Review Report: Frame Selection Algorithms

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Selection-only slice; VS-dependent work is explicitly deferred. |
| 2 | Dependencies | PASS | Pure Python selection over `FrameMetrics`; correct import of `SelectionError`. |
| 3 | File List | PASS | Includes code/tests + docs; `analysis/__init__.py` additive diff is specified. |
| 4 | Contract Impact | PASS | Declares **NO**; OK. |
| 5 | Types Complete | FAIL | Public function signatures are listed, but test fixtures lack SSOT-aligned construction for `FrameMetrics` / `MetricsMetadata` and `AnalysisConfig` field names. |
| 6 | Tests Complete | FAIL | Several tests remain non-mechanical or inconsistent with SSOT (min-gap scope, dedup/insufficient-candidates fixtures not fully specified). |
| 7 | Verification Complete | PASS | Commands + pass criteria are explicit. |
| 8 | Decision-Minimizing | FAIL | Coding Agent must decide how to build `FrameMetrics`/`AnalysisConfig` in tests and how to scope MIN_GAP assertions. |
| 9 | Determinism Defined | FAIL | Random-mode “different seed → different results” is not guaranteed; min-gap test as written would contradict QUANTILE adjacency unless scoped. |

## Additional Quality Checks

- Error Codes: OK — `SelectionError` exists and has the required `reason/requested/found` constructor.
- Failure Modes: Issue — plan must specify what constitutes “empty metrics” (len(luminance)==0, len(motion)==0, and/or metadata.frame_count==0) and align tests to that rule.
- Derived Outputs: OK — `save_frames_data` explicitly deferred and SSOT now notes this.
- Rollback Guidance: OK — STOP guidance present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. How to construct minimal valid `FrameMetrics` (requires `MetricsMetadata` + `ClipIdentity` + `Fraction`) for every test case.
2. How to construct `AnalysisConfig` for tests (field name is `selection_mode`, not `mode`; other required defaults must be explicit).
3. Scope of the MIN_GAP invariant (SSOT requires min-gap for motion/random picks; quantile picks may be adjacent).
4. Random-mode “different seed” test determinism (must avoid probabilistic inequality assertions).

## Concrete Edits Required (plan-v3; plan-only)

1. **Add explicit, reusable fixtures for `FrameMetrics` and `AnalysisConfig`**
   - Section: `tests/analysis/test_selection.py`
   - Required Change:
     - Specify a helper (in test file) like `make_metrics(luminance: list[float], motion: list[float]) -> FrameMetrics` with explicit deterministic metadata values:
       - `fps=Fraction(24)`
       - `config_fingerprint="fp"`
       - `clips=[ClipIdentity(path="video.mkv", size=1, mtime=1.0, sha1=None)]`
       - `frame_count` matches `len(luminance)` and `len(motion)`
     - Specify a helper `make_config(*, frame_count: int, selection_mode: SelectionMode, random_seed: int = 42) -> AnalysisConfig` using the real field name `selection_mode` (and allow defaults for other fields).

2. **Make MIN_GAP assertions SSOT-correct (no global min-gap for quantile)**
   - Section: tests table
   - Required Change:
     - Replace `test_select_frames_respects_min_gap` with two explicit tests:
       - `test_motion_selection_respects_min_gap` (mode=MOTION) asserts pairwise gaps in `frames` are `>= MIN_GAP`
       - `test_random_selection_respects_min_gap` (mode=RANDOM) asserts pairwise gaps in `frames` are `>= MIN_GAP`
     - For MIXED mode, either:
       - assert min-gap only for the `breakdown.motion + breakdown.random` picks relative to all selected frames, OR
       - omit MIXED min-gap testing if SSOT doesn’t require it beyond motion/random phases.

3. **Replace probabilistic “different seeds differ” assertion with exact expected outputs**
   - Section: `test_select_frames_random_mode_different_seed_different_results`
   - Required Change:
     - Use deterministic expected frame lists for seed 42 and 123 given `total_frames=100`, `count=10`, `MIN_GAP=5`, and the exact SSOT algorithm (shuffle + greedy). List both expected frame arrays in the plan so the Coding Agent does not compute them ad hoc.

4. **Specify concrete inputs for dedup/insufficient-candidates/empty-metrics tests**
   - Required Change:
     - `test_select_frames_deduplication_skips_already_selected`: define explicit `luminance` and `motion` arrays where motion peaks overlap quantile-selected indices (and list expected final `frames` + breakdown).
     - `test_select_frames_insufficient_candidates_raises`: define exact `luminance`/`motion` arrays length and explain why min-gap/exclude yields `found=<N>`; specify expected `found` value in the assertion.
     - `test_select_frames_empty_metrics_raises`: define whether “empty” means both arrays empty and require `found=0`.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-3__frame-selection

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-review-v2.md
Read file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v2.md
Write file: .agent-workflow/runs/2025-12-29__p2-3__frame-selection/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
