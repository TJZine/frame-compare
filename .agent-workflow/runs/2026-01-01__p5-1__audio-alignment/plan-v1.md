---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v1
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v1.md
---

# Implementation Plan: Audio Alignment Service

## Context

**Phase:** 5 (Services)
**Module:** `frame_compare.services`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` (Section 2)
**Dependencies:** Phase 4 complete (render module), `AudioAlignmentError` already exists in `errors.py`

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
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md`:
  - Section: "2.2 Exception Tree" (AudioAlignmentError FC-4005)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md`:
  - Section: "1. Timeout Policy"
  - Section: "7. HTTP Client Lifecycle Rules"
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

**Public API (signatures from spec Section 2.2):**

- `async def align_clips(reference: Path, comparisons: list[Path], config: AlignmentConfig, cache_dir: Path, progress: ProgressReporter | None = None) -> list[AlignmentResult]`
- `def load_cached_offsets(cache_dir: Path, clips: list[Path]) -> dict[str, AlignmentResult] | None`
- `def save_offsets_cache(cache_dir: Path, results: list[AlignmentResult]) -> None`

**Internal functions (from spec Section 2.3):**

- `def _extract_audio(video_path: Path, sample_rate: int) -> np.ndarray` — calls FFmpeg: `ffmpeg -i {video} -vn -ac 1 -ar {sample_rate} -f f32le -`
- `def _cross_correlate(reference: np.ndarray, comparison: np.ndarray) -> tuple[int, float]` — uses `np.correlate` mode='full'
- `def _samples_to_frames(sample_offset: int, sample_rate: int, fps: Fraction) -> int` — converts sample offset to frame offset

**FFmpeg error wrapping:**

- `subprocess.CalledProcessError` with non-zero exit → raise `FFmpegError(stderr, returncode)`
- `FileNotFoundError` (ffmpeg not in PATH) → raise `FFmpegNotFoundError()`

**Cache format:** `audio_offsets.toml` in `cache_dir`, keyed by reference/comparison path pairs.

### 4. `tests/services/__init__.py` [NEW]

**Purpose:** Test package marker (empty file).

### 5. `tests/services/test_alignment.py` [NEW]

**Purpose:** Unit tests for alignment service.

**Tests required:**

- `test_alignment_result_is_frozen` — verify `AlignmentResult` is immutable
- `test_alignment_config_defaults` — verify default values match spec
- `test_cross_correlate_identical_signals_returns_zero_offset` — identical input → offset=0, score≈1.0
- `test_cross_correlate_shifted_signals_returns_correct_offset` — known shift detected
- `test_samples_to_frames_converts_correctly` — deterministic conversion
- `test_extract_audio_calls_ffmpeg_correctly` — mock subprocess, verify args
- `test_extract_audio_ffmpeg_not_found_raises` — mock FileNotFoundError → `FFmpegNotFoundError`
- `test_extract_audio_ffmpeg_fails_raises` — mock non-zero exit → `FFmpegError`
- `test_load_cached_offsets_returns_none_when_missing` — no cache file returns None
- `test_load_cached_offsets_returns_cached_results` — valid cache file parsed correctly
- `test_save_offsets_cache_writes_toml` — results stored correctly
- `test_align_clips_uses_cache_when_available` — cache hit skips extraction

### 6. `importlinter.ini` [MODIFY]

**Purpose:** Add `frame_compare.services` to layer contract.

**Change:** Insert `frame_compare.services` into the layers list (between `frame_compare.render` and `frame_compare.vs`).

### 7. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2026-01-01__p5-1__audio-alignment`
- Scope: Audio alignment service types and implementation
- SSOT edits: None
- Verification gates: pyright, ruff, pytest, lint-imports

### 8. `CHANGELOG.md` [MODIFY]

**Purpose:** Add entry for new services module.

**Entry:** Under Unreleased, add "Added: Audio alignment service for synchronizing comparison clips"

## Acceptance Criteria

- [ ] GIVEN a reference and comparison audio with known offset WHEN calling `_cross_correlate` THEN the offset is detected within ±1 sample
- [ ] GIVEN identical audio signals WHEN calling `_cross_correlate` THEN score ≈ 1.0 and offset = 0
- [ ] GIVEN FFmpeg not in PATH WHEN calling `_extract_audio` THEN `FFmpegNotFoundError` is raised
- [ ] GIVEN FFmpeg fails WHEN calling `_extract_audio` THEN `FFmpegError` is raised with stderr/returncode
- [ ] GIVEN valid cache file WHEN calling `load_cached_offsets` THEN cached results are returned
- [ ] GIVEN no cache file WHEN calling `load_cached_offsets` THEN None is returned

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v1.md

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
2. **Sync subprocess** — Use `subprocess.run` with `stdout=PIPE` for FFmpeg extraction (the public `align_clips` is async, but `_extract_audio` itself is sync per spec)
3. **Cross-correlation formula** — Spec Section 2.3 provides the exact algorithm:
   - `correlation = np.correlate(reference, comparison, mode='full')`
   - `peak_idx = np.argmax(correlation)`
   - `offset = peak_idx - len(reference) + 1`
   - `score = correlation[peak_idx] / (norm(ref) * norm(comp))`
4. **Cache file format** — Use TOML with tomllib (read) and tomli_w or manual string (write)
5. **Error imports** — Import `AudioAlignmentError`, `FFmpegError`, `FFmpegNotFoundError` from `frame_compare.errors`
6. **ProgressReporter** — Import from `frame_compare.utils.progress` if it exists, otherwise use `Protocol` stub
7. **Fraction import** — `from fractions import Fraction` for FPS conversion
8. **Layer ordering** — Services layer sits between render and vs in the import hierarchy

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p5-1__audio-alignment

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v1.md
