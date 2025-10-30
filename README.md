# Frame Compare

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.13+](https://img.shields.io/badge/python-3.13+-3776ab.svg)

Automated frame sampling, alignment, tonemapping, and slow.pics uploads for deterministic encode comparisons.

## Table of Contents
  - [Overview](#overview)
  - [Features](#features)
  - [Quickstart](#quickstart)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Configuration](#configuration)
  - [CLI Reference](#cli-reference)
  - [Examples](#examples)
  - [Troubleshooting](#troubleshooting)
  - [FAQ](#faq)
  - [Performance](#performance)
  - [Security](#security)
  - [Privacy \& Telemetry](#privacy--telemetry)
  - [Versioning](#versioning)
  - [Contributing](#contributing)
  - [License](#license)
  - [Support](#support)

## Overview

Frame Compare samples darkest, brightest, high-motion, random, and user-pinned frames across multiple encodes of the same title. It aligns audio, renders deterministic PNGs through VapourSynth or FFmpeg, and can ship finished sets to slow.pics with TMDB naming. The CLI targets home media archivists, fansub QC crews, and boutique remastering teams that need repeatable comparisons, live dashboards, and machine-readable metadata for downstream tooling.

## Features

- Deterministic frame selection blending luminance quantiles, motion scoring, pinned frames, and seeded randomness.
- Cached metrics (`generated.compframes` plus selection sidecars) for fast reruns across large batches.
- Audio alignment with correlation, dynamic time warping refinements, and optional interactive confirmation frames.
- VapourSynth-first pipeline with FFmpeg fallback, HDR→SDR tonemapping, and placeholder recovery when writers fail.
- slow.pics integration with automatic uploads, retries, URL shortcuts, and clipboard hand-off.
- Optional HTML report generation for offline, browser-based comparisons with slider/overlay modes, pointer-anchored zoom + fit presets, and persistent pan/align controls inspired by slow.pics.
- TMDB-driven metadata resolution with GuessIt/Anitopy labelling to keep comparisons organised.
- Rich CLI layout featuring progress dashboards, Unicode fallbacks, batch auto-grouping, and optional JSON tails for automation.
- CLI override for audio stream selection (`--audio-align-track`) when auto-detection needs guidance.
- Configurable RAM guardrails and VapourSynth path injection for multi-host deployments.
- Optional clipboard support (`pyperclip`) to copy slow.pics links after uploads.

## Quickstart

Requirements:

- Python 3.13.x
- [uv](https://docs.astral.sh/uv/)
- [FFmpeg](https://ffmpeg.org/) and `ffprobe` on your `PATH`
- VapourSynth ≥72 (optional, enables the primary renderer)
- Optional audio-alignment stack: `numpy`, `librosa`, `soundfile`

1. Install dependencies and ensure the workspace config exists:

   ```bash
   uv sync
   uv run python -m frame_compare --write-config
   ```

2. Create a minimal comparison set and run the pipeline:

   ```bash
   mkdir -p comparison_videos/quickstart
   ffmpeg -y -f lavfi -i color=c=black:s=640x360:d=2 -vf "drawtext=text=SourceA:fontsize=48:x=20:y=20" comparison_videos/quickstart/clip-a.mp4
   ffmpeg -y -f lavfi -i color=c=blue:s=640x360:d=2 -vf "drawtext=text=SourceB:fontsize=48:x=20:y=20" comparison_videos/quickstart/clip-b.mp4

   uv run python -m frame_compare --root . --input comparison_videos/quickstart
   ```

One-line usage after setup:

```bash
uv run python -m frame_compare --root .
```

Expected outputs: PNGs under `comparison_videos/quickstart/screens`, cached metrics in `generated.compframes`, optional offsets in `generated.audio_offsets.toml`, and a slow.pics shortcut when uploads succeed.

> **Tip:** Run `uv run python -m frame_compare --diagnose-paths` to confirm workspace, config, and screenshot directories before heavy runs.

## Installation

| Method | When to use | Commands |
| ------ | ----------- | -------- |
| `uv` (recommended) | Isolated, reproducible environments | `uv sync`<br>`uv pip install vapoursynth` *(optional, for VS renderer)* |
| `pip` | System or virtualenv workflows | `python3.13 -m venv .venv`<br>`source .venv/bin/activate`<br>`pip install -U pip wheel`<br>`pip install -e .` |

Optional extras:

| Feature | Extras |
| ------- | ------ |
| VapourSynth renderer | `uv pip install vapoursynth` |
| VSPreview manual alignment | `uv pip install vspreview PySide6` *(or add the `preview` dependency group)* |
| slow.pics clipboard shortcut | `uv pip install pyperclip` |

> **Note:** Follow the [official VapourSynth installation guide](https://www.vapoursynth.com/doc/installation.html) for OS-specific runtime packages. Ensure the Python bindings are importable (e.g., set `VAPOURSYNTH_PYTHONPATH` on Linux/macOS).

## Usage

Frame Compare operates within a **workspace root** that controls config, media, and outputs. Root detection order:

1. `--root` flag
2. `$FRAME_COMPARE_ROOT`
3. Nearest ancestor containing `pyproject.toml`, `.git`, or `comparison_videos`
4. Current working directory

Within the root, each comparison lives under `comparison_videos/<set>/` with at least two supported video files.

Common commands:

```bash
# Seed config without running the pipeline
uv run python -m frame_compare --root /path/to/workspace --write-config

# Run the default pipeline (tonemapping, VapourSynth if available)
uv run python -m frame_compare --root /path/to/workspace

# Inspect resolved paths and writability
uv run python -m frame_compare --root /path/to/workspace --diagnose-paths

# Force FFmpeg screenshots for environments without VapourSynth
uv run python -m frame_compare --root /path --config config/config.toml --json-pretty --no-color

# Launch the interactive wizard (prompts for workspace, renderer, slow.pics)
uv run python -m frame_compare --root /path/to/workspace wizard

# Check dependency readiness (non-fatal, supports --json)
uv run python -m frame_compare --root /path/to/workspace doctor

# Apply a preset without prompts (non-interactive safe)
uv run python -m frame_compare --root /path/to/workspace preset apply quick-compare
```

> **Tip:** The first interactive run now launches the wizard automatically when `config/config.toml` is missing. Opt out with `--no-wizard` or by setting `FRAME_COMPARE_NO_WIZARD=1`.

### Wizard & Presets

`frame-compare wizard` guides you through workspace selection, input discovery, slow.pics options, audio alignment, and renderer preference. When stdin is not a TTY, supply `--preset <name>` to reuse a predefined profile without hanging automation.

The same prompts appear automatically on an interactive first run so new users can capture tailored settings without memorising command flags.

Available presets can be listed with `frame-compare preset list`. They ship with:

- `quick-compare` – minimal sampling, FFmpeg renderer, slow.pics disabled.
- `hdr-vs-sdr` – tonemap-focused defaults with stricter verification.
- `batch-qc` – expanded sampling quotas with slow.pics uploads enabled.

Use `frame-compare preset apply <name>` to seed `config/config.toml` in one step, optionally alongside `--root`/`--config` overrides.

### Dependency Doctor

`frame-compare doctor` performs fast, read-only diagnostics for VapourSynth, FFmpeg, audio extras, VSPreview tooling, slow.pics networking, clipboard helpers, and config writability. It always exits with code 0, making it safe to run during install scripts, and supports `--json` for machine-readable integrations. The wizard invokes it automatically after collecting answers so you can decide whether to continue when optional dependencies are missing.

Outputs are written beneath the input directory: screenshots under `screens` (configurable), cached metrics alongside video inputs, slow.pics shortcuts in the same directory, and a JSON summary on stdout. Shortcut filenames mirror the resolved slow.pics collection name.

> **Warning:** The default `[slowpics].delete_screen_dir_after_upload = true` removes the screenshots directory after successful uploads. Keep `screenshots.directory_name` relative to the input root and avoid reusing directories shared with other projects.

## Configuration

Frame Compare seeds `config/config.toml` from `src/data/config.toml.template`. Override the path with `--config` or `$FRAME_COMPARE_CONFIG`. Legacy `ROOT/config.toml` is still read but emits a migration warning.

Configuration highlights:

- `[paths].input_dir` controls the media subdirectory (default `comparison_videos`).
- Workspace guardrails keep everything under the resolved root: the CLI refuses `site-packages` roots, auto-seeds `ROOT/config/config.toml`, validates writability up front, and blocks relative paths that escape the workspace. Run `frame-compare --diagnose-paths` to confirm the resolved locations when in doubt.
- `[analysis]` governs frame quotas, random seed, and metric cache filename.
- `[screenshots]` selects renderer, geometry policy, dithering, and output directory name.
- `[color]` sets tonemap preset (`reference`, `contrast`, `filmic`), verification options, overlay text, and strictness.
- `[audio_alignment]` enables correlation, VSPreview hooks, offsets filename, and bias.
- `[slowpics]` toggles auto uploads (disabled by default), visibility, cleanup, webhook URL, and timeout.
- `[report]` enables the offline HTML report, output directory, default comparison pair, and auto-open behaviour.
- `[runtime]` sets VapourSynth memory guards and module search paths.
- `[overrides]` applies per-source trims and FPS adjustments.

Environment variables:

| Name | Purpose |
| ---- | ------- |
| `FRAME_COMPARE_ROOT` | Workspace root override |
| `FRAME_COMPARE_CONFIG` | Explicit config file path |
| `FRAME_COMPARE_TEMPLATE_PATH` | Custom config template location |
| `VAPOURSYNTH_PYTHONPATH` | Additional module path when VapourSynth bindings live outside the environment |

Common toggles (see [docs/README_REFERENCE.md](docs/README_REFERENCE.md) for full coverage):

| Key | Controls | Default | Example |
| --- | --- | --- | --- |
| `[paths].input_dir` | Base scan directory under the workspace root. | `"comparison_videos"` | `input_dir="projects/comparisons"` |
| `--input PATH` | One-off scan override. | `None` | `--input /data/releases` |
| `[analysis].frame_count_dark / frame_count_bright` | Scene quotas for shadows/highlights. | `20 / 10` | `frame_count_dark=12` |
| `[analysis].frame_count_motion` | Motion-heavy frame quota. | `15` | `frame_count_motion=24` |
| `[analysis].random_frames / random_seed` | Deterministic random picks. | `15 / 20202020` | `random_frames=8` |
| `[analysis].user_frames` | Always-rendered frame IDs. | `[]` | `user_frames=[10,200,501]` |
| `[audio_alignment].enable` (+`confirm_with_screenshots`) | Audio-guided offsets and preview pause. | `false` (`true`) | `enable=true` |
| `[screenshots].use_ffmpeg` | Prefer FFmpeg renderer. | `false` | `use_ffmpeg=true` |
| `[report].enable` (+`--html-report` / `--no-html-report`) | Generate the local HTML report and auto-open it. | `false` | `enable=true` |
| `[report].default_mode` | Initial viewer mode (`slider` or `overlay`). | `"slider"` | `default_mode="overlay"` |
| `[slowpics].auto_upload` | Upload results to slow.pics. | `false` | `auto_upload=true` |
| `[runtime].ram_limit_mb` | VapourSynth RAM guard. | `4000` | `ram_limit_mb=3072` |

Offline HTML reports mirror slow.pics ergonomics: Actual/Fit/Fill presets, an alignment selector, pointer-anchored zoom via the slider, +/- buttons, or Ctrl/⌘ + mouse wheel, and pan support (space + drag or regular drag once zoomed beyond fit). Zoom, fit, mode, and alignment choices persist in `localStorage` so every frame opens with the same viewer state.

> **Tip:** To seed another workspace, run `uv run python -m frame_compare --root alt-root --write-config`.

## CLI Reference

| Flag | Description |
| ---- | ----------- |
| `--root PATH` | Override workspace root discovery |
| `--config PATH` | Use a specific config file (falls back to `FRAME_COMPARE_CONFIG`) |
| `--input PATH` | Override `[paths].input_dir` for a single run |
| `--audio-align-track label=index` | Force the audio stream used per clip (repeatable) |
| `--write-config` | Ensure `ROOT/config/config.toml` exists, then exit |
| `--diagnose-paths` | Print JSON diagnostics (root, media, screens, writability) |
| `--quiet` / `--verbose` | Adjust console verbosity |
| `--no-color` | Disable ANSI colour output |
| `--json-pretty` | Pretty-print the JSON tail |
| `--help` | Display Click help |

Exit codes:

- `0` — success
- `2` — configuration or preflight error (invalid root, missing dependencies)
- `3` — runtime failure (rendering, uploads, analysis)
- `>3` — reserved for module-specific errors (`AudioAlignmentError`, `SlowpicsAPIError`, etc.)

## Examples

### VSPreview manual alignment assistant

1. Enable VSPreview support:

   ```toml
   [audio_alignment]
   enable = true
   use_vspreview = true
   confirm_with_screenshots = false  # let VSPreview handle the pause
   ```

2. Install the extras once per environment:

   ```bash
   uv pip install vspreview PySide6
   ```

3. Run the CLI interactively:

   ```bash
   uv run python -m frame_compare --root /workspace
   ```

The CLI launches VSPreview, summarises existing manual trims using friendly labels, and writes accepted offsets to `generated.audio_offsets.toml`. Headless sessions skip the launch but print the generated script path for manual review.

> **Note:** On legacy Windows consoles (`cp1252`), VSPreview helper logs use ASCII arrows (`->`, `<->`) to avoid encoding issues. Switch to UTF-8 with `chcp 65001` or run inside Windows Terminal for full Unicode output.

### Path diagnostics before heavy runs

```bash
uv run python -m frame_compare --root /workspace --diagnose-paths
```

This prints a single JSON object showing root, media, screenshot directories, whether they exist, and writability flags so you can catch site-packages or read-only locations early.

### FFmpeg-only captures

When VapourSynth is unavailable:

```toml
[screenshots]
use_ffmpeg = true
ffmpeg_timeout_seconds = 0  # disable per-frame timeout if desired
```

```bash
uv run python -m frame_compare --root /workspace --quiet
```

The renderer promotes subsampled SDR clips to YUV444P16 before cropping/padding, preventing mod-2 geometry failures.

## Troubleshooting

- **FFmpeg or VapourSynth not found:** ensure binaries are on `PATH`, set `VAPOURSYNTH_PYTHONPATH`, or install the Python bindings. The CLI falls back to FFmpeg when `[screenshots].use_ffmpeg = true`.
- **Workspace root is not writable:** choose another root via `--root` or `FRAME_COMPARE_ROOT`. Frame Compare refuses to run inside `site-packages`/`dist-packages`.
- **HDR renders look dim:** switch `[color].preset = "filmic"` or disable `[color].enable_tonemap` for SDR sources.
- **slow.pics upload fails:** if uploads are enabled (`[slowpics].auto_upload = true`), ensure network access and inspect the JSON tail for per-frame status. Adjust `[slowpics].image_upload_timeout_seconds` for slow links.
- **Placeholder PNGs appear:** review console warnings for renderer errors, then retry with FFmpeg or install missing VapourSynth plugins/codecs.
- **Audio alignment dependency errors:** install `numpy`, `librosa`, `soundfile`. Failures raise `AudioAlignmentError` with the missing import.
- **VSPreview fails to launch:** ensure PySide6 (or PyQt5) is installed and run from an interactive terminal. Non-interactive shells bypass the GUI launch by design.

## FAQ

**How do I change the screenshot output folder?**  
Set `[screenshots].directory_name` to a relative path. Containment checks block absolute paths outside the workspace unless the directory existed beforehand (cleanup is skipped in that case).

**How do I opt into slow.pics uploads?**  
Set `[slowpics].auto_upload = true` when you want automatic uploads; leave it `false` to keep runs local.

**Where are cached metrics stored?**  
`[analysis].frame_data_filename` (default `generated.compframes`) is written next to the comparison directory.

**Which operating systems are supported?**  
macOS, Linux, and Windows (64-bit Python 3.13+). VapourSynth support requires matching architecture builds. FFmpeg is mandatory across all platforms.

**Is there a GUI?**  
The pipeline is CLI-driven. VSPreview provides an optional GUI for manual alignment checks.

## Performance

- Metric caches let you reuse analysis results when inputs and settings match the stored `selection_hash`.
- Tonemapping runs once per clip with verification frames selected via `[color].verify_*` settings.
- Audio alignment extracts mono waveforms at configurable sample rates for faster correlation.
- Use `[analysis].save_frames_data = false` when caches are unnecessary to reduce IO pressure.
- Quiet runs (`--quiet`) cut console overhead for large batches while preserving JSON output.

## Security

- Workspace guardrails prevent writes inside `site-packages` and require writable roots before execution.
- `_path_is_within_root` ensures screenshot cleanup and caches stay under the workspace root.
- slow.pics uploads run over HTTPS and redact webhook hostnames in logs.
- TMDB API keys live in config files you control; no secrets are written elsewhere.

> **Warning:** Misconfiguring `[screenshots].directory_name` to point at shared directories may still delete pre-existing contents after upload, even with containment checks. Use dedicated directories per run.

## Privacy & Telemetry

Frame Compare sends no telemetry. Network calls occur only when:

- `[slowpics].auto_upload = true` (uploads PNGs to `https://slow.pics/`, optional webhook POST)
- `[tmdb].api_key` is provided (queries TMDB endpoints)

Disable these features to run entirely offline—screenshots and caches remain local.

## Versioning

Current version: `0.0.1`. Until 1.0 the API may change without notice. See [CHANGELOG.md](CHANGELOG.md) for detailed history. Recent highlights:

- 2025-10-21: Hardened VSPreview helper output on Windows consoles.
- 2025-10-20: Added odd-geometry YUV444 pivots and refreshed tonemap documentation.
- 2025-10-16: Locked workspace root discovery and enforced path containment.

## Contributing

1. Fork and clone the repository.
2. Install development dependencies:

   ```bash
   uv sync --group dev
   ```

3. Run quality checks:

   ```bash
   uv run pytest -q
   uv run pyright --warnings
   uv run ruff check
   ```

4. Add regression tests for behavioural changes and document decisions in `docs/DECISIONS.md` plus user-visible updates in `CHANGELOG.md`.

> **Tip:** Type hints are mandatory. Avoid introducing `Any`; guard `Optional[...]` values explicitly to satisfy Pyright.

## License

Distributed under the [MIT License](LICENSE). Frame Compare builds on FFmpeg, VapourSynth, slow.pics, TMDB, GuessIt, Anitopy, and the wider Python ecosystem.

## Support

- Runs on macOS, Linux, and Windows (64-bit). Ensure FFmpeg is on `PATH` and VapourSynth is installed when opting into the primary renderer.
- Consult the in-repo guides for deeper dives: [docs/audio_alignment_pipeline.md](docs/audio_alignment_pipeline.md), [docs/geometry_pipeline.md](docs/geometry_pipeline.md), [docs/hdr_tonemap_overview.md](docs/hdr_tonemap_overview.md), [docs/context_summary.md](docs/context_summary.md).
- File issues or feature requests via the GitHub issue tracker. For security concerns, open a private advisory so details remain confidential until patched.
