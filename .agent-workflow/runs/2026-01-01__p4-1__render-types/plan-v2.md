---
RUN_ID: 2026-01-01__p4-1__render-types
VERSION: v2
TARGET: Phase 4 → Item 4.1
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v1.md
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v2.md
---

# Implementation Plan: Render Module Types

## Changes Since plan-v1

1. **Fixed Spec Anchors to use exact SSOT headings** (per edit #1)
2. **Added mechanically-checkable one-line signatures** (per edit #2)
3. **Resolved `RenderRequest.clip` typing using `TYPE_CHECKING` pattern** (per edit #3)
4. **Added `importlinter.ini` [MODIFY] and import contract SSOT anchors** (per edit #4)
5. **Added `.gitkeep` [DELETE] to file list** (per edit #5)
6. **Tightened tests with explicit assertions for defaults and `get_args`** (per edit #6)
7. **Added Rollback/Stop Conditions section** (per edit #7)
8. **Fixed Dependencies section to mention import contract update**
9. **Added `lint-imports` to verification commands**

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:**

- Import contract update required (new top-level module `frame_compare.render`)
- Uses `TYPE_CHECKING` pattern for optional `vs.VideoNode` typing (no runtime VS dependency)

## Scope

This plan covers:

- [x] Create `src/frame_compare/render/types.py`
- [x] Define `OverlayMode` enum (MINIMAL, STANDARD, DIAGNOSTIC)
- [x] Define `EncoderSettings` dataclass
- [x] Define `OverlayConfig` dataclass
- [x] Define `RenderRequest` dataclass
- [x] Define `Renderer` type alias
- [x] Define `ScreenshotResult` dataclass
- [x] Create `src/frame_compare/render/__init__.py` with type exports
- [x] Update `importlinter.ini` with `frame_compare.render`
- [x] Write `tests/render/test_types.py` unit tests

This plan does NOT cover:

- Encoders (`encoders.py`) — Phase 4.5
- Geometry utilities (`geometry.py`) — Phase 4.2
- Naming utilities (`naming.py`) — Phase 4.3
- Overlay rendering (`overlay.py`) — Phase 4.4
- Orchestrator (`orchestrator.py`) — Phase 4.6

## Contract Impact

**Contracts touched:** NO (canonical contracts in `contracts/` are not touched; only `importlinter.ini`)

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: "2.0 OverlayMode"
  - Section: "2.1 RenderRequest"
  - Section: "2.2 OverlayConfig"
  - Section: "2.3 ScreenshotResult"
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`:
  - Section: "6. Import Contract Rules"
  - Section: "7. import-linter Configuration"

## Files to Create/Modify

### 1. `src/frame_compare/render/.gitkeep` [DELETE]

**Purpose:** Remove placeholder file.

### 2. `src/frame_compare/render/types.py` [NEW]

**Purpose:** Central type definitions for the render module.

**Types to implement (per SSOT code blocks):**

- `class OverlayMode(str, Enum)` — per Section 2.0
- `class EncoderSettings` — per Section 2.1
- `class RenderRequest` — per Section 2.1
- `class OverlayConfig` — per Section 2.2
- `Renderer = Literal["vapoursynth", "ffmpeg", "auto"]` — per Section 2.2
- `class ScreenshotResult` — per Section 2.3

All field types, defaults, and docstrings are defined in the SSOT code blocks above. Copy exactly.

**VS typing pattern (per project conventions):**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import vapoursynth as vs
```

This allows `vs.VideoNode` in annotations without runtime import.

**Dataclass conventions:**

- Use `@dataclass(frozen=True, slots=True)` per project pattern (see `analysis/types.py`)
- Exception: `ScreenshotResult.paths` is `list[Path]` not `Sequence` since it must be mutable during construction

### 3. `src/frame_compare/render/__init__.py` [NEW]

**Purpose:** Public exports for the render module.

**Content:**

```python
from frame_compare.render.types import (
    OverlayMode,
    EncoderSettings,
    OverlayConfig,
    RenderRequest,
    Renderer,
    ScreenshotResult,
)

__all__ = [
    "OverlayMode",
    "EncoderSettings",
    "OverlayConfig",
    "RenderRequest",
    "Renderer",
    "ScreenshotResult",
]
```

### 4. `importlinter.ini` [MODIFY]

**Purpose:** Add `frame_compare.render` to the layers contract.

**Change:** Add `frame_compare.render` at the same layer as `frame_compare.analysis`:

```ini
[importlinter:contract:layers]
name = Layered Architecture
type = layers
layers =
    frame_compare.cli_entry
    frame_compare.analysis
    frame_compare.render
    frame_compare.vs
    frame_compare.config
    frame_compare.utils
    frame_compare.errors
```

**Note:** Per SSOT section "## 7. import-linter Configuration", the end-state uses `(frame_compare.analysis | frame_compare.render | frame_compare.services)` but the current contract doesn't use grouping syntax. Add `render` as a separate layer at the same logical level as `analysis`.

### 5. `tests/render/__init__.py` [NEW]

**Purpose:** Test package marker.

**Content:** Empty file.

### 6. `tests/render/test_types.py` [NEW]

**Purpose:** Unit tests for render types.

**Tests required:**

| Test Name | Assertion |
|-----------|-----------|
| `test_overlay_mode_values` | `set(OverlayMode) == {OverlayMode.MINIMAL, OverlayMode.STANDARD, OverlayMode.DIAGNOSTIC}` |
| `test_overlay_mode_string_values` | `OverlayMode.MINIMAL.value == "minimal"`, etc. |
| `test_encoder_settings_defaults` | `EncoderSettings().format == "png"`, `.compression == 6`, `.bit_depth == 8` |
| `test_encoder_settings_custom` | `EncoderSettings(format="webp", compression=9, bit_depth=16)` stores values |
| `test_overlay_config_defaults` | `OverlayConfig(...).font_size == 24`, `.position == "top-left"` |
| `test_overlay_config_optional_none` | `OverlayConfig(..., hdr_info=None, font_path=None)` succeeds |
| `test_render_request_optional_overlay` | `RenderRequest(..., overlay=None, ...)` succeeds |
| `test_screenshot_result_creation` | `ScreenshotResult("label", [Path("a.png")], 1)` stores all fields |
| `test_renderer_literal_values` | `typing.get_args(Renderer) == ("vapoursynth", "ffmpeg", "auto")` |

### 7. `docs/DECISIONS.md` [MODIFY]

**Required facts to record:**

- RUN_ID: `2026-01-01__p4-1__render-types`, artifacts: plan-v1, plan-review-v1, plan-v2
- Scope: Render module types + import contract update
- SSOT edits: Added OverlayMode (2.0) and ScreenshotResult (2.3) to render-module.md
- Out-of-scope: encoders, geometry, naming, overlay logic, orchestrator

### 8. `CHANGELOG.md` [MODIFY]

**Entry:** Under `## [Unreleased]`:

- Added `frame_compare.render` module with type definitions

## Acceptance Criteria

- [ ] GIVEN `OverlayMode` WHEN accessing `.MINIMAL`, `.STANDARD`, `.DIAGNOSTIC` THEN all values exist
- [ ] GIVEN `EncoderSettings()` THEN defaults are format="png", compression=6, bit_depth=8
- [ ] GIVEN `OverlayConfig` with required fields THEN font_size=24 and position="top-left"
- [ ] GIVEN `RenderRequest` with `overlay=None` THEN object creates successfully
- [ ] GIVEN `typing.get_args(Renderer)` THEN result is `("vapoursynth", "ffmpeg", "auto")`
- [ ] GIVEN Pyright strict mode WHEN analyzing `types.py` THEN 0 errors
- [ ] GIVEN `lint-imports` WHEN run THEN 0 errors

## Verification Commands

```bash
# Primary gates
.venv/bin/pyright --warnings src/frame_compare/render/
.venv/bin/ruff check src/frame_compare/render/
.venv/bin/pytest -v tests/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Fallback if .venv/bin/* unavailable
UV_CACHE_DIR=./.uv_cache uv run --no-sync pyright --warnings src/frame_compare/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync ruff check src/frame_compare/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync pytest -v tests/render/
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Rollback / Stop Conditions

- **If `lint-imports` fails with unclear layer ordering:** STOP and return to Planning. Do not guess import contract rules.
- **If Pyright reports `reportMissingImports` for `vapoursynth`:** Verify `TYPE_CHECKING` block is correct. Do not remove the `vs.VideoNode` type from the annotation.

## Notes for Coding Agent

1. **Enum pattern:** `class OverlayMode(str, Enum)` — must inherit from `str` for serialization
2. **Dataclass pattern:** `@dataclass(frozen=True, slots=True)` — matches project conventions
3. **VS typing:** Use `from __future__ import annotations` + `if TYPE_CHECKING: import vapoursynth as vs`
4. **Path import:** `from pathlib import Path`
5. **Literal placement:** `Renderer = Literal[...]` after imports, before class definitions
6. **Position docstring:** Document valid values in `OverlayConfig.position` docstring
7. **Delete .gitkeep:** Must be removed (file will exist after tests/render created)

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-1__render-types

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v2.md
