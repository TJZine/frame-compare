---
description: Where Frame Compare keeps run folders and caches, how to reopen past runs, and how to save presets.
---

# Presets, history, and generated data

Frame Compare keeps your configuration separate from what runs produce. This guide
covers where run folders and caches go, how to reopen a past run, and how to save
settings
as a preset.

## Choose a durable generated-data location

`paths.generated_dir` sets the generated-data root, which holds:

- reserved run folders;
- screenshots and reports;
- run lifecycle records;
- shared analysis, probe, and alignment caches;
- run-local generated state.

A Windows portable reinstall moves the bundle's non-empty `generated/` folder by
default. Use `install.cmd -UserData Leave` to keep it in the active bundle when you
switch. To use one generated-data root across bundles, set an external path in the
config you use with both.

```toml
[paths]
generated_dir = "D:/FrameCompareData"
```

Choose a user-writable directory. The Windows installer and uninstaller leave
external generated-data roots in place. Review the
[Windows reinstall steps](../getting-started/windows-portable.md#update-behavior)
before switching bundles.

Environment variables and platform-specific path rules are documented in the
[CLI behavioral contract](../current-cli-contract.md#shared-path-resolution-rules).

## Run-folder layout

```text
<generated-data-root>/
├── cache/
├── clip_probe.toml
└── <run-name>/
    ├── report.html
    ├── screenshots/
    ├── alignment_diagnostics/
    ├── generated/
    ├── run_info.toml
    └── run_result.toml
```

History reads persisted run results from the selected generated-data root. It excludes
the top-level shared cache. Each immediate run folder is self-contained for review,
while selected caches remain reusable across compatible runs.

See [Output layout](../reference/output-layout.md) for ownership and portability rules.

## List recorded runs

```bash
frame-compare history list
```

The table shows the run name, local date and time, source and frame counts when
available, status, and whether a report is available. It can show `completed`,
`completed with warnings`, `failed`, `interrupted`, or `unavailable`. Older
interrupted runs may still show `failed`. You can list recorded runs after moving
the original media.

For structured automation:

```bash
frame-compare history list --json
```

## Open an exact run

```bash
frame-compare history open <run-name>
```

History opens the exact run name you give it. It uses no fuzzy matching and is
read-only:
it does not rename, delete, replay, or migrate runs.

## Save a preset

```bash
frame-compare preset save publication-quality
```

Use presets to reuse settings such as frame counts, overlays, analysis mode, and
publishing policy. Generated preset files omit runtime secrets.
User-authored symlinks for the preset directory remain supported: `preset save` follows
the directory link and writes the preset file to its resolved target.

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
manager. Keep them out of committed TOML files.

## Cache maintenance

Analysis and alignment reuse identify sources by path, size, and modification
time without hashing the full source file. If a workflow replaces media while
preserving all three values, clear the relevant cache or advance the modification
time. Probe facts and decoder indexes use a stronger filesystem identity that
includes change time for reuse between runs.

For unmanaged native runtimes, clear generated caches and Frame Compare-owned indexes
after replacing FFmpeg, VapourSynth, or decoder/plugin binaries outside the managed
profile contract.

Do not delete the complete generated-data root merely to solve one stale entry. Remove
the smallest relevant cache or run folder after confirming it is safe to discard.
