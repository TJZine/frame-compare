# Current Architecture

This document describes the present-day Frame Compare codebase. It is intentionally about what exists now, not desired future structure.

## Operating Stance

Frame Compare is a CLI-first packaged Python app with importable internal modules. The CLI and release artifacts are the primary supported surfaces.

## Composition Roots

- CLI entrypoint: `frame_compare.cli_entry:app`
- Runtime entry surface: `frame_compare.runner.run(...)`
- Async orchestration root: `frame_compare.orchestration.execute_run(...)`
- Diagnostic entry surface: `frame_compare.orchestration.doctor.run_doctor(...)`

The CLI keeps VS-heavy imports lazy through proxy functions so help text and simple commands do not import the full runtime stack at module import time.

## Runtime Flow

The main run path is:

1. Resolve root and config.
2. Prepare preflight and workspace paths.
3. Discover input clips.
4. Create a run folder when configured.
5. Load or compute clip probe data.
6. Execute orchestration phases in order:
   `frame_plan -> analyze -> align -> render -> metadata -> dovi -> publish -> report`

`frame_compare.orchestration.context.RunContext` carries the shared run state across phases.

## Module Boundaries

Import boundaries are enforced by `importlinter.ini`.

High-level layering:

- `frame_compare.cli_entry`
- `frame_compare.cli_output`
- `frame_compare.runner`
- `frame_compare.orchestration`
- sibling domain modules: `frame_compare.analysis`, `frame_compare.render`, `frame_compare.services`
- `frame_compare.vspreview`
- `frame_compare.vs`
- `frame_compare.config`
- `frame_compare.utils`
- `frame_compare.errors`

Working rule: keep new code inside the existing owner module unless there is a strong reason to create a new top-level boundary and update `importlinter.ini` in the same pass.

## Persistence And Filesystem Owners

The repo uses filesystem persistence, not a database.

Primary owned paths:

- `config/config.toml` and `config/presets/*.toml`: config owners
- `generated/cache/cache.compframes`: analysis metrics cache
- `generated/clip_probe.toml`: clip probe cache
- `generated/audio_offsets.toml`: alignment cache
- generated VSPreview session and override files under the generated/run area
- screenshot output directories and generated HTML reports
- Windows portable bundle outputs under `dist/frame-compare-portable-win-x64`

`WorkspacePaths` resolves the runtime path set and can switch into run-folder mode so screenshots and generated files live inside an input-specific run directory.

## External Boundaries

External runtime boundaries:

- FFmpeg / ffprobe subprocess calls
- VapourSynth runtime and plugins
- TMDB HTTP API
- slow.pics HTTP API
- default browser auto-open for generated reports
- Docker build/test runtime
- Windows PowerShell installer and updater scripts

Keep these integrations at their current owners:

- metadata lookups: `frame_compare.services.metadata`
- publishing: `frame_compare.services.publishers`
- browser auto-open for generated reports: `frame_compare.cli_entry`
- HTML report generation: `frame_compare.services.report`
- VS loading and HDR/tonemap logic: `frame_compare.vs.*`
- packaging/install/update flow: `tools/windows_portable/**`

## Public Boundaries

The repo exposes two kinds of externally visible surfaces today:

- user-facing CLI/config/release-asset behavior
- importable package modules and re-export namespaces used by tests and internal callers

Compatibility policy for those surfaces is defined in the runbook rather than in this document.

## Current Hotspots

These files currently carry disproportionate change risk:

- `src/frame_compare/orchestration/coordinator.py` (and neighboring `types.py`, `preparation.py`, `execution.py`)
- `src/frame_compare/errors.py`
- `src/frame_compare/services/report/**`
- `src/frame_compare/cli_entry.py`
- `src/frame_compare/services/alignment.py`
- `src/frame_compare/render/orchestrator.py`
- `src/frame_compare/orchestration/doctor.py`
- `src/frame_compare/vspreview/adapter.py`

Working rule: changes to these files should usually trigger full verification and, when they reshape behavior or ownership, a same-pass update to this document.

## Working Rules That Follow From The Codebase

- Keep CLI import time light; do not eagerly import VS-dependent runtime code in `cli_entry.py`.
- Keep config/env loading centralized; do not add ad hoc env reads deep in domain logic.
- The main pipeline passes HTTP clients from `runner` into orchestration, while diagnostics still create their own short-lived client for reachability checks.
- Keep persistence deterministic: stable ordering, stable JSON/TOML output, atomic writes where owners already use them.
- Respect the layered import contracts and sibling-domain independence.
- Treat Docker and Windows portable flows as first-class runtime surfaces, not optional afterthoughts.

## Unknowns And Maintainer Decisions Still Open

- Whether any import-level package APIs should be promoted from convenience-only to supported/stable.
- Whether a durable multi-session plan workflow should become active again in this repo. The runbook currently keeps `docs/plans/` inactive by default.
