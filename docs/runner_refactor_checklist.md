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
| 2. Architecture & Imports (final) | 🚧 | `runner.py` now imports analysis/screenshot/vs_core directly, but `_IMPL_ATTRS` still forwards `_build_cache_info`, `_prepare_preflight`, and other CLI helpers from `frame_compare.py:1954-2750`; audit complete 2025-11-09, extraction deferred to Phase 3. |
| 3. CLI Shim | ✅ | `frame_compare.run_cli` (`frame_compare.py:4415-4444`) builds a `RunRequest` and delegates to `runner.run`; `tests/test_frame_compare.py:52-118` guards the hand-off. |
| 5. Dead Code Sweep | ⛔ | `_build_cache_info`, `_build_plans`, `_prepare_preflight`, `_discover_media`, `_confirm_alignment_with_screenshots`, etc. still live in `frame_compare.py:1900-2740`; move to shared module/runner helpers during Phase 3. |
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

1. **CLI helper migration** — `_IMPL_ATTRS` still depends on `_build_cache_info`, `_build_plans`, `_prepare_preflight`, `_discover_media`, `_confirm_alignment_with_screenshots`, and related helpers under `frame_compare.py`. Relocate or wrap them before Phase 3 finalizes the runner contract.

---

## Phase 3 – Final Review & Docs (Future)

Phase 3 also splits into two sub-phases: final QA/doc polish and quality gates + handoff.

### Phase 3.1 – Final QA & Docs

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 1. Workspace prep | ⛔ | Capture `git status -sb`; confirm only expected files staged. |
| 2–6. Architecture / Shim / Type Safety / Dead Code / Behavior | ⛔ | Walk through each checklist item, recording verification notes. |
| 7. Documentation | ⛔ | Final README/DECISIONS review + add CHANGELOG entry summarizing runner work. |
| 8. Tests | ⛔ | Final `.venv/bin/pytest` run; note command + duration. |

**Exit criteria 3.1:** Checklist items 1–8 signed off with notes; CHANGELOG updated.

### Phase 3.2 – Quality Gates & Handoff

| Checklist Item | Status | Notes / Next Steps |
| --- | --- | --- |
| 9. Quality Gates | ⛔ | Final pyright/ruff/pytest runs (if not already captured), attach outputs. |
| 10. Residual Risk Log | ⛔ | Complete risk log + Phase 4/backlog pointers. |
| Final Summary & Phase 4 Preview | ⛔ | Draft final Codex summary and handoff plan for wizard refactors or other future objectives. |

**Exit criteria 3.2:** All ten checklist sections ✅, risk log finalized, Phase 4 objectives documented.

---

### Usage Notes
- Update this file at the end of each session: mark status, jot short notes, and mention pending verifications.  
- When referencing best practices (Click CLI, Pyright typing), cite the relevant doc links as reminders for reviewers.  
- Keep attachments (pyright/ruff/pytest outputs) in the final summary but note their status here (e.g., “Pyright ✅ on 2025‑11‑07”).  
- If scope changes, append an “Amendments” section with rationale so future sessions understand the deviations.
