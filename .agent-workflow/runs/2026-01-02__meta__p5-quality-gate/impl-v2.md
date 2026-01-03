---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v2
TARGET: Meta → Phase 5 Quality Gate Fixes
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v2.md
  - src/frame_compare/vs/tonemap.py
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v2.md
---

# Implementation Report: VapourSynth API Usage Fix

## Summary
**Date:** 2026-01-02
**Context:** Verification v2 identified an `AttributeError` in `src/frame_compare/vs/tonemap.py` when running in the Docker environment with real VapourSynth.

## Files Changed

### Modified
- `src/frame_compare/vs/tonemap.py` — Replaced `clip.std.core` with `vs.core`.
- `tests/vs/test_tonemap.py` — Updated mocks to use `vs.core` instead of `clip.std.core`.

## Implementation Notes
The `clip.std.core` property is not a standard VapourSynth API and was causing failures in environments where VapourSynth is correctly installed. The fix standardizes on `vs.core`.

Local unit tests were updated to patch `vapoursynth.core` instead of mocking a `std.core` property on the clip mock. This ensures the tests remain valid and isolated.

## Local Sanity Checks
- `.venv/bin/pytest -q` — [exit 0] (390 passed, 4 skipped)
- `.venv/bin/pyright --warnings` — [exit 0]
- `.venv/bin/ruff check .` — [exit 0]

## Ready for Verification
Fix applied and verified locally. Ready for the Docker integration gate.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Context
This is a revision (impl-v2) addressing the AttributeError identified in verify-v2.md.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v2.md
2. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v2.md (contains the fix list)
3. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md

## Your Task
1. Verify the specific fix was applied to src/frame_compare/vs/tonemap.py
2. Run the full verification suite (including Docker integration)
3. Confirm all review issues addressed

## Output
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md
