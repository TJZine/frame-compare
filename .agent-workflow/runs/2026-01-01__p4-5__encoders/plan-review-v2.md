---
RUN_ID: 2026-01-01__p4-5__encoders
VERSION: v2
TARGET: Phase 4 → Item 4.5
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v2.md
---

# Plan Review Report: Render Encoders

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; no scope sprawl. |
| 2 | Dependencies | FAIL | Plan does not pin runtime import strategy for optional `vapoursynth` + external `ffmpeg/ffprobe` presence, nor specify error mapping for missing binaries. |
| 3 | File List | PASS | Includes encoders + subproc + tests + docs; adds `render/__init__.py` modify. |
| 4 | Contract Impact | PASS | No canonical contracts touched; contract regen gates not needed. |
| 5 | Types Complete | PASS | Public + internal signatures are explicit and SSOT-anchored; `validate_spec_anchors.py` passes. |
| 6 | Tests Complete | FAIL | Test names exist, but required assertions are underspecified (exact exception classes/codes, deterministic numeric expectations, and overlay/encoding failure cases). |
| 7 | Verification Complete | FAIL | Commands listed, but explicit pass criteria (exit codes / “no violations”) are missing. |
| 8 | Decision-Minimizing | FAIL | Leaves key behavior choices unresolved (FFmpeg error class mapping, whether/when to raise `EncodingError`/`OverlayError`, and how to type-check `vs.VideoNode` without hard dependency). |
| 9 | Determinism Defined | FAIL | Seek-time formula is pinned, but `_probe_fps` parsing rules + numeric tolerances are not specified and tests do not define concrete deterministic vectors. |

## Additional Quality Checks

- Error Codes: Issue — render-module SSOT now pins dispatch + seek determinism, but error mapping is still internally inconsistent/underspecified (render-module `4.2` references FC-2006/FC-4015 while `6. Error Handling` lists only FC-4xxx render errors). Plan must not choose silently.
- Failure Modes: Issue — missing explicit behavior for: missing `ffprobe`, non-zero ffprobe exit, unreadable ffprobe output, and image save failures.
- Derived Outputs: OK — none in scope.
- Rollback Guidance: Issue — plan does not state “STOP and return to Planning” if SSOT contradictions are found during coding.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. `_render_ffmpeg` error contract: whether to raise `FFmpegNotFoundError`/`FFmpegError`/`SourceLoadError` vs wrapping into `RenderError`.
2. Overlay + encoding failures: when to raise `OverlayError` / `EncodingError` vs generic `RenderError`.
3. VapourSynth runtime dependency: exact import/type-check policy for `vs.VideoNode` and behavior on `ImportError`.
4. `_probe_fps` parsing: algorithm, error handling, and test tolerances for float output.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT: Make FFmpeg error contract unambiguous**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
   - Under heading: `### 4.2 FFmpeg Rendering`
   - Problem: SSOT lists error codes (FC-2006/FC-4015) but does not define which exception classes are raised for each failure mode (missing binary, non-zero exit, probe failure, etc.).
   - Required Change (minimal, deterministic; add as bullets under the existing “Errors”/policy block):
     - Map `FileNotFoundError` for `ffmpeg`/`ffprobe` to `FFmpegNotFoundError (FC-2005)`.
     - Map `subprocess.CalledProcessError` from `ffmpeg` to `FFmpegError (FC-2006)` using stderr + returncode.
     - Map `subprocess.CalledProcessError` from `ffprobe` (or invalid/unparseable output) to `SourceLoadError (FC-4015)` with `engine_error` describing the probe failure.
     - State explicitly whether `render_frame()` propagates these errors as-is or wraps them into `RenderError` (choose one and document).

2. **Update SSOT: Align module-level error list with FFmpeg policy**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
   - Under heading: `## 6. Error Handling`
   - Problem: The “Error classes used by this module” table omits dependency errors referenced in `4.2`.
   - Required Change (minimal):
     - Add the decided FFmpeg-related errors (`FFmpegNotFoundError`, `FFmpegError`, and/or `SourceLoadError`) to the table if they may escape `render_frame()`, OR explicitly state that `render_frame()` always wraps them into `RenderError` (and remove FC-2005/2006/4015 references from `4.2` accordingly).

3. **Revise plan-v3: Specify exact error mapping + overlay/encoding behavior**
   - Section: `src/frame_compare/render/encoders.py` plan bullets
   - Required Change:
     - Add an explicit “Error Mapping” subsection listing, per function (`render_frame`, `_render_vs`, `_render_ffmpeg`, `_probe_fps`), which exception classes are raised for each failure mode (type mismatch, get_frame failure, ffmpeg/ffprobe missing, non-zero exits, overlay failure, image save failure, unexpected exceptions).
     - Remove “export RenderError” from `src/frame_compare/render/__init__.py` unless that export is added to SSOT; keep export change to `render_frame` only.

4. **Revise plan-v3: Make tests mechanically checkable**
   - Section: test lists
   - Required Change (keep existing test names; add assertions):
     - For each test, specify exact assertions (e.g., exception class + `.code`, called helper name, exact `-ss` argument value for a provided `(frame, fps)` vector, `pytest.approx` tolerance for fps parse).
     - Add negative tests for overlay/encoding failure mapping (e.g., `apply_overlay` raises → `OverlayError` vs `RenderError`; `Image.save` raises → `EncodingError` vs `RenderError`), consistent with SSOT after update.

5. **Revise plan-v3: Verification pass criteria**
   - Section: `## Verification Commands`
   - Required Change:
     - Add explicit pass criteria: “all commands exit 0”, `lint-imports` reports “No violations”, and pytest runs deterministically (no network, no external binaries required due to mocking).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-5__encoders

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "### 4.2 FFmpeg Rendering" add/change:
  - Define exact exception mapping for ffmpeg/ffprobe failures: `FileNotFoundError` → `FFmpegNotFoundError (FC-2005)`; `CalledProcessError` from `ffmpeg` → `FFmpegError (FC-2006)`; `CalledProcessError` from `ffprobe` (or invalid output) → `SourceLoadError (FC-4015)`.
  - State explicitly whether `render_frame()` propagates these errors or wraps them into `RenderError (FC-4004)`; reconcile any removed/added error codes accordingly.

Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "## 6. Error Handling" add/change:
  - Align the “Error classes used by this module” table with the decision above (include FFmpeg-related errors if they may escape `render_frame()`, or explicitly state they are always wrapped into `RenderError` and remove them from `4.2`).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v2.md
Write file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
