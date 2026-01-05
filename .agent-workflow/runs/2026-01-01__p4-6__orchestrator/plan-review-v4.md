---
RUN_ID: 2026-01-01__p4-6__orchestrator
VERSION: v4
TARGET: Phase 4 → Item 4.6
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v4.md
---

# Plan Review Report: Render Orchestrator

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v4.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice with explicit out-of-scope list. |
| 2 | Dependencies | PASS | SSOT “Loading Strategy (Auto/VS)” now uses typed errors; VS loader entrypoint is `DefaultVSLoader`. |
| 3 | File List | FAIL | Missing `src/frame_compare/render/__init__.py` export updates for `render_batch`/`render_screenshots`. |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | FAIL | Plan still uses `render_batch(...)` / `render_screenshots(...)` placeholders; must list exact one-line signatures in backticks. |
| 6 | Tests Complete | FAIL | Test list is present but does not specify exact assertions (ordering, fail-fast semantics, `set_description` string, dict key/value ordering). |
| 7 | Verification Complete | FAIL | Missing workflow-required `lint-imports` gate and explicit per-command pass criteria (exit 0 / “No violations”). |
| 8 | Decision-Minimizing | FAIL | Leaves key algorithm choice open: how to implement SSOT fail-fast + ordering under `parallelism > 1` without submitting all tasks (SSOT says “subsequent tasks … not started”). Also leaves output-path generation unspecified. |
| 9 | Determinism Defined | FAIL | Plan claims determinism but does not pin deterministic output ordering (dict key order, per-label list order) in tests. |

## SSOT Update Audit (Best Practice / Correctness)

SSOT changes referenced in plan-v4 are directionally correct for this repo/run:

- Typed error surface (no raw `ImportError`, no undefined “PluginError”) aligns with `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md` and existing `frame_compare.errors` patterns.
- “auto falls back with warning, no exception” is pragmatic and matches the render module’s role as an orchestrator.
- “wrap unknown into `RenderError` with `__cause__`” matches the repo’s exception-chaining style.

No further SSOT changes are required for this slice **if** the plan locks down ordering + fail-fast algorithm + exports.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. `render_batch` concurrency algorithm that satisfies both: (a) result list order matches input order and (b) fail-fast without starting “subsequent” tasks.
2. How `render_screenshots` generates `output_path` deterministically (must use naming SSOT).
3. Public export surface for `frame_compare.render` (`__init__.py`) to expose `render_batch` and `render_screenshots`.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Complete file list + exports**
   - Section: `## Files to Create/Modify`
   - Required Change:
     - Add `src/frame_compare/render/__init__.py` (MODIFY) exporting `render_batch` and `render_screenshots`.

2. **Add exact public signatures (mechanically checkable)**
   - Section: “Functions to implement”
   - Required Change (exact one-line, backticked):
     - `render_batch(requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None) -> list[Path]`
     - `render_screenshots(clips: list[Path], frames: list[int], output_dir: Path, label_map: dict[Path, str] | None = None, renderer: Renderer = "auto", overlay_mode: OverlayMode = OverlayMode.STANDARD, reporter: ProgressReporter | None = None) -> dict[str, list[Path]]`

3. **Pin `render_batch` algorithm (no design choices left)**
   - Section: `render_batch` behavior
   - Problem: Current plan only says “use ThreadPoolExecutor + map futures by index”, leaving the core design choice open.
   - Required Change:
     - Specify bounded submission algorithm:
       - Submit at most `parallelism` tasks initially.
       - As each completes successfully, submit the next request (preserving stable mapping from request index → output).
       - On first exception: stop submitting new tasks; cancel pending (not-yet-started) futures; wait for in-flight futures if needed, then raise the first exception.
     - Specify how output ordering is produced: preallocate `results: list[Path | None]` sized `len(requests)`; fill by index; return casted list once complete.

4. **Pin output-path generation**
   - Section: `render_screenshots` behavior
   - Required Change:
     - Anchor to `render-module.md` naming behavior (Section `3.3 Naming`) and explicitly require using `generate_screenshot_path(output_dir, label, frame_number)` for every request.

5. **Make tests mechanically checkable**
   - Section: `tests/render/test_orchestrator.py`
   - Required Change:
     - Add explicit assertions for:
       - `render_batch` preserves order with `parallelism=2` (input request indices → output list indices).
       - fail-fast behavior in bounded submission mode (no tasks submitted beyond first failure; cancellation expectations for pending futures).
       - reporter calls: exact `start_phase("Rendering", len(requests))`, exact `set_description(f"Frame {req.frame_number}")`, `advance(1)` per completion, `complete_phase()` once.
       - `render_screenshots` returns dict keys in clip order and each value list in frame order.

6. **Verification gates**
   - Section: `## Verification Commands`
   - Required Change:
     - Add `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` with pass criteria: exit 0 / “No violations”.
     - Add explicit per-command pass criteria for pyright/ruff/pytest (exit 0).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v5.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-6__orchestrator

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v4.md
Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v4.md
Write file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v5.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
