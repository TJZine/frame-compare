---
search:
  exclude: true
---

# U4 review copy and layout (P4 / P4a)

**Status:** binding presentation spec for U4 (W4). It implements plan clauses P4 and
P4a within the existing terminal style tokens and the existing VSView panel sections
and actions. It adds no new panel section, control or style token.

## Who reads this, and what they need

The reader is one person comparing releases. The alignment either applied, or it
stopped short and they must decide in under a minute whether to trust the
suggestion. So each result leads with the outcome, then says why in plain words,
then says where to look. Technical evidence stays one level down, in verbose output
and the panel details.

**Tone rule (from the refusal principle):**

- Weak or local evidence (mix or level differences, quiet sections, local checks
  that were inconclusive) is **context**. It renders `MUTED`, never `WARN`, and is
  never worded as a problem.
- Only the unapplied outcome line and the reason for **not applying** render `WARN`.
- Applied results render `OK` and stay one line plus context.

## Shared vocabulary (use these words everywhere)

- **offset:** signed frames, always with sign and `f`: `+147f`, `+0f`, `-3f`.
- **section:** the user-facing word for an audio chunk. Never "chunk" or "window" in
  normal output.
- **check point:** one position where reference and comparison frames are compared.
- **Times:** reference video time, `m:ss` below one hour and `h:mm:ss` from one
  hour. The panel uses an en dash for ranges and `↔` for check points
  (`8:30–9:00`, `reference 13,123 ↔ comparison 12,880`). The terminal uses ASCII only
  (`8:30-9:00`, `<->`), matching its existing plain ` - ` convention and the
  Windows ASCII-safety acceptance. Frame numbers are reference and
  comparison **source** frames, with thousands separators: `13,123`.
- **Reason tokens** (`competing_offset` and the rest) never appear alone in normal
  output. They appear only in verbose `Decision` rows and the panel details.

## Suggested offset shown (P4a item 1)

Show the video-confirmed `c` when the video confirmed one. Otherwise show the audio's
rounded `r`. When the audio failed but the video confirmed a frame (V6), show that
frame.

## Reason sentences (P4a item 2)

Use one sentence per recorded reason, primary reason first, in V6's order.
`{o}` is the suggested offset, `{alt}` a region's offset, `{region}` a time range
(for example `9:02–9:32`), and `{n}` a count.

| Reason | Sentence |
| --- | --- |
| `competing_offset_confirmed_by_video` | `The video confirms {alt} in {region}, so the sources likely differ by an edit there.` |
| `competing_offset` | `Audio in {region} points to {alt}, and the video could not settle which offset is right there.` |
| `unresolved_audio_disagreement` | `Audio in {region} points to {alt}, and the video could not rule that out.` |
| `unresolved_audio_disagreement` (unexamined, budget reached) | `Audio in {n} more sections points elsewhere; they were not checked, so the offset is not applied.` |
| `video_check_inconclusive` | `The audio points to {o}, but the video could not confirm the exact frame (little motion or different framing at the checked points).` |
| `video_check_unavailable` | `The audio points to {o}, but the video could not be read to confirm the exact frame.` |
| audio failed, video confirms (V6) | `The audio does not agree on one offset across the track; the video suggests {o} at the checked points.` |

Unavailable results keep today's line, `No usable audio candidate ({phrase}) - NOT
APPLIED`, with the existing phrases.

## Regions (P4)

A region is a time range with its offset and how it was settled. Its status word is
one of: `confirmed by video`, `not settled`, `not checked`.

Normal output shows at most 3 region lines, then `and {n} more regions`. Verbose
output and the panel details show every region. The majority region (`c`) is always
listed first.

```text
  +147f  0:00–9:00   confirmed by video
  +243f  9:02–10:00  confirmed by video
```

## Check points (P4a item 4)

- List at most 5: each disagreeing or inconclusive region first (one point each, the
  highest-PSR target inside it), then one confirmed point for contrast.
- Format: `{time}  reference {ref_frame} ↔ comparison {cmp_frame} ({offset})`, where
  `cmp_frame = ref_frame - offset`.
- Frames come from the single V3a conversion (the same function as targets).
- Normal output shows the top 2; verbose output and the panel details show all.

**Click-to-jump: not in U4 (decision).** Moving the VSView playheads from a check
point would create captured positions at the suggested offset, which is effectively
prefilling a provisional value and would satisfy readiness. P4a forbids both. Check
points are shown as selectable text, and the user seeks with VSView's existing
frame entry. Revisit only with a separate design that seeks without capturing.

## Terminal: normal output (per comparison)

Each block is one comparison. Column 1 is the style token, then the text. Existing
prefix: `Comparison {i} - `.

### Applied, with recorded context (trusted_automatic)

```text
OK     Comparison 1 - Audio alignment accepted: +147f - APPLIED
MUTED  No additional confirmation needed.
MUTED  Noted: audio differed in 1 section (4:12-4:42); the video confirmed +147f there.
```

The `Noted` line appears only when resolved disagreements, same-frame context or
content differences were recorded. It summarizes them in one line:
`Noted: audio differed in {n} section(s) ({first region}[, …]); the video confirmed
{o} there.` If only content differences were recorded (V5a neither-wins at
non-credible targets), it reads
`Noted: the picture differs in {region} (for example a replaced shot); the offset
still holds.`

### Provisional: competing offset confirmed by video

```text
WARN   Comparison 1 - Provisional audio candidate: +147f - NOT APPLIED
WARN   The video confirms +243f in 9:02-10:00, so the sources likely differ by an edit there.
MUTED    +147f  0:00-9:00   confirmed by video
MUTED    +243f  9:02-10:00  confirmed by video
MUTED  Check 9:15  reference 13,123 <-> comparison 12,880 (+243f)
MUTED  Check 4:30  reference 6,474 <-> comparison 6,327 (+147f)
MUTED  Align manually or keep the current alignment.
```

### Provisional: competing offset (not settled)

```text
WARN   Comparison 1 - Provisional audio candidate: +147f - NOT APPLIED
WARN   Audio in 9:02-10:00 points to +243f, and the video could not settle which offset is right there.
MUTED    +147f  0:00-9:00   confirmed by video
MUTED    +243f  9:02-10:00  not settled
MUTED  Check 9:15  reference 13,123 <-> comparison 12,880 (+243f)
MUTED  Check 4:30  reference 6,474 <-> comparison 6,327 (+147f)
MUTED  Align manually or keep the current alignment.
```

### Provisional: unresolved audio disagreement

```text
WARN   Comparison 1 - Provisional audio candidate: +147f - NOT APPLIED
WARN   Audio in 5:00-5:30 points to +150f, and the video could not rule that out.
MUTED    +147f  0:00-10:00  confirmed by video
MUTED    +150f  5:00-5:30   not settled
MUTED  Check 5:12  reference 7,482 <-> comparison 7,332 (+150f)
MUTED  Check 2:00  reference 2,877 <-> comparison 2,730 (+147f)
MUTED  Align manually or keep the current alignment.
```

When unexamined sections exist, also add
`WARN   Audio in {n} more sections points elsewhere; they were not checked, so the
offset is not applied.`

### Provisional: video inconclusive or unavailable

```text
WARN   Comparison 1 - Provisional audio candidate: +146f - NOT APPLIED
WARN   The audio points to +146f, but the video could not confirm the exact frame (little motion or different framing at the checked points).
MUTED  Check 4:30  reference 6,474 <-> comparison 6,328 (+146f)
MUTED  Align manually or keep the current alignment.
```

`video_check_unavailable` uses its own sentence and shows no check points.

## Terminal: verbose output (adds, after the normal block)

The rows use the existing key/value style (`VALUE` values, key column muted).

```text
Established   Audio: 38 of 40 sections agree on +147f (2 differ, 0 quiet).
              Video: confirmed +147f at 11 of 12 check points (median margin 3.2×).
Regions       +147f  0:00-9:00   confirmed by video
              +243f  9:02-10:00  confirmed by video (3 of 4 targeted points)
Context       2 sections differ by less than a frame (sub-frame); not a disagreement.
              Picture differs in 5:00-5:04 (for example a replaced shot); offset still holds.
Check points  9:15  reference 13,123 <-> comparison 12,880 (+243f)
              9:40  reference 13,723 <-> comparison 13,480 (+243f)
              4:30  reference 6,474 <-> comparison 6,327 (+147f)
Decision      state=provisional; reason=competing_offset_confirmed_by_video; also=none
Evidence      (existing audio_evidence_rows lines follow unchanged)
```

- `Established` always has both lines.
- `Context` appears only when something was recorded.
- Raw U1 versus A4b recount, when they differ:
  `Audio (raw): 14 of 20 sections agree; 6 more are within the same frame, so 20 of
  20 agree for this offset.`

## JSON mode

Stdout is unchanged. The existing structured stderr review event keeps its shape;
only its reason values extend to the new V6 reasons. No new fields.

## VSView panel

**Persistent "Audio evidence" section** (per comparison, above the lineup). It uses
the same content as terminal normal output, in the panel's existing styles, with an
em dash instead of a hyphen, as today:

```text
Provisional audio candidate: +147f — NOT APPLIED
The video confirms +243f in 9:02–10:00, so the sources likely differ by an edit there.
  +147f  0:00–9:00   confirmed by video
  +243f  9:02–10:00  confirmed by video
Check 9:15 — reference 13,123 ↔ comparison 12,880 (+243f)
Visual confirmation required to use this hint.
```

- The last line is the existing panel guidance for provisional states. It replaces
  the terminal's action sentence, because the panel's actions are right there.
- Applied states keep today's lines, plus the one `Noted:` context line when present.

**Collapsed "Audio evidence details — Comparison N"**: the verbose block above
(Established, Regions, Context, all Check points, Decision), followed by the
existing evidence rows.

**Actions:** unchanged (`Confirm these aligned positions`, `Enter alignment
manually…`, `Keep current alignment`). Provisional values never prefill inputs,
move playheads, mark sources visited or count toward readiness. Check points are
selectable text only.

## Tests W4 must add

- Every reason above in normal, verbose and panel output: the exact strings with
  representative values.
- The `and {n} more regions` truncation at 4 regions.
- The time formats: `m:ss` and `h:mm:ss`.
- Frame numbers with thousands separators.
- Check-point ordering and the cap of 5.
- The applied `Noted:` line only when context exists.
- JSON stdout byte-identical.
- The frozen-strings updates.
