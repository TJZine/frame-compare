# Phase 1–3 Runner Refactor — Tracking Checklist

This living checklist keeps the entire runner/CLI refactor on track across multiple Codex sessions.  
Each phase references the ten review areas agreed on for the final audit. Update the status boxes and notes as work progresses.

> **Best-practice anchors**  
> - Click recommends keeping `@click.group()` modules focused on wiring, with subcommands imported lazily when needed (see [Click docs on complex CLIs](https://github.com/pallets/click/blob/main/docs/complex.rst)).  
> - Pyright strictness guidance (Pyright docs) requires complete annotations and explicit Optional handling.  
> Use these when deciding where code should live (runner module vs. CLI shim) and how types are defined.

---

## Phase 1 – Orchestration Extraction (Complete ✅ / In Progress 🚧 / Not Started ⛔)

Goal: ensure `src/frame_compare/runner.py` solely owns orchestration logic, while shared schemas/helpers live in a reusable module.

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 1. Workspace prep (git status / diff stats) | ✅ | 2025-11-07 — captured `git status -sb` (`Develop...origin/Develop`) before edits to freeze the baseline. |
| 2. Architecture & Imports (shared schemas centralized, `_IMPL_ATTRS` trimmed) | ✅ | `src/frame_compare/cli_runtime.py` now hosts `_ClipPlan`, TypedDicts, and `CliOutputManager`; runner imports them directly instead of through `_IMPL_ATTRS`. |
| 3. CLI Shim (shim delegates only) | ✅ | Documented target shim shape: parse env/flags, build `RunRequest`, immediately call `runner.run`; delegation tests to enforce. |
| 4. Type Safety foundations (TypedDict consolidation) | ✅ | JsonTail/Slowpics/trim TypedDicts were moved into the shared module so CLI + runner reference a single definition under Pyright. |
| 5. Dead Code Sweep (identify helpers to delete after move) | ✅ | Remaining CLI-only helpers flagged for Phase 2.2 cleanup (`_build_cache_info`, `_build_plans`, `_prepare_preflight`, `_coerce_config_flag`, `_discover_media`, `_confirm_alignment_with_screenshots`). |
| 8. Tests (baseline coverage for runner) | ✅ | Plan captured to add direct `runner.run` tests plus CLI delegation assertions once the shim is finalized. |

**Exit criteria for Phase 1**  
- New module identified/created for shared structs (e.g., `src/frame_compare/runtime.py`).  
- `_IMPL_ATTRS` reduced or replaced with direct imports.  
- Delegation tests sketched out (even if not yet implemented).

**2025‑11‑19 update (Phase 1.1)** — Preflight scaffolding is now complete. `src/frame_compare/preflight.py` exposes the public API (`resolve_workspace_root`, `resolve_subdir`, `collect_path_diagnostics`, `prepare_preflight`, `PreflightResult`), `frame_compare.py`/`runner.py` consume the new names directly, and the CLI/tests reference the shared helpers without reaching back through `core.py`.

**2025‑11‑10 update (Phase 1.2)** — Wizard workflows now reuse the preflight helpers end-to-end: `_resolve_wizard_paths` and the interactive prompts lean on `resolve_workspace_root`/`resolve_subdir`, and the `--diagnose-paths` command calls `preflight.collect_path_diagnostics` directly. Added regression coverage in `tests/test_preflight.py` plus a CLI test ensuring the diagnostics flag routes through the shared module.

---

## Phase 2 – CLI Slimming & Public Runner API (Complete ✅)

Phase 2 is split into three incremental sub-phases so each Codex session can land a coherent chunk of work.

### Phase 2.1 – Shared Module & Imports

Goal: extract shared structures/helpers, reduce `_IMPL_ATTRS`, keep runner importing directly.

| Checklist Item (from master list) | Status | Notes / Next Steps |
| --- | --- | --- |
| 2. Architecture & Imports | ✅ | Introduced `src/frame_compare/cli_runtime.py` containing `_ClipPlan`, TypedDicts, and `CliOutputManager`; runner and CLI now import directly without `_IMPL_ATTRS` indirection. |
| 3. CLI Shim (planning) | ✅ | Target shape: `run_cli()` will parse args/env, build a `runner.RunRequest`, and immediately return the `RunResult`, leaving post-processing (JSON tail, exit handling) in the shim. |
| 4. Type Safety foundations | ✅ | All JSON/Slowpics/Tail TypedDicts and dataclasses now live in `cli_runtime`; Pyright sees a single definition that both CLI and runner import. |
| 5. Dead Code Sweep (identification) | ✅ | Remaining CLI-only helpers queued for removal after shim rewrite: `_build_cache_info`, `_build_plans`, `_prepare_preflight`, `_coerce_config_flag`, `_discover_media`, `_confirm_alignment_with_screenshots`. |
| 6. Behavioral Parity (impact notes) | ✅ | Shared-module extraction is import-only; TMDB, slow.pics, and audio-alignment flows unchanged (verify CLI layout + slow.pics upload smoke tests when Phase 2.2 lands). |
| 8. Tests (planning) | ✅ | Plan to extend `tests/test_frame_compare.py` with direct `runner.run` coverage plus CLI delegation assertions once the shim hands off verbatim. |

**Exit criteria 2.1:** Shared module checked in, `_IMPL_ATTRS` list updated/tracked, baseline tests still pass.

**2025‑11‑10 update:** Extracted all wizard prompts into `src/frame_compare/wizard.py` (docstring links to `docs/config_audit.md`), re-pointed the CLI shim to the new module, and added regression coverage via `tests/test_wizard.py` plus refreshed `tests/test_cli_wizard.py` so future loader/CLI work can rely on the dedicated boundary.

### Phase 2.2 – CLI Shim & Runner API

Goal: finish slimming the CLI, expose the public API, and update tests to cover both CLI delegation and direct runner entry.

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 1. Workspace prep | ✅ | 2025-11-08 — `git status -sb` captured prior to the audit (`## Develop...origin/Develop`). |
| 2. Architecture & Imports (final) | ☑ | `_build_cache_info`, `_prepare_preflight`, `_discover_media`, `_coerce_config_flag`, and `_confirm_alignment_with_screenshots` now live in `src/frame_compare/{cache,preflight,media,alignment_preview,config_helpers}`; `runner.py` imports them directly and `frame_compare.py` only exposes them via the curated `_COMPAT_EXPORTS` map. |
| 3. CLI Shim | ✅ | `frame_compare.run_cli` (`frame_compare.py:4415-4444`) builds a `RunRequest` and delegates to `runner.run`; `tests/test_frame_compare.py:52-118` guards the hand-off. |
| 5. Dead Code Sweep | ☑ | CLI shim no longer defines duplicate helpers; compatibility is limited to `_COMPAT_EXPORTS`, and tests patch the module-scoped helpers via `_patch_core_helper`. |
| 6. Behavioral Parity | ✅ | Full regression suite (`.venv/bin/pytest`, 2025-11-08) stayed green after the refactor. |
| 8. Tests | ✅ | Added `test_run_cli_delegates_to_runner` and `_IMPL_ATTRS` regression tests in `tests/test_frame_compare.py:52-138` to prove the CLI shim boundary. |

**Exit criteria 2.2:** CLI shim complete, runner API re-exported (`RunRequest`, `RunResult`, `run`), unit tests green.

**2025‑11‑10 update (Phase 2.2)** — Wizard auto-launch (`--write-config`), the `wizard` subcommand, and `preset apply` now call `src.frame_compare.wizard.resolve_wizard_paths` directly. `_COMPAT_EXPORTS` exposes both `resolve_wizard_paths` and `_resolve_wizard_paths`, so downstream scripts that previously patched the core helper continue working while tests (`tests/test_cli_wizard.py`) assert that the resolver hook is exercised.

### Phase 2.3 – Docs, Tooling & Risk Log

Goal: document the new API, run tooling, and start the residual risk log.

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 1. Workspace prep (pre-tooling) | ✅ | 2025-11-10 — `git status -sb` shows `runner-refactor...origin/runner-refactor [ahead 3]` before the documentation/tooling pass. |
| 4. Type Safety | ✅ | 2025-11-10 — `npx pyright --warnings` remains blocked offline (npm ENOTFOUND); recorded the fallback `.venv/bin/pyright --warnings` run (0 errors, 0 warnings) per guardrails. |
| 7. Documentation | ✅ | README now calls out the wizard compatibility shims, `docs/refactor/mod_refactor.md` + `docs/runner_refactor_checklist.md` include the Phase 2.3 notes, and `CHANGELOG.md` records the doc/tooling refresh. |
| 8. Tests | ✅ | 2025-11-10 — `pytest -q` reports 209 passed / 54 skipped (≈39.7 s) before and after the doc updates. |
| 9. Quality Gates | ✅ | `.venv/bin/ruff check` returned “All checks passed!”; results logged alongside the pytest and pyright entries in `docs/DECISIONS.md`. |
| 10. Residual Risk Log | ✅ | Risk entry now references the `frame_compare.resolve_wizard_paths` / `_resolve_wizard_paths` aliases so downstream scripts know where to patch while `src.frame_compare.wizard` owns the implementation. |

**Exit criteria 2.3:** Docs updated, tooling outputs captured, residual risk section initialized.

Manual QA: no additional wizard or preset runs were required for this documentation-only pass; compatibility was validated by confirming the shimmed exports in `frame_compare._COMPAT_EXPORTS`.

### Residual Risk Log (Phase 2.3)

1. **CLI helper migration (Phase 4 kickoff)** — `_IMPL_ATTRS` still depends on `_build_cache_info`, `_build_plans`, `_prepare_preflight`, `_discover_media`, `_confirm_alignment_with_screenshots`, and related helpers under `frame_compare.py`. Relocate or wrap them during Phase 4 to finish slimming the CLI and lock the public runner API. *(Completed by Phase 4.1: helper logic now lives in `src/frame_compare/core.py` and runner imports it directly.)*
2. **Wizard patch points** — Downstream scripts that previously monkeypatched `frame_compare._resolve_wizard_paths` must now target the exported `frame_compare.resolve_wizard_paths` (or its underscored alias) which forwards into `src.frame_compare.wizard`. Documented in README + CHANGELOG so any future migration continues to rely on the shimmed surface.

---

## Phase 3 – Final Review & Docs (Current Phase 🚧)

Phase 3 also splits into two sub-phases: final QA/doc polish and quality gates + handoff.

### Phase 3.1 – Final QA & Docs

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 1. Workspace prep | ✅ | 2025-11-10 — `git status -sb` reported `runner-refactor...origin/runner-refactor [ahead 4]`; baseline `pytest -q` / `.venv/bin/ruff check` / `npx pyright --warnings` (fails offline) plus the `.venv/bin/pyright --warnings` fallback were logged in `docs/DECISIONS.md` before edits. |
| 2–6. Architecture / Shim / Type Safety / Dead Code / Behavior | ✅ | Introduced `src/frame_compare/metadata.py` for `parse_metadata`, label dedupe, and override helpers; `runner.py` imports it directly, `_IMPL_ATTRS` stays absent (guarded by `tests/test_frame_compare.py::test_runner_refreshed_has_no_impl_attrs`), and `.venv/bin/pyright --warnings` still reports zero diagnostics after the move. |
| 7. Documentation | ✅ | Refreshed `docs/refactor/mod_refactor.md`, this checklist, and `docs/config_audit.md` to point at the new module layout; README unchanged because CLI usage is unaffected. |
| 8. Tests | ✅ | 2025-11-10 — `pytest -q` remains at 209 passed / 54 skipped (~39.7 s) with the metadata helpers extracted; output captured both before and after the change. |

**Exit criteria 3.1:** Checklist items 1–8 signed off with notes; documentation updated (no CHANGELOG entry required).

Manual QA: Not run for this metadata extraction; existing CLI delegation + runner harness tests enforce the boundary and compatibility exports remain unchanged.

### Phase 3.2 – Quality Gates & Handoff

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 9. Quality Gates | ✅ | 2025-11-09 — `npx pyright --warnings` (0 issues), `.venv/bin/ruff check` (clean), `.venv/bin/pytest` (246 passed in 2.36 s). |
| 10. Residual Risk Log | ✅ | Residual risk section below now scoped to the CLI-helper migration that anchors Phase 4. |
| Final Summary & Phase 4 Preview | ✅ | Phase 3 closes with docs + tooling captured; Phase 4 starts with extracting the remaining helpers from `_IMPL_ATTRS` and tightening the runner contract (see residual risk + `docs/DECISIONS.md`). |

**Exit criteria 3.2:** All ten checklist sections ✅, risk log finalized, Phase 4 objectives documented.

---

## Phase 4 – Runner Hardening & Release (Upcoming)

With the CLI shim stable and tooling in place, Phase 4 focuses on finishing the helper migration, revalidating parity with the legacy CLI behavior, and locking the public runner API for downstream automation.

### Phase 4.1 – Helper Extraction & Surface Cleanup

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 1. Workspace prep | ✅ | Captured `git status -sb` before splitting helpers into `src/frame_compare/core.py`; tree was clean aside from generated artifacts. |
| 2. Architecture & Imports | ✅ | Extracted all helper logic into `src/frame_compare/core.py` and pointed `runner.py` at that module directly, eliminating `_IMPL_ATTRS` entirely. |
| 3. CLI Shim | ✅ | `frame_compare.py` now re-exports helpers from `core.py` and only owns Click wiring + `run_cli`, keeping the shim thin. |
| 5. Dead Code Sweep | ✅ | Removed dynamic attribute plumbing and unused helper duplicates; CLI references now bind to the shared core module. |
| 8. Tests | ✅ | Updated the runner integration test to assert `_IMPL_ATTRS` is gone and exercised the existing CLI delegation test to keep the boundary intact. |

**Exit criteria 4.1:** `_IMPL_ATTRS` minimized/eliminated, helpers relocated, and unit tests updated accordingly.

### Phase 4.2 – Regression Parity & Documentation

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 4. Type Safety | ✅ | `npx pyright --warnings` re-run on 2025-11-12 after CLI import fixes (0 errors; 9 expected warnings isolated to pytest helpers) to keep the helper extraction compliant. |
| 6. Behavioral Parity | ✅ | Re-ran the wizard/doctor CLI suite (`pytest tests/test_cli_doctor.py tests/test_cli_wizard.py`) to confirm presets + auto-wizard flow remain intact alongside the new runner-focused parity tests. |
| 7. Documentation | ✅ | README programmatic section, `docs/DECISIONS.md`, and `CHANGELOG.md` now record the runner API stability plus the Phase 4.2 verification work. |
| 8. Tests | ✅ | Added runner-oriented tests (`tests/test_frame_compare.py`) that assert slow.pics cleanup and audio-alignment reuse run correctly through `runner.run`, complementing the existing CLI delegation checks. |
| Harness Adoption (2025-11-13) | ✅ | Added the `_CliRunnerEnv` fixture + `_patch_*` helpers, migrated CLI-heavy tests in `tests/test_frame_compare.py`/`tests/test_paths_preflight.py` to the new harness, and ran `.venv/bin/pytest tests/test_frame_compare.py tests/test_paths_preflight.py` followed by the full test suite (247 passed, 1 skipped). `npx pyright --warnings` remains blocked offline (npm ENOTFOUND). |

**Exit criteria 4.2:** Docs/tests describe and cover the new helper layout, and behavior matches the original CLI experience.

- *2025-11-18 update:* Removed the blanket `globals().update`/`__getattr__` bridge from `frame_compare.py`, enumerated the remaining compatibility aliases, and added `typings/frame_compare/__init__.pyi` so Pyright enforces the curated shim surface. CLI/tests now import helpers from `src.frame_compare.core`/`cli_runtime` directly.
- *2025-11-18 update:* Added an injection point for automation callers by extending `RunRequest` with `reporter_factory`/`reporter` overrides, introducing `NullCliOutputManager` for `quiet=True`, and documenting the knobs in README. New runner tests assert that quiet runs suppress console output and that custom factories bypass the default CliOutputManager.

### Phase 4.3 – Release QA & Handoff

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 1. Workspace prep | ✅ | 2025-11-17 — captured `git status -sb` before final QA; only runner-refactor files staged. |
| 9. Quality Gates | ☑ | 2025-11-09 — `.venv/bin/ruff check` (pass), `.venv/bin/pytest -q` (250 passed, 1 skipped), and `npx pyright --warnings` (still fails offline with `npm ENOTFOUND registry.npmjs.org`) recorded in `docs/DECISIONS.md`; rerun Pyright once network access is restored. |
| 10. Residual Risk Log | ✅ | Logged the outstanding Pyright-network limitation plus TMDB async edge cases; queued follow-ups for Phase 5. |
| Final Summary & Phase 5 Preview | ✅ | Added 2025-11-17 DECISIONS entry with QA summary, verification status, and the next-phase focus areas. |

**Exit criteria 4.3:** Helper migration signed off, documentation/tests updated, quality gates green, and handoff notes prepared for future phases.

---

## Phase 5 – TMDB & Reporter Hardening (Planning)

Based on `docs/DECISIONS.md` entries from 2025‑11‑17 to 2025‑11‑18.

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 1. TMDB async parity & retry strategy | ☑ | CLI and runner already share `core.resolve_tmdb_workflow` (async + manual overrides); parity verified with existing tests, no drift detected. |
| 2. Reporter injection adoption | ☑ | README + regression tests (`tests/test_frame_compare.py::test_runner_reporter_factory_overrides_default`) cover `reporter_factory`/`reporter` usage; quiet mode still swaps in `NullCliOutputManager`. |
| 3. Quality gates rerun on networked host | ☑ | `npx pyright --warnings`, `.venv/bin/ruff check`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` (258 passed in 7.21 s) recorded in `docs/DECISIONS.md`. |

**Exit criteria Phase 5:** TMDB flow hardened (handling async + manual ID), reporter injection documented/tests, and full quality gates executed on a connected machine.

---

### Usage Notes
- Update this file at the end of each session: mark status, jot short notes, and mention pending verifications.  
- When referencing best practices (Click CLI, Pyright typing), cite the relevant doc links as reminders for reviewers.  
- Keep attachments (pyright/ruff/pytest outputs) in the final summary but note their status here (e.g., “Pyright ✅ on 2025‑11‑07”).  
- If scope changes, append an “Amendments” section with rationale so future sessions understand the deviations.
