---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v4
TARGET: Meta → Phase 5 Quality Gate Fixes (Docker-first)
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v3.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v12.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v4.md
---

# Verification Handoff: Phase 5 Quality Gate Fixes (Docker-first)

## Summary

**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md
**Plan Review Report:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v12.md (APPROVED)
**Implementation Report:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v3.md

## Implementation Review

### Plan Review Gate

- [x] Plan Review Report exists
- [x] Verdict: APPROVED (plan-review-v12.md)

### Plan Compliance (Files Modified)

- [x] `Dockerfile` — Vulkan enabled
- [x] `src/frame_compare/vs/tonemap.py` — RGB48 conversion + fallback pattern
- [x] `tests/vs/test_tonemap.py` — Fallback test added
- [x] `tests/vs/test_integration.py` — libplacebo Docker test added
- [x] `tools/verify_docker_integration.sh` — Marker filter removed
- [x] `docs/DECISIONS.md` — Updated
- [x] `CHANGELOG.md` — Updated

## Verification Results

### Quality Gates ✅

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.
```

### Contract Gates ✅

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

### Full Test Suite (Local) ✅

```text
$ .venv/bin/pytest -v --cov=src/frame_compare --cov-fail-under=80

415 passed, 2 skipped in 2.60s
Total coverage: 90.30%
```

### Docker Integration ❌

```text
$ bash tools/verify_docker_integration.sh

2 failed, 73 passed, 3 errors in 1.13s
ERROR: docker integration tests failed (exit 1)
```

**Errors (3):**

```
tests/vs/test_env.py::test_is_vapoursynth_available_no_vs_returns_false
tests/vs/test_env.py::test_ensure_vs_environment_missing_vs_raises_not_found_error
tests/vs/test_env.py::test_ensure_vs_environment_core_failure_raises_vs_error

fixture 'mocker' not found
```

**Root Cause:** `pytest-mock` is not installed in Docker (only available locally via dev dependencies).

**Failures (2):**

#### Failure 1: test_vs_integration_smoke

```
vapoursynth.Error: Resize error 1026: RGB color family cannot have YUV matrix coefficients
```

**Root Cause:** The `_apply_libplacebo` function uses `clip.resize.Bicubic(format=vs.RGB48, matrix_in_s="709")` which is invalid for RGB input (RGB clips don't have YUV matrix).

#### Failure 2: test_libplacebo_tonemap_succeeds_in_docker

```
Found no suitable device, giving up.
Failed initializing vulkan device
Failed creating vulkan context
```

**Root Cause:** Mesa lavapipe Vulkan driver is not functioning. Either:

1. Vulkan packages not properly installed
2. Lavapipe requires additional configuration
3. Container architecture mismatch

## Issues Found (BLOCKERS)

### Issue 1: pytest-mock Missing in Docker

**Severity:** ERROR (3 tests cannot run)
**Required Fix:** Add `pytest-mock` to the pip install in Dockerfile runtime stage.

### Issue 2: RGB48 Conversion Uses Invalid matrix_in_s

**Severity:** BLOCKER
**File:** `src/frame_compare/vs/tonemap.py:137`

**Current Code:**

```python
clip = clip.resize.Bicubic(format=vs.RGB48, matrix_in_s="709")
```

**Required Fix:** Remove `matrix_in_s` — it's only valid for YUV input:

```python
clip = clip.resize.Bicubic(format=vs.RGB48)
```

### Issue 3: Vulkan Backend Not Working in Docker

**Severity:** BLOCKER
**Error:** "Found no suitable device, giving up"

**Possible Fixes:**

1. Set `VK_ICD_FILENAMES` environment variable (despite plan saying not to)
2. Ensure `mesa-vulkan-drivers` is properly installed and ldconfig ran
3. Use software renderer explicitly: `LIBGL_ALWAYS_SOFTWARE=1`
4. Consider if libplacebo can work without Vulkan (use OpenGL or CPU fallback)

## Checklist Updates

- [ ] NOT updated: Phase 5 Quality Gate items remain unchecked pending Docker gate pass

## Index Updates

- [ ] NOT updated: Cannot append until verification passes

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__meta__p5-quality-gate

## Issues to Fix

Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v4.md
See "Issues Found (BLOCKERS)" section for details.

## Required Fixes

### Fix 1: Add pytest-mock to Docker

In `Dockerfile`, add `pytest-mock` to the pip install:

```dockerfile
RUN pip install --no-cache-dir --user -e .[dev] pytest-mock
```

### Fix 2: Remove matrix_in_s from RGB48 conversion

In `src/frame_compare/vs/tonemap.py:137`:

```python
# BEFORE
clip = clip.resize.Bicubic(format=vs.RGB48, matrix_in_s="709")

# AFTER
clip = clip.resize.Bicubic(format=vs.RGB48)
```

### Fix 3: Debug Vulkan in Docker

Try adding explicit Vulkan configuration to Dockerfile runtime stage:

```dockerfile
ENV LIBGL_ALWAYS_SOFTWARE=1
ENV VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.x86_64.json
```

Or investigate if libplacebo can work without Vulkan by using a different meson option.

## Verification After Fixes

```bash
bash tools/verify_docker_integration.sh
```

**Pass criteria:** Exit 0, zero errors, zero failed, zero skipped.

## Output

Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v4.md
