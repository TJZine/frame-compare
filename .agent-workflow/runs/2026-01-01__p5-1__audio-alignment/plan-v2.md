---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v2
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v1.md
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v2.md
---

# Implementation Plan: Audio Alignment Service

## Changes Since plan-v1

1. **Updated SSOT (Section 2.2 Public API):** Added explicit exception list (`FFmpegNotFoundError`, `FFmpegError`, `AudioAlignmentError`, `CacheCorruptionError`, `CacheVersionMismatchError`), ProgressReporter import reference to `frame_compare.utils.progress`, and cache key semantics.
2. **Updated SSOT (Section 2.3 Implementation Details):** Added FPS Sourcing subsection with `_probe_fps`, Audio Extraction with empty-audio failure, Cross-Correlation with zero-norm failure and offset sign convention, and Cache Schema with TOML format and version field.
3. **Fixed signature format:** Removed `def`/`async def` prefixes from Public API bullets per validator requirements.
4. **Eliminated "if exists" branches:** ProgressReporter import source is now explicit (`frame_compare.utils.progress`).
5. **Added deterministic test vectors:** Specified exact input arrays, expected offsets (including sign), and `pytest.approx` tolerances.
6. **Added `_probe_fps` internal function:** Required to obtain FPS without violating import layering.

## Context

**Phase:** 5 (Services)
**Module:** `frame_compare.services`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` (Section 2)
**Dependencies:** Phase 4 complete (render module), `AudioAlignmentError` already exists in `errors.py`, `ProgressReporter` exists in `frame_compare.utils.progress`

## Scope

This plan covers:

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

No changes to canonical contracts under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`.

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

### 1. `src/frame_compare/services/__init__.py` [NEW]

**Purpose:** Public exports for the services module.

**Exports:**

- `AlignmentResult`
- `AlignmentConfig`
- `align_clips`
- `load_cached_offsets`
- `save_offsets_cache`

### 2. `src/frame_compare/services/types.py` [NEW]

**Purpose:** Service-specific data types (reusable across services).

**Types to define (copy SSOT code blocks from spec Section 2.1):**

| Type | Fields |
|------|--------|
| `AlignmentResult` (frozen dataclass) | `reference_clip: str`, `comparison_clip: str`, `frame_offset: int`, `time_offset_seconds: float`, `correlation_score: float`, `method: str` |
| `AlignmentConfig` (frozen dataclass) | `enable: bool = True`, `sample_rate: int = 8000`, `max_offset_seconds: float = 30.0`, `use_vspreview: bool = False`, `cache_results: bool = True` |

### 3. `src/frame_compare/services/alignment.py` [NEW]

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

**Imports:**

- `from frame_compare.utils.progress import ProgressReporter`
- `from frame_compare.utils.subproc import run_subprocess`
- `from frame_compare.errors import ...`

### 4. `tests/services/__init__.py` [NEW]

**Purpose:** Test package marker (empty file).

### 5. `tests/services/test_alignment.py` [NEW]

**Purpose:** Unit tests for alignment service.

**Tests required:**

| Test Name | Input | Expected | Tolerance |
|-----------|-------|----------|-----------|
| `test_alignment_result_is_frozen` | `AlignmentResult(...)` | `FrozenInstanceError` on mutation | N/A |
| `test_alignment_config_defaults` | `AlignmentConfig()` | `enable=True`, `sample_rate=8000`, `max_offset_seconds=30.0`, `use_vspreview=False`, `cache_results=True` | N/A |
| `test_cross_correlate_identical_signals` | `ref = np.array([1.0, 0.5, 0.0, -0.5])`, `comp = ref.copy()` | `(offset=0, score=pytest.approx(1.0, abs=1e-6))` | `abs=1e-6` |
| `test_cross_correlate_positive_shift` | `ref = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)`, `comp = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)` | `offset=2` (positive = comp AFTER ref) | N/A |
| `test_cross_correlate_negative_shift` | `ref = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)`, `comp = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)` | `offset=-2` (negative = comp BEFORE ref) | N/A |
| `test_cross_correlate_zero_norm_raises` | `ref = np.zeros(10, dtype=np.float32)`, `comp = np.array([1.0]*10)` | `AudioAlignmentError` with "zero-norm" in reason | N/A |
| `test_samples_to_frames_converts_correctly` | `sample_offset=8000, sample_rate=8000, fps=Fraction(24, 1)` | `24` (1 second × 24 fps) | N/A |
| `test_samples_to_frames_fractional_fps` | `sample_offset=8008, sample_rate=8000, fps=Fraction(24000, 1001)` | `round(1.001 * 23.976) = 24` | N/A |
| `test_extract_audio_ffmpeg_not_found_raises` | mock `FileNotFoundError` | `FFmpegNotFoundError` | N/A |
| `test_extract_audio_ffmpeg_fails_raises` | mock non-zero exit | `FFmpegError` with returncode | N/A |
| `test_extract_audio_empty_raises` | mock empty output | `AudioAlignmentError` with "empty audio" in reason | N/A |
| `test_load_cached_offsets_returns_none_when_missing` | no cache file | `None` | N/A |
| `test_load_cached_offsets_returns_cached_results` | valid TOML with version="1" | Dict with correct key format | N/A |
| `test_load_cached_offsets_corruption_raises` | invalid TOML | `CacheCorruptionError` | N/A |
| `test_load_cached_offsets_version_mismatch_raises` | version="999" | `CacheVersionMismatchError` | N/A |
| `test_save_offsets_cache_writes_toml` | `[AlignmentResult(...)]` | File exists with correct schema | N/A |
| `test_align_clips_uses_cache_when_available` | pre-populated cache | No extraction called | N/A |

### 6. `importlinter.ini` [MODIFY]

**Purpose:** Add `frame_compare.services` to layer contract.

**Change:** Insert `frame_compare.services` into the layers list (between `frame_compare.render` and `frame_compare.vs`).

### 7. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2026-01-01__p5-1__audio-alignment`
- Artifact versions: plan-v1, plan-review-v1, plan-v2
- Scope: Audio alignment service types and implementation
- SSOT edits: Updated services-module.md sections 2.2 and 2.3 with exception list, ProgressReporter reference, cache semantics, FPS sourcing, failure modes
- Verification gates: pyright, ruff, pytest, lint-imports

### 8. `CHANGELOG.md` [MODIFY]

**Purpose:** Add entry for new services module.

**Entry:** Under Unreleased, add "Added: Audio alignment service for synchronizing comparison clips"

## Acceptance Criteria

- [ ] GIVEN identical audio signals WHEN calling `_cross_correlate` THEN offset=0 and score≈1.0 (within 1e-6)
- [ ] GIVEN comparison shifted +2 samples WHEN calling `_cross_correlate` THEN offset=+2
- [ ] GIVEN comparison shifted -2 samples WHEN calling `_cross_correlate` THEN offset=-2
- [ ] GIVEN zero-norm reference WHEN calling `_cross_correlate` THEN `AudioAlignmentError` with "zero-norm" in reason
- [ ] GIVEN FFmpeg not in PATH WHEN calling `_extract_audio` THEN `FFmpegNotFoundError` is raised
- [ ] GIVEN FFmpeg returns empty output WHEN calling `_extract_audio` THEN `AudioAlignmentError` with "empty audio" in reason
- [ ] GIVEN invalid TOML cache WHEN calling `load_cached_offsets` THEN `CacheCorruptionError`
- [ ] GIVEN version mismatch cache WHEN calling `load_cached_offsets` THEN `CacheVersionMismatchError`
- [ ] GIVEN valid cache file WHEN calling `load_cached_offsets` THEN dict returned with correct keys

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v2.md

# Type check
.venv/bin/pyright --warnings src/frame_compare/services

# Lint
.venv/bin/ruff check src/frame_compare/services

# Tests
.venv/bin/pytest -v tests/services/

# Import contract
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **numpy dependency** — `numpy` is already a runtime dependency in `pyproject.toml`
2. **Sync subprocess** — Use `subprocess.run` (via `run_subprocess` from utils) with `stdout=PIPE` for FFmpeg/ffprobe extraction
3. **Cross-correlation formula** — SSOT Section 2.3 "Cross-Correlation" provides the exact algorithm and zero-norm handling
4. **Offset sign convention** — Positive = comparison AFTER reference; Negative = comparison BEFORE reference
5. **Cache file format** — Use TOML with `tomllib` (read) and manual string formatting or `tomli_w` (write); include `version = "1"`
6. **Error imports** — Import `AudioAlignmentError`, `FFmpegError`, `FFmpegNotFoundError`, `CacheCorruptionError`, `CacheVersionMismatchError` from `frame_compare.errors`
7. **ProgressReporter** — Import from `frame_compare.utils.progress` (already exists per utils-module.md)
8. **Fraction import** — `from fractions import Fraction` for FPS
9. **FPS probing** — Use `_probe_fps` with ffprobe to avoid importing render/vs modules
10. **Layer ordering** — Services layer sits between render and vs in the import hierarchy

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p5-1__audio-alignment

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v2.md
