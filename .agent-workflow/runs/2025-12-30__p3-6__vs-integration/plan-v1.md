---
RUN_ID: 2025-12-30__p3-6__vs-integration
VERSION: v1
TARGET: Phase 3 → Item 3.6 Module Integration
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v1.md
---

# Implementation Plan: VapourSynth Module Integration

## Context

**Phase:** 3
**Module:** VapourSynth (vs)
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
**Dependencies:** Phase 3.1-3.5 (Environment, Source, Props, Color, Tonemap) - ALL COMPLETE.

## Scope

This plan covers:

- [ ] Create `src/frame_compare/vs/__init__.py` to export the public API.
- [ ] Verify import contracts (via `lint-imports` check).
- [ ] Add explicit export tests in `tests/vs/test_exports.py`.
- [ ] Add a real VapourSynth integration smoke test in `tests/vs/test_integration.py` (marked with `@pytest.mark.vs_required`).

This plan does NOT cover:

- CLI Integration (Phase 6).
- Service Logic (Phase 5).

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "8. AI Agent Implementation Prompt" -> "Public Exports (vs/**init**.py)"
  - Section: "3.1 Environment"
  - Section: "3.2 Source Loading"
  - Section: "3.3 Tonemapping"
  - Section: "3.4 Frame Properties"
  - Section: "3.5 Color Operations"

## Files to Create/Modify

### 1. `src/frame_compare/vs/__init__.py` (NEW)

**Purpose:** Expose the public API of the `vs` module.

**Exports to define (SSOT Section 8):**

- `VSLoader` (Protocol)
- `DefaultVSLoader` (Implementation)
- `SourceInfo`, `HDRMetadata`, `TonemapSettings`, `ColorProps` (Types)
- `is_vapoursynth_available`, `ensure_vs_environment`, `detect_plugins`, `require_plugin` (Functions)
- `load_source`, `apply_trim` (Functions)
- `get_color_props`, `is_hdr` (Functions)
- `infer_color_props`, `apply_color_props`, `expand_limited_rgb_to_full`, `to_rgb24` (Functions)
- `tonemap` (Function - alias for `apply_tonemap` to match Spec Section 8)

### 2. `tests/vs/test_exports.py` (NEW)

**Tests required:**

- `test_public_api_symbols_are_exported` — Verify all symbols listed above are present in `frame_compare.vs`.
- `test_all_property_is_complete` — Verify `__all__` matches the exported symbols.

### 3. `tests/vs/test_integration.py` (NEW)

**Tests required:**

- `test_vs_integration_smoke` — Real VapourSynth test (not mocked).
  - Marker: `@pytest.mark.vs_required`
  - Logic:
    1. Check `is_vapoursynth_available()`.
    2. If available, call `ensure_vs_environment()`.
    3. Create a `BlankClip`.
    4. Call `source = SourceInfo(...)` with blank clip.
    5. Call `tonemap(source.clip, ...)` (fallback or placebo).
    6. Assert output is valid `vs.VideoNode`.

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
- [ ] `pytest tests/vs/test_exports.py` passes.
- [ ] `pytest -m vs_required` skips gracefully if VS missing, or passes if VS present.

## Verification Commands

```bash
.venv/bin/pyright --warnings src/frame_compare/vs
.venv/bin/ruff check src/frame_compare/vs
.venv/bin/pytest -v tests/vs/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Notes for Coding Agent

- Spec Section 8 explicitly lists `tonemap` as an export, but Section 3.3 defines `apply_tonemap`. Use `from .tonemap import apply_tonemap as tonemap` in `__init__.py`.
- Ensure `__all__` is strictly typed as `list[str]`.
- For `test_integration.py`, wrap import of `vapoursynth` in `try...except ImportError` or use `pytest.importorskip("vapoursynth")` at module level to avoid collection errors on systems without VS (though the marker should handle execution, collection needs to be safe).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-30__p3-6__vs-integration

## Plan to Review

Read file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-30__p3-6__vs-integration/plan-review-v1.md
