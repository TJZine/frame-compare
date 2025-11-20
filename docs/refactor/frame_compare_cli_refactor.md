# Frame Compare CLI Refactor (completed)

> Snapshot of the CLI separation work (Click wiring + helpers) now that the refactor is done. Keep this as the canonical reference; new CLI changes should log decisions in docs/DECISIONS.md.

## Final shape

- `frame_compare.py` is a thin shim that exports the curated public surface and delegates to `src/frame_compare/cli_entry.main`.
- `src/frame_compare/cli_entry.py` owns all Click wiring and flag validation, building `RunRequest` objects and enforcing mutually exclusive toggles (e.g., tonemap flags, service-mode vs legacy runner).
- `src/frame_compare/cli_utils.py` hosts CLI-only helpers such as `_cli_override_value` and `_cli_flag_value`.
- Compatibility exports live in `src/frame_compare/compat.py` so tests and legacy imports continue to resolve without bloating the shim.

## Invariants locked

- CLI behavior and help text remain stable; Click defaults are guarded so env/default_map values cannot override tonemap or gamma flags unless explicitly passed.
- Public API is unchanged aside from the shim delegation; documented symbols stay reachable from `frame_compare`.
- Tooling gates stay green: `.venv/bin/pyright --warnings`, `.venv/bin/ruff check`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q` are the standard commands recorded in docs/DECISIONS.md for each phase.

## Evidence and related docs

- Decisions: docs/DECISIONS.md entries on 2025-11-19 for CLI wiring cleanup and compatibility exports; earlier 2025-11-18 entries cover tonemap flag guards and default-map handling.
- Tests: CLI suites under `tests/runner/test_cli_entry.py`, Dolby Vision flags coverage, and compatibility fixture helpers in `tests/helpers/runner_env.py`.
- Docs: README and docs/README_REFERENCE.md describe current flags and JSON tail outputs; runner service split status sits in docs/refactor/runner_service_split.md.

## Open items

- None pending in this track; future CLI work should be logged as new decisions and, if substantial, a new refactor doc.
