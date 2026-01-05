---
RUN_ID: 2025-12-29__p3-4__color-operations
VERSION: v1
TARGET: Phase 3 → Item 3.4 Color Operations
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-v1.md
  - .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-4__color-operations/review-v1.md
---

# Review Report: VS Color Operations + Perf Spans

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Review Agent (handoff requested by orchestrator)
**Date:** 2025-12-30
**Run:** 2025-12-29__p3-4__color-operations

## Findings

### 1) SSOT ↔ Implementation Drift: BT.2020 matrix preference order

- **SSOT requirement:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` → Section: "3.5 Color Operations"
  - HDR matrix backfill must prefer `MATRIX_BT2020_CL`, then `MATRIX_BT2020_NCL`, then fall back to `9`.
- **Current implementation:** `src/frame_compare/vs/color.py:47`
  - When HDR transfer is detected and `matrix == 2`, the code sets `matrix = 9` directly.

**Decision:** Keep SSOT as correct/authoritative; update implementation to match SSOT.

## Required Fixes (Implementation; no SSOT change)

1) Update `infer_color_props()` to backfill BT.2020 matrix using the SSOT preference order:
   - prefer `vapoursynth.MATRIX_BT2020_CL`
   - else `vapoursynth.MATRIX_BT2020_NCL`
   - else `9`

2) Update tests to validate preference order deterministically:
   - In mocked-vapoursynth tests, set `MATRIX_BT2020_CL` (and/or `MATRIX_BT2020_NCL`) on the vs mock and assert that value is chosen.
   - Keep a test for the “no constants present” case asserting fallback to `9`.

3) If typing requires it, update `typings/vapoursynth.pyi` to include any referenced constants.

## Verification (must pass)

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check src tests
.venv/bin/pytest -q
```

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-4__color-operations

## Read First
1. Read file: .agent-workflow/runs/2025-12-29__p3-4__color-operations/plan-v1.md
2. Read file: .agent-workflow/runs/2025-12-29__p3-4__color-operations/review-v1.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md (Section: "3.5 Color Operations")

## Your Task
Fix the SSOT ↔ implementation drift:
- Update `src/frame_compare/vs/color.py` HDR matrix backfill to prefer `MATRIX_BT2020_CL`, then `MATRIX_BT2020_NCL`, then `9`.
- Update/add tests to cover both “constants present” and “constants missing” cases deterministically.
- Update `typings/vapoursynth.pyi` only if needed by typing.

## Output
Write file: .agent-workflow/runs/2025-12-29__p3-4__color-operations/impl-v1.md
