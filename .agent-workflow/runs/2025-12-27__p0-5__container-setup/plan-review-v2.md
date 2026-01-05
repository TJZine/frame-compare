---
RUN_ID: 2025-12-27__p0-5__container-setup
VERSION: v2
TARGET: Phase 0 → Item 0.5 (Container Setup)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/002-containerization.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v2.md
---

# Plan Review Report: Container Setup (Phase 0.5)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-28
**Plan Reference:** .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single infra slice; explicit out-of-scope list (publish/GPU/docs). |
| 2 | Dependencies | FAIL | Runtime apt packages are distro-version-specific (`libavcodec60`, etc.) while base image is unpinned (`python:3.13-slim`), making the dependency set non-portable and likely to break. |
| 3 | File List | PASS | Explicit and minimal (`Dockerfile`, `docker-compose.yml`, `.devcontainer/devcontainer.json`, `.dockerignore`). |
| 4 | Contract Impact | PASS | Explicit “Contracts touched: NO”. |
| 5 | Types Complete | PASS | No Python public API introduced/changed in this slice. |
| 6 | Tests Complete | FAIL | No negative/failure-mode checks; “functional” lsmas check relies on an API not specified/verified (`c.lw.Version()`). |
| 7 | Verification Complete | FAIL | Commands are runnable now, but key assertions are likely incorrect/unstable (VapourSynth version check uses `core.version()` with numeric compare; lsmas uses `c.lw.Version()`). |
| 8 | Decision-Minimizing | FAIL | Two unresolved decision points remain: base image pin strategy and correct runtime deps/verification APIs; Coding Agent cannot safely choose. |
| 9 | Determinism Defined | FAIL | Git SHAs/tags are pinned, but base images are not pinned to a digest (and runtime deps depend on the base distro). |

## Additional Quality Checks

- Error Codes: OK (no new errors for infra-only slice)
- Failure Modes: Issue — “STOP and return to Planning” is present, but verification should also include at least one explicit negative check to validate failure behavior
- Derived Outputs: OK
- Rollback Guidance: OK (explicit file deletion + Docker cleanup + return-to-planning trigger)

## Implementation Regression Check (Against plan-review-v1 “Concrete Edits Required”)

- Verification commands executable with ENTRYPOINT: ADDRESSED (uses `--entrypoint python`)
- Non-deterministic git clones: ADDRESSED (explicit refs)
- Remove “iterate on missing deps”: ADDRESSED (explicitly forbids ad-hoc deps)
- Add plugin checks: PARTIALLY ADDRESSED (placebo ok; lsmas check uses unverified API)
- Resolve docs/ignore decisions: ADDRESSED (adds `.dockerignore`, defers docs explicitly)
- Add rollback: ADDRESSED

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Decide and specify a deterministic base image pin (exact `FROM` tags and/or `@sha256` digests) so builds don’t drift.
2. Decide and specify a runtime dependency strategy that is valid for the pinned base distro (avoid `libavcodecXX` guessing).
3. Decide and specify correct verification APIs for VapourSynth and lsmas that match the project’s own spec/docs (no “maybe it exists” calls).

## Concrete Edits Required (for plan-v3.md)

1. **Pin base images deterministically**
   - Section: `Dockerfile` (both stages)
   - Problem: `FROM python:3.13-slim` floats over time, invalidating apt package names and undermining reproducibility.
   - Required Change: Specify exact base image references for builder and runtime:
     - Either pin to a fully-qualified variant (e.g., `python:3.13.x-slim-bookworm`) AND state that suite explicitly, or
     - Pin by digest (`python:3.13-slim@sha256:...`) for both stages.

2. **Fix VapourSynth version verification to use a numeric API**
   - Section: `Acceptance Criteria` and `Verification Commands`
   - Problem: `vs.core.version()` is not guaranteed to be a numeric type; comparing to `73` may fail.
   - Required Change: Use the numeric API referenced elsewhere in project docs/tests:
     - `v = vs.core.version_number(); assert v >= 73`
     - Acceptance criteria must match the exact command.

3. **Fix lsmas verification to match the module spec’s detection pattern**
   - Section: `Acceptance Criteria` and `Verification Commands`
   - Problem: `c.lw.Version()` is not defined in the repo specs and may not exist; this is not implementation-ready.
   - Required Change: Replace with the spec-aligned check:
     - `assert hasattr(c, 'lw') and hasattr(c.lw, 'LWLibavSource')`
     - Optionally print the callable name to confirm linkage; do not call unknown APIs.

4. **Replace runtime lib version guessing with a stable dependency strategy**
   - Section: `Dockerfile` runtime stage
   - Problem: `libavcodec60`, `libavformat60`, etc. are not stable across Debian suites; this is likely to break on the chosen base.
   - Required Change: Choose one deterministic approach and specify it explicitly:
     - Option A: Install `ffmpeg` (runtime) plus any non-transitive libs needed (`libzimg2`, `libxxhash0`) on the pinned suite.
     - Option B: Pin the Debian suite and use the correct matching `libavcodecXX` names for that suite (must be correct and listed explicitly).
   - Note: The plan must remove any need for the Coding Agent to “try and see”.

5. **Add one explicit negative verification**
   - Section: `Verification Commands`
   - Problem: Checklist requires negative/failure-mode coverage; current commands only assert happy path.
   - Required Change: Add a command that intentionally breaks plugin discovery and asserts failure (exit non-zero), e.g.:
     - Set `VAPOURSYNTH_PLUGIN_PATH=/nonexistent` and assert the lsmas/placebo checks fail with an assertion message.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-27__p0-5__container-setup

## Revision Required
Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v2.md
This report contains specific changes required for the plan.

## Previous Plan
Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v2.md

## Your Task
Address all items marked FAIL in the plan review. Create a revised plan as a new file (do not edit plan-v2 in place).

## Output
Write file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v3.md
