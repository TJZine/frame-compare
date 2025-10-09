# Frame Compare

Automated frame comparison pipeline that samples representative scenes, renders aligned screenshots, and optionally publishes a slow.pics collection.

## Quickstart
1. `uv sync` to install the core dependencies defined in `pyproject.toml`; uv will spin up `.venv/` automatically if it doesn't exist yet.
2. Copy `config.toml.template` to `config.toml` and point `[paths].input_dir` at a folder that holds at least two source videos (for example `comparison_videos/`).
3. Drop your reference and comparison clips into that folder; filenames drive the automatic labelling step.
4. Run the CLI:
   ```bash
   uv run python frame_compare.py --config config.toml --input comparison_videos
   ```
5. Watch for the `Comparison ready` banner. PNG screenshots land in `screens/` (or your `[screenshots].directory_name`), the metrics cache saves to `generated.compframes` when `analysis.save_frames_data = true`, and audio alignment (when enabled) records offsets in `generated.audio_offsets.toml`.

## Common tasks
### Compare two videos
- **Goal:** Inspect a single pair with the existing config.
- **Run:**
  ```bash
  uv run python frame_compare.py --config config.toml --input comparison_videos
  ```
- **Outputs:** Category-labelled PNGs in `screens/` and cached metrics in `generated.compframes`.

### Batch multiple sources
- **Goal:** Process every matching pair in a directory.
- **Run:**
  ```bash
  uv run python frame_compare.py --config config.toml --input /data/video_batches
  ```
- **Outputs:** One subdirectory per comparison under `screens/`, plus the shared metrics cache `generated.compframes`.

### Random frames with a fixed seed
- **Goal:** Reproducible scatter of additional timestamps.
- **Prepare:** Add to `config.toml`:
  ```toml
  [analysis]
  random_frames = 20
  random_seed = 123456
  ```
- **Run:** `uv run python frame_compare.py --config config.toml --input comparison_videos`
- **Outputs:** Extra `Random_*.png` files in `screens/` and an updated `generated.compframes` that replays exactly with the same seed.

### User-selected frames
- **Goal:** Force specific indices into the output.
- **Prepare:**
  ```toml
  [analysis]
  user_frames = [10, 200, 501]
  ```
- **Run:** `uv run python frame_compare.py --config config.toml --input comparison_videos`
- **Outputs:** `User_*.png` captures for each pinned index alongside the standard categories, plus the refreshed cache file.

### Mix random and pinned frames
- **Goal:** Blend deterministic pins with seeded randomness.
- **Prepare:**
  ```toml
  [analysis]
  user_frames = [10, 200, 501]
  random_frames = 8
  random_seed = 98765
  ```
- **Run:** `uv run python frame_compare.py --config config.toml --input comparison_videos`
- **Outputs:** Combined `User_*.png`, `Random_*.png`, and auto-selected categories in `screens/`, plus the deterministic cache artefacts.

### Auto-align mismatched sources
- **Goal:** Suggest trim offsets when encodes drift out of sync.
- **Prepare:**
  ```toml
  [audio_alignment]
  enable = true
  correlation_threshold = 0.6
  ```
- **Run:** `uv run python frame_compare.py --config config.toml --input comparison_videos`
- **Workflow:** The CLI estimates per-source offsets, writes `generated.audio_offsets.toml`, auto-selects matching streams (language → codec → layout), and now reports the reference/target streams, search window, and per-target offsets in the `Prepare` phase. Previews still save under `screens/audio_alignment/`; confirming continues automatically, while declining captures five more random frames and opens the offsets file for manual tweaks. Explicit stream picks from `--audio-align-track label=index` remain respected.

## Install
### macOS quick path
```bash
brew install python@3.13 ffmpeg
brew install vapoursynth          # optional: primary renderer
brew install uv
uv sync
```
Optional: manage `uv` with pipx instead (`pipx install uv`). Set `VAPOURSYNTH_PYTHONPATH` or `[runtime.vapoursynth_python_paths]` when relying on a system VapourSynth install.

### Generic Python environment
```bash
pipx install uv
uv sync
```
If `pipx` is unavailable, install uv once with `pip install --user uv` (or your platform's package manager) and then run `uv sync`. `uv sync` writes the environment into `.venv/` automatically; no manual `python -m venv` step is required.

Optional: install `pyperclip` (for example, `uv pip install pyperclip`) if you want the generated slow.pics URL copied to your clipboard automatically after uploads.

Fallback when uv is unavailable:
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -U pip wheel
pip install -e .
```
Add VapourSynth support later with `uv sync --extra vapoursynth` or `pip install 'vapoursynth>=72'` inside whichever environment you are using, and keep FFmpeg on `PATH` for the fallback renderer.


## Features
- Deterministic frame selection that combines quantile-based brightness picks, smoothed motion scoring, user pins, and seeded randomness, while caching metrics for reruns.
- Configurable selection windows that respect per-clip trims, ignore/skip timing, and collapse to a safe fallback when sources disagree.
- VapourSynth integration with optional HDR→SDR tonemapping, FFmpeg screenshot fallback, modulus-aware cropping, and placeholder creation when writers fail.
- Audio-guided trim suggestions—the only automated offset step—that write `generated.audio_offsets.toml`, auto-select matching streams, use finer DTW hops, prompt for quick visual confirmation, and accelerate alignment for mismatched transfers.
- Automatic slow.pics uploads with webhook retries, `.url` shortcut generation, and strict naming validation so every frame lands in the right slot.
- Rich CLI that discovers clips, deduplicates labels, applies trims/FPS overrides consistently, and now renders accented section headers with Unicode/ASCII fallbacks, dimmed dividers, and a verbose legend that explains every token used in the progress dashboard.

## Configuration (start here)
| Flag/Key | What it controls | When to use it | Type | Default | Example | Impact / Trade-offs | Notes | Source |
|---|---|---|---|---|---|---|---|---|
| `[paths].input_dir` | Scan root for video sources | Set it before each new batch | str | `"."` | `input_dir = "comparison_videos"` | Larger folders increase discovery time |  | original, readme, new |
| `--input` | Temporary scan folder override | Point at ad-hoc directories without editing config | CLI Optional[str] | `None` | `--input comparison_videos` | Overrides only the current run |  | original, readme, new |
| `[screenshots].directory_name` | Output folder name | Change when organising multiple runs | str | `"screens"` | `directory_name = "frames"` | Renaming breaks scripts that expect `screens/` |  | original, readme, new |
| `[analysis].frame_count_dark` | Dark scene quota | Increase for shadow-heavy content | int | `20` | `frame_count_dark = 12` | Higher counts take longer to evaluate |  | original, readme, new |
| `[analysis].frame_count_bright` | Bright scene quota | Highlight highlights in HDR/SDr mixes | int | `10` | `frame_count_bright = 16` | More frames lengthen tonemapping time |  | original, readme, new |
| `[analysis].frame_count_motion` | Motion candidate quota | Boost when action scenes matter | int | `15` | `frame_count_motion = 24` | Extra smoothing and diff passes add CPU cost |  | original, readme, new |
| `[analysis].random_frames` | Random frame count | Sample filler shots deterministically | int | `15` | `random_frames = 8` | More random picks extend total render count |  | original, readme, new |
| `[analysis].user_frames` | Pinned frame list | Guarantee exact timestamps | list[int] | `[]` | `user_frames = [10, 200, 501]` | Each pin adds a render regardless of scoring |  | original, readme, new |
| `[analysis].random_seed` | RNG seed | Match runs across machines and time | int | `20202020` | `random_seed = 1337` | Changing the seed shuffles random picks |  | original, readme, new |
| `[analysis].downscale_height` | Analysis resolution cap | Drop it when metrics feel slow | int | `480` | `downscale_height = 720` | Lower values run faster but risk missing detail |  | original, readme, new |
| `[audio_alignment].enable` | Audio offset detection toggle | Turn on when encodes drift before frame sampling | bool | `false` | `enable = true` | Requires FFmpeg and the built-in audio stack; prompts for preview confirmation | Writes `generated.audio_offsets.toml` | config.toml |
| `[audio_alignment].correlation_threshold` | Minimum onset correlation | Raise for noisier sources that need manual review | float | `0.55` | `correlation_threshold = 0.65` | Higher values skip low-confidence matches | Skipped clips still land in the offsets file | config.toml |
| `[audio_alignment].max_offset_seconds` | Largest offset to auto-apply | Keep search windows realistic | float | `12.0` | `max_offset_seconds = 4.0` | Huge offsets take longer to vet | Exceeding the limit marks the clip for manual edits | config.toml |
| `[audio_alignment].offsets_filename` | Offset cache path | Store adjustments alongside other generated data | str | `"generated.audio_offsets.toml"` | `offsets_filename = "cache/audio_offsets.toml"` | Custom paths help track multiple scenarios | File retains both suggested and manual frame counts | config.toml |
| `[audio_alignment].frame_offset_bias` | Frame adjustment toward/away from zero | Nudge applied offsets to match trim heuristics | int | `1` | `frame_offset_bias = 0` | Positive values pull offsets toward zero; negative push them outward | Frames clamp at zero when the adjustment exceeds the measured magnitude | config.toml |
| `[audio_alignment].confirm_with_screenshots` | Preview confirmation prompt | Disable for unattended batch runs | bool | `true` | `confirm_with_screenshots = false` | Skipping previews removes guard rails | When false, trims apply without manual inspection | config.toml |
| `--audio-align-track label=index` | Manual audio stream override | Force a stream when auto-selection disagrees | CLI (repeatable) | `None` | `--audio-align-track BBB=2` | Useful for commentary/dub heavy releases | Overrides both reference and target indices | new |
| `[screenshots].use_ffmpeg` | Renderer selection | Enable when VapourSynth is unavailable | bool | `False` | `use_ffmpeg = true` | Faster on plain installs, no advanced overlays |  | original, readme, new |
| `[color].enable_tonemap` | HDR→SDR pipeline toggle | Disable when inputs are SDR | bool | `True` | `enable_tonemap = false` | Skipping tonemap speeds renders but loses HDR cues |  | original, readme, new |
| `[runtime].ram_limit_mb` | VapourSynth RAM guard | Tune on constrained systems | int | `8000` | `ram_limit_mb = 4096` | Lower limits prevent spikes yet may trigger reloads |  | original, readme, new |
| `VAPOURSYNTH_PYTHONPATH` | Env search path for VapourSynth | Set when using a system install | env var | (verify) | `export VAPOURSYNTH_PYTHONPATH=/opt/vs/site-packages` | Missing path triggers ClipInit errors | Value read at src/vs_core.py:186 (verify) | original, ripgrep |
| `[cli].emit_json_tail` | Append structured summary to CLI output | Enable downstream tooling that scrapes runs | bool | `True` | `emit_json_tail = false` | Disabling removes the trailing machine-readable block; legend output still renders | config.toml |

## Features & Metrics
Brightness and darkness metrics downscale each sampled frame when needed, convert it to GRAY, and inspect the Y (luma) plane. The pipeline records the normalized mean brightness (0.0–1.0). Tonemapping in `[color].enable_tonemap` runs before sampling when HDR sources need SDR previews.

Motion metrics compare each frame with its predecessor. If `analysis.motion_use_absdiff = true`, the tool uses an absolute pixel difference, which runs fastest. Otherwise it applies `MakeDiff` followed by a Prewitt edge filter and then smooths values with `analysis.motion_diff_radius`, trading speed for crisp edge detection.

## Outputs
| Artifact | Format | Path pattern | How to generate (flag/example) | Notes | Source |
|---|---|---|---|---|---|
| Screenshots (default pipeline) | PNG | `"<frame> - <label>.png"` under `[screenshots].directory_name` | Run the CLI with VapourSynth enabled (`use_ffmpeg = false`) | Categories include Dark, Bright, Motion, Random, and User | original, readme, new, ripgrep |
| VapourSynth fpng renders | PNG | Same as above | Leave `[screenshots].use_ffmpeg = false`; uses `fpng.Write` | Requires the VapourSynth fpng plugin | original, new, ripgrep |
| FFmpeg renders | PNG | Same as above | Set `[screenshots].use_ffmpeg = true` | Depends on `ffmpeg` binary on `PATH` | original, new, ripgrep |
| Placeholder images | Text | Same as above | Written when a writer fails; see `_save_frame_placeholder` | Helpful for spotting missing renders | new, ripgrep |
| Metrics cache | JSON | `[analysis].frame_data_filename` (`generated.compframes` by default) | Keep `analysis.save_frames_data = true` | Stores brightness, motion, and selection data | original, readme, new, ripgrep |
| Selection sidecar | JSON | `generated.selection.v1.json` beside the cache | Saved with `_save_selection_sidecar` | Speeds up reloads when files match | original, new, ripgrep |
| Audio offset cache | TOML | `[audio_alignment].offsets_filename` (`generated.audio_offsets.toml` by default) | Enable `[audio_alignment].enable = true` | Captures suggested and manual trim offsets per clip | new |

## Advanced (deep technical)

### Advanced configuration (full reference)
The CLI reads a UTF-8 TOML file and instantiates the dataclasses in `src/datatypes.py`. `_sanitize_section` coerces booleans, validates keys, and applies range checks for every section. Every field ships with a default. Update `[paths].input_dir` before each run so at least two video files are available.

| Flag/Key | Purpose | Type | Default | Example | Related sections |
|---|---|---|---|---|---|
| `--config` | Selects the TOML configuration file used for a run | CLI `str` | `config.toml` | `uv run python frame_compare.py --config myrun.toml` | Installation, Usage Modes |
| `--input` | Overrides `[paths].input_dir` for a single invocation | CLI `Optional[str]` | `None` (use config) | `--input comparison_videos` | Usage Modes, Outputs |
| `[paths].input_dir` | Root directory scanned for video sources | `str` | `"."` | `input_dir = "comparison_videos"` | Installation, Usage Modes |
| `analysis.frame_count_dark` | Number of darkest frames to consider | `int` | `20` | `frame_count_dark = 12` | Detailed Features (Brightness) |
| `analysis.frame_count_bright` | Number of brightest frames to consider | `int` | `10` | `frame_count_bright = 16` | Detailed Features (Brightness) |
| `analysis.frame_count_motion` | Frames picked from motion scoring | `int` | `15` | `frame_count_motion = 24` | Detailed Features (Motion) |
| `analysis.random_frames` | Additional random samples within window | `int` | `15` | `random_frames = 8` | Usage Modes (Random) |
| `analysis.user_frames` | Explicit frame indices to force-include | `List[int]` | `[]` | `user_frames = [42, 180, 512]` | Usage Modes (User-selected) |
| `analysis.random_seed` | Seed for deterministic RNG behaviour | `int` | `20202020` | `random_seed = 1337` | Detailed Features, Usage Modes |
| `analysis.step` | Sampling stride when frames are sequential | `int` | `2` | `step = 1` | Performance Tips |
| `analysis.downscale_height` | Downscale height prior to metrics | `int` | `480` | `downscale_height = 720` | Performance Tips |
| `analysis.save_frames_data` | Persist frame metrics to cache file | `bool` | `True` | `save_frames_data = false` | Outputs, Performance Tips |
| `analysis.motion_use_absdiff` | Switch between absdiff and Prewitt-based motion | `bool` | `False` | `motion_use_absdiff = true` | Detailed Features (Motion) |
| `analysis.motion_scenecut_quantile` | Filters out motion spikes above quantile | `float` | `0.0` | `motion_scenecut_quantile = 0.85` | Detailed Features (Motion) |
| `analysis.motion_diff_radius` | Radius for motion smoothing window | `int` | `4` | `motion_diff_radius = 6` | Detailed Features (Motion) |
| `analysis.analyze_clip` | Reference clip label for scoring | `str` | `""` | `analyze_clip = "baseline"` | Usage Modes (Mixed) |
| `analysis.frame_data_filename` | Cache filename for saved metrics | `str` | `"generated.compframes"` | `frame_data_filename = "cached_metrics.compframes"` | Outputs |
| `audio_alignment.enable` | Toggle audio-based offset estimation | `bool` | `False` | `enable = true` | Usage Modes (Auto-align) |
| `audio_alignment.correlation_threshold` | Minimum correlation needed before applying | `float` | `0.55` | `correlation_threshold = 0.65` | Usage Modes (Auto-align) |
| `audio_alignment.max_offset_seconds` | Reject offsets beyond this magnitude | `float` | `12.0` | `max_offset_seconds = 6.0` | Usage Modes (Auto-align) |
| `audio_alignment.offsets_filename` | TOML file storing per-clip trims | `str` | `"generated.audio_offsets.toml"` | `offsets_filename = "cache/audio_offsets.toml"` | Outputs |
| `audio_alignment.confirm_with_screenshots` | Ask for preview confirmation after detection | `bool` | `True` | `confirm_with_screenshots = false` | Usage Modes (Auto-align) |
| `screenshots.use_ffmpeg` | Use FFmpeg instead of VapourSynth writer | `bool` | `False` | `use_ffmpeg = true` | Installation, Outputs |
| `screenshots.directory_name` | Output folder for rendered images | `str` | `"screens"` | `directory_name = "frames"` | Outputs |
| `screenshots.compression_level` | Compression preset (0–2) | `int` | `1` | `compression_level = 2` | Outputs |
| `screenshots.add_frame_info` | Overlay frame statistics on outputs | `bool` | `True` | `add_frame_info = false` | Detailed Features |
| `screenshots.pad_to_canvas` | Pad images to consistent canvas | `str` | `"off"` | `pad_to_canvas = "auto"` | Outputs |
| `color.enable_tonemap` | Enable HDR→SDR tonemapping | `bool` | `True` | `enable_tonemap = false` | Detailed Features (Brightness) |
| `color.tone_curve` | Tonemap curve identifier | `str` | `"bt.2390"` | `tone_curve = "hable"` | Detailed Features (Brightness) |
| `color.target_nits` | Target peak nits for tonemapping | `float` | `100.0` | `target_nits = 120.0` | Detailed Features (Brightness) |
| `color.verify_luma_threshold` | Luma delta threshold for verification | `float` | `0.10` | `verify_luma_threshold = 0.05` | Detailed Features |
| `slowpics.auto_upload` | Enable automatic slow.pics uploads | `bool` | `False` | `auto_upload = true` | Outputs |
| `slowpics.webhook_url` | Webhook to notify after upload | `str` | `""` | `webhook_url = "https://slow.pics/hooks/..."` | Outputs |
| `slowpics.delete_screen_dir_after_upload` | Remove screenshots after upload | `bool` | `True` | `delete_screen_dir_after_upload = false` | Outputs |
| `runtime.ram_limit_mb` | Upper bound for VapourSynth RAM use | `int` | `8000` | `ram_limit_mb = 4096` | Performance Tips |
| `runtime.vapoursynth_python_paths` | Extra Python paths for VapourSynth | `List[str]` | `[]` | `vapoursynth_python_paths = ["/opt/vs/python"]` | Installation, Performance |
| `source.preferred` | Preferred VapourSynth source plugin | `str` | `"lsmas"` | `preferred = "ffms2"` | Detailed Features |

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
frame_count_motion = 10
user_frames = []
random_frames = 10
save_frames_data = true
downscale_height = 720
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

[color]
enable_tonemap = true
preset = "reference"
tone_curve = "bt.2390"
dynamic_peak_detection = true
target_nits = 100.0
dst_min_nits = 0.1
overlay_enabled = true
overlay_text_template = "Tonemapping Algorithm: {tone_curve} dpd = {dynamic_peak_detection} dst = {target_nits} nits"
overlay_mode = "minimal"
verify_enabled = true
verify_auto = true
verify_start_seconds = 10.0
verify_step_seconds = 10.0
verify_max_seconds = 90.0
verify_luma_threshold = 0.10
strict = false

[slowpics]
auto_upload = true
collection_name = ""
is_hentai = false
is_public = true
tmdb_id = ""
tmdb_category = ""
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
ram_limit_mb = 4000
vapoursynth_python_paths = []

[source]
preferred = "lsmas"

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
| `frame_count_motion` | int | 10 | No | Motion peaks after smoothing; quarter-gap spacing is applied via `screen_separation_sec/4`.|
| `user_frames` | list[int] | `[]` | No | Pinned frames that bypass scoring; out-of-window frames are dropped with a warning.|
| `random_frames` | int | 10 | No | Additional random picks seeded by `random_seed` and filtered by separation rules.|
| `save_frames_data` | bool | true | No | Persist metrics and selections to `frame_data_filename` for cache reuse.|
| `downscale_height` | int | 720 | No | Resizes clips before analysis; values below 64 raise a validation error.|
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
| `upscale` | bool | true | No | Allow scaling above source height (global tallest clip by default). Width never exceeds the widest source unless `single_res` is set.|
| `single_res` | int | 0 | No | Force a specific output height (`0` keeps clip-relative planning).|
| `mod_crop` | int | 2 | No | Crop to maintain dimensions divisible by this modulus; must be ≥0.|
| `letterbox_pillarbox_aware` | bool | true | No | Bias cropping toward letterbox/pillarbox bars when trimming.|
| `auto_letterbox_crop` | bool | false | No | Estimate scope letterbox bars across sources via aspect ratios and crop them before planning.|
| `pad_to_canvas` | str | `"off"` | No | When `single_res` is set, pad instead of scaling to hit the target canvas. Values: `off`, `on`, `auto`.|
| `letterbox_px_tolerance` | int | 8 | No | Maximum total pixels (per axis) treated as a “micro” bar when `pad_to_canvas="auto"`.|
| `center_pad` | bool | true | No | Split padding evenly across both sides when padding is applied.|

#### `[color]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `enable_tonemap` | bool | true | No | Toggle HDR→SDR processing. When false the SDR pipeline runs and logs a `[TM BYPASS]` reason.|
| `preset` | str | `"reference"` | No | High-level preset for tone mapping: `reference`, `contrast`, `filmic`, or `custom`. Presets set `tone_curve`, `target_nits`, and `dynamic_peak_detection`.|
| `tone_curve` | str | `"bt.2390"` | No | Tone-curve passed to `libplacebo.Tonemap` when `preset="custom"`. Accepts `bt.2390`, `mobius`, or `hable`.|
| `dynamic_peak_detection` | bool | true | No | Toggles libplacebo's DPD smoothing (1 = on).|
| `target_nits` | float | 100.0 | No | SDR peak nits (`dst_max`). Must be >0.|
| `dst_min_nits` | float | 0.1 | No | Minimum nits for libplacebo (`dst_min`). Must be ≥0.|
| `overlay_enabled` | bool | true | No | Draw an SDR metadata overlay (top-right). If true, failures log `[OVERLAY]` and obey `strict`.|
| `overlay_text_template` | str | `"Tonemapping Algorithm: {tone_curve} dpd = {dynamic_peak_detection} dst = {target_nits} nits"` | No | Template for the overlay text. Placeholders: `{tone_curve}`, `{dpd}`, `{dynamic_peak_detection}`, `{target_nits}`, `{preset}`, `{reason}`.|
| `overlay_mode` | str | `"minimal"` | No | Selects overlay detail level: `minimal` shows the template plus the render resolution summary and a `Frame Selection Type` line; `diagnostic` additionally adds HDR mastering luminance (when available).|
| `verify_enabled` | bool | true | No | Compute Δ vs naive SDR and log `[VERIFY] frame=… avg=… max=…`.|
| `verify_frame` | int? | null | No | Force a specific verification frame index.|
| `verify_auto` | bool | true | No | Enable the auto-search described in `docs/hdr_tonemap_overview.md`.|
| `verify_start_seconds` | float | 10.0 | No | Skip the first N seconds before sampling frames.|
| `verify_step_seconds` | float | 10.0 | No | Sampling stride (seconds) when auto-picking verification frames. Must be >0.|
| `verify_max_seconds` | float | 90.0 | No | Stop searching after this many seconds (clamped by clip length).|
| `verify_luma_threshold` | float | 0.10 | No | Minimum average luma (0–1) for verification frame candidates.|
| `strict` | bool | false | No | Escalate overlay/verification failures to hard errors instead of logging them.|

See `docs/hdr_tonemap_overview.md` for a walkthrough of the log messages, presets, and verification heuristics.

#### `[slowpics]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `auto_upload` | bool | true | No | Upload automatically after screenshots finish.|
| `collection_name` | str | `""` | No | Custom collection title sent to slow.pics.|
| `collection_suffix` | str | `""` | No | Text appended after the resolved title/year when building the slow.pics collection name.|
| `is_hentai` | bool | false | No | Marks the collection as hentai for filtering.|
| `is_public` | bool | true | No | Controls slow.pics visibility.|
| `tmdb_id` | str | `""` | No | Optional TMDB identifier (digits or preformatted `movie/#####` / `MOVIE_#####`).|
| `tmdb_category` | str | `""` | No | Optional TMDB category hint (`MOVIE` or `TV`).|
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
| `confirm_matches` | bool | false | No | When enabled (and `unattended=false`), show the matched TMDB link and require confirmation or a manual id before continuing.|
| `year_tolerance` | int | 2 | No | Acceptable difference between parsed year and TMDB results; must be ≥0.|
| `enable_anime_parsing` | bool | true | No | Use Anitopy-derived titles when searching for anime releases.|
| `cache_ttl_seconds` | int | 86400 | No | Cache TMDB responses in-memory for this many seconds; must be ≥0.|
| `category_preference` | str? | null | No | Optional default category when external IDs resolve to both movie and TV (set `MOVIE` or `TV`).|

#### `[naming]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `always_full_filename` | bool | true | No | Use the original filename as the label instead of parsed metadata.|
| `prefer_guessit` | bool | true | No | Prefer GuessIt over Anitopy when deriving metadata; falls back automatically.|

#### `[cli]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `emit_json_tail` | bool | true | No | Append a JSON summary block to the CLI footer so scripts can scrape run metadata alongside the human-readable legend.|

#### `[paths]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `input_dir` | str | `"comparison_videos"` | No | Root directory containing the comparison clips. Update this or use `--input` per run.|

#### `[runtime]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `ram_limit_mb` | int | 4000 | No | Applies `core.max_cache_size` on VapourSynth; must be >0.|
| `vapoursynth_python_paths` | list[str] | `[]` | No | Additional search paths appended to `sys.path` before importing VapourSynth.|

#### `[source]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `preferred` | str | `"lsmas"` | No | Preferred VapourSynth source plugin. Set to `ffms2` to flip the loader priority.|

#### `[overrides]`
| Name | Type | Default | Required? | Description |
| --- | --- | --- | --- | --- |
| `trim` | dict[str,int] | `{}` | No | Trim leading frames per clip; negative values prepend blanks to preserve indexing.|
| `trim_end` | dict[str,int] | `{}` | No | Trim trailing frames; accepts negative indexes as Python slicing does.|
| `change_fps` | dict[str, list[int] or "set"] | `{}` | No | Either `[num, den]` to apply `AssumeFPS`, or `"set"` to mark the clip as the reference FPS for others.|

## TMDB auto-discovery
Enabling `[tmdb].api_key` activates an asynchronous resolver that translates filenames into TMDB metadata. The CLI analyses the first detected source to gather title and year hints (via GuessIt or Anitopy). It then resolves `(category, tmdbId, original language)` once per run. Successful matches populate:

- `cfg.slowpics.tmdb_id` and `cfg.slowpics.tmdb_category` when empty so the slow.pics upload automatically links to TMDB (normalizing to the legacy `MOVIE_#####` / `TV_#####` format), and
- the templating context for `[slowpics].collection_name`, exposing `${Title}`, `${OriginalTitle}`, `${Year}`, `${TMDBId}`, `${TMDBCategory}`, `${OriginalLanguage}`, `${Filename}`, `${FileName}`, and `${Label}`.

Resolution follows a deterministic pipeline:

1. If the filename or metadata exposes external IDs, `find/{imdb|tvdb}_id` is queried first. The resolver honours `[tmdb].category_preference` when both movie and TV hits appear.
2. Otherwise, the resolver issues `search/movie` or `search/tv` calls with progressively broader queries. It uses year windows (`[tmdb].year_tolerance`), roman-numeral conversion, subtitle trimming, alternative title extraction (such as “VVitch” → “Witch”), reduced word sets, automatic movie/TV switching, and (when `[tmdb].enable_anime_parsing=true`) romaji titles from Anitopy.
3. Every response is scored by similarity, release year proximity, and light popularity boosts. Strong matches are selected immediately. If no clear winner exists, the highest scoring candidate wins and the heuristic is logged (for example “roman-numeral”). Ambiguity only surfaces when `[tmdb].unattended=false`; the CLI then prompts for a manual identifier such as `movie/603`, which normalizes to `MOVIE_603`.

All HTTP requests share an in-memory cache governed by `[tmdb].cache_ttl_seconds`. The client applies exponential backoff on rate limits or transient failures. Setting `[tmdb].api_key` is mandatory; when omitted the resolver is skipped and slow.pics uses whatever `tmdb_id` you supplied manually.

## CLI usage
```
Usage: frame_compare.py [OPTIONS]

Options:
  --config TEXT  Path to config.toml  [default: config.toml]
  --input TEXT   Override [paths.input_dir] from config.toml
  --audio-align-track TEXT
                 Manual audio stream override (label=index). Repeatable.
  --help         Show this message and exit.
```

### CLI dashboard & legend
- Section headers in the live dashboard now inherit accent colours from `cli_layout.v1.json`. When the terminal supports Unicode, subheads use `›` prefixes; ASCII fallbacks swap in `>` automatically.
- Divider rules dim relative to the active block so verbose runs remain readable even with dozens of groups.
- Verbose mode prints a dedicated `Legend` block under `[RENDER]` that explains every token (`key`, `value`, `unit`, `path`) and the new prefixes so operators can map colours to meaning quickly.
- Each run ends with an optional JSON tail (governed by `[cli].emit_json_tail`) that mirrors the human-readable summary for downstream tooling.

### Two-file comparison
```bash
uv run python frame_compare.py --config config.toml --input comparison_videos
```
**Produces:** aligned PNG screenshots (default `screens/`) plus cached metrics (`generated.compframes`) when `analysis.save_frames_data = true`.

**Outputs:**
- Images in `screens/` (or the value of `[screenshots].directory_name`).
- Cached metrics stored alongside the config file.
- `generated.audio_offsets.toml` when `[audio_alignment].enable = true`.

### Multi-file batch (N files)
```bash
uv run python frame_compare.py --config config.toml --input /data/video_batches
```
**Produces:** subdirectories under `screens/` for each comparison set; optional slow.pics upload if `[slowpics].auto_upload = true`.

**Outputs:**
- Per-source screenshots within `screens/<clip>/`.
- Shared cache files (`generated.compframes`, `generated.audio_offsets.toml` when audio alignment runs).

### Random frame selection with seed
```toml
[analysis]
random_frames = 20
random_seed = 123456
```
```bash
uv run python frame_compare.py --config seeded.toml --input comparison_videos
```
**Produces:** deterministic `Random` category frames alongside dark/bright/motion picks.

**Outputs:**
- Frames written to `screens/` with category labels.
- Cached metrics honouring the seed in `generated.compframes`.

### User-selected frames
```toml
[analysis]
user_frames = [10, 200, 501]
```
```bash
uv run python frame_compare.py --config pins.toml --input comparison_videos
```
**Produces:** forced frame captures (10, 200, 501) in the `User` category in addition to other selections.

**Outputs:**
- Screenshots saved under `screens/`.
- Updated cache file if enabled.

### Mixed random + user selection
```toml
[analysis]
user_frames = [10, 200, 501]
random_frames = 8
random_seed = 98765
```
```bash
uv run python frame_compare.py --config mixed.toml --input comparison_videos
```
**Produces:** merged `User` and seeded `Random` frames alongside dark/bright/motion results.

**Outputs:**
- Combined frame set in `screens/`.
- Deterministic cache `generated.compframes` for reuse.

### Determinism & reproducibility
- All random sampling uses `random.Random(random_seed)` so identical configs and inputs yield the same frame order.
- Cached metrics store a config fingerprint and clip metadata; the loader validates hashes, file lists, trims, FPS, and release groups before reuse, guaranteeing identical selections when nothing changed.
- Selection windows derive from computed clip metadata and obey deterministic rounding, so applying the same trims, ignores, and FPS overrides reproduces the same frame subset.

### Performance Tips
- **Minimise pixels processed:** Lower `analysis.downscale_height` to shrink the working resolution or raise `analysis.step` to sample fewer frames when full coverage is unnecessary. Both settings feed directly into the VapourSynth pipeline.
- **Balance motion costs:** Prewitt-based motion scoring (default) adds an extra edge filter pass; flip `analysis.motion_use_absdiff = true` to switch to a cheaper absolute-difference metric if edge sharpness is less important. Reducing `analysis.frame_count_motion` and `motion_diff_radius` shortens motion post-processing.
- **Tone mapping trade-offs:** HDR→SDR conversion (`color.enable_tonemap = true`, `color.tone_curve`) is one of the heavier stages. Disable tonemapping or choose a simpler curve when working with SDR sources or when throughput matters more than HDR fidelity.
- **Leverage caching:** Keep `analysis.save_frames_data = true` so the tool reuses `analysis.frame_data_filename` on subsequent runs. Purge the cache only when footage or config changes.
- **Choose the renderer:** VapourSynth generally offers richer processing but is heavier to initialise. Enable `[screenshots].use_ffmpeg = true` for faster, dependency-light rendering in environments where FFmpeg is already optimised.
- **Memory footprint:** Adjust `runtime.ram_limit_mb` if VapourSynth reports allocation failures; lowering it can prevent thrashing on constrained machines, while increasing it allows larger clips to be analysed in one pass.
- **Parallelism:** The CLI does not expose `--threads`, `--gpu`, or `--device` flags. Instead, rely on the underlying VapourSynth/FFmpeg installations for multithreading, and keep working directories on fast storage to reduce I/O contention.


## Roadmap
- **Must:**
  - Expose dedicated CLI flags for random/user frame selection so documentation and options remain aligned.
  - Add first-class output-format toggles (CSV/JSON grids) to match the documented workflow expectations.
  - add upscaling information to the overlay when performed
  - ensure tonemapping is still applied with a negative trim on an HDR clip
  - refine audio alignment heuristics to better handle per-scene drift
- **Should:**
  - Provide an opt-in GPU/Vulkan path for tone mapping to reduce HDR processing time.
  - Extend motion scoring with optional optical-flow backends for smoother clips.
- **Nice-to-have:**
  - Ship a gallery template that assembles comparison grids from the generated PNGs.
  - Offer a guided slow.pics wizard that validates webhooks before upload.

## Changelog
- **2025-09-29:** README refresh covering installation specifics, configuration reference, metric explanations, usage walkthroughs, outputs, and performance guidance.

## Troubleshooting
| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Config error: analysis.step must be >= 1` (or similar) | TOML value out of range. | Update the value to satisfy the validation listed in the config table.|
| `Config error: source.preferred must be either 'lsmas' or 'ffms2'` | Unsupported VapourSynth source preference. | Change `[source].preferred` to `lsmas` (default) or `ffms2`.|
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
  tmdb.py               # TMDB resolution client
  slowpics.py           # slow.pics client
  utils.py              # Filename metadata helpers
  vs_core.py            # VapourSynth helpers
tests/                  # Pytest suite covering all modules
```

## License
Licensed under the MIT License. See `LICENSE` for details.
