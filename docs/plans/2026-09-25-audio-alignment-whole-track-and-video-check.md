---
search:
  exclude: true
---

Status: Active
Scope: Replace the distributed-window audio estimator with whole-track chunked GCC-PHAT correlation plus container start compensation, and add an L-SMASH video frame check that picks the exact applied frame.
Owner: Audio alignment parity controller session; worktree `agent/audio-alignment-parity`, merged into `dev/v0.6.0-review-remediation`.

# Audio alignment: whole-track estimator and video frame check

## Baseline

- Worktree `/Users/tristan/Software/frame-compare-worktrees/audio-alignment-parity`,
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
refuse, rather than apply, when no single constant offset exists or the audio is
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
| Noise at about -15 dB SNR | -4f | correct | correct | correct |
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
- V4. Frames: luma, crop to each clip's resolved active rect (resolved during
  preparation, before any phase), bilinear downscale to 320x180, rank-normalize with
  average ranks for ties, mean absolute difference.
- V5. Per position, over the five scored offsets: the best offset must be a strict
  local minimum (both neighbours score worse). A position is informative when it has a
  strict local minimum and runner-up / best >= 1.1; best = 0 with runner-up > 0 counts
  as an infinite margin, and all-zero or tied scores are uninformative. The video stage
  confirms `c` when `c` is in `r - 1 ... r + 1`, there are >= 6 informative positions,
  `c` wins >= 75% of them, and the median margin is >= 1.5. A winner at `r +/- 2` is
  `video_check_inconclusive` (the audio is off by more than a frame).
- V6. Outcomes:
  - Audio passes and video confirms `c`: `trusted_automatic`, applied frame `c`,
    reason `audio_video_confirmed`.
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
- P3. Diagnostic artifact schema v3 -> v4 and VSView metadata v4 -> v5, both defined
  in full in U3 (video fields present as `not_observed` until U4 fills them), generated
  and parsed together. Evidence: selected streams, start times and compensation, chunk
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
  `audio +146.23f, video confirmed +147f`.

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

## Units

Execute in order. Each unit ends with its verification, a diff audit and a controller
commit on `agent/audio-alignment-parity`. Model choice happens at dispatch per the
runbook; the risk notes say why a unit is harder than it looks.

### P0 - Plan activation

Commit this plan and mark the 2026-09-22 plan `Status: Historical` with a one-line
pointer here. Commit: `docs(plan): activate whole-track audio alignment plan`.

### U1 - Chunked audio estimator (pure numeric)

Implement A1-A4, A1a-A1b and A6 in `alignment_correlation.py` over in-memory arrays
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

Wire U1+U2 into `_estimate_audio_pair` / workflow and add A5 start probing. Produce
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

Tests use synthetic VapourSynth clips (generated frames with motion, known offset):

- confirmation;
- truth at `r +/- 1` (confirmed) and at `r +/- 2`, `r +/- 3` (inconclusive);
- static or black content (inconclusive, zero-division rules);
- a monotonic tone curve on one side (still confirms);
- a loader failure and a missing loader (unavailable);
- cancellation after load and between positions;
- a source identity change around loads;
- an out-of-range overlap.

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
  confirmed frame: currently the three Black Sails pairs above (0, 147, 147). Add any
  further labelled sets the maintainer provides (different mix/master, HDR/DV,
  different cut, track-delay MKV) before merge; a mismatch is a stop condition.
- Record sanitized results (no paths or titles) in this plan's execution record.
- One final independent review (`deep_reviewer`) of the integrated branch diff,
  focused on authority paths, config removal, schema coordination and U2 lifetimes.
- Windows portable acceptance is recorded as pending release proof, not a merge gate
  for the remediation branch, unless the maintainer says otherwise.
- Mark this plan `Status: Historical` in the closing commit.

## Invariants

- Nothing is applied, trimmed or cached as computed authority unless the audio stage
  passes and the video stage confirms, or the offset is manual or reused manual.
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
  pair.

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
