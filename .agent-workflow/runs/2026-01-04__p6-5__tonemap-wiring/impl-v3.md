# Implementation Report v3: Phase 6.5 Tonemap Wiring

**RUN_ID:** `2026-01-04__p6-5__tonemap-wiring`
**Date:** 2026-01-04
**Previous Report:** impl-v2.md
**Review Addressed:** review-v1.md

## Summary

Addressed 2 Critical issues from review-v1.md.

## Fixes Applied

### Critical Issue 1: Public API export not in plan/SSOT

**Location:** src/frame_compare/render/**init**.py:11

**Fix:** Removed `probe_is_hdr_ffprobe` from imports and `__all__`.

The function remains internal to `orchestrator.py` and is not part of the public API per plan-v3 §3 (Add exports: `should_tonemap`, `resolve_tonemap_settings` only).

### Critical Issue 2: DECISIONS.md entry incomplete

**Location:** docs/DECISIONS.md:518

**Fix:** Expanded entry per plan-v3 §7 to include:

- Full artifact versions (plan-v3 + plan-review-v3 + impl-v1 + impl-v2 + impl-v3 + verify-v2 + review-v1)
- SSOT edits (render-module.md §1.4.1, §1.4.4, §3.1, §7.2)
- Contract alignment decision (FC-2001, no FC-4004)
- Probe determinism decision (probe failures disallow fallback when enable_tonemap=True)
- Out-of-scope items (CLI overrides, VSPreview, FramePlan)
- Complete verification gate list

## Verification Gates

| Gate | Result |
|------|--------|
| pyright --warnings | ✅ 0 errors |
| ruff check | ✅ All checks passed |
| pytest (unit) | ✅ All passed (1 skipped) |
| generate_contract_views --check | ✅ All derived files up-to-date |

## NEXT AGENT PROMPT

```
You are the Verification Agent for RUN_ID 2026-01-04__p6-5__tonemap-wiring.

Read:
1. .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
2. .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/impl-v3.md
3. .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/review-v1.md

Verify:
1. All Critical issues from review-v1 addressed
2. Run quality gates (pyright, ruff, pytest)
3. Verify contract freshness

Output: verify-v3.md with pass/fail summary and handoff block.
```
