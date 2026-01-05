---
RUN_ID: 2025-12-28__p1-1__config-module
VERSION: v1
TARGET: Phase 1 → Item 1.1 (Configuration Module)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v1.md
---

# Plan Review Report: Configuration Module

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single checklist slice with explicit out-of-scope items; includes minimal `errors.py` stub as declared dependency strategy. |
| 2 | Dependencies | FAIL | Plan does not specify how to honor “special env var” aliases (`TMDB_API_KEY`, `FRAME_COMPARE_LOG_LEVEL`) described in `config-module.md`; TOML writing strategy for presets is underspecified. |
| 3 | File List | PASS | File list is explicit and minimal (no “and related files”). |
| 4 | Contract Impact | PASS | Explicit “Contracts touched: NO”. |
| 5 | Types Complete | FAIL | Several required implementation details are not type-specified/contracted (normalizing `ValidationError.errors()` to `JSONValue`-compatible shapes; exact `load_config_from_env`/`get_default_config` source behavior). |
| 6 | Tests Complete | FAIL | Missing tests for required behaviors (special env var aliases; `no_upload` inversion; negative enum parsing if claiming case-insensitivity). Some test names/claims are ambiguous (“case_insensitive”). |
| 7 | Verification Complete | PASS | Commands are explicit and include pass criteria (assuming plan clarifies dependency install if it chooses to add one). |
| 8 | Decision-Minimizing | FAIL | Leaves multiple design decisions to Coding Agent: how to disable TOML/env sources, how to deep-merge overrides safely, and how to write TOML for presets. |
| 9 | Determinism Defined | FAIL | `save_preset()` output format/ordering/escaping is undefined (custom serializer “simple approach” is not a contract). |

## Additional Quality Checks

- Error Codes: Issue — `errors-module.md` defines `PresetInvalidError (FC-1005)` but the plan’s stub omits it while preset parsing is in-scope; the plan must explicitly choose which error is raised for invalid preset TOML and test it.
- Failure Modes: Issue — plan lacks explicit behavior for alias env vars (must define precedence vs `FRAME_COMPARE_*` vars).
- Derived Outputs: OK (none)
- Rollback Guidance: Issue — no rollback guidance section; add a “STOP and return to Planning” rule for any spec mismatch discovered during implementation.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact implementation for `load_config_from_env()` to ensure it never reads TOML and has deterministic source precedence.
2. Exact implementation for `get_default_config()` to ensure it never reads TOML or env and still returns fully-populated nested defaults.
3. Exact strategy for TOML serialization in `save_preset()` (dependency vs fully-specified custom serializer).
4. Exact deep-merge + validation strategy for `apply_cli_overrides()` and `apply_preset()` (avoid unvalidated `model_copy(update=...)` behavior ambiguity).
5. Exact handling and precedence of special env var aliases (`TMDB_API_KEY`, `FRAME_COMPARE_LOG_LEVEL`) per `config-module.md`.

## Concrete Edits Required (for plan-v2.md)

1. **Specify `load_config_from_env()` implementation exactly**
   - Section: `src/frame_compare/config/loader.py`
   - Problem: “use a subclass with toml_file disabled” is ambiguous.
   - Required Change: Provide the exact subclass (or source override) code in the plan, including `settings_customise_sources(...)` return tuple so TOML is never read. Define precedence explicitly (ENV only, or init+ENV only).

2. **Specify `get_default_config()` implementation exactly**
   - Section: `src/frame_compare/config/loader.py`
   - Problem: “use model_construct()” is ambiguous for `BaseSettings` and may bypass default factories/validators unexpectedly.
   - Required Change: Provide the exact code path the Coding Agent must implement (e.g., a defaults-only subclass with `settings_customise_sources` returning only `init_settings`, invoked with no kwargs), and state whether validators should run or be bypassed.

3. **Define how to normalize `ValidationError.errors()` into `JSONValue`**
   - Section: `src/frame_compare/config/loader.py` and `src/frame_compare/errors.py`
   - Problem: `ConfigValidationError` expects `list[dict[str, JSONValue]]`, but Pydantic error payloads can include non-JSON-safe values (e.g., tuples in `loc`).
   - Required Change: Add a specific normalization helper in the plan (name + signature + rules, e.g., convert tuples→lists; stringify unknown values) and update the loader to pass normalized errors. Add a unit test asserting `exc.context.to_dict()` is JSON-serializable for validation failures.

4. **Choose and specify a TOML writing strategy for `save_preset()`**
   - Section: `src/frame_compare/config/presets.py`
   - Problem: “simple custom TOML serializer” is not deterministic or testable as written.
   - Required Change: Pick exactly one:
     - Option A: Add a TOML writer dependency (e.g., `tomli-w`) and include exact `pyproject.toml` edits + import + usage; OR
     - Option B: Fully specify a custom serializer (supported types, quoting/escaping, key ordering, nested-table rules) and add tests that round-trip `save_preset()` → `tomllib.loads()` → `apply_preset()` deterministically.

5. **Make `apply_cli_overrides()` and `apply_preset()` merge semantics explicit**
   - Section: `src/frame_compare/config/overrides.py` and `src/frame_compare/config/presets.py`
   - Problem: `model_copy(update=...)` deep merge + validation behavior is underspecified.
   - Required Change: Specify the exact merge algorithm (deep-merge rules for nested dicts) and validation step (e.g., merge into `config.model_dump()` then `ConfigSchema.model_validate(merged)`).

6. **Add missing tests aligned to spec requirements**
   - Section: `tests/config/test_loader.py` and `tests/config/test_presets.py`
   - Problem: Missing tests for special env var aliases and inverted flags; ambiguous enum test naming.
   - Required Change:
     - Add `test_tmdb_api_key_legacy_alias_env_var` for `TMDB_API_KEY` behavior (and precedence vs `FRAME_COMPARE_TMDB__API_KEY`).
     - Add `test_log_level_legacy_alias_env_var` for `FRAME_COMPARE_LOG_LEVEL` behavior (and precedence vs `FRAME_COMPARE_LOGGING__LEVEL`).
     - Add `test_apply_cli_overrides_inverts_no_upload` to assert `no_upload=True` results in `slowpics.auto_upload=False`.
     - Rename or re-specify `test_enum_values_case_insensitive` to match the actual requirement (lowercase-only vs truly case-insensitive) and add a negative test for the rejected casing.
     - Add a preset invalid TOML test and specify whether it raises `ConfigParseError` or `PresetInvalidError (FC-1005)`; plan must choose one and align stub + tests.

7. **Add rollback guidance**
   - Section: add `Rollback`
   - Problem: No rollback section and no explicit “STOP and return to Planning” trigger for unexpected spec mismatches.
   - Required Change: Add rollback trigger conditions and minimal cleanup steps (files touched and how to revert) consistent with workflow stop conditions.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-28__p1-1__config-module

## Revision Required
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v1.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v1.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan as a new file (do not edit plan-v1 in place).

## Output
Write file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v2.md
