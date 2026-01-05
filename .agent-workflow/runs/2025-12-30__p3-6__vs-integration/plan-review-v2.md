---
RUN_ID: 2025-12-30__p3-6__vs-integration
VERSION: v2
TARGET: Phase 3 → Item 3.6 Module Integration
INPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v2.md
---

# Plan Review Report: VapourSynth Module Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v2.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: exports + export tests + VS smoke test + import contracts gate. |
| 2 | Dependencies | PASS | Depends on completed vs submodules; uses `vs_required` marker and optional dependency handling. |
| 3 | File List | PASS | Concrete files listed; `src/frame_compare/vs/__init__.py` correctly marked (MODIFY). |
| 4 | Contract Impact | PASS | Canonical contracts not touched. |
| 5 | Types Complete | FAIL | Plan exports `apply_tonemap` and `get_preset_settings` but does not list their one-line public signatures; also Spec Anchors must cover all listed signatures. |
| 6 | Tests Complete | FAIL | `tests/vs/test_exports.py` pseudo-code has `expected` undefined in the second test; export-set/`__all__` rules need to be mechanically actionable without decisions. |
| 7 | Verification Complete | PASS | Includes run validators + lint-imports + pyright/ruff/pytest. |
| 8 | Decision-Minimizing | FAIL | Spec Anchors include a non-verbatim heading (`Public Exports (vs/**init**.py)`) that will fail `validate_spec_anchors.py`, forcing the implementer to guess/fix anchors. |
| 9 | Determinism Defined | PASS | No nondeterminism introduced; export assertions use sets/sorting. |

## Additional Quality Checks

- Error Codes: OK — no new errors introduced.
- Failure Modes: OK — integration test includes `pytest.importorskip` + `pytest.skip` when VS not available.
- Derived Outputs: OK — none.
- Rollback Guidance: OK — no new spec or contract surfaces introduced.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether to add missing signatures for exported functions (currently omitted).
2. How to structure/export the shared `expected` export-set for tests (currently ambiguous).
3. How to fix Spec Anchors so validators pass (currently invalid).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Fix Spec Anchors to use exact SSOT headings**
   - Section: `## Spec Anchors (SSOT)` in `.agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v2.md`
   - Problem: `Section: "Public Exports (vs/**init**.py)"` is not a verbatim heading and will fail `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py ...`.
   - Required Change (plan): replace with the exact heading text from SSOT:
     - `Section: "Public Exports (vs/__init__.py)"`

2. **Add missing public signatures for exported tonemap functions**
   - Section: `## Public API Signatures (mechanically checkable)` in `.agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v2.md`
   - Problem: Plan requires exporting `apply_tonemap` and `get_preset_settings`, but only provides the `tonemap(...)` alias signature.
   - Required Change (plan): add:
     - `apply_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
     - `get_preset_settings(preset: str) -> TonemapSettings`

3. **Make export tests mechanically actionable (no undefined variables)**
   - Section: `tests/vs/test_exports.py` in `.agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v2.md`
   - Problem: `test_all_property_is_complete` references `expected` but doesn’t define it; implementation must choose how to share expected exports.
   - Required Change (plan): specify one deterministic structure, e.g.:
     - Define `EXPECTED_EXPORTS: set[str] = {...}` at module scope and reuse it in both tests.
     - In `test_all_property_is_complete`, assert `set(frame_compare.vs.__all__) == EXPECTED_EXPORTS` (and optionally require `__all__` is sorted: `frame_compare.vs.__all__ == sorted(frame_compare.vs.__all__)`).

4. **Update verification command to reference the revised plan filename**
   - Section: `## Verification Commands`
   - Problem: Validator line pins `plan-v2.md`; next plan version must update this.
   - Required Change (plan): in `plan-v3.md`, change the `validate_spec_anchors.py` invocation to target `plan-v3.md`.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-30__p3-6__vs-integration

## Revision Required
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v2.md
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v2.md
Write file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Keep changes minimal; do not change SSOT unless required by this report.
