---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v6
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v5.md
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v5.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v6.md
---

# Implementation Plan: Audio Alignment Service

## Changes Since plan-v5

1. **Updated SSOT (Section 2.2 Public API):** Added output ordering guarantee (same order as input `comparisons`) and cache behavior (full hit/partial hit/miss).
2. **Made tests mechanically checkable:** Added concrete TOML fixture, exact expected `AlignmentResult`, and explicit `pytest.approx` tolerances.

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

**Types to implement (from utils-module.md Section 4.2):**

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

**Output ordering (SSOT):** Returned `list[AlignmentResult]` is in the same order as input `comparisons`.

**Cache behavior (SSOT):**

- Full cache hit: return cached results without ffprobe/ffmpeg
- Partial hit: compute only missing, return combined in `comparisons` order
- Cache miss: compute all, cache results

### 6. `tests/utils/__init__.py` [NEW]

**Purpose:** Test package marker (empty file).

### 7. `tests/utils/test_progress.py` [NEW]

**Tests required:**

| Test Name | Input | Expected |
|-----------|-------|----------|
| `test_null_progress_reporter_noops` | `NullProgressReporter()` → call all 4 methods | No exception |
| `test_rich_progress_reporter_smoke` | `RichProgressReporter()` → all methods | No exception |
| `test_log_progress_reporter_smoke` | `LogProgressReporter()` → all methods | No exception |

### 8. `tests/services/__init__.py` [NEW]

**Purpose:** Test package marker (empty file).

### 9. `tests/services/test_alignment.py` [NEW]

**Purpose:** Unit tests for alignment service.

**Concrete cache test fixture:**

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

**Tests with exact assertions:**

| Test Name | Input | Expected Assertion |
|-----------|-------|-------------------|
| `test_alignment_result_is_frozen` | `AlignmentResult(...)`, mutation | `FrozenInstanceError` |
| `test_alignment_config_defaults` | `AlignmentConfig()` | `assert cfg.enable is True`, `assert cfg.sample_rate == 8000`, etc. |
| `test_cross_correlate_identical_signals` | `ref = comp = np.array([1.0, 0.5, 0.0, -0.5], dtype=np.float32)` | `assert offset == 0`, `assert score == pytest.approx(1.0, abs=1e-6)` |
| `test_cross_correlate_positive_shift` | `ref = np.array([0,0,1,2,3,0,0], dtype=np.float32)`, `comp = np.array([0,0,0,0,1,2,3], dtype=np.float32)` | `assert offset == 2` |
| `test_cross_correlate_negative_shift` | `ref = np.array([0,0,0,0,1,2,3], dtype=np.float32)`, `comp = np.array([0,0,1,2,3,0,0], dtype=np.float32)` | `assert offset == -2` |
| `test_cross_correlate_zero_norm_raises` | `ref = np.zeros(10)`, `comp = np.ones(10)` | `AudioAlignmentError`, `"zero-norm" in str(exc)` |
| `test_samples_to_frames_integer_fps` | `8000, 8000, Fraction(24,1)` | `assert result == 24` |
| `test_samples_to_frames_fractional_fps` | `8008, 8000, Fraction(24000,1001)` | `assert result == 24` |
| `test_probe_fps_fraction` | mock stdout `"24000/1001\n"` | `assert result == Fraction(24000, 1001)` |
| `test_probe_fps_integer` | mock stdout `"24\n"` | `assert result == Fraction(24, 1)` |
| `test_probe_fps_not_found_raises` | mock `FileNotFoundError` | `FFmpegNotFoundError` |
| `test_probe_fps_nonzero_exit_raises` | mock returncode=1 | `FFmpegError` |
| `test_extract_audio_ffmpeg_not_found` | mock `FileNotFoundError` | `FFmpegNotFoundError` |
| `test_extract_audio_ffmpeg_fails` | mock returncode=1 | `FFmpegError` |
| `test_extract_audio_empty_raises` | mock empty output | `AudioAlignmentError`, `"empty audio" in str(exc)` |
| `test_load_cached_offsets_missing_returns_none` | no file | `assert result is None` |
| `test_load_cached_offsets_valid_returns_dict` | TOML fixture above | `assert "ref:comp_a" in result`, `assert result["ref:comp_a"].frame_offset == 42` |
| `test_load_cached_offsets_valid_no_match_returns_empty` | valid TOML, clips=`[Path("other"), Path("x")]` | `assert result == {}` |
| `test_load_cached_offsets_corruption_raises` | `"not valid toml {{{"` | `CacheCorruptionError` |
| `test_load_cached_offsets_version_mismatch_raises` | `version = "999"` | `CacheVersionMismatchError` |
| `test_save_offsets_cache_writes_toml` | `[AlignmentResult(...)]` | `assert cache_file.exists()`, `assert 'version = "1"' in content`, `assert '["ref:comp"]' in content` |
| `test_align_clips_uses_cache` | pre-populated cache | mock `_extract_audio` not called |

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

**Required facts:** RUN_ID, artifacts v1-v6, scope, SSOT edits (output ordering, cache behavior).

### 12. `CHANGELOG.md` [MODIFY]

**Entry:** "Added: Audio alignment service for synchronizing comparison clips"

## Acceptance Criteria

- [ ] GIVEN identical audio signals WHEN calling `_cross_correlate` THEN offset=0, score≈1.0 (abs=1e-6)
- [ ] GIVEN shifted arrays WHEN calling `_cross_correlate` THEN offset matches shift direction
- [ ] GIVEN valid cache with all keys WHEN calling `align_clips` THEN no ffprobe/ffmpeg called
- [ ] GIVEN partial cache WHEN calling `align_clips` THEN only missing computed
- [ ] GIVEN `align_clips` result THEN `len(result) == len(comparisons)` and order matches

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v6.md

# Type check
.venv/bin/pyright --warnings src/frame_compare/services src/frame_compare/utils/progress.py

# Lint
.venv/bin/ruff check src/frame_compare/services src/frame_compare/utils/progress.py

# Tests
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
2. **Output ordering** — Result list must match input `comparisons` order (1:1)
3. **Cache behavior** — Full hit skips ffprobe/ffmpeg; partial hit computes only missing
4. **Offset sign** — Positive = comp AFTER ref; Negative = comp BEFORE ref
5. **Tolerance** — Use `pytest.approx(..., abs=1e-6)` for correlation scores

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p5-1__audio-alignment

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v6.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v6.md
