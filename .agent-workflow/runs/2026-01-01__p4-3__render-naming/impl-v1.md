---
RUN_ID: 2026-01-01__p4-3__render-naming
VERSION: v1
TARGET: Phase 4 → Item 4.3
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-3__render-naming/plan-v1.md
  - .agent-workflow/runs/2026-01-01__p4-3__render-naming/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-3__render-naming/impl-v1.md
  - src/frame_compare/render/naming.py
  - tests/render/test_naming.py
---

# Implementation Report: Render Naming Utilities

## Summary
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-3__render-naming/plan-v1.md
**Plan Review Report:** .agent-workflow/runs/2026-01-01__p4-3__render-naming/plan-review-v1.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/render/naming.py` — Screenshot naming and path generation logic.
- `tests/render/test_naming.py` — 14 tests covering sanitization, boundary cases, and error handling.

### Modified
- `src/frame_compare/render/__init__.py` — Added exports for naming utilities.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` — Added Sections 3.3.1 and 3.3.2 (SSOT behavior rules).
- `docs/DECISIONS.md` — Logged the implementation of render naming utilities.
- `CHANGELOG.md` — Added entry for `render.naming`.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md` (Regenerated)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` (Regenerated)
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py` (Regenerated)

## Implementation Notes
- Implemented `generate_screenshot_name` with robust sanitization using regex.
- Handled edge cases like empty labels (defaults to `unnamed`) and collapsing consecutive underscores.
- Verified that `generate_screenshot_path` correctly utilizes the naming logic.
- All unit tests pass with 100% coverage for the new module.
- Regenerated contract views to maintain freshness.

## Local Sanity Checks

- `.venv/bin/pyright --warnings src/frame_compare/render/` — exit 0
- `.venv/bin/ruff check src/frame_compare/render/ tests/render/` — exit 0
- `.venv/bin/pytest -v tests/render/test_naming.py` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — exit 0

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 4.3: Render Naming Utilities [SSOT]

## Open Questions

- None

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-3__render-naming

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-01__p4-3__render-naming/impl-v1.md
2. Read file: .agent-workflow/runs/2026-01-01__p4-3__render-naming/plan-v1.md
3. Read file: .agent-workflow/runs/2026-01-01__p4-3__render-naming/plan-review-v1.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-01-01__p4-3__render-naming/verify-v1.md
