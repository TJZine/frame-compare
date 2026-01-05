---
RUN_ID: 2025-12-28__p1-1__config-module
VERSION: v4
TARGET: Phase 1 → Item 1.1 (Configuration Module)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v4.md
---

# Plan Review Report: Configuration Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v4.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit in/out scope. |
| 2 | Dependencies | PASS | `tomli-w` is a runtime dependency; verification installs dev tooling explicitly. |
| 3 | File List | PASS | Fully enumerated; plan is now self-contained. |
| 4 | Contract Impact | PASS | Explicit “Contracts touched: NO”. |
| 5 | Types Complete | PASS | No `type: ignore`; narrowing/casts specified; JSON-safe error normalization specified. |
| 6 | Tests Complete | FAIL | Several tests use ambiguous terms (“idempotent”) without defining the exact assertion/equality semantics, leaving decisions to the Coding Agent. |
| 7 | Verification Complete | PASS | Commands are explicit and runnable (`uv sync --group dev`, then `.venv/bin/*`). |
| 8 | Decision-Minimizing | FAIL | Ambiguous test assertions and an inconsistent enum comment leave room for interpretation. |
| 9 | Determinism Defined | PASS | Deterministic preset output is explicitly required and tested. |

## Additional Quality Checks

- Error Codes: OK (`FC-1001`..`FC-1005` defined in stub)
- Failure Modes: OK (STOP triggers + rollback)
- Derived Outputs: OK
- Rollback Guidance: OK

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact equality/round-trip assertion for `test_save_preset_roundtrip` (“idempotent” is underspecified).
2. Whether the “all enums lowercase” comment is authoritative vs the `LogLevel` enum values (uppercase).

## Concrete Edits Required (for plan-v5.md)

1. **Make preset round-trip/idempotency assertions explicit**
   - Section: `tests/config/test_presets.py`
   - Problem: `test_save_preset_roundtrip` says “idempotent” but doesn’t define what must be equal (object equality vs `model_dump()` equality, and whether the base config is the comparison target).
   - Required Change: Provide the exact assertion(s) to implement, e.g.:
     - Compare `ConfigSchema.model_dump(mode="json")` outputs for equality, not object identity.
     - Define whether round-trip is:
       - `load_preset()` output equals the saved `config.model_dump(mode="json")`, and/or
       - `apply_preset(get_default_config(), preset_name).model_dump(mode="json") == get_default_config().model_dump(mode="json")` when preset is saved from defaults.

2. **Resolve enum casing guidance inconsistency**
   - Section: `src/frame_compare/config/schema.py` comments
   - Problem: Comment states “All enums use lowercase string values” but `LogLevel` values are uppercase (per spec).
   - Required Change: Update the comment to match the actual intended behavior (lowercase for most enums; uppercase for `LogLevel`) so the Coding Agent does not “correct” the enum definitions.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v5.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-1__config-module

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v4.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v4.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan as a new file (do not edit plan-v4 in place).

## Output
Write file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v5.md
