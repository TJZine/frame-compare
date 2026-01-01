---
RUN_ID: 2026-01-01__p4-2__render-geometry
VERSION: v2
TARGET: Phase 4 → Item 4.2
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-review-v2.md
---

# Plan Review Report: Render Geometry Utilities

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v2.md

Plan-v2 correctly anchors to newly added SSOT subsections for geometry behavior, but it is not yet implementation-ready because it (a) omits the SSOT spec file from the file-change list despite changing it, (b) leaves `render/__init__.py` export edits ambiguous, (c) includes underspecified test scenarios (one case depends on unspecified `position`), and (d) has incomplete verification fallbacks / insufficient Pyright scope for the files it modifies.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice; out-of-scope list explicit. |
| 2 | Dependencies | PASS | Depends on Phase 4.1 types; no new external deps. |
| 3 | File List | FAIL | SSOT was edited (Sections 5.1–5.3 added) but `render-module.md` is not listed under files to modify. |
| 4 | Contract Impact | PASS | Canonical contracts untouched. |
| 5 | Types Complete | PASS | Function signatures are explicit and typed. |
| 6 | Tests Complete | FAIL | One test scenario is ambiguous (`test_overlay_position_clamps_when_too_large` missing `position` and explicit image/overlay sizes in the scenario field), leaving a decision to the Coding Agent. |
| 7 | Verification Complete | FAIL | Fallback commands are commented and missing `--no-sync`; Pyright scope only checks `geometry.py` despite modifying `render/__init__.py`. |
| 8 | Decision-Minimizing | FAIL | `render/__init__.py` update includes placeholder “existing exports…” and does not specify exact `__all__` integration behavior. |
| 9 | Determinism Defined | PASS | SSOT now defines deterministic rounding/clamping rules. |

## Additional Quality Checks

- Error Codes: OK — no new/changed `FC-xxxx`.
- Failure Modes: OK — invalid-input behavior is now defined in SSOT (ValueError with specific messages).
- Derived Outputs: OK — no generated views in this slice.
- Rollback Guidance: OK — spec-anchor validation gate included.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact interpretation of the clamp test (depends on unspecified `position`).
2. Exact `render/__init__.py` export integration details (placeholder text).
3. Verification fallback commands and Pyright scope to cover modified files.

## Concrete Edits Required (plan-only)

1. **List the SSOT spec file as modified**
   - Section: `## Files to Create/Modify`
   - Problem: Plan states SSOT was updated (Sections 5.1–5.3) but does not list the SSOT file.
   - Required Change: Add:
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` [MODIFY] — “Added `### 5.1`, `### 5.2`, `### 5.3` behavior rules (no other changes).”

2. **Make `test_overlay_position_clamps_when_too_large` scenario fully explicit**
   - Section: `tests/render/test_geometry.py` test table
   - Problem: Expected `(0, 0)` only holds for specific `position` / image size / overlay size / margin.
   - Required Change: Spell out all inputs in the scenario cell, e.g.:
     - `image=(1920,1080), overlay=(1900,1060), position="bottom-right", margin=50` → expected `(0,0)`

3. **Make `render/__init__.py` export update deterministic**
   - Section: `src/frame_compare/render/__init__.py` [MODIFY]
   - Problem: Placeholder “existing exports…” is not implementable without looking up current code and deciding ordering.
   - Required Change: Specify exact behavior:
     - Keep all existing imports and `__all__` entries unchanged (from Phase 4.1), and append `calculate_dimensions`, `calculate_overlay_position`, `ensure_mod2` to `__all__` in that order.

4. **Fix verification commands to match workflow and cover changed files**
   - Section: `## Verification Commands`
   - Problems:
     - Fallback commands are commented and omit `--no-sync`.
     - Pyright only checks `geometry.py` but `render/__init__.py` is modified too.
   - Required Change:
     - Primary: `.venv/bin/pyright --warnings src/frame_compare/render/`
     - Fallbacks (uncommented and deterministic):
       - `UV_CACHE_DIR=./.uv_cache uv run --no-sync pyright --warnings src/frame_compare/render/`
       - `UV_CACHE_DIR=./.uv_cache uv run --no-sync ruff check src/frame_compare/render/ tests/render/`
       - `UV_CACHE_DIR=./.uv_cache uv run --no-sync pytest -v tests/render/test_geometry.py`

## Ready for Implementation

Return to Planning Agent for a plan-only revision. Next version: plan-v3.md

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-2__render-geometry

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v2.md
Write file: .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
