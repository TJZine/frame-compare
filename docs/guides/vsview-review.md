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
2. The active source’s **Frame** field follows its public viewer navigation position
   until you edit or pin it. Verify the picture and native **Original frame** number,
   then choose **Anchor [source]: [number]**. This prefill selects nothing.
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
other selections. Cancel preserves them. Manual edits (including empty/invalid entries),
Anchor/Select, and **Go to [number]** protect that row’s proposal from passive following.
**Use viewer frame** deliberately replaces the active row’s proposal and resumes following;
it never changes a pin. Focused editing is protected. Other rows remain untouched.
A paused step may briefly show **Waiting for viewer position** while public navigation
state settles. Such a value cannot be pinned until validated. On timeout the prior text
remains for inspection, with **temporarily unavailable**; enter a number or use the
explicit viewer action to recover. This is navigation convenience, not proof of the
presented pixels. Reset/clear and input-basis changes preserve ownership; successful
Save/Keep freezes following, and failed writes remain editable.

For stored offsets `d_i = Reference − source_i`, an anchor at frame `c` predicts
`c + d_anchor − d_target`. Thus A96 with A offset +504 and B offset −12 predicts
Reference600 and B612. These are raw source coordinates; base trims do not change them.
A missing/out-of-range hint still permits manual matching. It is not proof of no overlap.

### Read the preview labels

Video labels show the source and its native **Original frame**, followed by
**Predicted for this frame (opening hints)** for every other source in output order.
Names and stable roles identify each target. These estimates follow the viewed frame
using immutable session-opening offsets, even after Save or Keep. Provisional edges
are marked; unavailable or outside-range hints never mean matching content is absent.
If the whole list cannot fit, static labels explicitly say live hints are unavailable.
The panel instead shows hints **for the pinned anchor** (named source and frame);
browsing away can legitimately make its estimates differ from the video.

The preview is untrimmed and uses ordinary SDR packing even for HDR sources,
leaving final report tone mapping unchanged. Correct PQ/HLG/source color properties
remain intact. If neither live nor static labels fit, a warning accompanies raw
preview; explicit numeric entry remains available.

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
write keeps unsaved pins editable. Successful confirmation shows **Saved offset (Reference − Comparison)**
with the actual signed frame value. Redundant panel prediction labels and markers hide
after Save/Keep; video opening hints continue. Retained pins in Known offsets/Keep
remain unsaved. A standalone generated demo has no parent comparison to resume;
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
| Prediction unavailable | Choose/verify matching original frame numbers manually; unknown hints do not prevent selection |
| Seek rejected | Pause playback, activate the intended source, then retry; no frame was selected |
| Saved result rejected | Generate a fresh session; stale, mixed-session, duplicate, incomplete and out-of-bounds results are rejected |
