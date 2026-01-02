---
RUN_ID: 2026-01-01__p4-6__orchestrator
VERSION: v3
TARGET: Phase 4 → Item 4.6
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v3.md
---

# Plan Review Report: Render Orchestrator

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | One slice; out-of-scope section present. |
| 2 | Dependencies | FAIL | Plan + SSOT now claim `ImportError` propagation and “PluginError”, which is inconsistent with existing typed error policy and current VS loader implementation patterns (uses typed errors). |
| 3 | File List | FAIL | Still missing `src/frame_compare/render/__init__.py` exports for `render_batch`/`render_screenshots` (public API per render-module SSOT). |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | FAIL | Planned public functions are listed as `render_* (...)` placeholders; must include exact 1-line signatures (backticked) for mechanical coverage. |
| 6 | Tests Complete | FAIL | Test names exist, but assertions are not mechanically specified (ordering guarantees, fail-fast semantics, and exact exception types for forced VS load failure). |
| 7 | Verification Complete | FAIL | Missing `lint-imports` gate and explicit pass criteria (“exit 0”, “No violations”). |
| 8 | Decision-Minimizing | FAIL | Leaves Coding Agent decisions: exact exception classes for VS load failures; how to detect “VS missing” vs “load failed”; fail-fast strategy under parallelism with deterministic ordering. |
| 9 | Determinism Defined | FAIL | Mentions deterministic ordering but does not pin ordering of dict values / list outputs via tests. |

## Additional Quality Checks (SSOT Update Review)

- SSOT correctness: Issue — `render-module.md` “Loading Strategy (Auto/VS)” currently references `ImportError` propagation and “PluginError”, but the codebase’s VS layer uses typed errors (`VapourSynthNotFoundError`, `VapourSynthError`, `PluginNotFoundError`, `SourceLoadError`). This SSOT update is not best-practice aligned for this project and is likely unimplementable as written without intentionally reintroducing raw exceptions.
- Best practice for this run: Prefer typed `frame_compare.errors` exceptions across module boundaries; avoid propagating raw `ImportError` from deep deps.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. SSOT-vs-code mismatch: whether to propagate raw `ImportError` or typed `VapourSynthNotFoundError` on VS availability failures.
2. Undefined exception name “PluginError”.
3. Missing public API exports for `render_batch` / `render_screenshots`.
4. Missing pinned ordering and fail-fast semantics tests.

## Concrete Edits Required (if CHANGES REQUIRED)

### 1) Update SSOT spec first (required): Fix “Loading Strategy (Auto/VS)” exception surface

Edit file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
- Under heading: `### 3.1 Frame Rendering` → `render_screenshots` docstring → `Loading Strategy (Auto/VS):`
- Replace the current forced-VS failure bullets with typed errors only (no raw `ImportError`, no “PluginError”):
  - Missing VapourSynth dependency → `VapourSynthNotFoundError (FC-2001)`
  - VS core init/runtime failure → `VapourSynthError (FC-2002)`
  - Missing required plugin → `PluginNotFoundError (FC-2003)`
  - Source load failure → `SourceLoadError (FC-4015)`
  - Remove “Do not wrap unknown exceptions (let them bubble)” unless you also define a typed wrapper policy (preferred: wrap unknown into `RenderError (FC-4004)`).
- Confirm `renderer="auto"` behavior: on any of the above VS load failures, log a warning and fall back to Path-based requests (no exception from the load attempt).

Rationale (best practice for this repo/run):
- Orchestrator is a module boundary; typed errors are required for consistent exit-code mapping and CLI ergonomics.
- VS module already models failures with typed exceptions; SSOT should not instruct reintroducing raw `ImportError`.

### 2) Revise plan-v4 (after SSOT update): Make API surface mechanically checkable

- Add exact one-line signatures (backticked), matching SSOT:
  - `render_batch(requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None) -> list[Path]`
  - `render_screenshots(clips: list[Path], frames: list[int], output_dir: Path, label_map: dict[Path, str] | None = None, renderer: Renderer = "auto", overlay_mode: OverlayMode = OverlayMode.STANDARD, reporter: ProgressReporter | None = None) -> dict[str, list[Path]]`
- Update `## Spec Anchors (SSOT)` to include:
  - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` → Section: `1.3 VSLoader Protocol` (since plan depends on `DefaultVSLoader`)
  - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md` → Sections covering the typed errors referenced above

### 3) Revise plan-v4: Complete file list + verification gates

- Add `src/frame_compare/render/__init__.py` (MODIFY) exporting `render_batch` and `render_screenshots`.
- Add verification gate:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` with pass criteria (“exit 0”, “No violations”).
- Add explicit pass criteria for existing commands (pyright/ruff/pytest: exit 0).

### 4) Revise plan-v4: Tests must pin determinism + fail-fast semantics

- Add required assertions:
  - `render_batch` returns results in *input order* even when `parallelism=2`.
  - `render_batch` fail-fast semantics: define exactly what happens to already-submitted tasks after first failure (e.g., allow completion; cancel pending futures; never suppress the first exception).
  - `render_screenshots` mapping: keys in clip order and each value list in frame order.
  - Progress reporter: exact `set_description(f"Frame {req.frame_number}")` string.
  - Forced-VS load failure raises the exact typed error class per SSOT update (no raw `ImportError`).

## Ready for Implementation

Return to Planning Agent for SSOT correction + plan-v4 revision.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-6__orchestrator

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "### 3.1 Frame Rendering" (inside `render_screenshots` → "Loading Strategy (Auto/VS):") add/change:
  - Replace raw `ImportError` propagation and undefined “PluginError” with typed errors only: `VapourSynthNotFoundError (FC-2001)`, `VapourSynthError (FC-2002)`, `PluginNotFoundError (FC-2003)`, `SourceLoadError (FC-4015)`.
  - Remove “let unknown exceptions bubble” unless a typed wrapper policy is specified (preferred: wrap unknown into `RenderError (FC-4004)`).
  - Confirm `renderer="auto"` falls back to Path-based requests on any VS load failure (log warning; no exception).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v3.md
Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v3.md
Write file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
