# Frame Compare

Reproducible frame reviews and slow.pics automation for multi-encode QC.

<!-- tags: frame comparison, ffmpeg, vapoursynth, slow.pics, tmdb, cli -->

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.13+](https://img.shields.io/badge/python-3.13+-3776ab.svg)

## What is this?

Frame Compare scans multiple encodes of the same title and finds
representative frames ready for quality review. It automates audio
alignment, deterministic scene sampling, and optional slow.pics uploads
so reviewers avoid manual scrubbing. The CLI targets home media
archivists, fansub groups, and boutique remastering teams that need
reproducible outputs, VapourSynth or FFmpeg flexibility, and structured
metadata for downstream tooling.

## Quickstart

Requirements:

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/)
- FFmpeg available on your `PATH`
- Optional VapourSynth ≥72 for the primary renderer

```bash
uv sync
cp config.toml.template config.toml
uv run python frame_compare.py --config config.toml --input comparison_videos
```

Fallback when `uv` is unavailable:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -U pip wheel
pip install -e .
python frame_compare.py --config config.toml --input comparison_videos
```

## Minimal example

```bash
uv sync
cp config.toml.template config.toml
uv run python frame_compare.py --config config.toml --input comparison_videos
```

Expected outputs: PNGs under `screens/…`, cached metrics in
`generated.compframes`, and (when audio alignment is enabled) offsets in
`generated.audio_offsets.toml`.

## Configuration essentials

The most common toggles are below; see the
[full reference](docs/README_REFERENCE.md) for every option.

<!-- markdownlint-disable MD013 -->
| Key | What it controls | Default | Example |
| --- | --- | --- | --- |
| `[paths].input_dir` | Base scan directory. | `"comparison_videos"` | `input_dir="comparison_videos"` |
| `--input PATH` | One-off scan override. | `None` | `--input /data/releases` |
| `[analysis].frame_count_dark` | Dark-scene frame quota. | `20` | `frame_count_dark=12` |
| `[analysis].frame_count_motion` | Motion frame quota. | `10` | `frame_count_motion=24` |
| `[analysis].random_frames` | Deterministic random picks. | `10` | `random_frames=8` |
| `[analysis].user_frames` | Always-rendered frame IDs. | `[]` | `user_frames=[10,200,501]` |
| `[analysis].random_seed` | Seed for reproducible runs. | `20202020` | `random_seed=1337` |
| `[audio_alignment].enable` | Audio-guided offsets. | `false` | `enable=true` |
| `[audio_alignment].correlation_threshold` | Confidence gate. | `0.55` | `correlation_threshold=0.65` |
| `[audio_alignment].offsets_filename` | Offset cache path. | `"generated.audio_offsets.toml"` | `offsets_filename="cache/audio.toml"` |
| `[screenshots].directory_name` | PNG output folder. | `"screens"` | `directory_name="frames"` |
| `[screenshots].use_ffmpeg` | Use FFmpeg renderer. | `false` | `use_ffmpeg=true` |
| `[slowpics].auto_upload` | Push to slow.pics. | `true` | `auto_upload=false` |
| `[runtime].ram_limit_mb` | VapourSynth RAM guard. | `4000` | `ram_limit_mb=4096` |
<!-- markdownlint-restore -->

## Features

- Deterministic frame selection blending quantiles, motion scoring,
  pinned frames, and seeded randomness.
- Cached metrics (`generated.compframes` plus selection sidecars) for
  fast reruns across large batches.
- Audio alignment with correlation, dynamic time warping refinements,
  and optional interactive confirmation.
- VapourSynth-first pipeline with FFmpeg fallback, HDR→SDR tonemapping,
  and placeholder recovery when writers fail.
- slow.pics integration with automatic uploads, retries, URL shortcuts,
  and clipboard hand-off.
- TMDB-driven metadata resolution with GuessIt/Anitopy labelling to keep
  comparisons organised.
- Rich CLI layout featuring progress dashboards, Unicode fallbacks, and
  optional JSON tails for automation.
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
