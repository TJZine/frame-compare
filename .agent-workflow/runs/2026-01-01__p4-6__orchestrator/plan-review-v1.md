---
RUN_ID: 2026-01-01__p4-6__orchestrator
VERSION: v1
TARGET: Phase 4 → Item 4.6
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v1.md
---

# Plan Review Report: Render Orchestrator

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit out-of-scope present. |
| 2 | Dependencies | FAIL | Plan references `frame_compare.vs.source.load_video` (non-existent) and claims ProgressReporter “identical” to analysis while render spec requires `set_description`. |
| 3 | File List | FAIL | Missing required export updates in `src/frame_compare/render/__init__.py` for `render_batch` / `render_screenshots` public API. |
| 4 | Contract Impact | PASS | Contracts touched: NO. |
| 5 | Types Complete | FAIL | Missing required backticked 1-line signatures for public functions; `validate_spec_anchors.py` fails due to stray backticked non-signature content. |
| 6 | Tests Complete | FAIL | Test list exists but leaves multiple decision points (ordering, fail-fast semantics, overlay config construction, VS loading). Some tests reference undefined functions (`load_video`). |
| 7 | Verification Complete | FAIL | Verification commands omit `lint-imports` gate and do not state explicit pass criteria (exit 0 / no violations). |
| 8 | Decision-Minimizing | FAIL | Plan contains many unresolved “Decision/Clarification/Refinement” branches that the Coding Agent would have to choose. |
| 9 | Determinism Defined | FAIL | No pinned ordering requirements for returned lists/mappings; parallel execution likely introduces nondeterministic output ordering without an explicit policy. |

## Additional Quality Checks

- Error Codes: Issue — plan must anchor to and state which errors `render_batch`/`render_screenshots` propagate (e.g., `RenderError`, `FrameExtractionError`) and whether partial results are ever returned.
- Failure Modes: Issue — behavior for invalid frames, missing label_map entries, missing VS availability, and ffprobe/ffmpeg absence not specified.
- Derived Outputs: OK — none.
- Rollback Guidance: Issue — must explicitly “STOP and return to Planning” if SSOT cannot support required behavior without ad-hoc decisions.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Whether `render_screenshots` ever loads VS clips (and how) given it accepts `clips: list[Path]`.
2. How `OverlayConfig.resolution` is computed for FFmpeg/Path inputs (probe vs placeholder values).
3. `render_batch` determinism: result ordering + exception semantics (fail-fast vs partial results).
4. Progress reporting protocol definition (must include `set_description`).

## Concrete Edits Required (if CHANGES REQUIRED)

### A) Blocking SSOT Updates Required (Do this first)

1. **Update SSOT: Define render progress protocol**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
   - Under heading: `## 2. Key Types`
   - Add a minimal definition for `ProgressReporter` used by render APIs:
     - `start_phase(name: str, total: int) -> None`
     - `set_description(text: str) -> None`
     - `advance(count: int = 1) -> None`
     - `complete_phase() -> None`
   - Note: This is a render-specific protocol; do not claim it is identical to analysis.

2. **Update SSOT: Make `render_batch` and `render_screenshots` behaviors unambiguous**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
   - Under heading: `### 3.1 Frame Rendering`
   - Add bullets covering (minimally):
     - `render_batch` ordering contract: returned `list[Path]` is in the same order as `requests` input, even when `parallelism > 1`.
     - `render_batch` exception contract: fail-fast (raise first exception; no partial results) OR best-effort (return successes + aggregate failures) — pick one.
     - `render_screenshots` request generation order: clips outer loop in input order, frames inner loop in input order (stable/deterministic).
     - Overlay policy for orchestrator:
       - Whether overlay is always applied (via non-None `OverlayConfig`) or may be disabled; define mapping from `overlay_mode` to `overlay: OverlayConfig | None`.
       - How `OverlayConfig.resolution` is computed for Path-based clips (probe vs placeholder), and whether VS loading is performed for `renderer="vapoursynth"` / `renderer="auto"`.

3. **Update SSOT: Orchestrator implementation dependencies**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
   - Under heading: `### 3.1 Frame Rendering` (Notes/Responsibilities)
   - Specify the canonical loader entrypoint if VS loading is required:
     - Use `frame_compare.vs.loader.DefaultVSLoader` (or explicitly name the correct function/class), not `load_video`.

### B) Then Revise the Plan (plan-v2) (do not fix in-plan)

1. **Fix Spec Anchors compliance**
   - Remove backticked non-signature bullets containing parentheses (these trip `validate_spec_anchors.py`).
   - Add backticked one-line public signatures (must match SSOT):
     - `render_batch(requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None) -> list[Path]`
     - `render_screenshots(clips: list[Path], frames: list[int], output_dir: Path, label_map: dict[Path, str] | None = None, renderer: Renderer = "auto", overlay_mode: OverlayMode = OverlayMode.STANDARD, reporter: ProgressReporter | None = None) -> dict[str, list[Path]]`

2. **Complete file list**
   - Add `src/frame_compare/render/__init__.py` (MODIFY) to export `render_batch` and `render_screenshots` (public API parity with spec).

3. **Make tests deterministic and mechanically checkable**
   - Replace references to non-existent `load_video` with the SSOT-defined loader.
   - Add exact assertions for:
     - result ordering from `render_batch` under `parallelism > 1`
     - progress reporter call sequence (including `set_description`)
     - overlay config construction policy (per SSOT)

4. **Verification gates**
   - Add `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` and specify pass criteria (exit 0 / “No violations”).
   - Add explicit pass criteria for pyright/ruff/pytest (“exit 0”).

## Ready for Implementation

Return to Planning Agent for SSOT + plan revision. Next version: `plan-v2.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-6__orchestrator

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "## 2. Key Types" add/change:
  - Define `ProgressReporter` protocol used by render APIs with methods: `start_phase(name: str, total: int) -> None`, `set_description(text: str) -> None`, `advance(count: int = 1) -> None`, `complete_phase() -> None`.

Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "### 3.1 Frame Rendering" add/change:
  - Specify `render_batch` ordering contract (result order matches input `requests`).
  - Specify `render_batch` exception contract (fail-fast vs best-effort; pick one).
  - Specify `render_screenshots` deterministic request ordering (clips order, frames order).
  - Specify overlay construction policy (`overlay_mode` → `overlay: OverlayConfig | None`) and how `OverlayConfig.resolution` is computed for Path clips.
  - If VS loading is required for `renderer="vapoursynth"`/`"auto"`, name the correct loader entrypoint (e.g., `frame_compare.vs.loader.DefaultVSLoader`) and state when it is used.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v1.md
Write file: .agent-workflow/runs/2026-01-01__p4-6__orchestrator/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
