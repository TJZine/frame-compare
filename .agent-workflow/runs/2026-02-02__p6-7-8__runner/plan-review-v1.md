---
RUN_ID: 2026-02-02__p6-7-8__runner
VERSION: v1
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Create `src/frame_compare/runner.py` at package root (see `cli-module.md` §1.2)
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
  - importlinter.ini
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-review-v1.md
---

# Plan Review Report: runner.py Package-Root Scaffold

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-03
**Plan Reference:** `.agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v1.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | One checklist item; out-of-scope is clearly listed. |
| 2 | Dependencies | FAIL | Plan omits required `importlinter.ini` update to add `frame_compare.runner` as a layer (enforced by `lint-imports`). |
| 3 | File List | FAIL | File list is incomplete: must include `importlinter.ini` (otherwise verification can fail once `frame_compare.runner` exists). |
| 4 | Contract Impact | PASS | Contracts are not touched in this slice. |
| 5 | Types Complete | PASS | Public signature is listed: `run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult`. |
| 6 | Tests Complete | FAIL | Tests are described as “suggestions”; required exact test names/assertions and a negative case are missing. |
| 7 | Verification Complete | PASS | Commands are listed; add explicit “exit code 0” pass criteria in the plan revision. |
| 8 | Decision-Minimizing | FAIL | Leaves test names and `NotImplementedError` details to the Coding Agent. |
| 9 | Determinism Defined | N/A | No randomness/ordering requirements in this slice. |

## Additional Quality Checks

- Error Codes: OK (no CLI/exit-code mapping in this slice)
- Failure Modes: Issue (plan must specify the exact `NotImplementedError` message to keep behavior stable/testable)
- Derived Outputs: OK (none)
- Rollback Guidance: OK (low-risk slice; reverting `runner.py` + the test file is sufficient)
- SSOT Update Audit (if SSOT changed this loop): OK (no SSOT edits proposed)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

Remaining decision points to remove in `plan-v2.md`:
1. Whether/how to update `importlinter.ini` for the new `frame_compare.runner` layer.
2. Exact test file path and test function names/assertions.
3. Exact `NotImplementedError` message raised by `frame_compare.runner.run(...)`.

## Concrete Edits Required (for `plan-v2.md`)

1. **Add `importlinter.ini` update to keep `lint-imports` passing**
   - Section: `## Files to Create/Modify`
   - Problem: `importlinter.ini` layered contract does not currently include `frame_compare.runner`, but the architecture SSOT expects it as a top-level layer.
   - Required Change:
     - Add a third file entry: **[MODIFY] `importlinter.ini`**.
     - Specify the exact edit under `[importlinter:contract:layers]` → `layers =` list:
       - Insert `frame_compare.runner` immediately after `frame_compare.cli_entry` and before `frame_compare.orchestration`.
     - Add a brief note that `frame_compare.runner` may import `frame_compare.orchestration.*` but `frame_compare.orchestration.*` must not import `frame_compare.runner`.

2. **Make tests fully specified (names, assertions, negative case)**
   - Section: `2. [NEW] tests/...`
   - Problem: Test names are explicitly “suggestions” and do not define a negative case.
   - Required Change (pick one path and make it normative; do not leave alternatives):
     - Keep the planned file path (`tests/test_runner_import_smoke.py`) OR move it to a more specific folder, but state exactly one final path.
     - Specify at least these exact tests (or equivalent with explicit names and assertions):
       - `def test_runner_exports_public_symbols() -> None:` asserts `RunRequest`, `RunResult`, `RunDependencies`, and `run` exist on `frame_compare.runner`.
       - `def test_runner_run_is_scaffold_raises() -> None:` asserts `frame_compare.runner.run(...)` raises `NotImplementedError` with a stable message (use `pytest.raises(..., match=...)`).

3. **Make the scaffold failure behavior explicit**
   - Section: `1. [NEW] src/frame_compare/runner.py` and `## Acceptance Criteria`
   - Problem: Plan leaves the exact raised message unspecified.
   - Required Change:
     - Specify: `run(...)` MUST raise `NotImplementedError` with an exact message string (include the literal message in the plan) until the dedicated runner implementation slice lands.
     - Add `run` to the “Types to export”/public surface notes (so the public surface is complete and testable).

4. **Add explicit pass criteria to verification**
   - Section: `## Verification Commands`
   - Problem: Commands are present but pass criteria are implied.
   - Required Change:
     - Add a single line: “Pass criteria: all commands exit with code 0.”

## Ready for Implementation

Return to Planning Agent for `plan-v2.md` addressing the concrete edits above. Coding must not proceed until the revised plan is APPROVED and decision points are NONE.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-02-02__p6-7-8__runner

## Files to Read
1. Read file: `.agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v1.md`
2. Read file: `.agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-review-v1.md`
3. Read file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md` (Runner §§3.1–3.4)
4. Read file: `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md` (import-linter layer ordering)
5. Read file: `importlinter.ini`

## Your Task
Revise the plan to remove all decision points called out in `plan-review-v1.md`, producing an implementation-ready `plan-v2.md` with fully specified files, tests, and verification details.

## Output
Write file: `.agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v2.md`

## Note
After plan approval, the Coding Agent output for this run remains: `.agent-workflow/runs/2026-02-02__p6-7-8__runner/impl-v1.md`
