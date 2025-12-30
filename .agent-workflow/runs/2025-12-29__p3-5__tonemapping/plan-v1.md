---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v1
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v1.md
---

# Implementation Plan: HDR Tonemapping

## Context

**Phase:** 3
**Module:** `frame_compare.vs`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
**Dependencies:** Phase 3.4 (Color Operations) complete; `TonemapSettings` and `HDRMetadata` already exist in `types.py`

## Scope

This plan covers:

- [ ] Create `src/frame_compare/vs/tonemap.py`
- [ ] Define `TONEMAP_PRESETS` dict (7 presets)
- [ ] Implement `apply_tonemap(clip, settings, hdr_metadata) -> VideoNode`
- [ ] Implement `get_preset_settings(preset) -> TonemapSettings`
- [ ] Implement `_apply_libplacebo()` internal function
- [ ] Implement `_fallback_tonemap()` for missing libplacebo
- [ ] Update `vs/__init__.py` to export tonemap functions
- [ ] Write unit tests (mocked) and VS-required tests

This plan does NOT cover:

- Render module (Phase 4)
- CLI integration with tonemapping options (Phase 6)
- Performance optimization or caching

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "2.2 TonemapSettings"
  - Section: "3.3 Tonemapping"
  - Section: "4. Tonemap Presets"
  - Section: "5.2 libplacebo Integration"
  - Section: "5.3 Fallback Handling"
  - Section: "6. Error Handling"

## Public API Signatures (mechanically checkable)

- `apply_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
- `get_preset_settings(preset: str) -> TonemapSettings`

Internal (private):

- `_apply_libplacebo(clip: vs.VideoNode, settings: TonemapSettings, core: vs.Core) -> vs.VideoNode`
- `_fallback_tonemap(clip: vs.VideoNode, settings: TonemapSettings) -> vs.VideoNode`

## Determinism (Required)

- All preset settings are static and deterministic
- Tonemapping output is deterministic given the same input clip and settings
- No random seeds or sampling involved

## Files to Create/Modify (Complete List)

### 1. `src/frame_compare/vs/tonemap.py` (NEW)

**Purpose:** HDR to SDR tonemapping via libplacebo with fallback

**Constants to define:**

- `TONEMAP_PRESETS: dict[str, TonemapSettings]` — 7 presets per Section 4

**Functions to implement:**

- `apply_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
  - Check if libplacebo available via `detect_plugins()`
  - If available, call `_apply_libplacebo()`
  - If unavailable, call `_fallback_tonemap()`
  - Raise `TonemapError` on failure

- `get_preset_settings(preset: str) -> TonemapSettings`
  - Look up preset in `TONEMAP_PRESETS`
  - Raise `TonemapError` if preset not found

- `_apply_libplacebo(clip: vs.VideoNode, settings: TonemapSettings, core: vs.Core) -> vs.VideoNode`
  - Convert to float RGB (if needed)
  - Call `core.placebo.Tonemap()` with settings
  - Apply contrast recovery if enabled
  - Apply gamma lift if enabled

- `_fallback_tonemap(clip: vs.VideoNode, settings: TonemapSettings) -> vs.VideoNode`
  - Simple Reinhard curve via `core.std` operations
  - Quality degraded but functional

**Preset values (from Section 4):**

| Preset | tone_curve | target_nits | contrast_recovery | gamma_lift |
|--------|------------|-------------|-------------------|------------|
| `reference` | bt2390 | 203 | 0.0 | False |
| `filmic` | spline | 203 | 0.0 | False |
| `contrast` | reinhard | 203 | 0.0 | False |
| `bt2390_spec` | bt2390 | 100 | 0.0 | False |
| `spline` | spline | 203 | 0.0 | False |
| `bright_lift` | bt2390 | 250 | 0.0 | True |
| `highlight_guard` | spline | 180 | 0.0 | False |

### 2. `src/frame_compare/vs/__init__.py` (MODIFY)

**Purpose:** Export tonemapping functions

**Changes:**

- Add import: `from frame_compare.vs.tonemap import apply_tonemap, get_preset_settings, TONEMAP_PRESETS`
- Add to `__all__`: `"apply_tonemap"`, `"get_preset_settings"`, `"TONEMAP_PRESETS"`

### 3. `tests/vs/test_tonemap.py` (NEW)

**Purpose:** Unit tests for tonemapping

**Tests required:**

- `test_get_preset_settings_returns_valid_settings`
  - Assert `get_preset_settings("reference")` returns `TonemapSettings` with `tone_curve="bt2390"`, `target_nits=203`
- `test_get_preset_settings_all_presets_exist`
  - Assert all 7 preset names exist in `TONEMAP_PRESETS`
- `test_get_preset_settings_unknown_raises_tonemap_error`
  - Assert `get_preset_settings("invalid")` raises `TonemapError`
- `test_apply_tonemap_uses_fallback_when_libplacebo_missing`
  - Mock `detect_plugins()` to return `{"libplacebo": False}`
  - Assert fallback path is taken (mock `_fallback_tonemap`)
- `test_apply_tonemap_uses_libplacebo_when_available`
  - Mock `detect_plugins()` to return `{"libplacebo": True}`
  - Assert libplacebo path is taken (mock `_apply_libplacebo`)
- `test_tonemap_presets_have_correct_values`
  - Parametrized test checking each preset's curve/nits match Section 4 table

### 4. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry

**Required facts to record:**

- RUN_ID + artifact versions
- Scope: Phase 3.5 Tonemapping with libplacebo integration + fallback
- Preset values sourced from VS module spec Section 4
- No SSOT edits (spec already complete)
- Verification gates run + pass/fail

### 5. `CHANGELOG.md` (MODIFY)

**Purpose:** Add short entry for tonemapping feature

**Entry:**

- Add tonemapping support with 7 HDR-to-SDR presets
- libplacebo integration with Reinhard fallback for environments without libplacebo

## Acceptance Criteria

- [ ] GIVEN a preset name WHEN `get_preset_settings("reference")` is called THEN return `TonemapSettings` with `tone_curve="bt2390"` and `target_nits=203`
- [ ] GIVEN libplacebo is available WHEN `apply_tonemap()` is called THEN libplacebo path is used
- [ ] GIVEN libplacebo is unavailable WHEN `apply_tonemap()` is called THEN fallback path is used
- [ ] GIVEN an unknown preset name WHEN `get_preset_settings("invalid")` is called THEN `TonemapError` is raised
- [ ] GIVEN all tests pass WHEN verification commands run THEN all exit 0

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → Command Canon.

```bash
# Validate run artifacts
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-29__p3-5__tonemapping
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-29__p3-5__tonemapping
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v1.md

# Quality gates
.venv/bin/pyright --warnings src/frame_compare/vs/tonemap.py
.venv/bin/ruff check src/frame_compare/vs/tonemap.py tests/vs/test_tonemap.py
.venv/bin/pytest -v tests/vs/test_tonemap.py

# Full suite
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0.

## Notes for Coding Agent

- `TonemapSettings` already exists in `types.py` — do not redefine
- Use `detect_plugins(core)["libplacebo"]` to check availability
- Import `TonemapError` from `frame_compare.errors`
- The fallback uses basic Reinhard curve: `output = input / (1 + input)` scaled appropriately
- For libplacebo, map `tone_curve` to placebo's `gamut_mapping` / `tone_mapping_function` parameters
- The `hdr_metadata` parameter is optional; if None, extract from clip's frame 0 props
- Keep `_apply_libplacebo()` and `_fallback_tonemap()` as private (underscore prefix)

---

> **Proposed RUN_ID:** 2025-12-29__p3-5__tonemapping
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2025-12-29__p3-5__tonemapping` before running Plan Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p3-5__tonemapping

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v1.md
