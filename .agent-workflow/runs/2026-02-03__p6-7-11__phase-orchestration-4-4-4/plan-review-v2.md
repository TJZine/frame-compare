---
RUN_ID: 2026-02-03__p6-7-11__phase-orchestration-4-4-4
VERSION: v2
TARGET: Phase 6 → Item 6.7 Runner & Phase Orchestration — Implement phase orchestration per spec §4.4.4
INPUTS:
  - .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-review-v2.md
---

# Plan Review Report: Phase Orchestration (Phase Ordering §4.4.4)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-03
**Plan Reference:** .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single checklist slice (Phase 6 → Item 6.7); out-of-scope called out. |
| 2 | Dependencies | PASS | Dependencies and existing modules/functions are identified (preflight/context/probe_cache/probe_props/progress). |
| 3 | File List | PASS | Minimal and explicit (2 orchestration files + 2 test files). |
| 4 | Contract Impact | PASS | Explicit “Contracts touched: NO”; check commands included. |
| 5 | Types Complete | PASS | Public function signatures are explicit and spec-anchored. |
| 6 | Tests Complete | PASS | Test file + exact unit test names listed; execute_run tests updated with concrete expectations. |
| 7 | Verification Complete | PASS | Concrete commands + pass criteria provided. |
| 8 | Decision-Minimizing | FAIL | Failure-policy mapping + Align phase handling are not fully specified (see Concrete Edits). |
| 9 | Determinism Defined | PASS | Deterministic input ordering + deterministic timing keys + `0.0` for skipped phases defined. |

## Additional Quality Checks

- Error Codes: OK (no new error-code mapping proposed in this slice).
- Failure Modes: Issue — warn-only vs fail-fast mapping is not fully specified in a way that is consistent with the Phase 5 (Align) description.
- Derived Outputs: OK (no derived views expected to change; check commands included).
- Rollback Guidance: OK (changes are localized; revert via standard VCS rollback).
- SSOT Update Audit (if SSOT changed this loop): OK (no SSOT/spec changes indicated).

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: 2

1. How warn-only vs fail-fast is determined in `execute_phases(...)` in a way that is unambiguous and aligned to §4.4.4.
2. How Phase 5 (Align) is represented (skip_condition / warn-only semantics) under the chosen failure-policy rule.

## Concrete Edits Required (for plan-v3.md)

1. **Make failure policy mapping explicit and §4.4.4-aligned**
   - Section: “1. [MODIFY] `src/frame_compare/orchestration/phases.py`” → “Key implementation notes” → “Failure policy”
   - Problem: The current classification rule (“`skip_condition is None` → fail-fast, else warn-only”) is not explicitly reconciled with the Phase 5 (Align) entry in the Phase 3–10 list, which does not specify an Align skip_condition. This leaves a behavior decision to the Coding Agent and risks an unintended fail-fast Align.
   - Required Change: Update the plan to state the exact rule used to classify phases as warn-only vs fail-fast in a way that directly corresponds to the §4.4.4 table (required vs optional phases), without requiring the Coding Agent to infer special cases.

2. **Resolve Align phase handling under the chosen policy**
   - Section: “2. [MODIFY] `src/frame_compare/orchestration/coordinator.py`” → “Phases 3–10 (Ordering + Semantics)”
   - Problem: The plan lists Align as “optional / warn-only” but does not specify how Align is encoded so that `execute_phases(...)` will treat it as warn-only under the PhaseStatus/Phase model. In addition, §4.4.4 lists “No audio tracks” as Align’s skip condition; the plan must either define how that condition is evaluated in this slice or explicitly defer it (and state the resulting behavior for Align now).
   - Required Change: Update the plan to explicitly define Align’s `skip_condition` behavior for this slice (including whether “no audio tracks” is evaluated now, and how) and ensure it is consistent with the failure-policy rule from Edit #1.

## Ready for Implementation

Return to Planning Agent for `plan-v3.md` revisions. Coding must not proceed until this report is APPROVED and Decision Points Remaining is NONE.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID

2026-02-03__p6-7-11__phase-orchestration-4-4-4

## Target

Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement phase orchestration per spec §4.4.4

## Files To Read

1. Read file: .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v2.md
2. Read file: .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-review-v2.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Revise the plan to address the “Concrete Edits Required” in plan-review-v2.md. Emit plan-v3.md with a “Changes Since plan-v2” section and re-run the spec-anchor validator command listed in the plan.

## Output

Write file: .agent-workflow/runs/2026-02-03__p6-7-11__phase-orchestration-4-4-4/plan-v3.md
