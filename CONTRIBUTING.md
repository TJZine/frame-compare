# Contributing to Frame Compare

Thank you for your interest in contributing! This guide will help you get started.

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Workflow](#pull-request-workflow)
- [Code Style](#code-style)
- [Testing Requirements](#testing-requirements)
- [Releases](#releases)

---

## Prerequisites

Before contributing, ensure you have:

| Tool | Version | Purpose |
| ---- | ------- | ------- |
| Python | 3.13+ | Runtime |
| uv | Latest | Package management (recommended) |
| Git | Any recent | Version control |
| Docker | Latest | Integration testing (optional) |

---

## Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/TJZine/frame-compare.git
cd frame-compare
```

### 2. Install dependencies

**With uv (recommended):**

```bash
uv sync --group dev --frozen
```

**With pip:**

```bash
python3 -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
pip install -e .
pip install pytest pytest-cov ruff pyright
```

### 3. Verify your setup

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
```

---

## Making Changes

### 1. Create a feature branch

```bash
git checkout -b feat/your-feature-name
```

### 2. Make your changes

- Follow the [Code Style](#code-style) guidelines
- Add tests for new functionality
- Update documentation as needed

### 3. Run local checks

```bash
# Type checking
.venv/bin/pyright --warnings

# Linting
.venv/bin/ruff check .

# Auto-format
.venv/bin/ruff format .

# Tests
.venv/bin/pytest -q

# Import contracts
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

---

## Pull Request Workflow

### 1. Open a PR to `main`

### 2. Use Conventional Commit format for the PR title

This becomes the squash commit message. Use one of:

| Type | Description |
| ---- | ----------- |
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `refactor:` | Code change that neither fixes a bug nor adds a feature |
| `perf:` | Performance improvement |
| `test:` | Adding or updating tests |
| `build:` | Changes to build system or dependencies |
| `ci:` | CI/CD changes |
| `chore:` | Other changes that don't modify src or test files |
| `revert:` | Reverts a previous commit |

**Scopes are allowed but optional:**

```text
feat(cli): add --json output flag
fix(render): correct overlay positioning
docs: update installation guide
```

### 3. Ensure CI passes

All checks must pass before merge:

- ✅ Ruff linting
- ✅ Pyright type checking
- ✅ Pytest test suite
- ✅ Import contracts

---

## Code Style

### Python

- **Type hints**: Required on all function parameters and return types
- **Docstrings**: Required for public functions
- **Line length**: 100 characters max

### Formatting

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for issues
.venv/bin/ruff check .

# Auto-fix safe issues
.venv/bin/ruff check --fix .

# Format code
.venv/bin/ruff format .
```

### Type Checking

We use [Pyright](https://microsoft.github.io/pyright/) in strict mode:

```bash
.venv/bin/pyright --warnings
```

> [!IMPORTANT]
> All new code must pass Pyright strict mode with zero errors.

---

## Testing Requirements

### Test Categories

| Marker | Description | Requirements |
| ------ | ----------- | ------------ |
| `unit` | Fast isolated tests | None |
| `integration` | Module interaction tests | None |
| `vs_required` | VapourSynth tests | VapourSynth runtime |
| `network` | Network tests | Internet access |

### Running Tests

```bash
# All unit tests
.venv/bin/pytest -q

# Specific markers
.venv/bin/pytest -m unit
.venv/bin/pytest -m "not vs_required"

# With coverage
.venv/bin/pytest --cov=src/frame_compare --cov-report=term-missing
```

### Docker Integration Tests

For full integration with VapourSynth + FFmpeg:

```bash
bash tools/verify_docker_integration.sh
```

---

## Releases

Releases are automated from `main` using [Release Please](https://github.com/googleapis/release-please).

### How it works (no manual tagging)

- On every push to `main`, the Release Please workflow opens or updates a PR like `chore(release): v0.1.1`.
- Merging that PR publishes the GitHub Release and tag (e.g. `v0.1.1`).
- If the repo has Auto-merge enabled, the workflow attempts to set the release PR to auto-merge once required checks pass.

### CI on release PRs (recommended)

GitHub does not trigger other workflows from PRs created using the default `GITHUB_TOKEN`. To ensure CI runs on the
Release Please PR, add a `RELEASE_PLEASE_TOKEN` repo secret (a fine-scoped PAT or GitHub App token with permissions to
open PRs and create releases). The workflow falls back to `GITHUB_TOKEN` if the secret is not set.

---

## Project Guardrails

For detailed coding standards and approval requirements, see:

- [CODEX.md](CODEX.md) — Project guardrails and approval requirements
- [AGENTS.md](AGENTS.md) — Agent-specific guidelines (for AI assistants)

---

## Questions?

- Check the [documentation](docs/)
- Open a [discussion](https://github.com/TJZine/frame-compare/discussions)
- Review existing [issues](https://github.com/TJZine/frame-compare/issues)
