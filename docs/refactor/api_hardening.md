# API Hardening

Stabilise the public Python + CLI surface so we can evolve internal modules without breaking downstream automation. The curated list below mirrors `frame_compare.__all__` and the stub exported via `typings/frame_compare.pyi`.

## Curated Exports

| Name | Owning module | Notes |
| --- | --- | --- |
| `run_cli`, `main` | `frame_compare.py` | CLI entrypoints (Click group + runner shim). |
| `RunRequest`, `RunResult` | `src/frame_compare/runner.py` | Programmatic runner contract. |
| `CLIAppError`, `ScreenshotError` | `src/frame_compare/cli_runtime.py`, `src/frame_compare/render/errors.py` | User-facing exception boundaries for CLI + screenshot flows. |
| `resolve_tmdb_workflow`, `TMDBLookupResult`, `render_collection_name` | `src/frame_compare/tmdb_workflow.py` | Stable TMDB lookup helpers. |
| `prepare_preflight`, `resolve_workspace_root`, `PreflightResult`, `collect_path_diagnostics` | `src/frame_compare/preflight.py` | Workspace + diagnostics helpers. |
| `collect_doctor_checks`, `emit_doctor_results`, `DoctorCheck` | `src/frame_compare/doctor.py` | Doctor workflow helpers. |
| `vs_core` | `src/frame_compare/vs` | Canonical VapourSynth helper module alias (exposes `ClipInitError`, `ClipProcessError`, `VerificationResult`, etc.). |

## Deprecation Policy

- Curated names stay stable across patch releases. Removal or signature changes are announced one minor version ahead via the changelog and release notes.
- Deprecated aliases emit `DeprecationWarning` for one release cycle before removal.
- Internal modules (`src.frame_compare.*`) remain importable for contributors, but they are explicitly undocumented and excluded from stability guarantees.

## Exceptions Contract

- `CLIAppError` raises for user-facing CLI failures and subclasses `RuntimeError` (Click may wrap it for presentation).
- `ScreenshotError` remains the base class for screenshot/rendering issues; all screenshot helpers raise subclasses.
- `vs_core.ClipInitError` and `vs_core.ClipProcessError` cover VapourSynth initialisation/processing failures; runner-level code catches them and wraps the messages in `CLIAppError`.

## CLI Contract

`frame_compare.main` stays the primary Click entry. The `--help` output must always include these anchor options so tests can detect accidental churn:

- `--root`, `--config`, `--input`
- `--diagnose-paths`, `--write-config`
- `--html-report`, `--no-html-report`
- Representative tonemap flag (`--tm-preset`)

## Acceptance & CI Gates

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-sync python -m pytest -q tests/api tests/net`
- `uv run --no-sync npx pyright --warnings`
- `uv run --no-sync ruff check`
- `UV_CACHE_DIR=.uv_cache uv run --no-sync lint-imports --config importlinter.ini`

These checks gate future API edits and ensure the curated exports, exception contracts, and CLI flags stay locked.

- [x] Reviewed 2025-11-13 — API hardening exports/tests/docs verified (CI parity: pytest tests/api tests/net, pyright, ruff, import-linter).
