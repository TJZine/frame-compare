---
RUN_ID: 2026-01-01__p4-1__render-types
VERSION: v3
TARGET: Phase 4 → Item 4.1
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v3.md
---

# Plan Review Report: Render Module Types

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v3.md

The plan is now close to implementation-ready (SSOT-aligned types, Pyright-safe optional VS typing, explicit import-linter updates, deterministic tests). One remaining gap: verification commands don’t match the workflow’s “tooling” gate scope (ruff is only run on `src/frame_compare/render/`, so test-file lint failures can slip through and later fail CI/Verification).

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; explicit out-of-scope list. |
| 2 | Dependencies | PASS | Optional VS typing pattern and import-contract changes specified. |
| 3 | File List | PASS | Explicit create/modify/delete list, including `.gitkeep` and `importlinter.ini`. |
| 4 | Contract Impact | PASS | Canonical contracts untouched; no contract regen gates required. |
| 5 | Types Complete | PASS | Types are fully specified by SSOT code blocks; plan instructs “copy exactly” and pins decorators. |
| 6 | Tests Complete | PASS | Exact test names + deterministic assertions (including `typing.get_args(Renderer)`). |
| 7 | Verification Complete | FAIL | Ruff scope does not include `tests/render/` and diverges from workflow’s canonical `.venv/bin/ruff check .` gate. |
| 8 | Decision-Minimizing | FAIL | Coding agent must decide whether to run ruff on tests / whole repo vs just `src/frame_compare/render/`. |
| 9 | Determinism Defined | PASS | N/A for types-only slice. |

## Additional Quality Checks

- Error Codes: OK — no new/changed `FC-xxxx` errors.
- Failure Modes: OK — Pyright-safe `vapoursynth` typing explicitly handled.
- Derived Outputs: OK — none.
- Rollback Guidance: OK — STOP rules present for import contract ambiguity / missing imports.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Verification scope for Ruff (tests vs src-only) is not specified in a way that guarantees CI/Verification parity.

## Concrete Edits Required (plan-only)

1. **Align Ruff verification with workflow gate scope**
   - Section: `## Verification Commands`
   - Problem: `.venv/bin/ruff check src/frame_compare/render/` does not lint `tests/render/`, and diverges from the workflow’s preferred `.venv/bin/ruff check .`.
   - Required Change: Update verification to one of the following (pick exactly one, and mirror it in the uv-run fallback):
     - Preferred: `.venv/bin/ruff check .`
     - Minimal slice: `.venv/bin/ruff check src/frame_compare/render/ tests/render/`
   - Pass criteria: Ruff exits 0 with no errors.

## Ready for Implementation

Return to Planning Agent for a plan-only revision. Next version: plan-v4.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-1__render-types

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v3.md
Read file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v3.md
Write file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
