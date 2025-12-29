---
RUN_ID: 2025-12-28__p1-1__config-module
VERSION: v6
TARGET: Phase 1 → Item 1.1 (Configuration Module)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v6.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v6.md
---

# Plan Review Report: Configuration Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v6.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope is explicit. |
| 2 | Dependencies | PASS | Preset TOML `None` issue addressed via `exclude_none=True`; dev tooling install is explicit. |
| 3 | File List | PASS | Fully enumerated and self-contained. |
| 4 | Contract Impact | PASS | Explicit “Contracts touched: NO”. |
| 5 | Types Complete | PASS | No `type: ignore`; type narrowing/casts specified. |
| 6 | Tests Complete | FAIL | `test_save_preset_apply_restores_defaults` is not executable as specified: it saves preset into `tmp_path` but `apply_preset()` loads from `DEFAULT_PRESETS_DIR` only. Plan must specify how tests route `apply_preset()` to the temp presets location. |
| 7 | Verification Complete | FAIL | Verification depends on the above test passing; currently it will raise `PresetNotFoundError` unless test setup changes. |
| 8 | Decision-Minimizing | FAIL | Coding Agent would need to decide between changing `apply_preset()` API vs changing test setup (cwd/monkeypatch/DEFAULT_PRESETS_DIR). |
| 9 | Determinism Defined | PASS | `exclude_none=True` rule is explicit; deterministic file-content test remains. |

## Additional Quality Checks

- Error Codes: OK (`FC-1001`..`FC-1005` defined)
- Failure Modes: OK (STOP triggers + rollback present)
- Derived Outputs: OK
- Rollback Guidance: OK

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. How `apply_preset()` finds presets during tests without writing to repo paths.

## Concrete Edits Required (for plan-v7.md)

1. **Make `test_save_preset_apply_restores_defaults` route presets to the default lookup path**
   - Section: `tests/config/test_presets.py`
   - Problem: `save_preset(..., presets_dir=tmp_path)` writes to `tmp_path`, but `apply_preset()` always loads from `DEFAULT_PRESETS_DIR` (`config/presets`) and has no `presets_dir` parameter.
   - Required Change (recommended; preserves spec API): Update the test to use the default relative directory by changing CWD:
     - Add `monkeypatch` fixture usage: `monkeypatch.chdir(tmp_path)`
     - Call `save_preset("defaults", original_config)` with no `presets_dir` argument (so it writes to `tmp_path/config/presets`)
     - Call `apply_preset(base_config, "defaults")` (it will read from `tmp_path/config/presets` because `DEFAULT_PRESETS_DIR` is relative)
   - Alternative (not recommended unless spec updated): change `apply_preset()` signature to accept `presets_dir`; if chosen, update module spec alignment, exports, and all call sites/tests.

2. **Align acceptance criteria wording with the chosen behavior**
   - Section: `Acceptance Criteria`
   - Problem: Current criteria implies `apply_preset()` works for presets saved to arbitrary temp dir.
   - Required Change: State explicitly that `apply_preset()` loads from the default presets directory (`config/presets` relative to CWD/workspace root), and tests set CWD accordingly.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v7.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-1__config-module

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v6.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v6.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan as a new file (do not edit plan-v6 in place).

## Output
Write file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v7.md
