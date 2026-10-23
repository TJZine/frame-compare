---
description: Every configuration key with its values, its default, and what it changes.
---

# Configuration

Every key Frame Compare reads from `config/config.toml`, with its values, its default,
and what it changes.

## How settings combine

Settings take precedence in this order, highest first:

1. Run options
2. Environment variables
3. The TOML file
4. Built-in defaults

The default file is `config/config.toml` under the workspace root. Unknown top-level
tables are ignored; an unknown key inside a Frame Compare table fails validation.

Use the wizard for common settings and edit TOML for the rest. See [config validation](../current-cli-contract.md#config-validation-logging-and-migration).

## Environment variables and secrets

Environment variable names are `FRAME_COMPARE_` plus the table and key joined by
`__`, in upper case: `FRAME_COMPARE_SLOWPICS__WEBHOOK_URL`,
`FRAME_COMPARE_TMDB__API_KEY`, and `FRAME_COMPARE_SLOWPICS__AUTO_UPLOAD`. Keep
secrets in the environment; generated config and preset files never contain
`slowpics.webhook_url` or `tmdb.api_key`, and every configuration error shows their
values as `<redacted>`.

```bash title="Shell"
export FRAME_COMPARE_SLOWPICS__WEBHOOK_URL="<secret>"
```

## Paths

`[paths]` is explained in [Presets, history, and generated data](../guides/presets-history-generated-data.md).

#### `paths.input_dir` { #paths.input_dir .fc-key }

Values
:   path

Default
:   `"comparison_videos"`

Directory searched for sources; may be outside the workspace root.

#### `paths.generated_dir` { #paths.generated_dir .fc-key }

Values
:   path

Default
:   `"generated"`

Generated-data root for run folders and shared caches; may be outside the workspace root.

#### `paths.config_dir` { #paths.config_dir .fc-key }

Values
:   path

Default
:   `"config"`

Configuration directory; must stay inside the workspace root.

## Runtime

`[runtime]` controls VapourSynth's frame cache.

#### `runtime.memory_limit_mb` { #runtime.memory_limit_mb .fc-key }

Values
:   integer, at least `512`

Default
:   unset

VapourSynth frame-cache cap in MiB for analysis, rendering, alignment checks, and the VSView session.

The cap limits only VapourSynth's frame cache. Total process memory and audio alignment
buffers are outside this limit. A smaller cache can increase decoding work.

```toml
[runtime]
memory_limit_mb = 4096
```

## Sources

`[sources]` is explained in [Sources, references, and labels](../guides/sources-and-labels.md).

#### `sources.reference` { #sources.reference .fc-key }

Values
:   selector, `"auto"`, or unset

Default
:   unset (first discovered source)

Which source is the reference.

#### `sources.analysis_source` { #sources.analysis_source .fc-key }

Values
:   `"reference"`, `"fastest"`, or a selector

Default
:   `"reference"`

Source used for luminance and motion metrics.

#### `sources.match_fps` { #sources.match_fps .fc-key }

Values
:   `"disabled"`, `"assume_reference"`, `"majority"`

Default
:   `"disabled"`

How a common frame rate is chosen when sources disagree.

#### `sources.label_mode` { #sources.label_mode .fc-key }

Values
:   `"stem"`, `"filename"`, `"parsed"`

Default
:   `"stem"`

How automatic labels are built.

#### `sources.label_parser` { #sources.label_parser .fc-key }

Values
:   `"auto"`, `"guessit"`, `"anitopy"`

Default
:   `"auto"`

Release-name parser for `parsed` labels.

#### `sources.overrides` { #sources.overrides .fc-key }

Values
:   table of selector tables

Default
:   empty

Per-source settings in the key blocks below.

#### `sources.overrides.<selector>.trim_start_frames` { #sources.overrides.selector.trim_start_frames .fc-key }

Values
:   integer, at least `0`

Default
:   `0`

Frames removed from the start of that source.

#### `sources.overrides.<selector>.trim_end_frames` { #sources.overrides.selector.trim_end_frames .fc-key }

Values
:   integer, at least `0`

Default
:   `0`

Frames removed from the end of that source.

#### `sources.overrides.<selector>.active_rect` { #sources.overrides.selector.active_rect .fc-key }

Values
:   `{ x, y, width, height }`

Default
:   unset

Explicit active picture; must fit the source.

#### `sources.overrides.<selector>.effective_fps` { #sources.overrides.selector.effective_fps .fc-key }

Values
:   `"num/den"`

Default
:   unset

Frame rate used to interpret that source's timing.

#### `sources.overrides.<selector>.label` { #sources.overrides.selector.label .fc-key }

Values
:   text

Default
:   unset

Exact label for that source.

## Analysis

`[analysis]` is explained in [Frame selection and analysis](../guides/analysis-modes.md).

#### `analysis.user_frames` { #analysis.user_frames .fc-key }

Values
:   list of integers, at least `0`

Default
:   `[]`

Reference source frames to render.

#### `analysis.random_frame_count` { #analysis.random_frame_count .fc-key }

Values
:   integer, at least `0`

Default
:   `10`

Seeded random frames.

#### `analysis.dark_frame_count` { #analysis.dark_frame_count .fc-key }

Values
:   integer, at least `0`

Default
:   `0`

Darkest frames; needs metrics.

#### `analysis.bright_frame_count` { #analysis.bright_frame_count .fc-key }

Values
:   integer, at least `0`

Default
:   `0`

Brightest frames; needs metrics.

#### `analysis.motion_frame_count` { #analysis.motion_frame_count .fc-key }

Values
:   integer, at least `0`

Default
:   `0`

Highest-motion frames; needs metrics.

#### `analysis.random_seed` { #analysis.random_seed .fc-key }

Values
:   integer

Default
:   `42`

Seed for random selection.

#### `analysis.performance_mode` { #analysis.performance_mode .fc-key }

Values
:   `"quality"`, `"performance"`

Default
:   `"quality"`

Every eligible frame, or a deterministic sample.

#### `analysis.ignore_lead_seconds` { #analysis.ignore_lead_seconds .fc-key }

Values
:   number, at least `0`

Default
:   `0.0`

Seconds at the start excluded from selection.

#### `analysis.ignore_trail_seconds` { #analysis.ignore_trail_seconds .fc-key }

Values
:   number, at least `0`

Default
:   `0.0`

Seconds at the end excluded from selection.

#### `analysis.min_window_seconds` { #analysis.min_window_seconds .fc-key }

Values
:   number, at least `0`

Default
:   `5.0`

Minimum selectable window; a shorter window is extended within the source.

#### `analysis.dark_quantile` { #analysis.dark_quantile .fc-key }

Values
:   `0.0` to `0.5`

Default
:   `0.05`

Luminance quantile treated as dark.

#### `analysis.bright_quantile` { #analysis.bright_quantile .fc-key }

Values
:   `0.5` to `1.0`

Default
:   `0.95`

Luminance quantile treated as bright.

User frames and the four counts must request at least 1 and at most 100 frames in
total.

## Audio alignment

`[audio_alignment]` is explained in [Audio alignment](../guides/audio-alignment.md)
and [VSView alignment review](../guides/vsview-review.md).

#### `audio_alignment.enable` { #audio_alignment.enable .fc-key }

Values
:   `true`, `false`

Default
:   `true`

Run audio alignment.

#### `audio_alignment.max_offset_seconds` { #audio_alignment.max_offset_seconds .fc-key }

Values
:   number, at least `1`

Default
:   `30.0`

Largest offset searched in either direction.

#### `audio_alignment.use_vsview` { #audio_alignment.use_vsview .fc-key }

Values
:   `true`, `false`

Default
:   `false`

Open the VSView alignment panel after alignment.

#### `audio_alignment.force_interactive` { #audio_alignment.force_interactive .fc-key }

Values
:   `true`, `false`

Default
:   `false`

Require a successful panel review.

#### `audio_alignment.cache_results` { #audio_alignment.cache_results .fc-key }

Values
:   `true`, `false`

Default
:   `true`

Store applied and confirmed offsets for reuse.

#### `audio_alignment.previous_offsets` { #audio_alignment.previous_offsets .fc-key }

Values
:   `"disabled"`, `"prompt"`, `"always"`

Default
:   `"disabled"`

Reuse of previously confirmed offsets.

#### `audio_alignment.channel_strategy` { #audio_alignment.channel_strategy .fc-key }

Values
:   `"mono_downmix"`, `"best_channel"`

Default
:   `"mono_downmix"`

Channel handling during audio extraction.

#### `audio_alignment.reference_stream` { #audio_alignment.reference_stream .fc-key }

Values
:   integer, at least `0`, or unset

Default
:   unset

Reference audio stream number.

#### `audio_alignment.comparison_streams` { #audio_alignment.comparison_streams .fc-key }

Values
:   table of stem = stream number

Default
:   empty

Comparison audio stream numbers by filename stem.

## Screenshots

`[screenshots]` is explained in [Reports and overlays](../guides/reports-and-overlays.md)
and the contract's [screenshot surface](../current-cli-contract.md#config-only-screenshot-surface).

#### `screenshots.use_ffmpeg` { #screenshots.use_ffmpeg .fc-key }

Values
:   `true`, `false`

Default
:   `false`

Render with FFmpeg instead of VapourSynth; HDR sources then need `color.enable_tonemap = false`.

#### `screenshots.overlay_mode` { #screenshots.overlay_mode .fc-key }

Values
:   `"minimal"`, `"standard"`, `"diagnostic"`, `"none"`

Default
:   `"standard"`

Baked overlay detail.

#### `screenshots.include_frame_number` { #screenshots.include_frame_number .fc-key }

Values
:   `true`, `false`

Default
:   `true`

Include the frame number in baked overlays.

#### `screenshots.png_compression` { #screenshots.png_compression .fc-key }

Values
:   `0` to `9`

Default
:   `6`

PNG compression level.

#### `screenshots.ffmpeg_timeout_seconds` { #screenshots.ffmpeg_timeout_seconds .fc-key }

Values
:   finite number, at least `5`

Default
:   `30.0`

Timeout for FFmpeg frame extraction.

#### `screenshots.geometry_mode` { #screenshots.geometry_mode .fc-key }

Values
:   `"native"`, `"aligned"`

Default
:   `"native"`

Keep native frames, or scale sources onto one canvas.

#### `screenshots.active_rect_detection` { #screenshots.active_rect_detection .fc-key }

Values
:   `"provided"`, `"dimension"`, `"aspect_ratio"`, `"auto"`

Default
:   `"auto"`

Evidence used to find the active picture.

#### `screenshots.aligned_scale_policy` { #screenshots.aligned_scale_policy .fc-key }

Values
:   `"largest_active"`, `"smallest_active"`, `"reference_active"`, `"explicit_size"`

Default
:   `"largest_active"`

Canvas size in aligned mode.

#### `screenshots.aligned_target_width` { #screenshots.aligned_target_width .fc-key }

Values
:   positive even integer, or unset

Default
:   unset

Canvas width for `explicit_size`.

#### `screenshots.aligned_target_height` { #screenshots.aligned_target_height .fc-key }

Values
:   positive even integer, or unset

Default
:   unset

Canvas height for `explicit_size`.

#### `screenshots.vs_writer` { #screenshots.vs_writer .fc-key }

Values
:   `"auto"`, `"pillow"`, `"fpng"`

Default
:   `"auto"`

VapourSynth PNG writer.

## Color

`[color]` is explained in [HDR and tonemapping](../guides/hdr-tonemapping.md).

#### `color.enable_tonemap` { #color.enable_tonemap .fc-key }

Values
:   `true`, `false`

Default
:   `true`

Tonemap HDR sources to SDR.

#### `color.preset` { #color.preset .fc-key }

Values
:   `"reference"`, `"filmic"`, `"contrast"`, `"bt2390_spec"`, `"spline"`, `"bright_lift"`, `"highlight_guard"`, `"highlight_preserve"`

Default
:   `"reference"`

Baseline tonemap settings.

#### `color.tonemap_speed` { #color.tonemap_speed .fc-key }

Values
:   `"quality"`, `"fast"`

Default
:   `"quality"`

Choose the source-peak policy for HDR tonemapping. `"quality"` measures the peak
for each screenshot. `"fast"` disables dynamic peak detection and uses available
stream or static metadata, falling back to the configured or default source peak.
Fast mode is reproducible and shares native state across screenshots, but it can
look different from quality mode and depends on HDR metadata.

#### `color.target_nits` { #color.target_nits .fc-key }

Values
:   integer, `100` to `1000`

Default
:   from the preset

Output target luminance.

#### `color.tone_curve` { #color.tone_curve .fc-key }

Values
:   `"bt2390"`, `"spline"`, `"reinhard"`

Default
:   from the preset

Tone curve.

#### `color.gamma_lift` { #color.gamma_lift .fc-key }

Values
:   `true`, `false`

Default
:   from the preset

Brighten midtones after tonemapping.

#### `color.contrast_recovery` { #color.contrast_recovery .fc-key }

Values
:   `0.0` to `1.0`

Default
:   `0.3`

Contrast recovery strength.

Explicit configuration or environment values for `target_nits`, `tone_curve`,
`gamma_lift`, and `contrast_recovery` override the preset baseline. `--tm-target`
and `--tm-curve` override `target_nits` and `tone_curve` for one run and take
precedence over configuration and environment values.

`tonemap_speed` is independent of the preset and persists as an ordinary color
field. Configuration and environment values set its baseline; `--tm-speed` takes
precedence for one run.

`gamma_lift` and `contrast_recovery` can be set only through configuration or
environment variables;
they have no corresponding CLI flags. `--tm-preset` changes the preset baseline;
explicitly supplied field overrides still take precedence.

## Report

`[report]` is explained in [Reports and overlays](../guides/reports-and-overlays.md).

#### `report.enable` { #report.enable .fc-key }

Values
:   `true`, `false`

Default
:   `true`

Write `report.html`.

#### `report.default_mode` { #report.default_mode .fc-key }

Values
:   `"slider"`, `"overlay"`, `"diff"`, `"blink"`

Default
:   `"slider"`

View the report opens in; `overlay` is the Single view.

#### `report.include_filmstrip` { #report.include_filmstrip .fc-key }

Values
:   `true`, `false`

Default
:   `true`

Show the filmstrip.

#### `report.embed_images` { #report.embed_images .fc-key }

Values
:   `true`, `false`

Default
:   `false`

Embed screenshots in `report.html`.

#### `report.auto_open` { #report.auto_open .fc-key }

Values
:   `true`, `false`

Default
:   `true`

Open the report after an interactive local run.

## slow.pics

`[slowpics]` is explained in [Publishing and webhooks](../guides/publishing-and-webhooks.md)
and the contract's [slow.pics surface](../current-cli-contract.md#config-only-slowpics-surface).

#### `slowpics.auto_upload` { #slowpics.auto_upload .fc-key }

Values
:   `true`, `false`

Default
:   `false`

Upload after a successful run.

#### `slowpics.confirm_upload_after_report` { #slowpics.confirm_upload_after_report .fc-key }

Values
:   `true`, `false`

Default
:   `false`

Ask after the report is written; interactive runs only.

#### `slowpics.visibility` { #slowpics.visibility .fc-key }

Values
:   `"public"`, `"unlisted"`

Default
:   `"public"`

Collection visibility.

#### `slowpics.delete_after_upload` { #slowpics.delete_after_upload .fc-key }

Values
:   `true`, `false`

Default
:   `false`

Delete the uploaded local screenshots after the report is done.

#### `slowpics.timeout_seconds` { #slowpics.timeout_seconds .fc-key }

Values
:   finite number, at least `10`

Default
:   `60.0`

Navigation and metadata request timeout.

#### `slowpics.max_retries` { #slowpics.max_retries .fc-key }

Values
:   `1` to `10`

Default
:   `3`

Retry budget per request.

#### `slowpics.title` { #slowpics.title .fc-key }

Values
:   text

Default
:   `""`

Literal collection title.

#### `slowpics.title_template` { #slowpics.title_template .fc-key }

Values
:   template text

Default
:   `""`

Title built from `${Title}` and other fields; not with `title`.

#### `slowpics.title_suffix` { #slowpics.title_suffix .fc-key }

Values
:   text

Default
:   `""`

Text appended to the title.

#### `slowpics.is_hentai` { #slowpics.is_hentai .fc-key }

Values
:   `true`, `false`

Default
:   `false`

slow.pics adult-content flag.

#### `slowpics.tmdb_id` { #slowpics.tmdb_id .fc-key }

Values
:   positive integer, or unset

Default
:   unset

TMDB ID for the collection; needs `tmdb_media_type`.

#### `slowpics.tmdb_media_type` { #slowpics.tmdb_media_type .fc-key }

Values
:   `"movie"`, `"tv"`, or unset

Default
:   unset

TMDB category for `tmdb_id`.

#### `slowpics.remove_after_days` { #slowpics.remove_after_days .fc-key }

Values
:   `0` to `999999`

Default
:   `0`

Days until slow.pics removes the collection; `0` keeps it.

#### `slowpics.image_upload_timeout_seconds` { #slowpics.image_upload_timeout_seconds .fc-key }

Values
:   finite number, at least `10`

Default
:   `180.0`

Minimum image upload timeout.

#### `slowpics.copy_url_to_clipboard` { #slowpics.copy_url_to_clipboard .fc-key }

Values
:   `true`, `false`

Default
:   `true`

Copy the collection URL after upload.

#### `slowpics.open_in_browser` { #slowpics.open_in_browser .fc-key }

Values
:   `true`, `false`

Default
:   `true`

Open the collection URL after upload.

#### `slowpics.create_url_shortcut` { #slowpics.create_url_shortcut .fc-key }

Values
:   `true`, `false`

Default
:   `true`

Write a `.url` shortcut after upload.

#### `slowpics.webhook_url` { #slowpics.webhook_url .fc-key }

Values
:   HTTPS URL, or unset

Default
:   unset

Discord-compatible webhook for the collection URL; keep it in the environment.

## TMDB

`[tmdb]` controls the optional TMDB metadata lookup; see the [run command contract](../current-cli-contract.md#run-command-contract).

#### `tmdb.api_key` { #tmdb.api_key .fc-key }

Values
:   text, or unset

Default
:   unset

TMDB API key; keep it in the environment.

#### `tmdb.enabled` { #tmdb.enabled .fc-key }

Values
:   `true`, `false`

Default
:   `true`

Look up TMDB metadata.

#### `tmdb.unattended` { #tmdb.unattended .fc-key }

Values
:   `true`, `false`

Default
:   `false`

Retained for configuration compatibility. Both values currently use noninteractive
selection: a selected match is returned, while ambiguous or missing matches produce
no metadata. This setting does not enable a chooser.

#### `tmdb.timeout_seconds` { #tmdb.timeout_seconds .fc-key }

Values
:   finite number, at least `1`

Default
:   `10.0`

Request timeout.

#### `tmdb.year_tolerance` { #tmdb.year_tolerance .fc-key }

Values
:   `0` to `5`

Default
:   `2`

Release-year difference accepted for a match.

#### `tmdb.category_preference` { #tmdb.category_preference .fc-key }

Values
:   `"movie"`, `"tv"`, or unset

Default
:   unset

Category preferred when a title is ambiguous.

## Logging

`[logging]` controls run log output.

#### `logging.level` { #logging.level .fc-key }

Values
:   `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`

Default
:   `"INFO"`

Log level.

#### `logging.format` { #logging.format .fc-key }

Values
:   `"console"`, `"json"`

Default
:   `"console"`

Log format.

`--quiet` and `--verbose` override the level for one run.
