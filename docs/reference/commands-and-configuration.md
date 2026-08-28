# Commands and configuration

This page is the user-facing map of the CLI and configuration system. Use generated
`--help` for the installed version, task guides for normal workflows, and the
[CLI Behavioral Contract](../current-cli-contract.md) when exact precedence,
persistence, JSON, stream, or exit behavior matters.

## Command map

| Command | Purpose |
| --- | --- |
| `frame-compare version` | Print the installed application version |
| `frame-compare wizard` | Create or review configuration interactively |
| `frame-compare doctor` | Diagnose the selected media, UI, and optional integration runtime |
| `frame-compare run` | Validate and execute a comparison |
| `frame-compare history list` | List persisted run results under the selected generated-data root |
| `frame-compare history open RUN_NAME` | Open one exact recorded run |
| `frame-compare preset list` | List saved presets |
| `frame-compare preset save NAME` | Save reusable non-secret configuration |
| `frame-compare preset apply NAME` | Apply a saved preset to the selected configuration |

Discover the options provided by the installed version:

```bash
frame-compare --help
frame-compare run --help
frame-compare doctor --help
frame-compare history --help
frame-compare preset --help
```

## Shared workspace options

Commands that operate on a workspace generally accept:

```text
--root / -r     Select the workspace root
--config / -c   Select the configuration file; relative paths resolve from --root
```

When `--config` is omitted, the normal default is `config/config.toml` beneath the
selected root. The installed Windows shim can inject its documented bundle-local or
AppData fallback configuration.

## Important run modes

| Option or mode | Use |
| --- | --- |
| `--dry-run` | Validate configuration, discovery, source order, frame intent, and output intent without running the pipeline |
| `--diagnose-paths` | Show resolved path ownership and containment decisions |
| `--json` | Emit the documented machine-readable result or error shape |
| `--quiet` | Suppress normal human progress output |
| `--from-cache-only` | Require compatible cached analysis/probe evidence for the supported path |
| `--no-upload` | Force slow.pics upload off for the current run |
| `--overlay MODE` | Override the screenshot overlay for one run |
| `--write-config` | Persist supported CLI-to-config overrides after validation |

Always confirm the installed help text before scripting an option.

## Configuration ownership

| Table | Controls |
| --- | --- |
| `[paths]` | Input, config, and generated-data locations |
| `[sources]` | Reference, analysis source, labels, FPS policy, and per-source overrides |
| `[analysis]` | User/random/metric frame counts, mode, exclusions, and deterministic seed |
| `[audio_alignment]` | Audio stream, correlation, consensus, reuse, and VSPreview behavior |
| `[screenshots]` | Renderer, active-picture detection, geometry, overlays, PNG writer/compression, and timeouts |
| `[color]` | HDR-to-SDR tonemapping preset, target luminance, tone curve, lift, and contrast recovery |
| `[report]` | Static report generation, embedding, and auto-open behavior |
| `[slowpics]` | Explicit publication, visibility, retries, confirmation, and webhook behavior |
| `[tmdb]` | Optional metadata lookup behavior and secret reference |
| `[logging]` | Human or structured logging level and format |

The wizard is the preferred entry point for supported common settings. Use manual TOML
for advanced source overrides and configuration-only behavior.

The former `[diagnostics].per_frame_nits` setting has been removed without replacement.
A stale root `[diagnostics]` table is ignored, but should be deleted from maintained
configuration files. Diagnostic overlays now use observed structured media/render facts;
they never convert selection scores into luminance claims.

## Environment variables and secrets

Pydantic-settings environment variables use the Frame Compare prefix and nested field
separator documented by the configuration contract. Store secrets in the environment or
an external secret manager. Generated config and preset writes omit runtime secrets.

Example webhook variable:

```bash
export FRAME_COMPARE_SLOWPICS__WEBHOOK_URL="<secret>"
```

Do not commit a live value.

## Task-oriented guides

- [Sources, References, and Labels](../guides/sources-and-labels.md)
- [Frame Selection and Analysis](../guides/analysis-modes.md)
- [Audio Alignment and VSPreview](../guides/audio-alignment.md)
- [HDR and Tonemapping](../guides/hdr-tonemapping.md)
- [Reports and Overlays](../guides/reports-and-overlays.md)
- [Presets, History, and Generated Data](../guides/presets-history-generated-data.md)
- [Configuration Recipes](../guides/configuration-recipes.md)

## Automation guidance

For unattended use:

1. Validate the route with `doctor`.
2. Use a committed secret-free config or controlled generated config.
3. Run a dry run in deployment validation.
4. Use `--json` and parse stdout as exactly one JSON document.
5. Treat stderr as diagnostics rather than part of the result payload.
6. Disable interactive confirmations or configure a fail-closed non-interactive path.
7. Persist the generated-data root outside ephemeral containers or replaceable bundles.

The behavioral contract is authoritative for the successful JSON schema, typed error
payload, warning placement, exit codes, and interaction gating.
