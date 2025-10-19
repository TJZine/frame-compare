# Context Summary — Frame Compare

## Documentation Sources Reviewed
- Project guardrails and workflow expectations from `CODEX.md`.
- Repository usage overview from `README.md` and detailed configuration tables in `docs/README_REFERENCE.md`.
- Pipeline and component notes within `docs/` (including audio alignment, HDR tonemap, and VSPreview guidance).

## Architecture & Structure Highlights
- Python 3.13 project packaged via `pyproject.toml` with CLI entry point `frame_compare.py`.
- Source modules located in `src/`, covering analysis, audio alignment, configuration, screenshot generation, slow.pics uploads, TMDB metadata, and VapourSynth helpers.
- Tests under `tests/` mirror module coverage with pytest fixtures and integration exercises.
- Typed helpers and vendored stubs reside in `typings/`.

## Key Dependencies & Integrations
- Core libraries: Rich for CLI rendering, Click for argument parsing, HTTPX/requests for API calls, NumPy/librosa/soundfile for audio analysis.
- Optional VapourSynth dependency handled via extra `vapoursynth` group; FFmpeg integration for fallback renders.
- External services: slow.pics uploads via `src/slowpics.py`, TMDB lookups managed by `src/tmdb.py` with caching and parsing helpers.

## Configuration & Workflow
- Configuration is loaded from TOML using `src/config_loader.py` with dataclass models in `src/datatypes.py`; defaults seeded from `src/data/config.toml.template`.
- CLI layout rendering defined in `src/cli_layout.py` with formatting tests ensuring stable output.
- Guardrails emphasise diff-plan approvals, Pyright standard typing, and documentation of decisions in `docs/DECISIONS.md`.

## Testing & Quality
- Pytest suite spans CLI behaviour (`test_cli_layout_render.py`), analysis computations, audio alignment, screenshot generation, TMDB integrations, and config loading.
- Linting/formatting enforced via Ruff and Black settings in `pyproject.toml`; Pyright configured by `pyrightconfig.json`.

## Outstanding Notes
- MCP-based best practice refresh is pending; environment lacks direct MCP tooling, so external validation remains a follow-up action.
- Future tasks should respect standard flow: evidence sweep, doc check, plan, diffs, persistence, verification.
