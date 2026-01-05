---
RUN_ID: 2025-12-29__p2-4__cache-io
VERSION: v2
TARGET: Phase 2 → Item 2.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v1.md
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v2.md
---

# Implementation Plan: Cache I/O Module

## Changes Since plan-v1

- **Fixed `save_metrics_cache` signature drift**: Removed extra `fingerprint` arg from tests; fingerprint is derived from `metrics.metadata.config_fingerprint`
- **Added config-module.md spec anchor**: Explicitly list all `AnalysisConfig` fields used in cache key
- **Marked legacy filename out-of-scope**: `generated.compframes` support deferred to runner phase
- **Clarified warning responsibility**: `load_cached_metrics` returns `CacheLoadResult`, caller logs; no `CacheCorruptionError` raised
- **Made mtime tests deterministic**: Use `os.utime()` with fixed values

## Context

**Phase:** 2, **Module:** analysis
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
**Dependencies:** Phase 2.1 Types (complete)

## Scope

This plan covers:

- [ ] `src/frame_compare/analysis/cache_io.py` — cache persistence logic
- [ ] `tests/analysis/test_cache_io.py` — unit tests
- [ ] `src/frame_compare/analysis/__init__.py` — update exports (additive)
- [ ] `docs/DECISIONS.md`, `CHANGELOG.md`

This plan does NOT cover:

- Metrics calculation (Phase 2.2, blocked on VS)
- Legacy cache filename (`generated.compframes`) — deferred to Phase 6 runner integration
- Warning/logging on cache miss — caller responsibility (runner phase)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`:
  - Section: "2.3 CacheLoadResult"
  - Section: "3.3 Cache Operations"
  - Section: "5. Cache Strategy"
  - Section: "5.1 Cache Key Generation"
  - Section: "5.2 Invalidation Rules"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`:
  - Section: "2.2 Section Schemas"

## Files to Create/Modify

### 1. `src/frame_compare/analysis/cache_io.py` [NEW]

**Imports:**

```python
from __future__ import annotations
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING
from frame_compare.analysis.types import CacheLoadResult, ClipIdentity, FrameMetrics, MetricsMetadata
if TYPE_CHECKING:
    from frame_compare.config import AnalysisConfig
```

**Constants:**

```python
CACHE_FILENAME: str = "cache.compframes"
CACHE_VERSION: int = 2
```

**Functions (spec-anchored):**

- `compute_cache_key(video_paths: list[Path], config: AnalysisConfig) -> str`
- `load_cached_metrics(cache_dir: Path, fingerprint: str, clips: list[ClipIdentity]) -> CacheLoadResult`
- `save_metrics_cache(metrics: FrameMetrics, cache_dir: Path) -> None`

**`compute_cache_key` algorithm:**

```python
def compute_cache_key(video_paths: list[Path], config: AnalysisConfig) -> str:
    """Generate hex SHA-256 cache key from clip identities + config."""
    h = hashlib.sha256()
    for p in sorted(video_paths):
        stat = p.stat()
        h.update(f"{p}|{stat.st_size}|{stat.st_mtime}".encode())
    # All fingerprinted AnalysisConfig fields (from config-module.md 2.2 Section Schemas):
    h.update(f"{config.frame_count}".encode())
    h.update(f"{config.selection_mode.value}".encode())
    h.update(f"{config.random_seed}".encode())
    h.update(f"{config.dark_quantile}".encode())
    h.update(f"{config.bright_quantile}".encode())
    h.update(str(CACHE_VERSION).encode())
    return h.hexdigest()
```

**`load_cached_metrics` algorithm:**

```python
def load_cached_metrics(cache_dir: Path, fingerprint: str, clips: list[ClipIdentity]) -> CacheLoadResult:
    cache_file = cache_dir / CACHE_FILENAME
    if not cache_file.exists():
        return CacheLoadResult(success=False, reason="not_found")
    try:
        data = json.loads(cache_file.read_text())
    except (json.JSONDecodeError, OSError):
        return CacheLoadResult(success=False, reason="corrupted")
    if data.get("version") != CACHE_VERSION:
        return CacheLoadResult(success=False, reason="version_mismatch")
    if data.get("fingerprint") != fingerprint:
        return CacheLoadResult(success=False, reason="fingerprint_mismatch")
    metrics = _deserialize_metrics(data)
    return CacheLoadResult(success=True, metrics=metrics)
```

**`save_metrics_cache` algorithm:**

```python
def save_metrics_cache(metrics: FrameMetrics, cache_dir: Path) -> None:
    """Fingerprint is read from metrics.metadata.config_fingerprint."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / CACHE_FILENAME
    data = {
        "version": CACHE_VERSION,
        "fingerprint": metrics.metadata.config_fingerprint,
        "luminance": list(metrics.luminance),
        "motion": list(metrics.motion),
        "metadata": {
            "frame_count": metrics.metadata.frame_count,
            "fps": str(metrics.metadata.fps),
            "config_fingerprint": metrics.metadata.config_fingerprint,
            "clips": [{"path": c.path, "size": c.size, "mtime": c.mtime, "sha1": c.sha1} for c in metrics.metadata.clips],
            "version": metrics.metadata.version,
        },
    }
    cache_file.write_text(json.dumps(data, indent=2))
```

**Error handling:**

- No exceptions raised by this module; all failures return `CacheLoadResult(success=False, reason=...)`
- IO/stat failures in `load_cached_metrics` map to `reason="corrupted"`
- Warning/logging for cache miss is caller responsibility (runner phase)

### 2. `tests/analysis/test_cache_io.py` [NEW]

**Helpers:**

```python
import os
from fractions import Fraction
from pathlib import Path
from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.config import AnalysisConfig, SelectionMode

FIXED_MTIME = 1704067200.0  # 2024-01-01 00:00:00 UTC

def make_metrics(fingerprint: str = "fp") -> FrameMetrics:
    return FrameMetrics(
        luminance=[0.1, 0.2, 0.3], motion=[0.0, 0.1, 0.2],
        metadata=MetricsMetadata(
            frame_count=3, fps=Fraction(24), config_fingerprint=fingerprint,
            clips=[ClipIdentity(path="video.mkv", size=1, mtime=FIXED_MTIME, sha1=None)], version=2))

def make_config() -> AnalysisConfig:
    return AnalysisConfig(frame_count=10, selection_mode=SelectionMode.MIXED, random_seed=42)

def create_video_file(tmp_path: Path, name: str = "video.mkv") -> Path:
    """Create a test file with deterministic mtime."""
    f = tmp_path / name
    f.write_bytes(b"test")
    os.utime(f, (FIXED_MTIME, FIXED_MTIME))
    return f
```

**Tests (10 total):**

| # | Test Name | Assertion |
|---|-----------|-----------|
| 1 | `test_compute_cache_key_deterministic` | Same paths + config → same hex string (64 chars) |
| 2 | `test_compute_cache_key_changes_on_frame_count` | Different `frame_count` → different key |
| 3 | `test_compute_cache_key_changes_on_dark_quantile` | Different `dark_quantile` → different key |
| 4 | `test_compute_cache_key_changes_on_bright_quantile` | Different `bright_quantile` → different key |
| 5 | `test_save_and_load_round_trip` | `save_metrics_cache(metrics, dir)` → `load_cached_metrics(dir, fp, clips)` → `success=True`, data matches |
| 6 | `test_load_not_found` | Empty dir → `CacheLoadResult(success=False, reason="not_found")` |
| 7 | `test_load_corrupted` | Invalid JSON → `CacheLoadResult(success=False, reason="corrupted")` |
| 8 | `test_load_version_mismatch` | `version=1` in file → `reason="version_mismatch"` |
| 9 | `test_load_fingerprint_mismatch` | Different fingerprint → `reason="fingerprint_mismatch"` |
| 10 | `test_save_creates_directory` | Non-existent dir → dir + file created |

### 3. `src/frame_compare/analysis/__init__.py` [MODIFY]

**After (additive):**

```python
from frame_compare.analysis.cache_io import compute_cache_key, load_cached_metrics, save_metrics_cache
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.types import (CacheLoadResult, ClipIdentity, FrameMetrics, FrameSelection, MetricsMetadata, SelectionBreakdown)
__all__ = ["CacheLoadResult", "ClipIdentity", "FrameMetrics", "FrameSelection", "MetricsMetadata", "SelectionBreakdown", "compute_cache_key", "load_cached_metrics", "save_metrics_cache", "select_frames"]
```

### 4. `docs/DECISIONS.md` & `CHANGELOG.md` [MODIFY]

**CHANGELOG.md:**

```
### Added
- Cache I/O for frame metrics (`load_cached_metrics`, `save_metrics_cache`, `compute_cache_key`)
```

## Acceptance Criteria

- [ ] `compute_cache_key` returns same 64-char hex for identical inputs
- [ ] `compute_cache_key` returns different key when any fingerprinted config field changes
- [ ] `save_metrics_cache` → `load_cached_metrics` round-trip succeeds with matching data
- [ ] All error reasons (`not_found`, `corrupted`, `version_mismatch`, `fingerprint_mismatch`) tested

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v2.md
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Notes for Coding Agent

- **No `CacheCorruptionError` import**: Not raised; all failures return `CacheLoadResult`
- **Fingerprint source**: Always `metrics.metadata.config_fingerprint`
- **Mtime determinism**: Use `os.utime(path, (FIXED_MTIME, FIXED_MTIME))` in tests
- **STOP if ambiguous**

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-4__cache-io

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v2.md
