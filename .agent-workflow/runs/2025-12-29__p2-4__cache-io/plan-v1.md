---
RUN_ID: 2025-12-29__p2-4__cache-io
VERSION: v1
TARGET: Phase 2 → Item 2.4
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v1.md
---

# Implementation Plan: Cache I/O Module

## Context

**Phase:** 2, **Module:** analysis
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
**Dependencies:** Phase 2.1 Types (complete), `CacheLoadResult`/`FrameMetrics`/`ClipIdentity`

## Scope

This plan covers:

- [ ] `src/frame_compare/analysis/cache_io.py` — cache persistence logic
- [ ] `tests/analysis/test_cache_io.py` — unit tests
- [ ] `src/frame_compare/analysis/__init__.py` — update exports (additive)
- [ ] `docs/DECISIONS.md` — append run decision entry
- [ ] `CHANGELOG.md` — add entry

This plan does NOT cover:

- Metrics calculation (Phase 2.2, blocked on VS)
- Frame selection (Phase 2.3, complete)
- Integration with VS module

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`:
  - Section: "2.3 CacheLoadResult"
  - Section: "3.3 Cache Operations"
  - Section: "5. Cache Strategy"
  - Section: "5.1 Cache Key Generation"
  - Section: "5.2 Invalidation Rules"

## Files to Create/Modify

### 1. `src/frame_compare/analysis/cache_io.py` [NEW]

**Purpose:** Cache persistence for `FrameMetrics`.

**Imports:**

```python
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING
from frame_compare.analysis.types import CacheLoadResult, ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.errors import CacheCorruptionError
if TYPE_CHECKING:
    from frame_compare.config import AnalysisConfig
```

**Constants:**

```python
CACHE_FILENAME: str = "cache.compframes"
CACHE_VERSION: int = 2
```

**Functions to implement (spec-anchored):**

- `compute_cache_key(video_paths: list[Path], config: AnalysisConfig) -> str`
- `load_cached_metrics(cache_dir: Path, fingerprint: str, clips: list[ClipIdentity]) -> CacheLoadResult`
- `save_metrics_cache(metrics: FrameMetrics, cache_dir: Path) -> None`

**Algorithm for `compute_cache_key`:**

```python
def compute_cache_key(video_paths: list[Path], config: AnalysisConfig) -> str:
    """Generate cache key from clip identities + config. Returns hex SHA-256."""
    h = hashlib.sha256()
    for p in sorted(video_paths):
        stat = p.stat()
        h.update(f"{p}|{stat.st_size}|{stat.st_mtime}".encode())
    h.update(f"{config.frame_count}|{config.selection_mode.value}|{config.random_seed}".encode())
    h.update(str(CACHE_VERSION).encode())
    return h.hexdigest()
```

**Algorithm for `load_cached_metrics`:**

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
    # Reconstruct FrameMetrics from data
    metrics = _deserialize_metrics(data)
    return CacheLoadResult(success=True, metrics=metrics)
```

**Algorithm for `save_metrics_cache`:**

```python
def save_metrics_cache(metrics: FrameMetrics, cache_dir: Path) -> None:
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

> [!NOTE]
> Internal helpers `_serialize_metrics` and `_deserialize_metrics` may be extracted by Coding Agent for clarity, but are not part of public API.

### 2. `tests/analysis/test_cache_io.py` [NEW]

**Purpose:** Unit tests for cache operations.

**Test Helpers:**

```python
from fractions import Fraction
from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata

def make_metrics() -> FrameMetrics:
    return FrameMetrics(
        luminance=[0.1, 0.2, 0.3],
        motion=[0.0, 0.1, 0.2],
        metadata=MetricsMetadata(
            frame_count=3, fps=Fraction(24), config_fingerprint="fp",
            clips=[ClipIdentity(path="video.mkv", size=1, mtime=1.0, sha1=None)], version=2))
```

**Tests (8 total):**

| # | Test Name | Input | Expected |
|---|-----------|-------|----------|
| 1 | `test_compute_cache_key_deterministic` | Same paths + config | Same hex string |
| 2 | `test_compute_cache_key_different_config_different_key` | Different `frame_count` | Different keys |
| 3 | `test_save_and_load_round_trip` | `make_metrics()` → save → load | `success=True`, `metrics` matches original |
| 4 | `test_load_not_found` | Empty `cache_dir` | `CacheLoadResult(success=False, reason="not_found")` |
| 5 | `test_load_corrupted` | Write invalid JSON to cache file | `CacheLoadResult(success=False, reason="corrupted")` |
| 6 | `test_load_version_mismatch` | Write cache with `version=1` | `CacheLoadResult(success=False, reason="version_mismatch")` |
| 7 | `test_load_fingerprint_mismatch` | Save with fp="a", load with fp="b" | `CacheLoadResult(success=False, reason="fingerprint_mismatch")` |
| 8 | `test_save_creates_directory` | Non-existent `cache_dir` | Directory created, cache file written |

**Assertions pattern:**

```python
def test_save_and_load_round_trip(tmp_path: Path):
    metrics = make_metrics()
    fingerprint = "test_fp"
    # Serialize fingerprint into the saved data
    save_metrics_cache(metrics, tmp_path, fingerprint)
    result = load_cached_metrics(tmp_path, fingerprint, metrics.metadata.clips)
    assert result.success is True
    assert result.metrics is not None
    assert list(result.metrics.luminance) == list(metrics.luminance)
    assert list(result.metrics.motion) == list(metrics.motion)
```

### 3. `src/frame_compare/analysis/__init__.py` [MODIFY]

**After (additive):**

```python
from frame_compare.analysis.cache_io import compute_cache_key, load_cached_metrics, save_metrics_cache
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.types import (CacheLoadResult, ClipIdentity, FrameMetrics, FrameSelection, MetricsMetadata, SelectionBreakdown)
__all__ = ["CacheLoadResult", "ClipIdentity", "FrameMetrics", "FrameSelection", "MetricsMetadata", "SelectionBreakdown", "compute_cache_key", "load_cached_metrics", "save_metrics_cache", "select_frames"]
```

### 4. `docs/DECISIONS.md` & `CHANGELOG.md` [MODIFY]

**DECISIONS.md facts:** RUN_ID, artifact versions, scope, verification passed.

**CHANGELOG.md:**

```
### Added
- Cache I/O for frame metrics (`load_cached_metrics`, `save_metrics_cache`, `compute_cache_key`)
```

## Acceptance Criteria

- [ ] GIVEN valid `FrameMetrics` WHEN `save_metrics_cache` then `load_cached_metrics` THEN `success=True` and data matches
- [ ] GIVEN same video paths + config WHEN `compute_cache_key` called twice THEN identical hex strings
- [ ] GIVEN corrupted cache file WHEN `load_cached_metrics` THEN `CacheLoadResult(success=False, reason="corrupted")`
- [ ] GIVEN version mismatch WHEN `load_cached_metrics` THEN `CacheLoadResult(success=False, reason="version_mismatch")`

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v1.md
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0.

## Notes for Coding Agent

- **JSON serialization** — `Fraction` must be converted to string (`"24/1"`) for JSON; reconstruct on load
- **`clips` field** — Store as list of dicts, reconstruct as `ClipIdentity` objects
- **Fingerprint storage** — Include `fingerprint` in saved JSON for validation on load
- **STOP if ambiguous**

---

> **Proposed RUN_ID:** 2025-12-29__p2-4__cache-io
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2025-12-29__p2-4__cache-io` before running Plan Review Agent.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-4__cache-io

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-4__cache-io/plan-review-v1.md
