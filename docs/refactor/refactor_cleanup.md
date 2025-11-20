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
- The current default execution path uses the service-mode pipeline guarded by `runner.enable_service_mode` (or equivalent) and passes the existing test suite.
- There is a clear rollback strategy: reintroducing or re-enabling the legacy path should be possible via `git revert` of this session’s changes.

#### Phase 1 Exit Criteria

- Legacy runner branches and helpers are removed or confined to clearly diagnostic-only code paths, with no references from normal CLI/config flows.
- The `runner.enable_service_mode` flag no longer gates the main runner behaviour (either removed or demoted to a diagnostic toggle, as decided in this session).
- Config schema, CLI options, and datatypes accurately reflect the new baseline (service mode as the only supported path for normal use).
- All modified tests pass locally (`pytest`), and pyright/ruff are green for touched modules.
- This doc, `docs/DECISIONS.md`, and `CHANGELOG.md` are updated to describe what was done in Phase 1 and what remains for later phases.

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
  - [ ] Legacy runner path removed.
  - [ ] Service-mode flag retired / defaults updated.
  - [ ] Config/CLI docs updated.
  - [ ] Logging/tests/doc updates.
- Commands run:
  - [ ] `.venv/bin/pyright --warnings`
  - [ ] `.venv/bin/ruff check`
  - [ ] `.venv/bin/pytest -q`
- Date:
- Agent:
- Summary (include tests run, files touched, key decisions):

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
  -
- Follow-ups / tickets:
  -
- Commands re-run:
  - [ ] `.venv/bin/pyright --warnings`
  - [ ] `.venv/bin/ruff check`
  - [ ] `.venv/bin/pytest -q`
- Date:
- Reviewer:

---

## Open Items / Future Work

- [ ] (Optional) Evaluate introducing a formal `RunResult` DTO for JSON tail to reduce mutation.
- [ ] (Optional) Consider consolidating interface definitions (`TMDBClient`, `SlowpicsClient`, `PublisherIO`) into a shared module.
- [ ] (Optional) Further integration tests to compare CLI output with golden files.
- [ ] VSPreview overlay regression: `layout_data["vspreview"]` no longer shows alignment “suggested frame/seconds” offsets (always 0f / 0.000s). Restore the pre-refactor behaviour so manual alignment has actionable hints.
