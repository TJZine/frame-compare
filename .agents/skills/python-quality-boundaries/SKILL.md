---
name: python-quality-boundaries
description: Use for Frame Compare Python production code, strict typing, Pydantic, HTTPX, Typer/Rich, error handling, or typed internal seams.
---

# Python Quality Boundaries

Keep production states and owner seams explicit:

- narrow untrusted config, JSON, HTTP, subprocess, and runtime metadata at the
  boundary; do not pass `Any`, broad dictionaries, or raw payloads inward;
- model distinct outcomes with focused dataclasses, enums, unions, or Pydantic
  schemas rather than casts, sentinel strings, or boolean flag clusters;
- preserve exception causes while mapping expected failures to typed, sanitized,
  user-actionable errors; do not catch `Exception` without an owner-specific reason;
- use Pydantic for external/config validation and typed Python objects internally;
- give clients, files, subprocesses, temporary artifacts, and runtime handles one
  explicit lifetime and cleanup path;
- keep Typer/Rich wiring thin, JSON stdout machine-clean, and simple CLI paths free
  of eager heavy-runtime imports;
- require explicit HTTP/subprocess timeouts, bounded retries only for transient
  operations, redaction, and deterministic partial-failure behavior;
- prefer an existing owner over a generic helper, DTO layer, compatibility adapter,
  or speculative protocol.

Stop when correct typing requires a new ownership or public-contract decision. Run
focused behavior proof, Pyright, Ruff, Bandit, and import-linter when dependency
direction changes, plus the runbook-required gate.
