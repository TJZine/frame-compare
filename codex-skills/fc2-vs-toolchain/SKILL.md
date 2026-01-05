---
name: fc2-vs-toolchain
description: Use when working on VapourSynth-related code (vs module, plugin detection, tonemapping, vs_required tests) to keep optional-dependency behavior and test skipping correct.
---

# FC-2.0 VapourSynth Toolchain Skill

## Goals

- Optional dependency behavior is explicit (tests skip, errors are typed).
- No accidental requirement for VS in Tier-A or default unit tests.

## References

- Module specs: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
- Workflow (read first): `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md`
- Full workflow SSOT: `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`

## Checklist

- Mark VS-required tests with the agreed marker and ensure they skip cleanly when VS is unavailable.
- Avoid importing VS at module import time in code paths that should be runnable without VS.
