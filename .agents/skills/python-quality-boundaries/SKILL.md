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
- use Pydantic v2 validators, `ConfigDict`/`SettingsConfigDict`, and
  `model_validate` for external/config validation; do not add v1 compatibility
  shims, and pass typed Python objects inward;
- for TMDB/publishing, accept the shared `httpx.AsyncClient`; the coordinator creates
  and closes a default client only when none is injected. Preserve caller-owned
  clients, short-lived diagnostic clients, and the webhook's isolated pinned HTTPS
  transport. Classify expected statuses before decoding payloads;
- give clients, files, subprocesses, temporary artifacts, and runtime handles one
  explicit lifetime and cleanup path;
- keep Typer/Rich wiring thin, JSON stdout machine-clean, and simple CLI paths free
  of eager heavy-runtime imports;
- require explicit HTTP/subprocess timeouts, bounded retries only for transient
  operations, redaction, and deterministic partial-failure behavior;
- prefer an existing owner over a generic helper, DTO layer, compatibility adapter,
  or speculative protocol.

Resolve typing and ownership from current contracts and source. Escalate only a
consequential decision outside the authorized scope that remains unresolved.
Use the runbook's behavior-matched verification, including import-linter when import
boundaries change; reuse still-current results. Consult `python-test-design` when
test changes need guidance beyond the existing coverage and task context.
