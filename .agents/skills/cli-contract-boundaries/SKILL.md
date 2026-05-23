---
name: cli-contract-boundaries
description: Use when changing Frame Compare CLI commands, Typer options, stdout/stderr behavior, exit codes, JSON mode, help text, config persistence flags, or CLI contract tests.
---

# CLI Contract Boundaries

## Overview

Use this skill to keep Frame Compare's Typer CLI stable, testable, and contract-driven.

The CLI is the primary product surface.

## Research Basis

This skill is based on official Typer, Click, and Rich documentation plus Frame Compare's current CLI contract doc and tests.

## Use This Skill For

- New, removed, or renamed commands/subcommands
- New, removed, renamed, or reinterpreted options/arguments
- Changes to stdout, stderr, human summaries, JSON payloads, or help text
- Exit-code and error-mapping changes
- `--write-config`, config override, preset, wizard, or path-resolution behavior
- Report auto-open and TTY-gated post-run behavior

## Required Reading

1. [`docs/current-cli-contract.md`](../../../docs/current-cli-contract.md)
2. [`docs/ENGINEERING_RUNBOOK.md`](../../../docs/ENGINEERING_RUNBOOK.md)
3. [`src/frame_compare/cli/entry.py`](../../../src/frame_compare/cli/entry.py)
4. [`src/frame_compare/config/overrides.py`](../../../src/frame_compare/config/overrides.py) when flags map to config
5. Existing tests in `tests/cli/`, `tests/config/`, `tests/e2e/`, and [`tests/test_cli_contract_docs.py`](../../../tests/test_cli_contract_docs.py)

## Core Rules

- Treat command names, option names, arguments, exit codes, stdout/stderr placement, JSON shape, help text, and documented persistence behavior as public contracts.
- Keep Typer command functions thin: parse CLI input, call typed owners, translate failures, and report output.
- Preserve lazy runtime imports for simple commands such as help/version.
- Use explicit `typer.Option` or `typer.Argument` names when compatibility matters; do not rely on accidental snake_case-to-kebab-case conversion for public compatibility changes.
- Use `typer.Exit(code=...)` or the repo's typed error mapping for controlled termination.
- Keep machine-readable stdout clean. In JSON mode, stdout must be parseable JSON only; diagnostics, progress, and warnings belong on stderr.
- Use Rich for human display, not for machine JSON contracts.
- Preserve report auto-open ownership in CLI code; report generation belongs to report services.

## Contract Test Matrix

For CLI changes, update focused tests for the affected contract:

- success path: `exit_code == 0`, expected stdout, and expected stderr
- usage/error path: expected nonzero exit code and diagnostic stream
- help path: `--help` exits `0` and includes stable semantic fragments
- JSON mode: `json.loads(result.stdout)`, stable keys/schema, no human text in stdout
- option compatibility: canonical long option, documented aliases, and deprecated options if still supported
- persistence path: `--write-config`, presets, relative paths, and runtime-only flags when touched
- docs lockstep: update `docs/current-cli-contract.md` and `tests/test_cli_contract_docs.py` when public behavior changes

## Testing Rules

- Prefer `typer.testing.CliRunner` for command behavior.
- Use `result.stdout` and `result.stderr` when stream placement matters. Avoid `result.output` for machine-contract assertions because recent Click versions mix stdout and stderr there.
- If full help rendering is contractual, fix terminal width and color behavior; otherwise assert stable semantic fragments.
- Use isolated filesystems or pytest temp paths for commands that touch CWD or generated files.
- Do not run concurrent `CliRunner` invocations; Click's runner mutates interpreter state.

## Verification

- Run focused CLI/config tests for the changed contract.
- Run full verification for public CLI/config changes:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

## Common Mistakes

- Adding human text to JSON stdout
- Testing `result.output` when stdout/stderr separation is the contract
- Changing an option name without updating docs and contract tests
- Treating help text as incidental when users rely on it
- Letting CLI command bodies absorb runtime or config policy owned elsewhere
