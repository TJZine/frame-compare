---
RUN_ID: 2026-02-02__p6-7-7__rundependencies
VERSION: v2
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement RunDependencies for dependency injection
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-review-v2.md
---

# Plan Review Report: RunDependencies (Dependency Injection)

## Verdict: CHANGES_REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-03
**Plan Reference:** .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Scope is narrow and explicitly excludes `runner.py` and `execute_run(...)`. |
| 2 | Dependencies | PASS | No new external deps; plan keeps tests pure (no FFmpeg/VapourSynth/network). |
| 3 | File List | PASS | Files are enumerated; additions are localized to orchestration + tests (docs updates are optional but acceptable). |
| 4 | Contract Impact | PASS | Declares “Contracts touched: NO”. |
| 5 | Types Complete | FAIL | Plan leaves ambiguous ownership/signatures for new protocol + default impl (see required edits #1/#2). |
| 6 | Tests Complete | FAIL | Missing explicit coverage for default `ffmpeg_runner` provider behavior; `Functions to implement` list is currently misleading (see required edits #2/#3). |
| 7 | Verification Complete | PASS | Includes Command Canon gates and a targeted pytest invocation. |
| 8 | Decision-Minimizing | FAIL | Leaves at least one material implementation choice unresolved (DefaultFFmpegRunner behavior/location and doc mismatch handling). |
| 9 | Determinism Defined | N/A | DI container slice; no new nondeterministic behavior introduced beyond injected `clock`. |

## Additional Quality Checks

- Error Codes: OK (no new error codes proposed in this slice)
- Failure Modes: Issue (Default FFmpeg runner behavior is underspecified; needs an explicit “stub vs real” decision)
- Derived Outputs: OK (no contracts/codegen)
- Rollback Guidance: OK (additive types/exports; revert is straightforward)
- SSOT Update Audit (if SSOT changed this loop): OK (plan states no SSOT changes)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: 2

1. **Default FFmpeg runner behavior (this slice):** Should `DefaultFFmpegRunner` be a pure stub (raising `NotImplementedError`) or a minimal real implementation (subprocess-backed) consistent with existing error types?
2. **SSOT/example mismatch handling:** `testing-strategy.md` and `api-design.md` show `RunDependencies` shapes/imports that do not match the plan’s chosen temporary export location; plan must explicitly resolve how the Coding Agent should interpret these anchors for this slice.

## Concrete Edits Required (for plan-v3)

1. **Clarify DI surface ownership + exact signatures**
   - Section: “Files to Create/Modify” + “Functions to implement”
   - Problem: The plan does not explicitly state that `FFmpegRunner` (Protocol) and `DefaultFFmpegRunner` will live in `src/frame_compare/orchestration/coordinator.py`, nor does it list the exact method signatures with owning type context.
   - Required Change:
     - Add a short bullet under `src/frame_compare/orchestration/coordinator.py` explicitly listing the new symbols to introduce there:
       - `FFmpegRunner(Protocol)` with method signatures (wrapped in backticks)
       - `DefaultFFmpegRunner` with method signatures (wrapped in backticks)
       - `RunDependencies` fields + `get_vs_loader(...)` / `get_ffmpeg_runner(...)` signatures (wrapped in backticks)

2. **Resolve “stub vs real” DefaultFFmpegRunner decision**
   - Section: “Scope” + “Implementation notes” + “Acceptance Criteria”
   - Problem: The plan simultaneously calls for a “default implementation stub/adapter” and lists `extract_frame(...)` / `probe_hdr(...)` under “Functions to implement”, which reads like a requirement to implement real FFmpeg behavior now.
   - Required Change (choose one; must be explicit):
     - **Option A (stub in this slice):** State that `DefaultFFmpegRunner` methods raise `NotImplementedError` (or a project error type) and are intentionally non-functional until a later 6.7 slice implements real FFmpeg execution; update acceptance criteria accordingly.
     - **Option B (minimal real impl in this slice):** State where the implementation comes from (e.g., wrappers around existing `render/` or `services/` helpers, or a new subprocess implementation), plus the exact error behavior required (e.g., raise `FFmpegNotFoundError` when missing, raise `FFmpegError` on non-zero exit). Keep tests deterministic by testing only wiring and error mapping without executing real binaries.
     - Remove or rewrite the “Functions to implement” bullets so they match the chosen option (and include `self` for methods).

3. **Tighten the test requirements to match acceptance criteria**
   - Section: `tests/orchestration/test_run_dependencies.py` (ADD) + “Acceptance Criteria”
   - Problem: Tests listed do not explicitly require validating default `ffmpeg_runner` provider behavior (only injected override). This risks shipping a `get_ffmpeg_runner()` that returns a stub/None unexpectedly.
   - Required Change:
     - Add one explicit test requirement for `get_ffmpeg_runner()` when `ffmpeg_runner` is not injected (and, if relevant, that the default is constructed lazily, mirroring the `vs_loader` requirement).

## Ready for Implementation

Return to Planning Agent for `plan-v3.md` with the concrete edits above. Coding Agent must not proceed until this Plan Review verdict becomes APPROVED and decision points are NONE.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-02-02__p6-7-7__rundependencies

## Precondition
Read file: .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-review-v2.md
Confirm: Verdict is APPROVED and Implementation Agent Decision Points Remaining is NONE.
If either condition is false: STOP and return to the human orchestrator (do not write impl-v1.md).

## Files to Read
1. .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-v2.md
2. .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-review-v2.md

## Output
Write file: .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/impl-v1.md
