# Frame Compare reference

Supplemental reference material for [`README.md`](../README.md).
Use these tables when you need to fine-tune behaviour beyond the
quick-start configuration paths. For deep dives, see
`docs/audio_alignment_pipeline.md` (alignment) and
`docs/hdr_tonemap_overview.md`/`docs/geometry_pipeline.md`
(pipeline narratives).

Generated defaults (keys, types, and defaults) now live in
[`docs/_generated/config_tables.md`](./_generated/config_tables.md) and
serve as the source of truth for values. These tables are produced by
`tools/gen_config_docs.py`; run `python3 tools/gen_config_docs.py --check
docs/_generated/config_tables.md` whenever `src/datatypes.py` changes to
confirm the generated markdown matches the code, and rerun the script
without `--check` to update the committed table. This page remains
human-edited to explain purpose, intent, and integration tips.

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

### JSON tail

The CLI emits a JSON diagnostics block at the end of every run when `[cli].emit_json_tail` (default true) is enabled; disable the toggle for automation logs that must stay minimal. Example consumer:

```python
import json
import subprocess

result = subprocess.run(
    ["frame-compare", "compare", "--input", "comparison_videos"],
    capture_output=True,
    text=True,
)
tail = json.loads(result.stdout.splitlines()[-1])
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

### Cache performance

- Clip metadata stored in metrics caches only records file size and modification time by default to avoid large file reads.
- Set `FRAME_COMPARE_CACHE_HASH=1` (or pass `compute_sha1=True` into the internal builders) when you explicitly need SHA1 digests in the payload for diagnostics.

### `[analysis.thresholds]`

| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `mode` | Selection strategy: `"quantile"` chooses percentiles, `"fixed_range"` compares against absolute luma bands. | str | `"quantile"` |
| `dark_quantile / bright_quantile` | Percentile thresholds (fractions in `[0,1]`) used when `mode="quantile"`. | float | `0.20 / 0.80` |
| `dark_luma_min / dark_luma_max` | Inclusive brightness band used when `mode="fixed_range"` to tag “dark” scenes. | float | `0.062746 / 0.38` |
| `bright_luma_min / bright_luma_max` | Inclusive brightness band used when `mode="fixed_range"` to tag “bright” scenes. | float | `0.45 / 0.80` |
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
| `[audio_alignment].prompt_reuse_offsets` | Ask before recomputing cached offsets, reusing saved values when declined. | bool | `false` |
| `--audio-align-track label=index` | Force a specific audio stream. | repeatable flag | `None` |
<!-- markdownlint-restore -->

*VSPreview helper notes:* generated scripts log using ASCII arrows to stay compatible with legacy Windows consoles. Overlay text inside the preview still renders with full Unicode glyphs. Switch your console to UTF-8 (`chcp 65001`) or set `PYTHONIOENCODING=UTF-8` for Python-only runs if you prefer Unicode output in logs.

### CLI output hints

- The **Prepare · Audio** panel now mirrors the runtime summary produced after audio alignment completes.  
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
| `[screenshots].compression_level` | PNG compression tier (0 fastest/low, 2 slowest/high). | int | `1` |
| `[screenshots].upscale` | Permit global upscaling. | bool | `true` |
| `[screenshots].single_res` | Fixed output height (0 keeps source). | int | `0` |
| `[screenshots].mod_crop` | Crop modulus. | int | `2` |
| `[screenshots].odd_geometry_policy` | Policy for odd-pixel trims/pads on subsampled SDR (auto, force, or subsamp-safe). | str | `"auto"` |
| `[screenshots].rgb_dither` | Dithering applied during final RGB24 conversion (FFmpeg path forces deterministic ordered when `"error_diffusion"` is requested). | str | `"error_diffusion"` |
| `[screenshots].export_range` | Output range for PNGs (`"full"` expands limited SDR to full-range RGB; `"limited"` keeps video-range output). | str | `"full"` |
| `[screenshots].auto_letterbox_crop` | Auto crop black bars: `"off"` disables, `"basic"` uses cropped geometry for conservative scope detection, `"strict"` keeps the legacy aggressive ratio heuristic. Booleans continue to coerce to `"off"`/`"strict"`. | str \| bool | `"off"` |
| `[screenshots].pad_to_canvas` | Apply padding within `letterbox_px_tolerance` when bars are detected; padding remains centered. | str | `"off"` |
| `[screenshots].letterbox_px_tolerance` | Pixel budget for letterbox/pad detection when `pad_to_canvas` toggles. | int | `8` |
| `[screenshots].center_pad` | Deprecated and ignored; padding is always centered. | bool | `true[^screenshots-deprecated]` |
| `[screenshots].ffmpeg_timeout_seconds` | Per-frame FFmpeg timeout in seconds (must be >= 0; set 0 to disable). | float | `120.0` |
| `[color].enable_tonemap` | HDR→SDR conversion toggle. | bool | `true` |
| `[color].preset` | Tonemapping preset. | str | `"reference"` |
| `[color].dst_min_nits` | Controls HDR toe lift before RGB export. | float | `0.18` |
| `[color].knee_offset` | BT.2390 shoulder adjustment (0–1). | float | `0.50` |
| `[color].dpd_preset` | libplacebo dynamic peak detection profile (`off`, `fast`, `balanced`, `high_quality`). | str | `"high_quality"` |
| `[color].dpd_black_cutoff` | PQ fraction ignored during DPD sampling (0–0.05). | float | `0.01` |
| `[color].smoothing_period` | Frames used by the HDR peak smoothing window (0 disables smoothing). | float | `45.0` |
| `[color].scene_threshold_low` / `scene_threshold_high` | Window (in 1% PQ) that relaxes smoothing on scene changes. | float | `0.8` / `2.4` |
| `[color].percentile` | Brightness percentile considered the scene peak (0–100). | float | `99.995` |
| `[color].contrast_recovery` | High-frequency detail recovery strength. | float | `0.3` |
| `[color].metadata` | Metadata source (`auto`, `none`, `hdr10`, `hdr10+`, `luminance`, or `0-4`). | str\|int | `"auto"` |
| `[color].use_dovi` | Dolby Vision metadata usage (`auto`, `true`, `false`). | str\|bool\|null | `null` |
| `[color].visualize_lut` | Replace output with libplacebo LUT visualisation. | bool | `false` |
| `[color].show_clipping` | Highlight clipped pixels during tonemapping. | bool | `false` |
| `[color].post_gamma_enable` | Enables limited-range post-tonemap gamma lift. | bool | `false` |
| `[color].post_gamma` | Gamma factor applied when the lift is enabled (≈0.90–1.10). | float | `0.95` |
| `[color].overlay_enabled` | Tonemap overlay flag. | bool | `true` |
| `[color].default_matrix_hd` | Preferred matrix code when HD clips omit metadata. | str\|int\|null | `null` |
| `[color].default_matrix_sd` | Preferred matrix code when SD clips omit metadata. | str\|int\|null | `null` |
| `[color].default_primaries_hd` | Preferred primaries code for HD fallback. | str\|int\|null | `null` |
| `[color].default_primaries_sd` | Preferred primaries code for SD fallback. | str\|int\|null | `null` |
| `[color].default_transfer_sdr` | Override SDR transfer function fallback. | str\|int\|null | `null` |
| `[color].default_range_sdr` | Override SDR range fallback (`full` or `limited`). | str\|int\|null | `null` |
| `[color].color_overrides` | Table mapping clip names to `{matrix, primaries, transfer, range}` overrides. | table | `{}` |
<!-- markdownlint-restore -->

Preset highlights:

- `reference` — bt.2390 baseline with smoothing 45f, percentile `99.995`, contrast recovery `0.30`, and `dpd_preset=\"high_quality\"`.
- `bt2390_spec` — spec-faithful bt.2390 variant with neutral cutoff and gentle contrast recovery `0.05`.
- `filmic` — bt.2446a shoulder for softer roll-off and cinematic mid-tones.
- `spline` — smooth spline curve with modest lift (target 105 nits, contrast `0.25`).
- `contrast` — bt.2390 with extra punch (`target_nits=110`, contrast `0.45`) while keeping DPD active.
- `bright_lift` — brightens dim masters (`target_nits=130`, dst_min `0.22`, contrast `0.50`).
- `highlight_guard` — tames harsh highlights (`target_nits=90`, smoothing 50f, contrast `0.15`).

## Slow.pics and metadata automation

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `[slowpics].auto_upload` | Automatically upload runs. | bool | `false` |
| `[slowpics].collection_name` | slow.pics collection label. | str | `""` |
| `[slowpics].collection_suffix` | Optional suffix appended to the collection name for disambiguation. | str | `""` |
| `[slowpics].is_hentai` | Mark uploads as hentai content on slow.pics. | bool | `false` |
| `[slowpics].is_public` | Publish uploads as discoverable. | bool | `true` |
| `[slowpics].tmdb_id` | TMDB identifier. | str | `""` |
| `[slowpics].tmdb_category` | TMDB category hint (`movie` or `tv`). | str | `""` |
| `[slowpics].remove_after_days` | Days before slow.pics deletes the upload (0 keeps forever). | int | `0` |
| `[slowpics].webhook_url` | Notify this webhook when uploads finish. | str | `""` |
| `[slowpics].open_in_browser` | Open slow.pics URLs locally. | bool | `true` |
| `[slowpics].create_url_shortcut` | Create a `.url` shortcut pointing to the slow.pics page. | bool | `true` |
| `[slowpics].delete_screen_dir_after_upload` | Remove PNGs after upload. | bool | `true` |
| `[slowpics].image_upload_timeout_seconds` | Per-image HTTP timeout for uploads. | float | `180.0` |
| `[tmdb].api_key` | Key needed for TMDB lookup. | str | `""` |
| `[tmdb].enable_anime_parsing` | Anime-specific parsing toggle. | bool | `true` |
| `[tmdb].cache_ttl_seconds` | TMDB cache lifetime (seconds). | int | `86400` |
<!-- markdownlint-restore -->

The CLI attempts to save the `.url` shortcut for convenience, but failed writes (permissions, disk pressure, read-only shares) no longer
abort uploads—the JSON tail reports `shortcut_written=false` together with a `shortcut_error` label so UIs can explain the outcome.

TMDB lookups reuse the same workflow for CLI and automation: `tmdb_workflow.resolve_blocking` retries transient HTTP failures via `httpx.HTTPTransport(retries=...)`, `tmdb_workflow.resolve_workflow` (exported via `frame_compare.resolve_tmdb_workflow`) prompts once per run, and `[tmdb].unattended=true` suppresses ambiguity prompts while logging a warning instead of blocking the process. Manual identifiers entered during the prompt (movie/##### or tv/#####) propagate into slow.pics metadata, layout data, and JSON tails.

Network policy: transient statuses {429, 500, 502, 503, 504} backoff; connect=10 s/read=per-upload with a 256 KiB/s baseline plus margin; pooled sessions sized to the worker count.

**Shortcut naming:** uploaded runs create a `.url` file using the resolved collection name (sanitised via `build_shortcut_filename` in `src/frame_compare/slowpics.py:148-164`).  
If the name collapses to an empty string, the CLI falls back to the canonical comparison key; otherwise repeated runs with the same collection name will refresh the same shortcut file—append a suffix in `[slowpics].collection_name` if you need per-run artifacts.

## HTML report viewer

The bundled offline report mirrors slow.pics ergonomics and now includes:

- Filmstrip thumbnails with per-frame selection badges and category filters (labels come from `SelectionDetail`).
- Viewer modes for slider, overlay, difference, and blink comparisons, plus a fullscreen toggle.
- Pointer-anchored zoom controls, fit presets, alignment presets, and persistent viewer state saved in `localStorage` (zoom, fit, mode, alignment, filters).
- Keyboard shortcuts: `Ctrl/Cmd + wheel` to zoom, `Space + drag` to pan, `R` to reset zoom, `D`/`B` to switch modes, and `F` to toggle fullscreen.

## Runtime and environment

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `[paths].input_dir` | Default scan directory under the workspace root. | str | `"comparison_videos"` |
| `[runtime].ram_limit_mb` | VapourSynth RAM ceiling. | int | `8000` |
| `[runtime].vapoursynth_python_paths` | Extra VapourSynth module paths. | list[str] | `[]` |
| `[source].preferred` | Preferred source filter. | str | `"lsmas"` |
| `VAPOURSYNTH_PYTHONPATH` | Environment module path. | str | *(unset)* |
<!-- markdownlint-restore -->

Repository fixtures mirror the default structure and live under
`comparison_videos/` next to `frame_compare.py`; leave them in place when running
from the repo or copy them beneath your chosen `ROOT` (for example
`ROOT/comparison_videos`) if you customise the workspace.

> Need a quick health check after changing `[runtime]` or `[paths]`? Run `frame-compare --diagnose-paths` to confirm the resolved root, media directory, and VapourSynth search paths. The `[runtime]` audit entry in `docs/config_audit.md` covers additional tuning tips the wizard references during setup.

## `[cli]` defaults

These toggles control CLI output independent of per-run flags (`--quiet`, `--json-pretty`, etc.).

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Type | Default |
| --- | --- | --- | --- |
| `[cli].emit_json_tail` | Emit the JSON diagnostics block at the end of each run. Disable when CI logs must stay minimal. | bool | `true` |
| `[cli.progress].style` | Pick progress renderer style (`"fill"` bar vs `"dot"` indicator). Invalid values fall back to `"fill"`. | str | `"fill"` |
<!-- markdownlint-restore -->

**Semantics.**
- “single_res > 0 sets desired canvas height; with upscale=false clips do not upscale (effective height = min(single_res, cropped_h)); with upscale=true clips scale to single_res.”
- “With single_res = 0 and upscale=true, shorter clips upscale to the tallest cropped height; no downscaling occurs.”
- “Padding (pad_to_canvas on/auto) applies within letterbox tolerance; padding is always centered.”
- “Upscaling is bounded so width never exceeds the largest source width.”

Both the wizard and `docs/config_audit.md` highlight scenarios where suppressing the JSON tail or switching the progress style is helpful (for example, in automation harnesses with strict log parsers).

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
CLI flags are kept stable; `tests/runner/test_cli_entry.py` exercises a subset of these options so regressions in flag parsing surface quickly.

## API Reference

`frame_compare.__all__` documents the only names with a stability guarantee. Everything else under `src.frame_compare.*` stays importable for contributors but is explicitly unsupported for downstream consumers.

1. `run_cli`, `main` (`frame_compare.py`) — CLI entrypoints delegating to the runner.
2. `RunRequest`, `RunResult` (`src/frame_compare/runner.py`) — programmatic runner contract.
3. `CLIAppError`, `ScreenshotError` (`src/frame_compare/cli_runtime.py`, `src/frame_compare/render/errors.py`) — user-facing error boundaries.
4. `resolve_tmdb_workflow`, `TMDBLookupResult`, `render_collection_name` (`src/frame_compare/tmdb_workflow.py`) — TMDB helpers for metadata workflows.
5. `prepare_preflight`, `resolve_workspace_root`, `PreflightResult`, `collect_path_diagnostics` (`src/frame_compare/preflight.py`) — workspace + diagnostics helpers.
6. `collect_doctor_checks`, `emit_doctor_results`, `DoctorCheck` (`src/frame_compare/doctor.py`) — doctor workflow helpers.
7. `vs_core` (`src/frame_compare/vs`) — VapourSynth helper alias exposing `ClipInitError`, `ClipProcessError`, `VerificationResult`, and related utilities.

**Deprecation policy:** breaking removals are announced one minor release ahead via the changelog and release notes. Deprecated names raise `DeprecationWarning` for a full release cycle before removal. Stay on the curated list above to receive those warnings and predictable semantics.

### Selection & runtime utilities

`selection.init_clips` boots VapourSynth clips from the `planner` output, `resolve_selection_windows` computes the shared selection windows, and `log_selection_windows` prints the summaries (including warnings when windows collapse). `runtime_utils` offers display helpers such as `format_seconds`, `format_clock`, `fps_to_float`, `fold_sequence`, `evaluate_rule_condition`, and `build_legacy_summary_lines` for formatting CLI banners or JSON metadata.

### Typing & import guidance

`src/frame_compare/py.typed` ships with the package and `typings/frame_compare.pyi` mirrors the curated names, so type checkers (Pyright runs in strict mode for `src/frame_compare`) see the public surface. Always prefer `from frame_compare import ...` and skip `src.*` imports unless you are contributing to those modules directly.

## Overrides (`[overrides]`)

Per-clip trim and FPS adjustments. Keys match clip index, filename (with extension), filename stem, or parsed release group. Values must be integers (frames) or `[num, den]` pairs.

<!-- markdownlint-disable MD013 -->
| Key | Purpose | Example | Default |
| --- | --- | --- | --- |
| `trim` | Shift clip start by N frames (positive trims leading frames). | `{"0" = 120, "EncodeA.mkv" = -24}` | `{}` |
| `trim_end` | Adjust clip end by N frames (negative removes trailing frames). | `{"EncodeB" = -48}` | `{}` |
| `change_fps` | Override FPS per clip. Use `["num","den"]` to set explicit FPS or `"set"` to force reference selection. | `{"1" = [24000,1001], "BonusClip" = "set"}` | `{}` |
<!-- markdownlint-restore -->

See the `[overrides]` section of `docs/config_audit.md` for troubleshooting tips. Mis-typed keys are silently ignored, so prefer descriptive filenames or indices to ensure overrides apply.

## Security & Console Output

- TMDB-derived titles shown in interactive prompts or verbose logs run through `sanitize_console_text` before printing, matching OWASP A07 (Cross-Site Scripting – Output Encoding) guidance so terminal-only output stays safe even when matching/persistence use the raw metadata.

[^screenshots-deprecated]: The autogenerated tables in [`docs/_generated/config_tables.md`](./_generated/config_tables.md) still list `[screenshots].center_pad`; treat this note as the current deprecation warning until the key is removed.
