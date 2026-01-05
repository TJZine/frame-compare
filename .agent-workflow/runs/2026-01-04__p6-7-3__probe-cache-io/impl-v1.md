---
RUN_ID: 2026-01-04__p6-7-3__probe-cache-io
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Probe Snapshot Cache I/O)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/impl-v1.md
  - src/frame_compare/orchestration/probe_cache.py
  - tests/orchestration/test_probe_cache_io.py
---

# Implementation Report: Probe Snapshot Cache (`clip_probe.toml`) Load/Save

## Summary
**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md
**Plan Review Report:** .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v2.md (APPROVED)

## Files Changed (Exact Paths)

### Modified
- `src/frame_compare/orchestration/probe_cache.py` — Added `load_clip_probe_cache` and `save_clip_probe_cache` helpers.

### Created
- `tests/orchestration/test_probe_cache_io.py` — Unit tests for TOML round-trip, sanitization, and failure modes (7 tests).

### Regenerated (Hygiene)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py`

## Implementation Notes
- Implemented `load_clip_probe_cache` and `save_clip_probe_cache` as pure functions using `tomllib` (standard library for 3.11+) and `tomli_w`.
- Enforced SSOT failure policies: missing file or version mismatch returns an empty dict with a warning; invalid entries are skipped.
- Enforced HDR metadata invariant: `is_hdr=True` requires `hdr_metadata` during save.
- Sanitized `preserved_frame_props` at the persistence boundary to ensure only `str|int|float` primitives are stored.
- Applied Pyright best practices including explicit type narrowing and casting when dealing with `Any` from `tomllib.load`.
- Adhered to Ruff style rules (e.g., combining nested `if` statements, using `collections.abc.Mapping`).

## Local Sanity Checks

- `.venv/bin/pyright --warnings src/frame_compare/orchestration/probe_cache.py tests/orchestration/test_probe_cache_io.py` — [exit 0]
- `.venv/bin/ruff check src/frame_compare/orchestration/probe_cache.py tests/orchestration/test_probe_cache_io.py` — [exit 0]
- `.venv/bin/pytest -q tests/orchestration/test_probe_cache_io.py` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — [exit 0]

## Checklist Item Implemented

- [x] Implement deterministic probe-cache I/O helpers: `load_clip_probe_cache()` and `save_clip_probe_cache()`
- [x] Extend unit tests to lock down SSOT failure modes + deterministic behavior

## Ready for Verification

All files created/modified per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-7-3__probe-cache-io

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/impl-v1.md
2. Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-v2.md
3. Read file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/plan-review-v2.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-7-3__probe-cache-io/verify-v1.md
