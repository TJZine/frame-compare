---
RUN_ID: 2026-02-02__p6-7-8__runner
VERSION: v7
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Create `src/frame_compare/runner.py` at package root (see `cli-module.md` §1.2)
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-8__runner/verify-v7.md
  - .agent-workflow/runs/2026-02-02__p6-7-8__runner/impl-v7.md
  - .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v2.md
  - .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-8__runner/review-v7.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Runner Package-Root Scaffold

## Verdict: APPROVED

## Review Summary

**Reviewer:** Review Agent
**Date:** 2026-02-03
**Files Reviewed:** 6

### Files Reviewed

- src/frame_compare/runner.py
- tests/test_runner_import_smoke.py
- importlinter.ini
- .agent-workflow/runs/2026-02-02__p6-7-8__runner/plan-v2.md
- .agent-workflow/runs/2026-02-02__p6-7-8__runner/impl-v7.md
- .agent-workflow/runs/2026-02-02__p6-7-8__runner/verify-v7.md

## Process Gates

- [x] Plan approved by Plan Review Agent
- [x] Verification handoff complete
- [x] Verification gate outputs recorded
- [x] Run index updated with final verdict

## Findings

No findings. The scaffolded runner surface matches the plan exactly.

**Residual risk:** `frame_compare.runner.run` remains a scaffold and raises `NotImplementedError` by design; no execution behavior is implemented yet.

## Quality Check Results

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest -q
........................................................................ [ 13%]
........................................................................ [ 27%]
........................................................................ [ 40%]
........................................................................ [ 54%]
........................................................................ [ 68%]
........................................................................ [ 81%]
........................................................................ [ 95%]
.......................                                                  [100%]
=========================== short test summary info ============================
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

Analyzed 55 files, 121 dependencies.
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

- [x] `frame_compare.runner` exists at package root and imports cleanly
- [x] Public exports (`RunRequest`, `RunResult`, `RunDependencies`, `run`) present
- [x] `run(...)` raises the exact scaffold `NotImplementedError`
- [x] `importlinter.ini` layer updated (`cli_entry` → `runner` → `orchestration`)

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Scaffold failure message matches the required text

### Testing

- [x] Smoke tests cover exports and scaffold behavior
- [x] Tests deterministic; no external tools invoked

### Documentation

- [x] Master checklist updated for the completed sub-item

## Orchestrator Actions

1. Commit the changes:
   ```bash
   git add -A
   git commit -m "feat(orchestration): add runner scaffold" \
     -m "Run: 2026-02-02__p6-7-8__runner" \
     -m "Closes Phase 6 Item 6.7"
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
