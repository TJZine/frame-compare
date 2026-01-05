---
RUN_ID: 2026-01-05__p6-7-4__probe-props-preservation
VERSION: v2
TARGET: Phase 6 → Item 6.7 (Preserve HDR/DoVi Props + tonemap_prop_keys)
INPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md
---

# Plan Review Report: Probe Prop Preservation Helpers (tonemap_prop_keys + preserved_frame_props)

## Verdict: APPROVED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-05
**Plan Reference:** .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicitly excludes VS probing, cache I/O, and downstream re-injection. |
| 2 | Dependencies | PASS | Pure helpers; no external deps introduced. |
| 3 | File List | PASS | Minimal and explicit (`probe_props.py`, test file, `__init__.py` export). |
| 4 | Contract Impact | PASS | No canonical contracts touched. |
| 5 | Types Complete | PASS | Public signatures are listed as one-line backticked bullets and anchored to SSOT. |
| 6 | Tests Complete | PASS | Tests cover SSOT selection rules, ordering, TOML-safe filtering, and DolbyVisionRPU sentinel handling. |
| 7 | Verification Complete | PASS | File-scoped pyright/ruff/pytest commands with explicit pass criteria. |
| 8 | Decision-Minimizing | PASS | Plan removes prior ambiguity by specifying/validating preserved-props selection boundary and output ordering. |
| 9 | Determinism Defined | PASS | Ordering is explicitly required and tested (tuple ordering and dict insertion order). |

## Additional Quality Checks

- Error Codes: OK (no new errors).
- Failure Modes: OK (pure functions; no I/O).
- Derived Outputs: OK (no derived views in-scope).
- Rollback Guidance: OK (if SSOT mismatch is discovered, STOP per workflow rules).
- SSOT Update Audit (this loop): N/A

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NONE

## Ready for Implementation

All checklist items pass. Coding Agent may proceed.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-01-05__p6-7-4__probe-props-preservation

## Precondition
Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md
Confirm: Verdict is APPROVED and Decision Points Remaining is NONE.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-v2.md
2. Read file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/plan-review-v2.md

## Your Task
Implement EXACTLY what is specified in the plan. Run verification after each file.

## Output
Write file: .agent-workflow/runs/2026-01-05__p6-7-4__probe-props-preservation/impl-v1.md
