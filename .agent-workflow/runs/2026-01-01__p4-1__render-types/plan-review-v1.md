---
RUN_ID: 2026-01-01__p4-1__render-types
VERSION: v1
TARGET: Phase 4 → Item 4.1
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v1.md
---

# Plan Review Report: Render Module Types

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (render types-only) with explicit out-of-scope list. |
| 2 | Dependencies | FAIL | Plan claims “Dependencies: None”, but SSOT includes `vs.VideoNode` typing + repo requires import-contract updates when introducing `frame_compare.render`. |
| 3 | File List | FAIL | Plan requires deleting `src/frame_compare/render/.gitkeep` but does not list it under files to modify/delete. Missing `importlinter.ini` update despite new top-level module. |
| 4 | Contract Impact | PASS | Canonical contracts not touched; contract gates not required. |
| 5 | Types Complete | FAIL | Plan does not provide mechanically checkable one-line signatures for the public API surface (dataclass ctor signatures / alias) and leaves `RenderRequest.clip` type inconsistent with SSOT. |
| 6 | Tests Complete | FAIL | Some tests are underspecified/incorrectly framed (e.g., “Literal accepts …” needs a deterministic runtime assertion strategy such as `typing.get_args`). Missing explicit default-field assertions for `OverlayConfig` (`font_size`, `position`). |
| 7 | Verification Complete | FAIL | Missing `lint-imports` gate (required when adding a new top-level module). Also lacks explicit fallback commands when `.venv/bin/*` is unavailable per workflow guidance. |
| 8 | Decision-Minimizing | FAIL | Leaves decisions to Coding Agent (“consider frozen”, “VS integration deferred”, unpinned import-linter layer rules). |
| 9 | Determinism Defined | PASS | N/A for types; no outputs requiring determinism. |

## Additional Quality Checks

- Error Codes: OK — no new/changed `FC-xxxx` errors planned.
- Failure Modes: Issue — plan must specify how `vs.VideoNode` typing is handled without requiring VapourSynth to be installed (pyright `reportMissingImports=true`), consistent with existing repo patterns.
- Derived Outputs: OK — no generated artifacts in this slice.
- Rollback Guidance: Issue — add an explicit “STOP/ROLLBACK” note: if `lint-imports` fails due to unclear layering rules, return to Planning instead of ad-hoc changes.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. How to represent `RenderRequest.clip: vs.VideoNode | Path` in `types.py` without introducing a hard runtime dependency and while still passing Pyright strict (missing-import handling strategy must be specified).
2. Exact `importlinter.ini` contract update required for introducing `frame_compare.render` (layers order + whether to enable an independence contract).
3. Whether dataclasses use `frozen=`/`slots=` beyond what SSOT specifies (plan currently says “consider”, not “do X”).
4. Exact runtime strategy for testing `Renderer = Literal[...]` (plan currently implies a type-system check, but tests run at runtime).

## Concrete Edits Required (for plan-v2.md)

1. **Fix Spec Anchors to be verbatim headings**
   - Section: `## Spec Anchors (SSOT)`
   - Problem: Anchors are not copy/paste exact headings; must pass `scripts/validate_spec_anchors.py`.
   - Required Change: Replace with the exact headings from `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`, e.g.:
     - `### 2.0 OverlayMode`
     - `### 2.1 RenderRequest`
     - `### 2.2 OverlayConfig`
     - `### 2.3 ScreenshotResult`

2. **Make public API signatures mechanically checkable**
   - Section: Add a new subsection under `src/frame_compare/render/types.py` planning
   - Problem: Public surface is only described narratively; constructors/defaults are not pinned.
   - Required Change: List each public symbol with a one-line signature in backticks, derived from SSOT, e.g.:
     - `OverlayMode(str, Enum)`
     - `EncoderSettings(format: str = "png", compression: int = 6, bit_depth: int = 8)`
     - `OverlayConfig(mode: OverlayMode, label: str, frame_number: int, resolution: tuple[int, int], hdr_info: str | None, font_path: Path | None, font_size: int = 24, position: str = "top-left")`
     - `RenderRequest(clip: vs.VideoNode | Path, frame_number: int, output_path: Path, overlay: OverlayConfig | None, encoder_settings: EncoderSettings)`
     - `Renderer = Literal["vapoursynth", "ffmpeg", "auto"]`
     - `ScreenshotResult(label: str, paths: list[Path], frame_count: int)`

3. **Resolve `RenderRequest.clip` typing to match SSOT (no deferral)**
   - Section: `src/frame_compare/render/types.py` implementation notes
   - Problem: Plan currently says “use `Path` for clip; VS integration deferred”, which contradicts SSOT (`vs.VideoNode | Path`) and forces Coding Agent to decide.
   - Required Change: Specify an exact pattern consistent with existing code (`src/frame_compare/analysis/metrics.py`) to avoid hard dependency while keeping SSOT typing, e.g.:
     - Include `from __future__ import annotations`
     - Use `TYPE_CHECKING` block with `import vapoursynth as vs  # type: ignore` to avoid `reportMissingImports`
     - Use `vs.VideoNode | Path` in annotations (no runtime import of VapourSynth required)

4. **Update import contracts (required when introducing `frame_compare.render`)**
   - Section: `## Files to Create/Modify` + `## Verification Commands` + `## Spec Anchors (SSOT)`
   - Problem: Plan introduces a new top-level module but omits `importlinter.ini` updates and the `lint-imports` gate.
   - Required Change:
     - Add SSOT anchor(s) for import rules from `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`:
       - `## 6. Import Contract Rules`
       - `## 7. import-linter Configuration`
     - Add `importlinter.ini` to the file list with explicit intended contract change (layers + any independence contract needed to ensure `analysis` and `render` remain non-importing peers).
     - Add verification command: `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` (and/or `.venv/bin/lint-imports --config importlinter.ini` if the repo standardizes that path).

5. **Make the file list complete and minimal**
   - Section: `## Files to Create/Modify`
   - Problem: `.gitkeep` deletion is required but not enumerated; importlinter update is missing.
   - Required Change: Add explicit entries for:
     - `src/frame_compare/render/.gitkeep` [DELETE]
     - `importlinter.ini` [MODIFY]

6. **Tighten tests to be deterministic and runtime-checkable**
   - Section: `tests/render/test_types.py`
   - Problem: “Verify Literal accepts …” is ambiguous; `OverlayConfig` default fields not asserted.
   - Required Change: Update test spec to state exactly how to assert:
     - `Renderer` allowed values via `typing.get_args(Renderer)` (or equivalent) equals `("vapoursynth", "ffmpeg", "auto")`
     - `OverlayConfig` defaults: `font_size == 24` and `position == "top-left"`

7. **Add explicit rollback/stop guidance**
   - Section: Add `## Rollback / Stop Conditions`
   - Problem: Plan lacks a “stop” rule when import contracts can’t be made deterministic.
   - Required Change: Add a rule: if `lint-imports` failures indicate unclear layer ordering/peer rules, STOP and return to Planning with a spec anchor update (do not guess).

## Ready for Implementation

Return to Planning Agent for revision. Next version: plan-v2.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-1__render-types

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v1.md
Write file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
