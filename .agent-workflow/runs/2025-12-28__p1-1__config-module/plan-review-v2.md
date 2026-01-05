---
RUN_ID: 2025-12-28__p1-1__config-module
VERSION: v2
TARGET: Phase 1 → Item 1.1 (Configuration Module)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v2.md
---

# Plan Review Report: Configuration Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; adds minimal `errors.py` stub and config module + tests. |
| 2 | Dependencies | FAIL | Adds `tomli-w` only to `[dependency-groups].dev`, but `frame_compare.config` imports `tomli_w` at runtime via `presets.py` (and `config/__init__.py` re-exports presets), causing ImportError for non-dev installs. |
| 3 | File List | PASS | Explicit and minimal. |
| 4 | Contract Impact | PASS | Explicit “Contracts touched: NO”. |
| 5 | Types Complete | PASS | Major previously-ambiguous behaviors are now specified (sources behavior, JSON-safe errors, merge algorithm). |
| 6 | Tests Complete | PASS | Adds the missing alias/inversion/invalid preset tests and JSON-serializability check. |
| 7 | Verification Complete | FAIL | `save_preset()` example uses `preset_path.write_bytes(tomli_w.dumps(data))` but `tomli_w.dumps(...)` returns `str`, so this will fail at runtime; plan must specify correct file write semantics. |
| 8 | Decision-Minimizing | FAIL | Coding Agent would need to decide whether `tomli-w` is a runtime dependency (it must be if used) and how to fix the `write_bytes` bug; plan must specify both. |
| 9 | Determinism Defined | FAIL | Plan claims “Keys are sorted alphabetically for reproducibility” but no sorting step is specified; determinism contract must match implementation. |

## Additional Quality Checks

- Error Codes: OK (includes `PresetInvalidError` FC-1005 and tests for invalid preset TOML)
- Failure Modes: OK (explicit STOP triggers + rollback guidance present)
- Derived Outputs: OK (none)
- Rollback Guidance: OK

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Where to declare `tomli-w` so `frame_compare.config` works in non-dev installs.
2. How `save_preset()` writes TOML output (text vs bytes; encoding).
3. Whether “alphabetical key sorting” is a requirement (and, if so, the exact sorting rules).

## Concrete Edits Required (for plan-v3.md)

1. **Make `tomli-w` a runtime dependency (or remove it entirely)**
   - Section: `pyproject.toml` edit and `src/frame_compare/config/presets.py`
   - Problem: Importing `tomli_w` from a dev-only dependency breaks library runtime and CLI usage for non-dev installs.
   - Required Change (choose exactly one and specify it):
     - Option A (recommended): Add `tomli-w>=1.0.0` to `[project].dependencies` (runtime), and keep the dev group unchanged; update verification install command if needed.
     - Option B: Remove `tomli-w` and fully specify a custom TOML serialization strategy; update `save_preset()` and tests accordingly.

2. **Fix `save_preset()` file writing semantics**
   - Section: `src/frame_compare/config/presets.py`
   - Problem: `tomli_w.dumps(...)` returns `str`, but plan uses `Path.write_bytes(...)`.
   - Required Change: Specify the exact correct implementation in the plan, for example:
     - `toml_text = tomli_w.dumps(data)` then `preset_path.write_text(toml_text, encoding="utf-8")`
     - (or explicitly encode to bytes before `write_bytes`).

3. **Make determinism requirement match implementation**
   - Section: `src/frame_compare/config/presets.py` docstring/comments + tests
   - Problem: Plan states “Keys are sorted alphabetically” but does not implement sorting.
   - Required Change (choose exactly one and specify it):
     - Option A: Implement recursive key sorting before dumping (define helper name, signature, and rules for dict/list handling), and add a test asserting stable output ordering.
     - Option B: Remove the “alphabetically sorted” claim and define determinism as “stable schema field order”, with a test that saving twice yields identical file contents.

4. **Remove un-justified `# type: ignore[...]` suppressions (pyright strict)**
   - Section: `src/frame_compare/config/loader.py` and `src/frame_compare/config/overrides.py`
   - Problem: Plan includes `# type: ignore[arg-type]` / `# type: ignore[assignment]` without justification; strict typing should use explicit narrowing/casts.
   - Required Change: Specify the exact narrowing approach (e.g., `assert isinstance(...)` + `cast(dict[str, object], ...)`) and update the plan snippets accordingly so `.venv/bin/pyright --warnings` passes without ignores.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-1__config-module

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v2.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v2.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan as a new file (do not edit plan-v2 in place).

## Output
Write file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v3.md
