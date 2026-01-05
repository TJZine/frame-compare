---
RUN_ID: 2026-01-01__p4-4__render-overlay
VERSION: v2
TARGET: Phase 4 → Item 4.4
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v1.md
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v2.md
---

# Implementation Plan: Render Overlay Module

## Changes Since plan-v1

- **Public API signature added:** Backticked one-line signature for `apply_overlay`
- **Pillow dependency added:** `pyproject.toml` [MODIFY] to add `pillow>=10.0.0`
- **SSOT edit claim removed:** SSOT already contains Section 3.2.1 (no churn needed)
- **Tests made deterministic:** Monkeypatch strategy for `ImageDraw.Draw` and position function
- **Exports made explicit:** Append `"apply_overlay"` to `__all__` (end of list)
- **Missing negative test added:** Invalid mode raises `ValueError`

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:** Phase 4.1 (types), Phase 4.2 (geometry), Phase 4.3 (naming) — completed; runtime: Pillow

## Scope

This plan covers:

- [x] Create `src/frame_compare/render/overlay.py`
- [x] Implement `apply_overlay()` per SSOT Section 3.2.1
- [x] Support overlay modes (MINIMAL, STANDARD, DIAGNOSTIC)
- [x] Write deterministic unit tests

This plan does NOT cover:

- Encoder integration (Phase 4.5)
- Orchestrator (Phase 4.6)
- Font file bundling (uses PIL default when no font_path provided)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: "3.2 Overlay"
  - Section: "3.2.1 `apply_overlay` Behavior"
  - Section: "2.0 OverlayMode"
  - Section: "2.2 OverlayConfig"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Public API (signatures)

- `apply_overlay(image: Image.Image | np.ndarray, config: OverlayConfig) -> Image.Image`

## Files to Create/Modify

### 1. [MODIFY] `pyproject.toml`

**Purpose:** Add Pillow runtime dependency for overlay rendering.

**Exact change:** Add `pillow>=10.0.0` to the dependencies list in `[project.dependencies]`.

---

### 2. [NEW] `src/frame_compare/render/overlay.py`

**Purpose:** Text overlay rendering for screenshots.

**Functions to implement:**

- `apply_overlay(image: Image.Image | np.ndarray, config: OverlayConfig) -> Image.Image`

All behavior defined in SSOT Section 3.2.1.

---

### 3. [NEW] `tests/render/test_overlay.py`

**Deterministic Testing Strategy:**

Tests will monkeypatch `ImageDraw.Draw` to capture draw calls rather than inspect pixels.

| Test Name | Scenario | Deterministic Assertion |
|-----------|----------|------------------------|
| `test_apply_overlay_minimal_mode` | mode=MINIMAL, label="Source" | Monkeypatch `draw.text()` captures string `"Source"` |
| `test_apply_overlay_standard_mode` | mode=STANDARD, label="Ref", frame=100, res=(1920,1080) | Captured text is `"Ref \| Frame 00100 \| 1920x1080"` |
| `test_apply_overlay_diagnostic_mode` | mode=DIAGNOSTIC, hdr_info="PQ / BT.2020" | Captured text contains `"PQ / BT.2020"` |
| `test_apply_overlay_diagnostic_sdr` | mode=DIAGNOSTIC, hdr_info=None | Captured text contains `"SDR"` |
| `test_apply_overlay_returns_pil_image` | Any valid config | Returns instance of `PIL.Image.Image` |
| `test_apply_overlay_accepts_numpy` | Input as np.ndarray (100x100 RGB uint8) | Returns `PIL.Image.Image` |
| `test_apply_overlay_none_image_raises` | image=None | `ValueError("image must not be None")` |
| `test_apply_overlay_invalid_mode_raises` | config with mode=cast(OverlayMode, "bogus") | `ValueError("invalid overlay mode")` |
| `test_apply_overlay_calls_position_function` | position="bottom-right" | Monkeypatch `calculate_overlay_position` called with `position="bottom-right"` |
| `test_apply_overlay_draws_rectangle` | Any config | Monkeypatch `draw.rectangle()` called at least once |

**Monkeypatch Example:**

```python
def test_apply_overlay_minimal_mode(mocker):
    captured_text = []
    def mock_text(self, xy, text, **kwargs):
        captured_text.append(text)
    mocker.patch("PIL.ImageDraw.ImageDraw.text", mock_text)

    config = OverlayConfig(mode=OverlayMode.MINIMAL, label="Source", ...)
    result = apply_overlay(Image.new("RGB", (100, 100)), config)

    assert "Source" in captured_text
```

---

### 4. [MODIFY] `src/frame_compare/render/__init__.py`

**Purpose:** Export overlay function.

**Exact change:**

1. Add import after existing imports:

   ```python
   from frame_compare.render.overlay import apply_overlay
   ```

2. Append `"apply_overlay"` to end of existing `__all__` list (keep all existing entries unchanged).

---

### 5. [MODIFY] `docs/DECISIONS.md`

**Required facts to record:**

- RUN_ID: `2026-01-01__p4-4__render-overlay`
- SSOT edits: None (Section 3.2.1 already existed)
- Dependencies added: `pillow>=10.0.0`
- Scope: overlay rendering only

---

### 6. [MODIFY] `CHANGELOG.md`

**Entry:**

```markdown
### Added
- `render.overlay` module with text overlay rendering supporting MINIMAL/STANDARD/DIAGNOSTIC modes
- Pillow dependency for image operations
```

## Acceptance Criteria

- [ ] GIVEN `apply_overlay(image, OverlayConfig(mode=MINIMAL, label="Test", ...))` THEN overlay text is "Test"
- [ ] GIVEN `apply_overlay(image, OverlayConfig(mode=STANDARD, ...))` THEN overlay contains label, frame, resolution
- [ ] GIVEN `apply_overlay(image, OverlayConfig(mode=DIAGNOSTIC, hdr_info="PQ"))` THEN overlay contains "PQ"
- [ ] GIVEN `apply_overlay(numpy_array, config)` THEN returns `PIL.Image.Image`
- [ ] GIVEN `apply_overlay(None, config)` THEN raises `ValueError`
- [ ] GIVEN config with invalid mode THEN raises `ValueError("invalid overlay mode")`
- [ ] GIVEN Pyright strict mode WHEN analyzing `render/` THEN 0 errors
- [ ] GIVEN `pytest tests/render/test_overlay.py` THEN all tests pass

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v2.md

# Sync after adding Pillow
uv sync

# Quality gates (primary)
.venv/bin/pyright --warnings src/frame_compare/render/
.venv/bin/ruff check src/frame_compare/render/ tests/render/
.venv/bin/pytest -v tests/render/test_overlay.py

# Quality gates (fallback)
UV_CACHE_DIR=./.uv_cache uv run --no-sync pyright --warnings src/frame_compare/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync ruff check src/frame_compare/render/ tests/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync pytest -v tests/render/test_overlay.py

# Import contract
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors.

## Notes for Coding Agent

1. **PIL imports:** `from PIL import Image, ImageDraw, ImageFont`
2. **NumPy conversion:** `Image.fromarray(array)` for RGB uint8 arrays
3. **Default font:** `ImageFont.load_default()` when `font_path` is None
4. **Alpha compositing:** Create RGBA overlay layer, paste with alpha mask
5. **Text shadow:** Draw text at (x+1, y+1) in black before white foreground
6. **Uses geometry:** Import `calculate_overlay_position` from same package
7. **Padding constant:** `_PADDING = 8` (module-level private constant)
8. **Mode validation:** Check `config.mode in OverlayMode` or use enum member check

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-4__render-overlay

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v2.md
