---
RUN_ID: 2026-01-04__p6-7-3__probe-cache-io
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Probe Snapshot Cache I/O)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v1.md
---

# Plan Review Report: Probe Snapshot Cache (`clip_probe.toml`) Load/Save

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; clear out-of-scope list. |
| 2 | Dependencies | PASS | Depends on `ClipProbeSnapshot`/`ClipFingerprint` and `compute_probe_cache_key`; both are clearly identified. |
| 3 | File List | PASS | Minimal and explicit (`probe_cache.py` + test file). |
| 4 | Contract Impact | PASS | No canonical contracts touched. |
| 5 | Types Complete | PASS | Public function signatures are one-line, backticked, and SSOT-anchored. |
| 6 | Tests Complete | FAIL | Missing required negative cases from SSOT §3.5.1 (parse/version mismatch, invalid entry skipping, HDR invariant). |
| 7 | Verification Complete | PASS | File-scoped pyright/ruff/pytest commands with explicit pass criteria. |
| 8 | Decision-Minimizing | PASS | Behavior is SSOT-anchored; test gaps are the only blockers. |
| 9 | Determinism Defined | PASS | Stable TOML ordering and FPS persistence rules are specified. |

## Additional Quality Checks

- Error Codes: OK (no new errors).
- Failure Modes: Issue — SSOT requires warn-only empty mapping on parse/version errors and skipping invalid entries; plan lacks tests to lock this down.
- Derived Outputs: OK (no derived views in-scope).
- Rollback Guidance: OK (SSOT-anchored; do not invent behavior).
- SSOT Update Audit (if SSOT changed this loop): N/A

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Without explicit tests for SSOT-mandated failure modes, the Coding Agent could implement incorrect behavior (raise vs warn-only empty mapping; fail to skip invalid entries; fail HDR invariant), causing churn in verification/review.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Add SSOT-mandated negative tests for loader behavior**
   - Section: `tests/orchestration/test_probe_cache.py` → “Tests required”
   - Problem: SSOT §3.5.1 requires missing/parse/version errors return `{}` (warn-only) and invalid entries are ignored; plan only tests a happy-path round-trip and prop sanitation.
   - Required Change: Add the following test cases (names + assertions):
     - `test_load_clip_probe_cache_returns_empty_dict_on_missing_file`
       - Assert `{}` and no exception.
     - `test_load_clip_probe_cache_returns_empty_dict_on_parse_error`
       - Write invalid TOML bytes; assert `{}` and no exception.
     - `test_load_clip_probe_cache_returns_empty_dict_on_version_mismatch`
       - Write `version = "2"` (or missing); assert `{}` and no exception.
     - `test_load_clip_probe_cache_ignores_unknown_fields_and_skips_invalid_entries`
       - Include one entry with an extra unknown field (should still load) and one entry missing a required field (should be skipped); assert only the valid entry is returned.

2. **Add SSOT-mandated test for HDR invariant on save**
   - Section: `tests/orchestration/test_probe_cache.py` → “Tests required”
   - Problem: SSOT §3.5.1 requires `save_clip_probe_cache(...)` to raise `ValueError` if `snapshot.is_hdr` is True but `snapshot.hdr_metadata` is None.
   - Required Change: Add `test_save_clip_probe_cache_raises_when_is_hdr_true_but_hdr_metadata_missing` asserting `ValueError`.

3. **Strengthen round-trip test to cover schema fields that this slice owns**
   - Section: `test_probe_cache_round_trip_toml`
   - Problem: SSOT cache format includes `tonemap_prop_keys`, `preserved_frame_props`, and conditional `hdr_metadata`; the plan’s round-trip assertions currently omit these, leaving ambiguity in implementation.
   - Required Change: Expand assertions to include:
     - `tonemap_prop_keys` preserved (order preserved) for a non-HDR snapshot.
     - `hdr_metadata` round-trips for an HDR snapshot (`is_hdr=True` and non-None metadata).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-7-3__probe-cache-io

## Revision Required
Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v1.md
Write file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
