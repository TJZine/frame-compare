---
RUN_ID: 2026-02-04__p6-8-4__exitcode
VERSION: v1
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Implement `ExitCode` enum per spec §3.2 — Bundled 3 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/verify-v1.md
  - .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/impl-v1.md
  - .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-v1.md
  - .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: CLI Exit Codes (Bundled)

## Verdict: APPROVED

## Review Summary

**Reviewer:** Review Agent
**Date:** 2026-02-04
**Files Reviewed:** 8

### Files Reviewed

- src/frame_compare/errors.py
- src/frame_compare/cli_entry.py
- tests/test_errors.py
- tests/cli/test_cli_commands.py
- tests/cli/test_exit_codes.py
- .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/plan-v1.md
- .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/impl-v1.md
- .agent-workflow/runs/2026-02-04__p6-8-4__exitcode/verify-v1.md

## Process Gates

- [x] Plan approved by Plan Review Agent
- [x] Verification handoff complete
- [x] Verification gate outputs recorded
- [x] Run index updated with final verdict

## Findings

No findings. Exit code mapping follows the error code category prefix rules, CLI paths use `ExitCode` without magic numbers, and tests cover generic `FrameCompareError` mapping plus interrupt handling.

## Quality Check Results

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest -q
........................................................................ [ 12%]
........................................................................ [ 24%]
........................................................................ [ 37%]
........................................................................ [ 49%]
........................................................................ [ 62%]
........................................................................ [ 74%]
........................................................................ [ 87%]
........................................................................ [ 99%]
..                                                                       [100%]
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

Analyzed 56 files, 145 dependencies.
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

- [x] `ExitCode` enum values match spec §3.2
- [x] Error-to-exit-code mapping follows spec §3.3 by category prefix
- [x] CLI integration tests cover JSON error output and interrupt exit code

## Orchestrator Actions

1. Commit the changes:
   ```bash
   git add -A
   git commit -m "feat(cli): implement exit codes" \
     -m "Run: 2026-02-04__p6-8-4__exitcode" \
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
