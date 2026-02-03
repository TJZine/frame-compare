---
RUN_ID: 2026-02-03__p6-7-11__phase-orchestration-4-4-4
VERSION: v1
TARGET: Phase 6 → Item 6.7 Runner & Phase Orchestration — Implement phase orchestration per spec §4.4.4
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v1.md
---

# Implementation Plan: Phase Orchestration (Phase Ordering §4.4.4)

## Context
**Phase:** 6 (CLI & Orchestration)
**Module:** `frame_compare.orchestration`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` (§4.4.4, §5.2)
**Dependencies:** Existing scaffolding in `src/frame_compare/orchestration/` (preflight, context, probe_cache, progress, coordinator types)

## Contract Impact
**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "3.4 Phase Types"
  - Section: "4.4.3 Execute Function"
  - Section: "4.4.4 Phase Ordering (SSOT)"
  - Section: "5.2 Phase Execution"
  - Section: "6. Error Handling"

## Scope

This plan covers:

- [ ] Implement canonical phase primitives (`PhaseStatus`, `Phase`) in `orchestration/phases.py`
- [ ] Implement `execute_phases(...)` with SSOT skip + failure semantics and progress reporting hooks
- [ ] Wire `execute_run(...)` to:
  - [ ] Execute Phase 1 (Preflight) (fail-fast)
  - [ ] Execute Phase 2 (LoadSources) as a dedicated step that builds a `RunContext` from the workspace inputs (fail-fast)
  - [ ] Execute Phases 3–10 via `execute_phases(...)` in the exact SSOT order, with correct skip conditions and failure policy
  - [ ] Record deterministic phase timings in `RunResult.phase_timings`
- [ ] Add unit tests covering ordering + skip + warn-only + fail-fast behavior (no network / no VS / no FFmpeg required)

This plan does NOT cover:

- Consolidated FPS diagnostics (`orchestration-module.md` §5.4)
- Real implementations of Analyze/Align/Render/Metadata/Dovi/Publish/Report phase bodies (this slice wires ordering + semantics; later slices can replace phase bodies with real work)
- Docker integration gate or integration tests

## Files to Create/Modify

### 1. [MODIFY] `src/frame_compare/orchestration/phases.py`

**Purpose:** Define canonical phase types and the phase execution loop.

**Types to define:**
- `PhaseStatus` — Enum of canonical statuses (`pending`, `running`, `completed`, `skipped`, `warned`, `failed`)
- `Phase` — Dataclass representing a single phase (name, execute, optional skip_condition, status)

**Functions to implement (spec-anchored):**

- `async def execute_phases(phases: list[Phase], context: RunContext, reporter: ProgressReporter) -> None`

**Key implementation notes:**

- Ordering is defined by the list passed in (coordinator owns ordering per §4.4.4).
- Skip evaluation:
  - If `phase.skip_condition is not None` and returns True, set `status=SKIPPED` and continue.
  - Skip conditions are permitted to be closures that capture `RunRequest` values even though the callable receives `ConfigSchema`.
- Failure policy:
  - **Fail-fast** phases: any exception marks `FAILED` and is re-raised (stopping the pipeline).
  - **Warn-only** phases: any exception marks `WARNED` and execution continues.
  - Classification rule (decision-minimizing and consistent with §4.4.4 table): phases with `skip_condition is None` are treated as fail-fast; phases with `skip_condition is not None` are treated as warn-only.
- Progress reporting:
  - Call `reporter.start_phase(phase.name, total=1)` when a phase begins execution.
  - Call `reporter.advance(1)` on successful completion.
  - Call `reporter.complete_phase()` in a `finally` block for each phase that was started.

### 2. [MODIFY] `src/frame_compare/orchestration/coordinator.py`

**Purpose:** Orchestrate phases in the SSOT order and record timings.

**Functions to implement (spec-anchored):**

- `async def execute_run(request: RunRequest, deps: RunDependencies | None = None) -> RunResult`

**Key implementation notes:**

- Phase 1 (Preflight):
  - Run `prepare_preflight(root=request.root, config_path=request.config_path)` (fail-fast, existing behavior).
  - Record timing under key `"preflight"`.
  - Aggregate any `preflight.warnings` into `RunResult.warnings`.
- Phase 2 (LoadSources):
  - Discover the input video list using the same stable ordering rules already used in preflight (case-insensitive filename ordering).
  - Compute `ClipFingerprint` via `Path.stat()` (path, size_bytes, mtime_ns).
  - Use `compute_probe_cache_key(...)`, `load_clip_probe_cache(...)`, and `save_clip_probe_cache(...)` to reuse and persist `ClipProbeSnapshot` in `{workspace.generated_dir}/clip_probe.toml`.
  - Probe missing/stale entries using `deps.get_vs_loader().load(path)` and derive:
    - `ClipProbeSnapshot.width/height/num_frames/fps/is_hdr/hdr_metadata`
    - `tonemap_prop_keys` via `compute_tonemap_prop_keys(source_info.frame_props)`
    - `preserved_frame_props` via `compute_preserved_frame_props(source_info.frame_props)`
  - Build `ClipState` objects:
    - `source_fps = probe.fps`
    - `effective_fps = probe.fps` (no overrides in this slice)
    - `label`: `"Reference"` for first clip, `"Encode 1"`, `"Encode 2"`, ... for comparisons
  - Build `RunContext(config=preflight.config, workspace=preflight.workspace, reference=..., comparisons=..., reporter=deps.progress)`
  - Record timing under key `"load_sources"`.
- Phases 3–10 (Ordering + Semantics):
  - Create a `list[Phase]` in this exact order and execute via `execute_phases(...)`:
    1) FramePlan (required / fail-fast)
    2) Analyze (optional / skip when `request.skip_analysis`)
    3) Align (optional / warn-only in this slice)
    4) Render (required / fail-fast)
    5) Metadata (optional / skip when `request.skip_metadata`)
    6) Dovi (optional / skip when `request.skip_dovi`)
    7) Publish (optional / skip when `request.no_upload`)
    8) Report (optional / skip when `preflight.config.report.enable == False`)
  - For this slice, phase bodies may be no-op async functions; the orchestration correctness is enforced via tests (ordering, skip, warn-only, fail-fast).
- Timings:
  - Record timings for phases 3–10 using deterministic keys (e.g., `"frame_plan"`, `"analyze"`, `"align"`, `"render"`, `"metadata"`, `"dovi"`, `"publish"`, `"report"`).
  - Skipped phases MUST set a timing entry of `0.0` (deterministic presence across runs).

### 3. [NEW] `tests/orchestration/test_phases.py`

**Purpose:** Unit tests for `execute_phases(...)` ordering + semantics (no external deps).

**Tests required:**

- `test_execute_phases_runs_in_order_and_marks_completed()`
- `test_execute_phases_skips_when_skip_condition_true()`
- `test_execute_phases_warn_only_failure_marks_warned_and_continues()`
- `test_execute_phases_fail_fast_failure_marks_failed_and_raises()`

### 4. [MODIFY] `tests/orchestration/test_execute_run.py`

**Purpose:** Update orchestration entry-point tests to account for phase ordering + LoadSources wiring.

**Tests required (minimum updates):**

- Keep: `test_execute_run_returns_success_and_records_preflight_timing()` but update expectations:
  - `phase_timings` contains `"preflight"` and `"load_sources"` and the phase keys for 3–10 (with `0.0` where skipped).
- Keep: `test_execute_run_propagates_config_not_found_error()` (still fail-fast in Preflight).
- Keep: `test_execute_run_creates_and_closes_http_client_when_missing()` (ensure behavior unchanged).

**Test harness notes:**

- Inject a fake `VSLoader` via `RunDependencies(vs_loader=...)` so LoadSources can probe without VapourSynth.
- Create a minimal `SourceInfo` object with:
  - `fps=Fraction(24, 1)`
  - `frame_props` containing minimal keys used by `compute_tonemap_prop_keys(...)` / `compute_preserved_frame_props(...)`

## Acceptance Criteria

- [ ] GIVEN a phase list in the §4.4.4 order WHEN `execute_phases(...)` runs THEN phases execute strictly in order and end in `COMPLETED` when successful.
- [ ] GIVEN a phase with a skip condition that evaluates True WHEN executed THEN status is `SKIPPED`, phase body is not called, and subsequent phases still run.
- [ ] GIVEN an optional (warn-only) phase that raises an exception WHEN executed THEN status is `WARNED`, the exception is logged/recorded as a warning, and subsequent phases still run.
- [ ] GIVEN a required (fail-fast) phase that raises an exception WHEN executed THEN status is `FAILED` and the pipeline stops immediately (exception propagated).
- [ ] GIVEN `execute_run(...)` with a valid workspace and injected VSLoader WHEN executed THEN:
  - `RunResult.success is True`
  - `RunResult.phase_timings` includes deterministic keys for Phase 1–10 (skipped phases have `0.0`)

## Verification Commands

```bash
# Plan artifact validation (must pass before implementation)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v1.md

# Quality gates (targeted)
.venv/bin/pyright --warnings src/frame_compare/orchestration tests/orchestration
.venv/bin/ruff check src/frame_compare/orchestration tests/orchestration
.venv/bin/pytest -q tests/orchestration

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Contract + traceability gates (no changes expected)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Signature bullets:** Only use `- `...(...)...`` signature bullets in “Functions to implement” sections (validator treats them as planned signatures).
2. **Skip-condition closures:** It is acceptable for skip conditions to close over `RunRequest` flags while accepting `ConfigSchema` as the parameter type.
3. **Timings determinism:** Always include all phase timing keys 1–10; set `0.0` for skipped phases.
4. **No external deps in unit tests:** All unit tests in `tests/orchestration/` must run without VapourSynth/FFmpeg/network; inject fakes/mocks at module boundaries.
5. **STOP rule:** If the SSOT implies additional required data in `RunContext` (e.g., frame plans stored on context), STOP and return to Planning for an updated plan rather than guessing.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-02-03__p6-7-11__phase-orchestration-4-4-4

## Plan to Review

Read file: .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-review-v1.md
