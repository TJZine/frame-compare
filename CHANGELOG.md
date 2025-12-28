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

### Changed

- Planning/Plan Review prompts: require copy-forward plan revisions and a `## Changes Since plan-vN` summary to reduce churn during plan iteration.
