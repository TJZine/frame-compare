---
RUN_ID: 2025-12-27__p0-1__repo-foundation
VERSION: v3
TARGET: Phase 0 → Items 0.1-0.3 (Repository Setup, Project Structure, Development Tooling)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v2.md
  - .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v3.md
---

# Implementation Plan: Repository Foundation (Phase 0.1-0.3)

> **Revision:** v3 — Addresses FAIL items from plan-review-v2.md (lockfile handling, deterministic verification flow)

## Context

**Phase:** 0 — Foundation
**Module:** N/A (project scaffolding)
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md` (Phase 0 section)
**Dependencies:** None — this is the first implementation phase

## Scope

This plan covers:

- [x] 0.1 Repository Setup — Create `pyproject.toml` with build system
- [x] 0.2 Project Structure — Create directory structure with marker files
- [x] 0.3 Development Tooling — Configure dependencies, Pyright, Ruff

This plan does NOT cover:

- 0.4 CI/CD Pipeline (separate run: `p0-4__ci-pipeline`)
- 0.5 Container Setup (separate run: `p0-5__docker-setup`)
- Phase 0 Quality Gate (depends on CI)

## Contract Impact

**Contracts touched:** NO

---

## Rollback / Stop Conditions

> [!CAUTION]
> If any verification command fails, **do not patch around it**. Return to Planning Agent for a plan revision.

**Stop conditions:**

1. `uv sync --group dev` fails → Check Python version (must be 3.13+) and pyproject.toml syntax
2. `uv sync --group dev --frozen` fails → Lockfile was modified unexpectedly; check for drift
3. `pyright --warnings` reports errors → Return to Planning to fix type issues
4. `ruff check .` reports errors → Return to Planning to fix lint issues
5. `pytest -q` fails → Return to Planning to fix test issues
6. Run-artifact validators fail → Fix artifact structure before proceeding
7. `git status --porcelain` shows unexpected changes after `--frozen` sync → Lockfile unstable

**Prerequisite checks (before starting):**

- `uv --version` must succeed (uv must be installed)
- `python --version` must show 3.13+

If prerequisites fail, **STOP** and escalate to orchestrator.

---

## Files to Create/Modify

### 1. `pyproject.toml` [NEW]

**Purpose:** Project metadata, build system, dependencies, and tool configuration.

**Content (exact):**

```toml
[project]
name = "frame-compare"
version = "0.1.0"
description = "Video frame comparison tool with tonemapping and slow.pics integration"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.13"
authors = [
    { name = "Tristan", email = "tristan@example.com" }
]
keywords = ["video", "comparison", "vapoursynth", "tonemapping", "hdr"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
    "Topic :: Multimedia :: Video",
    "Typing :: Typed",
]

dependencies = [
    "typer>=0.15.0",
    "rich>=13.9.0",
    "numpy>=2.2.0",
    "httpx>=0.28.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "structlog>=24.4.0",
    "anyio>=4.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-mock>=3.14.0",
    "pytest-cov>=6.0.0",
    "pyright>=1.1.390",
    "ruff>=0.8.0",
    "respx>=0.22.0",
]

[project.scripts]
frame-compare = "frame_compare.cli_entry:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/frame_compare"]

# ─── Pyright ───────────────────────────────────────────────────────────────────
[tool.pyright]
pythonVersion = "3.13"
pythonPlatform = "All"
typeCheckingMode = "strict"
include = ["src"]
exclude = ["**/__pycache__", ".venv", "build", "dist"]
reportMissingImports = true
reportMissingTypeStubs = false
reportUnusedImport = true
reportUnusedVariable = true
reportPrivateUsage = true

# ─── Ruff ──────────────────────────────────────────────────────────────────────
[tool.ruff]
target-version = "py313"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B", "SIM", "C4"]
ignore = ["E501"]  # Line length handled by formatter

[tool.ruff.lint.isort]
known-first-party = ["frame_compare"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false

# ─── Pytest ────────────────────────────────────────────────────────────────────
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["-ra", "-q", "--strict-markers", "--strict-config"]
markers = [
    "unit: Fast isolated tests",
    "integration: Module interaction tests",
    "e2e: End-to-end CLI tests",
    "vs_required: Requires VapourSynth runtime",
    "slow: Long-running tests",
    "network: Requires network access",
    "tier_a: Contract/security tests (no VS, no network)",
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:vapoursynth",
]
anyio_mode = "auto"

# ─── Coverage ──────────────────────────────────────────────────────────────────
[tool.coverage.run]
source = ["src/frame_compare"]
branch = true
omit = ["*/__main__.py", "*/types.py"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@overload",
]
fail_under = 80
show_missing = true
```

---

### 2. `uv.lock` [NEW | GENERATED]

**Purpose:** Lockfile generated by `uv sync` for reproducible installs.

**Content:** Generated by `uv sync --group dev`. Do not edit by hand. Commit the generated file.

**Generation:** This file is created automatically in Verification Step 1. The Coding Agent does not write this file manually.

---

### 3. `src/frame_compare/__init__.py` [NEW]

**Purpose:** Package root with version export.

**Content (exact):**

```python
"""Frame Compare — Video frame comparison tool."""

__version__ = "0.1.0"
__all__ = ["__version__"]
```

---

### 4. `src/frame_compare/py.typed` [NEW]

**Purpose:** PEP 561 marker indicating the package ships type information.

**Content:** Empty file (0 bytes)

---

### 5. `src/frame_compare/cli_entry.py` [NEW]

**Purpose:** CLI entry point stub for Typer app. This is a placeholder to allow the project.scripts entry to work.

**Content (exact):**

```python
"""CLI entry point for frame-compare."""

import typer

app = typer.Typer(
    name="frame-compare",
    help="Video frame comparison tool with tonemapping and slow.pics integration.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print version and exit."""
    from frame_compare import __version__

    typer.echo(f"frame-compare {__version__}")


if __name__ == "__main__":
    app()
```

---

### 6. Directory Structure [NEW]

Create the following empty directories (with `.gitkeep` files to ensure they're tracked):

| Directory | Purpose |
|-----------|---------|
| `src/frame_compare/analysis/` | Frame analysis module |
| `src/frame_compare/vs/` | VapourSynth module |
| `src/frame_compare/render/` | Screenshot rendering module |
| `src/frame_compare/services/` | External services (slow.pics, TMDB) |
| `src/frame_compare/config/` | Configuration loading |
| `tests/` | Test suite root |
| `tests/e2e/` | End-to-end CLI tests |
| `tests/fixtures/` | Test fixture files |
| `config/` | User configuration directory |

**`.gitkeep` files:** Create a zero-byte `.gitkeep` in each empty directory listed above (except `tests/` and `tests/e2e/` which will have Python files).

---

### 7. `tests/conftest.py` [NEW]

**Purpose:** Shared pytest fixtures and configuration.

**Content (exact):**

```python
"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_video_path() -> Path:
    """Path to test video file (placeholder)."""
    return Path(__file__).parent / "fixtures" / "sample.mkv"


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """Temporary workspace with standard structure."""
    (tmp_path / "comparison_videos").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "generated").mkdir()
    yield tmp_path
```

---

### 8. `tests/__init__.py` [NEW]

**Purpose:** Make tests a package (required for some pytest configurations).

**Content:** Empty file (0 bytes)

---

### 9. `tests/e2e/__init__.py` [NEW]

**Purpose:** Make e2e tests a subpackage.

**Content:** Empty file (0 bytes)

---

### 10. `tests/e2e/test_cli_version.py` [NEW]

**Purpose:** Smoke test for the CLI `version` command.

**Content (exact):**

```python
"""E2E tests for CLI version command."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from frame_compare.cli_entry import app


@pytest.mark.e2e
def test_cli_version_command_exits_zero() -> None:
    """GIVEN the CLI app WHEN 'version' is invoked THEN exit code is 0."""
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0


@pytest.mark.e2e
def test_cli_version_command_outputs_version_string() -> None:
    """GIVEN the CLI app WHEN 'version' is invoked THEN output is 'frame-compare 0.1.0'."""
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    # Typer's echo adds a newline; strip for comparison
    assert result.output.strip() == "frame-compare 0.1.0"
```

---

### 11. `CHANGELOG.md` [MODIFY]

**Purpose:** Document changes for this phase.

**Content to prepend (after any existing header):**

```markdown
## [Unreleased]

### Added

- **Phase 0 Foundation:** Project scaffolding with `pyproject.toml`, `src/frame_compare/` structure, and development tooling (Pyright strict, Ruff, pytest).
- CLI entry point with `version` command.
- PEP 561 `py.typed` marker for typed package support.
```

> **Note:** If `CHANGELOG.md` already has an `[Unreleased]` section, merge the above entries into it. If not, add the section at the top after any header.

---

### 12. `docs/DECISIONS.md` [NEW]

**Purpose:** Document key architectural and tooling decisions for this run.

**Content Template:**

> [!IMPORTANT]
> Before writing this file, run `date -u +%Y-%m-%d` and use that value to replace `<UTC_DATE>` in the heading below.

```markdown
# Decision Log

> **Purpose:** Record key architectural and tooling decisions.
> **Format:** Each entry is dated (UTC) with context, decision, and rationale.

---

## <UTC_DATE> — Phase 0 Foundation Decisions

### Python Version: 3.13+

**Context:** The project requires modern Python features and performance improvements.

**Decision:** Require Python 3.13 or higher (`requires-python = ">=3.13"`).

**Rationale:**
- Access to latest `tomllib` standard library for TOML parsing
- Improved error messages and performance
- Long-term support alignment

---

### Type Checking: Pyright Strict Mode

**Context:** Strong typing improves maintainability and catches bugs early.

**Decision:** Use Pyright in `strict` mode for all source code.

**Rationale:**
- Stricter than mypy's default
- Better inference and error messages
- Enforces complete type annotations

---

### Linting: Ruff with Extended Rules

**Context:** Code quality and consistency are important for multi-agent development.

**Decision:** Use Ruff with rules: `E`, `F`, `I`, `W`, `UP`, `B`, `SIM`, `C4`.

**Rationale:**
- Fast (Rust-based)
- Covers pycodestyle (E), pyflakes (F), isort (I), warnings (W), pyupgrade (UP), bugbear (B), simplify (SIM), and comprehensions (C4)
- Single tool for linting and formatting

---

### Build System: Hatchling

**Context:** Need a PEP 517-compliant build backend.

**Decision:** Use Hatchling as the build backend.

**Rationale:**
- Modern, fast, and well-maintained
- Native support for src-layout
- Good integration with uv

---

### Dependency Baselines

**Context:** Pin minimum versions for reproducibility and feature availability.

**Decision:** Use the following minimum versions:

| Package | Minimum | Reason |
|---------|---------|--------|
| typer | 0.15.0 | Rich integration, modern API |
| pydantic | 2.10.0 | Settings integration, modern validation |
| httpx | 0.28.0 | Async support, modern API |
| numpy | 2.2.0 | Python 3.13 compatibility |
| structlog | 24.4.0 | Modern structured logging |

**Rationale:** These versions are latest stable releases with Python 3.13 support.

---

### Lockfile: Committed

**Context:** Reproducible builds require a stable lockfile.

**Decision:** Commit `uv.lock` to version control.

**Rationale:**
- Ensures CI and all developers use identical dependency versions
- Generated by `uv sync`; never hand-edited
```

---

### 13. `.gitignore` [MODIFY]

**Purpose:** Add Python-specific ignores if not already present.

**Content to append (if missing):**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.venv/
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.nox/

# Type checking
.pyright/
.mypy_cache/

# UV
.uv_cache/

# OS
.DS_Store
Thumbs.db
```

---

## Acceptance Criteria

- [ ] **AC-1:** GIVEN `pyproject.toml` exists WHEN `uv sync --group dev` is run THEN dependencies install successfully, `.venv/` is created, and `uv.lock` is generated (exit 0)
- [ ] **AC-2:** GIVEN `uv.lock` exists WHEN `uv sync --group dev --frozen` is run THEN exit code is 0 and no changes to `uv.lock`
- [ ] **AC-3:** GIVEN `src/frame_compare/__init__.py` exists WHEN `from frame_compare import __version__` is executed THEN it returns `"0.1.0"`
- [ ] **AC-4:** GIVEN `py.typed` marker exists WHEN Pyright analyzes the package THEN it recognizes the package as typed
- [ ] **AC-5:** GIVEN Pyright is configured in strict mode WHEN `.venv/bin/pyright --warnings` is run THEN exit code is 0 with 0 errors
- [ ] **AC-6:** GIVEN Ruff is configured WHEN `.venv/bin/ruff check .` is run THEN exit code is 0 with 0 errors
- [ ] **AC-7:** GIVEN pytest is configured WHEN `.venv/bin/pytest -q` is run THEN exit code is 0 and both `test_cli_version_*` tests pass
- [ ] **AC-8:** GIVEN CLI entry point exists WHEN `UV_CACHE_DIR=./.uv_cache uv run --no-sync frame-compare version` is run THEN exit code is 0 and stdout is exactly `frame-compare 0.1.0\n`
- [ ] **AC-9:** GIVEN run artifacts exist WHEN run-artifact validators are executed THEN both exit 0

---

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

**Single deterministic flow (execute in order):**

```bash
# ─── Step 0: Prerequisites ───────────────────────────────────────────────────
uv --version
# Pass criteria: exit 0

python --version
# Pass criteria: exit 0, output shows "Python 3.13.x"

# ─── Step 1: Generate lockfile ───────────────────────────────────────────────
uv sync --group dev
# Pass criteria: exit 0, creates .venv/ and uv.lock

# ─── Step 2: Verify lockfile stability ───────────────────────────────────────
uv sync --group dev --frozen
# Pass criteria: exit 0 (lockfile unchanged)

git status --porcelain uv.lock
# Pass criteria: outputs "?? uv.lock" (new file) or "A  uv.lock" if staged, but NOT "M  uv.lock"

# ─── Step 3: Type check ──────────────────────────────────────────────────────
.venv/bin/pyright --warnings
# Pass criteria: exit 0, "0 errors"

# ─── Step 4: Lint ────────────────────────────────────────────────────────────
.venv/bin/ruff check .
# Pass criteria: exit 0, no errors

# ─── Step 5: Test ────────────────────────────────────────────────────────────
.venv/bin/pytest -q
# Pass criteria: exit 0, "2 passed"

# ─── Step 6: CLI entry point ─────────────────────────────────────────────────
UV_CACHE_DIR=./.uv_cache uv run --no-sync frame-compare version
# Pass criteria: exit 0, stdout exactly "frame-compare 0.1.0"

# ─── Step 7: Run-artifact hygiene validators ─────────────────────────────────
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists 2025-12-27__p0-1__repo-foundation
# Pass criteria: exit 0

UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-27__p0-1__repo-foundation
# Pass criteria: exit 0
```

**Overall pass criteria:** All commands exit 0 with outputs matching criteria above.

---

## Notes for Coding Agent

1. **Use exact content:** All file contents in this plan are exact — copy them verbatim (except for `docs/DECISIONS.md` which requires dynamic date substitution).

2. **Directory creation order:** Create directories before files. Use `mkdir -p` equivalent or create parent directories first.

3. **Empty files:** For `py.typed`, `tests/__init__.py`, and `tests/e2e/__init__.py`, create zero-byte files. For `.gitkeep` files, create zero-byte files in each empty directory that has no other files.

4. **`.gitignore` handling:** Check if each section already exists before appending. Do not duplicate entries.

5. **`CHANGELOG.md` handling:** If an `[Unreleased]` section exists, merge the new entries. If the file doesn't exist, create it with the content provided. If it exists without `[Unreleased]`, add the section after any existing header.

6. **`docs/DECISIONS.md` date:** Run `date -u +%Y-%m-%d` and substitute the output for `<UTC_DATE>` in the heading.

7. **Python version:** This project requires Python 3.13+. Ensure `uv` uses Python 3.13.

8. **Allowed generated files:** The only generated artifact allowed beyond listed files is `uv.lock`. This file is created by `uv sync --group dev` and must be committed.

9. **No other additional files:** Do not create any files not listed in this plan. Specifically:
   - Do NOT create `__init__.py` in submodule directories yet (analysis, vs, render, services, config)
   - Do NOT create any placeholder modules beyond `cli_entry.py`

10. **Author email:** Replace `tristan@example.com` with the actual email if known, otherwise leave as-is.

11. **Verification order:** Run verification commands in the exact order listed. Step 1 must succeed before Step 2, and so on. No conditionals, no fallbacks.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-27__p0-1__repo-foundation

## Plan to Review

Read file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v3.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-review-v3.md
