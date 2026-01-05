---
RUN_ID: 2025-12-29__p2-4__cache-io
VERSION: v4
TARGET: Phase 2 → Item 2.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v3.md
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v4.md
---

# Implementation Plan: Cache I/O Module

## Changes Since plan-v3

- **SSOT updated**: Added clips semantics, failure mapping, v2 cache JSON schema, fps serialization to `analysis-module.md`
- **Added schema validation tests**: `test_save_writes_required_keys`, `test_load_missing_key_returns_corrupted`
- **Added docs updates section**: Explicit facts for DECISIONS.md and CHANGELOG.md

## Context

**Phase:** 2, **Module:** analysis
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`

## Scope

- [ ] `src/frame_compare/analysis/cache_io.py`
- [ ] `tests/analysis/test_cache_io.py`
- [ ] `src/frame_compare/analysis/__init__.py` (additive)
- [ ] `docs/DECISIONS.md`, `CHANGELOG.md`

**NOT covered:** Metrics calculation (Phase 2.2), legacy filename, warnings.

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`:
  - Section: "2.3 CacheLoadResult"
  - Section: "3.3 Cache Operations"
  - Section: "5. Cache Strategy"
  - Section: "5.1 Cache Key Generation"
  - Section: "5.2 Cache File Schema (v2)"
  - Section: "5.3 Invalidation Rules"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`:
  - Section: "2.2 Section Schemas"

## Files to Create/Modify

### 1. `src/frame_compare/analysis/cache_io.py` [NEW]

**Functions (spec-anchored):**

- `compute_cache_key(video_paths: list[Path], config: AnalysisConfig) -> str`
- `load_cached_metrics(cache_dir: Path, fingerprint: str, clips: list[ClipIdentity]) -> CacheLoadResult`
- `save_metrics_cache(metrics: FrameMetrics, cache_dir: Path) -> None`

**Exception propagation policy:**

- `compute_cache_key`: May propagate `OSError`. No Frame Compare exceptions.
- `save_metrics_cache`: May propagate `OSError`. No Frame Compare exceptions.
- `load_cached_metrics`: Returns `CacheLoadResult(success=False, reason=...)` for all failures. Does not raise.

**clips parameter:** Ignored (SSOT says "fingerprint is authoritative; do not recompute from clips").

**fps serialization (per SSOT 5.2):**

- Serialize: `str(metrics.metadata.fps)` → `"24/1"`
- Deserialize: `Fraction(fps_str)` → `Fraction(24, 1)`

### 2. `tests/analysis/test_cache_io.py` [NEW]

**Tests (15 total):**

| # | Test Name | Assertion |
|---|-----------|-----------|
| 1 | `test_compute_cache_key_deterministic` | Same paths + config → same 64-char hex |
| 2 | `test_compute_cache_key_order_independent` | `[a, b]` → same key as `[b, a]` |
| 3 | `test_compute_cache_key_changes_on_frame_count` | Different `frame_count` → different key |
| 4 | `test_compute_cache_key_changes_on_selection_mode` | Different `selection_mode` → different key |
| 5 | `test_compute_cache_key_changes_on_random_seed` | Different `random_seed` → different key |
| 6 | `test_compute_cache_key_changes_on_dark_quantile` | Different `dark_quantile` → different key |
| 7 | `test_compute_cache_key_changes_on_bright_quantile` | Different `bright_quantile` → different key |
| 8 | `test_save_and_load_round_trip` | Save → load → `success=True`, `luminance`/`motion` lists match, `fps == Fraction(24)` |
| 9 | `test_load_not_found` | Empty dir → `reason="not_found"` |
| 10 | `test_load_corrupted` | Invalid JSON → `reason="corrupted"` |
| 11 | `test_load_version_mismatch` | Wrong version → `reason="version_mismatch"` |
| 12 | `test_load_fingerprint_mismatch` | Wrong fingerprint → `reason="fingerprint_mismatch"` |
| 13 | `test_save_creates_directory` | Non-existent dir → created |
| 14 | `test_save_writes_required_keys` | Cache file JSON has all top-level keys (`version`, `fingerprint`, `luminance`, `motion`, `metadata`) and `version == 2` |
| 15 | `test_load_missing_key_returns_corrupted` | Cache file missing `luminance` key → `reason="corrupted"` |

### 3. `src/frame_compare/analysis/__init__.py` [MODIFY]

Add exports: `compute_cache_key`, `load_cached_metrics`, `save_metrics_cache`

### 4. `docs/DECISIONS.md` [MODIFY]

**Required facts:**

- RUN_ID: 2025-12-29__p2-4__cache-io
- Artifact versions: plan-v4, plan-review-v4, impl-v1, verify-v1, review-v1
- Public API: `compute_cache_key`, `load_cached_metrics`, `save_metrics_cache`
- SSOT updates: analysis-module.md sections 3.3 and 5

### 5. `CHANGELOG.md` [MODIFY]

```
### Added
- Cache I/O for frame metrics (`load_cached_metrics`, `save_metrics_cache`, `compute_cache_key`)
```

## Acceptance Criteria

- [ ] `compute_cache_key` returns same key regardless of path order
- [ ] `compute_cache_key` changes key when any fingerprinted config field changes
- [ ] Round-trip: `save_metrics_cache` → `load_cached_metrics` preserves data including `fps`
- [ ] Cache file contains all SSOT-required keys with `version == 2`
- [ ] Missing key in cache file → `reason="corrupted"`

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v4.md
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Notes for Coding Agent

- **clips parameter**: Ignored per SSOT; fingerprint is authoritative
- **fps serialization**: `str(Fraction)` on save, `Fraction(fps_str)` on load
- **Exception policy**: `compute_cache_key`/`save_metrics_cache` propagate `OSError`; only `load_cached_metrics` returns `CacheLoadResult`
- **If SSOT ambiguity encountered**: STOP and return to Planning with CHANGES REQUIRED; emit `plan-v(N+1).md`

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-4__cache-io

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v4.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v4.md
