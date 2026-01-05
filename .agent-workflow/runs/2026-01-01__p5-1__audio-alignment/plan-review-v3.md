---
RUN_ID: 2026-01-01__p5-1__audio-alignment
VERSION: v3
TARGET: Phase 5 → Item 5.1 Audio Alignment
INPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v3.md
---

# Plan Review Report: Audio Alignment Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v3.md

Notes:
- `scripts/validate_spec_anchors.py` passes for `plan-v3.md`.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 5 → 5.1) with explicit dependency implementation (utils progress). |
| 2 | Dependencies | PASS | Dependency files are now listed; ffmpeg/ffprobe dependency and error mapping are specified. |
| 3 | File List | FAIL | Missing exact modification details for `src/frame_compare/utils/__init__.py` (`__all__` export list) and incomplete utils progress implementation vs SSOT. |
| 4 | Contract Impact | PASS | Explicit **NO**. |
| 5 | Types Complete | PASS | Public signatures are one-line backticked call forms anchored to SSOT headings. |
| 6 | Tests Complete | PASS | Deterministic vectors and concrete TOML fixture are specified; `_probe_fps` tests included. |
| 7 | Verification Complete | PASS | Commands + pass criteria present; lint/typecheck scopes include new utils file. |
| 8 | Decision-Minimizing | FAIL | Import-linter change is incorrect vs architecture SSOT; `utils/progress.py` scope is underspecified vs utils SSOT, leaving decisions to the Coding Agent. |
| 9 | Determinism Defined | PASS | Correlation vectors, tolerances, and cache parsing fixture are explicit. |

## Additional Quality Checks

- Error Codes: OK (no new errors).
- Failure Modes: OK for specified ones (ffprobe/ffmpeg missing/fail, empty audio, zero-norm, cache corruption/version mismatch).
- Derived Outputs: OK (contracts not touched).
- Rollback Guidance: Issue — plan must say “if import-linter contract design conflicts with SSOT, STOP and return to Planning”.
- SSOT Update Audit (this run): **OK with notes**
  - **services-module.md 2.2 (exception list):** OK; maps dependency failures to `FFmpeg*` and processing failures to `AudioAlignmentError` consistently.
  - **services-module.md 2.3 (FPS sourcing via ffprobe):** OK; avoids cross-layer import and is deterministic (string parsing).
  - **services-module.md cache schema/version:** OK and implementable; note that keying by `Path.stem` can collide and does not guard against stale files (recommended follow-up, not blocking this slice).
  - **services-module.md load_cached_offsets semantics (clips[0] ref, {} on no-match):** OK; removes ambiguity and is testable.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. **Import-linter layer placement for `frame_compare.services`** — plan’s “between render and vs” contradicts architecture SSOT (services is a sibling layer of analysis/render) and the existing end-state comment in `importlinter.ini`.
2. **utils progress completeness** — plan creates `src/frame_compare/utils/progress.py` but does not require implementing the full SSOT-defined public surface (Rich + Log reporters) and does not specify exact `src/frame_compare/utils/__init__.py` `__all__` changes.

## Concrete Edits Required (plan-v4)

1. **Fix `importlinter.ini` update to match SSOT**
   - Section: Plan → `importlinter.ini` [MODIFY]
   - Problem: Proposed ordering (“services between render and vs”) violates the layered dependency model (services must not be importable by render, and must not import render).
   - Required Change (plan text must specify exact edit): Update `[importlinter:contract:layers] layers =` so that `frame_compare.services` is in the same layer group as analysis/render:
     - Replace separate `frame_compare.analysis` and `frame_compare.render` entries with a single grouping line: `(frame_compare.analysis | frame_compare.render | frame_compare.services)`
     - Keep `frame_compare.vs` below that group (and keep config/utils/errors below vs).
   - Required Change (domain independence): Update `[importlinter:contract:domain-independence] modules =` to include `frame_compare.services`.

2. **Align `src/frame_compare/utils/progress.py` scope with utils SSOT**
   - Section: Plan → `src/frame_compare/utils/progress.py` [NEW]
   - Problem: Plan only specifies `ProgressReporter` + `NullProgressReporter`, but SSOT `utils-module.md` Section “4.2 Progress Reporting” defines additional public implementations (Rich + Log).
   - Required Change: Require implementing at least:
     - `RichProgressReporter`
     - `LogProgressReporter`
     - (and export them from `src/frame_compare/utils/__init__.py`)

3. **Make `src/frame_compare/utils/__init__.py` edit unambiguous**
   - Section: Plan → `src/frame_compare/utils/__init__.py` [MODIFY]
   - Problem: File uses `__all__`; plan only shows an import statement and does not specify `__all__` updates.
   - Required Change: Specify the exact `__all__` additions for the progress symbols being exported.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p5-1__audio-alignment

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-review-v3.md
Read file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v3.md
Write file: .agent-workflow/runs/2026-01-01__p5-1__audio-alignment/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
