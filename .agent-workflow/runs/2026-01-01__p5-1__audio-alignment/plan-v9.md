---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v9
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v8.md
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v8.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v9.md
---

# Implementation Plan: Audio Alignment Service

## Changes Since plan-v8

1. **Mechanical test fix:** Partial-cache-hit async test now stubs `_extract_audio` to return deterministic `np.ndarray` samples (no real FFmpeg calls) while still asserting call args.

## Context

**Phase:** 5 (Services)
**Module:** `frame_compare.services`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` (Section 2)

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

**Types (from utils-module.md Section 4.2):**

| Type | Methods/Notes |
|------|---------------|
| `ProgressReporter(Protocol)` | `start_phase(name: str, total: int)`, `advance(amount: int = 1)`, `set_description(desc: str)`, `complete_phase()` |
| `NullProgressReporter` | No-op implementation of all 4 methods |
| `RichProgressReporter` | Uses `rich.progress.Progress` with SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn |
| `LogProgressReporter` | Uses structlog; logs at 10%, 25%, 50%, 75%, 100% milestones |

### 2. `src/frame_compare/utils/__init__.py` [MODIFY]

**Current content:**

```python
"""Utilities for Frame Compare 2.0."""

from frame_compare.utils.logging import configure_logging, get_run_id, new_run_id
from frame_compare.utils.perf import is_perf_enabled, perf_span

__all__ = [
    "configure_logging",
    "get_run_id",
    "new_run_id",
    "is_perf_enabled",
    "perf_span",
]
```

**After modification:**

```python
"""Utilities for Frame Compare 2.0."""

from frame_compare.utils.logging import configure_logging, get_run_id, new_run_id
from frame_compare.utils.perf import is_perf_enabled, perf_span
from frame_compare.utils.progress import (
    ProgressReporter,
    NullProgressReporter,
    RichProgressReporter,
    LogProgressReporter,
)

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

```python
"""Services for Frame Compare 2.0."""

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

**Public API (from spec Section 2.2):**

- `align_clips(reference: Path, comparisons: list[Path], config: AlignmentConfig, cache_dir: Path, progress: ProgressReporter | None = None) -> list[AlignmentResult]`
- `load_cached_offsets(cache_dir: Path, clips: list[Path]) -> dict[str, AlignmentResult] | None`
- `save_offsets_cache(cache_dir: Path, results: list[AlignmentResult]) -> None`

**Internal functions (from spec Section 2.3):**

- `_probe_fps(video_path: Path) -> Fraction`
- `_extract_audio(video_path: Path, sample_rate: int) -> np.ndarray`
- `_cross_correlate(reference: np.ndarray, comparison: np.ndarray) -> tuple[int, float]`
- `_samples_to_frames(sample_offset: int, sample_rate: int, fps: Fraction) -> int`

### 6. `tests/utils/__init__.py` [NEW]

Empty test package marker.

### 7. `tests/utils/test_progress.py` [NEW]

| Test Name | Input | Expected |
|-----------|-------|----------|
| `test_null_progress_reporter_noops` | `NullProgressReporter()` → all 4 methods | No exception |
| `test_rich_progress_reporter_smoke` | `RichProgressReporter()` → all 4 methods | No exception |
| `test_log_progress_reporter_smoke` | `LogProgressReporter()` → all 4 methods | No exception |

### 8. `tests/services/__init__.py` [NEW]

Empty test package marker.

### 9. `tests/services/test_alignment.py` [NEW]

#### Cache Fixture (for sync cache I/O tests)

```toml
version = "1"

["ref:comp_a"]
reference_clip = "ref.mkv"
comparison_clip = "comp_a.mkv"
frame_offset = 42
time_offset_seconds = 1.751
correlation_score = 0.987
method = "cross_correlation"
```

**Expected parsed result:**

```python
{
    "ref:comp_a": AlignmentResult(
        reference_clip="ref.mkv",
        comparison_clip="comp_a.mkv",
        frame_offset=42,
        time_offset_seconds=1.751,
        correlation_score=0.987,
        method="cross_correlation",
    )
}
```

#### Sync Unit Tests (with exact inputs and assertions)

| Test Name | Input | Assertion |
|-----------|-------|-----------|
| `test_alignment_result_is_frozen` | `AlignmentResult(...)`, mutation | `FrozenInstanceError` raised |
| `test_alignment_config_defaults` | `AlignmentConfig()` | `assert cfg.enable is True`; `assert cfg.sample_rate == 8000`; `assert cfg.max_offset_seconds == 30.0`; `assert cfg.use_vspreview is False`; `assert cfg.cache_results is True` |
| `test_cross_correlate_identical_signals` | `ref = comp = np.array([1.0, 0.5, 0.0, -0.5], dtype=np.float32)` | `assert offset == 0`; `assert score == pytest.approx(1.0, abs=1e-6)` |
| `test_cross_correlate_positive_shift` | `ref = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)`; `comp = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)` | `assert offset == 2` |
| `test_cross_correlate_negative_shift` | `ref = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)`; `comp = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)` | `assert offset == -2` |
| `test_cross_correlate_zero_norm_raises` | `ref = np.zeros(10, dtype=np.float32)`; `comp = np.ones(10, dtype=np.float32)` | `AudioAlignmentError` raised; `"zero-norm" in str(exc)` |
| `test_samples_to_frames_integer_fps` | `sample_offset=8000, sample_rate=8000, fps=Fraction(24, 1)` | `assert result == 24` |
| `test_samples_to_frames_fractional_fps` | `sample_offset=8008, sample_rate=8000, fps=Fraction(24000, 1001)` | `assert result == 24` |
| `test_probe_fps_fraction` | mock stdout `b"24000/1001\n"` | `assert result == Fraction(24000, 1001)` |
| `test_probe_fps_integer` | mock stdout `b"24\n"` | `assert result == Fraction(24, 1)` |
| `test_probe_fps_not_found_raises` | mock `FileNotFoundError` | `FFmpegNotFoundError` raised |
| `test_probe_fps_nonzero_exit_raises` | mock returncode=1 | `FFmpegError` raised |
| `test_extract_audio_ffmpeg_not_found` | mock `FileNotFoundError` | `FFmpegNotFoundError` raised |
| `test_extract_audio_ffmpeg_fails` | mock returncode=1 | `FFmpegError` raised |
| `test_extract_audio_empty_raises` | mock empty stdout | `AudioAlignmentError` raised; `"empty audio" in str(exc)` |
| `test_load_cached_offsets_missing_returns_none` | no cache file | `assert result is None` |
| `test_load_cached_offsets_valid_returns_dict` | TOML fixture above; `clips=[Path("ref.mkv"), Path("comp_a.mkv")]` | `assert "ref:comp_a" in result`; `assert result["ref:comp_a"].frame_offset == 42` |
| `test_load_cached_offsets_valid_no_match_returns_empty` | valid TOML; `clips=[Path("other.mkv"), Path("x.mkv")]` | `assert result == {}` |
| `test_load_cached_offsets_corruption_raises` | `"not valid toml {{{"` | `CacheCorruptionError` raised |
| `test_load_cached_offsets_version_mismatch_raises` | `version = "999"` | `CacheVersionMismatchError` raised |
| `test_save_offsets_cache_writes_toml` | `[AlignmentResult(...)]` | `assert cache_file.exists()`; `assert 'version = "1"' in content`; `assert '["ref:comp"]' in content` |

#### Async Cache Semantics Tests

**Full cache hit fixture (write this TOML):**

```toml
version = "1"

["ref:comp_a"]
reference_clip = "ref.mkv"
comparison_clip = "comp_a.mkv"
frame_offset = 10
time_offset_seconds = 0.417
correlation_score = 0.95
method = "cross_correlation"

["ref:comp_b"]
reference_clip = "ref.mkv"
comparison_clip = "comp_b.mkv"
frame_offset = 20
time_offset_seconds = 0.834
correlation_score = 0.92
method = "cross_correlation"
```

| Test Name | Setup | Assertions |
|-----------|-------|------------|
| `test_align_clips_full_cache_hit_skips_probe_and_extract` | `@pytest.mark.anyio`; `reference = tmp_path / "ref.mkv"`; `comparisons = [tmp_path / "comp_a.mkv", tmp_path / "comp_b.mkv"]`; touch all 3 files; write full cache TOML above; patch `_probe_fps` and `_extract_audio` to raise `AssertionError("should not be called")` | `assert len(result) == 2`; `assert result[0].comparison_clip == "comp_a.mkv"`; `assert result[0].frame_offset == 10`; `assert result[1].comparison_clip == "comp_b.mkv"`; `assert result[1].frame_offset == 20` |
| `test_align_clips_partial_cache_hit_computes_only_missing_and_preserves_order` | `@pytest.mark.anyio`; same paths; touch all 3 files; write cache with ONLY `"ref:comp_a"` entry (offset=10); patch `_probe_fps` → `Fraction(24, 1)`; patch `_extract_audio` as a stub returning `np.ones(10, dtype=np.float32)` (and record calls); patch `_cross_correlate` → `(0, 0.99)` | `assert len(result) == 2`; `assert result[0].comparison_clip == "comp_a.mkv"` (cached); `assert result[0].frame_offset == 10`; `assert result[1].comparison_clip == "comp_b.mkv"` (computed); assert `_extract_audio` called for `ref.mkv` and `comp_b.mkv` but NOT `comp_a.mkv` |

### 10. `importlinter.ini` [MODIFY]

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

### 11. `docs/DECISIONS.md` [MODIFY]

RUN_ID: `2026-01-01__p5-1__audio-alignment`; artifacts v1-v8; scope; SSOT edits.

### 12. `CHANGELOG.md` [MODIFY]

"Added: Audio alignment service for synchronizing comparison clips"

## Acceptance Criteria

- [ ] GIVEN identical signals WHEN `_cross_correlate` THEN offset=0, score≈1.0 (abs=1e-6)
- [ ] GIVEN full cache hit WHEN `align_clips` THEN `_probe_fps` and `_extract_audio` not called
- [ ] GIVEN partial cache hit WHEN `align_clips` THEN only missing comparisons computed
- [ ] GIVEN `align_clips` result THEN order matches input `comparisons`

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v8.md

# Type check
.venv/bin/pyright --warnings src/frame_compare/services src/frame_compare/utils/progress.py

# Lint
.venv/bin/ruff check src/frame_compare/services src/frame_compare/utils/progress.py

# Tests
.venv/bin/pytest -v tests/services/ tests/utils/

# Import contract
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0.

## Rollback / Stop Conditions

- **If lint-imports fails:** STOP and return to Planning.

## Notes for Coding Agent

1. **Create progress.py FIRST**
2. **Async tests** — Use `@pytest.mark.anyio`
3. **Output ordering** — Result list MUST match input `comparisons` order
4. **Cache behavior** — Full hit skips all ffprobe/ffmpeg
5. **Tolerance** — Use `pytest.approx(..., abs=1e-6)` for correlation scores

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p5-1__audio-alignment

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v8.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v9.md
