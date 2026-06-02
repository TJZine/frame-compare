Status: Historical
Scope: Restore production-grade N-source behavior and legacy functional parity for source selection, alignment, VSPreview, render geometry/crops, report viewing, and slow.pics publishing
Owner: Next Codex cleanup-loop implementation session

# N-Source Legacy Parity Plan

## Purpose

Frame Compare must support more than two clips as a first-class product mode.
The practical target is 3-10 sources, while preserving a design that does not
impose an artificial upper bound beyond runtime/resource constraints.

This plan converts the N-source audit into an implementation-grade handoff. It
is intentionally active because the work crosses high-risk owners:
orchestration, config, alignment, VSPreview, render geometry, generated reports,
slow.pics publishing, and public CLI/config docs.

The goal is functional parity with the legacy repo where legacy behavior was
valuable, while keeping the rebuilt app's current architecture, import layers,
typed DTOs, run-folder behavior, report ownership, slow.pics upload-plan seam,
and CLI-first contract intact.

## Workflow Entry

Use `frame-compare-cleanup-loop` as the controller because the maintainer
explicitly requested that workflow and because this is high-risk remediation.
Do not use the loop as a vague feature umbrella. Execute bounded units and
review each unit before moving to the next.

Controller sequence:

1. Load `AGENTS.md`, `docs/ENGINEERING_RUNBOOK.md`,
   `docs/current-architecture.md`, `docs/current-cli-contract.md`,
   `importlinter.ini`, this active plan, and matching boundary skills.
2. Keep authoritative live state in `update_plan`.
3. Run adversarial plan review before code changes.
4. Adjudicate plan-review findings with `review-adjudication`.
5. Implement one approved unit at a time.
6. Review that unit's diff before starting the next unit.
7. Adjudicate implementation-review findings.
8. Repeat until scope closes or a stop-and-replan trigger fires.
9. Use `closeout-verification` before calling the work done.

Because this is partly net-new feature parity, a session may use
`frame-compare-feature-plan`, `frame-compare-feature-review`, and
`frame-compare-feature-implement` inside the cleanup-loop slots when those
skills better match the implementation slice. The cleanup-loop remains the
controller and review cadence.

Initial review packet for the next session:

```text
REVIEW_REQUEST
TASK: N-source legacy functional parity
TASK_FAMILY: high-risk feature/remediation across orchestration, runtime, render, report, and config
RISK_TIER: high
REVIEW_TARGET: active tracked plan
PLAN_OR_ARTIFACT: docs/plans/2026-06-02-n-source-legacy-parity-plan.md
LEGACY_REFERENCE_ROOT: /Users/tristan/Software/frame-compare-legacy
CURRENT_ROOT: /Users/tristan/Software/frame-compare
PRIMARY_QUESTIONS:
- Does this plan preserve current CLI/config contracts where it says it does?
- Are the proposed owner seams aligned with docs/current-architecture.md and importlinter.ini?
- Are public config changes justified and documented with enough tests?
- Are N-source acceptance criteria complete across prep, alignment, VSPreview, render, report, and slow.pics?
- Are runtime/manual proof gaps called out honestly?
```

## Pre-Handoff Review Adjudication

This plan was reviewed before delivery. The reviewer found five material
issues; all are accepted and incorporated:

- Analysis cache identity must be reference-aware because metrics are computed
  for the selected reference frame domain and the current cache key is
  order-independent.
- Failed-comparison alignment policy must be frozen before implementation, not
  left for an implementer to invent.
- Source trim overrides must compose with alignment trims and must not be
  overwritten by alignment normalization.
- Effective FPS override parity must be either explicitly out of scope or fully
  planned. This plan keeps it in scope as Unit 2B with exact semantics.
- Source identity and alignment persistence must not conflict. Duplicate stems
  remain unsupported and fail early until alignment cache/manual overrides move
  to versioned stable source-identity keys.

## Task Family And Risk Tier

- Task family: high-risk feature/remediation with public config and runtime
  behavior.
- Runbook tier: High.

Why high risk:

- The work touches `src/frame_compare/orchestration/**`, a current hotspot.
- The work changes `src/frame_compare/services/alignment.py` and
  `alignment_vspreview.py`, current hotspots and runtime integration owners.
- The work changes generated report behavior under
  `src/frame_compare/services/report/**`, a current hotspot and user-visible
  output surface.
- The work changes render geometry/crop behavior under `src/frame_compare/render/**`,
  which requires full verification and Docker/runtime consideration under the
  runbook.
- Any source-reference or per-source override config is a public config
  contract and requires docs and config tests in the same pass.
- Correctness depends on stable source-frame semantics across audio alignment,
  manual VSPreview confirmation, trim normalization, render frame mapping,
  report payloads, and slow.pics upload ordering.

## Current Evidence To Preserve

Current rebuilt app facts:

- Input discovery returns all matching videos and sorts them deterministically.
  Current reference selection is implicit: first sorted input is the reference.
- `RunContext` already carries `reference: ClipState` and
  `comparisons: list[ClipState]`.
- Render, report, and slow.pics phases mostly build from
  `[ctx.reference, *ctx.comparisons]`.
- `align_clips()` accepts a list of comparisons and returns results in the same
  order.
- `calculate_alignment_trims()` accepts all comparison offsets, but
  `run_align_phase()` currently discards every valid alignment if any comparison
  returns `applied = false`.
- VSPreview generated sessions can include more than one comparison, but prompt
  confirmation is all-or-nothing and `skip` discards the whole confirmation
  session.
- Aligned render geometry accepts a sequence of sources, but automatic
  dimension-derived active rects only handle same-height/different-width or
  same-width/different-height cases. Mixed width and height differences fall
  back to full-frame unless metadata supplies a valid active rect.
- Report payloads and viewer clip selectors are plural, but report-viewer manual
  visual alignment is one global offset, not scoped per pair.
- slow.pics upload planning already builds row-major rows over every clip and
  has a 3-clip plan-order test. Publisher multipart coverage must still be
  widened beyond two columns.

Legacy parity facts from `/Users/tristan/Software/frame-compare-legacy`:

- More than two clips was a real supported flow, not a two-clip special case.
- Legacy alignment was reference-vs-each-comparison.
- Legacy config exposed an optional alignment reference selector.
- Legacy supported per-source trim/FPS overrides keyed by source identity.
- Legacy alignment normalized all desired trims by shifting the whole set so the
  minimum desired trim became zero. This preserved relative offsets while
  avoiding negative trims/padding. In practical terms, the source that would
  have needed the most "advance" becomes the zero-trim baseline, and every
  other source is trimmed forward to the shared content start.
- Legacy render/report/publish flows preserved deterministic source ordering.
- Legacy geometry handled explicit crop/mode planning, letterbox/pillarbox
  awareness, padding, and writer-specific crop/scale/pad sequencing.

## Approved Scope

Implement production-grade N-source behavior across all current app features:

1. Source discovery, ordering, reference selection, labels, identities, and
   configurable per-source overrides.
2. Audio alignment and trim normalization for one reference plus N comparisons.
3. VSPreview manual alignment verification for N comparisons.
4. Screenshot render frame mapping and aligned geometry/crop planning for N
   sources.
5. HTML report payload and viewer behavior for N clips.
6. slow.pics upload planning and publisher metadata/image upload behavior for N
   clips.
7. Tests and manual/runtime proof that exercise at least 3 and 4 source cases,
   with a path to 10-source confidence.
8. Same-pass authority doc updates for public config/CLI/report behavior changes.

## Explicit Non-Goals

Out of scope unless plan review or implementation evidence forces a
stop-and-replan:

- Supporting mixed source FPS without explicit user override.
- Changing `run --json` success schema.
- Adding new `run` flags for N-source features.
- Changing report-confirmed slow.pics upload phase ordering.
- Replacing the slow.pics browser-compatible upload protocol.
- Making a live mutating slow.pics integration test part of the default suite.
- Rewriting the report viewer into an all-clips grid/compositor mode. Pair-based
  comparison modes may remain pair-based as long as pair selection, state, and
  persistence are correct for N clips.
- Implementing aggressive pixel black-bar detection without a separate
  maintainer-approved design. Deterministic active-rect config/metadata support
  is in scope; heuristic pixel detection is a later optional feature.
- Changing Windows portable packaging unless public config defaults, docs, or
  generated config templates require a release-path update.

## Product Decisions To Freeze Before Implementation

Plan review must confirm or revise these decisions before code changes:

1. N-source default behavior remains backward-compatible:
   - if no explicit reference is configured, first discovered clip remains the
     reference;
   - comparisons preserve deterministic discovery order after the reference is
     moved to the front;
   - default report pair is clip 0 vs clip 1.
2. Add explicit reference selection as public config. Preferred shape:
   add a `[sources]` config section rather than `audio_alignment.reference`,
   because reference selection affects analysis metadata, alignment, render,
   report, and slow.pics, not only audio.
   Recommended public shape:

   ```toml
   [sources]
   reference = "00-reference.mkv" # optional selector; null/omitted keeps first discovered clip

   [sources.overrides."encode-a.mkv"]
   trim_start_frames = 0
   trim_end_frames = 0
   active_rect = { x = 240, y = 0, width = 1440, height = 1080 }
   # effective_fps = "24000/1001" # Unit 2B; AssumeFPS-style timing override
   ```

   `sources.reference` and `sources.overrides` keys are source selectors, not
   labels. Matching and ambiguity rules below apply to both.
3. Reference selector matching should be deterministic and fail loudly on
   ambiguity:
   - exact relative path from input dir;
   - exact filename;
   - exact stem;
   - selectors are case-sensitive config strings, not filesystem paths to
     resolve from the process cwd;
   - relative path selectors are input-dir-relative POSIX-style strings on all
     platforms;
   - backslashes in selectors are normalized to `/` before matching so Windows
     path separators work in config;
   - absolute POSIX paths, Windows drive paths, UNC paths, empty selectors, and
     selectors containing `.` or `..` path segments are invalid and fail before
     matching;
   - explicit numeric index is not recommended for the first implementation
     because it is fragile when discovery patterns or filenames change. If the
     maintainer still wants index selectors for legacy familiarity, stop and
     document whether indexes are zero- or one-based before implementation.
4. Add per-source override support only through a typed source/config owner.
   Required public fields for the initial implementation:
   - `trim_start_frames`: non-negative count of source frames to drop from the
     beginning;
   - `trim_end_frames`: non-negative count of source frames to drop from the end;
   - `active_rect`: optional `{x, y, width, height}` source-frame active image
     rectangle used by aligned geometry.
   Explicit config `active_rect` values are public config input and must fail
   with typed config/input errors when malformed, non-positive, negative,
   outside the probed source dimensions, or otherwise unsafe. Runtime-derived
   active rect candidates from metadata or dimensions may fall back with
   warnings when invalid.
   Effective FPS override is legacy-relevant and is in scope as a separate
   required unit. Add it as `effective_fps = "num/den"` only after the trim and
   active-rect override seam exists, and implement the full semantics in Unit
   2B. Do not add a half-wired FPS override.
5. Active image/crop overrides should have deterministic precedence:
   - explicit source override wins;
   - trusted per-frame metadata, such as a single consistent Dolby Vision L5
     active rect, comes next;
   - conservative dimension-derived rect comes next;
   - full-frame fallback last.
6. Pairwise alignment is the target behavior:
   - one failed comparison must not discard valid alignments for other
     comparisons;
   - failed comparisons stay in the output by default, but remain marked
     `alignment = None`;
   - trim/common-domain math uses accepted offsets plus an explicit zero-offset
     fallback for unresolved comparisons only to keep a single renderable frame
     domain across all clips;
   - warnings must clearly say that each unresolved comparison is rendered in a
     best-effort reference-frame domain and was not audio/manual aligned;
   - all clips remain included in render, report, and slow.pics membership by
     default if their selected source frames are renderable after base trims and
     common-domain normalization;
   - unresolved comparisons keep their normal clip labels, but report/frame
     metadata or run warnings must expose that the clip is unaligned; do not
     rename clips in a way that breaks slow.pics/report ordering;
   - if an unresolved comparison cannot render every selected frame after base
     trims and common-domain normalization, fail the run with a typed
     user-visible error. Omitting failed clips requires a separate
     maintainer-approved product decision;
   - do not silently pretend failed comparisons are aligned, and do not drop
     failed clips without a separate maintainer-approved product decision.
7. Report-viewer manual visual alignment must be scoped per comparison pair.
   A visual offset tuned for one pair must not leak into another pair.
8. VSPreview confirmation must allow per-comparison skip. Confirmed offsets
   already entered must remain usable and persisted.
9. Source-frame semantics remain unchanged:
   `frame_offset = reference_source_frame - comparison_source_frame`.
   Users must not be required to calculate global normalized trims. For
   VSPreview/manual alignment, users provide matching source-frame pairs for
   each comparison. Frame Compare computes pairwise offsets, then performs the
   global trim normalization.
10. slow.pics row/image ordering remains row-major by selected frame, then clip
    order: reference first, then comparisons in deterministic order.
11. Analysis cache identity must be reference-aware. Analysis metrics are for
    the selected reference clip's frame domain, so a cache created with one
    reference must not satisfy a later run that selects a different reference
    from the same input set.
12. Source trims and alignment trims must compose. Configured source trims
    establish each clip's base renderable domain; alignment normalization
    composes on top of that base domain and must never erase configured trims.
    Alignment normalization must preserve the legacy no-negative-trim rule:
    build a desired trim map in the base-trim domain, subtract the minimum
    desired trim from every clip, and apply the resulting non-negative
    alignment trim additions. In the rebuilt source-frame offset convention,
    this is equivalent to:
    - desired trim for reference: `0`;
    - desired trim for each comparison: `-frame_offset`;
    - `shift = -min(desired_trims)` when the minimum is negative, otherwise `0`;
    - final alignment addition for each clip: `desired_trim + shift`.
    The current rebuilt formula `baseline = max(0, max(offsets))` and
    `comparison_trim = baseline - offset` is the same normalization for a
    reference-vs-comparison offset set. Preserve that behavior while adding
    base-trim composition and partial-failure handling.
13. Duplicate stems remain unsupported for the first implementation because
    current alignment cache/manual override keys are stem-based. Preparation
    must fail early with a typed user-visible error if any discovered source
    stems collide, including reference-vs-comparison and same-stem
    different-extension/path cases. Versioned source-identity alignment
    persistence is a future optional improvement, not part of this first
    parity implementation.
14. Effective FPS override parity is required, but it must be implemented as a
    separate reviewed unit with exact semantics:
    - `source_fps` remains the probed source FPS;
    - `effective_fps` is an AssumeFPS-style override that changes timing/FPS
      interpretation without interpolating, dropping, or duplicating source
      frames;
    - mixed-FPS validation compares effective FPS values after overrides;
    - without overrides, current mixed-FPS fail-fast behavior remains unchanged;
    - audio offset frame conversion uses the selected reference effective FPS;
    - render source-frame mapping remains frame-index based and does not
      resample frames;
    - FPS reports, report metadata, cache identity, and timecodes must
      distinguish source FPS from effective FPS where user-visible.

If plan review rejects any of these decisions, update this plan before
implementation.

## Owner Seams

Keep behavior in current owners. Do not create a new top-level package or relax
`importlinter.ini` unless a reviewed architecture decision explicitly requires it.

Likely primary owners:

- `src/frame_compare/config/schema_models.py`,
  `src/frame_compare/config/defaults.py`, and config tests:
  public config shape for source reference and per-source overrides.
- `src/frame_compare/orchestration/preparation.py`:
  discovery ordering, reference selection, labels, source identity resolution,
  and initial `ClipState` construction.
- `src/frame_compare/orchestration/context.py`:
  typed source override state only if `ClipState` must carry applied trims,
  effective FPS, or active image metadata.
- `src/frame_compare/orchestration/coordinator.py`:
  composition root handoff only; keep policy out of this file where possible.
- `src/frame_compare/orchestration/phase_tasks.py`:
  phase handoffs, alignment application, frame-domain mapping, render/report/
  slow.pics phase assembly.
- `src/frame_compare/services/alignment.py`:
  alignment result list policy, cache/manual/VSPreview precedence integration.
- `src/frame_compare/services/alignment_math.py`:
  pure trim/common-domain math, especially if pairwise partial alignment needs
  clearer testable helpers.
- `src/frame_compare/services/alignment_vspreview.py`:
  terminal prompt flow, per-comparison confirmation/skip, manual override save.
- `src/frame_compare/vspreview/session_script.py`:
  generated VSPreview output ordering, labels, and N-source display clarity.
- `src/frame_compare/render/geometry.py`:
  pure N-source geometry/crop/scale/pad planning.
- `src/frame_compare/render/batch/expansion.py`:
  attach per-source active rects and geometry plans to render requests.
- `src/frame_compare/services/report/payload.py`,
  `renderer.py`, and `assets/viewer.js`/`viewer.css`:
  report payload defaults, clip selector behavior, pair-scoped viewer state,
  and N-clip UX affordances.
- `src/frame_compare/services/slowpics_upload_plan.py` and
  `src/frame_compare/services/publishers.py`:
  N-column metadata and image upload contract.

Authority docs likely in scope:

- `docs/current-cli-contract.md` for public config/CLI behavior.
- `docs/current-architecture.md` if source overrides, active rect ownership, or
  N-source runtime ownership changes materially.
- `docs/api.md` only if generated API docs drift after implementation.

Files out of scope by default:

- `tools/windows_portable/**`, unless config template or release packaging is
  directly affected.
- `Dockerfile` and `docker-compose.yml`, unless render/VS runtime verification
  exposes an environment issue.
- `src/frame_compare/cli/entry.py`, unless a public CLI/config contract change
  needs help text, error mapping, `--write-config`, or JSON guard updates.
- broad rewrites of `src/frame_compare/services/report/assets/viewer.js`
  unrelated to N-clip state correctness.

## Implementation Units

### Unit 0: Plan Review And Parity Matrix

Required before code changes:

- Review this active plan adversarially.
- Confirm public config shape for source reference and per-source overrides.
- Confirm the pairwise alignment policy for failed comparisons.
- Confirm crop override precedence.
- Create or update an N-source parity matrix in the implementation notes or
  plan review output covering:
  - discovery/reference;
  - analysis frame domain;
  - alignment/manual overrides/cache;
  - VSPreview;
  - render geometry/crops;
  - report viewer;
  - slow.pics;
  - CLI/JSON/docs.

Stop if product policy is still ambiguous.

### Unit 1: Characterization Tests For Current N-Source Behavior

Add tests that document current support and expose gaps before behavior fixes.

Recommended tests:

- Prep/discovery test with four clips proving deterministic default reference
  and labels.
- Alignment phase regression showing one rejected comparison currently
  suppresses valid alignments. Mark the intended fixed behavior in the test
  once Unit 3 implements it.
- Render phase test with three clips and known trims proving aligned frames map
  to each clip's expected source frames.
- Report payload test with four clips proving clip count, image count, and
  default pair selection.
- Report viewer test or JS unit/browser test showing global manual alignment
  leakage across pairs before Unit 6 fixes it, if the existing test harness can
  express it without brittle DOM snapshots.
- slow.pics publisher test gap note or failing test for 4 columns if feasible.

Verification:

```bash
.venv/bin/pytest tests/orchestration tests/render tests/services -q
```

Expected result for this unit may include intentional failing tests only if the
implementation session is using regression-first development and will fix them
in the same bounded unit. Do not commit intentionally failing tests.

### Unit 2: Source Identity, Reference Selection, And Source Overrides

Implement a source-owned config seam for N-source identity and explicit
reference selection.

Recommended schema owner:

- Add `SourcesConfig` to `src/frame_compare/config/schema_models.py` and
  `ConfigSchema`.
- Add `SourceOverrideConfig` for per-source overrides.
- Add a small typed active-rect config model rather than passing raw dicts into
  render geometry.
- Keep defaults empty/backward-compatible:

  ```toml
  [sources]
  # reference = null
  # overrides default to empty; add per-source override tables as needed
  ```

  For user-editable TOML examples, prefer quoted nested tables:

  ```toml
  [sources.overrides."encode-a.mkv"]
  trim_start_frames = 12
  trim_end_frames = 0
  active_rect = { x = 240, y = 0, width = 1440, height = 1080 }
  # effective_fps = "24000/1001" # Unit 2B; AssumeFPS-style timing override
  ```

Required behavior:

- Preserve default first-discovered reference behavior when no reference
  selector is configured.
- If reference is configured, resolve it deterministically against discovered
  input files.
- Fail with a typed user-visible config/input error for missing or ambiguous
  reference selectors.
- Preserve deterministic comparison ordering after moving the selected
  reference to the front.
- Preserve stable labels:
  - selected reference label remains `Reference`;
  - comparisons remain `Encode 1`, `Encode 2`, etc. in post-reference order.
- Make analysis cache identity reference-aware. Either include the selected
  reference identity and source overrides that affect the reference frame or
  timing domain in the cache key/fingerprint. Do not rely on a validate-only
  cache payload check after an order-independent lookup. Multiple selected
  references from the same input set must be able to coexist as separate cache
  entries, and `--no-cache` must delete only the matching reference-aware cache
  entry.
- Resolve source override keys with the same deterministic selector rules as
  `sources.reference`.
- Fail with a typed user-visible config/input error when an override selector
  matches no source or more than one source.
- Apply `trim_start_frames` and `trim_end_frames` during `ClipState`
  construction or an immediately adjacent preparation owner as base source
  trims. Later alignment trims must compose with these base trims rather than
  replacing them.
- Fail early on duplicate stems across all discovered clips until alignment
  cache/manual override persistence is migrated to a versioned stable
  source-identity key.
- Do not implement `effective_fps` in this unit except for schema reservation
  if the implementation plan chooses that sequencing. The behavioral work is
  Unit 2B and must not be partially wired.

Tests:

- config defaults and TOML loading;
- reference by relative path/name/stem;
- reference selector normalization for POSIX-style and Windows-style
  separators;
- absolute, traversal, empty, and `.`/`..` selector rejection;
- ambiguous selector failure;
- missing selector failure;
- override by relative path/name/stem;
- override missing/ambiguous selector failure;
- trim start/end conversion to `ClipTrimState`;
- source trims are preserved when later alignment trims are applied;
- invalid active rect validation;
- duplicate stems fail during preparation, including same stem with different
  extension or nested path;
- analysis cache created with default first-reference does not satisfy a later
  explicit second-reference run;
- `--from-cache-only` fails/misses when the selected reference differs from the
  cached reference identity;
- `--no-cache` deletes only the matching reference-aware analysis cache entry;
- configured reference source trims constrain analysis/frame selection so
  trimmed-out source frames are never selected;
- default behavior unchanged;
- mixed-FPS behavior unchanged before Unit 2B;
- `--write-config`/default config drift if config persistence surfaces changed.

Docs:

- update `docs/current-cli-contract.md` for public config behavior;
- update `docs/current-architecture.md` if a new source override owner is added.

### Unit 2B: Effective FPS Override Parity

Restore legacy `change_fps`-style behavior through the reviewed
`sources.overrides.<selector>.effective_fps` field.

Required behavior:

- Parse `effective_fps` as a positive rational value, accepting canonical string
  forms such as `"24000/1001"` and rejecting malformed values with typed
  config errors.
- Preserve both `source_fps` and `effective_fps` on `ClipState`.
- Treat the override as AssumeFPS-style metadata/timing interpretation only.
  Do not resample, interpolate, drop, or duplicate frames.
- Mixed-FPS validation compares effective FPS after overrides. A run with raw
  mixed FPS still fails unless overrides make every clip's effective FPS match
  the selected reference effective FPS.
- Audio alignment frame conversion uses selected reference effective FPS when
  turning time/sample offsets into frame offsets.
- Analysis frame selection remains source-frame-index based. Timecodes and
  user-visible timing use effective FPS where that is already the app's
  effective timing domain.
- Analysis cache identity includes effective FPS overrides that affect selected
  reference timing/metadata.
- FPS reports continue to show source FPS and effective FPS divergence.
- Report clip metadata and overlay timecodes must use the same effective FPS
  contract consistently.

Tests:

- malformed `effective_fps` config values fail clearly;
- raw mixed FPS without overrides still fails as today;
- raw mixed FPS with effective-FPS overrides succeeds when all effective FPS
  values match;
- audio frame-offset conversion uses reference effective FPS;
- source-frame mapping does not resample frames;
- FPS report shows source-to-effective divergence;
- analysis cache misses/fails when effective FPS override changes the selected
  reference timing identity;
- report payload metadata reflects effective FPS consistently.

### Unit 3: Pairwise Alignment And Trim Common-Domain Policy

Fix the all-or-nothing alignment failure mode.

Required behavior:

- Valid applied alignment results must remain attached to their comparison even
  if another comparison is rejected.
- Warnings for rejected comparisons must remain visible and deterministic.
- Trim calculation must operate from accepted pairwise offsets plus explicit
  zero-offset fallback entries for unresolved comparisons. The fallback is for
  common-domain rendering only; it must not create a `ClipAlignmentState`.
- Alignment trim outputs must compose with configured base source trims. For
  example, if a source override drops 12 leading frames and alignment
  normalization adds 5 more, aligned frame 0 maps to source frame 17. Alignment
  must not overwrite the configured source trim.
- Alignment trim normalization must match legacy baseline-shift behavior:
  preserve relative offsets, choose the no-negative-trim global shift, and make
  the earliest/common baseline source require zero additional alignment trim.
  Do not change this into pair-local trimming that leaves different aligned
  frame-zero meanings per comparison.
- Selected frame normalization must not choose aligned frames outside any clip's
  effective renderable domain.
- `_map_aligned_to_source_frame()` must remain the final guard against out-of-
  range source frames.
- The fix must not change signed offset semantics.

Design guidance:

- Prefer extracting pure math from `phase_tasks.py` into
  `services.alignment_math` if the policy becomes hard to test in orchestration.
- Keep orchestration responsible for phase state transitions, not low-level
  offset math.
- Avoid letting the zero-offset fallback leak into cache, manual overrides,
  report metadata, or any user-facing state as if it were an accepted alignment.

Tests:

- three comparisons: two accepted offsets and one rejected result;
- accepted alignments remain on accepted comparisons;
- rejected comparison warning is preserved;
- rejected comparison has `alignment is None` after trim normalization;
- trim windows and selected frames are valid for all clips under the chosen
  policy;
- base source trims plus positive/negative accepted offsets compose correctly
  for at least three clips;
- multiple positive and negative offsets normalize like legacy:
  for offsets `[10, -5, 0]`, reference gets `10` added trim frames, comparisons
  get `[0, 15, 10]` added trim frames before base-trim composition;
- source-frame-pair manual input computes offsets first and then global
  normalization; tests must not require users to enter normalized trim values;
- unresolved comparison stays included in render/report/slow.pics membership
  when selected frames are renderable, with explicit warnings;
- source-frame mapping for positive, negative, and zero offsets;
- cache/manual/VSPreview precedence still works for multiple comparisons.

### Unit 4: VSPreview N-Source Manual Alignment

Make interactive alignment usable and safe for 3-10 comparisons.

Required behavior:

- Preserve generated-session source-frame semantics: untrimmed source clips and
  audio hints only.
- Preserve `offset = reference_source_frame - comparison_source_frame`.
- Preserve manual override persistence schema unless plan review explicitly
  approves a schema change.
- Preserve optional-vs-forced interactive behavior:
  - optional VSPreview degrades when unavailable;
  - forced interactive fails when unavailable or no TTY exists.
- Preserve input comparison order consistently between generated VSPreview
  output and terminal prompts. Do not sort one side differently from the other.
- Support per-comparison skip:
  - confirmed offsets already entered remain usable;
  - skipped comparison keys are omitted from confirmed offsets;
  - no terminal input keeps current offsets as before.
- Display enough output labels that a user can map VSPreview output slots to
  terminal prompts for 3-10 clips.

Tests:

- three comparisons with confirm/skip/confirm behavior;
- already-confirmed offsets are saved when a later comparison is skipped;
- generated script output order matches prompt order;
- script escaping remains safe;
- no-tty and forced-interactive behavior unchanged;
- optional unavailable behavior unchanged.

Manual proof:

- If VSPreview is available locally, run a non-mutating/generated-session smoke
  with three temporary clips and confirm output ordering.
- If GUI interaction is not performed, record it as a manual runtime gap in
  closeout.

### Unit 5: N-Source Render Geometry And Crop Parity

Restore legacy-quality crop/canvas behavior for N sources without unsafe
heuristics.

Required behavior:

- `plan_render_geometry()` must remain pure and accept one or more sources.
- Add or wire explicit per-source active rect/crop overrides according to the
  reviewed config shape.
- Active rect precedence:
  1. explicit source override;
  2. trusted metadata active rect, currently consistent Dolby Vision L5;
  3. conservative dimension-derived active rect;
  4. full frame.
- Preserve `native` geometry behavior.
- In `aligned` mode, common canvas planning must be stable for 3+ sources.
- Overlay origin must stay anchored to active content when active content is
  known, not to bars or padding.
- Do not stretch active image content. Crop, scale proportionally, and pad.
- Fail explicit config active-rect errors with typed user-visible config/input
  errors. Fail closed to full-frame/native behavior with warnings only for
  invalid runtime-derived metadata or dimension-derived active rect candidates.

Tests:

- three-source same-height/different-width center crop;
- three-source same-width/different-height center crop;
- three-source mixed width+height with explicit active rects;
- metadata active rect vs explicit override precedence;
- malformed/unsafe explicit active rect failure and malformed runtime-derived
  active rect fallback;
- DOVI L5 consistent rect used, inconsistent per-frame rect ignored;
- FFmpeg batch expansion attaches correct geometry to every request;
- VapourSynth writer path preserves geometry plan or records documented-only
  runtime proof if local runtime is unavailable.

Runtime verification:

```bash
bash tools/verify_docker_integration.sh
```

If Docker or VS runtime cannot run locally, record that exact gap and rely on
CI/manual runtime proof. Do not claim full runtime verification without it.

### Unit 6: Report Payload And Viewer N-Clip UX

Make generated reports correct and ergonomic for N clips.

Required behavior:

- Payload clip and frame images remain ordered by current clip order.
- Default selection remains valid for any clip count >= 1.
- Pair-based modes remain pair-based but must support choosing any two clips.
- Overlay mode must support choosing any one active clip.
- Manual visual alignment state must be scoped per pair, not global.
- Persisted viewer state must clamp safely when a report is regenerated with a
  different clip count.
- Pair-scoped state keys must be report-local and clip-index/clip-identity safe.
- Switching pairs must load that pair's saved alignment or reset to neutral.
- Keyboard shortcuts should not make the tenth source unreachable. If number
  shortcuts stay 1-9, add a documented/select-based path and consider a
  non-conflicting shortcut for clip 10+ during plan review.
- UI text and controls must not overlap on mobile/desktop report viewports.

Tests:

- report payload with four clips and multiple frames;
- viewer state restore with four clips;
- pair-scoped manual alignment does not leak between pair A and pair B;
- clip selectors clamp invalid persisted indices;
- optional browser/in-app screenshot smoke for report UI if the test harness is
  available.

Do not add explanatory in-app text that describes how to use the viewer unless
the existing design pattern already does so.

### Unit 7: slow.pics N-Column Upload Contract

Strengthen slow.pics support for N clips.

Required behavior:

- Upload plan remains row-major by selected frame, then clip order.
- Publisher metadata request must include every image in every row.
- Response validation must catch row/column mismatches for N columns.
- Image upload requests must map the correct local file to the correct returned
  image UUID.
- Delete-after-upload must delete only exact planned uploaded local file paths.
- Shortcut files remain outside uploaded-file cleanup membership.
- No live mutating slow.pics tests in the default suite.

Tests:

- upload plan with 4 clips and either a 10-clip case or a parametrized
  N-column case covering 10 columns;
- publisher multipart metadata with `cols=4` and either `cols=10` or a
  parametrized N-column case covering 10 columns;
- response with too few/too many image UUIDs fails clearly;
- image upload ordering for multiple rows and N columns;
- delete-after-upload membership remains exact.

### Unit 8: End-To-End And Manual Acceptance Scenarios

Add high-signal acceptance coverage without making the default suite require
live VSPreview, FFmpeg, network, or Docker unless correctly marked.

Automated scenarios:

- Four synthetic clip states through orchestration phase tasks:
  reference plus three comparisons, known offsets, differing lengths, selected
  aligned frames map to expected source frames.
- Three or four render batch requests with mixed dimensions and active rects.
- Report payload plus viewer-state test for four clips.
- slow.pics upload metadata for four clips and at least two selected frames.

Manual runtime scenario for maintainer testing:

1. Put three same-FPS clips in `comparison_videos` with names that make the
   intended reference obvious, for example:
   - `00-reference.mkv`
   - `01-encode-a.mkv`
   - `02-encode-b.mkv`
2. Run once with `screenshots.geometry_mode = "native"` and no VSPreview to
   prove basic N-source flow.
3. Run with `screenshots.geometry_mode = "aligned"` and known crop/active-rect
   differences to inspect output.
4. Run with `audio_alignment.use_vspreview = true` to inspect prompt/output
   ordering and per-comparison confirmation.
5. Open the report and verify:
   - all clips are listed;
   - diff/blink can compare any pair;
   - overlay can show any clip;
   - manual visual alignment is pair-specific;
   - switching pairs does not leak offsets.
6. If slow.pics is enabled in a non-production test context, verify that every
   selected frame has all clips in the expected order.

### Unit 9: Docs, Review, Verification, And Plan Closeout

Before closeout:

- Run an adversarial implementation review.
- Adjudicate every finding.
- Update authority docs in the same pass as public behavior changes.
- Run full verification.
- Run Docker/runtime verification for render/VS changes or record the exact
  documented-only gap.
- Regenerate/check API docs if code changes affect generated API docs.
- Inspect `git status`, `git diff --stat`, and changed-file diffs.
- Mark this plan `Status: Historical` only after implementation, review,
  verification, and maintainer acceptance are complete.

## Verification Strategy

Primary verification modes:

- `contract-first` for config, CLI, report payload, and slow.pics upload shape.
- `regression-first` for all-or-nothing alignment and report alignment leakage.
- `integration-ops` for VSPreview, FFmpeg/VapourSynth render geometry, and
  Docker/runtime proof.
- `manual-runtime` for real VSPreview GUI confirmation and visual report review.

Required command gate for code changes in this plan:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Additional required gate when render/VS behavior changes:

```bash
bash tools/verify_docker_integration.sh
```

API docs drift check when relevant:

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check
```

Focused tests should be run before full verification. Expected focused areas:

- `tests/config/test_schema.py`
- `tests/config/test_overrides.py` if CLI overrides are touched
- `tests/orchestration/test_preparation.py`
- `tests/orchestration/test_phase_tasks_alignment.py`
- `tests/orchestration/test_phase_tasks_outputs.py`
- `tests/services/test_alignment_workflow.py`
- `tests/services/test_alignment_vspreview.py`
- `tests/services/test_alignment_workflow_vspreview.py`
- `tests/vspreview/test_adapter.py`
- `tests/render/test_geometry.py`
- `tests/render/test_expansion.py`
- report service/viewer tests under `tests/services`
- `tests/services/test_slowpics_upload_plan.py`
- `tests/services/test_publishers.py`
- `tests/test_cli_contract_docs.py` if CLI/config docs change

## Review Checklist

Every implementation review must check:

- No accidental two-clip assumptions remain in touched owners.
- No public CLI/config behavior changed without docs and tests.
- `run --json` stdout remains a single JSON object.
- Source ordering is deterministic after explicit reference selection.
- Ambiguous source selectors fail loudly.
- Pairwise alignment does not discard good offsets because one comparison fails.
- Source-frame offset sign convention is unchanged.
- VSPreview output order and terminal prompt order match.
- Per-comparison VSPreview skip does not discard other confirmations.
- Geometry active-rect precedence is deterministic and tested.
- Report-viewer manual alignment is pair-scoped.
- slow.pics metadata/image upload shape is correct for N columns.
- Tests are behavior-focused and do not depend on live network, real browser,
  real clipboard, or unmarked runtime tools.
- Import layers still pass `lint-imports`.

## Stop-And-Replan Triggers

Stop implementation and update this plan if any of these occur:

- The selected public config shape needs to change after code exploration.
- Reference selection cannot be represented without ambiguous matching.
- Effective-FPS overrides would weaken current mixed-FPS fail-fast behavior
  without explicit maintainer approval.
- Pairwise partial-alignment policy cannot guarantee valid source-frame mapping
  for all included clips.
- Render geometry needs pixel black-bar detection to satisfy the acceptance
  scenario.
- VSPreview N-source UX requires changing manual override schema.
- Report viewer changes require a larger UI redesign than pair-scoped state and
  selector behavior.
- slow.pics remote protocol appears to cap columns lower than the target N.
- Docker/runtime verification exposes environment assumptions not covered by
  current docs.
- Any implementation requires relaxing `importlinter.ini`.

## Rollback And Commit Strategy

Use small conventional commits by unit or tightly related units. Suggested
commit boundaries:

1. `test: cover n-source parity gaps`
2. `feat(config): support explicit source reference selection`
3. `feat(config): support per-source trim and active-rect overrides`
4. `feat(config): support per-source effective fps overrides`
5. `fix(alignment): preserve valid pairwise offsets across failed comparisons`
6. `fix(vspreview): support per-comparison n-source confirmations`
7. `feat(render): support explicit n-source active geometry overrides`
8. `fix(report): scope viewer alignment by clip pair`
9. `test(slowpics): verify n-column upload contracts`
10. `docs: document n-source parity behavior`

Do not stage unrelated files. Do not mark this plan historical until all
reviewed units are complete.

## Final Acceptance Criteria

The work is complete only when all are true:

- A run with at least three clips is supported through prep, analysis,
  alignment, render, report, and optional slow.pics upload.
- There is no intentional two-comparison cap in code or tests.
- Explicit reference selection works and default reference behavior remains
  backward-compatible.
- Source trim, active rect, and effective FPS overrides work through the
  source-owned config seam with typed validation.
- Analysis cache identity is reference-aware and includes source overrides that
  affect the selected reference frame/timing domain.
- Duplicate stems fail early until alignment persistence is migrated to stable
  versioned source-identity keys.
- Accepted pairwise alignments survive unrelated comparison failures.
- VSPreview can confirm or skip each comparison independently.
- Aligned geometry can handle 3+ sources with explicit active rects and
  conservative metadata/dimension fallbacks.
- Report viewer can compare any pair and keeps manual visual offsets per pair.
- slow.pics upload tests prove N-column metadata and image upload ordering.
- Authority docs describe new public config behavior.
- Full verification passes, with Docker/runtime/manual gaps recorded honestly.
