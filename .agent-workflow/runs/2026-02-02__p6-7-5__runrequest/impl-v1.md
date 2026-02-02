---
RUN_ID: 2026-02-02__p6-7-5__runrequest
VERSION: v1
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement `RunRequest` dataclass per spec
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v3.md
  - .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/impl-v1.md
  - src/frame_compare/orchestration/coordinator.py
  - src/frame_compare/orchestration/__init__.py
  - tests/orchestration/test_run_request.py
---

# Implementation Report: RunRequest (Runner & Phase Orchestration)

## Summary
**Date:** 2026-02-02
**Plan Reference:** .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v3.md
**Plan Review Report:** .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-review-v3.md (APPROVED)

## Files Changed (Exact Paths)

### Created
- `src/frame_compare/orchestration/coordinator.py` — Run coordination `RunRequest` dataclass per spec
- `tests/orchestration/test_run_request.py` — Defaults, immutability, and export coverage

### Modified
- `src/frame_compare/orchestration/__init__.py` — Exported `RunRequest`

## Implementation Notes
- No deviations from the plan.

## Local Sanity Checks (Command Output)

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v3.md`

```text
OK: Spec Anchors valid for .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v3.md
```

- `.venv/bin/pyright --warnings`

```text
0 errors, 0 warnings, 0 informations
```

- `.venv/bin/ruff check .`

```text
All checks passed!
```

- `.venv/bin/pytest -q`

```text
........................................................................ [ 13%]
........................................................................ [ 27%]
........................................................................ [ 41%]
........................................................................ [ 55%]
........................................................................ [ 69%]
........................................................................ [ 83%]
........................................................................ [ 97%]
...........                                                              [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/integration/test_render_vs.py:13: vapoursynth is mocked
SKIPPED [1] tests/vs/test_integration.py:13: VapourSynth is mocked, skipping integration test
```

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`

```text

╔══╗─────────▶╔╗ ╔╗      ╔╗◀───┐
╚╣╠╝◀─────┐  ╔╝╚╗║║────▶╔╝╚╗   │
 ║║   ╔══╦══╦╩╗╔╝║║  ╔╦═╩╗╔╝╔═╦══╗
 ║║╔══╣╔╗║╔╗║╔╣║ ║║ ╔╬╣╔╗║║ ║│║╔═╝
╔╣╠╣║║║╚╝║╚╝║║║╚╗║╚═╝║║║║║╚╗║═╣║
╚══╩╩╩╣╔═╩══╩╝╚═╝╚═══╩╩╝╚╩═╩╩═╩╝
  └──▶║║                    ▲
      ╚╝────────────────────┘


---------
Contracts
---------

Analyzed 54 files, 117 dependencies.
------------------------------------

Layered Architecture KEPT
Domain Independence KEPT

Contracts: 2 kept, 0 broken.
```

- `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`

```text
OK: All derived files are up-to-date
```

## Checklist Item Implemented
>
> ⚠️ **Report-only — do NOT edit the master checklist file**

- [x] Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement `RunRequest` dataclass per spec

## Open Questions
- None.

## Ready for Verification

All files created per plan. Ready for Verification Agent gate run.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-02-02__p6-7-5__runrequest

## Files to Read
1. Read file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/impl-v1.md
2. Read file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v3.md
3. Read file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-review-v3.md

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite
3. Update the master checklist
4. Update the run index

## Output
Write file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/verify-v1.md
