---
search:
  exclude: true
---

Status: Active
Scope: Redesign native VSView alignment review around viewer-recorded source positions and one whole-set decision
Owner: Maintainer-directed Frame Compare implementation session

# VSView Viewer-First Alignment UX Plan

## Goal

Make alignment feel like a viewer task instead of a form workflow. The operator
positions each actual source on the same visible moment in VSView, sees those source
positions and their resulting trims in the Frame Compare tool panel, and commits the
complete source set with one action.

Success means that a first-time operator can discover the panel, understand which
sources still need attention, obtain a trustworthy live offset preview, and finish a
three-or-more-source review without learning pair-confirmation mechanics. Manual input
and retaining the audio-derived alignment remain available as clearly secondary
whole-set paths.

This is a high-risk runtime/UI contract change. It modifies a generated VSView
workspace, a packaged plugin, a versioned metadata trust boundary, and Docker/Windows
proof surfaces. It does not change the CLI/config surface or alignment mathematics.

## Supersession and pre-cutover baseline

This plan supersedes the now-historical
[VSView-Native Alignment Review Plan](2026-08-31-vsview-native-alignment-review.md).
Only this file is active for the native alignment-panel UX workstream.

At plan creation, the repository contained the first native implementation:

- `session_script.py` loads every source with the Frame Compare-owned L-SMASH index
  policy, registers named outputs, and attaches strict versioned metadata;
- `alignment_review_contract.py` parses the workspace metadata and owns the UUID-bound,
  atomically written sibling result sidecar;
- `alignment_review_panel.py` is an inert-by-default VSView tool panel using public
  frame/output callbacks, seeking, and timeline notches;
- `alignment_vsview.py` validates the sidecar against authoritative raw source-frame
  counts, computes `reference - comparison`, and applies existing override policy;
- focused tests and Docker/Windows packaging proofs cover plugin discovery, offscreen
  construction, strict metadata/result handling, source loading, and result acceptance.

That pre-cutover generated workspace repeated the Reference output once per comparison,
and the panel asked the operator to capture or enter one pair, choose **Confirm pair** or
**Keep current offset**, repeat that decision, then choose **Finish review**. A manual
three-source trial found that this is discoverable only after experimentation and that
the multiple confirmation actions obscure the actual task.

No repository evidence records completion of the previous plan's visible physical-
Windows ergonomic acceptance. Treat it as unavailable, not complete, and perform the
new physical-Windows acceptance defined here before closing this plan.

## Fixed product decisions

- Alignment is performed in the VSView viewer. The right tool panel explains,
  mirrors, validates, and summarizes the work.
- The workspace contains each actual source exactly once: one `Reference` output and
  one `Comparison N` output per comparison, in source order.
- Viewer positions are the default input. Each source row shows its identity, latest
  recorded untrimmed source frame, input origin, readiness, relationship to the
  reference, and plain-language trim outcome.
- **Use these aligned positions** is the single primary whole-set action. It writes
  the complete result directly; there is no per-pair confirmation and no later
  finish step.
- **Keep audio-derived alignment** is a secondary whole-set action. It writes one
  ordered `keep_current` decision for every comparison and enters the same saved
  state. Its supporting text must say that it retains the alignment Frame Compare
  entered with, including the no-change case when no trusted suggestion exists.
- **Enter alignment manually...** is a permanent progressive-disclosure escape hatch,
  not an equal workflow shown by default.
- The first implementation uses public VSView 0.10.3 APIs only. It does not open or
  select the panel, select output tabs, change or inspect playhead synchronization,
  or read hidden per-output retained playheads.
- Clear generated-session/viewer guidance points to **Frame Compare Alignment Review**
  in the Tool Panel and tells the operator to unlink playheads before positioning
  sources. Upstream API enhancement is deferred polish and is not on the correctness
  or release critical path.

Do not reopen these decisions during implementation unless public API or source
evidence makes one impossible. If that occurs, stop and return to planning rather
than substituting private APIs or a second workflow.

## UX intent

The operator is comparing encodes at one-frame precision, usually immediately after
automatic audio alignment. They need to recognize the same cut or visible event in
several tabs, then trust how that observation changes source trims. The panel should
feel like a compact instrument attached to the viewer: calm, exact, keyboard-usable,
and honest about what it has and has not observed.

Domain concepts are playheads, source reels, sync marks, reference master, frame
stepping, slates, offsets, and shared visible moments. The color world remains the
host's grading-suite charcoal/monitor black/equipment grey, timecode white, cyan
reference/playhead cues, amber unresolved positions, and restrained green saved
state. Color reinforces but never carries status alone.

The signature is the **source lineup**: a live, ordered row for every actual source.
It replaces a generic form, a pair selector, and repeated reference tabs. The panel
uses the VSView Qt palette and typography, native controls, quiet borders/surface
separation, compact spacing, and no custom dashboard cards, modal wizard, decorative
theme, or floating window.

## Public VSView boundary and robust observation semantics

VSView 0.10.3 publicly exposes the complete output proxy list, the current output,
the current frame, output/frame callbacks, playback seeking, timeline notches,
`run_in_loop`, plugin shortcuts, and `set_output(..., **kwargs)` metadata. It does not
publicly expose panel selection, output-tab selection, sync-mode state/control, or all
retained per-output playheads.

The first implementation therefore uses this smallest honest model:

1. Panel activation starts a new in-memory draft with every source `Not visited`.
   Audio suggestions are displayed as suggestions; they do not mark a source ready
   or prefill the viewer-position draft.
2. While the panel is active and unsaved, each public current-output or current-frame
   callback records `api.current_frame` only for the current session output and marks
   that source `Ready`. The active row continues to update as the operator scrubs.
3. The initial active output becomes ready only through the normal public output/frame
   lifecycle after activation. Do not reach into the workspace to synthesize a visit.
4. Leaving a tab freezes the last frame observed for that source in the draft. Later
   callbacks for another output cannot mutate it. This snapshot is authoritative for
   the pending review even if VSView subsequently moves hidden linked playheads.
5. The panel instructs the operator to unlink playheads and visit every source tab
   after opening the panel. Because sync mode cannot be detected publicly, the panel
   does not claim to enforce this instruction.
6. In the default `positions` input basis, the primary action is enabled only when the
   Reference and every comparison have valid recorded frames. The preview for each
   comparison is `reference source frame - comparison source frame`.
7. A source revisited after becoming ready updates its draft frame and immediately
   recomputes all affected relationships. No per-row confirmation or dirty/confirmed
   state exists.
8. Hook-driven widget or marker changes remain marshalled through VSView's public
   `run_in_loop`. Only the Frame Compare timeline-notch group may be changed.

This explicit visit requirement is a product constraint, not a temporary hidden
workaround. A future public API that exposes all retained source playheads or sync mode
may remove the requirement after a separate product decision and proof pass.

## User journey

1. Frame Compare launches the generated session and prints bounded readiness guidance.
   Every output overlay includes one short, non-decorative direction to open **Tool
   Panel -> Frame Compare Alignment Review**; existing identity, audio hint, loading,
   index, color-default, and range diagnostics remain intact.
2. The opened panel leads with one instruction: unlink playheads, then visit each
   source and position it on the same visible moment. It reports the current `ready / N`
   source count rather than pair-completion status; only the initially visible output
   may already become ready through the public activation lifecycle.
3. The operator visits `Reference`, finds the sync moment, and leaves it there. Its
   row changes from `Not visited` to `Ready`, displays the current source frame, and is
   identified as the reference anchor.
4. The operator visits each `Comparison N` output and finds the same moment. Each row
   updates live and shows the signed relationship and trim meaning as soon as both it
   and the reference are ready.
5. The panel keeps unresolved rows visible and names the next action; it never moves
   the operator to another output or changes synchronization.
6. When the whole lineup is ready, the operator selects **Use these aligned
   positions** once. The panel writes one complete sidecar and immediately enters the
   saved state.
7. The operator closes VSView. Frame Compare strictly validates the result, applies
   the same offsets and precedence as today, persists through the existing owners,
   and continues.

Closing VSView before either whole-set action writes no result. Optional review keeps
the current alignment with an actionable diagnostic; forced review fails through the
existing typed interactive-alignment path.

## Manual and audio-derived alternatives

The collapsed manual disclosure uses the same whole-set draft and final action. It has
two explicit input bases; only one is active for the whole set at a time:

- `Source frames`: one non-negative untrimmed source-frame field per lineup row.
  Valid edits mark that row `Ready (manual)` and recompute the same relationships as
  viewer observation. Viewer callbacks may subsequently update an active row and mark
  its origin `Viewer`; no second manual result model is created.
- `Known offsets`: one signed integer per comparison using the existing
  `reference - comparison` convention. Every value immediately shows the equivalent
  trim in words. The whole set is ready only when every comparison has a valid value.
  To preserve the result schema, serialization converts each signed offset to the
  existing bounded canonical raw pair: positive uses `(offset, 0)`, negative uses
  `(0, abs(offset))`, and zero uses `(0, 0)`. Values whose canonical pair exceeds a
  public output clip bound are invalid in the panel and cannot be saved; the service
  still revalidates the same pair against the authoritative request bounds.

Switching input basis does not silently combine positions and offsets. Values may stay
in memory for convenience, but readiness, preview, and serialization come only from
the visibly selected basis. Returning to `positions` uses the current source-row
draft. There is no mixed per-comparison mode in this workstream.

The manual disclosure never writes a sidecar by itself. **Use these aligned
positions** remains the single commit action for both manual bases. **Keep
audio-derived alignment** bypasses draft readiness and atomically writes the complete
ordered `keep_current` result.

## Interaction and state contract

### Active unsaved states

- `Not visited`: no valid source frame has been observed or entered for the active
  positions basis.
- `Viewing`: the row corresponds to the current output; its frame updates live.
- `Ready`: a valid viewer-observed frame is frozen or active.
- `Ready (manual)`: a valid manual source frame supplies the row.
- `Needs attention`: invalid, empty, or out-of-range active-basis input blocks the
  primary action and carries a local correction message.
- `Manual offset`: known-offset basis is selected and that comparison has a valid
  signed value and trim preview.

The panel always shows the current input basis and `ready / total` status. Status text
and accessible names carry the meaning independently of color. The reference row has
no offset; each comparison row shows signed frames plus exactly one plain-language
outcome: trim reference, trim that comparison, or no starting trim.

### Primary and secondary actions

- **Use these aligned positions** is the sole primary action. It is disabled until
  the active basis is complete and valid. It never saves a partial subset.
- **Keep audio-derived alignment** is visually secondary but always available in an
  active valid session. It produces one `keep_current` decision for every comparison.
- Opening or editing manual fields never creates filesystem state.
- Repeated clicks after a successful save are impossible because all editing and
  action controls become read-only/disabled.

### Empty, inactive, error, and saved states

- Ordinary VSView workspace: `Inactive - not a Frame Compare alignment session`; no
  seek, marker, file write, output mutation, or source-row draft.
- Contract rejection: remain inactive and show a bounded sanitized reason without
  echoing untrusted values or paths.
- No trusted audio suggestion: show `Suggestion unavailable`; viewer/manual alignment
  and whole-set keep-current behavior remain available and honest.
- No source observed yet: show the ordered lineup with every row `Not visited` and an
  instruction to start with Reference.
- Invalid manual source frame or offset: preserve the entered text, show exact valid
  bounds/sign meaning, and disable the primary action.
- Sidecar write failure: keep all draft values editable, remain unsaved, and show a
  bounded actionable error. Do not disable controls or report success.
- Saved: show `Alignment saved - close VSView to continue Frame Compare`, retain the
  final lineup and trim summary read-only, disable both whole-set actions, and do not
  close VSView through private or global Qt state.

### Accessibility

- Preserve native Qt keyboard operation, visible labels, deterministic tab order,
  focus indicators, and one accessible name per row/input/action.
- The source lineup must be understandable in source order without relying on color,
  icon shape, hover, or timeline markers.
- The progressive disclosure and input-basis choice are keyboard-operable; changing
  basis moves no focus without an explicit operator action.
- Error text identifies the source/comparison and correction. Saving moves focus or
  an announcement to the saved status without trapping focus.
- Keep compact text wrapping and minimum-size behavior usable in VSView's normal right
  panel width and at Windows display scaling; do not require horizontal scrolling for
  names, frames, statuses, or trim explanations.

## Contract and cutover decision

### Output metadata: v1 clean replacement

The generated output topology changes before a supported release and has one active
tester, so metadata and results stay on one schema-v1 contract. Replace the earlier
pair shape directly; do not add a compatibility reader, migration, or fallback.

- Exactly one Reference output carries metadata version, session ID, role, and
  presentation name.
- Each comparison carries metadata version, the same session ID, role, presentation
  name, stable comparison key, contiguous comparison ordinal, and optional suggested
  offset.
- The parser requires exactly one reference, at least one comparison, unique output
  IDs/keys, contiguous ordinals, one session, strict role-specific fields, and source
  frame counts greater than zero.
- Repeated-pair workspaces are unsupported by the new panel and remain inert.
  Generated review sessions are disposable run artifacts; users regenerate them
  through Frame Compare.

The reference clip is loaded, prepared, and registered once. Comparisons retain source
order, `Comparison N` names, L-SMASH ownership/index behavior, AssumeFPS preview
behavior, overlays, color defaults, and all-or-nothing registration. A load or
registration failure still exposes no partial review workspace.

### Result sidecar: retain v1

The trusted result contract already represents the desired whole-set outcome: one
ordered decision per comparison, with either raw source frames or `keep_current`.
Keep result schema version 1 and its exact strict reader/writer.

- Positions basis emits the same shared reference frame with each comparison's
  recorded frame.
- Known-offset basis emits the bounded canonical raw pairs defined above.
- Keep-audio emits `keep_current` for every comparison.
- The service remains the authority that validates raw source-frame bounds and
  computes signed offsets. The panel does not write offsets, manual overrides, cache,
  config, or report state directly.

Because result v1 is unchanged, `alignment_vsview.py`, manual override schema,
alignment reuse schema, cache identity, provenance, precedence, warning policy, and
numeric error behavior should require no production change. If implementation finds
that one of those owners must change, stop and re-evaluate the boundary before adding
another parser, state machine, or compatibility path.

## Preserved invariants

- Signed offset is always `reference source frame - comparison source frame`:
  positive trims reference, negative trims comparison, zero trims neither.
- Raw source-frame bounds from `AlignmentClipRequest.source_frame_count` remain the
  final authority; public output clip lengths are only panel-side guidance.
- Session identity, exact result sibling path, regular-file containment, strict field
  sets/types, ordered complete comparison set, boolean rejection, and atomic writes
  remain fail closed.
- Optional review retains current alignment on unavailable/missing/invalid result;
  forced review fails. An explicit all-comparison `keep_current` result is success.
- Existing alignment precedence, run-local manual override persistence, shared reuse
  eligibility, source loading, owned indexes, source order, comparison ordinals,
  color/range behavior, JSON-mode rejection, non-TTY guard, and child-process policy
  remain unchanged.
- The plugin stays inert in ordinary workspaces and mutates only its own timeline
  marker group in valid active sessions.
- CLI flags, config fields, success JSON, error codes, dependencies, runtime
  fingerprint, and package entry point do not change.

## Ownership and architecture disposition

Use the existing owners and fewest files. No new production module is justified.

| Owner | Existing responsibility | New behavior | Disposition |
| --- | --- | --- | --- |
| `frame_compare.vsview.alignment_review_panel` | Native panel lifecycle, public VSView hooks, draft decisions, markers, and sidecar save | Source-lineup draft, whole-set actions, manual disclosure, state/accessibility behavior | Cohesive replacement inside the existing owner; delete pair workflow while adding lineup behavior |
| `frame_compare.vsview.alignment_review_contract` | Strict typed workspace/result trust boundary and atomic sidecar | Schema-v1 one-reference metadata and whole-set result topology | Cohesive contract replacement; retain one version constant and one parser |
| `frame_compare.vsview.session_script` | Deterministic generated script, source preparation/loading, output registration, diagnostics | Register Reference once, attach role-specific metadata, improve panel discovery guidance | Cohesive generated-session change; no new generator owner |
| `frame_compare.services.alignment_vsview` | Result acceptance, authoritative bounds, offset/override policy | No intended production change | Verify compatibility through its public result seam |
| Docker/Windows verifier owners | Real packaged integration proof | Assert one-reference topology and whole-set result behavior | Update only the existing proofs and their contract tests |

`alignment_review_panel.py` and `session_script.py` are above 500 physical production
lines and are named hotspots. The implementer must inspect both full owners, favor
deleting obsolete pair-selector/confirmation code, and record the final cohesive-
growth disposition in the handoff. Do not extract for line count or test access. A
new owner is permitted only if implementation discovers a distinct trust boundary or
lifecycle not already present; that is a stop-and-review event, not an automatic refactor.

Respect `importlinter.ini`: services may consume the dependency-light VSView contract,
while `frame_compare.vsview` must not import service/orchestration state. Preserve lazy
PySide6/VSView loading through the existing plugin entry point and adapter boundaries.

## Likely implementation write surface

Production owners:

- `src/frame_compare/vsview/alignment_review_panel.py`
- `src/frame_compare/vsview/alignment_review_contract.py`
- `src/frame_compare/vsview/session_script.py`

Focused behavior and integration proof:

- `tests/vsview/test_alignment_review_panel.py`
- `tests/vsview/test_alignment_review_contract.py`
- `tests/vsview/test_adapter.py`
- existing service workflow/result tests if assertions need the new whole-set fixture
- `tools/verify_docker_gui.sh`
- `tests/workflows/test_docker_gui_contract.py`
- `tools/windows_portable/build_portable.ps1`
- `tests/windows_portable/test_windows_portable_build_scripts.py`

Authority and user guidance updated in the same implementation pass:

- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- `docs/guides/audio-alignment.md`
- `docs/guides/troubleshooting.md`
- `docs/windows-portable.md`

Do not change `pyproject.toml`, `uv.lock`, runtime/component manifests, Docker base
images, config schema, CLI override map, or import layers unless contrary source
evidence triggers a stop condition. No custom viewer, new dependency, generic UI/state
framework, plugin API adapter, duplicate result owner, config knob, IPC, file polling,
or upstream VSView change belongs in this plan.

## Execution packages and dependency order

### Package 1 - Freeze metadata topology and result compatibility

1. Keep one schema-v1 constant for alignment-review metadata and results.
2. Define and test strict v1 metadata for one Reference plus ordered comparisons,
   including empty, missing/extra reference, duplicate, mixed-session, bad ordinal,
   unexpected-field, unsupported-version, and invalid-bound cases.
3. Retain result v1 byte/semantic shape and prove existing confirmed/keep-current,
   strict JSON, order, session, path, atomic-write, and authoritative-bound tests still
   pass.
4. Update the deterministic generated session to prepare all clips before registering
   Reference once and each comparison once. Preserve all-or-nothing failure, source
   order, overlay/index/color behavior, and deterministic-body/UUID-filename rules.
5. Add the concise Tool Panel direction to existing generated overlays and readiness
   diagnostics without introducing a new guide screen or output.

Package 1 and Package 2 are an inseparable product cutover: do not release the
one-reference generator with the old pair panel or the new panel against repeated-pair generation.

### Package 2 - Replace pair review with the source lineup

1. Replace the pair selector, per-pair decision state, capture/confirm actions, and
   finish action with the fixed lineup and observation semantics above.
2. Show reference anchor, current output, recorded frame/origin/readiness, signed
   relationship, and plain-language trim for every source without duplicating the
   reference visually.
3. Implement the two manual input bases as a collapsed native-Qt disclosure feeding
   the same draft and the same final result encoder.
4. Implement both whole-set actions, save-failure recovery, read-only saved state,
   inactive/contract-error/empty/unavailable states, and deterministic keyboard/focus
   behavior.
5. Keep public callback/event-loop handling and the owned timeline marker behavior;
   remove obsolete pair-selector, pair-confirmation, and finish code/tests rather than
   leaving disabled compatibility branches.

### Package 3 - Integrate proof and authority surfaces

1. Update focused panel/contract/session tests through stable behavior rather than
   private widget fields, call-order assertions, or layout snapshots. Use isolated
   temporary session/result paths and the existing offscreen Qt runtime; add no
   `pytest-qt` dependency.
2. Extend Docker GUI proof to cover the schema-v1 one-reference topology, panel
   inert state, complete source readiness, whole-set save, keep-audio save, strict
   result round trip, and malformed-result rejection.
3. Extend the Windows portable offscreen proof for the same packaged plugin and
   generated-session behavior. Keep runtime versions, entry point, source loader, and
   fingerprint unchanged.
4. Update current architecture, current CLI contract, alignment guide,
   troubleshooting, and Windows portable guidance to remove every `Confirm pair`,
   pair-selector, repeated-Reference, and `Finish review` instruction.
5. Run the complete proof matrix, inspect the diff/stale-symbol search, adjudicate one
   independent final review, and record unavailable host proof honestly.

## Acceptance criteria

- A generated three-source workspace exposes exactly `Reference`, `Comparison 1`, and
  `Comparison 2` in source order; Reference is loaded/registered once.
- The panel is inactive and side-effect free in an ordinary or rejected workspace.
- On activation every source is `Not visited`; visiting/scrubbing one output updates
  only its row, and leaving it freezes the last publicly observed frame.
- The primary action stays disabled until every source is ready in positions basis or
  every comparison offset is valid in known-offset basis.
- A ready three-source lineup previews both signed offsets and exact trim meanings,
  and one primary click writes a complete ordered result with no pair confirmation or
  finish step.
- Manual source-frame entry and known-offset entry are hidden by default, validate
  exact bounds/types/sign, immediately explain trim meaning, and use the same save
  action and v1 sidecar.
- **Keep audio-derived alignment** writes all comparisons as `keep_current` in one
  action and reaches the same saved state.
- Result v1 remains strict and service validation produces the same offsets,
  persistence, provenance, precedence, and optional/forced behavior as the baseline.
- Invalid input and save failures remain editable and unsaved; successful save is
  read-only and clearly directs the operator to close VSView.
- Generated guidance makes the panel and unlink/visit workflow discoverable without
  private auto-open/tab/sync behavior.
- Output overlays, L-SMASH indexes, source bounds, frame numbering, comparison order,
  color/range defaults, lazy imports, JSON stdout, and unattended safety do not regress.
- No stale `Confirm pair`, pair-selector, repeated-Reference, or `Finish review`
  behavior remains in production, tests, active authority docs, user guidance, or
  packaged proof scripts.
- No dependency, config, new production module, compatibility reader, private VSView
  access, or upstream API requirement is introduced.
- Full local, Docker GUI/offscreen where available, hosted Windows, and visible
  physical-Windows proof is recorded; unavailable proof is named rather than inferred.

## Verification record

```text
VERIFICATION_RECORD
RISK: high
PRIMARY_MODE: integration
RATIONALE: this changes a hotspot native UI, generated output topology, strict
metadata trust boundary, result creation workflow, and Docker/Windows packaged proof,
while preserving public alignment, persistence, and runtime contracts.
TEST_DECISION: update existing contract/integration coverage; add only focused cases
for source readiness, whole-set actions, manual bases, and topology that are not
already expressible through current tests.
COMMANDS_AND_EXPECTED_OUTCOMES:
1. Focused owner proof:
   uv run --no-sync pytest -q tests/vsview/test_alignment_review_contract.py tests/vsview/test_alignment_review_panel.py tests/vsview/test_adapter.py tests/services/test_alignment_vsview.py tests/services/test_alignment_workflow_vsview.py
   Expected: schema-v1 topology, whole-set panel behavior,
   and downstream offset acceptance all pass.
2. Packaging/workflow contract proof:
   uv run --no-sync pytest -q tests/workflows/test_docker_gui_contract.py tests/windows_portable/test_windows_portable_build_scripts.py tests/test_cli_contract_docs.py
   Expected: verifier, portable, and authority assertions match the new workflow.
3. Runbook full gate:
   uv run --no-sync pyright --warnings
   uv run --no-sync ruff check .
   uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
   uv run --no-sync pytest -q
   uv run --no-sync lint-imports --config importlinter.ini
   Expected: all commands pass with no warning suppression or unrelated-test waiver.
4. Canonical Docker runtime:
   bash tools/verify_docker_integration.sh
   Expected: the unchanged headless media runtime and source paths pass.
5. Linux X11 GUI integration, on a compatible host:
   bash tools/verify_docker_gui.sh
   Expected: real L-SMASH media, packaged plugin discovery, one-reference output set,
   offscreen panel/result contract, cleanup, and visible launch instructions pass.
6. Native Windows portable, on Windows:
   pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/validate_update_public_key.ps1 -PublicKeyPath tools/windows_portable/update_public_key.xml
   pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir dist/frame-compare-portable-win-x64 -CacheDir .portable_cache
   dist/frame-compare-portable-win-x64/frame-compare.ps1 doctor --json
   Expected: the full bundle builds, entry point and offscreen panel/session/result
   proof pass, and doctor reports the pinned VSView/panel available.
7. Hosted Windows exact-SHA verification:
   dispatch .github/workflows/windows-portable.yml with operation=verify and the
   runbook's protected-ref expected_sha inputs; record workflow URL, exact SHA,
   conclusion, and artifacts. Use:
   WorkflowRef='<branch-containing-the-workflow>'
   ExpectedSha='<40-character-lowercase-head-sha-of-WorkflowRef>'
   gh workflow run windows-portable.yml --ref "$WorkflowRef" -f operation=verify -f channel=rc -f expected_sha="$ExpectedSha"
   gh run list --workflow windows-portable.yml --limit 1
   Expected: the secret-free full portable/offscreen proof succeeds.
8. Physical Windows manual proof:
   run one terminal-attached optional and one forced three-source session on the
   portable runtime. Prove panel discovery, unlink guidance, each-tab readiness,
   viewer scrubbing, both signed trim directions, manual frame basis, known-offset
   basis, keep-audio whole-set action, save failure recovery where safely inducible,
   close-without-save, downstream override application, render/report continuation,
   keyboard-only operation, 125%/150% display scaling, and an ordinary inert VSView
   workspace. Record exact bundle/version, media fixture identity, outcomes, and a
   current provenance-recorded capture.
UNAVAILABLE_OR_DOCUMENTED_ONLY_PROOF: Linux X11 GUI execution when no compatible X11
host is available; physical-Windows ergonomics until performed on a real Windows
desktop; native macOS L-SMASH proof when core.lsmas is absent. Offscreen Qt, source
inspection, hosted Windows, or macOS synthetic proof must not be described as a
substitute for the missing physical platform.
```

A code-only update build/sign/apply cycle is not required for this source/UI change
because updater logic, dependency graph, and the media-runtime fingerprint are fixed
non-changes. If implementation changes any of those surfaces, stop and reclassify the
Windows proof through the runbook rather than silently expanding this exception.

Also run `git diff --check`, inspect the complete diff, and search active code/docs for
`Confirm pair`, `Finish review`, repeated reference registration, obsolete pair
decision state, private VSView workspace/tab/sync access, and new dependency/config
drift. A full suite does not replace the focused owner or physical UX proof.

## Independent final review

One fresh read-only reviewer is required after implementation and proof because the
change touches named hotspots above 500 lines and a filesystem/runtime trust boundary.
Give the reviewer the final diff, this plan, focused/full/Docker/Windows records, and
the physical-proof status without the implementation transcript. The review must
cover:

- cohesion versus accidental panel/session hotspot growth;
- public-only VSView API and event-loop/thread correctness;
- schema-v1 metadata/result strictness, path containment, atomicity, and raw bounds;
- no duplicate draft/result/parser owner or hidden pair workflow;
- source loading/index/color/order and optional/forced alignment invariants;
- keyboard, focus, error, saved, narrow-panel, and Windows scaling behavior;
- Docker/Windows verifier honesty and stale authority/user guidance.

Adjudicate every material finding and rerun affected focused proof. A second reviewer
is needed only after a material architecture/contract change, not for unchanged
closure ceremony.

## Risk and mitigations

| Risk | Mitigation |
| --- | --- |
| Hidden playheads are mistaken for readable state | Record only current public callbacks; require every tab to be visited after activation; never infer hidden frames |
| Linked mode yields a plausible but unintended lineup | Persistent unlink guidance plus explicit whole-set confirmation; do not pretend to detect or change sync mode |
| One-reference topology weakens strict pairing | Schema-v1 metadata has exactly one reference and strict ordered comparison keys/ordinals; result remains complete and ordered |
| Manual known offsets bypass raw-bound validation | Convert to canonical raw pairs, validate against public guidance bounds in panel and authoritative request bounds in service |
| UI redesign duplicates state or expands architecture | Replace pair draft in the current panel owner; retain one result writer/parser; no framework/module/dependency |
| Save or close creates partial evidence | Atomic complete write only from a whole-set action; failure stays editable; close without save writes nothing |
| Packaged UI differs from offscreen tests | Existing Docker/Windows packaged proofs plus required visible physical-Windows acceptance and scaling checks |
| Docs continue teaching old controls | Same-pass authority/user-guide updates plus stale-text search before closeout |

## Rollback

Rollback the viewer-first cutover as one unit: panel lineup/manual-basis changes,
schema-v1 parser, single-reference generated topology, discovery text, tests,
verifiers, and authority/user guidance. Restore the last accepted pair-panel code and
generator together. Alignment service, manual override/cache state, config, and
dependencies require no data rollback because this plan intentionally leaves them unchanged.

Do not ship a mixed rollback containing the one-reference generator with the old panel,
or the new panel with repeated-pair metadata. Existing generated session scripts/results are run
artifacts and may be discarded and regenerated; do not add migration code.

## Stop conditions

Stop implementation and return to planning if:

- reliable source readiness requires private VSView workspace, tab, panel, or sync
  state, or public callbacks cannot identify the active source/frame;
- one-reference registration changes source loading, frame numbering, comparison
  order, color/range behavior, or all-or-nothing session construction;
- whole-set output cannot be represented by the existing strict result-v1 decision
  set without weakening authoritative raw-frame validation;
- manual offset normalization cannot preserve the signed trim contract and source
  bounds without a result schema change;
- implementation requires changing alignment precedence, cache identity/schema,
  manual override persistence, config, CLI/JSON behavior, dependencies, entry point,
  runtime fingerprint, or import layers;
- a new production owner or generic API abstraction appears necessary;
- Docker, hosted Windows, or physical Windows reveals a product/UX decision not
  frozen here, including unusable normal panel width or display scaling;
- stale result/session behavior would require a compatibility reader rather than
  regeneration.

An upstream request for public panel selection, tab selection, retained per-output
playheads, or sync-mode state may be filed after this implementation. It must not delay
or weaken this plan, and adopting a future API requires its own compatibility and
verification decision.

## Closeout

Before marking this plan historical, update all current authority/user docs, record
the complete verification matrix and unavailable proof, inspect the diff, close the
independent review, and obtain the required visible physical-Windows acceptance. If
that platform proof remains unavailable, leave this plan Active and report the exact
remaining handoff rather than calling the UX complete.
