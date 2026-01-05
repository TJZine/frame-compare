---
RUN_ID: 2025-12-27__p0-5__container-setup
VERSION: v1
TARGET: Phase 0 → Item 0.5 (Container Setup)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/002-containerization.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v1.md
---

# Plan Review Report: Container Setup (Phase 0.5)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-28
**Plan Reference:** .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Dockerfile/compose/devcontainer) with explicit out-of-scope list. |
| 2 | Dependencies | FAIL | Missing pinned git SHAs for several source builds; host prerequisites (Docker/Compose versions) not specified. |
| 3 | File List | FAIL | Missing explicit decision on `.dockerignore` and docs updates (README/deployment instructions) vs explicitly out-of-scope. |
| 4 | Contract Impact | PASS | Explicit “Contracts touched: NO”. |
| 5 | Types Complete | PASS | No Python API/type surface touched in this slice. |
| 6 | Tests Complete | FAIL | Only smoke checks listed; no negative cases and several checks are not executable as written (see Verification). |
| 7 | Verification Complete | FAIL | `docker run frame-compare:dev python -c ...` will not run due to `ENTRYPOINT ["frame-compare"]`; commands must use `--entrypoint` or change entrypoint strategy. |
| 8 | Decision-Minimizing | FAIL | Plan instructs “Dockerfile may need iteration… add missing deps” (decision point) and leaves build flags/pinning unresolved. |
| 9 | Determinism Defined | FAIL | Uses HEAD clones for L-SMASH-Works/libplacebo/vs-placebo; no deterministic versioning strategy specified. |

## Additional Quality Checks

- Error Codes: OK (no new errors specified/needed for this infra-only slice)
- Failure Modes: Issue — missing explicit handling for build failures, missing plugins, and offline/no-network Docker builds (must define stop/rollback behavior instead of “iterate”)
- Derived Outputs: OK (no generated/derived artifacts in this slice)
- Rollback Guidance: Issue — no rollback steps if containerization introduces regressions

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Pin exact git SHAs/tags for every source build (L-SMASH-Works, libplacebo, vs-placebo) instead of cloning HEAD.
2. Choose and document an entrypoint strategy, then make verification commands executable (either use `--entrypoint` for Python checks or remove/adjust `ENTRYPOINT`).
3. Provide a complete, fixed apt dependency list and build flags (remove “may need iteration” guidance).
4. Decide whether this slice updates any docs (`README.md`, `docs/.../deployment.md`) and whether `.dockerignore` is required.

## Concrete Edits Required (for plan-v2.md)

1. **Make verification commands executable**
   - Section: `Acceptance Criteria` and `Verification Commands`
   - Problem: Commands conflict with `ENTRYPOINT ["frame-compare"]` (e.g., `docker run ... python -c ...` will invoke `frame-compare` instead of `python`).
   - Required Change: Specify one approach and update all commands accordingly:
     - Option A (recommended): keep `ENTRYPOINT ["frame-compare"]`, and use:
       - `docker run --rm frame-compare:dev --help`
       - `docker run --rm --entrypoint python frame-compare:dev -c "import vapoursynth; ..."`
     - OR Option B: remove/replace ENTRYPOINT and adjust all commands to match.

2. **Eliminate non-deterministic source builds**
   - Section: `Dockerfile` (Builder stage)
   - Problem: Several `git clone --depth 1` steps pull floating HEAD (breaks determinism and reproducibility).
   - Required Change: Add explicit version pins for each repo (tag or full commit SHA) and include the exact values in the plan (no “latest”, no HEAD). Example requirement (illustrative structure): `ARG LIBPLACEBO_REF=<sha>` then `git checkout "$LIBPLACEBO_REF"`.

3. **Remove “iterate on missing deps” and replace with fixed dependency lists**
   - Section: `Notes for Coding Agent` and `Dockerfile` build deps
   - Problem: “Dockerfile may need iteration… add missing deps” is a decision point and makes the plan non-executable without additional design choices.
   - Required Change: Provide a complete, explicit `apt-get install` list for each stage sufficient to build all specified components; if a build fails anyway, the plan must instruct the Coding Agent to STOP and return to Planning (plan update), not to ad-hoc patch.

4. **Define minimal plugin functional smoke checks (not just `hasattr`)**
   - Section: `Acceptance Criteria` and `Verification Commands`
   - Problem: `hasattr(core, "placebo")` can be true even if the plugin is mislinked/doesn’t load correctly at runtime.
   - Required Change: Add one minimal, explicit functional check per critical plugin namespace (e.g., instantiate/call `core.lw.LWLibavSource` on a known file path placeholder with “skipped if no sample provided”, and call `core.placebo.Tonemap` on a synthetic clip) and define exact expected output/exit code.

5. **Resolve documentation and ignore-file decisions**
   - Section: `Files to Create/Modify`
   - Problem: Plan does not specify whether to add `.dockerignore` and where/how to document Docker/DevContainer usage.
   - Required Change: Either:
     - Add `.dockerignore` with an explicit line list, and add a docs update target (e.g., `README.md` or `docs/OPUS_REBUILD_FRAME_COMPARE/06-operations/deployment.md`) including the exact commands/paths; OR
     - Explicitly declare these doc/ignore updates out-of-scope for Phase 0.5 and justify where they will be covered next.

6. **Add rollback guidance**
   - Section: add `Rollback` section
   - Problem: No rollback steps if build breaks CI/dev.
   - Required Change: Specify exact rollback steps (files to delete/revert, and optional Docker clean commands) and the condition that triggers rollback.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-27__p0-5__container-setup

## Revision Required
Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v1.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v1.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan.

## Output
Write file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v2.md
