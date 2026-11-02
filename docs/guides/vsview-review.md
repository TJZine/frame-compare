---
description: Confirm or enter alignment by eye in the VSView alignment panel.
---

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

## Confirm matching frames

1. Browse each source to the same visual moment with VSView’s source selector.
   Generated review sessions automatically **Unlink** playheads so each source keeps
   its own original-frame position.
2. Open **Tool Panel → Frame Compare Alignment Review** and check the original-frame
   numbers for Reference and every comparison. Tracking starts when the workspace
   loads, including while the panel is closed or another tool is selected.
3. Pause playback and allow any seek to finish, then choose **Confirm matching frames**.
   This saves the complete set once. Close VSView to resume Frame Compare.

Browsing and editing never save alignment. The confirmation expresses your intent
that the listed original frames match; it does not certify which pixels finished
presenting. Confirmation is disabled while the workspace is playing, seeking,
loading, draining a paused frame, or unavailable. Other VSView background jobs may
temporarily postpone confirmation while its shared worker pool is busy.
The panel keeps the waiting reason visible even when every frame is manually
entered; manual frame entry does not bypass this wait. Focus a panel action and
press Space to activate it; Space elsewhere retains the viewer playback shortcut.
A changed set refreshes the numbers and requires another
click. A valid frame zero is preserved.

You can enter original frame numbers directly in the source rows. Any edit, including
an empty or invalid value, protects that row from automatic updates. **Use viewer frame**
replaces that manual draft with its source’s retained viewer position and resumes
tracking. Focused editing is protected. Other source rows continue tracking.
Automatic tracking uses a contained bridge to the pinned VSView 0.13.0 workspace;
if unavailable, the panel explains how to unlink playheads and enter frames manually.
Ordinary VSView sessions are unaffected.

### Read the preview labels

Video labels show the source and its native **Original frame**, followed by
**Predicted for this frame (opening hints)** for every other source in output order.
Names and stable roles identify each target. These estimates follow the viewed frame
using immutable session-opening offsets, even after Save or Keep. Provisional edges
are marked; unavailable or outside-range hints never mean matching content is absent.
If the whole list cannot fit, static labels explicitly say live hints are unavailable.
The panel lists the actual tracked or manually entered original frames for confirmation.

The preview is untrimmed and uses ordinary SDR packing even for HDR sources,
leaving final report tone mapping unchanged. Correct PQ/HLG/source color properties
remain intact. If neither live nor static labels fit, a warning accompanies raw
preview; explicit numeric entry remains available.

## Enter known values

Source frame numbers use the stable lineup and the same **Confirm matching frames** action.
For known offsets, expand **Enter alignment manually...**, choose **Known offsets**,
enter every signed `reference − comparison` offset, then choose **Confirm these known offsets**.
This is a separate input basis: source frame drafts are retained but not submitted. Closing the
manual controls returns to source frames without losing the offset drafts.
With no base trims a positive offset trims Reference and a negative offset trims the comparison.

## Keep the current alignment

**Keep current alignment** retains existing applied offsets without confirming a
provisional candidate or the unsaved frame lineup. The terminal message is
**Keep decision saved — frame lineup was not confirmed**.

## What happens next

Successful confirmation shows **Alignment choices saved**, followed by
**Close VSView to resume Frame Compare.** Successful confirmation or Keep freezes edits;
a failed write leaves the drafts editable. Successful confirmation shows
**Saved offset (Reference − Comparison)** with the actual signed frame value.
Video opening hints continue after saving. Known offsets and Keep do not confirm
any source frame drafts that were not submitted. A standalone generated demo has no parent comparison to resume;
its helper says to close the demo, while normal CLI review resumes Frame Compare.
Frame Compare writes one typed, atomic sibling sidecar named
`vsview_*.alignment-result.json` for the complete source set and checks session freshness.
Closing VSView without saving writes no result. Missing, malformed,
stale, mixed-session, duplicate, incomplete, and out-of-bounds results fail closed. An ordinary VSView session
stays inactive.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Panel missing | Install the vsview extra in the same environment, or reinstall the complete Windows portable bundle |
| Inactive panel | Open a newly generated Frame Compare session; ordinary VSView sessions stay inactive |
| Prediction unavailable | Choose/verify matching original frame numbers manually; unknown hints do not prevent confirmation |
| Seek rejected | Pause playback, activate the intended source, then wait for the frame to settle before confirmation |
| Saved result rejected | Generate a fresh session; stale, mixed-session, duplicate, incomplete and out-of-bounds results are rejected |
