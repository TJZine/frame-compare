---
name: architecture-boundaries
description: Use when changing module ownership, composition roots, hotspot files, import layers, or any refactor that could expand responsibilities across Frame Compare's architecture.
---

# Architecture Boundaries

## Overview

Use this skill to keep Frame Compare's CLI-first Python architecture small, layered, and explicit.

The default move is extraction into the existing owner, not accretion in hotspots.

## Use This Skill For

- Changes touching composition roots: [`src/frame_compare/cli/entry.py`](../../../src/frame_compare/cli/entry.py), [`src/frame_compare/runner.py`](../../../src/frame_compare/runner.py), or [`src/frame_compare/orchestration/coordinator.py`](../../../src/frame_compare/orchestration/coordinator.py)
- Work in current hotspots listed in [`docs/current-architecture.md`](../../../docs/current-architecture.md)
- Changes to `importlinter.ini` or top-level package boundaries
- New coordinators, services, repositories, adapters, or output owners
- Refactors that move logic between CLI, config, orchestration, analysis, render, services, VapourSynth, or filesystem owners
- Type-heavy Python refactors where owner boundaries, DTO shapes, or import-time behavior may change

## Core Rules

- Treat `cli/entry.py`, `runner.py`, and `orchestration/coordinator.py` as composition and routing surfaces. Keep feature policy and heavy runtime logic in focused owners.
- Preserve lazy CLI import behavior. Help/version/simple CLI paths should not import the full VapourSynth/runtime stack.
- Keep config and environment interpretation centralized in config, CLI, preflight, or bootstrap owners.
- Respect `importlinter.ini`; update it in the same pass only when the architecture decision is intentional.
- One workflow, one owner. If orchestration starts absorbing a distinct phase or policy, prefer a focused module with an explicit API.
- Keep sibling domains independent: analysis, render, and services should not quietly depend on each other's internals.
- Keep filesystem ownership deterministic: stable ordering, stable JSON/TOML output, and atomic writes where the repo already uses them.
- Do not add compatibility shims, legacy bridges, or fallback API variants unless explicitly requested.
- If ownership is unclear, stop and resolve the boundary before coding.

## Required Reading

1. [`docs/ENGINEERING_RUNBOOK.md`](../../../docs/ENGINEERING_RUNBOOK.md)
2. [`docs/current-architecture.md`](../../../docs/current-architecture.md)
3. [`docs/current-cli-contract.md`](../../../docs/current-cli-contract.md) when CLI/config behavior is involved
4. [`importlinter.ini`](../../../importlinter.ini)

## Boundary Routing

- If the change touches config, generated caches, run folders, presets, reports, or filesystem persistence, also load `persistence-boundaries`.
- If the change touches FFmpeg, VapourSynth, TMDB, slow.pics, Docker, or Windows portable/release behavior, also load `runtime-integration-boundaries`.
- If the change touches generated HTML reports, overlay text, screenshot naming, or user-visible output formatting, also load `report-output-patterns`.
- If the change touches Python typing, Pydantic schemas, HTTPX clients, Typer/Rich wiring, or typed internal seams, also load `python-quality-boundaries`.
- If the change touches CLI commands, options, streams, JSON mode, help text, exit codes, or config-persistence flags, also load `cli-contract-boundaries`.
- If the change adds or reshapes tests, fixtures, markers, subprocess checks, HTTP mocks, or property-based tests, also load `python-test-design`.

## Discovery Pattern

1. Find exact owners and callers with search/direct reads. Use Codanna semantic or
   impact tools when available and materially useful for an unknown or shared seam;
   do not delay work merely to record a preferred-tool fallback.
2. Identify the current owner from docs and source before editing.
3. Define the target owner, public API, invariants, and verification surface.
4. Add or tighten behavior tests when the seam is under-protected.
5. Cross-check the final diff against `importlinter.ini` and the owner map.

## Verification

- Use the exact runbook verification gate for the classified risk; do not copy or
  omit individual commands from that canonical recipe.
- Run full verification for hotspots, architecture authority, public CLI/config
  contracts, Docker/runtime, Windows portable/release, or import-layer changes.
- Add the targeted proof for the owner seam; the full suite does not replace it.

## Common Mistakes

- Adding one more branch to a hotspot instead of extracting a real owner
- Eagerly importing heavy runtime modules from CLI paths
- Letting config/env parsing leak into domain logic
- Changing import layers without updating docs and tests
- Treating passing tests alone as proof that the architecture stayed clean
