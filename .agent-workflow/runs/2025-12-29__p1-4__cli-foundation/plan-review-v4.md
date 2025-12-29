---
RUN_ID: 2025-12-29__p1-4__cli-foundation
VERSION: v4
TARGET: Phase 1 → Item 1.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v4.md
---

# Plan Review Report: CLI Foundation

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v4.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit out-of-scope list. |
| 2 | Dependencies | PASS | Uses existing errors/logging; no new import-direction decisions. |
| 3 | File List | PASS | Explicit file list. |
| 4 | Contract Impact | PASS | Declared **NO**; no contract regen needed. |
| 5 | Types Complete | FAIL | Public signatures are not fully enumerated (uses `...` / “see SSOT”), so the API surface is not mechanically checkable from the plan. |
| 6 | Tests Complete | PASS | Deterministic assertions + full `run --help` flag list + SSOT-correct exception constructors are specified. |
| 7 | Verification Complete | PASS | Commands + pass criteria are explicit. |
| 8 | Decision-Minimizing | FAIL | Coding Agent must still reconstruct SSOT-exact function signatures (Typer `Option(...)` defaults + all params). |
| 9 | Determinism Defined | PASS | Stub output contracts + JSON schema are explicit. |

## Additional Quality Checks

- Error Codes: OK — plan uses `get_exit_code()` and SSOT-correct error constructors.
- Failure Modes: OK for this slice (stubs exit 0; error mapping unit-tested).
- Derived Outputs: OK — no generated artifacts.
- Rollback Guidance: OK — explicit STOP guidance present.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. The complete `run(...)` and `doctor(...)` function signatures (plan currently uses `...` and “see SSOT”), including all 21 parameters and Typer `Option(...)` defaults.

## Concrete Edits Required (plan-v5; plan-only, iteration-cap surgical)

1. **Make Public API signatures fully explicit (one-line, backticked, no ellipses)**
   - Section: `## Public API Signatures (spec-anchored)`
   - Problem: current signatures contain `...` and indirect references (“see SSOT”), leaving reconstruction work to Coding Agent.
   - Required Change:
     - Provide one-line backticked signatures for every public CLI function that the run will expose/touch, with no placeholders:
       - `main() -> None` (unchanged)
       - `version() -> None` (unchanged)
       - `run(...all 21 parameters...) -> None` with each parameter’s type and default expression as `typer.Option(...)` per `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md` `### 2.1 Command Structure`
       - `wizard() -> None`
       - `doctor(json_output: bool = typer.Option(...)) -> None` per SSOT `### 2.1 Command Structure`
       - `preset_list() -> None`
       - `preset_apply(name: str) -> None`
       - `preset_save(name: str) -> None`
       - `handle_error(error: FrameCompareError) -> int`
     - If the one-line `run(...)` signature would exceed reasonable readability, still keep it one line, but you may remove whitespace/newlines while keeping the exact parameter order, names, types, and defaults.

## Ready for Implementation

Return to Planning Agent for a plan-only revision. Next version: `plan-v5.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p1-4__cli-foundation

## Revision Required
Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v4.md
Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v4.md
Write file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v5.md

## Hard Rules
- Spec Anchors must pass `scripts/validate_spec_anchors.py`.
