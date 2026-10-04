# Contributing to Frame Compare

Thank you for improving Frame Compare. This guide covers contributor setup and pull
request mechanics. The [repository profile](.agents/project.md) owns local contracts
and command routes. Shared skills own agent methodology; the
[Engineering Runbook](docs/ENGINEERING_RUNBOOK.md) preserves complete specialist
verification, platform, release, and durable-plan procedures.

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
uv sync --group dev --extra vsview --frozen
```

A pip-only editable installation can run the application, but it does not reproduce the
complete contributor or CI toolchain.

Use the repository profile and relevant runbook recipe to establish the capabilities
needed for the task. Do not run unrelated gates merely to begin an edit.

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
4. Select meaningful evidence for the changed behavior and update affected product
   documentation. Reuse sufficient proof; do not add tests merely to satisfy a step.
5. Run applicable verification from the repository profile and specialist runbook.
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

Pyright checks both `src/` and `tests/` under their configured typing policies.

## Tests and verification

Test markers include:

| Marker | Meaning |
| --- | --- |
| `unit` | Fast isolated coverage |
| `integration` | Module interaction |
| `e2e` | End-to-end CLI behavior in `tests/e2e/`; includes the runtime-free CLI tier and media tier |
| `vs_required` | Media-tier E2E scenarios that require a VapourSynth runtime |
| `slow` | Long-running proof |
| `network` | Requires external network access |
| `tier_a` | Contract/security tests without VS or network |

Examples:

```bash
uv run --no-sync pytest -q -n4 --dist loadgroup
uv run --no-sync pytest -m unit
uv run --no-sync pytest -m "not vs_required"
uv run --no-sync pytest -q tests/e2e/ -m "e2e and not vs_required"  # CLI tier
bash tools/verify_docker_integration.sh --pytest-path tests/e2e  # focused media scenarios
uv run --no-sync pytest --cov=src/frame_compare --cov-report=term-missing
```

The CLI tier runs without a media runtime. The media tier is Docker-only: the gate
sets `FRAME_COMPARE_E2E_REQUIRE_MEDIA=1` and `FRAME_COMPARE_E2E_ARTIFACTS` for the
pinned media runtime and its inspectable scenario artifacts.

The full Docker gate is `bash tools/verify_docker_integration.sh`: it runs E2E,
integration and VS tests with ten workers and `--dist loadgroup`, plus runtime and
production-image proofs. It excludes the long-running alignment resource module;
see the runbook's separate resource command when streaming alignment memory or
collector cleanup changes. Docker CI runs that proof separately. The focused media command above is for development and
scenario proof; use the full gate for the runbook's runtime, dependency and media
boundary triggers. Images build by default; rebuild after `docker-test` dependency
or `uv.lock` changes before using the new plugin. Use `--no-build` only with
known-current images.

The verifier sets `FRAME_COMPARE_TEST_MEDIA_CACHE` to
`/workspace/generated/test-media-cache` (host `generated/test-media-cache`) for u4
media only. Entries use `<cache>/<generator>/<key>/`, keyed by exact generator
source and complete FFmpeg version output. Tests use temporary symlinks, keeping
indexes outside the cache; unset the variable for temporary generation. Run the
verifier one at a time from a checkout because cache pruning cannot overlap.
CI starts cold, adds no media cache, and retains Docker `--no-cache`.

New tests must be parallel-safe: use `tmp_path` and `monkeypatch`, avoid fixed paths
or ports, and use `xdist_group` only with a stated concrete reason. The local full
native count is four; focused runs may stay serial. Native CI uses
`-n auto --dist loadgroup`; Windows portable CI stays serial.

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
uv sync --group dev --group docs --extra vsview --locked
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
