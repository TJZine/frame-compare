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
- `--quiet` suppresses the at-a-glance summary but still allows a minimal success summary.
- When the at-a-glance summary reports optional VSPreview probe failures, it uses a
  sanitized summary rather than raw probe exception text.
- `--diagnose-paths` emits a pinned JSON object with keys `cache`, `config`, `input`,
  `output`, and `root`, then exits without invoking the runtime pipeline.
- `--write-config` writes the effective config to disk, then exits without invoking the
  runtime pipeline.

### Report Auto-Open Ownership

- HTML report generation is owned by `frame_compare.services.report`.
- Browser auto-open for a generated report is owned by `frame_compare.cli.entry`.
- The CLI only attempts to open a report when all of these are true:
  - the run succeeded and produced `report_path`
  - `--json` was not used
  - `--quiet` was not used
  - stdout is attached to a TTY
  - the CLI can reload the effective config and `report.auto_open` is true, or the
    post-run config reload fails and the CLI falls back to opening the report anyway

There is currently no dedicated `run` flag for `report.auto_open`; it is a config-only
surface.

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
| `--no-upload` | `slowpics.auto_upload` | Inverted flag: passing it persists `auto_upload = false`. |
| `--force-interactive-alignment` | `audio_alignment.force_interactive` | Also forces `audio_alignment.use_vspreview = true`. |

slow.pics publishing is disabled by default. Users must set `slowpics.auto_upload = true`
in config or through the wizard before `run` uploads generated screenshots.

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
