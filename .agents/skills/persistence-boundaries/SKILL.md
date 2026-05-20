---
name: persistence-boundaries
description: Use when adding or changing config persistence, generated caches, run folders, presets, reports, bundle outputs, or any code that reads or writes Frame Compare filesystem state.
---

# Persistence Boundaries

## Overview

Use this skill to keep filesystem persistence behind explicit owners.

Frame Compare has no database; persistence is mostly config files, generated run artifacts, caches, reports, screenshots, and release outputs.

## Required Reading

1. [`docs/ENGINEERING_RUNBOOK.md`](../../../docs/ENGINEERING_RUNBOOK.md)
2. [`docs/current-architecture.md`](../../../docs/current-architecture.md)
3. [`docs/current-cli-contract.md`](../../../docs/current-cli-contract.md) when config or CLI persistence is involved
4. Relevant owner modules such as config loaders, cache IO, run-folder services, report generation, or Windows packaging scripts

## Current Persistence Owners

- Config and presets: `src/frame_compare/config/**`
- CLI flag to config mapping: [`src/frame_compare/config/overrides.py`](../../../src/frame_compare/config/overrides.py)
- Runtime path set and run folders: `WorkspacePaths` and `src/frame_compare/services/run_folder.py`
- Analysis/probe/alignment caches: `src/frame_compare/analysis/**`, `src/frame_compare/orchestration/probe_cache.py`, and alignment services
- Generated reports: [`src/frame_compare/services/report.py`](../../../src/frame_compare/services/report.py)
- Atomic write mechanics: [`src/frame_compare/utils/atomic_write.py`](../../../src/frame_compare/utils/atomic_write.py)
- Windows portable outputs: `tools/windows_portable/**`

## Boundary Routing

- If persistence changes affect CLI flags, config loading, or `--write-config`, also load `architecture-boundaries` and check `docs/current-cli-contract.md`.
- If generated output or report presentation changes, also load `report-output-patterns`.
- If persistence touches Docker, VS, FFmpeg, or Windows packaging, also load `runtime-integration-boundaries`.

## Core Rules

- Do not scatter path construction, defaults, serialization, or schema decisions across callers.
- Keep config/env interpretation near config, CLI, preflight, or bootstrap owners.
- Preserve deterministic output: stable ordering, stable JSON/TOML, seeded randomness where relevant.
- Use existing atomic-write patterns for durable files when applicable.
- Normalize invalid or missing persisted values at the owner boundary.
- Keep run-folder behavior explicit; do not mix global generated paths with run-scoped outputs by accident.
- Treat CLI/config persistence as public behavior and update the CLI contract in the same pass when it changes.
- Do not let tests depend on unisolated generated state.

## Verification

- For config/CLI persistence changes, run full verification.
- For isolated owner changes, run focused tests plus `pyright`, `ruff`, and import-linter when imports changed.
- Add or update tests for valid stored value, invalid value, missing/default value, and filesystem failure when the owner behavior changes.

## Common Mistakes

- Resolving paths differently in CLI and runtime owners
- Persisting runtime-only flags through `--write-config`
- Hand-writing JSON/TOML in a caller instead of using the owner
- Letting report or cache generation become a second orchestration root
- Forgetting Windows paths and release artifacts are public runtime surfaces
