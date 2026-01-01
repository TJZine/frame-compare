---
RUN_ID: 2026-01-01__p4-5__encoders
VERSION: v5
TARGET: Phase 4 → Item 4.5
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v5.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v5.md
---

# Plan Review Report: Render Encoders

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v5.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice with explicit out-of-scope. |
| 2 | Dependencies | FAIL | Plan does not pin `encoders.py` optional VapourSynth import strategy (must avoid runtime `import vapoursynth` for unit tests). |
| 3 | File List | PASS | Includes code, tests, and required doc updates. |
| 4 | Contract Impact | PASS | Contracts untouched. |
| 5 | Types Complete | PASS | All planned public signatures are listed and spec anchors validate. |
| 6 | Tests Complete | FAIL | Missing a test that enforces SSOT overlay integration (call `apply_overlay` when `request.overlay` is set) and missing coverage for `run_subprocess(check=False)` behavior that is part of the SSOT API. |
| 7 | Verification Complete | PASS | Commands + explicit exit-0 criteria are present. |
| 8 | Decision-Minimizing | FAIL | Coding Agent still must decide how to implement optional `vapoursynth` typing/imports and whether overlay is tested vs “assumed”. |
| 9 | Determinism Defined | PASS | Seek-time policy and deterministic test vector are specified. |

## Additional Quality Checks

- Error Codes: OK — internal FFmpeg/probe errors wrap into `RenderError` per SSOT.
- Failure Modes: OK — enumerated mapping is adequate for this slice.
- Derived Outputs: OK — none.
- Rollback Guidance: OK — no new SSOT changes required.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Optional VapourSynth import/typing strategy in `encoders.py` (runtime vs TYPE_CHECKING).
2. Overlay integration enforcement via tests (currently not present).
3. `run_subprocess(check=False)` behavior (API exists but no test requirement).

## Concrete Edits Required (if CHANGES REQUIRED)

> [!IMPORTANT]
> This is `plan-v5` (iteration cap territory). Keep the `plan-v6` diff surgical; do not rewrite/reshuffle unrelated sections.

1. **Pin VapourSynth optional import strategy (plan-only)**
   - Section: `src/frame_compare/render/encoders.py` plan bullets
   - Problem: Without an explicit import strategy, Coding Agent may introduce a hard runtime dependency on VapourSynth and break unit tests.
   - Required Change:
     - Add a “Imports/typing” bullet requiring:
       - `from __future__ import annotations`
       - `from typing import TYPE_CHECKING`
       - `if TYPE_CHECKING: import vapoursynth as vs  # type: ignore`
       - Use `vs.VideoNode` only in annotations/TYPE_CHECKING contexts; dispatch logic is `Path` vs non-`Path` per SSOT.

2. **Add overlay integration test requirements (plan-only)**
   - Section: `tests/render/test_encoders.py`
   - Problem: SSOT `### 3.1 Frame Rendering` requires overlay integration; plan does not require a test that fails if `apply_overlay` is skipped.
   - Required Change:
     - Add `test_render_frame_overlay_integration`:
       - For VS path: `request.clip=FakeClip()`, `request.overlay` non-None; assert `apply_overlay` called once before save.
       - For FFmpeg path: `request.clip=Path(...)`, `request.overlay` non-None; mock `PIL.Image.open` + `apply_overlay`; assert `apply_overlay` called and final save invoked.

3. **Add `run_subprocess(check=False)` test requirement (plan-only)**
   - Section: `tests/utils/test_subproc.py`
   - Problem: SSOT `run_subprocess(..., check: bool = True)` includes non-default behavior; plan currently tests only `check=True`.
   - Required Change:
     - Add `test_run_subprocess_check_false` asserting a non-zero exit does **not** raise and returns a `CompletedProcess` with `returncode != 0`.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v6.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-5__encoders

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v5.md
Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v5.md
Write file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v6.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
