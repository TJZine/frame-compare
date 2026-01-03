# Requirements Traceability Matrix

> **Module:** Reference
> **Purpose:** Link v0.0.14 features to module specs and validation tests
> **Last Updated:** 2026-01-03

---

## 1. Core Features → Module Specs → Tests

| Feature ID | v0.0.14 Feature | Module Spec | Section | Validation Test(s) | Status |
|:-----------|:----------------|:------------|:--------|:-------------------|:-------|
| F-001 | Video Loading (lsmas) | vs-module.md | §3.2 load_source | `tests/vs/test_loader.py` | ✅ Implemented |
| F-002 | HDR Detection | vs-module.md | §5.1 _detect_hdr | `tests/vs/test_props.py` | ✅ Implemented |
| F-003 | PQ Tonemapping | vs-module.md | §3.3 apply_tonemap | `tests/vs/test_tonemap.py` | ✅ Implemented |
| F-004 | HLG Tonemapping | vs-module.md | §3.3 apply_tonemap | `tests/vs/test_tonemap.py` | ✅ Implemented |
| F-005 | Frame Selection | analysis-module.md | §3.2 select_frames | `tests/analysis/test_selection.py` | ✅ Implemented |
| F-006 | Screenshot Render | render-module.md | §3.1 render_batch | `tests/render/test_orchestrator.py` | ✅ Implemented |
| F-007 | Audio Alignment | services-module.md | §2.2 align_clips | `tests/services/test_alignment.py` | ✅ Implemented |
| F-008 | slow.pics Upload | services-module.md | §4.2 publish_to_slowpics | `tests/services/test_publishers.py` | ✅ Implemented |
| F-009 | TMDB Metadata | services-module.md | §3.2 lookup_tmdb | `tests/services/test_metadata.py` | ✅ Implemented |
| F-010 | HTML Report | services-module.md | §6.2 generate_report | `tests/services/test_report.py` | ✅ Implemented |
| F-011 | Caching | analysis-module.md | §5 Cache Strategy | `tests/analysis/test_cache_io.py` | ✅ Implemented |
| F-012 | CLI Interface | cli-module.md | §2.1 run command | `tests/cli/test_cli_commands.py` | ⚠️ Partial (stubs) |
| F-013 | Config Loading | config-module.md | §3 load_config | `tests/config/test_loader.py` | ✅ Implemented |
| F-014 | Deterministic Frame Selection (skip-analysis) | frame-plan-module.md | §4 Algorithm | PLANNED: `tests/analysis/test_frame_plan.py` | ⏳ Spec Complete |
| F-015 | Manual Alignment Override (VSPreview) | vspreview-module.md | §4 Public API | PLANNED: `tests/vspreview/test_overrides.py` | ⏳ Spec Complete |
| F-016 | HDR Tonemap Wiring | render-module.md | §1.4 HDR Tonemap Integration | PLANNED: `tests/render/test_tonemap_wiring.py` | ⏳ Spec Complete |

---

## 2. CLI Commands → Module Specs → Tests

| Command | Module Spec | Section | Validation Test(s) | Status |
|:--------|:------------|:--------|:-------------------|:-------|
| `run` | cli-module.md | §2.1 run command | `tests/cli/test_cli_commands.py::test_run_stub_executes` | ⚠️ Stub only |
| `wizard` | cli-module.md | §2.1 wizard | `tests/cli/test_cli_commands.py::test_wizard_stub` | ⚠️ Stub only |
| `doctor` | cli-module.md | §2.1 doctor | `tests/cli/test_cli_commands.py::test_doctor_stub_text` | ⚠️ Stub only |
| `preset list` | cli-module.md | §2.1 preset | `tests/cli/test_cli_commands.py::test_preset_list_stub` | ⚠️ Stub only |
| `preset apply` | cli-module.md | §2.1 preset | `tests/cli/test_cli_commands.py::test_preset_apply_stub` | ⚠️ Stub only |
| `preset save` | cli-module.md | §2.1 preset | `tests/cli/test_cli_commands.py::test_preset_save_stub` | ⚠️ Stub only |

---

## 3. CLI Flags → Config Keys → Tests

| Flag | Config Key | Module Spec | Test | Status |
|:-----|:-----------|:------------|:-----|:-------|
| `--tm-preset` | color.preset | config-module.md §4 | PLANNED: `tests/config/test_overrides.py::test_apply_cli_overrides_sets_tm_preset` | ⏳ Pending |
| `--tm-target` | color.target_nits | config-module.md §4 | PLANNED: `tests/config/test_overrides.py::test_apply_cli_overrides_sets_tm_target_nits` | ⏳ Pending |
| `--tm-curve` | color.tone_curve | config-module.md §4 | PLANNED: `tests/config/test_overrides.py::test_apply_cli_overrides_sets_tm_curve` | ⏳ Pending |
| `--frame-count` | analysis.frame_count | config-module.md §4 | `tests/config/test_overrides.py::test_apply_cli_overrides_basic` | ✅ Implemented |
| `--seed` | analysis.random_seed | config-module.md §4 | PLANNED: `tests/config/test_overrides.py::test_apply_cli_overrides_sets_random_seed` | ⏳ Pending |
| `--no-upload` | slowpics.auto_upload | config-module.md §4 | `tests/config/test_overrides.py::test_apply_cli_overrides_inverts_no_upload` | ✅ Implemented |
| `--overlay` | screenshots.overlay_mode | config-module.md §4 | PLANNED: `tests/config/test_overrides.py::test_apply_cli_overrides_sets_overlay_mode` | ⏳ Pending |
| `--quiet` | (RunRequest) | cli-module.md | PLANNED: `tests/cli/test_cli_commands.py::test_run_quiet_sets_mode` | ⏳ Pending |
| `--verbose` | (RunRequest) | cli-module.md | PLANNED: `tests/cli/test_cli_commands.py::test_run_verbose_sets_mode` | ⏳ Pending |
| `--json` | (RunRequest) | cli-module.md | PLANNED: `tests/cli/test_cli_commands.py::test_run_json_sets_mode` | ⏳ Pending |

---

## 4. Verification Scenarios → E2E Tests

> [!IMPORTANT]
> These E2E tests are **PLANNED** but not yet implemented.
> They require the orchestration layer (Phase 6) to be complete.

| Scenario | Status | Target File | Pytest Marker | Validates |
|:---------|:-------|:------------|:--------------|:----------|
| CLI version command | ✅ Implemented | `tests/e2e/test_cli_version.py` | `@pytest.mark.e2e` | F-012 |
| Load HDR video | PLANNED | `tests/e2e/test_load_hdr.py` | `@pytest.mark.e2e` | F-001, F-002 |
| Tonemap all presets | PLANNED | `tests/e2e/test_tonemap_presets.py` | `@pytest.mark.e2e`, `@pytest.mark.vs_required` | F-003, F-004 |
| Select frames (all modes) | PLANNED | `tests/e2e/test_selection.py` | `@pytest.mark.e2e` | F-005 |
| Render with overlay | PLANNED | `tests/e2e/test_render_overlay.py` | `@pytest.mark.e2e`, `@pytest.mark.vs_required` | F-006 |
| Upload to slow.pics | PLANNED | `tests/e2e/test_publish.py` | `@pytest.mark.e2e`, `@pytest.mark.network` | F-008 |
| Generate report | PLANNED | `tests/e2e/test_report.py` | `@pytest.mark.e2e` | F-010 |
| Full pipeline | PLANNED | `tests/e2e/test_golden_pipeline.py` | `@pytest.mark.e2e`, `@pytest.mark.slow` | ALL |

**E2E Test Marker Policy:**

- `@pytest.mark.e2e` — All end-to-end tests
- `@pytest.mark.vs_required` — Requires VapourSynth + plugins
- `@pytest.mark.network` — Requires network access
- `@pytest.mark.slow` — Takes > 30 seconds

**Test Infrastructure Required:**

1. Orchestration package must be implemented (Phase 6)
2. Sample videos must be available in `tests/fixtures/`
3. Docker environment recommended for VS-required tests

---

## 5. Missing Features (Parity Gaps)

Cross-reference with [feature-parity-delta.md](../05-implementation/feature-parity-delta.md) for full details.

| Gap ID | Feature | Blocking Runner? | SSOT Anchor |
|:-------|:--------|:-----------------|:------------|
| GAP-001 | Auto-Tonemap Wiring | Yes | render-module.md §1.4 |
| GAP-002 | Runner/Orchestration | Yes | orchestration-module.md §4.3 |
| GAP-003 | VSPreview Integration | No | vspreview-module.md |
| GAP-004 | FramePlan Skip-Analysis | Yes | frame-plan-module.md |
| GAP-005 | E2E Test Coverage | No | This document §4 |
