---
RUN_ID: 2026-01-01__p4-5__encoders
VERSION: v1
TARGET: Phase 4 → Item 4.5
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v1.md
---

# Implementation Plan: Render Encoders

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
- [ ] `src/frame_compare/utils/subproc.py` (New dependency for secure subprocess execution)
- [ ] Unit tests for encoders and fallback logic
- [ ] Unit tests for subprocess wrapper

This plan does NOT cover:

- `orchestrator.py` (Phase 4.6)
- Batch rendering / Progress reporting (Phase 4.6)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: “3.1 Frame Rendering”
  - Section: “4.1 VapourSynth Rendering”
  - Section: “4.2 FFmpeg Rendering”
  - Section: “6. Error Handling”

## Files to Create/Modify

### 1. `src/frame_compare/utils/subproc.py` (NEW)

**Purpose:** Secure subprocess wrapper as required by Spec 4.2.

**Functions to implement:**

- `run_subprocess(cmd: list[str], timeout_seconds: float = 30.0) -> subprocess.CompletedProcess`
  - *Behavior:* Wrapper around `subprocess.run` with `shell=False`, `check=True`, `capture_output=True`, `text=True`.
  - *Error Handling:* Raises `subprocess.TimeoutExpired` or `subprocess.CalledProcessError`.

### 2. `src/frame_compare/render/encoders.py` (NEW)

**Purpose:** Handle screenshot generation via VapourSynth (primary) or FFmpeg (fallback).

**Functions to implement (spec-anchored):**

- `render_frame(request: RenderRequest, renderer: Renderer = "auto") -> Path`
  - *Spec:* 3.1 Frame Rendering
  - *Behavior:* Dispatches to `_render_vs` or `_render_ffmpeg`.
  - *Logic:*
    - If `renderer="vapoursynth"`: call `_render_vs`.
    - If `renderer="ffmpeg"`: call `_render_ffmpeg`.
    - If `renderer="auto"`: try `_render_vs` if `vs` available in `sys.modules`; else `_render_ffmpeg`.
    - Wraps generic errors in `RenderError (FC-4004)`.

- `_render_vs(clip: vs.VideoNode, frame: int, output: Path, settings: EncoderSettings) -> None`
  - *Spec:* 4.1 VapourSynth Rendering
  - *Behavior:* `clip.get_frame(frame)`, convert to numpy/PIL, `apply_overlay` (if req.overlay), save to `output` via PIL/cv2.

- `_render_ffmpeg(video_path: Path, frame: int, output: Path, settings: EncoderSettings, timeout: int = 30) -> None`
  - *Spec:* 4.2 FFmpeg Rendering
  - *Behavior:*
    - Probes FPS if needed (via `_probe_fps` helper).
    - Constructs `ffmpeg` command with `-ss` seek.
    - Calls `run_subprocess`.
    - Applies overlay AFTER export? **Clarification:** FFmpeg export is raw frame. Overlay application logic differs:
      - *VS:* Overlay applied on `VideoFrame` -> Image conversion.
      - *FFmpeg:* Exports raw image -> Load PIL -> `apply_overlay` -> Save.
    - *Note:* Since `RenderRequest` contains `overlay: OverlayConfig`, this function is responsible for applying it before final save.

- `_probe_fps(video_path: Path) -> float`
  - *Behavior:* Uses `ffprobe` to get frame rate. Returns 23.976 etc.

### 3. `tests/utils/test_subproc.py` (NEW)

**Tests required:**

- `test_run_subprocess_success` — verifies stdout capture
- `test_run_subprocess_failure` — verifies CalledProcessError
- `test_run_subprocess_timeout` — verifies TimeoutExpired
- `test_run_subprocess_shell_injection` — ensures shell=False (list args)

### 4. `tests/render/test_encoders.py` (NEW)

**Tests required:**

- `test_render_frame_vs_success` — Mocks `vs` and `clip.get_frame`
- `test_render_frame_vs_overlay` — Verifies overlay application pipeline
- `test_render_frame_ffmpeg_fallback` — Simulates missing `vs` module
- `test_render_frame_ffmpeg_command` — Verifies args passed to `run_subprocess`
- `test_render_frame_ffmpeg_overlay` — Verifies image reload + overlay apply
- `test_render_frame_auto_selection`
- `test_render_error_wrapping` — Checks FC-4004, FC-4001 mapping

### 5. `docs/DECISIONS.md` (MODIFY)

**Required facts to record:**

- Implementation of `encoders.py` with VS/FFmpeg dual extraction strategies.
- Creation of `utils/subproc.py` for secure shell execution.
- Handling of overlays for FFmpeg path (post-process via PIL).

### 6. `CHANGELOG.md` (MODIFY)

**Purpose:** Entry for Phase 4.5 Encoders.

## Acceptance Criteria

- [ ] `render_frame` calls `_render_vs` when renderer="vapoursynth"
- [ ] `render_frame` calls `_render_ffmpeg` when renderer="ffmpeg"
- [ ] Auto-fallback logic selects VapourSynth if available, else FFmpeg
- [ ] `_render_ffmpeg` uses secure `run_subprocess` (no shell=True)
- [ ] Overlays are applied correctly in *both* paths (in-memory for VS, post-load for FFmpeg)
- [ ] Output images are saved with correct extension/format
- [ ] Unit tests pass with 100% coverage of fallback logic

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/render src/frame_compare/utils
.venv/bin/ruff check src/frame_compare/render src/frame_compare/utils
.venv/bin/pytest -v tests/render tests/utils
```

## Notes for Coding Agent

- **VapourSynth Availability:** Use `sys.modules.get("vapoursynth")` or try/except ImportError to detect VS availability for "auto" mode.
- **Overlay Pipeline:**
  - **VS:** `clip.get_frame` -> `np.ndarray` -> `PIL.Image` -> `apply_overlay` -> `image.save`
  - **FFmpeg:** `ffmpeg ... out.png` -> `PIL.Image.open(out.png)` -> `apply_overlay` -> `image.save(out.png)` (overwrite)
- **FFprobe:** You may need a simple `_probe_fps` helper parsing `ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate ...`.
- **Imports:** Import `run_subprocess` from `frame_compare.utils.subproc`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-5__encoders

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v1.md
