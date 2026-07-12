---
name: python-quality-boundaries
description: Use for Frame Compare Python production code, strict typing, Pydantic, HTTPX, Typer/Rich, error handling, or typed internal seams.
---

# Python Quality Boundaries

Keep strict typing useful: model real states explicitly, narrow at boundaries, and
avoid `Any`, broad casts, untyped dictionaries, and catch-all exceptions. Pydantic
schemas validate external/config input; internal owners should receive typed values.

Keep Typer/Rich wiring thin and machine stdout clean. HTTPX clients need explicit
timeouts, bounded error translation, and redaction. Preserve lazy imports on simple
CLI paths. Do not add generic helpers or DTO layers without a real ownership seam.

Run focused tests, Pyright, Ruff, Bandit, and import-linter when dependency direction
changes, using the runbook's risk tier.
