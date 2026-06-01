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

## `version` Command Contract

- Prints `frame-compare <version>` to stdout.
- Exits successfully without loading the runtime pipeline.

## `run` Command Contract

### Output Modes

- `--json` writes a single JSON object to stdout and suppresses human-readable summaries.
- In that JSON object, `slowpics_url` is the only machine-readable slow.pics
  result field. No copy/open/shortcut/webhook result fields are emitted.
- `--json` is incompatible with interactive alignment. If the effective config enables
  `audio_alignment.use_vspreview` or `audio_alignment.force_interactive`, the CLI exits
  with the standard config-error payload and exit code before entering the runtime
  pipeline.
- `--quiet` suppresses the at-a-glance summary but still allows a minimal success summary.
- When the at-a-glance summary reports optional VSPreview probe failures, it uses a
  sanitized summary rather than raw probe exception text.
- The at-a-glance workspace paths are resolved base paths. When
  `paths.use_run_folders = true`, the `screenshots` and `generated` rows describe the
  configured base paths rather than the fresh per-run subdirectories reserved later in
  execution.
- `--diagnose-paths` emits a pinned JSON object with keys `cache`, `config`, `input`,
  `output`, and `root`, then exits without invoking the runtime pipeline.
  The `cache` value is the resolved configured `paths.generated_dir`; the shared
  analysis cache lives below it at `cache/analysis`.
- `--write-config` writes the effective config to disk, then exits without invoking the
  runtime pipeline.

### Cache Mode Semantics

- Analysis cache entries live under `<resolved paths.generated_dir>/cache/analysis`
  using labeled full-fingerprint filenames:
  `<safe-human-label>__<full-fingerprint>.compframes`.
- The full fingerprint remains inside the cache payload and is validated on load.
  Legacy run-folder `cache.compframes` files are not used as analysis cache hits.
- With `paths.use_run_folders = true`, runs that proceed reserve a fresh run folder;
  existing run folders are not reused to satisfy analysis cache hits.
- `--no-cache` deletes only the matching shared analysis cache entry for the current
  inputs and analysis settings before continuing. It does not clear unrelated shared
  analysis entries and does not delete alignment offset caches.
- `--from-cache-only` is analysis-cache-only. When analysis is not skipped, it validates
  the matching shared analysis cache entry before metadata prefetch and before run-folder
  reservation, so a missing or invalid entry does not leave an empty run folder.
- `--from-cache-only` does not require cached alignment offsets from a previous run.
  Alignment can compute or use the current run folder's run-scoped alignment cache after
  the analysis cache validation succeeds.
- `--no-cache` and `--from-cache-only` are mutually exclusive.

### Report Auto-Open Ownership

- HTML report generation is owned by `frame_compare.services.report`.
- Browser auto-open for a generated report is owned by `frame_compare.cli.entry`.
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

### slow.pics Upload Behavior

- slow.pics publishing is disabled by default. Users must set
  `slowpics.auto_upload = true` in config or through the wizard before `run`
  uploads generated screenshots.
- When enabled and not suppressed by `--no-upload`, the current upload path uses
  the browser-compatible slow.pics flow owned by
  `frame_compare.services.publishers`: fetch `/comparison`, create metadata at
  `/upload/comparison`, then upload each planned image to
  `/upload/image/{imageUuid}`.
- Upload membership comes from the explicit current-render upload plan, not from
  scanning the screenshot directory. The plan is built from selected frames,
  current render artifacts, and clip order.
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
| `--frame-count` | `analysis.frame_count` | Frame-selection override. |
| `--seed` | `analysis.random_seed` | Deterministic frame-selection seed override. |
| `--overlay` | `screenshots.overlay_mode` | Overlay mode override. |
| `--no-upload` | `slowpics.auto_upload` | Inverted flag: passing it sets effective `auto_upload = false`, and persists that value when combined with `--write-config`. |
| `--force-interactive-alignment` | `audio_alignment.force_interactive` | Also forces `audio_alignment.use_vspreview = true`. |

`--no-upload` is the only slow.pics-specific `run` flag. No runtime-only
slow.pics `run` flags exist.

## Config-Only slow.pics Surface

These nine fields are the full current public `[slowpics]` config surface:

- `auto_upload = false`
- `visibility = "unlisted"`
- `delete_after_upload = false`
- `timeout_seconds = 60.0`
- `max_retries = 3`
- `copy_url_to_clipboard = true`
- `open_in_browser = true`
- `create_url_shortcut = true`
- `webhook_url = null`

`visibility` accepts only `public` and `unlisted`.

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

There are no current slow.pics config fields for collection suffix/name, image
format or optimization toggles, tags, hentai flag, or remote remove-after
behavior.

## Config-Only Screenshot Surface

The following `[screenshots]` fields are config-only public surfaces. There are no
dedicated `run` flags for them:

- `geometry_mode = "native" | "aligned"` selects screenshot geometry behavior.
  `native` is the default and preserves current full-frame screenshot behavior.
  `aligned` is accepted as the opt-in mode for deterministic mixed-geometry
  screenshot alignment work.
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
- Interruptions during prompting exit with the interrupted exit code.

## `doctor` Command Contract

- `doctor` runs dependency diagnostics through `run_doctor`.
- `doctor --json` writes a single JSON object to stdout using `_doctor_report_json`.
- If the `doctor` command hits a typed top-level failure before it can produce a
  `DoctorReport`, it uses the standard CLI error contract. In `--json` mode that means
  the standard error payload is written to stdout.
- Without `--json`, `doctor` writes a human-readable report to stdout.
- If any critical failures are present, `doctor` exits with the dependency error exit code.
- Optional VSPreview probe diagnostics may include exception type metadata, but do not
  expose raw probe exception messages.

## `preset` Command Contract

### `preset list`

- Resolves the presets directory under `<root>/config/presets`.
- Accepts `--config` for interface consistency, but current behavior ignores the resolved
  config path and uses `--root` only when locating presets.
- Prints preset names one per line to stdout.

### `preset apply`

- Loads the resolved config file.
- Applies the named preset from `<root>/config/presets`.
- Writes the updated config back to the resolved config path.

### `preset save`

- Loads the resolved config file.
- Saves the current config as a named preset under `<root>/config/presets`.
