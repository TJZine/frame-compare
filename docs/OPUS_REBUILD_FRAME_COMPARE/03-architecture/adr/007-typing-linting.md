# ADR-007: Typing, Linting, and Formatting Standards

## Status

Accepted

## Date

2025-12-16

## Context

Frame Compare 2.0 is a ground-up rebuild intended to be:

- AI-agent implementable with minimal ambiguity
- Highly maintainable over time
- Safe (especially around subprocess and filesystem operations)

The v0.0.14 baseline accumulated drift between configuration, CLI, and runtime behavior. A stricter static-analysis baseline reduces these classes of regressions early, before they reach end users.

## Decision

Adopt the following defaults across the v2 codebase:

1. **Type checking:** Pyright in **strict** mode for `src/frame_compare/`
2. **Linting:** Ruff for import/order and correctness rules
3. **Formatting:** Ruff formatter (or an equivalent single formatter), with line length 100
4. **Public API contracts:** No `Any` in public surfaces; prefer `Protocol`, `TypedDict`, and explicit unions

## Rationale

- **Pyright strict** catches optional/union misuse, incorrect async boundaries, and signature drift early.
- **Ruff** provides fast, deterministic linting and import sorting, reducing style-based churn.
- **Single formatter** prevents tool conflicts and stabilizes diffs for human + agent workflows.
- **No `Any` in public APIs** keeps contracts explicit and supports downstream tooling/IDE completion.

## Consequences

### Positive

- Higher confidence refactors (especially around CLI/config precedence)
- Better IDE/autocomplete and fewer runtime surprises
- Cleaner review diffs and fewer stylistic PR comments

### Negative

- Higher up-front effort for typing edge cases (notably around JSON-like payloads)
- Some third-party packages may require stubs or localized `Protocol` wrappers

## Notes

- Internal JSON-like payloads should use a structured alias (e.g., `JSONValue`) instead of `Any`.
- Type checking should be enforced in CI as a hard gate.

