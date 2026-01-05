---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v1
TARGET: Meta → Phase 5 Quality Gate Verification
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v1.md
---

# Verification Handoff: Phase 5 Quality Gate

## Summary

**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v1.md
**Type:** Meta verification run (no code implementation)

## Verification Results

### Static Analysis ✅

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.
```

**Status:** PASSED

### Contract Gates ❌

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md differs from generated
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md differs from generated
STALE: docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py differs from generated

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

**Status:** FAILED (contract freshness check has 3 stale files)

### Full Test Suite (Local) ⚠️

```text
$ .venv/bin/pytest -v --cov=src/frame_compare --cov-report=term-missing --cov-fail-under=80
# Initial run: 2 collection errors

ERROR tests/vs/test_exports.py - ValueError: vapoursynth.__spec__ is not set
ERROR tests/vs/test_tonemap.py - ValueError: vapoursynth.__spec__ is not set
```

**Root Cause:** VapourSynth module initialization issue on local macOS. The `importlib.util.find_spec("vapoursynth")` call raises `ValueError` instead of returning `None` when vapoursynth is partially loaded.

**Workaround Run (excluding problematic files):**

```text
$ .venv/bin/pytest -v --ignore=tests/vs/test_exports.py --ignore=tests/vs/test_tonemap.py \
    --cov=src/frame_compare --cov-report=term-missing --cov-fail-under=80

388 passed, 2 skipped in 2.69s
Total coverage: 88.08%
Required test coverage of 80% reached.
```

**Status:** PARTIAL PASS (all tests pass with workaround, 88% coverage)

### Services Tests ✅

```text
$ .venv/bin/pytest -v tests/services/ --cov=src/frame_compare/services

86 passed in 0.67s
Total coverage: 87.77%
```

**Status:** PASSED

### Docker Integration ❌

```text
$ bash tools/verify_docker_integration.sh

tests/integration/test_render_pipeline.py .F.

FAILED tests/integration/test_render_pipeline.py::test_overlay_application_adds_visible_content

Error: DeprecationWarning: Image.Image.getdata is deprecated and will be removed in Pillow 14 (2027-10-15). Use get_flattened_data instead.

1 failed, 4 passed in 1.03s
ERROR: docker integration tests failed (exit 1)
```

**Status:** FAILED (PIL deprecation warning raised as error in Docker container)

## Phase 5 Quality Gate Items Status

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Audio alignment calculates offsets | ✅ | 23 tests pass in `test_alignment.py` |
| 2 | Metadata parses filenames | ✅ | 18 tests pass in `test_metadata.py` |
| 3 | slow.pics uploads work | ✅ | 14 tests pass in `test_publishers.py` (mocked) |
| 4 | HTML report generates | ✅ | 31 tests pass in `test_report.py` |
| 5 | All services have error recovery | ✅ | Error handling patterns tested |
| 6 | Docker verification passes | ❌ | 1 PIL deprecation failure |
| 7 | Test coverage > 80% and ALL tests pass | ⚠️ | 88% coverage, but collection errors and Docker failure |

## Issues Found (BLOCKERS)

### Issue 1: Contract Freshness Check Failed

**Severity:** BLOCKER
**Stale files:**

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py`

**Required Fix:**

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py
```

### Issue 2: Docker Integration Test Failing

**Severity:** BLOCKER
**Failed Test:** `test_overlay_application_adds_visible_content`
**Root Cause:** The test uses `Image.getdata()` which is deprecated in Pillow 14 and raises a `DeprecationWarning` that's treated as an error.

**Required Fix:** Update test to use `Image.get_flattened_data()` instead.

**File:** `tests/integration/test_render_pipeline.py:58`

### Issue 3: Test Collection Errors (Local Environment)

**Severity:** MEDIUM (not blocking if Docker tests pass)
**Affected Files:**

- `tests/vs/test_exports.py`
- `tests/vs/test_tonemap.py`

**Root Cause:** `importlib.util.find_spec("vapoursynth")` raises `ValueError: vapoursynth.__spec__ is not set` on macOS where VapourSynth is partially initialized via stub package.

**Required Fix:** Wrap the `find_spec` call in try/except to catch `ValueError`.

## Verification Failed

**Two BLOCKERS identified:**

1. Contract freshness check failed (3 stale files)
2. Docker integration test failed (PIL deprecation)

## Checklist Updates

- [ ] NOT updated: Phase 5 Quality Gate items remain unchecked pending fixes

## Index Updates

- [ ] NOT updated: Cannot append until verification passes

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__meta__p5-quality-gate

## Issues to Fix

Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v1.md

See "Issues Found (BLOCKERS)" section for the specific failures.

## Required Fixes

### Fix 1: Regenerate Contract Views

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
```

### Fix 2: Update PIL Test Method

In `tests/integration/test_render_pipeline.py:58`:

- Replace `result.getdata()` with `result.get_flattened_data()`

### Fix 3 (Optional): Fix Test Collection Errors

In `tests/vs/test_exports.py` and `tests/vs/test_tonemap.py`:

- Wrap `importlib.util.find_spec("vapoursynth")` in try/except to catch `ValueError`

## Verification After Fixes

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
bash tools/verify_docker_integration.sh
.venv/bin/pytest -v --cov=src/frame_compare --cov-fail-under=80
```

## Output

Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v1.md
