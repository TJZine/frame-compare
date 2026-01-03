---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v10
TARGET: Meta → Phase 5 → Quality Gate Fixes (Docker-first)
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v9.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v9.md
  - Dockerfile
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v10.md
---

# Plan Review Report: Phase 5 Quality Gate Fixes (Docker-first)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v9.md`

The Spec Anchor STOP gate now passes and the SSOT formatting fix is sound. However, the plan still leaves an implementation-affecting ambiguity/bug in the `_apply_libplacebo` pseudocode (RGBS conversion is incorrectly indented inside the exception block), and it does not define a test/verification that proves “libplacebo has Vulkan support” (fallback behavior could mask a still-broken Vulkan backend).

## Spec Anchor STOP Gate (Required)

Ran:

`UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v9.md`

Result: **PASS (exit 0)**

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; follow-up parity gaps explicitly out-of-scope. |
| 2 | Dependencies | PASS | Correctly ties Docker build/runtime + tonemap + Docker gate. |
| 3 | File List | PASS | Concrete list; no “and related files”. |
| 4 | Contract Impact | PASS | No canonical contract changes. |
| 5 | Types Complete | PASS | Public signatures are listed and align with SSOT headings; STOP gate passes. |
| 6 | Tests Complete | FAIL | No test/verification guarantees libplacebo Vulkan path actually succeeds (fallback could make Docker tests pass while Vulkan is still broken). |
| 7 | Verification Complete | PASS | Includes static gates + import-lint + Docker integration gate with pass criteria. |
| 8 | Decision-Minimizing | FAIL | `_apply_libplacebo` post-tonemap RGBS conversion is placed inside the exception block (plan bug), and Vulkan-success verification is not mandated. |
| 9 | Determinism Defined | PASS | Deterministic fallback behavior defined in SSOT. |

## SSOT Update Audit (Required)

**Audit target:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` → `### 5.2 libplacebo Integration`

- SSOT change (indent code-block comment lines) is **mechanical and sound**.
- SSOT signature for `_apply_libplacebo(..., hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode | None` is **sound** and matches the plan’s signature bullets.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether Docker is required to validate “libplacebo Tonemap succeeds” vs “fallback makes tests pass” must be mandated in the plan (currently ambiguous).
2. The plan’s `_apply_libplacebo` pseudocode must be corrected so a Coding Agent cannot accidentally implement the conversion-back inside the exception path.

## Concrete Edits Required (CHANGES REQUIRED)

1. **Fix `_apply_libplacebo` pseudocode indentation (blocking)**
   - File: `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v10.md` (new plan; do not edit plan-v9 in place)
   - Section: `src/frame_compare/vs/tonemap.py` → “Change 3: Add post-tonemap RGBS conversion + runtime failure handling”
   - Required change:
     - Move the “Convert libplacebo output back to RGBS for post-processing” step to run only on success (i.e., after the `try/except`, not inside `except`).
     - The plan snippet must be copy/paste-correct, with the conversion line at the correct indentation level.

2. **Add an explicit Docker-only verification that libplacebo Tonemap succeeds (blocking)**
   - File: `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v10.md`
   - Section: Acceptance Criteria / Tests
   - Required change (choose one; mandate exactly one in the plan):
     - **Option A (preferred):** Modify `tests/vs/test_integration.py::test_vs_integration_smoke` to assert libplacebo tonemap succeeds without falling back (e.g., call `_apply_libplacebo(...)` and assert it returns a `vs.VideoNode` and not `None` inside Docker), OR
     - **Option B:** Add a new `tests/vs/test_integration.py` test that calls `_apply_libplacebo` directly and asserts a non-None return (ensures Vulkan backend is usable in Docker).
   - Rationale: The plan explicitly changes the Docker image to enable Vulkan; the Docker gate must prove the Vulkan path works, not only that fallback prevents failures.

3. **Align Docker success criteria to the mandated behavior**
   - File: `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v10.md`
   - Section: Acceptance Criteria
   - Required change:
     - Update the “libplacebo has Vulkan support” criterion to be mechanically checkable by the mandated test(s) in item (2).

## Ready for Implementation

Not ready. Requires a revised plan (`plan-v10.md`) that removes the remaining decision points and makes Docker libplacebo Vulkan success verifiable.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Revision Required
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v10.md
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v9.md
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v10.md

## Hard Rules
- Do not edit plan-v9 in place; write plan-v10.md with `## Changes Since plan-v9`.
- Keep Spec Anchors unchanged unless SSOT headings changed.
- The revised plan must mandate a Docker integration test that proves libplacebo Tonemap succeeds (not just fallback).
