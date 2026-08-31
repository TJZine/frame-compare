---
search:
  exclude: true
---

Status: Active
Scope: Replace terminal frame-pair confirmation with a Frame Compare-owned VSView alignment-review panel and session-result contract
Owner: Maintainer-directed Frame Compare implementation session

# VSView-Native Alignment Review Plan

## Purpose

Turn the completed VSPreview-to-VSView parity migration into a better Frame Compare
alignment workflow. Operators must inspect, enter, and confirm matching source frames
inside VSView. Frame Compare must consume that decision after VSView closes without a
second terminal prompt.

This is a follow-up workstream, not an expansion of the viewer-migration pull request.
Implementation starts from the merged and stabilized VSView-only baseline. The active
[VSView migration plan](2026-08-30-vsview-migration.md) remains the authority for its
remaining release, clean-machine, and distribution-compliance gates.

## Baseline and parity disposition

The current VSView integration preserves the Frame Compare feature set of the final
VSPreview implementation:

- audio-derived offset calculation and the `reference - comparison` sign convention;
- untrimmed source-frame inspection;
- reference/comparison ordering and multi-comparison sessions;
- suggested-offset and trim-direction overlays;
- L-SMASH source loading, owned indexes, color defaults, and range policy;
- confirmation-derived manual overrides, skip behavior, and alignment precedence;
- optional versus forced launch behavior and existing JSON/non-interactive policy.

VSView additionally supplies documented named outputs, synchronized output tabs,
frame/time navigation, plugin panels, output metadata, frame/output-change hooks,
programmatic seeking, and timeline notches. Frame Compare currently uses only named
outputs. This plan adopts the plugin, metadata, frame, seeking, and timeline surfaces.

The implementation must use public VSView 0.10.3 APIs only:

- [User API](https://jaded-encoding-thaumaturgy.github.io/vs-view/api/user/)
- [Plugin development](https://jaded-encoding-thaumaturgy.github.io/vs-view/plugins/development/)
- [Workspace and timeline behavior](https://jaded-encoding-thaumaturgy.github.io/vs-view/usage/workspaces/workspace/)

## Product decision

The VSView panel becomes the only frame-pair confirmation interface. Remove the
terminal pair-entry parser, prompt loop, confirmation header/footer, and their tests
in the same cutover. Do not retain a hidden fallback, compatibility flag, second
result parser, or dual confirmation state machine.

The final operator flow is:

1. Frame Compare launches a generated VSView session.
2. The operator opens the Frame Compare tool panel when VSView has not retained it as
   visible; the panel presents each comparison and its audio-derived suggestion.
3. The operator navigates the existing named output tabs and inspects matching frames.
4. The operator captures or directly enters the reference and comparison source
   frames, confirms the pair, or keeps the current offset for that comparison.
5. Finishing the review writes one complete session result.
6. The operator closes VSView.
7. Frame Compare validates the result, computes confirmed offsets, persists them
   through the existing manual-override owner, and continues the run.

Closing VSView without finishing the review makes no alignment changes. Optional
review continues with the current computed or cached offsets and reports that no
review result was accepted. Forced interactive mode still requires a working VSView
and Frame Compare panel; it does not require the operator to change an offset.

## UX intent

### Human and task

The operator has just asked Frame Compare to align multiple encodes or releases. They
are checking exact source-frame correspondence, often at one-frame granularity, and
need confidence in the offset before the render and report continue. The interface
should feel like a precise instrument already belonging to VSView: compact, calm,
keyboard-usable, and explicit about every sign and frame number.

### Domain exploration

- source frames and playheads;
- reference versus comparison roles;
- audio-derived suggestions;
- trim direction and signed offsets;
- synchronized and unlinked inspection;
- per-comparison decisions;
- confirmed versus unchanged alignment.

### Color world

The panel inherits VSView's Qt palette and typography rather than introducing a
second visual system. Domain color is limited to semantic accents already natural to
the viewer: timeline graphite, playhead red, reference blue/cyan, comparison amber,
confirmed green, and warning amber. Every status also has text and an icon or label;
color is never the sole carrier of meaning.

### Signature interaction

The identifying element is the live frame-pair equation:

`Reference 120 - Comparison 108 = +12 frames`

It updates from direct numeric entry or captured output frames and always pairs the
result with plain-language trim direction. This is the primary information hierarchy,
not a generic form summary.

### Rejected defaults

- No dashboard cards: use one dense review tool panel organized around the equation.
- No wizard or modal sequence: keep VSView's output tabs and timeline visible during
  every decision.
- No decorative custom theme: use native Qt/VSView controls and host palette.
- No automatic private tab switching: the operator uses VSView's existing tabs.
- No plugin settings screen: this workflow has no user-tunable settings in v1.

## Panel behavior

### Activation

Package the panel with Frame Compare and register it through VSView's standard Python
entry-point group. Pinned VSView globally registers installed tool panels and exposes
no public conditional visibility API, so a dormant Frame Compare panel may be present
in ordinary VSView workspaces. Its review contents activate only when the loaded
outputs contain a complete, supported Frame Compare session metadata contract.

Do not manipulate the host panel/tab container to auto-open, hide, or select the
panel. The operator opens it through VSView's normal Tool Panel control when it is not
already visible. Generated-session guidance must name that action clearly.

The supported runtime must launch VSView from the same Python environment as Frame
Compare so the plugin entry point is provably present. A PATH-only VSView executable
from an unrelated Python environment is no longer sufficient for interactive Frame
Compare alignment. Availability and doctor guidance must direct users to the pinned
`frame-compare[vsview]` environment.

Do not create a separately versioned plugin distribution or add a dependency. Keep
the plugin inside `frame_compare.vsview`; PySide6 and VSView imports remain lazy and
occur only when VSView discovers the plugin.

### Information hierarchy

The panel contains, in order:

1. the active comparison selector and completion status for all comparisons;
2. reference and comparison presentation names;
3. the audio-derived suggested pair and trim direction, or an explicit unavailable
   state;
4. editable non-negative reference and comparison source-frame controls;
5. the live signed frame-pair equation and trim explanation;
6. context-aware capture and seek actions;
7. `Confirm pair` and `Keep current offset` decisions;
8. one final `Finish review` action after every comparison has a decision.

Use VSView's current-output and current-frame hooks to show which output/frame will be
captured. `Capture current frame` fills the reference or comparison field according
to the active output metadata. `Go to suggested frame` seeks only the active output
frame domain through the public playback proxy. The seek is workspace-level and may
move linked outputs according to the operator's existing VSView sync mode. Frame
Compare must respect that mode; it must not switch tabs, change synchronization, or
access private workspace objects.

VSView documents output/frame hooks as running on the main or a background thread.
Any hook-triggered widget, control-state, or timeline-notch mutation must marshal to
the Qt event loop through VSView's public `run_in_loop` facility. Contract/model work
may remain thread-independent; do not update Qt widgets directly from an unspecified
hook thread.

The suggested frame pair follows the existing sign convention:

- positive offset: suggested reference frame is the offset and comparison frame is 0;
- negative offset: suggested reference frame is 0 and comparison frame is the
  absolute offset;
- zero: both frames are 0;
- unavailable: both fields remain unset until captured or entered.

Changing either field clears a previously confirmed decision for that comparison.
Confirmation is enabled only when both frames are valid for their corresponding
outputs. `Keep current offset` records an explicit skip and does not manufacture a
confirmed offset. The direct-entry controls derive their inclusive maximum from each
public `VideoOutputProxy` clip length rather than from the suggested offset.

### Timeline markers

Use the public timeline-notch API to mark the relevant suggested frame for the active
output. Refresh only the Frame Compare notch group when the active output changes.
Do not clear or mutate markers owned by VSView or another plugin.

The marker label identifies the comparison and whether it is the suggested reference
or comparison frame. No additional scene-detection, report-frame, or correlation-
window marker system belongs in this first version.

### Accessibility and failure states

- Every control has a visible label and deterministic tab order.
- All actions are keyboard-operable using native Qt behavior.
- Invalid or out-of-range frame values produce local text errors and cannot be
  confirmed.
- Completion states use text in addition to semantic color.
- The panel distinguishes `confirmed`, `keeping current`, `not reviewed`, and
  `result saved`.
- After `Finish review`, make the controls read-only and tell the operator to close
  VSView so Frame Compare can continue.
- Do not close the application through private VSView state or global Qt tricks.

## Session metadata contract

Extend each generated named output with Frame Compare-specific metadata through
documented `set_output(..., **kwargs)` arguments. The plugin discovers all pairs from
`PluginAPI.voutputs`; no second request file or plugin-global registry is needed.

The metadata contract is versioned and contains only the values required by the
panel:

- contract version and unique session identifier;
- stable alignment key and comparison ordinal;
- output role (`reference` or `comparison`);
- presentation name;
- suggested signed offset, including an explicit unavailable state.

The repeated reference outputs remain paired with their corresponding comparison so
existing output order and tab behavior do not change. Source paths, media
fingerprints, full probe payloads, credentials, and unrelated run configuration must
not be copied into plugin metadata.

The plugin treats malformed, incomplete, mixed-session, or unsupported-version
metadata as non-Frame-Compare content and stays inert. A host-visible inactive panel
may identify that the workspace is not a Frame Compare session, but it must not write
files, add markers, seek, or mutate workspace state. Frame Compare's startup/readiness
proof must verify that its registered plugin is discoverable before launching the full
session.

The generated session is all-or-nothing for review. If any expected comparison cannot
be found, loaded, or registered, the session fails instead of exposing a partial set
that cannot satisfy the result contract. Optional review then retains every current
offset; forced review fails through its existing typed error path. Do not invent a
partial-result or automatically skipped-missing-output policy.

## Session-result contract

Use one JSON sidecar whose path is derived deterministically from the unique generated
session script. Every generated script filename receives an always-present UUID token
in addition to its readable timestamp. The script derives the session identifier at
runtime from its own filename, so the generated body remains byte-identical for the
same inputs; do not serialize a random identifier into the body.

The plugin derives the sidecar only from the public `PluginAPI.file_path` and a Frame
Compare-owned result suffix; a missing file path leaves the plugin inert, and output
metadata must never supply an authoritative writable path. Frame Compare independently
derives the same session identifier and expected sibling path from the script path it
created. The result is a run artifact, not a reusable cache or user configuration.

The generated script must be an expected regular file contained by the owned
`vsview_sessions` directory, and the derived result path must initially be absent and
remain in that directory. After launch Frame Compare reads only that exact path and
rejects a symlink, non-regular file, or path outside the owned directory.

The result contains:

- schema version and exact session identifier;
- one ordered decision for every expected comparison key;
- for a confirmed decision, the raw non-negative reference and comparison source
  frames;
- for an unchanged decision, an explicit `keep_current` action.

Write the complete result atomically only when the operator finishes the review. Do
not persist partial decisions after each click. Use the repository's existing atomic
write mechanism and the standard library JSON implementation; do not add IPC,
sockets, a local server, file polling, locks, or a serialization dependency.
If the write fails, keep the review editable, show a bounded error in the panel, and
do not enter the `result saved` state.

After VSView exits, the alignment service owns result validation. It must reject the
entire sidecar when the schema, session identifier, comparison order/set, action,
integer type, non-negative constraint, or expected path is invalid. Booleans are not
valid integer frames. It must also check both frames against expected source-frame
bounds supplied from the already-prepared clip facts, not values echoed by the plugin
or sidecar. Add authoritative untrimmed source-frame counts to the typed alignment
clip request as runtime validation facts; they must not silently become new shared
cache identity inputs. Unknown fields may be ignored only if the schema version
explicitly permits them; v1 should otherwise be strict.

The alignment service—not the plugin—computes each confirmed signed offset as
`reference_source_frame - comparison_source_frame`. It then uses the existing manual
override and alignment-provenance owners. The plugin must never write
`manual_overrides.toml`, the shared reuse cache, config, or report state directly.

Missing, invalid, or unreadable result behavior:

- optional interactive review: warn once and retain current offsets;
- forced interactive review: raise the existing typed interactive-alignment failure
  after the viewer closes, because the required Frame Compare confirmation surface
  did not return a valid result;
- an explicit valid `keep_current` decision is successful in either mode.

Do not retain an invalid result as accepted evidence. Preserve it only when existing
generated-artifact policy already retains the containing run folder; diagnostics must
not echo arbitrary file contents.

## Public behavior changes

- Successful review no longer emits terminal confirmation prompts or reads stdin.
- VSView itself contains all frame entry, confirmation, and skip actions.
- The terminal still reports bounded launch, ready, accepted-result, invalid-result,
  and unchanged-offset diagnostics on stderr.
- JSON-mode interactive alignment remains rejected; JSON stdout remains JSON-only.
- Preserve the existing non-TTY launch guard for this CLI-first application. Removing
  stdin reads does not authorize surprise GUI launch from unattended jobs.
- Existing `audio_alignment.use_vsview`, `force_interactive`, manual-override schema,
  offset precedence, numeric error codes, and cache provenance remain unchanged.
- A supported Frame Compare VSView installation now requires the plugin and VSView in
  the same Python environment; remove the unprovable external-executable fallback.

Update `docs/current-cli-contract.md`, `docs/current-architecture.md`, user guidance,
doctor text, generated API documentation when affected, and focused contract tests in
the same pass.

## Ownership and likely write surface

| Concern | Owner |
| --- | --- |
| VSView plugin UI and public VSView API interaction | `frame_compare.vsview` focused plugin owner |
| Generated output metadata and session/result paths | existing `frame_compare.vsview.session_script` owner plus a focused result-contract owner if validation would otherwise mix UI and persistence |
| Launch, same-environment availability, and plugin readiness | existing `frame_compare.vsview.adapter` and managed launcher |
| Result acceptance, offset computation, optional/forced policy, and manual-override coordination | existing `frame_compare.services.alignment_vsview` |
| Expected source-frame bounds | existing prepared clip facts passed as authoritative untrimmed frame counts through the typed alignment request; do not re-probe media in the plugin or result reader, and do not change cache identity |
| Atomic filesystem mechanics | existing `frame_compare.utils.atomic_write` |
| Plugin registration and optional dependency contract | `pyproject.toml` and lock/package contract tests |
| CLI diagnostics and public behavior documentation | existing CLI output owner and authority docs |
| Docker and Windows packaged proof | existing GUI/runtime and Windows portable verifiers |

Do not create a generic viewer interface, plugin framework wrapper, message bus,
repository class, or result service with one caller. Extract a result-contract module
only if it owns the distinct versioned trust boundary and keeps Qt/VSView imports out
of the alignment service.

## Non-goals

- Change audio extraction, correlation, consensus, cache keys, or offset precedence.
- Change Frame Compare source loading from L-SMASH to BestSource.
- Add VSView `recommended` or `full` extras.
- Control VSView tab selection or synchronization through private APIs.
- Add audio A/B output, diff/blink clips, native-HDR defaults, scopes, or generalized
  color analysis in this workstream.
- Add report-selected frames, scene markers, or correlation-window visualization.
- Preserve PATH-only VSView environments that cannot load the Frame Compare plugin.
- Preserve terminal confirmation as a fallback.
- Redesign VSView or ship a custom visual theme.

Audio A/B review, aligned diagnostic outputs, and richer color/HDR diagnostics remain
candidate follow-up specifications after the panel/result seam has native proof.

## Execution sequence

### 1. Freeze the contract

- Define the minimal versioned output metadata and result schema.
- Change generated script naming to include an always-present UUID token; derive the
  runtime session identity and sidecar name from that filename while preserving the
  deterministic-body invariant.
- Add pure contract tests for complete, skipped, missing, malformed, mixed-session,
  out-of-range, and filesystem-failure cases.
- Add authoritative untrimmed source-frame counts to the typed alignment request and
  prove they validate results without changing shared alignment-cache identity.
- Prove the packaged Frame Compare entry point is discoverable by pinned VSView.

### 2. Build the native review panel

- Register one inert-by-default VSView plugin inside the existing distribution.
- Implement the compact frame-pair panel with native Qt/VSView controls.
- Consume only public output/frame/playback/timeline APIs.
- Marshal every hook-driven widget or timeline mutation through public
  `run_in_loop`.
- Add focused model/controller tests without introducing `pytest-qt`; use the already
  installed PySide6 runtime for the smallest offscreen widget smoke proof.

### 3. Cut over alignment confirmation

- Pass the session metadata on every named output.
- Make generated review sessions fail closed when any expected comparison cannot load
  or register; do not accept a partial output set.
- Read and validate the completed sidecar after VSView closes.
- Route confirmed raw pairs through existing offset and persistence owners.
- Delete terminal prompt parsing, pair-entry output helpers, imports, and tests in the
  same commit or inseparable commit series.
- Remove external-executable fallback and update availability/doctor behavior.

### 4. Reconcile public contracts and local proof

- Update current architecture, CLI contract, user guidance, troubleshooting, and
  relevant generated documentation.
- Run focused plugin, result, session, alignment, CLI, doctor, package, and stale-code
  tests.
- Run the runbook full gate because alignment, VSView, persistence, CLI behavior, and
  package entry points change.
- On macOS, prove a visible or offscreen synthetic multi-output session can load the
  panel, capture/edit/confirm/keep decisions, write the sidecar, and continue without
  terminal input. Record real L-SMASH GUI proof as unavailable if the host plugin is
  absent rather than substituting BestSource.
- Run the canonical Docker integration gate and extend the GUI verifier to prove
  plugin discovery, Frame Compare metadata, result writing, and result validation.

### 5. Windows acceptance

- Extend hosted Windows portable proof to verify the packaged entry point, plugin
  import, offscreen panel construction, sidecar round-trip, and absence of terminal
  confirmation symbols.
- On the physical Windows machine, run a visible terminal-attached multi-comparison
  session through suggestion, manual entry, current-frame capture, confirmation,
  `keep_current`, finish, close, downstream offset application, render, and report.
- Verify timeline markers, keyboard operation, invalid/out-of-range handling, close
  without finish, optional invalid-result fallback, forced invalid-result failure,
  clean child exit, and a non-Frame-Compare VSView script where the plugin stays inert.
- Re-run the affected complete portable/update proof if the packaged dependency or
  runtime fingerprint changes. A Python-only code change may use the documented
  code-only path only when the existing fingerprint contract permits it.

## Verification record

```text
VERIFICATION_RECORD
RISK: high
PRIMARY_MODE: integration
RATIONALE: the change replaces a public interactive confirmation surface, adds a
versioned filesystem trust boundary, registers a VSView plugin, and changes native
runtime availability and packaged GUI behavior.
TEST_DECISION: add and update
COMMANDS_AND_EXPECTED_OUTCOMES: focused contract/plugin/alignment/CLI/package tests;
runbook full gate; macOS synthetic VSView proof; canonical Docker integration and GUI
proof; hosted and physical Windows plugin/result acceptance.
UNAVAILABLE_OR_DOCUMENTED_ONLY_PROOF: native macOS L-SMASH media proof when the host
plugin is absent; visible Linux X11 behavior without a compatible host; native Windows
manual behavior until the physical acceptance pass.
```

Tests must assert behavior rather than Qt layout snapshots. The primary regression
proof is that a valid plugin result produces the same signed offset and persisted
manual override as the removed terminal frame pair, while no code path reads stdin.

## Acceptance criteria

- A supported Frame Compare VSView session always loads the Frame Compare panel from
  the same pinned Python environment.
- In an ordinary VSView session the plugin stays inert: it writes no file, adds no
  marker, performs no seek, and mutates no workspace state.
- Multi-comparison names, output order, overlays, L-SMASH indexes, color behavior, and
  downstream alignment precedence remain unchanged.
- A multi-comparison review loads every expected pair or fails as one session; no
  partial result can be accepted.
- Suggested, manually entered, and captured frame pairs display the correct live
  equation and trim direction.
- Every comparison can be explicitly confirmed or kept unchanged; partial review is
  never accepted as a completed result.
- The sidecar is atomic, session-scoped, strictly validated, and contains raw frame
  pairs rather than precomputed trusted offsets.
- Confirmed raw pairs produce the same signed offsets and manual overrides as the
  retired terminal workflow.
- Optional and forced missing/invalid-result behavior matches this plan.
- No terminal confirmation prompt, parser, test, import, or stale documentation
  remains.
- No external VSView executable can be reported as supported without the Frame Compare
  plugin in the launched environment.
- JSON stdout and unattended-run safety remain intact.
- No new dependency, compatibility shim, private VSView API, generic abstraction, or
  duplicate confirmation path is introduced.
- Full local, Docker, hosted Windows, and physical Windows proof is recorded, with
  unavailable cases identified rather than inferred.
- One independent architecture/runtime review finds no unadjudicated correctness,
  persistence, UI-thread, packaging, or stale-code issue.

## Stop conditions

Stop implementation and return to planning if:

- pinned VSView cannot reliably discover the packaged Frame Compare entry point;
- any required interaction needs private VSView workspace or tab-manager state;
- current output metadata cannot identify pairs without duplicating source-of-truth
  alignment state;
- a complete atomic result cannot be distinguished from a partial or stale result;
- generated-session source loading, output ordering, or color behavior must change to
  support the panel;
- Windows portable cannot load the plugin from the canonical environment;
- removing terminal confirmation would require retaining a second fallback parser;
- Mac, Docker, or hosted Windows proof exposes a product decision not frozen here.

## Rollback

Rollback is the whole native-confirmation feature. Revert the plugin entry point,
metadata/result contract, alignment-service cutover, public contract updates, and
terminal-code deletion together to the last accepted VSView parity baseline. Do not
ship a partial rollback containing both panel and terminal confirmation paths.

When all acceptance criteria pass, update current authority docs, mark this plan
`Status: Historical`, and retain it only as implementation and verification history.
