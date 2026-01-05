---
RUN_ID: 2026-01-03__p6-2__preflight-doctor
VERSION: v1
TARGET: Phase 6 → Item 6.2
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v1.md
---

# Implementation Plan: Preflight & Doctor

## Context

**Phase:** 6.2
**Module:** `frame_compare.orchestration` (preflight.py, doctor.py)
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
**Dependencies:**

- Phase 6.1 (orchestration package scaffold) — COMPLETED
- `frame_compare.config` module — COMPLETED
- `frame_compare.errors` module — COMPLETED
- `frame_compare.utils.progress` module — COMPLETED

## Scope

This plan covers:

- [x] Implement `PreflightResult` dataclass per spec §3.1
- [x] Implement `prepare_preflight(root, config_path) -> PreflightResult` per spec §4.1
- [x] Implement `WorkspacePaths` dataclass (new type needed by PreflightResult)
- [x] Implement `DoctorCheck`, `CheckResult`, `DoctorReport` types per spec §3.2
- [x] Implement `collect_checks() -> list[DoctorCheck]`
- [x] Implement `run_doctor(checks, reporter) -> DoctorReport` per spec §4.2
- [x] Write unit tests for preflight path resolution
- [x] Write unit tests for doctor checks
- [x] Update `orchestration/__init__.py` exports

This plan does NOT cover:

- Phase orchestration (6.7)
- FramePlan module (6.4)
- Tonemap wiring (6.5)
- VSPreview integration (6.6)
- CLI command completion (6.8)
- Full RunResult/RunRequest/execute_run (6.7)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "3.1 Preflight Types"
  - Section: "3.2 Doctor Types"
  - Section: "4.1 Preflight"
  - Section: "4.2 Doctor"
  - Section: "5.1 Path Resolution"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md`:
  - Section: "2.2 Exception Tree"

## Files to Create/Modify

### 1. `src/frame_compare/orchestration/types.py` [NEW]

**Purpose:** Define shared orchestration types (WorkspacePaths).

**Types to define:**

- `WorkspacePaths` — Frozen dataclass holding resolved workspace paths

```python
@dataclass(frozen=True)
class WorkspacePaths:
    """Resolved workspace paths."""
    root: Path
    config_path: Path
    input_dir: Path
    output_dir: Path
    cache_dir: Path
    reports_dir: Path
```

### 2. `src/frame_compare/orchestration/preflight.py` [MODIFY]

**Purpose:** Pre-run validation including config loading and path resolution.

**Types to define:**

- `PreflightResult` — `PreflightResult(config, workspace, warnings)` per spec §3.1

**Functions to implement (spec-anchored):**

- `prepare_preflight(root: Path | None = None, config_path: Path | None = None) -> PreflightResult` — per spec §4.1
- `resolve_workspace(root: Path | None) -> Path` — per spec §5.1
- `resolve_paths(config: ConfigSchema, root: Path) -> WorkspacePaths` — per spec §5.1

**Internal helpers (not in SSOT, implementation detail):**

- Video discovery logic that raises `NoVideosFoundError` when input directory is empty

### 3. `src/frame_compare/orchestration/doctor.py` [MODIFY]

**Purpose:** Diagnostic checks for runtime environment validation.

**Types to define:**

- `CheckResult` — `CheckResult(passed, message, hint, details)` per spec §3.2
- `DoctorCheck` — `DoctorCheck(name, category, check_fn)` per spec §3.2 (uses `Callable[[], CheckResult]`)
- `DoctorReport` — `DoctorReport(checks, all_passed, critical_failures)` per spec §3.2

**Functions to implement (spec-anchored):**

- `collect_checks() -> list[DoctorCheck]` — per spec §4.2
- `run_doctor(checks: list[DoctorCheck] | None = None, reporter: ProgressReporter | None = None) -> DoctorReport` — per spec §4.2

**Internal check implementations (categories per spec §4.2):**

The `collect_checks()` function returns `DoctorCheck` instances for the following categories. Individual check functions are internal implementation details:

- **core:** Python version (>= 3.12), VapourSynth, required plugins (lsmas)
- **optional:** FFmpeg, dovi_tool, vspreview
- **network:** slow.pics reachability, TMDB API key presence

### 4. `src/frame_compare/orchestration/__init__.py` [MODIFY]

**Purpose:** Export public API for orchestration module.

**Exports to add:**

```python
from frame_compare.orchestration.types import WorkspacePaths
from frame_compare.orchestration.preflight import (
    PreflightResult,
    prepare_preflight,
    resolve_workspace,
    resolve_paths,
)
from frame_compare.orchestration.doctor import (
    CheckResult,
    DoctorCheck,
    DoctorReport,
    collect_checks,
    run_doctor,
)

__all__ = [
    "WorkspacePaths",
    "PreflightResult",
    "prepare_preflight",
    "resolve_workspace",
    "resolve_paths",
    "CheckResult",
    "DoctorCheck",
    "DoctorReport",
    "collect_checks",
    "run_doctor",
]
```

### 5. `tests/orchestration/test_preflight.py` [NEW]

**Purpose:** Unit tests for preflight validation.

**Tests required:**

- `test_resolve_workspace_explicit_root` — Given explicit root → returns that path
- `test_resolve_workspace_cwd_with_config` — Given CWD with config.toml → returns CWD
- `test_resolve_workspace_searches_upward` — Given nested dir → searches upward for config.toml
- `test_resolve_workspace_fallback_cwd` — Given no config found → returns CWD
- `test_resolve_paths_expands_home` — Given "~/" in path → expands to home directory
- `test_resolve_paths_relative_to_root` — Given relative paths → resolves relative to root
- `test_prepare_preflight_success` — Given valid config → returns PreflightResult
- `test_prepare_preflight_config_not_found` — Given missing config → raises ConfigNotFoundError
- `test_prepare_preflight_empty_input_dir` — Given empty input dir → raises NoVideosFoundError
- `test_prepare_preflight_adds_warnings` — Given deprecated config → warnings list populated

### 6. `tests/orchestration/test_doctor.py` [NEW]

**Purpose:** Unit tests for diagnostic checks.

**Tests required:**

- `test_check_python_version_passes` — Given Python >= 3.12 → CheckResult(passed=True)
- `test_check_vapoursynth_passes_when_available` — Given VS importable → CheckResult(passed=True)
- `test_check_vapoursynth_fails_when_missing` — Given VS not importable → CheckResult(passed=False)
- `test_check_ffmpeg_passes_when_in_path` — Given ffmpeg in PATH → CheckResult(passed=True)
- `test_check_ffmpeg_fails_when_missing` — Given no ffmpeg → CheckResult(passed=False, hint=...)
- `test_collect_checks_returns_all_categories` — Returns checks with core, optional, network categories
- `test_run_doctor_all_pass` — Given all checks pass → DoctorReport(all_passed=True)
- `test_run_doctor_critical_failure` — Given core check fails → DoctorReport(all_passed=False, critical_failures=[...])
- `test_run_doctor_optional_failure_not_critical` — Given optional check fails → all_passed could be True, no critical_failures
- `test_run_doctor_with_reporter` — Given reporter → calls start_phase, advance, complete_phase

### 7. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2026-01-03__p6-2__preflight-doctor`
- Scope: Preflight and Doctor implementation for Phase 6.2
- SSOT edits: None (spec is sufficient)
- Out of scope: Full runner, CLI integration, phase orchestration
- WorkspacePaths type added (not in original spec but required by PreflightResult)

### 8. `CHANGELOG.md` [MODIFY]

**Purpose:** Add entry for new orchestration features.

**Entry:**

```markdown
### Added
- Preflight validation (`prepare_preflight`) with workspace path resolution
- Doctor diagnostics (`run_doctor`) for environment validation
- WorkspacePaths, PreflightResult, DoctorReport types
```

## Acceptance Criteria

- [ ] GIVEN valid config directory WHEN `prepare_preflight(root)` is called THEN returns PreflightResult with loaded config and resolved paths
- [ ] GIVEN missing config.toml WHEN `prepare_preflight(root)` is called THEN raises ConfigNotFoundError
- [ ] GIVEN empty input directory WHEN `prepare_preflight(root)` is called THEN raises NoVideosFoundError (FC-3002)
- [ ] GIVEN VapourSynth installed WHEN `run_doctor()` is called THEN core checks pass
- [ ] GIVEN VapourSynth missing WHEN `run_doctor()` is called THEN DoctorReport.critical_failures includes "vapoursynth"
- [ ] GIVEN ProgressReporter WHEN `run_doctor(reporter=reporter)` is called THEN reporter methods are invoked

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → **Command Canon**.

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v1.md

# Quality gates
.venv/bin/pyright --warnings src/frame_compare/orchestration
.venv/bin/ruff check src/frame_compare/orchestration tests/orchestration
.venv/bin/pytest -v tests/orchestration

# Import linter
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Contract gates (no contract changes, but verify freshness)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **WorkspacePaths is a new type** — The spec references `WorkspacePaths` in the `resolve_paths` function signature but doesn't define it explicitly. Create it as a frozen dataclass in `orchestration/types.py`.

2. **JSONValue import** — Import `JSONValue` from `frame_compare.errors` for the `CheckResult.details` field.

3. **Check function callables** — `DoctorCheck.check_fn` is `Callable[[], CheckResult]`. Each check is a zero-argument callable that returns a CheckResult.

4. **Critical vs optional failures** — Core category checks that fail should be added to `DoctorReport.critical_failures`. Optional and network checks that fail should NOT be critical.

5. **Network checks are synchronous** — For `check_slowpics()`, use `httpx.Client` (synchronous) with a short timeout (5 seconds). This is acceptable since doctor command is interactive.

6. **Config discovery order** — `resolve_workspace` priority:
   1. Explicit `root` parameter
   2. CWD if `config/config.toml` exists there
   3. Search upward from CWD for `config/config.toml`
   4. Fallback to CWD

7. **Default video patterns** — Use `["*.mkv", "*.mp4", "*.avi", "*.m2ts", "*.ts"]` per spec §4.3.6.

8. **Error classes** — Use existing error classes from `frame_compare.errors`:
   - `ConfigNotFoundError` for missing config.toml
   - `NoVideosFoundError` for empty input directory
   - Do NOT create new error classes

9. **Avoid circular imports** — `orchestration/types.py` should not import from other orchestration submodules.

10. **Test isolation** — Mock external dependencies (VS import, subprocess calls, network) in tests.

---

> **Proposed RUN_ID:** 2026-01-03__p6-2__preflight-doctor
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2026-01-03__p6-2__preflight-doctor` before running Plan Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-03__p6-2__preflight-doctor

## Plan to Review

Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v1.md
