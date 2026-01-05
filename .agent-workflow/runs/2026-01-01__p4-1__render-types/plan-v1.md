---
RUN_ID: 2026-01-01__p4-1__render-types
VERSION: v1
TARGET: Phase 4 → Item 4.1
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v1.md
---

# Implementation Plan: Render Module Types

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:** None (types-only module; no imports from other `frame_compare` modules)

## Scope

This plan covers:

- [x] Create `src/frame_compare/render/types.py`
- [x] Define `OverlayMode` enum (MINIMAL, STANDARD, DIAGNOSTIC)
- [x] Define `EncoderSettings` dataclass
- [x] Define `OverlayConfig` dataclass
- [x] Define `RenderRequest` dataclass
- [x] Define `Renderer` type alias
- [x] Define `ScreenshotResult` dataclass (for batch render return)
- [x] Create `src/frame_compare/render/__init__.py` with type exports
- [x] Write `tests/render/test_types.py` unit tests

This plan does NOT cover:

- Encoders (`encoders.py`) — Phase 4.5
- Geometry utilities (`geometry.py`) — Phase 4.2
- Naming utilities (`naming.py`) — Phase 4.3
- Overlay rendering (`overlay.py`) — Phase 4.4
- Orchestrator (`orchestrator.py`) — Phase 4.6

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: "2.0 OverlayMode"
  - Section: "2.1 RenderRequest" (includes `RenderRequest` and `EncoderSettings`)
  - Section: "2.2 OverlayConfig" (includes `OverlayConfig` and `Renderer`)
  - Section: "2.3 ScreenshotResult"

## Files to Create/Modify

### 1. `src/frame_compare/render/types.py` [NEW]

**Purpose:** Central type definitions for the render module.

**Types to define:**

- `OverlayMode` — Enum with values MINIMAL, STANDARD, DIAGNOSTIC
- `EncoderSettings` — PNG encoding configuration
- `OverlayConfig` — Overlay text/position configuration
- `RenderRequest` — Single frame render job specification
- `Renderer` — Literal type alias for renderer selection
- `ScreenshotResult` — Result of a batch screenshot operation

**Types to implement (per SSOT section references above):**

- `class OverlayMode(str, Enum)` — per Section 2.0
- `class EncoderSettings` — per Section 2.1
- `class RenderRequest` — per Section 2.1 (use `Path` for clip; VS integration deferred)
- `class OverlayConfig` — per Section 2.2
- `Renderer = Literal["vapoursynth", "ffmpeg", "auto"]` — per Section 2.2
- `class ScreenshotResult` — per Section 2.3

**Determinism:** None required for types.

### 2. `src/frame_compare/render/__init__.py` [NEW]

**Purpose:** Public exports for the render module.

**Exports:**

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

### 3. `tests/render/__init__.py` [NEW]

**Purpose:** Test package marker.

**Content:** Empty file.

### 4. `tests/render/test_types.py` [NEW]

**Purpose:** Unit tests for render types.

**Tests required:**

- `test_overlay_mode_values` — Verify enum has MINIMAL, STANDARD, DIAGNOSTIC
- `test_overlay_mode_string_values` — Verify string values match lowercase
- `test_encoder_settings_defaults` — Verify format="png", compression=6, bit_depth=8
- `test_encoder_settings_custom` — Verify custom values are accepted
- `test_overlay_config_creation` — Verify all fields stored correctly
- `test_overlay_config_optional_fields` — Verify hdr_info and font_path can be None
- `test_render_request_creation` — Verify all fields stored correctly
- `test_render_request_optional_overlay` — Verify overlay can be None
- `test_screenshot_result_creation` — Verify label, paths, frame_count stored
- `test_renderer_type_values` — Verify Literal accepts "vapoursynth", "ffmpeg", "auto"

### 5. `docs/DECISIONS.md` [MODIFY]

**Purpose:** Append run decision entry.

**Required facts to record:**

- RUN_ID: `2026-01-01__p4-1__render-types`
- Artifact versions: plan-v1
- Scope: Render module types only (no logic, no encoding, no overlay rendering)
- SSOT edits: None
- Out-of-scope: encoders, geometry, naming, overlay logic, orchestrator

### 6. `CHANGELOG.md` [MODIFY]

**Purpose:** Add entry for new render types module.

**Entry:** Under `## [Unreleased]`, add:

- Added `frame_compare.render` module with type definitions (`OverlayMode`, `EncoderSettings`, `OverlayConfig`, `RenderRequest`, `Renderer`, `ScreenshotResult`)

## Acceptance Criteria

- [ ] GIVEN `OverlayMode` imported WHEN accessing `.MINIMAL`, `.STANDARD`, `.DIAGNOSTIC` THEN all three values exist
- [ ] GIVEN `EncoderSettings()` with no args WHEN instantiated THEN defaults are format="png", compression=6, bit_depth=8
- [ ] GIVEN `OverlayConfig` with required fields WHEN `hdr_info=None` and `font_path=None` THEN object creates successfully
- [ ] GIVEN `RenderRequest` with `overlay=None` WHEN instantiated THEN object creates successfully
- [ ] GIVEN `ScreenshotResult` with label, paths list, frame_count WHEN instantiated THEN all fields accessible
- [ ] GIVEN Pyright strict mode WHEN analyzing `types.py` THEN 0 errors reported

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/render/
.venv/bin/ruff check src/frame_compare/render/
.venv/bin/pytest -v tests/render/
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Enum pattern:** Use `class OverlayMode(str, Enum)` so values serialize to strings naturally
2. **Dataclass frozen:** Consider `@dataclass(frozen=True)` for immutability (matches project conventions)
3. **Path import:** Import `Path` from `pathlib`
4. **Type alias:** `Renderer = Literal["vapoursynth", "ffmpeg", "auto"]` — place after imports
5. **Position values:** The `position` field in `OverlayConfig` accepts: `"top-left"`, `"top-right"`, `"bottom-left"`, `"bottom-right"` (document in docstring)
6. **No VS dependency:** `RenderRequest.clip` uses `Path` only; VapourSynth integration comes in Phase 4.5
7. **Delete `.gitkeep`:** Remove `src/frame_compare/render/.gitkeep` after creating `types.py`

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-1__render-types

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v1.md
