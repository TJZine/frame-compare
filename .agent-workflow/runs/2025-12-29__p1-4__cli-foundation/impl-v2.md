---
RUN_ID: 2025-12-29__p1-4__cli-foundation
VERSION: v2
TARGET: Phase 1 → Item 1.4
INPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/impl-v1.md
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v5.md
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/verify-v1.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/impl-v2.md
---

# Implementation Report: CLI Foundation (Revision v2)

## Summary
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v5.md
**Revision Context:** Addressing contract freshness failure in `verify-v1.md`.

## Files Changed (Exact Paths)

### Generated/Modified (Contract Views)
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md` — Updated CLI flags documentation
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` — Updated error codes reference
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md` — Updated config reference
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md` — Updated dependency graph
- `scaffold/src/frame_compare/cli/_generated.py` — Updated generated CLI code

## Implementation Notes
- Regenerated all derived contract views using `scripts/generate_contract_views.py`.
- The CLI changes in `cli_entry.py` (added commands and full flag lists) required these updates to maintain contract freshness.

## Local Sanity Checks

### Contract Freshness
```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
WROTE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md
WROTE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md
WROTE: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md
WROTE: docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
WROTE: docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py
OK: All derived files are up-to-date
```

### Verification Suite
- `.venv/bin/pytest -v tests/cli/` — exit 0 (10 passed)
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini` — exit 0
- `.venv/bin/pyright --warnings src/frame_compare/cli_entry.py` — exit 0
- `.venv/bin/ruff check src/frame_compare/cli_entry.py` — exit 0

## Checklist Item Implemented
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Regenerate derived contract views

## Ready for Verification

Contract views regenerated and verified. Ready for Verification Agent re-run.

## NEXT AGENT PROMPT (COPY/PASTE)

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p1-4__cli-foundation

## Context
This is a revision (impl-v2) addressing issues from verify-v1.md (Contract Freshness gate failure).

## Files to Read
1. Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/impl-v2.md
2. Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/verify-v1.md (contains the failure report)
3. Read file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/plan-v5.md

## Your Task
1. Verify the specific fixes (contract regeneration) were applied
2. Run the full verification suite (including the contract freshness gate)
3. Confirm all previous issues addressed

## Output
Write file: .agent-workflow/runs/2025-12-29__p1-4__cli-foundation/verify-v2.md
