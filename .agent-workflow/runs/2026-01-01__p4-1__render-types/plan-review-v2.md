---
RUN_ID: 2026-01-01__p4-1__render-types
VERSION: v2
TARGET: Phase 4 → Item 4.1
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v2.md
---

# Plan Review Report: Render Module Types

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v2.md

The plan addresses several v1 blockers (import contracts, VS typing intent, lint-imports gate, deterministic `Renderer` test), but it still leaves key implementation decisions and has internal inconsistencies with SSOT and the plan’s own file list.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope list is explicit. |
| 2 | Dependencies | FAIL | VS typing pattern is incomplete for strict Pyright (`reportMissingImports=true`): `TYPE_CHECKING` import must be ignored (repo precedent uses `# type: ignore`). Import-contract intent also doesn’t fully enforce forbidden imports (analysis↔render). |
| 3 | File List | FAIL | Plan requires recording “SSOT edits” to `render-module.md` but does not list that file under modifications; also `.gitkeep` delete is listed (good). |
| 4 | Contract Impact | PASS | Canonical contracts in `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` not touched. |
| 5 | Types Complete | FAIL | Plan claims “mechanically-checkable one-line signatures” but does not actually list the required public signatures (ctor/alias) in backticked one-liners. It also conflicts with SSOT dataclass decorators (“copy exactly” vs forcing `frozen=True, slots=True`). |
| 6 | Tests Complete | PASS | Test names + deterministic assertions are specified; includes defaults + `typing.get_args(Renderer)` runtime check. |
| 7 | Verification Complete | PASS | Includes pyright/ruff/pytest + `lint-imports` and uv-run fallbacks with explicit pass criteria. |
| 8 | Decision-Minimizing | FAIL | Dataclass mutability/slots/frozen choices are left as plan-level decisions that contradict SSOT code blocks; importlinter update does not fully specify how forbidden analysis↔render imports are enforced. |
| 9 | Determinism Defined | PASS | N/A for types-only slice. |

## Additional Quality Checks

- Error Codes: OK — no new/changed `FC-xxxx` errors.
- Failure Modes: Issue — plan must specify the exact Pyright-safe pattern for optional `vapoursynth` typing (ignore directive included).
- Derived Outputs: OK — no contract-derived view regen required.
- Rollback Guidance: OK — STOP rule present for unclear import contract failures.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact `TYPE_CHECKING` import line needed to avoid Pyright `reportMissingImports` for `vapoursynth`.
2. Whether to follow SSOT dataclass decorators (`@dataclass` / `@dataclass(frozen=True)`) or override with project conventions (`frozen=True, slots=True`)—plan currently asserts both.
3. Exact import-linter contract changes required to enforce the SSOT “Forbidden Imports” table for `analysis` vs `render` (currently only layers ordering is specified, which does not prevent `analysis` importing `render`).
4. Whether `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` is edited in this run (plan claims SSOT edits in `docs/DECISIONS.md` but does not include the file in the change list).

## Concrete Edits Required (for plan-v3.md)

1. **Make VS typing pattern Pyright-safe (no missing import errors)**
   - Section: `src/frame_compare/render/types.py` → “VS typing pattern”
   - Problem: `if TYPE_CHECKING: import vapoursynth as vs` will trigger Pyright `reportMissingImports` unless the environment always has VapourSynth installed.
   - Required Change: Specify the exact line to copy (match repo precedent in `src/frame_compare/analysis/metrics.py`):
     - `if TYPE_CHECKING: import vapoursynth as vs  # type: ignore`

2. **Add the required one-line public signatures (mechanically checkable)**
   - Section: `## Spec Anchors (SSOT)` (append a “Public API (signatures)” list immediately after anchors)
   - Problem: Plan does not actually list the signatures it claims to pin.
   - Required Change: Add backticked one-line signatures for each planned public symbol:
     - `OverlayMode(str, Enum)`
     - `EncoderSettings(format: str = "png", compression: int = 6, bit_depth: int = 8)`
     - `OverlayConfig(mode: OverlayMode, label: str, frame_number: int, resolution: tuple[int, int], hdr_info: str | None, font_path: Path | None, font_size: int = 24, position: str = "top-left")`
     - `RenderRequest(clip: vs.VideoNode | Path, frame_number: int, output_path: Path, overlay: OverlayConfig | None, encoder_settings: EncoderSettings)`
     - `Renderer = Literal["vapoursynth", "ffmpeg", "auto"]`
     - `ScreenshotResult(label: str, paths: list[Path], frame_count: int)`

3. **Remove or correctly scope the claimed SSOT edits**
   - Section: `docs/DECISIONS.md` required facts
   - Problem: Plan states “SSOT edits: Added OverlayMode (2.0) and ScreenshotResult (2.3) to render-module.md”, but those sections already exist in SSOT and the plan does not list `render-module.md` as a modified file.
   - Required Change (choose exactly one, explicitly):
     - Option A (recommended): Set “SSOT edits: None” and do not modify `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` in this run.
     - Option B: If SSOT truly needs edits, add `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` to the file list with the exact headings to change and the minimal bullet changes (but avoid spec churn unless necessary).

4. **Align dataclass decorators with SSOT (no convention overrides in this slice)**
   - Section: `src/frame_compare/render/types.py` → “Dataclass conventions”
   - Problem: Plan says “Copy exactly” from SSOT code blocks but also mandates `@dataclass(frozen=True, slots=True)` for all types; SSOT shows plain `@dataclass` for `RenderRequest`/`EncoderSettings`/`OverlayConfig` and only `ScreenshotResult` is `frozen=True`.
   - Required Change: Specify decorators to match SSOT exactly:
     - `RenderRequest`, `EncoderSettings`, `OverlayConfig`: `@dataclass`
     - `ScreenshotResult`: `@dataclass(frozen=True)`
     - Do not add `slots=True` in this run unless SSOT is updated to require it.

5. **Update import contracts to enforce forbidden `analysis`↔`render` imports**
   - Section: `importlinter.ini` [MODIFY]
   - Problem: Adding `frame_compare.render` to the layers list does not prevent `frame_compare.analysis` importing `frame_compare.render`, which is forbidden by `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md` (“Forbidden Imports”).
   - Required Change: Specify the exact additional import-linter contract to add so that `analysis` and `render` cannot import each other (plan must name the contract type and the exact module list to include, limited to modules that exist today).

## Ready for Implementation

Return to Planning Agent for revision. Next version: plan-v3.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-1__render-types

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v2.md
Write file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
