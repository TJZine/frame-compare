---
RUN_ID: 2026-02-04__p6-8-2__wizard
VERSION: v1
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `wizard` command (interactive config) — Bundled 2 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-2__wizard/verify-v1.md
  - .agent-workflow/runs/2026-02-04__p6-8-2__wizard/impl-v1.md
  - .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-v1.md
  - .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-2__wizard/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: CLI `wizard` + `doctor` Commands (Bundled)

## Verdict: APPROVED

## Review Summary

**Reviewer:** Review Agent
**Date:** 2026-02-04
**Files Reviewed:** 5

### Files Reviewed

- src/frame_compare/cli_entry.py
- tests/cli/test_cli_commands.py
- .agent-workflow/runs/2026-02-04__p6-8-2__wizard/plan-v1.md
- .agent-workflow/runs/2026-02-04__p6-8-2__wizard/impl-v1.md
- .agent-workflow/runs/2026-02-04__p6-8-2__wizard/verify-v1.md

## Process Gates

- [x] Plan approved by Plan Review Agent
- [x] Verification handoff complete
- [x] Verification gate outputs recorded
- [x] Run index updated with final verdict

## Findings

No findings. The wizard prompt flow, validation, and TOML output align with the plan, and doctor JSON/exit code behaviors are deterministic and schema-aligned.

## Quality Check Results

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest -q
........................................................................ [ 12%]
........................................................................ [ 25%]
........................................................................ [ 38%]
........................................................................ [ 51%]
........................................................................ [ 64%]
........................................................................ [ 77%]
........................................................................ [ 90%]
...................................................                      [100%]
=========================== short test summary info ==========================
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

Analyzed 56 files, 138 dependencies.
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

- [x] `frame-compare wizard` writes `config/config.toml` with prompted values and validates input directory
- [x] Wizard cancellation exits with code 130 without writing config
- [x] `frame-compare doctor --json` emits schema-aligned JSON with baseline `R73`
- [x] `frame-compare doctor` exit code depends only on core failures

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Wizard abort mapped to `ExitCode.INTERRUPTED`
- [x] Doctor uses `ExitCode.DEPENDENCY_ERROR` for core failures

### Testing

- [x] Wizard tests validate interactive prompt flow and config output
- [x] Doctor tests validate JSON shape and exit codes without network calls

### Documentation

- [x] Master checklist updated for bundled items

## Orchestrator Actions

1. Commit the changes:
   ```bash
   git add -A
   git commit -m "feat(cli): complete wizard and doctor commands" \
     -m "Run: 2026-02-04__p6-8-2__wizard" \
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
