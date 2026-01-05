---
RUN_ID: 2026-01-01__p4-integ__render-integration-tests
VERSION: v1
TARGET: Phase 4 → Integration Tests & Quality Gate
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/integration-tests.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-review-v1.md
---

# Plan Review Report: Render Module Integration Tests & Phase 4 Quality Gate

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v1.md

The plan is close, but it leaves key Phase 4 quality-gate requirements untested (VS renderer + orchestrator `render_screenshots`) and leaves several test/fixture decisions unspecified (FFmpeg/ffprobe presence checks, deterministic video generation, PNG validity assertions, ordering contract assertions). These gaps would force the Coding Agent to make design decisions.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | FAIL | Scope explicitly excludes VapourSynth integration, but Phase 4 quality gate requires “VS and FFmpeg renderers work”. |
| 2 | Dependencies | FAIL | FFmpeg tests implicitly require both `ffmpeg` and `ffprobe`; plan only mentions FFmpeg. VS availability/mocking behavior is not specified for skips. |
| 3 | File List | FAIL | Includes `tests/conftest.py` as “[MODIFY]” with an “already in pyproject.toml” note, creating a conditional decision point; does not list any integration-test helper module if needed for shared skip logic. |
| 4 | Contract Impact | PASS | Explicit “Contracts touched: NO” and no canonical contract edits implied. |
| 5 | Types Complete | FAIL | Plan targets Phase 4 quality gate but omits `render_screenshots(...) -> dict[str, list[Path]]` from signatures under test; integration coverage needs orchestrator API. |
| 6 | Tests Complete | FAIL | Missing VS renderer integration test(s); missing orchestrator integration test(s) covering naming/overlay/PNG validity; assertions are underspecified (valid PNG, ordering contract, skip conditions). |
| 7 | Verification Complete | FAIL | Missing required workflow validations (`validate_run_id.py`, `validate_run_artifacts.py`, `validate_spec_anchors.py`) and explicit “allowed skips” criteria for `vs_required` / missing FFmpeg. |
| 8 | Decision-Minimizing | FAIL | Leaves implementation choices to Coding Agent (exact FFmpeg lavfi command, which frames to render, how to assert overlay visibility, how to detect FFmpeg/ffprobe and VS mocking). |
| 9 | Determinism Defined | FAIL | Mentions deterministic policy, but does not specify deterministic fixture generation (video FPS/length/frames) or required ordering assertions (e.g., `render_batch` ordering contract). |

## Additional Quality Checks

- Error Codes: OK (no new/changed errors proposed)
- Failure Modes: Issue — skip policy for missing `ffmpeg`/`ffprobe` and mocked VS needs to be explicit and testable
- Derived Outputs: OK (contracts not touched; derived outputs unchanged)
- Rollback Guidance: Issue — plan should state “if validation fails, STOP and return to Planning”, not improvise
- SSOT Update Audit (if SSOT changed this loop): N/A (no SSOT changes indicated)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining:

1. Whether to add VS renderer integration tests (required by Phase 4 quality gate).
2. Whether to add orchestrator `render_screenshots` integration coverage (required by Phase 4 quality gate + checklist 4.6).
3. Exact deterministic video fixture (FPS/length/frames) needed to support `render_batch` / multi-frame cases.
4. Exact skip behavior for missing `ffmpeg` vs missing `ffprobe`, and for mocked VS.
5. Exact assertions to prove “PNG output valid”, “naming convention followed”, and “overlay visible” without pixel-perfect brittleness.

## Concrete Edits Required (plan-v2.md)

1. **Scope aligned to Phase 4 Quality Gate**
   - Section: `## Scope`
   - Problem: Excludes VS integration despite Phase 4 gate requiring VS+FFmpeg renderers work.
   - Required Change: Include a `@pytest.mark.vs_required` integration test that exercises `render_frame(..., renderer="vapoursynth")` (or `render_screenshots(..., renderer="vapoursynth")`) and define its skip logic when VS is missing/mocked.

2. **Add orchestrator integration coverage (required)**
   - Section: `## Public API (signatures under test)` and `tests/integration/test_*.py` test list
   - Problem: No integration test hits `render_screenshots`, so naming + overlay policy + output mapping are not exercised end-to-end.
   - Required Change: Add `render_screenshots(...) -> dict[str, list[Path]]` to the signatures list and add at least one integration test that asserts:
     - returned mapping keys match expected label(s)
     - output path names follow `{label}_{frame:05d}.png`
     - output files exist and are valid PNGs (openable via PIL with `img.format == "PNG"`)

3. **Deterministic FFmpeg fixture definition (no ad-hoc choices)**
   - Section: `tests/integration/conftest.py`
   - Problem: `mock_video_path` is underspecified and can’t reliably support multi-frame tests.
   - Required Change: Specify the exact FFmpeg command to generate a deterministic CFR test video with at least 3 frames (fixed `s=100x100`, fixed `r=<int>`, fixed duration or `-frames:v <n>`). Also specify that both `ffmpeg` and `ffprobe` must be present, otherwise the fixture skips.

4. **Explicit skip policies for FFmpeg/ffprobe and VS mocking**
   - Section: `## Notes for Coding Agent` (or in test plan details)
   - Problem: “skip if FFmpeg not installed” is not precise and doesn’t cover `ffprobe` or mocked VS.
   - Required Change: Define exact checks:
     - FFmpeg path tests: `shutil.which("ffmpeg")` and `shutil.which("ffprobe")` must both be non-None, else `pytest.skip(...)`.
     - VS tests: use `vs = pytest.importorskip("vapoursynth")` and skip if `isinstance(vs, MagicMock)` (match existing `tests/vs/test_integration.py` pattern).

5. **Strengthen test assertions to cover SSOT requirements without brittleness**
   - Section: `tests/integration/test_*.py` test list
   - Problem: Current assertions only check file existence and “image differs”, which does not prove “valid PNG” or “naming convention followed”; `render_batch` ordering contract is untested.
   - Required Change: For each planned test, specify the minimal assertions:
     - PNG validity (PIL open + `format == "PNG"`)
     - naming (`path.name == f\"{label}_{frame:05d}.png\"` or `path.name` matches regex)
     - overlay visibility: for deterministic solid-color inputs, assert output has >1 unique color (not pixel-perfect)
     - `render_batch` ordering: assert returned paths list order matches input request order (SSOT ordering contract in render-module.md).

6. **Remove conditional/unclear file modifications**
   - Section: `## Files to Create/Modify`
   - Problem: `tests/conftest.py` listed as “[MODIFY]” but the change is conditional (“already in pyproject.toml”), creating churn/ambiguity.
   - Required Change: Either remove this item (preferred; marker is already in `pyproject.toml`) or specify an unconditional, concrete change that must be made.

7. **Verification gates per workflow (must-pass)**
   - Section: `## Verification Commands`
   - Problem: Missing required run-artifact validators from `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`.
   - Required Change: Add the exact commands (with this RUN_ID and the plan version you are writing) and define pass criteria:
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2026-01-01__p4-integ__render-integration-tests`
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests`
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v2.md`

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-01__p4-integ__render-integration-tests

## Revision Required
Read file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v1.md
Write file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
