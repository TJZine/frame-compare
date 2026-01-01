---
RUN_ID: 2026-01-01__p4-4__render-overlay
VERSION: v4
TARGET: Phase 4 → Item 4.4
INPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v3.md
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v4.md
---

# Implementation Plan: Render Overlay Module

## Changes Since plan-v3

- **Position test config completed:** `test_apply_overlay_calls_position_function` now has full config
- **Assertions updated for shadow+foreground:** Use `any(... in captured_text)` to handle double draw

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

**Exact change:** Add `pillow>=10.0.0` to `[project.dependencies]`.

---

### 2. [NEW] `src/frame_compare/render/overlay.py`

**Function:** `apply_overlay(image: Image.Image | np.ndarray, config: OverlayConfig) -> Image.Image`

**Invalid-mode check:**

```python
if not isinstance(config.mode, OverlayMode):
    raise ValueError("invalid overlay mode")
```

All other behavior defined in SSOT Section 3.2.1.

---

### 3. [NEW] `tests/render/test_overlay.py`

**Monkeypatch Targets:**

- `PIL.ImageDraw.ImageDraw.text`
- `PIL.ImageDraw.ImageDraw.rectangle`
- `frame_compare.render.overlay.calculate_overlay_position`

**Tests (all configs complete, assertions handle shadow+foreground):**

| Test Name | Config | Assertion |
|-----------|--------|-----------|
| `test_apply_overlay_minimal_mode` | `OverlayConfig(mode=OverlayMode.MINIMAL, label="Source", frame_number=100, resolution=(1920, 1080), hdr_info=None, font_path=None)` | `assert any("Source" in t for t in captured_text)` |
| `test_apply_overlay_standard_mode` | `OverlayConfig(mode=OverlayMode.STANDARD, label="Ref", frame_number=100, resolution=(1920, 1080), hdr_info=None, font_path=None)` | `assert any(t == "Ref \| Frame 00100 \| 1920x1080" for t in captured_text)` |
| `test_apply_overlay_diagnostic_with_hdr` | `OverlayConfig(mode=OverlayMode.DIAGNOSTIC, label="Encode", frame_number=200, resolution=(3840, 2160), hdr_info="PQ / BT.2020", font_path=None)` | `assert any("PQ / BT.2020" in t for t in captured_text)` |
| `test_apply_overlay_diagnostic_sdr` | `OverlayConfig(mode=OverlayMode.DIAGNOSTIC, label="SDR_Test", frame_number=50, resolution=(1280, 720), hdr_info=None, font_path=None)` | `assert any("SDR" in t for t in captured_text)` |
| `test_apply_overlay_returns_pil_image` | `OverlayConfig(mode=OverlayMode.MINIMAL, label="Test", frame_number=1, resolution=(100, 100), hdr_info=None, font_path=None)` | `isinstance(result, Image.Image)` |
| `test_apply_overlay_accepts_numpy` | Same config, input=`np.zeros((100, 100, 3), dtype=np.uint8)` | Returns `Image.Image` |
| `test_apply_overlay_none_image_raises` | image=None, any valid config | `ValueError("image must not be None")` |
| `test_apply_overlay_invalid_mode_raises` | `OverlayConfig(mode=cast(OverlayMode, "bogus"), label="X", frame_number=0, resolution=(100, 100), hdr_info=None, font_path=None)` | `ValueError("invalid overlay mode")` |
| `test_apply_overlay_calls_position_function` | `OverlayConfig(mode=OverlayMode.MINIMAL, label="PosTest", frame_number=1, resolution=(100, 100), hdr_info=None, font_path=None, position="bottom-right")` | `calculate_overlay_position` called with `position="bottom-right"` |
| `test_apply_overlay_draws_rectangle` | `OverlayConfig(mode=OverlayMode.MINIMAL, label="RectTest", frame_number=1, resolution=(100, 100), hdr_info=None, font_path=None)` | `rectangle()` called ≥1 times |

---

### 4. [MODIFY] `src/frame_compare/render/__init__.py`

**Exact change:** Import `apply_overlay` and append `"apply_overlay"` to end of `__all__`.

---

### 5. [MODIFY] `docs/DECISIONS.md`

**Required facts:** RUN_ID, SSOT edits: None, Dependencies: `pillow>=10.0.0`

---

### 6. [MODIFY] `CHANGELOG.md`

**Entry:** Added `render.overlay` module and Pillow dependency.

## Acceptance Criteria

- [ ] GIVEN mode=MINIMAL THEN captured text list contains "Test" at least once
- [ ] GIVEN mode=STANDARD THEN captured text list contains exact format string at least once
- [ ] GIVEN mode=DIAGNOSTIC, hdr_info="PQ" THEN captured text contains "PQ" at least once
- [ ] GIVEN numpy input THEN returns `PIL.Image.Image`
- [ ] GIVEN image=None THEN raises `ValueError("image must not be None")`
- [ ] GIVEN invalid mode THEN raises `ValueError("invalid overlay mode")`
- [ ] GIVEN `pytest tests/render/test_overlay.py` THEN all tests pass

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v4.md

# Bootstrap if needed: uv sync --group dev --frozen

.venv/bin/pyright --warnings src/frame_compare/render/
.venv/bin/ruff check src/frame_compare/render/ tests/render/
.venv/bin/pytest -v tests/render/test_overlay.py
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All exit 0.

## Notes for Coding Agent

1. **Invalid-mode:** `if not isinstance(config.mode, OverlayMode): raise ValueError("invalid overlay mode")`
2. **Shadow+foreground:** Draw text at (x+1, y+1) black, then (x, y) white ⇒ two `text()` calls
3. **Padding:** `_PADDING = 8`
4. **Default font:** `ImageFont.load_default()`

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-01__p4-4__render-overlay

## Plan to Review

Read file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-v4.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-01__p4-4__render-overlay/plan-review-v4.md
