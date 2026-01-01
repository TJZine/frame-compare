---
RUN_ID: 2026-01-01__p4-5__encoders
VERSION: v4
TARGET: Phase 4 → Item 4.5
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v4.md
---

# Implementation Plan: Render Encoders (v4)

## Changes Since plan-v3

- **Public API:** Removed `RenderError` from `src/frame_compare/render/__init__.py` export list (SSOT compliance).
- **Test Logic:** Aligned dispatch tests with SSOT; now uses `request.clip` type (FakeClip vs Path) instead of `sys.modules` mocking.
- **Assertions:** Fixed error wrapping tests to assert on Python's `__cause__` attribute.
- **Tolerances:** Pinned `_probe_fps` float expectations using `pytest.approx(..., rel=1e-6)`.
- **Criteria:** Clarified Verification Command pass criteria (exit 0 / No violations).

## Context

**Phase:** 4 (Render Module)
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:**

- Phase 4.1 (Types) - `RenderRequest`, `EncoderSettings`
- Phase 4.4 (Overlay) - `apply_overlay`
- Phase 3.1 (VS Env) - `vs.Core`

## Scope

This plan covers:

- [ ] `src/frame_compare/render/encoders.py` (Public API + VS/FFmpeg impl)
- [ ] `src/frame_compare/render/__init__.py` (Export public API)
- [ ] `src/frame_compare/utils/subproc.py` (Secure subprocess wrapper)
- [ ] Unit tests for encoders, fallback logic, and subprocess wrapper

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: “3.1 Frame Rendering” (Dispatch behavior & Overlay integration)
  - Section: “4.1 VapourSynth Rendering”
  - Section: “4.2 FFmpeg Rendering” (Seek time calculation & Exceptions)
  - Section: “6. Error Handling”

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`:
  - Section: “4.5 Subprocess Wrapper” (Strict raises contract)

## Files to Create/Modify

### 1. `src/frame_compare/utils/subproc.py` (NEW)

**Purpose:** Secure subprocess wrapper.

**Functions to implement:**

- `run_subprocess(argv: Sequence[str], *, timeout_seconds: float | None = None, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]`
  - *Spec:* `utils-module.md` Section 4.5
  - *Raises:* `FileNotFoundError`, `subprocess.TimeoutExpired`, `subprocess.CalledProcessError`.

### 2. `src/frame_compare/render/encoders.py` (NEW)

**Purpose:** Screenshot generation strategies.

**Error Mapping Strategy:**

| Failure Mode | Internal Exception (Raised by helper) | Public Exception (Propagated by render_frame) |
| :--- | :--- | :--- |
| `vs.VideoNode` vs `Path` mismatch | `FrameExtractionError (FC-4001)` | `FrameExtractionError (FC-4001)` |
| `ffmpeg`/`ffprobe` binary missing | `FFmpegNotFoundError (FC-2005)` | `RenderError (FC-4004)` (wrapped) |
| `ffmpeg` non-zero exit | `FFmpegError (FC-2006)` | `RenderError (FC-4004)` (wrapped) |
| `ffprobe` fail/bad output | `SourceLoadError (FC-4015)` | `RenderError (FC-4004)` (wrapped) |
| Overlay application fails | `OverlayError (FC-4014)` | `RenderError (FC-4004)` (wrapped) |
| Image save fails | `EncodingError (FC-4013)` | `RenderError (FC-4004)` (wrapped) |
| Generic VS/Python error | `Exception` | `RenderError (FC-4004)` (wrapped) |

**Functions to implement:**

- `render_frame(request: RenderRequest, renderer: Renderer = "auto") -> Path`
  - *Spec:* `render-module.md` Section 3.1
  - *Dispatch Logic:*
    - If `request.clip` is `Path` -> use FFmpeg path.
    - If `request.clip` is not `Path` (assume VS node) -> use VS path.
    - Handle `renderer` overrides: if mismatch with type -> raise `FrameExtractionError`.
  - *Error Handling:* Wrap all internal renderer exceptions (except `FrameExtractionError`) into `RenderError`. Attach original exception as `__cause__`.

- `_render_vs(clip: vs.VideoNode, frame: int, output: Path, settings: EncoderSettings) -> None`
  - *Spec:* `render-module.md` Section 4.1
  - *Steps:* `clip.get_frame` -> `np` -> `PIL` -> `apply_overlay` -> save.

- `_render_ffmpeg(video_path: Path, frame: int, output: Path, settings: EncoderSettings, timeout: int = 30) -> None`
  - *Spec:* `render-module.md` Section 4.2
  - *Determinism:* `seek_seconds = floor((frame / fps) * 1000) / 1000`.
  - *Failure Handling:*
    - Catch `FileNotFoundError` -> raise `FFmpegNotFoundError`.
    - Catch `CalledProcessError` (from ffmpeg) -> raise `FFmpegError`.
    - Catch `CalledProcessError` (from probe) / ValueError -> raise `SourceLoadError`.

- `_probe_fps(video_path: Path) -> float`
  - *Steps:* Run `ffprobe` (via `run_subprocess`). Parse `avg_frame_rate`.
  - *Parsing:* standard "num/den" or float string. if fail -> raise `SourceLoadError`.

### 3. `src/frame_compare/render/__init__.py` (MODIFY)

**Purpose:** Export `render_frame` only.

### 4. `tests/utils/test_subproc.py` (NEW)

**Test Assertions:**

- `test_run_subprocess_check_true`: Assert usage of `check=True` defaults.
- `test_run_subprocess_failure`: Assert `subprocess.CalledProcessError` raised on exit 1.
- `test_run_subprocess_timeout`: Assert `subprocess.TimeoutExpired` raised.
- `test_run_subprocess_not_found`: Assert `FileNotFoundError` raised when bin missing.

### 5. `tests/render/test_encoders.py` (NEW)

**Test Assertions:**

- `test_render_frame_vs_dispatch`:
  - Input: `request.clip` = `FakeClip()` (generic object/mock). `renderer='auto'`.
  - Assert: `_render_vs` called.
- `test_render_frame_ffmpeg_dispatch`:
  - Input: `request.clip` = `Path("test.mp4")`. `renderer='auto'`.
  - Assert: `_render_ffmpeg` called.
- `test_render_frame_mismatch_error`: Assert `FrameExtractionError` (code FC-4001) raised.
- `test_ffmpeg_seek_calculation`:
  - Input: frame=100, fps=23.976 (24000/1001).
  - Expected Seek: `floor((100 / 23.97602...) * 1000) / 1000` = `4.170`.
  - Assert `run_subprocess` called with `["ffmpeg", "-ss", "4.170", ...]`.
- `test_error_wrapping`:
  - Sim: `_render_ffmpeg` raises `FFmpegNotFoundError`.
  - Assert: `with pytest.raises(RenderError) as excinfo: ...`
  - Assert: `isinstance(excinfo.value.__cause__, FFmpegNotFoundError)` is True.
- `test_probe_fps_logic`:
  - Sim: stdout `24000/1001\n`. Assert returns `pytest.approx(23.976023, rel=1e-6)`.
  - Sim: stdout `invalid`. Assert raises `SourceLoadError` (FC-4015).

## Verification Commands

**Acceptance Criteria:**

- `pyright`: Exits 0.
- `ruff`: Exits 0.
- `pytest`: Exits 0.
- `lint-imports`: Exits 0 (No violations).

```bash
.venv/bin/pyright --warnings src/frame_compare/render src/frame_compare/utils
.venv/bin/ruff check src/frame_compare/render src/frame_compare/utils
.venv/bin/pytest -v tests/render tests/utils
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-5__encoders

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v4.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v4.md
