# Audio alignment and VSView

Frame Compare can estimate timing offsets between the reference and comparison sources,
reuse a previously accepted source relationship, and optionally open the native VSView
alignment-review panel for human verification. Alignment changes which source frames
are compared; it does not retime or rewrite the input files.

## When alignment helps

Alignment is useful when sources contain the same program but differ because of:

- leading studio logos or broadcaster slates;
- different container start times;
- source-specific trims;
- a constant audio/video offset;
- short additional or missing sections before the shared content.

It is not a general edit-matching system. Different cuts, replaced music, silence,
commentary tracks, or unrelated audio can make correlation ambiguous or invalid.

## Recommended workflow

1. Let automatic alignment collect and report an offset candidate.
2. Review the evidence, hold notice, and warnings; computed authority is currently
   held and does not authorize a trim.
3. Use the native VSView panel for optional alignment review when the route is
   available and the evidence needs visual confirmation. It is not part of automatic
   correlation: position each source in the viewer, then save the complete lineup once.
4. Verify dialogue, cuts, and motion in the final report.
5. Reuse a validated human-confirmed result only while the same source identities and
   alignment-affecting settings remain valid.

## Audio stream selection

The alignment service uses the selected audio streams and preprocessing strategy from
configuration. Confirm that the sources are using corresponding language, mix, and
content. A stereo theatrical mix and a commentary track can correlate poorly even when
the video is the same.

When automatic stream selection is unsuitable, use the audio-alignment configuration
surface documented in the
[CLI Behavioral Contract](../current-cli-contract.md#config-only-audio-alignment-surface).

## Previous offset reuse

Interactively confirmed offsets can be stored in the shared alignment reuse cache.
While the automatic-authority hold is active, computed results are not written or reused
as trim authority. Reuse is keyed by the source set, fingerprints, trims, effective FPS,
selected reference relationship, audio stream choices, alignment settings, and relevant
runtime identity.

A cache miss simply returns to normal alignment. Corrupt or unsupported reuse data is
ignored with a warning rather than treated as authoritative evidence.

Computed alignment may also classify bounded evidence across the source as stable,
possible drift, possible discontinuity, variable, or insufficient. This summary is
diagnostic only: computed evidence remains separate from trim authority while the
automatic hold is active; explicit or human-confirmed offsets remain authoritative.
Consensus groups windows only when their requested-rate sample estimates produce the
same integer source-frame correction at the reference FPS. It does not merge adjacent
frames or use the diagnostic stability classification for acceptance. The winning
group retains an observed lower-median sample estimate for diagnostic time reporting,
while preserving every original per-window sample estimate as evidence.
Material non-stable evidence produces one concise warning and should be verified at
multiple points. Stable and insufficient evidence do not warn. Alignment reuse cache
schema v2 requires the compact summary and the reference-minus-comparison sign
convention. The estimator policy is part of the shared source-set identity for both
computed and interactively confirmed entries, so older-policy shared entries miss and
are recomputed or reviewed normally. Schema-v1 entries are ignored and recomputed;
there is no cache migration or compatibility path. Run-local `manual_overrides.toml`
remains a v1 file with the same path and offset semantics.

Fresh computation distinguishes two shipped audio-evidence states. `provisional` means
a unique display-qualified candidate survived an attempt; under the internal
`continuous-origin-distributed-2097152-v7-held` policy it is shown as a clearly
unaccepted review hint and is never applied or passed as the authoritative integer/null
field. Its decision
records `automatic_authority_held` when the remaining v5 gates qualify it. `unavailable`
means no unique usable
candidate exists, and Frame Compare does not invent zero. The
display-only qualification floor is score 0.90 and peak ratio 1.50; it does not filter
v5 voting. The automatic hold independently prevents computed application. Manual
confirmation is a separate fact and does not rewrite the original audio attempt.

Each run retains that attempt in
`alignment_diagnostics/comparison-<ordinal>.json` beneath the run folder. The bounded
schema-v2 file records selected stream metadata, every planned window outcome, raw
candidate and quality facts, the aggregate decision, and the final review resolution.
It also retains bounded continuous-collection summaries and useful-overlap/coverage
facts when observed. Continuous collection decodes each selected source from its audio
origin once per phase, keeps only admitted distributed intervals in memory, and records
clean endpoint versus observed-EOF counts without padding or backfilling short windows.
A lower-rate discovery pass is followed by requested-rate verification only when needed.
Fresh computation runs in one owned worker thread so the application can respond to
cancellation while FFmpeg collection or bounded scoring is active. Cancelling waits for
cooperative child/reader/worker cleanup before the interruption escapes; it does not
interrupt a native FFT already running, which may finish to its admitted safe boundary.
Cancelled work never applies trims, writes reusable offsets, publishes a completed
diagnostic, or opens native review. Failure to release the child or readers is fatal.
It records the expected media-runtime fingerprint; FFmpeg/ffprobe version fields say
`not_observed` because this package does not add version-probe subprocesses.
It contains no media paths, PCM, environment values, credentials, full commands, or
full subprocess stderr. Source identity digests are pseudonymous rather than anonymous,
and sharing a run folder also shares its bounded labels and timing facts. The file is
diagnostic only: editing, corrupting, or deleting it cannot change trims or cache reuse.
It is retained until the run folder is deleted.

## Native VSView alignment review

VSView 0.11.0 and the Frame Compare alignment panel are included in the Windows
portable bundle and are optional in native installations through the
`frame-compare[vsview]` extra. The panel entry point and VSView runtime must be
installed in the same Python environment; a PATH-only VSView executable is not
supported. The upstream `recommended` and `full` extras are intentionally not
selected. The default Docker route does not provide an interactive desktop session.
The Linux X11 profile has a verifier contract for offscreen VSView/session/metadata/
result proof; this feature run has static contract proof only, and execution plus
visible desktop launch remain host-dependent and unverified.

Set `audio_alignment.use_vsview = true` to request optional native panel review,
or use `--force-interactive-alignment` when a successful review is required. Normal
mode keeps launch and startup-failure presentation concise. Use `--verbose` for the
generated command and bounded startup diagnostics. If optional VSView verification
cannot start, Frame Compare retains the computed audio alignment and directs you to
`frame-compare doctor`; forced interactive mode still fails.

Successful sessions continue to inherit native L-SMASH-Works decoder/index output.
BestSource is a VSView/UI-only capability and does not replace Frame Compare's source
loader, analysis, probe, render, index, or cache-key behavior. The generated session
uses documented `from vsview import set_output` registration with explicit `Reference`
and `Comparison N` names, while preserving source order, multi-comparison behavior,
Frame Compare overlays, and BT.709 preview defaults.

Before review, normal terminal output identifies accepted, provisional, or unavailable
evidence, support/reason, and selected audio ordinals. Verbose output adds bounded
stream, gate, runtime/policy, work, and per-window facts. Quiet mode hides routine
accepted/status evidence but leaves actionable rejection and write-failure warnings;
JSON keeps its existing stdout schema and uses structured stderr for actionable
rejection. No-color and redirected output stay plain and nonblocking.

The terminal does not prompt for frames or read review input. Open **Frame Compare
Alignment Review** from VSView's Tool Panel, unlink
the playheads, and visit `Reference` and every `Comparison N` output. Leave each on the
same visible moment. The live source lineup records one current untrimmed source frame
per output, reports `ready / total`, and previews `reference - comparison` plus the
plain-language trim direction.

Select **Confirm these aligned positions** once the complete lineup is ready. It writes one
ordered result for the whole source set; the reference appears once and the decision is
made for the full lineup in one action. Known-offset entry uses **Confirm these known
offsets**. **Keep current alignment** is the secondary whole-set option. It retains each
comparison's existing accepted or manually confirmed authority; provisional candidates
are not applied or confirmed, and unresolved comparisons remain unresolved.

For a known value, expand **Enter alignment manually...**. **Source frames** accepts one
non-negative untrimmed frame per source; **Known offsets** accepts one signed integer per
comparison using `reference - comparison`. Both bases feed the same whole-set save
action and explain the trim direction immediately. Positive offsets trim the reference;
negative offsets trim that comparison. Manual fields are an escape hatch, not a second
result workflow. Provisional values never prefill those fields, move a playhead, mark a
source visited, increase readiness, or enable confirmation.

The persistent **Audio evidence** section distinguishes `Audio alignment accepted:
+0f`, `Provisional audio candidate: +0f — NOT APPLIED`, and `No usable audio candidate`.
Expandable **Audio details** shows the validated bounded attempt. Accepted,
provisional, reused accepted, and manual markers have separate labels; unavailable
evidence has no marker. After keep-current, each comparison reports whether an accepted
alignment was retained, a provisional candidate was not confirmed, no accepted
candidate existed, or a manually confirmed alignment was retained.

The result sidecar is written atomically only by a complete whole-set action; closing
VSView without saving writes no result. Missing, malformed, stale, mixed-session,
duplicate, incomplete, or out-of-bounds sidecars are rejected before any offset is
applied. Missing modern `_Range` is reported once but remains unset, preserving
VSView's native range inference; other native diagnostics remain inherited.

Generated Frame Compare sessions use metadata v3 while the result sidecar remains v1.
Metadata v1/v2, unknown-version, mixed-version, and malformed Frame Compare sessions must
be regenerated after upgrading; they are not migrated into trust. Ordinary VSView
sessions without Frame Compare metadata remain inert. Shared alignment cache schema v2,
diagnostic artifact schema v2, and manual override schema v1 are separate contracts and
are unchanged by this session-metadata update.

The native-panel workflow uses each source exactly once, named outputs, public
VSView callbacks, current frame/property surfaces, explicit lineup status and trim
guidance, and a typed fail-closed result boundary. Existing v1 shared alignment entries
are not reused; they are rebuilt as schema v2.

No alignment screenshot is embedded here until the physical-Windows VSView acceptance
pass supplies a current, provenance-recorded capture. macOS and headless Docker proof
does not establish native desktop ergonomics.

During verification, inspect multiple evidence points:

- a hard cut near the beginning;
- dialogue with visible mouth movement;
- a motion-heavy sequence;
- a later point in the program to detect drift;
- the final shared section to confirm the sources still overlap.

An offset that looks correct at one frame can still be wrong for variable timing or a
different edit.

## Failure modes

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Low or unstable correlation | Silence, replaced music, wrong stream, or different edit | Select corresponding audio, increase evidence, or verify manually |
| Good early match but later drift | FPS or timing mismatch | Recheck effective FPS and source structure; do not treat a constant offset as sufficient |
| VSView/panel cannot launch | Missing same-environment UI dependencies or desktop/runtime issue | Run `doctor`, install `frame-compare[vsview]` in the environment that runs Frame Compare, use the Windows portable bundle, or continue without optional review |
| Panel stays inactive | The session is ordinary, metadata is malformed/mixed, or the generated script/result identity is not trusted | Generate a fresh session through Frame Compare; do not open a hand-authored script or provide a PATH-only VSView executable |
| Panel closes before saving | No complete typed result sidecar was written | Reopen the generated session, visit every source, and use **Confirm these aligned positions** or **Keep current alignment** |
| Review result is rejected | Sidecar is missing, malformed, stale, duplicated, incomplete, or outside raw source-frame bounds | Discard the sidecar, generate a fresh session, and repeat the panel review; forced mode fails closed |
| Reused offset no longer looks correct | Source or runtime changed outside the reusable identity assumptions | Reject reuse, clear the alignment cache entry, and recompute |
| Selected frames disappear after alignment | Shared overlap is smaller than the initial reference-domain plan | Reduce trims or requested counts and review the warning/error context |

## Validation standard

Automatic correlation is a strong starting point, not a substitute for visual review.
For a publication-bound comparison, manually check the final report even when the
alignment cache hits and no warning is emitted.
