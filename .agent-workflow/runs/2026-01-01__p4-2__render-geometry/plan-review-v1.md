---
RUN_ID: 2026-01-01__p4-2__render-geometry
VERSION: v1
TARGET: Phase 4 → Item 4.2
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-review-v1.md
---

# Plan Review Report: Render Geometry Utilities

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-01
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v1.md

The plan is close but not implementation-ready because it invents behavioral requirements (“Behavior spec (from SSOT Section 5)”) that are not actually specified in SSOT. This violates the SSOT anchoring rule and leaves the Coding Agent implementing an algorithm chosen by the plan rather than by the spec. Additionally, verification scope and `render/__init__.py` export changes are underspecified.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (geometry utilities) with explicit out-of-scope list. |
| 2 | Dependencies | PASS | Depends on Phase 4.1 types; no new external deps. |
| 3 | File List | FAIL | Plan modifies `src/frame_compare/render/__init__.py` but does not specify the final `__all__` update (only an import snippet), leaving an integration decision. |
| 4 | Contract Impact | PASS | Canonical contracts untouched. |
| 5 | Types Complete | PASS | Function signatures are explicit and typed. |
| 6 | Tests Complete | PASS | Deterministic expected outputs listed, including negative case for invalid position. |
| 7 | Verification Complete | FAIL | Ruff scope omits `tests/render/` (`ruff check src/frame_compare/render/`), so test lint failures can slip through; also no explicit fallback commands for `.venv/bin/*` per workflow. |
| 8 | Decision-Minimizing | FAIL | Core behavior for `calculate_dimensions` / rounding / invalid inputs / overlay larger-than-image policy is not defined in SSOT and is currently being decided in the plan. |
| 9 | Determinism Defined | PASS | Outputs are deterministic; test vectors are concrete. |

## Additional Quality Checks

- Error Codes: OK — no new/changed `FC-xxxx` errors.
- Failure Modes: Issue — SSOT must define behavior for invalid/zero/negative dimensions and overlay sizing, not the plan.
- Derived Outputs: OK — no contract-view/traceability gates required.
- Rollback Guidance: OK — STOP not needed beyond SSOT update requirement.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Exact `calculate_dimensions` algorithm (scale selection, rounding, and what to do when constraints are larger than source).
2. Input validation and error behavior for non-positive inputs.
3. Policy for overlay larger than image / margin overflow (clamp vs raise).
4. Exact `render/__init__.py` export integration (import + `__all__` list update).
5. Verification scope for Ruff and fallback commands.

## Concrete Edits Required (SSOT update required)

1. **Update SSOT to define geometry behavior (algorithm + edge cases)**
   - Section: `## Spec Anchors (SSOT)` → `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
   - Problem: `## 5. Geometry Utilities` currently only provides function stubs/docstrings; the plan’s “Behavior spec” is not in SSOT.
   - Required Change: Edit SSOT first:
     - File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
     - Under heading: `## 5. Geometry Utilities` add bullet rules sufficient to make tests and implementation deterministic:
       - `calculate_dimensions`: how to choose scale when `max_width` and/or `max_height` are provided; rounding rule (must not exceed bounds); behavior when constraints are `None`; behavior when constraints are >= source.
       - `calculate_dimensions`: invalid inputs (`source_width/source_height <= 0`, `max_width/max_height <= 0`) → exact exception type (`ValueError`) and message requirement (if any).
       - `calculate_overlay_position`: validate `position` set; define behavior when `overlay_size` does not fit within `image_size` given `margin` (raise `ValueError` vs clamp—choose one).
       - `ensure_mod2`: define rounding-up-to-even for odd dimensions; invalid inputs (`<= 0`) behavior.

2. **Fix verification scope + workflow parity**
   - Section: `## Verification Commands`
   - Required Change: Add workflow-style fallbacks and ensure Ruff covers tests, e.g.:
     - `.venv/bin/ruff check src/frame_compare/render/ tests/render/`
     - Add uv-run fallbacks for pyright/ruff/pytest if `.venv/bin/*` is unavailable (per `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`).

3. **Make `render/__init__.py` change non-ambiguous**
   - Section: `src/frame_compare/render/__init__.py` [MODIFY]
   - Problem: Plan says “Add to `__all__`” but only shows an import snippet; it must also specify the exact `__all__` additions.
   - Required Change: Specify: add `calculate_dimensions`, `calculate_overlay_position`, `ensure_mod2` to the existing `__all__` list (either appended or inserted in a deterministic order—choose one).

## Ready for Implementation

Return to Planning Agent for revision. Next version: plan-v2.md (after SSOT update).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-2__render-geometry

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
- Under heading: "## 5. Geometry Utilities" add/change:
  - Define deterministic rules for `calculate_dimensions` (constraint selection + rounding + invalid inputs).
  - Define deterministic rules for `calculate_overlay_position` (invalid position + overlay-too-large policy + invalid inputs).
  - Define deterministic rules for `ensure_mod2` (round-up-to-even + invalid inputs).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v1.md
Write file: .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
