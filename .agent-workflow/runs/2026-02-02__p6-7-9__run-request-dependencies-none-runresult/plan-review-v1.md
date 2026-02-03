---
RUN_ID: 2026-02-02__p6-7-9__run-request-dependencies-none-runresult
VERSION: v1
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement `run(request, dependencies=None) -> RunResult` entry point in `src/frame_compare/runner.py` (see `cli-module.md` §2.1)
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - importlinter.ini
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-review-v1.md
---

# Plan Review Report: `frame_compare.runner.run` Entry Point

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-03
**Plan Reference:** .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | In-scope/out-of-scope boundaries are explicit and aligned with 6.7 slice intent. |
| 2 | Dependencies | PASS | Uses `httpx.AsyncClient` and orchestration progress selection per SSOT; no new external tools required for unit tests. |
| 3 | File List | PASS | Files to touch are enumerated and exist (`src/frame_compare/runner.py`, `tests/test_runner_import_smoke.py`). |
| 4 | Contract Impact | PASS | No canonical contracts touched. |
| 5 | Types Complete | PASS | Public signature and types are specified and already exist in `orchestration.coordinator`. |
| 6 | Tests Complete | PASS* | Test intent is solid, but needs one additional “event loop already running” behavior test after clarifying sync→async policy (see edits). |
| 7 | Verification Complete | PASS | Commands are concrete and include spec-anchor validator + import-linter. |
| 8 | Decision-Minimizing | FAIL | Plan leaves key implementation choices to Coding Agent (sync→async runner policy; how to call/patch missing `execute_run`). |
| 9 | Determinism Defined | N/A | No ordering/seeded behavior introduced in this slice. |

## Additional Quality Checks

- Error Codes: OK (explicitly out of scope for this slice).
- Failure Modes: Issue — `run()` behavior when invoked from an existing event loop is unspecified; `asyncio.run()` will raise a generic error unless handled intentionally.
- Derived Outputs: OK (no derived-view generators involved).
- Rollback Guidance: OK (single-module wrapper; revert is localized).
- SSOT Update Audit (if SSOT changed this loop): OK (no SSOT/spec/contract edits in plan-v1).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Sync→async execution policy for `run(...)` (which runner to use; what to do if an event loop is already running).
2. How `run(...)` references `frame_compare.orchestration.coordinator.execute_run` given it does not yet exist (must be patchable for unit tests without requiring `execute_run` to be implemented in this slice).

## Concrete Edits Required (for plan-v2)

1. **Specify the sync→async runner policy (eliminate event-loop decision)**
   - Section: `Files to Create/Modify` → `src/frame_compare/runner.py` “Implementation requirements”
   - Problem: “using an event loop runner” is underspecified; Coding Agent must choose `asyncio.run` vs alternatives and must decide what happens when `run()` is called under an already-running event loop.
   - Required Change:
     - Add an explicit subsection that commits to one policy. Recommended minimal policy:
       - Use `asyncio.run(...)` for the synchronous entry point.
       - If an event loop is already running, raise a `RuntimeError` with a clear message instructing programmatic callers to use the async entry point (e.g., `await frame_compare.orchestration.coordinator.execute_run(...)`) instead of calling `run(...)` from async contexts.
     - Add (or update) acceptance criteria and a unit test covering the “event loop already running” case to ensure the error is deterministic and user-friendly.

2. **Make `execute_run` lookup + monkeypatch target explicit (eliminate missing-symbol ambiguity)**
   - Section: `Files to Create/Modify` → `tests/test_runner_import_smoke.py` “Tests required”, and `runner.py` “Delegate to execute_run”
   - Problem: `frame_compare.orchestration.coordinator.execute_run` is not present yet; without an explicit lookup strategy, Coding Agent must decide whether to import the symbol directly (hard to monkeypatch) vs resolving it via module attribute (patchable).
   - Required Change:
     - Specify that `runner.run` must resolve `execute_run` from the **module** (e.g., `import frame_compare.orchestration.coordinator as coordinator` and call `coordinator.execute_run`) so unit tests can monkeypatch `coordinator.execute_run` without requiring it to exist in this slice.
     - Specify the behavior if `execute_run` is still absent at runtime and not monkeypatched (raise a clear `NotImplementedError` mentioning the missing symbol path).
     - Update the test plan to explicitly monkeypatch `frame_compare.orchestration.coordinator.execute_run` and validate:
       - the returned `RunResult` is propagated,
       - deps passed to `execute_run` are non-None,
       - http client lifecycle rules are honored.

3. **Clarify “do not mutate caller-owned dependencies” mechanics**
   - Section: `Files to Create/Modify` → `src/frame_compare/runner.py` “Construct an effective RunDependencies”
   - Problem: Plan states “without mutating caller-owned dependencies” but does not specify how (noting `RunDependencies` is a mutable dataclass in current code).
   - Required Change:
     - Specify that `runner.run` constructs a new “effective” `RunDependencies` instance (copy) rather than mutating the provided instance, and that it should not trigger lazy initialization (`get_vs_loader()` / `get_ffmpeg_runner()`) as part of wrapper wiring.

## Ready for Implementation

Return to Planning Agent for `plan-v2.md` incorporating the concrete edits above. Coding Agent must not proceed until Plan Review is re-run and Verdict is APPROVED with Decision Points Remaining: NONE.

---

## NEXT AGENT PROMPT (COPY/PASTE)

### If Verdict is CHANGES REQUIRED (use this now)

You are the Planning Agent for Frame Compare 2.0.

You MUST follow FC2 STOP rules and templates from:
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md

## RUN_ID
2026-02-02__p6-7-9__run-request-dependencies-none-runresult

## Your Task
Revise the plan to address the concrete required edits in the plan review report.

## Inputs
1. Read file: .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v1.md
2. Read file: .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-review-v1.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md

## Output
Write file: .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v2.md

## STOP
Do not proceed to coding. After writing `plan-v2.md`, hand off to Plan Review Agent for `plan-review-v2.md`.

### If Verdict is APPROVED (only valid after a future APPROVED plan-review)

You are the Coding Agent for Frame Compare 2.0.

You MUST follow FC2 STOP rules and templates from:
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
- docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md

## RUN_ID
2026-02-02__p6-7-9__run-request-dependencies-none-runresult

## Preconditions (STOP if unmet)
- Plan Review verdict is APPROVED
- Implementation Agent Decision Points Remaining: NONE

## Inputs
1. Read file: .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-v1.md (or newer approved plan)
2. Read file: .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/plan-review-v1.md (or newer approved plan review)

## Output
Write file: .agent-workflow/runs/2026-02-02__p6-7-9__run-request-dependencies-none-runresult/impl-v1.md
