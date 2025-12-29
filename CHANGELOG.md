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
- Complete error hierarchy: DependencyError, InputError, ProcessingError, NetworkError, InternalError
- `ExitCode` enum for CLI exit code mapping
- `get_exit_code()` helper function
- `format_error_console()` and `format_error_json()` formatting utilities
- Structured logging infrastructure with structlog (json/console formats)
- Correlation ID tracking for run tracing (`new_run_id`, `get_run_id`)
- CLI foundation commands: `run` (full signature), `wizard`, `doctor`, `preset` (list/apply/save) stubs.
- `handle_error` utility mapping FrameCompareError to exit codes.
- Analysis module types: `ClipIdentity`, `MetricsMetadata`, `FrameMetrics`, `SelectionBreakdown`, `FrameSelection`, `CacheLoadResult`
- Analysis module frame selection algorithms: quantile, motion, and random modes with minimum gap enforcement.
- Analysis module cache I/O: deterministic cache key generation, metrics persistence (JSON Schema v2), and failure-resilient cache loading.
- VapourSynth module foundation (`frame_compare.vs`) with environment detection, plugin checks, and `VSLoader` protocol.
- Video source loading (`load_source`) with LWLibavSource support.
- HDR detection from frame properties (PQ, HLG, BT.2020).
- Frame trimming with inclusive end semantics.


### Changed

- Planning/Plan Review prompts: require copy-forward plan revisions and a `## Changes Since plan-vN` summary to reduce churn during plan iteration.
- Planning/Plan Review/Coding/Review prompts + workflow docs: added SSOT anchoring guardrails (Spec Anchors + one-line signatures + SSOT drift gate), anti-churn line budget + iteration cap, and Review routing rules (implementation defect vs spec drift vs design issue).
- Verification workflow adds `scripts/validate_spec_anchors.py` as a STOP gate for plan/spec consistency.
- Planning/Plan Review prompts: do not gate plan approval on exact `docs/DECISIONS.md` prose; allow large parametric tests to anchor to the SSOT deterministic test vector policy instead of listing exhaustive constructor args.
- Import-linter configuration is treated as SSOT in `importlinter.ini`; docs/workflow updated to match real module paths and require updating `importlinter.ini` whenever new top-level modules are introduced.
- Coding Agent prompt tightened to stop at `impl-vN.md` handoff (no Verification/Review role bleed).
- Coding Agent required to run contract-view freshness check (and regenerate if needed) before handing off to Verification to prevent stale-contract churn.
- Review Agent now outputs a single-line Conventional Commit subject summarizing the full checklist item/run.
- Docker build now compiles `zimg` and `l-smash` from official release tarballs with checksum verification, installs Cython via pip for Python 3.13 compatibility, pins L-SMASH-Works to a published tag, and guards SSE2 headers for ARM builds.
- Docker build adds `python3-jinja2` and `libvulkan-dev` to satisfy libplacebo tooling requirements, pins vs-placebo to a commit with submodules, and pins ffms2 to a FFmpeg 5-compatible commit.
- Docker runtime image installs `wget` and `ca-certificates` to support DevContainer server bootstrap.
- Docker runtime image installs `which` so the DevContainer bootstrap can detect `wget`.
- Docker runtime image installs `procps` to provide `ps` for DevContainer bootstrap.
- OPUS rebuild docs synced to the container baseline (`Dockerfile`) and updated to match current Bookworm/pin assumptions (deployment/system design/ADR/vs-module/feature parity).
- Documentation updates L-SMASH Works verification to prefer the `lsmas` namespace with a legacy `lw` fallback.
