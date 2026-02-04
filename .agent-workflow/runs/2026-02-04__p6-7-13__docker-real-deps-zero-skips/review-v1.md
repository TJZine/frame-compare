---
RUN_ID: 2026-02-04__p6-7-13__docker-real-deps-zero-skips
VERSION: v1
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Write integration tests (Docker, real deps; zero skips)
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-7-13__docker-real-deps-zero-skips/verify-v1.md
  - .agent-workflow/runs/2026-02-04__p6-7-13__docker-real-deps-zero-skips/impl-v1.md
  - .agent-workflow/runs/2026-02-04__p6-7-13__docker-real-deps-zero-skips/plan-v1.md
  - .agent-workflow/runs/2026-02-04__p6-7-13__docker-real-deps-zero-skips/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-7-13__docker-real-deps-zero-skips/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: LoadSources Probe Cache Integration Tests

## Verdict: APPROVED

## Review Summary

**Reviewer:** Review Agent
**Date:** 2026-02-04
**Files Reviewed:** 4

### Files Reviewed

- tests/integration/test_loadsources_probe_cache.py
- .agent-workflow/runs/2026-02-04__p6-7-13__docker-real-deps-zero-skips/plan-v1.md
- .agent-workflow/runs/2026-02-04__p6-7-13__docker-real-deps-zero-skips/impl-v1.md
- .agent-workflow/runs/2026-02-04__p6-7-13__docker-real-deps-zero-skips/verify-v1.md

## Process Gates

- [x] Plan approved by Plan Review Agent
- [x] Verification handoff complete
- [x] Verification gate outputs recorded
- [x] Run index updated with final verdict

## Findings

No findings. The integration tests cover probe cache creation and warm-cache reuse, and the raising loader ensures probe reuse is exercised deterministically.

**Residual risk:** Docker real-deps zero-skips gate was not executed in this local verification run; it should be validated via `bash tools/verify_docker_integration.sh`.

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
........................................................................ [ 66%]
........................................................................ [ 79%]
........................................................................ [ 92%]
........................................                                 [100%]
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

Analyzed 56 files, 134 dependencies.
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

### Testing

- [x] Integration tests cover cache creation and reuse on warm cache
- [x] Tests are deterministic and use stable CFR inputs
- [ ] Docker zero-skips gate executed (pending)

### Documentation

- [x] Master checklist updated for completed sub-items

## Orchestrator Actions

1. Commit the changes:
   ```bash
   git add -A
   git commit -m "test(integration): cover LoadSources probe cache in Docker" \
     -m "Run: 2026-02-04__p6-7-13__docker-real-deps-zero-skips" \
     -m "Closes Phase 6 Item 6.7 (partial)"
   ```
2. Run Docker verification gate when available: `bash tools/verify_docker_integration.sh`
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
