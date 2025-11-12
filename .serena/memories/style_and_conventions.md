# Style & Conventions

General
- Fully typed code (PEP 484); PEP 561 marker `py.typed` included in `src/frame_compare/`.
- Pyright: `standard` globally; `strict` for library modules under `src/frame_compare/**`.
- Prefer `Mapping[...]` for read‑only dict parameters; `Dict[...]` for mutated locals.
- Guard all `Optional[...]` before attribute access/calls; favor early returns over nested branches.
- Use `TypedDict`/`Protocol`/`@dataclass` to model shapes; avoid `Any` leakage.
- Public API of modules controlled via explicit `__all__` lists.
- Private helpers prefixed with `_` and excluded from `__all__`.

Formatting & Linting
- Ruff is primary linter (E/F/I/W; E501 ignored). isort integrated via Ruff (first‑party configured: `frame_compare`, `src`).
- Black formatting (target: py313, line length 100). Ruff line length 120 (lint only).

CLI & Logging
- Click for CLI options and prompts; Rich for console output and styling.
- Errors exposed via `CLIAppError` (rich_message for user display) from the curated surface.

Imports & Layering
- Preferred surfaces: `from frame_compare import runner, RunRequest, RunResult, doctor, vspreview, presets, config_writer, preflight, selection, runtime_utils`.
- Avoid `src.frame_compare.*` in external code; keep it internal.
- Import-linter enforces layering: CLI → runner → modules; no module→CLI; core as compatibility only.

Testing
- Pytest with addopts disabling an external VS plugin (`-p no:vsengine`).
- Shared fixtures and helpers live in `tests/helpers/runner_env.py` and `tests/conftest.py`.

Error Boundaries
- Core library modules raise typed exceptions (e.g., `CLIAppError`, `TMDBResolutionError`) with stable messages; CLI translates to rich output.
