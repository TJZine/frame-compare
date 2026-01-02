---
RUN_ID: 2026-01-01__p4-integ__render-integration-tests
VERSION: v3
TARGET: Phase 4 → Integration Tests & Quality Gate
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-review-v2.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v3.md
---

# Implementation Plan: Render Module Integration Tests & Phase 4 Quality Gate

## Changes Since plan-v2

1. **FFmpeg skip scoped to FFmpeg-dependent tests only:** Changed `require_ffmpeg` from autouse to normal fixture; only tests using `mock_video_path` will skip when FFmpeg is unavailable. Overlay-only and VS tests are not affected.
2. **FFmpeg frame count hard-deterministic:** Added `-frames:v 3` to the FFmpeg command to guarantee exactly 3 frames regardless of encoder/duration math.
3. **VS clip format pinned:** Specified `BlankClip(..., format=vs.RGB24)` for 8-bit same-plane-shape compatibility with current encoder.
4. **RenderRequest fields fully specified:** Removed all ellipses; each test specifies exact `clip`, `frame_number`, `output_path`, `overlay`, and `encoder_settings`.
5. **DECISIONS artifact-version corrected:** Changed to "plan-v3 + plan-review-v3 + impl-vN + verify-vN + review-vN (as written)".

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

**Skip policy constant:**

- FFMPEG_AVAILABLE: True if both shutil.which("ffmpeg") and shutil.which("ffprobe") return non-None values

**Fixtures (test infrastructure):**

- **Fixture: `require_ffmpeg`** — NOT autouse. Calls `pytest.skip("ffmpeg/ffprobe not available")` if `FFMPEG_AVAILABLE` is `False`. Only tests that depend on `mock_video_path` (which depends on this fixture) will skip.

- **Fixture: `integration_output_dir`** — Takes `tmp_path`, returns `tmp_path / "output"`, creates the directory.

- **Fixture: `sample_image_path`** — Takes `tmp_path`. Creates a 100×100 solid red PNG via:

  ```python
  img = PIL.Image.new("RGB", (100, 100), (255, 0, 0))
  path = tmp_path / "red.png"
  img.save(path)
  return path
  ```

- **Fixture: `mock_video_path`** — Takes `tmp_path` and `require_ffmpeg`. Creates a deterministic 3-frame CFR video using exact command:

  ```bash
  ffmpeg -y -f lavfi -i "color=c=red:s=100x100:r=10" -frames:v 3 -c:v libx264 -pix_fmt yuv420p <tmp_path>/test.mp4
  ```

  Returns `tmp_path / "test.mp4"`. Guarantees exactly 3 frames at 10 fps.

### 3. `tests/integration/test_render_pipeline.py` [NEW]

**Purpose:** Integration tests for render module with FFmpeg and overlays.

**Tests (all marked `@pytest.mark.integration`):**

- **test_ffmpeg_render_creates_valid_png:**
  - Uses fixtures: `mock_video_path`, `integration_output_dir`
  - GIVEN:
    - `clip = mock_video_path` (3-frame video)
    - `frame_number = 0`
    - `output_path = integration_output_dir / "frame_00000.png"`
    - `overlay = None`
    - encoder_settings: default EncoderSettings
  - WHEN: Call render_frame with RenderRequest containing above fields and renderer="ffmpeg"
  - THEN:
    - `result == output_path`
    - `output_path.exists()` is True
    - PNG validity: open with PIL and verify format == "PNG"

- **test_overlay_application_adds_visible_content:**
  - Uses fixtures: `sample_image_path`
  - Does NOT use `mock_video_path`, so runs even if FFmpeg is unavailable
  - GIVEN:
    - `img = PIL.Image.open(sample_image_path)` (solid red 100×100)
    - config: OverlayConfig with mode=STANDARD, label="Test", frame_number=1, resolution=(100, 100), hdr_info=None, font_path=None, font_size=24, position="top-left"
  - WHEN: Call apply_overlay with the image and config
  - THEN: `len(set(result.getdata())) > 1` (more than one unique color)

- **test_render_batch_ordering_contract:**
  - Uses fixtures: `mock_video_path`, `integration_output_dir`
  - GIVEN:
    - requests: list of 3 RenderRequest objects for frames 0, 1, 2 with distinct output paths (frame_00000.png, frame_00001.png, frame_00002.png), overlay=None, encoder_settings=default EncoderSettings
  - WHEN: Call render_batch with requests and parallelism=1
  - THEN:
    - Returned list length == 3
    - Returned paths match input request order (results[i] == requests[i].output_path for all i)
    - All files exist
    - All are valid PNGs (open with PIL, verify format == "PNG")

### 4. `tests/integration/test_render_vs.py` [NEW]

**Purpose:** VapourSynth renderer integration test.

**Skip policy at module level:**

```python
vs = pytest.importorskip("vapoursynth")
from unittest.mock import MagicMock
if isinstance(vs, MagicMock):
    pytest.skip("vapoursynth is mocked", allow_module_level=True)
```

**Tests (marked `@pytest.mark.integration` and `@pytest.mark.vs_required`):**

- **test_vs_render_creates_valid_png:**
  - Uses fixtures: `tmp_path`
  - Does NOT depend on FFmpeg; skips only if VS is unavailable
  - GIVEN:
    - `core = vs.core`
    - clip: BlankClip from core.std with width=100, height=100, length=3, format=vs.RGB24
    - frame_number: 0
    - output_path: tmp_path / "vs_frame_00000.png"
    - overlay: None
    - encoder_settings: default EncoderSettings
  - WHEN: Call render_frame with RenderRequest containing above fields and renderer="vapoursynth"
  - THEN:
    - `output_path.exists()` is True
    - PNG validity: open with PIL and verify format == "PNG"

### 5. `tests/integration/test_render_orchestrator.py` [NEW]

**Purpose:** End-to-end orchestrator integration test covering naming, overlay, and output mapping.

**Tests (marked `@pytest.mark.integration`):**

- **test_render_screenshots_naming_and_output:**
  - Uses fixtures: `mock_video_path`, `integration_output_dir`
  - GIVEN:
    - `clips = [mock_video_path]`
    - `frames = [0, 1]`
    - `output_dir = integration_output_dir`
    - `label_map = {mock_video_path: "TestLabel"}`
    - `renderer = "ffmpeg"`
    - `overlay_mode = OverlayMode.MINIMAL`
  - WHEN: `results = render_screenshots(clips, frames, output_dir, label_map=label_map, renderer=renderer, overlay_mode=overlay_mode)`
  - THEN:
    - `"TestLabel" in results`
    - `len(results["TestLabel"]) == 2`
    - `results["TestLabel"][0].name == "TestLabel_00000.png"`
    - `results["TestLabel"][1].name == "TestLabel_00001.png"`
    - All files exist
    - All files are valid PNGs (open with PIL, verify format == "PNG")

### 6. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2026-01-01__p4-integ__render-integration-tests`
- Artifact versions: plan-v3 + plan-review-v3 + impl-vN + verify-vN + review-vN (as written)
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

- [ ] GIVEN `tests/integration/test_render_pipeline.py` WHEN `pytest -v -m integration tests/integration/` THEN all tests pass (or skip cleanly if ffmpeg/VS unavailable locally)
- [ ] GIVEN FFmpeg unavailable WHEN `pytest -v tests/integration/test_render_pipeline.py::test_overlay_application_adds_visible_content` THEN test runs (does not skip)
- [ ] GIVEN Phase 4 implementation WHEN Pyright runs on `src/frame_compare/render/` THEN 0 errors
- [ ] GIVEN Phase 4 implementation WHEN Ruff runs on `src/frame_compare/render/` THEN 0 errors
- [ ] GIVEN Phase 4 implementation WHEN `pytest tests/render/` runs THEN all unit tests pass
- [ ] GIVEN full project WHEN coverage checked THEN render module coverage > 80%
- [ ] GIVEN Docker container with VS WHEN `pytest -m vs_required tests/integration/` runs in container THEN VS integration test PASSES (not skipped)
- [ ] GIVEN Docker container with FFmpeg WHEN `pytest -m integration tests/integration/` runs in container THEN all integration tests PASS (not skipped)

## Verification Commands

```bash
# 0. Run-artifact validators (must pass before handoff)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2026-01-01__p4-integ__render-integration-tests
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v3.md

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

# 6. Docker verification (REQUIRED - ensures real VS works)
# Rebuild with --no-cache to pick up new integration tests, then run
docker compose build --no-cache
docker compose run --rm -w /home/framecompare/frame-compare frame-compare -c "pip install pytest && pytest -v -m 'integration or vs_required' tests/integration/"
```

**Pass criteria:**

- Local commands (0-5) exit 0 with no errors
- Local integration tests may skip if FFmpeg/VS unavailable locally
- Overlay test must NOT skip when FFmpeg is unavailable
- **Docker verification (step 6) is MANDATORY**: Integration tests must PASS (not skip) inside Docker container

**If validation fails:** STOP and return to Planning. Do not improvise.

## Notes for Coding Agent

1. **FFmpeg skip policy:** `require_ffmpeg` is a **normal fixture (not autouse)**. Only tests that depend on `mock_video_path` will skip when FFmpeg is unavailable. The overlay test does not depend on `mock_video_path`.

2. **VS skip policy:** At module level in `test_render_vs.py`:

   ```python
   vs = pytest.importorskip("vapoursynth")
   from unittest.mock import MagicMock
   if isinstance(vs, MagicMock):
       pytest.skip("vapoursynth is mocked", allow_module_level=True)
   ```

3. **Deterministic video fixture:** Use `-frames:v 3` to guarantee exactly 3 frames:

   ```bash
   ffmpeg -y -f lavfi -i "color=c=red:s=100x100:r=10" -frames:v 3 -c:v libx264 -pix_fmt yuv420p <output.mp4>
   ```

4. **VS clip format:** Use `format=vs.RGB24` for BlankClip to ensure 8-bit same-plane-shape compatibility with current encoder.

5. **PNG validity assertion:** Use `PIL.Image.open(path)` in a with-block, assert `img.format == "PNG"`.

6. **Overlay visibility assertion:** For solid-color input, check `len(set(img.getdata())) > 1`.

7. **Naming assertion:** Direct equality: `path.name == f"{label}_{frame:05d}.png"`.

8. **Ordering assertion:** `for i in range(len(requests)): assert results[i] == requests[i].output_path`.

9. **No network:** Integration tests must NOT make network calls.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-integ__render-integration-tests

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-integ__render-integration-tests/plan-review-v3.md
