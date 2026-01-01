---
RUN_ID: 2026-01-01__p4-1__render-types
VERSION: v4
TARGET: Phase 4 → Item 4.1
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v4.md
---

# Plan Review Report: Render Module Types

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v4.md

This is `plan-v4`, so iteration-cap rules apply: treat remaining issues as a spec/mechanical-gate mismatch and require the smallest SSOT + plan edits needed to unblock implementation with zero decisions. The remaining blocker is SSOT anchor validation readiness: the plan’s “Public API (signatures)” section does not provide backticked one-line signatures in a format that satisfies the repo’s mechanical gate (`scripts/validate_spec_anchors.py`) and the workflow’s SSOT anchoring rule.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope list explicit. |
| 2 | Dependencies | PASS | Optional VS typing pattern + import contract work specified. |
| 3 | File List | PASS | Explicit create/modify/delete list including `.gitkeep` + `importlinter.ini`. |
| 4 | Contract Impact | PASS | Canonical contracts untouched. |
| 5 | Types Complete | FAIL | “Public API (signatures)” lists `class …` entries (no constructor signatures); does not meet SSOT anchoring rule and will not satisfy `validate_spec_anchors.py` signature extraction. |
| 6 | Tests Complete | PASS | Deterministic runtime assertions specified. |
| 7 | Verification Complete | FAIL | Missing explicit plan-validation gate: plan must be able to pass `scripts/validate_spec_anchors.py` before Coding starts; current signature format cannot. |
| 8 | Decision-Minimizing | FAIL | Coding Agent would have to decide how to interpret/express public signatures and how to satisfy SSOT anchor validation. |
| 9 | Determinism Defined | PASS | N/A for types-only slice. |

## Additional Quality Checks

- Error Codes: OK — no new/changed `FC-xxxx`.
- Failure Modes: OK — VS typing pattern is explicit and Pyright-safe (via `# type: ignore`).
- Derived Outputs: OK — no contract-derived regen required.
- Rollback Guidance: OK — STOP conditions present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. The plan does not provide mechanically checkable one-line signatures (as required by SSOT anchoring rule / plan-validation script), so implementation would require guesswork or out-of-band fixes.

## Concrete Edits Required (SSOT update required)

1. **Make type constructor signatures discoverable by the spec-anchor validator**
   - Problem: The repo’s plan gate (`scripts/validate_spec_anchors.py`) requires at least one backticked signature bullet containing `(...)` and then checks the anchored SSOT text contains the symbol name with either a `def` or a call-form `Name(` substring. For these dataclass types, the SSOT currently defines `class EncoderSettings:` / `class RenderRequest:` / `class OverlayConfig:` / `class ScreenshotResult:` without any call-form examples, so constructor signatures cannot be validated unless SSOT includes at least one deterministic call-form usage.
   - Required SSOT Change (minimal, no behavior change):
     - Edit file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
       - Under heading: `### 2.1 RenderRequest` add a short “Example construction” code snippet containing **at least**:
         - `EncoderSettings()`
         - `RenderRequest(clip=Path("…"), frame_number=0, output_path=Path("…"), overlay=None, encoder_settings=EncoderSettings())`
       - Under heading: `### 2.2 OverlayConfig` add a short snippet containing **at least**:
         - `OverlayConfig(mode=OverlayMode.STANDARD, label="…", frame_number=0, resolution=(1920, 1080), hdr_info=None, font_path=None)`
       - Under heading: `### 2.3 ScreenshotResult` add a short snippet containing **at least**:
         - `ScreenshotResult(label="…", paths=[Path("…")], frame_count=1)`

2. **Update plan signatures to be one-line constructor signatures (backticked)**
   - Section: `## Public API (signatures)` in `.agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v5.md`
   - Problem: Current list is not a signature list and is not mechanically checkable.
   - Required Change: Replace with one-line ctor/alias signatures, e.g.:
     - `OverlayMode(str, Enum)`
     - `EncoderSettings(format: str = "png", compression: int = 6, bit_depth: int = 8)`
     - `RenderRequest(clip: vs.VideoNode | Path, frame_number: int, output_path: Path, overlay: OverlayConfig | None, encoder_settings: EncoderSettings)`
     - `OverlayConfig(mode: OverlayMode, label: str, frame_number: int, resolution: tuple[int, int], hdr_info: str | None, font_path: Path | None, font_size: int = 24, position: str = "top-left")`
     - `Renderer = Literal["vapoursynth", "ffmpeg", "auto"]`
     - `ScreenshotResult(label: str, paths: list[Path], frame_count: int)`

3. **Add an explicit plan-validation step (must-pass)**
   - Section: `## Verification Commands`
   - Required Change: Add:
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v5.md`
   - Pass criteria: exits 0.

## Ready for Implementation

Return to Planning Agent for revision. Next version: plan-v5.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-1__render-types

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "### 2.1 RenderRequest" add/change:
  - Add an “Example construction” snippet containing `EncoderSettings()` and `RenderRequest(..., encoder_settings=EncoderSettings())`.
- Under heading: "### 2.2 OverlayConfig" add/change:
  - Add an “Example construction” snippet containing `OverlayConfig(..., hdr_info=None, font_path=None)`.
- Under heading: "### 2.3 ScreenshotResult" add/change:
  - Add an “Example construction” snippet containing `ScreenshotResult(label=\"…\", paths=[Path(\"…\")], frame_count=1)`.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v4.md
Read file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v4.md
Write file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v5.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
