# Configuration Reference

> **Module:** Reference
> **Version:** 1.0

---

## Field Inventory

> [!NOTE]
> This section is synced from `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/config_schema.json`.
> Run `python scripts/generate_contract_views.py` to regenerate.

<!-- BEGIN GENERATED:config_inventory -->
| Section | Field | Type | Default |
|:--------|:------|:-----|:--------|
| paths | input_dir | string | "comparison_videos" |
| paths | screenshots_dir | string | "screenshots" |
| paths | generated_dir | string | "generated" |
| paths | config_dir | string | "config" |
| analysis | frame_count | integer | 10 |
| analysis | random_seed | integer | 42 |
| analysis | save_frames_data | boolean | true |
| analysis | selection_mode | string | "mixed" |
| analysis | dark_quantile | number | 0.05 |
| analysis | bright_quantile | number | 0.95 |
| audio_alignment | enable | boolean | true |
| audio_alignment | sample_rate | integer | 8000 |
| audio_alignment | max_offset_seconds | number | 30.0 |
| audio_alignment | use_vspreview | boolean | false |
| audio_alignment | cache_results | boolean | true |
| screenshots | use_ffmpeg | boolean | false |
| screenshots | directory_name | string | "screenshots" |
| screenshots | overlay_mode | string | "standard" |
| screenshots | include_frame_number | boolean | true |
| screenshots | png_compression | integer | 6 |
| screenshots | ffmpeg_timeout_seconds | number | 30.0 |
| color | enable_tonemap | boolean | true |
| color | preset | string | "reference" |
| color | target_nits | integer | 203 |
| color | tone_curve | string | "bt2390" |
| color | gamma_lift | boolean | false |
| color | contrast_recovery | number | 0.0 |
| slowpics | auto_upload | boolean | true |
| slowpics | visibility | string | "unlisted" |
| slowpics | delete_after_upload | boolean | false |
| slowpics | timeout_seconds | number | 60.0 |
| slowpics | max_retries | integer | 3 |
| tmdb | api_key | string/null | null |
| tmdb | enabled | boolean | true |
| tmdb | unattended | boolean | false |
| tmdb | timeout_seconds | number | 10.0 |
| report | enable | boolean | true |
| report | output_dir | string/null | null |
| report | default_mode | string | "slider" |
| report | include_filmstrip | boolean | true |
| report | embed_images | boolean | false |
| dovi | enable | boolean | true |
| dovi | dovi_tool_path | string/null | null |
| dovi | cache_results | boolean | true |
| diagnostics | per_frame_nits | boolean | false |
| diagnostics | show_hdr_info | boolean | false |
| diagnostics | frame_timing | boolean | false |
| logging | level | string | "INFO" |
| logging | format | string | "console" |
| logging | file | string/null | null |
<!-- END GENERATED:config_inventory -->

---

## 1. TOML Configuration Keys

### 1.1 Complete Configuration Example

```toml
# config/config.toml
# Frame Compare 2.0 Configuration

#──────────────────────────────────────────────────────────────────────────────
# PATHS
#──────────────────────────────────────────────────────────────────────────────
[paths]
input_dir = "comparison_videos"     # Video input directory
screenshots_dir = "screenshots"      # Screenshot output directory (also default for report.output_dir)
generated_dir = "generated"          # Cache and generated files
config_dir = "config"                # Config and presets directory

#──────────────────────────────────────────────────────────────────────────────
# ANALYSIS
#──────────────────────────────────────────────────────────────────────────────
[analysis]
frame_count = 10                    # Number of frames to capture [1-100]
random_seed = 42                    # RNG seed for reproducibility
save_frames_data = true             # Save frame selection data
selection_mode = "mixed"            # quantile|motion|random|mixed
dark_quantile = 0.05                # Percentile for dark frames [0.0-0.5]
bright_quantile = 0.95              # Percentile for bright frames [0.5-1.0]

#──────────────────────────────────────────────────────────────────────────────
# AUDIO ALIGNMENT
#──────────────────────────────────────────────────────────────────────────────
[audio_alignment]
enable = true                       # Enable audio-based alignment
sample_rate = 8000                  # Sample rate for analysis [4000-48000]
max_offset_seconds = 30.0           # Maximum offset to search [1.0+]
use_vspreview = false               # Use VSPreview for manual alignment
cache_results = true                # Cache alignment results

#──────────────────────────────────────────────────────────────────────────────
# SCREENSHOTS
#──────────────────────────────────────────────────────────────────────────────
[screenshots]
use_ffmpeg = false                  # Use FFmpeg instead of VapourSynth
directory_name = "screenshots"      # Output subdirectory name
overlay_mode = "standard"           # minimal|standard|diagnostic|none
include_frame_number = true         # Show frame number in overlay
png_compression = 6                 # PNG compression level [0-9]
ffmpeg_timeout_seconds = 30.0       # Per-frame extraction timeout (seconds)

#──────────────────────────────────────────────────────────────────────────────
# COLOR / TONEMAPPING
#──────────────────────────────────────────────────────────────────────────────
[color]
enable_tonemap = true               # Enable HDR tonemapping
preset = "reference"                # Tonemap preset (see presets below)
target_nits = 203                   # Target peak brightness [100-1000]
tone_curve = "bt2390"               # bt2390|spline|reinhard|mobius|linear
gamma_lift = false                  # Apply gamma lift for dark scenes
contrast_recovery = 0.0             # Contrast recovery amount [0.0-1.0]

#──────────────────────────────────────────────────────────────────────────────
# SLOW.PICS PUBLISHING
#──────────────────────────────────────────────────────────────────────────────
[slowpics]
auto_upload = true                  # Automatically upload after render
visibility = "unlisted"             # public|unlisted|private
delete_after_upload = false         # Delete local files after upload
timeout_seconds = 60.0              # Upload timeout [10.0+]
max_retries = 3                     # Retry attempts [1-10]

#──────────────────────────────────────────────────────────────────────────────
# TMDB METADATA
#──────────────────────────────────────────────────────────────────────────────
[tmdb]
# api_key = "your-api-key-here"     # TMDB API key (or use TMDB_API_KEY env)
enabled = true                      # Enable TMDB lookup
unattended = false                  # Auto-select first match
timeout_seconds = 10.0              # API timeout [1.0+]

#──────────────────────────────────────────────────────────────────────────────
# HTML REPORT
#──────────────────────────────────────────────────────────────────────────────
[report]
enable = true                       # Generate HTML report
output_dir = ""                     # Report output directory (empty = screenshots dir)
default_mode = "slider"             # slider|overlay|diff|blink
include_filmstrip = true            # Include filmstrip view
embed_images = false                # Embed images as base64

#──────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICS
#──────────────────────────────────────────────────────────────────────────────
[diagnostics]
per_frame_nits = false              # Calculate per-frame nits
show_hdr_info = false               # Overlay HDR metadata
frame_timing = false                # Show frame timing info

#──────────────────────────────────────────────────────────────────────────────
# LOGGING
#──────────────────────────────────────────────────────────────────────────────
[logging]
level = "INFO"                      # DEBUG|INFO|WARNING|ERROR
format = "console"                  # json|console
# file = "logs/frame-compare.log"  # Log file path (optional)

#──────────────────────────────────────────────────────────────────────────────
# DOLBY VISION (optional)
#──────────────────────────────────────────────────────────────────────────────
[dovi]
enable = true                       # Enable Dolby Vision detection/extraction
# dovi_tool_path = "tools/dovi_tool"  # Path to dovi_tool binary (auto-detected)
cache_results = true                # Cache extracted metadata
```

---

## 2. Environment Variables

| Variable | Maps To | Description |
|----------|---------|-------------|
| `FRAME_COMPARE_ROOT` | (special) | Workspace root directory |
| `FRAME_COMPARE_CONFIG` | (special) | Config file path |
| `FRAME_COMPARE_LOG_LEVEL` | `logging.level` | Convenience alias (canonical: `FRAME_COMPARE_LOGGING__LEVEL`) |
| `FRAME_COMPARE_PATHS__INPUT_DIR` | `paths.input_dir` | Input directory |
| `FRAME_COMPARE_ANALYSIS__FRAME_COUNT` | `analysis.frame_count` | Frame count |
| `FRAME_COMPARE_COLOR__PRESET` | `color.preset` | Tonemap preset |
| `FRAME_COMPARE_COLOR__TARGET_NITS` | `color.target_nits` | Target brightness |
| `FRAME_COMPARE_SLOWPICS__AUTO_UPLOAD` | `slowpics.auto_upload` | Auto upload |
| `TMDB_API_KEY` | `tmdb.api_key` | Legacy alias (canonical: `FRAME_COMPARE_TMDB__API_KEY`) |

**Nesting pattern:** Use double underscore (`__`) for nested keys.

**Best practice:** Prefer the canonical `FRAME_COMPARE_<SECTION>__<FIELD>` variables. Aliases exist for compatibility and Docker ergonomics.

---

## 3. CLI Flag → Config Mapping

> [!NOTE]
> The canonical CLI contract is defined in [cli-flags-canonical.md](cli-flags-canonical.md).
> This table must be kept in sync with that document.

| CLI Flag | Config Key | Notes |
|----------|------------|-------|
| `--root` | (special) | Workspace root override |
| `--config` | (special) | Config file path |
| `--input` | `paths.input_dir` | Input directory |
| `--tm-preset` | `color.preset` | Tonemap preset |
| `--tm-target` | `color.target_nits` | Target nits |
| `--tm-curve` | `color.tone_curve` | Tone curve |
| `--frame-count` | `analysis.frame_count` | Frame count |
| `--seed` | `analysis.random_seed` | Random seed |
| `--no-upload` | `slowpics.auto_upload` | **Inverted**: false |
| `--no-cache` | (runtime) | Ignore cache |
| `--from-cache-only` | (runtime) | Use only cache |
| `--overlay` | `screenshots.overlay_mode` | Overlay mode |
| `--json` | (runtime) | JSON output format |
| `--no-color` | (runtime) | Disable colored output |
| `--write-config` | (runtime) | Write config and exit |
| `--diagnose-paths` | (runtime) | Print path diagnostics as JSON |
| `--quiet` | (runtime) | Temporarily set logging to WARNING |
| `--verbose` | (runtime) | Temporarily set logging to DEBUG |

> [!IMPORTANT]
> **Runtime-only flags** (`--no-cache`, `--from-cache-only`, `--json`, `--no-color`, `--quiet`, `--verbose`, etc.)
> affect execution behavior but are **never persisted** to config, even with `--write-config`.
> They are carried in `RunRequest`, not `ConfigSchema`.

---

## 4. Tonemap Presets

| Preset | Description | Settings |
|--------|-------------|----------|
| `reference` | Faithful to source, balanced | Default curve and nits |
| `filmic` | Film-like rolloff | Spline curve, contrast 0.2 |
| `contrast` | Enhanced contrast | Higher contrast recovery |
| `bt2390_spec` | ITU-R BT.2390 spec | BT.2390 curve, no lift |
| `spline` | Smooth spline curve | Spline curve |
| `bright_lift` | Lifted shadows | Gamma lift enabled |
| `highlight_guard` | Protect highlights | Reinhard curve |

---

## 5. Override Priority

**Highest to lowest priority:**

1. CLI flags (`--tm-preset reference`)
2. Environment variables (`FRAME_COMPARE_COLOR__PRESET=reference`)
3. TOML config file (`[color] preset = "reference"`)
4. Built-in defaults

---

## 6. Validation Rules

| Field | Type | Constraint | Default |
|-------|------|------------|---------|
| `analysis.frame_count` | int | 1-100 | 10 |
| `analysis.random_seed` | int | any | 42 |
| `analysis.dark_quantile` | float | 0.0-0.5 | 0.05 |
| `analysis.bright_quantile` | float | 0.5-1.0 | 0.95 |
| `audio_alignment.sample_rate` | int | 4000-48000 | 8000 |
| `audio_alignment.max_offset_seconds` | float | ≥1.0 | 30.0 |
| `screenshots.png_compression` | int | 0-9 | 6 |
| `color.target_nits` | int | 100-1000 | 203 |
| `color.contrast_recovery` | float | 0.0-1.0 | 0.0 |
| `slowpics.timeout_seconds` | float | ≥10.0 | 60.0 |
| `slowpics.max_retries` | int | 1-10 | 3 |
| `tmdb.timeout_seconds` | float | ≥1.0 | 10.0 |
