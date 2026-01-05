---
RUN_ID: 2025-12-29__p2-4__cache-io
VERSION: v6
TARGET: Phase 2 → Item 2.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v5.md
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v5.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v6.md
---

# Implementation Plan: Cache I/O Module

## Changes Since plan-v5

- **Made plan standalone**: Replaced "Other functions: As specified in plan-v4" with explicit SSOT-anchored content for `load_cached_metrics` and `save_metrics_cache`
- **Re-added exception policy**: Explicit propagation rules for all three functions
- **Fixed STOP instruction**: Now names `plan-v7.md`

## Context

**Phase:** 2, **Module:** analysis

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

**Constants:**

```python
CACHE_FILENAME: str = "cache.compframes"
CACHE_VERSION: int = 2
```

**`compute_cache_key` encoding algorithm:**

```python
def compute_cache_key(video_paths: list[Path], config: AnalysisConfig) -> str:
    h = hashlib.sha256()
    for p in sorted(video_paths, key=str):
        stat = p.stat()
        h.update(f"{p}|{stat.st_size}|{stat.st_mtime}".encode("utf-8"))
    h.update(f"{config.frame_count}|{config.selection_mode.value}|{config.random_seed}|{config.dark_quantile}|{config.bright_quantile}".encode("utf-8"))
    h.update(str(CACHE_VERSION).encode("utf-8"))
    return h.hexdigest()
```

**`load_cached_metrics` behavior (per SSOT 3.3):**

- `clips` parameter: Ignored; fingerprint is authoritative (do not recompute from clips)
- Failure mapping (per SSOT 3.3):
  - Cache file not found → `CacheLoadResult(success=False, reason="not_found")`
  - Invalid JSON or missing required keys → `CacheLoadResult(success=False, reason="corrupted")`
  - `version != CACHE_VERSION` → `CacheLoadResult(success=False, reason="version_mismatch")`
  - `fingerprint` mismatch → `CacheLoadResult(success=False, reason="fingerprint_mismatch")`

**`save_metrics_cache` behavior (per SSOT 5.2):**

- Creates `cache_dir` if needed
- Writes JSON with required top-level keys: `version`, `fingerprint`, `luminance`, `motion`, `metadata`
- `fps` serialization: `str(Fraction)` → e.g. `"24/1"`

**Exception policy:**

- `compute_cache_key`: May propagate `OSError` from `Path.stat()`
- `save_metrics_cache`: May propagate `OSError` from filesystem writes
- `load_cached_metrics`: Does not raise; all failures return `CacheLoadResult(... reason=...)`

### 2. `tests/analysis/test_cache_io.py` [NEW]

**Tests (18 total):**

| # | Test Name | Assertion |
|---|-----------|-----------|
| 1 | `test_compute_cache_key_deterministic` | Same paths + config → same 64-char hex |
| 2 | `test_compute_cache_key_order_independent` | `[a, b]` → same key as `[b, a]` |
| 3 | `test_compute_cache_key_changes_on_frame_count` | Different `frame_count` → different key |
| 4 | `test_compute_cache_key_changes_on_selection_mode` | Different `selection_mode` → different key |
| 5 | `test_compute_cache_key_changes_on_random_seed` | Different `random_seed` → different key |
| 6 | `test_compute_cache_key_changes_on_dark_quantile` | Different `dark_quantile` → different key |
| 7 | `test_compute_cache_key_changes_on_bright_quantile` | Different `bright_quantile` → different key |
| 8 | `test_compute_cache_key_changes_on_path_change` | Rename file → different key |
| 9 | `test_compute_cache_key_changes_on_size_change` | Write more bytes to file → different key |
| 10 | `test_compute_cache_key_changes_on_mtime_change` | `os.utime(path, (new_mtime, new_mtime))` → different key |
| 11 | `test_save_and_load_round_trip` | Save → load → `success=True`, data matches, `fps == Fraction(24)` |
| 12 | `test_load_not_found` | Empty dir → `reason="not_found"` |
| 13 | `test_load_corrupted` | Invalid JSON → `reason="corrupted"` |
| 14 | `test_load_version_mismatch` | Wrong version → `reason="version_mismatch"` |
| 15 | `test_load_fingerprint_mismatch` | Wrong fingerprint → `reason="fingerprint_mismatch"` |
| 16 | `test_save_creates_directory` | Non-existent dir → created |
| 17 | `test_save_writes_required_keys` | Cache file JSON has all required keys + `version == 2` |
| 18 | `test_load_missing_key_returns_corrupted` | Missing `luminance` key → `reason="corrupted"` |

**Test helpers:**

```python
FIXED_MTIME = 1704067200.0  # 2024-01-01 00:00:00 UTC

def create_video_file(tmp_path: Path, name: str = "video.mkv", content: bytes = b"test") -> Path:
    f = tmp_path / name
    f.write_bytes(content)
    os.utime(f, (FIXED_MTIME, FIXED_MTIME))
    return f
```

### 3. `src/frame_compare/analysis/__init__.py` [MODIFY]

Add exports: `compute_cache_key`, `load_cached_metrics`, `save_metrics_cache`

### 4. Docs Updates

**DECISIONS.md facts:** RUN_ID, artifact versions, public API, SSOT updates.
**CHANGELOG.md:** Cache I/O functions added.

## Acceptance Criteria

- [ ] `compute_cache_key` returns same 64-char hex for identical inputs
- [ ] `compute_cache_key` changes key when any of: path, size, mtime, config.* changes
- [ ] Round-trip preserves data including `fps`
- [ ] Cache file contains all SSOT-required keys

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v6.md
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Notes for Coding Agent

- **Encoding algorithm**: Follow the exact encoding rules above
- **Invalidation tests**: Use `os.utime()` for mtime, file rename for path, different bytes for size
- **fps serialization**: `str(Fraction)` on save, `Fraction(fps_str)` on load
- **clips parameter**: Ignored per SSOT; fingerprint is authoritative
- **If SSOT ambiguity encountered**: STOP and return to Planning with CHANGES REQUIRED; emit `plan-v7.md`

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-4__cache-io

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v6.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v6.md
