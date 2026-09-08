---
name: report-output-patterns
description: Protect Frame Compare generated report payloads, viewer assets, screenshot naming, overlays, and presentation formatting. Use cli-contract-boundaries for command options, streams, exit codes, and CLI JSON contracts.
---

# Report Output Patterns

## Overview

Use this skill to keep user-visible output stable, inspectable, and owned by the right layer.

Frame Compare is CLI-first, so CLI text, JSON payloads, generated reports, screenshot naming, and overlay labels are product surfaces.

## Required Reading

Read the relevant sections and affected owners first. Expand to callers, adjacent
contracts, or full documents when material questions remain. Reuse task context.

1. [`docs/ENGINEERING_RUNBOOK.md`](../../../docs/ENGINEERING_RUNBOOK.md)
2. [`docs/current-cli-contract.md`](../../../docs/current-cli-contract.md) for CLI and JSON behavior
3. [`docs/current-architecture.md`](../../../docs/current-architecture.md) for output owners
4. Tests near the touched owner, especially CLI, render, orchestration, and report tests

## Output Owner Categories

Confirm file-level ownership in `docs/current-architecture.md`; the entries below
identify stable responsibility categories rather than a second owner map.

- CLI registration and dependency wiring: `cli/entry.py`; run presentation and browser
  precedence: `cli/run_command.py`; explicit history opening: `cli/history_command.py`
- CLI formatting helpers: [`src/frame_compare/cli/output.py`](../../../src/frame_compare/cli/output.py)
- HTML report generation: [`src/frame_compare/services/report/`](../../../src/frame_compare/services/report/)
- Screenshot naming and render outputs: [`src/frame_compare/render/`](../../../src/frame_compare/render/)
- Overlay text composition: [`src/frame_compare/render/overlay_text.py`](../../../src/frame_compare/render/overlay_text.py)
- Progress display: [`src/frame_compare/orchestration/progress.py`](../../../src/frame_compare/orchestration/progress.py) and [`src/frame_compare/utils/progress.py`](../../../src/frame_compare/utils/progress.py)

## Core Rules

- Keep JSON output machine-stable. Add or remove keys only with contract tests and doc updates.
- Keep human summaries concise and deterministic.
- Do not mix HTML report generation with orchestration policy.
- Do not let render/overlay modules decide CLI behavior.
- Preserve stable ordering and deterministic filenames.
- Keep report auto-open behavior in CLI ownership.
- Preserve report-owned payload validation and escaped HTML/embedded JSON. Reuse
  the existing viewer assets and state owners; report placement remains an explicit
  caller-supplied path. Consult persistence guidance only when write/path semantics change.
- Use focused assertions for output contracts; avoid broad snapshots unless the whole output is the contract.

## Verification

- Run CLI/report/render tests that cover the changed output.
- For viewer state, reuse `tests/services/node_harness.py` and nearby harnesses.
  Browser behavior uses the runbook's Report Viewer Verification route; Node or
  markup assertions alone do not prove layout, focus, or browser initialization.
- Run full verification for public CLI/config contract changes, generated report contract changes, or behavior changes in hotspot output owners; apply the runbook's nonbehavioral exception when appropriate.
- Update the authority describing the changed contract: the CLI contract for CLI
  output/JSON or auto-open rules, and the architecture's Report Viewer section for
  documented viewer/payload behavior. Presentation-only edits do not automatically
  require CLI documentation changes.

## Common Mistakes

- Treating "just copy" as non-contractual when it appears in CLI or generated reports
- Moving browser/report behavior out of the CLI owner
- Adding dynamic ordering that makes reports or JSON hard to diff
- Locking an entire large report snapshot when a small semantic assertion would catch the regression
