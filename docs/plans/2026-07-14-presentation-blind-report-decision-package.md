Status: Historical — Unit 11 deferred / accepted 2026-07-14
Scope: Follow-up decision package for an honest presentation-blind report artifact
Owner: Frame Compare maintainer; no active implementation owner

# Presentation-blind report follow-up decision package

## Outcome

Product/UX Unit 11 is deferred. The current generated report cannot offer the
approved presentation-blind claim through viewer-only changes. The maintainer
accepted this reviewed deferral on 2026-07-14.

This document preserves the evidence, the recommended future direction, the
decisions that require explicit approval, and the proof/rollback contract for a
future package. It is not an active implementation plan and does not authorize a
config, CLI, render, payload, report-format, or slow.pics change.

The active product/UX program remains
[`2026-07-13-product-ux-execution-program.md`](2026-07-13-product-ux-execution-program.md).

## Approved blind claim

The only permitted claim is **presentation blindness**. Before explicit reveal,
source identity must not be inferable through ordinary visual UI, accessibility
APIs, focus/keyboard order, restored visible state, baked image overlays, report
metadata, inspector/review/export UI, slow.pics surfaces, reference styling, or
ordinary browser open/save/copy-image behavior.

Developer tools, View Source, raw localStorage, and raw downloaded bytes remain
outside that claim. The feature must never be described as adversarial, secure, or
storage-level blindness.

## Feasibility evidence

### Blocking artifact facts

1. Screenshot overlays default to `standard` in
   [`config/defaults.py`](../../src/frame_compare/config/defaults.py) and
   [`config/schema_models.py`](../../src/frame_compare/config/schema_models.py).
2. The render request carries the physical source filename stem as
   `filename_label` in
   [`orchestration/phase_tasks.py`](../../src/frame_compare/orchestration/phase_tasks.py).
3. [`render/batch/expansion.py`](../../src/frame_compare/render/batch/expansion.py)
   promotes that value to `burn_in_label`.
4. [`render/overlay_text.py`](../../src/frame_compare/render/overlay_text.py) includes
   the label in Minimal, Standard, and Diagnostic overlays; only `none` omits it.
5. [`render/overlay.py`](../../src/frame_compare/render/overlay.py) draws the text
   into the raster. Viewer JavaScript and CSS cannot remove those pixels.
6. Screenshot files use `{frame} - {source stem}.png` in
   [`render/naming.py`](../../src/frame_compare/render/naming.py).
7. Reports default to non-embedded images. The relative filename or cross-drive
   `file:` URI becomes the image source in
   [`services/report/payload.py`](../../src/frame_compare/services/report/payload.py).
   Ordinary open/save/copy-image behavior can expose it.
8. Neither `ReportData` nor payload version `1.0` carries a trustworthy clean-artifact
   eligibility fact. A viewer cannot distinguish a clean overlay-free report from a
   default identity-bearing report and therefore cannot fail closed honestly.

### Reviewed outcome

A bounded feasibility worker and a separate fresh read-only adversarial reviewer
independently returned `STOP_REQUIRED`. The controller verified their cited render,
naming, payload, and default-config paths. Reviewer findings U11-R001 through
U11-R003 are accepted:

- **U11-R001:** default screenshots irreversibly expose source identity in pixels;
- **U11-R002:** ordinary image open/save behavior exposes source-stem filenames;
- **U11-R003:** the report has no trustworthy clean-artifact eligibility fact.

Viewer-owned labels, ARIA text, focus order, reference cues, inspector fields,
restored ordinals, review transfer controls, and slow.pics visibility are extensive
but mechanically addressable after the artifact contract is approved. They do not
remove the three blockers above.

## Recommended future direction

Prefer a **separate blind-report artifact** over mutating ordinary reports or
silently changing existing screenshot behavior.

The recommended shape is:

- ordinary reports and labeled screenshots remain behavior-compatible;
- an explicit, default-off public request produces a separate blind report;
- the blind report consumes clean overlay-free images delivered under neutral
  browser-visible names or another browser-proven neutral source mechanism;
- generation stamps a versioned, fail-closed eligibility contract that old reports
  do not possess;
- the first rendered document is identity-neutral before viewer initialization;
- one memory-only cryptographic Fisher–Yates mapping owns visual, DOM, focus,
  accessibility, keyboard, vote, and preferred-clip presentation order;
- reveal is explicit, irreversible for the session, and stored separately from vote;
- slow.pics, identity metadata, preferred-clip labels, and review transfer remain
  hidden or disabled until reveal.

This direction best contains compatibility risk, but it is a recommendation rather
than an approved public or architecture contract.

## Decisions required before activation

A future maintainer approval must freeze all of the following together:

1. **Invocation:** persisted report config, CLI option, separate command, or another
   explicit generation-time request. Viewer-only opt-in is not eligible.
2. **Artifact policy:** clean canonical screenshots, dual clean/labeled artifacts,
   or a verified-clean restriction. Define storage and performance budgets.
3. **Neutral delivery:** neutral physical filenames, embedded images, additional
   blind source fields, or a separate report format. Prove ordinary open/save/copy
   behavior and local `file:` operation.
4. **Eligibility/versioning:** where the clean-artifact fact is owned, payload/report
   version changes, and fail-closed behavior for old or unknown reports.
5. **Output ownership:** whether blind artifacts coexist in `RenderArtifacts`, how
   run folders name and retain them, and how rollback cleans or ignores them.
6. **First paint:** how identity-bearing static header, selectors, Info content,
   filmstrip alt text, and metadata are absent before JavaScript runs.
7. **Publishing:** whether slow.pics receives ordinary or clean artifacts and which
   surfaces remain unavailable before reveal.
8. **Review behavior:** how stored source ordinals map to anonymous presentation,
   and how Review V1 import/export stays unavailable until reveal without changing
   its exact shipped schema accidentally.
9. **Compatibility:** behavior of existing ordinary reports, existing review state,
   older payload versions, and non-blind run outputs.

Activation stops if any item remains implicit.

## Ownership map for the future package

Likely owners, subject to the approved contract:

- public config/defaults: `src/frame_compare/config/schema_models.py` and
  `src/frame_compare/config/defaults.py`;
- CLI surface only if invocation is CLI-owned: `src/frame_compare/cli/` and
  `docs/current-cli-contract.md`;
- artifact routing: `src/frame_compare/orchestration/phase_tasks.py`, execution DTOs,
  and `phase_post_render.py`;
- screenshot rendering/naming: `src/frame_compare/render/batch/`, `render/naming.py`,
  and overlay/encoder owners;
- report eligibility/payload/markup: `src/frame_compare/services/report/`;
- neutral viewer state: a focused new report-asset owner composed by `viewer.js`;
- slow.pics only if the approved contract changes publication inputs.

Do not add a generic anonymity layer, parallel report generator, duplicate clip-state
representation, or compatibility shim. The approved owner map must keep one fact and
one lifecycle owner for eligibility, artifact identity, presentation mapping, vote,
and reveal.

## Future execution packages

After the decisions above are approved, write a new active execution plan with these
ordered units:

1. **Contract gate:** integrate the approved invocation, artifact, eligibility,
   versioning, publishing, compatibility, and first-paint specification.
2. **Clean artifact production:** implement bounded neutral artifacts through the
   existing render/orchestration owners with deterministic containment and cleanup.
3. **Blind report bootstrap:** produce an identity-neutral initial document and
   fail closed when eligibility is absent or invalid.
4. **Presentation mapping:** implement the memory-only cryptographic permutation,
   neutral labels/order, vote/reveal state, and all Grid/Pixel/Review integrations.
5. **Adversarial proof:** exercise every visible/accessibility/error/restoration and
   ordinary browser filename channel before final independent review.

Each unit receives one bounded worker, controller-owned proof, and the program's
independent review/adjudication discipline. No unit proceeds past a newly discovered
public or architecture decision.

## Verification contract

The future implementation requires:

- behavior-first tests for both FFmpeg and VapourSynth screenshot paths producing
  clean, neutrally delivered artifacts;
- naming, containment, partial-failure cleanup, and old-report fail-closed tests;
- deterministic Fisher–Yates tests through an injected cryptographic-byte seam,
  including unbiased rejection sampling and no payload/report-ID derivation;
- automated pre-reveal DOM/accessibility/focus scans across all modes, inspector
  tabs, errors, restored viewport/review state, and 2/3/4/6 clips;
- review vote/reveal ordering, irreversible reveal, session reset, and transfer-gate
  tests;
- first-paint and ordinary open/save/copy-image browser proof;
- the canonical full repository gate;
- `bash tools/verify_docker_integration.sh` whenever render/VS output semantics are
  changed;
- the active program's complete in-app-browser matrix, including 8K, portrait,
  ultrawide, keyboard-only, coarse pointer, reduced motion, and 200% zoom.

Unavailable platform proof must be recorded as unverified, never inferred.

## Privacy, failure, and rollback

- Never place source names, paths, labels, report IDs, or deterministic payload-order
  labels into a pre-reveal browser-visible artifact name or accessible surface.
- Eligibility validation fails before blind UI activation. Unknown/old reports remain
  ordinary reports and do not display a misleading Blind control.
- Partial blind-artifact generation must not damage ordinary screenshots or reports.
- Rollback removes blind routing/UI and ignores or removes only the separately owned
  blind artifacts. Ordinary reports, report payload `1.0`, viewport state, and Review
  V1 data remain readable.
- Reveal/mapping state is never persisted. Vote remains distinct from reveal.

## Reevaluation trigger

Reevaluate Unit 11 only after the maintainer approves one complete contract covering
all nine decisions above and authorizes a new active execution plan with render/runtime
proof where required. Until then, the accepted deferral is the production-correct
outcome and no interface may claim Blind A/B.
