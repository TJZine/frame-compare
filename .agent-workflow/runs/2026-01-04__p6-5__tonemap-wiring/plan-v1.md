---
RUN_ID: 2026-01-04__p6-5__tonemap-wiring
VERSION: v1
TARGET: Phase 6 → Item 6.5 (Tonemap Wiring)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v1.md
---

# Implementation Plan: Tonemap Wiring Integration

## Context

**Phase:** 6
**Module:** `frame_compare.render`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` §1.4
**Dependencies:**

- `frame_compare.vs.tonemap.apply_tonemap` exists
- `frame_compare.vs.tonemap.get_preset_settings` exists
- `frame_compare.config.schema.ColorConfig` exists with `enable_tonemap` field

## Scope

This plan covers:

- [x] Update `render/orchestrator.py` to integrate tonemap gating
- [x] Implement `should_tonemap(source_info, config) -> bool` gating rule
- [x] Implement `resolve_tonemap_settings(config, cli_overrides=None) -> TonemapSettings`
- [x] Wire `config.color.enable_tonemap` to renderer
- [x] Add tonemap call after load, before frame extraction in `render_screenshots`
- [x] Implement fail-fast `RenderError(FC-4004)` for HDR + tonemap required + VS unavailable
- [x] Propagate `TonemapError` on `apply_tonemap()` failure
- [x] Update HDR info overlay formatting for tonemapped + native modes
- [x] Write 4 integration tests for tonemap gating scenarios

This plan does NOT cover:

- CLI flag overrides (`--tm-preset`, `--tm-target`, `--tm-curve`) — Phase 6.7+
- VSPreview integration (Phase 6.6)
- FramePlan integration (already complete in Phase 6.4)

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
  - Section: "7.2 Integration Tests"

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"
  - Section: "2.2 Integration Tests"

## Files to Create/Modify

### 1. `src/frame_compare/render/orchestrator.py` (MODIFY)

**Purpose:** Integrate tonemap gating into render pipeline.

**Functions to implement (spec-anchored):**

- `should_tonemap(source_info: SourceInfo, config: ConfigSchema) -> bool` — §1.4.1
- `resolve_tonemap_settings(config: ConfigSchema, cli_overrides: dict | None = None) -> TonemapSettings` — §1.4.2

**Functions to modify:**

- `render_screenshots()` — Update signature to accept `config: ConfigSchema`, integrate tonemap at §1.4.3 integration point

**Integration points:**

1. **After load, before frame extraction:**

   ```python
   # Load clip
   source_info = loader.load(clip_path)
   clip = source_info.clip

   # === TONEMAP INTEGRATION POINT ===
   if should_tonemap(source_info, config):
       settings = resolve_tonemap_settings(config)
       clip = apply_tonemap(clip, settings, source_info.hdr_metadata)
       tonemapped = True
   else:
       tonemapped = False

   # Continue with frame extraction
   ```

2. **Overlay HDR info:**
   Update `OverlayConfig.hdr_info` per §1.4.6:
   - HDR tonemapped: `f"HDR (tonemapped: {settings.preset}, {settings.target_nits} nits)"`
   - HDR native: `"HDR (native, no tonemap)"`
   - SDR: `None`

3. **Failure handling:**
   If `should_tonemap()` returns `True` but VapourSynth unavailable:

   ```python
   raise RenderError(
       code="FC-4004",
       message="Cannot tonemap HDR source: VapourSynth is required but not available",
       hint="Install VapourSynth with libplacebo, or set enable_tonemap=false to skip tonemapping (not recommended for accurate comparisons)",
   )
   ```

---

### 2. `src/frame_compare/render/__init__.py` (MODIFY)

**Purpose:** Export new helper functions.

**Add exports:**

- `should_tonemap`
- `resolve_tonemap_settings`

---

### 3. `tests/render/test_tonemap_wiring.py` (NEW)

**Purpose:** Integration tests for tonemap gating scenarios.

**Tests required:**

| Test Function | Marker | Description |
|---------------|--------|-------------|
| `test_hdr_enable_tonemap_requires_vs_when_renderer_auto` | `@pytest.mark.integration` | HDR source + enable_tonemap=True + renderer="auto" + VS missing → raises RenderError(FC-4004) |
| `test_hdr_enable_tonemap_requires_vs_when_renderer_ffmpeg` | `@pytest.mark.integration` | HDR source + enable_tonemap=True + renderer="ffmpeg" → raises RenderError(FC-4004) |
| `test_hdr_disable_tonemap_allows_ffmpeg_when_vs_missing` | `@pytest.mark.integration` | HDR source + enable_tonemap=False + VS missing → renders without tonemap (FFmpeg fallback) |
| `test_sdr_allows_ffmpeg_fallback_when_vs_missing` | `@pytest.mark.integration` | SDR source + VS missing + renderer="auto" → renders via FFmpeg (no tonemap needed) |

**Test approach:**

- Mock `DefaultVSLoader` to raise `VapourSynthNotFoundError` for VS-missing scenarios
- Mock `SourceInfo` to control `is_hdr` flag
- Mock `apply_tonemap` to verify it's called/not-called as expected
- Use `tmp_path` for output directories
- Assert on exception type and error code

---

### 4. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry.

**Required facts:**

- RUN_ID: `2026-01-04__p6-5__tonemap-wiring`
- Scope: Tonemap gating integration in render pipeline
- SSOT: No changes required (spec already complete)
- Out of scope: CLI flag overrides (`--tm-*`), VSPreview integration
- Verification gates: Pyright, Ruff, Pytest (including HDR gating tests)

---

### 5. `CHANGELOG.md` (MODIFY)

**Purpose:** Add entry for new feature.

**Entry:** Add automatic HDR tonemap wiring in render pipeline (enable_tonemap config)

## Acceptance Criteria

- [ ] GIVEN HDR source and `config.color.enable_tonemap=True` WHEN `should_tonemap()` is called THEN returns `True`
- [ ] GIVEN SDR source WHEN `should_tonemap()` is called THEN returns `False`
- [ ] GIVEN HDR source and `config.color.enable_tonemap=False` WHEN `should_tonemap()` is called THEN returns `False`
- [ ] GIVEN config with preset="contrast" and target_nits=250 WHEN `resolve_tonemap_settings()` is called THEN returns TonemapSettings with preset="contrast" and target_nits=250
- [ ] GIVEN HDR source + enable_tonemap=True + VS missing + renderer="auto" WHEN `render_screenshots()` is called THEN raises `RenderError(FC-4004)` with hint about installing VS
- [ ] GIVEN HDR source + enable_tonemap=True + VS missing + renderer="ffmpeg" WHEN `render_screenshots()` is called THEN raises `RenderError(FC-4004)`
- [ ] GIVEN HDR source + enable_tonemap=False + VS missing WHEN `render_screenshots()` is called THEN renders via FFmpeg fallback without exception
- [ ] GIVEN SDR source + VS missing WHEN `render_screenshots()` is called THEN renders via FFmpeg fallback without exception
- [ ] GIVEN HDR source + tonemapped WHEN overlay is rendered THEN `hdr_info` contains "HDR (tonemapped: {preset}, {nits} nits)"
- [ ] GIVEN HDR source + tonemap disabled WHEN overlay is rendered THEN `hdr_info` contains "HDR (native, no tonemap)"

## Verification Commands

```bash
# 1. Spec anchor validation
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v1.md

# 2. Quality gates
.venv/bin/pyright --warnings src/frame_compare/render/orchestrator.py
.venv/bin/ruff check src/frame_compare/render/orchestrator.py
.venv/bin/pytest -v tests/render/test_tonemap_wiring.py

# 3. Import-linter (layer contracts)
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# 4. Full test suite (catch regressions)
.venv/bin/pytest -q
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Signature update** — `render_screenshots()` must add `config: ConfigSchema` parameter after `output_dir`
2. **Import additions** — Add `from frame_compare.config.schema import ConfigSchema` and `from frame_compare.vs.types import TonemapSettings, HDRMetadata`
3. **Error import** — Add `from frame_compare.errors import RenderError, TonemapError`
4. **Gating order** — Check `should_tonemap()` BEFORE calling `apply_tonemap()` (fail-fast if VS missing)
5. **Overlay formatting** — Use exact format strings from spec §1.4.6 (preset + nits for tonemapped, "native" for disabled)
6. **Test mocking strategy** — Mock `DefaultVSLoader` at module level, not instance level; use `side_effect=VapourSynthNotFoundError()` for VS-missing scenarios
7. **Integration test marker** — Use `@pytest.mark.integration` for all 4 tests (not `@pytest.mark.vs_required` since they mock VS)
8. **CLI overrides** — Leave `cli_overrides` parameter as `None` default in `resolve_tonemap_settings()`; Phase 6.7+ will populate it

---

> **Proposed RUN_ID:** 2026-01-04__p6-5__tonemap-wiring
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2026-01-04__p6-5__tonemap-wiring` before running Plan Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-04__p6-5__tonemap-wiring

## Plan to Review

Read file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-review-v1.md
