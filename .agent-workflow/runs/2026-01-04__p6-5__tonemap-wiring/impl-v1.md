# Implementation Report: Phase 6.5 Tonemap Wiring

**RUN_ID:** `2026-01-04__p6-5__tonemap-wiring`
**Date:** 2026-01-04

## Summary

Implemented tonemap wiring logic in the render module per plan-v3.md.

## Changes Made

### Core Implementation

#### [MODIFY] orchestrator.py

- Added `config: ConfigSchema` parameter to `render_screenshots()`
- Implemented three helper functions:
  - `should_tonemap(source_info, config)` — gating logic (HDR + enable_tonemap)
  - `resolve_tonemap_settings(config, cli_overrides)` — settings resolution with preset/config/CLI priority
  - `probe_is_hdr_ffprobe(path)` — HDR detection via ffprobe for VS-unavailable fallback
- Integrated tonemap gating with deterministic fallback policy:
  - HDR + enable_tonemap=True + VS_missing → fail-fast (FC-2001)
  - SDR or enable_tonemap=False → FFmpeg fallback allowed

#### [MODIFY] **init**.py

- Added exports: `should_tonemap`, `resolve_tonemap_settings`, `probe_is_hdr_ffprobe`

---

### Test Updates

#### [MODIFY] test_orchestrator.py

- Added `default_config` fixture with `enable_tonemap=False`
- Updated all `render_screenshots` calls to pass config parameter
- Added `is_hdr=False` to mock sources for isolated tests

#### [MODIFY] test_render_orchestrator.py

- Added `integration_config` fixture
- Updated test to pass config parameter

#### [NEW] test_tonemap_wiring.py

7 new tests:

- `test_should_tonemap_truth_table` — 4 cases for (is_hdr, enable_tonemap)
- `test_resolve_tonemap_settings_applies_config_overrides`
- `test_probe_failure_disallows_fallback_when_tonemap_enabled`
- `test_hdr_enable_tonemap_requires_vs_when_renderer_auto`
- `test_hdr_enable_tonemap_requires_vs_when_renderer_ffmpeg`
- `test_hdr_disable_tonemap_allows_ffmpeg_when_vs_missing`
- `test_sdr_allows_ffmpeg_fallback_when_vs_missing`

---

### Documentation

#### [MODIFY] DECISIONS.md

- Added Phase 6.5 decision entry

#### [MODIFY] CHANGELOG.md

- Added tonemap wiring changelog entry

---

## Verification Gates

| Gate | Result |
|------|--------|
| pyright --warnings | ✅ 0 errors |
| ruff check | ✅ All checks passed |
| pytest (unit) | ✅ 269 passed, 1 skipped |
| pytest (render) | ✅ 21 passed |
| lint-imports | ✅ 2 contracts kept |

---

## NEXT AGENT PROMPT

```
You are the Verification Agent for RUN_ID 2026-01-04__p6-5__tonemap-wiring.

Read:
1. .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/plan-v3.md
2. .agent-workflow/runs/2026-01-04__p6-5__tonemap-wiring/impl-v1.md

Verify:
1. All files listed match the plan
2. Run spec anchor validation
3. Run quality gates (pyright, ruff, pytest, lint-imports)
4. Verify contract freshness

Output: verify-v1.md with pass/fail summary and handoff block.
```
