---
RUN_ID: 2026-01-01__p4-4__render-overlay
VERSION: v1
TARGET: Phase 4 → Item 4.4
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v1.md
---

# Implementation Plan: Render Overlay Module

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:** Phase 4.1 (types), Phase 4.2 (geometry), Phase 4.3 (naming) — completed

## Scope

This plan covers:

- [x] Create `src/frame_compare/render/overlay.py`
- [x] Implement `apply_overlay()` per SSOT Section 3.2.1
- [x] Support overlay modes (MINIMAL, STANDARD, DIAGNOSTIC)
- [x] Include frame number, label, resolution text
- [x] Include HDR metadata in diagnostic mode
- [x] Write unit tests

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

## Files to Create/Modify

### 1. [MODIFY] `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`

**Purpose:** Added Section 3.2.1 with deterministic behavior rules during this run.

**Changes made:** Added `#### 3.2.1 apply_overlay Behavior` with algorithm, constants, and invalid-input rules.

---

### 2. [NEW] `src/frame_compare/render/overlay.py`

**Purpose:** Text overlay rendering for screenshots.

**Functions to implement:**

- `apply_overlay(image: PIL.Image.Image | np.ndarray, config: OverlayConfig) -> PIL.Image.Image`

All behavior defined in SSOT Section 3.2.1. Internal helpers are implementation details.

---

### 3. [NEW] `tests/render/test_overlay.py`

**Tests required:**

| Test Name | Scenario | Expected |
|-----------|----------|----------|
| `test_apply_overlay_minimal_mode` | mode=MINIMAL, label="Source" | Text is `"Source"` |
| `test_apply_overlay_standard_mode` | mode=STANDARD, label="Ref", frame=100, res=(1920,1080) | Text contains `"Ref | Frame 00100 | 1920x1080"` |
| `test_apply_overlay_diagnostic_mode` | mode=DIAGNOSTIC, hdr_info="PQ / BT.2020" | Text contains `"PQ / BT.2020"` |
| `test_apply_overlay_diagnostic_sdr` | mode=DIAGNOSTIC, hdr_info=None | Text contains `"SDR"` |
| `test_apply_overlay_returns_pil_image` | Any valid config | Returns `PIL.Image.Image` |
| `test_apply_overlay_accepts_numpy` | Input as np.ndarray (RGB uint8) | Returns `PIL.Image.Image` |
| `test_apply_overlay_none_image_raises` | image=None | `ValueError("image must not be None")` |
| `test_apply_overlay_uses_position` | position="bottom-right" | Overlay is in bottom-right region |
| `test_apply_overlay_default_font` | font_path=None | Uses PIL default (no error) |

**Note:** Overlay visual correctness tests check text presence in specific regions using pixel sampling or image diff; exact pixel matching is not required (font rendering varies).

---

### 4. [MODIFY] `src/frame_compare/render/__init__.py`

**Purpose:** Export overlay function.

**Exact change:**

1. Add imports after existing imports:

   ```python
   from frame_compare.render.overlay import apply_overlay
   ```

2. Append to existing `__all__` list:

   ```python
   __all__ = [
       # ... existing 11 exports ...
       "apply_overlay",
   ]
   ```

---

### 5. [MODIFY] `docs/DECISIONS.md`

**Required facts to record:**

- RUN_ID: `2026-01-01__p4-4__render-overlay`
- SSOT edits: Added Section 3.2.1 to `render-module.md`
- Scope: overlay rendering only

---

### 6. [MODIFY] `CHANGELOG.md`

**Entry:**

```markdown
### Added
- `render.overlay` module with text overlay rendering supporting MINIMAL/STANDARD/DIAGNOSTIC modes
```

## Acceptance Criteria

- [ ] GIVEN `apply_overlay(image, OverlayConfig(mode=MINIMAL, label="Test", ...))` THEN overlay contains "Test"
- [ ] GIVEN `apply_overlay(image, OverlayConfig(mode=STANDARD, ...))` THEN overlay contains label, frame, resolution
- [ ] GIVEN `apply_overlay(image, OverlayConfig(mode=DIAGNOSTIC, hdr_info="PQ"))` THEN overlay contains "PQ"
- [ ] GIVEN `apply_overlay(numpy_array, config)` THEN returns `PIL.Image.Image`
- [ ] GIVEN `apply_overlay(None, config)` THEN raises `ValueError`
- [ ] GIVEN Pyright strict mode WHEN analyzing `render/` THEN 0 errors
- [ ] GIVEN `pytest tests/render/test_overlay.py` THEN all tests pass

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v1.md

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

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-4__render-overlay

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v1.md
