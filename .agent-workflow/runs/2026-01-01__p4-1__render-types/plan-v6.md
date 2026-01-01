---
RUN_ID: 2026-01-01__p4-1__render-types
VERSION: v6
TARGET: Phase 4 → Item 4.1
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v5.md
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v5.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v6.md
---

# Implementation Plan: Render Module Types

## Changes Since plan-v5

1. **Added SSOT spec file to Files to Create/Modify list** (per edit #1)

## Context

**Phase:** 4
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:**

- Import contract update required (new top-level module + independence contract)
- Uses `TYPE_CHECKING` pattern with `# type: ignore` for VS typing

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
- [x] Update `importlinter.ini` with layers + independence contract
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

## Public API (signatures)

- `OverlayMode(str, Enum)`
- `EncoderSettings(format: str = "png", compression: int = 6, bit_depth: int = 8)`
- `RenderRequest(clip: vs.VideoNode | Path, frame_number: int, output_path: Path, overlay: OverlayConfig | None, encoder_settings: EncoderSettings)`
- `OverlayConfig(mode: OverlayMode, label: str, frame_number: int, resolution: tuple[int, int], hdr_info: str | None, font_path: Path | None, font_size: int = 24, position: str = "top-left")`
- `Renderer = Literal["vapoursynth", "ffmpeg", "auto"]`
- `ScreenshotResult(label: str, paths: list[Path], frame_count: int)`

## Files to Create/Modify

### 1. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` [MODIFY]

**Purpose:** Add example construction snippets for validator discoverability.

**Changes:** Added example construction snippets under `### 2.1 RenderRequest`, `### 2.2 OverlayConfig`, `### 2.3 ScreenshotResult` (no behavior changes).

### 2. `src/frame_compare/render/.gitkeep` [DELETE]

**Purpose:** Remove placeholder file.

### 3. `src/frame_compare/render/types.py` [NEW]

**Purpose:** Central type definitions for the render module.

**Types to implement (copy SSOT code blocks exactly):**

- `class OverlayMode(str, Enum)` — per Section 2.0
- `class EncoderSettings` — per Section 2.1, use `@dataclass` (no frozen/slots)
- `class RenderRequest` — per Section 2.1, use `@dataclass` (no frozen/slots)
- `class OverlayConfig` — per Section 2.2, use `@dataclass` (no frozen/slots)
- `Renderer = Literal["vapoursynth", "ffmpeg", "auto"]` — per Section 2.2
- `class ScreenshotResult` — per Section 2.3, use `@dataclass(frozen=True)` as specified

**VS typing pattern (exact code to use):**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore
```

### 4. `src/frame_compare/render/__init__.py` [NEW]

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

### 5. `importlinter.ini` [MODIFY]

**Purpose:** Add `frame_compare.render` to layers contract + add independence contract.

**Changes:** Two modifications:

1. Add `frame_compare.render` to layers list (after `analysis`)
2. Add new independence contract to prevent `analysis`↔`render` imports

**Exact content after modification:**

```ini
[importlinter]
root_package = frame_compare

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

[importlinter:contract:domain-independence]
name = Domain Independence
type = independence
modules =
    frame_compare.analysis
    frame_compare.render
```

**Note:** The independence contract enforces that `analysis` and `render` cannot import each other (per SSOT "Forbidden Imports" table).

### 6. `tests/render/__init__.py` [NEW]

**Purpose:** Test package marker.

**Content:** Empty file.

### 7. `tests/render/test_types.py` [NEW]

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

### 8. `docs/DECISIONS.md` [MODIFY]

**Required facts to record:**

- RUN_ID: `2026-01-01__p4-1__render-types`, artifacts: plan-v1 through plan-v6, plan-review-v1 through plan-review-v5
- Scope: Render module types + import contract update (layers + independence)
- SSOT edits: Added example construction snippets to render-module.md sections 2.1, 2.2, 2.3
- Out-of-scope: encoders, geometry, naming, overlay logic, orchestrator

### 9. `CHANGELOG.md` [MODIFY]

**Entry:** Under `## [Unreleased]`:

- Added `frame_compare.render` module with type definitions

## Acceptance Criteria

- [ ] GIVEN `OverlayMode` WHEN accessing `.MINIMAL`, `.STANDARD`, `.DIAGNOSTIC` THEN all values exist
- [ ] GIVEN `EncoderSettings()` THEN defaults are format="png", compression=6, bit_depth=8
- [ ] GIVEN `OverlayConfig` with required fields THEN font_size=24 and position="top-left"
- [ ] GIVEN `RenderRequest` with `overlay=None` THEN object creates successfully
- [ ] GIVEN `typing.get_args(Renderer)` THEN result is `("vapoursynth", "ffmpeg", "auto")`
- [ ] GIVEN Pyright strict mode WHEN analyzing `types.py` THEN 0 errors
- [ ] GIVEN `lint-imports` WHEN run THEN 0 errors (layers + independence)

## Verification Commands

```bash
# Plan validation (must pass before implementation starts)
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v6.md

# Primary gates
.venv/bin/pyright --warnings src/frame_compare/render/
.venv/bin/ruff check src/frame_compare/render/ tests/render/
.venv/bin/pytest -v tests/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Fallback if .venv/bin/* unavailable
UV_CACHE_DIR=./.uv_cache uv run --no-sync pyright --warnings src/frame_compare/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync ruff check src/frame_compare/render/ tests/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync pytest -v tests/render/
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Rollback / Stop Conditions

- **If `lint-imports` fails with unclear layer ordering:** STOP and return to Planning.
- **If Pyright reports `reportMissingImports` for `vapoursynth`:** Verify `# type: ignore` is present on the import line.

## Notes for Coding Agent

1. **Enum:** `class OverlayMode(str, Enum)` — must inherit from `str`
2. **Dataclass decorators (match SSOT exactly):**
   - `EncoderSettings`, `RenderRequest`, `OverlayConfig`: plain `@dataclass`
   - `ScreenshotResult`: `@dataclass(frozen=True)`
3. **VS typing:** Use `if TYPE_CHECKING: import vapoursynth as vs  # type: ignore`
4. **Path import:** `from pathlib import Path`
5. **Literal:** `Renderer = Literal[...]` after imports, before classes
6. **Delete .gitkeep:** Delete `src/frame_compare/render/.gitkeep` after creating files

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-1__render-types

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-v6.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-1__render-types/plan-review-v6.md
