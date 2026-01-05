---
RUN_ID: 2025-12-29__p3-5__tonemapping
VERSION: v5
TARGET: Phase 3 → Item 3.5 Tonemapping
INPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v4.md
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v5.md
---

# Implementation Plan: HDR Tonemapping

## Changes Since plan-v4

- **Tests now fully specified:** Each test has explicit assertions per plan-review-v4 feedback
- No SSOT changes (feedback was plan-only)

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

## Internal Functions (not exported, implementation details)

The following internal functions are implementation details specified in SSOT Section 5.2 and 5.3:

- `_apply_libplacebo` — libplacebo tonemapping path
- `_fallback_tonemap` — Reinhard fallback path
- `_to_rgbs` — shared RGBS conversion helper
- `_apply_post_processing` — shared post-processing helper
- `_TONEMAP_PRESETS` — private preset dictionary
- `_TONE_CURVE_MAP` — private curve mapping

## Determinism (Required)

- All preset settings are static and deterministic
- Tonemapping output is deterministic given the same input clip and settings
- No random seeds or sampling involved
- Both libplacebo and fallback paths use identical RGBS conversion and post-processing

## Files to Create/Modify (Complete List)

### 1. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` (MODIFY)

**Purpose:** SSOT updates for this run (completed in prior versions)

**Sections modified:**

- Section 3.3: Core acquisition expression
- Section 5.2: RGBS conversion rule, contrast_recovery expression, std.Expr shape
- Section 5.3: References to Section 5.2 rules

### 2. `src/frame_compare/vs/tonemap.py` (NEW)

**Purpose:** HDR to SDR tonemapping via libplacebo with Reinhard fallback

**Private constants:**

- `_TONEMAP_PRESETS: dict[str, TonemapSettings]` — 7 presets per Section 4
- `_TONE_CURVE_MAP: dict[str, int]` — `{"bt2390": 2, "spline": 1, "reinhard": 4}`

**Shared helpers (per SSOT unified rules):**

- `_to_rgbs(clip: vs.VideoNode) -> vs.VideoNode`:
  - Exact: `if clip.format.id != vs.RGBS: clip = clip.resize.Bicubic(format=vs.RGBS, matrix_in_s="709")`
  - Already RGBS: no-op
  - Failure: wrap in `TonemapError(FC-4003)`

- `_apply_post_processing(clip: vs.VideoNode, settings: TonemapSettings) -> vs.VideoNode`:
  - If `contrast_recovery > 0.0`: `expr = f"x 0.5 - {1 + contrast_recovery} * 0.5 + 0 max 1 min"`, apply `clip.std.Expr(expr=[expr, expr, expr])`
  - If `gamma_lift == True`: apply `clip.std.Levels(gamma=0.9)`

**Functions to implement (anchored to SSOT Section 3.3, 5.2, 5.3):**

- `apply_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
  - If `settings.enabled == False`: return `clip` unchanged
  - Core: `core = clip.std.core` (AttributeError propagates)
  - libplacebo check: `detect_plugins(core)["libplacebo"]`
  - If available: call `_apply_libplacebo()`
  - If unavailable: call `_fallback_tonemap()` silently
  - Wrap exceptions in `TonemapError(FC-4003)`

- `get_preset_settings(preset: str) -> TonemapSettings`
  - Look up in `_TONEMAP_PRESETS`
  - Raise `TonemapError(FC-4003)` with hint if not found

**Internal: `_apply_libplacebo` (libplacebo path):**

- Call `_to_rgbs(clip)` (shared helper)
- Check `settings.tone_curve` in `_TONE_CURVE_MAP`; if not, raise `TonemapError(FC-4003)`
- Call `core.placebo.Tonemap(src_max=..., dst_max=settings.target_nits, tone_mapping_function=...)`
- Call `_apply_post_processing(clip, settings)` (shared helper)

**Internal: `_fallback_tonemap` (Reinhard fallback):**

- Call `_to_rgbs(clip)` (same shared helper)
- Reinhard: `expr = f"x {peak} / dup 1 + / {target_nits} {peak} / * 0 max 1 min"`, apply `clip.std.Expr(expr=[expr, expr, expr])`
- Call `_apply_post_processing(clip, settings)` (same shared helper)

### 3. `src/frame_compare/vs/__init__.py` (MODIFY)

**Changes:**

- Add import: `from frame_compare.vs.tonemap import apply_tonemap, get_preset_settings`
- Add to `__all__`: `"apply_tonemap"`, `"get_preset_settings"`

### 4. `tests/vs/test_tonemap.py` (NEW)

**Tests with explicit assertions:**

- `test_get_preset_settings_returns_valid_settings`
  - Assert `get_preset_settings("reference")` returns `TonemapSettings`
  - Assert `result.preset == "reference"`
  - Assert `result.tone_curve == "bt2390"`
  - Assert `result.target_nits == 203`

- `test_get_preset_settings_all_presets_exist` (parametrized over 7 presets)
  - Assert `get_preset_settings(preset_name)` returns `TonemapSettings`
  - Assert `result.enabled == True`

- `test_get_preset_settings_unknown_raises_tonemap_error`
  - Assert `pytest.raises(TonemapError)` with `get_preset_settings("invalid")`
  - Assert `exc.code == "FC-4003"`
  - Assert hint contains valid preset names

- `test_apply_tonemap_enabled_false_returns_clip_unchanged`
  - Create mock clip, settings with `enabled=False`
  - Assert returned clip `is` same object as input (identity check)

- `test_apply_tonemap_uses_libplacebo_when_available`
  - Mock `detect_plugins` to return `{"libplacebo": True}`
  - Mock `_apply_libplacebo`
  - Assert `_apply_libplacebo` called once with `(clip, settings, core)` where `core == clip.std.core`
  - Assert `_fallback_tonemap` not called

- `test_apply_tonemap_uses_fallback_when_libplacebo_missing`
  - Mock `detect_plugins` to return `{"libplacebo": False}`
  - Mock `_fallback_tonemap`
  - Assert `_fallback_tonemap` called once with `(clip, settings, hdr_metadata)`
  - Assert `_apply_libplacebo` not called

- `test_apply_tonemap_unsupported_tone_curve_raises_error`
  - Set `settings.tone_curve = "invalid"`
  - Assert `pytest.raises(TonemapError)` with `apply_tonemap(...)`
  - Assert `exc.code == "FC-4003"`
  - Assert hint contains `"bt2390, spline, reinhard"`

- `test_apply_tonemap_wraps_exception_in_tonemap_error`
  - Mock libplacebo path to raise `RuntimeError("test")`
  - Assert `pytest.raises(TonemapError)`
  - Assert `exc.code == "FC-4003"`
  - Assert original exception is chained via `exc.__cause__`

- `test_tonemap_presets_have_correct_values` (parametrized per SSOT Section 4)
  - For each preset, assert `tone_curve` matches table
  - For each preset, assert `target_nits` matches table
  - Assert `bright_lift` preset has `gamma_lift == True`
  - Assert other presets have `gamma_lift == False`

- `test_to_rgbs_no_op_when_already_rgbs`
  - Create mock clip with `clip.format.id == vs.RGBS`
  - Assert returned clip `is` same object as input
  - Assert `clip.resize.Bicubic` not called

- `test_to_rgbs_converts_non_rgbs`
  - Create mock clip with `clip.format.id != vs.RGBS`
  - Assert `clip.resize.Bicubic` called once
  - Assert call includes `format=vs.RGBS, matrix_in_s="709"`
  - Assert returned clip is the result of `resize.Bicubic`

### 5. `docs/DECISIONS.md` (MODIFY)

**Required facts:** RUN_ID, scope, SSOT edits (RGBS conversion, contrast_recovery unification)

### 6. `CHANGELOG.md` (MODIFY)

**Entry:** Add HDR tonemapping with 7 presets, libplacebo with Reinhard fallback

## Acceptance Criteria

- [ ] GIVEN `settings.enabled == False` WHEN `apply_tonemap()` THEN return clip unchanged
- [ ] GIVEN "reference" preset WHEN `get_preset_settings()` THEN return correct settings
- [ ] GIVEN libplacebo available WHEN `apply_tonemap()` THEN use libplacebo path
- [ ] GIVEN libplacebo unavailable WHEN `apply_tonemap()` THEN use fallback silently
- [ ] GIVEN unknown preset WHEN `get_preset_settings()` THEN raise `TonemapError(FC-4003)`
- [ ] GIVEN unsupported tone_curve WHEN `apply_tonemap()` THEN raise `TonemapError(FC-4003)`
- [ ] GIVEN clip already RGBS WHEN `_to_rgbs()` THEN return unchanged (no-op)
- [ ] GIVEN all tests pass WHEN verification commands run THEN all exit 0

## Verification Commands

```bash
# Validate run artifacts
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-29__p3-5__tonemapping
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-29__p3-5__tonemapping
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md

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

- Core: `core = clip.std.core` exactly
- RGBS check: `if clip.format.id != vs.RGBS:` then convert
- RGBS conversion: `clip.resize.Bicubic(format=vs.RGBS, matrix_in_s="709")`
- Contrast recovery expr: `f"x 0.5 - {1 + contrast_recovery} * 0.5 + 0 max 1 min"`
- Reinhard expr: `f"x {peak} / dup 1 + / {target_nits} {peak} / * 0 max 1 min"`
- Both use `clip.std.Expr(expr=[expr, expr, expr])` for RGB planes
- Extract shared logic into `_to_rgbs()` and `_apply_post_processing()` helpers
- Exception chaining: use `raise TonemapError(...) from exc`
- If behavior unclear, STOP and return to Planning

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-29__p3-5__tonemapping

## Plan to Review

Read file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-v5.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-29__p3-5__tonemapping/plan-review-v5.md
