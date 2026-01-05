---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v3
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v2.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v3.md
---

# Implementation Plan: HDR Tonemapping

## Changes Since plan-v2

- **SSOT updated:** Section 3.3 now specifies exact core acquisition: `core = clip.std.core` (AttributeError propagated)
- **SSOT updated:** Section 5.2 now specifies unsupported `tone_curve` raises `TonemapError(FC-4003)` with hint
- **SSOT updated:** Section 5.3 now provides exact `std.Expr` expression for fallback Reinhard formula with clamping
- **SSOT updated:** Section 5.2/5.3 now provide exact `std.Expr` expression for `contrast_recovery` post-processing
- **File list fixed:** Added `vs-module.md` to Files to Create/Modify

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
- [ ] Write unit tests (mocked only)

This plan does NOT cover:

- Render module (Phase 4)
- CLI integration with tonemapping options (Phase 6)
- VS-required integration tests (deferred; repo uses mocks)

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
- Fallback uses deterministic Reinhard formula with explicit clamping

## Files to Create/Modify (Complete List)

### 1. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` (MODIFY)

**Purpose:** SSOT updates for this run

**Sections modified:**

- Section 3.3: Core acquisition expression, failure mode
- Section 5.2: Unsupported tone_curve handling, contrast_recovery expression
- Section 5.3: Exact std.Expr expressions with clamping

### 2. `src/frame_compare/vs/tonemap.py` (NEW)

**Purpose:** HDR to SDR tonemapping via libplacebo with Reinhard fallback

**Private constants:**

- `_TONEMAP_PRESETS: dict[str, TonemapSettings]` — 7 presets per Section 4
- `_TONE_CURVE_MAP: dict[str, int]` — `{"bt2390": 2, "spline": 1, "reinhard": 4}`

**Functions to implement (anchored to SSOT Section 3.3, 5.2, 5.3):**

- `apply_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
  - If `settings.enabled == False`: return `clip` unchanged
  - Core acquisition: `core = clip.std.core` (AttributeError propagates)
  - Check libplacebo via `detect_plugins(core)["libplacebo"]`
  - If available: call `_apply_libplacebo()`
  - If unavailable: call `_fallback_tonemap()` silently
  - Wrap tonemap exceptions in `TonemapError(FC-4003)`

- `get_preset_settings(preset: str) -> TonemapSettings`
  - Look up preset in `_TONEMAP_PRESETS`
  - Raise `TonemapError(FC-4003)` with hint if not found

- `_apply_libplacebo(clip: vs.VideoNode, settings: TonemapSettings, core: vs.Core) -> vs.VideoNode`
  - Convert to RGBS via `resize.Bicubic`
  - Check `settings.tone_curve` in `_TONE_CURVE_MAP`; if not, raise `TonemapError(FC-4003)` with hint
  - Call `core.placebo.Tonemap(src_max=..., dst_max=settings.target_nits, tone_mapping_function=...)`
  - If `contrast_recovery > 0.0`: apply `std.Expr` with `f"x 0.5 - {1 + contrast_recovery} * 0.5 + 0 max 1 min"`
  - If `gamma_lift == True`: apply `std.Levels(gamma=0.9)`

- `_fallback_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None) -> vs.VideoNode`
  - Ensure clip is RGBS (convert if needed)
  - Apply Reinhard via `std.Expr`: `f"x {peak} / dup 1 + / {target_nits} {peak} / * 0 max 1 min"`
  - Apply same post-processing (contrast_recovery, gamma_lift)

### 3. `src/frame_compare/vs/__init__.py` (MODIFY)

**Purpose:** Export tonemapping functions (public API only)

**Changes:**

- Add import: `from frame_compare.vs.tonemap import apply_tonemap, get_preset_settings`
- Add to `__all__`: `"apply_tonemap"`, `"get_preset_settings"`

### 4. `tests/vs/test_tonemap.py` (NEW)

**Purpose:** Unit tests for tonemapping (mocked)

**Tests required:**

- `test_get_preset_settings_returns_valid_settings`
  - Assert `get_preset_settings("reference")` returns `TonemapSettings` with `preset="reference"`, `tone_curve="bt2390"`, `target_nits=203`

- `test_get_preset_settings_all_presets_exist`
  - Parametrized: all 7 preset names return valid `TonemapSettings`

- `test_get_preset_settings_unknown_raises_tonemap_error`
  - Assert `get_preset_settings("invalid")` raises `TonemapError` with code `FC-4003`

- `test_apply_tonemap_enabled_false_returns_clip_unchanged`
  - Create mock clip with `settings.enabled=False`
  - Assert returned clip is same object as input

- `test_apply_tonemap_uses_fallback_when_libplacebo_missing`
  - Mock `detect_plugins()` to return `{"libplacebo": False}`
  - Assert fallback path is taken

- `test_apply_tonemap_uses_libplacebo_when_available`
  - Mock `detect_plugins()` to return `{"libplacebo": True}`
  - Assert libplacebo path is taken

- `test_apply_tonemap_unsupported_tone_curve_raises_error`
  - Set `settings.tone_curve="invalid"`
  - Assert `TonemapError(FC-4003)` raised with hint

- `test_apply_tonemap_wraps_exception_in_tonemap_error`
  - Mock libplacebo to raise `Exception`
  - Assert `TonemapError(FC-4003)` is raised

- `test_tonemap_presets_have_correct_values`
  - Parametrized: check each preset's curve/nits/gamma_lift match SSOT Section 4

### 5. `docs/DECISIONS.md` (MODIFY)

**Required facts to record:**

- RUN_ID: 2025-12-29__p3-5__tonemapping
- Artifacts: plan-v1..v3, plan-review-v1..v3, impl-v1, verify-v1, review-v1
- Scope: Phase 3.5 Tonemapping
- SSOT edits: Section 3.3 (core acquisition), Section 5.2 (tone_curve handling, contrast_recovery), Section 5.3 (exact expressions)

### 6. `CHANGELOG.md` (MODIFY)

**Entry:**

- Add HDR tonemapping with 7 presets
- libplacebo integration with Reinhard fallback

## Acceptance Criteria

- [ ] GIVEN `settings.enabled == False` WHEN `apply_tonemap()` is called THEN return clip unchanged
- [ ] GIVEN preset name "reference" WHEN `get_preset_settings("reference")` is called THEN return `TonemapSettings` with `tone_curve="bt2390"`, `target_nits=203`
- [ ] GIVEN libplacebo is available WHEN `apply_tonemap()` is called THEN libplacebo path is used
- [ ] GIVEN libplacebo is unavailable WHEN `apply_tonemap()` is called THEN fallback path is used silently
- [ ] GIVEN unknown preset WHEN `get_preset_settings("invalid")` is called THEN `TonemapError(FC-4003)` is raised
- [ ] GIVEN unsupported tone_curve WHEN `apply_tonemap()` is called THEN `TonemapError(FC-4003)` is raised with hint
- [ ] GIVEN all tests pass WHEN verification commands run THEN all exit 0

## Verification Commands

```bash
# Validate run artifacts
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-29__p3-5__tonemapping
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-29__p3-5__tonemapping
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v3.md

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
- Core acquisition: `core = clip.std.core` exactly (AttributeError propagates)
- Import `detect_plugins` from `frame_compare.vs.env`
- Import `TonemapError` from `frame_compare.errors`
- Import `_detect_hdr` from `source.py` if extracting hdr_metadata from frame 0
- `_TONEMAP_PRESETS` and `_TONE_CURVE_MAP` are private (underscore prefix)
- Exact std.Expr for fallback: `f"x {peak} / dup 1 + / {target_nits} {peak} / * 0 max 1 min"`
- Exact std.Expr for contrast_recovery: `f"x 0.5 - {1 + contrast_recovery} * 0.5 + 0 max 1 min"`
- If behavior unclear, STOP and return to Planning

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p3-5__tonemapping

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v3.md
