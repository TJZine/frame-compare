# Changelog

All notable changes to this project are documented in this file.

This project follows Conventional Commits and is intended to be released via Release Please.

## Unreleased

### Added

- **CI/CD Pipeline:** GitHub Actions workflow with Ruff linting, Pyright type checking, and pytest stages.
- **Phase 0 Foundation:** Project scaffolding with `pyproject.toml`, `src/frame_compare/` structure, and development tooling (Pyright strict, Ruff, pytest).
- CLI entry point with `version` command.
- PEP 561 `py.typed` marker for typed package support.
- Dev dependency `pyyaml` for local contract view checks.
- Dev dependency `import-linter` for running `lint-imports` locally.

### Changed

- Planning/Plan Review prompts: require copy-forward plan revisions and a `## Changes Since plan-vN` summary to reduce churn during plan iteration.
- Docker build now compiles `zimg` and `l-smash` from official release tarballs with checksum verification, installs Cython via pip for Python 3.13 compatibility, pins L-SMASH-Works to a published tag, and guards SSE2 headers for ARM builds.
- Docker build adds `python3-jinja2` and `libvulkan-dev` to satisfy libplacebo tooling requirements, pins vs-placebo to a commit with submodules, and pins ffms2 to a FFmpeg 5-compatible commit.
- Docker runtime image installs `wget` and `ca-certificates` to support DevContainer server bootstrap.
- Docker runtime image installs `which` so the DevContainer bootstrap can detect `wget`.
- Docker runtime image installs `procps` to provide `ps` for DevContainer bootstrap.
- OPUS rebuild docs synced to the container baseline (`Dockerfile`) and updated to match current Bookworm/pin assumptions (deployment/system design/ADR/vs-module/feature parity).
- Documentation updates L-SMASH Works verification to prefer the `lsmas` namespace with a legacy `lw` fallback.
