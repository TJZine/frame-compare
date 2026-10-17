---
description: Every Frame Compare command and option, and the exit codes it returns.
---

# Commands

Every command and option, with what it changes and whether `--write-config` saves it.
For exact output streams and JSON fields, see the
[CLI behavioral contract](../current-cli-contract.md).

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

`run`, `doctor`, `wizard`, `preset apply`, `preset save`, `history list`, and `history open`
accept both options. `preset list` accepts `--config` but ignores it and reads
presets from `<root>/config/presets`. `version` accepts neither option.

The installed Windows shim supplies the bundle or AppData config when you omit
`--config`; see the contract's [shared path rules](../current-cli-contract.md#shared-path-resolution-rules).

## Run

Options apply to one run; `--write-config` saves the options marked "Saved" and
exits without running.

Runs and dry runs reject `--no-cache` combined with `--from-cache-only`
([`--no-cache` and `--from-cache-only`](../current-cli-contract.md#run-command-contract)).
An invalid `--overlay`, `--tm-preset`, or `--tm-curve` value names the option and
lists its choices before any work starts. Preset names are `reference`, `filmic`,
`contrast`, `bt2390_spec`, `spline`, `bright_lift`, and `highlight_guard`.

`frame-compare run --help` groups the options under the same six headings as this
section.

### Workspace and configuration

#### `--root`, `-r` { #run-root .fc-key }

Value
:   path

Saved by `--write-config`
:   No

Workspace root.

#### `--config`, `-c` { #run-config .fc-key }

Value
:   path

Saved by `--write-config`
:   No

Config file.

### Sources and frame selection

#### `--input`, `-i` { #run-input .fc-key }

Value
:   path

Saved by `--write-config`
:   `paths.input_dir`

Input directory.

#### `--frames` { #run-frames .fc-key }

Value
:   `FRAME[,FRAME…]`

Saved by `--write-config`
:   `analysis.user_frames`

Reference source frames to render.

#### `--random-frame-count` { #run-random-frame-count .fc-key }

Value
:   count

Saved by `--write-config`
:   `analysis.random_frame_count`

Random frames.

#### `--dark-frame-count` { #run-dark-frame-count .fc-key }

Value
:   count

Saved by `--write-config`
:   `analysis.dark_frame_count`

Dark frames; needs analysis.

#### `--bright-frame-count` { #run-bright-frame-count .fc-key }

Value
:   count

Saved by `--write-config`
:   `analysis.bright_frame_count`

Bright frames; needs analysis.

#### `--motion-frame-count` { #run-motion-frame-count .fc-key }

Value
:   count

Saved by `--write-config`
:   `analysis.motion_frame_count`

Motion frames; needs analysis.

#### `--seed` { #run-seed .fc-key }

Value
:   integer

Saved by `--write-config`
:   `analysis.random_seed`

Frame-selection seed.

### Rendering and alignment

#### `--tm-preset` { #run-tm-preset .fc-key }

Value
:   preset name

Saved by `--write-config`
:   `color.preset`

Tonemap preset.

#### `--tm-target` { #run-tm-target .fc-key }

Value
:   nits

Saved by `--write-config`
:   `color.target_nits`

Tonemap target.

#### `--tm-curve` { #run-tm-curve .fc-key }

Value
:   `bt2390`, `spline`, `reinhard`

Saved by `--write-config`
:   `color.tone_curve`

Tonemap curve.

#### `--overlay` { #run-overlay .fc-key }

Value
:   `minimal`, `standard`, `diagnostic`, `none`

Saved by `--write-config`
:   `screenshots.overlay_mode`

Baked overlay mode.

#### `--force-interactive-alignment` { #run-force-interactive-alignment .fc-key }

Saved by `--write-config`
:   `audio_alignment.force_interactive` and `audio_alignment.use_vsview`

Require a successful VSView review.

### Reports and publishing

#### `--no-upload` { #run-no-upload .fc-key }

Saved by `--write-config`
:   `slowpics.auto_upload = false`

Turn slow.pics upload off.

### Planning and diagnostics

#### `--skip-analysis` { #run-skip-analysis .fc-key }

Saved by `--write-config`
:   No

Skip metric analysis; dark, bright, and motion counts must be zero.

#### `--skip-metadata` { #run-skip-metadata .fc-key }

Saved by `--write-config`
:   No

Skip the TMDB lookup.

#### `--no-cache` { #run-no-cache .fc-key }

Saved by `--write-config`
:   No

Refresh the matching shared analysis cache entry: remove it during preparation,
recompute analysis, and persist a fresh entry. Unrelated analysis entries,
alignment reuse, and TMDB caches are preserved. See the
[run command contract](../current-cli-contract.md#run-command-contract).

#### `--from-cache-only` { #run-from-cache-only .fc-key }

Saved by `--write-config`
:   No

Require valid cached analysis; never recompute.

#### `--dry-run` { #run-dry-run .fc-key }

Saved by `--write-config`
:   No

Show what a run would use and create, without side effects.

#### `--write-config` { #run-write-config .fc-key }

Saved by `--write-config`
:   No

Save the effective configuration and exit.

#### `--diagnose-paths` { #run-diagnose-paths .fc-key }

Saved by `--write-config`
:   No

Print resolved paths as JSON and exit.

### Output modes

#### `--json` { #run-json .fc-key }

Saved by `--write-config`
:   No

Machine-readable output on stdout; diagnostics on stderr.

#### `--no-color` { #run-no-color .fc-key }

Saved by `--write-config`
:   No

Plain output.

#### `--quiet`, `-q` { #run-quiet .fc-key }

Saved by `--write-config`
:   No

Hide progress and detailed summaries.

#### `--verbose`, `-v` { #run-verbose .fc-key }

Saved by `--write-config`
:   No

Debug logging and detailed errors.

## Wizard

The wizard requires an interactive terminal. It prompts for the input directory,
generated-data root, reference, and a frame goal (**Random spot check**, **Visual coverage**,
**Specific frame numbers**, or **Keep current frame selection**).

It shows a review and writes only after you confirm, then prints suggested next
commands. See
[Your first comparison](../getting-started/first-comparison.md).

## Doctor

`--root`/`-r` and `--config`/`-c` select the same configuration as `run`.
The root defaults to `.`; doctor does not search parent directories. The installed
Windows shim injects its selected bundle or AppData config for doctor too.
An absent default config uses defaults and environment; an explicit config load
failure appears in the TMDB diagnostic. Invalid or escaping paths fail through the
normal typed command error.

Doctor checks VapourSynth, L-SMASH-Works, vs-placebo, FFMS2, FFmpeg/ffprobe, and
VSView. Its TMDB check validates local configuration and credential format only.
Doctor makes no network requests; slow.pics connectivity is exercised when
publishing. `--json` emits the report as JSON. Doctor exits with the dependency
error code when a required check fails. See the
[doctor command contract](../current-cli-contract.md#doctor-command-contract).

## Preset

Presets live in `<root>/config/presets`; `save` omits secrets. See [Presets, history,
and generated data](../guides/presets-history-generated-data.md).

## History

`list` reads `run_result.toml` records under the generated-data root, with `--json`
available for automation. `open` opens one report by exact name.

## Version

`version` prints `frame-compare <version>`.

## Exit codes

Commands exit with these codes:

| Code | Meaning |
| --- | --- |
| `0` | Success, including a dry run, `--write-config`, a wizard no-op, and a declined wizard confirmation |
| `1` | Unexpected or unclassified error |
| `2` | Configuration error (`FC-1xxx`) or command-line usage error |
| `3` | Dependency error (`FC-2xxx`), including a `doctor` run with a failing required check |
| `4` | Input error (`FC-3xxx`) |
| `5` | Processing error (`FC-4xxx`), or a run that finished unsuccessfully |
| `6` | Network error (`FC-5xxx`) |
| `130` | A run or the wizard interrupted by Ctrl+C, or a wizard prompt aborted or reaching end of input |

The first digit of an `FC-` code selects its family and exit code. Human output prints
the code and message on stderr; `--json` prints a typed error document, described in
the [CLI behavioral contract](../current-cli-contract.md#output-modes).

## Automation

For unattended use:

1. Validate the route with `doctor`.
2. Use a committed secret-free config or controlled generated config.
3. Run a dry run in deployment validation.
4. Use `--json` and parse stdout as exactly one JSON document.
5. Read diagnostics from stderr and the result payload from stdout.
6. Disable native VSView alignment review or configure a fail-closed non-interactive path.
7. Persist the generated-data root outside ephemeral containers or replaceable bundles.

The behavioral contract is authoritative for the successful JSON schema, typed error
payload, warning placement, exit codes, and interaction gating.
