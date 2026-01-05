---
RUN_ID: 2026-01-01__p4-6__orchestrator
VERSION: v3
TARGET: Phase 4 → Item 4.6
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v3.md
---

# Implementation Plan: Render Orchestrator

## Changes Since plan-v2

- Updated Spec Anchors to reflect SSOT changes defining precise exception handling for VS loading failures.
- Explicitly specified exception propagation (`ImportError`, `SourceLoadError`) vs bubbling in "Loading Strategy".
- Confirmed fallback behavior logging (log warning) for `renderer="auto"`.

## Changes Since plan-v1

- Updated Spec Anchors to reflect SSOT changes defining `ProgressReporter`, batch contracts, and loading strategy.
- Explicitly specified `ProgressReporter` methods in the "Functional Requirements" section.
- Added SSOT-defined contracts for batch ordering (result matches input) and exception handling (fail-fast).
- Clarified VS loading strategy using `DefaultVSLoader` as per updated SSOT.
- Clarified `OverlayConfig` resolution policy for Path inputs `(0, 0)`.

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

This plan does NOT cover:

- Audio adjustment application
- Report generation

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: “2.4 ProgressReporter”
  - Section: “3.1 Frame Rendering” (for `render_batch` and `render_screenshots` signatures and behavior chunks)

## Files to Create/Modify

### 1. `src/frame_compare/render/orchestrator.py`

**Purpose:** High-level coordinator that turns a list of clips + frames into specific `RenderRequest`s and executes them.

**Types to define:**

- `ProgressReporter` (Protocol) — Define methods `start_phase`, `set_description`, `advance`, `complete_phase` per SSOT Section 2.4.

**Functions to implement (spec-anchored):**

- `render_screenshots(...) -> dict[str, list[Path]]` — See SSOT for signature.
  - **Behavior (SSOT 3.1):**
    - **Determinism:** Process clips and frames in provided order. Result dict keys match resolved labels.
    - **Labels:** Use `label_map` or `path.stem`.
    - **Loading Strategy:**
      - If `renderer="vapoursynth"` or `"auto"`, use `frame_compare.vs.loader.DefaultVSLoader` (deferred import).
      - If loading fails (ImportError/PluginError) and renderer="auto", fallback to FFmpeg Path-based rendering (log warning).
      - If renderer="vapoursynth" and loading fails:
        - Propagate `ImportError` if `vapoursynth` module is missing.
        - Propagate `SourceLoadError (FC-4015)` if loader fails.
        - Do not wrap unknown exceptions (let them bubble).
    - **Overlay Policy:**
      - Construct `OverlayConfig`.
      - VS: use `clip.width`, `clip.height`.
      - Path: use `(0, 0)`.
    - Delegate execution to `render_batch`.

- `render_batch(...) -> list[Path]` — See SSOT for signature.
  - **Behavior (SSOT 3.1):**
    - **Ordering:** Result list matches input `requests` order.
    - **Exception Contract:** Fail-fast (raise first exception).
    - **Parallelism:** Use `ThreadPoolExecutor`.
    - **Reporting:** `start_phase` -> `set_description` -> `advance` -> `complete_phase`.

### 2. `tests/render/test_orchestrator.py`

**Tests required:**

- `test_render_batch_sequential` — Mocks `render_frame`, verifies result order matches input order.
- `test_render_batch_parallel` — Verifies concurrent execution (using delays in mock) and fail-fast behavior.
- `test_render_batch_progress` — Verifies `ProgressReporter` callbacks.
- `test_render_screenshots_vs_loading` — Mocks `DefaultVSLoader` to verify VS path.
- `test_render_screenshots_fallback` — Mocks loader failure to verify fallback to FFmpeg path (check for warning log).
- `test_render_screenshots_vs_forced_fail` — Mocks loader failure with `renderer="vapoursynth"` to verify strict exception propagation.
- `test_render_screenshots_overlay_resolution` — Verifies `(0, 0)` resolution for Path clips and real dims for VS clips.

### 3. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry.

- **Run ID:** 2026-01-01__p4-6__orchestrator
- **Scope:** Orchestrator implementation.
- **Decision:** `render_screenshots` enforces strict exception propagation for forced VS mode and graceful fallback for auto mode.

### 4. `CHANGELOG.md` (MODIFY)

**Purpose:** Add entry for "Render Orchestrator".

## Acceptance Criteria

- [ ] `render_screenshots` returns results in deterministic order matching inputs.
- [ ] `render_batch` raises immediately on first error.
- [ ] Progress reporting covers full batch count.
- [ ] VS loading fallback logic works as specified (logs warning, falls back).
- [ ] VS loading forced failure raises expected exceptions.
- [ ] Overlay config uses `(0, 0)` for non-loaded paths.

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/render/orchestrator.py
.venv/bin/ruff check src/frame_compare/render/orchestrator.py
.venv/bin/pytest -v tests/render/test_orchestrator.py
```

## Notes for Coding Agent

- Use `concurrent.futures.ThreadPoolExecutor`.
- To implement fail-fast in `render_batch`: use `executor.submit` and collect futures, then `as_completed` or iterate. To ensure output order matches input order, map futures by index.
- For `render_screenshots`:
  - Import `DefaultVSLoader` inside the function (local import) or lazy import to avoid hard dependency at module level.
  - Implement the "Loading Strategy" exactly as spec'd: check renderer, try loading, catch exceptions, decide based on renderer.
- Be careful with `ProgressReporter` typing (use `Protocol` from `typing`).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-6__orchestrator

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v2.md
