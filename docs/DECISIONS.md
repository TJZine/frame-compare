# Historical Decisions

This log retains product or workflow decisions whose rationale remains useful but
does not belong in a present-state authority document. Current workflow authority
lives in [Engineering Runbook](ENGINEERING_RUNBOOK.md), current architecture in
[Current Architecture](current-architecture.md), and public CLI/config behavior in
[Current CLI Contract](current-cli-contract.md).

Completed implementation transcripts, verification counts, superseded phase plans,
and removed workflow assets are intentionally left to Git history.

## 2026-04-15 — Consolidate Authority Surfaces

**Context:** Active documentation had drifted into overlapping runbooks,
architecture summaries, tool-specific entrypoints, and stale workflow references.

**Decision:** Use `docs/ENGINEERING_RUNBOOK.md` as the single operating runbook and
`docs/current-architecture.md` as the single present-state architecture authority.
Keep `AGENTS.md`, `CODEX.md`, and tool-specific rules as thin routing shims rather
than parallel policy surfaces.

**Rationale:** A small authority map reduces workflow drift and makes conflicts
resolvable through explicit precedence.

## 2026-02-07 — Distinguish Tonemap Policy From Dependency Discovery

**Context:** FFmpeg-only screenshot paths used `VapourSynthNotFoundError (FC-2001)`
when HDR input required the VapourSynth tonemap path, conflating a rendering-policy
failure with dependency discovery.

**Decision:** Use `TonemapRequiresVapourSynthError (FC-2009)` for FFmpeg-only
HDR+tonemap gating. Preserve dependency-category exit mapping and keep automatic
renderer fallback behavior unchanged.

**Rationale:** Operator diagnostics should identify the policy constraint without
misreporting how the runtime dependency was discovered.

## 2026-02-17 — Remove Legacy Environment Aliases

**Context:** Configuration loading and doctor diagnostics accepted both canonical
and legacy environment-variable names for TMDB and logging.

**Decision:** Require canonical nested names only:

- `FRAME_COMPARE_TMDB__API_KEY` replaces `TMDB_API_KEY`.
- `FRAME_COMPARE_LOGGING__LEVEL` replaces `FRAME_COMPARE_LOG_LEVEL`.

**Rationale:** One configuration path avoids hidden precedence and keeps runtime and
doctor behavior explicit.

## 2026-07-14 — Defer Presentation-Blind Reports

**Context:** The generated report was evaluated for a presentation-blind comparison
mode.

**Decision:** Do not add or advertise a viewer-only blind mode. Ordinary report
artifacts can expose source identity through baked screenshot overlays, physical
image filenames or URLs, metadata, and initial presentation. The current payload
also has no trustworthy eligibility fact proving that an artifact is clean.

Reconsider the feature only as a separately approved clean-artifact workflow with
explicit eligibility/versioning, neutral naming and delivery, first-paint behavior,
reveal semantics, review-state transfer, and publishing rules. The claim must remain
limited to presentation blindness; it must not imply adversarial or storage-level
secrecy.

**Rationale:** Product language must not promise a guarantee that the underlying
generated files cannot support.
