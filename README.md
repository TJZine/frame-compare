# Frame Compare

Automated frame sampling, alignment, and slow.pics uploads for repeatable QC.

<!-- tags: frame comparison, ffmpeg, vapoursynth, slow.pics, tmdb, cli -->

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.13+](https://img.shields.io/badge/python-3.13+-3776ab.svg)

## What is this?

Frame Compare samples darkest, brightest, high-motion, random, and
user-pinned frames across multiple encodes of the same title. It aligns
audio, renders deterministic PNGs through VapourSynth or FFmpeg, and can
ship finished sets to slow.pics with TMDB naming. The CLI targets home
media archivists, fansub QC crews, and boutique remastering teams that
need repeatable comparisons, live dashboards, and machine-readable
metadata for downstream tooling.

## Quickstart

Requirements:

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/)
- FFmpeg available on your `PATH`
- VapourSynth ≥72 if you plan to use the primary renderer (install manually; see below)

Repository fixtures live under `comparison_videos/` beside
`frame_compare.py`; they provide tiny MKV stubs suitable for smoke
tests and match the default `paths.input_dir`.

```bash
uv sync
# install the VapourSynth runtime manually (see the steps below)
uv pip install vapoursynth  # or `uv add vapoursynth` to persist it to your project
uv run python frame_compare.py
```

The CLI ships with a configuration template stored at `data/config.toml.template`. Frame Compare loads that packaged template by default so the CLI works out of the box. When you want to edit the defaults, copy the template to a writable location—`python -c "from src.config_template import copy_default_config; copy_default_config('~/frame_compare.toml')"` is a quick way—and point the CLI at it with `--config` or by setting `$FRAME_COMPARE_CONFIG`.

Install VapourSynth manually after `uv sync` so the renderer is available:

1. Follow the [official VapourSynth installation guide](https://www.vapoursynth.com/doc/installation.html) for your OS to install the core runtime (`vspipe`, libraries, and plugins). Package managers such as Homebrew, AUR, or `apt` provide maintained builds, and Windows users should run the official installer.
2. Ensure the VapourSynth Python module directory is on `VAPOURSYNTH_PYTHONPATH` (Linux/macOS) or registered via the installer (Windows) so it can be discovered by Python.
3. Activate your `uv` environment and install the Python bindings with `uv pip install vapoursynth`. Run `uv add vapoursynth` instead if you want the dependency recorded in `pyproject.toml` for future syncs.

Fallback when `uv` is unavailable:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -U pip wheel
pip install -e .
python frame_compare.py
```

## Minimal example

```bash
uv sync
uv pip install vapoursynth  # or `uv add vapoursynth`
uv run python frame_compare.py
```

Expected outputs: PNGs under `screens/…`, cached metrics in
`generated.compframes`, optional offsets in
`generated.audio_offsets.toml`, and (when uploads are enabled) a
slow.pics shortcut file.

## Configuration essentials

Frame Compare looks for its configuration at the path specified by the
``$FRAME_COMPARE_CONFIG`` environment variable. When the variable is unset, the
CLI uses ``config.toml`` alongside ``frame_compare.py``. If that file does not
exist, the CLI seeds it from the bundled ``data/config.toml.template`` before
loading so a fresh checkout is immediately runnable. To customise the
settings, edit ``config.toml`` directly or copy the template to another
writable location with ``python -c 'from src.config_template import
copy_default_config; copy_default_config("~/frame-compare.toml")'`` and either
set ``$FRAME_COMPARE_CONFIG`` or pass ``--config`` when invoking the CLI.

The most common toggles are below; see the
[full reference](docs/README_REFERENCE.md) for every option.

<!-- markdownlint-disable MD013 -->
| Key | What it controls | Default | Example |
| --- | --- | --- | --- |
| `[paths].input_dir` | Base scan directory. | `"comparison_videos"` | `input_dir="comparison_videos"` |
| `--input PATH` | One-off scan override. | `None` | `--input /data/releases` |
| `[analysis].frame_count_dark / frame_count_bright` | Scene quotas for shadows and highlights. | `20 / 10` | `frame_count_dark=12` |
| `[analysis].frame_count_motion` | Motion-heavy frame quota. | `10` | `frame_count_motion=24` |
| `[analysis].random_frames / random_seed` | Deterministic random picks. | `10 / 20202020` | `random_frames=8` |
| `[analysis].user_frames` | Always-rendered frame IDs. | `[]` | `user_frames=[10,200,501]` |
| `[audio_alignment].enable (+confirm_with_screenshots)` | Audio-guided offsets and optional preview pause. | `false (true)` | `enable=true` |
| `[screenshots].use_ffmpeg` | Use FFmpeg renderer. | `false` | `use_ffmpeg=true` |
| `[slowpics].auto_upload` | Push to slow.pics. | `true` | `auto_upload=false` |
| `[runtime].ram_limit_mb` | VapourSynth RAM guard. | `4000` | `ram_limit_mb=4096` |
<!-- markdownlint-restore -->

## Features

- Deterministic frame selection blending luminance quantiles, motion
  scoring, pinned frames, and seeded randomness.
- Cached metrics (`generated.compframes` plus selection sidecars) for
  fast reruns across large batches.
- Audio alignment with correlation, dynamic time warping refinements,
  and optional interactive confirmation frames.
- VapourSynth-first pipeline with FFmpeg fallback, HDR→SDR tonemapping,
  and placeholder recovery when writers fail.
- slow.pics integration with automatic uploads, retries, URL shortcuts,
  and clipboard hand-off.
- TMDB-driven metadata resolution with GuessIt/Anitopy labelling to keep
  comparisons organised.
- Rich CLI layout featuring progress dashboards, Unicode fallbacks,
  batch auto-grouping, and optional JSON tails for automation.
- CLI override for audio stream selection (`--audio-align-track`) when
  auto-detection needs guidance.
- Configurable RAM guardrails and VapourSynth path injection for
  multi-host deployments.
- Optional clipboard support (`pyperclip`) to copy slow.pics links after
  uploads.

## Performance & troubleshooting

- **FFmpeg or VapourSynth not found:** ensure binaries are on `PATH`, set
  `VAPOURSYNTH_PYTHONPATH`, or populate
  `[runtime].vapoursynth_python_paths`. The CLI falls back to FFmpeg
  captures when `use_ffmpeg=true`.
- **High RAM usage:** lower `[runtime].ram_limit_mb` or
  `[analysis].downscale_height`; VapourSynth reloads clips automatically
  if limits are hit.
- **HDR renders look dim:** disable `[color].enable_tonemap` for SDR
  sources or switch `[color].preset` to `filmic` for brighter curves.
- **slow.pics upload fails:** keep `[slowpics].auto_upload=true`, ensure
  network access, and inspect the slow.pics response in the JSON tail if
  retries exhaust.
- **Placeholder PNGs appear:** review console warnings for the failed
  renderer, then retry with `use_ffmpeg=true` or install the missing
  VapourSynth plugin/codec.

## Compatibility & support

- Runs on macOS, Linux, and Windows (64-bit Python 3.13+) with FFmpeg
  available; VapourSynth support requires matching architecture builds.
- File issues or feature requests via the GitHub issue tracker. For
  security concerns, open a private GitHub security advisory so details
  stay confidential until patched.

## Contributing

Dev env: `uv sync --group dev` · Lint: `uv run ruff` · Test: `uv run pytest -q`.
Please follow conventional commits, add regression tests for behavioural
changes, and keep docs aligned with new flags.

## License & acknowledgements

Distributed under the [MIT License](LICENSE). Frame Compare builds on
FFmpeg, VapourSynth, slow.pics, TMDB, GuessIt, Anitopy, and the wider
Python ecosystem.

## Changelog

See [CHANGELOG.md](CHANGELOG.md). README last updated 2025-10-11
(America/New_York).
