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
- Deterministic frame selection that combines quantile-based brightness picks, smoothed motion scoring, user pins, and seeded randomness, while caching metrics for reruns.
- Configurable selection windows that respect per-clip trims, ignore/skip timing, and collapse to a safe fallback when sources disagree.
- VapourSynth integration with optional HDR→SDR tonemapping, FFmpeg screenshot fallback, modulus-aware cropping, and placeholder creation when writers fail.
- Automatic slow.pics uploads with webhook retries, `.url` shortcut generation, and strict naming validation so every frame lands in the right slot.
- Rich CLI that discovers clips, deduplicates labels, applies trims/FPS overrides consistently, and cleans up rendered images after upload when requested.

## Installation
### Requirements
- Python 3.11 (>=3.11,<3.12).
- Runtime tools depending on your workflow:
  - VapourSynth with the `lsmas` plugin and (optionally) `libplacebo` for HDR tonemapping.
  - FFmpeg when `screenshots.use_ffmpeg=true` (the CLI checks for the executable).
  - `requests-toolbelt` is installed via `pyproject.toml` for slow.pics uploads; the code warns if it is missing.
  - Optional: `pyperclip` to copy the slow.pics URL to your clipboard.

### Install Python dependencies with uv
```bash
uv sync
```
This resolves the application dependencies listed in `pyproject.toml`. Add `--group dev` when you also want linting and test tools.

### Provision VapourSynth
- **Inside the virtual environment**: install a wheel that matches your interpreter, e.g. `uv pip install VapourSynth`.
- **Using a system install**: install VapourSynth through your platform’s packages, then expose its Python modules by either
  - setting the `VAPOURSYNTH_PYTHONPATH` environment variable, or
  - listing search folders in `[runtime.vapoursynth_python_paths]` (they are prepended to `sys.path`).

Ensure the interpreter ABI matches the VapourSynth build; otherwise imports will raise `ClipInitError` with guidance on the missing module.

### FFmpeg workflow
Keep `screenshots.use_ffmpeg=false` to render through VapourSynth. When set to `true`, make sure `ffmpeg` is on `PATH`; otherwise a `ScreenshotWriterError` is raised.

## Configuration
The CLI reads a UTF-8 TOML file and instantiates the dataclasses in `src/datatypes.py`. `_sanitize_section` coerces booleans, validates keys, and applies range checks for every section. All fields have defaults, but you should at least point `[paths].input_dir` to a folder containing **two or more** video files.

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
debug_log_color_ranges = false

[tonemap]
preset = "reference"
func = "bt2390"
dpd = false
dst_max = 100.0
dst_min = 0.0
gamut_mapping = "clip"
smoothing_period = 3
scene_threshold_low = 0.12
scene_threshold_high = 0.32
overlay = false
verify = false
verify_metric = "abs"
verify_auto_search = true
verify_search_max = 180
verify_search_step = 12
verify_start_frame = 0
verify_luma_thresh = 0.45
use_dovi = true
always_try_placebo = false
dst_primaries = "bt709"
dst_transfer = "bt1886"
dst_matrix = "bt709"
dst_range = "limited"

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

[tmdb]
api_key = ""
unattended = true
year_tolerance = 2
enable_anime_parsing = true
cache_ttl_seconds = 86400
category_preference = ""

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
| `frame_count_dark` | int | 20 | No | Number of darkest frames to keep; uses quantiles or fallback ranges. Must be ≥0.|
| `frame_count_bright` | int | 10 | No | Number of brightest frames to keep using the same logic as dark picks.|
| `frame_count_motion` | int | 15 | No | Motion peaks after smoothing; quarter-gap spacing is applied via `screen_separation_sec/4`.|
| `user_frames` | list[int] | `[]` | No | Pinned frames that bypass scoring; out-of-window frames are dropped with a warning.|
| `random_frames` | int | 15 | No | Additional random picks seeded by `random_seed` and filtered by separation rules.|
| `save_frames_data` | bool | true | No | Persist metrics and selections to `frame_data_filename` for cache reuse.|
| `downscale_height` | int | 480 | No | Resizes clips before analysis; must be ≥64 if non-zero.|
| `step` | int | 2 | No | Sampling stride used when iterating frames; must be ≥1.|
| `analyze_in_sdr` | bool | true | No | Tonemap HDR sources through `vs_core.process_clip_for_screenshot`.|
| `use_quantiles` | bool | true | No | Toggle quantile thresholds; `false` enables fixed brightness bands.|
| `dark_quantile` | float | 0.20 | No | Quantile for dark picks when `use_quantiles=true`.|
| `bright_quantile` | float | 0.80 | No | Quantile for bright picks when `use_quantiles=true`.|
| `motion_use_absdiff` | bool | false | No | Switch between absolute differences and edge-enhanced diffs for motion metrics.|
| `motion_scenecut_quantile` | float | 0.0 | No | Drops motion values above this quantile to avoid extreme scene cuts.|
| `screen_separation_sec` | int | 6 | No | Minimum spacing between frames (also scales the motion gap). Must be ≥0.|
| `motion_diff_radius` | int | 4 | No | Radius for smoothing motion metrics before ranking.|
| `analyze_clip` | str | `""` | No | Filename, label, or index controlling which source drives analysis.|
| `random_seed` | int | 20202020 | No | Seed for deterministic randomness; must be ≥0.|
| `frame_data_filename` | str | `"generated.compframes"` | No | Cache filename (must be non-empty). Stored next to the input root.|
| `skip_head_seconds` | float | 0.0 | No | Skips early frames after scoring; must be ≥0.|
| `skip_tail_seconds` | float | 0.0 | No | Skips trailing frames after scoring; must be ≥0.|
| `ignore_lead_seconds` | float | 0.0 | No | Trims the comparison window’s start before selection; must be ≥0.|
| `ignore_trail_seconds` | float | 0.0 | No | Trims the comparison window’s end before selection; must be ≥0.|
| `min_window_seconds` | float | 5.0 | No | Ensures the ignore window leaves at least this much footage; must be ≥0.|

#### `[screenshots]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `directory_name` | str | `"screens"` | No | Folder (under the input root) where PNGs are written.|
| `add_frame_info` | bool | true | No | Overlay frame index/picture type (VapourSynth) or drawtext (FFmpeg).|
| `use_ffmpeg` | bool | false | No | Use FFmpeg for rendering when VapourSynth is unavailable or trimmed frames require source indexes.|
| `compression_level` | int | 1 | No | Compression preset: 0 (fast), 1 (balanced), 2 (small). Other values raise `ConfigError`.|
| `upscale` | bool | true | No | Allow scaling above source height (global tallest clip by default).|
| `single_res` | int | 0 | No | Force a specific output height (`0` keeps clip-relative planning).|
| `mod_crop` | int | 2 | No | Align every clip to the smallest width/height while keeping dimensions divisible by this modulus; must be ≥0.|
| `letterbox_pillarbox_aware` | bool | true | No | When widths or heights already match, only crop the mismatched axis (preserves letterbox/pillarbox bars).|
| `debug_log_color_ranges` | bool | false | No | When `true`, logs format/prop diagnostics if VapourSynth screenshot rendering fails (useful for MaskedMerge range mismatches).|

#### `[tonemap]`

Key options are summarised below (see `docs/tonemap.md` for the complete table):

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `preset` | str | `"reference"` | Preset bundle controlling the curve and heuristics. |
| `func` | str | `"bt2390"` | Tonemap curve passed to libplacebo. |
| `dpd` | bool | `false` | Enable libplacebo dynamic peak detection. |
| `dst_max` | float | `100.0` | SDR target peak in nits. |
| `dst_min` | float | `0.0` | SDR floor in nits. |
| `gamut_mapping` | str | `"clip"` | libplacebo gamut mapping mode. |
| `overlay` | bool | `false` | Draw the diagnostic overlay with active parameters. |
| `verify` | bool | `false` | Enable verification metrics (`abs`, `psnr`, `ssim`, `deltae`). |
| `use_dovi` | bool | `true` | Forward Dolby Vision metadata when the source provides it. |
| `always_try_placebo` | bool | `false` | Attempt libplacebo even if HDR heuristics are inconclusive. |

```toml
[tonemap]
# Example: brighten SDR target and enable verification with SSIM
preset = "custom"
func = "hable"
dst_max = 120.0
verify = true
verify_metric = "ssim"
overlay = true
```

The CLI mirrors every field with `--tm-*` flags; for example `--tm-preset filmic --tm-overlay` overrides TOML settings for a single run.

#### `[slowpics]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `auto_upload` | bool | false | No | Upload automatically after screenshots finish.|
| `collection_name` | str | `""` | No | Custom collection title sent to slow.pics.|
| `is_hentai` | bool | false | No | Marks the collection as hentai for filtering.|
| `is_public` | bool | true | No | Controls slow.pics visibility.|
| `tmdb_id` | str | `""` | No | Optional TMDB identifier.|
| `remove_after_days` | int | 0 | No | Schedule deletion after N days; must be ≥0.|
| `webhook_url` | str | `""` | No | Webhook notified after upload; retries with backoff.|
| `open_in_browser` | bool | true | No | Launch slow.pics URL with `webbrowser.open` on success.|
| `create_url_shortcut` | bool | true | No | Save a `.url` shortcut next to screenshots.|
| `delete_screen_dir_after_upload` | bool | true | No | Delete rendered screenshots after a successful upload.|

#### `[tmdb]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `api_key` | str | `""` | No | Enable TMDB matching by providing your API key.| 
| `unattended` | bool | true | No | Automatically select the best TMDB match; disable to allow manual overrides when ambiguous.|
| `year_tolerance` | int | 2 | No | Acceptable difference between parsed year and TMDB results; must be ≥0.|
| `enable_anime_parsing` | bool | true | No | Use Anitopy-derived titles when searching for anime releases.|
| `cache_ttl_seconds` | int | 86400 | No | Cache TMDB responses in-memory for this many seconds; must be ≥0.|
| `category_preference` | str | `""` | No | Optional default category when external IDs resolve to both movie and TV (set `MOVIE` or `TV`).|

#### `[naming]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `always_full_filename` | bool | true | No | Use the original filename as the label instead of parsed metadata.|
| `prefer_guessit` | bool | true | No | Prefer GuessIt over Anitopy when deriving metadata; falls back automatically.|

#### `[paths]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `input_dir` | str | `"."` | No | Root directory containing the comparison clips. Update this or use `--input` per run.|

#### `[runtime]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `ram_limit_mb` | int | 8000 | No | Applies `core.max_cache_size` on VapourSynth; must be >0.|
| `vapoursynth_python_paths` | list[str] | `[]` | No | Additional search paths appended to `sys.path` before importing VapourSynth.|

#### `[overrides]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `trim` | dict[str,int] | `{}` | No | Trim leading frames per clip; negative values prepend blanks to preserve indexing.|
| `trim_end` | dict[str,int] | `{}` | No | Trim trailing frames; accepts negative indexes as Python slicing does.|
| `change_fps` | dict[str, list[int] or "set"] | `{}` | No | Either `[num, den]` to apply `AssumeFPS`, or `"set"` to mark the clip as the reference FPS for others.|

## TMDB auto-discovery
Enabling `[tmdb].api_key` activates an asynchronous resolver that translates filenames into TMDB metadata before screenshots are rendered. The CLI analyses the first detected source to gather title/year hints (via GuessIt/Anitopy), then resolves `(category, tmdbId, original language)` once per run. Successful matches populate:

- `cfg.slowpics.tmdb_id` when it is empty so the slow.pics upload automatically links to TMDB,
- the templating context for `[slowpics].collection_name`, exposing `${Title}`, `${OriginalTitle}`, `${Year}`, `${TMDBId}`, `${TMDBCategory}`, `${OriginalLanguage}`, `${Filename}`, `${FileName}`, and `${Label}`, and
- the default slow.pics collection title when `[slowpics].collection_name` is blank, using `${Title}`/`${Year}` when present or the first filename as a fallback.

Resolution follows a deterministic pipeline:

1. If the filename or metadata exposes external IDs, `find/{imdb|tvdb}_id` is queried first, honouring `[tmdb].category_preference` when both movie and TV hits are returned.
2. Otherwise, the resolver issues `search/movie` or `search/tv` calls with progressively broader queries derived from the cleaned title. Heuristics include year windows within `[tmdb].year_tolerance`, roman-numeral conversion, subtitle/colon trimming, reduced word sets, automatic movie↔TV switching, and, when `[tmdb].enable_anime_parsing=true`, romaji titles via Anitopy.
3. Every response is scored by similarity, release year proximity, and light popularity boosts. Strong matches are selected immediately; otherwise the highest scoring candidate wins with logging that notes the heuristic (e.g. “roman-numeral”). Ambiguity only surfaces when `[tmdb].unattended=false`, in which case the CLI prompts for a manual identifier such as `movie/603`.

All HTTP requests share an in-memory cache governed by `[tmdb].cache_ttl_seconds` and automatically apply exponential backoff on rate limits or transient failures. Setting `[tmdb].api_key` is mandatory; when omitted the resolver is skipped.
The CLI prints a reminder and slow.pics falls back to whatever `tmdb_id` you manually provided in the config.

## CLI usage
```
Usage: frame_compare.py [OPTIONS]

Options:
  --config TEXT  Path to config.toml  [default: config.toml]
  --input TEXT   Override [paths.input_dir] from config.toml
  --help         Show this message and exit.
```

### Common recipes
- **Run against another folder**: `uv run python frame_compare.py --config config.toml --input D:/captures` overrides `[paths].input_dir` for a single run.
- **Pin the analysis driver**: set `analysis.analyze_clip` to a filename, label, or index (as a string) so that clip guides scoring while others inherit its FPS when marked with `change_fps = { "name" = "set" }`.
- **Reuse cached metrics**: keep `save_frames_data=true`. Subsequent runs load `frame_data_filename`, skip metric collection, and immediately reuse the stored frame list.
- **Render with FFmpeg**: toggle `[screenshots].use_ffmpeg = true` to render directly from source files—useful when VapourSynth is unavailable or trims insert synthetic blanks.
- **Upload to slow.pics**: enable `[slowpics].auto_upload`, optionally set `webhook_url`, and the CLI will stream uploads with progress bars, retry the webhook, and delete screenshots after success when configured.

## Determinism & reproducibility
- All random sampling uses `random.Random(random_seed)` so identical configs and inputs yield the same frame order.
- Cached metrics store a config fingerprint and clip metadata; the loader validates hashes, file lists, trims, FPS, and release groups before reuse, guaranteeing identical selections when nothing changed.
- Selection windows derive from computed clip metadata and obey deterministic rounding, so applying the same trims, ignores, and FPS overrides reproduces the same frame subset.

## Troubleshooting
| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Config error: analysis.step must be >= 1` (or similar) | TOML value out of range. | Update the value to satisfy the validation listed in the config table.|
| `VapourSynth is not available in this environment.` | `vapoursynth` module not importable from the current interpreter. | Install a matching VapourSynth build or add its site-packages directory to `runtime.vapoursynth_python_paths`/`VAPOURSYNTH_PYTHONPATH`.|
| `VapourSynth core is missing the lsmas plugin` | `lsmas.LWLibavSource` unavailable, so clips cannot be opened. | Install the `lsmas` plugin in the active VapourSynth environment.|
| `FFmpeg executable not found in PATH` | `[screenshots].use_ffmpeg` enabled without FFmpeg installed. | Install FFmpeg and ensure the binary is discoverable, or disable the flag.|
| `requests-toolbelt is required for slow.pics uploads.` | Dependency missing from the runtime environment. | Install `requests-toolbelt` (bundled via `uv sync`) before enabling auto-upload.|
| `Screenshot '<name>' does not follow '<frame> - <label>.png' naming` | PNG files renamed or altered before upload. | Keep the generated naming scheme so the uploader can group frames correctly.|
| `Missing XSRF token` when uploading | slow.pics session cookie not returned. | Retry later; the client requires the token from the landing page before posting images.|
| `Falling back to placeholder for frame …` warning | VapourSynth/FFmpeg writer raised an exception while rendering. | Inspect the log; install missing plugins or leave placeholders as cues to re-render later.|

## Development
- Install dev tools: `uv sync --group dev`
- Lint: `uv run ruff check .`
- Format: `uv run black .`
- Tests: `uv run python -m pytest -q`

The test suite covers analysis heuristics, configuration validation, screenshot planning, slow.pics integration, and the VapourSynth shim.

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
Licensed under the MIT License. See `LICENSE` for details.
