---
RUN_ID: 2025-12-27__p0-1__repo-foundation
VERSION: v1
TARGET: Phase 0 → Items 0.1-0.3 (Repository Setup, Project Structure, Development Tooling)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v1.md
---

# Implementation Plan: Repository Foundation (Phase 0.1-0.3)

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

### 2. `src/frame_compare/__init__.py` [NEW]

**Purpose:** Package root with version export.

**Content (exact):**

```python
"""Frame Compare — Video frame comparison tool."""

__version__ = "0.1.0"
__all__ = ["__version__"]
```

---

### 3. `src/frame_compare/py.typed` [NEW]

**Purpose:** PEP 561 marker indicating the package ships type information.

**Content:** Empty file (0 bytes)

---

### 4. `src/frame_compare/cli_entry.py` [NEW]

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

### 5. Directory Structure [NEW]

Create the following empty directories (with `.gitkeep` files to ensure they're tracked):

| Directory | Purpose |
|-----------|---------|
| `src/frame_compare/analysis/` | Frame analysis module |
| `src/frame_compare/vs/` | VapourSynth module |
| `src/frame_compare/render/` | Screenshot rendering module |
| `src/frame_compare/services/` | External services (slow.pics, TMDB) |
| `src/frame_compare/config/` | Configuration loading |
| `tests/` | Test suite root |
| `tests/fixtures/` | Test fixture files |
| `config/` | User configuration directory |

**`.gitkeep` files:** Create a zero-byte `.gitkeep` in each empty directory listed above.

---

### 6. `tests/conftest.py` [NEW]

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

### 7. `tests/__init__.py` [NEW]

**Purpose:** Make tests a package (required for some pytest configurations).

**Content:** Empty file (0 bytes)

---

### 8. `.gitignore` [MODIFY]

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

- [ ] **AC-1:** GIVEN `pyproject.toml` exists WHEN `uv sync --group dev` is run THEN dependencies install successfully and `.venv/` is created
- [ ] **AC-2:** GIVEN `src/frame_compare/__init__.py` exists WHEN `from frame_compare import __version__` is executed THEN it returns `"0.1.0"`
- [ ] **AC-3:** GIVEN `py.typed` marker exists WHEN Pyright analyzes the package THEN it recognizes the package as typed
- [ ] **AC-4:** GIVEN Pyright is configured in strict mode WHEN `.venv/bin/pyright --warnings` is run THEN 0 errors are reported
- [ ] **AC-5:** GIVEN Ruff is configured WHEN `.venv/bin/ruff check .` is run THEN 0 errors are reported
- [ ] **AC-6:** GIVEN pytest is configured WHEN `.venv/bin/pytest` is run THEN it executes with 0 errors (empty suite OK)
- [ ] **AC-7:** GIVEN CLI entry point exists WHEN `uv run frame-compare version` is run THEN it prints `frame-compare 0.1.0`

---

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# Step 1: Install dependencies
uv sync --group dev

# Step 2: Type check
.venv/bin/pyright --warnings

# Step 3: Lint
.venv/bin/ruff check .

# Step 4: Test (empty suite OK)
.venv/bin/pytest

# Step 5: CLI entry point
uv run frame-compare version
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

---

## Notes for Coding Agent

1. **Use exact content:** All file contents in this plan are exact — copy them verbatim.

2. **Directory creation order:** Create directories before files. Use `mkdir -p` equivalent or create parent directories first.

3. **Empty files:** For `py.typed` and `tests/__init__.py`, create zero-byte files. For `.gitkeep` files, create zero-byte files in each empty directory.

4. **`.gitignore` handling:** Check if each section already exists before appending. Do not duplicate entries.

5. **Python version:** This project requires Python 3.13+. Ensure `uv` uses Python 3.13.

6. **No additional files:** Do not create any files not listed in this plan. Specifically:
   - Do NOT create `__init__.py` in submodule directories yet (analysis, vs, render, services, config)
   - Do NOT create any placeholder modules beyond `cli_entry.py`

7. **Author email:** Replace `tristan@example.com` with the actual email if known, otherwise leave as-is.

8. **Verification order:** Run verification commands in the exact order listed. `uv sync` must succeed before other commands can run.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-27__p0-1__repo-foundation

## Plan to Review

Read file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-27__p0-1__repo-foundation/plan-review-v1.md
