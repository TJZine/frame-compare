---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v9
TARGET: Meta → Phase 5 → Quality Gate Fixes (Docker-first)
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v8.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v8.md
  - Dockerfile
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v9.md
---

# Plan Review Report: Phase 5 Quality Gate Fixes (Docker-first)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v8.md`

The plan is close and the SSOT signature change is directionally correct, but the plan is not implementation-ready because the Spec Anchor validator fails due to an SSOT formatting/validator interaction, and the Docker Vulkan wiring contains an architecture-specific assumption that can break the Docker gate.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: “Phase 5 Docker-first quality gate pass”, with explicit deferred follow-ups. |
| 2 | Dependencies | PASS | Correctly ties Docker build/runtime + tonemap behavior + Docker test gate. |
| 3 | File List | PASS | Explicit list for Dockerfile, tonemap, tests, docker gate script, docs. |
| 4 | Contract Impact | PASS | No canonical contract edits required. |
| 5 | Types Complete | FAIL | STOP: `validate_spec_anchors.py` fails; function-name presence is not discoverable in anchored SSOT spans. |
| 6 | Tests Complete | PASS | Adds a deterministic unit test for runtime-failure fallback. |
| 7 | Verification Complete | PASS | Includes static gates + `lint-imports` + Docker integration gate with pass criteria. |
| 8 | Decision-Minimizing | FAIL | Docker Vulkan ICD path is architecture-specific; libplacebo meson flag change omits a required constraint (`-Dopengl=disabled`) leaving build behavior to chance. |
| 9 | Determinism Defined | PASS | Fallback trigger is deterministic; no new randomized behavior. |

## SSOT Update Audit (Required)

**Audit target:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` → `### 5.2 libplacebo Integration`

- **SSOT behavior/signature change:** OK
  - `_apply_libplacebo(..., hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode | None` is sound and resolves the earlier “signature vs behavior” mismatch.
- **SSOT formatting vs validator:** **Issue (blocking)**
  - The `validate_spec_anchors.py` heading-span extraction treats any line starting with `#` as a Markdown heading even inside fenced code blocks.
  - In `### 5.2 libplacebo Integration`, fenced code blocks include comment lines like `# Exact conversion call ...` at column 0, which truncates the anchored span before the `_apply_libplacebo` `def` block appears.
  - Result: the anchored SSOT span does not contain `def _apply_libplacebo`, so the plan fails the STOP-gate validator.

**Evidence:** Running `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v8.md` fails, even though the SSOT section text contains the function—because the anchored span is truncated early.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. SSOT must be formatted so the spec-anchor validator can actually “see” the required function names in the anchored spans.
2. Docker Vulkan ICD selection must not assume `x86_64` (this repo’s Dockerfile already implies non-x86 multiarch paths elsewhere).

## Concrete Edits Required (CHANGES REQUIRED)

1. **Fix SSOT so `validate_spec_anchors.py` can parse Section 5.2 (blocking)**
   - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
   - Under heading: `### 5.2 libplacebo Integration`
   - Required change (mechanical, no behavior change):
     - In fenced code blocks under this heading, remove or indent any standalone comment lines that start with `#` at column 0 (e.g., `# Exact conversion call for libplacebo path`, `# Convert libplacebo output back to RGBS ...`, `# Exact conversion call for fallback path ...`).
     - Goal: the anchored span for `### 5.2 libplacebo Integration` must include the `def _apply_libplacebo` block so the validator can find `def _apply_libplacebo`.

2. **Revise the plan to remove architecture-specific Vulkan assumptions (blocking)**
   - File: `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v9.md` (new plan; do not edit plan-v8 in place)
   - Section: `Dockerfile` changes
   - Required change:
     - Do NOT hardcode `ENV VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.x86_64.json` (breaks arm64 builds). Either:
       - Omit `VK_ICD_FILENAMES` entirely (preferred), or
       - Set it in `tools/verify_docker_integration.sh` dynamically by discovering the installed `lvp_icd.*.json` file inside the container.
     - Ensure the libplacebo build remains headless/deterministic by explicitly keeping `-Dopengl=disabled` while enabling Vulkan.

3. **Re-run the STOP gate validator after SSOT+plan revision (required)**
   - After the revised plan is written, the Planning Agent must confirm:
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v9.md` exits 0.

## Ready for Implementation

Not ready. Fix the SSOT formatting issue (so anchors are extractable) and revise the Docker Vulkan ICD wiring to be architecture-safe, then re-issue the plan.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- Under heading: "### 5.2 libplacebo Integration" add/change:
  - In fenced code blocks, remove or indent any standalone lines that begin with `#` at column 0 (these are mis-parsed as Markdown headings by `validate_spec_anchors.py` and truncate the anchored section before `def _apply_libplacebo`).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v9.md
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v8.md
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v9.md

## Hard Rules
- Spec Anchors must pass the STOP gate:
  - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v9.md`
- Do not hardcode an architecture-specific `VK_ICD_FILENAMES` path in `Dockerfile`.
- Keep libplacebo build headless: explicitly keep `-Dopengl=disabled` while enabling Vulkan.
