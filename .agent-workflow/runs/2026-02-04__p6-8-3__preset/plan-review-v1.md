---
RUN_ID: 2026-02-04__p6-8-3__preset
VERSION: v1
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `preset` subcommands (list, apply, save) — Bundled 2 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v1.md
---

# Plan Review Report: CLI `preset` subcommands + api-design CLI options

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-04
**Plan Reference:** `.agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v1.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | FAIL | Plan does not prove “implement all CLI options documented in api-design.md”; it only enumerates a subset without an explicit coverage audit. |
| 2 | Dependencies | PASS | Uses existing `config`, `errors`, `preflight`, `typer` surfaces. |
| 3 | File List | PASS | Proposed files are plausible and localized. |
| 4 | Contract Impact | PASS | No contract edits planned. |
| 5 | Types Complete | PASS | Plan is compatible with repo typing constraints. |
| 6 | Tests Complete | FAIL | Tests omit required behaviors implied by api-design global options (`--root`, `--config`) for new behaviors (`--write-config`, `preset apply/save`). |
| 7 | Verification Complete | PASS | Quality gate commands listed. |
| 8 | Decision-Minimizing | FAIL | Several behaviors are underspecified (notably `--config`/`--root` precedence and `--diagnose-paths` output key mapping). |
| 9 | Determinism Defined | PASS | Deterministic ordering/TOML/JSON goals are stated, but JSON schema mapping needs pinning. |

## Additional Quality Checks

- Error Codes: **Issue** — `--json` error envelope references “existing error JSON formatter”; plan must name the function (`frame_compare.errors.format_error_json`) and confirm it matches `api-design.md` error schema fields.
- Failure Modes: **Issue** — `--write-config` / `--diagnose-paths` interactions with missing config, custom `--config`, and custom `--root` are not specified.
- Derived Outputs: **OK** — None planned.
- Rollback Guidance: **OK** — Localized changes; revert affected modules/tests if needed.
- SSOT Update Audit (if SSOT changed this loop): **N/A** — No SSOT edits proposed.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Should `--write-config` write to the path provided by `--config` (and how should relative paths be resolved w.r.t. `--root`)?
2. What exact internal paths map to `api-design.md` `--diagnose-paths` output keys: `root`, `config`, `input`, `output`, `cache`?
3. What exact JSON keys must be emitted for `--json` success output (e.g., `screenshots_dir` vs `screenshot_dir`) and how do `RunResult` fields map?
4. Do `preset list/apply/save` need to support `--root` / `--config` global options (api-design declares them as global)?

## Concrete Edits Required (to approve)

1. **Add an explicit “api-design CLI options coverage audit” to the plan**
   - Section: `## Scope` (or a new `## CLI Option Coverage` section)
   - Problem: Requirement says “Implement all CLI options documented in api-design.md”; plan lists only a subset without confirming the rest are already functional.
   - Required Change: Add a table enumerating every option from `api-design.md` §2.3 (global) and §2.4 (run options), with columns: “Current status (already functional / missing)”, “Where implemented”, “Test coverage”. Anything “missing” must be added to the implementation steps and tests.

2. **Specify `--root` / `--config` precedence and apply consistently to new behaviors**
   - Section: `src/frame_compare/cli_entry.py` → `run(...)` (`--write-config`, `--diagnose-paths`) and `preset_*`
   - Problem: Plan hardcodes `config/config.toml` for reading/writing in multiple places; this conflicts with `api-design.md` global `--config` and makes `--root` resolution ambiguous.
   - Required Change:
     - Define: if `--config` is provided, read/write that exact path; else default to `{resolved_root}/config/config.toml`.
     - Define: if a provided `--config` is relative, resolve it relative to `{resolved_root}` (or explicitly choose and document another rule).
     - Update acceptance criteria + tests to cover these rules.

3. **Pin the `--diagnose-paths` JSON schema mapping (keys + values)**
   - Section: `src/frame_compare/cli_entry.py` → `--diagnose-paths`
   - Problem: Plan references “operations doc example keys” but does not specify which internal paths populate `output` and `cache`, nor how to compute them deterministically.
   - Required Change: Add a concrete mapping, for example:
     - `root` = resolved workspace root (absolute string)
     - `config` = resolved config file path (absolute string)
     - `input` = resolved input directory (absolute string, honoring `--input`)
     - `output` = resolved screenshots/report output directory (explicitly choose: `workspace.screenshots_dir` vs `config.report.output_dir`, and justify per SSOT)
     - `cache` = resolved generated/cache directory (explicitly choose: `workspace.generated_dir` or another SSOT path)
     - JSON determinism rules: `sort_keys=True`, fixed separators, no trailing newline (or specify if newline is acceptable).

4. **Make `--input` override wiring explicit end-to-end**
   - Section: `src/frame_compare/orchestration/preflight.py` + `src/frame_compare/cli_entry.py` plan steps
   - Problem: Current code uses `RunRequest.input_dir` but coordinator applies overrides without `input`, and `discover_inputs()` uses preflight workspace paths; plan must specify exactly how `--input` flows into preflight path resolution and discovery.
   - Required Change: Choose and document one mechanism:
     - (A) pass an explicit `overrides` dict into `prepare_preflight(..., overrides=...)` derived from `RunRequest.input_dir`, OR
     - (B) adjust coordinator/preflight to compute workspace paths from the effective config after applying CLI overrides.
     - Add/adjust tests to validate `--input` affects both validation and discovery.

5. **Define `--json` success output keys and mapping to `RunResult`**
   - Section: `src/frame_compare/cli_entry.py` → `--json`
   - Problem: api-design success schema uses specific key names (e.g., `screenshots_dir`); plan must specify the exact keys emitted and how they map from `RunResult`.
   - Required Change: Add a concrete JSON schema mapping for success output (and confirm error output uses `frame_compare.errors.format_error_json` and matches `api-design.md` error fields).

6. **Expand tests to cover global-option-sensitive behaviors**
   - Section: `tests/cli/test_cli_commands.py`
   - Problem: Plan tests do not exercise `--root`/`--config` behavior for `--write-config` and preset apply/save.
   - Required Change: Add at least:
     - `test_run_write_config_respects_config_path_and_root`
     - `test_preset_apply_respects_config_path_and_root` (or explicitly scope out global options for preset commands if SSOT allows; if scoped out, update SSOT/plan accordingly)

## Ready for Implementation

Return to Planning Agent for revision (`plan-v2.md`). Coding Agent must not proceed until verdict is APPROVED and Decision Points Remaining is NONE.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-02-04__p6-8-3__preset

## Precondition
Read file: `.agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v1.md`
Confirm: Verdict is APPROVED and Implementation Agent Decision Points Remaining is NONE.
If not, STOP and request a revised plan + plan review.

## Files to Read
1. `.agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v1.md`
2. `.agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v1.md`

## Output
Write file: `.agent-workflow/runs/2026-02-04__p6-8-3__preset/impl-v1.md`

## STOP CONDITIONS (Hard)
- If verdict != APPROVED or Implementation Agent Decision Points Remaining != NONE, do not proceed.
