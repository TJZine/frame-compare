# Frame Compare reference

Supplemental reference material for [`README.md`](../README.md).
Use these tables when you need to fine-tune behaviour beyond the
quick-start configuration paths.

## CLI helpers

- `frame-compare wizard` — interactive configuration assistant. Prompts for workspace root, input directory, slow.pics settings, audio alignment, and renderer preference. Provide `--preset <name>` when stdin is not a TTY to avoid blocking automation.
- `frame-compare doctor` — quick dependency checklist (VapourSynth, FFmpeg, audio extras, VSPreview, slow.pics, clipboard, config writability). Always exits with 0; add `--json` for machine-readable output.
- `frame-compare preset list` — enumerate packaged presets: `quick-compare`, `hdr-vs-sdr`, `batch-qc`.
- `frame-compare preset apply <name>` — merge the selected preset with the default template and write `config/config.toml` (supports `--root`/`--config` like the primary command).

Preset summaries:

| Preset | Focus |
| --- | --- |
| `quick-compare` | FFmpeg renderer, reduced sampling quotas, slow.pics disabled for fast iterations. |
| `hdr-vs-sdr` | Tonemap verification tightened (stricter thresholds and `color.strict=true`). |
| `batch-qc` | Larger sampling windows and automatic slow.pics uploads for review batches. |

Sample doctor output:

```text
Dependency check:
✅ Config path writable  — /workspace/config/config.toml is writable.
✅ VapourSynth import    — VapourSynth module available.
✅ FFmpeg binaries       — ffmpeg/ffprobe available.
✅ Audio alignment deps  — Optional audio dependencies available.
⚠️ slow.pics network     — [slowpics].auto_upload is enabled. Allow network access to https://slow.pics/ or disable auto_upload.
✅ Clipboard helper      — Clipboard helper optional when slow.pics auto-upload is disabled.
```

## Analysis settings

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `[analysis].frame_count_dark` | Count of dark-scene frames per run. | int | `20` |
| `[analysis].frame_count_bright` | Bright-scene frame quota. | int | `10` |
| `[analysis].frame_count_motion` | Motion-heavy frames queued. | int | `15` |
| `[analysis].random_frames` | Extra deterministic random frames. | int | `15` |
| `[analysis].user_frames` | Always-rendered frame numbers. | list[int] | `[]` |
| `[analysis].random_seed` | Seed for random selection. | int | `20202020` |
| `[analysis].downscale_height` | Metric computation height cap. | int | `480` |
| `[analysis].ignore_lead_seconds` | Seconds trimmed from the start. | float | `0.0` |
| `[analysis].ignore_trail_seconds` | Seconds trimmed from the end. | float | `0.0` |
| `[analysis].min_window_seconds` | Minimum usable footage window. | float | `5.0` |
| `[analysis].frame_data_filename` | Metrics cache path. | str | `"generated.compframes"` |
<!-- markdownlint-restore -->

## Audio alignment

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `[audio_alignment].enable` | Toggle automatic offset detection. | bool | `false` |
| `[audio_alignment].use_vspreview` | Surface offsets as suggestions, launch VSPreview for manual trims, and record the accepted delta (skips launch when non-interactive or VSPreview is missing). | bool | `false` |
| `[audio_alignment].sample_rate` | Audio extraction rate. | int | `16000` |
| `[audio_alignment].hop_length` | Onset envelope hop length. | int | `512` |
| `[audio_alignment].correlation_threshold` | Minimum accepted score. | float | `0.55` |
| `[audio_alignment].max_offset_seconds` | Offset search window. | float | `12.0` |
| `[audio_alignment].offsets_filename` | Offset output file. | str | `"generated.audio_offsets.toml"` |
| `[audio_alignment].confirm_with_screenshots` | Require preview confirmation. | bool | `true` |
| `[audio_alignment].prompt_reuse_offsets` | Ask before recomputing cached offsets, reusing saved values when declined. | bool | `false` |
| `[audio_alignment].frame_offset_bias` | Bias toward/away from zero. | int | `1` |
| `--audio-align-track label=index` | Force a specific audio stream. | repeatable flag | `None` |
<!-- markdownlint-restore -->

*VSPreview helper notes:* generated scripts log using ASCII arrows to stay compatible with legacy Windows consoles. Overlay text inside the preview still renders with full Unicode glyphs. Switch your console to UTF-8 (`chcp 65001`) or set `PYTHONIOENCODING=UTF-8` for Python-only runs if you prefer Unicode output in logs.

### CLI output hints

- The **Prepare · Audio** panel now mirrors the runtime summary produced by `_maybe_apply_audio_alignment` (`frame_compare.py:2620-2735, 4606-4630`).  
- When offsets are reused from disk, the estimation line switches to `Audio offsets reused from existing file (…)` so you can confirm cached trims without digging into logs.  
- Per-clip offset lines include both seconds and frame counts (for example `+0.083s (+2f @ 23.976)`), helping you spot outliers before renders begin.  
- The footer always surfaces the resolved offsets file so you can open or edit `alignment.toml` directly.

## Screenshot rendering

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `[screenshots].directory_name` | Output directory for PNGs. | str | `"screens"` |
| `[screenshots].use_ffmpeg` | Prefer FFmpeg for captures. | bool | `false` |
| `[screenshots].add_frame_info` | Overlay frame metadata. | bool | `true` |
| `[screenshots].upscale` | Permit global upscaling. | bool | `true` |
| `[screenshots].single_res` | Fixed output height (0 keeps source). | int | `0` |
| `[screenshots].mod_crop` | Crop modulus. | int | `2` |
| `[screenshots].odd_geometry_policy` | Policy for odd-pixel trims/pads on subsampled SDR (auto, force, or subsamp-safe). | str | `"auto"` |
| `[screenshots].rgb_dither` | Dithering applied during final RGB24 conversion (FFmpeg path forces deterministic ordered when `"error_diffusion"` is requested). | str | `"error_diffusion"` |
| `[screenshots].auto_letterbox_crop` | Auto crop black bars. | bool | `false` |
| `[screenshots].ffmpeg_timeout_seconds` | Per-frame FFmpeg timeout in seconds (must be >= 0; set 0 to disable). | float | `120.0` |
| `[color].enable_tonemap` | HDR→SDR conversion toggle. | bool | `true` |
| `[color].preset` | Tonemapping preset. | str | `"reference"` |
| `[color].overlay_enabled` | Tonemap overlay flag. | bool | `true` |
| `[color].default_matrix_hd` | Preferred matrix code when HD clips omit metadata. | str\|int\|null | `null` |
| `[color].default_matrix_sd` | Preferred matrix code when SD clips omit metadata. | str\|int\|null | `null` |
| `[color].default_primaries_hd` | Preferred primaries code for HD fallback. | str\|int\|null | `null` |
| `[color].default_primaries_sd` | Preferred primaries code for SD fallback. | str\|int\|null | `null` |
| `[color].default_transfer_sdr` | Override SDR transfer function fallback. | str\|int\|null | `null` |
| `[color].default_range_sdr` | Override SDR range fallback (`full` or `limited`). | str\|int\|null | `null` |
| `[color].color_overrides` | Table mapping clip names to `{matrix, primaries, transfer, range}` overrides. | table | `{}` |
<!-- markdownlint-restore -->

## Slow.pics and metadata automation

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `[slowpics].auto_upload` | Automatically upload runs. | bool | `false` |
| `[slowpics].collection_name` | slow.pics collection label. | str | `""` |
| `[slowpics].tmdb_id` | TMDB identifier. | str | `""` |
| `[slowpics].open_in_browser` | Open slow.pics URLs locally. | bool | `true` |
| `[slowpics].delete_screen_dir_after_upload` | Remove PNGs after upload. | bool | `true` |
| `[tmdb].api_key` | Key needed for TMDB lookup. | str | `""` |
| `[tmdb].enable_anime_parsing` | Anime-specific parsing toggle. | bool | `true` |
| `[tmdb].cache_ttl_seconds` | TMDB cache lifetime (seconds). | int | `86400` |
<!-- markdownlint-restore -->

**Shortcut naming:** uploaded runs create a `.url` file using the resolved collection name (sanitised via `build_shortcut_filename` in `src/slowpics.py:148-164`).  
If the name collapses to an empty string, the CLI falls back to the canonical comparison key; otherwise repeated runs with the same collection name will refresh the same shortcut file—append a suffix in `[slowpics].collection_name` if you need per-run artifacts.

## Runtime and environment

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `[paths].input_dir` | Default scan directory under the workspace root. | str | `"comparison_videos"` |
| `[runtime].ram_limit_mb` | VapourSynth RAM ceiling. | int | `4000` |
| `[runtime].vapoursynth_python_paths` | Extra VapourSynth module paths. | list[str] | `[]` |
| `[source].preferred` | Preferred source filter. | str | `"lsmas"` |
| `VAPOURSYNTH_PYTHONPATH` | Environment module path. | str | *(unset)* |
<!-- markdownlint-restore -->

Repository fixtures mirror the default structure and live under
`comparison_videos/` next to `frame_compare.py`; leave them in place when running
from the repo or copy them beneath your chosen `ROOT` (for example
`ROOT/comparison_videos`) if you customise the workspace.

## CLI flags

<!-- markdownlint-disable MD013 -->
| Flag | Description | Default |
| --- | --- | --- |
| `--root PATH` | Workspace root override (else sentinel discovery). | `None` |
| `--config PATH` | Use a specific configuration file. | ``$FRAME_COMPARE_CONFIG`` or ``ROOT/config/config.toml`` |
| `--input PATH` | Override `[paths].input_dir` within the root. | `None` |
| `--write-config` | Ensure `ROOT/config/config.toml` exists then exit. | `false` |
| `--quiet` | Show minimal console output. | `false` |
| `--verbose` | Emit additional diagnostics. | `false` |
| `--no-color` | Disable ANSI colour. | `false` |
| `--json-pretty` | Pretty-print the JSON tail. | `false` |
<!-- markdownlint-restore -->
> The CLI refuses workspace roots inside `site-packages`/`dist-packages`, seeds `ROOT/config/config.toml` when missing, validates writability before running, and blocks derived paths from escaping the workspace. Use `--diagnose-paths` to inspect the resolved locations.
