---
RUN_ID: 2026-01-01__p4-4__render-overlay
VERSION: v5
TARGET: Phase 4 → Item 4.4
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v4.md
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v5.md
---

# Implementation Plan: Render Overlay Module

## Changes Since plan-v4

- **Fixed STANDARD-mode expected string:** Use literal `|` (not escaped)
- **Restored uv-run fallback commands:** Added `UV_CACHE_DIR=... uv run --no-sync` variants

## Context

**Phase:** 4 | **Module:** `frame_compare.render` | **Dependencies:** Phases 4.1–4.3; runtime: Pillow

## Scope

- [x] Create `overlay.py` with `apply_overlay()` per SSOT Section 3.2.1
- [x] Write deterministic unit tests

NOT covered: Encoders (4.5), Orchestrator (4.6)

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

Add `pillow>=10.0.0` to `[project.dependencies]`.

### 2. [NEW] `src/frame_compare/render/overlay.py`

Implement `apply_overlay`. Invalid-mode: `if not isinstance(config.mode, OverlayMode): raise ValueError("invalid overlay mode")`.

### 3. [NEW] `tests/render/test_overlay.py`

**Monkeypatch:** `PIL.ImageDraw.ImageDraw.text`, `.rectangle`, `frame_compare.render.overlay.calculate_overlay_position`

| Test | Config | Assertion |
|------|--------|-----------|
| `test_apply_overlay_minimal_mode` | MINIMAL, label="Source", frame=100, res=(1920,1080), hdr=None, font=None | `any("Source" in t for t in captured_text)` |
| `test_apply_overlay_standard_mode` | STANDARD, label="Ref", frame=100, res=(1920,1080), hdr=None, font=None | `any(t == "Ref | Frame 00100 | 1920x1080" for t in captured_text)` |
| `test_apply_overlay_diagnostic_with_hdr` | DIAGNOSTIC, label="Encode", frame=200, res=(3840,2160), hdr="PQ / BT.2020", font=None | `any("PQ / BT.2020" in t for t in captured_text)` |
| `test_apply_overlay_diagnostic_sdr` | DIAGNOSTIC, label="SDR_Test", frame=50, res=(1280,720), hdr=None, font=None | `any("SDR" in t for t in captured_text)` |
| `test_apply_overlay_returns_pil_image` | MINIMAL, label="Test", frame=1, res=(100,100), hdr=None, font=None | `isinstance(result, Image.Image)` |
| `test_apply_overlay_accepts_numpy` | Same, input=np.zeros((100,100,3), uint8) | Returns `Image.Image` |
| `test_apply_overlay_none_image_raises` | image=None | `ValueError("image must not be None")` |
| `test_apply_overlay_invalid_mode_raises` | mode=cast(OverlayMode,"bogus"), label="X", frame=0, res=(100,100) | `ValueError("invalid overlay mode")` |
| `test_apply_overlay_calls_position_function` | MINIMAL, label="PosTest", frame=1, res=(100,100), position="bottom-right" | `calculate_overlay_position` called with `position="bottom-right"` |
| `test_apply_overlay_draws_rectangle` | MINIMAL, label="RectTest", frame=1, res=(100,100) | `rectangle()` called ≥1 |

### 4. [MODIFY] `src/frame_compare/render/__init__.py`

Import `apply_overlay`, append `"apply_overlay"` to `__all__`.

### 5. [MODIFY] `docs/DECISIONS.md`

RUN_ID, SSOT edits: None, Added: `pillow>=10.0.0`

### 6. [MODIFY] `CHANGELOG.md`

Added `render.overlay`, Pillow dependency.

## Acceptance Criteria

- [ ] MINIMAL mode captures "Test"
- [ ] STANDARD mode captures exact string with literal pipes
- [ ] DIAGNOSTIC with hdr captures "PQ"
- [ ] numpy input returns PIL.Image
- [ ] None image raises ValueError
- [ ] invalid mode raises ValueError

## Verification Commands

```bash
# Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v5.md

# Bootstrap if needed: uv sync --group dev --frozen

# Primary (.venv)
.venv/bin/pyright --warnings src/frame_compare/render/
.venv/bin/ruff check src/frame_compare/render/ tests/render/
.venv/bin/pytest -v tests/render/test_overlay.py

# Fallback (uv run)
UV_CACHE_DIR=./.uv_cache uv run --no-sync pyright --warnings src/frame_compare/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync ruff check src/frame_compare/render/ tests/render/
UV_CACHE_DIR=./.uv_cache uv run --no-sync pytest -v tests/render/test_overlay.py

# Import contract
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Notes for Coding Agent

1. Invalid-mode: `if not isinstance(config.mode, OverlayMode): raise ValueError("invalid overlay mode")`
2. Shadow+foreground: draw text at (x+1,y+1) black, then (x,y) white
3. `_PADDING = 8`
4. Default font: `ImageFont.load_default()`

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-4__render-overlay

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v5.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v5.md
