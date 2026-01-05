---
RUN_ID: 2026-01-01__p4-integ__render-integration-tests
VERSION: v1
TARGET: Phase 4 → Integration Tests & Quality Gate
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v1.md
---

# Implementation Plan: Render Module Integration Tests & Phase 4 Quality Gate

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` (Section 7.2)
**Dependencies:** All Phase 4 items (4.1–4.6) are implemented and unit-tested

## Scope

This plan covers:

- [x] Create `tests/integration/` directory structure
- [x] Create `tests/integration/conftest.py` with integration fixtures
- [x] Create `tests/integration/test_render_pipeline.py` with real file I/O tests
- [x] Verify Phase 4 Quality Gate passes

This plan does NOT cover:

- VapourSynth integration tests (require VS runtime; covered by `@pytest.mark.vs_required` tests)
- E2E CLI tests (Phase 6 scope)
- Performance benchmarks (Phase 7 scope)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: "3.1 Frame Rendering"
  - Section: "3.2 Overlay"
  - Section: "7.2 Integration Tests"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "2.2 Integration Tests"
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Public API (signatures under test)

Functions being integration-tested (signatures per render-module.md Section 3.1/3.2):

- `render_frame(request: RenderRequest, renderer: Renderer = "auto") -> Path` — Single frame render
- `render_batch(requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None) -> list[Path]` — Batch render
- `apply_overlay(image: PIL.Image | np.ndarray, config: OverlayConfig) -> PIL.Image` — Overlay application

## Files to Create/Modify

### 1. `tests/integration/__init__.py` [NEW]

**Purpose:** Package marker for integration tests.

**Content:** Empty file.

### 2. `tests/integration/conftest.py` [NEW]

**Purpose:** Shared fixtures for integration tests.

**Fixtures to define (test infrastructure, not public API):**

- Fixture: `integration_output_dir` — Returns `tmp_path / "output"`, creates the directory
- Fixture: `sample_image_path` — Creates a 100x100 test PNG, returns the path
- Fixture: `mock_video_path` — Creates a minimal video file using FFmpeg, returns the path

### 3. `tests/integration/test_render_pipeline.py` [NEW]

**Purpose:** Integration tests for render module with real file I/O.

**Tests required (per `render-module.md` Section 7.2):**

- `test_ffmpeg_render_creates_png_file` — GIVEN valid video path and frame WHEN `render_frame` called with `renderer="ffmpeg"` THEN PNG file is created at output path
- `test_overlay_application_produces_visible_overlay` — GIVEN image and `OverlayConfig` WHEN `apply_overlay` called THEN returned image differs from input
- `test_render_batch_creates_multiple_files` — GIVEN list of `RenderRequest`s WHEN `render_batch` called THEN all output paths exist as files

**Test markers:** `@pytest.mark.integration`

### 4. `tests/conftest.py` [MODIFY]

**Purpose:** Ensure integration marker is registered.

**Change:** Verify `integration` marker is registered in pytest config (already in `pyproject.toml` per testing-strategy.md Section 3.1).

### 5. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2026-01-01__p4-integ__render-integration-tests`
- Scope: Phase 4 integration tests for render module + quality gate completion
- Out-of-scope: VapourSynth integration (requires runtime), E2E (Phase 6)
- SSOT edits: None
- Verification: All Phase 4 Quality Gate items must pass

### 6. `CHANGELOG.md` [MODIFY]

**Purpose:** Add entry for Phase 4 completion.

**Entry:** "Phase 4 (Render Module) complete with integration tests"

## Acceptance Criteria

- [ ] GIVEN `tests/integration/test_render_pipeline.py` WHEN `pytest tests/integration/ -m integration` THEN all tests pass
- [ ] GIVEN Phase 4 implementation WHEN Pyright runs on `src/frame_compare/render/` THEN 0 errors
- [ ] GIVEN Phase 4 implementation WHEN Ruff runs on `src/frame_compare/render/` THEN 0 errors
- [ ] GIVEN Phase 4 implementation WHEN `pytest tests/render/` runs THEN all tests pass
- [ ] GIVEN full project WHEN coverage checked THEN render module coverage > 80%

## Verification Commands

```bash
# 1. Run integration tests
.venv/bin/pytest -v -m integration tests/integration/

# 2. Phase 4 Quality Gate checks
.venv/bin/pyright --warnings src/frame_compare/render/
.venv/bin/ruff check src/frame_compare/render/
.venv/bin/pytest -v tests/render/

# 3. Coverage check
.venv/bin/pytest --cov=src/frame_compare/render --cov-report=term-missing tests/render/

# 4. Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# 5. Contract gates
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** All commands exit 0 with no errors.

## Notes for Coding Agent

1. **FFmpeg integration test caveat:** FFmpeg must be available in the test environment. The test should be skipped if FFmpeg is not installed (use `pytest.importorskip` pattern or check subprocess).

2. **Mock video for FFmpeg:** Create the simplest possible test: use FFmpeg itself to generate a 1-frame test video in the fixture:

   ```bash
   ffmpeg -f lavfi -i color=c=red:s=100x100:d=0.1 -frames:v 1 test.mp4
   ```

   Or skip if FFmpeg unavailable.

3. **Overlay visibility test:** Compare pixel values between original and overlaid images. The overlay adds text/background, so at least some pixels must differ.

4. **Integration marker:** Tests must be marked with `@pytest.mark.integration` per testing-strategy.md.

5. **No network:** Integration tests must NOT make network calls (per testing-strategy.md Section 2.2).

---

> **Proposed RUN_ID:** 2026-01-01__p4-integ__render-integration-tests
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2026-01-01__p4-integ__render-integration-tests` before running Plan Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-integ__render-integration-tests

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-review-v1.md
