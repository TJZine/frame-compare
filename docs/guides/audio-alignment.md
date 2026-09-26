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

1. Let automatic alignment collect and report an offset candidate. An agreed
   audio result stays provisional until the video check confirms it; nothing
   applies automatically in this state.
2. Review the evidence and warnings, especially for provisional or unavailable results.
3. Use the native VSView panel for optional alignment review when the route is
   available and the evidence needs visual confirmation. It is not part of automatic
   correlation: position each source in the viewer, then save the complete lineup once.
4. Verify dialogue, cuts, and motion in the final report.
5. Reuse a validated human-confirmed result only while the same source identities and
   alignment-affecting settings remain valid.

## Audio stream selection

The alignment service uses the selected audio streams from
configuration. Confirm that the sources are using corresponding language, mix, and
content. A stereo theatrical mix and a commentary track can correlate poorly even when
the video is the same.

When automatic stream selection is unsuitable, use the audio-alignment configuration
surface documented in the
[CLI Behavioral Contract](../current-cli-contract.md#config-only-audio-alignment-surface).

## Evidence and temporal support

Frame Compare decodes the whole selected audio stream at 8 kHz mono and tiles the
reference into chunks of `C = clamp(floor(D/3), 5 s, 30 s)`, where `D` is the
shorter selected-stream duration (one chunk of length `D` below 5 s). Each chunk
is correlated against the comparison with GCC-PHAT over lags `[-M, +M]` with
`M = max_offset_seconds` (default 30 s). A chunk counts only when both sides are
above -50 dBFS RMS, and is credible at a peak prominence (PSR) of at least 25.
The global lag is the argmax of the summed active-chunk correlations. Chunks
within 2 ms of that lag agree; the audio stage passes when at least
`min(3, analyzed)` chunks agree and they cover at least 80% of the credible
chunks. A global lag within 2 ms of the search edge is never applied.

Container start times matter: the compensated offset adds the
reference-vs-comparison difference of (audio start minus video start) to the
chunked lag, so sources with container audio delays align to video rather than to
a confidently wrong sample offset. A missing start time counts as 0 and is
recorded as `default_zero`.

Disagreement (`no_single_offset`) keeps contiguous chunk runs grouped by lag so
an insert or drift reads as runs, never as an applied value. Unrelated audio,
edits, and speed differences refuse rather than apply. Only two FFmpeg children
run per comparison with bounded memory: memory does not grow with duration, but
compute time does.
Failed collection PCM is never usable: accumulated evidence counts only after
both decodes succeed with complete cleanup.

## Previous offset reuse

Interactively confirmed offsets can be stored in the shared alignment reuse cache.
Fresh computed audio candidates are provisional and are never written or reused as
trim authority. Reuse is keyed by the source set, fingerprints, trims, effective FPS,
selected reference relationship, audio stream choices, alignment settings, and relevant
runtime identity.

A cache miss simply returns to normal alignment. Corrupt or unsupported reuse data is
ignored with a warning rather than treated as authoritative evidence.

Computed alignment also classifies bounded evidence across the source as stable,
possible drift, possible discontinuity, variable, or insufficient. This summary is
diagnostic only and is derived from credible chunk runs; unobserved planned chunks
remain unassessed. Any reported change position is an approximate interval between observations,
not an observed edit location. Provisional computed evidence remains separate
from trim authority; explicit or human-confirmed offsets remain authoritative.
Alignment reuse cache
schema v2 requires the compact summary and the reference-minus-comparison sign
convention. The internal estimator policy token
`whole-track-chunked-phat-video-check-20260925`
is part of the full shared source-set identity for both computed and interactively confirmed
entries. A stale-policy shared entry misses and is recomputed or reviewed normally. Schema-v1 entries are ignored and recomputed;
there is no cache migration or compatibility path. Run-local `manual_overrides.toml`
remains a v1 file with the same path and offset semantics.

Fresh computation distinguishes two shipped audio-evidence states while the video
check is pending. `provisional` means the audio stage agreed on one constant
offset, reported with reason `video_check_pending` as a clearly unaccepted review
hint: audio alone fixes the offset only to within about one frame, and the pending
video check picks the exact applied frame. `unavailable`
means no single usable
offset exists, and Frame Compare does not invent zero. Manual confirmation is a
separate fact and does not rewrite the
original audio attempt. The replacement policy identity invalidates stale shared source-set
entries, including embedded computed results and prior interactive confirmations; cache
schema v2 and the manual-override schema remain unchanged.

Each run retains that attempt in
`alignment_diagnostics/comparison-<ordinal>.json` beneath the run folder. The bounded
schema-v4 file records selected stream metadata with start-time compensation, chunk
runs, compact per-chunk rows (start, lag, PSR, active/credible/agree flags), the
global lag, the sub-frame estimate, the audio decision, and the final review
resolution.
It also retains bounded paired-collection summaries when observed. A failed collection
never contributes usable PCM evidence. Paired collection decodes reference and
comparison concurrently in lockstep, keeping per side one sample store plus one
delivery scratch buffer, and never spills PCM to disk.
Fresh computation runs in one owned worker thread so the application can respond to
cancellation while FFmpeg collection or bounded scoring is active. Cancelling waits for
cooperative child/reader/worker cleanup before the interruption escapes; it does not
interrupt a native FFT already running, which may finish to its admitted safe boundary.
Cancelled work never applies trims, writes reusable offsets, publishes a completed
diagnostic, or opens native review. Failure to release a child or its readers is fatal.
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

Before review, normal terminal output leads with the current decision and signed frame
offset. A provisional state is
`Comparison N - Provisional audio candidate: +Nf - NOT APPLIED`. A
`video_check_pending` candidate adds exactly `Video confirmation pending; not applied.`;
other provisional candidates add exactly `Visual confirmation required to use this hint. Align manually or keep the current alignment.` An unavailable state
emits `Comparison N - No usable audio candidate (<plain-words reason>) - NOT APPLIED`
followed by `Align manually or keep the current alignment.` Applied states are
manual-only in this state:
`Accepted audio alignment reused: +Nf - APPLIED` or
`Manually confirmed alignment: +Nf - APPLIED`,
followed by `No additional confirmation needed.` A previously shared manual result is
labeled `Manually confirmed alignment reused: +Nf - APPLIED`; current-run and
preexisting manual results keep the unqualified manual label.
The current manual authority leads even when an original provisional or
unavailable attempt is retained as history. Verbose output adds bounded stream, gate,
runtime/policy, work, and credible-chunk counts, plus original-attempt facts;
individual diagnostic chunks are never printed; the original provisional
state remains explicitly `NOT APPLIED` there. Quiet mode hides routine accepted/status
evidence but leaves actionable rejection and write-failure warnings; JSON keeps its
existing stdout schema and uses structured stderr for actionable rejection, including
the `audio_alignment_requires_review` warning. No-color
and redirected output stay plain and nonblocking.

The terminal does not prompt for frames or read review input. Open **Frame Compare
Alignment Review** from VSView's Tool Panel, unlink the playheads, and position
`Reference` and every `Comparison N` output on the same visible moment. Before saving,
the panel distinguishes `Viewing: frame N` from the callback-derived `Captured position:
frame N` (inactive sources show only their last captured position). A complete viewer
draft reports `{n}/{total} positions captured — ready to confirm`; incomplete drafts
report `{n}/{total} positions captured`.

Select **Confirm these aligned positions** once the complete lineup is ready. It writes one
ordered result for the whole source set; the reference appears once and the decision is
made for the full lineup in one action. The viewer guidance is `To confirm a new
alignment, unlink the playheads and position each source on the same visible moment. Or
keep the current alignment.` Known-offset entry uses **Confirm these known offsets** and
reports `{n}/{total} offsets entered`, adding ` — ready to confirm` only when complete
and valid. **Keep current alignment** is the secondary whole-set option. Its help is
`Keeps existing alignment. Provisional candidates are not confirmed; unresolved
comparisons remain unresolved.`

For a known value, expand **Enter alignment manually...**. **Source frames** accepts one
non-negative untrimmed frame per source; **Known offsets** accepts one signed integer per
comparison using `reference - comparison`. Both bases feed the same whole-set save
action and explain the trim direction immediately. Source-frame entry reports
`{n}/{total} source frames entered`, adding ` — ready to confirm` only when complete and
valid; each valid draft is shown as `Entered source frame: N`. Invalid input is
shown as `Needs attention — {validation message}`. The known-offset guidance is
`Enter the signed reference-minus-comparison offsets, then confirm. Or keep the current
alignment.` With no configured base trims, positive offsets trim the reference and
negative offsets trim that comparison.
Configured base trims do not change this raw source-frame value: Frame Compare converts
it only at the trim-application boundary, then composes the calculated trims onto each
base domain so the final reference source start minus the comparison source start still
equals the entered offset. This also preserves a raw zero when base trims differ. Manual
fields are an escape hatch, not a second result workflow. Provisional values never
prefill those fields, move a playhead, mark a source visited, increase readiness, or
enable confirmation.

The persistent **Audio evidence** section leads with the current authority:
`Accepted audio alignment reused: +Nf — APPLIED` or
`Manually confirmed alignment: +Nf — APPLIED`, each followed by `No additional
confirmation needed.` The unqualified `Accepted audio alignment: +Nf — APPLIED`
form is reserved for a video-confirmed fresh result (a later unit); fresh
computed results stay provisional until then. Without current authority the
section shows either `Provisional audio
candidate: +Nf — NOT APPLIED` with `Visual confirmation required to use this hint.` or
`Unresolved comparison — no usable audio candidate`. A manual authority remains first
when original provisional or unavailable evidence is retained; original evidence stays
provisional/unresolved in its own line and in the details. Expandable **Audio evidence
details — Comparison N** is collapsed by default and retains the validated bounded
attempt.

After either whole-set action, the panel shows `Alignment choices saved` and
`Close VSView to resume Frame Compare.` It disables the save actions, hides stale
keep-current help, hides the pre-save audio summaries, and focuses the saved status.
Frozen captured or entered positions remain in the source lineup; the collapsed audio
evidence details retain the original immutable classification. Keep-current outcomes are
`Accepted alignment retained: +Nf`, `Current alignment retained: +Nf — manually
confirmed`, `Current alignment retained. Provisional candidate +Nf not confirmed — NOT
APPLIED. Comparison unresolved.`, or `Current alignment retained. Comparison unresolved
— no accepted alignment.` Confirmed positions or offsets show `Alignment confirmed: +Nf
— manually confirmed`. A raw `+0f` remains distinct from no candidate; trim previews do
not claim that existing base trims are absent.

The result sidecar is written atomically only by a complete whole-set action; closing
VSView without saving writes no result. Missing, malformed, stale, mixed-session,
duplicate, incomplete, or out-of-bounds sidecars are rejected before any offset is
applied. Missing modern `_Range` is reported once but remains unset, preserving
VSView's native range inference; other native diagnostics remain inherited.

Generated Frame Compare sessions use metadata v5 while the result sidecar remains v1.
Older, unknown-version, mixed-version, and malformed Frame Compare sessions must
be regenerated after upgrading; they are not migrated into trust. Ordinary VSView
sessions without Frame Compare metadata remain inert. Shared alignment cache schema v2,
diagnostic artifact schema v4, and manual override schema v1 are separate contracts and
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
