---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v3
TARGET: Meta → Phase 5 Quality Gate Fixes
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v2.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v2.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md
---

# Verification Handoff: VapourSynth API Usage Fix

## Summary

**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md
**Implementation Report:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v2.md

## Implementation Review

### Fix Verification

- [x] tonemap.py:165 — Changed from `clip.std.core` to `vs.core` ✅
- [x] test_tonemap.py — Mocks updated to patch `vapoursynth.core` ✅

### Previous Issue Status

| Issue | Status | Notes |
|-------|--------|-------|
| `AttributeError: There is no function named core` | ✅ FIXED | `vs.core` now used correctly |

## Verification Results

### Quality Gates ✅

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date
```

### Full Test Suite (Local) ✅

```text
$ .venv/bin/pytest -v --cov=src/frame_compare --cov-fail-under=80

415 passed, 2 skipped in 2.89s
Total coverage: 90.54%
```

### Docker Integration ❌

```text
$ bash tools/verify_docker_integration.sh

tests/integration/test_render_orchestrator.py .                          [ 16%]
tests/integration/test_render_pipeline.py ...                            [ 66%]
tests/integration/test_render_vs.py .                                    [ 83%]
tests/vs/test_integration.py F                                           [100%]

FAILED tests/vs/test_integration.py::test_vs_integration_smoke
```

**New Failure (different from verify-v2):**

```
TonemapError: [FC-4003] Tonemapping failed: libplacebo tonemap failed:
placebo.Tonemap: Input must be 16 bits per sample!
Hint: Check libplacebo plugin version

libplacebo compiled without Vulkan support!
Failed creating vulkan context
```

**Previous Issue:** `AttributeError: There is no function named core` → ✅ FIXED
**New Issue:** libplacebo bit depth incompatibility + no Vulkan support

**Root Cause Analysis:**

1. **Test creates RGBS clip (32-bit float):** `core.std.BlankClip(..., format=vs.RGBS, ...)`
2. **libplacebo.Tonemap requires 16-bit input:** The plugin rejects 32-bit float
3. **libplacebo has no Vulkan in Docker:** Software fallback fails

**Fix Options:**

1. **Test fix:** Create clip with 16-bit format (e.g., `vs.RGB48`) or convert before calling `tonemap()`
2. **Code fix:** Add bit depth conversion in `_apply_libplacebo()` before calling `core.placebo.Tonemap()`
3. **Test skip:** Skip libplacebo path in Docker if no Vulkan (use fallback path instead)

This is a **pre-existing integration issue** — the tonemap integration test has never successfully run in Docker before because VS tests weren't included until this run.

## Checklist Updates

- [ ] NOT updated: Phase 5 Quality Gate items remain unchecked pending Docker gate pass

## Index Updates

- [ ] NOT updated: Cannot append until verification passes

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the plan review Agent for Frame Compare 2.0. We have found significant issues in the Docker integration test. Please review the plan and determine the best course of action to get this working correctly and how we want. There are several decisions that we need to figure out and expand this tasks scope significantly to ensure we have everything we have built so far working in docker as it should be since that is our actually way to use this program.

## RUN_ID

2026-01-02__meta__p5-quality-gate

## Issue to Fix

Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md
See "New Failure" section for details.

## Context

The vs.core fix (impl-v2) is CORRECT. The new failure is a **libplacebo bit depth incompatibility** in the Docker integration test.

## Required Fix (choose one approach)

### Option A: Fix the test (recommended — minimal scope)

In `tests/vs/test_integration.py`, the test creates `vs.RGBS` (32-bit float) but libplacebo requires 16-bit input.

Either:

1. Use `vs.RGB48` instead of `vs.RGBS` for the test clip
2. Or disable `settings.enabled=True` to skip tonemap entirely and just test the passthrough

### Option B: Fix the code (broader scope — affects production)

In `src/frame_compare/vs/tonemap.py::_apply_libplacebo()`, add bit depth conversion before calling `core.placebo.Tonemap()`:

```python
# Convert to 16-bit if needed (libplacebo requires 16bpp)
if clip.format.bits_per_sample != 16:
    clip = clip.resize.Bicubic(format=vs.RGB48)
```

## Verification After Fix

```bash
bash tools/verify_docker_integration.sh
```

**Pass criteria:** Exit 0, ALL passed, 0 failed, zero skipped.

## Output

Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v6.md
