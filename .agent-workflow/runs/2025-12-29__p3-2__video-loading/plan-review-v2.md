---
RUN_ID: 2025-12-29__p3-2__video-loading
VERSION: v2
TARGET: Phase 3 → Item 3.2 Video Loading
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-review-v2.md
---

# Plan Review Report: Video Source Loading

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v2.md

SSOT gaps from plan-v1 are addressed in `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` (raise contract, HDRMetadata mapping/defaults, apply_trim semantics). Remaining blockers are plan-level: Spec Anchors are still not verbatim headings (not mechanically checkable), `load_source()` loader selection deviates from the SSOT plugin-detection pattern, and the proposed test mocks rely on instance-level `__getitem__` (won’t work for slicing).

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice, explicit out-of-scope list. |
| 2 | Dependencies | PASS | Phase 3.1 dependency and VS plugin assumptions identified. |
| 3 | File List | PASS | Complete and explicit list. |
| 4 | Contract Impact | PASS | Explicit NO; contract freshness checks remain check-only. |
| 5 | Types Complete | FAIL | `## Spec Anchors (SSOT)` does not copy/paste verbatim SSOT headings (missing `###`/`##` markers). |
| 6 | Tests Complete | FAIL | `tests/vs/test_source.py` mock plan is not implementable as written (instance `__getitem__` won’t satisfy slicing semantics). |
| 7 | Verification Complete | FAIL | Missing required plan-gate command from workflow: `scripts/validate_spec_anchors.py` for the plan artifact. |
| 8 | Decision-Minimizing | FAIL | Loader selection logic leaves a correctness decision (must match SSOT plugin detection patterns). |
| 9 | Determinism Defined | PASS | Determinism for HDR detection rules + trim semantics is now SSOT-defined and reflected in tests. |

## Additional Quality Checks

- Error Codes: OK — explicit `FC-2003` / `FC-4015` assertions listed.
- Failure Modes: OK — missing plugin vs corrupt file differentiated per updated SSOT.
- Derived Outputs: OK — check-only commands included.
- Rollback Guidance: OK — STOP rule present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Loader selection: whether to select `core.lsmas` based on mere presence vs verified `LWLibavSource` existence (must be specified to match SSOT).
2. Test doubles: how to implement a sliceable “clip” mock that correctly supports `clip[start:]` and `clip[start:end+1]` (plan currently suggests an approach that will not work).

## Concrete Edits Required (plan-only)

1. **Fix Spec Anchors to be verbatim headings**
   - Section: `## Spec Anchors (SSOT)`
   - Problem: Uses `Section: "3.2 Source Loading"` etc., which is not a verbatim heading line.
   - Required Change: Replace every anchor line with the exact heading text including markdown markers, e.g.:
     - `### 3.2 Source Loading`
     - `### 5.1 HDR Detection`
     - `### 2.1 SourceInfo`
     - `### 1.3 VSLoader Protocol`
     - `### 1.4 Plugin Detection`
     - `## 6. Error Handling`
     - `### 3.2 Dependency Errors (FC-2xxx) — Exit Code 3` (errors-module)
     - `### 3.4 Processing Errors (FC-4xxx) — Exit Code 5` (errors-module)

2. **Make loader selection match SSOT plugin detection**
   - Section: `src/frame_compare/vs/source.py` → `load_source` implementation details
   - Problem: `loader = core.lsmas if hasattr(core, 'lsmas') else core.lw` can pick `lsmas` even when only `lw.LWLibavSource` exists (SSOT allows this).
   - Required Change: Specify exact selection logic (no discretion), aligned to `### 1.4 Plugin Detection`:
     - If `hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource")`: use `core.lsmas`
     - Else: use `core.lw` (and assume it has `LWLibavSource` because `require_plugin(core, "lsmas")` already passed)

3. **Fix test mock design for slicing**
   - Section: `tests/vs/test_source.py` → helper(s)
   - Problem: Special methods like `__getitem__` are looked up on the class, not the instance; `SimpleNamespace(__getitem__=...)` won’t make `clip[start:]` work.
   - Required Change: Plan must specify a concrete, minimal mock class for a sliceable clip, e.g. `class MockClip: ... def __getitem__(self, s: slice) -> MockClip: ...`, and state exactly how `num_frames` is updated for slices so the `apply_trim` tests can assert deterministically.

4. **Add the required plan-spec-anchor validation gate**
   - Section: `## Verification Commands`
   - Problem: Missing workflow-required plan gate.
   - Required Change: Add this command (must-pass) with explicit pass criteria:
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v3.md`

## Ready for Implementation

Return to Planning Agent for a plan-only revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-2__video-loading

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-review-v2.md
Read file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v2.md
Write file: .agent-workflow/runs/2025-12-29__p3-2__video-loading/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
