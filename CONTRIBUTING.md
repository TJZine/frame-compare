# Contributing to Frame Compare

Thank you for your interest in contributing! This guide will help you get started.

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Contribution licensing](#contribution-licensing)
- [Documentation Development](#documentation-development)
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

## Contribution licensing

Submitted contributions are licensed under `GPL-3.0-only`, and contributors affirm
that they have the right to submit them under those terms.

---

## Documentation Development

Authored documentation lives under `docs/`. The root `zensical.toml` owns the public
site navigation and built-in presentation features; do not duplicate documentation in
a separate site project. Generated output belongs in the ignored `site/` directory.

Install the locked documentation toolchain and run a strict build:

```bash
uv sync --only-group docs --locked
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
```

For a local preview, run:

```bash
uv run --no-sync zensical serve
```

A docs-only sync replaces the normal contributor environment. Restore both groups
before running development checks while continuing documentation work:

```bash
uv sync --group dev --group docs --locked
```

Keep `docs/api.md` generated through `scripts/generate_api_docs.py`. Changes to the
generator or its source definitions must pass the drift check above.

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

Release Please owns reviewed version/changelog PRs after initialization. The
guarded Windows workflow owns every public release so mandatory assets always
exist before publication.

### Initial `v0.1.0`

- Prepare and accept a disposable RC on `cleanup` or an approved release branch.
- After RC acceptance, align every version source and `CHANGELOG.md` at `0.1.0`
  and remove temporary `bootstrap-sha`/`release-as` settings on that branch.
- Squash-merge once into `main`. That exact squash commit is the source for
  `v0.1.0`; there is no generated initial version-bump commit.
- A maintainer dispatches **Windows portable** from `main` with operation
  `release`, channel `stable`, version `0.1.0`, tag `v0.1.0`, and the exact
  40-character `main` SHA.
- The workflow rejects a moved `main`, existing tag/release, version disagreement,
  RC syntax, missing changelog entry, incomplete assets, or unsigned update. It
  creates and verifies a complete draft first, then publishes as its final step.
- Stable publication uses the protected GitHub `production` environment and
  requires maintainer approval.

Do not create or move the tag manually. Live RC/stable dispatches, environment
approval, release/tag cleanup, and the final squash are maintainer-only operations.

### Later releases

After the published stable `v0.1.0` release exists, [Release
Please](https://github.com/googleapis/release-please) resumes version-PR behavior
on pushes to `main`:

- it opens or updates a human-reviewed release PR;
- it never auto-merges that PR;
- it does not create a tag or GitHub release;
- after merging the approved release PR, a maintainer publishes its exact `main`
  commit through **Windows portable** with operation `release`, the final version
  and tag, and the exact SHA.

Configure `RELEASE_PLEASE_TOKEN` as a narrowly scoped fine-grained PAT or GitHub
App token when release-created pull requests must trigger the normal CI suite.
Restrict it to this repository, use a bounded lifetime, and grant only the
contents and pull-request permissions required by the pinned action.

Repository maintainers must also create a `production` Actions environment,
configure required reviewers, prevent self-review where supported, and restrict
deployment branches/tags to the approved stable policy. The environment protects
every stable publication job; repository secrets remain configured under Actions
without exposing their values.

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
