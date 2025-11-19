# Frame Compare CLI Refactor

> Source of truth for the ongoing refactor of CLI wiring, helpers, and public surface related to `frame_compare.py`.

Status: `in-progress`  
Owner(s): Codex (Phase 0 mapping)  
Last Updated: 2025-11-19 (UTC)

---

## How to Use This Doc

- **Implementation / Dev agents**
  - Use the **Phase checklists** (Sections 5–9) as your to‑do list.
  - Check off items as you implement and verify them.
  - Fill in the **Implementation Notes** for each phase with:
    - What you changed.
    - Tests and commands you ran.
    - Any deviations from the original plan.

- **Review / Code‑review agents**
  - Use the same phase checklists as your review checklist.
  - Fill in the **Review Notes** for each phase:
    - Confirm the **Global Invariants** are preserved.
    - Note any regressions, questions, or follow‑up items.
  - You are not expected to re‑derive the plan; use this document as the spec.

---

## 1. Overview

### 1.1 Goal

`frame_compare.py` currently mixes:

- CLI wiring (Click groups, options, and subcommands).
- CLI-only helpers (`_cli_override_value`, `_cli_flag_value`, etc.).
- Orchestration / core behavior and compatibility exports.

This structure is still manageable but makes it easier to:

- Introduce regressions when touching the CLI.
- Tangle core logic with CLI glue.
- Accumulate more responsibilities in a single module over time.

**Target state:**

- A dedicated CLI entry module that owns Click wiring.
- A dedicated CLI utilities module that owns CLI-specific helpers.
- `frame_compare.py` reduced to a thin shim exposing the public surface and delegating to the new modules.
- No change in observable CLI behavior or public API.

### 1.2 Non‑goals

- No redesign of the CLI UX (commands, flags, help text).
- No change to public module names or function signatures used by external callers, except through compatibility shims.
- No broad re‑architecture of non‑CLI code beyond what is required to separate concerns.

---

## 2. Global Invariants (Target State)

These should remain true at the end of **every phase** (unless explicitly noted), and must be re‑verified at the end of the refactor.

- [ ] **CLI behavior** remains unchanged:
  - [ ] All existing commands and subcommands still exist with the same names.
  - [ ] Options/flags, defaults, and help text are unchanged unless tests/docs were updated intentionally.
  - [ ] Exit codes and error behavior (for tested paths) are unchanged.

- [ ] **Public API** remains compatible:
  - [ ] `from frame_compare import main` (and any current public imports) still works.
  - [ ] Any symbols used by tests or documented as public are still importable from the same paths, or via shims.

- [ ] **Entry points** are stable:
  - [ ] Console script entry points in `pyproject.toml` (or equivalent) are unchanged and still resolve successfully.
  - [ ] Running `python -m frame_compare` (if supported today) continues to work.

- [ ] **Type and style guarantees** hold:
  - [ ] New/changed functions have full type annotations.
  - [ ] `Optional[...]` usage is guarded (no unsafe `reportOptionalMemberAccess` patterns).
  - [ ] No new `Any` leaks without strong justification.
  - [ ] Code passes `ruff` or is no worse than baseline.

- [ ] **Testing and tooling** remain green:
  - [ ] Key CLI tests continue to pass.
  - [ ] `.venv/bin/pyright --warnings` is clean or improved.
  - [ ] `.venv/bin/pytest -q` is clean or improved.

---

## 3. Architecture Snapshot (Context)

> Keep this section updated as phases complete. It should always reflect the **current** structure after the latest merged phase.

### 3.1 Current key modules

- `frame_compare.py`
  - Contains:
    - Click CLI wiring via `@click.group` `main` (invokes `_run_cli_entry` when no subcommand) plus subcommands: `run` (explicit passthrough to `_run_cli_entry`), `doctor` (dependency/config diagnostics with optional `--json`), `wizard` (interactive config creation), and `preset` group with `list`/`apply`.
    - Root-level options gated by `_cli_override_value`/`_cli_flag_value` so Click `default_map`/env sources never override config unless the flag was passed: `--root/--config/--input`, `--audio-align-track` (multiple), quiet/verbose/color/json-pretty, cache flags (`--no-cache`, `--from-cache-only`, `--show-partial`, `--show-missing/--hide-missing`), service-mode vs legacy runner (mutually exclusive, sets `service_mode_override`), HTML report toggles, `--diagnose-paths`, `--write-config`, `--no-wizard`, `--debug-color`, diagnostic frame metrics (flag pair), and tonemap overrides via `--tm-*` (preset/curve/target/dst-min/knee/dpd preset/black-cutoff/gamma & disable/smoothing/scene thresholds/percentile/contrast/metadata/use-dovi/visualize-lut/show-clipping`).
    - `_run_cli_entry` builds `RunRequest`, validates incompatible flags (e.g., `--html-report` vs `--no-html-report`, gamma vs gamma-disable), handles write-config/diagnose-paths short-circuiting, invokes `run_cli`, then manages slow.pics shortcut/browser/clipboard plus JSON/report tail emission.
    - CLI helper functions `_cli_override_value` (ParameterSource guard) and `_cli_flag_value` (boolean guard), plus `_execute_wizard_session` shared by the `wizard` command for preset/interactive config creation.
    - Public surface: `run_cli` shim to `runner.run`; curated `__all__` (asserted in `tests/api/test_public_surface.py`) exposing `run_cli`, `main`, `RunRequest`, `RunResult`, `CLIAppError`, `ScreenshotError`, `resolve_tmdb_workflow`, `TMDBLookupResult`, `render_collection_name`, `prepare_preflight`, `resolve_workspace_root`, `PreflightResult`, `collect_path_diagnostics`, `collect_doctor_checks`, `emit_doctor_results`, `DoctorCheck`, `vs_core`; `_COMPAT_EXPORTS` additionally attach modules/helpers (cli_runtime, core, config_writer, presets, preflight, tmdb_workflow, vspreview, collect_doctor_checks/emit_doctor_results, wizard prompts, Console, CliOutputManager, NullCliOutputManager, render helpers, ScreenshotError, etc.).
    - Entry points: console_script `frame-compare = "frame_compare:main"` (`pyproject.toml`) and `if __name__ == "__main__": main()`; `python -m frame_compare` today resolves to this module.

- `src/frame_compare/cli_utils.py`
  - Proto helper module already contains `_cli_override_value`/`_cli_flag_value` mirrored from `frame_compare.py` with `__all__` set, but the Click wiring still calls the inline versions (not imported).

- `src/frame_compare/cli_entry.py`
  - Proto CLI entry module (68 lines) with imports and `__all__ = ("cli", "main", "run_cli", ...)` but no click decorators/logic; currently unused by entry points/tests and should be reconciled in later phases rather than left divergent.

- `tests/helpers/runner_env.py`
  - Contains `_patch_core_helper` (patches both `frame_compare.*` and `runner_module.*` helpers like `prepare_preflight`/`_collect_path_diagnostics`/`parse_metadata`/`_write_vspreview_script`/`resolve_subdir`/`apply_audio_alignment`/`launch`/`prompt_offsets`, etc.) plus other runner/VS/audio patchers. Assumes these attribute names remain reachable on the `frame_compare` shim and runner modules, so relocations require shims.

### 3.2 Target layout (end state)

- `frame_compare.py`
  - Thin shim that:
    - Exposes public CLI entry (e.g., `main`).
    - Exposes any public library symbols as before.
    - Delegates CLI wiring to `cli_entry` and CLI helpers to `cli_utils`.

- `frame_compare/cli_entry.py` (new)
  - Owns Click CLI wiring:
    - Top-level CLI group.
    - Subcommands (wizard, preset, etc.).
  - Exposes a canonical CLI entry function (`main()` or `cli()`).

- `frame_compare/cli_utils.py` (new)
  - Owns CLI-specific helpers:
    - `_cli_override_value`, `_cli_flag_value`, and similar.
  - Importable by CLI code and tests.

- `frame_compare/__init__.py`
  - Continues to expose the public surface (including `main`) and delegates to the new structure.

---

## 4. Phases Overview

> Each phase should be independently reviewable and, if needed, shippable. Later phases depend on earlier ones being completed and merged.

- **Phase 0 – Baseline & mapping**
  - Inventory current CLI structure, helpers, and public API usage.
  - No code changes; pure analysis.

- **Phase 1 – Extract CLI helpers to `cli_utils`**
  - Create `cli_utils` and move `_cli_override_value`, `_cli_flag_value`, etc., into it.
  - Update imports in CLI code and tests.

- **Phase 2 – Extract CLI wiring into `cli_entry`**
  - Move Click group/command definitions out of `frame_compare.py`.
  - Introduce a canonical CLI entry in `cli_entry`.

- **Phase 3 – Make `frame_compare.py` a thin shim**
  - Remove remaining CLI wiring.
  - Ensure `frame_compare.py` is a public surface + delegating shim.

- **Phase 4 – Cleanup, docs, and final verification**
  - Remove dead code.
  - Finalize documentation and decision logs.
  - Run final tool/test passes.

---

## 5. Phase 0 – Baseline & Mapping

Status: `completed`  
Owner: Codex (Phase 0 mapping)  
Related PR(s): n/a (docs-only)

### 5.1 Scope

- Understand the current CLI and public API.
- Map where `frame_compare` is used (including tests).
- No structural or behavioral changes.

### 5.2 Entry Criteria

- None; this is the starting phase.

### 5.3 Exit Criteria

- Inventory of:
  - CLI entry function(s) in `frame_compare.py` (e.g. `main`, `cli`).
  - All Click groups/commands/options.
  - CLI helpers (`_cli_override_value`, `_cli_flag_value`, etc.).
  - Public symbols exported from `frame_compare` that are used elsewhere.
- Document updated with this information.

### 5.4 Checklist

- [x] Identify CLI entry function(s) in `frame_compare.py` (e.g. `main`).
- [x] Enumerate Click groups/commands and their options/flags.
- [x] List CLI helper functions including `_cli_override_value`, `_cli_flag_value`, and similar.
- [x] Use Codanna to find references to:
  - [x] `frame_compare.main`
  - [x] Other public symbols imported outside `frame_compare.py`.
- [x] Use Codanna to locate tests that:
  - [x] Patch or import `frame_compare` internals (e.g. via `tests/helpers/runner_env.py`).
  - [x] Exercise CLI behavior directly.
- [x] Update Section **3. Architecture Snapshot** with:
  - [x] CLI structure summary.
  - [x] Known public API and their call sites.

### 5.5 Implementation Notes (Dev Agent)

- Date: 2025-11-19  
- Dev Agent: Codex (Phase 0 mapping)

Notes:

- CLI surface: `frame_compare.main` is the Click group entry (also console_script target) with default execution into `_run_cli_entry` plus subcommands `run`, `doctor`, `wizard`, and `preset list/apply`. Options cover root/config/input/audio-align, quiet/verbose/color/json-pretty, cache flags (`--no-cache`, `--from-cache-only`, `--show-partial`, `--show-missing/--hide-missing`), service-mode vs legacy-runner, HTML report toggles, diagnose/write-config, debug-color, diagnostic-frame-metrics flag pair, and tonemap `--tm-*` overrides (preset/curve/target/dst-min/knee/dpd preset/black cutoff/gamma + disable/smoothing/scene thresholds/percentile/contrast/metadata/use-dovi/visualize-lut/show-clipping). Mutual exclusions raise ClickExceptions (service-mode vs legacy-runner, html-report enable/disable, gamma vs gamma-disable).
- Helpers and usage: `_cli_override_value` (ParameterSource guard) and `_cli_flag_value` (boolean guard) live inline in `frame_compare.py` and are used for every option listed above; `_run_cli_entry` builds `RunRequest` and post-processes slow.pics/report/JSON tails; `_execute_wizard_session` backs the `wizard` flow. A proto `src/frame_compare/cli_utils.py` mirrors the helper definitions and `src/frame_compare/cli_entry.py` is a stub with only imports/`__all__`; neither is wired into the current entry point yet.
- Public API and call sites: `frame_compare.__all__` is asserted by `tests/api/test_public_surface.py` to the curated tuple (run_cli/main/RunRequest/RunResult/CLIAppError/ScreenshotError/resolve_tmdb_workflow/TMDBLookupResult/render_collection_name/prepare_preflight/resolve_workspace_root/PreflightResult/collect_path_diagnostics/collect_doctor_checks/emit_doctor_results/DoctorCheck/vs_core). Console script stays `frame-compare = frame_compare:main`. Tests invoking the Click CLI include `tests/runner/test_cli_entry.py`, `tests/runner/test_dovi_flags.py`, `tests/runner/test_audio_alignment_cli.py`, `tests/runner/test_slowpics_workflow.py`, `tests/cli/test_help.py`, `tests/cli/test_doctor.py`, `tests/cli/test_wizard.py`, `tests/test_paths_preflight.py`, and `tests/api/test_cli_flags.py` (stable flag/help coverage); many rely on Click `default_map` semantics being filtered by `_cli_override_value/_cli_flag_value`. `frame_compare.run_cli` is used extensively across runner suites (e.g., `tests/test_frame_compare.py`, `tests/runner/test_cli_entry.py`, `tests/runner/test_audio_alignment_cli.py`, `tests/runner/test_dovi_flags.py`, `tests/runner/test_slowpics_workflow.py`).
- Gotchas / risks: `tests/helpers/runner_env.py::_patch_core_helper` patches numerous attributes on `frame_compare` and runner modules (prepare/collect_path_diagnostics/parse_metadata/_write_vspreview_script/apply_audio_alignment/resolve_subdir/launch/prompt_offsets, etc.), so Phase 1–2 moves need shims to keep these names reachable. Existing proto `cli_entry.py`/`cli_utils.py` could drift from the live CLI if not reconciled. Changing `__all__` ordering, `ParameterSource` gating, or tonemap flag names/types will break multiple CLI regression tests.

### 5.6 Review Notes (Review Agent)

- Date: 2025-11-19  
- Review Agent: Codex (Skeptical reviewer)

Notes:

- Phase 0 mapping aligns with current CLI wiring/helpers/public surface; stable flag/help coverage captured via `tests/api/test_cli_flags.py`.
- No code changes in this phase; ready for Phase 1 to proceed using this map.

---

## 6. Phase 1 – Extract CLI Helpers to `cli_utils`

Status: `completed`  
Owner: Codex (surgical Python refactorer)  
Related PR(s): _fill in_

### 6.1 Scope

- Introduce a `cli_utils` module.
- Move CLI-specific helper functions out of `frame_compare.py`.
- Keep behavior and public imports unchanged.

### 6.2 Entry Criteria

- Phase 0 completed and documented.
- No open questions about which helpers are CLI-specific.

### 6.3 Exit Criteria

- `frame_compare/cli_utils.py` exists with CLI helper functions.
- `frame_compare.py` uses `cli_utils` instead of defining helpers inline.
- Tests and any external imports relying on helpers still work (either via new imports or shims).
- Type checking, linting, and tests pass or are no worse than baseline.

### 6.4 Checklist

- [x] Create `frame_compare/cli_utils.py` (path adjusted to actual layout, e.g. `src/frame_compare/cli_utils.py`).
- [x] Move `_cli_override_value` into `cli_utils` with full type annotations.
- [x] Move `_cli_flag_value` and similar CLI-only helpers into `cli_utils`.
- [x] Ensure `cli_utils` imports are minimal and avoid circular dependencies.
- [x] In `frame_compare.py`, remove moved helper definitions and import them from `cli_utils`.
- [ ] Decide on helper visibility:
  - [ ] If **internal**: update tests to import from `frame_compare.cli_utils` or test via higher-level APIs.
  - [x] If **effectively public**: re-export them from `frame_compare.py` to preserve existing imports.
- [x] Update tests that import helpers directly from `frame_compare` to align with the chosen visibility.
- [x] Run:
  - [x] `.venv/bin/pyright --warnings`
  - [x] `.venv/bin/ruff check`
  - [x] `.venv/bin/pytest -q`
- [x] Confirm no behavior changes in CLI flag handling related to these helpers.

### 6.5 Implementation Notes (Dev Agent)

- Date: 2025-11-19  
- Dev Agent: Codex (surgical Python refactorer)

Notes:

- Migrated `_cli_override_value` and `_cli_flag_value` into `src/frame_compare/cli_utils.py`, aligning the implementations and typing with the live `frame_compare` versions; `frame_compare.py` now imports them to keep the names reachable and behavior identical.
- No test imports required changes; `frame_compare` continues to expose the helper names via module globals for compatibility.
- Tooling runs: `.venv/bin/pyright --warnings` and `.venv/bin/ruff check` still report pre-existing unused-import/private-name issues in the proto `src/frame_compare/cli_entry.py` stub (not touched in this phase). `.venv/bin/pytest -q` passed (444 passed, 1 skipped).

### 6.6 Review Notes (Review Agent)

- Date: _YYYY-MM-DD_  
- Review Agent: _name / persona_

Notes:

- Confirm helpers are fully typed and behavior unchanged (especially override semantics).
- Verify tests cover helper behavior sufficiently.
- Note any remaining coupling that might affect later phases.

---

## 7. Phase 2 – Extract CLI Wiring into `cli_entry`

Status: `not-started` | `in-progress` | `completed`  
Owner: _fill in_  
Related PR(s): _fill in_

### 7.1 Scope

- Create `cli_entry` module.
- Move Click CLI wiring (group, commands, options) out of `frame_compare.py`.
- Provide a canonical CLI entry function while preserving `frame_compare.main` behavior.

### 7.2 Entry Criteria

- Phase 1 completed and merged.
- CLI helpers in `cli_utils` are in use.

### 7.3 Exit Criteria

- `frame_compare/cli_entry.py` exists and defines:
  - Click group and subcommands.
  - Canonical CLI entry function (`main` or `cli`).
- `frame_compare.py` delegates its CLI entry to `cli_entry`.
- CLI tests continue to pass without needing to understand the internal move.

### 7.4 Checklist

- [ ] Create `frame_compare/cli_entry.py` (path adjusted to repo layout).
- [ ] Move Click decorators, group, and subcommands from `frame_compare.py` to `cli_entry.py`.
- [ ] Ensure options/flags, defaults, and help text are unchanged.
- [ ] Implement canonical CLI entry in `cli_entry`:
  - [ ] `def main(...)` or `def cli(...)` matching current `frame_compare.main` semantics (return code, exit behavior).
- [ ] In `frame_compare.py`:
  - [ ] Remove moved Click wiring.
  - [ ] Import the entry function from `cli_entry`.
  - [ ] Re-implement `frame_compare.main` as a thin delegation to `cli_entry`’s entry point.
- [ ] Ensure orchestrating business logic stays in appropriate modules (not duplicated across `frame_compare.py` and `cli_entry.py`).
- [ ] Update tests:
  - [ ] Tests may call `frame_compare.main` (shim) or `frame_compare.cli_entry.main` explicitly.
  - [ ] No test should depend on CLI wiring staying inside `frame_compare.py`.
- [ ] Run:
  - [ ] `.venv/bin/pyright --warnings`
  - [ ] `.venv/bin/ruff check`
  - [ ] `.venv/bin/pytest -q`
- [ ] Optional smoke check:
  - [ ] `python -m frame_compare --help` (if supported today).

### 7.5 Implementation Notes (Dev Agent)

- Date: _YYYY-MM-DD_  
- Dev Agent: _name / persona_

Notes:

- Summary of moved commands and any minor reshuffling.
- Any subtle behavior issues encountered and fixed.
- How `main` semantics were preserved.

### 7.6 Review Notes (Review Agent)

- Date: _YYYY-MM-DD_  
- Review Agent: _name / persona_

Notes:

- Confirm `frame_compare.main` still behaves identically for all tested cases.
- Confirm CLI surface (commands/options) is unchanged.
- Note any edge cases needing additional tests.

---

## 8. Phase 3 – Make `frame_compare.py` a Thin Shim

Status: `not-started` | `in-progress` | `completed`  
Owner: _fill in_  
Related PR(s): _fill in_

### 8.1 Scope

- Remove remaining CLI wiring from `frame_compare.py`.
- Ensure it primarily acts as a public surface and delegating shim.
- Preserve all public imports and entry points.

### 8.2 Entry Criteria

- Phase 2 completed and merged.
- CLI is functioning via `cli_entry`.

### 8.3 Exit Criteria

- `frame_compare.py` contains:
  - Public API definitions / re-exports.
  - Minimal delegating logic (e.g., `main` calling `cli_entry.main`).
- No Click decorators or heavy CLI logic remain in `frame_compare.py`.
- Entry points and imports continue to work.

### 8.4 Checklist

- [ ] Review `frame_compare.py` for any remaining CLI-only logic.
- [ ] Move remaining CLI bits to:
  - [ ] `cli_entry` (wiring, options, command implementation).
  - [ ] `cli_utils` (reusable CLI helpers).
- [ ] Ensure `frame_compare.py`:
  - [ ] Exposes `main` delegating to `cli_entry`’s entry point.
  - [ ] Exposes any public library functions/classes as before.
- [ ] Verify `__init__.py`:
  - [ ] Imports from `frame_compare` still resolve.
  - [ ] No unintended removal of public names.
- [ ] Check `pyproject.toml` (or equivalent):
  - [ ] Console scripts still reference `frame_compare:main` (or current entry).
  - [ ] They resolve to the new underlying CLI entry.
- [ ] Ensure tests that import from `frame_compare` still pass.
- [ ] Run:
  - [ ] `.venv/bin/pyright --warnings`
  - [ ] `.venv/bin/ruff check`
  - [ ] `.venv/bin/pytest -q`

### 8.5 Implementation Notes (Dev Agent)

- Date: _YYYY-MM-DD_  
- Dev Agent: _name / persona_

Notes:

- What remained in `frame_compare.py` and why.
- Any small cleanups or name changes required for clarity.

### 8.6 Review Notes (Review Agent)

- Date: _YYYY-MM-DD_  
- Review Agent: _name / persona_

Notes:

- Confirm `frame_compare.py` is now clearly a thin shim.
- Confirm public API is unchanged.
- Note any suggestions for future cleanup or documentation.

---

## 9. Phase 4 – Cleanup, Docs, and Final Verification

Status: `not-started` | `in-progress` | `completed`  
Owner: _fill in_  
Related PR(s): _fill in_

### 9.1 Scope

- Remove dead code and unused imports.
- Finalize documentation and decision logging.
- Run and record final tool/test runs.

### 9.2 Entry Criteria

- Phases 1–3 completed and merged.
- CLI behavior stable.

### 9.3 Exit Criteria

- No unused CLI helpers or dead code remain.
- Docs and changelog entries reflect the refactor.
- Final type/lint/test runs are documented.

### 9.4 Checklist

- [ ] Remove unused imports and dead code from:
  - [ ] `frame_compare.py`
  - [ ] `cli_entry.py`
  - [ ] `cli_utils.py`
- [ ] Verify test helpers in `tests/helpers/runner_env.py`:
  - [ ] Patching logic for `frame_compare.*` still works.
- [ ] Update `docs/DECISIONS.md`:
  - [ ] Add entry for the CLI refactor, with date from `date -u +%Y-%m-%d`.
  - [ ] Include short rationale and architecture summary.
- [ ] Update `CHANGELOG.md`:
  - [ ] Note internal refactor (no user-visible behavior change).
- [ ] Run final:
  - [ ] `.venv/bin/pyright --warnings`
  - [ ] `.venv/bin/ruff check`
  - [ ] `.venv/bin/pytest -q`
- [ ] Confirm all **Global Invariants** (Section 2) are satisfied.

### 9.5 Implementation Notes (Dev Agent)

- Date: _YYYY-MM-DD_  
- Dev Agent: _name / persona_

Notes:

- Summary of cleanup performed.
- Final verification commands and outcomes.

### 9.6 Review Notes (Review Agent)

- Date: _YYYY-MM-DD_  
- Review Agent: _name / persona_

Notes:

- Confirm no regressions introduced during cleanup.
- Confirm docs accurately describe the final state.
- Final risk assessment for the refactor.

---

## 10. Open Questions / Notes

Use this section to capture cross‑phase decisions and follow‑ups.

- [ ] Are CLI helpers intended to remain publicly accessible, or should we introduce a dedicated test-facing API and mark helpers as internal?
- [ ] Are there external integrations (outside this repo) that import `frame_compare.main` or other internals in undocumented ways?
- [ ] Should we add dedicated tests that call both `frame_compare.main` and `cli_entry.main` to guard future refactors?
- [ ] Phase 2 should reconcile the proto `src/frame_compare/cli_entry.py` stub (currently triggering unused import/private name warnings) with the live CLI wiring to avoid lint noise and drift.
