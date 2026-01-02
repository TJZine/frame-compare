---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v4
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v3.md
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v4.md
---

# Implementation Plan: Audio Alignment Service

## Changes Since plan-v3

1. **Fixed `importlinter.ini` layer placement:** Services grouped as sibling of analysis/render using `(frame_compare.analysis | frame_compare.render | frame_compare.services)`.
2. **Added `frame_compare.services` to independence contract:** Prevents cross-imports between analysis/render/services.
3. **Expanded `progress.py` to full SSOT surface:** Added `RichProgressReporter` and `LogProgressReporter` per utils-module.md Section 4.2.
4. **Specified exact `utils/__init__.py` changes:** Both import statement and `__all__` additions.

## Context

**Phase:** 5 (Services)
**Module:** `frame_compare.services`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` (Section 2)
**Dependencies:** Phase 4 complete (render module), `AudioAlignmentError` exists in `errors.py`

## Scope

This plan covers:

- [x] Create `src/frame_compare/utils/progress.py` with full SSOT surface
- [x] Update `src/frame_compare/utils/__init__.py` to export progress types
- [x] Create `src/frame_compare/services/__init__.py` with public exports
- [x] Create `src/frame_compare/services/types.py` with alignment types
- [x] Create `src/frame_compare/services/alignment.py` with audio alignment logic
- [x] Write unit tests for alignment service
- [x] Update `importlinter.ini` with correct layer grouping

This plan does NOT cover:

- Metadata service (5.2), Publishers service (5.3), Dovi service (5.4), Report service (5.5)
- Integration tests with real audio files (Phase 5 Quality Gate)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`:
  - Section: "2. Audio Alignment Service"
  - Section: "2.1 Types"
  - Section: "2.2 Public API"
  - Section: "2.3 Implementation Details"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`:
  - Section: "4.2 Progress Reporting"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md`:
  - Section: "2.2 Exception Tree"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. `src/frame_compare/utils/progress.py` [NEW]

**Purpose:** ProgressReporter protocol + all implementations per utils-module.md Section 4.2.

**Types to implement:**

| Type | Methods/Notes |
|------|---------------|
| `ProgressReporter(Protocol)` | `start_phase(name: str, total: int)`, `advance(amount: int = 1)`, `set_description(desc: str)`, `complete_phase()` |
| `NullProgressReporter` | No-op implementation |
| `RichProgressReporter` | Uses `rich.progress.Progress` with SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn |
| `LogProgressReporter` | Uses structlog; logs at 10%, 25%, 50%, 75%, 100% milestones |

### 2. `src/frame_compare/utils/__init__.py` [MODIFY]

**Purpose:** Export progress types.

**Exact changes:**

Add import:

```python
from frame_compare.utils.progress import (
    ProgressReporter,
    NullProgressReporter,
    RichProgressReporter,
    LogProgressReporter,
)
```

Add to `__all__`:

```python
__all__ = [
    "configure_logging",
    "get_run_id",
    "new_run_id",
    "is_perf_enabled",
    "perf_span",
    # New exports
    "ProgressReporter",
    "NullProgressReporter",
    "RichProgressReporter",
    "LogProgressReporter",
]
```

### 3. `src/frame_compare/services/__init__.py` [NEW]

**Purpose:** Public exports for the services module.

**Content:**

```python
from frame_compare.services.types import AlignmentResult, AlignmentConfig
from frame_compare.services.alignment import (
    align_clips,
    load_cached_offsets,
    save_offsets_cache,
)

__all__ = [
    "AlignmentResult",
    "AlignmentConfig",
    "align_clips",
    "load_cached_offsets",
    "save_offsets_cache",
]
```

### 4. `src/frame_compare/services/types.py` [NEW]

**Purpose:** Service-specific data types.

**Types to define (from spec Section 2.1):**

| Type | Fields |
|------|--------|
| `AlignmentResult` (frozen dataclass) | `reference_clip: str`, `comparison_clip: str`, `frame_offset: int`, `time_offset_seconds: float`, `correlation_score: float`, `method: str` |
| `AlignmentConfig` (frozen dataclass) | `enable: bool = True`, `sample_rate: int = 8000`, `max_offset_seconds: float = 30.0`, `use_vspreview: bool = False`, `cache_results: bool = True` |

### 5. `src/frame_compare/services/alignment.py` [NEW]

**Purpose:** Audio alignment using FFmpeg and cross-correlation.

**Public API (from spec Section 2.2):**

- `align_clips(reference: Path, comparisons: list[Path], config: AlignmentConfig, cache_dir: Path, progress: ProgressReporter | None = None) -> list[AlignmentResult]`
- `load_cached_offsets(cache_dir: Path, clips: list[Path]) -> dict[str, AlignmentResult] | None`
- `save_offsets_cache(cache_dir: Path, results: list[AlignmentResult]) -> None`

**Internal functions (from spec Section 2.3):**

- `_probe_fps(video_path: Path) -> Fraction`
- `_extract_audio(video_path: Path, sample_rate: int) -> np.ndarray`
- `_cross_correlate(reference: np.ndarray, comparison: np.ndarray) -> tuple[int, float]`
- `_samples_to_frames(sample_offset: int, sample_rate: int, fps: Fraction) -> int`

**Error wrapping, cache format, load_cached_offsets semantics:** Same as plan-v3.

### 6. `tests/services/__init__.py` [NEW]

**Purpose:** Test package marker (empty file).

### 7. `tests/services/test_alignment.py` [NEW]

**Purpose:** Unit tests for alignment service. Same test list as plan-v3 (17 tests with deterministic vectors).

### 8. `importlinter.ini` [MODIFY]

**Purpose:** Add `frame_compare.services` with correct layer grouping.

**Exact content after modification:**

```ini
[importlinter]
root_package = frame_compare

[importlinter:contract:layers]
name = Layered Architecture
type = layers
layers =
    frame_compare.cli_entry
    (frame_compare.analysis | frame_compare.render | frame_compare.services)
    frame_compare.vs
    frame_compare.config
    frame_compare.utils
    frame_compare.errors

[importlinter:contract:domain-independence]
name = Domain Independence
type = independence
modules =
    frame_compare.analysis
    frame_compare.render
    frame_compare.services
```

### 9. `docs/DECISIONS.md` [MODIFY]

**Required facts to record:**

- RUN_ID: `2026-01-01__p5-1__audio-alignment`
- Artifacts: plan-v1 through plan-v4, plan-review-v1 through plan-review-v3
- Scope: Audio alignment + ProgressReporter dependency (full implementation)
- SSOT edits: services-module.md 2.2 and 2.3
- Layer contract: services is sibling of analysis/render, added to independence contract

### 10. `CHANGELOG.md` [MODIFY]

**Entry:** "Added: Audio alignment service for synchronizing comparison clips"

## Acceptance Criteria

Same as plan-v3, plus:

- [ ] GIVEN `frame_compare.services` and `frame_compare.render` WHEN running lint-imports THEN no imports between them
- [ ] GIVEN `RichProgressReporter()` WHEN calling `start_phase("test", 10)` THEN no error raised

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v4.md

# Type check
.venv/bin/pyright --warnings src/frame_compare/services src/frame_compare/utils/progress.py

# Lint
.venv/bin/ruff check src/frame_compare/services src/frame_compare/utils/progress.py

# Tests
.venv/bin/pytest -v tests/services/

# Import contract
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Rollback / Stop Conditions

- **If lint-imports fails with layer or independence contract errors:** STOP and return to Planning to verify architecture SSOT alignment.
- **If Rich import fails at runtime:** Ensure `rich` is in project dependencies (it is, per pyproject.toml).

## Notes for Coding Agent

1. **Create progress.py FIRST** — Required by alignment.py
2. **RichProgressReporter** — Copy implementation from utils-module.md Section 4.2
3. **LogProgressReporter** — Uses structlog, logs at milestone percentages
4. **importlinter layer grouping** — Use parentheses for sibling modules: `(a | b | c)`
5. **Offset sign convention** — Positive = comp AFTER ref; Negative = comp BEFORE ref
6. **Cache format** — TOML with `version = "1"`
7. **FPS probing** — Parse ffprobe output as `num/den` or `num` → Fraction

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p5-1__audio-alignment

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v4.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v4.md
