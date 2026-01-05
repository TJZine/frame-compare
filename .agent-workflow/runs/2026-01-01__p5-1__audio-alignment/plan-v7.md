---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v7
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v6.md
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v6.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v7.md
---

# Implementation Plan: Audio Alignment Service

## Changes Since plan-v6

1. **Added async cache semantics tests:** Two new `@pytest.mark.anyio` tests for `align_clips` validating full-cache-hit (skips ffprobe/ffmpeg) and partial-cache-hit (computes only missing, preserves order).

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
- [x] Write unit tests for alignment service (including async cache tests)
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

- `ProgressReporter(Protocol)` — `start_phase`, `advance`, `set_description`, `complete_phase`
- `NullProgressReporter` — No-op
- `RichProgressReporter` — Uses rich.progress.Progress
- `LogProgressReporter` — Uses structlog at milestone %

### 2. `src/frame_compare/utils/__init__.py` [MODIFY]

Add imports and `__all__` entries for: `ProgressReporter`, `NullProgressReporter`, `RichProgressReporter`, `LogProgressReporter`.

### 3. `src/frame_compare/services/__init__.py` [NEW]

Exports: `AlignmentResult`, `AlignmentConfig`, `align_clips`, `load_cached_offsets`, `save_offsets_cache`.

### 4. `src/frame_compare/services/types.py` [NEW]

- `AlignmentResult` (frozen dataclass)
- `AlignmentConfig` (frozen dataclass)

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

- `test_null_progress_reporter_noops`
- `test_rich_progress_reporter_smoke`
- `test_log_progress_reporter_smoke`

### 8. `tests/services/__init__.py` [NEW]

Empty test package marker.

### 9. `tests/services/test_alignment.py` [NEW]

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

**Sync unit tests (same as plan-v6):**

- `test_alignment_result_is_frozen`
- `test_alignment_config_defaults`
- `test_cross_correlate_identical_signals` — `pytest.approx(1.0, abs=1e-6)`
- `test_cross_correlate_positive_shift` — offset=2
- `test_cross_correlate_negative_shift` — offset=-2
- `test_cross_correlate_zero_norm_raises`
- `test_samples_to_frames_integer_fps`
- `test_samples_to_frames_fractional_fps`
- `test_probe_fps_fraction`
- `test_probe_fps_integer`
- `test_probe_fps_not_found_raises`
- `test_probe_fps_nonzero_exit_raises`
- `test_extract_audio_ffmpeg_not_found`
- `test_extract_audio_ffmpeg_fails`
- `test_extract_audio_empty_raises`
- `test_load_cached_offsets_missing_returns_none`
- `test_load_cached_offsets_valid_returns_dict`
- `test_load_cached_offsets_valid_no_match_returns_empty`
- `test_load_cached_offsets_corruption_raises`
- `test_load_cached_offsets_version_mismatch_raises`
- `test_save_offsets_cache_writes_toml`
- `test_align_clips_uses_cache` (sync mock test)

**NEW: Async cache semantics tests:**

| Test Name | Setup | Assertions |
|-----------|-------|------------|
| `test_align_clips_full_cache_hit_skips_probe_and_extract` | `@pytest.mark.anyio`; `reference = tmp_path / "ref.mkv"`, `comparisons = [tmp_path / "comp_a.mkv", tmp_path / "comp_b.mkv"]`; write cache with BOTH keys `"ref:comp_a"` (offset=10) and `"ref:comp_b"` (offset=20); patch `_probe_fps` and `_extract_audio` to fail if called | `assert len(result) == 2`; `assert result[0].comparison_clip == "comp_a.mkv"`; `assert result[0].frame_offset == 10`; `assert result[1].comparison_clip == "comp_b.mkv"`; `assert result[1].frame_offset == 20`; assert `_probe_fps.call_count == 0`; assert `_extract_audio.call_count == 0` |
| `test_align_clips_partial_cache_hit_computes_only_missing_and_preserves_order` | `@pytest.mark.anyio`; same paths; cache contains ONLY `"ref:comp_a"` (offset=10); patch `_probe_fps` to return `Fraction(24, 1)`; patch `_extract_audio` with spy; patch `_cross_correlate` to return `(0, 0.99)` | `assert len(result) == 2`; `assert result[0].comparison_clip == "comp_a.mkv"` (cached); `assert result[0].frame_offset == 10`; `assert result[1].comparison_clip == "comp_b.mkv"` (computed); `_extract_audio` called for ref and comp_b but NOT comp_a; assert order preserved |

### 10. `importlinter.ini` [MODIFY]

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

RUN_ID, artifacts v1-v7, SSOT edits.

### 12. `CHANGELOG.md` [MODIFY]

"Added: Audio alignment service for synchronizing comparison clips"

## Acceptance Criteria

- [ ] GIVEN full cache hit WHEN calling `align_clips` THEN `_probe_fps` and `_extract_audio` not called
- [ ] GIVEN partial cache hit WHEN calling `align_clips` THEN only missing comparisons computed
- [ ] GIVEN `align_clips` result THEN `len(result) == len(comparisons)` and order preserved

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v7.md

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
2. **Async tests** — Use `@pytest.mark.anyio` for `align_clips` tests
3. **Mock patching** — Use `unittest.mock.patch` or `pytest-mock` to spy/stub internal functions
4. **Output ordering** — Result list MUST match input `comparisons` order
5. **Cache behavior** — Full hit skips all ffprobe/ffmpeg; partial hit computes only missing

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p5-1__audio-alignment

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v7.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v7.md
