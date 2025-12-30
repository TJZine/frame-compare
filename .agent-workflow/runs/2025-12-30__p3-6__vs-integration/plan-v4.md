---
RUN_ID: 2025-12-30__p3-6__vs-integration
VERSION: v4
TARGET: Phase 3 → Item 3.6 Module Integration
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v4.md
---

# Implementation Plan: VapourSynth Module Integration

## Changes Since plan-v3

- **SSOT Update:** Added full call-form signature for `tonemap` to SSOT exports list.
- **Spec Anchors:** Corrected `Public Exports (vs/__init__.py)` anchor to be verbatim (removed markdown bolding).
- **Verification:** Updated verification commands to target `plan-v4.md`.

## Context

**Phase:** 3
**Module:** VapourSynth (vs)
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
**Dependencies:** Phase 3.1-3.5 (Environment, Source, Props, Color, Tonemap) - ALL COMPLETE.

## Scope

This plan covers:

- [ ] Update `src/frame_compare/vs/__init__.py` to export the public API.
- [ ] Verify import contracts (via `lint-imports` check).
- [ ] Add explicit export tests in `tests/vs/test_exports.py`.
- [ ] Add a real VapourSynth integration smoke test in `tests/vs/test_integration.py` (marked with `@pytest.mark.vs_required`).

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "8. AI Agent Implementation Prompt"
  - Section: "Public Exports (vs/**init**.py)"
  - Section: "3.1 Environment"
  - Section: "3.2 Source Loading"
  - Section: "3.3 Tonemapping"
  - Section: "3.4 Frame Properties"
  - Section: "3.5 Color Operations"

## Public API Signatures (mechanically checkable)

- `tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
  - (Alias for `apply_tonemap`, exported as `tonemap`)
- `apply_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
- `get_preset_settings(preset: str) -> TonemapSettings`

## Files to Create/Modify

### 1. `src/frame_compare/vs/__init__.py` (MODIFY)

**Purpose:** Expose the public API of the `vs` module.

**Exports to define (SSOT Section 8):**

- `VSLoader` (Protocol)
- `DefaultVSLoader` (Implementation)
- `SourceInfo`, `HDRMetadata`, `TonemapSettings`, `ColorProps` (Types)
- `is_vapoursynth_available`, `ensure_vs_environment`, `detect_plugins`, `require_plugin` (Functions)
- `load_source`, `apply_trim` (Functions)
- `get_color_props`, `is_hdr` (Functions)
- `infer_color_props`, `apply_color_props`, `expand_limited_rgb_to_full`, `to_rgb24` (Functions)
- `tonemap` (Function - alias for `apply_tonemap`)
- `apply_tonemap` (Function)
- `get_preset_settings` (Function)

### 2. `tests/vs/test_exports.py` (NEW)

**Tests required:**

- Global constant for the file:

  ```python
  EXPECTED_EXPORTS = {
      "VSLoader", "DefaultVSLoader",
      "SourceInfo", "HDRMetadata", "TonemapSettings", "ColorProps",
      "is_vapoursynth_available", "ensure_vs_environment", "detect_plugins", "require_plugin",
      "load_source", "apply_trim",
      "get_color_props", "is_hdr",
      "infer_color_props", "apply_color_props", "expand_limited_rgb_to_full", "to_rgb24",
      "tonemap", "apply_tonemap", "get_preset_settings"
  }
  ```

- `test_public_api_symbols_are_exported`
  - **Logic:**

    ```python
    # Check that all expected symbols are present in vs module
    for name in EXPECTED_EXPORTS:
        assert hasattr(frame_compare.vs, name)
    ```

- `test_all_property_is_complete`
  - **Logic:**

    ```python
    # Ensure __all__ contains exactly the expected set, sorted
    assert sorted(frame_compare.vs.__all__) == sorted(list(EXPECTED_EXPORTS))
    ```

### 3. `tests/vs/test_integration.py` (NEW)

**Tests required:**

- `test_vs_integration_smoke` — Real VapourSynth test (not mocked).
  - Marker: `@pytest.mark.vs_required`
  - **Logic:**

    ```python
    vs = pytest.importorskip("vapoursynth")
    from frame_compare.vs import (
        is_vapoursynth_available, ensure_vs_environment,
        tonemap, TonemapSettings
    )

    if not is_vapoursynth_available():
        pytest.skip("VapourSynth not available")

    # 1. Initialize core
    core = ensure_vs_environment()

    # 2. Create blank clip (1 frame, RGBS)
    clip = core.std.BlankClip(width=1920, height=1080, format=vs.RGBS, length=1)

    # 3. Call tonemap (alias)
    # Using defaults: enabled=True, preset="reference"
    settings = TonemapSettings(enabled=True)
    out = tonemap(clip, settings, hdr_metadata=None)

    # 4. Verify output
    assert isinstance(out, vs.VideoNode)
    assert out.width == 1920
    assert out.height == 1080
    assert out.format.id == vs.RGBS
    ```

### 4. `docs/DECISIONS.md` (MODIFY)

**Required facts to record:**

- RUN_ID: 2025-12-30__p3-6__vs-integration
- Aliased `apply_tonemap` as `tonemap` in `__init__.py` to satisfy Spec Section 8 requirement.
- Added `test_integration.py` with `@pytest.mark.vs_required` to validate real VS runtime if present.

### 5. `CHANGELOG.md` (MODIFY)

**Entry:**

- `feat(vs): Finalize VapourSynth module exports and integration tests`

## Acceptance Criteria

- [ ] `from frame_compare import vs` works.
- [ ] `from frame_compare.vs import tonemap` works (points to `apply_tonemap`).
- [ ] `pytest tests/vs/test_exports.py` passes (verifies exact `__all__`).
- [ ] `pytest -m vs_required` skips gracefully if VS missing, or passes if VS present.

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-30__p3-6__vs-integration
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-30__p3-6__vs-integration
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v4.md

.venv/bin/pyright --warnings src/frame_compare/vs
.venv/bin/ruff check src/frame_compare/vs
.venv/bin/pytest -v tests/vs/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Notes for Coding Agent

- Spec Section 8 explicitly lists `tonemap` as an export. Use `from .tonemap import apply_tonemap as tonemap` in `__init__.py`.
- `EXPECTED_EXPORTS` set in `test_exports.py` must match strict list in `__all__`.
- `test_integration.py` must handle `ImportError` gracefully during collection (use `pytest.importorskip` at top level or try/except block).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-30__p3-6__vs-integration

## Plan to Review

Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v4.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v4.md
