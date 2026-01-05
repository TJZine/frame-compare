---
RUN_ID: 2026-01-04__p6-5__tonemap-wiring
VERSION: v3
TARGET: Phase 6 → Item 6.5 (Tonemap Wiring)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v3.md
---

# Plan Review Report: Tonemap Wiring Integration

## Verdict: APPROVED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-04
**Plan Reference:** .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md

Plan-v3 is implementation-ready:
- SSOT now fully specifies deterministic HDR probing (`probe_is_hdr_ffprobe`) including parse rules + conservative return policy + exception mapping + fallback effects.
- VS-missing tonemap-required behavior is contract-aligned (fails fast via `VapourSynthNotFoundError (FC-2001)`; no FC-4004 customization).
- Public API signature change for `render_screenshots(..., config: ConfigSchema, ...)` is fully specified and call sites are enumerated.
- Test list includes tonemap gating scenarios + helper truth tables + probe-failure non-fallback behavior.
- Spec-anchor validation passes for `plan-v3.md`.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Phase 6.5 wiring only; explicit out-of-scope list. |
| 2 | Dependencies | PASS | All required modules/types/errors are named and spec-anchored. |
| 3 | File List | PASS | Complete and explicit, including SSOT edits + in-repo call sites. |
| 4 | Contract Impact | PASS | Contracts untouched; runtime behavior is aligned to existing contracts. |
| 5 | Types Complete | PASS | One-line backticked signatures provided for public API + new helpers. |
| 6 | Tests Complete | PASS | Exact test names + required assertions; includes negative probe-failure case. |
| 7 | Verification Complete | PASS | Full pyright/ruff/pytest + import-linter; explicit pass criteria. |
| 8 | Decision-Minimizing | PASS | No open algorithm/error/behavior choices remain. |
| 9 | Determinism Defined | PASS | Deterministic gating + deterministic probe + deterministic failure policy. |

## Additional Quality Checks

- Error Codes: OK (no new errors; FC-2001 used for VS-missing tonemap-required)
- Failure Modes: OK (probe failures explicitly disallow fallback when `enable_tonemap=True`)
- Derived Outputs: OK (no contract generators involved)
- Rollback Guidance: OK (STOP guidance present for unexpected callers)
- SSOT Update Audit (this loop): OK (SSOT edits are implementable, deterministic, and contract-aligned)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NONE

## Ready for Implementation

All checklist items pass. Coding Agent may proceed.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-5__tonemap-wiring

## Precondition
Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v3.md
Confirm: Verdict is APPROVED and Decision Points Remaining is NONE.

## Files to Read
1. Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
2. Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v3.md

## Your Task
Implement the plan exactly. Do not make design decisions; if something is missing from SSOT, STOP and return to Planning/Plan Review with CHANGES REQUIRED.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/impl-v1.md
