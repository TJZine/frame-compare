---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v1
TARGET: Phase 5 → Item 5.2
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/impl-v1.md
  - src/frame_compare/services/metadata.py
  - src/frame_compare/services/types.py
  - src/frame_compare/services/__init__.py
  - tests/services/test_metadata.py
  - pyproject.toml
  - docs/DECISIONS.md
  - CHANGELOG.md
---

# Implementation Report: Metadata Service

## Summary
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md
**Plan Review Report:** .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v4.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/services/metadata.py` — Filename parsing and TMDB lookup service.
- `tests/services/test_metadata.py` — 17 unit tests for metadata service (sync and async).

### Modified
- `pyproject.toml` — Added `guessit>=3.8.0` and `anitopy>=2.1.1` dependencies.
- `src/frame_compare/services/types.py` — Added `ParsedMetadata`, `TmdbMetadata`, and `MetadataConfig` types.
- `src/frame_compare/services/__init__.py` — Exported metadata service public API.
- `docs/DECISIONS.md` — Added Phase 5.2 decisions (Filename parsing strategy, search helper, dependency adjustment).
- `CHANGELOG.md` — Added entry for metadata service.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md` — Regenerated.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` — Regenerated.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md` — Regenerated.
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md` — Regenerated.
- `src/frame_compare/cli/_generated.py` — Regenerated.

## Implementation Notes

- **Dependency Adjustment:** `anitopy 2.2.0` (from plan) is not yet available as a stable release. Reverted to `2.1.1` to satisfy dependency resolution while maintaining functionality.
- **Search Logic:** Implemented internal `_search_tmdb` helper to allow `resolve_metadata` to handle multiple results while keeping `lookup_tmdb` signature returning a single result as specified.
- **Test Adjustment:** `test_parse_filename_western_movie` updated to expect `Blu-ray` (library default) instead of `BluRay`.
- **Pre-existing Issues:** Discovered pre-existing `ValueError: vapoursynth.__spec__ is not set` in `tests/vs/` during full suite collection. These are unrelated to Phase 5.2 and persist in the environment; full gate passes with `pytest --ignore tests/vs/`.

## Local Sanity Checks

- `.venv/bin/pyright --warnings` — [exit 0]
- `.venv/bin/ruff check .` — [exit 0]
- `.venv/bin/pytest tests/services/test_metadata.py` — [exit 0]
- `.venv/bin/pytest -q --ignore tests/vs/` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — [exit 0]

## Checklist Item Implemented

- [x] Phase 5.2: Metadata Service (Filename parsing + TMDB)

## Open Questions

- NONE

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-2__metadata-service

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/impl-v1.md
2. Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md
3. Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v4.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/verify-v1.md
