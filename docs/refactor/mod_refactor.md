# Modularization Refactor Plan

This plan deconstructs the remaining monoliths (`src/frame_compare/core.py`, `tests/test_frame_compare.py`, etc.) into cohesive modules. Work is split into phases and sub-phases sized for a single Codex session. Update the checklists and notes after each session to preserve context.

---

## Definition of Done (per sub-phase)

- [ ] Code split aligns with plan (no surprise regressions).
- [ ] Unit/integration tests exist or are updated for moved logic.
- [ ] `pytest`, `ruff`, and `pyright` run (or blocked reason recorded).
- [ ] Documentation touched (`docs/runner_refactor_checklist.md`, `docs/DECISIONS.md`, plus others if surface changes).
- [ ] Progress tracker row flipped to ☑ with summary.
- [ ] Session Checklist template filled and committed (or stored in PR description).

Keep this DoD visible when reviewing PRs.

---

## Progress Tracker

| Phase | Sub-phase | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| 0 | Preparation |  | ☑ | Phase 0 checklist (git status + pytest/ruff/pyright) logged on 2025‑11‑19 ahead of Phase 1 work. |
| 1 | 1.1 Preflight scaffolding |  | ☑ | Extracted the public preflight API (`resolve_workspace_root`, `resolve_subdir`, `collect_path_diagnostics`, `prepare_preflight`, `PreflightResult`) and rewired CLI/runner/tests. |
| 1 | 1.2 Wizard path integration |  | ☑ | Wizard prompts now delegate to `preflight.resolve_workspace_root/resolve_subdir`, `--diagnose-paths` calls `preflight.collect_path_diagnostics`, and new preflight/CLI diagnostics tests cover site-packages and escape attempts. |
| 2 | 2.1 Wizard module creation |  | ☑ | Wizard prompts now live in `src/frame_compare/wizard.py` with dedicated tests (`tests/test_wizard.py`) and CLI wiring updated (2025‑11‑10). |
| 2 | 2.2 Loader/CLI updates |  | ☑ | CLI + preset flows now call `src.frame_compare.wizard` APIs directly; CLI tests patched to assert the new boundary. |
| 3 | 3.1 Metadata utilities |  | ☑ | Created `src/frame_compare/metadata.py`, rewired `runner.py`/tests to import it directly, and updated docs/QA logs. |
| 3 | 3.2 Plan builder |  | ☑ | Extracted `build_plans` into `src/frame_compare/planner.py`, rewired `runner.py`, and added planner-focused tests/QA logs. |
| 4 | 4.1 Alignment summary module |  | ☑ | Extracted `_AudioAlignmentSummary`/display helpers into `src/frame_compare/alignment_runner.py`, rewired `runner.py` to call the module directly, and re-exported the helpers for compatibility. |
| 4 | 4.2 VSPreview integration |  | ☑ | VSPreview script writer/launcher hardened (new helpers, logging, and telemetry) with dedicated unit tests plus docs/log updates for manual offset reuse. |
| 5 | 5.1 VSPreview module |  | ☑ | `src/frame_compare/vspreview.py` owns script rendering/persistence/launch plus manual-offset helpers; CLI/runner now import from the module, `_COMPAT_EXPORTS` re-exports for shims, and tests cover rendering, launch, and telemetry paths. |
| 5 | 5.2 Layout utilities |  | ☑ | `src/frame_compare/layout_utils.py` centralizes `plan_label`, `format_resolution_summary`, color helpers, etc., and all layout consumers (cli_runtime, alignment_runner, runner, screenshot) import from it to avoid circular dependencies. |
| 6 | 6.1 Shared fixtures |  | ☑ | Helpers/fixtures promoted into `tests/helpers/runner_env.py` plus `tests/conftest.py` so runner suites share `_CliRunnerEnv`, `_patch_*`, and the JSON/VSPreview stubs. |
| 6 | 6.2 Test split |  | ☑ | Split the monolithic runner suite into `tests/runner/test_cli_entry.py`, `tests/runner/test_audio_alignment_cli.py`, and `tests/runner/test_slowpics_workflow.py`; added `runner`/`runner_vs_core_stub` fixtures and documented the relocation in `docs/runner_refactor_checklist.md`. |
| 6 | 6.3 Runner test polish |  | ☑ | Added shared `dummy_progress` fixture, VSPreview shim exports, and centralized helpers so Phase 6 suites rely exclusively on the helper module. |
| 7 | 7.1 VSPreview shim validation |  | ☑ | VSPreview shim exports now fail fast via `_require_vspreview_constant`, `tests/runner/test_audio_alignment_cli.py` asserts the error path, and verification details live in the Phase 7 DECISIONS entry. |
| 8 | Docs & cleanup |  | ☑ | README/CHANGELOG/checklists updated to describe the `tests/runner/` split, shared fixtures, and lint status, with both Phase 8 prep/completion quartets logged in `docs/DECISIONS.md`. |

_Mark status with ☑ when completed. Keep the "Notes" column for future session reminders._

---

## Phase 0 – Preparation (each session)

1. **Sync & Baseline**
   - [x] `git fetch --all` and rebase/merge latest `Develop`.
   - [x] Record `git status -sb`.
   - [x] Run `pytest -q`, `.venv/bin/ruff check`, and `npx pyright --warnings` (or note if blocked) and paste summaries into `docs/DECISIONS.md`.
2. **Context Refresh**
   - [x] Re-read latest entries in `docs/runner_refactor_checklist.md` and `refactor/mod_refactor.md` progress tracker.
   - [x] Identify target sub-phase for the session; jot down scope in Session Checklist.
3. **Branching**
   - [x] Create/checkout feature branch (e.g., `feature/refactor-phase1.1`).

Notes:
- Keep sub-phase change sets small (<300 LOC) to ease review.
- If blocked, update "Open Questions" section before finishing session.

---

## Phase 1 – Preflight & Path Guard Extraction

**Goal:** Move workspace/preflight logic from `src/frame_compare/core.py` into a dedicated module. This reduces repeated IO coupling and clarifies path guardrails.

### Sub-phase 1.1 – Preflight module scaffolding
- [x] Create `src/frame_compare/preflight.py` exporting:
  - `resolve_workspace_root`
  - `resolve_subdir`
  - `collect_path_diagnostics`
  - dataclass for preflight result (`PreflightResult`)
- [x] Move `_discover_workspace_root`, `_resolve_workspace_subdir`, `_path_is_within_root`, `_abort_if_site_packages`, `_is_writable_path`, `_collect_path_diagnostics`, `_prepare_preflight` into the new module.
- [x] Ensure functions remain importable (re-export minimal API from `core.py` if needed).
- [x] Update imports in `frame_compare.py`, `runner.py`, tests.
- [x] Update tracker table row (Phase 1 / Sub-phase 1.1) with ☑ when merged.

### Sub-phase 1.2 – Wizard path prompts & CLI diagnostics
- [x] Update wizard helpers in `core.py` to call `preflight.resolve_subdir`.
- [x] Ensure `frame_compare --diagnose-paths` uses `preflight.collect_path_diagnostics` directly.
- [x] Add targeted unit tests (e.g., new `tests/test_preflight.py`) covering path-escape & site-packages rejection.
- [x] Record verification commands + notes in Session Checklist and `docs/DECISIONS.md`.

Notes:
- Keep logging behavior identical; consumers rely on warning strings.
- Document new module in `docs/runner_refactor_checklist.md`.

---

## Phase 2 – Wizard Module

**Goal:** Extract interactive wizard logic from `core.py`.

### Sub-phase 2.1 – Module creation
- [x] Create `src/frame_compare/wizard.py` with:
  - `run_wizard_prompts`
  - Prompt helpers (`prompt_workspace_root`, `prompt_input_dir`, `prompt_slowpics`, etc.)
- [x] Maintain CLI colorized output; use `click` import local to module.
- [x] Add docstring referencing relevant config audit sections.

### Sub-phase 2.2 – Loader & CLI updates
- [x] Updated `frame_compare.py` (`--write-config`, `wizard`, `preset apply`) to call `src.frame_compare.wizard.resolve_wizard_paths` and expanded `_COMPAT_EXPORTS` so downstream scripts can continue patching `_run/_resolve_wizard_prompts`.
- [x] Patched `tests/cli/test_wizard.py` (formerly `tests/test_cli_wizard.py`) to monitor `wizard.resolve_wizard_paths` during auto-wizard runs, ensuring the CLI exercises the new module boundary.
- [x] Captured the boundary shift in `docs/refactor/mod_refactor.md`, `docs/runner_refactor_checklist.md`, and `docs/DECISIONS.md` (no CHANGELOG entry — internal refactor).

**2025‑11‑10 update (Phase 2.2)** — Loader helpers (`--write-config`, auto-wizard, preset apply) now rely solely on `src.frame_compare.wizard`, so wizard logic lives in one module. Compatibility exports keep `_run/_resolve_wizard_prompts` accessible, and CLI wizard tests assert that the resolver path is exercised when auto-seeding configs.

---

## Phase 3 – Plan Builder / Metadata Module

**Goal:** Separate clip metadata parsing and plan construction from orchestration.

### Sub-phase 3.1 – Metadata utilities
- [x] Create `src/frame_compare/metadata.py` containing:
  - `parse_metadata` (formerly `_parse_metadata`)
  - Label dedup helpers
  - Override matching utilities (`normalise_override_mapping`, `_match_override`)
- [x] Update `runner.py` + tests to import from the new module, patch helpers via `metadata_utils`, and keep CLI shim compatibility intact.

**2025-11-10 update:** Metadata parsing/dedupe/override helpers now live in `src/frame_compare/metadata.py`, `runner.py` consumes the module directly, and tests patch the new namespace through `_patch_core_helper`. Docs (`docs/config_audit.md`, tracker tables) capture the new layout; no CHANGELOG entry required.

### Sub-phase 3.2 – Plan builder
- [x] Create `src/frame_compare/planner.py` exporting `build_plans`.
- [x] Ensure `build_plans` encapsulates trim/trim_end/FPS overrides and returns typed `_ClipPlan` objects (import from `cli_runtime` or define protocol).
- [x] Add unit tests (`tests/test_planner.py`) verifying overrides apply correctly.

**2025-11-10 update:** Planner extraction complete—`runner.py` imports `planner_utils.build_plans`, `core.py` re-exports the helper for compatibility, and a dedicated `tests/test_planner.py` suite covers trims/FPS overrides plus error handling. Tracker docs, DECISIONS logs, and Session Checklist entries capture the verification commands; behavior remains internal so CHANGELOG/README are unchanged.

Notes:
- Keep `CliOutputManager` integration unchanged; only move pure logic.

---

## Phase 4 – Audio Alignment Orchestration

**Goal:** Move CLI/runner-specific audio alignment helpers into `src/frame_compare/alignment_runner.py`.

### Sub-phase 4.1 – Summary and display data extraction
- [x] Relocate `_AudioAlignmentSummary`, `_AudioAlignmentDisplayData`, `_compose_measurement_details`, `_emit_measurement_lines` into new module.
- [x] Provide functions `apply_audio_alignment` and `format_alignment_output`.

**2025-11-10 update:** `src/frame_compare/alignment_runner.py` now owns the alignment dataclasses plus `_compose_measurement_details`/`_emit_measurement_lines`, and exposes `apply_audio_alignment` + `format_alignment_output`. `core.py` re-exports those names for compatibility, while `runner.py` imports the new module directly. Tests gained coverage for the formatter to ensure JSON tail wiring stays intact.

### Sub-phase 4.2 – VSPreview integration
- [x] Move `_write_vspreview_script`, `_launch_vspreview`, `_apply_vspreview_manual_offsets` into the alignment module or a dedicated `vspreview.py`.
- [x] Add focused tests for script generation and VSPreview launch/manual-offset flows (mock filesystem/subprocess).

**2025-11-10 update:** VSPreview orchestration (`_write_vspreview_script`, `_launch_vspreview`, `_apply_vspreview_manual_offsets`) now owns rendering, persistence, and telemetry inside `alignment_runner`; the runner calls `alignment_runner.apply_audio_alignment` directly, `_write_vspreview_script` gained a pure renderer + persistence helper, `_launch_vspreview` logs missing executables/env vars with injectable subprocess runners, `_apply_vspreview_manual_offsets` updates JSON-tail offsets with guardrails, and `tests/test_alignment_runner.py` exercises the new seams.

Notes:
- Coordinate with doc `audio_alignment_pipeline.md` if surface changes.

---

## Phase 5 – VSPreview & Layout Utilities

**Goal:** Split UI-related helpers away from `core.py`.

### Sub-phase 5.1 – VSPreview module
- [x] Introduce `src/frame_compare/vspreview.py` for script generation + launching.
- [x] Update CLI/runner to import from the module; keep manual CLI instructions identical.

**2025-11-10 update:** VSPreview orchestration now lives in `src/frame_compare/vspreview.py` (`render_script`, `persist_script`, `write_script`, `launch`, `apply_manual_offsets`, `prompt_offsets`). `alignment_runner.py` and `core.py` alias those helpers, `_COMPAT_EXPORTS` re-exports them (with deprecation notes), and `typings/frame_compare.pyi` shares the same surface. `tests/test_vspreview.py` exercises script rendering, persistence failures, launcher injection/missing-backend telemetry, and manual-offset propagation; `_patch_core_helper` now patches the new module for CLI/runner suites.

### Sub-phase 5.2 – Layout annotations
- [x] Extract `_plan_label`, `_format_resolution_summary`, other Rich layout helpers into `src/frame_compare/layout_utils.py`.
- [x] Ensure `CliOutputManager` still receives same data structures.

**2025-11-10 update:** Added `src/frame_compare/layout_utils.py` with `color_text`, `format_kv`, `plan_label`, `plan_label_parts`, `normalise_vspreview_mode`, and `format_resolution_summary`. `cli_runtime`, `alignment_runner`, `runner`, and `screenshot` import from the shared module, reducing circular imports and keeping presentation helpers centralized for both CLI output and programmatic reporters.

---

## Phase 6 – Test Suite Restructuring

**Goal:** Align tests with new module boundaries.

### Sub-phase 6.1 – Shared fixtures
- [x] Move `_CliRunnerEnv` and patch helpers into `tests/helpers/runner_env.py` + `tests/conftest.py`.
- [x] Ensure the helper module exports the patch utilities and pytest fixtures consumed across the runner/VSPreview test suites.

**2025-11-11 update:** Added `tests/helpers/runner_env.py` containing `_CliRunnerEnv`, the `_patch_*` helpers, `_make_config`, JSON/VSPreview stubs, and `tests/conftest.py` fixtures (`cli_runner_env`, `recording_output_manager`, `json_tail_stub`). Updated `tests/test_frame_compare.py`, `tests/test_alignment_runner.py`, and `tests/test_vspreview.py` to import from the helper module so later splits can share the scaffolding without circular imports.

### Sub-phase 6.2 – Test split
- [x] Carve `tests/test_frame_compare.py` into:
  - `tests/runner/test_cli_entry.py`
  - `tests/runner/test_audio_alignment_cli.py`
  - `tests/runner/test_slowpics_workflow.py`
- [x] Ensure each file imports shared fixtures.
- [x] Update `pytest` selection docs (if any) to reference new paths.

Notes:
- Update `docs/runner_refactor_checklist.md` each time a split happens.

### Sub-phase 6.3 – Runner test polish
- [☑] Replace remaining direct `_patch_core_helper("Progress", DummyProgress)` usage in the slow.pics suites with a shared `dummy_progress` fixture exported from `tests/helpers/runner_env.py`.
- [☑] Provide a typed helper or shim for `_format_vspreview_manual_command` and the `_VSPREVIEW_*` constants so the relocated audio-alignment tests no longer trigger Pyright attribute warnings.
- [☑] Audit the new `tests/runner/*` modules for lingering inline helpers and move reusable pieces into `tests/helpers/runner_env.py`.
- [☑] Re-run `git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, and `.venv/bin/pyright --warnings`, then log the outputs (with `date -u +%Y-%m-%d`) in `docs/DECISIONS.md`.

**2025-11-11 update:** Added `dummy_progress` as a shared fixture in `tests/conftest.py` so every runner suite automatically patches the Rich `Progress` helper, avoiding per-test `_patch_*` calls. The VSPreview shim (typed constants + `_format_vspreview_manual_command`) now lives in `tests/helpers/runner_env.py`, mirroring Pyright’s constant guidance for `Final` exports (source:https://github.com/microsoft/pyright/blob/main/docs/typed-libraries.md@2025-11-10). Audio-alignment tests import the shim directly, and no additional inline helpers required migration after the audit. Ruff still reports the longstanding import-order debt in `src/frame_compare/*`, and Pyright is back to the known alignment-runner backlog only.

Scope: finalize Phase 6 by ensuring all runner tests rely on the shared fixture module and that the only remaining Ruff/Pyright failures are the known alignment-module backlog, not test-level shims.

---

## Phase 7 – VSPreview shim validation

**Goal:** Harden the VSPreview shims used by CLI/runner tests so regressions in the public compatibility layer immediately surface through pytest/Pyright.

### Sub-phase 7.1 – Shim constant enforcement (2025-11-11)
- [x] Update `tests/helpers/runner_env.py` so `_VSPREVIEW_WINDOWS_INSTALL` / `_VSPREVIEW_POSIX_INSTALL` raise `RuntimeError` when the frame_compare module no longer exposes the constants (rather than silently providing defaults), matching the `_format_vspreview_manual_command` guard.
- [x] Add an audio-alignment CLI test (`tests/runner/test_audio_alignment_cli.py::test_audio_alignment_vspreview_constants_raise_when_missing`) that asserts we surface the error when the constants are missing, ensuring behavior coverage alongside the typing guard.
- [x] Re-run `git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, and `.venv/bin/pyright --warnings`, logging outputs with `date -u +%Y-%m-%d` in `docs/DECISIONS.md` (Phase 7 entries capture both the baseline and post-change quartets).

Scope: make VSPreview surface areas fail fast before tackling the broader documentation/cleanup phase.

---

## Phase 8 – Documentation & Cleanup

- [x] Update `docs/runner_refactor_checklist.md` after each sub-phase (status + notes). ✅ Added the Phase 8 section summarizing the doc refresh, Ruff decision, and residual risks.
- [x] Summarize changes in `docs/DECISIONS.md` with dates and verification steps. ✅ Phase 8 prep/completion entries log the 2025-11-11 quartets (`git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`) and cite the pytest fixture doc that backs the shared runner fixtures.
- [x] Ensure `CHANGELOG.md` captures user-visible improvements (easier configuration, new modules). ✅ Added the Phase 6–7 bullet describing the `tests/runner/` split, shared fixtures, VSPreview guardrails, and verification commands.
- [x] Re-run `ruff`, `pyright`, and targeted `pytest` suites after every major extraction. ✅ Phase 8 prep re-ran the quartet (all clean) before touching docs; Phase 8 completion re-run recorded below.

---

## Session Checklist Template

Copy this block into each PR or session log:

- [ ] Phase/Sub-phase: `___`
- [ ] Modules touched:
- [ ] Commands run: `git status`, `pytest`, `ruff`, `pyright`
- [ ] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`)
- [ ] Tests added/updated:
- [ ] Risks noted:
- [ ] Follow-ups for next session:

_Optional fields:_ Date, Branch, Reviewer, Metrics (LOC touched, tests runtime).

## Session Checklist — 2025-11-10

- [x] Phase/Sub-phase: `1 / 1.2 Wizard path integration`
- [x] Modules touched: `src/frame_compare/core.py`, `frame_compare.py`, `tests/test_preflight.py`, `tests/test_paths_preflight.py`
- [x] Commands run: `git status -sb`, `pytest -q`, `.venv/bin/ruff check`, `npx pyright --warnings` (fails: ENOTFOUND registry.npmjs.org), `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Updated `docs/DECISIONS.md`, `docs/runner_refactor_checklist.md`, and this tracker (CHANGELOG unchanged—no user-visible behavior change).
- [x] Tests added/updated: Added `tests/test_preflight.py`, extended `tests/test_paths_preflight.py` with a diagnostics routing check.
- [x] Risks noted: Config dir derivation now flows through `resolve_subdir`; if validation fails the message references the generic “input directory” wording—monitor for user confusion.
- [x] Follow-ups for next session: Phase 2.1 wizard module creation (extract prompts), consider documenting diagnostics routing in README once the wizard module stabilizes.

## Session Checklist — 2025-11-10 (Phase 2.1)

- [x] Phase/Sub-phase: `2 / 2.1 Wizard module creation`
- [x] Modules touched: `src/frame_compare/wizard.py`, `src/frame_compare/core.py`, `frame_compare.py`, `tests/cli/test_wizard.py` (relocated from `tests/test_cli_wizard.py`), `tests/test_wizard.py`, `docs/DECISIONS.md`, `docs/refactor/mod_refactor.md`, `docs/runner_refactor_checklist.md`
- [x] Commands run: `git status -sb`, `pytest -q`, `.venv/bin/ruff check`, `npx pyright --warnings` (fails: ENOTFOUND registry.npmjs.org), `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Updated `docs/DECISIONS.md`, `docs/refactor/mod_refactor.md`, `docs/runner_refactor_checklist.md` (CHANGELOG unchanged—internal refactor only).
- [x] Tests added/updated: Added `tests/test_wizard.py`, updated `tests/cli/test_wizard.py` to patch the new module boundary.
- [x] Risks noted: CLI still exposes compatibility shims but downstream scripts that patched `frame_compare._run_wizard_prompts` must now patch `src.frame_compare.wizard.run_wizard_prompts` for behavior to change.
- [x] Follow-ups for next session: Phase 2.2 should reroute loader/CLI helpers to import the wizard module directly and document the new boundary in README once the CLI shim is simplified.

## Session Checklist — 2025-11-10 (Phase 2.2)

- [x] Phase/Sub-phase: `2 / 2.2 Loader & CLI updates`
- [x] Modules touched: `frame_compare.py`, `src/frame_compare/wizard.py`, `src/frame_compare/core.py`, `tests/cli/test_wizard.py`
- [x] Commands run: `git status -sb`, `pytest -q`, `.venv/bin/ruff check`, `npx pyright --warnings` (fails: ENOTFOUND registry.npmjs.org), `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): `docs/DECISIONS.md`, `docs/refactor/mod_refactor.md`, and `docs/runner_refactor_checklist.md` updated (CHANGELOG untouched — internal refactor).
- [x] Tests added/updated: `tests/cli/test_wizard.py` now asserts the resolver hook is exercised during auto-wizard seeding.
- [x] Risks noted: Downstream tools that previously patched `frame_compare._resolve_wizard_paths` now hit the alias that forwards to `src.frame_compare.wizard`—monitor for any imports that reach into `src.frame_compare.core` directly.
- [x] Follow-ups for next session: Begin Phase 3 metadata extraction; audit README once the CLI shim is slimmer to mention the new wizard module boundary if user-facing behavior changes.

## Session Checklist — 2025-11-11 (Phase 9.2)

- [x] Phase/Sub-phase: `9 / 9.2 Config writer + presets`
- [x] Modules touched: `frame_compare.py`, `src/frame_compare/core.py`, `src/frame_compare/config_writer.py`, `src/frame_compare/presets.py`, `docs/refactor/mod_refactor.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Updated this tracker + `docs/DECISIONS.md` (no README/CHANGELOG deltas for this internal refactor).
- [x] Tests added/updated: None—existing CLI wizard/preset suites already cover the flows.
- [x] Risks noted: CLI preset/wizard outputs must remain byte-for-byte identical; shims in `src.frame_compare.core` keep third-party imports stable but we should monitor for missed aliasing before Phase 9.5 curated-export cleanup.
- [x] Follow-ups for next session: Phase 9.3 unhook (move runner callers to preflight/vspreview constants) and start planning the curated export adjustments slated for Phase 9.5.

## Session Checklist — 2025-11-11 (Phase 9.3)

- [x] Phase/Sub-phase: `9 / 9.3 Runner unhook (trivial callers)`
- [x] Modules touched: `src/frame_compare/runner.py`, `src/frame_compare/metadata.py`, `src/frame_compare/runtime_utils.py`, `src/frame_compare/core.py`, `docs/refactor/mod_refactor.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Updated this tracker + `docs/DECISIONS.md` (README/CHANGELOG untouched—internal refactor only).
- [x] Tests added/updated: None (existing runner/CLI suites already cover metadata parsing, VSPreview hints, and layout summaries).
- [x] Risks noted: New `runtime_utils` import must stay acyclic—verify no modules other than runner rely on it until Phase 9.4 extracts additional helpers; monitor for any callers still expecting `core._parse_*` implementations once shims flip to metadata.
- [x] Follow-ups for next session: Phase 9.4 selection/init helpers extraction plus early planning for Phase 9.5 curated exports & deprecations.

## Session Checklist — 2025-11-11 (Phase 9.4)

- [x] Phase/Sub-phase: `9 / 9.4 Selection & clip init helpers`
- [x] Modules touched: `src/frame_compare/selection.py`, `src/frame_compare/runner.py`, `src/frame_compare/core.py`, `docs/refactor/mod_refactor.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Updated this tracker plus `docs/DECISIONS.md` (README/CHANGELOG unchanged because the API surface remains internal pending Phase 9.5 curated exports).
- [x] Tests added/updated: None (existing runner + CLI suites already cover clip init failures and selection-window logging; moving code preserved behavior byte-for-byte).
- [x] Risks noted: Monitor for any latent import cycles if future modules import `selection.py`; `core` shims remain in place so downstream `core._init_clips` patch points stay valid until curated exports ship.
- [x] Follow-ups for next session: Phase 9.5 curated exports/typing cleanup plus planning for TMDB workflow extraction in Phase 10.

## Session Checklist — 2025-11-11 (Phase 9.6)

- [x] Phase/Sub-phase: `9 / 9.6 Fixture cleanup plan`
- [x] Modules touched: `tests/helpers/runner_env.py`, `tests/conftest.py`, `tests/cli/test_doctor.py` (renamed from `tests/test_cli_doctor.py`), `tests/runner/test_audio_alignment_cli.py`, `docs/refactor/mod_refactor.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb` → `## runner-refactor...origin/runner-refactor [ahead 18]`; `.venv/bin/pyright --warnings` → `0 errors, 0 warnings, 0 informations`; `.venv/bin/ruff check` → `All checks passed!`; `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` → `273 passed, 1 skipped in 40.13 s`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Logged this tracker plus `docs/DECISIONS.md`; other docs unchanged because prod code stayed the same.
- [x] Tests added/updated: `tests/cli/test_doctor.py` now uses the shared fixtures + localized audio dependency patches; `tests/runner/test_audio_alignment_cli.py` covers the VSPreview fixtures for both present/missing runs.
- [x] Risks noted: New fixtures sit alongside legacy `_patch_*` helpers—ensure future refactors keep the helper docstrings in sync and avoid reordering `monkeypatch` patches that intentionally override fixture behavior (e.g., forcing `shutil.which` to fail when VSPreview is “present”).
- [x] Follow-ups for next session: Phase 10 CLI test relocation into `tests/cli/` plus continuing to replace bespoke `_patch_*` helpers once the fixtures soak.

## Session Checklist — 2025-11-11 (Phase 9.5)

- [x] Phase/Sub-phase: `9 / 9.5 Curated exports + typing`
- [x] Modules touched: `frame_compare.py`, `typings/frame_compare.pyi`, `src/frame_compare/py.typed`, `MANIFEST.in`, `docs/refactor/mod_refactor.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Updated this tracker plus `docs/DECISIONS.md` (README/CHANGELOG unchanged; CLI surface still stable apart from curated exports).
- [x] Tests added/updated: None — existing CLI/runner suites already cover doctor, presets, config_writer, and VSPreview helpers.
- [x] Risks noted: Downstream extensions must import doctor/config_writer/presets through `frame_compare`; continue promoting the compatibility map comments and monitor for reports before removing shims in a future release.
- [x] Follow-ups for next session: Phase 9.6 fixture cleanup plan and TMDB workflow extraction planning for Phase 10.

## Session Checklist — 2025-11-11 (Phase 9.8)

- [x] Phase/Sub-phase: `9 / 9.8 Remove legacy shims`
- [x] Modules touched: `src/frame_compare/core.py`, `frame_compare.py`, `docs/refactor/mod_refactor.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` (273 passed, 1 skipped in 39.96 s), `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Updated this tracker + `docs/DECISIONS.md` (README/CHANGELOG unchanged because the API still targets internal callers).
- [x] Tests added/updated: None — existing runner + CLI suites already exercise doctor/config-writer/presets/selection workflows now that they import the extracted modules directly.
- [x] Risks noted: Third-party scripts that still import `src.frame_compare.core._*` helpers will now fail; monitor incoming bug reports and steer users to the documented module entry points.
- [x] Follow-ups for next session: Phase 10 TMDB workflow extraction plus the planned VSPreview/wizard shim removals once dependent tests migrate.

## Session Checklist — 2025-11-11 (Phase 9.9)

- [x] Phase/Sub-phase: `9 / 9.9 Test layout finalization`
- [x] Modules touched: `tests/cli/test_wizard.py`, `tests/cli/test_doctor.py`, `tests/cli/test_help.py`, `tests/cli/test_layout.py`, `tests/cli/__init__.py`, `docs/refactor/mod_refactor.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` (baseline and post-move: 273 passed / 1 skipped, ~39.9 s), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q tests/cli/test_doctor.py`, `... test_wizard.py`, `... test_help.py`, `... test_layout.py`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Updated this tracker + `docs/DECISIONS.md` (no CHANGELOG/README impact—organization-only work).
- [x] Tests added/updated: Relocated the remaining CLI tests into `tests/cli/` and added `tests/cli/__init__.py` so pytest assigns unique module names; assertions stay the same.
- [x] Risks noted: Any tooling that referenced the old `tests/test_cli_*.py` paths (CI filters, docs) must be updated to `tests/cli/test_*.py`; pytest needed the package marker to prevent duplicate module imports when `tests/test_wizard.py` remains at the top level.
- [x] Follow-ups for next session: Audit workflow/test-selection globs for the renamed files and continue Phase 9.10 export hardening once CI confirms the new layout.

## Session Checklist — 2025-11-11 (Phase 9.10)

- [x] Phase/Sub-phase: `9 / 9.10 Public __all__ contracts`
- [x] Modules touched: `src/frame_compare/selection.py`, `docs/refactor/mod_refactor.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` (273 passed / 1 skipped, 39.91 s), `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Updated this tracker + `docs/DECISIONS.md` (RUNNER checklist/CHANGELOG unaffected).
- [x] Tests added/updated: None needed; existing suites already cover selection window behavior.
- [x] Risks noted: `selection` only re-exports three helpers now; downstream wildcard imports must import explicitly or rely on curated exports (documented in DECISIONS entry).
- [x] Follow-ups for next session: Audit remaining modules before Phase 9.11 strictness ratchet to ensure `__all__` lists stay in sync with CLI/runner imports.

### Phase 2.3 – Docs, Tooling & Risk Log

Goal: capture the tooling outputs, refresh compatibility documentation, and extend the residual-risk notes before moving on.

| Checklist Item | Status | Notes |
| --- | --- | --- |
| Workspace prep & tooling | ✅ | 2025-11-10 — `git status -sb` shows `runner-refactor...origin/runner-refactor [ahead 3]`; `pytest -q` (209 passed / 54 skipped, 39.71 s), `.venv/bin/ruff check` (clean), `npx pyright --warnings` (fails: npm ENOTFOUND) with fallback `.venv/bin/pyright --warnings` (0 errors). |
| Documentation & CHANGELOG | ✅ | README now explains that `frame_compare.resolve_wizard_paths` / `_resolve_wizard_paths` forward into `src.frame_compare.wizard`, this tracker plus `docs/runner_refactor_checklist.md` record the risk notes, and CHANGELOG captures the doc/tooling refresh. |
| Session logs | ✅ | `docs/DECISIONS.md` includes both the pre- and post-edit command captures stamped via `date -u +%Y-%m-%d`, and the Session Checklist below records scope/risks. |
| Residual risk | ✅ | Added explicit migration guidance so downstream scripts keep patching the compatibility exports instead of the retired `src.frame_compare.core` helpers; no additional manual wizard/preset QA was required for this doc-only pass. |

## Session Checklist — 2025-11-10 (Phase 2.3)

- [x] Phase/Sub-phase: `2 / 2.3 Docs, Tooling & Risk Log`
- [x] Modules touched: `README.md`, `CHANGELOG.md`, `docs/refactor/mod_refactor.md`, `docs/runner_refactor_checklist.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `pytest -q`, `.venv/bin/ruff check`, `npx pyright --warnings` (fails: ENOTFOUND registry.npmjs.org), `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Yes — README compatibility note, CHANGELOG entry, both refactor trackers, and `docs/DECISIONS.md`.
- [x] Tests added/updated: None (documentation-only pass; existing suites already cover the wizard boundary).
- [x] Risks noted: Legacy scripts must patch `frame_compare.resolve_wizard_paths` (or `_resolve_wizard_paths`) because those names now forward into `src.frame_compare.wizard`; manual wizard/preset QA deferred until behavior changes again.
- [x] Follow-ups for next session: Pick up the Phase 3 metadata extraction once additional module splits resume.

## Session Checklist — 2025-11-10 (Phase 3.1)

- [x] Phase/Sub-phase: `3 / 3.1 Metadata utilities`
- [x] Modules touched: `src/frame_compare/metadata.py`, `src/frame_compare/runner.py`, `src/frame_compare/core.py`, `tests/test_frame_compare.py`, `docs/config_audit.md`, `docs/refactor/mod_refactor.md`, `docs/runner_refactor_checklist.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `pytest -q`, `.venv/bin/ruff check`, `npx pyright --warnings` (fails: ENOTFOUND registry.npmjs.org), `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Yes — trackers plus `docs/config_audit.md` refreshed; `CHANGELOG.md` unchanged (internal refactor only).
- [x] Tests added/updated: Patched `tests/test_frame_compare.py` helpers to target `src.frame_compare.metadata.parse_metadata` via `_patch_core_helper`, ensuring runner/CLI patches hit the new module.
- [x] Risks noted: Compatibility shim still funnels through `frame_compare._COMPAT_EXPORTS`; no `_IMPL_ATTRS` remain, but Phase 3.2 must extract `_build_plans` next to keep plan overrides co-located with the new metadata module (resolved in the Phase 3.2 entry below).
- [x] Follow-ups for next session: Start Phase 3.2 (`planner.py`) so trim/FPS logic moves alongside the override helpers; consider documenting the new module boundary in README once planners stabilize.

## Session Checklist — 2025-11-10 (Phase 3.2)

- [x] Phase/Sub-phase: `3 / 3.2 Plan builder`
- [x] Modules touched: `src/frame_compare/planner.py`, `src/frame_compare/core.py`, `src/frame_compare/runner.py`, `tests/test_planner.py`, `tests/test_frame_compare.py`, `docs/config_audit.md`, `docs/refactor/mod_refactor.md`, `docs/runner_refactor_checklist.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `pytest -q`, `.venv/bin/ruff check`, `npx pyright --warnings` (fails: ENOTFOUND registry.npmjs.org), `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Tracker docs refreshed; CHANGELOG unchanged (internal refactor only).
- [x] Tests added/updated: New `tests/test_planner.py` plus runner harness patches covering planner overrides.
- [x] Risks noted: Planner now shares `_ClipPlan`; downstream callers patching `frame_compare.core._build_plans` should shift to `planner.build_plans` (compat helper bridges both, but test coverage is key). Monitor for CLI scripts that assumed `_match_override` lived beside `_build_plans`.
- [x] Follow-ups for next session: Phase 4 alignment summary module extraction; rerun manual plan-builder QA with real configs once CLI glue thins further.

---

## Phase 9 – CLI vs Runner Boundary Hardening (Sized per session)

Goal: finish modularizing `src/frame_compare/core.py` by extracting remaining CLI-only helpers into purpose-built modules, reduce runner’s dependency on `core`, and present a stable runner API. Each sub‑phase below is scoped to complete within a single Codex session and follows our orchestrator handoff pattern.

### Evidence Sweep (current state)

- Monolith hotspots in `src/frame_compare/core.py` (still present):
  - Config template/preset + writer helpers: `_read_template_text`, `_load_template_config`, `_deep_merge`, `_diff_config`, `_format_toml_value`, `_flatten_overrides`, `_apply_overrides_to_template`, `_write_config_file`, `_present_diff`, `_list_preset_paths`, `_load_preset_data`, `PRESETS_DIR`, `PRESET_DESCRIPTIONS`.
  - Doctor: `DoctorCheck` (TypedDict), `_collect_doctor_checks`, `_emit_doctor_results`.
  - Runtime helpers consumed by runner: `_parse_audio_track_overrides`, `_first_non_empty`, `_parse_year_hint`, `_format_seconds`, `_fps_to_float`, `_fold_sequence`, `_evaluate_rule_condition`, `_build_legacy_summary_lines`, `_format_clock`, `_init_clips`, `_resolve_selection_windows`, `_log_selection_windows`, `_validate_tonemap_overrides`.
  - TMDB workflow: `TMDBLookupResult`, `_should_retry_tmdb_error`, `_resolve_tmdb_blocking`, `resolve_tmdb_workflow`, `_prompt_manual_tmdb`, `_prompt_tmdb_confirmation`, `_render_collection_name`.
  - CLI constants used by `frame_compare.py`: `_DEFAULT_CONFIG_HELP`, `PRESET_DESCRIPTIONS`.
- Existing extractions already in place: `wizard.py`, `preflight.py`, `vspreview.py`, `cli_runtime.py`, `metadata.py`, `layout_utils.py`.
- Tests import `core` broadly for shims/monkeypatching across `tests/runner` and CLI suites; compatibility exports must be preserved during the transition.

### Sub‑phase 9.1 – Extract Doctor module (single session)

- Scope
  - Create `src/frame_compare/doctor.py` exposing:
    - `DoctorCheck` (TypedDict)
    - `collect_checks(config_path: Path, cfg) -> list[DoctorCheck]`
    - `emit_results(checks: list[DoctorCheck], *, json_mode: bool) -> None`
  - Rewire `frame_compare.py` doctor subcommand to use the new module.
  - Keep `core._collect_doctor_checks` and `core._emit_doctor_results` as thin shims (deprecation planned post‑stabilization).
  - Design: keep the doctor surface programmatic — `collect_checks` returns structured data (`list[DoctorCheck]`), and the CLI formats output; this enables external tooling to reuse checks without importing CLI wiring.
- Orchestrator Handoff
  - Provide target file list, function moves, and acceptance tests (`tests/cli/test_doctor.py`, formerly `tests/test_cli_doctor.py`).
  - Confirm no change to CLI flags/structures.
- Success Checks
  - `pytest -q` passes, no CLI behavior change, `ruff`/`pyright` clean.
  - New module covered by existing tests; no new failures.
- Rollback
  - Revert import wiring to `core` and retain the module for future re‑attempt.

**2025-11-11 update (Phase 9.1):** `src/frame_compare/doctor.py` now owns `DoctorCheck`, `collect_checks`, and `emit_results`; `frame_compare.py` imports the module as `doctor_module` to avoid clashing with the CLI command while both the `doctor` subcommand and the wizard invoke the extracted helpers. `src/frame_compare/core.py` initially aliased `_collect_doctor_checks` / `_emit_doctor_results` so downstream monkeypatches could continue targeting `core`; those shims were deleted in Phase 9.8 once the curated exports proved stable. `tests/cli/test_doctor.py` (previously `tests/test_cli_doctor.py`) plus the wizard/runner suites exercised the flow unchanged, and docs/checklists reference the new boundary.

### Sub‑phase 9.2 – Extract Config Writer and Presets (single session)

- Scope
  - Add `src/frame_compare/config_writer.py` with: `read_template_text`, `load_template_config`, `render_config_text`, `write_config_file` (public); supporting `_deep_merge`, `_diff_config`, `_format_toml_value`, `_flatten_overrides` (private).
  - Add `src/frame_compare/presets.py` with: `PRESETS_DIR`, `PRESET_DESCRIPTIONS`, `list_preset_paths`, `load_preset_data`.
  - Update `frame_compare.py` to import from these modules; maintain `core` shims for one release.
- Orchestrator Handoff
  - Provide mapping of function names moved and CLI call sites.
  - Ensure preset descriptions remain identical (affects `frame_compare.py` help text).
- Success Checks
  - `pytest`/`ruff`/`pyright` clean; CLI `wizard`/`preset` flows unchanged.
  - Docs updated where they reference template/preset responsibilities.
- Rollback
  - Repoint CLI imports to `core` functions; keep the new modules staged but unused.

### Sub‑phase 9.3 – Unhook Runner from `core` where trivial (single session)

- Scope
  - Replace `core._abort_if_site_packages` with `preflight._abort_if_site_packages` in `runner.py`.
  - Replace `core._VSPREVIEW_*` constants with direct imports from `vspreview`.
  - Introduce shared formatting helpers (time/FPS/clock/fold/conditions) under `layout_utils` (or new `runtime_utils`) and update `runner.py` callers.
  - Move `_first_non_empty` (and optionally `_parse_year_hint`) into `metadata.py`; update runner references.
  - Move `_parse_audio_track_overrides` from `core` to `metadata.py` and refactor `runner.py` call sites accordingly.
- Orchestrator Handoff
  - Provide the exact runner call sites to update and the replacement helpers.
- Success Checks
  - `pytest`/`ruff`/`pyright` clean; zero behavior drift in logs/JSON.
- Rollback
  - Temporary re‑alias the new helpers back through `core` if needed.

**2025-11-11 update (Phase 9.3):** `runner.py` now imports `_abort_if_site_packages` directly from `src.frame_compare.preflight`, reads VSPreview install hints and manual-command helpers from `src.frame_compare.vspreview`, and relies on the new `src.frame_compare/runtime_utils.py` module for FPS math, elapsed/ETA clocks, legacy summary folding, and simple condition evaluation. `_parse_audio_track_overrides`, `first_non_empty`, and `parse_year_hint` live in `src.frame_compare.metadata`; `core` briefly provided shims for those names until Phase 9.8 removed them. No behavior changes were observed in the layout JSON or console output, and the existing runner/CLI suites exercise the updated helpers without modification.

### Sub‑phase 9.4 – Selection and Clip Initialization helpers (single session)

- Scope
  - Move `_init_clips`, `_resolve_selection_windows`, `_log_selection_windows` to `alignment_runner.py` (or a new `selection.py`).
  - Publicly export stable names; update runner imports.
  - Keep `core` shims to forward for one release.
- Orchestrator Handoff
  - Provide the function signatures and test touch points in `tests/runner/test_cli_entry.py` and related suites.
- Success Checks
  - `pytest`/`ruff`/`pyright` clean;
  - Runner path retains identical messages/progress lines.
- Rollback
  - Restore runner imports to `core` and leave new exports in place.

**2025-11-11 update (Phase 9.4):** Added `src/frame_compare/selection.py` to house `_extract_clip_fps`, `init_clips`, `resolve_selection_windows`, and `log_selection_windows`. `runner.py` now imports `selection_utils` for clip init and selection logging; the temporary `core` delegates kept `_COMPAT_EXPORTS` consumers working until Phase 9.8 removed those shims entirely. No new tests were required because the existing runner suites already cover selection window logging and clip initialization, and the CLI behavior (progress output + Rich messages) remains unchanged.

### Sub‑phase 9.5 – Curated exports + typing surface (single session)

- Scope
  - Update top‑level `frame_compare` curated exports to point to new modules.
  - Maintain `_COMPAT_EXPORTS` shims for removed `core` members with deprecation notes.
  - Update `typings/frame_compare.pyi` for any newly surfaced functions when exposed via `frame_compare`.
  - Decide on shipping `py.typed` (likely yes) to support inline typing across modules.
- Orchestrator Handoff
  - Provide the intended public API list and any deprecations to announce.
- Success Checks
  - `pyright --warnings` remains clean for consumers importing from `frame_compare`.
  - CHANGELOG entry drafted (internal: deprecations noted; external: new stable imports).
- Rollback
  - Limit curated exports to previous set and hold new modules as internal.

**2025-11-11 update (Phase 9.5):** `frame_compare.py` now re-exports the dedicated doctor, config_writer, presets, and VSPreview helpers through `_COMPAT_EXPORTS` so downstream imports no longer reach into `src.frame_compare.core`. `typings/frame_compare.pyi` advertises the curated surface (doctor helpers, VSPreview constants, `RunRequest/RunResult`), and `src/frame_compare/py.typed` plus the `MANIFEST.in` entry mark the package as typed per PEP 561. Tests remain unchanged because the compatibility map still exposes the legacy names, but Pyright now sees the public doctor helpers without falling back to `Any`.

### Sub‑phase 9.6 – Fixture cleanup plan + representative refactors (single session)

- Scope
  - Document the test moves for CLI (`tests/cli/test_wizard.py`, `tests/cli/test_doctor.py`) to mirror `tests/runner/` pattern.
  - Design fixtures to replace `_patch_*` helpers (e.g., a fixture for CLI dependency patching, VSPreview context manager), keeping current tests intact for now.
- Orchestrator Handoff
  - Provide a fixture design proposal with 1–2 representative refactors guarded by existing tests.
- Success Checks
  - No test failures; clearer path for Phase 10 test reorg.
- Rollback
  - Keep design notes; do not change existing `_patch_*` usages.

**2025-11-11 update (Phase 9.6):** Added shared VSPreview helpers/fixtures plus a thin CLI harness fixture, refactored `tests/cli/test_doctor.py` (renamed from `tests/test_cli_doctor.py`) and `tests/runner/test_audio_alignment_cli.py` to consume them, and noted in helper docstrings that legacy `_patch_*` utilities survive until Phase 10.

- **CLI test split plan:** When we relocate the CLI-focused suites in Phase 10, target `tests/cli/test_wizard.py` and `tests/cli/test_doctor.py` so the structure mirrors `tests/runner/`.

### Risks & Mitigations

- Test breakage from shim changes
  - Keep `core` shims and `_COMPAT_EXPORTS` intact for one release; update curated exports last. If failures appear, temporarily re‑alias new helpers back through `core`.
- Runner drift from duplicated helpers
  - Centralize time/FPS/fold/condition/clock/formatting helpers in `layout_utils` (or `runtime_utils`). Consider adding a tiny unit test for these pure helpers if gaps appear; otherwise rely on existing suites.
- CLI regressions in doctor/presets flows
  - Keep CLI command signatures/flags unchanged; wire to new modules beneath. `tests/cli/test_doctor.py` covers JSON/text outputs and dependency checks.
- Downstream patch points
  - Preserve `frame_compare._COMPAT_EXPORTS` names for the compatibility window and document deprecations in CHANGELOG with migration notes.

### Verification (each sub‑phase)

- Commands
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`
  - `.venv/bin/ruff check`
  - `.venv/bin/pyright --warnings`
  - Optional smoke: `python -m frame_compare --help`
- Artifacts
  - Update `docs/DECISIONS.md` with UTC date stamp, brief summary, and quartet outcomes.
  - Update tracker tables here and in `docs/runner_refactor_checklist.md`.

### Documentation updates (each sub‑phase)

- README.md: Runner API examples (`RunRequest`, `RunResult`, `runner.run`) and import guidance (avoid `src.*`).
- CHANGELOG.md: Note deprecations/new modules and typed surface updates.
- `docs/DECISIONS.md`: Session logs and verification output summaries.
- This file: mark sub‑phase as ☑ when merged; keep notes concise.

### Progress Tracker Rows (Phase 9)

| Phase | Sub-phase | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| 9 | 9.1 Doctor extraction |  | ☑ | `doctor.py` added; CLI routes via `doctor_module`; rollout shims lived in `core` until Phase 9.8 removed them. |
| 9 | 9.2 Config writer + presets |  | ☑ | Extracted config_writer/presets modules, rewired CLI, and retired the temporary `core` shims as part of Phase 9.8. |
| 9 | 9.3 Runner unhook (trivial) |  | ☑ | Runner now sources metadata helpers + runtime utils outside `core`, uses `preflight` `_abort_if_site_packages`, and reads VSPreview constants directly; the interim metadata shims were deleted in Phase 9.8. |
| 9 | 9.4 Selection/init helpers |  | ☑ | `selection.py` now owns clip init + selection window logging; runner imports it directly and the compatibility shims were removed during Phase 9.8. |
| 9 | 9.5 Curated exports + typing |  | ☑ | `_COMPAT_EXPORTS` now points to the doctor/presets/config_writer modules plus VSPreview helpers, typings expose the doctor helpers, and `py.typed` ships for PEP 561. |
| 9 | 9.6 Fixture cleanup plan |  | ☑ | Added VSPreview/which fixtures + runner context manager, refactored doctor/audio-alignment tests, and documented the upcoming CLI test split plan. |
| 9 | 9.7 Import contracts |  | ☑ | `importlinter.ini` enforces runner→core→modules layering plus module→CLI/core bans, and the lint job now installs + runs `lint-imports` (runner→core ignore documented). |
| 9 | 9.8 Remove legacy shims |  | ☑ | Removed `core` doctor/config-writer/presets/metadata/selection shims and trimmed curated exports to point at the extracted modules directly. |
| 9 | 9.9 Test layout finalization |  | ☑ | CLI suites now live in `tests/cli/` (package-ified to avoid duplicate module names), mirroring the runner layout. |
| 9 | 9.10 Public __all__ |  | ☑ | Added explicit `__all__` lists for the extracted modules (doctor/config_writer/presets/runtime_utils/selection) so wildcard imports mirror the curated exports; tracked in DECISIONS on 2025‑11‑11. |
| 9 | 9.11 Type strictness ratchet |  | ☑ | `pyrightconfig.json` now enables `"strict": ["src/frame_compare"]`, and the resulting annotation/Optional fixes keep `.venv/bin/pyright --warnings` clean (see DECISIONS 2025‑11‑11). |
| 9 | 9.12 Runner API docs |  | ☑ | Documented curated runner/doctor API usage, reference guide, and tracker/log updates. |
| 10 | 10.1 TMDB workflow extraction |  | ☑ | `src/frame_compare/tmdb_workflow.py` now hosts the resolver dataclass, prompts, and collection helper; CLI/runner import it directly and trackers/DEC log the verification quartet (2025‑11‑12). |
| 10 | 10.2 TMDB shim removal |  | ☑ | `core.py` dropped the transitional TMDB forwarders, `_COMPAT_EXPORTS` no longer re-export `_resolve_tmdb_blocking`, and tests/docs patch `tmdb_workflow` directly (2025‑11‑12). |
| 10 | Compatibility cleanup |  | ⛔ | Final audit of `_COMPAT_EXPORTS`, wizard/VSPreview shims, and import-linter ignores still pending post-Phase 10. |

---

## Sub‑phase 9.7 — Import Contracts (enforce boundaries)

Goal: codify and enforce import layering so CLI shims stay thin and modules don’t back‑import higher layers.

Scope
- Define layers: `frame_compare (CLI)` → `src.frame_compare.runner` → `src.frame_compare.*` modules. Prohibit `modules → CLI` and `modules → core` (core is shim only).
- Add import-linter contracts and wire into CI.

Deliverables
- `importlinter.ini` at repo root with contracts:
  - Layered contract enforcing the ordering above.
  - Forbidden contract blocking direct imports from `src.frame_compare.*` into `frame_compare.py` (only curated exports allowed).
- CI step in `.github/workflows/ci.yml` running import-linter.

**2025-11-11 update:** `importlinter.ini` now encodes a runner→core→modules layering contract plus forbidden module→CLI/core rules (the existing `runner.py` dependency on `core` is temporarily ignored and tagged for Phase 10 cleanup). The lint workflow installs `import-linter` and runs `lint-imports --config importlinter.ini` so CI fails on new violations, and Ruff’s config now treats `frame_compare` as first-party so style checks stay stable around the CLI shim.

Acceptance
- Local run documented in DECISIONS: `lint-imports --config importlinter.ini` passes (import-linter ships this entrypoint instead of `python -m importlinter`).
- CI job passes; violations fail with clear messages.

Risks & Mitigations
- Transitional shims may trip contracts; add temporary ignores with TODO removal notes.

Verification
- Record command outputs and waivers in `docs/DECISIONS.md` (UTC stamped).

## Sub‑phase 9.8 — Remove Legacy Shims (no deprecation window)

Goal: eliminate redundant `core` forwarders introduced in Phase 9 and rely solely on the extracted modules; minimize dead code and confusion.

Scope
- Remove the following shim functions from `src/frame_compare/core.py` (they currently delegate to extracted modules):
  - Doctor: `_collect_doctor_checks`, `_emit_doctor_results` → use `src.frame_compare.doctor`
  - Config writer/presets: `_read_template_text`, `_load_template_config`, `_deep_merge`, `_diff_config`, `_format_toml_value`, `_flatten_overrides`, `_apply_overrides_to_template`, `_render_config_text`, `_write_config_file`, `_present_diff`, `PRESETS_DIR`, `_list_preset_paths`, `_load_preset_data`, `PRESET_DESCRIPTIONS` → use `src.frame_compare.config_writer` and `src.frame_compare.presets`
  - Metadata helpers: `_parse_audio_track_overrides`, `_first_non_empty`, `_parse_year_hint` → use `src.frame_compare.metadata`
  - Selection: `_init_clips`, `_resolve_selection_windows`, `_log_selection_windows` → use `src.frame_compare.selection`
- Prune redundant curated exports in `frame_compare.py` where they only existed to expose the above shims; ensure curated names point to final modules, not `core`.
- Intentionally out of scope for 9.8 (kept for Phase 10): TMDB workflow and any remaining VSPreview/wizard shims used by tests.

Deliverables
- Deletions in `core.py` for the shim functions above.
- Trim `_COMPAT_EXPORTS` in `frame_compare.py` to remove entries for deleted shims (or repoint to the concrete modules if still useful at top level).
- Test adjustments only if they directly import deleted shims (prefer importing the concrete module or curated export instead). Aim to keep changes minimal.

Acceptance
- `pytest -q`, `ruff`, and `pyright --warnings` are clean.
- No runtime references to removed shims remain in runner/CLI.
- Tests (and any curated exports) refer to concrete modules after removal.

Verification
- Record removed names and replacement imports in `docs/DECISIONS.md` with a UTC stamp.

**2025-11-11 update:** `src/frame_compare/core.py` no longer defines the doctor/config-writer/presets/metadata/selection shims—the CLI and runner call the extracted modules directly, and `frame_compare._COMPAT_EXPORTS` simply aliases `doctor_module.collect_checks` plus the module surfaces instead of forwarding through `core`. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` (273 passed, 1 skipped in 39.96 s), `.venv/bin/ruff check`, and `.venv/bin/pyright --warnings` all passed after the cleanup, matching the acceptance criteria above.

## Sub‑phase 9.9 — Test Layout Finalization (CLI split)

Goal: move remaining CLI tests to `tests/cli/` to mirror `tests/runner/` and improve discoverability.

Scope
- Move tests: `tests/test_cli_wizard.py` → `tests/cli/test_wizard.py`, `tests/test_cli_doctor.py` → `tests/cli/test_doctor.py`, plus preset CLI tests if present.
- Ensure fixtures in `tests/conftest.py` keep paths/imports stable.

Deliverables
- File moves with updated imports if necessary; no behavior changes.
- Docs tracker updates reflecting new locations.

Acceptance
- `pytest -q` passes with the same count (modulo path changes).

Verification
- Record pre/post test discovery and path changes in DECISIONS.

**2025-11-11 update:** Relocated the CLI suites into `tests/cli/` (`test_doctor.py`, `test_wizard.py`, `test_help.py`, `test_layout.py`) and added `tests/cli/__init__.py` so pytest qualifies the modules uniquely alongside `tests/test_wizard.py`. Targeted runs (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q tests/cli/test_doctor.py`, etc.) plus the full suite remained at 273 passed / 1 skipped, and `.venv/bin/ruff check` + `.venv/bin/pyright --warnings` stayed clean. `docs/runner_refactor_checklist.md` and this tracker now reference the new directory structure, and the DEC log notes the relocation along with the pytest collection rationale.

## Sub‑phase 9.10 — Public __all__ Contracts

Goal: constrain module surfaces to intended exports to avoid accidental bleed of private helpers.

Scope
- Add explicit `__all__` lists to: `src/frame_compare/selection.py`, `runtime_utils.py`, `presets.py`, `config_writer.py`, `doctor.py`.
- Ensure runner/CLI imports align with `__all__`.

Deliverables
- Updated modules with `__all__` and any import fixes in call sites.

Acceptance
- `ruff`/`pyright` clean; no import errors.

**2025-11-11 update:** `__all__` declarations now live in `src/frame_compare/selection.py`, `runtime_utils.py`, `config_writer.py`, `presets.py`, and `doctor.py`, restricting wildcard imports to the intended helpers (e.g., `selection.__all__ = ["extract_clip_fps", "init_clips", "resolve_selection_windows", "log_selection_windows"]`). Runner/CLI callers import those public names directly, `_COMPAT_EXPORTS` mirrors them, and the verification quartet (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`) stayed clean as logged in DECISIONS.

## Sub‑phase 9.11 — Type Strictness Ratchet (recommended)

Goal: increase type safety for library modules now that surfaces are stable.

Scope
- Update `pyrightconfig.json` to set `strict` for `src/frame_compare/**` (excluding the top-level `frame_compare.py` CLI shim if needed).
- Address surfaced annotations/Optional guards in the new modules (doctor, selection, presets, config_writer, runtime_utils).

Deliverables
- `pyrightconfig.json` edits and minimal code annotation/guard tweaks if warnings appear.

Acceptance
- `.venv/bin/pyright --warnings` clean; no behavior changes.

Risks & Mitigations
- If strictness produces noisy false positives, scope it to the extracted modules first, then widen later.

**2025-11-11 update:** `pyrightconfig.json` now enables `"strict": ["src/frame_compare"]`, covering all extracted modules while leaving the top-level CLI shim under standard mode. The resulting annotation/Optional fixes (runner reporter wiring, VSPreview helpers, tonemap/media exports) landed alongside a clean `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` run recorded in DECISIONS, so the stricter gate is fully enforced going forward.

## Sub‑phase 9.12 — Runner API Docs + Examples

Goal: document the stable programmatic API and provide concise usage recipes.

Scope
- Update `docs/README_REFERENCE.md` (or README) with examples for:
  - `RunRequest` → `runner.run` → `RunResult`
  - Programmatic doctor usage (`collect_checks`/`emit_results`)
  - Import guidance: use `frame_compare` curated exports; avoid `src.*`.

Deliverables
- Docs updated; link MIGRATIONS and module map.

Acceptance
- Examples run in a minimal snippet; no code changes needed.

## Phase 10 – TMDB Workflow Extraction (stub)

Goal: move TMDB workflow out of `core` into `src/frame_compare/tmdb_workflow.py` with stable, typed API for both CLI and runner.

- Scope (future sessions)
  - Extract `TMDBLookupResult`, `_should_retry_tmdb_error`, `_resolve_tmdb_blocking`, `resolve_tmdb_workflow`, `_prompt_manual_tmdb`, `_prompt_tmdb_confirmation`, `_render_collection_name`.
  - Provide non‑interactive/unattended paths and prompt hooks; centralize retry/backoff.
  - Update runner and CLI to import workflow; keep `core` shims for one release.
- Verification
  - Same quartet; ensure existing `tests/test_tmdb.py` and runner slow.pics workflow tests keep passing.
- Docs
  - README and `docs/README_REFERENCE.md` to reference shared workflow; CHANGELOG notes compatibility window.

### Sub-phase 10.1 — Extract TMDB Workflow

- [x] Move `TMDBLookupResult`, `_should_retry_tmdb_error`, `_resolve_tmdb_blocking`, `resolve_tmdb_workflow`, `_prompt_manual_tmdb`, `_prompt_tmdb_confirmation`, and `_render_collection_name` into `src/frame_compare/tmdb_workflow.py` behind a public API (`resolve_workflow`, `resolve_blocking`, `render_collection_name`).
- [x] Rewire `core`, `runner`, curated exports, and typings to import the new module while keeping thin forwarders so existing tests/scripts stay stable ahead of Phase 10.2.
- [x] Append docs/DECISIONS + tracker notes plus rerun the verification quartet to confirm behavior parity (slow.pics naming, prompts, unattended paths).

**2025-11-12 update:** New module `src/frame_compare/tmdb_workflow.py` now owns the TMDB workflow dataclass, blocking resolver, rendering helper, and prompt utilities. `core.py` simply forwards the public API plus transitional prompt wrappers, the runner imports `tmdb_workflow` directly, and `_COMPAT_EXPORTS`/typing stubs now point to the extracted module (including an optional `render_collection_name` export for scripts). `docs/refactor/mod_refactor.md` + `docs/DECISIONS.md` capture the migration details and the `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings` run recorded below passed without regressions.

### Sub-phase 10.2 — Remove Legacy Shims (post-extraction cleanup)

Goal: eliminate any remaining `core` forwarders related to TMDB/VSPreview/Wizard that were retained for test stability, so only the extracted modules provide the functionality.

Scope
- After 10.1 lands, delete TMDB shims from `core` (e.g., `_resolve_tmdb_blocking`, `resolve_tmdb_workflow`, prompts, `_render_collection_name`) and repoint or prune any curated exports that referenced them.
- Remove lingering VSPreview/Wizard compatibility shims if tests no longer need them (they should rely on `src.frame_compare.vspreview` and `src.frame_compare.wizard`).
- Update tests to import concrete modules or curated exports where they still referenced the shim names.

Deliverables
- Shim removals in `src/frame_compare/core.py`.
- Pruned or repointed entries in `frame_compare._COMPAT_EXPORTS`.
- Any necessary test import updates.

- [x] Remove TMDB shim exports from `core.py` and drop the `_resolve_tmdb_blocking` compatibility entry in `frame_compare._COMPAT_EXPORTS`.
- [x] Update runner helpers/tests to patch `tmdb_workflow` directly plus refresh README, docs/config audits, and tracker notes to reference the shared module.
- [x] Log DECISIONS/tracker updates for Phase 10.2 and rerun the quartet + `uv run --no-sync lint-imports --config importlinter.ini` (see 2025‑11‑12 entry).

Acceptance
- `pytest -q`, `ruff`, and `pyright --warnings` clean with no references to removed shims.
- Docs updated in `docs/DECISIONS.md` (UTC) summarizing removed names and replacements.

**2025-11-12 update:** `core.py` no longer imports or forwards TMDB helpers, `_COMPAT_EXPORTS` only exposes the curated names backed by `tmdb_workflow`, runner/tests patch `tmdb_workflow` directly, and README/config docs point at the workflow module. Verification recorded in `docs/DECISIONS.md` captured `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` (`273 passed, 1 skipped in 39.99 s`), `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`, and `uv run --no-sync lint-imports --config importlinter.ini` with all contracts kept.

## Phase 11 – Production Readiness Refactors (single‑session sub‑phases)

Goal: reduce remaining monoliths, harden subprocess/logging practices, and finalize packaging/layout for maintainability and safety. Each sub‑phase is designed to be completed in a single Codex session.

### Progress Tracker (Phase 11)

| Phase | Sub‑phase | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| 11 | 11.1 Render helpers extraction |  | ☑ | `src/frame_compare/render/{naming,overlay,encoders,geometry,errors}.py` host the pure helpers moved out of `src/screenshot.py`, with wrappers/tests + import-linter layering recorded on 2025‑11‑12. |
| 11 | 11.2 Analysis split |  | ☑ | Analysis helpers now live in `src/frame_compare/analysis/{metrics,selection,cache_io}.py` with `src/analysis.py` as a shim; DEC logs + tests recorded on 2025‑11‑12. |
| 11 | 11.3 Subprocess hardening |  | ☑ | `src/frame_compare/subproc.py::run_checked` now wraps FFmpeg/FFprobe/VSPreview calls from screenshot, audio_alignment, and vspreview; tests/logs updated on 2025‑11‑12. |
| 11 | 11.4 Logging normalization |  | ☑ | Library modules now log via `logger`/reporter instead of `print()`, with CLI surfaces unchanged (2025‑11‑12). |
| 11 | 11.5 Packaging cleanup + legacy removal |  | ☑ | Moved `src/{cli_layout,report,slowpics,config_template}.py` under `src/frame_compare/`, added shims, and removed `Legacy/comp.py` (2025‑11‑12). |
| 11 | 11.6 vs_core split by concerns |  | ☑ | `src/frame_compare/vs/{env,source,props,color,tonemap}.py` host the VS helpers; `src/vs_core.py` is now a shim until 11.10 (2025‑11‑12). |
| 11 | 11.7 Retry/backoff consolidation |  | ⛔ | Introduce `net.py` retry/HTTP client helpers; refactor network users. |
| 11 | 11.8 Config docs generation |  | ⛔ | Script to generate config reference from `src/datatypes.py`. |
| 11 | 11.9 CI + packaging checks |  | ⛔ | Update import‑linter, build wheel, validate artifacts. |
| 11 | 11.10 Remove transitional shims |  | ⛔ | Delete temporary shims/bridges introduced in Phase 11. |

### Sub‑phase 11.1 — Render Helpers Extraction (from `src/screenshot.py`)

Goal: extract pure helpers (naming, geometry shaping/formatting, overlay text/state, encoder mappings) into dedicated modules to shrink the screenshot monolith and enable focused tests — with zero behavior changes.

Scope & constraints
- Keep public behavior and CLI outputs stable; file naming and overlay text must not change.
- Do not introduce new runtime deps; extracted helpers must remain pure (no VapourSynth or subprocess usage).
- Preserve existing private helper names in `src/screenshot.py` via thin wrappers to avoid touching current tests.
- Package location: `src/frame_compare/render/` with modules `naming.py`, `geometry.py`, `overlay.py`, `encoders.py` and curated `__all__`.
- Leave heavy VS‑dependent functions in `src/screenshot.py` (e.g., `_apply_frame_info_overlay`, `_apply_overlay_text`, writers); only move pure helpers.
- Keep `GeometryPlan` TypedDict defined in `src/screenshot.py` for this sub‑phase to avoid churn; geometry helpers may accept/return plain tuples/ints.

Detailed step list (per‑file; anchors/search)
1) Scaffold package structure
   - Add files: `src/frame_compare/render/__init__.py`, `src/frame_compare/render/naming.py`, `src/frame_compare/render/geometry.py`, `src/frame_compare/render/overlay.py`, `src/frame_compare/render/encoders.py`.
   - `__init__.py` should re‑export curated symbols for convenience; include `__all__`.

2) Extract naming helpers to `render/naming.py`
   - Move constants and helpers (keep same semantics; public names without leading underscore):
     - `INVALID_LABEL_PATTERN` from `src/screenshot.py:38` (pattern literal) → export.
     - `sanitise_label(label: str) -> str` from `src/screenshot.py:1957`.
     - `derive_labels(source: str, metadata: Mapping[str, str]) -> tuple[str, str]` from `src/screenshot.py:1965`.
     - `prepare_filename(frame: int, label: str) -> str` from `src/screenshot.py:1971`.
   - In `src/screenshot.py`, replace bodies with thin wrappers that call into `render.naming.*` and keep original private names:
     - `_sanitise_label`, `_derive_labels`, `_prepare_filename`.

3) Extract overlay text/state helpers to `render/overlay.py`
   - Move mapping + helpers:
     - Selection labels map `_SELECTION_LABELS` from `src/screenshot.py:58` (export as `SELECTION_LABELS`).
     - `new_overlay_state`, `append_overlay_warning`, `get_overlay_warnings` from `src/screenshot.py:80`, `:133`, `:144`.
     - `normalize_selection_label`, `format_selection_line` from `src/screenshot.py:286`, `:308`.
     - MDL helpers: `extract_mastering_display_luminance`, `format_luminance_value`, `format_mastering_display_line` from `src/screenshot.py:194`, `:248`, `:266`.
     - `compose_overlay_text` from `src/screenshot.py:321`.
     - Style constants `FRAME_INFO_STYLE` and `OVERLAY_STYLE` from `src/screenshot.py:813`, `:817` (export; used by overlay application in screenshot module).
   - In `src/screenshot.py`, import from `render.overlay` and keep wrappers under original private names: `_new_overlay_state`, `_append_overlay_warning`, `_get_overlay_warnings`, `_normalize_selection_label`, `_format_selection_line`, `_format_mastering_display_line`, `_compose_overlay_text`. Update constant references to imported ones.
   - Leave VS‑dependent overlay application functions in place (`_apply_frame_info_overlay` at `src/screenshot.py:825`, `_apply_overlay_text` at `src/screenshot.py:921`).

4) Extract encoder/compression helpers to `render/encoders.py`
   - Move helpers:
     - `normalise_compression_level`, `map_fpng_compression`, `map_png_compression_level` from `src/screenshot.py:1975`, `:1983`, `:1988`.
     - `map_ffmpeg_compression` from `src/screenshot.py:2345`.
     - `escape_drawtext` from `src/screenshot.py:2351`.
   - In `src/screenshot.py`, keep wrappers under original private names: `_normalise_compression_level`, `_map_fpng_compression`, `_map_png_compression_level`, `_map_ffmpeg_compression`, `_escape_drawtext`.

5) Extract minimal geometry formatting/odds helpers to `render/geometry.py`
   - Move strictly pure helpers (no VS/frame objects):
     - `format_dimensions` from `src/screenshot.py:154`.
     - `axis_has_odd`, `get_subsampling` from `src/screenshot.py:1146`, `:1135`.
     - `compute_requires_full_chroma` from `src/screenshot.py:1377`.
     - `plan_mod_crop` from `src/screenshot.py:1398`.
     - `align_letterbox_pillarbox` from `src/screenshot.py:1440`.
     - `plan_letterbox_offsets` from `src/screenshot.py:1479`.
     - `split_padding`, `align_padding_mod` from `src/screenshot.py:1556` (search: `def _split_padding`), `:1568` (search: `def _align_padding_mod`).
     - `compute_scaled_dimensions` from `src/screenshot.py:1602` (search: `def _compute_scaled_dimensions`).
     - `describe_plan_axes` from `src/screenshot.py:1157`.
   - Keep `_plan_geometry` in `src/screenshot.py` and switch its internal calls to the imported helpers from `render.geometry` to avoid type churn on `GeometryPlan` this session.
   - In `src/screenshot.py`, keep wrapper names for moved helpers to preserve existing test imports: `_format_dimensions`, `_compute_requires_full_chroma`, etc., delegating to `render.geometry`.

6) Rewire references inside `src/screenshot.py`
   - Add imports at top: `from src.frame_compare.render import naming as _naming, overlay as _overlay, encoders as _enc, geometry as _geo`.
   - Replace internal calls to moved helpers with their delegated equivalents. Keep function docstrings and signatures unchanged in the wrappers.

7) Add focused unit tests for the new modules (no VS required)
   - New files:
     - `tests/render/test_naming.py`: port assertions from `tests/test_screenshot.py::test_sanitise_label_*`, plus `_derive_labels`, `_prepare_filename` happy paths.
     - `tests/render/test_overlay_text.py`: port assertions from `tests/test_screenshot.py::test_compose_overlay_text_*` that don’t need VS; assert MDL formatting edge cases.
     - `tests/render/test_encoders.py`: cover normalise/map functions and `escape_drawtext` escaping matrix.
     - `tests/render/test_geometry_helpers.py`: cover `plan_mod_crop`, `compute_requires_full_chroma` (using simple fake fmt objects), `split/align padding`, `format_dimensions`.
   - Keep existing `tests/test_screenshot.py` intact; wrappers ensure parity.

8) Import‑linter layering (coding step in 11.1)
   - Update `importlinter.ini` modules layer to include `src.frame_compare.render` in the third layer list so render helpers are treated as modules consumed by `core`/`runner` but never vice‑versa.

Acceptance criteria & verification commands
- Behavior parity: filenames, overlay text lines, and writer selection logic unchanged for existing tests.
- Lint/type/tests clean:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` (or `.venv/bin/pytest -q`) → all existing tests pass; new `tests/render/` pass without VapourSynth.
  - `.venv/bin/ruff check` → no issues.
  - `.venv/bin/pyright --warnings` → 0 errors/warnings. If local binaries missing, use `uv run --no-sync ruff check` and `npx pyright --warnings` as fallback.
- Import contracts unchanged: run `uv run --no-sync lint-imports --config importlinter.ini` and confirm 0 broken contracts after adding `render` to the layer list.

Docs/tracker updates
- Flip row description for 11.1 in the Phase 11 tracker to reference `render/*` modules once merged; status remains ⛔ until PR lands.
- Append a quartet entry to `docs/DECISIONS.md` capturing baseline commands and the extraction boundaries; include anchors above.

Risks & mitigations
- Type churn on `GeometryPlan`: keep it in `src/screenshot.py` for now; only move shape in a later phase when consumers are ready.
- Hidden dependencies on underscore helpers: wrappers with identical names and signatures avoid test churn; search for direct calls with Serena search before edits.
- Import cycles: `render/*` must not import `src/screenshot.py`; keep helpers independent and rely only on stdlib and `src.datatypes` if needed.
- Naming drift: preserve function semantics; add `__all__` in each new module to document surface.

Conventional Commit subject
- `refactor(render): extract pure screenshot helpers into render modules`

**2025-11-12 update:** Added the dedicated `src/frame_compare/render/` package (naming, overlay, encoders, geometry, errors) plus focused `tests/render/*` suites. `src/screenshot.py` now imports the helpers and exposes thin wrappers so existing tests keep their imports, while `render/overlay.py` exports overlay styles/state helpers and `render/geometry.py` owns subsampling/cropping math. `importlinter.ini` includes the new package in the modules layer, and docs/runner_refactor_checklist.md + this tracker were updated to describe the split. Verification logs (git status, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`, `uv run --no-sync lint-imports --config importlinter.ini`) are captured in the 2025‑11‑12 Phase 11.1 entry in `docs/DECISIONS.md`.

### Sub‑phase 11.2 — Analysis Split (`metrics.py`, `selection.py`, `cache_io.py`)

Goal: separate metrics computation, selection strategies, and cache IO currently concentrated in `src/analysis.py`, keeping behavior and the public surface stable via a thin shim in `src/analysis.py` (removed in 11.10).

Scope & constraints
- Add package `src/frame_compare/analysis/` with modules:
  - `metrics.py` — frame rate detection, HDR probe, quantile/smoothing math, VapourSynth metric collection and fallback generator.
  - `selection.py` — selection window resolution, selection hashing, selection heuristics and `select_frames` orchestration, selection detail JSON helpers.
  - `cache_io.py` — metrics/selection cache read/write, cache fingerprinting, sidecar load/save, atomic JSON helpers.
- Do not change behavior, logging text, or signatures. Keep `tests/test_analysis.py` unchanged.
- Use absolute imports from `src.frame_compare.analysis` inside the shim to avoid ambiguity with `src/analysis.py`.

Detailed step list (per‑file; anchors/search)
1) Scaffold package structure
   - Add: `src/frame_compare/analysis/__init__.py`, `metrics.py`, `selection.py`, `cache_io.py`.
   - `__init__.py` re‑exports curated public names: `FrameMetricsCacheInfo`, `SelectionDetail`, `compute_selection_window`, `selection_details_to_json`, `selection_hash_for_config`, `select_frames`, `probe_cached_metrics`, `write_selection_cache_file`, `dedupe`.

2) Move metrics helpers to `analysis/metrics.py`
   - Functions (anchors in `src/analysis.py`): `_quantile` (~371), `_frame_rate` (~1175), `_is_hdr_source` (~1258), `_collect_metrics_vapoursynth` (~1282, include internal helpers), `_generate_metrics_fallback` (~1518), `_smooth_motion` (~1548).

3) Move selection logic to `analysis/selection.py`
   - Types/helpers: `SelectionWindowSpec` (~90), `SelectionDetail` (~131) and `_SerializedSelectionDetail`, `_frame_to_timecode` (~216), `_coerce_seconds` (~433), `compute_selection_window` (~457), `selection_details_to_json` (~354), `_serialize_selection_details` (~289), `_deserialize_selection_details` (~306), `_format_selection_annotation` (~341), `selection_hash_for_config` (~579) + `_selection_fingerprint` (~549), `dedupe` (~1146).
   - Orchestration: `select_frames` (~1571) refactored to call into `analysis.metrics` and `analysis.cache_io` for metric collection and persistence.

4) Move cache IO to `analysis/cache_io.py`
   - Dataclasses: `FrameMetricsCacheInfo` (~47), `CachedMetrics` (~62), `CacheLoadResult` (~81).
   - Fingerprints/snapshots: `_threshold_snapshot` (~393), `_config_fingerprint` (~409) live here; import in `selection.py`.
   - Read path: `probe_cached_metrics` (~585) and convenience loader (~720), plus coercers strictly needed for cache parsing (`_coerce_metric_series` (~220), `_coerce_int_list` (~186), `_coerce_selection_categories` (~200), `_coerce_optional_*` (~156–178)).
   - File IO helpers: `_atomic_write_json` (~240), `_compute_file_sha1` (~268).
   - Sidecar helpers: `_selection_sidecar_path` (~737), `_build_clip_inputs` (~755), `_selection_cache_key` (~784), `_selection_payload_from_inputs` (~800), `_build_selection_sidecar_payload` (~830), `_save_selection_sidecar` (~848), `write_selection_cache_file` (~927), `_load_selection_sidecar` (~985).
   - Import `SelectionDetail` from `analysis.selection` only for typing/serialization; use `typing.TYPE_CHECKING` and string annotations to avoid cycles.

5) Shim in `src/analysis.py`
   - Replace implementations with delegates to the new package while preserving names used by tests:
     - Public: `FrameMetricsCacheInfo`, `SelectionDetail`, `selection_details_to_json`, `compute_selection_window`, `dedupe`, `probe_cached_metrics`, `select_frames`, `selection_hash_for_config`, `write_selection_cache_file`.
     - Private used by tests: `_quantile`.
   - Keep module docstring and `logger` intact.

6) Rewire internal imports
   - `analysis.selection` imports `analysis.metrics` (`_quantile`, `_frame_rate`, `_smooth_motion`, `_generate_metrics_fallback`, `_collect_metrics_vapoursynth`, `_is_hdr_source`).
   - `analysis.selection` imports `analysis.cache_io` (`probe_cached_metrics`, `_save_cached_metrics`, `_save_selection_sidecar`, `_load_selection_sidecar`).
   - `analysis.cache_io` imports `analysis.selection.SelectionDetail` behind `TYPE_CHECKING`.

7) Update import‑linter layering
   - In `importlinter.ini` → `layers` list: append `src.frame_compare.analysis` to the third layer (module list after `src.frame_compare.core`).

8) Tests
   - Keep `tests/test_analysis.py` unchanged; the shim preserves imports and behavior.
   - Optional: add `tests/analysis/` micro‑suites targeting `src.frame_compare.analysis` modules directly (not required for acceptance).

Acceptance criteria & verification commands
- Behavior parity: selection, windowing, HDR tonemap path, cache hit/miss identical; logging messages unchanged.
- Commands:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` → all tests pass.
  - `.venv/bin/ruff check` → no issues.
  - `.venv/bin/pyright --warnings` → 0 errors/warnings. Fallbacks: `uv run --no-sync ruff check`, `npx pyright --warnings`.
  - `uv run --no-sync lint-imports --config importlinter.ini` → 0 broken contracts; confirms new package in layer.

Risks & mitigations
- Import cycles: avoid by placing dataclasses where consumed (`SelectionDetail` in `selection.py`) and using `TYPE_CHECKING` in `cache_io`.
- Hidden private dependencies: retain wrappers in the shim (e.g., `_quantile`) to keep tests stable.
- Drift in floating‑point math: keep existing implementations unchanged; do not alter rounding or thresholds.

Conventional Commit subject
- `refactor(analysis): split selection, metrics, and cache IO into package`

**2025-11-12 update:** Added `src/frame_compare/analysis/{__init__,metrics,selection,cache_io}.py`, moved the quantile/metrics collectors, selection orchestration (including `SelectionDetail`, hashing, dedupe, and selection metadata serializers), and cache I/O helpers out of `src/analysis.py`, and kept the legacy module as a shim that re-exports the public API plus the `_collect_metrics_*` helpers the tests patch. `importlinter.ini` now includes `src.frame_compare.analysis` in the module layer so runner/core can safely depend on it, and the new modules declare `# pyright: standard` to avoid regressing strict checks elsewhere. Verification commands (`git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`, `uv run --no-sync lint-imports --config importlinter.ini`) ran clean and are logged in the 2025‑11‑12 Phase 11.2 entry in `docs/DECISIONS.md`. Residual shims stay in `src/analysis.py` until Phase 11.10 removes them.

### Sub‑phase 11.3 — Subprocess Hardening

Goal: centralize and harden all subprocess calls (FFmpeg/FFprobe/VSPreview) to enforce safe argv handling, consistent timeouts and output capture, and predictable error mapping. No behavior or messages visible to users should change.

Scope & constraints
- Add `src/frame_compare/subproc.py` exposing a single entrypoint with safe defaults:
  - `run_checked(argv: Sequence[str], *, cwd: Path | str | None = None, env: Mapping[str, str] | None = None, timeout: float | None = None, stdin: object | None = subprocess.DEVNULL, stdout: object | None = subprocess.PIPE, stderr: object | None = subprocess.PIPE, text: bool = True, check: bool = False) -> subprocess.CompletedProcess[str]`.
  - Always execute with `shell=False`. Document that callers must pass argv lists only.
  - Propagate `subprocess.TimeoutExpired` as‑is; do not raise on non‑zero exit when `check=False` (keeps current calling patterns intact). When `check=True`, raise `subprocess.CalledProcessError` like `subprocess.run`.
  - Log debug summaries of argv and truncated stderr/stdout when `check=True` raises (no secrets handled in our use cases; still avoid echoing full argv at INFO).
- Refactor in‑repo callers to use `run_checked` with equivalent kwargs:
  - `src/screenshot.py::_save_frame_with_ffmpeg` (lines ~2375–2520): replace direct `subprocess.run` with `subproc.run_checked` preserving `stdin=DEVNULL`, `stdout=DEVNULL`, `stderr=PIPE`, and `timeout` semantics; continue mapping `TimeoutExpired` → `ScreenshotWriterError` and non‑zero return code → `ScreenshotWriterError` with decoded stderr.
  - `src/frame_compare/vspreview.py::launch` (lines ~959–998): default its `ProcessRunner` to `subproc.run_checked`; keep `check=False`. In verbose mode, allow inherited stdio by passing `stdout=None, stderr=None`; in non‑verbose mode capture both streams as text.
  - `src/audio_alignment.py`:
    - `probe_audio_streams` (lines ~119–167): replace `subprocess.check_output` with `subproc.run_checked([...], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True)` and parse `result.stdout`.
    - `_extract_audio` (lines ~206–245): replace `subprocess.run(..., check=True, stdout=PIPE, stderr=PIPE, text=True)` with `subproc.run_checked(..., check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)`; preserve error wrapping/messages.
    - `_probe_fps` (lines ~292–323): replace `subprocess.check_output` with `subproc.run_checked([...], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True)`; parse `result.stdout`.
- No `shell=True` anywhere in library code after this change.
- Preserve function signatures of public APIs and domain exceptions (`ScreenshotWriterError`, `AudioAlignmentError`).

Detailed step list (per‑file; anchors/search)
1) Add `src/frame_compare/subproc.py`
   - Implement `run_checked` with the signature above; call `subprocess.run` with `shell=False` and pass through provided stdio/timeout/env/cwd; return the `CompletedProcess`. When `check=True`, re‑raise `CalledProcessError` like `subprocess.run`.
   - Module docstring: purpose + usage contract (argv list, no shell, defaults safe for CLI tools). Export `__all__ = ["run_checked"]`.

2) Refactor `src/screenshot.py` ffmpeg writer
   - At ~2375–2520: replace the `subprocess.run` block with `subproc.run_checked(cmd, stdin=DEVNULL, stdout=DEVNULL, stderr=PIPE, timeout=timeout_seconds, text=False, check=False)`.
   - Keep existing try/except mapping:
     - `except subprocess.TimeoutExpired as exc` → raise `ScreenshotWriterError(f"FFmpeg timed out after {duration:.1f}s for frame {frame_idx}")`.
     - After call, if `process.returncode != 0`, decode stderr and raise `ScreenshotWriterError` (leave current wording unchanged).

3) Refactor `src/frame_compare/vspreview.py` launcher
   - Update `ProcessRunner` default at ~959 to `subproc.run_checked` instead of `subprocess.run`.
   - Ensure non‑verbose path passes `stdout=PIPE, stderr=PIPE, text=True`; verbose path leaves them as inherited (`stdout=None, stderr=None`). Keep `check=False`.
   - Keep the current exception handling (FileNotFoundError, OSError/SubprocessError/RuntimeError) and messages.

4) Refactor `src/audio_alignment.py` tools
   - `probe_audio_streams` (~140): switch to `subproc.run_checked(..., check=True, text=True)`; on `CalledProcessError` wrap into `AudioAlignmentError("ffprobe failed for {path.name}")`.
   - `_extract_audio` (~221): switch to `subproc.run_checked(..., check=True, text=True)`; on `CalledProcessError` include stderr like current behavior.
   - `_probe_fps` (~298): switch to `subproc.run_checked(..., check=True, text=True)`; parse stdout.

5) Tests adjustments (surgical, to keep intent intact)
   - `tests/test_screenshot.py`:
     - test_save_frame_with_ffmpeg_honours_timeout (~1721): monkeypatch `src.frame_compare.subproc.run_checked` (instead of `screenshot.subprocess.run`) to a fake capturing kwargs and returning a `CompletedProcess`‑like object; assert `timeout` and that the assembled `cmd` includes `-nostdin`; drop direct assertions about `stdin/stdout/stderr` if not passed through; alternatively, ensure `_save_frame_with_ffmpeg` passes these through to `run_checked` so assertions remain valid.
     - test_save_frame_with_ffmpeg_disables_timeout_when_zero (~1763): same monkeypatch target; assert `timeout` is None/absent.
     - test_save_frame_with_ffmpeg_inserts_full_chroma_filters (~1806) and test_ffmpeg_expands_limited_range_when_exporting_full (~1861): monkeypatch `src.frame_compare.subproc.run_checked` to capture `cmd` only.
     - test_save_frame_with_ffmpeg_raises_on_timeout (~1901): monkeypatch `src.frame_compare.subproc.run_checked` to raise `subprocess.TimeoutExpired` and assert `ScreenshotWriterError` message contains "timed out".
   - `tests/test_vspreview.py` remains valid (still injects a `ProcessRunner` that returns a `CompletedProcess`). If needed, update type hints to accept our wrapper signature (it matches `subprocess.run`).
   - Audio‑alignment tests do not assert subprocess semantics; no changes expected.

6) Import‑linter layering
   - Append `src.frame_compare.subproc` to the third layer in `importlinter.ini` under the `Runner→Core→Modules layering` contract to treat it as a consumable module. Confirm contracts remain 0 broken.

Acceptance criteria & verification commands
- Functional parity: screenshot ffmpeg writer still honors timeout zero/positive; VSPreview still launches and reports exit code; audio‑alignment still probes streams/fps and extracts audio with the same error messages.
- Security: no `shell=True` anywhere under `src/` library code.
- Commands:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` → all tests pass (with test updates above).
  - `.venv/bin/ruff check` → no issues.
  - `.venv/bin/pyright --warnings` → 0 errors/warnings.
  - `uv run --no-sync lint-imports --config importlinter.ini` → 0 broken contracts; confirms `subproc` added to layer.

Risks & mitigations
- Test coupling to `subprocess.run` kwargs in screenshot tests: route these kwargs through `run_checked` so tests can continue asserting on `timeout`/stdio, or update tests to assert on command assembly and timeout only (less brittle). Prefer passing through kwargs to minimize churn.
- Platform differences in env/stdio defaults: keep explicit `stdin=DEVNULL` and `text=True/False` as before to avoid hanging on tools that read stdin.
- Error mapping drift: keep exception messages exactly as today; reuse decoded stderr in `ScreenshotWriterError`.

Conventional Commit subject
- `refactor(subproc): centralize subprocess calls and harden FFmpeg/VSPreview/ffprobe usage`

**2025-11-12 update:** Introduced `src/frame_compare/subproc.py::run_checked` (argv-only, `shell=False`, safe stdio defaults, optional `check`) and refactored `src/screenshot.py`, `src/frame_compare/vspreview.py`, and `src/audio_alignment.py` to route FFmpeg/FFprobe/VSPreview invocations through the helper so timeout handling and error messages stayed identical while banning `shell=True`. `tests/test_screenshot.py` now monkeypatches `src.frame_compare.subproc.run_checked` in the timeout/filter-chain cases, and `importlinter.ini` lists `src.frame_compare.subproc` in the Runner→Core→Modules layer to keep contracts green. Verification commands (`git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`, `UV_CACHE_DIR=.uv_cache uv run --no-sync lint-imports --config importlinter.ini`) ran clean; see the 2025‑11‑12 Phase 11.3 entry in `docs/DECISIONS.md` for logs.

**2025-11-12 update:** Replaced the remaining `print()`/`rich.print()` calls in library modules with loggers or reporter console output so CLI formatting stays centralized. `config_writer`, `core`, `runner`, `selection`, `tmdb_workflow`, and `screenshot` now emit via `logger`/reporter (with `selection.log_selection_windows` accepting an optional reporter), while VSPreview script prints remain untouched. Verification (`git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`, `UV_CACHE_DIR=.uv_cache uv run --no-sync lint-imports --config importlinter.ini`) is captured in the 2025‑11‑12 Phase 11.4 DEC entry.

### Sub‑phase 11.4 — Logging Normalization

Source of truth for the coding agent: this section in `docs/refactor/mod_refactor.md` (Sub‑phase 11.4). Follow these steps rather than relying solely on the prompt.

Goal
- Remove all direct `print()`/`rich.print()` calls from library modules and standardize on `logging` (module‑scoped `logger = logging.getLogger(__name__)`) or on the existing reporter interface where applicable. Preserve current user‑visible output and formatting at the CLI layer (Rich/console via `CliOutputManager`), and do not alter VSPreview script generation prints.

Scope & constraints
- Library modules to normalize (anchors below):
  - `src/frame_compare/config_writer.py`: `_present_diff` prints.
  - `src/frame_compare/runner.py`: exception trace and slow.pics upload prints.
  - `src/frame_compare/core.py`: analyze‑file selection note.
  - `src/frame_compare/selection.py`: imported `rich.print` and several prints; prefer reporter when available, else `logger`.
  - `src/screenshot.py`: overlay debug prints gated by `FRAME_COMPARE_LOG_OVERLAY_RANGE`.
  - `src/frame_compare/tmdb_workflow.py`: interactive guidance/validation prints; prefer `click.echo` or reporter.
- Exclusions (do not change):
  - VSPreview generated script content inside `src/frame_compare/vspreview.py` (the embedded `safe_print` function and `print()` lines within the persisted script). These are intentionally emitted to the user’s console and are covered by `tests/test_console_safety.py`.
  - Any `reporter.console.print(...)` calls in CLI presentation modules (keep as is).
- No behavior or message text changes visible to end users. For prints converted to logging, choose levels that map current intent (INFO for guidance, WARNING for warnings, DEBUG for developer diagnostics).
- Maintain Pyright/Ruff cleanliness and import‑linter contracts.

Detailed step list (per‑file; anchors/search)
1) `src/frame_compare/config_writer.py`
   - Anchors: ~211–227 (`_present_diff` uses `print(line)` and `print("No differences from the template.")`).
   - Actions:
     - Add (if missing) `logger = logging.getLogger(__name__)` at module top.
     - Replace looped `print(line)` with `logger.info(line)` (or route through a passed reporter if available — no reporter exists here today, so INFO logging is acceptable).
     - Replace the “No differences …” print with `logger.info` using the same text.

2) `src/frame_compare/runner.py`
   - Anchors: ~1255–1256 (prints frame selection trace), ~1722 (prints slow.pics upload note).
   - Actions:
     - Replace the two `print(...)` calls in the exception block with either `reporter.console.print(...)` (preferred, to preserve Rich markup) or `logger.error(...)` followed by including the rich_message already passed to `CLIAppError`. Keep the traceback visible to users in the same circumstances as today (leverage `reporter.console.print(tb)` in the exception path).
     - Replace the slow.pics “Preparing …” `print(...)` with `reporter.console.print("[cyan]Preparing slow.pics upload...[/cyan]")` to keep formatting centralized under the reporter.

3) `src/frame_compare/core.py`
   - Anchor: ~265 (prints "Determining which file to analyze…").
   - Actions:
     - Replace `print(...)` with `logger.info(...)` using the same message text. If a `reporter` is available in the calling context, consider moving this user‑facing guidance up to the CLI/reporting layer in a later phase; for 11.4, logging is sufficient.

4) `src/frame_compare/selection.py`
   - Anchors: `from rich import print` at line ~8; prints at ~57 (indexing note fallback), ~171–177 (per‑clip window lines), ~187, ~193–195 (common window + collapsed note).
   - Actions:
     - Remove `from rich import print` and add `logger = logging.getLogger(__name__)`.
     - For indexing note in `init_clips`, keep the existing reporter path; change the fallback `print(...)` to `logger.info("[CACHE] Indexing %s…", filename)`.
     - For `log_selection_windows`, introduce an optional `reporter: CliOutputManagerProtocol | None = None` parameter (backward‑compatible default) and:
       - If reporter is provided, use `reporter.console.print(...)` for each user‑visible line (preserving existing Rich markup).
       - If reporter is None, log with `logger.info(...)` using unstyled text (e.g., strip markup or keep plain strings to avoid bracket styling in logs).
     - Update imports/usages in callers (e.g., runner) to pass `reporter` if they call `log_selection_windows` (no current references were found; this change is safe and future‑proofs usage).

5) `src/screenshot.py`
   - Anchors: ~1848–1854, ~1877–1882, ~1932–1937 (overlay debug prints under `log_overlay`).
   - Actions:
     - Replace these `print(...)` calls with `logger.info(...)` retaining the same assembled message; keep the `flush=True` semantics by logging at INFO (no flush required for logging).

6) `src/frame_compare/tmdb_workflow.py`
   - Anchors: ~215–221, ~233, ~245–247, ~261 (interactive prompt guidance/error prints).
   - Actions:
     - Replace `print(...)` with `click.echo(...)` to keep CLI output under Click while avoiding raw `print`. Alternatively, if a reporter is available in upstream flows, route through `reporter.console.print(...)` (preserve Rich markup).

7) Repository‑wide safeguard
   - Add a short note in `docs/runner_refactor_checklist.md` clarifying: library modules should use `logging` or reporter calls; CLI shim/components may use `Rich`/`Click` output helpers; generated scripts are allowed to use `print()`.

Acceptance criteria & verification commands
- Behavior parity: CLI messages and formatting remain unchanged for end users; VSPreview script generation unaffected (tests under `tests/test_console_safety.py` still pass). Overlay debug output still available via logs when `FRAME_COMPARE_LOG_OVERLAY_RANGE` is set.
- Tests:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` — all suites pass unchanged (notably screenshot, vspreview, selection, tmdb, runner).
- Lint/type:
  - `.venv/bin/ruff check` — no issues.
  - `.venv/bin/pyright --warnings` — 0 errors/warnings.
- Import contracts:
  - `uv run --no-sync lint-imports --config importlinter.ini` — 0 broken contracts.

Risks & mitigations
- Reporter availability: when a reporter is not present in function signatures, prefer `logger` to avoid API churn. Where adding an optional reporter parameter provides better UX (e.g., `log_selection_windows`), keep a default `None` to maintain backward compatibility.
- Rich markup in logs: avoid emitting Rich markup brackets to plain logs when a reporter is not available; use descriptive plain text or keep the bracketed strings if existing logs already use them for quick grepping.
- VSPreview script prints: explicitly excluded from normalization to preserve console safety tests and user guidance.

Conventional Commit subject
- `refactor(logging): replace prints in libs with logger or reporter and preserve CLI formatting`

### Sub‑phase 11.5 — Packaging Cleanup + Legacy Removal (grouped)

Source of truth for the coding agent: this section in `docs/refactor/mod_refactor.md` (Sub‑phase 11.5). Follow these steps rather than relying solely on the prompt.

Goal
- Reduce top‑level module sprawl by relocating internal modules into the `src.frame_compare` package while preserving import compatibility via thin shims. Remove stale legacy code.

Scope & constraints
- Relocations (with compatibility shims left in `src/` and removed in 11.10):
  - `src/cli_layout.py` → `src/frame_compare/cli_layout.py` (tests import `src.cli_layout` today; keep shim in place).
  - `src/report.py` → `src/frame_compare/report.py` (tests import `src.report`).
  - `src/slowpics.py` → `src/frame_compare/slowpics.py` (internal consumers/tests import `src.slowpics`).
  - `src/config_template.py` → `src/frame_compare/config_template.py` (tests import `src.config_template`).
- Do not relocate in this sub‑phase:
  - `src/datatypes.py` (widely used core types), `src/utils.py` (used by `frame_compare.metadata`), `src/tmdb.py` (public contract; `tmdb_workflow` exists under `frame_compare` for newer flows), `src/screenshot.py`, `src/vs_core.py` (split scheduled in 11.6), `src/analysis.py` shim (will be removed in 11.10).
- Delete `Legacy/comp.py` after verifying no references.
- Keep public behavior/imports stable: imports like `from src.cli_layout ...` continue working via shims. No user‑visible message changes.
- Packaging and data files remain intact (no changes to `cli_layout.v1.json` path resolution or package data lists).

Detailed step list (file moves, shims, layering)
1) Move modules under `src/frame_compare/`
   - Create the target modules by moving code verbatim:
     - `src/cli_layout.py` → `src/frame_compare/cli_layout.py`
     - `src/report.py` → `src/frame_compare/report.py`
     - `src/slowpics.py` → `src/frame_compare/slowpics.py`
     - `src/config_template.py` → `src/frame_compare/config_template.py`
   - Do not change module content during the move (only imports that reference sibling modules might need path updates to absolute imports if any exist).

2) Add compatibility shims at old locations (remove in 11.10)
   - Replace the contents of each moved top‑level module with a shim that re‑exports everything:
     - Example shim body:
       - `from src.frame_compare.cli_layout import *  # type: ignore[F401,F403]\n` and, optionally, `__all__ = [name for name in dir() if not name.startswith('_')]`.
   - These shims keep all existing imports in code/tests working without churn and will be removed in Sub‑phase 11.10.

3) Update import‑linter layering
   - In `importlinter.ini`, append the new modules to the third layer under the `Runner→Core→Modules layering` contract:
     - `src.frame_compare.cli_layout`
     - `src.frame_compare.report`
     - `src.frame_compare.slowpics`
     - `src.frame_compare.config_template`
   - Ensure no back‑imports from these modules into `src.frame_compare.core` or the CLI shim.

4) Remove legacy file
   - Delete `Legacy/comp.py` after confirming no imports reference it (Serena search shows no references; MANIFEST already prunes `Legacy/`).

5) Packaging review (no functional changes required)
   - `pyproject.toml` currently packages `src`, `src.frame_compare`, and `data` with `include-package-data = true`. No changes needed for this move; both destinations are packaged.
   - Confirm `MANIFEST.in` already excludes `Legacy/` (it does) and includes `src/frame_compare/py.typed`.

Acceptance criteria & verification commands
- Behavior parity: user‑facing paths and CLI outputs unchanged; tests continue to import `src.*` via shims. No import cycles introduced.
- Commands:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` → all tests pass.
  - `.venv/bin/ruff check` → no issues.
  - `.venv/bin/pyright --warnings` → 0 errors/warnings (pay attention to shim star‑imports; add `# type: ignore` comments as noted).
  - `uv run --no-sync lint-imports --config importlinter.ini` → 0 broken contracts after adding the new modules to the layer list.

Risks & mitigations
- Import churn: shims eliminate the need to update all import sites; schedule shim removal for 11.10 and create a PR note advising internal code to migrate to `src.frame_compare.*` imports before then.
- Shadowing or name leakage via `*`: include `# type: ignore[F401,F403]` in shims to keep lint/type clean; optionally define `__all__` to be explicit.
- Hidden runtime path assumptions: moving modules should not affect data file discovery; tests assert `cli_layout.v1.json` discovery via `frame_compare.__file__` remains valid.

Conventional Commit subject
- `refactor(packaging): move internal modules under frame_compare and remove legacy file`

**2025-11-12 update:** Moved `src/{cli_layout,report,slowpics,config_template}.py` (plus their `.pyi` stubs) into `src/frame_compare/`, added compatibility shims at the old paths that now proxy the actual modules via `sys.modules` so monkeypatching works, updated `importlinter.ini` to include the new modules, and deleted `Legacy/comp.py`. Packaging logic now locates template/report assets from `Path(__file__).resolve().parents[1] / "data"` after the move. Verification commands (`git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`, `UV_CACHE_DIR=.uv_cache uv run --no-sync lint-imports --config importlinter.ini`) ran clean with the VSPreview extra installed locally; see the 2025‑11‑12 Phase 11.5 DEC entry for logs.

### Sub‑phase 11.6 — vs_core Split by Concerns

Source of truth for the coding agent: this section in `docs/refactor/mod_refactor.md` (Sub‑phase 11.6). Follow these steps rather than relying solely on the prompt.

Goal
- Decompose the monolithic `src/vs_core.py` into `src/frame_compare/vs/` grouped by responsibilities (env/config, source/open/trim, props/color metadata, tonemap/verification) with a compatibility shim left in `src/vs_core.py` for this phase.

Scope & constraints
- Create `src/frame_compare/vs/` with modules:
  - `env.py`: VapourSynth discovery/config and RAM limit.
  - `source.py`: opening/trim/FPS mapping, plugin discovery/errors, `init_clip`.
  - `props.py`: frame props access and color metadata extraction/mappings.
  - `color.py`: color defaults/overrides/heuristics, `normalise_color_metadata`.
  - `tonemap.py`: tonemap settings/processing, verification helpers, containers.
- Backward compatibility shim: `src/vs_core.py` re-exports all used public/private names. Remove in 11.10.
- Avoid behavioral/logging changes; copy functions verbatim. Maintain Pyright/Ruff cleanliness and import-linter contracts.

Detailed step list (anchors)
1) Scaffold subpackage: add `src/frame_compare/vs/{__init__,env,source,props,color,tonemap}.py`.
2) Move env/config: `_VS_MODULE_NAME`, `_ENV_VAR`, `_EXTRA_SEARCH_PATHS`, `_normalise_search_path`, `_add_search_paths`, `_load_env_paths_from_env`, `configure`, `_get_vapoursynth_module`, `set_ram_limit` (anchors ~21–28, ~229–360, ~326, ~1134).
3) Move source/open: `_SOURCE_*` constants (~17–22), plugin error classes (~41–76), `_set_source_preference` (~300), `_resolve_core` (~366), `_open_clip_with_sources` (search in file), `_slice_clip` (~1056), `_extend_with_blank` (~1070), `_apply_fps_map` (~1090), `init_clip` (~1104), `ClipInitError`.
4) Move props/color extraction: mappings/labels (~138–227), `_describe_code` (~229), `_coerce_prop` (~750), `_first_present` (~768), `_normalise_resolved_code` (~774), `_resolve_color_metadata` (~778), `_extract_frame_props` (~1186), `_snapshot_frame_props` (~1196), `_props_signal_hdr` (~736), `_infer_frame_height` (~812).
5) Move color normalization: `_resolve_configured_color_defaults` (~834), `_resolve_color_overrides` (search), `_guess_default_colourspace` (search), `_adjust_color_range_from_signal` (~1208), `normalise_color_metadata` (~1228).
6) Move tonemap/verification: dataclasses `TonemapInfo` (~92), `VerificationResult` (~121), `ColorDebugArtifacts` (~137), `TonemapSettings` (~150), `_parse_unexpected_kwarg` (~1872), `_call_tonemap_function` (~1898), `_apply_post_gamma_levels` (~1926), `_compute_verification` (~1969), `process_clip_for_screenshot` (~2010), `ClipProcessError`.
7) Add shim in `src/vs_core.py` that re-exports from `src.frame_compare.vs` (temporary until 11.10). Keep module docstring; add `# type: ignore[F401,F403]` for star exports.
8) Wire intra-vs imports: `color` imports from `props`; `tonemap` imports from `env`, `props`, `color`.
9) Update import‑linter: add `src.frame_compare.vs` (or the five modules) to the third layer under the modules contract.

Acceptance
- Parity: all VS paths unchanged; tests (e.g., `tests/test_vs_core.py`, screenshot/selection/vspreview) pass; pyright/ruff clean; contracts kept.

**2025-11-12 update:** Split `vs_core` into `src/frame_compare/vs/{env,source,props,color,tonemap}.py`, kept `src/vs_core.py` as a compatibility shim (plus `.pyi`) that proxies shared globals like `_vs_module`, `_compute_luma_bounds`, and `_tonemap_with_retries`, and updated `importlinter.ini` to include the new modules in the Runner→Core→Modules layer. After installing the `preview` extra locally, verification ran clean: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` (`289 passed, 1 skipped`), `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`, and `UV_CACHE_DIR=.uv_cache uv run --no-sync lint-imports --config importlinter.ini`—see the 2025‑11‑12 Phase 11.6 DEC entry for logs.

### Sub‑phase 11.7 — Retry/Backoff Consolidation

Goal: standardize HTTP retry/backoff and clients.

Scope
- Add `src/frame_compare/net.py` with helpers for httpx client/transport and retry rules.
- Refactor TMDB/slow.pics to use shared helpers where appropriate.

Acceptance
- Network tests pass; error messages consistent; pyright/ruff clean.

### Sub‑phase 11.8 — Config Docs Generation

Goal: keep `docs/config_reference.md` synchronized with `src/datatypes.py`.

Scope
- Add a script (e.g., `tools/gen_config_docs.py`) to introspect dataclasses and output a table of sections/fields/defaults/types.
- Run manually in this phase; wire into CI later if desired.

Acceptance
- Generated doc matches current defaults; reviewer sign‑off.

### Sub‑phase 11.9 — CI & Packaging Checks

Goal: ensure quality as modules split.

Scope
- Update import‑linter contracts for new packages (`render`, `analysis`, `vs`).
- Build a wheel in CI and confirm packaged files (py.typed, data assets) are correct.

Acceptance
- CI green; wheel contents validated.

### Sub‑phase 11.10 — Remove Transitional Shims (post‑Phase 11 cleanup)

Goal: delete temporary shims/bridges introduced while splitting modules to minimize redundancy.

Scope
- Remove `src/analysis.py` shim re‑exports; update any tests/imports.
- Remove any remaining bridges in `src/screenshot.py` after render helpers have been fully adopted.
- Prune or repoint curated exports that referenced transitional names.
- Remove `src/vs_core.py` shim aliases after consumers import from `src/frame_compare/vs/*`.

Acceptance
- `pytest -q`, `ruff`, `pyright --warnings` clean; no references to removed bridges remain.

## Post-phase Cleanup — Compatibility shim/bridge retirement

Goal: remove all temporary bridges and transitional shims left behind after Phases 9–11 (compat exports, wizard/VSPreview/TMDB shims, screenshot/analysis/vs_core shims, and any test-only bridges), so only the extracted modules and curated exports remain.

Scope
- Audit `_COMPAT_EXPORTS`, wizard/VSPreview/TMDB helpers, and any aliases marked “temporary” during Phases 9–11.
- Remove Phase 11 bridges: `src/analysis.py` shim, any `src/screenshot.py` bridge calls replaced by `render/*`, and `src/vs_core.py` delegates once `src/frame_compare/vs/*` is fully adopted.
- Confirm downstream automation/tests now rely on extracted modules or curated exports.
Deliverables
- Deletions of obsolete compatibility surfaces plus documentation updates (README/CHANGELOG, trackers, DEC).
- Verification quartet demonstrating no remaining references to the removed shims.

Acceptance
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings` all pass after the cleanup.
- Import‑linter contracts remain kept for new packages (`render`, `analysis`, `vs`).
- Trackers and DEC log explicitly note the removed names and replacement guidance.
  
### Orchestrator Handoff Protocol (applies to Phases 9–11)

- Reviewer orchestrator prepares: scope, entry points, acceptance tests to watch, and risk notes per sub‑phase.
- Coding agent executes the sub‑phase within a single session, requests approvals as needed, and updates DECISIONS/tracker entries.
- Shims/deprecations: keep compatibility for at least one release; document exit criteria to remove shims later.

### Appendix — Function Moves (line anchors)

Planned moves from `src/frame_compare/core.py` with start lines for reviewer navigation:

- To `src/frame_compare/config_writer.py`
  - `_read_template_text` (src/frame_compare/core.py:157)
  - `_load_template_config` (src/frame_compare/core.py:164)
  - `_deep_merge` (src/frame_compare/core.py:171)
  - `_diff_config` (src/frame_compare/core.py:187)
  - `_format_toml_value` (src/frame_compare/core.py:203)
  - `_flatten_overrides` (src/frame_compare/core.py:224)
  - `_apply_overrides_to_template` (src/frame_compare/core.py:240)
  - `_render_config_text` (src/frame_compare/core.py:412)
  - `_write_config_file` (src/frame_compare/core.py:299)
  - `_present_diff` (src/frame_compare/core.py:324)

- To `src/frame_compare/presets.py`
  - `PRESETS_DIR` (src/frame_compare/core.py:150)
  - `_list_preset_paths` (src/frame_compare/core.py:343)
  - `_load_preset_data` (src/frame_compare/core.py:355)
  - `PRESET_DESCRIPTIONS` (src/frame_compare/core.py:374)

- To `src/frame_compare/doctor.py`
  - `DoctorCheck` (src/frame_compare/core.py:384)
  - `_collect_doctor_checks` (src/frame_compare/core.py:435)
  - `_emit_doctor_results` (src/frame_compare/core.py:600)

- To `src/frame_compare/metadata.py`
  - `_parse_audio_track_overrides` (src/frame_compare/core.py:634)
  - `_first_non_empty` (src/frame_compare/core.py:651)
  - `_parse_year_hint` (src/frame_compare/core.py:660)

- To `src/frame_compare/layout_utils.py` (or new `runtime_utils.py`)
  - `_format_seconds` (src/frame_compare/core.py:982)
  - `_fps_to_float` (src/frame_compare/core.py:1008)
  - `_fold_sequence` (src/frame_compare/core.py:1026)
  - `_evaluate_rule_condition` (src/frame_compare/core.py:1059)
  - `_build_legacy_summary_lines` (src/frame_compare/core.py:1088)
  - `_format_clock` (src/frame_compare/core.py:1224)

- To `src/frame_compare/alignment_runner.py` (or new `selection.py`)
  - `_init_clips` (src/frame_compare/core.py:1236)
  - `_resolve_selection_windows` (src/frame_compare/core.py:1299)
  - `_log_selection_windows` (src/frame_compare/core.py:1353)

- Moved to `src/frame_compare/tmdb_workflow.py` during Phase 10.1; Phase 10.2 removed the transitional `core` forwarders so only the workflow module exposes these names.
  - `TMDBLookupResult` (src/frame_compare/core.py:671)
  - `_should_retry_tmdb_error` (src/frame_compare/core.py:681)
  - `_resolve_tmdb_blocking` (src/frame_compare/core.py:698)
  - `resolve_tmdb_workflow` (src/frame_compare/core.py:764)
  - `_prompt_manual_tmdb` (src/frame_compare/core.py:830)
  - `_prompt_tmdb_confirmation` (src/frame_compare/core.py:853)
  - `_render_collection_name` (src/frame_compare/core.py:883)

## Session Checklist — 2025-11-12 (Phase 9.12)

- [x] Phase/Sub-phase: `9 / 9.12`
- [x] Modules/files touched: `README.md`, `docs/README_REFERENCE.md`, `docs/refactor/mod_refactor.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): README.md, docs/README_REFERENCE.md, docs/refactor/mod_refactor.md, docs/DECISIONS.md (CHANGELOG unchanged — docs only)
- [x] Tests added/updated: No
- [x] Risks noted: None (docs only)
- [x] Follow-ups for next session: None

## Session Checklist — 2025-11-12 (Phase 10.1)

- [x] Phase/Sub-phase: `10 / 10.1`
- [x] Modules/files touched: `src/frame_compare/tmdb_workflow.py`, `src/frame_compare/core.py`, `src/frame_compare/runner.py`, `frame_compare.py`, `tests/helpers/runner_env.py`, `tests/runner/test_cli_entry.py`, `tests/runner/test_slowpics_workflow.py`, `typings/frame_compare.pyi`, `docs/refactor/mod_refactor.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): docs/refactor/mod_refactor.md (phase tracker + session log) and docs/DECISIONS.md
- [x] Tests added/updated: Updated runner + slow.pics suites to patch `tmdb_workflow` and ensure TMDB prompts/resolution stubs hit the new module
- [x] Risks noted: Transitional core shims still exist until Phase 10.2; need follow-up to delete shim exports once callers migrate
- [x] Follow-ups for next session: Phase 10.2 cleanup (delete core shims, point tests directly at `tmdb_workflow`)

## Session Checklist — 2025-11-12 (Phase 10.2)

- [x] Phase/Sub-phase: `10 / 10.2`
- [x] Modules/files touched: `src/frame_compare/core.py`, `frame_compare.py`, `tests/helpers/runner_env.py`, `tests/runner/test_slowpics_workflow.py`, `tests/runner/test_cli_entry.py`, `typings/frame_compare.pyi`, `README.md`, `docs/README_REFERENCE.md`, `docs/config_audit.md`, `docs/runner_refactor_checklist.md`, `docs/refactor/mod_refactor.md`, `docs/DECISIONS.md`
- [x] Commands run: `git status -sb`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`, `.venv/bin/ruff check`, `.venv/bin/pyright --warnings`, `uv run --no-sync lint-imports --config importlinter.ini`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Yes — README/reference/config audit, tracker tables, and DECISIONS entries captured the shim removal + verification results (CHANGELOG unchanged; API surface is stable).
- [x] Tests added/updated: Runner slow.pics + CLI suites now invoke/patch `tmdb_workflow` directly; compat helper alias map trimmed accordingly.
- [x] Risks noted: Final compatibility audit (wizard/VSPreview shims + `_COMPAT_EXPORTS` sweep) remains for the Post-phase cleanup row.
- [x] Follow-ups for next session: Execute the broader compatibility cleanup and revisit import-linter ignores once the remaining shims are retired.

## Verification Commands Reference

Run these after each sub-phase (adjust paths if using `uv`):

```bash
git status -sb
pytest -q
.venv/bin/ruff check
npx pyright --warnings
```

If network blocks `pyright`, note ENOTFOUND in `docs/DECISIONS.md` (see prior entries).

---

## Documentation Touchpoints

- `docs/runner_refactor_checklist.md` – update status tables each time a phase/sub-phase lands.
- `docs/DECISIONS.md` – record verification commands + summary per PR.
- `CHANGELOG.md` – mention user-visible improvements (easier configuration, new modules) once a phase materially affects UX.
- `docs/config_audit.md` – link new modules when configuration behavior changes.

Use this list to avoid missing doc updates.

---

## Open Questions / Parking Lot

- [ ] Should `CliOutputManager` live in its own package once layout utilities move? (Impacts Pyright typing.)
- [ ] Evaluate opportunity to replace manual Rich layout JSON with dataclasses after modularization.
- [ ] Consider whether VSPreview module should support dependency injection for alternate preview tools.

Keep unresolved decisions here; reference them at the start of each session.

Notes:
- Keep PRs focused on a single sub-phase.
- When blocking issues appear (e.g., unexpected coupling), record in `refactor/mod_refactor.md` under a new “Open Questions” section for future sessions.

---
