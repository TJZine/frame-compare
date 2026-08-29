# Presets, history, and generated data

Frame Compare separates authored configuration from generated run state. Presets help
reuse intentional settings, while history reads persisted run results from the selected
generated-data root.

## Choose a durable generated-data location

`paths.generated_dir` owns:

- reserved run folders;
- screenshots and reports;
- run lifecycle records;
- shared analysis, probe, and alignment caches;
- run-local generated state.

For Windows portable installs, choose a normal directory outside the replaceable bundle
when reports and reusable state must survive a reinstall, update rollback, or bundle
move.

```toml
[paths]
generated_dir = "D:/FrameCompareData"
```

Environment variables and platform-specific path rules are documented in the
[CLI Behavioral Contract](../current-cli-contract.md#shared-path-resolution-rules).

## Run-folder layout

```text
<generated-data-root>/
├── cache/
│   ├── analysis/
│   └── alignment/
├── clip_probe.toml
└── <run-name>/
    ├── report.html
    ├── screenshots/
    ├── generated/
    ├── run_info.toml
    └── run_result.toml
```

The top-level shared cache is not a history entry. Each immediate run folder is
self-contained for review, while selected caches remain reusable across compatible runs.

See [Output Layout](../reference/output-layout.md) for ownership and portability rules.

## List recorded runs

```bash
frame-compare history list
```

The list uses persisted lifecycle records and reports `completed`,
`completed_with_warnings`, `failed`, or `unavailable` entries. It does not require the
original media to remain at its old path.

For structured automation:

```bash
frame-compare history list --json
```

## Open an exact run

```bash
frame-compare history open <run-name>
```

History uses exact run names rather than fuzzy matching. It is read-only: the current
command surface does not rename, delete, replay, or migrate runs.

## Save a preset

```bash
frame-compare preset save publication-quality
```

Presets are appropriate for reusable comparison intent such as frame counts, overlays,
analysis mode, and publishing policy. Generated preset files omit runtime secrets.

## Apply a preset

```bash
frame-compare preset apply publication-quality
```

Review the resulting configuration or use a dry run before rendering. Presets do not
prove that new sources have compatible trims, FPS, audio, crop, or HDR properties.

## List presets

```bash
frame-compare preset list
```

## Secrets are not preset data

Generated configuration and preset writes exclude sensitive values such as webhook URLs
and TMDB API keys. Supply secrets through environment variables or an external secret
manager rather than committing them to TOML.

## Cache maintenance

Cache reuse is performance-first. Source identity uses path, size, and modification time
rather than hashing multi-gigabyte media. If a workflow replaces media while preserving
all three values, clear the relevant cache or advance the modification time.

For unmanaged native runtimes, clear generated caches and Frame Compare-owned indexes
after replacing FFmpeg, VapourSynth, or decoder/plugin binaries outside the managed
profile contract.

Do not delete the complete generated-data root merely to solve one stale entry. Remove
the smallest relevant cache or run directory after confirming it is safe to discard.
