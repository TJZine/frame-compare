---
RUN_ID: 2025-12-30__p3-6__vs-integration
VERSION: v1
TARGET: Phase 3 → Item 3.6 Module Integration
INPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v1.md
---

# Plan Review Report: VapourSynth Module Integration

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2025-12-30
**Plan Reference:** .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: exports + import contracts + export tests + VS smoke test. |
| 2 | Dependencies | PASS | Depends on completed Phase 3.1–3.5; uses existing `frame_compare.vs.*` modules. |
| 3 | File List | FAIL | Plan marks `src/frame_compare/vs/__init__.py` as (NEW) but it already exists; also plan header `OUTPUTS` points to `plan-v1.md` instead of the review artifact path (breaks run artifact validation). |
| 4 | Contract Impact | PASS | Canonical contracts not touched. |
| 5 | Types Complete | FAIL | Missing `## Public API Signatures` section; introduces exported alias `tonemap` without a one-line signature. |
| 6 | Tests Complete | FAIL | `tests/vs/test_exports.py` and `tests/vs/test_integration.py` are under-specified (exact expected export set, `__all__` contract, skip semantics, `BlankClip` creation call, and `TonemapSettings`/args are not pinned). |
| 7 | Verification Complete | FAIL | Does not follow command canon: missing `validate_run_id.py`, `validate_run_artifacts.py`, and `validate_spec_anchors.py` for this plan. |
| 8 | Decision-Minimizing | FAIL | Plan forces design decisions about whether to keep exporting `apply_tonemap`/`get_preset_settings` vs only `tonemap`; also integration test currently requires inventing `SourceInfo(...)` field values and tonemap call arguments. |
| 9 | Determinism Defined | PASS | No RNG or unstable ordering introduced by this slice. |

## Additional Quality Checks

- Error Codes: OK — no new error codes proposed.
- Failure Modes: Issue — integration test does not specify what happens when `is_vapoursynth_available()` is false (must `pytest.skip`), and does not pin behavior when `vapoursynth` import succeeds but core init fails.
- Derived Outputs: OK — no generated outputs.
- Rollback Guidance: Issue — add “STOP and return to Planning if SSOT export list is inconsistent” guidance.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Export surface: whether `frame_compare.vs` exports `apply_tonemap` / `get_preset_settings` in addition to the required `tonemap` alias.
2. Integration smoke test: exact blank clip creation call, `TonemapSettings` values, and skip/collection behavior without VapourSynth.
3. Export tests: exact expected set and strictness rules for `__all__`.

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT: reconcile `tonemap` vs `apply_tonemap` exports**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` → `## Public Exports (vs/__init__.py)`
   - Problem: SSOT requires `tonemap` export but does not specify whether `apply_tonemap` and `get_preset_settings` are also exported; current repo state exports `apply_tonemap` and `get_preset_settings` from `frame_compare.vs`.
   - Required Change (SSOT): under `## Public Exports (vs/__init__.py)` add bullets that explicitly define:
     - `tonemap` is an alias of `apply_tonemap`.
     - Whether `apply_tonemap` is also exported from `frame_compare.vs` (YES/NO; choose one).
     - Whether `get_preset_settings` is exported from `frame_compare.vs` (YES/NO; choose one).

2. **Fix Spec Anchors to match exact headings (must pass `validate_spec_anchors.py`)**
   - Section: `## Spec Anchors (SSOT)` in `.agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v1.md`
   - Problem: Anchor uses `"8. AI Agent Implementation Prompt" -> "Public Exports (vs/**init**.py)"`, which is not a verbatim heading string.
   - Required Change (plan): replace with exact headings present in SSOT:
     - `Section: "8. AI Agent Implementation Prompt"`
     - `Section: "Public Exports (vs/__init__.py)"`

3. **Correct plan artifact header + file classifications**
   - Section: YAML frontmatter + `## Files to Create/Modify`
   - Problem: `OUTPUTS` points to `plan-v1.md` (wrong), and `src/frame_compare/vs/__init__.py` is marked (NEW) though it exists.
   - Required Change (plan): set `OUTPUTS` to `.agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v1.md` and mark `src/frame_compare/vs/__init__.py` as (MODIFY).

4. **Add `## Public API Signatures (mechanically checkable)`**
   - Section: plan body
   - Problem: missing signature list; alias export `tonemap` needs a signature.
   - Required Change (plan): add at minimum:
     - `tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
   - If plan changes any other public symbols, list their signatures too; otherwise state “no new public functions; exports only”.

5. **Make tests fully specified**
   - Section: `tests/vs/test_exports.py` and `tests/vs/test_integration.py`
   - Problem: currently leaves the Coding Agent to choose assertion strictness and how to construct required objects.
   - Required Change (plan-only):
     - For `tests/vs/test_exports.py`, include an explicit ordered list of expected export names (strings) and define the rule:
       - Either `set(__all__) == expected_set` AND `sorted(__all__) == __all__` (or other deterministic ordering rule), plus `hasattr(frame_compare.vs, name)` for each.
     - For `tests/vs/test_integration.py`, replace the `SourceInfo(...)` construction with a deterministic smoke call that does not require inventing dataclass fields:
       - `vs = pytest.importorskip("vapoursynth")`
       - `if not is_vapoursynth_available(): pytest.skip("VapourSynth not available")`
       - `core = ensure_vs_environment()`
       - `clip = core.std.BlankClip(length=1, format=vs.RGBS)`
       - `out = tonemap(clip, TonemapSettings(enabled=True), hdr_metadata=None)`
       - `assert isinstance(out, vs.VideoNode)`

6. **Update verification commands to follow command canon**
   - Section: `## Verification Commands`
   - Required Change (plan): prepend:
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-30__p3-6__vs-integration`
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-30__p3-6__vs-integration`
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v2.md`
   - Keep `.venv/bin/*` for pyright/ruff/pytest, and `lint-imports` via `uv run --no-sync`.

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2025-12-30__p3-6__vs-integration

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- Under heading: "Public Exports (vs/__init__.py)" add/change:
  - Specify that `tonemap` is an alias of `apply_tonemap`.
  - Specify whether `apply_tonemap` is exported from `frame_compare.vs` (YES/NO).
  - Specify whether `get_preset_settings` is exported from `frame_compare.vs` (YES/NO).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v1.md
Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v1.md
Write file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
