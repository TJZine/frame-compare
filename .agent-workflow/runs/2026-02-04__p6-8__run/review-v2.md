---
RUN_ID: 2026-02-04__p6-8__run
VERSION: v2
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `run` command implementation — Bundled 3 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/verify-v2.md
  - .agent-workflow/runs/2026-02-04__p6-8__run/impl-v2.md
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-v4.md
  - .agent-workflow/runs/2026-02-04__p6-8__run/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8__run/review-v2.md
  - .agent-workflow/index.md (updated)
---

# Review Report: CLI `run` Command (Bundled)

## Verdict: APPROVED

## Review Summary

**Reviewer:** Review Agent
**Date:** 2026-02-04
**Files Reviewed:** 12

### Files Reviewed

- src/frame_compare/cli_entry.py
- src/frame_compare/orchestration/coordinator.py
- src/frame_compare/orchestration/preflight.py
- src/frame_compare/config/overrides.py
- tests/cli/test_cli_commands.py
- tests/config/test_overrides.py
- tests/orchestration/test_execute_run.py
- tests/orchestration/test_preflight.py
- tests/orchestration/test_run_request.py
- .agent-workflow/runs/2026-02-04__p6-8__run/plan-v4.md
- .agent-workflow/runs/2026-02-04__p6-8__run/impl-v2.md
- .agent-workflow/runs/2026-02-04__p6-8__run/verify-v2.md

## Process Gates

- [x] Plan approved by Plan Review Agent
- [x] Verification handoff complete
- [x] Verification gate outputs recorded
- [x] Run index updated with final verdict

## Findings

No findings. The CLI `run` implementation, CLI→config override mapping, and input discovery behavior align with the §4.4.5/§4.4.6 specs, and the tests cover the critical mappings and empty-input error behavior.

## Quality Check Results

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest -q
........................................................................ [ 13%]
........................................................................ [ 26%]
........................................................................ [ 39%]
........................................................................ [ 52%]
........................................................................ [ 65%]
........................................................................ [ 78%]
........................................................................ [ 91%]
...............................................                          [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/integration/test_loadsources_probe_cache.py:23: vapoursynth is mocked
SKIPPED [1] tests/integration/test_render_vs.py:13: vapoursynth is mocked
SKIPPED [1] tests/vs/test_integration.py:13: VapourSynth is mocked, skipping integration test

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

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

Analyzed 56 files, 136 dependencies.
------------------------------------

Layered Architecture KEPT
Domain Independence KEPT

Contracts: 2 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Checklist Results

### Correctness

- [x] `frame-compare run` exits 0 on success and returns exit code 5 on unsuccessful results
- [x] CLI flag → config override mapping applies `tm_target`, `overlay`, `seed`, `no_upload`, and force-interactive alignment rules
- [x] Empty input directory raises `NoVideosFoundError(FC-3001)` with effective patterns

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] CLI error mapping uses `get_exit_code(...)` for `FrameCompareError`
- [x] `KeyboardInterrupt` exits with code 130

### Testing

- [x] CLI tests cover run request construction, success and failure exit codes
- [x] Orchestration tests cover CLI override application and discovery error behavior

### Documentation

- [x] Master checklist updated for the bundled sub-items

## Orchestrator Actions

1. Commit the changes:
   ```bash
   git add -A
   git commit -m "feat(cli): complete run command wiring" \
     -m "Run: 2026-02-04__p6-8__run" \
     -m "Closes Phase 6 Item 6.8"
   ```
2. Verify master checklist remains accurate
3. Select the next unchecked checklist item

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID

NEW_RUN_ID
(ORCHESTRATOR: replace `NEW_RUN_ID` with the next run’s confirmed RUN_ID before running the Planning Agent)

## Target

Pick the next unchecked checklist item (Planning Agent will read the checklist).

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Pick the next unchecked checklist item and create a detailed Implementation Plan.

## Output

Write file: .agent-workflow/runs/NEW_RUN_ID/plan-v1.md
