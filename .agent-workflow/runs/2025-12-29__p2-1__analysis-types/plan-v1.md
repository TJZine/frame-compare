---
RUN_ID: 2025-12-29__p2-1__analysis-types
VERSION: v1
TARGET: Phase 2 → Item 2.1
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v1.md
---

# Implementation Plan: Analysis Types

## Context

**Phase:** 2
**Module:** `frame_compare.analysis`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`
**Dependencies:** Phase 1 (Config, Errors, Logging, CLI) ✅

## Scope

This plan covers:

- [ ] Create `src/frame_compare/analysis/types.py` with all dataclasses
- [ ] Create `src/frame_compare/analysis/__init__.py` with exports
- [ ] Write unit tests in `tests/analysis/test_types.py`

This plan does NOT cover:

- `metrics.py` (Phase 2.2)
- `selection.py` (Phase 2.3)
- `cache_io.py` (Phase 2.4)
- Integration with VapourSynth

## Contract Impact

**Contracts touched:** NO (new module, no existing contracts)

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md`:
  - Section: "2.1 FrameMetrics"
  - Section: "2.2 FrameSelection"
  - Section: "2.3 CacheLoadResult"
  - Section: "3.1 calculate_metrics"

## Public API Signatures (spec-anchored)

**Dataclasses to implement (per SSOT Section 2):**

The following frozen dataclasses are defined in SSOT with field specifications. Copy the class definitions exactly from the SSOT code blocks:

1. **ClipIdentity** — Identity of a video clip (path, size, mtime, sha1)
2. **MetricsMetadata** — Metadata about calculated metrics (frame_count, fps, config_fingerprint, clips, version)
3. **FrameMetrics** — Analysis results with luminance and motion arrays plus metadata
4. **SelectionBreakdown** — Breakdown by selection method (quantile_dark, quantile_bright, motion, random)
5. **FrameSelection** — Selected frames with mode, seed, and breakdown
6. **CacheLoadResult** — Cache load result with success, metrics, and reason fields

All classes use `@dataclass(frozen=True, slots=True)` decorator.

**Note:** `SelectionMode` is imported from `frame_compare.config` per SSOT Section 1.3.

**Function reference (for validator, NOT implemented in this phase):**

- `calculate_metrics(video_paths: list[Path], config: AnalysisConfig, cache_dir: Path, reporter: ProgressReporter | None = None) -> FrameMetrics`

> The types defined in this phase are prerequisites for the `calculate_metrics` function (Phase 2.2).

## Files to Create/Modify

### 1. `src/frame_compare/analysis/__init__.py` (NEW)

**Purpose:** Package marker and public exports.

**Exports:**

```python
from frame_compare.analysis.types import (
    ClipIdentity,
    MetricsMetadata,
    FrameMetrics,
    SelectionBreakdown,
    FrameSelection,
    CacheLoadResult,
)

__all__ = [
    "ClipIdentity",
    "MetricsMetadata",
    "FrameMetrics",
    "SelectionBreakdown",
    "FrameSelection",
    "CacheLoadResult",
]
```

### 2. `src/frame_compare/analysis/types.py` (NEW)

**Purpose:** Define all dataclasses per SSOT Section 2.

**Types to implement (copy SSOT definitions):**

```python
from dataclasses import dataclass
from fractions import Fraction
from frame_compare.config import SelectionMode

@dataclass(frozen=True, slots=True)
class ClipIdentity:
    """Identity of a video clip for cache key generation."""
    path: str
    size: int
    mtime: float
    sha1: str | None = None

@dataclass(frozen=True, slots=True)
class MetricsMetadata:
    """Metadata about calculated metrics."""
    frame_count: int
    fps: Fraction
    config_fingerprint: str
    clips: list[ClipIdentity]
    version: int = 2

@dataclass(frozen=True, slots=True)
class FrameMetrics:
    """Analysis results for a video clip."""
    luminance: list[float]
    motion: list[float]
    metadata: MetricsMetadata

@dataclass(frozen=True, slots=True)
class SelectionBreakdown:
    """Breakdown of selected frames by selection method."""
    quantile_dark: list[int]
    quantile_bright: list[int]
    motion: list[int]
    random: list[int]

@dataclass(frozen=True, slots=True)
class FrameSelection:
    """Selected frame numbers with reasoning."""
    frames: list[int]
    mode: SelectionMode
    seed: int
    breakdown: SelectionBreakdown

@dataclass(frozen=True, slots=True)
class CacheLoadResult:
    """Result of attempting to load metrics from cache."""
    success: bool
    metrics: FrameMetrics | None = None
    reason: str | None = None  # "not_found" | "corrupted" | "version_mismatch" | "fingerprint_mismatch"
```

### 3. `tests/analysis/__init__.py` (NEW)

**Purpose:** Empty marker file for test package.

### 4. `tests/analysis/test_types.py` (NEW)

**Purpose:** Unit tests for dataclass instantiation and immutability.

**Tests required:**

- `test_clip_identity_creation` — creates ClipIdentity with all fields
- `test_clip_identity_optional_sha1` — sha1 defaults to None
- `test_clip_identity_frozen` — assignment raises FrozenInstanceError
- `test_metrics_metadata_creation` — creates MetricsMetadata with Fraction fps
- `test_metrics_metadata_default_version` — version defaults to 2
- `test_frame_metrics_creation` — creates FrameMetrics with nested metadata
- `test_selection_breakdown_creation` — creates SelectionBreakdown with all lists
- `test_frame_selection_creation` — creates FrameSelection with mode enum
- `test_cache_load_result_success` — success=True with metrics
- `test_cache_load_result_failure` — success=False with reason

### 5. `CHANGELOG.md` (MODIFY)

**Entry format:** Under `## [Unreleased]`, add:

```markdown
### Added
- Analysis module types: `ClipIdentity`, `MetricsMetadata`, `FrameMetrics`, `SelectionBreakdown`, `FrameSelection`, `CacheLoadResult`
```

## Acceptance Criteria

- [ ] GIVEN `ClipIdentity(path="a.mkv", size=100, mtime=1.0)` WHEN created THEN all fields accessible
- [ ] GIVEN `ClipIdentity` instance WHEN assigning to field THEN raises `FrozenInstanceError`
- [ ] GIVEN `FrameMetrics` with nested `MetricsMetadata` WHEN accessed THEN all nested fields accessible
- [ ] GIVEN `FrameSelection` with `SelectionMode.MIXED` WHEN created THEN mode is correct enum value
- [ ] GIVEN `CacheLoadResult(success=False, reason="not_found")` WHEN created THEN metrics is None

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/analysis/
.venv/bin/ruff check src/frame_compare/analysis/
.venv/bin/pytest -v tests/analysis/
.venv/bin/pyright --warnings
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0.

## Notes for Coding Agent

1. **SelectionMode import:** Per SSOT Section 1.3, `SelectionMode` is defined in `frame_compare.config`. Import it from there.

2. **Frozen dataclasses:** All dataclasses MUST use `frozen=True, slots=True` for immutability and efficiency.

3. **Fraction import:** Use `from fractions import Fraction` for the fps field.

4. **No VapourSynth dependency:** This types-only module has no VS dependency.

5. **Rollback:** If import contracts fail, STOP and return to Planning.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p2-1__analysis-types

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p2-1__analysis-types/plan-review-v1.md
