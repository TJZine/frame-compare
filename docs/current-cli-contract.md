# Current CLI Contract

This document describes the present-day user-facing CLI contract for Frame Compare.
It is intentionally about current behavior, not desired future behavior.

## Operating Stance

Frame Compare is a CLI-first packaged Python app. Command names, flags, exit behavior,
machine-readable output modes, and documented config-persistence behavior are public
surfaces.

Importable Python modules are not promoted to supported public APIs unless the repo
documents that promise elsewhere.

## Authority And Update Rules

- `src/frame_compare/cli/entry.py` is the implementation owner for CLI command routing,
  argument parsing, stdout/stderr behavior, and interactive post-run behavior.
- `src/frame_compare/config/overrides.py` owns CLI flag to config override mappings.
- Primary executable contract checks include:
  - `tests/cli/test_cli_commands.py` for help text, JSON payloads, report auto-open
    gating, and command-level CLI behavior.
  - `tests/cli/test_run_slowpics_options.py` for the slow.pics `run` option
    surface.
  - `tests/cli/test_run_output.py` for human output, JSON stdout cleanliness,
    and slow.pics post-upload presentation behavior.
  - `tests/config/test_schema.py` for config schema/defaults, including the
    exact slow.pics field set.
  - `tests/config/test_overrides.py` for CLI override mapping semantics.
  - `tests/e2e/test_cli_version.py` for the public `version` command contract.
  - `tests/cli/test_exit_codes.py` for exit-code behavior.
  - `tests/test_cli_contract_docs.py` for keeping this document aligned with the live
    override map and authority wiring.
- `docs/ENGINEERING_RUNBOOK.md` owns workflow, verification, and public-surface policy.

Update this document in the same pass when changing:

- command names or subcommand structure
- user-facing flag names or meanings
- CLI flag to config mapping or persistence rules
- JSON output schema for `run --json` or `doctor --json`
- browser/report-opening rules
- slow.pics post-upload side-effect behavior or warning placement

## Command Surface

Current user-facing command surface:

- `frame-compare version`
- `frame-compare run`
- `frame-compare wizard`
- `frame-compare doctor`
- `frame-compare preset`
  - `frame-compare preset list`
  - `frame-compare preset apply`
  - `frame-compare preset save`

## Shared Path Resolution Rules

These commands share the same root/config path resolution rules:

- `run`
- `wizard`
- `preset apply`
- `preset save`

For those commands:

- `--root` selects the workspace root and defaults to `.`.
- `--config` selects the config file path. Relative paths resolve from `--root`.
- If `--config` is omitted, the CLI resolves `config/config.toml` under `--root`.

For the installed Windows portable shim, the shim runs the bundle launcher from the
bundle root and injects a default `--config` for `run`, `wizard`, and supported
`preset` subcommands when the user did not pass `--config`. The injected default
prefers `<bundle>/config/config.toml` when it exists, otherwise it falls back to
`%LOCALAPPDATA%/Programs/FrameCompare/state/config.toml` when that state config
exists.

## Config-Only Sources Surface

`[sources]` is a config-only public surface for source identity, explicit
reference selection, analysis source selection, FPS matching, and per-source
overrides. There are no dedicated `run` flags for these fields.

Current fields:

- `reference`: optional source selector. When omitted or set to literal `"auto"`,
  the first discovered input remains the selected reference. A non-auto value
  resolves through source selector rules and moves the selected source to the
  front of clip order; comparisons keep deterministic discovery order after it.
- `analysis_source`: config-only string. Defaults to `"reference"`. `"reference"`
  analyzes the selected reference clip when analysis metrics are required.
  `"fastest"` benchmarks discovered clips and analyzes the fastest usable clip
  when analysis metrics are required. Any other value resolves as a source
  selector when analysis metrics are required. It never changes the selected
  reference, comparison order, input order, or display order.
- `match_fps`: FPS matching policy. Defaults to `disabled`. When set to
  `assume_reference`, every comparison source without an explicit
  `effective_fps` override inherits the selected reference effective FPS.
  When set to `majority`, Frame Compare chooses the strict majority effective
  FPS after explicit `effective_fps` overrides. If no strict majority exists,
  it falls back to the selected reference effective FPS and emits a human
  warning diagnostic.
  This is an AssumeFPS-style timing override; it does not resample, drop,
  interpolate, or duplicate frames.
- `overrides`: mapping from source selector to per-source override table.
  Current override fields are `trim_start_frames`, `trim_end_frames`, and
  `active_rect = { x, y, width, height }`, and `effective_fps = "num/den"`.

Source selectors match discovered input clips in this order: input-dir-relative
path, filename, then stem. Selectors are case-sensitive. Backslashes are
normalized to `/` before matching so Windows-style separators work in config.
Absolute paths, Windows drive paths, UNC paths, empty selectors, and selectors
with `.` or `..` path segments are rejected. Missing or ambiguous selectors fail
with the standard typed input/config error path before runtime work proceeds.

Duplicate discovered source stems fail early. This remains true until alignment
cache/manual override persistence moves from stem-based keys to versioned stable
source IDs.

Configured source trims define each clip's base renderable domain. Alignment
trims compose on top of those base trims rather than replacing them. Explicit
config `active_rect` values are validated against the probed source dimensions
and invalid explicit rectangles fail instead of falling back silently.
`effective_fps` is an explicit AssumeFPS-style timing override: it changes
timing/FPS interpretation without resampling, dropping, interpolating, or
duplicating source frames. Mixed-FPS validation compares effective FPS values
after explicit overrides and after `match_fps = "assume_reference"` or
`match_fps = "majority"` matching. Explicit per-source `effective_fps` values
take precedence over `match_fps`.

When analysis is skipped because effective `[analysis]` requests only
`user_frames` and/or `random_frame_count`, `sources.analysis_source` is not
resolved for metrics, `fastest` is not benchmarked, and no analysis metrics
cache is loaded, validated, written, or keyed by `analysis_source`.

When analysis metrics are required, `sources.analysis_source = "fastest"` is
incompatible with `run --from-cache-only` because fastest-source benchmark
selection is runtime-state dependent. The run fails through the standard typed
error path before probe loading, metadata prefetch, run-folder reservation,
analysis cache validation, or fastest benchmarking. JSON error mode keeps the
existing error payload shape, and the successful `run --json` schema is
unchanged.

## `version` Command Contract

- Prints `frame-compare <version>` to stdout.
- Exits successfully without loading the runtime pipeline.

## `run` Command Contract

### Output Modes

- `--json` writes a single JSON object to stdout and suppresses human-readable summaries.
- In that JSON object, `slowpics_url` is the only machine-readable slow.pics
  result field. No copy/open/shortcut/webhook result fields are emitted.
  Report-confirmed upload confirmation status is also not emitted; the success
  schema remains unchanged and `slowpics_url` remains the only machine-readable
  slow.pics result field.
- `--json` is incompatible with interactive alignment. If the effective config enables
  `audio_alignment.use_vspreview` or `audio_alignment.force_interactive`, the CLI exits
  with the standard config-error payload and exit code before entering the runtime
  pipeline.
- `--json` is incompatible with `audio_alignment.previous_offsets = "prompt"`
  because prompt mode is an interactive human surface. The CLI exits with the
  standard config-error JSON payload before entering the runtime pipeline.
  `previous_offsets = "always"` is compatible with `--json` and does not add
  fields to the successful JSON schema.
- `--json` is incompatible with report-confirmed slow.pics upload when that
  prompt would be needed. If effective config has `slowpics.auto_upload = true`
  and `slowpics.confirm_upload_after_report = true`, the CLI rejects `--json`
  before entering the runtime pipeline with the standard config-error JSON
  payload on stdout.
- `--quiet` suppresses the at-a-glance summary but still allows a minimal success summary.
- `--quiet` is incompatible with `audio_alignment.previous_offsets = "prompt"`
  and is rejected before entering the runtime pipeline. It is compatible with
  `previous_offsets = "always"`.
- `--quiet` is incompatible with report-confirmed slow.pics upload when that
  prompt would be needed.
- Human-readable non-quiet runs emit a `Frame Alignment` diagnostic to stderr after
  the alignment phase when accepted or rejected frame alignment changes need
  explanation. The diagnostic reports normalized source-frame row 0, final trim
  ranges, offsets, selected aligned frames, and rejected alignment warning context
  for comparisons with material alignment information. It is suppressed by
  `--quiet` and is never emitted to `run --json` stdout.
- Human-readable non-quiet successful runs group final warnings by source in a
  `Warnings` panel. Existing runtime warning strings and slow.pics post-upload
  action warnings are bridged into presentation rows with source, severity,
  message, and optional detail/action context, then de-duplicated for display.
  The visible warning cap remains eight rows; truncated output includes the
  number of hidden rows and counts by hidden source.
- `run --json` does not emit the human warning panel, does not add warning
  fields, and keeps warning text off stdout for successful runs. Runtime logs and
  diagnostics may still use stderr. The known native L-SMASH-Works
  `libvslsmashsource.dll` API3 deprecation warning is filtered from stderr until
  the bundled/installed plugin is updated; other native VapourSynth and plugin
  stderr remains visible.
- When the at-a-glance summary reports optional VSPreview probe failures, it uses a
  sanitized summary rather than raw probe exception text.
- The at-a-glance summary uses user-facing row labels such as `run folders`,
  `FFmpeg audio`, `previous offsets`, `interactive alignment`,
  `force interactive`, and `VSPreview` while preserving the same effective
  configuration facts. The `previous offsets` row reports only the effective
  config mode: `disabled`, `prompt`, or `always`.
- The at-a-glance workspace paths are resolved base paths. When
  `paths.use_run_folders = true`, the `screenshots` and `generated` rows describe the
  configured base paths rather than the fresh per-run subdirectories reserved later in
  execution.
- Human Rich progress uses product phase labels: `PLAN`, `ANALYZE`, `ALIGN`,
  `RENDER`, `METADATA`, `DOVI`, `PUBLISH`, `REPORT`, `CONFIRM`, and `CLEANUP`.
  Internal phase names in logs and `phase_timings` remain the runtime keys such
  as `frame_plan`, `analyze`, `align`, and `confirm_slowpics_upload`.
- `--no-color` disables ANSI color in interactive Rich progress output. It does
  not switch an interactive human run to structlog progress. It also disables
  ANSI styling for the previous-offset reuse table and prompt. Quiet and JSON
  modes still suppress Rich progress, and non-TTY runs still use log progress.
- `--diagnose-paths` emits a pinned JSON object with keys `cache`, `config`, `input`,
  `output`, and `root`, then exits without invoking the runtime pipeline.
  The `cache` value is the resolved configured `paths.generated_dir`; the shared
  analysis cache lives below it at `cache/analysis`, and shared alignment reuse
  entries live below it at `cache/alignment`. `--diagnose-paths` does not report
  the shared alignment cache path separately.
- `--write-config` writes the effective config to disk, then exits without invoking the
  runtime pipeline.

### Cache Mode Semantics

- Analysis cache entries live under `<resolved paths.generated_dir>/cache/analysis`
  using labeled full-fingerprint filenames:
  `<safe-human-label>__<full-fingerprint>.compframes`.
- The analysis cache fingerprint includes the selected reference identity and a
  stable all-source selection-domain token. That token stores
  `analysis_source_path`, `reference_path`, source identities, source trims,
  effective FPS values, the configured analysis ignore-window settings, and the
  final shared selectable window. Cache schema v4 stores `analysis_source_path`
  in `MetricsMetadata`, and different selected references, selected analysis
  sources, or selection domains from the same input set do not satisfy each
  other. When `sources.analysis_source = "reference"`, `analysis_source_path`
  is the selected reference path. Metric-array cache identity excludes
  `user_frames`, random seed, frame-selection counts, `dark_quantile`, and
  `bright_quantile` because those values affect frame choice rather than metric
  computation.
- The full fingerprint remains inside the cache payload and is validated on load.
  Legacy run-folder `cache.compframes` files are not used as analysis cache hits.
- Analysis is skipped automatically when `dark_frame_count`, `bright_frame_count`,
  and `motion_frame_count` are all `0`; `frame_plan` still selects configured
  user/random frames. With `paths.use_run_folders = true`, runs that proceed reserve a fresh run folder;
  existing run folders are not reused to satisfy analysis cache hits.
- `--no-cache` deletes only the matching shared analysis cache entry for the current
  inputs, selected reference, all-source selection domain, and analysis settings
  before continuing. It does not clear unrelated shared analysis entries and
  does not delete shared previous-offset reuse entries under
  `<resolved paths.generated_dir>/cache/alignment/`.
- `--from-cache-only` is analysis-cache-only. When analysis is not skipped, it validates
  the matching shared analysis cache entry before metadata prefetch and before run-folder
  reservation, so a missing or invalid entry does not leave an empty run folder.
- When the exact all-source selection-domain token requires probe data and the
  probe cache is missing, `--from-cache-only` fails before metadata prefetch and
  before run-folder reservation rather than validating a weaker fingerprint.
- `--from-cache-only` does not require cached alignment offsets from a previous run.
  Previous alignment reuse is not part of analysis cache-only prevalidation. A
  cache-only run may reuse previous alignment offsets when
  `previous_offsets = "always"` and a complete valid set exists, but missing
  previous alignment offsets do not fail `--from-cache-only` by themselves.
  Alignment can compute current-run offsets or use accepted shared previous
  offsets after analysis cache validation succeeds.
- `--no-cache` and `--from-cache-only` are mutually exclusive.

### Report Auto-Open Ownership

- HTML report generation is owned by `frame_compare.services.report`.
- Browser auto-open and report-path presentation for a generated report are
  owned by `frame_compare.cli.entry` and its run-command helper.
- Clipboard copy and slow.pics browser opening are also CLI-owned interactive
  post-run actions.
- The CLI only attempts to open a report when all of these are true:
  - the run succeeded and produced `report_path`
  - `--json` was not used
  - `--quiet` was not used
  - stdout is attached to a TTY
  - the CLI can reload the effective config and `report.auto_open` is true, or the
    post-run config reload fails and the CLI falls back to opening the report anyway

There is currently no dedicated `run` flag for `report.auto_open`; it is a config-only
surface.

If an enabled slow.pics browser open is attempted for the same successful run,
report auto-open is suppressed for that run. If slow.pics browser open is not
attempted, the existing report auto-open rules above still apply.

Report-confirmed slow.pics upload is the exception to that precedence rule. In
that opted-in workflow, the CLI presents the local report before prompting for
upload, regardless of whether a later confirmed upload will open the slow.pics
URL in a browser. The same report auto-open rules decide whether the report is
opened. If it is not opened, the CLI prints the report path before prompting.

### slow.pics Upload Behavior

- slow.pics publishing is disabled by default. Users must set
  `slowpics.auto_upload = true` in config or through the wizard before `run`
  uploads generated screenshots.
- Users may additionally opt into report-confirmed upload with the config-only
  field `slowpics.confirm_upload_after_report = true`. The field is inert unless
  effective `slowpics.auto_upload = true`.
- There is no dedicated `run` flag for report-confirmed upload. `--no-upload`
  remains the only slow.pics-specific `run` flag and still forces effective
  `slowpics.auto_upload = false`.
- When enabled and not suppressed by `--no-upload`, the current upload path uses
  the browser-compatible slow.pics flow owned by
  `frame_compare.services.publishers`: fetch `/comparison`, create metadata at
  `/upload/comparison`, then upload each planned image to
  `/upload/image/{imageUuid}`.
- Upload membership comes from the explicit current-render upload plan, not from
  scanning the screenshot directory. The plan is built from selected frames,
  current render artifacts, and clip order.
- The normal non-confirmed phase order remains:
  `frame_plan -> analyze -> align -> render -> metadata -> dovi -> publish -> report -> post_report_cleanup`.
- Report-confirmed upload changes only the opted-in interactive path:
  `frame_plan -> analyze -> align -> render -> metadata -> dovi -> report -> confirm_slowpics_upload -> publish -> post_report_cleanup`.
- Report-confirmed upload requires an interactive report-enabled run when the
  prompt would be needed. If effective `slowpics.auto_upload = true` and
  `slowpics.confirm_upload_after_report = true`, the CLI rejects the run before
  runtime when any of these are true: `--json` was passed, `--quiet` was passed,
  stdin is not attached to a TTY, stdout is not attached to a TTY, or
  `report.enable = false`.
- In the report-confirmed workflow, the report is generated before upload and is
  not regenerated after upload. The generated report payload has
  `slowpics_url = null`; after a confirmed upload, the CLI summary remains the
  place where the uploaded slow.pics URL is shown.
- If the report phase warns, fails, or produces no `report_path`, confirmation
  does not prompt and slow.pics upload is skipped with the deterministic warning
  `slow.pics upload skipped because report confirmation was unavailable`. Human
  output includes that message as a neutral skipped Result row rather than a
  successful artifact row.
- If the user declines the prompt, the run still succeeds, no slow.pics upload
  side effects run, human output includes a neutral skipped Result row
  `slow.pics upload skipped by confirmation` rather than a successful artifact
  row, and `slowpics_url` remains `None`.
- `delete_after_upload` is local-only and report-safe. It is not mapped to
  slow.pics `removeAfter`; the current remote metadata request sends an empty
  `removeAfter` value.
- When `delete_after_upload = true`, Frame Compare deletes only the exact
  planned local screenshot files that were successfully uploaded. Deletion runs
  after the report phase, not inside the slow.pics publisher, and never scans the
  screenshot directory for deletion membership.
- Local uploaded-file deletion runs only when the slow.pics upload completed and
  report handling is safe: reports are disabled, or report generation completed
  with `report.embed_images = true`. When reports are enabled with
  `report.embed_images = false`, deletion is skipped because the report
  references screenshot files on disk. If report generation warns/fails,
  deletion is skipped.
- In the report-confirmed workflow, reports are required, so delete-after-upload
  can run only after a confirmed successful upload when the already-generated
  report embedded images. With `report.embed_images = false`, deletion is
  skipped because the report references local screenshot files. If upload is
  declined or report confirmation is unavailable, no files are considered
  uploaded and no slow.pics delete-after-upload cleanup runs.
- Local uploaded-file deletion errors do not fail an otherwise successful run.
  They are surfaced as run warnings and logs. In `run --json`, warnings remain
  off stdout so the stdout payload stays a single JSON object.
- After a successful slow.pics upload, enabled post-upload actions run according
  to their owners:
  - `copy_url_to_clipboard` copies the slow.pics URL through the CLI only when
    `--json` was not used, `--quiet` was not used, and stdout is attached to a
    TTY.
  - `open_in_browser` opens the slow.pics URL through the CLI under the same
    interactive-only conditions as clipboard copy.
  - `create_url_shortcut` writes a deterministic `.url` shortcut after upload
    whenever configured, including `--json` and `--quiet` runs.
  - `webhook_url` posts the slow.pics URL to the configured webhook after upload
    whenever configured, including `--json` and `--quiet` runs.
- Post-upload side-effect failures do not fail an otherwise successful run.
  They are warning-only. In `run --json`, warnings remain off stdout and no
  post-upload action fields are added to the JSON payload.
- Human output shows enabled successful post-upload action outcomes and warnings.
  Disabled or skipped post-upload actions are not listed by default.
- Confirmed report-first upload still runs the existing post-upload actions
  after a successful upload according to their normal owners and gating.
- The current public upload surface does not include collection suffix/name,
  image format or optimization toggles, tags, hentai flag, or remote
  remove-after behavior.

### slow.pics Shortcut Policy

- Shortcut creation is owned by `frame_compare.services.slowpics_shortcut`.
- The shortcut is a Windows InternetShortcut-compatible `.url` file containing
  the uploaded slow.pics comparison URL.
- The shortcut output directory is deterministic:
  - the current run folder when run folders are enabled
  - otherwise the safe common parent of the resolved screenshots and generated
    output directories
- Without a run folder, the common parent must be under the resolved workspace
  root and must not be a drive root, filesystem anchor, UNC/share root, or the
  user home directory. Paths on different drives or anchors have no safe common
  parent.
- The filename is derived from current run metadata or upload title, with a
  stable fallback from the slow.pics URL key.
- Repeated writes overwrite the same deterministic shortcut path.
- Shortcut files are not members of `slowpics.delete_after_upload` cleanup.
- Shortcut write or path-selection failures are warning-only.

### slow.pics Webhook Policy

- Webhook delivery is owned by `frame_compare.services.slowpics_webhook`.
- The payload is exactly `{"content":"<slowpics_url>"}` serialized as JSON.
- The configured webhook URL must be a strict external HTTPS endpoint:
  non-HTTPS URLs, localhost names, loopback, private, link-local, multicast,
  reserved, unspecified, and otherwise non-public IP targets are rejected.
- Hostname targets are rejected when DNS resolution fails, returns no addresses,
  includes an unparseable address, or includes any disallowed address.
- Delivery prevents validation-to-connect DNS rebinding by connecting to a
  prevalidated pinned IP address while preserving TLS certificate verification
  and SNI for the original hostname.
- Delivery uses no redirects, a fixed 10 second timeout, and 3 attempts.
- The webhook request path is isolated from the slow.pics upload client: it does
  not reuse slow.pics cookies, headers, client state, redirect policy, proxy
  settings, or environment trust.
- Webhook URL details are redacted from warnings and logs.
- Delivery failures are warning-only and do not write to JSON stdout.

## CLI Flag To Config Mapping

These `run` flags currently map into config values through `CLI_OVERRIDE_MAP`:

| CLI flag | Config path | Notes |
| --- | --- | --- |
| `--input` | `paths.input_dir` | Relative values remain relative to the workspace root. |
| `--tm-preset` | `color.preset` | Tonemap preset override. |
| `--tm-target` | `color.target_nits` | Tonemap target nits override. |
| `--tm-curve` | `color.tone_curve` | Tonemap curve override. |
| `--frames` | `analysis.user_frames` | Comma-separated original reference source-frame numbers. Values outside the effective selectable domain are dropped with warnings at runtime. |
| `--random-frame-count` | `analysis.random_frame_count` | Random frame count override. |
| `--dark-frame-count` | `analysis.dark_frame_count` | Dark metric frame count override; requires analysis. |
| `--bright-frame-count` | `analysis.bright_frame_count` | Bright metric frame count override; requires analysis. |
| `--motion-frame-count` | `analysis.motion_frame_count` | Motion metric frame count override; requires analysis. |
| `--seed` | `analysis.random_seed` | Deterministic frame-selection seed override. |
| `--overlay` | `screenshots.overlay_mode` | Overlay mode override. |
| `--no-upload` | `slowpics.auto_upload` | Inverted flag: passing it sets effective `auto_upload = false`, and persists that value when combined with `--write-config`. |
| `--force-interactive-alignment` | `audio_alignment.force_interactive` | Also forces `audio_alignment.use_vspreview = true`. |

`--no-upload` is the only slow.pics-specific `run` flag. No runtime-only
slow.pics `run` flags exist.

`--frame-count` and `-n` are removed. They may be parsed as hidden
rejection-only traps so Frame Compare can return its standard typed error in
human and JSON modes, but they are not supported aliases, do not appear in help,
do not map to config, and do not persist through `--write-config`.

## Config-Only Analysis Surface

The default `[analysis]` frame-selection surface is:

- `user_frames = []`
- `random_frame_count = 10`
- `dark_frame_count = 0`
- `bright_frame_count = 0`
- `motion_frame_count = 0`
- `random_seed = 42`
- `save_frames_data = true`

`user_frames` are original selected-reference source-frame numbers. They are not
trim-relative offsets and are not post-alignment frame numbers. Configured source
trims and the global selection window constrain whether each requested frame is
renderable.

At least one of `user_frames`, `random_frame_count`, `dark_frame_count`,
`bright_frame_count`, or `motion_frame_count` must request a frame, and the total
requested selector count must not exceed 100. Removed stale analysis keys
`selection_mode` and `frame_count` fail validation explicitly.

These remaining `[analysis]` fields are config-only public surface; there are no
dedicated `run` flags for them:

- `ignore_lead_seconds = 0.0`
- `ignore_trail_seconds = 0.0`
- `min_window_seconds = 5.0`
- `dark_quantile = 0.05`
- `bright_quantile = 0.95`

The lead/trail fields define a global selectable analysis window inside each
clip's source-specific base trim domain. They do not physically trim sources or
change reported source-frame numbers. `min_window_seconds` expands a too-small
per-clip selectable window within clip bounds, preferring to extend the end
first and then shift the start earlier. If a shared selectable intersection
cannot be formed, the run fails with the standard typed selection error.

## Config-Only slow.pics Surface

These ten fields are the full current public `[slowpics]` config surface:

- `auto_upload = false`
- `confirm_upload_after_report = false`
- `visibility = "unlisted"`
- `delete_after_upload = false`
- `timeout_seconds = 60.0`
- `max_retries = 3`
- `copy_url_to_clipboard = true`
- `open_in_browser = true`
- `create_url_shortcut = true`
- `webhook_url = null`

`visibility` accepts only `public` and `unlisted`.

`confirm_upload_after_report` is a config-only, interactive-only opt-in. It only
has effect when effective `auto_upload = true`; it adds no `run` flag, no wizard
prompt, and no `run --json` stdout field. When the prompt would be needed, it is
incompatible with `--json`, `--quiet`, non-TTY stdin, non-TTY stdout, and
`report.enable = false`.

`delete_after_upload` is local-only and report-safe: it removes only the exact
planned local screenshot files that were successfully uploaded, and only after
report processing is complete. Deletion is allowed when reports are disabled or
when an embedded-image report is generated successfully. Deletion is skipped for
non-embedded reports and for warn-only report failures. It does not request
slow.pics remote removal and does not map to remote `removeAfter`.

`copy_url_to_clipboard`, `open_in_browser`, `create_url_shortcut`, and
`webhook_url` are implemented config fields for slow.pics legacy UX parity. They
do not add new `run` flags, wizard prompts, or `run --json` stdout fields.

`copy_url_to_clipboard` and `open_in_browser` are interactive CLI-owned actions:
they run only after a successful upload in human non-quiet TTY runs. Clipboard
and slow.pics browser failures are warning-only. If slow.pics browser opening is
attempted, generated-report auto-open is suppressed for that run.

`create_url_shortcut` and `webhook_url` run after successful upload whenever
configured, including `--json` and `--quiet`. Their warning-only failures remain
off JSON stdout and do not fail the run.

The JSON output schema remains unchanged by report-confirmed upload:
`slowpics_url` is still the only machine-readable slow.pics result field.

There are no current slow.pics config fields for collection suffix/name, image
format or optimization toggles, tags, hentai flag, or remote remove-after
behavior.

## VSPreview Interactive Diagnostics

VSPreview parent telemetry, generated Frame Compare session diagnostics,
preview assumptions, ready text, and terminal confirmation prompts use stderr as
the single human diagnostic stream. The VSPreview child process is launched with
inherited stdout, and its stderr is passed through except for the known native
L-SMASH-Works `libvslsmashsource.dll` API3 deprecation warning. Frame
Compare-owned generated script diagnostics are written to stderr.

When interactive alignment launches a generated VSPreview session, the
diagnostic order is:

1. parent `VSPreview Session` telemetry
2. generated `VSPreview Bootstrap`
3. generated reference and loaded comparison rows
4. generated `VSPreview Assumptions`, only when assumptions exist
5. generated output slot rows
6. generated `VSPreview Ready`
7. parent `VSPreview Confirmation` prompt text

Generated VSPreview assumptions are preview-only diagnostics derived from
Frame Compare's existing clip probe metadata and serialized into the generated
session script. Missing, unspecified, malformed, or unparseable `_Matrix`,
`_Transfer`, or `_Primaries` frame properties are collected and shown in the
`VSPreview Assumptions` section before output rows and before `VSPreview Ready`.
The generated session does not decode source frames just to collect these
assumptions. These assumptions do not change render, report, analysis, or
alignment semantics.

## Config-Only Screenshot Surface

The following `[screenshots]` fields are config-only public surfaces. There are no
dedicated `run` flags for them:

- `geometry_mode = "native" | "aligned"` selects screenshot geometry behavior.
  `native` is the default and preserves current full-frame screenshot behavior.
  `aligned` is the opt-in mode for deterministic mixed-geometry screenshot
  alignment. Native mode ignores aligned-only geometry fields for behavior, but
  the config schema still validates their enum values and target field types.
- `active_rect_detection = "provided" | "dimension" | "aspect_ratio"` selects
  the active-image rectangle evidence used by aligned screenshots. `provided`
  uses only explicit per-source `active_rect` overrides and trusted metadata
  active rectangles. `dimension` also allows same-height or same-width centered
  crop inference. `aspect_ratio` is the aligned default and additionally allows
  conservative centered vertical letterbox inference when a target content
  aspect ratio has at least two matching sources or one explicit/trusted
  metadata source.
- `aligned_scale_policy = "largest_active" | "smallest_active" |
  "reference_active" | "explicit_size"` selects the aligned output canvas policy.
  `largest_active` is the aligned default and uses the active-source envelope
  `{max(active_width), max(active_height)}`. `smallest_active` uses
  `{min(active_width), min(active_height)}`. `reference_active` uses the selected
  reference source active dimensions. `explicit_size` uses
  `aligned_target_width x aligned_target_height`.
- `aligned_target_width` and `aligned_target_height` are optional positive even
  integers used only by `aligned_scale_policy = "explicit_size"` in aligned
  mode. In aligned mode, both are required for `explicit_size` and both must be
  omitted for all other scale policies. In native mode they are inert for
  behavior, but any provided target value must still be positive and even.
- Aligned scaling preserves aspect ratio, fits active content inside the selected
  target width and height without exceeding either dimension, and centers black
  padding on the final canvas. Derived policy targets are normalized downward to
  mod-safe dimensions; explicit-size targets preserve the exact configured
  canvas after validation.
- `vs_writer = "auto" | "pillow" | "fpng"` selects the VapourSynth screenshot writer
  policy. `auto` is the default and preserves current behavior until a writer-specific
  runtime path is eligible. `pillow` means the existing Pillow PNG writer policy, and
  `fpng` is the explicit VapourSynth `core.fpng.Write` writer selection for the
  screenshot runtime path. When `use_ffmpeg = false` and renderer selection is `auto`,
  explicit `fpng` requires successful VapourSynth loading and does not silently fall
  back to FFmpeg; `use_ffmpeg = true` still forces the FFmpeg path.
- `png_compression` remains an integer from `0` through `9`. It is the public
  compression input for Pillow and VapourSynth fpng. Pillow receives the value
  directly. Fpng maps `0..3` to `0`, `4..6` to `1`, and `7..9` to `2`;
  unsupported values fail config validation rather than being silently clamped.

## Config-Only Audio Alignment Surface

The following `[audio_alignment]` fields are config-only public surfaces for the
audio-alignment accuracy workstream. There are no dedicated `run` flags for them.
These fields affect current computed alignment behavior when audio alignment is
enabled.

- `previous_offsets = "disabled" | "prompt" | "always"` controls opt-in reuse of
  shared VSPreview-confirmed offsets. It is config-only, has no `run` flag, and
  is not present in the CLI override map. Exact-match computed audio alignment
  offsets are deterministic cache hits when `cache_results = true`, regardless
  of `previous_offsets`; the policy only controls whether prior human-confirmed
  offsets are reused. `disabled` is the default and does not read or reuse shared
  VSPreview-confirmed offsets, but eligible current-run computed or
  VSPreview-confirmed results still write to the shared reuse cache when
  `cache_results = true`. `prompt` shows a Rich stderr table for a complete
  valid VSPreview-confirmed offset set and asks
  `Reuse previous preview-confirmed alignment offsets? [y/N]`; default, EOF,
  unavailable stdin, or unavailable stderr all continue without confirmed-offset
  reuse. If a confirmed cache entry also contains the computed audio alignment
  result that produced the preview suggestion, declining the prompt reuses that
  computed result instead of rerunning audio alignment. `always` reuses a
  complete valid confirmed set without prompting. Prompt mode writes no
  prompt/table to stdout.
- Previous-offset prompt mode requires both stdin and stderr to be TTYs before
  any blocking read. If stderr is not a TTY, the prompt is invisible and the run
  continues without reuse and without a human diagnostic. If stderr is a TTY but
  stdin is not a TTY, or EOF occurs while prompting, the CLI emits
  `Previous alignment offset reuse prompt unavailable; continuing without reuse.`
  to stderr and continues without reuse.
- The previous-offset reuse table displays reference and comparison labels,
  signed frame offset, time offset seconds, source label `confirmed`, the shared
  cache path, and each entry's persisted `accepted_at` timestamp. It does not
  derive freshness from file mtime or index mtime.
- Shared previous-offset entries live under
  `<resolved paths.generated_dir>/cache/alignment/`. This is shared
  workspace-level cache state even when `paths.use_run_folders = true`; it does
  not live inside a fresh run folder.
- `previous_offsets = "prompt"` and `previous_offsets = "always"` require
  `cache_results = true`. `previous_offsets = "disabled"` remains compatible
  with `cache_results = false`.
- `force_interactive = true` is incompatible with `previous_offsets = "prompt"`
  and `previous_offsets = "always"` because reuse can skip VSPreview.
- Successful `run --json` output remains unchanged by previous-offset reuse.
- `correlation_mode = "raw_fft" | "gcc_phat"` selects the correlation algorithm
  used by the computed estimator. `raw_fft` is the default.
- `preprocessing_mode = "none" | "standard"` selects signal preprocessing before
  correlation. `none` is the default.
- `channel_strategy = "mono_downmix" | "best_channel"` selects the audio channel
  handling used during extraction. `mono_downmix` is the default.
- `confidence_threshold` remains a float from `0.0` through `1.0`, defaulting to
  `0.0`. It gates whether computed offsets are applied.
- `ambiguity_peak_ratio` remains a float greater than or equal to `1.0`,
  defaulting to `1.0`. It gates ambiguous correlation peaks.
- `window_length_seconds` and `window_stride_seconds` remain floats greater than
  or equal to `0.0`, both defaulting to `0.0`. They control the consensus window
  shape used by computed alignment.
- `minimum_valid_windows` remains an integer greater than or equal to `1`,
  defaulting to `1`. It gates whether enough windows produced valid estimates.
- `consensus_minimum_ratio` remains a float from `0.0` through `1.0`, defaulting
  to `1.0`. It gates whether enough windows agree on the selected offset.
- `refinement_mode = "disabled" | "local"` selects whether local offset
  refinement runs after coarse correlation. `disabled` is the default.
- `refinement_sample_rate` is either `null` or an integer from `4000` through
  `48000`, defaulting to `null`. When local refinement is enabled, it selects
  the refinement sample rate; `null` uses the alignment sample rate.
- `reference_stream` is either `null` or a non-negative audio stream ordinal,
  defaulting to `null`. When set, it selects the reference clip audio stream.
- `comparison_streams` is a mapping from comparison filename stem to non-negative
  audio stream ordinal, defaulting to an empty map. Matching entries select the
  comparison clip audio stream for that stem.

## Persistence Rules

`run --write-config` persists the effective config after applying the mapped overrides
above. That means the flags in the previous section are persistent when combined with
`--write-config`.

Before writing, `run --write-config` rejects effective configs that combine
`audio_alignment.previous_offsets = "prompt"` or `"always"` with
`audio_alignment.force_interactive = true`, and rejects those reuse modes when
`audio_alignment.cache_results = false`. The config is not written when either
conflict is present.

The following `run` flags are runtime-only and do not persist through `--write-config`:

- `--root`
- `--config`
- `--no-cache`
- `--from-cache-only`
- `--skip-analysis`
- `--skip-metadata`
- `--skip-dovi`
- `--json`
- `--no-color`
- `--write-config`
- `--diagnose-paths`
- `--quiet`
- `--verbose`

If a future change makes a runtime-only flag persistent, or adds a new persistent flag,
update this document, `src/frame_compare/config/overrides.py`, and the relevant CLI
tests in the same pass.

### Tonemap Preset And Target Resolution

`color.preset` selects the baseline tonemap settings. The `reference` preset targets
100 nits. `color.target_nits` overrides that preset target only when the value is
explicitly present in config or supplied through `--tm-target`; unrelated CLI overrides
must not turn schema defaults into explicit tonemap target overrides.

The default `reference` baseline also uses `contrast_recovery = 0.3`. This value is
forwarded to libplacebo tonemapping, not applied as a separate post-tonemap contrast
curve. VapourSynth HDR screenshot export preserves the live tonemap-output range and
only applies limited-to-full expansion during PNG encoding when the rendered frame
props still indicate limited-range RGB on the active VapourSynth runtime.

## `wizard` Command Contract

- `wizard` is interactive and writes a minimal config payload to the resolved config path.
- It prompts for:
  - input directory
  - slow.pics auto-upload, defaulting to disabled
  - slow.pics visibility (`public` or `unlisted`)
  - slow.pics delete-after-upload
  - optional TMDB API key
- It validates the generated payload against `ConfigSchema` before writing.
- It does not advertise or accept unsupported slow.pics visibility values.
- On success, it writes a concise confirmation to stderr including the resolved
  config path.
- Interruptions during prompting exit with the interrupted exit code.
- Typed validation/write failures use the standard CLI error contract on stderr,
  honor the `NO_COLOR` environment variable, and do not suggest unsupported
  `--verbose` usage.

## `doctor` Command Contract

- `doctor` runs dependency diagnostics through `run_doctor`.
- `doctor --json` writes a single JSON object to stdout using `_doctor_report_json`.
- If the `doctor` command hits a typed top-level failure before it can produce a
  `DoctorReport`, it uses the standard CLI error contract. In `--json` mode that means
  the standard error payload is written to stdout.
- Human-mode typed top-level failures honor the `NO_COLOR` environment variable
  and do not suggest unsupported `--verbose` usage.
- Without `--json`, `doctor` writes a human-readable report to stdout.
- Human output uses a neutral status marker for optional unavailable checks such as
  VSPreview, so optional availability gaps are visually distinct from critical
  dependency failures. This does not change `doctor --json` status values.
- If any critical failures are present, `doctor` exits with the dependency error exit code.
- Optional VSPreview probe diagnostics may include exception type metadata, but do not
  expose raw probe exception messages.

## `preset` Command Contract

- Typed preset command failures use the standard CLI error contract on stderr,
  honor the `NO_COLOR` environment variable, and do not suggest unsupported
  `--verbose` usage.

### `preset list`

- Resolves the presets directory under `<root>/config/presets`.
- Accepts `--config` for interface consistency, but current behavior ignores the resolved
  config path and uses `--root` only when locating presets.
- Prints preset names one per line to stdout.
- Emits no success confirmation.

### `preset apply`

- Loads the resolved config file.
- Applies the named preset from `<root>/config/presets`.
- Writes the updated config back to the resolved config path.
- On success, writes a concise confirmation to stderr including the preset name and
  resolved config path.

### `preset save`

- Loads the resolved config file.
- Saves the current config as a named preset under `<root>/config/presets`.
- On success, writes a concise confirmation to stderr including the preset name and
  saved preset path.
