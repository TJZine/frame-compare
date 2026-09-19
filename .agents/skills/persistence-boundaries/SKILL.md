---
name: persistence-boundaries
description: Protect Frame Compare persisted state, serialization, cache recovery, and managed paths. Use for config/preset writes, caches, run records, or output placement; presentation-only edits do not need this skill.
---

# Persistence Boundaries

## Overview

Use this skill to keep filesystem persistence behind explicit owners.

Frame Compare has no database; persistence is mostly config files, generated run artifacts, caches, reports, screenshots, and release outputs.

## Required Reading

Read the relevant sections and affected owners first. Expand to callers, adjacent
contracts, or full documents when material questions remain. Reuse task context.

1. [`docs/ENGINEERING_RUNBOOK.md`](../../../docs/ENGINEERING_RUNBOOK.md)
2. [`docs/current-architecture.md`](../../../docs/current-architecture.md)
3. [`docs/current-cli-contract.md`](../../../docs/current-cli-contract.md) when config or CLI persistence is involved
4. Relevant owner modules such as config loaders, cache IO, run-folder services, report generation, or Windows packaging scripts

## Persistence Owner Categories

Confirm the current file-level owner map in `docs/current-architecture.md`; the
categories below are routing aids, not a second authoritative inventory.

- Config and presets: `src/frame_compare/config/**`
- CLI flag to config mapping: [`src/frame_compare/config/overrides.py`](../../../src/frame_compare/config/overrides.py)
- Runtime path set and run folders: `WorkspacePaths` and `src/frame_compare/services/run_folder.py`
- Analysis/probe/alignment caches: `src/frame_compare/analysis/**`, `src/frame_compare/orchestration/probing/probe_cache.py`, and alignment services
- Generated reports: [`src/frame_compare/services/report/`](../../../src/frame_compare/services/report/)
- Atomic write mechanics: [`src/frame_compare/utils/atomic_write.py`](../../../src/frame_compare/utils/atomic_write.py)
- Windows portable outputs: `tools/windows_portable/**`

## Boundary Routing

- If persistence changes affect CLI flags, config loading, or `--write-config`, consult `cli-contract-boundaries` and the relevant current CLI contract. Use `architecture-boundaries` when ownership or import direction changes.
- If generated output or report presentation changes, consult relevant guidance in `report-output-patterns`.
- If persistence touches Docker, VS, FFmpeg, or Windows packaging, consult relevant guidance in `runtime-integration-boundaries`.

## Core Rules

- Do not scatter path construction, defaults, serialization, or schema decisions across callers.
- Keep config/env interpretation near config, CLI, preflight, or bootstrap owners.
- Preserve deterministic output: stable ordering, stable JSON/TOML, seeded randomness where relevant.
- Use existing atomic-write patterns for durable files when applicable.
- Validate persisted data at its owner and preserve its explicit missing, corrupt,
  and unsupported-version behavior. Invalid user config raises typed errors;
  recoverable caches may miss or warn. Do not silently default authoritative config.
- Reuse `config/persistence.py` for generated config/preset serialization so runtime
  TMDB keys and webhook URLs are excluded. The wizard uses `load_raw_config` to
  preserve the selected document independently of environment overrides.
- Reuse preflight containment and `WorkspacePaths`: config stays under the workspace
  except for the exact portable-state exception; the generated root may be external,
  its managed descendants remain contained, and external media reads are allowed.
- Keep run-folder behavior explicit; do not mix global generated paths with run-scoped outputs by accident.
- Treat CLI/config persistence as public behavior and update the CLI contract in the same pass when it changes.
- Do not let tests depend on unisolated generated state.

## Verification

- Use the applicable runbook verification recipe without substituting a local
  command subset. Persistence does not lower CLI/config, runtime, or release gates.
- Reuse existing owner tests. Add or update valid, invalid, missing/default, or
  filesystem-failure cases only where the changed behavior needs that proof.

## Common Mistakes

- Resolving paths differently in CLI and runtime owners
- Persisting runtime-only flags through `--write-config`
- Hand-writing JSON/TOML in a caller instead of using the owner
- Letting report or cache generation become a second orchestration root
- Forgetting Windows paths and release artifacts are public runtime surfaces
