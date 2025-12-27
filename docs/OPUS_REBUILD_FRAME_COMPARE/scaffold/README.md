# Code Scaffold Package

> **Purpose:** Ready-to-use starter files for Phase 0  
> **Usage:** Copy these files to your project root to bootstrap Frame Compare 2.0

---

## Contents

| File | Description |
|------|-------------|
| `pyproject.toml` | Complete project configuration |
| `src/frame_compare/__init__.py` | Package init with version |
| `src/frame_compare/cli_entry.py` | Typer CLI stub (keeps packaging/CI happy) |
| `src/frame_compare/runner.py` | Runner stub (placeholder) |
| `src/frame_compare/{analysis,config,orchestration,render,services,vs}/__init__.py` | Package stubs for import contracts |
| `src/frame_compare/errors.py` | Base error hierarchy |
| `src/frame_compare/utils/result.py` | Result type pattern |
| `tests/conftest.py` | Pytest configuration |
| `.github/workflows/ci.yml` | CI pipeline |

---

## Quick Start

> [!IMPORTANT]
> This scaffold is a **reference subproject** within the Frame Compare monorepo.
> Tier-A contract tests require access to `contracts/` and `scripts/` via repo-relative paths.
> For standalone projects, see the published `frame-compare` package on PyPI.

**Within the monorepo:**

```bash
# Navigate to scaffold
cd docs/OPUS_REBUILD_FRAME_COMPARE/scaffold

# Create venv and install
uv venv && uv sync

# Run Tier-A tests (requires monorepo context)
.venv/bin/pytest -q -m tier_a

# Type check and lint
.venv/bin/pyright && .venv/bin/ruff check .
```

**For new standalone projects:**

```bash
# Use the published package (when available)
pip install frame-compare

# Or start from template without contract tests
# (contract tests are for verifying doc/code sync in the monorepo)
```

---

## Next Steps After Scaffold

After setting up the scaffold:

1. ✅ Verify `uv sync` completes
2. ✅ Verify `.venv/bin/pyright --warnings` shows 0 errors
3. ✅ Verify `.venv/bin/ruff check .` shows 0 errors
4. ✅ Verify `.venv/bin/pytest -q` runs
5. ➡️ Proceed to implement `config/` module
