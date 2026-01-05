---
RUN_ID: 2026-01-04__p6-7-3__probe-cache-io
VERSION: v2
TARGET: Phase 6 → Item 6.7 (Probe Snapshot Cache I/O)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md
---

# Implementation Plan: Probe Snapshot Cache (`clip_probe.toml`) Load/Save

## Changes Since plan-v1

- Added SSOT-mandated negative tests for loader behavior: missing file, parse error, version mismatch, invalid-entry skipping, unknown-field tolerance.
- Added SSOT-mandated negative test for HDR invariant on save (`is_hdr=True` with missing `hdr_metadata` → `ValueError`).
- Strengthened round-trip test to assert `tonemap_prop_keys` preservation and HDR `hdr_metadata` persistence.

## Context
**Phase:** 6
**Module:** `frame_compare.orchestration`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
**Dependencies:**
- Existing `ClipProbeSnapshot` / `ClipFingerprint` in `src/frame_compare/orchestration/context.py`
- Existing `compute_probe_cache_key(fingerprint: ClipFingerprint) -> str` in `src/frame_compare/orchestration/probe_cache.py`

## Scope
This plan covers:
- [ ] Implement deterministic probe-cache I/O helpers: `load_clip_probe_cache()` and `save_clip_probe_cache()`
- [ ] Extend unit tests to lock down SSOT failure modes + deterministic behavior

This plan does NOT cover:
- Implementing the actual “probe” step (extracting width/height/fps/HDR from media) or LoadSources phase wiring
- Preserving HDR/DoVi props from real VapourSynth frames (beyond enforcing TOML-safe primitives at persistence boundary)
- Integration tests (Docker) that write/reuse `generated/clip_probe.toml` during a full run

## Contract Impact
**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "3.5 Runtime Context Types (SSOT)"
  - Section: "3.5.1 Probe Cache I/O Helpers (SSOT)"
  - Section: "7. Testing Strategy"
  - Section: "7.1 Unit Tests"

## Files to Create/Modify

### 1. `src/frame_compare/orchestration/probe_cache.py` (MODIFY)
**Purpose:** Add deterministic `clip_probe.toml` load/save helpers alongside existing keying function.

**Functions to implement (spec-anchored):**
- `load_clip_probe_cache(cache_path: Path) -> dict[str, ClipProbeSnapshot]`
  - Behavior per SSOT: missing file → `{}`, parse/version errors → `{}` with warning, ignore unknown fields, skip invalid entries.
- `save_clip_probe_cache(cache_path: Path, entries_by_key: Mapping[str, ClipProbeSnapshot]) -> None`
  - Behavior per SSOT: overwrite file, stable ordering, sanitize `preserved_frame_props` to `str|int|float` only (drop others), enforce HDR metadata invariant (`is_hdr=True` implies `hdr_metadata is not None`).

**Determinism requirements (spec-anchored):**
- Stable TOML output ordering: `version` first, then sorted entry keys, stable per-entry field order.
- `fps` persisted as `fps_num` / `fps_den` ints.

### 2. `tests/orchestration/test_probe_cache.py` (MODIFY)
**Purpose:** Validate TOML round-trip, persistence boundary sanitation, and SSOT failure modes without requiring external tools.

**Tests required (spec-anchored; orchestration spec §3.5.1 + §7.1):**
- `test_load_clip_probe_cache_returns_empty_dict_on_missing_file`
  - Assert `{}` and no exception.
- `test_load_clip_probe_cache_returns_empty_dict_on_parse_error`
  - Write invalid TOML bytes; assert `{}` and no exception.
- `test_load_clip_probe_cache_returns_empty_dict_on_version_mismatch`
  - Write `version = "2"` (and optionally also “missing version”); assert `{}` and no exception.
- `test_load_clip_probe_cache_ignores_unknown_fields_and_skips_invalid_entries`
  - Include:
    - one valid entry with an extra unknown field (must still load),
    - one invalid entry missing a required field (must be skipped),
    - assert only the valid entry is returned.
- `test_save_clip_probe_cache_raises_when_is_hdr_true_but_hdr_metadata_missing`
  - Assert `ValueError`.
- `test_probe_cache_round_trip_toml`
  - Write a cache via `save_clip_probe_cache`, then load via `load_clip_probe_cache`, and assert:
    - fingerprint fields round-trip,
    - width/height/num_frames round-trip,
    - fps round-trips via `fps_num`/`fps_den`,
    - `tonemap_prop_keys` preserved (order preserved) for a non-HDR snapshot,
    - `hdr_metadata` round-trips for an HDR snapshot (`is_hdr=True` and non-None metadata).
- `test_preserved_frame_props_are_toml_safe_primitives_only`
  - Provide `preserved_frame_props` containing TOML-safe and unsafe values; after save+load, assert only `str|int|float` values remain (unsafe keys dropped).

## Acceptance Criteria

- [ ] GIVEN a missing `clip_probe.toml` WHEN calling `load_clip_probe_cache` THEN it returns `{}` without raising
- [ ] GIVEN invalid TOML WHEN calling `load_clip_probe_cache` THEN it returns `{}` without raising
- [ ] GIVEN version mismatch/missing version WHEN calling `load_clip_probe_cache` THEN it returns `{}` without raising
- [ ] GIVEN an entry missing required fields WHEN loading THEN it is skipped (valid entries still load)
- [ ] GIVEN `is_hdr=True` and `hdr_metadata is None` WHEN saving THEN `save_clip_probe_cache` raises `ValueError`
- [ ] GIVEN a valid cache file WHEN saving then loading THEN `tonemap_prop_keys` and conditional `hdr_metadata` round-trip correctly
- [ ] GIVEN `preserved_frame_props` contains non-primitive values WHEN saving THEN those keys are dropped and do not reappear after load
- [ ] GIVEN entries are written THEN file output is deterministic with sorted entry keys (stable across runs)

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → **Command Canon**.

```bash
.venv/bin/pyright --warnings src/frame_compare/orchestration/probe_cache.py tests/orchestration/test_probe_cache.py
.venv/bin/ruff check src/frame_compare/orchestration/probe_cache.py tests/orchestration/test_probe_cache.py
.venv/bin/pytest -q tests/orchestration/test_probe_cache.py
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Keep this slice unit-test-only; do not invoke VapourSynth/FFprobe/FFmpeg.
- Follow SSOT for warn-only cache failures (parse/version mismatch → empty mapping; invalid entries skipped).
- Use `tomli_w` (already used in repo) and build dicts in deterministic insertion order to guarantee stable output.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-7-3__probe-cache-io

## Plan to Review
Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v2.md
