---
RUN_ID: 2025-12-30__p3-6__vs-integration
VERSION: v3
TARGET: Phase 3 → Item 3.6 Module Integration
INPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v3.md
---

# Plan Review Report: VapourSynth Module Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v3.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: exports + export tests + VS smoke test + lint-imports gate. |
| 2 | Dependencies | PASS | Depends on completed vs submodules; uses `vs_required` marker and safe optional import. |
| 3 | File List | PASS | Concrete file list; `src/frame_compare/vs/__init__.py` marked (MODIFY). |
| 4 | Contract Impact | PASS | Canonical contracts not touched. |
| 5 | Types Complete | FAIL | Plan adds `tonemap(...)` signature, but SSOT does not contain any `tonemap(` mention/definition, so `validate_spec_anchors.py` will fail coverage unless SSOT is updated. |
| 6 | Tests Complete | PASS | Export tests and integration smoke test are fully specified and deterministic. |
| 7 | Verification Complete | PASS | Includes run validators + pyright/ruff/pytest + lint-imports. |
| 8 | Decision-Minimizing | FAIL | Spec Anchors still include non-verbatim heading `Public Exports (vs/**init**.py)` which will fail `validate_spec_anchors.py` and forces the implementer to guess/fix anchors. |
| 9 | Determinism Defined | PASS | Export validation uses set membership + sorting; smoke test uses deterministic BlankClip. |

## Additional Quality Checks

- Error Codes: OK — no new error codes introduced.
- Failure Modes: OK — `pytest.importorskip("vapoursynth")` and runtime skip logic defined.
- Derived Outputs: OK — none.
- Rollback Guidance: OK — no new spec/contract outputs.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether to change the plan or change SSOT to satisfy signature coverage for `tonemap(...)`.
2. How to fix Spec Anchors to pass validators.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT: add mechanically-checkable `tonemap(...)` signature mention**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
   - Problem: SSOT includes `apply_tonemap` and `get_preset_settings` signatures but does not include `tonemap(` anywhere; plan signature coverage will fail.
   - Required Change (SSOT): edit `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
     - Under heading: `## Public Exports (vs/__init__.py)` add a bullet that includes the call-form signature, e.g.:
       - ``- `tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode` (alias of `apply_tonemap`)``

2. **Fix plan Spec Anchors to use verbatim headings**
   - Section: `## Spec Anchors (SSOT)` in `.agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v3.md`
   - Problem: Plan still uses `Section: "Public Exports (vs/**init**.py)"` (invalid).
   - Required Change (plan): replace with:
     - `Section: "Public Exports (vs/__init__.py)"`

3. **Update verification command references in revised plan**
   - Section: `## Verification Commands`
   - Required Change (plan-v4): update `validate_spec_anchors.py` command to reference `plan-v4.md`.

## Ready for Implementation

Return to Planning Agent for SSOT+plan revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-30__p3-6__vs-integration

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- Under heading: "Public Exports (vs/__init__.py)" add/change:
  - Add a bullet with the call-form signature for `tonemap(...)` (must include `tonemap(` so `validate_spec_anchors.py` can match it), and state it is an alias of `apply_tonemap`.

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v3.md
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v3.md
Write file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
