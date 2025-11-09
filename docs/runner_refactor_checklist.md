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

---

## Phase 2 – CLI Slimming & Public Runner API (Current Phase 🚧)

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

### Phase 2.3 – Docs, Tooling & Risk Log

Goal: document the new API, run tooling, and start the residual risk log.

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 1. Workspace prep (pre-tooling) | ✅ | 2025-11-08 — verified clean tree via `git status -sb` before lint/test runs. |
| 4. Type Safety | ✅ | `npx pyright --warnings` ran successfully on 2025-11-09 (0 errors, 0 warnings, 0 information). |
| 7. Documentation | ✅ | README now includes a “Programmatic Usage” section, `docs/DECISIONS.md` logs the Phase 2.3 work, and `CHANGELOG.md` highlights the runner API docs plus tooling results. |
| 8. Tests | ✅ | `.venv/bin/pytest` (246 passed in 2.42s on 2025-11-08) captured as the verification baseline. |
| 9. Quality Gates | ✅ | `.venv/bin/ruff check` completed with “All checks passed!”; pytest output recorded alongside. |
| 10. Residual Risk Log | ✅ | See the section below for deferred tasks (CLI helper migration). |

**Exit criteria 2.3:** Docs updated, tooling outputs captured, residual risk section initialized.

### Residual Risk Log (Phase 2.3)

1. **CLI helper migration (Phase 4 kickoff)** — `_IMPL_ATTRS` still depends on `_build_cache_info`, `_build_plans`, `_prepare_preflight`, `_discover_media`, `_confirm_alignment_with_screenshots`, and related helpers under `frame_compare.py`. Relocate or wrap them during Phase 4 to finish slimming the CLI and lock the public runner API. *(Completed by Phase 4.1: helper logic now lives in `src/frame_compare/core.py` and runner imports it directly.)*

---

## Phase 3 – Final Review & Docs (Future)

Phase 3 also splits into two sub-phases: final QA/doc polish and quality gates + handoff.

### Phase 3.1 – Final QA & Docs

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 1. Workspace prep | ✅ | 2025-11-09 — `git status -sb` shows `## Develop...origin/Develop` plus the expected runner/doc edits only. |
| 2–6. Architecture / Shim / Type Safety / Dead Code / Behavior | 🚧 | Shim + behavior verified: `frame_compare.run_cli` (`frame_compare.py:4415-4444`) delegates cleanly and `tests/test_frame_compare.py:52-138` guard the boundary; type safety confirmed via `npx pyright --warnings` (2025-11-09, zero findings). Architecture/dead-code still pending because `_IMPL_ATTRS` in `src/frame_compare/runner.py:98-168` imports `_build_cache_info`/`_prepare_preflight`/`_discover_media` from `frame_compare.py:1954-2740`. *(Resolved by Phase 4.1, see table below.)* |
| 7. Documentation | ✅ | README programmatic usage (`README.md:169-192`) and `docs/DECISIONS.md` now capture the Phase 3.1 review; this checklist updated with the latest audit results. |
| 8. Tests | ✅ | `.venv/bin/pytest` (2025-11-09) → 246 passed in 2.42 s; recorded as the Phase 3.1 verification run. |

**Exit criteria 3.1:** Checklist items 1–8 signed off with notes; CHANGELOG updated.

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
