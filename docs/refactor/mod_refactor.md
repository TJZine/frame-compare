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
| 5 | 5.1 VSPreview module |  | ☐ |  |
| 5 | 5.2 Layout utilities |  | ☐ |  |
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
- [x] Patched `tests/test_cli_wizard.py` to monitor `wizard.resolve_wizard_paths` during auto-wizard runs, ensuring the CLI exercises the new module boundary.
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
- [x] Modules touched: `src/frame_compare/wizard.py`, `src/frame_compare/core.py`, `frame_compare.py`, `tests/test_cli_wizard.py`, `tests/test_wizard.py`, `docs/DECISIONS.md`, `docs/refactor/mod_refactor.md`, `docs/runner_refactor_checklist.md`
- [x] Commands run: `git status -sb`, `pytest -q`, `.venv/bin/ruff check`, `npx pyright --warnings` (fails: ENOTFOUND registry.npmjs.org), `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): Updated `docs/DECISIONS.md`, `docs/refactor/mod_refactor.md`, `docs/runner_refactor_checklist.md` (CHANGELOG unchanged—internal refactor only).
- [x] Tests added/updated: Added `tests/test_wizard.py`, updated `tests/test_cli_wizard.py` to patch the new module boundary.
- [x] Risks noted: CLI still exposes compatibility shims but downstream scripts that patched `frame_compare._run_wizard_prompts` must now patch `src.frame_compare.wizard.run_wizard_prompts` for behavior to change.
- [x] Follow-ups for next session: Phase 2.2 should reroute loader/CLI helpers to import the wizard module directly and document the new boundary in README once the CLI shim is simplified.

## Session Checklist — 2025-11-10 (Phase 2.2)

- [x] Phase/Sub-phase: `2 / 2.2 Loader & CLI updates`
- [x] Modules touched: `frame_compare.py`, `src/frame_compare/wizard.py`, `src/frame_compare/core.py`, `tests/test_cli_wizard.py`
- [x] Commands run: `git status -sb`, `pytest -q`, `.venv/bin/ruff check`, `npx pyright --warnings` (fails: ENOTFOUND registry.npmjs.org), `.venv/bin/pyright --warnings`
- [x] Docs updated? (`runner_refactor_checklist`, `DECISIONS`, `CHANGELOG`?): `docs/DECISIONS.md`, `docs/refactor/mod_refactor.md`, and `docs/runner_refactor_checklist.md` updated (CHANGELOG untouched — internal refactor).
- [x] Tests added/updated: `tests/test_cli_wizard.py` now asserts the resolver hook is exercised during auto-wizard seeding.
- [x] Risks noted: Downstream tools that previously patched `frame_compare._resolve_wizard_paths` now hit the alias that forwards to `src.frame_compare.wizard`—monitor for any imports that reach into `src.frame_compare.core` directly.
- [x] Follow-ups for next session: Begin Phase 3 metadata extraction; audit README once the CLI shim is slimmer to mention the new wizard module boundary if user-facing behavior changes.

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
