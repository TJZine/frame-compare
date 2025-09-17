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

## Setup & Installation

```bash
uv lock
uv sync --group dev
```

## Running Tests

```bash
uv run python -m pytest -q
```

## Running the CLI

Run the tool against a directory containing at least two video files:

```bash
uv run python main.py --config config.toml --input .
```

Use the `[analysis.analyze_clip]` config field to select which clip drives frame discovery, and enable `[slowpics].auto_upload` to publish the results to slow.pics automatically.

## Additional Commands

- Sync dependencies again after modifying `pyproject.toml`:
  ```bash
  uv sync --group dev
  ```
- Fix formatting and linting:
  ```bash
  uv run ruff check . --fix
  uv run black .
  ```

## Contributing

1. Keep the lock file (`uv.lock`) up to date via `uv lock` after dependency changes.
2. Run `uv run python -m pytest -q` before submitting a pull request.
3. Ensure new features include tests and documentation updates where appropriate.
