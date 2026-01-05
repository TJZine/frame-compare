# CLI Flags — Single Source of Truth

> **Module:** Reference
> **Purpose:** Canonical CLI flag definitions to sync docs/specs/tests

> [!NOTE]
> This file is AUTO-GENERATED from `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml`.
> Do not edit manually. Regenerate with: `python scripts/generate_contract_views.py`

---

## Canonical Flag Table

| ID | Long | Short | Type | Default | Config Key | Help |
|:---|:-----|:------|:-----|:--------|:-----------|:-----|
| FLAG_ROOT | --root | -r | Path | . | - | Workspace root directory |
| FLAG_CONFIG | --config | -c | Path | None | - | Config file path |
| FLAG_INPUT | --input | -i | Path | None | paths.input_dir | Input directory override |
| FLAG_TM_PRESET | --tm-preset | -p | str | None | color.preset | Tonemap preset (defers to config) |
| FLAG_TM_TARGET | --tm-target | -t | int | None | color.target_nits | Target peak luminance (defers to config) |
| FLAG_TM_CURVE | --tm-curve | - | str | None | color.tone_curve | Tone curve override |
| FLAG_FRAME_COUNT | --frame-count | -n | int | None | analysis.frame_count | Frames to capture (defers to config) |
| FLAG_SEED | --seed | -s | int | None | analysis.random_seed | Random seed |
| FLAG_SKIP_ANALYSIS | --skip-analysis | - | bool | False | - | Skip frame analysis; use uniform frame sampling with seed |
| FLAG_OVERLAY | --overlay | - | str | None | screenshots.overlay_mode | Overlay mode (defers to config) |
| FLAG_NO_UPLOAD | --no-upload | - | bool | False | slowpics.auto_upload | Skip slow.pics upload |
| FLAG_NO_CACHE | --no-cache | - | bool | False | - | Ignore cached metrics |
| FLAG_FROM_CACHE_ONLY | --from-cache-only | - | bool | False | - | Use only cached snapshot |
| FLAG_WRITE_CONFIG | --write-config | - | bool | False | - | Write resolved config and exit |
| FLAG_DIAGNOSE_PATHS | --diagnose-paths | - | bool | False | - | Print path diagnostics as JSON |
| FLAG_QUIET | --quiet | -q | bool | False | - | Suppress output |
| FLAG_VERBOSE | --verbose | -v | bool | False | - | Debug output |
| FLAG_JSON | --json | - | bool | False | - | JSON output mode |
| FLAG_NO_COLOR | --no-color | - | bool | False | - | Disable colors |
| FLAG_SKIP_METADATA | --skip-metadata | - | bool | False | - | Skip TMDB metadata lookup |
| FLAG_SKIP_DOVI | --skip-dovi | - | bool | False | - | Skip Dolby Vision extraction |

---

*Generated from version 2.0*
