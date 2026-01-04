---
RUN_ID: 2026-01-04__p6-7-2__probe-cache-key
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Probe Snapshot Cache Keying)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/plan-v1.md
---

# Implementation Plan: Probe Snapshot Cache Key (`compute_probe_cache_key`)

## Context
**Phase:** 6
**Module:** `frame_compare.orchestration`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
**Dependencies:**
- `ClipFingerprint` type from `src/frame_compare/orchestration/context.py`

## Scope
This plan covers:
- [ ] Implement `compute_probe_cache_key(fingerprint: ClipFingerprint) -> str` per SSOT (stable JSON + blake2s)
- [ ] Add unit tests for key stability and invalidation (fingerprint change → different key)

This plan does NOT cover:
- `clip_probe.toml` read/write format, schema, or versioning (separate Phase 6.7 slice)
- Probe snapshot extraction from real media / VapourSynth / FFprobe (integration work)

## Contract Impact
**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "3.5 Runtime Context Types (SSOT)"
  - Section: "7. Testing Strategy"
  - Section: "7.1 Unit Tests"

## Files to Create/Modify

### 1. `src/frame_compare/orchestration/probe_cache.py` (CREATE)
**Purpose:** Host probe-cache utilities that are deterministic and unit-testable.

**Functions to implement (spec-anchored):**
- `compute_probe_cache_key(fingerprint: ClipFingerprint) -> str`
  - Build `payload = {"path": str(fingerprint.path), "size_bytes": ..., "mtime_ns": ..., "schema_version": 1}`
  - Serialize using `json.dumps(payload, sort_keys=True, separators=(",", ":"))`
  - Return `hashlib.blake2s(serialized.encode("utf-8")).hexdigest()`

### 2. `tests/orchestration/test_probe_cache.py` (CREATE)
**Purpose:** Unit tests for probe-cache key determinism.

**Tests required (spec-anchored, orchestration spec §7.1 + master checklist §6.7):**
- `test_compute_probe_cache_key_stable_for_same_fingerprint`
  - Same `ClipFingerprint` inputs → identical key string (across repeated calls)
- `test_probe_cache_invalidates_on_fingerprint_change`
  - Change any one fingerprint field (`path` or `size_bytes` or `mtime_ns`) → key differs

### 3. `src/frame_compare/orchestration/__init__.py` (MODIFY)
**Purpose:** Export probe-cache key function as part of orchestration public API (optional but keeps imports stable).

**Export to add:**
- `compute_probe_cache_key`

## Acceptance Criteria

- [ ] GIVEN the same `ClipFingerprint` WHEN calling `compute_probe_cache_key(...)` repeatedly THEN it returns the same hex digest string
- [ ] GIVEN a changed `ClipFingerprint` WHEN any fingerprint field changes THEN `compute_probe_cache_key(...)` returns a different string
- [ ] GIVEN unit tests run THEN `tests/orchestration/test_probe_cache.py` passes without filesystem or external tooling

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → **Command Canon**.

```bash
.venv/bin/pyright --warnings src/frame_compare/orchestration/probe_cache.py tests/orchestration/test_probe_cache.py
.venv/bin/ruff check src/frame_compare/orchestration/probe_cache.py tests/orchestration/test_probe_cache.py
.venv/bin/pytest -q tests/orchestration/test_probe_cache.py
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Keep keying independent of trim state (SSOT: fingerprint-only keying).
- Do not include any non-deterministic fields (timestamps, random seeds) in the payload.
- Ensure JSON serialization uses the exact SSOT settings (`sort_keys=True`, `separators=(",", ":")`).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-7-2__probe-cache-key

## Plan to Review
Read file: .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/plan-v1.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/plan-review-v1.md
