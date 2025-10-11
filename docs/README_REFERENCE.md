# Frame Compare reference

Supplemental reference material for [`README.md`](../README.md).
Use these tables when you need to fine-tune behaviour beyond the
quick-start configuration paths.

## Analysis settings

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `[analysis].frame_count_dark` | Count of dark-scene frames per run. | int | `20` |
| `[analysis].frame_count_bright` | Bright-scene frame quota. | int | `10` |
| `[analysis].frame_count_motion` | Motion-heavy frames queued. | int | `10` |
| `[analysis].random_frames` | Extra deterministic random frames. | int | `10` |
| `[analysis].user_frames` | Always-rendered frame numbers. | list[int] | `[]` |
| `[analysis].random_seed` | Seed for random selection. | int | `20202020` |
| `[analysis].downscale_height` | Metric computation height cap. | int | `720` |
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
| `[audio_alignment].sample_rate` | Audio extraction rate. | int | `16000` |
| `[audio_alignment].hop_length` | Onset envelope hop length. | int | `512` |
| `[audio_alignment].correlation_threshold` | Minimum accepted score. | float | `0.55` |
| `[audio_alignment].max_offset_seconds` | Offset search window. | float | `12.0` |
| `[audio_alignment].offsets_filename` | Offset output file. | str | `"generated.audio_offsets.toml"` |
| `[audio_alignment].confirm_with_screenshots` | Require preview confirmation. | bool | `true` |
| `[audio_alignment].frame_offset_bias` | Bias toward/away from zero. | int | `1` |
| `--audio-align-track label=index` | Force a specific audio stream. | repeatable flag | `None` |
<!-- markdownlint-restore -->

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
| `[screenshots].auto_letterbox_crop` | Auto crop black bars. | bool | `false` |
| `[color].enable_tonemap` | HDR→SDR conversion toggle. | bool | `true` |
| `[color].preset` | Tonemapping preset. | str | `"reference"` |
| `[color].overlay_enabled` | Tonemap overlay flag. | bool | `true` |
<!-- markdownlint-restore -->

## Slow.pics and metadata automation

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `[slowpics].auto_upload` | Automatically upload runs. | bool | `true` |
| `[slowpics].collection_name` | slow.pics collection label. | str | `""` |
| `[slowpics].tmdb_id` | TMDB identifier. | str | `""` |
| `[slowpics].open_in_browser` | Open slow.pics URLs locally. | bool | `true` |
| `[slowpics].delete_screen_dir_after_upload` | Remove PNGs after upload. | bool | `true` |
| `[tmdb].api_key` | Key needed for TMDB lookup. | str | `""` |
| `[tmdb].enable_anime_parsing` | Anime-specific parsing toggle. | bool | `true` |
| `[tmdb].cache_ttl_seconds` | TMDB cache lifetime (seconds). | int | `86400` |
<!-- markdownlint-restore -->

## Runtime and environment

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `[paths].input_dir` | Default scan directory. | str | `"comparison_videos"` |
| `[runtime].ram_limit_mb` | VapourSynth RAM ceiling. | int | `4000` |
| `[runtime].vapoursynth_python_paths` | Extra VapourSynth module paths. | list[str] | `[]` |
| `[source].preferred` | Preferred source filter. | str | `"lsmas"` |
| `VAPOURSYNTH_PYTHONPATH` | Environment module path. | str | *(unset)* |
<!-- markdownlint-restore -->

## CLI flags

<!-- markdownlint-disable MD013 -->
| Flag | Description | Default |
| --- | --- | --- |
| `--config PATH` | Use a specific configuration file. | `config.toml` |
| `--input PATH` | Override `[paths.input_dir]` for this run. | `None` |
| `--quiet` | Show minimal console output. | `false` |
| `--verbose` | Emit additional diagnostics. | `false` |
| `--no-color` | Disable ANSI colour. | `false` |
| `--json-pretty` | Pretty-print the JSON tail. | `false` |
<!-- markdownlint-restore -->
