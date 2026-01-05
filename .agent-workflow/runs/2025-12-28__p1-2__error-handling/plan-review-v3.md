---
RUN_ID: 2025-12-28__p1-2__error-handling
VERSION: v3
TARGET: Phase 1 → Item 1.2 (Error Handling)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v3.md
---

# Plan Review Report: Error Handling Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit out-of-scope list. |
| 2 | Dependencies | PASS | Leaf-module import constraint stated. |
| 3 | File List | PASS | Includes code, tests, `docs/DECISIONS.md`, and `CHANGELOG.md`; derived-output “do not edit” is clear enough for this slice. |
| 4 | Contract Impact | PASS | `Contracts touched: NO` and no regeneration gates are required for this run. |
| 5 | Types Complete | PASS | SSOT anchors present and helper signatures listed in backticks. |
| 6 | Tests Complete | FAIL | Missing exact test function names for the parametric exception test and the ExitCode tests; also contains an incorrect exception-count claim (“38”). |
| 7 | Verification Complete | FAIL | Commands are listed, but explicit “pass” criteria (exit 0 + no warnings) is missing, and contract gates are marked optional without a clear “when to run” condition. |
| 8 | Decision-Minimizing | FAIL | Remaining decisions: which exact test names to use, and whether to parametrize 38 vs the full set (tables enumerate 44 FC-coded exceptions). |
| 9 | Determinism Defined | PASS | Console-details assertions use stable substrings (`'path'`, `'/cache'`) and avoid dict-order comparisons. |

## Additional Quality Checks

- Error Codes: OK — `PublishError` SSOT ambiguity is resolved in `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md` (now explicitly a marker base, never instantiated).
- Failure Modes: OK — unknown code mapping to `GENERAL_ERROR` is specified.
- Derived Outputs: OK — derived contract views are not edited; optional contract gates are listed.
- Rollback Guidance: OK — “SSOT clarification required? STOP” is explicit.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. Exact names for the parametric exception test and ExitCode tests (plan requires “exact test names” but does not provide them).
2. Whether to cover 38 vs 44 exceptions (tables list 44 FC-coded instantiable exceptions; plan states 38).
3. When optional contract gates should be run (always vs only if contract/spec files change).

## Concrete Edits Required (for `plan-v4.md`)

1. **Fix the exception-count mismatch**
   - Section: `### 2. NEW tests/test_errors.py`
   - Problem: Plan claims “38 new exception classes” but the plan’s tables enumerate 44 FC-coded instantiable exception classes (8 dependency + 9 input + 16 processing + 8 network + 3 internal).
   - Required Change: Replace the count with a correct value (`44`) or remove the number entirely and say “parametrize over every FC-coded exception listed in the tables above (in table order)”.

2. **Specify exact test function names (Hard Requirement)**
   - Section: `### 2. NEW tests/test_errors.py`
   - Problem: Parametric test and ExitCode tests have behavior described but no exact function names, leaving the Coding Agent to choose.
   - Required Change: Provide the exact list of test function names and what each asserts, at minimum:
     - `test_exception_class_contract` (parametric; iterates all FC-coded exceptions listed above)
     - `test_exit_code_enum_values`
     - `test_get_exit_code_config`
     - `test_get_exit_code_dependency`
     - `test_get_exit_code_input`
     - `test_get_exit_code_processing`
     - `test_get_exit_code_network`
     - `test_get_exit_code_internal`
     - `test_get_exit_code_unknown`
     - Keep the existing formatting test names as already specified.

3. **Make verification pass criteria explicit**
   - Section: `## Verification Commands`
   - Problem: Missing explicit pass criteria and “when to run optional contract gates”.
   - Required Change:
     - Add: “Pass criteria: all commands exit 0; `pyright` emits no warnings; `ruff` emits no findings; pytest exits 0.”
     - Add: “Run optional contract gates only if any file under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` changed in this run; otherwise skip.”

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-2__error-handling

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v3.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v3.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan.

## Output
Write file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v4.md
