---
search:
  exclude: true
---

# TODO

> Non-authoritative backlog. These items are candidates, not approved plans or
> current product contracts. Update or remove an item when its work is completed,
> rejected, or promoted into an active plan.

- Bundle a permissively-licensed font (OFL) and pin overlay font selection for deterministic appearance + golden-image tests.
- Consider adding a dedicated packaging/release workflow skill if Python packaging, Docker, Windows portable, or updater/signing work becomes frequent.

---

## CLI Output Follow-Ups

### Optional Phase Section Headers

**Context**: Current interactive progress now uses concise product phase labels
inside the Rich progress task. It does not emit durable section headers around
phase boundaries.

**What**: If users still need more visible workflow landmarks after the progress
label pass, evaluate lightweight phase section headers around runtime progress
without duplicating the existing progress task labels.

**Risk**: Touches orchestration hotspot files (`execution.py`, `coordinator.py`)
and user-visible CLI output. Requires a focused plan and full verification.

### Post-Probe Clip Metadata Summary

**Context**: The legacy project shows per-clip metadata (resolution, fps, frame
count, duration timecode) in a `[DISCOVER]` section.

**What**: Surface clip probe data (resolution, fps, frames, duration) through
`RunResult` or a post-probe callback and render it as a styled clip table.

**Config gating**: Should be gated behind `--verbose` or a config flag (e.g.
`diagnostics.show_clip_metadata`).

**Risk**: Same as the frame plan breakdown — requires expanding `RunResult` and
the orchestration data flow.
