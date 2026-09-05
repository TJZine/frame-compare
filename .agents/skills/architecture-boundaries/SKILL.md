---
name: architecture-boundaries
description: Assess Frame Compare responsibility, composition, and import boundaries when adding or moving behavior between owners. Hotspot location alone does not require an architecture workflow for nonbehavioral edits.
---

# Architecture Boundaries

## Overview

Use this skill to keep Frame Compare's CLI-first Python architecture cohesive,
layered, and explicit without forcing either monoliths or artificial fragmentation.

## Use This Skill For

- Changes touching composition roots: [`src/frame_compare/cli/entry.py`](../../../src/frame_compare/cli/entry.py), [`src/frame_compare/runner.py`](../../../src/frame_compare/runner.py), or [`src/frame_compare/orchestration/coordinator.py`](../../../src/frame_compare/orchestration/coordinator.py)
- Behavior or ownership changes in current hotspots listed in [`docs/current-architecture.md`](../../../docs/current-architecture.md)
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
- Resolve ownership from current source, callers, contracts, and task decisions.
  Escalate only consequential choices outside the authorized scope that remain
  unresolved after investigation, following the runbook.

## Architecture Attention

Use physical production LOC and named hotspots as attention signals. Exclude
generated assets. Inspect the affected lifecycle, callers, and invariants; read the
whole owner when needed to assess a behavior or ownership change. Record the
compact disposition below when adding or moving responsibilities. File size alone
does not require it, an extraction, or an independent reviewer. Follow the runbook's
Review Policy for consequential risks that merit a second assessment.

```text
Owner | Existing responsibility | New behavior
Decision: cohesive growth | extract
Evidence
```

The reviewer must reject both responsibility accumulation and thin forwarding
abstractions created only to reduce file length.

## Required Reading

Read the relevant sections first; expand when affected contracts, callers, or
invariants remain unclear. Existing task context need not be reread.

1. [`docs/ENGINEERING_RUNBOOK.md`](../../../docs/ENGINEERING_RUNBOOK.md)
2. [`docs/current-architecture.md`](../../../docs/current-architecture.md)
3. [`docs/current-cli-contract.md`](../../../docs/current-cli-contract.md) when CLI/config behavior is involved
4. [`importlinter.ini`](../../../importlinter.ini)

## Boundary Routing

Load another skill only when the changed boundary needs guidance not already in
context. These routes are conditional, not a checklist for every architecture task.

- If the change alters persisted schemas, recovery, writes, or managed paths, consult `persistence-boundaries`; presentation-only report work does not require it.
- If the change touches FFmpeg, VapourSynth, TMDB, slow.pics, Docker, or Windows portable/release behavior, consult relevant guidance in `runtime-integration-boundaries`.
- If the change touches generated HTML reports, overlay text, screenshot naming, or user-visible output formatting, consult relevant guidance in `report-output-patterns`.
- If the change touches Python typing, Pydantic schemas, HTTPX clients, Typer/Rich wiring, or typed internal seams, consult relevant guidance in `python-quality-boundaries`.
- If the change touches CLI commands, options, streams, JSON mode, help text, exit codes, or config-persistence flags, consult relevant guidance in `cli-contract-boundaries`.
- If the change adds or reshapes tests, fixtures, markers, subprocess checks, HTTP mocks, or property-based tests, consult relevant guidance in `python-test-design`.

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
- Use the runbook's behavior-based gate and nonbehavioral exception; preserve
  required proof for changed public contracts, runtime, release, and import layers.
- Add the targeted proof for the owner seam; the full suite does not replace it.
- Use independent review under the runbook's Review Policy. Repeat review only
  after a material finding or material review-surface change.

## Common Mistakes

- Adding an unrelated branch to a hotspot instead of extracting a real owner
- Splitting cohesive behavior into tiny helpers or forwarding services to satisfy LOC
- Eagerly importing heavy runtime modules from CLI paths
- Letting config/env parsing leak into domain logic
- Changing import layers without updating docs and tests
- Treating passing tests alone as proof that the architecture stayed clean
