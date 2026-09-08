---
name: cli-contract-boundaries
description: Use for Frame Compare commands, Typer options, streams, exit codes, JSON mode, help text, config persistence flags, or CLI contract tests.
---

# CLI Contract Boundaries

Read the relevant current CLI contract sections and affected command/tests;
expand to adjacent contracts when behavior or callers remain unclear. Command
names, options, exit codes, stream placement, JSON shape, help, and documented
persistence are public.
Keep command functions thin and lazy-loaded.

JSON stdout must contain JSON only; diagnostics belong on stderr. Translate expected
validation/runtime failures through the typed error contract without tracebacks.
Update the CLI contract when documented behavior changes, and add focused tests
where existing coverage is insufficient. Use `CliRunner`, separate
stdout/stderr assertions, isolated filesystems, and stable semantic help fragments.

Run focused CLI/config proof and the runbook's full gate for changed public behavior;
apply its nonbehavioral exception when appropriate and reuse still-current results.
