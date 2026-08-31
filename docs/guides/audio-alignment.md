# Audio alignment and VSView

Frame Compare can estimate timing offsets between the reference and comparison sources,
reuse a previously accepted source relationship, and optionally open VSView for
manual verification. Alignment changes which source frames are compared; it does not
retime or rewrite the input files.

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
3. Use VSView for optional interactive verification when the route is available and
   the evidence needs manual confirmation. It is not part of automatic correlation.
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

## Interactive verification with VSView

VSView 0.10.3 is included in the Windows portable bundle and is optional in native
installations through the base `vsview` extra. The upstream `recommended` and `full`
extras are intentionally not selected. The default Docker route does not provide an
interactive desktop session. The Linux X11 profile has an offscreen VSView/session/
render proof, but visible desktop launch remains host-dependent and unverified.

Set `audio_alignment.use_vsview = true` to request optional interactive verification,
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

The interactive terminal flow remains nested under `ALIGN` and stages the operator
through `[RUN] VSView Bootstrap`, `[OK] VSView Ready`, and `[WAIT] VSView Confirmation`.
Normal labels use the same prepared release-aware source identities as the rest of
Frame Compare, while paths and filename stems remain internal alignment identities.
These literal markers remain present with color disabled. Ready gives a directly
nested next action, and confirmation instructions and prompts are visibly nested
beneath the blocking `[WAIT]` state. Missing modern `_Range` is reported once but
remains unset, preserving VSView's native range inference; other native diagnostics
remain inherited.

The migration gains a maintained viewer, named outputs, synchronized multi-output
review, and current frame/property surfaces. It intentionally removes the retired
viewer-specific config key, package extra, imports, generated session path, symbolic
names, and compatibility mutations. Existing v1 shared alignment entries are not
reused; they are rebuilt as schema v2.

Confirmation uses untrimmed source-frame indices. Find the same visible moment in the
reference and comparison, then enter the reference frame followed by the comparison
frame; Frame Compare calculates the offset and required trim. The audio hint shows an
equivalent source-frame pair and the source it would trim. `skip` leaves the current
audio result unchanged when one is available. Every signed offset is reference minus
comparison: positive trims the reference, negative trims the comparison. Native decoder
and index diagnostics remain visible between Frame Compare-owned status rows.

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
| VSView cannot launch | Missing optional UI dependencies or desktop/runtime issue | Run `doctor`, use the Windows portable bundle or a valid native VSView installation, or continue without interactive verification |
| Reused offset no longer looks correct | Source or runtime changed outside the reusable identity assumptions | Reject reuse, clear the alignment cache entry, and recompute |
| Selected frames disappear after alignment | Shared overlap is smaller than the initial reference-domain plan | Reduce trims or requested counts and review the warning/error context |

## Validation standard

Automatic correlation is a strong starting point, not a substitute for visual review.
For a publication-bound comparison, manually check the final report even when the
alignment cache hits and no warning is emitted.
