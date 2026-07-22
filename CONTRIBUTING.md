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

Use the repository's canonical frozen uv environment:

```bash
uv sync --group dev --frozen
```

The project uses uv dependency groups and its lockfile for the complete contributor
toolchain. A pip-only editable install can run the application, but it is not a
substitute for the canonical environment and cannot be assumed to reproduce the
full local or CI gates.

### 3. Verify your setup

Use the [Engineering Runbook](docs/ENGINEERING_RUNBOOK.md) command canon to verify that
the local environment is healthy.

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

Use the [Engineering Runbook](docs/ENGINEERING_RUNBOOK.md) to choose and run the
required verification for the current change.

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

Ensure the required GitHub Actions checks pass before merge. Treat the
[Engineering Runbook](docs/ENGINEERING_RUNBOOK.md) and the workflow files under
`.github/workflows/` as the current source of truth for required verification.

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
uv run --no-sync ruff check .

# Auto-fix safe issues
uv run --no-sync ruff check --fix .

# Format code
uv run --no-sync ruff format .
```

### Type Checking

We use [Pyright](https://microsoft.github.io/pyright/) in strict mode:

```bash
uv run --no-sync pyright --warnings
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
| `e2e` | End-to-end CLI tests | None |
| `vs_required` | VapourSynth tests | VapourSynth runtime |
| `slow` | Long-running tests | Extra runtime |
| `network` | Network tests | Internet access |
| `tier_a` | Contract/security tests | No VS, no network |

### Running Tests

Examples only. Merge and release gates still come from the
[Engineering Runbook](docs/ENGINEERING_RUNBOOK.md).

Fast isolated tests default into the `unit` bucket during collection. Use explicit
markers for heavier routes such as `integration`, `e2e`, `vs_required`, `slow`, or
`network`.

```bash
# All unit tests
uv run --no-sync pytest -q

# Specific markers
uv run --no-sync pytest -m unit
uv run --no-sync pytest -m "not vs_required"

# With coverage
uv run --no-sync pytest --cov=src/frame_compare --cov-report=term-missing
```

### Docker Integration Tests

For Docker-based verification requirements, use the
[Engineering Runbook](docs/ENGINEERING_RUNBOOK.md).

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

Repo-wide workflow policy lives in the [Engineering Runbook](docs/ENGINEERING_RUNBOOK.md).

Supporting pointers:

- [AGENTS.md](AGENTS.md) — short agent entrypoint map
- [Current Architecture](docs/current-architecture.md) — present-day runtime and boundary map
- [CODEX.md](CODEX.md) — thin Codex pointer only

---

## Questions?

- Check the [documentation](docs/)
- Open a [discussion](https://github.com/TJZine/frame-compare/discussions)
- Review existing [issues](https://github.com/TJZine/frame-compare/issues)
