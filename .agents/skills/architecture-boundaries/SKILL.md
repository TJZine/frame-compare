---
name: architecture-boundaries
description: Use when changing module ownership, composition roots, hotspot files, import layers, or any refactor that could expand responsibilities across Frame Compare's architecture.
---

# Architecture Boundaries

## Overview

Use this skill to keep Frame Compare's CLI-first Python architecture cohesive,
layered, and explicit without forcing either monoliths or artificial fragmentation.

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
- One workflow, one owner. Keep new behavior in the current owner when it shares the
  same invariants, state, lifecycle, and reason to change. Extract a focused owner
  only for a distinct present-day phase, policy, lifecycle, trust boundary, or
  stable caller contract.
- Keep sibling domains independent: analysis, render, and services should not quietly depend on each other's internals.
- Keep filesystem ownership deterministic: stable ordering, stable JSON/TOML output, and atomic writes where the repo already uses them.
- Do not add compatibility shims, legacy bridges, or fallback API variants unless explicitly requested.
- Do not create an interface, registry, strategy, factory, or pass-through service
  for speculative reuse. A new owner must transfer meaningful responsibility and
  improve navigation or boundary enforcement now.
- Do not extract solely for line count, test convenience, or a hypothetical future
  consumer. Do not keep accumulating unrelated behavior merely because extraction
  would add a file.
- If ownership is unclear, stop and resolve the boundary before coding.

## Architecture Attention

Use physical production LOC only as a review trigger, never as a decomposition
verdict. Exclude generated assets.

- Above 500 lines: inspect the full owner and record the compact disposition below.
- Above 800 lines, or for a named hotspot or composition root: require one fresh
  Sol-high architecture review before closeout.
- Below either threshold: still extract when the change introduces a distinct owner.

```text
Owner | Existing responsibility | New behavior
Decision: cohesive growth | extract
Evidence
```

The reviewer must reject both responsibility accumulation and thin forwarding
abstractions created only to reduce file length.

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
2. Identify the current owner's responsibility from docs and source before editing.
3. Decide whether the behavior shares that owner's invariants, state, lifecycle,
   and reason to change. If not, define one focused target owner and its current API.
4. Add or tighten behavior tests when the seam is under-protected; do not extract
   solely to expose private state to tests.
5. Cross-check the final diff against `importlinter.ini`, the owner map, and the
   architecture disposition when one was triggered.

## Verification

- Use the exact runbook verification gate for the classified risk; do not copy or
  omit individual commands from that canonical recipe.
- Run full verification for hotspots, architecture authority, public CLI/config
  contracts, Docker/runtime, Windows portable/release, or import-layer changes.
- Add the targeted proof for the owner seam; the full suite does not replace it.
- Use one independent review for the triggered hotspot surface. Repeat review only
  after a material finding or material review-surface change.

## Common Mistakes

- Adding an unrelated branch to a hotspot instead of extracting a real owner
- Splitting cohesive behavior into tiny helpers or forwarding services to satisfy LOC
- Eagerly importing heavy runtime modules from CLI paths
- Letting config/env parsing leak into domain logic
- Changing import layers without updating docs and tests
- Treating passing tests alone as proof that the architecture stayed clean
