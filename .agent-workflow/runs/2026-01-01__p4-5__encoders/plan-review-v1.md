---
RUN_ID: 2026-01-01__p4-5__encoders
VERSION: v1
TARGET: Phase 4 → Item 4.5
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v1.md
---

# Plan Review Report: Render Encoders

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 4.5 encoders) with explicit out-of-scope items. |
| 2 | Dependencies | FAIL | Missing explicit dependency + import strategy for `vapoursynth`, `PIL`, `numpy`, and external `ffmpeg`/`ffprobe` availability + error mapping expectations. |
| 3 | File List | FAIL | Missing required export update in `src/frame_compare/render/__init__.py` (public API). Also adds `utils/subproc.py` but does not anchor to `utils-module.md` SSOT for its signature/behavior. |
| 4 | Contract Impact | PASS | Contracts not touched; no contract regen gates needed. |
| 5 | Types Complete | FAIL | `run_subprocess` signature/raises in plan conflicts with `utils-module.md` SSOT and `errors-module.md` (cannot instantiate `DependencyError`). Error mapping for `render_frame`/encoders not fully specified. |
| 6 | Tests Complete | FAIL | Test list exists but assertions, negative cases, and error-code expectations are not fully specified (e.g., exact exception class + `.code` checks, ffprobe parsing cases, renderer/clip-type mismatch). |
| 7 | Verification Complete | FAIL | Commands are listed, but pass criteria are not explicit and `lint-imports` gate is omitted (workflow expects it as a must-pass quality gate unless explicitly out-of-scope). |
| 8 | Decision-Minimizing | FAIL | Leaves implementation choices open (VS availability detection, overlay application boundary, PIL vs cv2, FFmpeg seek-time rounding/parsing, which typed errors to raise vs wrap). |
| 9 | Determinism Defined | FAIL | FFmpeg seek-time rounding (“floor to 3 decimals”), ffprobe parsing rules, and stable command construction are not fully pinned. |

## Additional Quality Checks

- Error Codes: Issue — plan references FC codes but does not specify exact exception classes + mapping rules per failure mode (missing ffmpeg/ffprobe, ffmpeg non-zero, timeout, VS import failure, invalid renderer/clip-type).
- Failure Modes: Issue — missing explicit behavior for: `request.clip` type mismatch vs `renderer`, missing `ffmpeg`/`ffprobe`, `subprocess.TimeoutExpired`, and overlay/font failures.
- Derived Outputs: OK — no contract-derived outputs in scope.
- Rollback Guidance: Issue — no “stop and return to Planning” guidance if SSOT contradictions are discovered during implementation.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. `run_subprocess` contract (signature + raise types) is ambiguous/inconsistent across SSOT (`utils-module.md` vs `errors-module.md`).
2. `render_frame` renderer selection policy is not specified for `request.clip: vs.VideoNode | Path` combinations.
3. Overlay application policy is not specified (where/how applied in VS vs FFmpeg path).
4. FFmpeg determinism details are incomplete (ffprobe parsing and seek-time rounding policy).
5. Missing public export updates for `frame_compare.render` API surface.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT: Fix subprocess wrapper exception contract**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`
   - Section: `### 4.5 Subprocess Wrapper`
   - Problem: SSOT states `run_subprocess` raises `DependencyError`, but `DependencyError` is non-instantiable per `errors-module.md` (base class with no `__init__`); current plan also specifies a different signature/exception surface.
   - Required Change (minimal, deterministic):
     - Specify `run_subprocess(..., check: bool = True) -> subprocess.CompletedProcess[bytes]` uses `subprocess.run(..., shell=False, capture_output=True, check=check, timeout=timeout_seconds, cwd=cwd)`.
     - Specify raises: `FileNotFoundError`, `subprocess.TimeoutExpired`, `subprocess.CalledProcessError` (when `check=True` and non-zero exit).
     - Remove/replace all claims that it raises `DependencyError` directly.

2. **Update SSOT: Render-frame dispatch + overlay integration**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
   - Section: `### 3.1 Frame Rendering`
   - Problem: SSOT defines `RenderRequest.clip` as `vs.VideoNode | Path` but does not specify dispatch rules and overlay application behavior; plan currently leaves these as Coding-Agent choices.
   - Required Change (minimal, deterministic):
     - Define dispatch rules for `renderer` × `request.clip` type:
       - `renderer="vapoursynth"` requires `vs.VideoNode`, otherwise raise `RenderError` or `FrameExtractionError` (choose one and name it).
       - `renderer="ffmpeg"` requires `Path`, otherwise raise `RenderError` or `FrameExtractionError` (choose one and name it).
       - `renderer="auto"`: use VS when `request.clip` is `vs.VideoNode`; use FFmpeg when `request.clip` is `Path` (no `sys.modules` heuristic).
     - Define overlay rule: if `request.overlay is not None`, call `apply_overlay` before final save for both renderers.

3. **Update SSOT: FFmpeg seek-time and fps probing**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
   - Section: `### 4.2 FFmpeg Rendering`
   - Problem: SSOT snippet references `settings.fps` but `EncoderSettings` does not define `fps`; seek-time rounding/parsing needs a deterministic rule.
   - Required Change (minimal, deterministic):
     - Remove `settings.fps` reference and require fps probing via `_probe_fps(video_path)` (avg_frame_rate).
     - Define seek-time rounding precisely: `seek_seconds = floor((frame / fps) * 1000) / 1000`, then format with 3 decimals.

4. **Revise plan after SSOT updates**
   - Section: `## Spec Anchors (SSOT)`
   - Problem: Plan does not anchor to the SSOT that defines `run_subprocess` contract.
   - Required Change:
     - Add `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md` with `Section: "4.5 Subprocess Wrapper"`.
     - Add `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md` anchors covering all error classes the run will raise/catch (e.g., `RenderError`, `FrameExtractionError`, `EncodingError`, `OverlayError`, `FFmpegNotFoundError`, `FFmpegError`, `VapourSynthNotFoundError`), and update the plan’s error-mapping rules accordingly.

5. **Revise plan: File list + tests + verification gates**
   - Section: `## Files to Create/Modify`, `## Verification Commands`, tests sections
   - Required Change:
     - Add `src/frame_compare/render/__init__.py` (MODIFY) to export `render_frame`.
     - Update test list to include exact assertions per case:
       - Exception class + `.code` assertions for typed errors.
       - Renderer/clip-type mismatch negative tests.
       - Deterministic seek-time and ffprobe parse tests (e.g., `"24000/1001"` → expected float).
     - Add `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` to verification commands and specify pass criteria (“exit 0”).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-5__encoders

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
- Under heading: "### 4.5 Subprocess Wrapper" add/change:
  - Define `run_subprocess(argv: Sequence[str], *, timeout_seconds: float | None = None, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]` and specify it uses `subprocess.run(..., shell=False, capture_output=True, check=check, timeout=timeout_seconds, cwd=cwd)`.
  - Replace the current “Raises” contract with: `FileNotFoundError`, `subprocess.TimeoutExpired`, `subprocess.CalledProcessError` (when `check=True` and non-zero exit); remove `DependencyError` direct instantiation language.

Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "### 3.1 Frame Rendering" add/change:
  - Define renderer dispatch rules for `renderer` × `request.clip` type (VS requires `vs.VideoNode`; FFmpeg requires `Path`; `auto` selects by `request.clip` type).
  - Define overlay rule: if `request.overlay is not None`, call `apply_overlay` before final save in both paths.

Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "### 4.2 FFmpeg Rendering" add/change:
  - Remove the `settings.fps` reference; require `_probe_fps(video_path)` as the fps source.
  - Define seek-time rounding precisely: `seek_seconds = floor((frame / fps) * 1000) / 1000`, then format with 3 decimals.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v1.md
Write file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
