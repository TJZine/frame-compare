---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v3
TARGET: Meta → Phase 5 Quality Gate Fixes (Docker-first)
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v12.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v3.md
  - Dockerfile
  - src/frame_compare/vs/tonemap.py
  - tests/vs/test_tonemap.py
  - tests/vs/test_integration.py
  - tools/verify_docker_integration.sh
  - docs/DECISIONS.md
  - CHANGELOG.md
---

# Implementation Report: Phase 5 Quality Gate Fixes (Docker-first)

## Summary
**Date:** 2026-01-03
**Plan Reference:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md
**Plan Review Report:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v12.md (APPROVED)

## Files Changed (Exact Paths)

### Modified
- `Dockerfile` — Enabled Vulkan in libplacebo build and runtime (Mesa lavapipe).
- `src/frame_compare/vs/tonemap.py` — Updated `_apply_libplacebo` signature, added RGB48 conversion, implemented runtime fallback pattern.
- `tests/vs/test_tonemap.py` — Added fallback test, updated mocks to support new flow.
- `tests/vs/test_integration.py` — Added `test_libplacebo_tonemap_succeeds_in_docker` to verify Vulkan backend.
- `tools/verify_docker_integration.sh` — Removed marker filter to run full VS integration suite.
- `docs/DECISIONS.md` — Documented Docker libplacebo decisions.
- `CHANGELOG.md` — Added fix entries.

## Implementation Notes
- **Docker Vulkan:** `libplacebo` requires Vulkan compute shaders for tonemapping. Enabled via `glslang-tools` (build) and `mesa-vulkan-drivers` (runtime).
- **Runtime Fallback:** `_apply_libplacebo` now catches exceptions (e.g., if Vulkan init fails despite drivers being present) and returns `None`, allowing `apply_tonemap` to degrade gracefully to Reinhard fallback.
- **Verification:** The new test `test_libplacebo_tonemap_succeeds_in_docker` is critical; it asserts that `_apply_libplacebo` returns a `VideoNode`, proving the Vulkan pipeline actually works inside the container.

## Local Sanity Checks

- `.venv/bin/pyright --warnings` — [exit 0]
- `.venv/bin/ruff check .` — [exit 0] (Applied 1 auto-fix for imports)
- `.venv/bin/pytest -q` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — [exit 0]

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Fix 6: libplacebo 16-bit input
- [x] Fix 7: No Vulkan in Docker
- [x] Fix 8: No runtime fallback

## Open Questions

- None.

## Ready for Verification

Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v3.md
2. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md
3. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v12.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v4.md
