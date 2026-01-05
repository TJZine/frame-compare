---
RUN_ID: 2026-01-01__p4-integ__render-integration-tests
VERSION: v2
TARGET: Phase 4 → Integration Tests & Quality Gate
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v2.md
---

# Implementation Plan: Render Module Integration Tests & Phase 4 Quality Gate

## Changes Since plan-v1

1. **Scope aligned to Phase 4 Quality Gate:** Added VS integration test with `@pytest.mark.vs_required` marker.
2. **Orchestrator coverage:** Added `render_screenshots(...) -> dict[str, list[Path]]` to signatures under test with a dedicated integration test.
3. **Deterministic FFmpeg fixture:** Specified exact `ffmpeg` command for 3-frame CFR video.
4. **Explicit skip policies:** Defined `shutil.which` checks for `ffmpeg`/`ffprobe` and `pytest.importorskip("vapoursynth")` for VS.
5. **Strengthened assertions:** Added PNG validity via `PIL.Image.open`/`format`, naming convention regex, overlay color count, ordering contract.
6. **Removed `tests/conftest.py`:** Marker already in `pyproject.toml`; no modification needed.
7. **Verification gates:** Added `validate_run_id.py`, `validate_run_artifacts.py`, `validate_spec_anchors.py` commands.

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` (Section 7.2)
**Dependencies:** All Phase 4 items (4.1–4.6) are implemented and unit-tested

## Scope

This plan covers:

- [x] Create `tests/integration/` directory structure
- [x] Create `tests/integration/conftest.py` with deterministic integration fixtures
- [x] Create `tests/integration/test_render_pipeline.py` with FFmpeg and overlay tests
- [x] Create `tests/integration/test_render_vs.py` with VapourSynth renderer test (skipped if VS missing)
- [x] Create `tests/integration/test_render_orchestrator.py` with `render_screenshots` end-to-end test
- [x] Verify Phase 4 Quality Gate passes (both VS and FFmpeg renderers work)

This plan does NOT cover:

- E2E CLI tests (Phase 6 scope)
- Performance benchmarks (Phase 7 scope)
- HDR-specific tonemapping tests (Phase 3 unit tests cover this)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: "3.1 Frame Rendering"
  - Section: "3.2 Overlay"
  - Section: "7.2 Integration Tests"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "2.2 Integration Tests"
  - Section: "2.4 VapourSynth Tests"
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Public API (signatures under test)

Functions being integration-tested (signatures per render-module.md Section 3.1/3.2):

- `render_frame(request: RenderRequest, renderer: Renderer = "auto") -> Path` — Single frame render
- `render_batch(requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None) -> list[Path]` — Batch render (ordering contract)
- `apply_overlay(image: PIL.Image | np.ndarray, config: OverlayConfig) -> PIL.Image` — Overlay application
- `render_screenshots(clips: list[Path], frames: list[int], output_dir: Path, label_map: dict[Path, str] | None = None, renderer: Renderer = "auto", overlay_mode: OverlayMode = OverlayMode.STANDARD, reporter: ProgressReporter | None = None) -> dict[str, list[Path]]` — Orchestrator

## Files to Create/Modify

### 1. `tests/integration/__init__.py` [NEW]

**Purpose:** Package marker for integration tests.

**Content:** Empty file.

### 2. `tests/integration/conftest.py` [NEW]

**Purpose:** Shared fixtures for integration tests with deterministic behavior.

**Skip policy constants:**

- `FFMPEG_AVAILABLE`: `shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None`

**Fixtures (test infrastructure):**

- Fixture: `require_ffmpeg` — Autouse fixture that calls `pytest.skip("ffmpeg/ffprobe not available")` if `FFMPEG_AVAILABLE` is `False`.
- Fixture: `integration_output_dir(tmp_path)` — Returns `tmp_path / "output"`, creates the directory.
- Fixture: `sample_image_path(tmp_path)` — Creates a 100×100 solid red PNG via `PIL.Image.new("RGB", (100, 100), (255, 0, 0))`, saves to `tmp_path / "red.png"`, returns path.
- Fixture: `mock_video_path(tmp_path, require_ffmpeg)` — Creates a deterministic 3-frame CFR video using exact command:

  ```bash
  ffmpeg -y -f lavfi -i color=c=red:s=100x100:r=10:d=0.3 -c:v libx264 -pix_fmt yuv420p tmp_path/test.mp4
  ```

  Returns `tmp_path / "test.mp4"`. Video has 3 frames at 10 fps, duration 0.3s.

### 3. `tests/integration/test_render_pipeline.py` [NEW]

**Purpose:** Integration tests for render module with FFmpeg and overlays.

**Tests (all marked `@pytest.mark.integration`):**

- **test_ffmpeg_render_creates_valid_png:**
  - GIVEN: `mock_video_path` (3-frame video), `frame_number=0`, `output_path=integration_output_dir / "frame_00000.png"`
  - WHEN: `render_frame(RenderRequest(...), renderer="ffmpeg")`
  - THEN:
    - Returned path equals `output_path`
    - File exists
    - PNG validity: open with PIL and verify format == "PNG"

- **test_overlay_application_adds_visible_content:**
  - GIVEN: Solid red 100×100 image, `OverlayConfig(mode=OverlayMode.STANDARD, label="Test", frame_number=1, resolution=(100, 100), hdr_info=None, font_path=None)`
  - WHEN: `apply_overlay(Image.open(sample_image_path), config)`
  - THEN: Output image has more than 1 unique color (use `len(set(img.getdata())) > 1`)

- **test_render_batch_ordering_contract:**
  - GIVEN: 3 `RenderRequest`s for frames 0, 1, 2 with distinct output paths
  - WHEN: `render_batch(requests, parallelism=1)`
  - THEN:
    - Returned list length == 3
    - Returned paths match input request order (`results[i] == requests[i].output_path`)
    - All files exist
    - All are valid PNGs

### 4. `tests/integration/test_render_vs.py` [NEW]

**Purpose:** VapourSynth renderer integration test.

**Skip policy:** `vs = pytest.importorskip("vapoursynth")` at module level + skip if mocked.

**Tests (marked `@pytest.mark.integration` and `@pytest.mark.vs_required`):**

- **test_vs_render_creates_valid_png:**
  - GIVEN: Create a synthetic `vs.VideoNode` using `core.std.BlankClip(width=100, height=100, length=3)`, frame 0
  - WHEN: `render_frame(RenderRequest(clip=clip, frame_number=0, ...), renderer="vapoursynth")`
  - THEN:
    - File exists
    - PNG validity: open with PIL and verify format == "PNG"

### 5. `tests/integration/test_render_orchestrator.py` [NEW]

**Purpose:** End-to-end orchestrator integration test covering naming, overlay, and output mapping.

**Tests (marked `@pytest.mark.integration`):**

- **test_render_screenshots_naming_and_output:**
  - GIVEN: `clips=[mock_video_path]`, `frames=[0, 1]`, `label_map={mock_video_path: "TestLabel"}`
  - WHEN: `render_screenshots(clips, frames, integration_output_dir, label_map=label_map, renderer="ffmpeg", overlay_mode=OverlayMode.MINIMAL)`
  - THEN:
    - Returned dict has key `"TestLabel"`
    - `len(results["TestLabel"]) == 2`
    - Paths match pattern `TestLabel_00000.png`, `TestLabel_00001.png`
    - All files exist
    - All files are valid PNGs (open with PIL, verify format == "PNG")

### 6. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2026-01-01__p4-integ__render-integration-tests`
- Artifact versions: plan-v2, plan-review-v1, impl-v1, verify-v1, review-v1 (or as written)
- Scope: Phase 4 integration tests for full render module (VS + FFmpeg + orchestrator)
- Explicit out-of-scope: E2E CLI (Phase 6), Performance benchmarks (Phase 7)
- SSOT edits: None
- Verification gates: All passed

### 7. `CHANGELOG.md` [MODIFY]

**Purpose:** Add entry for Phase 4 completion.

**Entry (Unreleased section):**

```
- Phase 4 (Render Module) complete: types, geometry, naming, overlay, encoders, orchestrator with integration tests
```

## Acceptance Criteria

- [ ] GIVEN `tests/integration/test_render_pipeline.py` WHEN `pytest -v -m integration tests/integration/` THEN all tests pass (or skip cleanly if ffmpeg/VS unavailable)
- [ ] GIVEN Phase 4 implementation WHEN Pyright runs on `src/frame_compare/render/` THEN 0 errors
- [ ] GIVEN Phase 4 implementation WHEN Ruff runs on `src/frame_compare/render/` THEN 0 errors
- [ ] GIVEN Phase 4 implementation WHEN `pytest tests/render/` runs THEN all unit tests pass
- [ ] GIVEN full project WHEN coverage checked THEN render module coverage > 80%
- [ ] GIVEN VS is available WHEN `pytest -m vs_required tests/integration/` THEN VS integration test passes
- [ ] GIVEN FFmpeg is available WHEN `pytest -m integration tests/integration/` THEN FFmpeg-based tests pass

## Verification Commands

```bash
# 0. Run-artifact validators (must pass before handoff)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2026-01-01__p4-integ__render-integration-tests
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v2.md

# 1. Run integration tests
.venv/bin/pytest -v -m integration tests/integration/

# 2. Phase 4 Quality Gate checks
.venv/bin/pyright --warnings src/frame_compare/render/
.venv/bin/ruff check src/frame_compare/render/
.venv/bin/pytest -v tests/render/

# 3. Coverage check
.venv/bin/pytest --cov=src/frame_compare/render --cov-report=term-missing tests/render/ tests/integration/

# 4. Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# 5. Contract gates
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** All commands exit 0 with no errors. Integration tests may skip if FFmpeg/VS unavailable; this is acceptable.

**If validation fails:** STOP and return to Planning. Do not improvise.

## Notes for Coding Agent

1. **FFmpeg skip policy:** Use `shutil.which("ffmpeg")` and `shutil.which("ffprobe")` at fixture level. If either is `None`, `pytest.skip()`.

2. **VS skip policy:** Use `pytest.importorskip("vapoursynth")` at module level. Additionally, skip if the module is a mock: `if isinstance(vapoursynth, MagicMock): pytest.skip("VS is mocked")`.

3. **Deterministic video fixture:** Exact command for 3-frame 10fps video:

   ```bash
   ffmpeg -y -f lavfi -i "color=c=red:s=100x100:r=10:d=0.3" -c:v libx264 -pix_fmt yuv420p <output.mp4>
   ```

   Run via `subprocess.run([...], check=True)`.

4. **PNG validity assertion:** Use `PIL.Image.open(path)` in a with-block, assert `img.format == "PNG"`.

5. **Overlay visibility assertion:** For solid-color input, check `len(set(img.getdata())) > 1` to confirm text/background was added.

6. **Naming assertion:** Use regex `r"^TestLabel_\d{5}\.png$"` or direct equality `path.name == f"{label}_{frame:05d}.png"`.

7. **Ordering assertion:** `for i, req in enumerate(requests): assert results[i] == req.output_path`.

8. **No network:** Integration tests must NOT make network calls.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-integ__render-integration-tests

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-review-v2.md
