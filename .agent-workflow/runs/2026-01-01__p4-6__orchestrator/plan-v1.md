---
RUN_ID: 2026-01-01__p4-6__orchestrator
VERSION: v1
TARGET: Phase 4 → Item 4.6
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v1.md
---

# Implementation Plan: Render Orchestrator

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:** Phase 4.5 (Encoders) must be complete (it is).

## Scope

This plan covers:

- [ ] Implement `src/frame_compare/render/orchestrator.py`
- [ ] Implement `render_screenshots` (high-level orchestration)
- [ ] Implement `render_batch` (bulk processing with progress)
- [ ] Define `ProgressReporter` Protocol

This plan does NOT cover:

- Audio adjustment application (that happens at VS layer before passing clip, or future feature)
- Report generation

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: “3.1 Frame Rendering” (for `render_screenshots` and `render_batch` signatures)
  - Section: “1.2 Module Structure” (for file placement)
  - Section: “2. Key Types” (for `RenderRequest` usage)

## Files to Create/Modify

### 1. `src/frame_compare/render/orchestrator.py`

**Purpose:** High-level coordinator that turns a list of clips + frames into specific `RenderRequest`s and executes them.

**Types to define:**

- `ProgressReporter` (Protocol) — Identical to `frame_compare.analysis.metrics.ProgressReporter`.

**Functions to implement (spec-anchored):**

- `render_screenshots(...) -> dict[str, list[Path]]` — See SSOT for full signature and behavior.
  - **Behavior:**
    1. Resolve labels: if `label_map` is None, use `path.stem`.
    2. Build `RenderRequest`s: Loop over clips (outer) and frames (inner).
       - Create `OverlayConfig` if `overlay_mode != MINIMAL` (or always, per logic). Note: Spec implies overlay config construction logic belongs here.
       - Logic: For each clip/frame, construct `OverlayConfig` using `mode`, `label`, `frame`, `video_node.width/height` (if VS) or probe (if FFmpeg) - *Correction*: `render_screenshots` takes `clips: list[Path]`. It can't easily know resolution without loading.
       - **Refinement:** The spec says `render_screenshots` takes `clips: list[Path]`. However, for VS rendering we need `vs.VideoNode`. The spec says "The caller is responsible for applying audio offsets... at the VS layer".
       - **Clarification:** `render_screenshots` in the spec takes `clips: list[Path]`. It then says "Delegate actual rendering to render_batch". `render_batch` takes `RenderRequest`. `RenderRequest` takes `vs.VideoNode | Path`.
       - **Implementation Strategy:**
         - `render_screenshots` will assume `Path` inputs (CLI usage).
         - If `renderer="vapoursynth"`, it must load them using `frame_compare.vs.loader.load_video` (if available) OR expecting the caller to have handled it?
         - Looking at spec 3.1: "Note: The caller is responsible for applying audio offsets/trims at the VS layer." BUT the signature only accepts `list[Path]`.
         - **Decision:** The current spec signature restricts `render_screenshots` to Paths only. This implies it handles loading IF it wants to use VS.
         - However, to keep it simple and compliant with the *exact* signature in the spec, we will implement it such that it creates `RenderRequest` objects with `Path`s.
         - `render_frame` (from Phase 4.5) handles the "auto" logic: if it gets a Path, it tries FFmpeg (unless `renderer="vapoursynth"` is forced, which would raise `FrameExtractionError` inside `render_frame` if passed a Path).
         - **Wait:** If `renderer="vapoursynth"`, `render_frame` raises if passed a `Path`. This means `render_screenshots` **MUST** load the video if VS is requested.
         - **Constraint:** The spec does NOT list `frame_compare.vs` as a dependency for `orchestrator.py`, but it does say "Resolve labels... Generate RenderRequests".
         - **Resolution:** I will implement `render_screenshots` to support identifying if the input is compatible. But adhering strictly to the spec signature `clips: list[Path]`:
           - If `renderer="vapoursynth"` (or "auto" and VS is available), it should probably try to load via `frame_compare.vs` if available.
           - *Actually*, looking at Phase 6 (CLI) plans, the Runner coordinates phases.
           - Let's stick to the simplest interpretation: `render_screenshots` passes the `Path` to `RenderRequest`. If the user asked for VS but provided a Path, `render_frame` (Phase 4.5) *explicitly* raises `FrameExtractionError`.
           - **CORRECTION:** Phase 4.5 `render_frame` implementation:

             ```python
             if renderer == "vapoursynth":
                 if is_path:
                     raise FrameExtractionError(...)
             ```

           - This implies `render_screenshots` MUST load the video if VS is desired.
           - **Plan:** Import `frame_compare.vs.source` inside `render_screenshots` (deferred import) to load clips if `renderer != "ffmpeg"`.
           - If `frame_compare.vs` is missing/fails, fall back to "ffmpeg" (unless "vapoursynth" was forced).

- `render_batch(...) -> list[Path]` — See SSOT for signature.
  - **Behavior:**
    - Initialize reporter.
    - `executor = ThreadPoolExecutor(max_workers=parallelism)`
    - Submit all tasks.
    - As they complete, report progress.
    - Collect results (Path) or raise first exception? Spec doesn't say.
    - **Decision:** Raise first exception (fail-fast) is standard unless "best effort" specified. Spec 3.1 doesn't specify partial success. I will implement fail-fast.

### 2. `tests/render/test_orchestrator.py`

**Tests required:**

- `test_render_batch_sequential` — mocks `render_frame`, checks calls.
- `test_render_batch_parallel` — checks behavior with `parallelism=2`.
- `test_render_batch_progress` — verifies reporter calls.
- `test_render_screenshots_integration_mocked` — mocks `load_video` (VS) and `render_batch`, verifies `RenderRequest` creation with correct overlay/paths.
- `test_render_screenshots_ffmpeg` — e2e flow with "ffmpeg" forced (no VS loading).

### 3. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry.

- **Run ID:** 2026-01-01__p4-6__orchestrator
- **Scope:** Orchestrator implementation.
- **Decision:** `render_screenshots` will attempt to load VS clips if renderer is "auto" or "vapoursynth". If VS import fails, it falls back to FFmpeg (if "auto").

### 4. `CHANGELOG.md` (MODIFY)

**Purpose:** Add entry for "Render Orchestrator".

## Acceptance Criteria

- [ ] `render_screenshots` correctly generates unique output paths for all clip/frame combinations.
- [ ] `render_batch` executes requests and reports progress.
- [ ] VS loading works (when available) for "auto"/"vapoursynth" modes.
- [ ] FFmpeg fallback (passed as Path) behaves correctly.

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/render/orchestrator.py
.venv/bin/ruff check src/frame_compare/render/orchestrator.py
.venv/bin/pytest -v tests/render/test_orchestrator.py
```

## Notes for Coding Agent

- Use `concurrent.futures.ThreadPoolExecutor` for parallelism in `render_batch`.
- Use `frame_compare.vs.source.load_video` to load clips if needed. Handle `ImportError` gracefully (treat as VS unavailable).
- `RenderRequest` requires `overlay: OverlayConfig | None`. You need to construct this in `render_screenshots`.
  - For `OverlayConfig.resolution`, if using VS, use `clip.width/height`.
  - If using FFmpeg (Path), you might need to probe or pass (0,0) if unknown?
  - **Refinement:** The spec Phase 4.2 has `calculate_dimensions`.
  - Additional Note: If FFmpeg is used, we can't easily get resolution without `ffprobe`. Phase 4.5 `_probe_fps` exists but no `probe_resolution`.
  - **Decision:** For FFmpeg path, use `(0, 0)` for resolution in OverlayConfig if probing is too expensive/not implemented, OR implement a local probe helper.
  - Given Phase 4.6 scope doesn't explicitly add probing, pass `(0, 0)` for resolution if strictly path-based, or rely on `render_frame`'s internal probing? `render_frame` applies overlay *after* rendering?
  - Phase 4.5 `render_frame` (FFmpeg path):

    ```python
    _render_ffmpeg(...)
    if request.overlay: _apply_overlay_to_file(...)
    ```

    `_apply_overlay_to_file` opens the rendered image -> `img.size` is available!
    **Wait:** `OverlayConfig` *contains* `resolution`. If we create `OverlayConfig` in `orchestrator`, we need to know it upfront.
    **Solution:** If VS is used, use `(clip.width, clip.height)`. If FFmpeg is used, we might not know it yet.
    **Trick:** Initialize `OverlayConfig` with `(0,0)` if unknown. Phase 4.5 `apply_overlay` does `calculate_overlay_position` using `image.size` (the actual image), ignoring `config.resolution`?
    *Correction:* Spec 3.2.1 says "Generate text string... {width}x{height}". It reads `config.resolution` for the text label.
    **Plan:** For `render_screenshots` with FFmpeg, we accept `(0,0)` or "Unknown" for resolution text for now, as we don't want to probe every input file in the orchestrator unless necessary.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-6__orchestrator

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v1.md
