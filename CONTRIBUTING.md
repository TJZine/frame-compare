# Contributing to Frame Compare

Thank you for improving Frame Compare. This guide covers contributor setup and pull
request mechanics. The [Engineering Runbook](docs/ENGINEERING_RUNBOOK.md) is the
canonical source for risk classification, verification, release gates, and handoff
requirements.

## Prerequisites

| Tool | Requirement | Purpose |
| --- | --- | --- |
| Python | 3.13 or newer | Application and test runtime |
| `uv` | Repository-selected compatible version | Locked dependency and command execution |
| Git | Recent release | Version control |
| Docker | Optional for ordinary work; required for Docker/runtime changes | Integration proof |
| PowerShell on Windows | Required for portable packaging changes | Windows build, install, update, and verification paths |

## Development setup

Clone the repository and install the canonical frozen contributor environment:

```bash
git clone https://github.com/TJZine/frame-compare.git
cd frame-compare
uv sync --group dev --frozen
```

A pip-only editable installation can run the application, but it does not reproduce the
complete contributor or CI toolchain.

Use the runbook command canon to confirm the environment is healthy before changing
code.

### Optional Codanna setup

Codanna users should generate checkout-local settings before indexing. The generated
file is ignored because Codanna requires canonical absolute roots:

```bash
python3 scripts/bootstrap_codanna.py
codanna config
codanna index
```

Re-run the bootstrap after moving the checkout. Project-wide defaults remain in the
tracked `.codanna/settings.toml.in` template; never commit the rendered
`.codanna/settings.toml`.

## Branch and pull request workflow

1. Start from the base branch named in the issue, handoff, or maintainer request.
   Otherwise target `main`.
2. Create a focused branch:

   ```bash
   git switch -c feat/your-change
   ```

3. Keep the change bounded to one coherent outcome.
4. Add or update tests and documentation for public behavior.
5. Run risk-matched verification from the runbook.
6. Open a pull request against the intended integration branch.

Do not assume `main`, `staging`, `cleanup`, or a version-development branch is the
correct target when the task names another base explicitly.

## Pull request titles

Use Conventional Commit format because the squash title becomes release history:

| Type | Use |
| --- | --- |
| `feat:` | New user-visible behavior |
| `fix:` | Bug fix |
| `docs:` | Documentation-only change |
| `refactor:` | Internal restructuring without a behavior change |
| `perf:` | Performance improvement |
| `test:` | Test-only change |
| `build:` | Build system or dependency change |
| `ci:` | Workflow change |
| `chore:` | Maintenance outside production and test behavior |
| `revert:` | Revert of an earlier change |

Scopes are optional:

```text
feat(cli): add structured history filtering
fix(render): preserve range metadata during tonemapping
docs: restructure the user guide
```

## Code style

### Python

- Use Python 3.13+ syntax and complete type annotations.
- Prefer `pathlib.Path` for filesystem paths.
- Keep public behavior at explicit owner boundaries.
- Add docstrings to public functions.
- Preserve the repository’s 100-character formatting target.

### Formatting and linting

```bash
uv run --no-sync ruff check .
uv run --no-sync ruff check --fix .
uv run --no-sync ruff format .
```

### Type checking

```bash
uv run --no-sync pyright --warnings
```

All production code must pass the configured strict Pyright policy.

## Tests and verification

Test markers include:

| Marker | Meaning |
| --- | --- |
| `unit` | Fast isolated coverage |
| `integration` | Module interaction |
| `e2e` | End-to-end CLI behavior |
| `vs_required` | Requires a VapourSynth runtime |
| `slow` | Long-running proof |
| `network` | Requires external network access |
| `tier_a` | Contract/security tests without VS or network |

Examples:

```bash
uv run --no-sync pytest -q
uv run --no-sync pytest -m unit
uv run --no-sync pytest -m "not vs_required"
uv run --no-sync pytest --cov=src/frame_compare --cov-report=term-missing
```

These examples do not replace the runbook. Changes to CLI/config contracts, runtime
owners, Docker, Windows portable packaging, release workflows, or architectural
boundaries require their documented complete verification paths.

## Documentation development

Authored documentation lives under `docs/`. `zensical.toml` owns site navigation and
presentation settings. Generated site output belongs in the ignored `site/` directory.

Install the locked documentation environment and run a strict build:

```bash
uv sync --only-group docs --locked
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
```

Preview locally:

```bash
uv run --no-sync zensical serve
```

A docs-only sync replaces the ordinary contributor environment. Restore both groups
before continuing application checks:

```bash
uv sync --group dev --group docs --locked
```

`docs/api.md` is generated by `scripts/generate_api_docs.py`. Update the generator or
its source definitions rather than editing generated output manually.

Documentation expectations:

- Begin with user goals and observable outcomes.
- Keep task guides separate from maintainer contracts.
- Use screenshots only when they add information that text cannot convey efficiently.
- Include useful alt text and redact private paths, source names, and secrets.
- Avoid decorative emoji, marketing filler, and diagrams that merely restate a sentence.
- Update the authoritative contract in the same change when public behavior changes.

## Architecture and public contracts

Consult the relevant authority before changing a boundary:

- [Current Architecture](docs/current-architecture.md)
- [CLI Behavioral Contract](docs/current-cli-contract.md)
- [Supported Media Runtime](docs/supported-media-runtime.md)
- [Import contracts](importlinter.ini)

Do not create a second architecture summary, runbook, or current CLI contract.

## Contribution licensing

Submitted contributions are licensed under `GPL-3.0-only`. Contributors affirm that
they have the right to submit the work under those terms.

## Releases

Release Please owns reviewed version and changelog pull requests after project
initialization. The guarded Windows release workflow owns exact-commit publication,
mandatory assets, checksums, update signing, and final release creation.

Maintainer procedure and current branch policy live exclusively in the
[Engineering Runbook](docs/ENGINEERING_RUNBOOK.md). Historical initial-release steps
belong in release evidence, not this contributor onboarding guide.
