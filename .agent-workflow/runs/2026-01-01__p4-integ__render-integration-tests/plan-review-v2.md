---
RUN_ID: 2026-01-01__p4-integ__render-integration-tests
VERSION: v2
TARGET: Phase 4 → Integration Tests & Quality Gate
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-review-v2.md
---

# Plan Review Report: Render Module Integration Tests & Phase 4 Quality Gate

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v2.md

Plan-v2 fixes the major Phase 4 gaps (adds VS + orchestrator tests and workflow validators). Remaining issues are about deterministic and correct execution of the tests: the FFmpeg “autouse” skip fixture would incorrectly skip non-FFmpeg tests (overlay-only and VS) when FFmpeg is absent, and the VS test leaves critical runtime choices unspecified (clip format compatible with current encoder implementation). The Coding Agent would have to make decisions.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: Phase 4 render integration tests; explicit out-of-scope list. |
| 2 | Dependencies | PASS | Calls out `ffmpeg` + `ffprobe` and VS import/skip policy; no network. |
| 3 | File List | PASS | Complete and explicit; removed conditional `tests/conftest.py` change. |
| 4 | Contract Impact | PASS | “Contracts touched: NO”; no regen required. |
| 5 | Types Complete | PASS | All targeted public signatures listed and anchored to render SSOT headings. |
| 6 | Tests Complete | FAIL | Skip fixture is scoped incorrectly (skips overlay + VS tests when FFmpeg missing); VS test lacks explicit clip format + fully specified `RenderRequest` fields. |
| 7 | Verification Complete | PASS | Includes run-artifact validators + quality-gate commands + pass criteria. |
| 8 | Decision-Minimizing | FAIL | Leaves the Coding Agent to choose (a) how to scope FFmpeg skipping, (b) VS clip format compatible with encoder, and (c) how to guarantee “3 frames” deterministically. |
| 9 | Determinism Defined | FAIL | FFmpeg fixture uses duration math for “3 frames” without an explicit `-frames:v 3` guarantee; skip scoping currently hides non-FFmpeg tests. |

## Additional Quality Checks

- Error Codes: OK (no new errors)
- Failure Modes: Issue — FFmpeg missing should skip only FFmpeg-dependent tests; VS missing should skip only VS-dependent tests
- Derived Outputs: OK
- Rollback Guidance: OK (“STOP and return to Planning” present)
- SSOT Update Audit (if SSOT changed this loop): N/A

## Implementation Agent Decision Points Remaining

1. Whether `require_ffmpeg` should be autouse (it must not skip overlay-only / VS tests).
2. Which VapourSynth clip format to use so `_render_vs` can round-trip into PIL deterministically (must avoid subsampled YUV and float formats given current encoder implementation).
3. How to guarantee the “3-frame CFR video” claim deterministically (duration alone is not a hard guarantee across encoders/builds).
4. Exact `RenderRequest(...)` field values for each test (avoid implicit “...” construction).

## Concrete Edits Required (plan-v3.md)

1. **Scope FFmpeg skip to FFmpeg-dependent tests only**
   - Section: `tests/integration/conftest.py` fixture list
   - Problem: `require_ffmpeg` is specified as an autouse fixture, which would skip `test_overlay_application_adds_visible_content` and `test_vs_render_creates_valid_png` when FFmpeg is unavailable.
   - Required Change (choose one, but specify it explicitly in the plan):
     - Option A (preferred): Make `require_ffmpeg` a normal fixture (not autouse) and only depend on it via `mock_video_path(tmp_path, require_ffmpeg)` so only tests using `mock_video_path` skip.
     - Option B: Keep it autouse but make it conditional on a required marker (e.g., `@pytest.mark.ffmpeg_required`) and specify exactly which tests carry that marker.

2. **Make the FFmpeg test video frame count hard-deterministic**
   - Section: `mock_video_path` fixture command
   - Problem: Using `d=0.3` to imply “3 frames at 10fps” can be encoder/build dependent.
   - Required Change: Add an explicit frame cap in the fixture command (e.g., include `-frames:v 3`) and restate the deterministic guarantee in the plan.

3. **Pin a VS clip format compatible with current encoder behavior**
   - Section: `tests/integration/test_render_vs.py` test definition
   - Problem: Current render implementation builds a numpy array via `np.dstack(planes)` and calls `PIL.Image.fromarray(array)`. This requires same-shaped planes and a PIL-compatible dtype; subsampled YUV planes and float RGB formats are not safe.
   - Required Change: Specify `BlankClip(..., format=vs.RGB24)` (or another explicitly safe, same-plane-shape 8-bit format) and keep it consistent across environments.

4. **Fully specify `RenderRequest(...)` construction in each test**
   - Section: `tests/integration/test_render_pipeline.py` and `tests/integration/test_render_vs.py`
   - Problem: Plan uses `RenderRequest(...)` with ellipses, leaving values for `overlay` and `encoder_settings` implicit.
   - Required Change: For each test, list the exact `RenderRequest` fields and values (e.g., `overlay=None`, `encoder_settings=EncoderSettings()`), and pin all output filenames/paths.

5. **Fix DECISIONS artifact-version bullet for the revised plan**
   - Section: `docs/DECISIONS.md` required facts
   - Problem: The “Artifact versions” bullet still hardcodes `plan-review-v1`; plan-v3 should require recording the actual `plan-review-vN` produced for this plan revision.
   - Required Change: Replace with a rule like “Artifact versions: plan-v3 + plan-review-v3 + impl-v1 + verify-v1 + review-v1 (or as written)” so it stays correct across revisions.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-integ__render-integration-tests

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v2.md
Write file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
