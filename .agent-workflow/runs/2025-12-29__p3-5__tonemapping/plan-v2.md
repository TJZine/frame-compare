---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v2
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v1.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v2.md
---

# Implementation Plan: HDR Tonemapping

## Changes Since plan-v1

- **SSOT updated:** Added behavioral requirements to Section 3.3 (enabled=False, core acquisition, fallback rule, unknown preset error)
- **SSOT updated:** Added Preset Resolution Rules to Section 4 (full TonemapSettings mapping)
- **SSOT updated:** Added libplacebo kwarg mapping table to Section 5.2 (tone_curve mapping, hdr_metadata handling, post-processing)
- **SSOT updated:** Added Fallback Algorithm to Section 5.3 (Reinhard formula, std.Expr implementation, output expectations)
- Removed `TONEMAP_PRESETS` from public exports (per review feedback)
- Added failure-mode tests per review requirements
- Removed "VS-required tests" from scope (using mocks per repo patterns)

## Context

**Phase:** 3
**Module:** `frame_compare.vs`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
**Dependencies:** Phase 3.4 (Color Operations) complete; `TonemapSettings` and `HDRMetadata` already exist in `types.py`

## Scope

This plan covers:

- [ ] Create `src/frame_compare/vs/tonemap.py`
- [ ] Define `_TONEMAP_PRESETS` dict (private, 7 presets)
- [ ] Implement `apply_tonemap(clip, settings, hdr_metadata) -> VideoNode`
- [ ] Implement `get_preset_settings(preset) -> TonemapSettings`
- [ ] Implement `_apply_libplacebo()` internal function
- [ ] Implement `_fallback_tonemap()` for missing libplacebo
- [ ] Update `vs/__init__.py` to export public tonemap functions
- [ ] Write unit tests (mocked only; no VS-required tests this run)

This plan does NOT cover:

- Render module (Phase 4)
- CLI integration with tonemapping options (Phase 6)
- VS-required integration tests (deferred; repo uses mocks)
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

Internal (private, not exported):

- `_apply_libplacebo(clip: vs.VideoNode, settings: TonemapSettings, core: vs.Core) -> vs.VideoNode`
- `_fallback_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None) -> vs.VideoNode`
- `_TONEMAP_PRESETS: dict[str, TonemapSettings]` (private constant)

## Determinism (Required)

- All preset settings are static and deterministic
- Tonemapping output is deterministic given the same input clip and settings
- No random seeds or sampling involved
- Fallback uses deterministic Reinhard formula

## Files to Create/Modify (Complete List)

### 1. `src/frame_compare/vs/tonemap.py` (NEW)

**Purpose:** HDR to SDR tonemapping via libplacebo with Reinhard fallback

**Private constants:**

- `_TONEMAP_PRESETS: dict[str, TonemapSettings]` — 7 presets per Section 4

**Functions to implement (anchored to SSOT Section 3.3, 5.2, 5.3):**

- `apply_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
  - If `settings.enabled == False`: return `clip` unchanged
  - Obtain core via `clip.std` (not `ensure_vs_environment()`)
  - Check libplacebo via `detect_plugins(core)["libplacebo"]`
  - If available: call `_apply_libplacebo()`
  - If unavailable: call `_fallback_tonemap()` silently
  - Wrap exceptions in `TonemapError(FC-4003)`

- `get_preset_settings(preset: str) -> TonemapSettings`
  - Look up preset in `_TONEMAP_PRESETS`
  - Raise `TonemapError(FC-4003)` with hint if not found

- `_apply_libplacebo(clip: vs.VideoNode, settings: TonemapSettings, core: vs.Core) -> vs.VideoNode`
  - Convert to RGBS via `resize.Bicubic`
  - Map `tone_curve` to `tone_mapping_function`: `"bt2390"` → `2`, `"spline"` → `1`, `"reinhard"` → `4`
  - Call `core.placebo.Tonemap(src_max=..., dst_max=settings.target_nits, tone_mapping_function=...)`
  - Apply contrast_recovery post-processing if > 0.0
  - Apply gamma_lift post-processing if True

- `_fallback_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None) -> vs.VideoNode`
  - Ensure clip is RGBS
  - Apply Reinhard: `x / (1 + x / target_nits * (peak / target_nits))` via `std.Expr`
  - Apply same post-processing (contrast_recovery, gamma_lift)

### 2. `src/frame_compare/vs/__init__.py` (MODIFY)

**Purpose:** Export tonemapping functions (public API only)

**Changes:**

- Add import: `from frame_compare.vs.tonemap import apply_tonemap, get_preset_settings`
- Add to `__all__`: `"apply_tonemap"`, `"get_preset_settings"`
- Do NOT export `_TONEMAP_PRESETS` (private)

### 3. `tests/vs/test_tonemap.py` (NEW)

**Purpose:** Unit tests for tonemapping (mocked)

**Tests required:**

- `test_get_preset_settings_returns_valid_settings`
  - Assert `get_preset_settings("reference")` returns `TonemapSettings` with `preset="reference"`, `tone_curve="bt2390"`, `target_nits=203`, `enabled=True`

- `test_get_preset_settings_all_presets_exist`
  - Parametrized: all 7 preset names return valid `TonemapSettings`

- `test_get_preset_settings_unknown_raises_tonemap_error`
  - Assert `get_preset_settings("invalid")` raises `TonemapError` with code `FC-4003`

- `test_apply_tonemap_enabled_false_returns_clip_unchanged`
  - Create mock clip with `settings.enabled=False`
  - Assert returned clip is same object as input

- `test_apply_tonemap_uses_fallback_when_libplacebo_missing`
  - Mock `detect_plugins()` to return `{"libplacebo": False}`
  - Mock `_fallback_tonemap` and assert it is called

- `test_apply_tonemap_uses_libplacebo_when_available`
  - Mock `detect_plugins()` to return `{"libplacebo": True}`
  - Mock `_apply_libplacebo` and assert it is called

- `test_tonemap_presets_have_correct_values`
  - Parametrized test checking each preset's curve/nits/gamma_lift match SSOT Section 4

- `test_apply_tonemap_wraps_exception_in_tonemap_error`
  - Mock libplacebo path to raise `Exception`
  - Assert `TonemapError` is raised with code `FC-4003`

### 4. `docs/DECISIONS.md` (MODIFY)

**Required facts to record:**

- RUN_ID: 2025-12-29__p3-5__tonemapping, artifacts: plan-v1, plan-review-v1, plan-v2, plan-review-v2, impl-v1, verify-v1, review-v1
- Scope: Phase 3.5 Tonemapping with libplacebo integration + Reinhard fallback
- SSOT edits: Added behavioral requirements to Section 3.3, preset resolution to Section 4, libplacebo mapping to Section 5.2, fallback algorithm to Section 5.3
- Verification gates: pyright, ruff, pytest, lint-imports

### 5. `CHANGELOG.md` (MODIFY)

**Entry:**

- Add HDR tonemapping support with 7 presets (reference, filmic, contrast, bt2390_spec, spline, bright_lift, highlight_guard)
- libplacebo integration with silent Reinhard fallback for environments without libplacebo

## Acceptance Criteria

- [ ] GIVEN `settings.enabled == False` WHEN `apply_tonemap()` is called THEN return clip unchanged
- [ ] GIVEN preset name "reference" WHEN `get_preset_settings("reference")` is called THEN return `TonemapSettings` with `tone_curve="bt2390"`, `target_nits=203`
- [ ] GIVEN libplacebo is available WHEN `apply_tonemap()` is called THEN libplacebo path is used
- [ ] GIVEN libplacebo is unavailable WHEN `apply_tonemap()` is called THEN fallback path is used silently
- [ ] GIVEN an unknown preset name WHEN `get_preset_settings("invalid")` is called THEN `TonemapError(FC-4003)` is raised
- [ ] GIVEN all tests pass WHEN verification commands run THEN all exit 0

## Verification Commands

```bash
# Validate run artifacts
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-29__p3-5__tonemapping
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-29__p3-5__tonemapping
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v2.md

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
- Obtain core via `clip.std` (uses clip's existing core), NOT `ensure_vs_environment()`
- Import `detect_plugins` from `frame_compare.vs.env`
- Import `TonemapError` from `frame_compare.errors`
- Import `_detect_hdr` from `source.py` if extracting hdr_metadata from frame 0
- The `_TONEMAP_PRESETS` dict is private (underscore prefix), not exported
- Map `tone_curve` strings to placebo ints: `"bt2390"` → `2`, `"spline"` → `1`, `"reinhard"` → `4`
- For `source_peak` resolution: use `settings.source_peak` or `hdr_metadata.max_cll` or `1000`
- Reinhard formula operates on float RGB (RGBS format)
- If behavior unclear, STOP and return to Planning (do not make design decisions)

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p3-5__tonemapping

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v2.md
