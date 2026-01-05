---
RUN_ID: 2026-01-01__p4-4__render-overlay
VERSION: v3
TARGET: Phase 4 → Item 4.4
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v2.md
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v3.md
---

# Implementation Plan: Render Overlay Module

## Changes Since plan-v2

- **Test configs fully specified:** All `OverlayConfig` values are complete (no placeholders)
- **Fixed expected strings:** Removed escaped pipes, use literal `|`
- **Invalid-mode check pinned:** `if not isinstance(config.mode, OverlayMode): raise ValueError(...)`
- **Monkeypatch targets explicit:** Exact patch paths for `text`, `rectangle`, and `calculate_overlay_position`
- **Removed `uv sync`:** Replaced with offline-friendly bootstrap note

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:** Phases 4.1–4.3 completed; runtime: Pillow

## Scope

This plan covers:

- [x] Create `src/frame_compare/render/overlay.py`
- [x] Implement `apply_overlay()` per SSOT Section 3.2.1
- [x] Write deterministic unit tests

This plan does NOT cover:

- Encoder integration (Phase 4.5)
- Orchestrator (Phase 4.6)

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

**Purpose:** Add Pillow runtime dependency.

**Exact change:** Add `pillow>=10.0.0` to `[project.dependencies]`.

---

### 2. [NEW] `src/frame_compare/render/overlay.py`

**Purpose:** Text overlay rendering.

**Function:** `apply_overlay(image: Image.Image | np.ndarray, config: OverlayConfig) -> Image.Image`

**Invalid-mode check (exact implementation):**

```python
if not isinstance(config.mode, OverlayMode):
    raise ValueError("invalid overlay mode")
```

All other behavior defined in SSOT Section 3.2.1.

---

### 3. [NEW] `tests/render/test_overlay.py`

**Monkeypatch Targets (exact paths):**

- `PIL.ImageDraw.ImageDraw.text`
- `PIL.ImageDraw.ImageDraw.rectangle`
- `frame_compare.render.overlay.calculate_overlay_position`

**Tests with complete configs:**

| Test Name | Config | Expected Assertion |
|-----------|--------|-------------------|
| `test_apply_overlay_minimal_mode` | `OverlayConfig(mode=OverlayMode.MINIMAL, label="Source", frame_number=100, resolution=(1920, 1080), hdr_info=None, font_path=None)` | Captured `text()` call includes `"Source"` |
| `test_apply_overlay_standard_mode` | `OverlayConfig(mode=OverlayMode.STANDARD, label="Ref", frame_number=100, resolution=(1920, 1080), hdr_info=None, font_path=None)` | Captured text is `"Ref | Frame 00100 | 1920x1080"` |
| `test_apply_overlay_diagnostic_with_hdr` | `OverlayConfig(mode=OverlayMode.DIAGNOSTIC, label="Encode", frame_number=200, resolution=(3840, 2160), hdr_info="PQ / BT.2020", font_path=None)` | Captured text contains `"PQ / BT.2020"` |
| `test_apply_overlay_diagnostic_sdr` | `OverlayConfig(mode=OverlayMode.DIAGNOSTIC, label="SDR_Test", frame_number=50, resolution=(1280, 720), hdr_info=None, font_path=None)` | Captured text contains `"SDR"` |
| `test_apply_overlay_returns_pil_image` | `OverlayConfig(mode=OverlayMode.MINIMAL, label="Test", frame_number=1, resolution=(100, 100), hdr_info=None, font_path=None)` | `isinstance(result, Image.Image)` |
| `test_apply_overlay_accepts_numpy` | Same config, input=`np.zeros((100, 100, 3), dtype=np.uint8)` | Returns `Image.Image` |
| `test_apply_overlay_none_image_raises` | image=None, any valid config | `ValueError("image must not be None")` |
| `test_apply_overlay_invalid_mode_raises` | `OverlayConfig(mode=cast(OverlayMode, "bogus"), label="X", frame_number=0, resolution=(100, 100), hdr_info=None, font_path=None)` | `ValueError("invalid overlay mode")` |
| `test_apply_overlay_calls_position_function` | `OverlayConfig(..., position="bottom-right", ...)` | `calculate_overlay_position` called with `position="bottom-right"` |
| `test_apply_overlay_draws_rectangle` | Any valid config | `rectangle()` called ≥1 times |

**Monkeypatch Example (complete):**

```python
from typing import cast
from unittest.mock import MagicMock
from PIL import Image
import numpy as np
from frame_compare.render.overlay import apply_overlay
from frame_compare.render.types import OverlayConfig, OverlayMode

def test_apply_overlay_minimal_mode(mocker):
    captured_text = []
    def mock_text(self, xy, text, **kwargs):
        captured_text.append(text)
    mocker.patch("PIL.ImageDraw.ImageDraw.text", mock_text)
    mocker.patch("PIL.ImageDraw.ImageDraw.rectangle", MagicMock())

    config = OverlayConfig(
        mode=OverlayMode.MINIMAL,
        label="Source",
        frame_number=100,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
    )
    result = apply_overlay(Image.new("RGB", (100, 100)), config)

    assert any("Source" in t for t in captured_text)
    assert isinstance(result, Image.Image)
```

---

### 4. [MODIFY] `src/frame_compare/render/__init__.py`

**Exact change:** Add import and append `"apply_overlay"` to end of `__all__`.

---

### 5. [MODIFY] `docs/DECISIONS.md`

**Required facts:** RUN_ID, SSOT edits: None, Dependencies added: `pillow>=10.0.0`

---

### 6. [MODIFY] `CHANGELOG.md`

**Entry:** Added `render.overlay` module and Pillow dependency.

## Acceptance Criteria

- [ ] GIVEN mode=MINIMAL, label="Test" THEN captured text is "Test"
- [ ] GIVEN mode=STANDARD THEN captured text is "{label} | Frame {frame:05d} | {w}x{h}"
- [ ] GIVEN mode=DIAGNOSTIC, hdr_info="PQ" THEN captured text contains "PQ"
- [ ] GIVEN numpy input THEN returns `PIL.Image.Image`
- [ ] GIVEN image=None THEN raises `ValueError("image must not be None")`
- [ ] GIVEN invalid mode THEN raises `ValueError("invalid overlay mode")`
- [ ] GIVEN `pytest tests/render/test_overlay.py` THEN all tests pass

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v3.md

# Bootstrap (if .venv missing/outdated):
# uv sync --group dev --frozen

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

**Pass criteria:** All exit 0.

## Notes for Coding Agent

1. **Invalid-mode check:** `if not isinstance(config.mode, OverlayMode): raise ValueError("invalid overlay mode")`
2. **PIL imports:** `from PIL import Image, ImageDraw, ImageFont`
3. **NumPy conversion:** `Image.fromarray(array)`
4. **Default font:** `ImageFont.load_default()`
5. **Text shadow:** Draw at (x+1, y+1) black, then white
6. **Padding constant:** `_PADDING = 8`

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-4__render-overlay

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v3.md
