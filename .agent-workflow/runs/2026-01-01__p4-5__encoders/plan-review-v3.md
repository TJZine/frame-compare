---
RUN_ID: 2026-01-01__p4-5__encoders
VERSION: v3
TARGET: Phase 4 → Item 4.5
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v3.md
---

# Plan Review Report: Render Encoders

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Phase 4.5 slice only. |
| 2 | Dependencies | FAIL | Plan still implies runtime dependence on `vapoursynth` via `sys.modules` test behavior; must specify dispatch/type-check strategy that does not require importing VapourSynth in unit tests. |
| 3 | File List | FAIL | Plan adds `src/frame_compare/render/__init__.py` export of `RenderError` without SSOT anchor (SSOT shows importing errors from `frame_compare.errors`, not `frame_compare.render`). |
| 4 | Contract Impact | PASS | No canonical contracts touched. |
| 5 | Types Complete | PASS | Public/internal function signatures are explicit and spec-anchored; `validate_spec_anchors.py` passes for plan-v3. |
| 6 | Tests Complete | FAIL | Tests include incorrect/ambiguous assertions (`exc.cause` vs Python `__cause__`), and dispatch tests are inconsistent with SSOT (dispatch is by `request.clip` type, not `sys.modules`). `_probe_fps` numeric tolerance is not specified. |
| 7 | Verification Complete | FAIL | Commands are listed, but pass criteria are partially inaccurate (mentions “strict mode” though command is `pyright --warnings`); must pin exit-0 expectations for each command. |
| 8 | Decision-Minimizing | FAIL | Remaining decisions: how to detect VS clip type without VapourSynth installed; whether to add logging; error wrapping details (cause propagation field). |
| 9 | Determinism Defined | PASS | Seek-time floor policy + a concrete seek test vector are provided. |

## Additional Quality Checks

- Error Codes: OK — SSOT now pins FFmpeg error mapping and render_frame wrapping policy; plan aligns on “wrap into `RenderError` except `FrameExtractionError`”.
- Failure Modes: Issue — plan must specify behavior if VapourSynth is not installed but a non-`Path` clip-like object is passed (unit test doubles).
- Derived Outputs: OK — none.
- Rollback Guidance: Issue — missing explicit “STOP and return to Planning” instruction when assumptions are violated (e.g., tests require VapourSynth).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Dispatch implementation vs tests: `auto` selection is by `request.clip` type per SSOT, but plan tests use `sys.modules` gating.
2. Error cause assertion: plan tests refer to `exc.cause`, but the error system uses Python exception chaining (`__cause__`) unless SSOT adds a `.cause` field/property.
3. Public API exports: whether `RenderError` should be exported from `frame_compare.render` (currently not SSOT-defined).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Revise plan-v4: Remove non-SSOT public export**
   - Section: `src/frame_compare/render/__init__.py` (MODIFY)
   - Problem: Plan says export `RenderError` from `frame_compare.render`, but SSOT error usage imports `RenderError` from `frame_compare.errors`.
   - Required Change:
     - Change this step to: “Export `render_frame` only” (no `RenderError` export), unless you also update SSOT to require that export (not recommended for this slice).

2. **Revise plan-v4: Make VS/FFmpeg dispatch tests consistent with SSOT**
   - Section: `tests/render/test_encoders.py`
   - Problem: `test_render_frame_vs_dispatch` / `test_render_frame_ffmpeg_dispatch` rely on `sys.modules["vapoursynth"]` presence, but SSOT `### 3.1 Frame Rendering` defines dispatch by inspecting `request.clip` type.
   - Required Change:
     - Replace the dispatch test requirements with:
       - VS path test uses a non-`Path` test double for `request.clip` (e.g., a `FakeClip` with `.get_frame`) and asserts `_render_vs` is called.
       - FFmpeg path test uses `request.clip=Path(...)` and asserts `_render_ffmpeg` is called.
     - Explicitly state the dispatch implementation rule used by code (to avoid VapourSynth dependency): `if isinstance(request.clip, Path)` → FFmpeg else → VS (and mismatch handling for explicit renderer values).

3. **Revise plan-v4: Fix error-wrapping assertion to match error system**
   - Section: `tests/render/test_encoders.py` (`test_error_wrapping`)
   - Problem: Plan asserts `exc.cause` exists; current error types are regular exceptions, so cause is represented by `exc.__cause__` when using `raise ... from ...`.
   - Required Change:
     - Require: `with pytest.raises(RenderError) as excinfo: ...; assert isinstance(excinfo.value.__cause__, FFmpegNotFoundError)`.
     - Require that implementation uses Python chaining: `raise RenderError() from inner_exc` (or equivalent) and does not invent new `.cause` API.

4. **Revise plan-v4: Pin `_probe_fps` float tolerance**
   - Section: `tests/render/test_encoders.py` (`test_probe_fps_logic`)
   - Problem: “23.976...” is not a checkable contract without a tolerance.
   - Required Change:
     - Specify `pytest.approx(24000 / 1001, rel=1e-6)` (or explicitly chosen tolerance) for the returned fps.

5. **Revise plan-v4: Verification pass criteria wording**
   - Section: `## Verification Commands`
   - Problem: “pyright passes (no errors in strict mode)” is not what the command enforces.
   - Required Change:
     - Replace with explicit per-command pass criteria: “each command exits 0”; for lint-imports: “No violations”.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v4.md` (keep edits surgical; avoid churn outside the items above).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-5__encoders

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v3.md
Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v3.md
Write file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
