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

- [ ] Document the new `runner.run` signature and how CLI inputs map to service requests.
- [ ] Decide where service instances are constructed (factory vs dependency container).
- [ ] List side effects to mock in tests (filesystem writes, Slowpics uploads, TMDB HTTP calls).

### B2. Implementation Notes (Coding Agent)

- [ ] Refactor `runner.run` to:  
  1. Build `RunRequest` from CLI/config data.  
  2. Invoke MetadataResolver → `MetadataResult`.  
  3. Invoke AlignmentWorkflow with resolver output.  
  4. Invoke ReportPublisher and SlowpicsPublisher with aggregated state.
- [ ] Remove direct TMDB/alignment/report logic from runner; ensure logging lines survive (maybe via `layout_data` or event hooks).
- [ ] Update CLI entrypoints/tests to accommodate new interfaces (dependency injection hooks, factories).
- [ ] Capture unit/integration tests covering the sequencing (fixtures mocking services).

### B3. Review Notes

- [ ] Confirm runner now orchestrates without side effects (calls interfaces only).
- [ ] Verify dependency injection allows stubbing/mocking in tests (inspect new tests).
- [ ] Ensure warnings, prompts, layout data, and JSON tail remain identical (compare snapshots/tests).

---

## Track C – Publishing & Side-Effect Isolation

### C1. Abstraction Plan (Planning)

- [ ] Enumerate filesystem/network outputs (report files, Slowpics API, cache writes).
- [ ] Design interface boundaries (`PublisherIO`, `SlowpicsClient`, `TMDBClient`, etc.).
- [ ] Define error-handling expectations and retry/backoff policies.

### C2. Implementation Notes (Coding Agent)

- [ ] Implement adapters and inject them into services (default implementations + test doubles).
- [ ] Add tests stubbing adapters to prove runner/services no longer touch disk/network directly.
- [ ] Update documentation/README if workflows require new configuration for adapters.

### C3. Review Notes

- [ ] Verify no lingering direct `Path` operations or HTTP calls in runner/services; everything goes through adapters.
- [ ] Ensure logging/metrics hooks remain intact.
- [ ] Confirm tests cover success/failure paths for adapters.

---

## Verification Checklist

- [ ] `.venv/bin/pyright --warnings`
- [ ] `.venv/bin/ruff check`
- [ ] `.venv/bin/pytest -q` (include new suites: `tests/services/test_metadata.py`, `tests/services/test_alignment.py`, `tests/services/test_publishers.py`, updated runner tests)
- [ ] Optional smoke: `uv run frame_compare --help`

Record command outputs (hash or summary) in Implementation Notes; reviewers re-run if missing or suspicious.

## Risk & Rollback

- Maintain a feature flag (e.g., `runner.enable_service_mode`) during rollout; default OFF initially for quick rollback.
- Keep legacy runner path available while services stabilize; document toggles so support can revert. 
- Provide instructions for clearing caches/temp directories if services change storage paths.
- Track TODOs/follow-ups with issue IDs; no naked `# TODO`.

## Open Questions / Parking Lot

- [ ] Should we introduce a `RunResult` DTO to replace direct JSON tail dict mutation?
- [ ] Where should shared interfaces (TMDB client, Slowpics client, Publisher IO) live—central module or per-service packages?
- [ ] How should integration tests mock TMDB/Slowpics? (Fixture vs dependency injection.)
- [ ] Are config schema updates needed to configure service adapters or feature flag?
