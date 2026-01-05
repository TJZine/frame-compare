---
RUN_ID: 2025-12-28__p1-1__config-module
VERSION: v5
TARGET: Phase 1 → Item 1.1 (Configuration Module)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v5.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v5.md
---

# Plan Review Report: Configuration Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v5.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice with explicit out-of-scope items. |
| 2 | Dependencies | PASS | `tomli-w` is runtime; dev tooling install is explicit. |
| 3 | File List | PASS | Fully enumerated and self-contained. |
| 4 | Contract Impact | PASS | Explicit “Contracts touched: NO”. |
| 5 | Types Complete | PASS | Type narrowing/casts specified; no `type: ignore`. |
| 6 | Tests Complete | FAIL | `test_save_preset_roundtrip` asserts an equality that is likely impossible because TOML cannot represent `None` values present in `model_dump(mode="json")`. |
| 7 | Verification Complete | FAIL | Preset save path is under-specified for optional `None` fields; current algorithm likely errors or produces data that cannot satisfy acceptance criteria. |
| 8 | Decision-Minimizing | FAIL | Coding Agent would have to decide how to handle `None` values when serializing presets to TOML. |
| 9 | Determinism Defined | PASS | Deterministic output requirement is explicit. |

## Additional Quality Checks

- Error Codes: OK
- Failure Modes: Issue — behavior for optional `None` fields in preset serialization is not specified (TOML has no null)
- Derived Outputs: OK
- Rollback Guidance: OK

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. How `save_preset()` handles `None` values (omit keys vs stringify vs other).
2. What the round-trip contract is when optional keys are omitted (dump equality vs applied-config equality).

## Concrete Edits Required (for plan-v6.md)

1. **Define preset serialization rules for `None` explicitly**
   - Section: `src/frame_compare/config/presets.py` and `tests/config/test_presets.py`
   - Problem: `config.model_dump(mode="json")` includes optional keys with `None`, but TOML cannot represent null; tomli-w is unlikely to support `None`.
   - Required Change: Choose exactly one rule and make plan/tests consistent:
     - Option A (recommended): Serialize with `exclude_none=True` (and state whether `exclude_defaults` is used). Example: `data = config.model_dump(mode="json", exclude_none=True)`.
     - Option B: Keep `None` fields by mapping them to a representable value (must specify per-field mapping and update schema validators accordingly).

2. **Fix acceptance criteria and `test_save_preset_roundtrip` to match the chosen rule**
   - Section: `tests/config/test_presets.py` + Acceptance Criteria
   - Problem: Current test asserts `load_preset() == config.model_dump(mode="json")`, which conflicts with TOML limitations.
   - Required Change: Specify the exact assertions. For Option A, one valid contract is:
     - `loaded_data == original_config.model_dump(mode="json", exclude_none=True)`
     - and/or `ConfigSchema.model_validate(loaded_data).model_dump(mode="json") == original_config.model_dump(mode="json")` (if defaults fill missing keys).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v6.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-1__config-module

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v5.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v5.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan as a new file (do not edit plan-v5 in place).

## Output
Write file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v6.md
