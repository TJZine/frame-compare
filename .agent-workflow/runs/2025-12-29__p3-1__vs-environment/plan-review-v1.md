---
RUN_ID: 2025-12-29__p3-1__vs-environment
VERSION: v1
TARGET: Phase 3 → Item 3.1 Environment
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-review-v1.md
---

# Plan Review Report: VapourSynth Environment (Minimal Vertical Slice)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-29
**Plan Reference:** .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope is explicit. |
| 2 | Dependencies | PASS | Dependencies identified; import-layers change planned (needs precise contract edit). |
| 3 | File List | PASS | Exact files listed (but one change item is ambiguous; see below). |
| 4 | Contract Impact | PASS | Declares NO; includes contract check commands. |
| 5 | Types Complete | FAIL | Public dataclasses are underspecified (missing exact field types and defaults from SSOT). |
| 6 | Tests Complete | FAIL | Tests/assertions are underspecified and conflict with SSOT error semantics; `vs_required` handling is mis-described. |
| 7 | Verification Complete | PASS | Commands are explicit with pass criteria. |
| 8 | Decision-Minimizing | FAIL | Ambiguous “or verify” instruction; several behaviors rely on implied decisions (error class for missing VS; loader stub behavior). |
| 9 | Determinism Defined | PASS | No nondeterministic behavior introduced in this slice. |

## Additional Quality Checks

- Error Codes: Issue — plan asserts `ensure_vs_environment` raises `VapourSynthNotFoundError (FC-2001)`, but `vs-module.md` “3.1 Environment” currently says it raises `VapourSynthError` when VS is not available; SSOT needs clarification.
- Failure Modes: Issue — `DefaultVSLoader.load()` stub uses `NotImplementedError`, which is outside the project’s typed error taxonomy; prefer typed failure (`SourceLoadError`) or defer `DefaultVSLoader` entirely.
- Derived Outputs: OK — contract views/traceability are check-only in this run.
- Rollback Guidance: Issue — plan lacks an explicit “if ambiguous, STOP and return to Planning” workflow instruction.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:
1. Which error class represents “VapourSynth not installed” (`VapourSynthNotFoundError` vs `VapourSynthError`) and what tests should assert.
2. Exact dataclass field types/defaults for `SourceInfo`, `HDRMetadata`, `TonemapSettings`.
3. Whether `tests/conftest.py` changes are marker registration, skip behavior for `vs_required`, or a `mock_vs` fixture (current text says “or verify”).
4. What `DefaultVSLoader.load()` should raise while Phase 3.2 is deferred (typed error vs `NotImplementedError`).
5. Exact `importlinter.ini` layer order after inserting `frame_compare.vs`.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT spec first: clarify missing-VS error**
   - Edit file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
   - Under heading: "### 3.1 Environment" add/change:
     - Specify: missing `vapoursynth` import → raise `VapourSynthNotFoundError` (FC-2001).
     - Specify: other VS runtime/core failures → raise `VapourSynthError` (FC-2002) with details.
   - Under heading: "## 6. Error Handling" add/change:
     - Include `VapourSynthNotFoundError` in the “Error classes used by this module” table and import snippet.

2. **Make types fully specified (no defaults inferred)**
   - Section: `src/frame_compare/vs/types.py`
   - Problem: Plan lists field *names* only; SSOT defines field *types* and `TonemapSettings` defaults.
   - Required Change: In `plan-v2`, specify the exact dataclass definitions (field types + defaults) aligned to SSOT:
     - `vs-module.md` "### 2.1 SourceInfo"
     - `vs-module.md` "### 2.2 TonemapSettings"

3. **Remove ambiguity in `tests/conftest.py`**
   - Section: `tests/conftest.py`
   - Problem: “Add marker … or verify it’s in pyproject” is ambiguous, and marker is already defined in `pyproject.toml`.
   - Required Change: Choose exactly one concrete change:
     - Add the `mock_vs` fixture per `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md` (VapourSynth Stubs), and use it in unit tests; OR
     - Implement deterministic skip behavior for `@pytest.mark.vs_required` when VS is unavailable (if you want this slice to establish that infrastructure).
   - Also update the file list accordingly (only modify `tests/conftest.py` if an actual change is required).

4. **Replace `NotImplementedError` with typed failure or defer the stub**
   - Section: `src/frame_compare/vs/loader.py` + acceptance criteria + docs facts
   - Problem: `NotImplementedError` is not part of the project’s error taxonomy and leaks an untyped failure mode.
   - Required Change: In `plan-v2`, pick one explicit behavior and test it:
     - Preferred: `DefaultVSLoader.load()` raises `SourceLoadError(path, engine_error="...")` until Phase 3.2 implements `load_source`; OR
     - Move `DefaultVSLoader` out of this slice’s scope (only define `VSLoader` protocol in this run).

5. **Make import contract edit mechanically checkable**
   - Section: `importlinter.ini`
   - Problem: “Insert layer between analysis and config” leaves the final layer list implicit.
   - Required Change: Specify the full `layers =` order after change (verbatim list), so the Coding Agent doesn’t choose ordering.

6. **Add workflow-compliant STOP instruction**
   - Section: `## Notes for Coding Agent`
   - Required Change: “If SSOT ambiguity encountered: STOP and return to Planning with CHANGES REQUIRED; emit `plan-v2.md`.”

## Ready for Implementation

Return to Planning Agent for revision after SSOT updates. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-29__p3-1__vs-environment

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- Under heading: "### 3.1 Environment" add/change:
  - Missing `vapoursynth` import → raise `VapourSynthNotFoundError` (FC-2001).
  - Other VS runtime/core failures → raise `VapourSynthError` (FC-2002) with details.
- Under heading: "## 6. Error Handling" add/change:
  - Add `VapourSynthNotFoundError` to the module’s error list + import snippet.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-review-v1.md
Read file: .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v1.md
Write file: .agent-workflow/runs/2025-12-29__p3-1__vs-environment/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
