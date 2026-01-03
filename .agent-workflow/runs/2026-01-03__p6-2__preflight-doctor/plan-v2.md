---
RUN_ID: 2026-01-03__p6-2__preflight-doctor
VERSION: v2
TARGET: Phase 6 → Item 6.2
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/001-language-runtime.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v2.md
---

# Implementation Plan: Preflight & Doctor

## Changes Since plan-v1

- **Fixed WorkspacePaths location**: Moved from `orchestration/types.py` to `utils/types.py` per SSOT (`utils-module.md` §3.1)
- **Added Spec Anchor**: `utils-module.md` §3.1 for WorkspacePaths fields
- **Added Spec Anchor**: ADR-001 → "Decision" for Python 3.13+ requirement
- **Fixed error code**: Updated acceptance criteria from FC-3002 to FC-3001 (matches SSOT fix)
- **Fixed Python version**: Changed from 3.12 to 3.13+ per ADR-001
- **Fixed config sentinel**: Changed from `config.toml` to `config/config.toml`
- **Fixed DoctorReport semantics**: Made `all_passed` and `critical_failures` semantics explicit
- **Fixed verification commands**: Now uses exact canon commands from workflow
- **Removed deprecated-config test** (undefined behavior, out of scope)
- **Added utils/**init**.py update** to export WorkspacePaths

## Context

**Phase:** 6.2
**Module:** `frame_compare.orchestration` (preflight.py, doctor.py), `frame_compare.utils` (types.py)
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
**Dependencies:**

- Phase 6.1 (orchestration package scaffold) — COMPLETED
- `frame_compare.config` module — COMPLETED
- `frame_compare.errors` module — COMPLETED
- `frame_compare.utils.progress` module — COMPLETED

## Scope

This plan covers:

- [ ] Create `WorkspacePaths` dataclass per `utils-module.md` §3.1
- [ ] Implement `PreflightResult` dataclass per orchestration spec §3.1
- [ ] Implement `prepare_preflight(root, config_path) -> PreflightResult` per spec §4.1
- [ ] Implement `DoctorCheck`, `CheckResult`, `DoctorReport` types per spec §3.2
- [ ] Implement `collect_checks() -> list[DoctorCheck]` per spec §4.2
- [ ] Implement `run_doctor(checks, reporter) -> DoctorReport` per spec §4.2
- [ ] Write unit tests for preflight path resolution
- [ ] Write unit tests for doctor checks
- [ ] Update `orchestration/__init__.py` exports
- [ ] Update `utils/__init__.py` to export WorkspacePaths

This plan does NOT cover:

- Phase orchestration (6.7)
- FramePlan module (6.4)
- Tonemap wiring (6.5)
- VSPreview integration (6.6)
- CLI command completion (6.8)
- Full RunResult/RunRequest/execute_run (6.7)
- Deprecated config detection/warnings (undefined SSOT behavior)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "3.1 Preflight Types"
  - Section: "3.2 Doctor Types"
  - Section: "4.1 Preflight"
  - Section: "4.2 Doctor"
  - Section: "5.1 Path Resolution"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md`:
  - Section: "3.1 WorkspacePaths"

- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/001-language-runtime.md`:
  - Section: "Decision"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md`:
  - Section: "2.2 Exception Tree"

## Files to Create/Modify

### 1. `src/frame_compare/utils/types.py` [NEW]

**Purpose:** Define shared utility types per `utils-module.md` §3.1.

**Types to define:**

- `WorkspacePaths` — Frozen dataclass per SSOT with fields: `root`, `input_dir`, `screenshots_dir`, `generated_dir`, `config_dir`, `config_file`, and computed properties `cache_dir`, `probe_cache_dir`

The exact shape is defined in `utils-module.md` §3.1 — copy verbatim.

### 2. `src/frame_compare/utils/__init__.py` [MODIFY]

**Purpose:** Export WorkspacePaths from utils.

**Exports to add:**

```python
from frame_compare.utils.types import WorkspacePaths

# Add to __all__:
"WorkspacePaths",
```

### 3. `src/frame_compare/orchestration/preflight.py` [MODIFY]

**Purpose:** Pre-run validation including config loading and path resolution.

**Types to define:**

- `PreflightResult` — `PreflightResult(config, workspace, warnings)` per spec §3.1

**Functions to implement (spec-anchored):**

- `prepare_preflight(root: Path | None = None, config_path: Path | None = None) -> PreflightResult` — per spec §4.1
- `resolve_workspace(root: Path | None) -> Path` — per spec §5.1
- `resolve_paths(config: ConfigSchema, root: Path) -> WorkspacePaths` — per spec §5.1

**Implementation requirements:**

- Import `WorkspacePaths` from `frame_compare.utils.types`
- `resolve_workspace` priority: (1) explicit root, (2) CWD if `config/config.toml` exists, (3) search upward for `config/config.toml`, (4) fallback to CWD
- `resolve_paths` builds `WorkspacePaths` from `ConfigSchema.paths` fields (`input_dir`, `screenshots_dir`, `generated_dir`, `config_dir`) with `config_file` set to the loaded config path
- Video discovery raises `NoVideosFoundError(directory)` (existing constructor, FC-3001) when no videos match patterns

### 4. `src/frame_compare/orchestration/doctor.py` [MODIFY]

**Purpose:** Diagnostic checks for runtime environment validation.

**Types to define:**

- `CheckResult` — `CheckResult(passed, message, hint, details)` per spec §3.2
- `DoctorCheck` — `DoctorCheck(name, category, check_fn)` per spec §3.2 (uses `Callable[[], CheckResult]`)
- `DoctorReport` — `DoctorReport(checks, all_passed, critical_failures)` per spec §3.2

**Functions to implement (spec-anchored):**

- `collect_checks() -> list[DoctorCheck]` — per spec §4.2
- `run_doctor(checks: list[DoctorCheck] | None = None, reporter: ProgressReporter | None = None) -> DoctorReport` — per spec §4.2

**DoctorReport semantics (deterministic):**

- `all_passed`: `True` if and only if **all** checks passed (regardless of category)
- `critical_failures`: List of `DoctorCheck.name` values for **failed core category checks only**

**Internal check implementations (categories per spec §4.2):**

- **core:** Python version (>= 3.13, per ADR-001), VapourSynth, required plugins (lsmas)
- **optional:** FFmpeg, dovi_tool, vspreview
- **network:** slow.pics reachability (HEAD request, 5s timeout), TMDB API key presence (env var check only)

**Reporter integration:**

- `run_doctor` calls `reporter.start_phase("doctor", total=len(checks))` at start
- Calls `reporter.advance(1)` after each check completes
- Calls `reporter.complete_phase()` at end

### 5. `src/frame_compare/orchestration/__init__.py` [MODIFY]

**Purpose:** Export public API for orchestration module.

**Exports to add:**

```python
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

Note: `WorkspacePaths` is exported from `frame_compare.utils`, not orchestration.

### 6. `tests/orchestration/test_preflight.py` [NEW]

**Purpose:** Unit tests for preflight validation.

**Tests required (with deterministic fixtures):**

- `test_resolve_workspace_explicit_root` — Given explicit `root=tmp_path` → returns `tmp_path`
- `test_resolve_workspace_cwd_with_config` — Given `tmp_path/config/config.toml` exists and `monkeypatch.chdir(tmp_path)` → returns `tmp_path`
- `test_resolve_workspace_searches_upward` — Given `tmp_path/config/config.toml` exists and `monkeypatch.chdir(tmp_path / "subdir")` → returns `tmp_path`
- `test_resolve_workspace_fallback_cwd` — Given no config found and `monkeypatch.chdir(tmp_path)` → returns `tmp_path`
- `test_resolve_paths_relative_to_root` — Given config with relative paths → resolves relative to root
- `test_prepare_preflight_success` — Given valid config dir with video files → returns `PreflightResult` with loaded config
- `test_prepare_preflight_config_not_found` — Given missing `config/config.toml` → raises `ConfigNotFoundError`
- `test_prepare_preflight_empty_input_dir` — Given empty input dir → raises `NoVideosFoundError`

**Fixture setup:**

- Use `tmp_path` for all filesystem tests
- Create `config/config.toml` with minimal valid TOML
- Create dummy video files (empty `.mkv` files) for success tests

### 7. `tests/orchestration/test_doctor.py` [NEW]

**Purpose:** Unit tests for diagnostic checks.

**Tests required:**

- `test_check_python_version_passes` — Mock `sys.version_info` to `(3, 13, 0)` → `CheckResult(passed=True)`
- `test_check_python_version_fails` — Mock `sys.version_info` to `(3, 12, 0)` → `CheckResult(passed=False, hint="...")`
- `test_check_vapoursynth_passes_when_available` — Mock successful VS import → `CheckResult(passed=True)`
- `test_check_vapoursynth_fails_when_missing` — Mock `ImportError` on VS import → `CheckResult(passed=False)`
- `test_check_ffmpeg_passes_when_in_path` — Mock `shutil.which("ffmpeg")` returns path → `CheckResult(passed=True)`
- `test_check_ffmpeg_fails_when_missing` — Mock `shutil.which("ffmpeg")` returns `None` → `CheckResult(passed=False)`
- `test_collect_checks_returns_all_categories` — `collect_checks()` returns checks with "core", "optional", "network" categories
- `test_run_doctor_all_pass` — Given all mocked checks pass → `DoctorReport(all_passed=True, critical_failures=[])`
- `test_run_doctor_core_failure` — Given "python_version" check fails → `DoctorReport(all_passed=False, critical_failures=["python_version"])`
- `test_run_doctor_optional_failure_not_critical` — Given "ffmpeg" check fails but core passes → `DoctorReport(all_passed=False, critical_failures=[])`
- `test_run_doctor_with_reporter` — Given mock `ProgressReporter` → asserts `start_phase`, `advance`, `complete_phase` called

### 8. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2026-01-03__p6-2__preflight-doctor`
- Scope: Preflight and Doctor implementation for Phase 6.2
- SSOT edits: Fixed FC-3002 → FC-3001 in orchestration-module.md §4.3.6
- Out of scope: Full runner, CLI integration, phase orchestration, deprecated config warnings
- WorkspacePaths created in `utils/types.py` per existing SSOT (`utils-module.md` §3.1)

### 9. `CHANGELOG.md` [MODIFY]

**Purpose:** Add entry for new orchestration features.

**Entry:**

```markdown
### Added
- Preflight validation (`prepare_preflight`) with workspace path resolution
- Doctor diagnostics (`run_doctor`) for environment validation
- WorkspacePaths type in `frame_compare.utils`
- PreflightResult, DoctorCheck, CheckResult, DoctorReport types
```

## Acceptance Criteria

- [ ] GIVEN valid config directory with videos WHEN `prepare_preflight(root)` called THEN returns `PreflightResult` with loaded config and resolved `WorkspacePaths`
- [ ] GIVEN missing `config/config.toml` WHEN `prepare_preflight(root)` called THEN raises `ConfigNotFoundError`
- [ ] GIVEN empty input directory WHEN `prepare_preflight(root)` called THEN raises `NoVideosFoundError` (FC-3001)
- [ ] GIVEN Python 3.13+ WHEN `run_doctor()` called THEN python_version check passes
- [ ] GIVEN Python < 3.13 WHEN `run_doctor()` called THEN `DoctorReport.critical_failures` includes "python_version"
- [ ] GIVEN VapourSynth missing WHEN `run_doctor()` called THEN `DoctorReport.critical_failures` includes "vapoursynth"
- [ ] GIVEN optional check (ffmpeg) fails WHEN `run_doctor()` called THEN `DoctorReport.all_passed=False` but `critical_failures` excludes "ffmpeg"
- [ ] GIVEN `ProgressReporter` WHEN `run_doctor(reporter=reporter)` called THEN reporter methods are invoked with correct sequence

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → **Command Canon**.

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v2.md

# Quality gates (exact canon)
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q

# Import linter
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Contract gates
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **WorkspacePaths location** — Create in `utils/types.py` (not orchestration). Copy exact shape from `utils-module.md` §3.1 including `cache_dir` and `probe_cache_dir` computed properties.

2. **Python version check** — Must check for 3.13+ (not 3.12) per ADR-001 "Decision" section.

3. **Config sentinel path** — Use `config/config.toml` (not `config.toml`) for workspace discovery.

4. **NoVideosFoundError** — Use existing constructor signature `NoVideosFoundError(directory: Path)`. Do not add `patterns` parameter.

5. **DoctorReport.all_passed** — Is `False` if **any** check fails (core, optional, or network). Is `True` only if all pass.

6. **DoctorReport.critical_failures** — Contains `DoctorCheck.name` strings for failed **core** category checks only.

7. **JSONValue import** — Import `JSONValue` from `frame_compare.errors` for `CheckResult.details` field.

8. **Check function callables** — `DoctorCheck.check_fn` is `Callable[[], CheckResult]`. Each check is a zero-argument callable.

9. **Network checks** — Use `httpx.Client` (synchronous) with 5 second timeout. TMDB check only verifies `TMDB_API_KEY` env var is set (no network call).

10. **Test determinism** — All tests use `tmp_path` fixture for filesystem, `monkeypatch` for environment/cwd, and mocks for external dependencies.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-03__p6-2__preflight-doctor

## Plan to Review

Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/001-language-runtime.md
5. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v2.md
