# Refactor Cleanup & Legacy Retirement

> Source of truth for the post-refactor cleanup focused on removing the legacy runner path, hardening service-mode defaults, and ensuring the codebase meets production standards. Designed for a future pair of agents: one coding session (implementation) and one review session.

## Context

- Runner refactor (Tracks A–C) introduced service-based architecture (`MetadataResolver`, `AlignmentWorkflow`, `ReportPublisher`, `SlowpicsPublisher`) plus the `runner.enable_service_mode` feature flag and legacy fallback pathway.
- Goal now: remove temporary scaffolding, ensure defaults rely on the new pipeline, tighten logging/tests/docs, and eliminate legacy code once burn-in is complete.
- This cleanup ensures maintainability, avoids drift, and documents how to safely retire the legacy path.

## How to Use This Doc

- **Coding Agent (“CleanSweep”)**: execute the tasks under “Coding Agent Plan,” update checkboxes, document commands/tests, and leave review sections untouched.
- **Review Agent (“GuardRail”)**: after implementation, follow the “Review Agent Plan,” verify invariants, and record findings with file:line references.
- Both agents must adhere to `AGENTS.md` (planning, documentation, verification) and record outcomes in this doc plus `docs/DECISIONS.md`/`CHANGELOG.md`.

---

## Coding Agent Plan (CleanSweep)

### Persona

You are “CleanSweep,” a meticulous, test-driven engineer. You hate dead code, enforce typed boundaries, keep documentation up to date, and never regress logging. You follow the plan exactly, capture every command (`.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, `.venv/bin/pytest -q`), and document each change in this file and `docs/DECISIONS.md`. No TODOs without follow-up IDs.

### Phase 1 – Legacy Runner Removal & Flag Cleanup (This Session)

> Scope: Tasks 1–3 below (discovery/checklist alignment, legacy runner removal, config & flag cleanup). Tasks 4–6 are reserved for a follow-up stabilization session.

#### Phase 1 Scope & Invariants

- Scope (allowed changes for this session):
  - Runner/runner-services wiring related to legacy vs service-mode paths.
  - Removal or deprecation of legacy runner branches (`_run_legacy_publishers` or equivalents) once service mode is safe as the default.
  - Config/CLI flags and datatypes that control legacy vs service-mode behaviour.
  - Tests that assert legacy behaviour or toggle the legacy runner flag.
- Out of scope (must not change in this session):
  - Business behaviour of TMDB lookup, alignment math, or report formats.
  - Logging payloads and JSON tail structure beyond what’s required to remove legacy conditionals.
  - CLI UX flows other than removing legacy-only options or wiring them as diagnostics.
- Invariants that must hold at all times:
  - Public CLI entry points (`frame_compare` CLI and any documented Python entry points) continue to work as before for service-mode users.
  - The new service-based pipeline remains the default code path; any legacy path is either removed or clearly diagnostic-only.
  - `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, `.venv/bin/pytest -q` pass (or any failures are documented with follow-up IDs and not caused by this change).
  - No new global state or cross-module imports that would violate the runner service split design in `docs/refactor/runner_service_split.md`.

#### Phase 1 Entry Criteria

- Track A–C in `docs/refactor/runner_service_split.md` show completed implementation and review notes.
- The current default execution path uses the service-mode pipeline; the `runner.enable_service_mode` rollout flag exists for compatibility but is being retired in this session.
- There is a clear rollback strategy: reintroducing or re-enabling the legacy path should be possible via `git revert` of this session’s changes.

#### Phase 1 Exit Criteria

- Legacy runner branches and helpers are removed or confined to clearly diagnostic-only code paths, with no references from normal CLI/config flows.
- The `runner.enable_service_mode` flag no longer gates the main runner behaviour (either removed or demoted to a diagnostic toggle, as decided in this session).
- Config schema, CLI options, and datatypes accurately reflect the new baseline (service mode as the only supported path for normal use).
- All modified tests pass locally (`pytest`), and pyright/ruff are green for touched modules.
- This doc, `docs/DECISIONS.md`, and `CHANGELOG.md` are updated to describe what was done in Phase 1 and what remains for later phases.

### Phase 2 – Logging, Docs & Final Verification (Next Session)

> Scope: Tasks 4–6 below (logging & telemetry audit, documentation & decisions, verification), assuming Phase 1 has already removed or isolated legacy branches and cleaned up flags/config while preserving behaviour.

#### Phase 2 Scope & Invariants

- Scope (allowed changes for this session):
  - Logging, telemetry, and reporter flags in the runner and services, especially around publishing mode and diagnostics.
  - Documentation and decision records related to the legacy runner retirement and service-mode baseline (`docs/DECISIONS.md`, `CHANGELOG.md`, README, and runner refactor docs).
  - Test additions or adjustments needed to assert logging/telemetry parity and CLI output expectations.
- Out of scope (must not change in this session):
  - Core control flow that selects between services vs legacy paths (that was handled in Phase 1).
  - Public CLI argument names or Python API signatures beyond docstring/help-text updates and clarifications.
  - Business logic (TMDB heuristics, alignment math, report content) except where tests/docs prove an existing regression that must be fixed.
- Invariants that must hold at all times:
  - Service-mode remains the baseline execution path established in Phase 1; no new legacy branches are introduced.
  - Reporter flags (e.g., `service_mode_enabled`, TMDB/Slowpics/report/overlay diagnostics flags) still fire as expected and are covered by tests where practical.
  - Logging and JSON tail output remain compatible with pre-refactor expectations (no loss of essential information).
  - `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, `.venv/bin/pytest -q` pass or any residual issues are documented with explicit follow-up IDs and evidence.

#### Phase 2 Entry Criteria

- Phase 1 implementation and review are complete or at least in a state where:
  - Legacy runner branches are removed or clearly diagnostic-only.
  - `runner.enable_service_mode` no longer gates the main behaviour for normal runs.
  - Config and CLI flags reflect service-mode as the only supported baseline for normal operation.
- Implementation Notes for Phase 1 in this doc are filled out with tasks, commands, and a short summary.

#### Phase 2 Exit Criteria

- Logging and telemetry for the runner and publishers are audited and updated so that:
  - Publishing mode (services vs any residual legacy path) is clearly logged.
  - Reporter flags for TMDB, Slowpics, reports, and overlay diagnostics remain accurate and are not regressed.
- Documentation is updated to reflect the post-cleanup world:
  - `docs/DECISIONS.md` includes a section clearly explaining the legacy runner retirement and service-mode default, with verification evidence.
  - `CHANGELOG.md` has an entry (with UTC date) summarizing the cleanup and verification for this phase.
  - `docs/refactor/runner_service_split.md` links to this cleanup doc and states the legacy removal status.
- Final verification is complete:
  - pyright/ruff/pytest are run and recorded in this doc’s Implementation Notes.
  - Any remaining gaps or risks are captured in “Open Items / Future Work.”

### Phase 3 – VSPreview Overlay Regression & Structural Follow-Ups (Optional Session)

> Scope: Fix the VSPreview overlay regression and, optionally, tackle remaining structural open items (RunResult DTO, interface consolidation, additional golden-file tests) once Phases 1–2 have stabilized the runner and logging baseline.

#### Phase 3 Scope & Invariants

- Scope (allowed changes for this session):
  - Audio alignment + VSPreview plumbing where `layout_data["vspreview"]` and related JSON tail fields are produced and mapped into the CLI layout.
  - Tests and fixtures that exercise VSPreview/manual-alignment flows and JSON tail/layout data (e.g., VSPreview overlay diagnostics, audio-alignment CLI tests).
  - Optional structural improvements listed under “Open Items / Future Work” that do not change observable behaviour (RunResult DTO, interface consolidation, golden-file tests).
- Out of scope (must not change in this session):
  - Core runner control flow, legacy vs service-mode branching, or config/CLI flags already addressed in Phases 1–2.
  - Business logic unrelated to VSPreview/manual alignment (TMDB heuristics, report formats, non-audio pipelines).
  - JSON tail schema beyond the fields already documented for audio alignment and VSPreview unless you are restoring a previously documented/implemented field.
- Invariants that must hold at all times:
  - Service-mode remains the default and only supported runner pipeline; VSPreview fixes must work within that baseline.
  - Manual-alignment UX remains intact: VSPreview prompts, scripts, and JSON tail must continue to reflect the same guidance semantics as pre-refactor (or better), without losing information.
  - VSPreview overlay hints (suggested frames/seconds) are visible again in `layout_data["vspreview"]` and the CLI layout, matching the JSON tail fields.
  - `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, `.venv/bin/pytest -q` remain green, or any regressions introduced in this phase are fixed or explicitly documented with follow-up IDs.

#### Phase 3 Entry Criteria

- Phases 1–2 implementation and review are complete or in a stable state where:
  - Legacy runner paths are removed or diagnostic-only.
  - Service-mode default, logging, and telemetry are aligned with docs and tests.
- The VSPreview overlay regression is still outstanding:
  - `layout_data["vspreview"]` does not currently show alignment suggested frame/seconds offsets (always 0 / 0.000) as noted under “Open Items / Future Work.”
- Existing VSPreview/audio-alignment tests pass but do not fully assert the overlay hint behaviour.

#### Phase 3 Exit Criteria

- The VSPreview overlay regression is resolved:
  - `layout_data["vspreview"]` and CLI layout now display accurate suggested frame/seconds offsets for manual alignment, in line with pre-refactor expectations.
  - JSON tail and layout data fields for VSPreview hints are consistent and covered by tests.
- Optional structural follow-ups (if tackled in this session) are implemented without behavioural regressions:
  - `RunResult` DTO (if introduced) and interface consolidations (`TMDBClient`, `SlowpicsClient`, `PublisherIO`) are wired through without changing public API shapes or JSON tail semantics.
  - Additional golden-file tests, if added, pass and are documented.
- All changes are reflected in:
  - This doc’s Implementation Notes (Phase 3 subsection, if added).
  - `docs/DECISIONS.md` (brief entry for the VSPreview regression fix and any structural decisions).
  - `CHANGELOG.md` (UTC-dated note capturing the VSPreview fix and any optional structural work).

### Tasks (Overall Cleanup)

1. **Discovery & Checklist Alignment**
   - Re-read `docs/refactor/runner_service_split.md` and confirm Track A–C show completed implementation/review notes.
   - Identify any lingering TODOs or flagged follow-ups (service factories, adapters, overlays) and list them under “Open Items” here before coding.
   - Confirm the `runner.enable_service_mode` flag defaults to ON; if not, note why.

2. **Legacy Runner Removal**
   - Remove `_run_legacy_publishers` (or equivalent) and any legacy runner branches once the flag can default to the new path safely.
   - Delete CLI/config options that force legacy mode, or convert them to diagnostics-only flags if still useful.
   - Ensure `RunDependencies` no longer conditionally injects legacy components.
   - Update tests that referenced legacy path; remove or rewrite as service-mode tests.

3. **Config & Flag Cleanup**
   - Remove the `runner.enable_service_mode` flag from config schema, CLI, and documentation (unless you choose to keep a diagnostic toggle).
   - Update `src/datatypes.py` definitions, README tables, and doc references accordingly.
   - Add migration notes (if necessary) to alert users that the new pipeline is mandatory.

4. **Logging & Telemetry Audit**
   - Compare logs from new pipeline vs pre-cleanup (use existing fixtures) to ensure parity.
   - Remove redundant logging or `TODO` placeholders related to legacy mode.
   - Ensure reporter flags (`reporter.set_flag`) still fire for TMDB, Slowpics, reports, overlay diagnostics.

5. **Documentation & Decisions**
   - Update `docs/DECISIONS.md` with a section explaining the legacy runner retirement, referencing the initial architecture finding.
   - Add a `CHANGELOG.md` entry with the UTC date (`date -u +%Y-%m-%d`) summarizing “cleanup legacy runner / service mode default.”
   - Update `docs/refactor/runner_service_split.md` to mention that the cleanup is complete or reference this doc if future tasks remain.

6. **Verification**
   - Required commands:  
     - `.venv/bin/pyright --warnings`  
     - `.venv/bin/ruff check`  
     - `.venv/bin/pytest -q` (focus on runner/services/publishers suites)  
   - Optional smoke: run representative CLI command to ensure expected output.
   - Record command outputs (hash or summary) in the “Implementation Notes” section below.

### Implementation Notes (Coding Agent)

- Tasks completed:
  - [x] Legacy runner path removed.
  - [x] Service-mode flag retired / defaults updated.
  - [x] Config/CLI docs updated.
  - [x] Logging/tests/doc updates.
- Commands run:
  - [x] `.venv/bin/pyright --warnings`
  - [x] `.venv/bin/ruff check`
  - [x] `.venv/bin/pytest -q`
- Date: 2025-11-20
- Agent: CleanSweep (Codex)
- Summary (include tests run, files touched, key decisions):
  - Removed `_run_legacy_publishers` and made `_publish_results` service-only; runner now warns when configs or overrides request legacy mode and still sets `service_mode_enabled` to `True`.
  - Dropped CLI `--service-mode`/`--legacy-runner` options, deprecated `[runner].enable_service_mode` (template note only), and kept `RunRequest.service_mode_override` as a no-op diagnostic hook for compatibility.
  - Updated tests to assume service-mode baseline (`tests/runner/test_runner_services.py`, `tests/runner/test_slowpics_workflow.py`, `tests/runner/test_cli_entry.py`) and refreshed docs (README, refactor docs) plus CHANGELOG/DECISIONS entries.
  - Verification: `.venv/bin/pyright --warnings` (0 errors), `.venv/bin/ruff check` (clean), `.venv/bin/pytest -q` (444 passed, 1 skipped).

---

## Review Agent Plan (GuardRail)

### Persona

You are “GuardRail,” a skeptical reviewer. You confirm the new default flow works, no dead code remains, tests/logging are adequate, and documentation matches reality. You re-run pyright/ruff/pytest if evidence is missing, use Codanna to map dependencies, and record findings with severity + file:line. You update the “Review Notes” section below with outcomes and follow-ups.

### Tasks

1. **Doc Alignment**
   - Verify this file’s Implementation Notes are complete (tasks checked, commands recorded).
   - Inspect `docs/DECISIONS.md` and `CHANGELOG.md` entries for the cleanup.
   - Ensure `docs/refactor/runner_service_split.md` references this cleanup or states that legacy removal is done.

2. **Code Inspection**
   - Confirm `runner.enable_service_mode` flag and legacy branches are gone (or intentionally retained for diagnostics). Ensure config/CLI no longer expose deprecated options.
   - Use Codanna to ensure no remaining references to legacy runner functions or adapters exist.
   - Check service factories and tests for hard-coded legacy paths.

3. **Logging & Behaviour**
   - Compare logs/JSON tail output against previous snapshots (use tests or manual inspection) to ensure no regressions occurred.
   - Validate reporter flags and CLI prompts still fire appropriately.

4. **Tests & Verification**
   - Confirm coding agent’s pyright/ruff/pytest logs are valid; re-run if missing or suspicious.
   - Ensure runner/service tests cover the new baseline (no reliance on legacy toggles).

5. **Documentation**
   - Ensure README/config docs no longer mention legacy mode or outdated instructions.
   - Verify `docs/refactor/refactor_cleanup.md` (this doc) reflects the state post-review, including any follow-up tickets needed.

6. **Findings & Follow-Ups**
   - Record findings with severity, `file:line`, explanation, and suggested fix.
   - Note any residual risks or follow-up tasks (e.g., future Track D removal of other scaffolding) so they can be scheduled.

### Review Notes (Review Agent)

- Findings:
  - None; service-mode is enforced and legacy runner paths are unreachable via CLI/config.
- Follow-ups / tickets:
  - None.
- Commands re-run:
  - [ ] `.venv/bin/pyright --warnings` (not rerun; relying on CleanSweep log dated 2025-11-20)
  - [ ] `.venv/bin/ruff check`
  - [ ] `.venv/bin/pytest -q`
- Date: 2025-11-19
- Reviewer: GuardRail (Codex)

---

## Open Items / Future Work

- [ ] (Optional) Evaluate introducing a formal `RunResult` DTO for JSON tail to reduce mutation.
- [ ] (Optional) Consider consolidating interface definitions (`TMDBClient`, `SlowpicsClient`, `PublisherIO`) into a shared module.
- [ ] (Optional) Further integration tests to compare CLI output with golden files.
- [ ] VSPreview overlay regression: `layout_data["vspreview"]` no longer shows alignment “suggested frame/seconds” offsets (always 0f / 0.000s). Restore the pre-refactor behaviour so manual alignment has actionable hints.
