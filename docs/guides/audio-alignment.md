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

1. Let automatic alignment compute an offset.
2. Review confidence and warnings.
3. Use the native VSView panel for optional alignment review when the route is
   available and the evidence needs visual confirmation. It is not part of automatic
   correlation: position each source in the viewer, then save the complete lineup once.
4. Verify dialogue, cuts, and motion in the final report.
5. Reuse an accepted result only while the same source identities and alignment-affecting
   settings remain valid.

## Audio stream selection

The alignment service uses the selected audio streams and preprocessing strategy from
configuration. Confirm that the sources are using corresponding language, mix, and
content. A stereo theatrical mix and a commentary track can correlate poorly even when
the video is the same.

When automatic stream selection is unsuitable, use the audio-alignment configuration
surface documented in the
[CLI Behavioral Contract](../current-cli-contract.md#config-only-audio-alignment-surface).

## Previous offset reuse

Accepted computed or interactively confirmed offsets can be stored in the shared alignment
reuse cache. Reuse is keyed by the source set, fingerprints, trims, effective FPS,
selected reference relationship, audio stream choices, alignment settings, and relevant
runtime identity.

A cache miss simply returns to normal alignment. Corrupt or unsupported reuse data is
ignored with a warning rather than treated as authoritative evidence.

Computed alignment may also classify bounded evidence across the source as stable,
possible drift, possible discontinuity, variable, or insufficient. This summary is
diagnostic only: Frame Compare always retains the selected constant offset and trims.
Material non-stable evidence produces one concise warning and should be verified at
multiple points. Stable and insufficient evidence do not warn. Alignment reuse cache
schema v2 requires the compact summary and the reference-minus-comparison sign
convention. Schema-v1 entries are ignored and recomputed; there is no cache migration
or compatibility path. Run-local `manual_overrides.toml` remains a v1 file with the
same path and offset semantics.

## Native VSView alignment review

VSView 0.10.3 and the Frame Compare alignment panel are included in the Windows
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

The terminal reports only the generated session, bounded readiness, inherited decoder
diagnostics, and the final review outcome. It does not prompt for frames or read
review input. Open **Frame Compare Alignment Review** from VSView's Tool Panel, unlink
the playheads, and visit `Reference` and every `Comparison N` output. Leave each on the
same visible moment. The live source lineup records one current untrimmed source frame
per output, reports `ready / total`, and previews `reference - comparison` plus the
plain-language trim direction.

Select **Use these aligned positions** once the complete lineup is ready. It writes one
ordered result for the whole source set; the reference appears once and the decision is
made for the full lineup in one action. **Keep audio-derived alignment** is
the secondary whole-set option. It retains the alignment Frame Compare entered with,
including the no-change case when no trusted suggestion exists.

For a known value, expand **Enter alignment manually...**. **Source frames** accepts one
non-negative untrimmed frame per source; **Known offsets** accepts one signed integer per
comparison using `reference - comparison`. Both bases feed the same whole-set save
action and explain the trim direction immediately. Positive offsets trim the reference;
negative offsets trim that comparison. Manual fields are an escape hatch, not a second
result workflow.

The result sidecar is written atomically only by a complete whole-set action; closing
VSView without saving writes no result. Missing, malformed, stale, mixed-session,
duplicate, incomplete, or out-of-bounds sidecars are rejected before any offset is
applied. Missing modern `_Range` is reported once but remains unset, preserving
VSView's native range inference; other native diagnostics remain inherited.

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
| Panel closes before saving | No complete typed result sidecar was written | Reopen the generated session, visit every source, and use **Use these aligned positions** or **Keep audio-derived alignment** |
| Review result is rejected | Sidecar is missing, malformed, stale, duplicated, incomplete, or outside raw source-frame bounds | Discard the sidecar, generate a fresh session, and repeat the panel review; forced mode fails closed |
| Reused offset no longer looks correct | Source or runtime changed outside the reusable identity assumptions | Reject reuse, clear the alignment cache entry, and recompute |
| Selected frames disappear after alignment | Shared overlap is smaller than the initial reference-domain plan | Reduce trims or requested counts and review the warning/error context |

## Validation standard

Automatic correlation is a strong starting point, not a substitute for visual review.
For a publication-bound comparison, manually check the final report even when the
alignment cache hits and no warning is emitted.
