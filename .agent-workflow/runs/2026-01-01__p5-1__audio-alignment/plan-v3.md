---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v3
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v2.md
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v3.md
---

# Implementation Plan: Audio Alignment Service

## Changes Since plan-v2

1. **Updated SSOT (Section 2.2 Public API):** Added `load_cached_offsets` semantics: clips[0] = reference, clips[1:] = comparisons, matching semantics, returns `{}` when cache exists but no requested keys found.
2. **Added dependency files:** `src/frame_compare/utils/progress.py` and `__init__.py` export update (ProgressReporter does not exist in repo).
3. **Added `_probe_fps` unit tests:** Parsing `"24000/1001"`, `"24"`, and error mapping.
4. **Made cache tests deterministic:** Added concrete TOML fixture and exact expected `AlignmentResult` values.

## Context

**Phase:** 5 (Services)
**Module:** `frame_compare.services`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` (Section 2)
**Dependencies:** Phase 4 complete (render module), `AudioAlignmentError` exists in `errors.py`

## Scope

This plan covers:

- [x] Create `src/frame_compare/utils/progress.py` with `ProgressReporter` protocol (dependency)
- [x] Update `src/frame_compare/utils/__init__.py` to export `ProgressReporter`
- [x] Create `src/frame_compare/services/__init__.py` with public exports
- [x] Create `src/frame_compare/services/types.py` with alignment types
- [x] Create `src/frame_compare/services/alignment.py` with audio alignment logic
- [x] Write unit tests for alignment service
- [x] Update `importlinter.ini` to include `frame_compare.services`

This plan does NOT cover:

- Metadata service (5.2)
- Publishers service (5.3)
- Dovi service (5.4)
- Report service (5.5)
- Integration tests with real audio files (deferred to Phase 5 Quality Gate)

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

**Purpose:** ProgressReporter protocol + NullProgressReporter (dependency for services).

**Types to implement (from utils-module.md Section 4.2):**

| Type | Methods |
|------|---------|
| `ProgressReporter(Protocol)` | `start_phase(name: str, total: int)`, `advance(amount: int = 1)`, `set_description(desc: str)`, `complete_phase()` |
| `NullProgressReporter` | No-op implementation of all methods |

### 2. `src/frame_compare/utils/__init__.py` [MODIFY]

**Purpose:** Export `ProgressReporter` and `NullProgressReporter`.

**Add exports:**

```python
from frame_compare.utils.progress import ProgressReporter, NullProgressReporter
```

### 3. `src/frame_compare/services/__init__.py` [NEW]

**Purpose:** Public exports for the services module.

**Exports:**

- `AlignmentResult`
- `AlignmentConfig`
- `align_clips`
- `load_cached_offsets`
- `save_offsets_cache`

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

**Error wrapping (per SSOT Section 2.2):**

| Condition | Exception |
|-----------|-----------|
| FFmpeg/ffprobe not found | `FFmpegNotFoundError` |
| FFmpeg/ffprobe non-zero exit | `FFmpegError(stderr, returncode)` |
| Empty audio track | `AudioAlignmentError(reason="empty audio track in {name}")` |
| Zero-norm signal | `AudioAlignmentError(reason="zero-norm audio signal prevents correlation")` |
| Cache parse failure | `CacheCorruptionError(path)` |
| Cache version mismatch | `CacheVersionMismatchError(found, expected)` |

**Cache format (per SSOT Section 2.3):**

- File: `{cache_dir}/audio_offsets.toml`
- Version field: `version = "1"` (CACHE_VERSION constant)
- Key format: `f"{reference.stem}:{comparison.stem}"`

**load_cached_offsets semantics (per SSOT Section 2.2):**

- `clips[0]` = reference, `clips[1:]` = comparisons
- Return `None` if cache file missing
- Return `{}` if cache valid but no requested keys found
- Return dict of matching keys only

### 6. `tests/services/__init__.py` [NEW]

**Purpose:** Test package marker (empty file).

### 7. `tests/services/test_alignment.py` [NEW]

**Purpose:** Unit tests for alignment service.

**Tests required:**

| Test Name | Input | Expected | Tolerance |
|-----------|-------|----------|-----------|
| `test_alignment_result_is_frozen` | `AlignmentResult(...)` | `FrozenInstanceError` on mutation | N/A |
| `test_alignment_config_defaults` | `AlignmentConfig()` | `enable=True, sample_rate=8000, max_offset_seconds=30.0, use_vspreview=False, cache_results=True` | N/A |
| `test_cross_correlate_identical_signals` | `ref = np.array([1.0, 0.5, 0.0, -0.5])`, `comp = ref.copy()` | `(0, pytest.approx(1.0, abs=1e-6))` | `abs=1e-6` |
| `test_cross_correlate_positive_shift` | `ref = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)`, `comp = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)` | `offset=2` | N/A |
| `test_cross_correlate_negative_shift` | `ref = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)`, `comp = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)` | `offset=-2` | N/A |
| `test_cross_correlate_zero_norm_raises` | `ref = np.zeros(10)`, `comp = np.ones(10)` | `AudioAlignmentError` with "zero-norm" | N/A |
| `test_samples_to_frames_integer_fps` | `offset=8000, rate=8000, fps=Fraction(24,1)` | `24` | N/A |
| `test_samples_to_frames_fractional_fps` | `offset=8008, rate=8000, fps=Fraction(24000,1001)` | `24` | N/A |
| `test_probe_fps_fraction` | mock stdout `"24000/1001\n"` | `Fraction(24000, 1001)` | N/A |
| `test_probe_fps_integer` | mock stdout `"24\n"` | `Fraction(24, 1)` | N/A |
| `test_probe_fps_not_found_raises` | mock `FileNotFoundError` | `FFmpegNotFoundError` | N/A |
| `test_probe_fps_nonzero_exit_raises` | mock returncode=1 | `FFmpegError` | N/A |
| `test_extract_audio_ffmpeg_not_found` | mock `FileNotFoundError` | `FFmpegNotFoundError` | N/A |
| `test_extract_audio_ffmpeg_fails` | mock returncode=1 | `FFmpegError` | N/A |
| `test_extract_audio_empty_raises` | mock empty output | `AudioAlignmentError` with "empty audio" | N/A |
| `test_load_cached_offsets_missing_returns_none` | no file | `None` | N/A |
| `test_load_cached_offsets_valid_returns_dict` | see fixture below | dict with key `"ref:comp_a"` | N/A |
| `test_load_cached_offsets_valid_no_match_returns_empty` | valid TOML, clips=`[other_ref, other_comp]` | `{}` | N/A |
| `test_load_cached_offsets_corruption_raises` | `"not valid toml {{{"` | `CacheCorruptionError` | N/A |
| `test_load_cached_offsets_version_mismatch_raises` | `version = "999"` | `CacheVersionMismatchError` | N/A |
| `test_save_offsets_cache_writes_toml` | `[AlignmentResult(...)]` | file with correct schema | N/A |
| `test_align_clips_uses_cache` | pre-populated cache | no extraction called | N/A |

**Cache test fixture (concrete TOML):**

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

### 8. `importlinter.ini` [MODIFY]

**Purpose:** Add `frame_compare.services` to layer contract.

**Change:** Insert `frame_compare.services` between `frame_compare.render` and `frame_compare.vs`.

### 9. `docs/DECISIONS.md` [MODIFY]

**Required facts to record:**

- RUN_ID: `2026-01-01__p5-1__audio-alignment`
- Artifact versions: plan-v1 through plan-v3, plan-review-v1 through plan-review-v2
- Scope: Audio alignment + ProgressReporter dependency
- SSOT edits: services-module.md 2.2 (load_cached_offsets semantics), 2.3 (FPS, cache, failures)
- Verification gates: pyright, ruff, pytest, lint-imports

### 10. `CHANGELOG.md` [MODIFY]

**Entry:** "Added: Audio alignment service for synchronizing comparison clips"

## Acceptance Criteria

- [ ] GIVEN identical audio signals WHEN calling `_cross_correlate` THEN offset=0, score≈1.0
- [ ] GIVEN comparison shifted +2 samples WHEN calling `_cross_correlate` THEN offset=+2
- [ ] GIVEN zero-norm reference WHEN calling `_cross_correlate` THEN `AudioAlignmentError`
- [ ] GIVEN ffprobe stdout `"24000/1001\n"` WHEN calling `_probe_fps` THEN `Fraction(24000, 1001)`
- [ ] GIVEN cache file missing WHEN calling `load_cached_offsets` THEN `None`
- [ ] GIVEN valid cache but no matching keys WHEN calling `load_cached_offsets` THEN `{}`
- [ ] GIVEN invalid TOML cache WHEN calling `load_cached_offsets` THEN `CacheCorruptionError`

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v3.md

# Type check (includes utils)
.venv/bin/pyright --warnings src/frame_compare/services src/frame_compare/utils/progress.py

# Lint
.venv/bin/ruff check src/frame_compare/services src/frame_compare/utils/progress.py

# Tests
.venv/bin/pytest -v tests/services/

# Import contract
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **ProgressReporter dependency** — Create `progress.py` FIRST before alignment.py
2. **Sync subprocess** — Use `subprocess.run` via `run_subprocess` from utils
3. **Cross-correlation** — SSOT Section 2.3 "Cross-Correlation" defines algorithm and zero-norm handling
4. **Offset sign** — Positive = comp AFTER ref; Negative = comp BEFORE ref
5. **Cache format** — TOML with `version = "1"`, use `tomllib` (read) + manual string (write)
6. **Error imports** — From `frame_compare.errors`
7. **FPS probing** — Parse ffprobe output as `num/den` or `num` → Fraction
8. **Layer ordering** — Services sits between render and vs

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p5-1__audio-alignment

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v3.md
