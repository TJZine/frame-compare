---
search:
  exclude: true
---

Status: Active
Scope: Replace the distributed-window audio estimator with whole-track chunked GCC-PHAT correlation plus container start compensation, and add an L-SMASH video frame check that picks the exact applied frame.
Owner: Audio alignment parity controller session; branch `agent/audio-alignment-parity` in the main checkout, merged into `dev/v0.6.0-review-remediation`.

# Audio alignment: whole-track estimator and video frame check

## Baseline

- Main checkout `/Users/tristan/Software/frame-compare`,
  branch `agent/audio-alignment-parity`, created from
  `origin/dev/v0.6.0-review-remediation` at `d7b069d5`. The branch merges back into
  `dev/v0.6.0-review-remediation`; no push, PR, release or signing is authorized by
  this plan.
- Authorities: `AGENTS.md`, `docs/ENGINEERING_RUNBOOK.md`,
  `docs/current-architecture.md`, `docs/current-cli-contract.md`,
  `docs/guides/audio-alignment.md`, `importlinter.ini`, `pyproject.toml`.
- Supersedes [2026-09-22 post-activation remediation](2026-09-22-audio-alignment-post-activation-remediation-and-ux.md),
  which this plan's P0 marks Historical. Its W1 Windows acceptance of the old estimator
  is no longer required. The [2026-09-14 plan](2026-09-14-audio-alignment-trust-and-diagnostics.md)
  stays Historical; its measurements remain evidence. Where its rules conflict with
  this plan (no timestamp compensation, fixed 0.90 waveform floor, single FFmpeg child,
  no new representation), this plan governs.
- Shipped policy token being replaced:
  `continuous-origin-qualified-channel-corroboration-2097152-v2-temporal-invariants-20260922`.

## Goal and product bar

The maintainer's bar: automatic alignment must be at least as accurate as v0.1.0
(`57a11cbb`, one whole-track cross-correlation, no quality gates) and must not fail
because releases have different mixes, downmixes, codecs or masters. It must also
refuse, rather than apply, when it detects that no single constant offset exists
(within the sampling contract and limits stated in V5a) or that the audio is
unrelated. Memory stays bounded; the v0.1.0 whole-track FFT (several GB) is not
reintroduced.

Non-goals: drift or speed correction (24 vs 23.976, PAL speed-up), edit matching or
per-segment offsets, variable-frame-rate sources (expected outcome: provisional,
usually `video_check_inconclusive`), new CLI flags, native macOS L-SMASH support
(Docker and Windows are the supported routes), a VSView redesign, and cache or
diagnostic migration.

## Evidence behind the decisions

Recorded by the controller session on 2026-09-25 using the local, untracked
`tools/alignment_benchmark.py` (v0.1.0 estimator extracted verbatim from `57a11cbb`,
current production via `_estimate_audio_pair`, and a prototype of this design).

Synthetic matrix: 180 s program, 5.1 AC-3 reference, E-AC-3/AAC comparisons, native
macOS FFmpeg 9.0.2. v0.1.0 used the opposite sign convention; its magnitudes are
compared.

| Case | Truth | v0.1.0 | Production | Prototype (audio stage) |
| --- | --- | --- | --- | --- |
| Same 5.1 mix | -5f | correct | correct | correct |
| Studio stereo downmix vs 5.1 | +7f | correct | correct | correct |
| Music stem -8 dB (remix) | -5f | correct | provisional only | correct |
| Remaster (EQ, limiter, noise) | -5f | correct | correct (score 0.91) | correct |
| Foreign dub, same M&E | -2f | correct | provisional only | correct (PSR 88-120) |
| Added noise at about +15 dB SNR (noise 15 dB below the signal; earlier mislabelled as -15 dB) | -4f | correct | correct | correct |
| 20 s extra intro | -480f | correct | correct | correct |
| Container audio delay 0.5 s, video identical | 0f | applied 12f | applied 12f | correct (start compensation) |
| 4 s insert at 90 s | refuse | applied | refused | refused, located -3f / -99f segments |
| 0.1% speed drift | refuse | applied | refused | refused |
| Unrelated program | refuse | applied (score 0.02) | refused | refused (PSR 5-8) |

Real media (one episode, three releases: Blu-ray remux DTS-HD MA, Blu-ray encode
AC-3, AMZN WEB-DL E-AC-3; all 5.1(side), 24000/1001, container start times 0).
Truth is the visually confirmed frame (pixel difference at frames 12000/30000 plus a
maintainer-inspected still). Audio lags were sample-identical on native FFmpeg 9.0.2
and Docker FFmpeg 7.1.5.

| Pair | Truth | v0.1.0 | Production | Prototype audio (sub-frame) | Prototype + video check (Docker L-SMASH 1310) |
| --- | --- | --- | --- | --- | --- |
| Remux to encode | 0 | 0 | 0 | 0 (-0.32f) | 0, 12/12 positions, margin 8.3x |
| Remux to WEB-DL | 147 | 146 | 146 | 146 (+146.23f) | 147, 12/12, margin 3.2x |
| Encode to WEB-DL | 147 | 147 | 147 | 147 (+146.55f) | 147, 12/12, margin 2.8x |

Conclusions carried into this plan:

1. The 0.90 waveform score measures mix similarity, not timing; it is the recall
   bottleneck (also R6B finding 2). Chunked GCC-PHAT prominence plus cross-chunk
   agreement separates true matches (PSR 88-984) from unrelated audio (5-8) with a
   wide margin and is insensitive to mix and level.
2. Container start offsets are ignored today and produce confidently applied wrong
   offsets.
3. Audio alone fixes the offset only to within about one frame: each release's audio
   can sit tens of milliseconds differently relative to its own video, and no
   metadata records it. A video check on the neighbouring frames resolves this.
4. Rank normalization of luma makes the video check invariant to any monotonic tone
   curve; a simulated PQ-vs-SDR case kept the same 3.5x margin, whereas mean/std
   normalization fell to 1.3x.
5. Cost per comparison in Docker: production 21-46 s; prototype audio about 17 s
   (sequential decode plus 6.4 s analysis for 57 min); video check 4-5 s with
   existing indexes.

## Replacement stance

This is a total replacement with one user and tester. The old estimator, its config
fields, schemas, cache entries and review metadata are removed rather than kept
alongside, adapted, migrated or given special error paths. Existing generic behaviour
(unknown config keys rejected, stale cache tokens missing, old metadata versions
rejected) is sufficient. Every unit prefers deletion over adaptation and adds no
abstraction, option or fallback that a current requirement doesn't need.

## Refusal principle

Added 2026-09-26 at the maintainer's direction. The previous implementation refused
three sources with matching offsets because their audio differed in level and mix in
places. That class of false refusal must not come back.

- Automatic application requires sufficient **global** audio and video
  confirmation: A4 agreement, V5 confirmation and, where relevant, the V5a
  resolution. Unrelated audio or globally inconclusive video still cannot establish
  an automatic offset.
- **Local** weak or missing evidence does not independently veto an otherwise
  confirmed offset. Examples: low PSR from mix, level or loudness differences; quiet
  or inactive sections; a non-credible chunk; a `local_video_inconclusive` record at
  a non-credible target. It is recorded and shown as context.
- **Credible** evidence of another offset must be resolved before application:
  coherent competing runs (A4a), and credible disagreeing chunks under V5a. An
  unresolved credible disagreement blocks because the contradictory audio evidence
  remains, not merely because the local video was inconclusive.
- Credible audio disagreements are **resolved by video**, never vetoed
  unconditionally. PHAT whitening removes level and spectral-shape differences
  (loudness, dynamic range, EQ, codec), but not multipath content. When a mix
  contains the same material at two lags (a delayed surround or effects copy, a
  reverb tail) and a release changes which copy is louder, the audio peak can
  genuinely move for a few chunks. Over identical video, the video resolves such a
  disagreement in favour of the confirmed offset, and the result applies. A real
  edit's frames match the competing offset instead, so it stays blocked. Avoiding
  mix-caused false refusals of this kind is a primary goal of this redesign.
- Disagreements that cannot change the compared frame never need resolving (A4b).
- U4 tests pin all of this: level and mix changes, the multipath lag reversal, and
  same-frame disagreements.

## Locked decisions

Confirmed with the maintainer on 2026-09-25.

### Audio stage

- A1. Whole-track chunked correlation replaces discovery/verification windows: 8 kHz
  mono (existing `mono_downmix` / `best_channel` channel treatment), reference chunks
  of length `C` tiled from reference sample 0, each searched over lags `[-M, +M]`,
  where `M = max_offset_seconds` (default 30 s). Lag definition: `lag = i_ref - i_cmp`,
  the reference PCM sample index minus the comparison PCM sample index of the same
  content, so positive lag means the content occurs later in the reference. U1 pins
  this sign with a test. Comparison samples outside the stream are zero.
- A1a. Chunk length: `C = clamp(floor(D / 3), 5 s, 30 s)`, where `D` is the shorter
  selected-stream duration; if `D < 5 s`, one chunk of length `D`. A final partial
  chunk is analysed if it is at least `C / 2` long and dropped otherwise. This keeps
  short sources (which v0.1.0 aligned) eligible instead of requiring 90 s.
- A1b. Admission: the per-chunk FFT is at most 2^22 points
  (`C + 2M <= 4,194,304` samples at 8 kHz, so `M <= 247 s` at `C = 30 s`). Requests
  beyond that return the existing non-applied `analysis_budget_exceeded` result
  before any decode. There is no schema change to `max_offset_seconds`.
- A2. Per chunk: GCC-PHAT cross-correlation (full whitening). A chunk is active only
  if both its reference chunk and its comparison search segment have RMS above
  -50 dBFS. Chunk PSR = (peak - median) / (1.4826 x MAD) over lags outside +/-20 ms
  of the peak.
- A3. Credible chunk: PSR >= 25. A global lag exists only when at least one chunk is
  active; it is the argmax of the sum of active chunks' PHAT correlations. With no
  active chunk the result is `unavailable` / `no_usable_audio`.
- A4. Audio agreement: a credible chunk agrees when `|lag - global| <= 2 ms`. The audio
  stage passes only when agreeing >= `min(3, analysed chunks)` (and at least 1) and
  agreeing >= 0.8 x credible. Otherwise the result is `no_single_offset` and
  diagnostics report contiguous chunk runs grouped by lag (edit or drift diagnosis,
  never an applied value). A global lag within 2 ms of +/-M is `search_edge` and never
  applied. M bounds the PCM lag, not the compensated offset.
- A4a. Coherent competing offset (added 2026-09-26 after external review). Majority
  agreement alone does not prove one constant offset: a 4 s insert near either end
  of a 10-minute program leaves 18/20 or 19/20 chunks agreeing, which passes A4.
  - A competing run is at least 2 credible chunks with **consecutive** chunk indices
    whose lags agree with each other within 2 ms and differ from the global lag by
    more than 2 ms. That is about 60 s of continuous disagreement at `C = 30 s`, which
    scattered measurement errors don't produce. U1's `ChunkRun` does not break at
    non-credible gaps (it serves stability diagnostics and stays unchanged), so the
    decision layer checks index adjacency itself.
  - A competing run must be **resolved by the video** (V3a, V5a) before automatic
    application. Resolved in favour of the confirmed offset `c`, it is recorded as
    context and doesn't block. If the video confirms the run's own offset, the
    result is `competing_offset_confirmed_by_video`. If it stays unresolved or
    unexamined, the result is `competing_offset`. Both are provisional hints whose
    evidence and copy name every run's frame offset and time range. A run is judged
    against `c`, so it exists only for frame-distinct disagreements (A4b).
  - Single credible disagreeing chunks, which can come from repeated music cues or
    an edit inside the last or first chunk, don't block the audio stage. A competing
    region interrupted by a quiet chunk also breaks into singles. Singles are
    recorded and checked by the video stage (V3a, V5a).
  - Implemented in `alignment_decision.py` from existing runs in U4; U1's numeric
    outcome is unchanged. U3 applies nothing, so it needs no change.
- A4b. Same-frame disagreements (added 2026-09-26). A credible chunk whose lag
  differs from the global lag by more than 2 ms can still map to the same video
  frame. At 24 fps half a frame is about 21 ms, and mix differences produce shifts
  of that size. Video can never tell such a disagreement apart, so it must not
  block.
  - For each chunk, `x_chunk` is its compensated sub-frame position (A5/A6 applied
    to the chunk's own lag) and `r_chunk = floor(x_chunk + 0.5)`.
  - After the video confirms `c` (V5), a disagreement is **frame-distinct** only if
    `r_chunk != c`.
  - Chunks with `r_chunk == c` count as agreeing for authority purposes, are never
    targets, and are recorded as sub-frame context in verbose output and the panel
    details.
  - A4a runs and V3a targets consider only frame-distinct disagreements.
  - **Authority agreement gate.** A4b changes A4's pass/fail for authority, not only
    targeting. After V5 confirms `c`, recompute the agreement count with
    frame-level agreement: a credible chunk agrees when its lag is within 2 ms of
    the global lag, or when `r_chunk == c`. Then apply A4's rules to that count:
    - agreeing >= `min(3, analysed chunks)` (and at least 1);
    - agreeing >= 0.8 x credible;
    - not `search_edge`.

    Several same-frame disagreements therefore can't fail the gate on their own.
    U1's raw numeric outcome (the 2 ms agreement, `agreed` / `no_single_offset`) is
    kept unchanged as evidence and shown in verbose output. The V6 trusted predicate
    uses the recomputed authority gate. Without a confirmed `c` there is no
    recount, and the result is provisional or unavailable as before.
- A5. Container start compensation per source:
  `offset_seconds = lag_seconds + (audio_start_ref - video_start_ref) - (audio_start_cmp - video_start_cmp)`,
  with `lag_seconds = lag / 8000` under A1's definition. It uses ffprobe `start_time`
  of the selected audio stream and of the first video stream that is not an
  `attached_pic` (the track L-SMASH decodes). A missing start time counts as 0 and is
  recorded as `default_zero`. The formula assumes decoded PCM sample 0 is at the
  audio stream's `start_time`; U3's fixtures prove this on both runtimes.
- A6. The sub-frame estimate `x = offset_seconds x fps_reference` is kept as evidence;
  applied frames come only from the video stage. `r = floor(x + 0.5)`.
- A7. Collection: reference and comparison are decoded concurrently by two FFmpeg
  children read in lockstep, with bounded memory: one reference chunk, one comparison
  window of `chunk + 2M`, fixed-size pipe queues and FFT scratch. No whole-track PCM,
  no disk PCM, no cross-comparison PCM cache (the reference is decoded again per
  comparison; that decode overlaps the comparison decode). Children keep the default
  `close_fds=True`, so neither inherits the other's pipe ends. Existing cancellation,
  first-error precedence, stderr bounds and cleanup-failure fatality are preserved.
  On any failure or cancellation, both children are sent terminate before any join
  wait begins; kill and join then follow the existing bounds.
- A7a. Authority of streamed evidence: blocks are checked for finiteness before
  delivery, but accumulated correlation state and chunk rows become usable only after
  both children exit 0, both readers finish, and cleanup completes. Any failure
  discards the accumulated state; failed collections never yield a result or partial
  evidence beyond scalar collection facts.
- A8. Deadlines: the fixed 120 s total per FFmpeg invocation is replaced by a no-progress
  watchdog and a total cap. Progress means the consumer received a block from the side
  it is currently waiting on; the reference side, deliberately held back by
  back-pressure, is never timed out for that. The watchdog fires after 30 s without
  progress. The total cap is `120 s + 0.1 x max(known selected-stream durations)`. If
  neither duration is known, the existing non-applied `selected_audio_timeline_unavailable`
  refusal stands. Collection ends at EOF; output beyond `known duration + 60 s` is
  `output_exceeded` (a failure).

### Video stage

- V1. Runs whenever the audio stage yields a global lag (passing or not), using the
  run's own L-SMASH sources through the existing `VSLoader`. No FFMS2 or other loader
  fallback.
- V2. Scored offsets: `r - 2 ... r + 2`. Only `r - 1, r, r + 1` can be confirmed.
- V3. Positions: 12, evenly spaced over the middle 90% of the raw-frame overlap valid
  for all candidates. Each position compares reference frame `n` with comparison frame
  `n - candidate` in raw source frames (public sign convention; base trims do not
  enter).
- V3a. Targeted positions (added 2026-09-26, revised the same day). In addition to
  the V3 positions, sample positions inside the reference time range of each target
  chunk: 4 evenly spaced positions for a credible disagreeing chunk, 2 for a
  non-credible one. They are mapped to reference frames and kept only where valid
  for every frame they are compared at.
  - Targets are chosen after V5 confirms `c`, from frame-distinct disagreements
    only (A4b), in priority order:
    1. competing runs (A4a): 4 positions spread evenly across the run's time range;
    2. single credible disagreeing chunks: 4 positions each, highest PSR first;
    3. active non-credible disagreeing chunks: 2 positions each, highest PSR first.
  - At most 12 targeted positions in total, in that priority order. A competing run
    or credible chunk that gets no position because the budget ran out is
    **unexamined**. It counts as unresolved and blocks automatic application
    (`competing_offset` or `unresolved_audio_disagreement`); skipping a target
    never counts as resolving it.
  - Audio-to-video time conversion (A5's assumption that decoded PCM sample 0 sits
    at the audio stream's `start_time`):
    - reference video time for reference PCM sample `k` is
      `t = k / 8000 + audio_start_ref - video_start_ref`;
    - reference frame = `floor(t x fps_reference)`;
    - positions are clipped to frames valid for every offset they are compared at.
      A target with no valid position is unexamined.
  - The P4a check points use the same conversion.
  - Targeted positions never count toward V5's confirmation vote. They are judged
    only by V5a.
- V4. Frames: luma, crop to each clip's resolved active rect (resolved during
  preparation, before any phase), bilinear downscale to 320x180, rank-normalize with
  average ranks for ties, mean absolute difference.
- V5. Per position, over the five scored offsets: the best offset must be a strict
  local minimum (both neighbours score worse). A position is informative when it has a
  strict local minimum and runner-up / best >= 1.1; best = 0 with runner-up > 0 counts
  as an infinite margin, and all-zero or tied scores are uninformative. The video stage
  confirms `c` when `c` is in `r - 1 ... r + 1`, there are >= 6 informative positions,
  `c` wins >= 75% of them, and the median margin over the positions `c` wins is
  >= 1.5 (clarified 2026-09-27: the 75% rule already counts losses; the margin
  measures how decisive `c`'s wins are, and rivals' margins are not evidence for
  `c`). A winner at `r +/- 2` is
  `video_check_inconclusive` (the audio is off by more than a frame).
- V5a. Targeted hypothesis check (added 2026-09-26, revised the same day). At each
  targeted position, compare two video hypotheses:
  - the confirmed offset `c`;
  - the alternative: the target's own audio lag, compensated and converted to frames
    per A5/A6 (`r_chunk`; for a run, the run's true median lag, which may fall on a
    half sample; it is computed in the decision module, leaving U1's `ChunkRun`
    unchanged), scored at the distinct
    offsets `{r_chunk - 1, r_chunk, r_chunk + 1}` minus `c`. The alternative set
    never contains `c`, so a shared candidate can't create false ambiguity. A4b
    guarantees `r_chunk != c`, so the set is never empty.

  Each hypothesis takes its best (lowest) difference over its offsets. The better
  hypothesis wins when the other's difference divided by its own is at least 1.5
  (the V5 margin). Rules:
  - exact ties count as neither;
  - a best difference of 0 against a non-zero one is an infinite margin;
  - both 0 counts as neither.
  - **`c` wins:** consistent; the audio disagreement there is resolved as a false
    audio match.
  - **The chunk lag wins:** a video-confirmed competing offset, meaning a
    length-changing edit. Blocks automatic application.
  - **Neither wins:** `local_video_inconclusive`. This can mean replacement content,
    low motion, a wrong alternative lag or weak visual discrimination; it is not
    proof of a content difference. It is recorded with its time range and scores.
    - For a **non-credible** target chunk it never blocks (weak audio evidence,
      refusal principle).
    - For a **credible** disagreeing chunk the disagreement stays unresolved. The
      chunk is resolved only when `c` wins at one or more of its positions and the
      alternative wins at none. An unresolved single credible chunk gives
      `unresolved_audio_disagreement`.
    - A **competing run** (A4a) is resolved only when `c` wins at 2 or more of the
      run's positions and the alternative wins at none. An unresolved or unexamined
      run gives `competing_offset`. Resolving a run resolves all of its member chunks
      for V6: they are not separate targets and don't each need their own 4
      positions.

    Credible disagreement is positive audio evidence of another offset, so it has to
    be explained by the video, not ignored.

  Every decision is relative between hypotheses, so no absolute difference threshold
  exists to calibrate. A garbage lag from a non-credible chunk almost never wins a
  video comparison, which is why including those chunks is safe.

  Stated contract and limits:
  - Automatic application is withheld for every frame-distinct competing run (A4a)
    and every frame-distinct credible disagreeing chunk that is unexamined or
    unresolved under V5a, or whose own offset the video confirms.
    This is the enforceable guarantee. It is not a claim that every length-changing
    edit touching credible audio is refused: V5a resolves a chunk from sampled
    positions, so a chunk straddling an edit (moving video confirms `c` before the
    edit, low motion stays inconclusive after it) can resolve in favour of `c`. In
    practice the following chunks usually carry the shifted lag and form a competing
    run, but sampling doesn't prove it.
  - An edit whose shifted part has only active but non-credible audio is refused
    when a targeted position samples it and the video confirms the competing
    offset. Sparse sampling can't guarantee this.
  - An edit whose shifted part is entirely silent or inactive audio produces no
    audio target and is outside this check. It is covered only by this documented
    limit.
  - Same-length replacements are applied by design: the constant offset is still
    correct, and only content differs. Keeping comparison frames out of unverified
    regions belongs to the region-limited follow-up in `docs/TODO.md`.
- V6. Outcomes:
  - **Trusted predicate.** The result is `trusted_automatic` (applied frame `c`,
    reason `audio_video_confirmed`) if and only if **all** of these hold:
    - the audio stage passes the A4b authority agreement gate;
    - the video confirms `c` (V5);
    - every frame-distinct competing run (A4a) and every frame-distinct credible
      disagreeing chunk is examined and resolved in favour of `c` under V5a;
    - no V5a target of any kind has its alternative confirmed by the video.

    Records that don't block (`local_video_inconclusive` at non-credible targets,
    same-frame context, resolved disagreements) stay with the result and show in
    verbose output and the panel details. The predicate is one function in
    `alignment_decision.py`, never implied by branch order. Every other outcome
    below is `provisional` or `unavailable`.
  - A competing run that is unresolved or unexamined: `provisional` at `c`, reason
    `competing_offset`; the regions are shown.
  - Audio passes and video confirms `c`, but V5a confirms a competing offset at a
    targeted position: `provisional` at `c`, reason
    `competing_offset_confirmed_by_video`; the regions and their offsets are shown.
  - Audio passes and video confirms `c`, but a credible disagreeing chunk stays
    unresolved (V5a): `provisional` at `c`, reason `unresolved_audio_disagreement`;
    the unresolved regions, their audio offsets and the local video scores are
    shown.
  - When several reasons apply, all of them are recorded, and the primary reason is
    the first in this order: `competing_offset_confirmed_by_video`,
    `competing_offset`, `unresolved_audio_disagreement`, `video_check_inconclusive`,
    `video_check_unavailable`.
  - Audio passes and video is inconclusive: `provisional` at `r`, reason
    `video_check_inconclusive`.
  - Video cannot open or decode a source: `provisional` at `r`, reason
    `video_check_unavailable`.
  - Audio fails (`no_single_offset` or no credible chunks): never applied; if video
    still confirms, the hint shows the video-suggested frame.
  - Truth outside `r - 2 ... r + 2`: the strict-local-minimum rule makes a
    consistent confirmation there unlikely; U4 tests truths at `r +/- 2` and `r +/- 3`
    and requires `video_check_inconclusive`.
- V7. Video frame reads run in the existing alignment worker thread. They check the
  cancellation event after each source load and between positions, and re-check
  source identity (path/size/mtime) around the loads as the audio path does. If the
  owned `.lwi` index is missing (a probe-cache hit skips loading during preparation),
  `LWLibavSource` builds it inside the worker. That native call is not interruptible,
  and its cost is not new work: render needs the same index. Its duration is recorded
  in diagnostics. The video check never makes a run fail; failures become V6
  outcomes. A missing `VSLoader` gives `video_check_unavailable`.

### Authority, persistence and presentation

- P1. States stay `trusted_automatic`, `provisional` and `unavailable`. Only
  `trusted_automatic` reaches trims and the computed cache. Manual confirmation,
  VSView review, reuse precedence and the raw-offset/base-trim application
  conversion (AA-01) are unchanged.
- P2. New opaque policy token `whole-track-chunked-phat-video-check-20260925`; old
  computed and shared entries miss and recompute. Cache schema v2 and manual override
  v1 are unchanged. No migration. The `alignment` scope of the runtime fingerprint
  gains the video decoder identity (VapourSynth and L-SMASH versions), because
  applied frames now depend on L-SMASH frame numbering.
- P2a. Existing result fields keep a defined source. `stability` is derived from chunk
  runs, and cache v2 still requires it:
  - `stable` when the audio stage passes;
  - `possible_discontinuity` for two or more credible runs at different lags;
  - `possible_drift` when credible lags change monotonically;
  - `variable` otherwise;
  - `insufficient_evidence` with fewer than 3 credible chunks.

  `correlation_score` becomes the agreement fraction (agreeing / credible, 0..1). The
  phase warning branches that can no longer fire for applied results ("applied but
  drifting") are removed.
- P3. Diagnostic artifact schema v3 -> v4 and VSView metadata v4 -> v5, generated
  and parsed together. U3 defines them with a single five-offset video table
  (`not_observed`). U4 extends them for the 2026-09-26 amendments:
  - targeted positions with their target (chunk or run), the alternative offsets and
    both hypotheses' scores;
  - per-target resolution status (resolved, unresolved, unexamined, alternative
    confirmed) and the same-frame context;
  - the P4a check points.

  The shared parser, diagnostics writer, VSView contract and panel are updated
  together. The branch is unreleased, so U4 amends v4 and v5 in place without
  another version bump. Evidence: selected streams, start times and compensation, chunk
  runs (always), per-chunk rows (start, lag, PSR, active/credible/agree flags), global
  lag, sub-frame estimate, the video table (per-position differences for each scored
  offset, index-build time), decision and reason. Per-chunk rows are stored as
  compact arrays; about 22 KB for 3 h keeps the artifact well within the existing
  128 KiB cap, so no truncation path is added. Native metadata carries runs, not
  per-chunk rows. Native result v1 is unchanged. Older metadata is rejected and
  regenerated.
- P4. Terminal and VSView copy keeps the existing decision-first hierarchy and adds
  the reasons from V6 and A4. Applied states read
  `Audio alignment accepted: {offset} - APPLIED`, with verbose evidence
  `audio +146.23f, video confirmed +147f`. `competing_offset` and
  `competing_offset_confirmed_by_video` name the regions in normal output, for
  example `+147f from 0:00 to 9:00; +243f after 9:02`. Normal output keeps this to
  one line per region, up to 3 lines, then `and N more regions`.
- P4a. Review information (added 2026-09-26). When a result is not applied, the user
  gets everything needed to confirm or reject it quickly, in plain language, in both
  the terminal and the VSView panel:
  1. **Outcome first:** the suggested offset, preferring the video-confirmed one,
     and `NOT APPLIED`.
  2. **Why, in one sentence per reason, in plain words.** For example: "Audio
     suggests a different offset between 9:00 and 9:30 that the video could not
     rule out." Never an internal reason token on its own.
  3. **What was established:**
     - how much of the track agreed, for example "38 of 40 audio sections agree on
       +147f";
     - whether the video confirmed the offset, and at how many points;
     - the regions where evidence differs or was inconclusive, each with its time
       range and suggested offset.
  4. **Where to look:** a short list of check points (at most 5) with timestamp,
     reference frame and suggested comparison frame. The list covers each
     disagreeing or inconclusive region first, then one confirmed point for
     contrast.
  5. **What to do:** confirm this offset, enter another, or keep the current
     alignment. This uses the existing panel actions; provisional values never
     prefill inputs or satisfy readiness, as today.

  Weak evidence (level or mix differences, quiet sections, inconclusive local
  checks) is presented as context, never as an error or warning. Normal terminal
  output keeps items 1, 2 and 5 plus the top check points; verbose output and the
  panel's details show everything.

  UI design is collaborative (maintainer rule): before implementing the panel and
  terminal layout, U4 produces a short layout and copy mockup for the provisional,
  competing-offset and unresolved states, using the `interface-design` skill within
  the existing panel. It gets the maintainer's approval first. Whether a check point
  offers a click-to-jump action in VSView is decided in that mockup, since it
  touches the panel's captured-position semantics.

### Public configuration

- C1. `[audio_alignment]` keeps `enable`, `max_offset_seconds`, `channel_strategy`,
  `reference_stream`, `comparison_streams`, `use_vsview`, `force_interactive`,
  `cache_results` and `previous_offsets`.
- C2. The tuning fields of the replaced estimator are removed: `sample_rate`,
  `correlation_mode`, `preprocessing_mode`, `confidence_threshold`,
  `ambiguity_peak_ratio`, `window_length_seconds`, `window_stride_seconds`,
  `minimum_valid_windows`, `consensus_minimum_ratio`, `refinement_mode` and
  `refinement_sample_rate`. The schema already forbids unknown keys; a config that
  still sets a removed key fails through the schema's existing `extra="forbid"`
  unknown-key error. No custom message, acceptance or migration is added. Docs,
  `CHANGELOG.md` and the generated API reference are updated to match.

### Deletions

- D1. Deleted in U3 on this branch (the branch merges only after U5 passes):
  - channel corroboration and its schema and panel fields;
  - the discovery/verification staging, halos and duration tiers;
  - the waveform-score authority gate;
  - the score and FFT work budgets tied to windows (A1b's admission replaces them);
  - frame-bin contradiction grouping;
  - the internal authority-hold latch and its callers in
    `alignment_previous_offsets.py` and `alignment_reuse_cache.py`;
  - the `FRAME_COMPARE_CHANNEL_CORROBORATION` opt-in in
    `tools/verify_docker_integration.sh` and its pin in
    `tests/workflows/test_docker_integration_contract.py`;
  - obsolete oracle/policy tests whose target no longer exists.

  The historical scalar evidence under `tests/fixtures/alignment_oracle/` is kept on
  purpose as the record behind earlier plans; its README or plan references say so.

## Ownership

- `services/alignment_streaming.py`: paired lockstep collection (A7, A8). It is
  generalized from the single-child collector, not duplicated; there is no trust or
  cache policy here.
- `services/alignment_audio.py`: stream probing and selection, audio/video start
  probing (A5), FFmpeg recipe, no window planning.
- `services/alignment_correlation.py`: chunk PHAT, PSR, global accumulation and
  agreement (A2-A4) as pure numeric code.
- `services/alignment_consensus.py`: shrinks to the decision combining audio and
  video outcomes (V6, P1), or merges into its caller if little remains.
- New `services/alignment_video.py`: the V1-V5 check. It depends on
  `frame_compare.vs` (a lower layer) and must not import orchestration.
- `services/alignment.py`: workflow, attempt construction, presentation, diagnostics
  and cache precedence.
- `orchestration/phase_alignment.py` and `orchestration/execution.py`: the
  `VSLoader` (already present in `build_phases_before_align`) is passed to
  `run_align_phase` and on to the service as a separate argument, not inside
  `AlignmentRequest`: `utils/types.py` sits below `vs` in `importlinter.ini`. Active
  rects travel as primitive fields on `AlignmentClipRequest`. The phase's stability
  warnings follow P2a.
- `orchestration/alignment_report.py`, `services/alignment_stability.py`: P2a
  derivation.
- `vs/runtime_contract.py`, `docs/supported-media-runtime.md` and runtime-contract
  tests: P2's fingerprint scope.
- `services/types.py`, `alignment_diagnostics.py`, `alignment_vsview.py`,
  `vsview/session_script.py`, `vsview/alignment_review_contract.py`,
  `vsview/alignment_review_panel.py`: coordinated P3 schema.
- `config/schema_models.py`, `utils/types.py`: C1-C2.
- `tools/verify_docker_integration.sh`,
  `tests/workflows/test_docker_integration_contract.py`: D1 opt-in removal.
- Docs in the same pass: `current-architecture.md` (including the metadata-version
  row in its hotspot table), `current-cli-contract.md` (short-source and search-edge
  rules, config fields, cache and runtime fingerprint), `guides/audio-alignment.md`,
  `reference/commands-and-configuration.md`, `supported-media-runtime.md`,
  `docs/api.md` (generated), `CHANGELOG.md`.
- Import direction must keep passing `lint-imports`.
- Structure amendments (2026-09-25, controller, per the maintainer's architecture
  guidance):
  - The audio-evidence dataclasses move to a new
    `utils/alignment_evidence.py`, with one strict payload parser. The VSView
    contract validates the embedded attempt through that parser instead of
    re-describing the schema by hand, so the schema is defined once.
  - `services/alignment_decision.py` replaces `alignment_consensus.py` and absorbs
    `alignment_stability.py`.
  - Terminal evidence presentation moves from `alignment.py` to
    `services/alignment_presentation.py`.
  - `alignment_streaming.py` stays one module with a `_ChildStream` per-side class
    (U2 review).

  These refine the owners above; they add no product behaviour.

## Units

Execute in order. Each unit ends with its verification, a diff audit and a controller
commit on `agent/audio-alignment-parity`. Model choice happens at dispatch per the
runbook; the risk notes say why a unit is harder than it looks.

### P0 - Plan activation

Commit this plan and mark the 2026-09-22 plan `Status: Historical` with a one-line
pointer here. Commit: `docs(plan): activate whole-track audio alignment plan`.

### U1 - Chunked audio estimator (pure numeric)

Implement A1-A4 and A1a-A1b in `alignment_correlation.py` over in-memory arrays
with a streaming-shaped interface (chunk in, running state out), so U2 can feed it
incrementally. Track the synthetic program generator (seeded) as test support. Unit
tests cover:

- same/remix/downmix/dub/noise positives;
- both signs, with the A1 sign convention pinned;
- a long intro within M;
- an insert (two runs), drift and unrelated audio;
- silence (all chunks inactive) and a single credible chunk;
- the 79%/80% agreement boundary and a lag at the +/-M search edge;
- short sources (4 s, 20 s, 60 s) and partial final chunks;
- admission beyond A1b.

Expected outputs recorded from the controller's prototype (global lag in samples,
credible and agreeing counts, PSR bands) become test constants.

Risk: medium; pure code with direct proof.

### U2 - Paired lockstep collection

Implement A7-A8 in `alignment_streaming.py`: two children, bounded queues, a
look-ahead window of `chunk + 2M` for the comparison side, and delivery of aligned
(reference chunk, comparison window) pairs to a consumer callback, per A7-A7a-A8.
The plan comes from probed durations, so decoded length can differ slightly. A
reference that ends early zero-pads its final planned chunk to the planned count,
and chunks with no decoded reference samples are fed as all-zero (inactive), which
follows A1's rule that samples outside the stream are zero. Comparison windows must
equal `comparison_window()` from U1 value for value.
Preserve every existing lifetime guarantee: distinct reader errors, first-error
precedence, cleanup failure as fatal, no usable evidence after failure. Tests extend
the existing controlled-child suites:

- both children succeed;
- either child fails first, including good PCM followed by a nonzero exit (the result
  must be none);
- a non-finite block;
- one side stalls, firing the watchdog, while back-pressure on the other side does
  not;
- the total cap;
- unequal lengths, and one child reaching EOF while the other is still running;
- cancellation during decode, back-pressure and analysis;
- stderr floods;
- both children terminated before any join wait;
- at most 2 simultaneous children;
- retained buffers bounded independent of duration, with resource tests at 3 h
  synthetic and at the largest admitted M.

Windows handle-release proof is recorded as pending.

Risk: high (concurrent pipe and process lifetimes, Windows handle release). One
independent `deep_reviewer` pass on U2's diff before U3 starts.

### U3 - Integrate the audio stage and compensation

Wire U1+U2 into `_estimate_audio_pair` / workflow, add A5 start probing and the A6
sub-frame estimate and rounding. Produce
the full P3 schemas, with video fields `not_observed`, and the P2a stability and
score derivation. Install the P2 token, remove the C2 fields (with the removal
error), and perform the D1 deletions. Video is not wired yet: in this intermediate
state every audio pass is `provisional` with reason `video_check_pending`, so no
unconfirmed value can be applied between commits. Update the docs and API reference
for the audio side.

Tests cover the service path over synthetic media fixtures:

- start-offset fixtures with positive and negative audio-start deltas, a resampled
  44.1/48 kHz -> 8 kHz stream, and MKV plus MP4-with-edit-list containers, run on
  native FFmpeg and in Docker (a merge gate);
- both offset signs, remix, unrelated and insert;
- short-source fixtures replacing the 3 s clips in
  `tests/integration/test_alignment_runtime.py`, now expecting `video_check_pending`
  in U3 and confirmation in U4;
- the existing schema tests updated so the removed fields are unknown keys;
- a cache miss on the old token;
- diagnostics within 128 KiB at the 3 h chunk count;
- JSON-mode stdout unchanged.

Risk: high (hotspot owners, public config, schema).

### U4 - Video frame check

Implement V1-V7 in `alignment_video.py` and pass `VSLoader` and active rects from
the align phase per the ownership section. Combine outcomes per V6/P1, fill the video
fields of the U3 schemas (diagnostic v4 and metadata v5), and show the video table in
the collapsed panel evidence details. Add the P2 fingerprint scope and replace
`video_check_pending`.

Also implement A4a and A4b (competing runs and same-frame disagreements, in
`alignment_decision.py`), V3a and V5a (targeted positions, time conversion, the
alternative set that excludes `c`), the V6 trusted predicate as one function, the
new V6 outcomes, the P4 region copy, P4a, and the P3 schema extension.

Tests use synthetic VapourSynth clips (generated frames with motion, known offset):

- confirmation;
- truth at `r +/- 1` (confirmed) and at `r +/- 2`, `r +/- 3` (inconclusive);
- static or black content (inconclusive, zero-division rules);
- a monotonic tone curve on one side (still confirms);
- a loader failure and a missing loader (unavailable);
- cancellation after load and between positions;
- a source identity change around loads;
- an out-of-range overlap;
- A4a/V5a acceptance cases on synthetic A/V programs of at least 10 minutes:
  - never automatically applied:
    - a 4 s insert near the start (60 s), giving `competing_offset_confirmed_by_video`
      over moving video, or `competing_offset` over low motion;
    - a 4 s insert near the end (540 s), with the same outcomes;
    - a 4 s insert inside the last chunk (570 s, a single disagreeing chunk), giving
      `competing_offset_confirmed_by_video` when the video resolves it, otherwise
      `unresolved_audio_disagreement`;
  - applied (`trusted_automatic`), with any local inconclusive evidence observed
    recorded; the assertion is on application, not on a difference being found:
    - a 4 s and a 30 s same-length replacement at 300 s (different content, same
      offset after it);
  - still `trusted_automatic`: a single credible disagreeing chunk that is a false
    audio match (a repeated music cue, with identical, moving video that resolves
    it);
  - provisional `unresolved_audio_disagreement`: a single credible disagreeing chunk
    over low-motion video where neither hypothesis wins;
  - budget exhaustion: 4 or more non-adjacent credible disagreeing chunks (no
    competing run), where the chunks beyond the 12-position budget are unexamined.
    The result is `unresolved_audio_disagreement` and must never be
    `trusted_automatic`;
  - insert whose shifted part has active, non-credible audio and a targeted position
    sampling it: `competing_offset_confirmed_by_video` (or
    `unresolved_audio_disagreement` if that audio turns out credible). A fully silent
    shifted tail is covered by the documented limit only; no test pins a wrong
    result as expected;
  - mix-caused audio disagreement (these must all be `trusted_automatic`, since the
    video resolves them):
    - the multipath lag reversal: content mixed with its 30 ms-delayed copy, with
      the copies' relative levels reversed over 2 consecutive chunks, over
      identical moving video (the reviewer's reproduced case: global lag 0, 18/20
      agreeing, a 2-chunk alternate run at PSR about 520);
    - a same-frame disagreement: a credible chunk shifted by 10 ms at 24 fps, which
      is never a target and is recorded as sub-frame context;
    - many same-frame disagreements (the authority gate): 20 credible chunks, 6 at a
      10 ms alternate lag, all rounding to the same frame. The raw U1 outcome is
      `no_single_offset` (14/20); the A4b recount must pass and the result must be
      `trusted_automatic`, with the raw outcome kept in the evidence;
    - a run resolved by video: member chunks aren't separately targeted, and the
      result applies;
  - V5a mechanics:
    - an alternative set overlapping `c` (`c = 147`, `r_chunk = 148`), where 147 is
      excluded from the alternative and a clearly correct `c` resolves the target;
    - exact ties and zero scores follow the V5a rules;
    - a reference with a nonzero audio/video start delta plus a local disagreement,
      where targeted frames land in the disagreeing region per the V3a conversion;
    - a competing run over moving video that confirms its own offset, giving
      `competing_offset_confirmed_by_video`;
    - a run resolved in favour of `c` with only 1 winning position, which stays
      `competing_offset` (the 2-position rule);
  - trusted predicate: orchestration and cache tests show that each failing
    conjunct alone (an unresolved run, an unexamined credible chunk, a confirmed
    alternative at a non-credible target) prevents `trusted_automatic`, trims and
    the computed-cache write, independent of evaluation order;
  - schema: diagnostics and metadata round-trip with targeted evidence populated,
    within the size bounds at the maximum target count;
  - refusal principle (these must all be `trusted_automatic`):
    - the same program with loudness changes of +/-10 dB in several places;
    - dynamic-range compression over part of the track;
    - a different surround level or downmix in places;
    - a music-stem change over one section.

    This is the class that the previous implementation wrongly refused.
  - A4a adjacency: credible disagreeing chunks at the same lag but non-adjacent
    indices (for example 2 and 15) are not a competing run; each goes to V3a;
- video false-minimum cases:
  - repeated or duplicated frames (cadence), where ties must be uninformative, never
    a confirmation;
  - periodic motion whose period aliases a neighbouring offset;
  - an edit affecting a minority of V3 positions.

  None may confirm a wrong frame.
- The synthetic noise label is corrected (the "-15 dB SNR" helper is about
  +15 dB SNR), and a genuine -15 dB SNR case (noise 15 dB above the signal) is added
  and must still align.

P4a presentation tests cover every non-applied reason in normal, verbose, JSON and
panel output, including the check-point list. They follow the maintainer-approved
mockup.

An orchestration test proves `trusted_automatic` requires a confirmed video stage and
that provisional results never reach trims or the computed cache. Docker integration
covers real L-SMASH on generated media.

Risk: medium-high (new service boundary, thread use of VapourSynth, native-panel
schema).

### U5 - Acceptance and closeout

- Full command canon (pyright, ruff check/format, bandit, pytest, lint-imports, API
  docs check), `bash tools/verify_docker_integration.sh`, and a strict docs build.
- Real-media gate in Docker: `tools/alignment_benchmark.py` is reduced to production
  path plus labels (the v0.1.0 comparator stays local and untracked) and tracked. It
  takes a local, untracked label file. Every labelled pair must equal its visually
  confirmed frame: currently the three Black Sails pairs above (0, 147, 147).
- Independent real-media set (merge gate, added 2026-09-26). Besides the
  development episode, at least one labelled pair from each of:
  - a different title;
  - real HDR vs SDR mastering (Dolby Vision profile 5 if available);
  - a foreign-language dub;
  - a different cut or extended edition (expected: never applied automatically);
  - an MKV with a container track delay.

  The maintainer supplies the pairs and their visually confirmed frames. If a
  category can't be sourced, record it as missing in the execution record and get
  the maintainer's explicit sign-off before merge; don't silently drop it.
- Report outcomes in four separate counts, not one accuracy figure:
  - correct and applied;
  - wrong and applied (must be 0; any is a stop condition);
  - provisional;
  - unavailable.

  Also record the provisional-plus-unavailable rate on true-positive pairs as the
  refusal rate. **Every refusal on a labelled same-content pair is investigated
  and adjudicated with the maintainer before merge.** Record its reason and
  evidence; a refusal caused by local weak evidence (refusal principle) is a defect.
  Such a failure is diagnosed to its cause first; it is never by itself a
  justification to weaken a threshold (the threshold stop condition still applies). The v0.1.0 parity goal means a high refusal rate on same-content
  pairs is a failure to report, even when nothing wrong was applied.
- Record sanitized results (no paths or titles) in this plan's execution record.
- One final independent review (`deep_reviewer`) of the integrated branch diff,
  focused on authority paths, config removal, schema coordination and U2 lifetimes.
- Windows portable acceptance is recorded as pending release proof, not a merge gate
  for the remediation branch, unless the maintainer says otherwise.
- Mark this plan `Status: Historical` in the closing commit.

## Invariants

- Nothing is applied, trimmed or cached as computed authority unless the V6 trusted
  predicate holds (audio passes, video confirms `c`, every frame-distinct credible
  disagreement and competing run is examined and resolved, and no alternative is
  video-confirmed), or the offset is manual or reused manual.
- `+0f` is a real result and is distinct from no candidate.
- Public offset sign: reference source frame minus comparison source frame.
- At most two FFmpeg children per comparison; memory does not grow with media
  duration; cleanup completes before cancellation propagates.
- No media paths, PCM, full commands or full stderr in diagnostics.

## Verification per unit

- U1: focused pytest plus pyright/ruff on touched files.
- U2: focused and resource tests natively and in Docker (`frame-compare-test`
  service).
- U3-U4: full command canon plus Docker integration.
- U5: everything above plus the real-media gate and final review.

## Rollback

Each unit is its own commit. Before U3, reverting U1/U2 leaves the shipped estimator
intact. After U3, rollback is a branch-level revert of U3-U5 (do not merge the
branch). The old policy token is never reused.

## Stop conditions

Return to the controller or maintainer if:

- a labelled real pair disagrees with its visually confirmed frame;
- a negative control is applied;
- a PSR, agreement or video threshold needs changing to pass a case (record the
  evidence and decide with the maintainer rather than tuning quietly);
- U2 needs more than two children or unbounded buffers;
- a start-offset fixture shows decoded PCM sample 0 is not at the audio stream's
  `start_time` on either runtime (A5's assumption);
- the video check needs a loader other than the run's L-SMASH source;
- removing a C2 field breaks a surface not listed here;
- short-source handling (A1a) cannot reach the v0.1.0 outcome on a labelled short
  pair;
- the A4a run length, the V3a position counts, or the V5a margin (1.5) need changing
  to pass a case;
- a refusal-principle case, or a labelled same-content real pair, is not
  automatically applied.

## Execution record

- 2026-09-25: plan authored. Independent plan review by `deep_reviewer` (Opus, high)
  returned 1 blocker, 10 major and 7 minor findings. All were accepted:
  - Blocker: out-of-set video pick. Fixed by V2 (score r+/-2) and V5 (strict local
    minimum).
  - Majors: lag sign and start fixtures (A1, A5, U3); the streaming authority boundary
    (A7a); watchdog and cleanup order (A7, A8); the unbounded-M budget (A1b); the
    fingerprint scope (P2); stability and score sources (P2a); the duration and EOF
    basis (A8); short sources (A1a); unnamed surfaces and import layering
    (ownership); uninterruptible index builds (V7); the parity baseline (U1).
  - Minors: rounding, search edge and zero-division rules; schema sequencing; D1
    timing; environment-variable removal; attached_pic and VFR; closeout.
- 2026-09-25: the maintainer confirmed A1a and the replacement stance. The C2
  custom removal error and the P3 runs-only fallback were removed as unneeded
  code.
- 2026-09-25: U1 implemented by the maintainer's external implementer, with two
  adversarial self-reviews. The independent `reviewer` checkpoint (Opus, medium)
  found no blockers, 1 major and 8 minor findings; all were accepted and fixed by the
  controller:
  - the PSR formula and MAD = 0 rules are pinned by hand-computed tests;
  - the partial-chunk ceiling is tested with an odd C;
  - the unused constant and generator options were removed;
  - credibility is decided once;
  - the remix gain now matches the spec.

  Carried forward: A6 moves to U3, since it needs A5's start times, and U2
  zero-pads a short final reference chunk (see U2). Verification: 31 focused tests,
  `tests/services`, pyright, ruff check/format, lint-imports and `git diff --check`
  all pass.
- 2026-09-25: U2 implemented by the external implementer with three adversarial
  self-reviews. The independent `deep_reviewer` (Opus, high) found one major and
  eight minor findings; a re-review then found one new minor, one test flake and
  nits. All were accepted and fixed by the controller:
  - the failure slot is re-read after cleanup (a late reader failure can no longer
    look like success);
  - every decoded block is finiteness-checked;
  - the overflow is raised, not asserted;
  - a crashed child is detected and reaped at its EOF, with a stall bound and slot
    checks;
  - one spawn helper, callable failure recorders and early buffer allocation;
  - signal-death, late-reader and stdout-closed-but-alive tests were added, and
    timing-dependent tests made deterministic.

  Memory note (A7): each side holds one sample store plus one delivery scratch
  buffer, so window-sized memory is 2x the plan's wording. It is still constant:
  about 34 MB at the largest admitted M.

  Structure decision for U3, from the review: keep one streaming module (a split
  would create a private cross-module API with one consumer). As U3's first step,
  fold the per-side state and free functions into a `_ChildStream` class with a
  frozen run context, alongside deleting the single-child collector.

  Verification: full pytest, paired resource tests, pyright, ruff, bandit,
  lint-imports and `git diff --check` pass natively; focused and paired resource
  tests pass in Docker. Windows handle-release proof is pending.
- 2026-09-26: external direction review (GPT-6 Astra) adopted by the maintainer.
  Its central finding was confirmed from the A4 arithmetic: majority agreement
  admits edits near either end (18/20 and 19/20 pass). Changes:
  - A4a blocks automatic application on a coherent competing run of at least 2
    chunks;
  - V3a/V5a check targeted video positions inside disagreeing chunks with an
    absolute mismatch rule;
  - new V6 outcomes (`competing_offset`, `video_mismatch_in_disagreeing_region`)
    and region copy (P4);
  - new U4 acceptance cases (early and late inserts, an insert in the last chunk, a
    middle replacement, a false audio match, repeated frames, periodic motion,
    minority edits);
  - the SNR label correction plus a genuine -15 dB case;
  - U5 gains an independent real-media set as a merge gate, and four-outcome
    reporting with a refusal rate.

  U1-U3 behaviour is unchanged: U3 applies nothing, and A4a lives in the decision
  module. A region-limited automatic mode (apply the dominant offset and select
  frames only where it is confirmed) is deliberately out of scope; it is specified
  as a follow-up in `docs/TODO.md`.
- 2026-09-26: second external review (GPT-6 Astra) adopted by the maintainer:
  - A4a now requires consecutive chunk indices. U1 runs don't break at non-credible
    gaps, so indices 2 and 15 could otherwise form a "run".
  - V3a also targets active non-credible chunks, capped at 12 positions.
  - V5a is replaced by a relative two-hypothesis check (the confirmed offset against
    the chunk's own lag). This removes the uncalibrated absolute threshold, whose
    0.05 floor sat above a measured 0.018 wrong-frame difference. It also tells a
    length-changing edit (blocked, `competing_offset_confirmed_by_video`) apart
    from a same-length replacement (applied, content difference recorded).
  - The earlier acceptance case "middle replacement must not be applied" was wrong:
    a same-length replacement keeps a constant offset. It is now an applied case.
  - The plan states the detection limit for edits hidden in non-credible audio.
- 2026-09-26: third external review (GPT-6 Astra), adjudicated with the maintainer:
  - An unresolved credible disagreement no longer allows application: a credible
    disagreeing chunk must be resolved by the video in favour of `c` (with 4
    targeted positions), otherwise the result is `unresolved_audio_disagreement`.
    That makes the stated guarantee true. Weakening the wording was rejected: it
    would have left a known wrong-application path.
  - "Neither wins" is recorded as `local_video_inconclusive`, not as a content
    difference.
  - Acceptance cases now respect sampling coverage, and the fully silent tail is a
    documented limit only.

  At the maintainer's direction, the refusal principle (withhold only on positive
  evidence of a different offset; weak evidence never blocks, with refusal-principle
  tests and a U5 stop condition) and P4a (the review-information spec with a
  maintainer-approved mockup before the UI is implemented) were added.
- 2026-09-26: fourth external review (GPT-6 Astra), all three points accepted:
  - Credible disagreeing chunks the 12-position budget doesn't reach are
    *unexamined* and block (`unresolved_audio_disagreement`), with an acceptance
    case.
  - The refusal principle is restated so global audio and video confirmation stay
    required, and only local weak evidence loses its veto.
  - The guarantee is narrowed to the enforceable contract (withhold on competing
    runs and on any unexamined or unresolved credible disagreeing chunk), and the
    straddling-chunk limit is stated.

  Refusal failures are diagnosed rather than answered with threshold changes. The
  reviewer supports proceeding with no further estimator, fallback or redesign.
- 2026-09-26: fifth external review (GPT-6 Astra), full-plan read against the code.
  Adjudicated with the maintainer:
  - **1, accepted; maintainer: "one of the main problems we need to avoid".** The
    universal PHAT mix-tolerance claim was false: multipath content with reversed
    relative levels produces a credible 2-chunk alternate run at PSR about 520.
    Coherent runs are now resolved by video instead of vetoed unconditionally. A4b
    (added by the controller while checking this) makes same-frame disagreements
    non-blocking, because video can't separate them and they were a second route to
    mix-caused false refusals.
  - **2, accepted.** The V5a alternative set excludes `c`.
  - **3, accepted.** One explicit trusted predicate, mirrored in the invariants and
    tests.
  - **4, accepted.** The audio-to-video time conversion is specified for targets and
    check points.
  - **5, rejected.** Crop rectangles stay out of the computed-cache identity. The
    cached value is the source relationship, which a crop change can't make wrong. A
    bad crop yields uninformative (rank-tied) positions, not false confirmations.
    The decoder identity stays in the key because it changes frame numbering itself.
    Clearing the cache still forces re-verification.
  - **6, accepted.** U4 extends the diagnostic v4 and metadata v5 schemas in place
    (unreleased branch).
  - **Cleanups:** the goal statement now says "refuse when it detects", and the
    obsolete token in the TODO is replaced.
- 2026-09-26: At the maintainer's direction, the branch moved from its separate
  worktree into the main checkout (`/Users/tristan/Software/frame-compare`), so
  every tool works in one folder on one branch; the uncommitted U3/U3-R state was
  carried over intact. The maintainer authorized pushing the branch; it tracks
  `origin/agent/audio-alignment-parity`. PR, release and signing remain
  unauthorized.
- 2026-09-26: sixth external review (GPT-6 Astra):
  - A4b now also recomputes the A4 authority agreement gate after V5 (frame-level
    agreement), because several same-frame disagreements could otherwise fail A4
    before the exemption applied. Raw U1 numbers are kept as evidence, and there is
    a new U4 case (6/20 same-frame shifts must apply).
  - Resolving a run resolves its member chunks.
  - An unresolved run consistently gives `competing_offset`.
  - The point-5 rejection stands, on a corrected basis: an accepted source
    relationship stays reusable across presentation crop changes, and clearing the
    cache re-verifies. The earlier claim that removing information can't cause a
    false confirmation was too strong: a crop can leave repeated motion or an
    overlay that favours a wrong offset.
- 2026-09-26: U3 implemented by an external implementer. Remediation U3-R was
  completed by a Codex controller with Luna workers after the first implementer ran
  out of usage.
  - Checkpoint review: the independent `deep_reviewer` (Opus, high) found 1
    blocker, 7 major and 15 minor findings. All were accepted and remediated:
    - cleanup failure stays fatal ahead of cancellation;
    - identity changes give per-comparison results;
    - native metadata omits per-chunk rows;
    - shared trusted replay stays write-eligible;
    - A5 is implemented once;
    - one generic evidence parser, with invariants in `__post_init__`;
    - restored coverage;
    - start-offset truths come from fixture construction, not the formula.
  - A Codex stop on shared computed replay was overruled by the controller: P1
    allows replaying trusted entries under the current token, and U3 never writes
    same-run computed authority.
  - A controller delta check by `reviewer` (Opus, medium) found a regression: the
    run invariant required contiguous indices, although U1 runs skip non-credible
    chunks, so real media with a quiet chunk would have failed the phase. It is
    fixed, and a quiet-chunk test proves it. Three test gaps were also closed:
    cancellation outranks identity, two-layer write eligibility, and a guarded
    identity freeze.
  - Evidence: every in-sync start-offset fixture gives r == 0 and the 5-frame case
    gives r == 5, on native FFmpeg 9.0.2 and Docker FFmpeg 7.1.5. Full pytest,
    pyright, ruff, bandit, lint-imports, the API-docs check, resource tests and the
    strict docs build pass; the canonical Docker gate had zero skips.
  - Known follow-up for U4: `utils/alignment_evidence.py` (about 890 lines) keeps
    parallel `_check_value` and `_parse_value` type walkers. Unify them if U4's
    schema extension touches that code.
- 2026-09-27: U4 implemented and remediated through accepted commit `9360e10a`.
  `alignment_video.py` now owns V1-V5a over the run's L-SMASH loader;
  `alignment_decision.py` owns A4a/A4b, the authority recount, ordered V6 failures,
  and the single trusted predicate; orchestration passes loader, active rectangles,
  cancellation, source identities, and the scoped alignment-runtime fingerprint.
  Only `trusted_automatic` reaches trims or the computed cache.
  - Diagnostic v4 and metadata v5 were extended in place with base and targeted
    video evidence, same-frame context, authority recount, and P4a check points.
    `VideoTargetEvidence.target_offset`, `credible`, `start_sample`, and
    `end_sample` are authoritative. Compact native metadata omits per-chunk rows but
    retains those target facts, aggregate counts, and `chunks.total_samples`.
  - P4/P4a projection policy moved into `utils/alignment_evidence.py`, with terminal
    and panel code as renderers. The U3 follow-up was completed by replacing the
    parallel walkers with one schema walker: the file was 897 lines before U4 and
    1,036 immediately after the schema/walker commit; later video and presentation
    evidence grew the same cohesive owner further.
  - The synthetic ten-minute acceptance matrix covers inserts at 60, 540, and 570
    seconds; 4 s and 30 s replacements; repeated-cue and low-motion disagreement;
    4- and 7-target budget exhaustion; active non-credible shifted audio; multipath,
    same-frame, 14/20 raw authority, and resolved-run cases; loudness, compression,
    surround/downmix, and stem changes; adjacency; V5a mechanics; false minima;
    loader/cancellation/identity/out-of-range failures; start-time conversion; and
    trusted trim/cache conjuncts. Canonical Docker most recently passed 254 tests
    with zero skips. Three warmed direct video-check samples were 2.863 s, 2.758 s,
    and 2.690 s (mean 2.770 s), below the plan's approximate 4 s expectation.
  - The approved historical copy mockup remains unchanged. Governing-plan/final-source
    deviations are explicit: a non-credible V5a neither-win is
    `local_video_inconclusive`, not proof that picture/content differs; active
    non-credible audio is weak evidence, not quiet, while inactive sections are
    planned but unanalyzed context; an alternative video win at any target still
    blocks; check points preserve authoritative producer target identity, planned
    frames, and the winning offset rather than reconstructing them from compact
    presentation rows; and the shared projection may merge/split overlapping run and
    chunk regions only while retaining their authoritative target keys/resolutions.
- 2026-09-27: U4 adversarial-review remediation was authorized and integrated on the
  accepted fix base. The unintended 12-record limits on retained targets and
  same-frame context were removed; the 12 **scored targeted-position** budget remains.
  Repeated chunk/target collections now use a lossless standard-library packed JSON
  projection only when large, so full diagnostic and compact native attempts round-trip
  at `MAX_AUDIO_CHUNKS` below 128 KiB without truncation.
  - A4a run formation now requires a complete adjacent lag span of at most 16 samples.
    V5a uses the true run median and preserves half-sample centres. Per maintainer
    clarification, V5 confirmation keeps the median of margins won by the candidate,
    not all informative margins.
  - Local video evidence retains the unique offset that actually won; tied alternatives
    confirm nothing. Region endpoints use reference-video time, the load/index timer
    stops after both native loads, and raw audio plus video failures are both retained
    in prescribed order. The historical copy mockup remains unchanged; its approved
    `exact match`, lowercase status words, ASCII `x`, and local-inconclusive wording are
    implemented in the shared projection owner.
  - Presentation policy moved from the schema module to
    `utils/alignment_review_projection.py`; pure compensation, conversion, voting, and
    confirmation policy moved to `utils/alignment_policy.py`. The schema remains the
    single strict evidence owner, and orchestration now calls the current typed loader
    seam directly with no signature introspection or legacy fallback.
  - Proof adds literal A02/A03/A04 counterexamples, a real-estimator 13-same-frame
    acceptance case, maximum full/compact serialization, controlled timing, nonzero
    reference-start rendering, actual alternative-offset copy/checkpoints, and a real
    seven-case phase/cache matrix. That matrix isolates A4b, V5, unresolved-run,
    unexamined-credible, and noncredible-alternative failures; proves a noncredible
    neither-win remains applicable; and covers trusted replay, manual precedence,
    active crop, and a localized surround/downmix change.
