# When a Task Is Completed

Verification
- Run the verification quartet:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`
  - `.venv/bin/ruff check`
  - `.venv/bin/pyright --warnings`
  - (Optional) `python -m importlinter --config importlinter.ini`

Documentation & Logs
- Append an entry to `docs/DECISIONS.md` with:
  - UTC date (`date -u +%Y-%m-%d`), summary of changes, commands and outcomes
  - Any follow‑ups or waivers/ignores added (e.g., import‑linter temporary ignores)
- Update trackers:
  - `docs/refactor/mod_refactor.md` — flip the phase/sub‑phase row, add a Session Checklist block (scope, files changed, commands run, risks, follow‑ups)
  - `docs/runner_refactor_checklist.md` if relevant to runner/CLI refactors
- README/CHANGELOG only when user‑visible surfaces change (new public API, deprecations/ removals)

Git Hygiene
- Use Conventional Commit subjects, e.g.:
  - `refactor: extract <module> from core with shims (phase X.Y)`
  - `docs: add runner API examples (phase X.Y)`
  - `test: move CLI tests to tests/cli (phase X.Y)`
- Keep changes focused; avoid bundling unrelated fixes.

Release/Packaging (when needed)
- Ensure `src/frame_compare/py.typed` is included (PEP 561).
- Confirm `MANIFEST.in` entries and console scripts are intact.
