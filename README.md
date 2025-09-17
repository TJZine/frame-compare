# Frame Compare
Automated video frame selection, screenshots, and optional slow.pics upload.

## Badges
<!-- TODO: Add GitHub Actions CI badge once the public repository URL is known. -->

## TL;DR
- Discover comparison-worthy frames across multiple sources and gather consistent screenshots in one pass.
- `uv run python frame_compare.py --config config.toml --input .`
- Tune behaviour in `config.toml`; every option is validated against the dataclasses in `src/datatypes.py`.

## Features
- Quantile- and motion-driven frame selection algorithms with deterministic seeds for reproducible runs.
- Geometry planning, modulus-aware cropping, and screenshot writers with placeholder fallbacks when native deps are missing.
- Optional slow.pics upload workflow with webhook support and automatic shortcut creation.
- Centralised TOML configuration with strict validation and reasonable defaults.
- Continuous integration via GitHub Actions running `uv sync --group dev --frozen` and `pytest`.
- Documented VS Code task flow so you can wire common commands into your IDE quickly.

## Project structure
```
.
├─ frame_compare.py          — Click-based CLI orchestrating analysis, screenshots, and uploads.
├─ config.toml               — Sample configuration matching the dataclass defaults.
├─ comparison_videos/        — Example input directory referenced by the default config.
├─ legacy/compv4_improved.py — Legacy implementation kept for reference during migration.
├─ src/
│  ├─ datatypes.py           — Configuration dataclasses and defaults.
│  ├─ config_loader.py       — TOML loader with type coercion and validation.
│  ├─ utils.py               — Filename metadata parsing helpers (GuessIt/Anitopy).
│  ├─ analysis.py            — Frame scoring, quantiles, and selection heuristics.
│  ├─ screenshot.py          — Cropping, scaling, and screenshot rendering orchestration.
│  ├─ slowpics.py            — Slow.pics API client for automated uploads.
│  └─ vs_core.py             — VapourSynth clip initialisation and HDR→SDR tonemapping helpers.
└─ tests/                    — Pytest suite covering analysis, config, screenshot, slow.pics, and vs_core.
```

## Quickstart
Run the project with Python 3.11+ and [uv](https://github.com/astral-sh/uv). These commands install dependencies, execute tests, and launch the CLI:

```bash
uv lock
uv sync --group dev
uv run python -m pytest -q
uv run python frame_compare.py --config config.toml --input .
```

```powershell
uv lock
uv sync --group dev
uv run python -m pytest -q
uv run python frame_compare.py --config config.toml --input .
```

> ℹ️ VapourSynth, libplacebo, and ffmpeg deliver full-fidelity screenshots; without them the tool still runs, saving placeholder files through the built-in fallbacks.

## Usage
```
Usage: uv run python frame_compare.py [OPTIONS]

Options:
  --config PATH  Path to the TOML configuration file. Defaults to config.toml.
  --input PATH   Override [paths.input_dir] for this run.
  --help         Show this message and exit.
```

Examples:
- Scan the default sample folder: `uv run python frame_compare.py --config config.toml --input comparison_videos`
- Point to an absolute path on Windows: `uv run python frame_compare.py --config config.toml --input "D:/captures"`
- Enable auto-upload in your config, then run: `uv run python frame_compare.py --config profiles/slowpics.toml --input ./captures`

Output files land in `<input>/<screenshots.directory_name>/` (default `screens/`). Filenames are derived from parsed labels plus `_frameNNNNNN.png` (or an index when `add_frame_info = false`). The CLI prints a summary and, when uploads are enabled, the slow.pics URL.

## Configuration
Configuration lives in `config.toml` and is loaded through `src/config_loader.py`, which coerces booleans, checks ranges, and instantiates the dataclasses in `src/datatypes.py`. Defaults come from those dataclasses; the bundled `config.toml` provides a practical starting point. Key sections:

### [analysis]
| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `frame_count_dark` | int | 20 | Number of darkest frames to keep (quantile or fixed thresholds). |
| `frame_count_bright` | int | 10 | Number of brightest frames to keep. |
| `frame_count_motion` | int | 15 | Frames with highest motion scores after smoothing. |
| `user_frames` | list[int] | `[]` | Explicit frame numbers to force into the selection. |
| `random_frames` | int | 15 | Additional random frames seeded by `random_seed`. |
| `save_frames_data` | bool | true | Persist raw metric data alongside selections (future use). |
| `downscale_height` | int | 480 | Downscale height for metrics to speed up analysis. |
| `step` | int | 2 | Sampling stride; must stay ≥1. |
| `analyze_in_sdr` | bool | true | Tonemap HDR clips before analysis using `vs_core`. |
| `use_quantiles` | bool | true | Switch between quantile thresholds or fixed value bands. |
| `dark_quantile` | float | 0.20 | Quantile cutoff for dark frame selection. |
| `bright_quantile` | float | 0.80 | Quantile cutoff for bright frame selection. |
| `motion_use_absdiff` | bool | false | Use absolute differences instead of edge-emphasised diffs. |
| `motion_scenecut_quantile` | float | 0.0 | Optional cap to drop extreme motion/scene-cut frames. |
| `screen_separation_sec` | int | 6 | Minimum separation between chosen frames in seconds. |
| `motion_diff_radius` | int | 4 | Radius for motion smoothing window. |
| `analyze_clip` | str | `""` | Name/index/label hint to pick the driving clip. |
| `random_seed` | int | 20202020 | Seed controlling deterministic randomness. |
| `frame_data_filename` | str | `"generated.compframes"` | On-disk cache filename for selection metadata. |

### [screenshots]
| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `directory_name` | str | `"screens"` | Subdirectory inside the input root for output images. |
| `add_frame_info` | bool | true | Overlay frame numbers in the PNG footer bar. |
| `use_ffmpeg` | bool | false | Reserved toggle for ffmpeg-based writers (currently VapourSynth). |
| `compression_level` | int | 1 | PNG compression preset: 0 (fast) / 1 (balanced) / 2 (small). |
| `upscale` | bool | true | Allow scaling above source resolution when `single_res` > native. |
| `single_res` | int | 0 | Force output height (0 keeps native). |
| `mod_crop` | int | 2 | Crop so width/height stay multiples of this value. |
| `letterbox_pillarbox_aware` | bool | true | Bias cropping toward bars to preserve active area. |

### [slowpics]
| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `auto_upload` | bool | false | Upload screenshots automatically after rendering. |
| `collection_name` | str | `""` | Optional slow.pics collection title. |
| `is_hentai` | bool | false | Flag NSFW content for slow.pics filters. |
| `is_public` | bool | true | Make the comparison publicly visible. |
| `tmdb_id` | str | `""` | Attach a TMDB identifier when available. |
| `remove_after_days` | int | 0 | Schedule collection deletion after N days (0 keeps forever). |
| `webhook_url` | str | `""` | Notify an external service once the upload finishes. |
| `open_in_browser` | bool | true | Launch the slow.pics URL in a browser when ready. |
| `create_url_shortcut` | bool | true | Drop a `.url` shortcut inside the screenshot directory. |
| `delete_screen_dir_after_upload` | bool | true | Remove rendered screenshots once the upload succeeds. |

### [naming]
| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `always_full_filename` | bool | true | Use the original filename as the screenshot label. |
| `prefer_guessit` | bool | true | Prefer GuessIt over Anitopy when parsing metadata. |

### [paths]
| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `input_dir` | str | `"."` | Base directory for input videos (sample config sets this to `comparison_videos`). |

Additional helpers:
- `[runtime]` exposes `ram_limit_mb` (default 8000) for future guardrails.
- `[overrides]` supplies optional per-file `trim`, `trim_end`, and `change_fps` mappings validated by `config_loader`.

## Development
- Sync tooling: `uv lock` (after dependency edits) and `uv sync --group dev`.
- Lint: `uv run ruff check . --fix`
- Format: `uv run black .`
- Test: `uv run python -m pytest -q`

No `.vscode/tasks.json` is included yet; mirror the commands above if you create VS Code tasks for a one-click dev loop.

## CI
The `.github/workflows/ci.yml` workflow checks out the code, installs uv, caches the uv directory, runs `uv sync --group dev --frozen --python 3.11`, and executes `uv run python -m pytest -q` on Ubuntu runners for every push and pull request.

## Architecture overview
- `frame_compare.py` wires together config loading, clip discovery, frame selection, screenshot rendering, and optional uploading.
- `src/config_loader.py` parses TOML, coerces bool-like values, validates ranges, and produces an `AppConfig` instance.
- `src/datatypes.py` defines the configuration dataclasses that capture defaults and structure for every section.
- `src/utils.py` encapsulates filename parsing heuristics using GuessIt/Anitopy to produce consistent labels.
- `src/analysis.py` samples clips, gathers brightness/motion metrics (VapourSynth or fallback), and returns the frame list.
- `src/screenshot.py` plans crops/scales, renders frames via VapourSynth, and falls back to placeholder files when rendering fails.
- `src/slowpics.py` handles slow.pics session bootstrapping, file uploads, webhooks, and `.url` shortcut generation.
- `src/vs_core.py` initialises VapourSynth clips, applies trims/fps overrides, and tonemaps HDR sources to SDR for downstream modules.

## Troubleshooting
- `uv run` complaining about missing project metadata usually means you are outside the repository root—ensure `pyproject.toml` is visible to uv.
- On Windows PowerShell, prefer absolute paths or quote inputs (`"D:/captures"`) to avoid escaping issues; uv manages virtual environments automatically.
- Missing VapourSynth/libplacebo/ffmpeg will limit screenshots to placeholder files. Install the native dependencies to unlock full rendering.

## Contributing
Fork, branch, and submit pull requests with clear descriptions. Keep `uv.lock` in sync after dependency changes, run `uv run python -m pytest -q`, and ensure lint/format checks pass before opening a PR.

## License
No license file is present yet. **TODO:** add an explicit license (MIT recommended).
