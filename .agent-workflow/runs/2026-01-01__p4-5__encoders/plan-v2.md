---
RUN_ID: 2026-01-01__p4-5__encoders
VERSION: v2
TARGET: Phase 4 → Item 4.5
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v2.md
---

# Implementation Plan: Render Encoders (v2)

## Changes Since plan-v1

- **SSOT Alignment:** Anchored `run_subprocess` to updated `utils-module.md` (Section 4.5).
- **Public API:** Added `src/frame_compare/render/__init__.py` to export `render_frame`.
- **Error Handling:** Explicitly mapped errors to `FrameExtractionError` / `RenderError` as per updated SSOT.
- **Dispatch Logic:** Defined strict dispatch rules for `vs.VideoNode` vs `Path` in `render_frame`.
- **FFmpeg Determinism:** Removed `settings.fps` inference; mandated `_probe_fps` and deterministic seek rounding.
- **Verification:** Added `lint-imports` gate.

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
  - Section: “3.1 Frame Rendering” (Dispatch behavior)
  - Section: “4.1 VapourSynth Rendering”
  - Section: “4.2 FFmpeg Rendering” (Seek time calculation)
  - Section: “6. Error Handling”

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`:
  - Section: “4.5 Subprocess Wrapper”

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: “3.2 Dependency Errors (FC-2xxx) — Exit Code 3”
  - Section: “3.4 Processing Errors (FC-4xxx) — Exit Code 5”

## Files to Create/Modify

### 1. `src/frame_compare/utils/subproc.py` (NEW)

**Purpose:** Secure subprocess wrapper.

**Functions to implement (spec-anchored):**

- `run_subprocess(argv: Sequence[str], *, timeout_seconds: float | None = None, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]`
  - *Spec:* `utils-module.md` Section 4.5
  - *Raises:* `FileNotFoundError`, `subprocess.TimeoutExpired`, `subprocess.CalledProcessError`.

### 2. `src/frame_compare/render/encoders.py` (NEW)

**Purpose:** Screenshot generation strategies.

**Functions to implement:**

- `render_frame(request: RenderRequest, renderer: Renderer = "auto") -> Path`
  - *Spec:* `render-module.md` Section 3.1
  - *Dispatch Logic:*
    - `vapoursynth`: Requires `vs.VideoNode`; calls `_render_vs`. Raises `FrameExtractionError` if `request.clip` is Path.
    - `ffmpeg`: Requires `Path`; calls `_render_ffmpeg`. Raises `FrameExtractionError` if `request.clip` is VideoNode.
    - `auto`: If `request.clip` is `vs.VideoNode` → `_render_vs`. If `Path` → `_render_ffmpeg`.
  - *Overlay Logic:* Ensure `apply_overlay` is called before save if `request.overlay` is set.
  - *Error Wrapping:* Catch renderer-specific errors and wrap in `RenderError` (FC-4004) or `FrameExtractionError` (FC-4001).

- `_render_vs(clip: vs.VideoNode, frame: int, output: Path, settings: EncoderSettings) -> None`
  - *Spec:* `render-module.md` Section 4.1

- `_render_ffmpeg(video_path: Path, frame: int, output: Path, settings: EncoderSettings, timeout: int = 30) -> None`
  - *Spec:* `render-module.md` Section 4.2
  - *Determinism:* Use strict `seek_seconds = floor((frame / fps) * 1000) / 1000` logic for timestamps.
  - *FPS:* Must use `_probe_fps` (do not rely on `settings.fps`).

- `_probe_fps(video_path: Path) -> float`
  - *Behavior:* helper ensuring `run_subprocess` is used to call `ffprobe`.

### 3. `src/frame_compare/render/__init__.py` (MODIFY)

**Purpose:** Export `render_frame` and `RenderError` to public API.

### 4. `tests/utils/test_subproc.py` (NEW)

**Tests:**

- `test_run_subprocess_check_true` (raises `CalledProcessError` on exit 1)
- `test_run_subprocess_check_false` (returns `CompletedProcess` on exit 1)
- `test_run_subprocess_timeout` (raises `TimeoutExpired`)
- `test_run_subprocess_not_found` (raises `FileNotFoundError`)
- `test_run_subprocess_args` (verifies args passed strictly as list)

### 5. `tests/render/test_encoders.py` (NEW)

**Tests:**

- `test_render_frame_dispatch` (verifies auto/vs/ffmpeg selection logic)
- `test_render_frame_mismatch_error` (VS renderer + Path input -> FrameExtractionError)
- `test_render_frame_ffmpeg_determinism` (verifies seek time string format `X.XXX`)
- `test_render_frame_overlay_integration` (verifies overlay applied in both paths)
- `test_probe_fps_parsing` (parses "24000/1001" correctly)

### 6. `docs/DECISIONS.md` (MODIFY)

**Record:**

- Encoders implementation (VS/FFmpeg fallback).
- `run_subprocess` strict contract.
- Deterministic FFmpeg seeking policy.

### 7. `CHANGELOG.md` (MODIFY)

- Added `frame_compare.render.encoders`.
- Added `frame_compare.utils.subproc`.

## Acceptance Criteria

- [ ] `run_subprocess` enforces shell=False and raises correct standard exceptions.
- [ ] `render_frame` correctly dispatches based on clip type (VideoNode vs Path).
- [ ] `FrameExtractionError` raised for type mismatches.
- [ ] FFmpeg defaults to deterministic seek time with 3 decimal precision.
- [ ] `apply_overlay` is invoked in both render paths when config present.
- [ ] `render` module exports `render_frame`.

## Verification Commands

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

Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v2.md
