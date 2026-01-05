---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v5
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v4.md
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v5.md
---

# Implementation Plan: Audio Alignment Service

## Changes Since plan-v4

1. **Added utils progress tests:** `tests/utils/test_progress.py` with smoke tests for all 3 reporter implementations.
2. **Updated verification command:** Now runs `pytest -v tests/services/ tests/utils/` to include new progress tests.

## Context

**Phase:** 5 (Services)
**Module:** `frame_compare.services`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` (Section 2)
**Dependencies:** Phase 4 complete

## Scope

This plan covers:

- [x] Create `src/frame_compare/utils/progress.py` with full SSOT surface
- [x] Update `src/frame_compare/utils/__init__.py` to export progress types
- [x] Create `src/frame_compare/services/__init__.py` with public exports
- [x] Create `src/frame_compare/services/types.py` with alignment types
- [x] Create `src/frame_compare/services/alignment.py` with audio alignment logic
- [x] Write unit tests for alignment service
- [x] Write unit tests for utils progress
- [x] Update `importlinter.ini` with correct layer grouping

This plan does NOT cover:

- Metadata/Publishers/Dovi/Report services (5.2-5.5)
- Integration tests with real audio (Phase 5 Quality Gate)

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
| `RichProgressReporter` | Uses `rich.progress.Progress` |
| `LogProgressReporter` | Uses structlog; logs at milestone percentages |

### 2. `src/frame_compare/utils/__init__.py` [MODIFY]

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
    "ProgressReporter",
    "NullProgressReporter",
    "RichProgressReporter",
    "LogProgressReporter",
]
```

### 3. `src/frame_compare/services/__init__.py` [NEW]

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

**Types (from spec Section 2.1):**

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

**Error wrapping, cache format, load_cached_offsets semantics:** Same as plan-v4.

### 6. `tests/utils/__init__.py` [NEW]

**Purpose:** Test package marker (empty file).

### 7. `tests/utils/test_progress.py` [NEW]

**Purpose:** Smoke tests for progress reporter implementations.

**Tests required:**

| Test Name | Input | Expected |
|-----------|-------|----------|
| `test_null_progress_reporter_noops` | `NullProgressReporter()` → call all 4 methods | No exception raised |
| `test_rich_progress_reporter_smoke` | `RichProgressReporter()` → `start_phase("test", 10)`, `advance(1)`, `set_description("x")`, `complete_phase()` | No exception raised |
| `test_log_progress_reporter_smoke` | `LogProgressReporter()` → same sequence | No exception raised |

### 8. `tests/services/__init__.py` [NEW]

**Purpose:** Test package marker (empty file).

### 9. `tests/services/test_alignment.py` [NEW]

**Purpose:** Unit tests for alignment service.

**Tests required (same as plan-v3/v4):**

| Test Name | Input | Expected |
|-----------|-------|----------|
| `test_alignment_result_is_frozen` | mutation attempt | `FrozenInstanceError` |
| `test_alignment_config_defaults` | `AlignmentConfig()` | correct defaults |
| `test_cross_correlate_identical_signals` | `ref = comp = [1.0, 0.5, 0.0, -0.5]` | `(0, ≈1.0)` |
| `test_cross_correlate_positive_shift` | shifted arrays | `offset=2` |
| `test_cross_correlate_negative_shift` | shifted arrays | `offset=-2` |
| `test_cross_correlate_zero_norm_raises` | zeros array | `AudioAlignmentError` |
| `test_samples_to_frames_integer_fps` | 8000 samples, 8000 Hz, 24 fps | `24` |
| `test_samples_to_frames_fractional_fps` | 8008 samples, 8000 Hz, 24000/1001 fps | `24` |
| `test_probe_fps_fraction` | mock `"24000/1001\n"` | `Fraction(24000, 1001)` |
| `test_probe_fps_integer` | mock `"24\n"` | `Fraction(24, 1)` |
| `test_probe_fps_not_found_raises` | `FileNotFoundError` | `FFmpegNotFoundError` |
| `test_probe_fps_nonzero_exit_raises` | returncode=1 | `FFmpegError` |
| `test_extract_audio_ffmpeg_not_found` | `FileNotFoundError` | `FFmpegNotFoundError` |
| `test_extract_audio_ffmpeg_fails` | returncode=1 | `FFmpegError` |
| `test_extract_audio_empty_raises` | empty output | `AudioAlignmentError` |
| `test_load_cached_offsets_missing_returns_none` | no file | `None` |
| `test_load_cached_offsets_valid_returns_dict` | valid TOML | dict with key |
| `test_load_cached_offsets_valid_no_match_returns_empty` | valid TOML, wrong clips | `{}` |
| `test_load_cached_offsets_corruption_raises` | invalid TOML | `CacheCorruptionError` |
| `test_load_cached_offsets_version_mismatch_raises` | version="999" | `CacheVersionMismatchError` |
| `test_save_offsets_cache_writes_toml` | results list | file written |
| `test_align_clips_uses_cache` | pre-populated cache | no extraction |

### 10. `importlinter.ini` [MODIFY]

**Exact content:**

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

### 11. `docs/DECISIONS.md` [MODIFY]

**Required facts:** RUN_ID, artifacts v1-v5, scope, SSOT edits.

### 12. `CHANGELOG.md` [MODIFY]

**Entry:** "Added: Audio alignment service for synchronizing comparison clips"

## Acceptance Criteria

Same as plan-v4, plus:

- [ ] GIVEN `NullProgressReporter()` WHEN calling all methods THEN no exception
- [ ] GIVEN `RichProgressReporter()` WHEN calling all methods THEN no exception
- [ ] GIVEN `LogProgressReporter()` WHEN calling all methods THEN no exception

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v5.md

# Type check
.venv/bin/pyright --warnings src/frame_compare/services src/frame_compare/utils/progress.py

# Lint
.venv/bin/ruff check src/frame_compare/services src/frame_compare/utils/progress.py

# Tests (includes both services and utils)
.venv/bin/pytest -v tests/services/ tests/utils/

# Import contract
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Rollback / Stop Conditions

- **If lint-imports fails:** STOP and return to Planning.
- **If Rich import fails:** Ensure `rich` is in dependencies.

## Notes for Coding Agent

1. **Create progress.py FIRST** — Required by alignment.py
2. **RichProgressReporter** — Copy from utils-module.md Section 4.2
3. **LogProgressReporter** — Uses structlog, logs at milestone %
4. **importlinter layer grouping** — Use `(a | b | c)` for siblings
5. **Offset sign** — Positive = comp AFTER ref
6. **Cache format** — TOML with `version = "1"`

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p5-1__audio-alignment

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v5.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v5.md
