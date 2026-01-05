---
RUN_ID: 2026-01-04__p6-5__tonemap-wiring
VERSION: v3
TARGET: Phase 6 → Item 6.5 (Tonemap Wiring)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v2.md
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
---

# Implementation Plan: Tonemap Wiring Integration

## Changes Since plan-v2

- Updated SSOT `render-module.md` “1.4.1 Gating Rule (Deterministic)” to fully specify `probe_is_hdr_ffprobe(...)` parsing rules, failure behavior, and how probe failures affect FFmpeg fallback decisions when `config.color.enable_tonemap` is True.
- Updated plan test coverage to include explicit helper tests (`should_tonemap`, `resolve_tonemap_settings`) and at least one probe-failure case that asserts deterministic non-fallback behavior.
- Clarified deterministic `ConfigSchema` construction for updated orchestrator call sites (avoid env/config-file dependence).

## Context

**Phase:** 6
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`
**Dependencies:**
- `frame_compare.vs.tonemap.apply_tonemap` exists
- `frame_compare.vs.tonemap.get_preset_settings` exists
- `frame_compare.config.schema.ColorConfig` exists with `enable_tonemap` field

## Scope

This plan covers:

- [ ] Integrate tonemap gating into `render_screenshots(...)` using `config.color.enable_tonemap` and HDR detection.
- [ ] Add deterministic non-VS HDR probe for gating FFmpeg usage when VS is missing/not used.
- [ ] Apply tonemap after VS load and before any frame extraction.
- [ ] Implement fail-fast behavior for HDR + tonemap-required when VS is missing using `VapourSynthNotFoundError (FC-2001)`.
- [ ] Add tests for helper truth tables and probe-failure determinism (no real VS/FFmpeg required by default).

This plan does NOT cover:

- CLI flag overrides (`--tm-preset`, `--tm-target`, `--tm-curve`) — Phase 6.7+
- VSPreview integration (Phase 6.6)
- FramePlan integration (Phase 6.4)

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md`:
  - Section: "1.4 HDR Tonemap Wiring (Auto-Tonemap for HDR → SDR)"
  - Section: "1.4.1 Gating Rule (Deterministic)"
  - Section: "1.4.2 Settings Resolution"
  - Section: "1.4.3 Integration Point"
  - Section: "1.4.4 Failure Policy"
  - Section: "1.4.6 Overlay/HDR Info Policy"
  - Section: "3.1 Frame Rendering"
  - Section: "7.2 Integration Tests"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "3.3 Tonemapping"
  - Section: "4. Tonemap Presets"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"
  - Section: "2.2 Integration Tests"

## Files to Create/Modify

### 1. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` (MODIFY)

**Purpose:** SSOT corrections required by Plan Review to remove contract conflicts and define deterministic gating when VS is unavailable.

**SSOT edits (headings; copy/paste exact):**
- "1.4.1 Gating Rule (Deterministic)" (adds parsing rules + failure behavior for `probe_is_hdr_ffprobe(path: Path) -> bool`)
- "1.4.4 Failure Policy" (VS-missing tonemap-required uses `VapourSynthNotFoundError (FC-2001)`)
- "3.1 Frame Rendering" (updated `render_screenshots(...)` signature + loading strategy notes)
- "7.2 Integration Tests" (updated markers and expected exceptions for VS-missing tonemap-required cases)

### 2. `src/frame_compare/render/orchestrator.py` (MODIFY)

**Purpose:** Integrate tonemap gating + deterministic fallback policy into the render pipeline.

**Public API signature (required; spec-anchored):**
- `render_screenshots(clips: list[Path], frames: list[int], output_dir: Path, config: ConfigSchema, label_map: dict[Path, str] | None = None, renderer: Renderer = "auto", overlay_mode: OverlayMode = OverlayMode.STANDARD, reporter: ProgressReporter | None = None) -> dict[str, list[Path]]`

**Functions to implement (spec-anchored):**
- `should_tonemap(source_info: SourceInfo, config: ConfigSchema) -> bool`
- `resolve_tonemap_settings(config: ConfigSchema, cli_overrides: dict | None = None) -> TonemapSettings`
- `probe_is_hdr_ffprobe(path: Path) -> bool`

**Behavior changes (spec-anchored):**
- Apply tonemap at the `§1.4.3 Integration Point` (after VS load, before frame extraction) using `apply_tonemap(...)`.
- When VS load fails:
  - For `renderer="auto"` and `config.color.enable_tonemap=True`, call `probe_is_hdr_ffprobe(path)`:
    - If it returns `True`: re-raise the original VS failure (no FFmpeg fallback).
    - If it returns `False`: fallback to FFmpeg Path-based rendering.
    - If it raises: propagate the probe exception (no fallback).
  - For `renderer="ffmpeg"` and `config.color.enable_tonemap=True`, call `probe_is_hdr_ffprobe(path)`:
    - If it returns `True`: raise `VapourSynthNotFoundError (FC-2001)` (tonemap required; no FFmpeg path).
    - If it returns `False`: proceed with FFmpeg rendering.
    - If it raises: propagate the probe exception (no FFmpeg path).
- Overlay HDR info string formatting follows `§1.4.6 Overlay/HDR Info Policy`.

### 3. `src/frame_compare/render/__init__.py` (MODIFY)

**Purpose:** Export tonemap helper functions as part of the render module API.

**Add exports:**
- `should_tonemap`
- `resolve_tonemap_settings`

### 4. `tests/render/test_orchestrator.py` (MODIFY)

**Purpose:** Update in-repo callers for the `render_screenshots(...)` signature change.

**Required changes:**
- Update all calls to `render_screenshots(...)` to pass `config: ConfigSchema`.

**Deterministic config construction (required):**
- Construct config explicitly in tests (no env/config-file dependence), e.g.:
  - `ConfigSchema(color=ColorConfig(enable_tonemap=False))` for FFmpeg-only tests
  - `ConfigSchema(color=ColorConfig(enable_tonemap=True))` for tonemap-enabled gating tests

### 5. `tests/integration/test_render_orchestrator.py` (MODIFY)

**Purpose:** Update in-repo callers for the `render_screenshots(...)` signature change.

**Required changes:**
- Update the call to `render_screenshots(...)` to pass `config: ConfigSchema`.

### 6. `tests/render/test_tonemap_wiring.py` (NEW)

**Purpose:** Integration tests for tonemap gating scenarios (mocked module boundaries; no real VS/FFmpeg required by default), plus helper-function coverage required by plan-review-v2.

**Tests required (spec-anchored names):**
- `test_hdr_enable_tonemap_requires_vs_when_renderer_auto` — marker `@pytest.mark.integration`
- `test_hdr_enable_tonemap_requires_vs_when_renderer_ffmpeg` — marker `@pytest.mark.integration`
- `test_hdr_disable_tonemap_allows_ffmpeg_when_vs_missing` — marker `@pytest.mark.integration`
- `test_sdr_allows_ffmpeg_fallback_when_vs_missing` — marker `@pytest.mark.integration`

**Additional required tests (plan-review-v2; deterministic, pure-Python):**
- `test_should_tonemap_truth_table`
  - Asserts: (`is_hdr`, `enable_tonemap`) → expected bool for all 4 combinations.
- `test_resolve_tonemap_settings_applies_config_overrides`
  - Asserts: returned `TonemapSettings` reflects `config.color.preset`, `config.color.target_nits`, `config.color.tone_curve` (and that CLI overrides remain out-of-scope/None in this slice).
- `test_probe_failure_disallows_fallback_when_tonemap_enabled`
  - Scenario: VS load fails, `config.color.enable_tonemap=True`, `renderer="auto"`.
  - Setup: patch `probe_is_hdr_ffprobe` to raise `SourceLoadError (FC-4015)` (or `FFmpegNotFoundError (FC-2005)`).
  - Assert: `render_screenshots(...)` propagates the probe exception (no FFmpeg fallback).

**Boundary mocking requirements (to keep tests deterministic/offline):**
- Force “VS missing” by patching `DefaultVSLoader.load` to raise `VapourSynthNotFoundError()`.
- Control HDR vs SDR by patching `probe_is_hdr_ffprobe` to return `True`/`False`.
- Ensure no real `ffprobe` / `ffmpeg` subprocess is invoked in these tests by mocking the render dispatch boundary (`render_frame` or `render_batch`) as needed.

### 7. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry (repo persistence).

**Required facts to record (bullets; do not prewrite exact prose):**
- RUN_ID + artifact versions (plan/plan-review/impl/verify/review)
- SSOT edits made this run (spec file path + exact headings changed)
- Contract alignment decision: VS-missing tonemap-required uses `VapourSynthNotFoundError (FC-2001)` (no FC-4004 customization)
- Probe determinism decision: probe failures disallow fallback when `enable_tonemap=True`
- Out-of-scope items
- Verification gates run + pass/fail

### 8. `CHANGELOG.md` (MODIFY)

**Purpose:** Add a short entry for user-visible changes.

**Entry:** Add HDR tonemap gating and deterministic FFmpeg fallback rules in render pipeline.

## Acceptance Criteria

- [ ] GIVEN HDR source AND `config.color.enable_tonemap=True` WHEN `should_tonemap(...)` is called THEN returns `True`
- [ ] GIVEN SDR source WHEN `should_tonemap(...)` is called THEN returns `False`
- [ ] GIVEN HDR source AND `config.color.enable_tonemap=False` WHEN `should_tonemap(...)` is called THEN returns `False`
- [ ] GIVEN HDR source + enable_tonemap=True + VS missing + renderer="auto" WHEN `render_screenshots(...)` is called THEN raises `VapourSynthNotFoundError (FC-2001)` (or propagates probe failure when probe cannot run)
- [ ] GIVEN HDR source + enable_tonemap=True + VS missing + renderer="ffmpeg" WHEN `render_screenshots(...)` is called THEN raises `VapourSynthNotFoundError (FC-2001)` (or propagates probe failure when probe cannot run)
- [ ] GIVEN HDR source + enable_tonemap=False + VS missing WHEN `render_screenshots(...)` is called THEN renders via FFmpeg path without raising
- [ ] GIVEN SDR source + VS missing WHEN `render_screenshots(...)` is called THEN renders via FFmpeg path without raising
- [ ] GIVEN probe failure AND `enable_tonemap=True` WHEN VS is missing/not used THEN `render_screenshots(...)` does not fall back to FFmpeg and propagates the probe exception
- [ ] GIVEN HDR source + tonemapped WHEN overlay is rendered THEN `hdr_info` contains `HDR (tonemapped: {preset}, {target_nits} nits)`
- [ ] GIVEN HDR source + tonemap disabled WHEN overlay is rendered THEN `hdr_info` contains `HDR (native, no tonemap)`

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → Command Canon.

```bash
# 1. Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md

# 2. Quality gates
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q

# 3. Import-linter (layer contracts)
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Do not create new error codes/classes in this slice; VS-missing tonemap-required must use `VapourSynthNotFoundError (FC-2001)` per SSOT.
- Implement `probe_is_hdr_ffprobe(...)` exactly per SSOT parsing rules and failure behavior; do not introduce heuristics.
- Keep tests pure-Python by mocking `DefaultVSLoader.load`, `probe_is_hdr_ffprobe`, and the render dispatch boundary; do not require real VS/FFmpeg by default.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-5__tonemap-wiring

## Plan to Review
Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v3.md
