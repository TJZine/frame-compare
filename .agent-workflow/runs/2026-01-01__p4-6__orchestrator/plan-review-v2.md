---
RUN_ID: 2026-01-01__p4-6__orchestrator
VERSION: v2
TARGET: Phase 4 → Item 4.6
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v2.md
---

# Plan Review Report: Render Orchestrator

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice with explicit out-of-scope list. |
| 2 | Dependencies | PASS | References correct VS loader (`DefaultVSLoader`) and render-module `ProgressReporter`. |
| 3 | File List | FAIL | Missing required `src/frame_compare/render/__init__.py` export updates for `render_batch`/`render_screenshots`. |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | FAIL | Plan still does not list the full backticked one-line signatures for `render_batch` and `render_screenshots` (only “(...)”). |
| 6 | Tests Complete | FAIL | Test list exists but does not specify exact assertions for determinism (ordering), fail-fast semantics under parallelism, and progress reporter `set_description` string. |
| 7 | Verification Complete | FAIL | Missing `lint-imports` gate and explicit exit-0/no-violations criteria. |
| 8 | Decision-Minimizing | FAIL | Leaves implementation choices open for `render_batch` fail-fast strategy under `parallelism > 1` (submit-all vs bounded queue) and exception mapping on VS load failure when `renderer="vapoursynth"`. |
| 9 | Determinism Defined | FAIL | Plan mentions determinism but does not pin the concrete ordering contract for returned mapping values and list ordering assertions in tests. |

## Additional Quality Checks

- Error Codes: Issue — SSOT states “raise error” on VS load failure when forced; plan must not choose exception classes without SSOT guidance.
- Failure Modes: Issue — needs explicit behavior and tests for `renderer="vapoursynth"` load failure (which error type escapes).
- Derived Outputs: OK — none.
- Rollback Guidance: OK — revision can remain plan-only if SSOT clarifies exception surface.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Exact public exception surface for `render_screenshots` when VS loading fails and `renderer="vapoursynth"`.
2. `render_batch` fail-fast strategy under `parallelism > 1` that meets SSOT wording and is testable/deterministic.
3. Public export surface (`frame_compare.render.__init__`) for `render_batch`/`render_screenshots`.

## Concrete Edits Required (if CHANGES REQUIRED)

### 1) Update SSOT: Define `render_screenshots` raises for VS load failures

**Update SSOT spec first** (do not “decide in plan”):

- Edit file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
- Under heading: `### 3.1 Frame Rendering`
- Add a `Raises:` block (or bullets) for `render_screenshots` covering at least:
  - When `renderer="vapoursynth"` and VS load fails, which specific exception types may be raised (choose from existing: `VapourSynthNotFoundError (FC-2001)`, `VapourSynthError (FC-2002)`, `PluginNotFoundError (FC-2003)`, `SourceLoadError (FC-4015)`), and whether they are propagated or wrapped.
  - When `renderer="auto"` and VS load fails, confirm it falls back to Path-based requests (no exception raised from loading path).

### 2) Revise plan-v3: Make signatures and file exports mechanically checkable

- Add full backticked signatures (1 line each, exact) in the plan:
  - `render_batch(requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None) -> list[Path]`
  - `render_screenshots(clips: list[Path], frames: list[int], output_dir: Path, label_map: dict[Path, str] | None = None, renderer: Renderer = "auto", overlay_mode: OverlayMode = OverlayMode.STANDARD, reporter: ProgressReporter | None = None) -> dict[str, list[Path]]`
- Add `src/frame_compare/render/__init__.py` (MODIFY) exporting `render_batch` and `render_screenshots`.

### 3) Revise plan-v3: Pin determinism + progress strings + fail-fast testability

- Tests must assert:
  - `render_batch` returns paths in input request order (even with `parallelism=2`).
  - `reporter.set_description` uses exactly `f"Frame {req.frame_number}"`.
  - `render_screenshots` builds requests in clip order then frame order; returned dict values are in frame order.
- For fail-fast under `parallelism > 1`, constrain tests to a single failure and explicitly define expected behavior for “already submitted tasks” (e.g., may complete; no new submissions after first failure). Plan must specify the approach so Coding Agent doesn’t choose.

### 4) Revise plan-v3: Verification gates per workflow

- Add `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` with pass criteria: exit 0 / “No violations”.
- Add explicit exit-0 criteria for pyright/ruff/pytest commands.

## Ready for Implementation

Return to Planning Agent for SSOT update + plan-v3 revision.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-6__orchestrator

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "### 3.1 Frame Rendering" add/change:
  - Specify the exact `render_screenshots` exception surface when `renderer=\"vapoursynth\"` and VS loading fails (which exception classes may raise, and whether they are propagated or wrapped).
  - Confirm `renderer=\"auto\"` falls back to Path-based requests on VS load failure (no exception from load attempt).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v2.md
Write file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
