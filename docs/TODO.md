# TODO

- Bundle a permissively-licensed font (OFL) and pin overlay font selection for deterministic appearance + golden-image tests.
- Consider adding a dedicated packaging/release workflow skill if Python packaging, Docker, Windows portable, or updater/signing work becomes frequent.

---

## CLI Output Enhancements (follow-ups from CLI styling redesign)

### Phase-Badge Headers Around Runtime Progress

**Context**: The legacy project renders colored phase badges (`[DISCOVER]`,
`[PREPARE]`, `[ANALYZE]`, `[RENDER]`, `[PUBLISH]`) around each orchestration
phase, giving the user clear visual context for what the pipeline is currently
doing.

**What**: Add styled phase-badge section headers (e.g. `[bold cyan][ANALYZE][/]`,
`[bold bright_magenta][RENDER][/]`) emitted by the orchestration layer around
phase progress output.

**Risk**: Touches orchestration hotspot files (`execution.py`, `coordinator.py`).
Requires a formal plan with full verification. The rendering helpers already
exist in `cli/output.py` after the styling redesign — the work is wiring the
orchestration phases to emit them.

**Depends on**: CLI styling redesign (completed).

### Frame Selection Plan Breakdown in Post-Analysis Summary

**Context**: The legacy project shows `Dark=N Bright=N Motion=N Random=N User=N`
after analysis completes — the actual breakdown of how many frames were selected
in each category.

**What**: Surface `SelectionBreakdown` data from the analysis phase through
`RunResult` (or a post-analysis callback) and render it as a styled summary line
in the CLI output.

**Config gating**: Should be gated behind `--verbose` or a config flag (e.g.
`diagnostics.show_analysis_breakdown`) so the default output stays clean.

**Risk**: Requires adding a field to `RunResult` (frozen dataclass in
`orchestration/types.py`) and wiring it through `execution.py`. Medium risk —
not a behavioral change, but touches the orchestration data flow.

**Depends on**: CLI styling redesign (completed).

### Post-Probe Clip Metadata Summary

**Context**: The legacy project shows per-clip metadata (resolution, fps, frame
count, duration timecode) in a `[DISCOVER]` section.

**What**: Surface clip probe data (resolution, fps, frames, duration) through
`RunResult` or a post-probe callback and render it as a styled clip table.

**Config gating**: Should be gated behind `--verbose` or a config flag (e.g.
`diagnostics.show_clip_metadata`).

**Risk**: Same as the frame plan breakdown — requires expanding `RunResult` and
the orchestration data flow.

**Depends on**: CLI styling redesign (completed), phase-badge headers (optional
but related).
