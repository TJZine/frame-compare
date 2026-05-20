---
name: verification-strategy
description: Use when a Frame Compare task needs an explicit verification mode and proof surface without defaulting every change to fail-first tests or brittle snapshots.
---

# Verification Strategy

## Overview

Use this skill to choose the smallest verification mode that proves the change safely.

Verification is mandatory. Fail-first testing is not.

## Use This Skill For

- Planning work where verification must be locked before implementation
- Refactors, workflow changes, docs authority changes, or boundary work
- Deciding whether to add a test, rely on existing coverage, run integration gates, or record a documented-only runtime gap

## Verification Modes

- `regression-first`: concrete bug with a stable reproduction; usually needs a targeted regression test.
- `contract-first`: CLI, config, JSON, generated output, import-layer, packaging, or public behavior contract risk.
- `refactor-invariance`: structure changes while behavior should remain unchanged; start from existing tests and static checks.
- `integration-ops`: correctness lives across runtime/tooling layers such as Docker, FFmpeg, VapourSynth, Windows packaging, or workflow control plane.
- `manual-runtime`: proof requires a platform, generated artifact inspection, browser open behavior, or Windows host.
- `spike`: bounded exploration where the output is learning, not a durable behavior guarantee.

## Required Output

Before implementation or plan freeze, state:

- primary verification mode
- plan classification:
  - `new regression/contract test required`
  - `existing coverage sufficient`
  - `broader integration/manual proof required`
  - `no new automated test needed`
- exact commands and/or manual proof
- expected outcomes
- why that depth matches the risk
- why new tests are or are not needed

## Command Routing

Use [`docs/ENGINEERING_RUNBOOK.md`](../../../docs/ENGINEERING_RUNBOOK.md) first.

Full verification:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Docker/runtime verification:

```bash
bash tools/verify_docker_integration.sh
```

## Guardrails Against Brittle Tests

- Test public seams, not helper internals that are expected to move.
- Prefer narrow CLI/config/output assertions over giant snapshots.
- Do not mock owned boundaries just to make a unit test easy.
- If a runtime or release-path proof cannot run locally, say exactly what was not verified.

## Common Mistakes

- Treating docs/workflow changes as no-verification changes
- Adding a test that only restates the implementation
- Claiming Windows or Docker paths are verified when they were only read
- Using full verification as a substitute for a targeted root-cause proof
