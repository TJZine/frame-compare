---
search:
  exclude: true
---

# TODO

> Non-authoritative backlog. These items are candidates, not approved plans or
> current product contracts. Update or remove an item when its work is completed,
> rejected, or promoted into an active plan.

- Consider adding a dedicated packaging/release workflow skill if Python packaging, Docker, Windows portable, or updater/signing work becomes frequent.

## Release Identity Presentation Follow-Ups

- Consider dedicated release-identity display fields for the HTML report source labels, baked
  screenshot overlays, wizard/dry-run exact-file presentation, and warnings where
  useful. Exclude run-folder/history names, the slow.pics collection title, and all
  internal identities.

---

## Audio Alignment: Release And Performance Follow-Ups

From the whole-track audio alignment plan's closeout (2026-09-30). The plan,
`docs/plans/2026-09-25-audio-alignment-whole-track-and-video-check.md`, was
removed in `ec86e357`; read it from git history.

- **Windows portable proof (release gate).** Run the retimed, motion-selected
  alignment path and the new `[runtime] memory_limit_mb` setting in the Windows
  portable build before release. It can't be proven on macOS or Docker.
- **Keyframe-placed motion candidates (only if video-check speed becomes a
  problem again).** Moving each M1 candidate to the first keyframe inside its
  quarter kept every outcome correct. It was 30% faster than the current version
  on long-keyframe 4K pairs, but 37% slower on a 2 s-GOP 4K pair, and it
  depended on the decoder's index file format. Revisit only with a
  keyframe source the loader exposes, and with no pair slower.

## Audio Alignment: Region-Limited Automatic Selection

Follow-up to the whole-track audio alignment plan (A4a, V3a, V5a), which is in
git history before `ec86e357`. This is not approved scope: it needs its own plan before
implementation, and it should wait for that plan's U5 real-media results to show how
often competing offsets occur.

**Problem.** When the sources contain an edit, such as an inserted or removed scene,
a recap, or a different ending, the audio stage finds a dominant offset plus one or
more competing regions. The current plan correctly refuses to apply anything
automatically in that case (`competing_offset`,
`competing_offset_confirmed_by_video` or `unresolved_audio_disagreement`), so each
such comparison needs a manual
decision. Yet the dominant offset is usually correct for most of the program.

**Goal.** Apply the dominant offset automatically, but select comparison frames only
from regions where that offset is confirmed, so every screenshot is a genuine match
and the report says which parts of the program were compared.

**Proposed behaviour:**

- **Eligibility.** Only results that would be `trusted_automatic` apart from A4a or
  V5a: audio agreement passes A4, the video check confirms `c` at the general V3
  positions, and the blocking reason is limited to competing runs or targeted-
  position mismatches.
- **Confirmed region.** The reference time ranges of chunks that agree with the
  global lag, minus:
  - every chunk in a competing run;
  - every chunk with a V5a mismatch;
  - one chunk of safety margin on each side of any excluded chunk, because an
    edit's exact position inside a chunk is unknown. The margin could later shrink
    by probing video frames near the boundary;
  - the time ranges the video check records as `local_video_inconclusive` (plan
    V5a). These are unverified, not proven content differences: a same-length
    replacement, low motion or weak discrimination all look alike. The current plan
    applies the offset over them (the refusal principle); here they are only kept
    out of frame selection, which is the safe direction.

  Because sampling is sparse, unverified ranges found this way are a subset of the
  real ones. A denser video scan of the selectable region is a possible later
  refinement if screenshots of differing content turn out to matter.

  Map the ranges to reference frames via `fps_reference`; the comparison frame is
  `reference frame - c`, as usual.
- **Minimum coverage.** If the confirmed region covers less than a set share of the
  shared overlap (a proposed 50%, to be calibrated), fall back to the current
  provisional behaviour.
- **Several comparisons.** Frames are selected in the reference domain and shared by
  all comparisons, so the selectable region is the intersection of every
  comparison's confirmed region. If that becomes too small, fall back to provisional
  for the offending comparisons, or ask the maintainer (see the open questions).
- **Frame selection.** Restrict the analysis and selection candidates (dark, bright,
  motion and random frames) to the selectable region, reusing the existing
  post-alignment reselection path (`_reselect_frames_for_trimmed_overlap` and
  `_selectable_aligned_source_window` in `orchestration/phase_alignment.py`). That
  path already reselects when trims shrink the overlap; it would gain a list of
  allowed ranges instead of one window. Explicit `user_frames` outside the region
  are kept, but marked in the report as unverified (or dropped with a warning; see
  the open questions).
- **Authority and persistence.**
  - The applied offset is a new, explicit state or reason, for example
    `trusted_automatic` with a `confirmed_ranges` field, or a distinct
    `trusted_partial`. It must never look like a full-program confirmation.
  - Don't write it to the shared computed cache at first; a cache entry would need
    the ranges, which is a cache-schema change. Manual confirmation in VSView stays
    available and would override it.
- **Presentation.**
  - Terminal: `Audio alignment accepted for 0:00-9:00 and 9:34-42:10: +147f -
    APPLIED (sources differ after 9:02; frames limited to matching regions)`.
  - The HTML report gets a short notice naming the compared ranges and the excluded
    ranges with their competing offsets.
  - The VSView panel shows the regions, with the excluded ones marked.
- **Diagnostics.** The confirmed and excluded ranges, the margin applied, the
  coverage share, and the per-comparison intersection.

**Acceptance cases (synthetic A/V, at least 10 minutes):**

- An insert near the start, near the end, and in the middle: applied, with every
  selected frame inside the confirmed region and pixel-matched at `c`.
- A middle replacement (same length, different content): the replaced span is
  excluded, frames elsewhere are applied.
- An edit in the last chunk: that chunk is excluded, the rest applied.
- Coverage below the minimum: provisional, as today.
- Two comparisons with different edits: the intersection is respected, and the
  fallback is exercised when it is too small.
- `user_frames` inside and outside the region.
- Report and terminal copy tests.
- Real media: at least one labelled different-cut pair, where no selected frame may
  fall in a mismatched region.

**Open questions for the maintainer:**

- Should this run by default, or behind an explicit config option? The replacement
  stance prefers no new options.
- For `user_frames` outside the region: keep them and label them as unverified, or
  drop them with a warning?
- What minimum coverage share is acceptable? Should the fallback for several
  comparisons be per comparison or for the whole run?
- Should partial results ever be cached as computed authority?

**Risks:**

- Edit boundaries are only known to chunk resolution (30 s). The margin trades
  coverage for safety.
- Frame selection and the report are hotspot surfaces (`services/report/**` gets
  extra scrutiny per the runbook).
- A wrong region boundary would silently compare mismatched frames, so the V5a check
  must also cover sampled positions near each region edge.
