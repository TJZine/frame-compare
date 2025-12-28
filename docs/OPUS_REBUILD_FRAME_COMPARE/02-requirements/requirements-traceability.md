# Requirements Traceability Matrix

> **Module:** Reference
> **Purpose:** Link v0.0.14 features to module specs and validation tests

---

## 1. Core Features → Module Specs → Tests

| Feature ID | v0.0.14 Feature | Module Spec | Section | Validation Test(s) |
|:-----------|:----------------|:------------|:--------|:-------------------|
| F-001 | Video Loading (lsmas) | vs-module.md | §3.2 load_source | test_load_mkv, test_load_mp4 |
| F-002 | HDR Detection | vs-module.md | §5.1 _detect_hdr | test_detect_pq, test_detect_hlg |
| F-003 | PQ Tonemapping | vs-module.md | §3.3 apply_tonemap | test_pq_tonemap_presets |
| F-004 | HLG Tonemapping | vs-module.md | §3.3 apply_tonemap | test_hlg_tonemap |
| F-005 | Frame Selection | analysis-module.md | §3.2 select_frames | test_selection_modes |
| F-006 | Screenshot Render | render-module.md | §3.1 render_batch | test_render_png |
| F-007 | Audio Alignment | services-module.md | §2.2 align_clips | test_cross_correlation |
| F-008 | slow.pics Upload | services-module.md | §4.2 publish_to_slowpics | test_slowpics_upload |
| F-009 | TMDB Metadata | services-module.md | §3.2 lookup_tmdb | test_tmdb_lookup |
| F-010 | HTML Report | services-module.md | §6.2 generate_report | test_report_html |
| F-011 | Caching | analysis-module.md | §5 Cache Strategy | test_cache_roundtrip |
| F-012 | CLI Interface | cli-module.md | §2.1 run command | test_cli_run |
| F-013 | Config Loading | config-module.md | §3 load_config | test_config_load |

---

## 2. CLI Commands → Module Specs → Tests

| Command | Module Spec | Section | Validation Test(s) |
|:--------|:------------|:--------|:-------------------|
| `run` | cli-module.md | §3.1 run_command | test_cli_run_basic, test_cli_run_with_flags |
| `wizard` | cli-module.md | §3.2 wizard | test_wizard_interactive |
| `doctor` | orchestration-module.md | §4.2 run_doctor | test_doctor_all_pass |
| `preset list` | cli-module.md | §3.3 preset | test_preset_list |
| `preset apply` | cli-module.md | §3.3 preset | test_preset_apply |
| `preset save` | cli-module.md | §3.3 preset | test_preset_save |

---

## 3. CLI Flags → Config Keys → Tests

| Flag | Config Key | Module Spec | Test |
|:-----|:-----------|:------------|:-----|
| `--tm-preset` | color.preset | config-module.md §4 | test_override_preset |
| `--tm-target` | color.target_nits | config-module.md §4 | test_override_target |
| `--tm-curve` | color.tone_curve | config-module.md §4 | test_override_curve |
| `--frame-count` | analysis.frame_count | config-module.md §4 | test_override_count |
| `--seed` | analysis.random_seed | config-module.md §4 | test_override_seed |
| `--no-upload` | slowpics.auto_upload | config-module.md §4 | test_no_upload |
| `--overlay` | screenshots.overlay_mode | config-module.md §4 | test_overlay_mode |
| `--quiet` | (RunRequest) | cli-module.md | test_quiet_mode |
| `--verbose` | (RunRequest) | cli-module.md | test_verbose_mode |
| `--json` | (RunRequest) | cli-module.md | test_json_output |

---

## 4. Verification Scenarios → E2E Tests

| Scenario | Test Name | Validates |
|:---------|:----------|:----------|
| Load HDR video | test_e2e_load_hdr | F-001, F-002 |
| Tonemap all presets | test_e2e_tonemap_presets | F-003, F-004 |
| Select frames (all modes) | test_e2e_selection | F-005 |
| Render with overlay | test_e2e_render_overlay | F-006 |
| Upload to slow.pics | test_e2e_publish | F-008 |
| Generate report | test_e2e_report | F-010 |
| Full pipeline | test_e2e_golden_pipeline | ALL |
