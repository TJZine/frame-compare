# Frame Compare

Automated frame comparison pipeline that samples representative scenes, renders aligned screenshots, and optionally publishes a slow.pics collection.

## TL;DR Quickstart
```bash
uv sync
cp config.toml.template config.toml
uv run python frame_compare.py --config config.toml --input comparison_videos
```
You should see `Comparison ready` followed by the selected frames, output directory, and slow.pics URL (when enabled).

## Features
- Deterministic frame selection that combines quantile-based brightness picks, smoothed motion scoring, user pins, and seeded randomness, while caching metrics for reruns.【F:src/analysis.py†L89-L116】【F:src/analysis.py†L472-L543】
- Configurable selection windows that respect per-clip trims, ignore/skip timing, and collapse to a safe fallback when sources disagree.【F:frame_compare.py†L229-L306】【F:src/analysis.py†L520-L566】
- VapourSynth integration with optional HDR→SDR tonemapping, FFmpeg screenshot fallback, modulus-aware cropping, and placeholder creation when writers fail.【F:src/analysis.py†L551-L575】【F:src/vs_core.py†L158-L214】【F:src/screenshot.py†L107-L205】【F:src/screenshot.py†L272-L360】
- Automatic slow.pics uploads with webhook retries, `.url` shortcut generation, and strict naming validation so every frame lands in the right slot.【F:src/slowpics.py†L40-L115】【F:src/slowpics.py†L117-L204】
- Rich CLI that discovers clips, deduplicates labels, applies trims/FPS overrides consistently, and cleans up rendered images after upload when requested.【F:frame_compare.py†L78-L175】【F:frame_compare.py†L307-L478】【F:frame_compare.py†L640-L789】

## Installation
### Requirements
- Python 3.11 (>=3.11,<3.12).【F:pyproject.toml†L3-L5】
- Runtime tools depending on your workflow:
  - VapourSynth with the `lsmas` plugin and (optionally) `libplacebo` for HDR tonemapping.【F:src/vs_core.py†L66-L148】【F:src/vs_core.py†L186-L228】
  - FFmpeg when `screenshots.use_ffmpeg=true` (the CLI checks for the executable).【F:src/screenshot.py†L330-L360】
  - `requests-toolbelt` is installed via `pyproject.toml` for slow.pics uploads; the code warns if it is missing.【F:pyproject.toml†L6-L14】【F:src/slowpics.py†L117-L135】
  - Optional: `pyperclip` to copy the slow.pics URL to your clipboard.【F:frame_compare.py†L812-L825】

### Install Python dependencies with uv
```bash
uv sync
```
This resolves the application dependencies listed in `pyproject.toml`. Add `--group dev` when you also want linting and test tools.【F:pyproject.toml†L16-L22】

### Provision VapourSynth
- **Inside the virtual environment**: install a wheel that matches your interpreter, e.g. `uv pip install VapourSynth`.
- **Using a system install**: install VapourSynth through your platform’s packages, then expose its Python modules by either
  - setting the `VAPOURSYNTH_PYTHONPATH` environment variable, or
  - listing search folders in `[runtime.vapoursynth_python_paths]` (they are prepended to `sys.path`).【F:src/vs_core.py†L34-L82】

Ensure the interpreter ABI matches the VapourSynth build; otherwise imports will raise `ClipInitError` with guidance on the missing module.【F:src/vs_core.py†L84-L132】

### FFmpeg workflow
Keep `screenshots.use_ffmpeg=false` to render through VapourSynth. When set to `true`, make sure `ffmpeg` is on `PATH`; otherwise a `ScreenshotWriterError` is raised.【F:src/screenshot.py†L312-L360】

## Configuration
The CLI reads a UTF-8 TOML file and instantiates the dataclasses in `src/datatypes.py`. `_sanitize_section` coerces booleans, validates keys, and applies range checks for every section.【F:src/config_loader.py†L24-L109】 All fields have defaults, but you should at least point `[paths].input_dir` to a folder containing **two or more** video files.

### Minimal config
```toml
[paths]
input_dir = "comparison_videos"
```

### Full config example
```toml
[analysis]
frame_count_dark = 20
frame_count_bright = 10
frame_count_motion = 15
user_frames = []
random_frames = 15
save_frames_data = true
downscale_height = 480
step = 2
analyze_in_sdr = true
use_quantiles = true
dark_quantile = 0.20
bright_quantile = 0.80
motion_use_absdiff = false
motion_scenecut_quantile = 0.0
screen_separation_sec = 6
motion_diff_radius = 4
analyze_clip = ""
random_seed = 20202020
frame_data_filename = "generated.compframes"
skip_head_seconds = 0.0
skip_tail_seconds = 0.0
ignore_lead_seconds = 0.0
ignore_trail_seconds = 0.0
min_window_seconds = 5.0

[screenshots]
directory_name = "screens"
add_frame_info = true
use_ffmpeg = false
compression_level = 1
upscale = true
single_res = 0
mod_crop = 2
letterbox_pillarbox_aware = true

[slowpics]
auto_upload = false
collection_name = ""
is_hentai = false
is_public = true
tmdb_id = ""
remove_after_days = 0
webhook_url = ""
open_in_browser = true
create_url_shortcut = true
delete_screen_dir_after_upload = true

[naming]
always_full_filename = true
prefer_guessit = true

[paths]
input_dir = "comparison_videos"

[runtime]
ram_limit_mb = 8000
vapoursynth_python_paths = []

[overrides]
trim = {}
trim_end = {}
change_fps = {}
```

### Config reference
#### `[analysis]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `frame_count_dark` | int | 20 | No | Number of darkest frames to keep; uses quantiles or fallback ranges. Must be ≥0.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L622-L653】|
| `frame_count_bright` | int | 10 | No | Number of brightest frames to keep using the same logic as dark picks.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L653-L670】|
| `frame_count_motion` | int | 15 | No | Motion peaks after smoothing; quarter-gap spacing is applied via `screen_separation_sec/4`.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L670-L698】|
| `user_frames` | list[int] | `[]` | No | Pinned frames that bypass scoring; out-of-window frames are dropped with a warning.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L566-L619】|
| `random_frames` | int | 15 | No | Additional random picks seeded by `random_seed` and filtered by separation rules.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L698-L717】|
| `save_frames_data` | bool | true | No | Persist metrics and selections to `frame_data_filename` for cache reuse.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L360-L451】|
| `downscale_height` | int | 480 | No | Resizes clips before analysis; must be ≥64 if non-zero.【F:src/datatypes.py†L10-L31】【F:src/config_loader.py†L111-L138】|
| `step` | int | 2 | No | Sampling stride used when iterating frames; must be ≥1.【F:src/datatypes.py†L10-L31】【F:src/config_loader.py†L111-L118】|
| `analyze_in_sdr` | bool | true | No | Tonemap HDR sources through `vs_core.process_clip_for_screenshot`.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L551-L560】|
| `use_quantiles` | bool | true | No | Toggle quantile thresholds; `false` enables fixed brightness bands.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L622-L670】|
| `dark_quantile` | float | 0.20 | No | Quantile for dark picks when `use_quantiles=true`.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L622-L633】|
| `bright_quantile` | float | 0.80 | No | Quantile for bright picks when `use_quantiles=true`.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L633-L670】|
| `motion_use_absdiff` | bool | false | No | Switch between absolute differences and edge-enhanced diffs for motion metrics.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L420-L449】|
| `motion_scenecut_quantile` | float | 0.0 | No | Drops motion values above this quantile to avoid extreme scene cuts.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L676-L692】|
| `screen_separation_sec` | int | 6 | No | Minimum spacing between frames (also scales the motion gap). Must be ≥0.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L609-L669】|
| `motion_diff_radius` | int | 4 | No | Radius for smoothing motion metrics before ranking.【F:src/datatypes.py†L10-L31】【F:src/analysis.py†L462-L471】|
| `analyze_clip` | str | `""` | No | Filename, label, or index controlling which source drives analysis.【F:src/datatypes.py†L10-L31】【F:frame_compare.py†L178-L227】|
| `random_seed` | int | 20202020 | No | Seed for deterministic randomness; must be ≥0.【F:src/datatypes.py†L10-L31】【F:src/config_loader.py†L118-L129】|
| `frame_data_filename` | str | `"generated.compframes"` | No | Cache filename (must be non-empty). Stored next to the input root.【F:src/datatypes.py†L10-L31】【F:frame_compare.py†L408-L451】|
| `skip_head_seconds` | float | 0.0 | No | Skips early frames after scoring; must be ≥0.【F:src/datatypes.py†L20-L31】【F:src/config_loader.py†L129-L138】|
| `skip_tail_seconds` | float | 0.0 | No | Skips trailing frames after scoring; must be ≥0.【F:src/datatypes.py†L20-L31】【F:src/config_loader.py†L129-L138】|
| `ignore_lead_seconds` | float | 0.0 | No | Trims the comparison window’s start before selection; must be ≥0.【F:src/datatypes.py†L20-L31】【F:src/config_loader.py†L129-L138】|
| `ignore_trail_seconds` | float | 0.0 | No | Trims the comparison window’s end before selection; must be ≥0.【F:src/datatypes.py†L20-L31】【F:src/config_loader.py†L129-L138】|
| `min_window_seconds` | float | 5.0 | No | Ensures the ignore window leaves at least this much footage; must be ≥0.【F:src/datatypes.py†L20-L31】【F:src/config_loader.py†L129-L138】|

#### `[screenshots]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `directory_name` | str | `"screens"` | No | Folder (under the input root) where PNGs are written.【F:src/datatypes.py†L33-L43】【F:frame_compare.py†L587-L635】|
| `add_frame_info` | bool | true | No | Overlay frame index/picture type (VapourSynth) or drawtext (FFmpeg).【F:src/datatypes.py†L33-L43】【F:src/screenshot.py†L144-L205】【F:src/screenshot.py†L330-L360】|
| `use_ffmpeg` | bool | false | No | Use FFmpeg for rendering when VapourSynth is unavailable or trimmed frames require source indexes.【F:src/datatypes.py†L33-L43】【F:src/screenshot.py†L300-L360】|
| `compression_level` | int | 1 | No | Compression preset: 0 (fast), 1 (balanced), 2 (small). Other values raise `ConfigError`.【F:src/datatypes.py†L33-L43】【F:src/config_loader.py†L138-L144】【F:src/screenshot.py†L231-L260】|
| `upscale` | bool | true | No | Allow scaling above source height (global tallest clip by default).【F:src/datatypes.py†L33-L43】【F:src/screenshot.py†L205-L244】|
| `single_res` | int | 0 | No | Force a specific output height (`0` keeps clip-relative planning).【F:src/datatypes.py†L33-L43】【F:src/screenshot.py†L205-L244】|
| `mod_crop` | int | 2 | No | Crop to maintain dimensions divisible by this modulus; must be ≥0.【F:src/datatypes.py†L33-L43】【F:src/config_loader.py†L138-L142】【F:src/screenshot.py†L156-L205】|
| `letterbox_pillarbox_aware` | bool | true | No | Bias cropping toward letterbox/pillarbox bars when trimming.【F:src/datatypes.py†L33-L43】【F:src/screenshot.py†L156-L205】|

#### `[slowpics]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `auto_upload` | bool | false | No | Upload automatically after screenshots finish.【F:src/datatypes.py†L45-L58】【F:frame_compare.py†L702-L789】|
| `collection_name` | str | `""` | No | Custom collection title sent to slow.pics.【F:src/datatypes.py†L45-L58】【F:src/slowpics.py†L150-L204】|
| `is_hentai` | bool | false | No | Marks the collection as hentai for filtering.【F:src/datatypes.py†L45-L58】【F:src/slowpics.py†L150-L204】|
| `is_public` | bool | true | No | Controls slow.pics visibility.【F:src/datatypes.py†L45-L58】【F:src/slowpics.py†L150-L204】|
| `tmdb_id` | str | `""` | No | Optional TMDB identifier.【F:src/datatypes.py†L45-L58】【F:src/slowpics.py†L150-L204】|
| `remove_after_days` | int | 0 | No | Schedule deletion after N days; must be ≥0.【F:src/datatypes.py†L45-L58】【F:src/config_loader.py†L142-L146】|
| `webhook_url` | str | `""` | No | Webhook notified after upload; retries with backoff.【F:src/datatypes.py†L45-L58】【F:src/slowpics.py†L40-L75】【F:src/slowpics.py†L198-L204】|
| `open_in_browser` | bool | true | No | Launch slow.pics URL with `webbrowser.open` on success.【F:src/datatypes.py†L45-L58】【F:frame_compare.py†L800-L812】|
| `create_url_shortcut` | bool | true | No | Save a `.url` shortcut next to screenshots.【F:src/datatypes.py†L45-L58】【F:src/slowpics.py†L198-L204】|
| `delete_screen_dir_after_upload` | bool | true | No | Delete rendered screenshots after a successful upload.【F:src/datatypes.py†L45-L58】【F:frame_compare.py†L812-L823】|

#### `[naming]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `always_full_filename` | bool | true | No | Use the original filename as the label instead of parsed metadata.【F:src/datatypes.py†L60-L69】【F:frame_compare.py†L133-L175】|
| `prefer_guessit` | bool | true | No | Prefer GuessIt over Anitopy when deriving metadata; falls back automatically.【F:src/datatypes.py†L60-L69】【F:src/utils.py†L46-L122】|

#### `[paths]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `input_dir` | str | `"."` | No | Root directory containing the comparison clips. Update this or use `--input` per run.【F:src/datatypes.py†L71-L77】【F:frame_compare.py†L331-L381】|

#### `[runtime]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `ram_limit_mb` | int | 8000 | No | Applies `core.max_cache_size` on VapourSynth; must be >0.【F:src/datatypes.py†L79-L87】【F:src/config_loader.py†L144-L147】【F:src/vs_core.py†L214-L225】|
| `vapoursynth_python_paths` | list[str] | `[]` | No | Additional search paths appended to `sys.path` before importing VapourSynth.【F:src/datatypes.py†L79-L87】【F:src/vs_core.py†L34-L82】|

#### `[overrides]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `trim` | dict[str,int] | `{}` | No | Trim leading frames per clip; negative values prepend blanks to preserve indexing.【F:src/datatypes.py†L89-L97】【F:src/vs_core.py†L132-L186】|
| `trim_end` | dict[str,int] | `{}` | No | Trim trailing frames; accepts negative indexes as Python slicing does.【F:src/datatypes.py†L89-L97】【F:src/vs_core.py†L132-L186】|
| `change_fps` | dict[str, list[int] or "set"] | `{}` | No | Either `[num, den]` to apply `AssumeFPS`, or `"set"` to mark the clip as the reference FPS for others.【F:src/datatypes.py†L89-L97】【F:frame_compare.py†L199-L275】|

## CLI usage
```
Usage: frame_compare.py [OPTIONS]

Options:
  --config TEXT  Path to config.toml  [default: config.toml]
  --input TEXT   Override [paths.input_dir] from config.toml
  --help         Show this message and exit.
```

### Common recipes
- **Run against another folder**: `uv run python frame_compare.py --config config.toml --input D:/captures` overrides `[paths].input_dir` for a single run.【F:frame_compare.py†L364-L381】
- **Pin the analysis driver**: set `analysis.analyze_clip` to a filename, label, or index (as a string) so that clip guides scoring while others inherit its FPS when marked with `change_fps = { "name" = "set" }`.【F:frame_compare.py†L178-L275】
- **Reuse cached metrics**: keep `save_frames_data=true`. Subsequent runs load `frame_data_filename`, skip metric collection, and immediately reuse the stored frame list.【F:frame_compare.py†L408-L478】【F:src/analysis.py†L360-L451】
- **Render with FFmpeg**: toggle `[screenshots].use_ffmpeg = true` to render directly from source files—useful when VapourSynth is unavailable or trims insert synthetic blanks.【F:src/screenshot.py†L300-L360】【F:frame_compare.py†L587-L706】
- **Upload to slow.pics**: enable `[slowpics].auto_upload`, optionally set `webhook_url`, and the CLI will stream uploads with progress bars, retry the webhook, and delete screenshots after success when configured.【F:frame_compare.py†L702-L823】【F:src/slowpics.py†L40-L204】

## Determinism & reproducibility
- All random sampling uses `random.Random(random_seed)` so identical configs and inputs yield the same frame order.【F:src/analysis.py†L604-L717】
- Cached metrics store a config fingerprint and clip metadata; the loader validates hashes, file lists, trims, FPS, and release groups before reuse, guaranteeing identical selections when nothing changed.【F:src/analysis.py†L330-L419】
- Selection windows derive from computed clip metadata and obey deterministic rounding, so applying the same trims, ignores, and FPS overrides reproduces the same frame subset.【F:src/analysis.py†L520-L566】【F:frame_compare.py†L229-L306】

## Troubleshooting
| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Config error: analysis.step must be >= 1` (or similar) | TOML value out of range. | Update the value to satisfy the validation listed in the config table.【F:src/config_loader.py†L111-L142】|
| `VapourSynth is not available in this environment.` | `vapoursynth` module not importable from the current interpreter. | Install a matching VapourSynth build or add its site-packages directory to `runtime.vapoursynth_python_paths`/`VAPOURSYNTH_PYTHONPATH`.【F:src/vs_core.py†L34-L110】|
| `VapourSynth core is missing the lsmas plugin` | `lsmas.LWLibavSource` unavailable, so clips cannot be opened. | Install the `lsmas` plugin in the active VapourSynth environment.【F:src/vs_core.py†L110-L170】|
| `FFmpeg executable not found in PATH` | `[screenshots].use_ffmpeg` enabled without FFmpeg installed. | Install FFmpeg and ensure the binary is discoverable, or disable the flag.【F:src/screenshot.py†L300-L360】|
| `requests-toolbelt is required for slow.pics uploads.` | Dependency missing from the runtime environment. | Install `requests-toolbelt` (bundled via `uv sync`) before enabling auto-upload.【F:src/slowpics.py†L117-L135】|
| `Screenshot '<name>' does not follow '<frame> - <label>.png' naming` | PNG files renamed or altered before upload. | Keep the generated naming scheme so the uploader can group frames correctly.【F:src/slowpics.py†L135-L172】|
| `Missing XSRF token` when uploading | slow.pics session cookie not returned. | Retry later; the client requires the token from the landing page before posting images.【F:src/slowpics.py†L177-L204】|
| `Falling back to placeholder for frame …` warning | VapourSynth/FFmpeg writer raised an exception while rendering. | Inspect the log; install missing plugins or leave placeholders as cues to re-render later.【F:src/screenshot.py†L360-L420】|

## Development
- Install dev tools: `uv sync --group dev`
- Lint: `uv run ruff check .`
- Format: `uv run black .`
- Tests: `uv run python -m pytest -q`

The test suite covers analysis heuristics, configuration validation, screenshot planning, slow.pics integration, and the VapourSynth shim.【F:tests/test_analysis.py†L1-L216】【F:tests/test_config.py†L1-L63】【F:tests/test_screenshot.py†L1-L160】【F:tests/test_slowpics.py†L1-L204】【F:tests/test_vs_core.py†L1-L160】

## Repository structure
```
frame_compare.py        # Click-based CLI entry point
config.toml.template    # Sample configuration
comparison_videos/      # Example input directory
legacy/                 # Reference legacy scripts
src/
  analysis.py           # Frame scoring & selection
  config_loader.py      # TOML loader & validation
  datatypes.py          # Configuration schema
  screenshot.py         # Screenshot planning & writers
  slowpics.py           # slow.pics client
  utils.py              # Filename metadata helpers
  vs_core.py            # VapourSynth helpers
tests/                  # Pytest suite covering all modules
```

## License
Licensed under the MIT License. See `LICENSE` for details.【F:LICENSE†L1-L9】
