---
name: repo-production-review
description: Frame Compare wrapper for the global repo-production-review suite. Use for read-only production code-health reviews of this repo with local workflow, boundary, verification, and release-surface constraints.
---

# repo-production-review

Thin Frame Compare wrapper for the global `repo-production-review` skill suite.

## Local Required Reads

Before running the universal review, read and honor:

- `AGENTS.md`
- `docs/ENGINEERING_RUNBOOK.md`
- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- `importlinter.ini`
- `pyproject.toml`
- `.codex/skills/*/SKILL.md`

Also open and follow the global orchestrator at:

- `${CODEX_HOME:-$HOME/.codex}/skills/repo-production-review/SKILL.md`

## Local Review Boundary

The review remains read-only:

- no product-code changes
- no test changes
- no dependency or lockfile changes
- no config changes
- no docs changes unless explicitly approved as a planning artifact
- no implementation work

## Local Focus Areas

Calibrate findings against Frame Compare's real surfaces:

- CLI/config/JSON behavior and exit codes
- filesystem persistence and generated artifacts
- import-layer boundaries
- FFmpeg/ffprobe, VapourSynth, TMDB, slow.pics, browser-open, Docker, and Windows portable/release behavior
- packaging and installer/update paths
- tests, static checks, and runtime verification gates

## Invocation Behavior

Run the global `repo-production-review` orchestrator. Use installed global specialist skills when available.

The final report must separate confirmed defects, inferred risks, subjective maintainability concerns, and insufficient-data items. Every material finding must include evidence, risk mechanism, severity, confidence, suggested verification, and remediation direction.

## Verification For Wrapper Changes

For changes to this wrapper or related workflow docs, run the runbook-required verification tier before calling the work complete.
