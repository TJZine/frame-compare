---
name: report-output-patterns
description: Use when changing generated HTML reports, screenshot output, overlay text, CLI summaries, JSON output, or other user-visible Frame Compare output surfaces.
---

# Report Output Patterns

## Overview

Use this skill to keep user-visible output stable, inspectable, and owned by the right layer.

Frame Compare is CLI-first, so CLI text, JSON payloads, generated reports, screenshot naming, and overlay labels are product surfaces.

## Required Reading

1. [`docs/ENGINEERING_RUNBOOK.md`](../../../docs/ENGINEERING_RUNBOOK.md)
2. [`docs/current-cli-contract.md`](../../../docs/current-cli-contract.md) for CLI and JSON behavior
3. [`docs/current-architecture.md`](../../../docs/current-architecture.md) for output owners
4. Tests near the touched owner, especially CLI, render, orchestration, and report tests

## Output Owner Categories

Confirm file-level ownership in `docs/current-architecture.md`; the entries below
identify stable responsibility categories rather than a second owner map.

- CLI command routing, human summaries, JSON modes, and browser auto-open: [`src/frame_compare/cli/entry.py`](../../../src/frame_compare/cli/entry.py)
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
- Use focused assertions for output contracts; avoid broad snapshots unless the whole output is the contract.

## Verification

- Run CLI/report/render tests that cover the changed output.
- Run full verification for public CLI/config contract changes, generated report contract changes, or hotspot output owners.
- Update `docs/current-cli-contract.md` when command output, JSON schema, or report auto-open rules change.

## Common Mistakes

- Treating "just copy" as non-contractual when it appears in CLI or generated reports
- Moving browser/report behavior out of the CLI owner
- Adding dynamic ordering that makes reports or JSON hard to diff
- Locking an entire large report snapshot when a small semantic assertion would catch the regression
