---
RUN_ID: 2026-01-01__p4-2__render-geometry
VERSION: v3
TARGET: Phase 4 → Item 4.2
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v2.md
  - .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v3.md
---

# Implementation Plan: Render Geometry Utilities

## Changes Since plan-v2

- **File list fixed:** Added SSOT spec file as modified (Sections 5.1–5.3)
- **Test scenario explicit:** `test_overlay_position_clamps_when_too_large` now has full inputs
- **`__init__.py` deterministic:** Exact append behavior specified, no placeholders
- **Verification fixed:** Primary commands cover full `render/` dir; fallbacks uncommented with `--no-sync`

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:** Phase 4.1 (render/types.py) — completed

## Scope

This plan covers:

- [x] Create `src/frame_compare/render/geometry.py`
- [x] Implement `calculate_dimensions()` per SSOT Section 5.1
- [x] Implement `calculate_overlay_position()` per SSOT Section 5.2
- [x] Implement `ensure_mod2()` per SSOT Section 5.3
- [x] Write unit tests including input validation

This plan does NOT cover:

- Auto-crop detection (deferred; requires VS integration)
- Overlay rendering (Phase 4.4)
- Encoder integration (Phase 4.5)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: "5. Geometry Utilities"
  - Section: "5.1 `calculate_dimensions` Behavior"
  - Section: "5.2 `calculate_overlay_position` Behavior"
  - Section: "5.3 `ensure_mod2` Behavior"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. [MODIFY] `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`

**Purpose:** Added Sections 5.1, 5.2, 5.3 with deterministic behavior rules during this run.

**Changes made:** Added `### 5.1 calculate_dimensions Behavior`, `### 5.2 calculate_overlay_position Behavior`, `### 5.3 ensure_mod2 Behavior` with algorithm and invalid-input rules.

---

### 2. [NEW] `src/frame_compare/render/geometry.py`

**Purpose:** Geometry calculation utilities for screenshot rendering.

**Functions to implement:**

- `calculate_dimensions(source_width: int, source_height: int, max_width: int | None = None, max_height: int | None = None) -> tuple[int, int]`
- `calculate_overlay_position(image_size: tuple[int, int], overlay_size: tuple[int, int], position: str, margin: int = 10) -> tuple[int, int]`
- `ensure_mod2(width: int, height: int) -> tuple[int, int]`

All behavior is defined in SSOT Sections 5.1–5.3.

---

### 3. [NEW] `tests/render/test_geometry.py`

**Tests required:**

| Test Name | Scenario | Expected |
|-----------|----------|----------|
| `test_calculate_dimensions_no_constraints` | source=(1920,1080), max_width=None, max_height=None | `(1920, 1080)` |
| `test_calculate_dimensions_max_width_constrains` | source=(1920,1080), max_width=960, max_height=None | `(960, 540)` |
| `test_calculate_dimensions_max_height_constrains` | source=(1920,1080), max_width=None, max_height=540 | `(960, 540)` |
| `test_calculate_dimensions_both_constraints` | source=(3840,2160), max_width=1920, max_height=720 | `(1280, 720)` |
| `test_calculate_dimensions_constraint_exceeds_source` | source=(1280,720), max_width=1920, max_height=None | `(1280, 720)` |
| `test_calculate_dimensions_invalid_source_raises` | source_width=0, source_height=100 | `ValueError("source dimensions must be positive")` |
| `test_calculate_dimensions_invalid_max_raises` | source=(100,100), max_width=-1 | `ValueError("max dimensions must be positive")` |
| `test_overlay_position_top_left` | image=(1920,1080), overlay=(200,50), position="top-left", margin=10 | `(10, 10)` |
| `test_overlay_position_top_right` | image=(1920,1080), overlay=(200,50), position="top-right", margin=10 | `(1710, 10)` |
| `test_overlay_position_bottom_left` | image=(1920,1080), overlay=(200,50), position="bottom-left", margin=10 | `(10, 1020)` |
| `test_overlay_position_bottom_right` | image=(1920,1080), overlay=(200,50), position="bottom-right", margin=10 | `(1710, 1020)` |
| `test_overlay_position_invalid_raises` | image=(1920,1080), overlay=(100,50), position="center", margin=10 | `ValueError("invalid position: center")` |
| `test_overlay_position_clamps_when_too_large` | image=(1920,1080), overlay=(1900,1060), position="bottom-right", margin=50 | `(0, 0)` |
| `test_overlay_position_invalid_dims_raises` | image=(0,100), overlay=(10,10), position="top-left", margin=10 | `ValueError("dimensions must be positive")` |
| `test_ensure_mod2_already_even` | width=1920, height=1080 | `(1920, 1080)` |
| `test_ensure_mod2_rounds_up` | width=1919, height=1079 | `(1920, 1080)` |
| `test_ensure_mod2_invalid_raises` | width=0, height=100 | `ValueError("dimensions must be positive")` |

---

### 4. [MODIFY] `src/frame_compare/render/__init__.py`

**Purpose:** Export geometry utilities.

**Exact change:**

1. Add imports after existing imports:

   ```python
   from frame_compare.render.geometry import (
       calculate_dimensions,
       calculate_overlay_position,
       ensure_mod2,
   )
   ```

2. Append to existing `__all__` list (keep all existing entries unchanged):

   ```python
   __all__ = [
       # ... all existing exports from Phase 4.1 ...
       "calculate_dimensions",
       "calculate_overlay_position",
       "ensure_mod2",
   ]
   ```

---

### 5. [MODIFY] `docs/DECISIONS.md`

**Required facts to record:**

- RUN_ID: `2026-01-01__p4-2__render-geometry`
- SSOT edits: Added Sections 5.1–5.3 to `render-module.md`
- Scope: geometry utilities only; auto-crop deferred

---

### 6. [MODIFY] `CHANGELOG.md`

**Entry:**

```markdown
### Added
- `render.geometry` module with dimension calculation and overlay positioning utilities
```

## Acceptance Criteria

- [ ] GIVEN `calculate_dimensions(1920, 1080, max_width=960)` THEN returns `(960, 540)`
- [ ] GIVEN `calculate_dimensions(0, 100)` THEN raises `ValueError`
- [ ] GIVEN `calculate_overlay_position((1920, 1080), (200, 50), "bottom-right", 10)` THEN returns `(1710, 1020)`
- [ ] GIVEN `calculate_overlay_position(..., position="center")` THEN raises `ValueError`
- [ ] GIVEN `ensure_mod2(1919, 1079)` THEN returns `(1920, 1080)`
- [ ] GIVEN `ensure_mod2(0, 100)` THEN raises `ValueError`
- [ ] GIVEN Pyright strict mode WHEN analyzing `render/` THEN 0 errors
- [ ] GIVEN `pytest tests/render/test_geometry.py` THEN all tests pass

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v3.md

# Quality gates (primary — .venv)
.venv/bin/pyright --warnings src/frame_compare/render/
.venv/bin/ruff check src/frame_compare/render/ tests/render/
.venv/bin/pytest -v tests/render/test_geometry.py

# Quality gates (fallback — uv run)
UV_CACHE_DIR=./.uv_cache uv run --no-sync pyright --warnings src/frame_compare/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync ruff check src/frame_compare/render/ tests/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync pytest -v tests/render/test_geometry.py

# Import contract
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors.

## Notes for Coding Agent

1. **No external dependencies** — only stdlib (`math` if needed)
2. **Integer arithmetic** — use `//` for division, `int()` for truncation
3. **Aspect ratio:** `ratio = source_width / source_height` (float division)
4. **mod2 formula:** `(width + width % 2, height + height % 2)`
5. **Coordinate clamping:** `max(0, computed_x)` for overlay overflow

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-2__render-geometry

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-2__render-geometry/plan-review-v3.md
