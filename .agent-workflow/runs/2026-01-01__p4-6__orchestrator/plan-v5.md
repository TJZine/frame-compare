---
RUN_ID: 2026-01-01__p4-6__orchestrator
VERSION: v5
TARGET: Phase 4 → Item 4.6
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v5.md
---

# Implementation Plan: Render Orchestrator

## Changes Since plan-v4

- Added `src/frame_compare/render/__init__.py` to file list.
- Added exact public signatures for `render_batch` and `render_screenshots`.
- Pinned `render_batch` bounded submission algorithm with fail-fast semantics.
- Pinned output-path generation using `generate_screenshot_path`.
- Made tests mechanically checkable with exact assertions.
- Added `lint-imports` gate and explicit per-command pass criteria.

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:** Phase 4.5 (Encoders) must be complete.

## Scope

This plan covers:

- [ ] Implement `src/frame_compare/render/orchestrator.py`
- [ ] Implement `render_screenshots` (high-level orchestration)
- [ ] Implement `render_batch` (bulk processing with progress)
- [ ] Define `ProgressReporter` Protocol
- [ ] Update `src/frame_compare/render/__init__.py` with exports

This plan does NOT cover:

- Audio adjustment application
- Report generation

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: "2.4 ProgressReporter"
  - Section: "3.1 Frame Rendering"
  - Section: "3.3 Naming"

## Public API (signatures)

```python
render_batch(requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None) -> list[Path]
```

```python
render_screenshots(clips: list[Path], frames: list[int], output_dir: Path, label_map: dict[Path, str] | None = None, renderer: Renderer = "auto", overlay_mode: OverlayMode = OverlayMode.STANDARD, reporter: ProgressReporter | None = None) -> dict[str, list[Path]]
```

## Files to Create/Modify

### 1. `src/frame_compare/render/orchestrator.py` [NEW]

**Purpose:** High-level coordinator that turns a list of clips + frames into specific `RenderRequest`s and executes them.

**Types to define:**

- `ProgressReporter` (Protocol) — Define methods `start_phase`, `set_description`, `advance`, `complete_phase` per SSOT Section 2.4.

**Functions to implement:**

#### `render_batch`

- **Signature:** `render_batch(requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None) -> list[Path]`
- **Behavior (SSOT 3.1):**
  - **Ordering:** Result list matches input `requests` order.
  - **Exception Contract:** Fail-fast (raise first exception).
  - **Parallelism:** Use `ThreadPoolExecutor`.
  - **Reporting:** `start_phase` -> `set_description` -> `advance` -> `complete_phase`.
- **Algorithm (pinned):**
  1. Preallocate `results: list[Path | None] = [None] * len(requests)`.
  2. If `parallelism == 1`: sequential loop, fill `results[i]` with `render_frame(requests[i])`. On exception, raise immediately.
  3. If `parallelism > 1`:
     - Use bounded submission: submit at most `parallelism` tasks initially.
     - As each completes successfully, submit the next request (preserving stable mapping from request index → output).
     - On first exception: stop submitting new tasks; cancel pending (not-yet-started) futures; wait for in-flight futures to complete (or cancel), then raise the first exception.
  4. Return `cast(list[Path], results)` after all complete.

#### `render_screenshots`

- **Signature:** `render_screenshots(clips: list[Path], frames: list[int], output_dir: Path, label_map: dict[Path, str] | None = None, renderer: Renderer = "auto", overlay_mode: OverlayMode = OverlayMode.STANDARD, reporter: ProgressReporter | None = None) -> dict[str, list[Path]]`
- **Behavior (SSOT 3.1):**
  - **Determinism:** Process clips in provided list order. Process frames in provided list order. Result dict keys in clip order; each value list in frame order.
  - **Labels:** Use `label_map[clip]` if provided, else `clip.stem`.
  - **Loading Strategy (SSOT 3.1):**
    - If `renderer="vapoursynth"` or `"auto"`, use `frame_compare.vs.loader.DefaultVSLoader` (deferred import).
    - If loading fails and renderer="auto", fallback to FFmpeg Path-based rendering (log warning; no exception raised).
    - If renderer="vapoursynth" and loading fails:
      - Propagate `VapourSynthNotFoundError (FC-2001)` if vapoursynth module is missing.
      - Propagate `PluginNotFoundError (FC-2003)` if required VS plugin is missing.
      - Propagate `SourceLoadError (FC-4015)` if loader fails.
      - Wrap any other exception into `RenderError (FC-4004)` with original exception as `__cause__`.
  - **Overlay Policy:**
    - Construct `OverlayConfig`.
    - VS: use `clip.width`, `clip.height`.
    - Path: use `(0, 0)`.
  - **Output-path generation (SSOT 3.3):**
    - Use `generate_screenshot_path(output_dir, label, frame_number)` for every request.
  - Delegate execution to `render_batch`.

### 2. `src/frame_compare/render/__init__.py` [MODIFY]

**Purpose:** Export `render_batch` and `render_screenshots`.

**Changes:**

- Add imports: `from .orchestrator import render_batch, render_screenshots, ProgressReporter`
- Add to `__all__`: `"render_batch"`, `"render_screenshots"`, `"ProgressReporter"`

### 3. `tests/render/test_orchestrator.py` [NEW]

**Tests required (with exact assertions):**

| Test Name | Assertions |
|-----------|------------|
| `test_render_batch_sequential` | Mock `render_frame`, verify result order `[result_0, result_1, ...]` matches input order. |
| `test_render_batch_parallel_order` | With `parallelism=2`, verify result indices match input indices. |
| `test_render_batch_fail_fast` | On first exception, verify no tasks submitted beyond failure index; pending futures cancelled. |
| `test_render_batch_progress` | Verify `start_phase("Rendering", len(requests))`, `set_description(f"Frame {req.frame_number}")` per task, `advance(1)` per completion, `complete_phase()` once at end. |
| `test_render_screenshots_vs_loading` | Mock `DefaultVSLoader`, verify VS path used. |
| `test_render_screenshots_fallback` | Mock loader failure with `renderer="auto"`, verify fallback to FFmpeg path (check for warning log). |
| `test_render_screenshots_vs_forced_fail_vs_not_found` | Mock `VapourSynthNotFoundError` with `renderer="vapoursynth"`, verify propagated. |
| `test_render_screenshots_vs_forced_fail_plugin` | Mock `PluginNotFoundError`, verify propagated. |
| `test_render_screenshots_vs_forced_fail_source` | Mock `SourceLoadError`, verify propagated. |
| `test_render_screenshots_vs_forced_fail_unknown` | Mock unknown exception, verify wrapped into `RenderError` with `__cause__`. |
| `test_render_screenshots_overlay_resolution` | Verify `(0, 0)` resolution for Path clips, real dims for VS clips. |
| `test_render_screenshots_dict_order` | Verify dict keys in clip order; each value list in frame order. |
| `test_render_screenshots_output_path` | Verify output paths match `generate_screenshot_path(output_dir, label, frame_number)`. |

### 4. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Append run decision entry.

- **Run ID:** 2026-01-01__p4-6__orchestrator
- **Scope:** Orchestrator implementation.
- **Decision:** `render_screenshots` enforces typed exception propagation for forced VS mode and graceful fallback for auto mode. `render_batch` uses bounded submission with fail-fast semantics.

### 5. `CHANGELOG.md` [MODIFY]

**Purpose:** Add entry for "Render Orchestrator".

## Acceptance Criteria

- [ ] `render_screenshots` returns results in deterministic order matching inputs.
- [ ] `render_batch` raises immediately on first error; no subsequent tasks started.
- [ ] Progress reporting covers full batch count with exact method calls.
- [ ] VS loading fallback logic works as specified (logs warning, falls back).
- [ ] VS loading forced failure raises typed exceptions.
- [ ] Unknown exceptions wrapped into `RenderError`.
- [ ] Overlay config uses `(0, 0)` for non-loaded paths.
- [ ] Output paths use `generate_screenshot_path`.
- [ ] Public exports added to `__init__.py`.

## Verification Commands

```bash
# Type checking (pass criteria: exit 0)
.venv/bin/pyright --warnings src/frame_compare/render/orchestrator.py

# Linting (pass criteria: exit 0)
.venv/bin/ruff check src/frame_compare/render/orchestrator.py

# Import linting (pass criteria: exit 0 / "No violations")
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Unit tests (pass criteria: exit 0)
.venv/bin/pytest -v tests/render/test_orchestrator.py
```

## Notes for Coding Agent

- Use `concurrent.futures.ThreadPoolExecutor` with bounded submission.
- Preallocate results list and fill by index.
- For `render_screenshots`: Import `DefaultVSLoader` inside the function (local import).
- Use `generate_screenshot_path` from `.naming` for output paths.
- Be careful with `ProgressReporter` typing (use `Protocol` from `typing`).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-6__orchestrator

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v5.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v5.md
