# Runner Service Split

> Source of truth for the multi-session effort to decompose `src/frame_compare/runner.py` (lines 337‑2460) into focused services so each workflow can be tested, mocked, and extended without touching a monolithic orchestrator.

## How to Use This Doc

- **Planning Agent (session 0)**  
  - Keep scope, success criteria, and blocked items accurate before implementation starts.  
  - Capture open questions or docs needed for Coding/Review agents.  
  - Update the “Open Questions” list as new discoveries surface.

- **Coding Agent (implementation session)**  
  - Work through the track checklists in order; update checkboxes as tasks complete.  
  - Fill every “Implementation Notes” section with diffs, commands, evidence (pyright/ruff/pytest).  
  - Persist key decisions to `docs/DECISIONS.md` and append `CHANGELOG.md` entries (UTC stamp from `date -u +%Y-%m-%d`).  
  - Keep logging consistent and record verification commands + outcomes.

- **Code Review Agent (review session)**  
  - Record findings with file:line anchors under “Review Notes”.  
  - Verify global invariants, regression tests, and logging coverage.  
  - Re-run pyright/ruff/pytest if the coding agent didn’t capture outputs; document discrepancies.

## Overview

- **Goal:** Replace the monolithic runner orchestration with typed services:
  1. `MetadataResolver` (config resolution, filesystem probes, TMDB lookup).
  2. `AlignmentWorkflow` (audio alignment, selection window prep, manual confirmation).
  3. `ReportPublisher` (JSON tail, report files, console output).
  4. `SlowpicsPublisher` (auto-upload, prompts).

- **Outcomes:**  
  - `runner.run` orchestrates typed request/response objects; no direct filesystem or network calls.  
  - Each service lives in its own module with unit tests and dependency injection for side effects.  
  - Side-effectful code (disk, network, CLI I/O) sits behind interfaces so integration tests can stub/memoize.

- **Non-goals:** changing business behaviour (TMDB heuristics, alignment math, report formats) beyond necessary layering adjustments.

## Global Invariants (Target State)

- [ ] `runner.run` only sequences services; it never mutates global state directly.
- [ ] Every service exposes typed `Request`/`Response` dataclasses (no `Any` leaks).
- [ ] Side effects (filesystem, network) flow through injectable adapters.
- [ ] `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, `.venv/bin/pytest -q` are clean.
- [ ] CLI workflows (TMDB prompts, unattended mode, alignment confirmation, Slowpics uploads) behave identically pre/post refactor (tests prove this).
- [ ] Logging/reporting parity: no lost console output or JSON tail data.

---

## Track A – Service Boundaries & Requests

### A1. Inventory & Decomposition (Planning)

- [ ] Map runner sections to service ownership (config boot, TMDB, alignment, reporting).
- [ ] Identify data passed between services (`plans`, TMDB context, JSON tail, layout data).
- [ ] Define typed request/response objects per service (attributes + invariants).
- [ ] Enumerate external dependencies each service abstracts (filesystem, network, CLI output).

**Planning Notes:**  
- [x] MetadataResolver consumes planner utilities, TMDB client, filesystem/cache; outputs `PlanSet`, `TMDBContext`, `LayoutData`.
- [x] AlignmentWorkflow uses `plans`, runtime config, analyze path, audio overrides; outputs `AlignmentSummary`, `AlignmentDisplay`, updated `plans`.
- ReportPublisher/SlowpicsPublisher require `layout_data`, `json_tail`, `reporter`, plus new `PublisherIO` adapters for disk/network operations.

### A2. Implementation Notes (Coding Agent)

- [x] Create `src/frame_compare/services/metadata.py` (or similar) containing request/response dataclasses and `MetadataResolver`.
- [x] Extract TMDB lookup, clip planning, metadata logging from runner; ensure CLI prompts remain injectable (interface for `CliOutputManagerProtocol` interactions).
- [x] Add `src/frame_compare/services/alignment.py` housing `AlignmentWorkflow`; move audio alignment invocation + manual confirmation logic here.
- [ ] Introduce shared DTOs (`RunContext`, `ClipInventory`, etc.) to avoid mutating `plans` directly within runner.
- [x] Log decisions/tests executed (pyright/ruff/pytest) for these modules.

**Session module plan:**  
- `src/frame_compare/services/metadata.py` will define:
  - `MetadataResolveRequest` (fields: `cfg`, `root`, `files`, `reporter`, `layout_data`, `json_tail`, `collected_warnings`).  
  - `MetadataResolveResult` (fields: `plans`, `metadata`, `metadata_title`, `analyze_path`, `slowpics_title_inputs`, `slowpics_resolved_base`, `slowpics_tmdb_disclosure_line`, `slowpics_verbose_tmdb_tag`, `tmdb_notes`).  
  - Adapter protocols: `TMDBClientProtocol`, `FilesystemProbeProtocol`, `CliPromptProtocol` for injecting TMDB workflow + probe helpers.
- `src/frame_compare/services/alignment.py` will define:
  - `AlignmentRequest` (fields: `plans`, `cfg`, `root`, `analyze_path`, `audio_track_overrides`, `reporter`, `json_tail`, `vspreview_mode`, `collected_warnings`).  
  - `AlignmentResult` (fields: `plans`, `summary`, `display`).  
  - Injectable callables for `alignment_runner.apply_audio_alignment`, `alignment_runner.format_alignment_output`, and `core.confirm_alignment_with_screenshots`.
- `src/frame_compare/services/factory.py` will build default service instances so the runner can request typed services without importing concrete modules directly.

**Session implementation notes:**  
- Implemented metadata/alignment services plus factory wiring, moving TMDB lookup, planner, and audio alignment orchestration behind typed DTOs.  
- Added unit tests covering metadata happy-path/fallbacks (`tests/services/test_metadata.py`) and alignment workflow behaviors (`tests/services/test_alignment.py`).  
- Verification: `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, `.venv/bin/pytest -q`.

### A3. Review Notes (Code Review Agent)

- [x] Verify dataclasses have full annotations (no `Any`) and pass Pyright strictness. `MetadataResolveRequest`, `MetadataResolveResult`, `AlignmentRequest`, and `AlignmentResult` all carry explicit field types, and `.venv/bin/pyright --warnings` (2025‑11‑18) reported `0 errors, 0 warnings`.
- [x] Confirm services have no hidden dependency on runner globals (e.g., module-level state). Both services rely solely on injected protocols/factories; runner wiring now goes through `build_metadata_resolver()` / `build_alignment_workflow()`.
- [x] Ensure TMDB prompt logic still honours unattended mode (cite regression tests). `tests/services/test_metadata.py::test_metadata_resolver_records_unattended_ambiguity` exercises the unattended branch and still surfaces the warning-only behaviour previously covered via runner tests.
- [x] List findings, open questions, and follow-up tasks.
  - Finding: `MetadataResolver` wraps `selection_utils.probe_clip_metadata` errors as `CLIAppError`, but the new unit suite never asserts this path—add a test that forces `ClipInitError` to guarantee the CLI still receives the sanitized message.
  - Follow-up: Track B still needs the shared DTO layer (`RunContext`, `ClipInventory`, etc.) to eliminate runner-side plan mutation.
  - Verification evidence captured this session:  
    - `.venv/bin/pyright --warnings` → `0 errors, 0 warnings` (2025‑11‑18)  
    - `.venv/bin/ruff check` → `All checks passed!` (2025‑11‑18)  
    - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` → `416 passed, 1 skipped` (2025‑11‑18)

---

## Track B – Runner Sequencing & Interfaces

### B1. Runner Wiring Plan (Planning)

- [x] Document the new `runner.run` signature and how CLI inputs map to service requests (now `run(request, *, dependencies)` with `RunDependencies` + `RunContext` recorded below).
- [x] Decide where service instances are constructed (CLI shims call `runner.default_run_dependencies()`; tests can inject doubles via the dataclass).
- [x] List side effects to mock in tests (new `tests/runner/test_runner_services.py` suite exercises metadata/alignment ordering and failure cases with runner stubs).

### B2. Implementation Notes (Coding Agent)

- [x] Refactor `runner.run` to:  
  1. Build `RunRequest` from CLI/config data.  
  2. Invoke MetadataResolver → `MetadataResult` via `RunDependencies`.  
  3. Invoke AlignmentWorkflow with resolver output inside the new `RunContext`.  
  4. Report/Slowpics publishers still run inline for Track C, but the aggregated context now carries all state for the upcoming split.
- [x] Remove direct TMDB/alignment logic from runner sections; logging + JSON tail hooks now reference `RunContext` so behaviour stays identical (publishing/reporting stays inline until Track C).
- [x] Update CLI entrypoints/tests to accommodate new interfaces (CLI shims call `runner.default_run_dependencies`, mocks accept the new `dependencies` kwarg).
- [x] Capture unit/integration tests covering the sequencing (see `tests/runner/test_runner_services.py` for order/failure/flag coverage plus refreshed CLI shim tests).

**Implementation summary (2025-11-18):**
- `src/frame_compare/runner.py` adds `RunDependencies`, `RunContext`, and DI plumbing; `frame_compare.run_cli` now passes `default_run_dependencies`.
- New test suite `tests/runner/test_runner_services.py` asserts metadata/alignment sequencing, error propagation, and reporter flag wiring; existing CLI/Dolby Vision stubs accept the DI kwarg.
- Documentation + logs updated below; Track C items remain for publishing abstraction.

**Verification (2025-11-18):**
- `.venv/bin/pyright --warnings` → 0 errors, 0 warnings.
- `.venv/bin/ruff check` → clean.
- `.venv/bin/pytest -q` → 421 passed, 1 skipped.

### B3. Review Notes

- [x] Confirm runner now orchestrates without side effects (calls interfaces only). Session 2 verified `runner.run` now builds its own `RunDependencies` after preflight so MetadataResolver/AlignmentWorkflow receive typed adapters without touching globals; the CLI shims no longer instantiate services ahead of runtime context.
- [x] Verify dependency injection allows stubbing/mocking in tests (inspect new tests). `tests/runner/test_runner_services.py` still injects doubles through `dependencies=` while CLI callers rely on the runner’s default bundle.
- [x] Ensure warnings, prompts, layout data, and JSON tail remain identical (compare snapshots/tests). New targeted test `tests/test_frame_compare.py::test_run_cli_delegates_to_runner` ensured shims keep forwarding the `RunRequest` unchanged while allowing the runner to manage DI internally; cache/logging parity covered by existing suites.

---

## Track C – Publishing & Side-Effect Isolation

### C1. Abstraction Plan (Planning)

- [x] Enumerate filesystem/network outputs (report files, Slowpics API, cache writes).
- [x] Design interface boundaries (`PublisherIO`, `SlowpicsClient`, `TMDBClient`, etc.).
- [x] Define error-handling expectations and retry/backoff policies.

**Planning Notes:**  
- Filesystem outputs: report JSON tail, screenshot exports, cached layout data, Slowpics shortcut files.  
- Network outputs: TMDB (already abstracted), Slowpics API uploads, potential webhook/publishing endpoints.  
- Interface plan: `PublisherIO` (wraps Path ops + JSON serialization), `SlowpicsClientProtocol` (submit uploads, poll status), optional `ReportWriterProtocol` if separation helps testing.  
- Error handling: consolidate retries at adapter layer (Slowpics: exponential backoff capped; filesystem: surface exceptions immediately).  
- Update (2025-11-19): service-mode publishers are now the only supported path; the legacy runner flag is retired and only surfaces warnings when requested.

### C2. Implementation Notes (Coding Agent)

- [x] Implement adapters and inject them into services (default implementations + test doubles).
- [x] Add tests stubbing adapters to prove runner/services no longer touch disk/network directly.
- [x] Update documentation/README if workflows require new configuration for adapters.
- [x] Document CLI overrides (`--service-mode` / `--legacy-runner`) and `service_mode_override` so QA can force legacy paths.

**Implementation Summary (2025-11-19):**

- Added `PublisherIO`, `ReportRendererProtocol`, and `SlowpicsClientProtocol` to `src/frame_compare/interfaces/publishers.py` plus concrete adapters inside `src/frame_compare/services/factory.py`.
- Created `ReportPublisher` and `SlowpicsPublisher` services (`src/frame_compare/services/publishers.py`) that encapsulate HTML report generation and slow.pics uploads without touching `Path` or HTTP helpers directly.
- Wired `RunDependencies`/`_publish_results` to inject the new services; legacy `_run_legacy_publishers` has since been removed and `service_mode_override` now only records warnings when callers request the retired path.
- Test coverage:
  - `tests/services/test_publishers.py` (service success/failure paths, stub adapters, unattended mode).
  - `tests/runner/test_runner_services.py` (dependency ordering, flag wiring, `_publish_results` service-vs-legacy selection).
  - Existing slow.pics workflow/CLI suites updated to default to legacy mode where direct patching is still required.
- Docs touched: README flag table, `docs/DECISIONS.md`, `CHANGELOG.md`, this file.

**Verification Evidence (Recorded 2025-11-19 in docs/DECISIONS.md):**

- `.venv/bin/pyright --warnings` (0 errors, 0 warnings)
- `.venv/bin/ruff check`
- `.venv/bin/pytest -q` (428 passed, 1 skipped)

Outstanding TODOs: None for Track C; any additional adapter reshuffling will be handled in Track D planning.

### C3. Review Notes

- [x] Verify no lingering direct `Path` operations or HTTP calls in runner/services; everything goes through adapters.
- [x] Ensure logging/metrics hooks remain intact.
- [x] Confirm tests cover success/failure paths for adapters.

**Review Outcome (2025-11-19):**

- Runner now calls slow.pics/HTML generation exclusively through the injected services; the legacy path is removed and legacy requests only emit warnings.
- Reporter warnings/logs continue to mirror the legacy flow; CLI prompts confirmed via `tests/runner/test_runner_services.py`.
- Service/runner tests cover service success, adapter failure surfacing, CLI flag overrides, and legacy fallback; no gaps remain.
- Track C accepted pending documentation polish (addressed in this update).

---

## Verification Checklist

- [x] `.venv/bin/pyright --warnings`
- [x] `.venv/bin/ruff check`
- [x] `.venv/bin/pytest -q` (include new suites: `tests/services/test_metadata.py`, `tests/services/test_alignment.py`, `tests/services/test_publishers.py`, updated runner tests)
- [ ] Optional smoke: `uv run frame_compare --help`

Record command outputs (hash or summary) in Implementation Notes; reviewers re-run if missing or suspicious.

## Risk & Rollback

- Service-mode flag retired after the Phase 1 cleanup; rollback would require reverting the cleanup commit rather than toggling config.
- Legacy runner path removed; only warnings remain when callers request it. 
- Provide instructions for clearing caches/temp directories if services change storage paths.
- Track TODOs/follow-ups with issue IDs; no naked `# TODO`.

## Open Questions / Parking Lot

- [ ] Should we introduce a `RunResult` DTO to replace direct JSON tail dict mutation?
- [ ] Where should shared interfaces (TMDB client, Slowpics client, Publisher IO) live—central module or per-service packages?
- [ ] Does `RunContext` remain in `runner.py` or move into a shared services module once the publishing layer is extracted?
- [ ] How should integration tests mock TMDB/Slowpics? (Fixture vs dependency injection.)
- [ ] Are config schema updates needed to configure service adapters or feature flag?
