---
RUN_ID: 2025-12-28__p1-2__error-handling
VERSION: v2
TARGET: Phase 1 → Item 1.2 (Error Handling)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v2.md
---

# Plan Review Report: Error Handling Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit out-of-scope list, including contract-only codes. |
| 2 | Dependencies | PASS | Leaf-module import constraints are explicit. |
| 3 | File List | PASS | Includes `src/frame_compare/errors.py`, `tests/test_errors.py`, `docs/DECISIONS.md`, `CHANGELOG.md`, plus derived-output “do not edit” note. |
| 4 | Contract Impact | PASS | Correctly `NO` and contract gates are optional safety checks. |
| 5 | Types Complete | FAIL | Hard SSOT rule not met: plan lacks a backticked, one-line signature list for planned public functions; `PublishError` behavior contradicts SSOT wording (“Publishing failed (FC-5xxx)”) and needs SSOT clarification first. |
| 6 | Tests Complete | PASS | Parametric coverage is exhaustive and includes negative cases; determinism guidance present. |
| 7 | Verification Complete | PASS | Includes quality gates + workflow validators + optional contract gates, with pass criteria. |
| 8 | Decision-Minimizing | FAIL | Remaining implementation decisions: `PublishError` semantics (SSOT ambiguity), exact determinism substring assertions, and `CHANGELOG.md` insertion rules. |
| 9 | Determinism Defined | PASS | Explicitly avoids dict-order/string exactness; adds “no-details” case. |

## Additional Quality Checks

- Error Codes: OK (explicitly treats contract-only codes as out-of-scope), but **PublishError is still SSOT-ambiguous**.
- Failure Modes: OK (unknown code mapping explicitly tested).
- Derived Outputs: OK (explicitly “do not edit”).
- Rollback Guidance: Issue — plan should explicitly instruct “if SSOT clarification is required, stop and revise SSOT + plan; do not improvise”.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. Whether `PublishError` is a marker base with no FC code (plan) vs a concrete FC-5xxx error (SSOT wording implies).
2. Exact substring assertions for `format_error_console(verbose=True)` details output (plan’s example `'"path":'` is likely incorrect for Python dict repr).
3. Where/how to insert `CHANGELOG.md` entry without duplicating `[Unreleased]` / `### Added` headers.
4. Plan is 440 lines (>350 rule-of-thumb) without justification; needs de-duplication to reduce churn.

## Concrete Edits Required (for `plan-v3.md`)

1. **Add required “Planned Public Signatures” list (Hard Requirement)**
   - Section: `## Spec Anchors (SSOT)`
   - Problem: Missing mechanically checkable function signatures wrapped in backticks.
   - Required Change: Add a subsection listing at minimum:
     - `get_exit_code(error: FrameCompareError) -> ExitCode`
     - `format_error_console(error: FrameCompareError, *, verbose: bool = False) -> str`
     - `format_error_json(error: FrameCompareError) -> dict[str, JSONValue]`

2. **Resolve `PublishError` SSOT ambiguity (SSOT update required)**
   - Section: SSOT file `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`, under “Service-Level Error Aliases (FC-4xxx/FC-5xxx)”
   - Problem: SSOT text `class PublishError(ServiceError): """Publishing failed (FC-5xxx)."""` implies a concrete FC code, but provides no code/constructor contract; plan defines it as a marker base with no FC code.
   - Required Change: Update SSOT to one unambiguous interpretation, then update plan-v3 to match:
     - Preferred: define `PublishError` as a **marker base with no FC code** (remove “Publishing failed (FC-5xxx)” phrasing, or replace with “Publishing errors (FC-5xxx) marker base; concrete publish errors use NetworkError subclasses”).
     - Then list `PublishError` as “no `__init__`; never instantiated directly” in the plan.
   - Contract Impact: remains `NO` if only spec doc is changed.

3. **Make `format_error_console` determinism assertions fully explicit**
   - Section: `tests/test_errors.py` + “Notes for Coding Agent” determinism bullet
   - Problem: Current example substring `'"path":'` likely won’t appear because `Details: {dict}` uses Python `dict.__repr__` (single quotes).
   - Required Change: Specify exact assertions using a specific error instance with details, e.g.:
     - Use `CacheCorruptionError(Path("/cache"))` (details key is `path`) and assert `"Details:"`, `"'path'"`, and `"/cache"` are present (or equivalent unambiguous substrings).

4. **Remove remaining doc-edit decision in `CHANGELOG.md`**
   - Section: `### 4. UPDATE CHANGELOG.md`
   - Problem: “Entry to add” leaves ambiguity if `[Unreleased]`/`### Added` already exist.
   - Required Change: Specify deterministic edit rule:
     - “Append these bullets under the existing `## [Unreleased]` → `### Added` section; if `### Added` is missing, create it under `[Unreleased]`; do not create duplicate `[Unreleased]` headers.”

5. **Reduce plan length below anti-churn threshold**
   - Section: Whole plan
   - Problem: `plan-v2.md` is 440 lines (>350) without justification and contains duplicated lists (tables + tuple list).
   - Required Change: Remove redundant pasted code blocks (especially the full parametrize tuple list) and keep exactly one canonical enumeration of classes/constructors (either the tables or the param list), referencing SSOT for message/hint/details content.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-2__error-handling

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v2.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v2.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan.

## Output
Write file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v3.md
