---
RUN_ID: 2025-12-29__p1-4__cli-foundation
VERSION: v1
TARGET: Phase 1 → Item 1.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v1.md
---

# Plan Review Report: CLI Foundation

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (CLI foundation stubs) + explicit out-of-scope list. |
| 2 | Dependencies | PASS | Prior phases referenced; CLI layer depends on Typer + Rich + errors. |
| 3 | File List | PASS | Files are enumerated explicitly (no “related files”). |
| 4 | Contract Impact | PASS | Declared **NO** and no contract regen steps included (correct for this slice). |
| 5 | Types Complete | FAIL | Missing one-line backticked signatures for every planned public function; Spec Anchors are not copy/pasted verbatim headings. |
| 6 | Tests Complete | FAIL | Test behaviors/expectations are underspecified and one test contradicts Typer behavior (`run` with no args). Exit-code tests don’t specify concrete exception constructors/args. |
| 7 | Verification Complete | PASS | Commands + explicit “exit 0” criteria are listed. |
| 8 | Decision-Minimizing | FAIL | Plan leaves key decisions: preset subcommand wiring (SSOT template uses unsupported `@app.group()`), stub output contracts (stdout vs JSON shape), and `ExitCode` source of truth (dup vs import). |
| 9 | Determinism Defined | FAIL | Stub outputs are not defined tightly enough for deterministic assertions (especially `doctor --json`). |

## Additional Quality Checks

- Error Codes: Issue — plan implies defining `ExitCode` in `cli_entry.py`, but `src/frame_compare/errors.py` already defines `ExitCode` + `get_exit_code()`. Plan must specify the single source of truth used by CLI for exit codes.
- Failure Modes: Issue — `frame-compare run` behavior with no options must be specified (execute stub vs show help), and `doctor --json` output must be specified as valid JSON with a stable schema.
- Derived Outputs: OK — no derived/generated artifacts touched.
- Rollback Guidance: Issue — add an explicit “Stop and return to Planning” instruction if CLI behavior diverges from SSOT or Typer limitations block implementation.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Preset command group implementation: SSOT template uses `@app.group()` which Typer 0.21.0 does not support; plan also says “follow templates verbatim”, creating a hard conflict.
2. Exact stub output contract for `doctor --json` (schema, keys, stdout/stderr) and for other stubs (exact text vs substring assertions).
3. `run` no-args behavior: plan test says “shows help”, but Typer will execute the command unless explicitly configured otherwise.
4. Exit code mapping source of truth: whether CLI redefines `ExitCode` / mapping or imports `ExitCode` + `get_exit_code` from `frame_compare.errors`.

## Concrete Edits Required (for plan-v2)

1. **Update SSOT spec first: fix Typer preset group template**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`
   - Under heading: `### 2.1 Command Structure` change the preset portion of the code template to Typer-supported sub-app wiring:
     - Replace `@app.group()` / `@preset.command(...)` with `preset_app = typer.Typer(...)` + `app.add_typer(preset_app, name="preset")`
     - Replace decorators to `@preset_app.command("list")`, `@preset_app.command("apply")`, `@preset_app.command("save")`
     - Remove (or explicitly deprecate) the `def preset() -> None` group-container function from the template so planned public API is unambiguous

2. **Fix Spec Anchors (SSOT) to be mechanically valid**
   - Section: `## Spec Anchors (SSOT)`
   - Required change: copy/paste exact headings (including the `##`/`###` text) that will pass `scripts/validate_spec_anchors.py`, e.g.:
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md` → `### 2.1 Command Structure`, `### 2.2 Exit Codes`
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md` → `### 4.1 CLI Layer`, `## 7. Exit Code Reference`
     - (Add) `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md` → the headings that define the concrete error classes used in tests

3. **Add required one-line public signatures**
   - Section: `## Spec Anchors (SSOT)` (or a dedicated “Public API” subsection immediately after it)
   - Required change: list every planned public function with a one-line signature in backticks, matching SSOT (after the SSOT update in item 1). At minimum include:
     - `run(...) -> None` (full option list with types)
     - `wizard() -> None`
     - `doctor(json_output: bool = ...) -> None`
     - `preset_list() -> None`
     - `preset_apply(name: str) -> None`
     - `preset_save(name: str) -> None`
     - `handle_error(error: FrameCompareError) -> int`
     - (If present) `main() -> None` callback signature (since `cli_entry.py` already defines it and it impacts CLI behavior)

4. **Make tests deterministic and non-contradictory**
   - Section: `tests/cli/test_cli_commands.py`
   - Required change:
     - Replace or rewrite `test_run_no_args_shows_help` to reflect the intended, Typer-true behavior (either “invokes stub” or “shows help” with the exact Typer configuration needed).
     - For each stub-command test, specify exact assertions (exit code + output substring(s) + stdout/stderr expectations).
     - For `doctor --json`, specify the exact JSON schema to emit (keys + value types) and require the test to parse JSON and assert that schema.

5. **Specify concrete error instances for exit-code mapping tests**
   - Section: `tests/cli/test_exit_codes.py`
   - Required change: for each category mapping test, name the exact error class and constructor args to use (all deterministic), e.g., one concrete subclass per category, so Coding Agent does not choose.

6. **Clarify exit-code mapping source of truth**
   - Section: `src/frame_compare/cli_entry.py` implementation notes
   - Required change: explicitly state whether CLI uses `frame_compare.errors.ExitCode/get_exit_code` or defines its own `ExitCode`/mapping; require a single source of truth and align tests accordingly.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p1-4__cli-foundation

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
- Under heading: "### 2.1 Command Structure" add/change:
  - Replace the preset group template (`@app.group()` / `@preset.command(...)`) with Typer sub-app wiring using `preset_app = typer.Typer(...)`, `app.add_typer(preset_app, name=\"preset\")`, and `@preset_app.command(\"list\"|\"apply\"|\"save\")`.
  - Remove the `def preset() -> None` group-container function from the template (or explicitly mark it deprecated/non-required) so the public API is unambiguous.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-review-v1.md
Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v1.md
Write file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
