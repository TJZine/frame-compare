---
RUN_ID: 2026-01-05__p6-7-4__probe-props-preservation
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Preserve HDR/DoVi Props + tonemap_prop_keys)
INPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v1.md
---

# Plan Review Report: Probe Prop Preservation Helpers (tonemap_prop_keys + preserved_frame_props)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-05
**Plan Reference:** .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; clear out-of-scope items (no VS probing, no cache I/O, no downstream re-injection). |
| 2 | Dependencies | PASS | Depends only on Mapping inputs and the existence of `ClipProbeSnapshot` fields; no new module dependencies introduced. |
| 3 | File List | PASS | Minimal and explicit (`probe_props.py`, test file, `__init__.py` export). |
| 4 | Contract Impact | PASS | No canonical contracts touched. |
| 5 | Types Complete | PASS | All planned public signatures are listed as one-line backticked bullets and anchored to SSOT. |
| 6 | Tests Complete | FAIL | Missing tests to lock down SSOT-required selection boundary and preserved-props output determinism. |
| 7 | Verification Complete | PASS | File-scoped pyright/ruff/pytest commands with explicit pass criteria. |
| 8 | Decision-Minimizing | FAIL | Without the missing tests/acceptance bullets, Coding Agent must decide whether non-tonemap TOML-safe keys are excluded and whether preserved-props dict ordering is required. |
| 9 | Determinism Defined | FAIL | SSOT requires `compute_preserved_frame_props` to return a dict populated in sorted original-key order; plan doesn’t specify or test this. |

## Additional Quality Checks

- Error Codes: OK (no new errors).
- Failure Modes: OK (pure helpers, no I/O); missing determinism requirements for preserved-props output order.
- Derived Outputs: OK (no generated views in-scope).
- Rollback Guidance: OK (SSOT is anchored; do not invent behavior).
- SSOT Update Audit (if SSOT changed this loop): N/A

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether `compute_preserved_frame_props` includes only keys from `compute_tonemap_prop_keys` (SSOT says it must) vs “all TOML-safe keys”.
2. Whether `compute_preserved_frame_props` output dict must be populated in sorted original-key order (SSOT says it must).
3. Which original key is used for the DolbyVisionRPU presence indicator when the input key varies by casing/leading underscores.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Add test: preserved props only come from tonemap keys**
   - Section: `tests/orchestration/test_probe_props.py` → “Tests required”
   - Problem: SSOT §3.5.3 requires selection starting from `compute_tonemap_prop_keys(frame_props)`; plan does not test that non-tonemap TOML-safe keys are excluded.
   - Required Change: Add `test_compute_preserved_frame_props_includes_only_tonemap_related_keys`:
     - Input includes at least one TOML-safe, non-tonemap key (e.g., `"UnrelatedKey": 1`) and at least one tonemap key.
     - Assert `"UnrelatedKey"` is not present in output.

2. **Add test: preserved props output dict insertion order is deterministic**
   - Section: `tests/orchestration/test_probe_props.py` → “Tests required”
   - Problem: SSOT §3.5.3 requires returning a dict populated in sorted original-key order; plan doesn’t specify or test ordering.
   - Required Change: Add `test_compute_preserved_frame_props_returns_keys_in_sorted_original_key_order`:
     - Provide two+ selected tonemap keys in an unsorted input order.
     - Assert `list(result.keys()) == sorted(expected_keys)`.

3. **Clarify and test DolbyVisionRPU key handling for normalization**
   - Section: `tests/orchestration/test_probe_props.py` → `test_compute_preserved_frame_props_persists_dolbyvisionrpu_as_presence_indicator`
   - Problem: SSOT triggers on “any key normalizes to dolbyvisionrpu”; current plan only tests the exact key spelling.
   - Required Change: Expand the test to include a variant key (e.g. `"_DolbyVisionRPU"` or `"__DolbyVisionRPU"`) and assert the persisted presence indicator uses the *original* key that was present in the mapping (value `1`).

4. **Add acceptance criteria bullet for preserved-props ordering**
   - Section: `## Acceptance Criteria`
   - Problem: Ordering is an explicit SSOT requirement for deterministic caches; acceptance criteria do not mention it.
   - Required Change: Add a bullet asserting preserved-props dict keys are lexicographically sorted by original key.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-05__p6-7-4__probe-props-preservation

## Revision Required
Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v1.md
Write file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
