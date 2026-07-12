---
name: cli-contract-boundaries
description: Use for Frame Compare commands, Typer options, streams, exit codes, JSON mode, help text, config persistence flags, or CLI contract tests.
---

# CLI Contract Boundaries

Read the current CLI contract and affected command/tests. Command names, options,
exit codes, stream placement, JSON shape, help, and documented persistence are public.
Keep command functions thin and lazy-loaded.

JSON stdout must contain JSON only; diagnostics belong on stderr. Translate expected
validation/runtime failures through the typed error contract without tracebacks.
Update the CLI contract and focused tests in the same pass. Use `CliRunner`, separate
stdout/stderr assertions, isolated filesystems, and stable semantic help fragments.

Run focused CLI/config proof and the runbook's full public-contract gate.
