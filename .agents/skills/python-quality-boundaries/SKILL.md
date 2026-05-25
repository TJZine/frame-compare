---
name: python-quality-boundaries
description: Use when changing Python production code, typing, Pyright behavior, Pydantic schemas, HTTPX usage, Typer/Rich wiring, error handling, or typed internal seams in Frame Compare.
---

# Python Quality Boundaries

## Overview

Use this skill to keep Frame Compare's Python code strict, typed, maintainable, and production-safe.

Pyright strictness is a design constraint, not a cleanup step.

## Research Basis

This skill is based on official documentation for Python 3.13 typing, Pyright configuration, Pydantic v2 validation, HTTPX clients/timeouts, Typer, Rich, pytest, and PyPA packaging, plus Frame Compare's current `pyproject.toml`, source layout, and tests.

## Use This Skill For

- Changes under `src/frame_compare/**`
- Typing, Pyright, import, decorator, callback, or dynamic-object work
- Pydantic config/schema/validation changes
- HTTPX clients, transport, timeout, status handling, or network boundary changes
- Typer/Rich CLI implementation changes
- Error mapping, exception wrapping, and typed result/DTO shapes

## Required Reading

1. [`pyproject.toml`](../../../pyproject.toml) for Python version, Pyright, Ruff, pytest, and packaging config
2. [`docs/ENGINEERING_RUNBOOK.md`](../../../docs/ENGINEERING_RUNBOOK.md)
3. [`docs/current-architecture.md`](../../../docs/current-architecture.md)
4. [`docs/current-cli-contract.md`](../../../docs/current-cli-contract.md) when CLI behavior is involved
5. Relevant owner modules and tests

## Core Rules

- Do not introduce `Any`, bare containers, untyped decorators, untyped callbacks, broad `dict[str, Any]`, or ignored diagnostics unless the diff includes a narrow reason and a safer alternative was considered.
- Prefer `object` for unknown external values, then validate and narrow at the boundary.
- Do not broaden an established internal domain type, union, dataclass, protocol,
  or result DTO to `object`, `Any`, or an ad hoc dictionary merely to satisfy a
  call site. In hotspot/orchestration code, preserving typed seams is part of the
  design even when Pyright would accept the broader type.
- Prefer Python 3.13-era typing: built-in generics, `type Alias = ...`, `collections.abc` protocols/ABCs, `NewType` for logically distinct IDs, and `typing.assert_never` for exhaustive branches.
- Keep `TYPE_CHECKING` guards and lazy imports where the repo uses them to avoid heavy optional/runtime imports.
- Use `typing.cast` only after a real runtime guard or source-backed library limitation; never use it to silence design ambiguity.
- Avoid broad `except Exception` unless the owner boundary is explicitly translating unknown failures. Preserve useful sanitized causes.
- Keep command functions and composition roots thin: parse inputs, call typed services, translate failures, and return/report outcomes.

## Typed Boundary Shapes

- External input: raw library value or `object` -> Pydantic `model_validate`, `TypeAdapter`, or a focused parser.
- Internal data: dataclasses, protocols, typed aliases, explicit result types, and concrete return annotations.
- Output: explicit DTO/serializer shape, not ad hoc dictionaries spread across callers.

When reviewing typed seams, compare the changed signature against neighboring
types and call sites. If a named type alias or union already represents the
allowed outputs, use it on both producer and consumer sides and keep runtime
guards for defensive checks. Passing Pyright is not enough if the diff weakens
static exhaustiveness or hides an owner-boundary contract.

## Pydantic Rules

- Use Pydantic v2 `ConfigDict`, validators, and `model_post_init`; do not add v1-style `Config` or custom `__init__` patterns.
- Default to `extra="forbid"` for config, API, and file schemas where unexpected fields would hide contract drift.
- Frame Compare's root `ConfigSchema` currently uses `extra="ignore"` as public config behavior. Do not tighten it without an explicit contract decision, doc update, and tests.
- Use `strict=True` at model, field, adapter, or validation-call level when coercion would hide bugs.
- Allow coercion only when it is the public contract, and test that behavior.
- Do not use Pydantic models as internal domain structs by default; validate at boundaries, then pass typed domain values inward.

## HTTPX Rules

- Inject `httpx.Client` or `httpx.AsyncClient` when network behavior must be tested or shared.
- Use context managers or explicit close for clients owned by the code.
- Configure explicit timeout/resource policy for production network calls.
- Call `raise_for_status()` or handle status codes intentionally.
- Test HTTP behavior without live network by default.

## Verification

- Run the runbook-selected gate.
- For logic changes, expect focused pytest for the touched behavior plus:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
```

- Run full `pytest -q` and the rest of the full gate when the runbook classifies the change as full-verification work.
- Also run import-linter when imports or top-level module boundaries changed.
- Pair CLI changes with `cli-contract-boundaries`; pair test changes with `python-test-design`.

## Common Mistakes

- Treating Pyright strict failures as noise instead of design feedback
- Using `Any`, `cast`, or `type: ignore` before narrowing the boundary
- Replacing a precise internal result/union type with `object` and assuming a
  runtime `else: raise TypeError` fully replaces static checking
- Letting Pydantic coercion hide config or file-format bugs
- Creating internal logic that depends on raw HTTP, JSON, TOML, or CLI payload shapes
- Eagerly importing optional heavy runtime dependencies from simple CLI paths
