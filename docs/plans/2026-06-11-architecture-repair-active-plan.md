Status: Historical
Scope: Production architecture repair program across Frame Compare hotspots
Owner: Codex session

# Architecture Repair Program

This plan is activated from `docs/plans/2026-06-11-architecture-repair-goal-prompt.md`.
It is a high-risk architecture/hotspot workstream. Do not implement a package
until its scope has read-only adversarial review and adjudication.

## Authorities Read

- `AGENTS.md`
- `docs/ENGINEERING_RUNBOOK.md`
- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- `importlinter.ini`
- `pyproject.toml`
- Repo-local skills: `architecture-boundaries`, `execution-plan-authoring`,
  `verification-strategy`, `review-request`, `review-adjudication`,
  `closeout-verification`, `cli-contract-boundaries`,
  `persistence-boundaries`, `python-quality-boundaries`,
  `python-test-design`, `report-output-patterns`,
  `runtime-integration-boundaries`, `bounded-worker-execution`, and
  `parallel-sidecars`.

Initial discovery used `rg`, direct source reads, and read-only explorer
subagents. Codanna became available after the first plan draft; its index
reported 13,848 symbols across 336 files and confirmed significant impact for
`ExecutionState` and `RunArtifacts`, while `_apply_phase_output` has one
production caller plus direct seam tests. Package 1 is therefore narrowed to the
phase-output application seam before broader DTO movement is attempted. This is
sequencing only, not a reduction of the architecture repair goal.

## Global Invariants

- Preserve documented CLI commands, flags, exit behavior, stdout/stderr
  placement, JSON payloads, and config persistence semantics unless a package
  explicitly scopes a contract change.
- Preserve lazy CLI imports for help/version/simple command paths.
- Preserve import-linter layer order and sibling-domain independence.
- Keep filesystem persistence inside existing owners and preserve deterministic
  TOML/JSON/report output.
- Keep Docker, Windows portable, packaging, dependency, and release paths out of
  scope unless a reviewed replan explicitly brings them in.
- No compatibility shims, legacy bridges, fallback API variants, or no-value
  forwarding owners without maintainer approval.
- Behavior-preserving refactors must prove invariance through existing or
  focused public/owner-seam tests plus full verification for hotspot changes.

## Plan Review Adjudication

### Review 1

Reviewer: read-only `reviewer` subagent.

Findings:

- Package briefs missed required execution-plan fields.
- Package 1 had two competing seams and would make implementation invent
  architecture.
- Deferrals lacked owner, risk, and revisit triggers.
- Package 1 verification was too narrow for public facade/API-doc invariants.
- Worker suitability was not satisfied for broad packages.
- Codanna availability note was stale.

Verdict:

- Accept all findings.

Actions taken:

- Package 1 is narrowed to the exact `phase_output_application.py` seam.
- Broader internal DTO ownership is retained as required Package 1B.
- Acceptance criteria, rollback, invariants, and stop/replan triggers are added
  to all packages.
- Package 1 verification now names package-surface and API-doc drift checks.
- Worker policy remains gated on exact package briefs and disjoint write sets.
- Deferrals now include owner, risk, and revisit trigger records.
- Codanna evidence is recorded as available and incorporated into Package 1.

### Review 2

Reviewer: read-only `reviewer` subagent.

Findings:

- No blocking findings remain before Package 1 implementation.
- Package 1 may proceed after adjudication.
- Future package review gates are uneven.
- Package 6 lacks an explicit out-of-scope section and dedicated review gate.

Verdict:

- Accept all findings.

Actions taken:

- Package 1 is approved for implementation.
- Future packages now explicitly require package-specific read-only plan review
  before implementation or no-code closeout.
- Package 6 now has an explicit out-of-scope section and review gate.

## Evidence Inventory

### Orchestration Core

Files:

- `src/frame_compare/orchestration/coordinator.py`
- `src/frame_compare/orchestration/types.py`
- `src/frame_compare/orchestration/preparation.py`
- `src/frame_compare/orchestration/execution.py`

Evidence:

- `coordinator.py` is the async run composition root. It initializes default
  `VSLoader`, `FFmpegRunner`, progress reporter, and HTTP client, runs
  preparation, constructs `RunContext`, emits post-load and post-align reports,
  executes split phase plans, and assembles `RunResult`.
- `types.py` mixes externally re-exported request/result/dependency DTOs with
  internal phase outputs, mutable `RunArtifacts`, `ExecutionState`, `PrepState`,
  and `ExecutionPhasePlan`.
- `execution.py` owns both phase-plan construction and `_apply_phase_output`,
  which mutates `ExecutionState`, `RunArtifacts`, and `RunContext`.
- `preparation.py` owns effective config, discovery, source selection,
  analysis-cache prevalidation, run-folder reservation, run-info writes, probe
  cache reads/writes, active-rect/selection-domain preparation, and metadata
  prefetch degradation.

Tests and call sites:

- `tests/orchestration/test_execution_phase_plan.py` directly tests phase order,
  request override projection, and `_apply_phase_output`.
- `tests/orchestration/test_execute_run_phase_integration.py` covers align,
  report-confirmed upload sequencing, metadata prefetch, publish/report outputs,
  and post-report cleanup behavior through `execute_run` and phase functions.
- `tests/orchestration/test_run_dependencies.py` protects dependency cloning,
  default initialization, and progress selection.
- `tests/orchestration/test_execute_run_cache_modes.py` and
  `tests/orchestration/test_execute_run_run_folders.py` protect cache-only,
  no-cache, run-folder, probe-cache, metadata-prefetch, and run-info ordering.

Boundary concerns:

- Public exposure is via `frame_compare.orchestration` lazy facade and
  `frame_compare.runner.run`; runbook treats importable modules as convenience
  APIs, but tests assert selected exports.
- Filesystem concerns include shared analysis/probe caches and run folders.
- Runtime concerns include lazy VS/FFmpeg initialization and HTTP client
  ownership.
- State risk is concentrated in phase-output mutation and ordering-dependent
  artifacts such as `report_succeeded`, uploaded slow.pics file paths, warnings,
  and selected frames.

Initial repair stance:

- Touch early, but as a behavior-preserving internal ownership split. Codanna
  impact evidence makes broad `ExecutionState`/`RunArtifacts` movement too large
  for the first package. The first package must extract phase-output application
  from phase-plan construction only. A later package may move internal DTOs after
  the applicator seam is stable and reviewed. Do not change phase order or
  public `RunResult` shape.

### Shared Errors

Files:

- `src/frame_compare/errors.py`
- `src/frame_compare/error_context.py`
- `src/frame_compare/error_categories.py`
- `src/frame_compare/error_*`

Evidence:

- `errors.py` is already a stable facade over focused error owner modules.
- `error_context.py` owns `ErrorContext`, `ErrorDetails`, `FrameCompareError`,
  and `JSONValue`.
- `error_categories.py` owns category base classes.
- Tests in `tests/test_errors.py` and `tests/test_error_modules.py` protect
  formatting, export surface, subclasses, JSON shape, and repr behavior.

Initial repair stance:

- Defer. Current structure already reflects the intended extraction from the
  hotspot facade. Only touch if downstream packages need an error owner update.

### Report And CLI Output

Files:

- `src/frame_compare/services/report/**`
- `src/frame_compare/cli/entry.py`
- `src/frame_compare/cli/run_command.py`
- `src/frame_compare/orchestration/phase_post_render.py`

Evidence:

- `services.report.entry.generate_report` owns report path resolution,
  validation, HTML build, and atomic write.
- `services.report.payload`, `renderer`, `viewer`, and display modules are
  already separated by report payload, markup, static assets, and labels.
- Browser open, clipboard copy, report auto-open, and report-confirmed upload
  prompt ownership remain in CLI/run-command helpers, not report services.
- Orchestration report and cleanup phases carry typed output state rather than
  browser side effects.

Tests:

- `tests/services/test_report_entry.py`
- `tests/services/test_report.py`
- `tests/services/test_report_renderer_markup.py`
- `tests/services/test_report_viewer_assets_*`
- `tests/cli/test_run_report_open.py`
- `tests/cli/test_run_command.py`
- `tests/cli/test_run_output.py`

Initial repair stance:

- Defer from first package unless orchestration package changes affect
  report-confirmed lifecycle. Current seams are mostly aligned and well tested.

### Alignment Services

Files:

- `src/frame_compare/services/alignment.py`
- `src/frame_compare/services/alignment_audio.py`
- `src/frame_compare/services/alignment_correlation.py`
- `src/frame_compare/services/alignment_consensus.py`
- `src/frame_compare/services/alignment_vspreview.py`
- `src/frame_compare/orchestration/phase_tasks.py`

Evidence:

- `alignment.py` is the service entrypoint and policy coordinator for manual
  overrides, previous-offset reuse, computed audio alignment, VSPreview
  confirmation, cache writes, and result precedence.
- `alignment_audio.py` owns FFmpeg/ffprobe extraction, audio stream probing,
  stream selection, subprocess output parsing, and channel strategy.
- `alignment_correlation.py` and `alignment_consensus.py` own numeric
  correlation and candidate/window consensus.
- `alignment_vspreview.py` owns interactive VSPreview alignment behavior and
  terminal/TTY-sensitive prompting.
- `phase_tasks.py` builds the layer-neutral `AlignmentRequest` and consumes
  `AlignmentResult` into updated clip state and selected frames.

Tests:

- `tests/services/test_alignment_workflow.py`
- `tests/services/test_alignment_ffmpeg.py`
- `tests/services/test_alignment_reuse_cache.py`
- `tests/services/test_alignment_reuse_prompt.py`
- `tests/services/test_alignment_vspreview.py`
- `tests/integration/test_alignment_runtime.py`
- `tests/orchestration/test_phase_tasks_alignment.py`
- `tests/orchestration/test_phase_tasks_outputs.py`

Boundary concerns:

- FFmpeg subprocess and stdout parsing are runtime-sensitive.
- Shared previous-offset cache is filesystem persistence and must remain
  service-owned.
- Prompt mode is interactive and stderr/stdin TTY gated.
- `services` must not import orchestration-owned identity types.

Initial repair stance:

- High-value early package after plan review. Candidate seam: split
  `alignment.py` policy stages into focused service-owned helpers or typed
  stage DTOs without changing result precedence, cache eligibility, prompts, or
  request shape. Treat `alignment_audio.py` hardening as a separate package
  unless the first package directly exposes a parsing/policy defect.

### Render Batch

File:

- `src/frame_compare/render/batch/orchestrator.py`

Evidence:

- Render batch orchestrator owns batch expansion execution, artifact creation,
  progress reporting, warnings, and partial render error propagation.
- Callers enter through `orchestration.phase_tasks.run_render_phase`.
- Tests exist in `tests/render/test_orchestrator*.py`,
  `tests/integration/test_render_orchestrator.py`, and orchestration phase tests.

Boundary concerns:

- Runtime outputs are filesystem artifacts used by report, slow.pics upload, and
  cleanup.
- Partial failure semantics and deterministic output ordering are the main risk.

Initial repair stance:

- Defer until orchestration/alignment contracts are stabilized. Candidate seam is
  an explicit batch execution/result accumulator, preserving current artifact
  ordering and warning behavior.

### Doctor And VSPreview Adapter

Files:

- `src/frame_compare/orchestration/doctor.py`
- `src/frame_compare/vspreview/adapter.py`
- `src/frame_compare/services/alignment_vspreview.py`

Evidence:

- `doctor.py` owns dependency diagnostic check ordering and human/JSON result
  mapping through the doctor command.
- `vspreview.adapter` owns VSPreview availability and launch bridge behavior.
- `alignment_vspreview.py` consumes adapter behavior for interactive alignment.
- Tests exist in `tests/orchestration/test_doctor.py`,
  `tests/orchestration/test_doctor_runner.py`, and
  `tests/vspreview/test_adapter.py`.

Boundary concerns:

- User-visible doctor output and exit status are CLI contract surfaces.
- VSPreview availability must not eagerly import or require unavailable runtime
  dependencies on simple CLI paths.
- Process launch, TTY, and timeout behavior are runtime-adjacent.

Initial repair stance:

- Doctor registry/execution split is a bounded package with clear tests.
  VSPreview adapter/interactive alignment should be a later package because
  process and TTY behavior need tighter proof.

## Repair Packages

### Package 1: Phase Output Application Owner

Goal:

- Reduce orchestration execution hotspot coupling by giving phase-output
  mutation a single focused owner.

Chosen owner seam:

- Create `src/frame_compare/orchestration/phase_output_application.py`.
- Move `_apply_phase_output` from `execution.py` to that module and rename it to
  `apply_phase_output`.
- `execution.py` keeps phase construction and timed phase execution, importing
  and calling `apply_phase_output`.
- No DTOs move in Package 1.

Files in scope:

- `src/frame_compare/orchestration/phase_output_application.py`
- `src/frame_compare/orchestration/execution.py`
- `tests/orchestration/test_execution_phase_plan.py`, limited to importing the
  new applicator owner for direct seam tests
- `docs/current-architecture.md` if ownership truth changes
- generated `docs/api.md` only if the generated import reference changes

Out of scope:

- DTO movement, phase behavior, phase ordering, CLI/config behavior, report HTML
  behavior, Docker/Windows/release surfaces, and alignment algorithm policy.

Invariants:

- `RunRequest`, `RunDependencies`, `RunResult`, and current lazy
  `frame_compare.orchestration` facade exports stay compatible.
- Phase order and timing keys stay unchanged.
- `RunResult` warning ordering and JSON-facing values stay unchanged.
- No new imports that violate `importlinter.ini`.
- `apply_phase_output` remains exhaustively typed over `PhaseOutput` and keeps
  the existing unknown-output `TypeError` guard.

Acceptance criteria:

- `execution.py` no longer owns phase-output mutation branches.
- Direct applicator tests still cover every current phase-output variant.
- `build_execution_phase_plan`, `build_phases_before_align`, and
  `build_phases_after_align` public behavior is unchanged.
- Codanna/`rg` confirms the only production call to `apply_phase_output` is the
  timed phase executor unless a reviewed reason is documented.
- No public facade exports are added or removed.

Verification:

- Mode: `refactor-invariance`.
- Classification: existing coverage sufficient unless imports expose an
  uncovered move; add focused tests only if a new owner API has behavior.
- Commands:
  - `.venv/bin/pytest -q tests/orchestration/test_execution_phase_plan.py tests/orchestration/test_execute_run_phase_integration.py tests/orchestration/test_run_dependencies.py tests/orchestration/test_run_result.py`
  - `.venv/bin/pytest -q tests/orchestration/test_execute_run_lifecycle.py tests/test_package_surface_policy.py tests/test_api_docs_cli.py`
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check`
  - `.venv/bin/pyright --warnings`
  - `.venv/bin/ruff check .`
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`
  - Full gate before package closeout: `.venv/bin/pytest -q` plus the commands above and bandit.

Rollback:

- Re-inline `apply_phase_output` into `execution.py` and delete
  `phase_output_application.py`; no persistence or generated runtime artifacts
  should need cleanup.

Stop/replan:

- Any public facade compatibility break is required.
- Any phase order/timing behavior changes.
- Pyright requires broad `Any`, casts without runtime guards, or weakened phase
  output typing.
- Applicator extraction requires moving `ExecutionState`, `RunArtifacts`, or
  phase-output DTOs in the same package.

Review gate:

- Read-only adversarial plan review before implementation.
- Read-only adversarial implementation review before moving to Package 2.

Implementation status:

- Implemented in this session.
- Added `src/frame_compare/orchestration/phase_output_application.py`.
- `execution.py` now imports and calls `apply_phase_output`; phase construction
  and timed execution remain in `execution.py`.
- Direct phase-output application tests now import the new owner.
- `docs/current-architecture.md` was updated in the same pass.

Observed verification:

- `.venv/bin/pytest -q tests/orchestration/test_execution_phase_plan.py tests/orchestration/test_execute_run_phase_integration.py tests/orchestration/test_run_dependencies.py tests/orchestration/test_run_result.py` passed: 30 tests.
- `.venv/bin/pytest -q tests/orchestration/test_execute_run_lifecycle.py tests/test_package_surface_policy.py tests/test_api_docs_cli.py` passed: 28 tests.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check` passed with no drift.
- `.venv/bin/pyright --warnings` passed: 0 errors, 0 warnings.
- `.venv/bin/ruff check .` passed.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` passed: both contracts kept.
- `.venv/bin/bandit -c pyproject.toml -r src --severity-level medium` passed with no medium/high issues.
- `.venv/bin/pytest -q` passed; expected runtime/platform skips remained.
- `rg -n "apply_phase_output\\(" src tests` confirmed one production call in
  `execution.py`, one definition, and direct seam tests.

Implementation review:

- Two Package 1 implementation reviewer agents timed out and were closed without
  findings.
- A third read-only reviewer reported no blockers.
- Non-blocking finding: direct helper tests do not cover every match arm, but
  existing phase/integration coverage plus the passed full gates are adequate for
  this mechanical move.
- Verdict: accept with no code change. Package 1 is closed after adjudication.

### Package 1B: Internal Orchestration DTO Ownership Repair

Goal:

- Repair internal orchestration DTO ownership after the phase-output applicator
  seam is stable, so public run DTOs and internal execution carriers are not
  left mixed merely because the broad move was split for reviewability.

Chosen owner seam:

- Keep `src/frame_compare/orchestration/types.py` as the public run contract
  owner for `RunRequest`, `RunDependencies`, `RunResult`, slow.pics upload
  confirmation callback DTO/protocol/decision, `MetricsCacheStatus`,
  `SlowpicsUploadConfirmationStatus`, and `PostUploadActionResults`.
- `PostUploadActionResult` remains owned by
  `src/frame_compare/utils/post_upload_actions.py`; Package 1B should update
  direct imports that only need that concrete type to import from the true owner.
- Create `src/frame_compare/orchestration/execution_types.py` as the internal
  owner for phase outputs and mutable execution/preparation carriers:
  `RenderArtifacts`, `FramePlanPhaseOutput`, `AnalyzePhaseOutput`,
  `AlignPhaseOutput`, `RenderPhaseOutput`, `MetadataPhaseOutput`,
  `PublishPhaseOutput`, `ReportPhaseOutput`,
  `ConfirmSlowpicsUploadPhaseOutput`, `PostReportCleanupPhaseOutput`,
  `PhaseOutput`, `RunArtifacts`, `ExecutionState`, `MetadataPrefetch`,
  `PrepState`, and `ExecutionPhasePlan`.
- Update internal production imports to consume moved symbols from
  `execution_types.py`.
- Update tests that directly exercise internal phase/execution carriers to
  import moved symbols from `execution_types.py`.
- Do not add compatibility forwarding imports in `types.py` for moved internal
  symbols.

Files in scope:

- `src/frame_compare/orchestration/types.py`
- `src/frame_compare/orchestration/execution_types.py`
- import/call sites and direct tests if symbols move
- `docs/current-architecture.md`
- generated `docs/api.md` if import reference changes

Out of scope:

- Public `RunRequest`, `RunDependencies`, and `RunResult` compatibility changes.

Invariants:

- Lazy `frame_compare.orchestration` facade exports stay compatible.
- Type precision is not weakened with `Any`, broad `object`, or ad hoc dicts.
- No behavior changes to phase application, execution planning, or result
  assembly.

Acceptance criteria:

- The exact DTO move above is reviewed and implemented.
- All moved internal imports are updated and no compatibility forwarding module
  is added.
- `types.py` no longer imports `ClipState`, `FrameMetrics`,
  `SelectionBreakdown`, `SelectionDetailsByFrame`, `SelectionWindow`,
  `TmdbMetadata`, or `WorkspacePaths` solely for internal execution carriers.
- Public run contract imports from `frame_compare.orchestration`,
  `frame_compare.orchestration.coordinator`, and
  `frame_compare.orchestration.types` remain compatible for `RunRequest`,
  `RunDependencies`, `RunResult`, slow.pics confirmation callback symbols, and
  public status/result aliases retained in `types.py`.
- API docs drift is checked.

Verification:

- Mode: `refactor-invariance`.
- Classification: existing coverage sufficient for pure moves; new tests only if
  an owner API gains behavior.
- Commands:
  - `.venv/bin/pytest -q tests/orchestration/test_execution_phase_plan.py tests/orchestration/test_execute_run_phase_integration.py tests/orchestration/test_phase_tasks.py tests/orchestration/test_phase_tasks_outputs.py tests/orchestration/test_run_dependencies.py tests/orchestration/test_run_result.py tests/test_package_surface_policy.py`
  - `.venv/bin/pytest -q tests/cli/test_run_command.py tests/cli/test_run_output.py tests/cli/test_run_report_open.py`
  - `.venv/bin/pytest -q tests/orchestration/test_execute_run_lifecycle.py tests/orchestration/test_phases.py tests/test_cli_contract_docs.py`
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check`
  - Full gate before package closeout.

Rollback:

- Revert the DTO move as a unit.

Stop/replan:

- Import facade compatibility would require a shim.
- Moved symbols create cycles or import-layer pressure.

Review gate:

- Read-only adversarial package review before implementation.
- Read-only adversarial implementation review after refactor.

Package plan review:

- Reviewer reported no blockers and `MAY_PROCEED_AFTER_ADJUDICATION: yes`.
- Non-blocking findings accepted:
  - Clarify that `SlowpicsUploadConfirmationDecision` remains in `types.py`.
  - Route `PostUploadActionResult` direct imports to
    `utils.post_upload_actions` where they only need the concrete type.
  - Add `tests/orchestration/test_execute_run_lifecycle.py`,
    `tests/orchestration/test_phases.py`, and `tests/test_cli_contract_docs.py`
    to focused verification.

Implementation record:

- Implemented in this session.
- Added `src/frame_compare/orchestration/execution_types.py` as the internal
  phase-output and execution/preparation carrier owner.
- Pruned `src/frame_compare/orchestration/types.py` to the public run and
  callback contract.
- Updated production and test imports so internal DTOs come from
  `execution_types.py`, public run/callback DTOs remain in `types.py` or the
  curated facade/coordinator, and concrete `PostUploadActionResult` imports use
  `frame_compare.utils.post_upload_actions`.
- Updated `docs/current-architecture.md` to document the public/internal DTO
  boundary.

Observed verification:

- `.venv/bin/pytest -q tests/orchestration/test_execution_phase_plan.py tests/orchestration/test_execute_run_phase_integration.py tests/orchestration/test_phase_tasks.py tests/orchestration/test_phase_tasks_outputs.py tests/orchestration/test_run_dependencies.py tests/orchestration/test_run_result.py tests/test_package_surface_policy.py` passed.
- `.venv/bin/pytest -q tests/cli/test_run_command.py tests/cli/test_run_output.py tests/cli/test_run_report_open.py` passed.
- `.venv/bin/pytest -q tests/orchestration/test_execute_run_lifecycle.py tests/orchestration/test_phases.py tests/test_cli_contract_docs.py` passed.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check` passed with no drift.
- `.venv/bin/pyright --warnings` passed: 0 errors, 0 warnings.
- `.venv/bin/ruff check .` passed.
- `.venv/bin/bandit -c pyproject.toml -r src --severity-level medium` passed with no medium/high issues.
- `.venv/bin/pytest -q` passed; expected runtime/platform skips remained.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` passed: both contracts kept.

Implementation review:

- Read-only reviewer Goodall reported no P0-P3 defects in the DTO ownership
  diff.
- Read-only reviewer Plato reported no P0/P1 blockers and two findings:
  - P2: new owner modules are untracked. Adjudication: accepted as closeout/git
    hygiene, not a code defect; the files are intentionally new and must be
    staged with the package before any commit/patch closeout.
  - P3: `types.py` still accidentally bound concrete
    `PostUploadActionResult` via its tuple alias import. Adjudication: accepted
    and fixed by importing `PostUploadActionResults` from
    `frame_compare.utils.post_upload_actions` instead.
- Verification was rerun after the P3 cleanup and remained green.
- Verdict: Package 1B is closed after adjudication.

### Package 2: Alignment Policy Coordinator Split

Goal:

- Shrink `services/alignment.py` by extracting service-owned policy stages or
  typed internal helpers while preserving existing alignment precedence, shared
  reuse cache eligibility, prompt behavior, and returned `AlignmentResult`
  ordering.

Chosen owner seam:

- Keep `align_clips_from_request` in `src/frame_compare/services/alignment.py`
  as the public service entrypoint.
- Extract only one reviewed policy stage at a time into an exact service-owned
  module. The first candidate is
  `src/frame_compare/services/alignment_previous_offsets.py` if evidence shows
  previous-offset reuse policy is the largest independent block.
- Do not use a worker until the exact helper module, moved functions, and tests
  are named in a package-specific brief.

Files in scope:

- `src/frame_compare/services/alignment.py`
- new focused `src/frame_compare/services/alignment_*.py` owner only if it has
  real policy responsibility
- relevant service/orchestration alignment tests
- `docs/current-architecture.md` if owner truth changes

Out of scope:

- Audio extraction command semantics, correlation math, consensus thresholds,
  VSPreview process behavior, CLI/config contract changes.

Invariants:

- `align_clips_from_request` signature and result ordering stay unchanged.
- Shared previous-offset cache reads/writes and warning behavior stay unchanged.
- Prompt mode remains stderr/stdin TTY gated.
- `services` continues to consume only layer-neutral request DTOs.

Acceptance criteria:

- `alignment.py` no longer carries the extracted policy stage body, but remains
  the service entrypoint and result precedence coordinator.
- Extracted helper owns one coherent policy stage with typed inputs/outputs.
- No cache file format, prompt text, warning text, provenance, or result ordering
  changes occur.
- Existing alignment workflow tests pass without broad fixture rewrites.

Verification:

- Mode: `refactor-invariance` with runtime-boundary awareness.
- Classification: existing coverage sufficient for pure extraction; new focused
  tests required if a policy branch becomes newly explicit.
- Commands:
  - `.venv/bin/pytest -q tests/services/test_alignment_workflow.py tests/services/test_alignment_reuse_cache.py tests/services/test_alignment_reuse_prompt.py tests/services/test_alignment_vspreview.py tests/orchestration/test_phase_tasks_alignment.py`
  - Full gate before package closeout.

Rollback:

- Re-inline extracted policy helper calls into `alignment.py`.

Stop/replan:

- Result precedence, cache provenance, or prompt semantics become unclear.
- A service helper needs orchestration-owned types.
- The extraction wants to change audio extraction, correlation, consensus, or
  VSPreview runtime behavior.

Review gate:

- Package-specific read-only plan review before implementation.
- Worker subagent may implement this package only after Package 1 is closed and
  the exact write set is disjoint from active local work.
- Read-only adversarial implementation review after refactor.

Package-specific implementation brief:

- Extract previous-offset reuse policy into
  `src/frame_compare/services/alignment_previous_offsets.py`.
- Move these policy helpers from `alignment.py` to the new owner:
  `_validate_previous_offsets_policy`, `_shared_reuse_prompt_input`,
  `_apply_cached_alignment_result`, `_apply_shared_reuse`,
  `_shared_write_is_service_eligible`, and
  `prompt_for_previous_alignment_offset_reuse`.
- Rename moved private helpers to owner-local public-in-module helpers where
  useful: `validate_previous_offsets_policy`, `apply_shared_reuse`, and
  `shared_write_is_service_eligible`.
- Keep `align_clips_from_request` and `align_clips` in `alignment.py` as the
  public service entrypoints and sequencing coordinators.
- Keep `save_reusable_offsets` write execution in `alignment.py`; the new module
  decides write eligibility only.
- Preserve the legacy import
  `frame_compare.services.alignment.prompt_for_previous_alignment_offset_reuse`
  by importing the moved function into `alignment.py` and retaining it in
  `__all__`.
- Update workflow tests that monkeypatch reusable-entry reads or previous-offset
  prompts to patch `frame_compare.services.alignment_previous_offsets`, because
  the new owner performs those reads/prompts.
- Do not change cache schemas, prompt text, warning text, alignment math,
  VSPreview launch behavior, result ordering, or provenance strings.

Package plan review:

- Reviewer Lorentz reported no P0/P1 blockers and `MAY_PROCEED_AFTER_ADJUDICATION: yes`.
- P2 finding: `docs/current-architecture.md` would become stale when ownership
  moved. Adjudication: accepted; Package 2 implementation updated both the
  narrative ownership section and runtime ownership matrix.
- P2 finding: moved helpers needed a single `_alignment_key` strategy to avoid
  cycles or drift. Adjudication: accepted; implementation added
  `src/frame_compare/services/alignment_keys.py` as the shared service-local key
  owner used by both `alignment.py` and `alignment_previous_offsets.py`.
- Non-blocking finding: monkeypatch targets should move for cache reads/prompts,
  but `save_reusable_offsets` guards should remain cache-owner durable
  persistence checks. Adjudication: accepted; tests patch moved call sites on
  `alignment_previous_offsets`, and write execution remains in `alignment.py`.

Implementation record:

- Implemented in this session.
- Added `src/frame_compare/services/alignment_previous_offsets.py` for
  previous-offset validation, reusable-entry prompt input construction, shared
  reuse application, shared write eligibility, and the prompt wrapper.
- Added `src/frame_compare/services/alignment_keys.py` for stable
  reference/comparison alignment key construction.
- `alignment.py` remains the public service entrypoint and sequencing
  coordinator for `align_clips_from_request` and `align_clips`; it keeps manual
  overrides, compute, VSPreview sequencing/provenance, final result ordering,
  and `save_reusable_offsets` write execution.
- Preserved legacy import compatibility for
  `frame_compare.services.alignment.prompt_for_previous_alignment_offset_reuse`.
- Updated workflow test monkeypatch targets for moved cache reads/prompts and
  updated `docs/current-architecture.md` owner truth.

Observed verification:

- `.venv/bin/pytest -q tests/services/test_alignment_workflow.py tests/services/test_alignment_reuse_cache.py tests/services/test_alignment_reuse_prompt.py tests/services/test_alignment_vspreview.py tests/orchestration/test_phase_tasks_alignment.py` passed.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check` passed with no drift.
- `.venv/bin/pyright --warnings` passed: 0 errors, 0 warnings.
- `.venv/bin/ruff check .` passed.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` passed: both contracts kept.
- `.venv/bin/bandit -c pyproject.toml -r src --severity-level medium` passed with no medium/high issues.
- `.venv/bin/pytest -q` passed; expected runtime/platform skips remained.

Implementation review:

- Read-only reviewer Helmholtz reported no P0-P3 findings and no blockers.
- Reviewer verified result ordering remains driven by `request.comparisons`,
  previous-offset policy/provenance/write eligibility moved intact, `alignment.py`
  still owns sequencing and save execution, legacy prompt import compatibility
  remains, shared key ownership is centralized, and architecture docs are
  updated.
- Verdict: Package 2 is closed after adjudication.

### Package 3: Doctor Check Registry And Execution Split

Goal:

- Make doctor check ordering, optionality, and result mapping explicit without
  changing `doctor` human/JSON output or exit behavior.

Chosen owner seam:

- Keep `run_doctor` in `src/frame_compare/orchestration/doctor.py` as the
  diagnostic entry surface.
- If extraction is justified, create a focused orchestration-owned helper such
  as `src/frame_compare/orchestration/doctor_checks.py` for check definitions
  and ordering only; result DTOs and public JSON/human mapping stay unchanged
  unless a reviewed package brief says otherwise.

Files in scope:

- `src/frame_compare/orchestration/doctor.py`
- optional new orchestration doctor helper module
- `tests/orchestration/test_doctor.py`
- `tests/orchestration/test_doctor_runner.py`
- `docs/current-architecture.md` if owner truth changes

Out of scope:

- CLI command flags/output schema changes, new diagnostics, Docker/Windows
  verification, real runtime probe behavior changes.

Invariants:

- `doctor --json` payload shape stays unchanged.
- Human doctor output status semantics stay unchanged.
- Critical versus optional checks keep current exit behavior.
- Optional VSPreview probe diagnostics remain sanitized and optional.

Acceptance criteria:

- Check order and optionality are represented by a focused owner, unless a
  package-specific adversarial review proves no material maintainability concern
  remains and that no-code closeout is adjudicated in this plan.
- Existing doctor tests prove unchanged category/status/exit behavior.
- No eager VSPreview/VapourSynth import is introduced on simple CLI paths.

Verification:

- Mode: `contract-first` plus `refactor-invariance`.
- Classification: existing coverage sufficient if behavior is unchanged.
- Commands:
  - `.venv/bin/pytest -q tests/orchestration/test_doctor.py tests/orchestration/test_doctor_runner.py tests/cli/test_doctor_command.py`
  - Full gate before package closeout.

Review gate:

- Package-specific read-only plan review before implementation.
- Read-only adversarial implementation review after refactor.

Package-specific implementation brief:

- Create `src/frame_compare/orchestration/doctor_types.py` for
  `CheckResult`, `DoctorCheck`, and `DoctorReport`.
- Create `src/frame_compare/orchestration/doctor_checks.py` for canonical check
  order, check implementations, TMDB config resolution, and `collect_checks()`.
- Keep `src/frame_compare/orchestration/doctor.py` as the diagnostic execution
  entry surface; it should import DTOs from `doctor_types.py` and
  `collect_checks()` from `doctor_checks.py`, then own only `run_doctor()`.
- Preserve public import compatibility by re-exporting `CheckResult`,
  `DoctorCheck`, `DoctorReport`, and `collect_checks` from `doctor.py`.
- Update tests that patch check implementation internals to patch
  `frame_compare.orchestration.doctor_checks`, because the new owner performs
  those checks.
- Do not change check order, category labels, optional/core/network semantics,
  output text, JSON shape, exit behavior, TMDB config loading, slow.pics
  healthcheck behavior, or lazy VSPreview import behavior.

Package plan review:

- Initial reviewer Turing timed out and was closed to avoid subagent slot
  leakage.
- Quick reviewer Heisenberg reported no P0-P2 blockers and
  `MAY_PROCEED_AFTER_ADJUDICATION: yes`.
- P3 cautions accepted:
  - Preserve `frame_compare.orchestration.doctor` imports for `CheckResult`,
    `DoctorCheck`, `DoctorReport`, and `collect_checks`.
  - Move test patch targets for check internals to `doctor_checks`.
  - Keep dependency flow one-way: `doctor_types` independent,
    `doctor_checks` imports `doctor_types`, and `doctor` imports both.
  - Keep VSPreview adapter import lazy inside `_check_vspreview()`.

Implementation record:

- Implemented in this session.
- Added `src/frame_compare/orchestration/doctor_types.py` for doctor DTOs.
- Added `src/frame_compare/orchestration/doctor_checks.py` for canonical check
  order, check implementations, TMDB config resolution, slow.pics healthcheck
  URL, and `collect_checks()`.
- Replaced `src/frame_compare/orchestration/doctor.py` with a slim execution
  surface owning `run_doctor()` and re-exporting public compatibility symbols.
- Updated moved test patch targets to `doctor_checks`.
- Updated `docs/current-architecture.md` runtime ownership matrix and hotspot
  list for `doctor`, `doctor_checks`, and `doctor_types`.

Observed verification:

- `.venv/bin/pytest -q tests/orchestration/test_doctor.py tests/orchestration/test_doctor_runner.py tests/cli/test_doctor_command.py` passed.
- `.venv/bin/pytest -q tests/orchestration/test_doctor_network.py tests/orchestration/test_import_smoke.py tests/test_package_surface_policy.py` passed.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check` passed with no drift.
- `.venv/bin/pyright --warnings` passed: 0 errors, 0 warnings.
- `.venv/bin/ruff check .` passed.
- `.venv/bin/bandit -c pyproject.toml -r src --severity-level medium` passed with no medium/high issues.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` passed: both contracts kept.
- `.venv/bin/pytest -q` passed; expected runtime/platform skips remained.
- Import-time sanity check confirmed importing
  `frame_compare.orchestration.doctor` does not import
  `frame_compare.vspreview.adapter`.

Implementation review:

- Read-only reviewer Volta reported no P0-P2 findings.
- P3 finding: `docs/current-architecture.md` hotspot list still named only
  `doctor.py`. Adjudication: accepted and fixed by adding `doctor_checks.py` and
  `doctor_types.py` to the hotspot entry.
- Verification was rerun after the P3 doc cleanup and remained green.
- Verdict: Package 3 is closed after adjudication.

Rollback:

- Re-inline extracted check registry/order helper into `doctor.py`.

Stop/replan:

- Any doctor output text, JSON shape, exit code, or optional/critical status
  would change implicitly.
- Real runtime probe behavior needs to change to complete the refactor.

### Package 4: Render Batch Execution Result Accumulator

Goal:

- Isolate render batch scheduling/result accumulation from per-frame rendering
  execution while preserving deterministic artifact ordering and warning/error
  behavior.

Chosen owner seam:

- Keep public render batch entrypoints in
  `src/frame_compare/render/batch/orchestrator.py`.
- If extraction is justified, create a render-owned helper such as
  `src/frame_compare/render/batch/results.py` for result accumulation only.
  Expansion, geometry, naming, and encoder behavior remain with their current
  owners.

Files in scope:

- `src/frame_compare/render/batch/orchestrator.py`
- optional focused render batch helper module
- render/orchestration tests covering batch outputs
- docs if owner truth changes

Out of scope:

- Screenshot geometry, naming, encoders, FFmpeg command construction, report
  payload behavior, slow.pics upload semantics.

Invariants:

- Screenshot paths and ordering remain deterministic.
- Progress updates and warning collection remain unchanged.
- Partial failure behavior remains unchanged.
- No report or slow.pics upload membership is derived from directory scans.

Acceptance criteria:

- Result accumulation is isolated, unless a package-specific adversarial review
  proves no material maintainability concern remains and that no-code closeout
  is adjudicated in this plan.
- Render batch tests prove identical output artifact structure and warning
  behavior.
- No Docker/runtime verification is claimed unless render runtime semantics
  actually change and the Docker gate is run or documented-only.

Verification:

- Mode: `refactor-invariance`.
- Classification: existing coverage sufficient unless partial-failure branches
  are newly exposed.
- Commands:
  - `.venv/bin/pytest -q tests/render/test_orchestrator.py tests/render/test_orchestrator_batch_screenshots.py tests/render/test_orchestrator_screenshots.py tests/integration/test_render_orchestrator.py tests/orchestration/test_phase_tasks_outputs.py`
  - Full gate before package closeout.
  - Docker gate only if render runtime integration semantics change; otherwise
    record Docker as not touched.

Review gate:

- Package-specific read-only plan review before implementation.
- Read-only adversarial implementation review after refactor.

Package-specific implementation brief:

- Create `src/frame_compare/render/batch/results.py` for result-slot
  accumulation only.
- Add a small typed accumulator, e.g. `RenderBatchResults`, that:
  - initializes one slot per input request,
  - records rendered paths by original request index,
  - exposes completed ordered paths,
  - preserves the existing `"render batch completed without a rendered path"`
    runtime error if any slot is missing.
- Keep scheduling, fail-fast behavior, in-flight wait behavior, progress
  descriptions, and `render_frame` call sites in
  `src/frame_compare/render/batch/orchestrator.py`.
- Keep public entrypoints `render_batch`, `render_screenshots`, and
  `render_screenshots_from_batch` in `orchestrator.py`.
- Do not move or change `render_batch_results_by_label` in `expansion.py`; it
  owns label/range mapping, not execution result-slot accumulation.
- Update tests only if they need to patch or directly exercise the new
  accumulator; do not change artifact ordering expectations.

Package plan review:

- Reviewer Avicenna reported no P0-P2 blockers and
  `MAY_PROCEED_AFTER_ADJUDICATION: yes`.
- Non-blocking findings accepted:
  - Keep `results.py` free of scheduling concepts, progress reporter, and
    `render_frame` imports.
  - Preserve empty-batch behavior where `render_batch([])` returns `[]` before
    starting/completing a progress phase.
  - Add `tests/integration/test_render_pipeline.py` to focused verification.
  - Record Docker/runtime proof as not touched because the implementation is a
    pure accumulator extraction.

Implementation record:

- Implemented in this session.
- Added `src/frame_compare/render/batch/results.py` with `RenderBatchResults`
  owning slot initialization, indexed path recording, and ordered completion
  validation.
- Updated `src/frame_compare/render/batch/orchestrator.py` so sequential and
  parallel scheduling record rendered paths through the accumulator while
  scheduling, progress, fail-fast behavior, in-flight wait behavior, and
  `render_frame` call sites remain in the orchestrator.
- Added direct accumulator tests for ordering and missing-slot error behavior.
- Docker/runtime integration semantics were not touched, so no Docker proof is
  claimed for this package.

Observed verification:

- `.venv/bin/pytest -q tests/render/test_orchestrator.py tests/render/test_orchestrator_batch_screenshots.py tests/render/test_orchestrator_screenshots.py tests/integration/test_render_orchestrator.py tests/integration/test_render_pipeline.py tests/orchestration/test_phase_tasks_outputs.py` passed.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check` passed with no drift.
- `.venv/bin/pyright --warnings` passed: 0 errors, 0 warnings.
- `.venv/bin/ruff check .` passed.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` passed: both contracts kept.
- `.venv/bin/bandit -c pyproject.toml -r src --severity-level medium` passed with no medium/high issues.
- `.venv/bin/pytest -q` passed; expected runtime/platform skips remained.

Implementation review:

- Read-only reviewer Godel reported no P0/P1 runtime findings.
- P2 finding: `src/frame_compare/render/batch/results.py` was untracked while
  `orchestrator.py` and tests imported it. Adjudication: accepted as
  closeout/git hygiene; Package 4 must be staged and committed with the new file
  before moving on.
- Reviewer confirmed ordering remains index-based, empty batches return before
  progress starts, failure/progress behavior remains in `orchestrator.py`, no
  new parallel submissions occur after first exception, and label/range
  projection remains in `expansion.py`.
- Verdict: Package 4 is closed after adjudication and commit hygiene.

Rollback:

- Re-inline result accumulation helper into `render/batch/orchestrator.py`.

Stop/replan:

- Output ordering, warning behavior, progress behavior, or exception propagation
  would change.
- Extraction requires changing geometry, naming, encoder, or report owners.

### Package 5: VSPreview Boundary Hardening

Goal:

- Clarify VSPreview availability/launch result boundaries between
  `vspreview.adapter`, `alignment_vspreview`, and `doctor` without changing
  user-visible interactive alignment behavior.

Chosen owner seam:

- `src/frame_compare/vspreview/adapter.py` owns executable discovery, launch
  command construction, process lifecycle, and availability result typing.
- `src/frame_compare/services/alignment_vspreview.py` owns alignment-specific
  prompt/override policy and consumes adapter outputs.
- `src/frame_compare/orchestration/doctor_checks.py` owns the doctor availability
  check that presents adapter availability as an optional diagnostic result;
  `doctor.py` owns execution/result aggregation only.

Files in scope:

- `src/frame_compare/vspreview/adapter.py`
- `src/frame_compare/services/alignment_vspreview.py`
- focused VSPreview tests
- docs if owner truth changes

Out of scope:

- New CLI flags, new VSPreview features, Docker GUI support, and real desktop
  launch behavior.

Invariants:

- Interactive alignment prompt behavior, stderr diagnostics, and manual override
  persistence stay unchanged.
- VSPreview remains optional in doctor output.
- Simple CLI paths do not eagerly import unavailable VSPreview/VapourSynth
  runtime dependencies.
- Live desktop launch is not claimed verified without an actual compatible
  environment proof.

Acceptance criteria:

- Adapter result/failure ownership is explicit and typed, unless a
  package-specific adversarial review proves no material runtime-boundary or
  maintainability concern remains and that no-code closeout is adjudicated in
  this plan.
- Alignment VSPreview tests cover malformed/unavailable adapter outputs if new
  result branches are introduced.
- Doctor tests continue to prove optional VSPreview status handling.

Verification:

- Mode: `manual-runtime` plus `refactor-invariance`.
- Classification: new tests required if launch/probe result objects or failure
  branches are introduced.
- Commands:
  - `.venv/bin/pytest -q tests/vspreview/test_adapter.py tests/services/test_alignment_vspreview.py tests/services/test_alignment_workflow_vspreview.py tests/orchestration/test_doctor.py tests/orchestration/test_doctor_runner.py`
  - Full gate before package closeout.
  - Record any live VSPreview desktop launch as documented-only unless a local
    runtime proof is actually executed.

Review gate:

- Package-specific read-only plan review before implementation.
- Read-only adversarial implementation review after refactor.

Package-specific audit brief:

- Current code already has explicit typed adapter boundaries:
  `VSPreviewAvailabilityStatus`, `VSPreviewAvailability`,
  `VSPreviewConfig`, and `VSPreviewSessionRequest` live in
  `src/frame_compare/vspreview/adapter.py`.
- Adapter availability probing returns structured statuses and redacted public
  probe-failure details; launch writes the session script, resolves the command,
  runs the process, maps missing launcher/nonzero/probe-failure errors, and owns
  subprocess mechanics.
- `src/frame_compare/services/alignment_vspreview.py` consumes adapter outputs
  and owns alignment-specific optional/forced policy, TTY decisions, prompt
  parsing, confirmed-offset persistence, progress suspension, and optional
  warning versus forced error behavior.
- `src/frame_compare/orchestration/doctor_checks.py` lazily imports the adapter
  inside `_check_vspreview()` and maps adapter availability to optional doctor
  `CheckResult` values.
- Existing tests cover adapter availability statuses, probe-failure redaction,
  launch error mapping, optional and forced alignment behavior, malformed prompt
  input, TTY handling, manual override persistence, and optional doctor
  VSPreview probe handling.
- Proposed closeout stance: no code change unless package-specific review finds
  a material boundary or maintainability issue. Update docs only for the
  `doctor_checks.py` owner correction above.
- Package-specific adversarial review accepted no-code closeout with no P0-P2
  findings. P3 follow-ups were applied by correcting the `doctor_checks.py`
  adapter docstring and adding `tests/orchestration/test_doctor_runner.py` to
  the focused verification command because that file contains the explicit
  optional VSPreview probe-failure assertion.

Rollback:

- Revert adapter/result-shape changes and restore direct existing call flow.

Stop/replan:

- Any user-visible interactive alignment, doctor output, or launch behavior
  would change.
- Local verification requires a VSPreview desktop environment not available in
  the named proof path.

### Package 6: Report/CLI Boundary Audit And Follow-up

Goal:

- Address any residual CLI/report lifecycle coupling discovered by earlier
  packages.

Files in scope:

- `src/frame_compare/cli/entry.py`
- `src/frame_compare/cli/run_command.py`
- `src/frame_compare/services/report/**`
- `src/frame_compare/orchestration/phase_post_render.py`
- relevant CLI/report tests and docs

Out of scope:

- New CLI flags, new report viewer features, new slow.pics behavior, new
  browser/clipboard behavior, and report HTML redesign.

Initial stance:

- Existing report/CLI boundaries appear better split and better covered than the
  central orchestration/alignment hotspots, but this package is still required
  as an audit gate. It may close with no code only after a package-specific
  adversarial review confirms there is no material architecture or
  maintainability concern left in the named report/CLI hotspot surfaces.

Owner seam:

- CLI command parsing, JSON/human output, browser/report-open, clipboard, and
  interactive prompt behavior remain in `cli.entry`, `cli.run_command`, and
  `cli_helpers`.
- Report generation, payload validation, viewer assets, and atomic report write
  behavior remain in `services.report`.
- Orchestration phase lifecycle carries report state but does not own browser or
  clipboard side effects.

Invariants:

- No JSON stdout schema changes.
- Report auto-open and slow.pics browser precedence remain CLI-owned.
- Report service performs no browser, clipboard, or prompt side effects.

Acceptance criteria:

- If earlier packages do not touch report/CLI lifecycle, run a fresh read-only
  adversarial audit of this package scope and adjudicate no-code closeout before
  deferring implementation.
- If touched, update `docs/current-cli-contract.md` and CLI/report tests in the
  same pass.

Verification:

- Mode: `contract-first`.
- Classification: existing coverage sufficient for no-code deferral; new
  contract tests required for any CLI/report behavior change.
- Commands when touched:
  - `.venv/bin/pytest -q tests/cli/test_run_report_open.py tests/cli/test_run_command.py tests/cli/test_run_output.py tests/services/test_report_entry.py tests/services/test_report.py`
  - Full gate before package closeout.

Rollback:

- Revert CLI/report lifecycle changes as a unit.

Stop/replan:

- Browser, clipboard, prompt, JSON, or report output behavior would change
  without explicit contract scope.

Review gate:

- Package-specific read-only audit before implementation or no-code closeout.
- Read-only adversarial implementation review after any refactor.

Package-specific audit closeout:

- Earlier packages did not change report generation, CLI JSON output, report
  auto-open, slow.pics browser precedence, clipboard behavior, or prompt
  behavior.
- Direct owner review confirmed CLI side effects remain injected through
  `RunCommandDeps` in `src/frame_compare/cli/entry.py` and executed only by
  `src/frame_compare/cli/run_command.py`.
- `src/frame_compare/services/report/**` remains limited to report payload,
  rendering, viewer assets, validation, and atomic HTML writes. A side-effect
  search for browser, clipboard, and prompt hooks found no report-service owner
  violations.
- `src/frame_compare/orchestration/phase_post_render.py` carries report state
  and invokes only the typed slow.pics confirmation callback; it does not own
  browser or clipboard effects.
- Package-specific adversarial review reported no P0-P2 findings and accepted
  no-code closeout with `PACKAGE_6_NO_CODE_CLOSEOUT_ACCEPTABLE: yes`.
- Focused verification passed:
  `.venv/bin/pytest -q tests/cli/test_run_report_open.py tests/cli/test_run_command.py tests/cli/test_run_output.py tests/services/test_report_entry.py tests/services/test_report.py`.

## Package Ranking

1. Package 1: central hotspot, strong existing proof, enables later work.
2. Package 1B: completes the broader internal DTO ownership repair after the
   lower-risk applicator seam is stable.
3. Package 2: high production risk and upcoming runtime feature blocker.
4. Package 3: user-visible diagnostic contract, bounded and reviewable.
5. Package 4: high runtime traffic but safer after state contracts stabilize.
6. Package 5: highest external/runtime risk; needs tighter proof.
7. Package 6: required report/CLI audit gate; implementation only if the audit
   finds material remaining coupling.

## Review And Worker Policy

- Before implementation, send this plan to a read-only reviewer and adjudicate
  findings.
- Worker subagents may implement only approved, concrete, disjoint packages with
  exact files in scope and verification commands.
- The main session owns integration, local verification, review adjudication,
  authority doc updates, and final judgment.
- After each major refactor, run a read-only adversarial implementation review
  and adjudicate findings before moving to the next package.

## Full Verification Gate

Required before closing any hotspot package:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Docker/runtime and Windows portable/release gates are not in scope unless a
package intentionally touches those surfaces after reviewed replan.

## Deferral Records

These are not dropped concerns. They are explicit deferrals that must be revisited
before final goal closeout.

| Concern | Owner | Risk | Revisit trigger |
| --- | --- | --- | --- |
| Shared errors facade | `src/frame_compare/errors.py` and focused `error_*` modules | Low current architecture risk because the facade is already split and covered by `tests/test_errors.py` and `tests/test_error_modules.py`; medium blast radius if downstream packages need new error ownership. | Any package changes error classes, error JSON, CLI error mapping, traceback behavior, or service-specific error ownership; otherwise run a final no-code adversarial audit before closing the goal. |
| Docker, Windows portable, dependency, lockfile, build, and packaging surfaces | Runbook-listed owners under Docker files, workflows, `tools/windows_portable/**`, and packaging metadata | High release-path risk if touched; currently out of architecture repair implementation scope because no package proposes changing those surfaces. | Any package requires runtime/release-path changes, dependency updates, lockfile changes, packaging behavior changes, or Docker/Windows proof; otherwise record final documented-only non-touch status before closing the goal. |
| Live VSPreview desktop launch proof | `src/frame_compare/vspreview/adapter.py`, `src/frame_compare/services/alignment_vspreview.py`, and local runtime environment | High runtime-environment risk; automated tests can prove adapter semantics but not a real desktop launch without a compatible environment. | Package 5 changes launch behavior or maintainer provides a compatible local proof path; otherwise record documented-only status and exact unverified surface. |

## Final Closeout Evidence

- Package implementation and audit commits:
  - `af4bc37 refactor: repair orchestration ownership boundaries`
  - `a3df26a refactor: isolate render batch results`
  - `cc3c52f docs: close vspreview boundary audit`
  - `c5a41bc docs: close report cli boundary audit`
- Full verification passed:
  - `.venv/bin/pyright --warnings`
  - `.venv/bin/ruff check .`
  - `.venv/bin/bandit -c pyproject.toml -r src --severity-level medium`
  - `.venv/bin/pytest -q`
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check`
- Final deferral audit:
  - `src/frame_compare/errors.py`, focused error modules, error JSON, CLI error
    mapping, and service-specific error classes were not changed by the
    architecture repair commits; existing facade coverage remains
    `tests/test_errors.py` and `tests/test_error_modules.py`.
  - Docker, Windows portable, dependency, lockfile, build, packaging, release,
    and workflow files were not changed by the architecture repair commits.
  - Package 5 did not change VSPreview launch behavior; live desktop launch proof
    remains documented-only because no compatible local runtime proof path was
    provided or required by the no-code boundary audit.
- Remaining risk:
  - Full pytest skipped environment-gated VapourSynth integration, live slow.pics,
    PowerShell/Windows portable, and Windows process-semantics tests in this
    local environment.
- Final read-only closeout review reported no P0-P2 findings and accepted goal
  closeout with `GOAL_CLOSEOUT_ACCEPTABLE: yes`.
