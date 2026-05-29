Status: Active
Scope: Restore screenshot overlay and report-viewer output parity for the approved legacy-gap remediation set
Owner: Next Codex cleanup-loop session

# Overlay and Report Cleanup Plan

## Purpose

This is a durable execution plan for the next session that will use
`frame-compare-cleanup-loop` to remediate the approved screenshot-overlay and
report-viewer gaps identified in the 2026-05-29 head-to-head audit against the
legacy repo.

This plan is intentionally execution-grade. It freezes scope, owner seams,
invariants, verification, and stop-and-replan triggers without prescribing
unnecessary local implementation detail.

## Task Family and Risk Tier

- Task family: cleanup/refactor/remediation of user-visible generated outputs
- Runbook tier: High

Why high risk:

- The work changes generated screenshot overlays, which are a user-visible output
  surface.
- The work changes the local HTML report viewer under `services/report/**`, a
  current hotspot in `docs/current-architecture.md`.
- The work may require threading richer per-frame metadata across analysis,
  orchestration, render, and report seams.

## Historical References

These are reference-only and must not override current repo authority:

- `docs/archive/legacy_overlay_and_cli_reference.md`
- `docs/archive/legacy_html_viewer.md`
- `../frame-compare-legacy/src/frame_compare/render/overlay.py`
- `../frame-compare-legacy/src/frame_compare/screenshot/render.py`
- `../frame-compare-legacy/src/frame_compare/report.py`
- `../frame-compare-legacy/src/data/report/*`

Use them to confirm legacy behavior, not to import legacy structure wholesale.

## Approved Scope

Address all approved `add` and `maybe` recommendations from the 2026-05-29
overlay/report audit.

### Approved `add` work

1. Restore filename-backed screenshot overlay identity instead of burning only
   `Reference` / `Encode N`.
2. Restore real picture-type behavior instead of the current always-`N/A`
   outcome when frame props are unavailable to the current path.
3. Restore richer legacy-grade diagnostic overlay behavior using available HDR,
   Dolby Vision, range, and selection metadata.
4. Restore selection-detail-driven overlay labels so screenshot overlays can
   represent more than the reduced dark/bright/motion/random breakdown.
5. Fix report-viewer displayed-encode pill placement for overlay/blink
   presentation.
6. Fix font/glyph handling so resolution text renders correctly and does not
   degrade into missing-glyph boxes.

### Approved `maybe` work

7. Resolve the dormant screenshot overlay position surface. If the field is
   required for the approved overlay placement behavior, wire it through with
   tests. If it is not required, remove or narrow the dead surface so the repo
   does not keep a misleading unused API.

## Explicit Non-Goals

Do not let this turn into a general feature umbrella.

Out of scope unless a stop-and-replan trigger is hit and approved:

- new CLI flags
- new persistent config knobs
- full legacy HTML viewer reimplementation
- unrelated CLI/dashboard cleanup
- slow.pics publishing changes
- Windows portable or release-path changes
- import-layer expansion beyond what this plan names
- reviving the legacy ASS/drawtext split as an architectural goal

## Current Known Gaps To Remediate

The next session should treat these as confirmed starting-state findings unless
 the code changes before implementation begins:

1. Screenshot overlay identity uses `ClipState.label`, which is populated as
   `Reference` / `Encode N`, while the output filename already uses the source
   stem. This is why the burn-in overlay says `Encode 1` instead of the
   filename.
2. `OverlayConfig.picture_type` exists but is never populated, so the current
   overlay composer falls back to `N/A`.
3. The current diagnostic screenshot overlay only receives a coarse `hdr_info`
   string and ignores the richer probe-time preserved props and HDR metadata the
   repo already caches.
4. The current render path derives selection labels only from
   `SelectionBreakdown`, which cannot represent the richer legacy categories and
   selection provenance.
5. The current report viewer anchors the displayed-encode overlay label at the
   top-left and writes the active encode name into the left-side label.
6. The current overlay font fallback uses Pillow's default font path, which can
   miss the multiplication sign glyph and render a boxed substitute.
7. `OverlayConfig.position` and `render.geometry.calculate_overlay_position()`
   exist but are not used by the actual Pillow overlay renderer.

## Owner Seams

Prefer changes inside existing owners. Do not invent a new top-level boundary
for this work.

Primary owners in scope:

- analysis selection metadata:
  - `src/frame_compare/analysis/types.py`
  - `src/frame_compare/analysis/selection.py`
- orchestration handoff and probe metadata consumption:
  - `src/frame_compare/orchestration/context.py`
  - `src/frame_compare/orchestration/preparation.py`
  - `src/frame_compare/orchestration/phase_tasks.py`
  - `src/frame_compare/orchestration/execution.py` only if required for a typed
    handoff
- render output DTOs and overlay composition:
  - `src/frame_compare/render/types.py`
  - `src/frame_compare/render/overlay_text.py`
  - `src/frame_compare/render/overlay.py`
  - `src/frame_compare/render/prepare.py`
  - `src/frame_compare/render/encoders.py`
  - `src/frame_compare/render/batch/expansion.py`
  - `src/frame_compare/render/geometry.py` only if position wiring/removal is
    needed
- report payload and viewer chrome:
  - `src/frame_compare/services/report/payload.py`
  - `src/frame_compare/services/report/renderer.py`
  - `src/frame_compare/services/report/assets/viewer.js`
  - `src/frame_compare/services/report/assets/viewer.css`

Secondary owners only if required by an approved unit:

- `src/frame_compare/vs/source.py`
- `src/frame_compare/vs/props.py`
- `src/frame_compare/render/backend/ffmpeg.py`

## Files Out of Scope By Default

- `src/frame_compare/cli/entry.py`
- `src/frame_compare/cli/output.py`
- `tools/windows_portable/**`
- `.github/workflows/**`
- slow.pics publishing owners
- unrelated docs outside same-pass authority updates required by the runbook

## Required Invariants

The implementation must preserve these invariants unless the maintainer
explicitly changes them:

1. Keep human clip labels (`Reference`, `Encode N`) available for CLI/report
   surfaces that intentionally use them. Do not repurpose global clip labels to
   solve filename burn-in.
2. Keep screenshot output filenames stable unless a correctness fix forces a
   documented change.
3. Preserve aligned vs source frame semantics:
   - output filenames continue to use the aligned/display frame number
   - extraction/rendering continues to use the source frame number
   - overlay display frame number must remain aligned to the filename domain
4. Do not add a new public CLI/config contract unless there is no safe internal
   path. If a new knob becomes unavoidable, stop and re-plan first.
5. Keep report-viewer chrome separate from screenshot burn-in identity.
6. Prefer typed internal seams over raw dict plumbing when carrying new overlay
   metadata across orchestration and render owners.
7. Do not degrade FFmpeg-only runs with an expensive or unstable metadata path
   just to emulate legacy text literally.
8. Do not reintroduce dead or misleading fields. Any retained overlay surface
   must be exercised by real runtime code and tests.

## Approved Behavioral Decisions

These decisions are frozen for implementation unless a stop-and-replan trigger
fires.

### Screenshot overlay identity

- Screenshot burn-in identity must be able to use the source filename stem or a
  dedicated filename label, independently of the human clip label used
  elsewhere.
- The current `Reference` / `Encode N` labels remain valid for report and CLI
  surfaces unless a local viewer surface explicitly needs a different label.

### Picture type behavior

- The preferred outcome is legacy-grade picture-type display when the active
  render path has access to frame props.
- If the active path cannot produce picture type reliably and cheaply, the
  approved fallback is to omit the picture-type line rather than render a
  misleading `N/A`.
- Do not add a speculative heavyweight probe path for picture type without
  review.

### Selection detail behavior

- The overlay path must recover richer selection detail than the current
  `SelectionBreakdown` allows.
- The approved direction is to thread typed per-frame selection detail through
  the analyze-to-render seam rather than inferring everything from a reduced
  breakdown.
- Preserve the existing reduced breakdown if other owners still need it; do not
  force unrelated consumers to migrate in the same pass unless necessary.

### Diagnostic overlay behavior

- Reuse existing probe-time `preserved_frame_props` and `hdr_metadata` where
  possible instead of adding a second metadata cache or parallel ad hoc prop
  persistence path.
- The overlay text should regain the legacy-grade detail level for MDL, HDR,
  Dolby Vision, dynamic range, and per-frame nits when those facts are
  available.
- Avoid giant string-builder duplication. Keep composition logic inside the
  render overlay owner.

### Report-viewer pill behavior

- The report-viewer displayed-encode pill for overlay/blink presentation should
  move to top-right.
- Do not destabilize split-mode left/right semantics just to move the
  overlay/blink pill. The preferred change is narrowly scoped to the overlay and
  blink presentation path unless review finds a broader cleanup is lower risk.

### Font behavior

- The approved fix is deterministic glyph coverage, not replacing the
  multiplication sign with a plain ASCII `x`.
- Prefer an explicit font selection path that can render the existing text
  contract correctly.

### Overlay position surface

- Do not leave `OverlayConfig.position` as a dead knob.
- Approved outcomes:
  - wire it through to the actual overlay renderer with tests, or
  - remove/narrow it if the surface is not needed by the approved behavior

## Execution Units

Implement one approved unit at a time. Review after each unit or after each
paired unit if the reviewer agrees.

### Unit 1: Split screenshot identity from human clip label

Target:

- Reuse the existing filename-identity seam where possible so screenshot
  burn-in can use filename identity without breaking report/CLI labels.
- Only add a dedicated overlay-only identity field if the existing
  `filename_label` path cannot preserve human labels for other intended
  surfaces.

Must prove:

- output filename remains stable
- overlay display frame number remains correct
- screenshot overlay no longer burns `Encode N` where filename identity is
  required

### Unit 2: Restore typed selection detail handoff

Target:

- Replace or supplement the reduced overlay selection source with typed
  per-frame selection detail suitable for screenshot overlays and report payload
  needs.
- Keep analysis, orchestration, and render boundaries clean by letting
  orchestration translate analysis detail into render/report-local DTOs instead
  of making render import analysis selection types directly.

Must prove:

- trimmed/aligned frame mapping still resolves labels in the correct source-frame
  domain
- richer categories and provenance can reach the overlay path

### Unit 3: Restore picture-type behavior

Target:

- Populate picture type where available and remove misleading fallback behavior
  where it is not.

Must prove:

- VS-backed overlay path renders real picture type when frame props exist
- unsupported paths do not regress into incorrect text

### Unit 4: Restore legacy-grade diagnostic overlay detail

Target:

- Compose screenshot diagnostic text from real preserved HDR/range/DoVi facts
  plus per-frame selection metrics where enabled.

Must prove:

- existing probe-time preserved metadata is consumed rather than duplicated
- standard vs diagnostic ordering stays deterministic
- no output contract regressions in aligned frame numbering or screenshot naming

### Unit 5: Fix report-viewer displayed-encode pill placement

Target:

- Move the overlay/blink displayed-encode indicator to top-right and keep viewer
  semantics cleanly separated from screenshot burn-in identity.

Must prove:

- slider and diff modes retain sensible left/right labeling
- overlay/blink use the corrected pill placement

### Unit 6: Fix font coverage and resolve dormant position surface

Target:

- Make overlay typography deterministic enough to avoid boxed glyphs.
- Resolve the unused `position` surface by wiring it or deleting/narrowing it.

Must prove:

- resolution text renders with the intended multiplication sign under the chosen
  font path
- the final API surface has no dead overlay-position knob

## Verification Strategy

Primary verification mode:

- `contract-first` for generated screenshot/report output behavior

Required plan classification:

- `new regression/contract test required`
- `broader integration/manual proof required`

Why this depth matches the risk:

- The changed surfaces are user-visible generated artifacts.
- Static typing and unit coverage alone are insufficient for overlay/report
  correctness.
- The work spans hotspot report/viewer files and render/output owners.

### Required automated coverage

At minimum, extend or add focused tests around:

- `tests/render/test_overlay_text_composer.py`
- `tests/render/test_overlay.py`
- `tests/render/test_expansion.py`
- `tests/render/test_encoders.py`
- `tests/render/test_geometry.py`
- `tests/orchestration/test_overlay_frame_number.py`
- `tests/orchestration/test_overlay_selection_label_domain.py`
- `tests/orchestration/test_preparation.py`
- `tests/services/test_report_renderer.py`
- `tests/services/test_report.py`
- `tests/services/test_report_entry.py`

If richer selection detail affects the analysis contract, add focused analysis or
orchestration regression coverage instead of broad snapshots.

### Required commands

Focused proof during implementation:

```bash
.venv/bin/pytest -q tests/render/test_overlay_text_composer.py tests/render/test_overlay.py tests/render/test_expansion.py tests/render/test_encoders.py tests/render/test_geometry.py tests/orchestration/test_overlay_frame_number.py tests/orchestration/test_overlay_selection_label_domain.py tests/orchestration/test_preparation.py tests/services/test_report_renderer.py tests/services/test_report.py tests/services/test_report_entry.py
```

Runbook full verification before closeout:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Runbook Docker/runtime verification for this workstream's render/vs owner
changes:

```bash
bash tools/verify_docker_integration.sh
```

If the Docker/runtime gate cannot run locally, record that exact gap as
documented-only and do not claim the render/runtime proof passed.

### Required manual/runtime proof

If the environment can generate screenshots and a report locally, produce a
small sample run and inspect:

- screenshot overlay filename identity
- picture type line behavior
- selection type label correctness
- HDR/DoVi/range diagnostic lines
- report overlay/blink pill placement
- multiplication sign glyph rendering

If local runtime proof cannot run in the current environment, record the exact
gap and do not claim that manual proof passed.

## Review Requirements

The next session must follow the cleanup-loop controller workflow:

1. Load this plan.
2. Use `frame-compare-cleanup-plan` only to validate or tighten the plan if the
   repo changed.
3. Request `frame-compare-cleanup-review` on the plan before implementation.
4. Implement one bounded unit with `frame-compare-cleanup-implement`.
5. Review the implementation.
6. Use `review-adjudication` for findings.
7. Repeat until scope closes.
8. Use `closeout-verification` before any completion claim.

## Stop-And-Replan Triggers

Stop and re-plan before coding further if any of these occur:

1. The clean owner seam for richer selection detail is not local to existing
   analysis/orchestration/render owners.
2. A new CLI flag or persistent config knob appears necessary.
3. The report payload needs schema changes that are broader than local viewer
   needs.
4. Picture-type fidelity on FFmpeg-only paths would require a materially slower
   or unstable metadata strategy.
5. The work implicitly changes output filename contracts.
6. Import-layer changes outside current owners become necessary.
7. A doc/code mismatch appears intentional and risky instead of stale.
8. Existing `ClipProbeSnapshot.hdr_metadata` /
   `ClipProbeSnapshot.preserved_frame_props` are insufficient and the work would
   require changing `generated/clip_probe.toml` schema or adding a new overlay
   metadata sidecar.
9. Deterministic glyph coverage would require bundling a font asset or other
   release-path/platform packaging work outside the approved render-owner scope.

## Same-Pass Documentation Rules

Update active authority docs only if their owned surfaces are actually changed:

- `docs/current-cli-contract.md` only if CLI/config/public command behavior or
  report auto-open behavior changes
- `docs/current-architecture.md` only if owner seams, runtime phase ownership,
  or persistence ownership change materially

Do not promote the archived legacy docs into current authority.

## Bootstrap Reminder

If `.venv` is missing, bootstrap with:

```bash
uv sync --group dev --frozen
```

## Suggested Session Start Prompt

Use this in the next session:

```text
Use [$frame-compare-cleanup-loop](C:\Software\video\frame-compare\.agents\skills\frame-compare-cleanup-loop\SKILL.md).

Load and follow the active tracked plan at docs/plans/2026-05-29-overlay-legacy-parity-cleanup.md.

Task: implement the full approved scope in that plan, not just a partial audit. Treat it as high-risk generated-output remediation. Follow the cleanup-loop controller workflow exactly:
1. Keep live state in update_plan.
2. Validate/load the active plan with frame-compare-cleanup-plan.
3. Run frame-compare-cleanup-review on the plan before implementation.
4. Implement one bounded unit at a time with frame-compare-cleanup-implement.
5. Review each unit, adjudicate findings, and continue until the active plan scope closes or a stop-and-replan trigger fires.
6. Use closeout-verification before claiming completion.

Constraints:
- Follow AGENTS.md and docs/ENGINEERING_RUNBOOK.md.
- Preserve public CLI/config behavior unless the plan explicitly authorizes a change.
- Do not introduce compatibility shims, dead config, or speculative abstractions.
- Keep changes inside existing owner modules where possible.
- Use typed seams instead of raw dict plumbing when carrying new overlay metadata.
- Do not leave the overlay position surface half-live.
- Run the plan's focused tests during implementation and full verification before closeout.
- If local runtime proof for screenshot/report output cannot be produced, state the exact gap and do not claim it passed.
```
