---
RUN_ID: 2025-12-28__p1-2__error-handling
VERSION: v1
TARGET: Phase 1 → Item 1.2 (Error Handling)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v1.md
---

# Plan Review Report: Error Handling Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Clear in-scope/out-of-scope. |
| 2 | Dependencies | FAIL | Missing explicit import constraint from SSOT (“leaf module: stdlib + typing only; must not import other frame_compare modules”). |
| 3 | File List | FAIL | Missing required doc updates (`docs/DECISIONS.md`, `CHANGELOG.md`) and missing explicit “generated outputs must not be edited” note in the file list section. |
| 4 | Contract Impact | FAIL | Marked “YES” but simultaneously says “No changes planned”; this is ambiguous and conflicts with Contract-First Loop guidance. |
| 5 | Types Complete | FAIL | Public API not mechanically checkable: exception “signatures” are not Pythonic `__init__` signatures, and `PublishError` is underspecified in SSOT (no code/constructor contract). |
| 6 | Tests Complete | FAIL | Claims “unit tests for all error types” but lists a small subset; missing required negative cases and deterministic assertions for formatting helpers. |
| 7 | Verification Complete | FAIL | Missing required workflow validation commands (`validate_run_id.py`, `validate_run_artifacts.py`, `validate_spec_anchors.py`) and explicit criteria for when to run contract gates. |
| 8 | Decision-Minimizing | FAIL | Leaves open decisions: exact `format_error_console()` output assertions; what “all error types” means in tests; how to handle SSOT/contract drift (extra FC codes). |
| 9 | Determinism Defined | FAIL | Tests could become order-sensitive (details dict rendering); determinism rules for assertions aren’t specified. |

## Additional Quality Checks

- Error Codes: Issue — contract contains codes not represented in `errors-module.md` (e.g., FC-1006, FC-3010/3011/3012, FC-5010/5011). Plan must explicitly state whether this slice implements only SSOT `errors-module.md` classes (recommended) and treats remaining contract codes as reserved/out-of-scope.
- Failure Modes: Issue — plan does not specify behavior for `get_exit_code()` on unknown/nonstandard codes (should follow SSOT: default `GENERAL_ERROR`).
- Derived Outputs: Issue — plan names generated `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` but does not explicitly state “do not edit; regen only”.
- Rollback Guidance: Issue — missing “if SSOT is ambiguous/drifting, stop and return to Planning/SSOT update” guidance.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. Whether contracts are actually being modified (plan says YES but also says no changes).
2. What to do about SSOT/contract drift (implement missing codes vs defer).
3. What `PublishError` is (marker base vs concrete FC code) and how/if it can be instantiated.
4. Exact `format_error_console()` expectations to encode into tests (line breaks, “For more details…” line, “Details:” rendering).
5. Whether tests must cover every new exception class or only a subset (plan contradicts itself).
6. How to avoid nondeterministic assertions around dict rendering/order.

## Concrete Edits Required (for `plan-v2.md`)

1. **Fix Contract Impact classification**
   - Section: `## Contract Impact`
   - Problem: Marked `Contracts touched: YES` while also stating no contract changes are planned.
   - Required Change: Set `Contracts touched: NO` unless `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml` will be modified. If keeping contract gates, move them under Verification as “optional safety checks” (or specify “run only if contract YAML changes”).

2. **Add missing workflow validation commands**
   - Section: `## Verification Commands`
   - Problem: Missing required artifact/spec validation commands from `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`.
   - Required Change: Add:
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-28__p1-2__error-handling`
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-28__p1-2__error-handling`
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v2.md`
     - Pass criteria: all exit 0.

3. **Make the file list complete (including required docs)**
   - Section: `## Files to Create/Modify`
   - Problem: Missing required repo persistence artifacts.
   - Required Change: Add planned updates for:
     - `docs/DECISIONS.md` (entry describing scope decisions, including how SSOT/contract drift is handled in this slice)
     - `CHANGELOG.md` (entry for new error hierarchy + formatting helpers)
     - Explicit note under “Derived outputs” that `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` must not be edited by hand.

4. **Resolve SSOT ambiguity for `PublishError` (SSOT update required)**
   - Section: `## Spec Anchors (SSOT)` + `src/frame_compare/errors.py` planned changes
   - Problem: `errors-module.md` declares `PublishError(ServiceError)` but provides no FC code nor instantiation contract; plan currently instructs adding an “empty class”, which still leaves behavior ambiguous.
   - Required Change (choose exactly one, SSOT-first):
     - **Update SSOT spec first:** edit `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md` to either (a) remove the “(FC-5xxx)” claim and define `PublishError` as a pure marker base (no concrete code), or (b) assign a concrete FC-5xxx code, add it to `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml`, and specify `__init__` signature + `ErrorContext` fields. Then update `plan-v2.md` anchors accordingly.

5. **Make types mechanically checkable**
   - Section: `## Spec Anchors (SSOT)` and the “Types to add” lists
   - Problem: Exception entries use “constructor returns error” pseudo-signatures; not a mechanically checkable API list.
   - Required Change: For every planned exception class, list its `__init__` signature in backticks (e.g., `class FFmpegError(DependencyError): __init__(self, details: str, returncode: int | None = None) -> None`) and explicitly state whether it sets attributes (e.g., `.path`, `.plugin`) per SSOT.

6. **Define “all error types” testing approach and add negative cases**
   - Section: `tests/test_errors.py` plan
   - Problem: Current test list covers only a subset and omits negative cases; leaves test design decisions to implementer.
   - Required Change: Specify either:
     - A single parametric test that enumerates *every* exception class added in this slice (exact list) and asserts: `code`, `name`, `hint` (non-empty), and `context.to_dict()` shape; OR
     - Individual per-class tests (explicitly listed) — but then list them all.
   - Add required negative/edge tests with exact names + assertions:
     - `format_error_console(verbose=False)` includes the SSOT “For more details…” line even when `details` exist.
     - `format_error_console(verbose=True)` includes a “Details:” line only when `error.context.details` is non-empty.
     - `get_exit_code()` returns `ExitCode.GENERAL_ERROR` for `GenericInternalError(...)` and for a synthetic `FrameCompareError(ErrorContext(code="FC-0000", ...))` (if allowed by SSOT; otherwise update SSOT).
   - Determinism rule: assertions must not rely on dict key ordering in rendered `Details:`; check presence of key substrings or compare parsed JSON structures.

7. **Explicitly state SSOT vs contract drift handling**
   - Section: `## Scope` (or a new `## Out of Scope` bullet)
   - Problem: Contract defines additional FC codes not covered by current module SSOT.
   - Required Change: Add an explicit rule: “This slice implements only the error classes defined in `errors-module.md` sections 3.2–3.6 + helpers in sections 4–5. Contract-only codes without SSOT classes are out-of-scope for this run.”

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-2__error-handling

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-review-v1.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v1.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan.

## Output
Write file: .agent-workflow/runs/2025-12-28__p1-2__error-handling/plan-v2.md
