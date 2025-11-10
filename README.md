# Frame Compare

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.13+](https://img.shields.io/badge/python-3.13+-3776ab.svg)

Automated frame sampling, audio alignment, HDR tonemapping, and slow.pics uploads for deterministic encode comparisons.

## At a Glance

| Audience | Why it helps |
| --- | --- |
| Fansub/QC, boutique remaster teams, archivists | Deterministic screenshot sets with JSON metadata for automation |
| Automation engineers | Thin CLI shim that delegates to a reusable runner with programmatic hooks |
| HDR/SDR hobbyists | Built-in tonemap presets, overrides, and VSPreview-powered alignment workflows |

> [!TIP]
> New users can finish a complete comparison in three steps: install dependencies, seed the config, drop encodes under `comparison_videos/<name>/`, then run `uv run python -m frame_compare --root .`.

<details>
<summary>Table of Contents</summary>

- [Frame Compare](#frame-compare)
  - [At a Glance](#at-a-glance)
  - [Overview](#overview)
  - [Get Started](#get-started)
    - [Requirements](#requirements)
    - [Install](#install)
    - [First Comparison](#first-comparison)
    - [Verify](#verify)
  - [Workspace \& Usage Essentials](#workspace--usage-essentials)
  - [Guided Setup \& Presets](#guided-setup--presets)
  - [Dependency Doctor](#dependency-doctor)
  - [Programmatic Usage](#programmatic-usage)
  - [Advanced Guides \& Reference](#advanced-guides--reference)
    - [Configuration Highlights](#configuration-highlights)
    - [Tonemap Quick Recipes](#tonemap-quick-recipes)
    - [CLI Reference](#cli-reference)
    - [Examples](#examples)
      - [VSPreview manual alignment assistant](#vspreview-manual-alignment-assistant)
      - [Path diagnostics before heavy runs](#path-diagnostics-before-heavy-runs)
      - [FFmpeg-only captures](#ffmpeg-only-captures)
    - [Troubleshooting](#troubleshooting)
    - [FAQ](#faq)
    - [Performance](#performance)
    - [Security](#security)
    - [Privacy \& Telemetry](#privacy--telemetry)
    - [Versioning](#versioning)
    - [Context Management](#context-management)
    - [Contributing](#contributing)
    - [License](#license)
    - [Support](#support)
    - [Future Updates](#future-updates)

</details>

## Overview

Frame Compare samples darkest, brightest, motion-heavy, random, and user-pinned frames across multiple encodes of the same title. It aligns audio, renders deterministic PNGs through VapourSynth (or FFmpeg fallback), and ships finished sets to slow.pics with TMDB naming. Outputs include screenshot folders, cached metrics, HTML reports, and JSON tails for dashboards.

**Key features**

- Deterministic frame selection with luminance quantiles, motion scoring, and seeded randomness.
- Cached metrics (`generated.compframes`) for quick reruns across large batches.
- Audio alignment with correlation + dynamic time warping, optional VSPreview confirmation.
- HDR➜SDR tonemapping presets, BT.2390 knee controls, Dolby Vision overrides, and FFmpeg fallback.
- slow.pics auto uploads with retries, clipboard shortcuts, and JSON tail summaries.
- Optional HTML report mirroring slow.pics (slider/overlay/difference/blink modes, zoom/pan, filterable filmstrips).
- TMDB-driven metadata resolution powered by GuessIt + Anitopy labelling.
- Rich CLI layout with progress dashboards plus JSON tails for automation.

## Get Started

### Requirements

- [ ] Python 3.13+
- [ ] [uv](https://docs.astral.sh/uv/) (recommended) or `pip`
- [ ] [FFmpeg](https://ffmpeg.org/) + `ffprobe` on `PATH`
- [ ] VapourSynth ≥72 (optional but enables the primary renderer)
- [ ] Optional audio extras: `numpy`, `librosa`, `soundfile`

### Install

| Method | When to use | Commands |
| --- | --- | --- |
| `uv` (recommended) | Reproducible, isolated env | `uv sync`<br>`uv pip install vapoursynth` *(optional)* |
| `pip` virtualenv | Standard venv workflows | `python3.13 -m venv .venv`<br>`source .venv/bin/activate`<br>`pip install -U pip wheel`<br>`pip install -e .` |

Optional extras:

| Feature | Extras |
| --- | --- |
| VSPreview manual alignment | `uv pip install vspreview PySide6` 
| slow.pics clipboard shortcut | `uv pip install pyperclip` |

> [!NOTE]
> Follow the [official VapourSynth install guide](https://www.vapoursynth.com/doc/installation.html) per OS. Ensure the Python bindings are importable, e.g. by setting `VAPOURSYNTH_PYTHONPATH`.

### First Comparison

1. **Seed the workspace config.**
   ```bash
   uv run python -m frame_compare --write-config
   ```
2. **Create input clips under the workspace.**
   ```bash
   mkdir -p comparison_videos/quickstart
   ffmpeg -y -f lavfi -i color=c=black:s=640x360:d=2 \
     -vf "drawtext=text=SourceA:fontsize=48:x=20:y=20" \
     comparison_videos/quickstart/clip-a.mp4
   ffmpeg -y -f lavfi -i color=c=blue:s=640x360:d=2 \
     -vf "drawtext=text=SourceB:fontsize=48:x=20:y=20" \
     comparison_videos/quickstart/clip-b.mp4
   ```
3. **Run the pipeline.**
   ```bash
   uv run python -m frame_compare --root . --input comparison_videos/quickstart
   ```

Expected outputs: PNGs in `screens/`, cached metrics in `generated.compframes`, optional `generated.audio_offsets.toml`, and a slow.pics shortcut when uploads succeed.

> [!TIP]
> First interactive run with a missing config auto-launches the wizard. Disable with `--no-wizard` or `FRAME_COMPARE_NO_WIZARD=1` for automation.

### Verify

- Run `uv run python -m frame_compare --diagnose-paths` to confirm resolved root/media/screen directories and writability.
- Use `uv run python -m frame_compare doctor` to verify optional dependencies before long batches.

## Workspace & Usage Essentials

The workspace root controls config, media, caches, and outputs. Root discovery order:

1. `--root`
2. `$FRAME_COMPARE_ROOT`
3. Nearest ancestor containing `pyproject.toml`, `.git`, or `comparison_videos`
4. Current working directory

Each comparison lives under `comparison_videos/<set>/` (configurable via `[paths].input_dir`). Common workflows:

| Goal | Command |
| --- | --- |
| Seed config without running | `uv run python -m frame_compare --root /path --write-config` |
| Full pipeline (VS + tonemap) | `uv run python -m frame_compare --root /path` |
| Override input directory once | `uv run python -m frame_compare --root /path --input comparison_videos/my-set` |
| Force FFmpeg screenshots | `uv run python -m frame_compare --root /path --config config/config.toml --json-pretty --no-color` |
| Inspect resolved paths | `uv run python -m frame_compare --root /path --diagnose-paths` |
| Launch wizard manually | `uv run python -m frame_compare --root /path wizard` |
| Apply preset non-interactively | `uv run python -m frame_compare --root /path preset apply quick-compare` |
| Check dependencies | `uv run python -m frame_compare --root /path doctor` |

> [!WARNING]
> The default `[slowpics].delete_screen_dir_after_upload = true` removes screenshot directories after successful uploads. Keep `screenshots.directory_name` relative to the workspace root.

## Guided Setup & Presets

`frame-compare wizard` prompts for workspace, renderer, slow.pics settings, and alignment options. Non-interactive runs can pass `--preset <name>` to reuse curated profiles (`quick-compare`, `hdr-vs-sdr`, `batch-qc`). Presets can be listed with `frame-compare preset list` and applied via `frame-compare preset apply <name>`.

## Dependency Doctor

`frame-compare doctor` runs fast, read-only diagnostics for VapourSynth, FFmpeg, audio extras, VSPreview tooling, slow.pics networking, clipboard helpers, and config writability. It always exits `0`, supports `--json`, and is automatically invoked by the wizard.

## Programmatic Usage

The Click CLI delegates to the shared runner in `src/frame_compare/runner.py`, so automation can bypass Click entirely:

```python
from pathlib import Path
from rich.console import Console

from frame_compare.runner import RunRequest, run
from src.frame_compare.cli_runtime import CliOutputManager


def build_reporter(request: RunRequest, layout_path: Path, console: Console) -> CliOutputManager:
    return CliOutputManager(
        quiet=request.quiet,
        verbose=request.verbose,
        no_color=request.no_color,
        layout_path=layout_path,
        console=console,
    )


request = RunRequest(
    config_path="config/config.toml",
    input_dir="comparison_videos/demo",
    root_override=".",
    quiet=True,
    reporter_factory=build_reporter,
)

result = run(request)
print(result.files)
print(result.json_tail)
```

`RunResult` exposes rendered files, selected frame indices, resolved root, optional slow.pics URL, and HTML report path. Setting `quiet=True` swaps in a `NullCliOutputManager` so automation logs stay clean. The regression suite calls `runner.run` directly to keep CLI and programmatic behavior in sync.

Already own a configured reporter? Pass it via `RunRequest.reporter` to skip the default Rich wiring. This is handy when you need to mirror output into JSON/metrics without losing the familiar CLI layout:

```python
from pathlib import Path
from rich.console import Console

from frame_compare.runner import RunRequest, run
from src.frame_compare.cli_runtime import CliOutputManager


layout_path = Path(__file__).resolve().with_name("cli_layout.v1.json")
json_reporter = CliOutputManager(
    quiet=False,
    verbose=False,
    no_color=False,
    layout_path=layout_path,
    console=Console(record=True),
)

run(
    RunRequest(
        config_path="config/config.toml",
        reporter=json_reporter,
    )
)
```

Need to override wizard prompts programmatically? Continue patching the compatibility shims that `frame_compare` re-exports. Both `resolve_wizard_paths` and `_resolve_wizard_paths` forward to `src.frame_compare.wizard`, so legacy automation that previously pointed at `frame_compare._resolve_wizard_paths` keeps working without reaching into `src.frame_compare.core`.

## Advanced Guides & Reference

### Configuration Highlights

Frame Compare seeds `config/config.toml` from `src/data/config.toml.template`. Legacy `ROOT/config.toml` is still read but emits a migration warning.

| Area | Highlights | Notes |
| --- | --- | --- |
| `[paths]` | Workspace-relative input dir, screenshot folder | Guardrails block escaping the root |
| `[analysis]` | Frame quotas, randomness, cache filename | `generated.compframes` reused when hashes match |
| `[screenshots]` | Renderer choice, geometry policy, dithering | Set `use_ffmpeg=true` to bypass VapourSynth |
| `[color]` | Tonemap presets, BT.2390 knee, DPD presets, gamma lift | Override via `--tm-*` flags |
| `[audio_alignment]` | Correlation settings, VSPreview hooks, offsets file | `confirm_with_screenshots` toggles preview pause |
| `[slowpics]` | Auto upload, visibility, cleanup, webhook, timeout | Disabled by default |
| `[report]` | Offline HTML report toggle, output dir, default mode | Modes: slider, overlay, difference, blink |
| `[runtime]` | VapourSynth RAM guard, module search paths | Prevents runaway scripts |
| `[overrides]` | Per-source trims, FPS adjustments | Match filenames, stems, or GuessIt labels |

Environment variables: `FRAME_COMPARE_ROOT`, `FRAME_COMPARE_CONFIG`, `FRAME_COMPARE_TEMPLATE_PATH`, `FRAME_COMPARE_NO_WIZARD`, `VAPOURSYNTH_PYTHONPATH`.

TMDB metadata lookups now flow through a shared workflow (`core.resolve_tmdb_workflow`) for both Click and programmatic runs. Ambiguous matches respect `[tmdb].unattended` (no prompts when true, warnings logged instead), manual identifiers entered at the prompt propagate through slow.pics/JSON tails, and `_resolve_tmdb_blocking` retries transient HTTP failures using `httpx.HTTPTransport(retries=...)` before surfacing an error.

### Tonemap Quick Recipes

- **Reference SDR (BT.2390)** — `preset="reference"`, `tone_curve="bt.2390"`, `target_nits=100`, `dst_min_nits=0.18`, `knee_offset=0.50`, smoothing `45f`, percentile `99.995`, contrast `0.30`.
- **Highlight guard** — `preset="highlight_guard"`, higher `target_nits` (250–350) plus `knee_offset=0.35` to keep specular detail.
- **Filmic SDR view** — `preset="filmic"` with `contrast_recovery=0.20` for a softer shoulder.

Fine-grained overrides (`smoothing_period`, `scene_threshold_*`, `percentile`, `contrast_recovery`, `metadata`, `use_dovi`, `visualize_lut`, `show_clipping`) map directly to libplacebo knobs and are exposed via matching `--tm-*` flags.

> [!TIP]
> Seed another workspace with `uv run python -m frame_compare --root alt-root --write-config` and copy tuned sections across projects.

### CLI Reference

| Flag | Description |
| --- | --- |
| `--root PATH` | Override workspace root discovery |
| `--config PATH` | Use a specific config file (`FRAME_COMPARE_CONFIG` fallback) |
| `--input PATH` | Override `[paths].input_dir` once |
| `--audio-align-track label=index` | Force audio streams per clip (repeatable) |
| `--tm-preset NAME` | Override tonemap preset (`reference`, `filmic`, `contrast`, `bt2390_spec`, `spline`, `bright_lift`, `highlight_guard`) |
| `--tm-curve NAME` | Override `[color].tone_curve` |
| `--tm-target NITS` | Override `[color].target_nits` |
| `--tm-dst-min VALUE` | Override `[color].dst_min_nits` |
| `--tm-knee VALUE` | Override `[color].knee_offset` (0–1) |
| `--tm-dpd-preset NAME` | `off`, `fast`, `balanced`, `high_quality` |
| `--tm-dpd-black-cutoff VALUE` | Override `[color].dpd_black_cutoff` (0.0–0.05) |
| `--tm-gamma VALUE` / `--tm-gamma-disable` | Control post-tonemap gamma lift |
| `--tm-smoothing VALUE` | Override `[color].smoothing_period` |
| `--tm-scene-low/HIGH VALUE` | Override scene thresholds |
| `--tm-percentile VALUE` | Override `[color].percentile` (0–100) |
| `--tm-contrast VALUE` | Override `[color].contrast_recovery` |
| `--tm-metadata VALUE` | `auto`, `none`, `hdr10`, `hdr10+`, `luminance`, or `0-4` |
| `--tm-use-dovi / --tm-no-dovi` | Force Dolby Vision metadata usage |
| `--tm-visualize-lut`, `--tm-show-clipping` | Toggle debug overlays |
| `--write-config` | Ensure `config/config.toml` exists, then exit |
| `--diagnose-paths` | Print JSON diagnostics |
| `--quiet` / `--verbose` / `--no-color` / `--json-pretty` | Adjust console behavior |
| `wizard`, `preset`, `doctor` | Subcommands for guided setup, presets, dependency checks |

Exit codes: `0` success, `2` preflight error, `3` runtime failure, `>3` module-specific errors (`AudioAlignmentError`, `SlowpicsAPIError`, etc.).

### Examples

#### VSPreview manual alignment assistant
1. Enable VSPreview in config:
   ```toml
   [audio_alignment]
   enable = true
   use_vspreview = true
   confirm_with_screenshots = false
   ```
2. Install extras: `uv pip install vspreview PySide6`
3. Run interactively: `uv run python -m frame_compare --root /workspace`

Headless sessions skip the GUI but print generated script paths. Legacy Windows consoles fall back to ASCII arrows to avoid encoding issues.

#### Path diagnostics before heavy runs
```bash
uv run python -m frame_compare --root /workspace --diagnose-paths
```
Prints JSON containing workspace root, media directory, screenshot directory, and writability flags so you can catch `site-packages` roots early.

#### FFmpeg-only captures
```toml
[screenshots]
use_ffmpeg = true
ffmpeg_timeout_seconds = 0
```
```bash
uv run python -m frame_compare --root /workspace --quiet
```
Promotes subsampled SDR clips to YUV444P16 before cropping/padding to prevent mod-2 geometry failures.

### Troubleshooting

- **FFmpeg or VapourSynth not found** — ensure binaries are on `PATH`, set `VAPOURSYNTH_PYTHONPATH`, or enable `[screenshots].use_ffmpeg`.
- **Workspace root not writable** — choose another root via `--root`/`FRAME_COMPARE_ROOT`; running under `site-packages`/`dist-packages` is blocked.
- **HDR renders look dim** — switch `[color].preset = "filmic"` or disable `[color].enable_tonemap` for SDR sources.
- **slow.pics upload fails** — ensure network access, inspect JSON tail, and adjust `[slowpics].image_upload_timeout_seconds` for slow links.
- **Placeholder PNGs** — review console warnings, retry with FFmpeg, or install missing VapourSynth plugins.
- **Audio alignment dependency errors** — install `numpy`, `librosa`, `soundfile` (errors raise `AudioAlignmentError`).
- **VSPreview launch fails** — ensure PySide6 is installed and run from an interactive terminal.

### FAQ

- **Change screenshot output folder?** Set `[screenshots].directory_name` to a relative path; containment checks block escapes.
- **Opt into slow.pics uploads?** Set `[slowpics].auto_upload = true`.
- **Where are caches stored?** `[analysis].frame_data_filename` (default `generated.compframes`).
- **Supported OS?** macOS, Linux, Windows (64-bit Python 3.13+).
- **GUI available?** CLI-first; VSPreview supplies optional GUI alignment flows.

### Performance

- Metric caches reuse selection hashes, speeding reruns.
- Tonemapping executes once per clip; verification samples governed by `[color].verify_*`.
- Audio alignment extracts mono waveforms with tunable sample rates.
- Disable `[analysis].save_frames_data` to reduce IO when caches aren’t needed.
- `--quiet` minimizes console overhead for large batches while preserving JSON results.

### Security

- Workspace guardrails reject roots inside `site-packages` and ensure writability before execution.
- `_path_is_within_root` keeps cleanup/caches within the workspace.
- slow.pics uploads use HTTPS and redact webhook hostnames in logs.
- TMDB API keys stay in your config files; no other secrets are stored.

> [!WARNING]
> Misconfiguring `[screenshots].directory_name` to a shared folder may delete prior contents after uploads. Use dedicated directories per run.

### Privacy & Telemetry

Frame Compare sends no telemetry. Network calls only occur when `[slowpics].auto_upload = true` or `[tmdb].api_key` is set. Disable those features to run completely offline.

### Versioning

Current version: `0.0.1`. Until 1.0, APIs may change without notice. See [CHANGELOG.md](CHANGELOG.md) for release notes (recent entries cover VSPreview helper fixes, odd-geometry pivots, and tonemap refinements).

### Context Management

Advisors and Codex sessions keep Sequential Thinking logs lean to avoid flooding reviewers: only short stage/next-step summaries show up in chat, and only the latest ~10 thoughts stay visible while older ones move into the MCP history. See [CODEX.md](CODEX.md#sequential-thinking-context-management) for the full policy if you notice intentionally condensed responses.

**Metadata etiquette:** when Sequential Thinking metadata like `files_touched`, `tests_to_run`, or `dependencies` doesn’t apply, leave those lists empty instead of inventing placeholder entries. Likewise, keep `risk_level` and `confidence_score` at their defaults unless you have real signal to share. Fabricated values corrupt downstream analysis and reviewer trust.

Sequential Thinking always walks through Scoping → Research & Spike → Implementation → Testing → Review thoughts; keep `next_thought_needed=true` until the Review entry lands so the orchestrator knows the flow is still active.

### Contributing

1. Fork/clone the repo.
2. Install dev dependencies: `uv sync --group dev`.
3. Run checks:
   ```bash
   uv run pytest -q
   uv run pyright --warnings
   uv run ruff check
   ```
4. Add regression tests for behavioral changes. Document decisions in `docs/DECISIONS.md` and user-visible updates in `CHANGELOG.md`.

Type hints are mandatory—avoid introducing `Any` and guard `Optional[...]`s explicitly to satisfy Pyright.

### License

Distributed under the [MIT License](LICENSE). Frame Compare builds upon FFmpeg, VapourSynth, slow.pics, TMDB, GuessIt, Anitopy, and the wider Python ecosystem.

### Support

- Works on macOS, Linux, Windows (64-bit). Ensure FFmpeg is on `PATH` and VapourSynth is installed when using the primary renderer.
- Additional docs: [docs/audio_alignment_pipeline.md](docs/audio_alignment_pipeline.md), [docs/geometry_pipeline.md](docs/geometry_pipeline.md), [docs/hdr_tonemap_overview.md](docs/hdr_tonemap_overview.md), [docs/context_summary.md](docs/context_summary.md).
- File issues or feature requests via GitHub; report sensitive bugs privately.

### Future Updates

- Continue refining CLI status panels and VSPreview workflows so long-running batches communicate progress while matching legacy scripts.
- Polish the local viewer (persistent zoom/mode state, richer overlays, multi-encode summaries).
- Audit configuration surfaces for clarity, trimming duplicates while keeping power-user overrides accessible.
- Ensure there is a flag like --slowpics to pass via CLI that will enable auto upload feature for slowpics and take an argument for the collection suffix portion that can be passed alongside like "4k dv/hdr MA WEB-dl vs. 4k DV/HDR Bluray Remux"

Detailed technical tasks live on the [GitHub Issues board](https://github.com/TJZine/frame-compare/issues).
