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

## Choose an anchor and matching frame numbers

1. Open **Tool Panel → Frame Compare Alignment Review**. Its stable lineup identifies
   every source; **Alignment on entry** describes existing authority and audio evidence.
2. In any source row, enter or verify its native **Original frame** number in
   **Frame**, then choose **Anchor [source]: [number]**.
3. Switch directly between A and B using the viewer source selector. The panel shows
   **Predicted** positions for the pinned moment. On the active source, **Go to [number]**
   fills a predicted proposal and requests a paused seek. Verify the
   picture/number; an admitted seek does not select or prove the displayed image.
4. Enter or correct the matching number, then choose **Select [source]: [number]**.
   These actions select explicit numbers, rather than capturing the screen. You may
   select a numeric coordinate while another source is active. Reference need not be
   visited first, but must be selected before saving the complete lineup.
5. Choose **Save selected alignment** when all sources are selected. Close VSView to resume.

**Predicted** is an opening-offset hint; provisional and unavailable hints are labelled.
**Selected** is your unsaved numeric pin. **Saved** appears only after a successful
complete decision write. Editing proposals, browsing, seeking and switching sources
never alter pins. Clear/replace affects only that source. Making an already selected
source the anchor preserves the moment; a new anchor number/reset warns before clearing
other selections. Cancel preserves them. Proposed numbers are retained until edited.

For stored offsets `d_i = Reference − source_i`, an anchor at frame `c` predicts
`c + d_anchor − d_target`. Thus A96 with A offset +504 and B offset −12 predicts
Reference600 and B612. These are raw source coordinates; base trims do not change them.
A missing/out-of-range hint still permits manual matching. It is not proof of no overlap.

### Read the preview labels

Video labels show source identity and native **Original frame** only. Predictions and
selected/saved state belong to the panel. The preview is untrimmed and uses the ordinary
SDR viewer even for HDR sources, leaving final report tone mapping unchanged. Correct
PQ/HLG/source color properties remain intact; this is an alignment view, not calibrated HDR.
Static fallback identifies the source without inventing a current frame. If neither
label mode works, a warning accompanies raw preview; numeric entry remains available.

## Enter known values

Source frame numbers use the stable lineup and its explicit anchor/select actions.
For known offsets, expand **Enter alignment manually...**, choose **Known offsets**,
enter every signed `reference − comparison` offset, then choose **Confirm these known offsets**.
This is a separate input basis: source pins are retained but not submitted. Closing the
manual controls returns to source selections without losing the offset drafts.
With no base trims a positive offset trims Reference and a negative offset trims the comparison.

## Keep the current alignment

**Keep current alignment** retains existing applied offsets without confirming a
provisional candidate or the unsaved selected lineup. The terminal message is
**Keep decision saved — selected lineup was not confirmed**.

## What happens next

Successful confirmation shows **Alignment choices saved**, followed by
**Close VSView to resume Frame Compare.** Successful Save/Keep freezes edits; a failed
write keeps unsaved pins editable. Frame Compare writes one typed, atomic sibling sidecar named
`vsview_*.alignment-result.json` for the complete source set and checks session freshness.
Closing VSView without saving writes no result. Missing, malformed,
stale, mixed-session, duplicate, incomplete, and out-of-bounds results fail closed. An ordinary VSView session
stays inactive.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Panel missing | Install the vsview extra in the same environment, or reinstall the complete Windows portable bundle |
| Inactive panel | Open a newly generated Frame Compare session; ordinary VSView sessions stay inactive |
| Prediction unavailable | Choose/verify matching original frame numbers manually; unknown hints do not prevent selection |
| Seek rejected | Pause playback, activate the intended source, then retry; no frame was selected |
| Saved result rejected | Generate a fresh session; stale, mixed-session, duplicate, incomplete and out-of-bounds results are rejected |
