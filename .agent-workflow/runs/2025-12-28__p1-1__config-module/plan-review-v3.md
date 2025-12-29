---
RUN_ID: 2025-12-28__p1-1__config-module
VERSION: v3
TARGET: Phase 1 → Item 1.1 (Configuration Module)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v3.md
---

# Plan Review Report: Configuration Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice, explicit in/out scope. |
| 2 | Dependencies | PASS | `tomli-w` moved to runtime deps; special env var aliases specified. |
| 3 | File List | FAIL | Plan references “See plan-v2 section …” for required implementations (`schema.py`, `defaults.py`, `__init__.py`), but Coding Agent prompt will only read plan-v3 unless plan is made self-contained. |
| 4 | Contract Impact | PASS | Explicit “Contracts touched: NO”. |
| 5 | Types Complete | PASS | Removes `type: ignore`; specifies narrowing/casts and JSON-safe normalization. |
| 6 | Tests Complete | PASS | Includes determinism, alias env vars, inversion, invalid preset TOML, JSON-serializable error context. |
| 7 | Verification Complete | FAIL | Uses `uv sync` without explicitly installing `dev` tools required for `.venv/bin/pyright`, `.venv/bin/ruff`, `.venv/bin/pytest`; command must be unambiguous. |
| 8 | Decision-Minimizing | FAIL | Coding Agent must decide whether to read plan-v2 for omitted sections and whether to run `uv sync --group dev`; plan must specify both. |
| 9 | Determinism Defined | PASS | Determinism defined as identical output for same config; explicit test included. |

## Additional Quality Checks

- Error Codes: OK (`FC-1001`..`FC-1005` included; preset invalid path uses `PresetInvalidError`)
- Failure Modes: OK (STOP triggers + rollback steps present)
- Derived Outputs: OK
- Rollback Guidance: OK

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether/when to read plan-v2 to obtain required code for schema/defaults/__init.
2. Whether `uv sync` installs dev tooling or if `uv sync --group dev` is required (must not be left to implementer).

## Concrete Edits Required (for plan-v4.md)

1. **Make plan-v4 self-contained (no “see plan-v2”)**
   - Section: `Files to Create/Modify`
   - Problem: Plan-v3 omits the full implementations for `src/frame_compare/config/schema.py`, `src/frame_compare/config/defaults.py`, and `src/frame_compare/config/__init__.py`, delegating to plan-v2.
   - Required Change: Copy the full required content into plan-v4 (or provide complete, explicit step-by-step diffs) so the Coding Agent can implement from plan-v4 alone.

2. **Make the dependency install command unambiguous for verification**
   - Section: `Verification Commands`
   - Problem: `uv sync` alone may not install `dev` group tools required by subsequent commands.
   - Required Change: Replace with an explicit command that guarantees the tools exist, aligned with workflow:
     - `uv sync --group dev` (or `uv sync --group dev --frozen` if that’s the repo standard), and keep subsequent `.venv/bin/*` invocations.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-1__config-module

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v3.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v3.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan as a new file (do not edit plan-v3 in place).

## Output
Write file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v4.md
