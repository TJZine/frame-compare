---
RUN_ID: 2026-01-05__p6-7-4__probe-props-preservation
VERSION: v2
TARGET: Phase 6 → Item 6.7 (Preserve HDR/DoVi Props + tonemap_prop_keys)
INPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
---

# Implementation Plan: Probe Prop Preservation Helpers (tonemap_prop_keys + preserved_frame_props)

## Changes Since plan-v1

- Added tests to lock down SSOT selection boundary (preserved props must come only from tonemap-related keys).
- Added tests + acceptance criteria to lock down preserved-props output determinism (sorted original-key order).
- Expanded DolbyVisionRPU test to include normalized variants and assert original-key preservation.

## Context
**Phase:** 6
**Module:** `frame_compare.orchestration`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
**Dependencies:**
- `ClipProbeSnapshot` carries `preserved_frame_props` and `tonemap_prop_keys` in `src/frame_compare/orchestration/context.py`

## Scope
This plan covers:
- [ ] Implement deterministic helper functions for tonemap-related prop key selection + TOML-safe prop extraction
- [ ] Add unit tests that lock down selection rules, normalization rules, ordering, and Dolby Vision RPU sentinel handling

This plan does NOT cover:
- Probing real frame props via VapourSynth (no VS dependency in unit tests)
- Writing these props into `clip_probe.toml` (covered by probe-cache I/O slice)
- Downstream re-injection of props into clips or overlays (render/orchestration later)

## Contract Impact
**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "3.5 Runtime Context Types (SSOT)"
  - Section: "3.5.2 Tonemap Prop Key Selection Helpers (SSOT)"
  - Section: "3.5.3 Preserved Frame Props Extraction Helpers (SSOT)"

## Files to Create/Modify

### 1. `src/frame_compare/orchestration/probe_props.py` (CREATE)
**Purpose:** Pure, deterministic helpers for selecting tonemap-related prop keys and extracting TOML-safe preserved props.

**Functions to implement (spec-anchored):**
- `normalize_probe_prop_key(key: str) -> str`
- `compute_tonemap_prop_keys(frame_props: Mapping[str, object]) -> tuple[str, ...]`
- `compute_preserved_frame_props(frame_props: Mapping[str, object]) -> dict[str, str | int | float]`

### 2. `tests/orchestration/test_probe_props.py` (CREATE)
**Purpose:** Unit tests for probe prop selection and preservation helpers.

**Tests required:**
- `test_normalize_probe_prop_key_strips_leading_underscores_and_lowercases`
- `test_compute_tonemap_prop_keys_selects_expected_keys_and_is_sorted_deterministically`
  - Include keys that match exact base names and prefix rules; assert returned tuple order matches `(normalized, key)` sorting.
- `test_compute_preserved_frame_props_includes_only_tonemap_related_keys`
  - Include at least one TOML-safe non-tonemap key (e.g. `"UnrelatedKey": 1`) and at least one selected tonemap key; assert non-tonemap key is excluded.
- `test_compute_preserved_frame_props_returns_keys_in_sorted_original_key_order`
  - Provide selected keys in an unsorted input order; assert `list(result.keys()) == sorted(expected_keys)`.
- `test_compute_preserved_frame_props_drops_non_toml_safe_values`
  - Include values of types not in `str|int|float` (e.g., `bytes`, `object()`, `dict`) and assert they are omitted.
- `test_compute_preserved_frame_props_persists_dolbyvisionrpu_as_presence_indicator`
  - Provide a DolbyVisionRPU key in both exact and normalized-variant forms (e.g., `"DolbyVisionRPU"` and `"_DolbyVisionRPU"`), with a non-primitive value, and assert:
    - the presence-indicator key uses the original key present in the mapping,
    - the persisted value is `1`.

### 3. `src/frame_compare/orchestration/__init__.py` (MODIFY)
**Purpose:** Export these helpers to keep import sites stable for later LoadSources/probing implementation.

**Exports to add:**
- `normalize_probe_prop_key`
- `compute_tonemap_prop_keys`
- `compute_preserved_frame_props`

## Acceptance Criteria

- [ ] GIVEN a prop key WHEN normalizing THEN it strips leading underscores and lowercases
- [ ] GIVEN a frame-props mapping WHEN selecting tonemap prop keys THEN it includes all keys matching SSOT selection rules and returns a deterministically sorted tuple
- [ ] GIVEN a frame-props mapping WHEN extracting preserved props THEN it includes only keys selected by `compute_tonemap_prop_keys(...)` (plus DolbyVisionRPU presence-indicator behavior)
- [ ] GIVEN preserved props are returned THEN the dict is populated in lexicographically sorted original-key order
- [ ] GIVEN non-TOML-safe values WHEN extracting preserved props THEN those keys are omitted (except DolbyVisionRPU sentinel)
- [ ] GIVEN a DolbyVisionRPU blob-like value WHEN extracting preserved props THEN output contains the original key with value `1` (presence only)

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → **Command Canon**.

```bash
.venv/bin/pyright --warnings src/frame_compare/orchestration/probe_props.py tests/orchestration/test_probe_props.py
.venv/bin/ruff check src/frame_compare/orchestration/probe_props.py tests/orchestration/test_probe_props.py
.venv/bin/pytest -q tests/orchestration/test_probe_props.py
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Keep helpers pure: no filesystem, no VapourSynth imports.
- Treat ordering as part of the contract: sorting is required for deterministic caches and stable debug output.
- For DolbyVisionRPU: normalization is for matching only; persist the original key that appeared in the mapping.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-01-05__p6-7-4__probe-props-preservation

## Plan to Review
Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md
