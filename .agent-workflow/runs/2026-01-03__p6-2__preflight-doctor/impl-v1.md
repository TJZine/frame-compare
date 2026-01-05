---
RUN_ID: 2026-01-03__p6-2__preflight-doctor
VERSION: v1
TARGET: Phase 6 → Item 6.2
INPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v1.md
  - src/frame_compare/orchestration/preflight.py
  - src/frame_compare/orchestration/doctor.py
  - src/frame_compare/orchestration/__init__.py
  - src/frame_compare/utils/types.py
  - src/frame_compare/utils/__init__.py
  - src/frame_compare/errors.py
  - tests/orchestration/test_preflight.py
  - tests/orchestration/test_doctor.py
  - docs/DECISIONS.md
  - CHANGELOG.md
---

# Implementation Report: Preflight & Doctor

## Summary

**Date:** 2026-01-03
**Plan Reference:** `.agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md`
**Total Files Modified/Created:** 11

## Implementation Overview

### Types Created

| Type | Location | Description |
|------|----------|-------------|
| `WorkspacePaths` | `utils/types.py` | Frozen dataclass with resolved paths + computed `cache_dir`/`probe_cache_dir` |
| `PreflightResult` | `orchestration/preflight.py` | Result of preflight validation (config, workspace, warnings) |
| `CheckResult` | `orchestration/doctor.py` | Individual check result (passed, message, hint, details) |
| `DoctorCheck` | `orchestration/doctor.py` | Check definition (name, category, check_fn) |
| `DoctorReport` | `orchestration/doctor.py` | Complete report (checks, all_passed, critical_failures) |

### Functions Implemented

| Function | Location | Description |
|----------|----------|-------------|
| `resolve_workspace(root)` | `preflight.py` | 4-priority workspace discovery |
| `resolve_paths(config, root, config_file)` | `preflight.py` | Env var expansion + path resolution |
| `prepare_preflight(root, config_path)` | `preflight.py` | Full preflight validation |
| `collect_checks()` | `doctor.py` | Returns 8 checks in SSOT order |
| `run_doctor(checks, reporter)` | `doctor.py` | Executes checks with progress reporting |

### Doctor Checks (Deterministic Order per SSOT §4.2.1)

1. `python_version` (core) — Python >= 3.13
2. `vapoursynth` (core) — VS module available
3. `lsmas` (core) — L-SMASH-Works plugin
4. `ffmpeg` (optional) — FFmpeg in PATH
5. `dovi_tool` (optional) — dovi_tool in PATH
6. `vspreview` (optional) — VSPreview module
7. `slowpics` (network) — HEAD <https://slow.pics/>, timeout 5.0s
8. `tmdb_api_key` (network) — Env var check only

### Modified Errors

**`NoVideosFoundError`** (FC-3001):

- Constructor: `(path: Path, patterns: list[str] | None = None)`
- Instance attributes: `self.path`, `self.patterns`
- Details include patterns for introspection

## Files Changed (Exact Paths)

### Created

- `src/frame_compare/utils/types.py` — WorkspacePaths dataclass
- `tests/orchestration/test_preflight.py` — 12 unit tests
- `tests/orchestration/test_doctor.py` — 15 unit tests

### Modified

- `src/frame_compare/errors.py` — NoVideosFoundError signature
- `src/frame_compare/utils/__init__.py` — Export WorkspacePaths
- `src/frame_compare/orchestration/preflight.py` — Full implementation
- `src/frame_compare/orchestration/doctor.py` — Full implementation
- `src/frame_compare/orchestration/__init__.py` — Public API exports
- `docs/DECISIONS.md` — Phase 6.2 decision entry
- `CHANGELOG.md` — Phase 6.2 changelog entry

## Implementation Notes

**Deviations from plan:** NONE. All implementations match plan-v4.md exactly.

**Key decisions (from SSOT):**

- Workspace discovery uses `config/config.toml` sentinel
- Input patterns: `["*.mkv", "*.mp4", "*.avi", "*.m2ts", "*.ts"]`
- Stable ordering: case-insensitive lexicographic by filename
- DoctorReport.all_passed is False if ANY check fails
- DoctorReport.critical_failures contains core failures only

## Local Sanity Checks

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest -q
427 passed, 2 skipped

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.
```

## Checklist Item Implemented

> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] 6.2 Preflight validation (`prepare_preflight`) + Doctor diagnostics (`run_doctor`)

## Open Questions

- None

## Ready for Verification

All plan items implemented and local gates pass.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID

2026-01-03__p6-2__preflight-doctor

## Files to Read

1. Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/impl-v1.md
2. Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md

## Your Task

1. Verify the implementation matches the plan
2. Run the full verification suite
3. Update the master checklist and run index

## Output

Write file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/verify-v1.md
