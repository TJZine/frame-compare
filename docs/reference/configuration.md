# Configuration

## How settings combine

Settings take precedence in this order, highest first: run options, environment
variables, the TOML file, and built-in defaults. The default file is
`config/config.toml` under the workspace root. Unknown top-level tables are ignored;
an unknown key inside a Frame Compare table fails validation. Use the wizard for
common settings and edit TOML for the rest. See [config validation](../current-cli-contract.md#config-validation-logging-and-migration).

## Environment variables and secrets

Environment variable names are `FRAME_COMPARE_` plus the table and key joined by
`__`, in upper case: `FRAME_COMPARE_SLOWPICS__WEBHOOK_URL`,
`FRAME_COMPARE_TMDB__API_KEY`, and `FRAME_COMPARE_SLOWPICS__AUTO_UPLOAD`. Keep
secrets in the environment; generated config and preset files never contain
`slowpics.webhook_url` or `tmdb.api_key`, and every configuration error shows their
values as `<redacted>`.

```bash
export FRAME_COMPARE_SLOWPICS__WEBHOOK_URL="<secret>"
```

## Paths

`[paths]` is explained in [Presets, history, and generated data](../guides/presets-history-generated-data.md).

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `paths.input_dir` | path | `"comparison_videos"` | Directory searched for sources; may be outside the workspace root |
| `paths.generated_dir` | path | `"generated"` | Generated-data root for run folders and shared caches; may be outside the workspace root |
| `paths.config_dir` | path | `"config"` | Configuration directory; must stay inside the workspace root |

## Runtime

`[runtime]` controls VapourSynth's frame cache.

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `runtime.memory_limit_mb` | integer, at least `512` | unset | VapourSynth frame-cache cap in MiB for analysis, rendering, alignment checks, and the VSView session |

The cap applies to VapourSynth's frame cache, not to total process memory, and does
not affect audio alignment buffers. A smaller cache can increase decoding work.

```toml
[runtime]
memory_limit_mb = 4096
```

## Sources

`[sources]` is explained in [Sources, references, and labels](../guides/sources-and-labels.md).

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `sources.reference` | selector, `"auto"`, or unset | unset (first discovered source) | Which source is the reference |
| `sources.analysis_source` | `"reference"`, `"fastest"`, or a selector | `"reference"` | Source used for luminance and motion metrics |
| `sources.match_fps` | `"disabled"`, `"assume_reference"`, `"majority"` | `"disabled"` | Common frame-rate interpretation policy |
| `sources.label_mode` | `"stem"`, `"filename"`, `"parsed"` | `"stem"` | How automatic labels are built |
| `sources.label_parser` | `"auto"`, `"guessit"`, `"anitopy"` | `"auto"` | Release-name parser for `parsed` labels |
| `sources.overrides` | table of selector tables | empty | Per-source settings in the rows below |
| `sources.overrides.<selector>.trim_start_frames` | integer, at least `0` | `0` | Frames removed from the start of that source |
| `sources.overrides.<selector>.trim_end_frames` | integer, at least `0` | `0` | Frames removed from the end of that source |
| `sources.overrides.<selector>.active_rect` | `{ x, y, width, height }` | unset | Explicit active picture; must fit the source |
| `sources.overrides.<selector>.effective_fps` | `"num/den"` | unset | Frame rate used to interpret that source's timing |
| `sources.overrides.<selector>.label` | text | unset | Exact label for that source |

## Analysis

`[analysis]` is explained in [Frame selection and analysis](../guides/analysis-modes.md).

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `analysis.user_frames` | list of integers, at least `0` | `[]` | Reference source frames to render |
| `analysis.random_frame_count` | integer, at least `0` | `10` | Seeded random frames |
| `analysis.dark_frame_count` | integer, at least `0` | `0` | Darkest frames; needs metrics |
| `analysis.bright_frame_count` | integer, at least `0` | `0` | Brightest frames; needs metrics |
| `analysis.motion_frame_count` | integer, at least `0` | `0` | Highest-motion frames; needs metrics |
| `analysis.random_seed` | integer | `42` | Seed for random selection |
| `analysis.performance_mode` | `"quality"`, `"performance"` | `"quality"` | Every eligible frame, or a deterministic sample |
| `analysis.ignore_lead_seconds` | number, at least `0` | `0.0` | Seconds at the start excluded from selection |
| `analysis.ignore_trail_seconds` | number, at least `0` | `0.0` | Seconds at the end excluded from selection |
| `analysis.min_window_seconds` | number, at least `0` | `5.0` | Minimum selectable window; a shorter window is extended within the source |
| `analysis.dark_quantile` | `0.0` to `0.5` | `0.05` | Luminance quantile treated as dark |
| `analysis.bright_quantile` | `0.5` to `1.0` | `0.95` | Luminance quantile treated as bright |

User frames and the four counts must request at least 1 and at most 100 frames in
total.

## Audio alignment

`[audio_alignment]` is explained in [Audio alignment](../guides/audio-alignment.md)
and [VSView alignment review](../guides/vsview-review.md).

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `audio_alignment.enable` | `true`, `false` | `true` | Run audio alignment |
| `audio_alignment.max_offset_seconds` | number, at least `1` | `30.0` | Largest offset searched in either direction |
| `audio_alignment.use_vsview` | `true`, `false` | `false` | Open the VSView alignment panel after alignment |
| `audio_alignment.force_interactive` | `true`, `false` | `false` | Require a successful panel review |
| `audio_alignment.cache_results` | `true`, `false` | `true` | Store applied and confirmed offsets for reuse |
| `audio_alignment.previous_offsets` | `"disabled"`, `"prompt"`, `"always"` | `"disabled"` | Reuse of previously confirmed offsets |
| `audio_alignment.channel_strategy` | `"mono_downmix"`, `"best_channel"` | `"mono_downmix"` | Channel handling during audio extraction |
| `audio_alignment.reference_stream` | integer, at least `0`, or unset | unset | Reference audio stream number |
| `audio_alignment.comparison_streams` | table of stem = stream number | empty | Comparison audio stream numbers by filename stem |

## Screenshots

`[screenshots]` is explained in [Reports and overlays](../guides/reports-and-overlays.md)
and the contract's [screenshot surface](../current-cli-contract.md#config-only-screenshot-surface).

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `screenshots.use_ffmpeg` | `true`, `false` | `false` | Render with FFmpeg instead of VapourSynth; HDR sources then need `color.enable_tonemap = false` |
| `screenshots.overlay_mode` | `"minimal"`, `"standard"`, `"diagnostic"`, `"none"` | `"standard"` | Baked overlay detail |
| `screenshots.include_frame_number` | `true`, `false` | `true` | Include the frame number in baked overlays |
| `screenshots.png_compression` | `0` to `9` | `6` | PNG compression level |
| `screenshots.ffmpeg_timeout_seconds` | number, at least `5` | `30.0` | Timeout for FFmpeg frame extraction |
| `screenshots.geometry_mode` | `"native"`, `"aligned"` | `"native"` | Keep native frames, or scale sources onto one canvas |
| `screenshots.active_rect_detection` | `"provided"`, `"dimension"`, `"aspect_ratio"`, `"auto"` | `"auto"` | Evidence used to find the active picture |
| `screenshots.aligned_scale_policy` | `"largest_active"`, `"smallest_active"`, `"reference_active"`, `"explicit_size"` | `"largest_active"` | Canvas size in aligned mode |
| `screenshots.aligned_target_width` | positive even integer, or unset | unset | Canvas width for `explicit_size` |
| `screenshots.aligned_target_height` | positive even integer, or unset | unset | Canvas height for `explicit_size` |
| `screenshots.vs_writer` | `"auto"`, `"pillow"`, `"fpng"` | `"auto"` | VapourSynth PNG writer |

## Color

`[color]` is explained in [HDR and tonemapping](../guides/hdr-tonemapping.md).

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `color.enable_tonemap` | `true`, `false` | `true` | Tonemap HDR sources to SDR |
| `color.preset` | `"reference"`, `"filmic"`, `"contrast"`, `"bt2390_spec"`, `"spline"`, `"bright_lift"`, `"highlight_guard"` | `"reference"` | Baseline tonemap settings |
| `color.target_nits` | integer, `100` to `1000` | from the preset | Output target luminance |
| `color.tone_curve` | `"bt2390"`, `"spline"`, `"reinhard"` | from the preset | Tone curve |
| `color.gamma_lift` | `true`, `false` | from the preset | Brighten midtones after tonemapping |
| `color.contrast_recovery` | `0.0` to `1.0` | `0.3` | Contrast recovery strength |

`target_nits`, `tone_curve`, `gamma_lift`, and `contrast_recovery` override the
preset only when explicitly supplied in the configuration file or environment variables.

## Report

`[report]` is explained in [Reports and overlays](../guides/reports-and-overlays.md).

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `report.enable` | `true`, `false` | `true` | Write `report.html` |
| `report.default_mode` | `"slider"`, `"overlay"`, `"diff"`, `"blink"` | `"slider"` | View the report opens in; `overlay` is the Single view |
| `report.include_filmstrip` | `true`, `false` | `true` | Show the filmstrip |
| `report.embed_images` | `true`, `false` | `false` | Embed screenshots in `report.html` |
| `report.auto_open` | `true`, `false` | `true` | Open the report after an interactive local run |

## slow.pics

`[slowpics]` is explained in [Publishing and webhooks](../guides/publishing-and-webhooks.md)
and the contract's [slow.pics surface](../current-cli-contract.md#config-only-slowpics-surface).

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `slowpics.auto_upload` | `true`, `false` | `false` | Upload after a successful run |
| `slowpics.confirm_upload_after_report` | `true`, `false` | `false` | Ask after the report is written; interactive runs only |
| `slowpics.visibility` | `"public"`, `"unlisted"` | `"public"` | Collection visibility |
| `slowpics.delete_after_upload` | `true`, `false` | `false` | Delete the uploaded local screenshots after the report is done |
| `slowpics.timeout_seconds` | number, at least `10` | `60.0` | Navigation and metadata request timeout |
| `slowpics.max_retries` | `1` to `10` | `3` | Retry budget per request |
| `slowpics.title` | text | `""` | Literal collection title |
| `slowpics.title_template` | template text | `""` | Title built from `${Title}` and other fields; not with `title` |
| `slowpics.title_suffix` | text | `""` | Text appended to the title |
| `slowpics.is_hentai` | `true`, `false` | `false` | slow.pics adult-content flag |
| `slowpics.tmdb_id` | positive integer, or unset | unset | TMDB ID for the collection; needs `tmdb_media_type` |
| `slowpics.tmdb_media_type` | `"movie"`, `"tv"`, or unset | unset | TMDB category for `tmdb_id` |
| `slowpics.remove_after_days` | `0` to `999999` | `0` | Days until slow.pics removes the collection; `0` keeps it |
| `slowpics.image_upload_timeout_seconds` | number, at least `10` | `180.0` | Minimum image upload timeout |
| `slowpics.copy_url_to_clipboard` | `true`, `false` | `true` | Copy the collection URL after upload |
| `slowpics.open_in_browser` | `true`, `false` | `true` | Open the collection URL after upload |
| `slowpics.create_url_shortcut` | `true`, `false` | `true` | Write a `.url` shortcut after upload |
| `slowpics.webhook_url` | HTTPS URL, or unset | unset | Discord-compatible webhook for the collection URL; keep it in the environment |

## TMDB

`[tmdb]` controls the optional TMDB metadata lookup; see the [run command contract](../current-cli-contract.md#run-command-contract).

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `tmdb.api_key` | text, or unset | unset | TMDB API key; keep it in the environment |
| `tmdb.enabled` | `true`, `false` | `true` | Look up TMDB metadata |
| `tmdb.unattended` | `true`, `false` | `false` | Never prompt for an unresolved match |
| `tmdb.timeout_seconds` | number, at least `1` | `10.0` | Request timeout |
| `tmdb.year_tolerance` | `0` to `5` | `2` | Release-year difference accepted for a match |
| `tmdb.category_preference` | `"movie"`, `"tv"`, or unset | unset | Category preferred when a title is ambiguous |

## Logging

`[logging]` controls run log output.

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `logging.level` | `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` | `"INFO"` | Log level; `--quiet` and `--verbose` override it |
| `logging.format` | `"console"`, `"json"` | `"console"` | Log format |

`--quiet` and `--verbose` override the level for one run.
