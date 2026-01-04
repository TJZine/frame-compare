---
RUN_ID: 2026-01-04__p6-7-2__probe-cache-key
VERSION: v1
TARGET: Phase 6 → Item 6.7 (Probe Snapshot Cache Keying)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/plan-v1.md
  - .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/impl-v1.md
  - src/frame_compare/orchestration/probe_cache.py
  - tests/orchestration/test_probe_cache.py
---

# Implementation Report: Probe Snapshot Cache Key (`compute_probe_cache_key`)

## Summary
**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/plan-v1.md
**Plan Review Report:** .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/plan-review-v1.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/orchestration/probe_cache.py` — Implements stable cache key computation.
- `tests/orchestration/test_probe_cache.py` — Unit tests for key stability and invalidation (2 tests).

### Modified
- `src/frame_compare/orchestration/__init__.py` — Added export for `compute_probe_cache_key`.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md` — Regenerated (hygiene).
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` — Regenerated (hygiene).
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md` — Regenerated (hygiene).
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md` — Regenerated (hygiene).
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py` — Regenerated (hygiene).

## Implementation Notes
- Implemented `compute_probe_cache_key` using `json.dumps` with `sort_keys=True` and `separators=(",", ":")` as specified in SSOT.
- Used `hashlib.blake2s` for the hash digest.
- Tests confirm that the key is stable for identical fingerprints and changes when any field of the fingerprint changes.

## Local Sanity Checks

- `.venv/bin/pyright --warnings src/frame_compare/orchestration/probe_cache.py tests/orchestration/test_probe_cache.py` — [exit 0]
- `.venv/bin/ruff check src/frame_compare/orchestration/probe_cache.py tests/orchestration/test_probe_cache.py` — [exit 0]
- `.venv/bin/pytest -q tests/orchestration/test_probe_cache.py` — [exit 0]
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` — [exit 0]

## Checklist Item Implemented

- [x] Implement `compute_probe_cache_key(fingerprint: ClipFingerprint) -> str` per SSOT (stable JSON + blake2s)
- [x] Add unit tests for key stability and invalidation (fingerprint change → different key)

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-7-2__probe-cache-key

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/impl-v1.md
2. Read file: .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/plan-v1.md
3. Read file: .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/plan-review-v1.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-7-2__probe-cache-key/verify-v1.md
