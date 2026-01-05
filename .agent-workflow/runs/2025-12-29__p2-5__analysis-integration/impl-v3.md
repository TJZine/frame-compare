---
RUN_ID: 2025-12-29__p2-5__analysis-integration
VERSION: v3
TARGET: Phase 2 → Item 2.5 (Module Integration)
INPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v5.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v5.md
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/impl-v3.md
---

# Implementation Report: Analysis Module Integration

## Summary
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v5.md
**Plan Review Report:** .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-review-v5.md (APPROVED)
**Review Report:** .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/review-v2.md (CHANGES REQUIRED)

## Files Changed (Exact Paths)

### Modified
- `src/frame_compare/analysis/__init__.py` — Added `calculate_metrics` export to public API
- `src/frame_compare/analysis/metrics.py` — Refactored to lazy VapourSynth imports per SSOT
- `tests/analysis/test_metrics.py` — Added deterministic test for import invariant and fixed Ruff SIM103
- `docs/DECISIONS.md` — Updated Phase 2.5 decision entry
- `CHANGELOG.md` — Updated Analysis module completion entry
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md` — Regenerated (derived)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` — Regenerated (derived)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md` — Regenerated (derived)
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md` — Regenerated (derived)
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py` — Regenerated (derived)

## Implementation Notes
- Followed `plan-v5.md` exactly.
- Added `calculate_metrics` to `analysis/__init__.py` public exports.
- Refactored `metrics.py` to use local `import vapoursynth as vs` inside processing functions and `TYPE_CHECKING` for hints to support non-VS environments.
- Implemented `test_no_toplevel_vapoursynth_import` in `test_metrics.py` using `ast` to enforce the import invariant.
- Fixed Ruff SIM103 in `tests/analysis/test_metrics.py`.
- This revision (`impl-v3.md`) corrects the `INPUTS` metadata which was incomplete in previous versions.

## Local Sanity Checks (Optional)

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v5.md` — [exit 0]
- `.venv/bin/pyright --warnings src/frame_compare/analysis/` — [exit 0]
- `.venv/bin/ruff check .` — [exit 0]
- `.venv/bin/pytest -v tests/analysis/` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — [exit 0]

## Checklist Item Implemented

- [x] Phase 2.5: Analysis Module Integration

## Ready for Verification

Implementation complete and verified locally. Corrected metadata referencing `plan-v5.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p2-5__analysis-integration

## Context
This is a revision (impl-v3) addressing metadata issues from review-v2.md.

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/impl-v3.md
2. Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/review-v2.md (contains the fix list)
3. Read file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/plan-v5.md

## Your Task
1. Verify the specific fixes (INPUTS metadata) were applied
2. Run the full verification suite
3. Confirm all review issues addressed

## Output
Write file: .agent-workflow/runs/2025-12-29__p2-5__analysis-integration/verify-v3.md
