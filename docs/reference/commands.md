# Commands

This page lists every command and option; exact behavior is in the [CLI behavioral contract](../current-cli-contract.md).

## Command map

| Command | Purpose |
| --- | --- |
| `frame-compare version` | Print the installed version |
| `frame-compare wizard` | Set the input directory, generated-data root, reference, and frame selection interactively |
| `frame-compare doctor` | Check the media runtime and optional integrations |
| `frame-compare run` | Compare sources and write screenshots and a report |
| `frame-compare preset list` | List saved presets |
| `frame-compare preset save <name>` | Save the selected configuration as a preset |
| `frame-compare preset apply <name>` | Apply a preset to the selected configuration |
| `frame-compare history list` | List recorded runs, newest first |
| `frame-compare history open <run-name>` | Open one recorded report by its exact run name |

## Shared options

`--root`/`-r` sets the workspace root and defaults to `.`. `--config`/`-c` selects
the config file; relative paths resolve from `--root`, and the default is
`config/config.toml`.

`run`, `wizard`, `preset apply`, `preset save`, `history list`, and `history open`
accept both options. `preset list` accepts `--config` but ignores it and reads
presets from `<root>/config/presets`. `doctor` and `version` accept neither option.

The installed Windows shim supplies the bundle or AppData config when you omit
`--config`; see the contract's [shared path rules](../current-cli-contract.md#shared-path-resolution-rules).

## Run

Options apply to one run; `--write-config` saves the options marked "Saved" and
exits without running.

| Option | Value | Effect | Saved by `--write-config` |
| --- | --- | --- | --- |
| `--root`, `-r` | path | Workspace root | No |
| `--config`, `-c` | path | Config file | No |
| `--input`, `-i` | path | Input directory | `paths.input_dir` |
| `--frames` | `FRAME[,FRAME…]` | Reference source frames to render | `analysis.user_frames` |
| `--random-frame-count` | count | Random frames | `analysis.random_frame_count` |
| `--dark-frame-count` | count | Dark frames; needs analysis | `analysis.dark_frame_count` |
| `--bright-frame-count` | count | Bright frames; needs analysis | `analysis.bright_frame_count` |
| `--motion-frame-count` | count | Motion frames; needs analysis | `analysis.motion_frame_count` |
| `--seed` | integer | Frame-selection seed | `analysis.random_seed` |
| `--tm-preset` | preset name | Tonemap preset | `color.preset` |
| `--tm-target` | nits | Tonemap target | `color.target_nits` |
| `--tm-curve` | `bt2390`, `spline`, `reinhard` | Tonemap curve | `color.tone_curve` |
| `--overlay` | `minimal`, `standard`, `diagnostic`, `none` | Baked overlay mode | `screenshots.overlay_mode` |
| `--force-interactive-alignment` | — | Require a successful VSView review | `audio_alignment.force_interactive` and `audio_alignment.use_vsview` |
| `--no-upload` | — | Turn slow.pics upload off | `slowpics.auto_upload = false` |
| `--skip-analysis` | — | Skip metric analysis; dark, bright, and motion counts must be zero | No |
| `--skip-metadata` | — | Skip the TMDB lookup | No |
| `--no-cache` | — | Do not read or write the analysis cache | No |
| `--from-cache-only` | — | Require valid cached analysis; never recompute | No |
| `--dry-run` | — | Show what a run would use and create, without side effects | No |
| `--write-config` | — | Save the effective configuration and exit | No |
| `--diagnose-paths` | — | Print resolved paths as JSON and exit | No |
| `--json` | — | Machine-readable output on stdout; diagnostics on stderr | No |
| `--no-color` | — | Plain output | No |
| `--quiet`, `-q` | — | Hide progress and detailed summaries | No |
| `--verbose`, `-v` | — | Debug logging and detailed errors | No |

Runs and dry runs reject `--no-cache` combined with `--from-cache-only`
([`--no-cache` and `--from-cache-only`](../current-cli-contract.md#run-command-contract)).
An invalid `--overlay`, `--tm-preset`, or `--tm-curve` value names the option and
lists its choices before any work starts. Preset names are `reference`, `filmic`,
`contrast`, `bt2390_spec`, `spline`, `bright_lift`, and `highlight_guard`.

`frame-compare run --help` lists the same options under six headings: Workspace and
configuration, Sources and frame selection, Rendering and alignment, Reports and
publishing, Planning and diagnostics, and Output modes.

## Wizard

The wizard requires an interactive terminal. It prompts for the input directory,
generated-data location, reference, and a frame goal (`Random spot check`, `Visual
coverage`, `Specific frame numbers`, or `Keep current frame selection`). It shows a
review and writes only after you confirm, then prints suggested next commands. See
[Your first comparison](../guides/first-comparison.md).

## Doctor

Doctor checks VapourSynth, L-SMASH-Works, vs-placebo, FFMS2, FFmpeg, VSView, and the
optional slow.pics and TMDB integrations. `--json` emits the report as JSON. Doctor
exits with the dependency error code when a required check fails. The slow.pics check
contacts the service.

## Preset

Presets live in `<root>/config/presets`; `save` omits secrets. See [Presets, history,
and generated data](../guides/presets-history-generated-data.md).

## History

`list` reads `run_result.toml` records under the generated-data root, with `--json`
available for automation. `open` opens one report by exact name.

## Version

`version` prints `frame-compare <version>`.

## Exit codes

See [exit codes and error families](../current-cli-contract.md#exit-codes-and-error-families).

## Automation

For unattended use:

1. Validate the route with `doctor`.
2. Use a committed secret-free config or controlled generated config.
3. Run a dry run in deployment validation.
4. Use `--json` and parse stdout as exactly one JSON document.
5. Treat stderr as diagnostics rather than part of the result payload.
6. Disable native VSView alignment review or configure a fail-closed non-interactive path.
7. Persist the generated-data root outside ephemeral containers or replaceable bundles.

The behavioral contract is authoritative for the successful JSON schema, typed error
payload, warning placement, exit codes, and interaction gating.
