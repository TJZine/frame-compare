---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v13
TARGET: Meta → Phase 5 → Docker Gate Fixes (verify-v4 blockers)
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v12.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - src/frame_compare/errors.py
  - Dockerfile
  - tools/verify_docker_integration.sh
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v13.md
---

# Plan Review Report: Phase 5 Docker Gate Fixes (verify-v4 blockers)

## Verdict: APPROVED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v12.md`

Plan-v12 is implementation-ready and directly addresses all verify-v4 Docker blockers with a single mandated approach, including an SSOT alignment for the RGB/YUV conversion rule.

## Spec Anchor STOP Gate (Required)

Ran:

`UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v12.md`

Result: **PASS (exit 0)**

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Narrow: only verify-v4 Docker blockers. |
| 2 | Dependencies | PASS | Captures Docker + VS resize rules + Vulkan loader + pytest plugin. |
| 3 | File List | PASS | Explicit `Dockerfile`, `tonemap.py`, `verify_docker_integration.sh`, SSOT doc. |
| 4 | Contract Impact | PASS | No canonical contract edits. |
| 5 | Types Complete | PASS | Public signatures listed; SSOT anchored. |
| 6 | Tests Complete | PASS | Uses existing Docker tests as the proof; adds deterministic Vulkan env for the Docker gate. |
| 7 | Verification Complete | PASS | Includes STOP gate + local gates + Docker primary gate with explicit pass criteria. |
| 8 | Decision-Minimizing | PASS | Mandates exact fixes for pytest-mock, matrix handling, and lavapipe selection. |
| 9 | Determinism Defined | PASS | Vulkan selection is deterministic via lavapipe ICD pinning when present. |

## SSOT Update Audit (Required)

**SSOT updated this loop:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` → `### 5.2 libplacebo Integration`

- Change is sound and required by observed runtime constraints:
  - RGB inputs must not pass YUV matrix coefficients (`matrix_in_s`) when converting RGB→RGB formats.
  - YUV inputs retain `matrix_in_s="709"` for deterministic YUV→RGB conversion.
- No contradictions introduced with `### 3.3 Tonemapping` or `### 5.3 Fallback Handling`.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NONE

## Ready for Implementation

All checklist items pass. Coding Agent may proceed.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Approved Plan
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v12.md

## Plan Review Approval
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v13.md

## Verification Context
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v4.md

## Your Task
Implement the plan exactly. After implementation, rerun:
- `bash tools/verify_docker_integration.sh`

## Output
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v4.md
