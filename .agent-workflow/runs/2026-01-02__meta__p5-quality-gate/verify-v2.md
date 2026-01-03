---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v2
TARGET: Meta → Phase 5 Quality Gate Fixes
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v1.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v5.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v2.md
---

# Verification Handoff: Phase 5 Quality Gate Fixes

## Summary

**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md
**Plan Review Report:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v5.md (APPROVED)
**Implementation Report:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v1.md

## Implementation Review

### Plan Review Gate

- [x] Plan Review Report exists
- [x] Verdict: APPROVED (plan-review-v5.md)

### Plan Compliance

- [x] Contract views regenerated
- [x] PIL deprecation fix applied to `test_render_pipeline.py`
- [x] `_vs_needs_mock()` implemented in `tests/conftest.py`
- [x] `_vs_spec_available()` implemented in `tests/vs/test_exports.py` and `tests/vs/test_tonemap.py`
- [x] Docker script updated to include `tests/vs/`
- [x] DECISIONS.md updated
- [x] CHANGELOG.md updated
- [ ] Deviations: None from plan; new pre-existing bug exposed (see Issues below)

### Documentation Check

- [x] All public functions have docstrings
- [x] Type hints complete
- [x] Module descriptions present

## Verification Results

### Contract Gates ✅

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

### Quality Gates ✅

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.
```

### Full Test Suite (Local) ✅

```text
$ .venv/bin/pytest -v --cov=src/frame_compare --cov-report=term-missing --cov-fail-under=80

415 passed, 2 skipped in 2.87s
Total coverage: 90.54%
Required test coverage of 80% reached.
```

**Original blockers resolved:**

- ✅ No collection errors (test_exports.py and test_tonemap.py now collect)
- ✅ Coverage > 80% (90.54%)
- ✅ All local tests pass

### Docker Integration ❌

```text
$ bash tools/verify_docker_integration.sh

tests/integration/test_render_orchestrator.py .                          [ 16%]
tests/integration/test_render_pipeline.py ...                            [ 66%]
tests/integration/test_render_vs.py .                                    [ 83%]
tests/vs/test_integration.py F                                           [100%]

FAILED tests/vs/test_integration.py::test_vs_integration_smoke - AttributeError
```

**Original blockers resolved in Docker:**

- ✅ PIL deprecation fixed (test_render_pipeline.py passes 3/3)
- ✅ VS tests now run in Docker (tests/vs/ included)

**New failure exposed:**

```python
# tests/vs/test_integration.py:38
out = tonemap(clip, settings, hdr_metadata=None)

# src/frame_compare/vs/tonemap.py:165
core = clip.std.core  # AttributeError: There is no function named core
```

**Root Cause:** The `apply_tonemap()` function at line 165 tries to access `clip.std.core`, which is not a valid VapourSynth API pattern. The correct approach is to use `vs.core` directly or call `ensure_vs_environment()`.

**Status:** 5 passed, 1 failed (pre-existing bug, NOT introduced by impl-v1)

## Original Blockers Status

| # | Original Issue | Status |
|---|----------------|--------|
| 1 | Contract freshness check failed | ✅ FIXED |
| 2 | Docker integration test failing (PIL) | ✅ FIXED |
| 3 | Test collection errors on macOS | ✅ FIXED |
| 4 | VS tests not in Docker verification | ✅ FIXED |

## New Issue Found

### Issue: VapourSynth API Usage Bug in tonemap.py

**Severity:** BLOCKER (Docker gate fails)
**File:** `src/frame_compare/vs/tonemap.py:165`
**Error:** `AttributeError: There is no function named core`

**Current Code:**

```python
core = clip.std.core  # May raise AttributeError, let it propagate
```

**Required Fix:**

```python
core = vs.core  # Use the vapoursynth module-level core singleton
```

**Note:** This is a **pre-existing bug** in the tonemap module, NOT introduced by impl-v1.md. It was previously hidden because VS integration tests were not running in Docker.

## Checklist Updates

- [ ] NOT updated: Phase 5 Quality Gate items remain unchecked pending Docker gate pass

## Index Updates

- [ ] NOT updated: Cannot append until verification passes

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__meta__p5-quality-gate

## Issue to Fix

Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v2.md
See "New Issue Found" section for the specific failure.

## Required Fix

In `src/frame_compare/vs/tonemap.py`, line 165:

```python
# BEFORE
core = clip.std.core  # May raise AttributeError, let it propagate

# AFTER
core = vs.core  # Use the vapoursynth module-level core singleton
```

## Verification After Fix

```bash
bash tools/verify_docker_integration.sh
```

**Pass criteria:** Exit 0, ALL passed, 0 failed, zero skipped.

## Output

Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v2.md
