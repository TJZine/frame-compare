# Suggested Commands (Dev Cheatsheet)

Environment
- Create venv (pip):
  - `python3.13 -m venv .venv && source .venv/bin/activate`
  - `pip install -U pip wheel && pip install -e .`
- Create env (uv):
  - `uv sync`
  - Optional: `uv pip install vapoursynth` (VS core), `uv pip install vspreview PySide6` (VSPreview)

Run CLI / Entrypoint
- `python -m frame_compare --help`
- `frame-compare --help`

Common CLI Flows
- Seed config: `uv run python -m frame_compare --write-config`
- Diagnose paths: `uv run python -m frame_compare --diagnose-paths`
- Wizard: `uv run python -m frame_compare wizard`
- Preset list/apply: `uv run python -m frame_compare preset list|apply <name>`
- Doctor: `uv run python -m frame_compare doctor [--json]`
- Full run: `uv run python -m frame_compare --root . --input comparison_videos/<set>`

Verification Quartet (run before/after changes)
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`
- `.venv/bin/ruff check`
- `.venv/bin/pyright --warnings`
- (Optional) `python -m importlinter --config importlinter.ini`

Dev Utilities (Darwin)
- Shell: `ls`, `find`, `sed -n 'start,endp'`, `grep -n`, `rg -n` (ripgrep), `pbcopy/pbpaste`
- Git: `git status -sb`, `git diff`, `git add -p`, `git restore -p`

Packaging / Scripts
- Console script installed: `frame-compare`
- Project scripts via uv: `uv run ...`
