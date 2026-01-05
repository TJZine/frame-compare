---
RUN_ID: 2026-01-01__p4-2__render-geometry
VERSION: v1
TARGET: Phase 4 → Item 4.2
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v1.md
---

# Implementation Plan: Render Geometry Utilities

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` → Section 5
**Dependencies:** Phase 4.1 (render/types.py) — completed

## Scope

This plan covers:

- [x] Create `src/frame_compare/render/geometry.py`
- [x] Implement `calculate_dimensions()` — aspect-ratio-preserving resize
- [x] Implement `calculate_overlay_position()` — overlay top-left corner
- [x] Implement `ensure_mod2()` — mod-2 padding helper
- [x] Write unit tests for all geometry functions

This plan does NOT cover:

- Auto-crop detection (deferred to a future slice; requires VS integration)
- Overlay rendering (Phase 4.4)
- Encoder integration (Phase 4.5)

## Contract Impact

**Contracts touched:** NO

No canonical contract files are modified by this slice.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: "5. Geometry Utilities"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. [NEW] `src/frame_compare/render/geometry.py`

**Purpose:** Geometry calculation utilities for screenshot rendering.

**Functions to implement (spec-anchored):**

- `calculate_dimensions(source_width: int, source_height: int, max_width: int | None = None, max_height: int | None = None) -> tuple[int, int]`
- `calculate_overlay_position(image_size: tuple[int, int], overlay_size: tuple[int, int], position: str, margin: int = 10) -> tuple[int, int]`
- `ensure_mod2(width: int, height: int) -> tuple[int, int]`

**Behavior spec (from SSOT Section 5):**

1. **`calculate_dimensions`**:
   - Preserve aspect ratio when constrained by max_width or max_height
   - If no constraints, return original dimensions
   - If both constraints apply, fit within the smaller bounding box
   - Return values must be positive integers

2. **`calculate_overlay_position`**:
   - Accepts `position` in `{"top-left", "top-right", "bottom-left", "bottom-right"}`
   - Returns top-left (x, y) corner for overlay placement
   - Applies `margin` offset from image edges
   - Invalid position → raise `ValueError`

3. **`ensure_mod2`**:
   - Round dimensions up to nearest even values
   - Required for video encoding compatibility (H.264/H.265)

---

### 2. [NEW] `tests/render/test_geometry.py`

**Tests required:**

| Test Name | Scenario | Expected |
|-----------|----------|----------|
| `test_calculate_dimensions_no_constraints_returns_original` | No max_width/max_height | Returns (source_width, source_height) |
| `test_calculate_dimensions_max_width_constrains` | 1920×1080, max_width=960 | (960, 540) |
| `test_calculate_dimensions_max_height_constrains` | 1920×1080, max_height=540 | (960, 540) |
| `test_calculate_dimensions_both_constraints_fits_within` | 3840×2160, max_width=1920, max_height=720 | (1280, 720) |
| `test_calculate_dimensions_preserves_aspect_ratio` | 1280×720, max_width=640 | (640, 360) |
| `test_overlay_position_top_left` | image=(1920,1080), overlay=(200,50), margin=10 | (10, 10) |
| `test_overlay_position_top_right` | image=(1920,1080), overlay=(200,50), margin=10 | (1710, 10) |
| `test_overlay_position_bottom_left` | image=(1920,1080), overlay=(200,50), margin=10 | (10, 1020) |
| `test_overlay_position_bottom_right` | image=(1920,1080), overlay=(200,50), margin=10 | (1710, 1020) |
| `test_overlay_position_invalid_raises` | position="center" | Raises `ValueError` |
| `test_ensure_mod2_already_even` | (1920, 1080) | (1920, 1080) |
| `test_ensure_mod2_rounds_up` | (1919, 1079) | (1920, 1080) |

---

### 3. [MODIFY] `src/frame_compare/render/__init__.py`

**Purpose:** Export geometry utilities from the render module.

**Change:** Add to `__all__`:

```python
from frame_compare.render.geometry import (
    calculate_dimensions,
    calculate_overlay_position,
    ensure_mod2,
)
```

---

### 4. [MODIFY] `docs/DECISIONS.md`

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2026-01-01__p4-2__render-geometry`
- Scope: geometry utilities only; auto-crop deferred
- SSOT edits: none
- Verification gates: pyright, ruff, pytest

---

### 5. [MODIFY] `CHANGELOG.md`

**Purpose:** Add entry for geometry utilities.

**Entry format:**

```markdown
### Added
- `render.geometry` module with dimension calculation and overlay positioning utilities
```

## Acceptance Criteria

- [ ] GIVEN `calculate_dimensions(1920, 1080, max_width=960)` THEN returns `(960, 540)`
- [ ] GIVEN `calculate_dimensions(3840, 2160, max_width=1920, max_height=720)` THEN returns `(1280, 720)`
- [ ] GIVEN `calculate_overlay_position((1920, 1080), (200, 50), "bottom-right", 10)` THEN returns `(1710, 1020)`
- [ ] GIVEN `calculate_overlay_position(..., position="invalid")` THEN raises `ValueError`
- [ ] GIVEN `ensure_mod2(1919, 1079)` THEN returns `(1920, 1080)`
- [ ] GIVEN Pyright strict mode WHEN analyzing `geometry.py` THEN 0 errors
- [ ] GIVEN `pytest tests/render/test_geometry.py` THEN all tests pass

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v1.md
.venv/bin/pyright --warnings src/frame_compare/render/geometry.py
.venv/bin/ruff check src/frame_compare/render/
.venv/bin/pytest -v tests/render/test_geometry.py
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **No external dependencies** — geometry.py uses only stdlib (math for floor/ceil if needed)
2. **Integer arithmetic** — all return values must be `int`, use `//` for division
3. **Aspect ratio formula** — `new_height = source_height * new_width // source_width`
4. **mod2 rounding** — use `(n + 1) & ~1` or `n + (n % 2)` for ceiling to even
5. **Position map** — use a dict mapping position strings to coordinate formulas

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-2__render-geometry

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-review-v1.md
