---
RUN_ID: 2026-01-01__p4-5__encoders
VERSION: v4
TARGET: Phase 4 → Item 4.5
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v4.md
---

# Plan Review Report: Render Encoders

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v4.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | FAIL | Single slice is clear, but plan no longer includes an explicit out-of-scope section. |
| 2 | Dependencies | PASS | VS/FFmpeg dispatch strategy avoids requiring VapourSynth at runtime for type checks (Path vs non-Path). |
| 3 | File List | FAIL | Missing required documentation updates (`docs/DECISIONS.md`, `CHANGELOG.md`) that were present in earlier versions and are workflow-required. |
| 4 | Contract Impact | PASS | Contracts untouched. |
| 5 | Types Complete | PASS | All planned public function signatures are present and SSOT-anchored; `validate_spec_anchors.py` passes. |
| 6 | Tests Complete | FAIL | Tests still leave a small but material ambiguity: `run_subprocess` returns `CompletedProcess[bytes]`, so `_probe_fps` fixtures must specify stdout as bytes; also plan must state tests MUST NOT invoke real `ffprobe/ffmpeg` binaries (always mock `run_subprocess`). |
| 7 | Verification Complete | PASS | Commands and per-command pass criteria are explicit. |
| 8 | Decision-Minimizing | FAIL | Remaining decision points are small but real: whether tests use real external binaries vs mocks, and exact stdout byte/str handling for `_probe_fps`. |
| 9 | Determinism Defined | PASS | Seek-time floor policy + concrete vector are specified. |

## Additional Quality Checks

- Error Codes: OK — plan aligns to SSOT: internal dependency errors are wrapped into `RenderError` except `FrameExtractionError`.
- Failure Modes: OK — mapping enumerated; remaining ambiguity is only test fixture shape (bytes).
- Derived Outputs: OK — none.
- Rollback Guidance: OK — no SSOT contradictions detected in this revision.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Whether tests should call real `ffprobe/ffmpeg` (must be “NO”; mock `run_subprocess`).
2. Whether `_probe_fps` parses bytes or str stdout (must be bytes per `CompletedProcess[bytes]` contract).

## Concrete Edits Required (if CHANGES REQUIRED)

> [!IMPORTANT]
> This is `plan-v4`. Keep the `plan-v5` diff surgical; do not restructure unrelated sections.

1. **Restore explicit out-of-scope section**
   - Section: `## Scope`
   - Problem: Missing the required “does NOT cover” list.
   - Required Change:
     - Add `## Out of Scope` (or equivalent) listing at least: `render/orchestrator.py` (Phase 4.6), batch rendering, and progress reporting.

2. **Re-add workflow-required documentation updates**
   - Section: `## Files to Create/Modify`
   - Problem: Plan omits `docs/DECISIONS.md` and `CHANGELOG.md` updates (required by workflow/invariants).
   - Required Change:
     - Add `docs/DECISIONS.md` (MODIFY) with facts to record (encoders added; subprocess wrapper; deterministic seek policy; public wrapping policy).
     - Add `CHANGELOG.md` (MODIFY) entry for Phase 4.5 encoders/subproc.

3. **Make `_probe_fps` test vectors type-correct and non-flaky**
   - Section: `tests/render/test_encoders.py` (`test_probe_fps_logic`, `test_ffmpeg_seek_calculation`)
   - Problem: `run_subprocess` returns `CompletedProcess[bytes]`; plan uses string stdout examples and does not explicitly forbid real binary invocation.
   - Required Change:
     - Specify stdout fixtures as bytes, e.g. `b\"24000/1001\\n\"`.
     - Add an explicit rule under tests: “All tests MUST mock `run_subprocess` (no external `ffmpeg/ffprobe` required).”

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v5.md`

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-5__encoders

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-review-v4.md
Read file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v4.md
Write file: .agent-workflow/runs/2026-01-01__p4-5__encoders/plan-v5.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
