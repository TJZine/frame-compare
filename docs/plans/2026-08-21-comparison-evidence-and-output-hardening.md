---
search:
  exclude: true
---

Status: Active
Scope: Automatic frame-selection diversity, plain non-TTY progress, alignment-stability diagnostics, report-viewer modularization, and file-size HUD presentation
Owner: Primary implementation controller

# Frame Compare Comparison-Evidence and Output-Hardening Plan

## Execution-ready plan for bounded GPT-5.6 Sol Light sessions

**Repository:** `TJZine/frame-compare`
**Working branch:** latest `dev/v0.2.0` unless current repository authority changes the branch policy
**Dispatch intent:** bounded sequential implementation sessions using GPT-5.6 Sol Light; current repository role configuration remains authoritative if it differs
**Parallelism:** none; sessions share authority documents, tests, and integration surfaces
**Plan policy:** not SHA-locked; every session must fetch and inspect the current branch before editing
**Final review:** one fresh read-only adversarial review followed by one minimality/YAGNI pass

---

# 1. Executive decision

Implement the locked work as eight sequential sessions:

| Session | Outcome |
| --- | --- |
| A | Improve deterministic temporal diversity for random, dark, bright, and motion frame selection |
| B | Replace non-TTY human log milestones with a chronological plain progress renderer |
| C | Retain bounded per-window audio-alignment evidence and classify stability |
| D | Integrate alignment stability into runtime warnings, cache compatibility, and Frame Alignment output |
| E | Extract viewer formatting and Inspector behavior into focused vanilla-JavaScript owners |
| F | Extract viewport, zoom/pan, fit, and pair-alignment mechanics into a focused owner |
| G | Surface canonical source file size in the viewer HUD using existing report facts |
| H | Integrate, independently review, remediate valid findings, verify, and close the plan |

The work is intentionally split because it spans independent ownership domains and must remain suitable for a light-reasoning implementation session. Each session has a bounded write surface, explicit invariants, direct proof, rollback, and stop conditions.

---

# 2. Locked product decisions

| Item | Decision |
| ---: | --- |
| Effective run manifest/replay | Deferred/declined |
| Improved automatic frame diversity | Approved |
| Plain non-TTY human output | Approved |
| File-size decision context | Approved, limited to missing viewer/HUD presentation |
| Blind comparison | Deferred |
| Review conclusion artifact | Deferred |
| Alignment drift/edit-discontinuity diagnostics | Approved, diagnostics-only |
| Stable source IDs | Deferred |
| Viewer modularization | Approved and must precede new viewer HUD work |
| Cross-source divergence frame selection | Separate future plan |
| Stronger source-content fingerprint | Declined |
| Piecewise alignment | Deferred |
| Objective quality metrics | Deferred |

## 2.1 Blind-comparison decision

Do not implement blind mode in this program.

A browser-side rectangle that covers baked overlay pixels is not acceptable because it:

- hides real image content;
- depends on overlay geometry and wrapping;
- can be bypassed by opening the image directly or disabling the mask;
- would need separate behavior across Slider, Single, Diff, Blink, Grid, Lens, zoom, pan, and fullscreen.

A trustworthy one-image-set blind design should be reconsidered only if canonical screenshots become clean and identifying overlays move to the report presentation layer. A second image set or second render pass is not approved.

## 2.2 Divergence-selection decision

Do not add cross-source divergence selection in this program.

It requires a separate plan resolving:

- post-alignment phase ownership;
- multi-source normalization;
- cheap metric choice;
- temporal sampling and local refinement;
- runtime budget;
- cache/config behavior;
- multi-comparison allocation;
- user-facing terminology that does not imply a quality score.

No placeholder config field, phase, DTO, cache key, or partial implementation is permitted here.

---

# 3. Global goals

1. Improve the representativeness of automatically selected evidence without materially increasing media-analysis time.
2. Make redirected and CI human output readable without changing JSON, quiet, or interactive TTY contracts.
3. Detect and report when one constant alignment offset is not stable across the source, without changing the applied offset.
4. Reduce `viewer.js` ownership concentration while preserving the offline single-file report architecture.
5. Surface existing file-size facts where users make archival decisions without treating size as a quality metric.

---

# 4. Global non-goals

The implementation must not:

- add a run-manifest or history-rerun feature;
- add blind-mode flags, reveal maps, image masks, duplicate image sets, or hidden identities;
- add divergence/difference selection or a new cross-source analysis phase;
- replace filename-stem source identities;
- alter cache freshness to use stronger content hashing;
- implement piecewise alignment or regional frame mappings;
- add VMAF, CAMBI, SSIM, ML, OCR, optical flow, or perceptual hashing;
- add a frontend framework, TypeScript, Vite, npm runtime dependency, or network-loaded asset;
- change successful `run --json` output;
- change report payload version `1.2` for the viewer refactor or file-size HUD;
- add user configuration merely to tune internal diversity or diagnostic heuristics;
- combine unrelated opportunistic cleanup with an implementation session.

---

# 5. Repository preconditions

## 5.1 Resolve overlapping active work

Before Session A:

1. Inspect PR #81 and the latest `dev/v0.2.0`.
2. Confirm PR #81 is merged, closed, or otherwise stable enough for new work.
3. Confirm no other writer owns the files in the assigned session.
4. Preserve all unrelated tracked and untracked changes.

Before Session E:

1. Inspect `docs/plans/2026-08-21-report-viewer-layout-and-release-display.md`.
2. Mark it historical if its remaining evidence has been completed, or transfer its unresolved evidence requirements into this plan.
3. Do not leave two Active plans claiming ownership of the same report-viewer files.

## 5.2 Session-start commands

Every session starts with:

```bash
git status --short
git branch --show-current
git fetch origin
git log -1 --oneline
```

Then:

1. Confirm the required branch.
2. Compare local and remote state.
3. Incorporate upstream only through the maintainer's normal non-force workflow.
4. Stop on merge conflicts or overlapping uncommitted work.
5. Re-read affected owners after any update.
6. Record the baseline SHA in the session handoff only; do not write it into this plan.

Before every commit:

```bash
git status --short
git diff --check
git diff --stat
git diff
git fetch origin
```

Never force-push `dev/v0.2.0`.

---

# 6. Required authority reads

Every session reads current versions of:

- `AGENTS.md`
- relevant sections of `docs/ENGINEERING_RUNBOOK.md`
- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- this active plan
- complete affected production owners
- complete focused tests

Additional required reads by domain:

| Domain | Additional reads |
| --- | --- |
| Analysis | `docs/guides/analysis-modes.md` |
| Alignment | `docs/guides/audio-alignment.md` |
| Report/viewer | `docs/guides/reports-and-overlays.md`, current active report plan |
| Model/dispatch | `.agents/skills/model-selection/SKILL.md`, `.agents/skills/bounded-worker-execution/SKILL.md` |
| Final closeout | `.agents/skills/closeout-verification/SKILL.md`, applicable review/minimality skills |

Current source and tests outrank stale paths or helper names in this plan.

---

# 7. Shared implementation rules

## 7.1 Session discipline

Each session must:

- implement only its assigned unit;
- use one authoritative writer;
- not delegate or spawn subagents;
- not broaden public behavior beyond the locked acceptance criteria;
- run focused proof before a full gate;
- inspect the complete diff;
- commit only the session's changes;
- update this plan's Progress section;
- return a compact handoff;
- stop instead of deciding a new product, ownership, public-contract, architecture, or proof requirement.

## 7.2 Required session return

```text
RESULT
FILES CHANGED
BEHAVIORAL CHANGES
PROOF
PERFORMANCE EVIDENCE
ASSUMPTIONS
BLOCKERS
NEXT SESSION READINESS
```

## 7.3 Common static verification

For Python changes:

```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync lint-imports --config importlinter.ini
```

For public CLI, orchestration, alignment, or report behavior:

```bash
uv run --no-sync pytest -q
```

Documentation closeout:

```bash
uv sync --only-group docs --locked
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
uv sync --group dev --group docs --locked
```

No physical-Windows or Docker media-runtime campaign is required solely because of these changes, but current CI Windows portable, Docker integration, distribution, browser, docs, and source jobs must remain green.

---

# 8. Session A — Deterministic temporal diversity

## Objective

Improve random, dark, bright, and motion frame representativeness without opening, decoding, or analyzing any additional media frames.

## Current problem

The current selector:

- uses a fixed `MIN_GAP = 5` only for motion and random;
- lets dark and bright results cluster in one scene;
- samples dark/bright candidates across score order rather than timeline position;
- can fail on short clips even when enough distinct frames exist but the preferred gap cannot be maintained.

## Primary owner

```text
src/frame_compare/analysis/selection.py
```

Likely focused tests:

```text
tests/analysis/test_selection.py
tests/orchestration/test_phase_tasks_alignment.py
tests/orchestration/test_phase_tasks.py
```

Likely docs:

```text
docs/guides/analysis-modes.md
docs/current-architecture.md
docs/current-cli-contract.md
CHANGELOG.md
```

Do not modify metric calculation, performance sampling, cache schema, config schema, category names/counts, or coordinate domains.

## Locked algorithm

### Category precedence

Preserve:

```text
User -> Dark -> Bright -> Motion -> Random
```

Earlier categories own collisions.

### User frames

User frames remain exact, highest-priority, and never moved or replaced.

### Temporal strata

For a category requesting `N` frames:

1. Divide the full eligible selection domain into `N` deterministic half-open strata.
2. Compute boundaries with integer frame arithmetic.
3. Use source-frame coordinates when metric samples are sparse.
4. Do not use timestamps or floating-point allocation.

### Random

1. Within each stratum, use the existing stable seed-derived order.
2. Choose the first unused candidate satisfying the preferred gap.
3. Fill empty strata from the remaining global stable ordering.
4. Prefer five-frame separation from all existing selections.
5. If enough distinct frames exist but spacing prevents completion, relax spacing deterministically.
6. Never relax uniqueness.

### Dark

1. Preserve the configured dark-quantile pool.
2. Choose the darkest eligible candidate in each stratum.
3. Fill empty strata from the remaining globally darkest quantile candidates.
4. Use the current broader-pool fallback only when the quantile pool cannot satisfy the count.
5. Prefer the gap; relax it only when necessary to fulfill a valid count.

### Bright

Use the same policy, choosing the brightest candidate.

### Motion

1. Preserve descending motion score.
2. Choose the highest-motion candidate in each stratum.
3. Fill empty strata from the remaining global ranking.
4. Prefer the gap and use deterministic relaxation when necessary.

Do not add weighted optimization, scene detection, image similarity, or a global solver.

## Performance constraints

- zero additional source access;
- zero additional VapourSynth work;
- zero additional metric calculation;
- no new dependency;
- allocation work remains sorting plus bounded candidate selection;
- record an ad hoc synthetic selection benchmark in the handoff;
- do not add timing assertions to CI.

## Acceptance criteria

- same input/config/version/seed is deterministic;
- random selections cover separate strata where possible;
- dark/bright/motion selections cover separate temporal regions where valid candidates exist;
- user frames remain exact;
- category counts remain exact when enough unique candidates exist;
- short clips no longer fail only because five-frame spacing cannot be preserved;
- sparse metric coordinates, labels, scores, and timecodes remain correct;
- metric cache identity is unchanged;
- docs state that exact selections may differ from earlier releases.

## Focused verification

```bash
uv run --no-sync pytest -q \
  tests/analysis/test_selection.py \
  tests/orchestration/test_phase_tasks_alignment.py \
  tests/orchestration/test_phase_tasks.py
```

Then run the common static checks and full pytest.

## Stop conditions

Stop if:

- a new config field appears necessary;
- a new media scan is proposed;
- sparse coordinates cannot remain correct;
- category count semantics must change;
- deterministic output cannot be preserved;
- implementation grows into an elaborate scoring framework.

## Commit

```text
feat(analysis): diversify automatic frame selection
```

## Rollback

Reverting this commit restores prior frame choices. Metric caches remain valid because metric computation and identity are unchanged.

---

# 9. Session B — Plain non-TTY progress

## Objective

Replace non-TTY human use of structured log-progress milestones with a chronological ASCII plain progress reporter.

## Primary owners

```text
src/frame_compare/utils/progress.py
src/frame_compare/orchestration/progress.py
```

Touch `src/frame_compare/orchestration/phases.py` only for a narrow protocol integration.

Likely tests:

```text
tests/utils/test_progress.py
tests/orchestration/test_progress.py
tests/orchestration/test_phases.py
tests/cli/test_run_output.py
tests/cli/test_run_command.py
tests/cli/test_run_json_errors.py
```

Docs:

```text
docs/current-cli-contract.md
docs/TODO.md
docs/current-architecture.md
```

## Locked reporter selection

```text
quiet                 -> NullProgressReporter
JSON                  -> LogProgressReporter
interactive TTY human -> RichProgressReporter
non-TTY human         -> PlainProgressReporter
```

`force_tty=False` means plain human progress unless JSON mode is active.

## Locked plain output

- stderr only;
- ASCII only;
- no ANSI;
- no Rich panel, spinner, progress bar, carriage return, or redraw;
- no percentage milestones;
- one line per top-level phase, emitted at completion;
- successful nested activities remain silent;
- warned/failed nested work may emit one durable line only when needed to preserve a material outcome;
- existing product phase labels and ASCII statuses are reused;
- completed top-level phases include elapsed time;
- existing skip detail remains visible.

Example:

```text
[OK] PLAN  Completed in 0s
[OK] ANALYZE  Completed in 1m 24s
[SKIP] METADATA  Disabled
[OK] REPORT  Completed in 1s
```

Do not redesign Run plan, source/FPS facts, Frame Alignment, Final Selection, result summary, or final warnings.

## Public invariants

- successful JSON stdout unchanged;
- JSON continues structured stderr logging;
- quiet behavior unchanged;
- interactive Rich behavior unchanged;
- prompt eligibility unchanged;
- exit codes unchanged;
- no `--plain` option.

## Acceptance criteria

- non-TTY human runs contain no progress `phase_started`, `phase_progress`, or `phase_completed` log events;
- each top-level phase appears at most once;
- JSON still uses `LogProgressReporter`;
- TTY still uses Rich;
- quiet still uses Null;
- plain output contains no ANSI or Unicode status glyphs;
- failure emits one `[FAIL]` phase line before existing typed error presentation;
- completed TODO item is removed.

## Focused verification

```bash
uv run --no-sync pytest -q \
  tests/utils/test_progress.py \
  tests/orchestration/test_progress.py \
  tests/orchestration/test_phases.py \
  tests/cli/test_run_output.py \
  tests/cli/test_run_command.py \
  tests/cli/test_run_json_errors.py
```

Then full gate.

## Stop conditions

Stop if:

- successful JSON must change;
- CLI-specific types leak into `utils`;
- existing output owners would duplicate facts;
- stream ownership is unclear;
- prompt behavior would change.

## Commit

```text
feat(cli): add plain non-tty progress output
```

## Rollback

Revert to restore existing non-TTY log-progress behavior. No data migration exists.

---

# 10. Session C — Alignment-stability evidence and classifier

## Objective

Retain and classify bounded per-window offset evidence without changing accepted offsets, trims, or mapped frames.

## Primary owners

```text
src/frame_compare/services/alignment_consensus.py
src/frame_compare/services/alignment_stability.py
src/frame_compare/services/types.py
```

A new focused pure owner is preferred if it prevents `alignment_consensus.py` from mixing estimation with presentation-oriented classification.

Likely tests:

```text
tests/services/test_alignment_core.py
tests/services/test_alignment_workflow.py
tests/services/test_alignment_stability.py
```

Do not modify orchestration, cache serialization, CLI rendering, report payload, or config schema in this session.

## Locked evidence model

Use immutable typed evidence equivalent to:

```python
AlignmentWindowEvidence(
    start_sample,
    end_sample,
    sample_offset,
    score,
    peak_ratio,
)

AlignmentStabilitySummary(
    classification,
    valid_windows,
    offset_min_frames,
    offset_max_frames,
    first_offset_frames,
    last_offset_frames,
    largest_adjacent_jump_frames,
    change_position_seconds,
)
```

Allowed classifications:

```text
stable
possible_drift
possible_discontinuity
variable
insufficient_evidence
```

## Evidence collection

### Reuse existing consensus windows

If current consensus already yields at least three valid distinct window estimates, reuse them without recomputation.

### Supplemental diagnostic windows

If fewer than three usable windows exist:

1. reuse already extracted audio arrays;
2. create at most five evenly placed deterministic windows;
3. deduplicate identical spans on short clips;
4. do not invoke FFmpeg again;
5. perform at most five supplemental correlations per comparison.

Window duration:

```text
preferred = 2 * max_offset_seconds + 15 seconds
minimum = 30 seconds
maximum = 90 seconds
clamp to available signal duration
```

A diagnostic window is valid only when energy is nonzero, correlation succeeds, score passes the configured confidence threshold, and peak ratio passes the ambiguity threshold.

## Classification in frame units

### Stable

```text
offset_max - offset_min <= 1 frame
```

### Possible discontinuity

- largest adjacent jump is at least two frames; and
- it accounts for at least 60% of the complete observed span.

Reported position is the midpoint between windows around the largest jump.

### Possible drift

- first-to-last change is at least two frames; and
- at least 75% of meaningful adjacent changes move in the same direction, allowing one-frame noise.

### Variable

Material span exists but does not satisfy drift or discontinuity rules.

### Insufficient evidence

Fewer than three valid windows.

## Critical invariant

The summary is diagnostic only. It must not affect:

- offset selection;
- acceptance/rejection;
- trims;
- selected frames;
- source-frame mapping;
- alignment cache identity.

## Performance constraints

- no second audio extraction;
- at most five supplemental windows per comparison;
- 90-second window cap;
- no DTW;
- no piecewise map;
- no clustering framework;
- no dependency;
- record synthetic before/after performance evidence;
- stop if diagnostics materially dominate alignment time.

## Acceptance criteria

Pure tests prove:

- constant offset -> stable;
- gradual monotonic change -> possible drift;
- one dominant jump -> possible discontinuity;
- scattered variation -> variable;
- fewer than three valid windows -> insufficient evidence;
- one-frame noise does not warn;
- low-confidence windows do not create false variation;
- supplemental window count is bounded;
- classifier invokes no source/FFmpeg boundary;
- classification does not alter the accepted estimate.

## Focused verification

```bash
uv run --no-sync pytest -q \
  tests/services/test_alignment_core.py \
  tests/services/test_alignment_workflow.py \
  tests/services/test_alignment_stability.py
```

Then common static checks.

## Stop conditions

Stop if:

- piecewise alignment becomes necessary;
- more than five supplemental windows are required;
- a new config field appears necessary;
- accepted-offset behavior must change;
- obvious constant-offset fixtures produce warnings.

## Commit

```text
feat(alignment): classify offset stability evidence
```

## Rollback

Reverting removes internal evidence. No persisted/public contract is introduced by this session.

---

# 11. Session D — Integrate alignment diagnostics

## Objective

Carry Session C evidence through computed/cached alignment results, orchestration, warnings, and the existing Frame Alignment diagnostic.

## Primary owners

```text
src/frame_compare/services/types.py
src/frame_compare/services/alignment.py
src/frame_compare/services/alignment_reuse_cache.py
src/frame_compare/orchestration/context.py
src/frame_compare/orchestration/phase_alignment.py
src/frame_compare/orchestration/alignment_report.py
```

Likely tests:

```text
tests/services/test_alignment_core.py
tests/services/test_alignment_workflow.py
tests/services/test_alignment_reuse_cache.py
tests/services/test_alignment_previous_offsets.py
tests/services/test_alignment_vspreview.py
tests/orchestration/test_alignment_report.py
tests/orchestration/test_phase_tasks_alignment.py
```

Docs:

```text
docs/guides/audio-alignment.md
docs/current-architecture.md
docs/current-cli-contract.md
```

Do not change HTML report payload/viewer.

## Locked integration

### Results

Add an optional compact stability summary to `AlignmentResult`. Existing constructors remain valid with a default of `None`.

### Computed results

Attach the current-run summary.

### Cache

Persist and restore the optional compact summary without invalidating existing version-1 cache entries.

- legacy entries without summary remain readable/reusable;
- no cache-wide version bump solely for this addition;
- no raw audio or unbounded window list is stored;
- new optional fields are validated when present.

### VSPreview/manual provenance

- VSPreview-confirmed results may preserve the underlying computed summary as evidence;
- do not describe manual confirmation as window-derived;
- pure manual overrides have no stability evidence.

### Orchestration

Carry the summary on immutable comparison alignment state. Do not create a mutable diagnostics side channel.

### Warning policy

Applied alignment remains applied.

- `stable`: no warning;
- `insufficient_evidence`: no warning;
- `possible_drift`: one bounded `align:` warning;
- `possible_discontinuity`: one bounded `align:` warning;
- `variable`: one bounded `align:` warning.

Warnings must contain no raw path or exception text.

### Frame Alignment output

Normal mode shows a concise stability row only for non-stable material evidence.

Example:

```text
stability  possible discontinuity; +178..+202 frames; change near 00:47:12
```

Verbose mode may show valid-window count and stable/unavailable evidence.

Do not print every window.

### JSON

Successful `run --json` stdout remains unchanged.

## Acceptance criteria

- stable fixtures retain byte/semantic alignment behavior;
- diagnostics never change offset or trims;
- non-stable evidence warns while retaining the constant offset;
- cache round-trip preserves optional summary;
- legacy cache remains readable;
- VSPreview-confirmed results preserve computed evidence where available;
- manual overrides do not invent evidence;
- normal output remains concise;
- verbose output is diagnostic enough;
- warnings are bounded and path-safe;
- report payload remains unchanged.

## Focused verification

```bash
uv run --no-sync pytest -q \
  tests/services/test_alignment_core.py \
  tests/services/test_alignment_workflow.py \
  tests/services/test_alignment_reuse_cache.py \
  tests/services/test_alignment_previous_offsets.py \
  tests/services/test_alignment_vspreview.py \
  tests/orchestration/test_alignment_report.py \
  tests/orchestration/test_phase_tasks_alignment.py
```

Then full gate.

## Stop conditions

Stop if:

- legacy cache compatibility cannot be preserved;
- diagnostic evidence starts controlling application;
- warnings require raw paths;
- report payload must change;
- implementation starts becoming piecewise alignment.

## Commit

```text
feat(alignment): report non-constant offset evidence
```

## Rollback

Revert to remove presentation and optional cache fields. Legacy cache compatibility means rollback requires no destructive migration.

---

# 12. Session E — Extract formatting and Inspector ownership

## Objective

Reduce `viewer.js` responsibility by extracting pure formatting and Inspector behavior into focused plain-JavaScript owners.

## Preconditions

- overlapping active viewer plan resolved;
- prior sessions integrated and green;
- latest viewer implementation and harnesses re-read.

## Production owners

```text
src/frame_compare/services/report/assets/viewer_format.js
src/frame_compare/services/report/assets/inspector.js
src/frame_compare/services/report/assets/viewer.js
src/frame_compare/services/report/viewer.py
```

Likely tests/harnesses:

```text
tests/services/inspector_harness.js
tests/services/test_report_viewer_inspector.py
tests/services/viewer_state_harness.js
tests/services/test_report_viewer_state.py
tests/services/test_report_renderer_markup.py
tests/services/test_report_viewer_assets_css.py
tests/browser/test_report_browser_smoke.py
```

Docs:

```text
docs/current-architecture.md
```

## Locked architecture

### `ViewerFormat`

Pure dependency-free formatting owner for:

- display-profile lookup;
- exact filename;
- accessible clip name;
- FPS;
- IEC file size;
- signal labels;
- presentation/tonemap labels;
- active-picture labels;
- mode labels;
- stable clip roles.

It must not access DOM, storage, viewer state, or parse release filenames.

### `Inspector.create(viewer)`

Own:

- open/close application;
- focus capture/restoration;
- inert/tab-index policy;
- tab selection and roving keyboard behavior;
- Inspector DOM references;
- Frame, Clips, Align, and Export rendering;
- safe slow.pics link;
- lazy Review-controller activation.

Root viewer retains canonical report state, modes, frame/source selection, root initialization/render sequencing, and component composition.

### Compatibility facade

Thin delegating methods on `ReportViewer` are permitted temporarily for existing Lens/Grid/Review/harness calls. Ownership must genuinely move; wrappers must not duplicate logic.

### Asset assembly

`get_js()` concatenates assets in deterministic dependency order. Report remains one offline HTML file with no loader/network dependency.

## Public invariants

- payload stays 1.2;
- report identity unchanged;
- storage keys/schemas unchanged;
- Review import/export unchanged;
- DOM IDs/classes and shortcuts unchanged unless a mechanical ownership transfer requires otherwise;
- no intended visual/responsive change;
- no framework or build-system addition.

## Test strategy

Move Inspector-specific assertions to a dedicated harness. Retain one root composition smoke test. Do not test the same behavior in both suites.

## Acceptance criteria

- `viewer.js` no longer implements Inspector rendering/focus policy;
- one focused formatting owner exists;
- one focused Inspector owner exists;
- existing viewport, Lens, Grid, Review, keyboard, and browser behavior passes;
- no payload/storage migration;
- no circular controller graph;
- asset order is deterministic;
- responsibility is reduced rather than merely wrapped.

## Focused verification

```bash
uv run --no-sync pytest -q \
  tests/services/test_report_viewer_inspector.py \
  tests/services/test_report_viewer_state.py \
  tests/services/test_report_renderer_markup.py \
  tests/services/test_report_viewer_assets_css.py \
  tests/browser/test_report_browser_smoke.py
```

Then full gate.

## Stop conditions

Stop if:

- payload changes are required;
- Review storage/schema must change;
- controller interface becomes broad and bidirectional;
- a framework/transpiler is proposed;
- visual changes become inseparable from refactor.

## Commit

```text
refactor(report): extract viewer formatting and inspector owners
```

## Rollback

Revert to restore behavior inside `viewer.js`. Payload and storage remain compatible.

---

# 13. Session F — Extract viewport and pair-alignment ownership

## Objective

Move viewport coordinate math and pair-alignment mechanics out of `viewer.js` while keeping one canonical root state and persistence owner.

## Production owners

```text
src/frame_compare/services/report/assets/viewport.js
src/frame_compare/services/report/assets/viewer.js
src/frame_compare/services/report/viewer.py
```

Likely tests/harnesses:

```text
tests/services/viewport_harness.js
tests/services/test_report_viewer_viewport.py
tests/services/viewer_state_harness.js
tests/services/test_report_viewer_state.py
tests/services/grid_view_harness.js
tests/services/lens_harness.js
tests/browser/test_report_browser_smoke.py
```

Docs:

```text
docs/current-architecture.md
```

## Locked architecture

Use:

```javascript
Viewport.create(viewer)
```

Viewport owner handles:

- zoom clamping/application;
- zoom-at-pointer anchoring;
- pan and bounds;
- fit actual/width/height;
- viewport reset;
- reveal percentage;
- canvas/image bounds;
- Grid normalized pan conversions;
- pair-alignment keys;
- directional pair normalization;
- presets/custom offsets;
- viewport refresh after mode/layout/source changes;
- current Lens/Grid viewport refresh hooks.

Root viewer retains:

- canonical state object;
- localStorage serialization;
- event registration;
- shortcut routing;
- mode/source/frame transitions;
- root render sequencing.

Thin delegate methods are allowed to preserve current public component calls.

## Public invariants

- zoom range 25%–400%;
- current fit semantics;
- Slider reveal behavior;
- Grid pan semantics;
- directional report-scoped pair alignments;
- pointer/wheel/touch/pinch behavior;
- Lens sample stability;
- storage keys/schema;
- payload and CSS.

## Test strategy

Move viewport math to a dedicated harness:

- zoom bounds;
- pointer anchor;
- pan clamping;
- fit calculations;
- Grid conversion;
- directional pair alignment;
- reset;
- Lens/Grid refresh.

Root harness retains composition proof only.

## Acceptance criteria

- `viewer.js` no longer owns coordinate math;
- one viewport owner exists;
- no duplicate canonical state;
- all existing Node/browser behavior remains green;
- root viewer is materially more cohesive;
- no framework, payload, storage, or visual change.

## Focused verification

```bash
uv run --no-sync pytest -q \
  tests/services/test_report_viewer_viewport.py \
  tests/services/test_report_viewer_state.py \
  tests/services/test_report_viewer_assets_css.py \
  tests/browser/test_report_browser_smoke.py
```

Also run Lens and Grid harnesses, then full gate.

## Stop conditions

Stop if:

- viewport needs independent canonical state;
- event ownership duplicates;
- Lens/Grid contracts need redesign;
- behavioral changes become inseparable;
- additional controller proliferation is proposed.

## Commit

```text
refactor(report): extract viewport controller
```

## Rollback

Revert to restore viewport logic inside `viewer.js`. No payload or storage migration exists.

---

# 14. Session G — File-size HUD

## Objective

Append existing canonical source file size to visible stage/source HUD labels using the refactored formatting owner.

## Important scope limit

File size already exists in:

- report payload;
- Clips Inspector;
- baked non-`none` screenshot overlays.

Do not add probing, payload fields, render facts, or another overlay implementation.

## Production owners

```text
src/frame_compare/services/report/assets/viewer_format.js
src/frame_compare/services/report/assets/viewer.js
src/frame_compare/services/report/assets/grid_view.js
src/frame_compare/services/report/assets/viewer.css
```

Touch only the actual current owners after inspection.

Likely tests:

```text
tests/services/viewer_state_harness.js
tests/services/test_report_viewer_state.py
tests/services/grid_view_harness.js
tests/services/test_report_renderer_markup.py
tests/services/test_report_viewer_assets_css.py
tests/browser/test_report_browser_smoke.py
```

Docs:

```text
docs/guides/reports-and-overlays.md
```

Do not modify:

```text
src/frame_compare/services/report/payload.py
src/frame_compare/render/overlay_text.py
src/frame_compare/render/**
src/frame_compare/orchestration/phase_post_render.py
```

## Locked UX

Append existing IEC size formatting to visible source labels.

Examples:

```text
LEFT: 2160p | AMZN WEB-DL | DV HDR10 | FLUX • 3840×2160 • HDR • 17.42 GiB
RIGHT: 1080p | NF WEB-DL | SDR | Kira • 1920×1080 • SDR • 4.81 GiB
```

Preserve current mode prefixes:

- Slider: `LEFT` / `RIGHT`
- Diff: `BASE` / `COMPARE`
- Blink: `FIRST` / `SECOND`
- Single: active source with no false pair role
- Grid: each cell includes its own size

Rules:

- use existing IEC formatter;
- two decimal places;
- omit invalid/missing/zero/negative values;
- no bitrate;
- no size ratio;
- no quality inference;
- no Lens identity addition;
- no new toggle;
- current HUD/overlay visibility toggle hides size with labels;
- retain wrapping and no horizontal document overflow.

## Accessibility

Expose size once in the visible label's accessible text. Do not add duplicate screen-reader-only text.

## Acceptance criteria

- size appears in Slider, Single, Diff, Blink, and Grid HUD labels;
- Clips Inspector remains correct;
- baked screenshot output unchanged;
- payload remains 1.2;
- no new probe or backend fact;
- hiding HUD hides size;
- usable at 375, 768, 1280, 1440, and 2560 CSS-pixel widths;
- no horizontal document overflow;
- docs state size is context, not bitrate or proof of quality.

## Focused verification

```bash
uv run --no-sync pytest -q \
  tests/services/test_report_viewer_state.py \
  tests/services/test_report_renderer_markup.py \
  tests/services/test_report_viewer_assets_css.py \
  tests/browser/test_report_browser_smoke.py
```

Also run Grid/viewport harnesses, then full gate.

## Stop conditions

Stop if:

- payload version must change;
- a new probe is proposed;
- labels become unusably dense;
- formatting is duplicated;
- a new drawer is required solely for file size.

## Commit

```text
feat(report): show source file sizes in the viewer hud
```

## Rollback

Revert to remove HUD size. Payload, Inspector, screenshots, and reports remain compatible.

---

# 15. Session H — Integration, independent review, and closeout

## Objective

Prove the integrated program, close valid findings, update authority documents, and mark this plan historical.

## Full verification

```bash
uv sync --group dev --group docs --locked

uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
```

Verify current CI:

- CI;
- Documentation;
- generated report browser smoke;
- dependency audit on Linux and Windows;
- build/install distribution;
- Windows portable;
- Docker integration.

## Independent review packet

Use one fresh read-only reviewer with no implementation transcript.

Review:

1. selection semantics and sparse coordinates;
2. hidden analysis/runtime cost;
3. duplicate/misplaced CLI output;
4. alignment false positives and bounded work;
5. legacy cache compatibility;
6. viewer owner boundaries versus wrapper-only movement;
7. browser state, accessibility, and local persistence;
8. file-size language and responsive behavior;
9. authority-document drift;
10. accidental deferred-scope implementation.

## Minimality/YAGNI pass

Explicitly validate:

- one focused temporal allocator;
- no unnecessary config;
- plain reporter is simpler than mode flags inside log reporter;
- stability remains summary-only and diagnostics-only;
- viewer extraction stops at justified owners;
- file size reuses existing facts/formatter;
- no blind/divergence placeholders;
- no one-use helper layer without an ownership benefit.

Remove unnecessary abstractions before closeout.

## Documentation closeout

Update as required:

- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- `docs/guides/analysis-modes.md`
- `docs/guides/audio-alignment.md`
- `docs/guides/reports-and-overlays.md`
- `docs/TODO.md`
- `CHANGELOG.md`
- this plan's Progress section

Remove the completed plain-renderer TODO.

Do not add a divergence implementation plan or placeholder config during closeout.

Mark this plan historical only after:

- all sessions integrated;
- valid review findings closed;
- full verification passes;
- CI passes;
- unavailable manual evidence is explicitly recorded.

## Optional closeout commit

```text
docs: close comparison evidence and output hardening plan
```

---

# 16. Program rollback

Each implementation session must be a standalone commit.

| Session | Rollback result |
| --- | --- |
| A | Previous selection algorithm returns; metric caches remain valid |
| B | Existing non-TTY log progress returns |
| C | Internal stability evidence disappears; no persisted contract yet |
| D | Stability warnings/cache fields disappear; legacy cache remains valid |
| E | Inspector/formatting ownership returns to `viewer.js` |
| F | Viewport ownership returns to `viewer.js` |
| G | HUD size disappears; payload/screenshots unchanged |

No session may require destructive config, report, or cache migration to roll back.

---

# 17. Progress

- 2026-08-21 — Session B completed: non-TTY human runs now use chronological
  ASCII plain progress while JSON, quiet, and interactive Rich selection remain
  unchanged; focused proof and the full local gate passed; the existing reporter
  protocol required no phase wiring or ownership change; a 10,000-phase synthetic
  run emitted exactly 10,000 ASCII lines in 0.063 seconds; environment-gated
  Windows, live-service, and real-VapourSynth tests remain unavailable; Session C
  is ready.

Add one concise entry after each session:

```text
- YYYY-MM-DD — Session X completed: outcome; focused proof; full-gate/CI status;
  material decisions; known unavailable evidence; next-session readiness.
```

When complete:

```text
Status: Historical
```

Retain the plan as implementation history after closeout.

- 2026-08-21 — Session A completed: automatic categories now use deterministic
  temporal strata with ranked global backfill and spacing-only relaxation; focused
  selection/orchestration proof and the full local gate passed; sparse coordinates,
  cache identity, and media-analysis work remain unchanged; a 216,000-frame synthetic
  benchmark measured 0.324s before and 0.369s after (1.14x); CI was not run locally;
  Session B is ready.

- 2026-08-21 — Session C completed: bounded immutable window evidence now classifies
  stable, drift, discontinuity, variable, and insufficient evidence without changing
  accepted offsets or application; focused proof and the full local gate passed; a
  120-second synthetic comparison measured 0.081s before and 0.178s with diagnostics
  (2.20x total) using two supplemental windows, with the selected offset unchanged;
  CI was not run locally and environment-gated skips remain; Session D is ready.

- 2026-08-21 — Session D completed: compact stability summaries now survive computed,
  cached, and VSPreview-confirmed results, immutable orchestration state, bounded
  path-safe warnings, and concise/verbose Frame Alignment output without changing
  offsets, trims, JSON, or HTML payloads; focused proof and the full local gate passed;
  100,000 synthetic summaries serialized at 0.416 microseconds each and parsed at
  2.237 microseconds each; CI was not run locally and environment-gated skips remain;
  Session E is ready.
