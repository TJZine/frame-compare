---
name: runtime-integration-boundaries
description: Use when changing FFmpeg, ffprobe, VapourSynth, TMDB, slow.pics, Docker, browser-opening, or Windows portable/release integration logic in Frame Compare.
---

# Runtime Integration Boundaries

## Overview

Use this skill to keep external runtime integrations explicit and testable.

The main anti-pattern is mixing subprocess, HTTP, VapourSynth, browser, packaging, and domain policy in one workflow.

## Required Reading

1. [`docs/ENGINEERING_RUNBOOK.md`](../../../docs/ENGINEERING_RUNBOOK.md)
2. [`docs/current-architecture.md`](../../../docs/current-architecture.md)
3. [`docs/current-cli-contract.md`](../../../docs/current-cli-contract.md) when CLI output or exit behavior changes
4. Relevant tests under `tests/integration`, `tests/vs`, `tests/render`, `tests/services`, or `tests/utils`

## Relevant Owners

- FFmpeg and subprocess mechanics: [`src/frame_compare/utils/subproc.py`](../../../src/frame_compare/utils/subproc.py), orchestration preflight/probe modules, and render pipeline owners
- VapourSynth source, color, tonemap, and loader logic: [`src/frame_compare/vs/`](../../../src/frame_compare/vs/)
- Render orchestration and overlays: [`src/frame_compare/render/`](../../../src/frame_compare/render/)
- TMDB metadata: [`src/frame_compare/services/metadata.py`](../../../src/frame_compare/services/metadata.py)
- slow.pics publishing: [`src/frame_compare/services/publishers.py`](../../../src/frame_compare/services/publishers.py)
- Browser auto-open: [`src/frame_compare/cli/entry.py`](../../../src/frame_compare/cli/entry.py)
- Docker runtime: [`Dockerfile`](../../../Dockerfile), [`docker-compose.yml`](../../../docker-compose.yml), [`tools/verify_docker_integration.sh`](../../../tools/verify_docker_integration.sh)
- Windows portable and updater flow: [`tools/windows_portable/`](../../../tools/windows_portable/)

## Boundary Routing

- If the change reshapes module ownership or hotspots, also load `architecture-boundaries`.
- If generated artifacts, report HTML, screenshot naming, or overlay text are involved, also load `report-output-patterns`.
- If config or path persistence changes, also load `persistence-boundaries`.

## Core Rules

- Keep subprocess command construction, execution, error mapping, and redaction in explicit owners.
- Keep network integrations behind services that can be tested with mocked HTTP boundaries.
- Keep VapourSynth-heavy imports lazy where the CLI contract depends on fast/light commands.
- Do not let orchestration callers build raw external command strings or HTTP payload policy when an owner exists.
- Keep secrets, tokens, credentials, private key paths, and sensitive URLs out of user-facing errors.
- Preserve copy/paste-friendly filesystem paths, commands, report paths, and diagnostic details when the CLI contract, tests, or troubleshooting workflow expects them.
- Preserve Docker and Windows portable flows as first-class surfaces, not optional afterthoughts.
- If local OS/runtime cannot execute a release-path proof, report it as documented-only instead of claiming full verification.

## Verification

- Run focused tests for the touched owner first.
- Run full verification for orchestration, render, VS, services, CLI/config contract, Docker/runtime, or Windows release-path changes.
- Run `bash tools/verify_docker_integration.sh` for Docker/runtime surfaces when locally available.
- For Windows portable/release changes, follow the runbook's Windows verification path on a compatible host or record the documented-only gap.

## Common Mistakes

- Hiding external tool failures behind generic errors
- Eagerly importing VS code into simple CLI paths
- Treating HTTP or subprocess behavior as untestable
- Updating docs without keeping the CI/local command path aligned
- Adding fallback behavior that changes public CLI semantics without contract updates
