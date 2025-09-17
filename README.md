# Frame Compare

Frame Compare is a CLI workflow for selecting comparison frames from multiple video sources, generating normalized screenshots, and optionally uploading the collection to [slow.pics](https://slow.pics).

## Features

- TOML-driven configuration for analysis, screenshot, and upload behaviour.
- GuessIt/Anitopy filename parsing with label-aware output.
- Quantile-based frame discovery with motion heuristics and deterministic random selection.
- Modulus-safe geometry planning with fpng or ffmpeg renderers.
- Optional slow.pics upload with webhook support.

## Requirements

- Python 3.11 or newer *(handled automatically by [uv](https://github.com/astral-sh/uv))*
- VapourSynth runtime and plugins if you plan to generate real screenshots.

## Quick Start (runtime use)

Install the locked runtime dependencies and run the CLI against a directory containing at least two video files:

```bash
uv sync
uv run python main.py --config config.toml --input .
```

Use the `[analysis.analyze_clip]` config field to choose which clip drives frame discovery, and enable `[slowpics].auto_upload` to publish the results to slow.pics automatically.

## For Contributors

Development tasks require the additional tooling declared in the `dev` dependency group:

```bash
uv lock              # regenerate the lockfile after dependency changes
uv sync --group dev  # install runtime + dev/test tooling
uv run python -m pytest -q
```

Useful helper commands:

```bash
uv run ruff check . --fix
uv run black .
```

## Contributing Guidelines

1. Keep the lock file (`uv.lock`) up to date via `uv lock` whenever dependencies change.
2. Run `uv run python -m pytest -q` before submitting a pull request.
3. Ensure new features include tests and documentation updates where appropriate.
