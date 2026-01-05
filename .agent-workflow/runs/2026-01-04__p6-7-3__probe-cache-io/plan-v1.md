---
RUN_ID: 2026-01-04__p6-7-3__probe-cache-io
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Probe Snapshot Cache I/O)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v1.md
---

# Implementation Plan: Probe Snapshot Cache (`clip_probe.toml`) Load/Save

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
- [ ] Extend unit tests to cover TOML round-trip and TOML-safe prop sanitation

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
  - Behavior per SSOT: missing file → `{}`, parse/version errors → `{}` with warning, ignore unknown fields/invalid entries.
- `save_clip_probe_cache(cache_path: Path, entries_by_key: Mapping[str, ClipProbeSnapshot]) -> None`
  - Behavior per SSOT: overwrite file, stable ordering, sanitize `preserved_frame_props` to `str|int|float` only (drop others), enforce HDR metadata invariant.

**Determinism requirements (spec-anchored):**
- Stable TOML output ordering: `version` first, then sorted entry keys, stable per-entry field order.
- `fps` persisted as `fps_num` / `fps_den` ints.

### 2. `tests/orchestration/test_probe_cache.py` (MODIFY)
**Purpose:** Validate TOML round-trip and persistence boundary sanitation without requiring external tools.

**Tests required (spec-anchored; master checklist Phase 6.7):**
- `test_probe_cache_round_trip_toml`
  - Write a cache with at least one entry via `save_clip_probe_cache`, then load via `load_clip_probe_cache`, and assert key presence and critical fields equality (fingerprint, width/height/num_frames, fps, is_hdr).
- `test_preserved_frame_props_are_toml_safe_primitives_only`
  - Provide `preserved_frame_props` containing TOML-safe and unsafe values; after save+load, assert only `str|int|float` values remain (unsafe keys dropped).

## Acceptance Criteria

- [ ] GIVEN a missing `clip_probe.toml` WHEN calling `load_clip_probe_cache` THEN it returns `{}` without raising
- [ ] GIVEN a valid cache file WHEN saving then loading THEN the loaded snapshot(s) match the saved canonical fields
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
- Follow SSOT for warn-only cache failures (parse/version mismatch → empty mapping).
- Use `tomli_w` (already used in repo) and build dicts in deterministic insertion order to guarantee stable output.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-7-3__probe-cache-io

## Plan to Review
Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v1.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v1.md
