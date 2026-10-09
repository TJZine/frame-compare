# VSView alignment review

The VSView alignment panel is the only place to confirm or enter alignment by eye. It
runs inside VSView and saves one decision for the whole set of sources.

## Before you start

The Windows portable bundle includes the panel. Native installs need the `vsview`
extra in the same Python environment that runs Frame Compare. The default Docker route
has no desktop. A PATH-only VSView executable is not supported.

Turn review on with `audio_alignment.use_vsview = true`, or require it with
`--force-interactive-alignment`:

```toml
[audio_alignment]
use_vsview = true
```

If optional review cannot start, Frame Compare keeps the current alignment and points
you to `doctor`, while forced review fails.

## Open the panel

1. Run the comparison. Frame Compare generates a session and opens VSView.
2. Open **Frame Compare Alignment Review** from VSView’s **Tool Panel**.
3. Confirm that the workspace shows one `Reference` output and one `Comparison N`
   output per comparison.

The panel stays inactive in an ordinary VSView session.

## Confirm the positions

1. Unlink the playheads.
2. Visit every output and leave each on the same visible moment.
3. Watch the source lineup until it shows `{n}/{total} positions captured — ready to confirm`.
4. Select **Confirm these aligned positions**.

The panel distinguishes the frame you are viewing from the captured position and
previews the signed offset and which source is trimmed. It shows the audio candidate
under **Audio evidence** without applying it.

## Enter known values

Expand **Enter alignment manually...** and choose
**Source frames** or **Known offsets**.
Enter one non-negative untrimmed frame per source for **Source frames**, or one signed
integer per comparison for **Known offsets**, using `reference − comparison`.

Source frames use **Confirm these aligned positions**.
Known offsets use **Confirm these known offsets**.
With no base trims, a positive offset trims the reference and a negative offset
trims the comparison. Base trims do not change the value you enter.

## Keep the current alignment

**Keep current alignment** keeps existing applied offsets and leaves a
provisional candidate unconfirmed.

## What happens next

After either action the panel shows `Alignment choices saved`.
The panel then shows `Close VSView to resume Frame Compare.`
Frame Compare writes one typed, atomic sibling sidecar named
`vsview_*.alignment-result.json` for the complete source set. It checks the sidecar
against the session and applies it.

Closing VSView without saving writes no result.
Missing, malformed, stale, mixed-session, duplicate, incomplete, and out-of-bounds results fail closed.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `doctor` reports the alignment panel is missing | Install the `vsview` extra in the environment that runs Frame Compare, or reinstall the complete Windows portable bundle |
| VSView will not launch | Run `frame-compare doctor`; check that a desktop session is available; continue without review, or use the Windows portable bundle |
| The panel stays inactive | Open the session Frame Compare generated; ordinary sessions and hand-written scripts stay inactive |
| VSView closed before saving | No result was written; run again, visit every source, and choose **Confirm these aligned positions** or **Keep current alignment** |
| The saved result is rejected | Run again to generate a fresh session; Frame Compare rejects stale, mixed, duplicate, incomplete, and out-of-bounds results |
