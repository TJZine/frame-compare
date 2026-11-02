---
search:
  exclude: true
---

Status: Active
Source: `25d1e75ac9323f6a238fb398b3a4a8d15646a590` (laptop checkout, clean), 2026-10-18.
The Windows run that produced the diagnosis recorded version 0.7.0 and its runtime
fingerprints, but not its source SHA.
Evidence: the Codex diagnosis bundle `kill-bill-diagnosis.zip` (run inspection,
native and highlight probes, audio decode checks, source findings). It is not
stored in the repository.
Approved: the maintainer approved K1b-A (canonical frame rates) on 2026-10-18.
K3 default changes still need the K3 study and a separate decision.

# Kill Bill comparison fixes

The comparison is the 2160p MainFrame DV/HDR10 release (reference) against
`Kill.Bill.Vol.2.2004.1080p.BluRay.DTS.x264-FoRM.mkv` (an SDR file muxed in 2010 with
libmatroska 0.8.1). Analysis, the 2× upscale and the manual 504-frame offset all
worked. Three problems remain, each fixed independently below.

## K1. Automatic audio alignment

The run was rejected before collection with `selected_audio_timeline_unavailable`.
There are two separate causes. Fixing only the first leaves the same rejection.

### K1a. Selected-stream duration from tail packets

**Cause.** The FoRM audio stream has no `duration_ts`, no stream `duration` and no
`DURATION` tag. `_parse_audio_stream`
(`services/alignment_audio.py:266-281`) therefore yields no duration. The container
duration (8217.867 s) is also what every subtitle stream reports, so it is not
evidence about the audio stream.

**Change.**

1. In `_plan_audio_pair` (`services/alignment.py`), after stream selection and
   before rejecting for a missing duration, measure each selected stream that has
   no metadata duration. Do this only for the selected stream, never for every
   audio stream.
2. Add a measurement in `services/alignment_audio.py`. It makes one ffprobe call
   with `-select_streams a:<ordinal> -read_intervals <seek>% -show_entries
   packet=pts,duration`.
   - The seek point is `max(0, video_seconds - 60)`.
   - `video_seconds` is that side's decoder timeline (`source_frame_count /
     source_fps` from the alignment clip request), not the container duration.
     ffmpeg `-live 1` Matroska files have neither stream nor container durations,
     and this still works for them.
   - The seek point is only a place to start reading. The result is the latest
     packet end (`pts + duration`, times the time base) minus the stream start
     time.
3. Accept the measurement only when:
   - at least one packet has a pts at or after the seek point, showing the
     window reached the stream's tail;
   - every value parses;
   - the resulting duration is positive.

   Otherwise keep `selected_audio_timeline_unavailable`.
4. Bounds: use the existing `_load_ffprobe_json` runner with its 15 s timeout.
   Call `raise_if_alignment_cancelled` before the probe. Do not loop or retry with
   wider windows.
5. Add `"packet_tail"` to `AudioDurationBasis` (`utils/alignment_evidence.py`). Show
   it wherever the review projection prints the duration basis. Do not migrate
   older evidence.

**Authority is unchanged.** The measured duration only feeds chunk planning and the
timeout and output limits. Collection still decodes the real samples, and too much
output still fails through the existing limit. A new computed result stays a
candidate until the audio/video decision authorizes it. Zero stays distinct from
unavailable.

**Rejected alternatives.**

- Using the container duration as the audio duration.
- `-count_packets`, which reads the whole file (14 GB here).
- Measuring EOF during collection. Chunk planning would have to move after
  collection, and the bounds would still need a duration first.

### K1b. Container-imprecise frame rates

**Cause.**

- L-SMASH reports the FoRM video at 27021/1127 fps, which ffprobe also reports.
  This is an old muxer's rounding of 24000/1001: the frame duration differs by
  about 33 ns, or 0.78 ppm.
- The reference is 24000/1001. Under default config this pair would hit FC-3011
  (mixed source fps), so the Windows config must have set `sources.match_fps` or
  an `effective_fps` override.
- That leaves a comparison `timeline_scale` of 1288001/1288000. `retime_rates`
  (`services/alignment_audio.py:626`) would need a 1,288,001 Hz rate, which is
  above `MAX_RETIME_RATE` (384,000). It raises the same
  `selected_audio_timeline_unavailable` category.

**K1b-A (approved): canonical frame rates.**

1. In `orchestration/selection_domain.py` `_build_selection_domain_clip`, derive
   `source_fps` from the decoder rate as follows:
   - when the decoder rate is within 10 ppm of exactly one standard rate, use that
     standard rate;
   - otherwise use the decoder rate unchanged.

   The standard rates are 24000/1001, 24, 25, 30000/1001, 30, 48, 50, 60000/1001,
   and 60.
2. An explicit `effective_fps` override still wins.
3. The probe snapshot and probe cache keep the raw decoder rate. Do not bump the
   probe cache version.
4. Report every snap in the fps report (`orchestration/fps_report.py`) as
   `raw -> canonical`, with a short reason.

Why 10 ppm: the observed error is 0.78 ppm, and the real 1000/1001 distinction is
about 1000 ppm. No mastered content runs at a rate a few ppm away from a standard
rate. Frame indices never change. Only time conversions use the canonical rate.

**K1b-C: distinct retime rejection.** Give the `retime_rates` rejection its own
category (for example `retime_rate_unsupported`). Thread it through the decision,
evidence and presentation reason text so it no longer looks like a missing
duration.

**K1b-B (deferred).** Accepting an approximate retime within a drift budget would
cover unusual user-chosen `effective_fps` values. It changes persisted evidence.
Do it only when a real case needs it. K1b-C makes that case visible.

**Blast radius checked at the source revision.**

- `ClipState.source_fps` is read by `orchestration/phase_alignment.py:432` (the
  alignment request) and `orchestration/fps_report.py`.
- `analysis/window.py` uses its own clip fps for second-based window trims. A
  sub-ppm change is far below one frame.
- VSView sessions already apply `AssumeFPS` to the reference rate
  (`vsview/session_runtime.py:430`).
- Recheck these readers when implementing.

### K1c. Offset across the whole film

The manual 504-frame offset matched one point. After K1a and K1b, the whole-track
chunked audio estimate gives a per-window offset and a stability classification
across the film, and the video check confirms the candidate. That is the evidence
for the whole film. If audio still cannot decide, check the offset manually in
VSView at about 10%, 50% and 90% of the runtime.

### K1 verification

- **Generated media.** Add recipes in `tests/integration/alignment_u4_media_recipes.py`
  with a matching integration test:
  - a `-live 1` Matroska pair with a known delay, expecting a planned and
    collected result, `duration_basis == "packet_tail"`, and the labelled offset;
  - a negative case where the audio ends more than 60 s before the video,
    expecting `selected_audio_timeline_unavailable`.

  Run them in Docker, where L-SMASH is available.
- **Focused table test for K1b-A:**
  - 27021/1127 becomes 24000/1001;
  - 24 stays 24 and 24000/1001 stays 24000/1001;
  - 25 stays 25;
  - a rate 50 ppm off stays raw;
  - an explicit override wins.
- **Focused test for K1b-C:** the rejection category.
- **Gates:** pyright, ruff, import-linter, and the focused alignment tests. Run the
  full native suite once, because this changes shared alignment behavior.
- **Acceptance on Windows (target runtime):**
  - Rerun the Kill Bill pair into a fresh run folder, without the saved manual
    override and with `match_fps` left at its default.
  - Expect an audio candidate of about 504 frames that the video check confirms,
    plus a stability classification.
  - Record the exact source SHA.

## K2. Destination primaries

**Cause.** `vs/tonemap_libplacebo.py:85` passes `dst_prim=1` under a BT.709
comment. In the pinned vs-placebo 2.0.4 (`3cfd23f`), 1 is SMPTE-C and 3 is BT.709.
Native evidence showed a mean difference of 0.78 code values on a color frame and
no brightness change.

**Change.**

1. Pass `dst_prim=3` in `build_libplacebo_tonemap_kwargs`.
2. Use the same value in the capability probe (`vs/tonemap_runtime.py:62`) for
   consistency.
3. Leave the post-tonemap `_Primaries`/`_Transfer` props alone unless a reader is
   found. The RGB to RGB24 path ignores them.

**Verification.**

- Correct the three assertions that currently freeze the wrong value
  (`tests/vs/test_tonemap_apply.py:180`,
  `tests/vs/test_tonemap_extracted_modules.py:205,322`).
- Add one native check to `tests/e2e/test_media_tonemap.py`. It renders a
  saturated BT.2020 patch and compares the output against BT.709 values computed
  independently, with a tolerance that SMPTE-C output fails.
- Add a changelog entry: HDR screenshots change slightly in color.

## K3. Tone-map highlight compression (study before any default change)

**Facts.**

- Frame 12382 is the deliberately overexposed black-and-white porch scene. The HDR
  grade places the sky at about 130-250 nits, above the 203-nit HDR reference
  white, so some compression for 100-nit SDR is inherent.
- With dynamic peak detection the frame peak (about 253 nits) maps to 100 nits.
  BT.2390's hermite segment has zero slope at the peak, so that region collapses
  into the top 8-bit codes.
- No component reaches exact white at 16 bits. This is 8-bit rounding loss, not
  hard clipping.
- The pinned libplacebo header (`a7a18af`) calls knee 0.5 the BT.2390 spec value
  and 1.0 the libplacebo default. libplacebo's general default curve is `spline`.

**Study.** Run on Windows using existing CLI overrides and diagnostic graphs. No
product changes.

- **Titles:** Kill Bill plus 2-4 other HDR titles with different MaxCLL (about 1000
  and about 4000 nits), mixing DV and HDR10. Include matched SDR releases where
  available.
- **Frames:** fixed and aligned frames for each title: high-key, specular, dark,
  saturated, and skin.
- **Variants:** run after K2 lands. Change one control at a time:
  - the current `reference` preset;
  - knee 1.0;
  - knee 1.0 with contrast recovery 0;
  - `spline`;
  - a static peak (MaxCLL).
- **Metrics:**
  - the share of pixels at the top code, at 16 bits and at 8 bits;
  - gradient energy in the source's brightest 5% compared with the source;
  - the output level of source mid-tones (about 10-20 nits), which should not
    move;
  - the mean code value.
  - The color difference against the SDR release is secondary and labelled as a
    different grade.
- **Perceptual review:** a blind side-by-side review by the maintainer on a fixed
  rubric (highlight detail, overall brightness, mid-tone contrast).

**Candidate outcomes.** The maintainer decides.

- **O1:** change the `reference` knee to 1.0. On Kill Bill, near-white pixels fell
  from 7.2% to 0.8% and the mean fell 2.5%.
- **O2:** switch `reference` to `spline`. Near-white pixels fell to almost 0, but
  the mean fell 13%.
- **O3:** keep the default, document why, and point to `spline` or
  `highlight_guard`.

A chosen change updates `vs/tonemap_presets.py`, the preset tests, the tonemap
section of `docs/current-cli-contract.md`, and the changelog.

## Order and ownership

- K2 is small and should land first, because the K3 study depends on it.
- K1 touches only alignment, selection-domain and fps-report files, so it can run
  in parallel with K2.
- K3 is diagnostic work on Windows. Its default change is a later, separate
  decision.

## Stop conditions

- A K1 change that lets unavailable or provisional evidence become an applied trim
  or computed-cache authority.
- A K1b-A tolerance that would snap two standard rates to each other (for example
  24 and 24000/1001).
- Changing an alignment estimator constant to make a case pass.
- Changing a tonemap default before the K3 decision.

## Execution record

- 2026-10-18: Plan written from the diagnosis bundle and a source trace at
  `25d1e75a`. K1b-A approved. Nothing implemented.
- 2026-10-18: Execution dispatched from branch `v0.7.0`, actual HEAD
  `25d1e75ac9323f6a238fb398b3a4a8d15646a590`. Original human authorization:
  orchestrator chat `01a14e1b-4bb8-7920-a9e1-a2b04743095a` (host `local`), turn
  `01a14e1b-5372-72c3-ad32-62615b375a89`, user message
  `01a14e1b-5806-77c3-b130-a3934797625b`, which supplies the controller handoff
  attachment as the user's request and authorizes child chats and callbacks.
  Pending children (same checkout, no child Git ownership):
  - W1 / K2: `01a14e1c-032b-7b51-b217-ed7f1fe41bda`, `gpt-5.6-luna`, `xhigh`.
  - W2 / K1a + K1b-C: `01a14e1c-0967-7f13-9673-74a6ba9a1e38`,
    `gpt-6.1-sol`, `medium`; holds the exclusive wave-1 Docker slot.
  - W3 / K1b-A: `01a14e1c-1015-7093-8a59-fc8c7403d669`, `gpt-5.6-luna`, `xhigh`.
  Children report meaningful blockers and completion to the orchestrator after
  verifying the original human turn. Integration, changelog, full gates, R1 review,
  and execution-record commit remain pending. Windows acceptance and K3 remain
  outside this laptop task. Nothing pushed or released.
- 2026-10-18: Confirmed W2's requested non-services/utils ownership before edits:
  `tests/integration/alignment_u4_media_recipes.py`, new
  `tests/integration/test_alignment_packet_tail.py`,
  `tests/services/test_alignment_ffmpeg.py`,
  `tests/services/test_alignment_workflow.py`,
  `tests/services/test_alignment_frozen_strings.py`, and the alignment-evidence
  passage of `docs/current-architecture.md`. These are within W2's assigned proof
  and documentation scope; no plan deviation.
- 2026-10-18: Wave 1 completed and integrated (same executor settings as dispatch):
  - W1: `44dc3ba7`, `fix(tonemap): target BT.709 destination primaries`.
    Focused native checks: 34 passed, 2 media skips (opt-in unset; local
    libplacebo unavailable). Independent patch oracle and SMPTE-C negative
    control await the full Docker gate.
  - W2: `060643d7`, `fix(alignment): measure selected audio duration from tail packets`.
    Focused native checks: 211 passed, 1 module skip (local L-SMASH unavailable);
    cache tests: 9 passed. Focused Docker: 11 passed, no skips; known +48-frame
    offset required video confirmation, early-ending audio rejected before
    collection. Docker slot released. Approved the necessary recipe inventory
    test and runbook count changes from 37 to 40 files.
  - W3: `e24fafe1`, `fix(sources): canonicalize container-imprecise frame rates`.
    Focused checks: 54 passed, CLI documentation: 5 passed. Integration requested
    required raw-FPS reporting without a compatibility fallback, unchanged
    unsnapped Sources formatting, and exact tolerance boundary coverage while
    retaining the specified 50 ppm case. Accepted the necessary one-line direct
    constructor update in `tests/cli/test_run_output.py`.
  - `8dec58ec`, `docs(changelog): describe Kill Bill comparison fixes`.
  All children report clean focused type/lint/format checks. No estimator constants,
  authority predicates, tonemap presets, or collection resource bounds changed.
  Full static gates pass: pyright (0 errors/warnings), Ruff check and format
  (542 files), Bandit (0 medium/high issues), import-linter (2 contracts kept),
  CLI documentation (5 tests). Full native and Docker gates are running; R1 and
  final execution record remain pending. Logs:
  `/tmp/frame-compare-kill-bill.h3Cl8h/`.
- 2026-10-18: Full native command exited 1 with four failures: Chrome/display
  startup at two scale factors, Chrome text-input timeout, and PTY prompt startup
  timeout. All four passed without assertion/source changes on focused rerun
  (JUnit: `/tmp/frame-compare-kill-bill.h3Cl8h/native-rechecks.xml`, 4 tests,
  0 failures/errors/skips). Native skips include missing local L-SMASH/libplacebo,
  media opt-in, Windows/PowerShell, opt-in resources, and live external services;
  these are not platform passes.
  Full Docker runtime/provenance/real-frame smoke passed, but its pytest run has
  reported a color-patch failure and is still running (exec session `4382`, log
  `/tmp/frame-compare-kill-bill.h3Cl8h/docker.log`, artifacts
  `generated/e2e/run.zGYtrV`). A focused diagnostic confirmed pytest's
  warnings-as-errors turns an existing `_ColorRange` deprecation into a failure
  before Tonemap. W1 is correcting its native test to invoke the real plugin
  using the production kwargs builder for actual and negative-control renders,
  preserving independent expectations and assertions. This meets the K2 color
  conversion proof without expanding scope into shared range normalization;
  existing E2E/runtime-smoke proof retains application-path coverage. No warning
  filter or skip is authorized. Numeric oracle and SMPTE-C control are still
  unverified. Pending W1 correction callback; full Docker completion, corrected
  native proof, R1, and final execution-record commit remain pending.
- 2026-10-18: Full Docker run completed: 302 passed, 1 failed, no skips, in
  534.09 seconds; its sole failure was the original color-test setup described
  above. W1 correction committed as `b7856f53`,
  `test(tonemap): verify native primaries with independent BT.1886 oracle`.
  The corrected test uses the production kwargs unchanged for its BT.709 render
  and changes only `dst_prim` for the SMPTE-C control. The independent oracle
  reflects the pinned plugin's BT.709-primary/BT.1886 output contract. Native
  Docker diagnostic passed: expected RGB approximately
  `(0.11706, 0.75544, 0.55816)`, actual `(0.11815, 0.75573, 0.55842)`;
  SMPTE-C `(0, 0.76504, 0.55908)` fails the unchanged 0.08 tolerance.
  The canonical verifier is rerunning the affected tonemap E2E file, including
  the production-image proof omitted after the failed full test command.
  Log: `/tmp/frame-compare-kill-bill.h3Cl8h/docker-correction.log`.
  Native full-run exact outcomes reconstructed from progress and skip summary:
  3698 passed, 4 failed, 298 skipped (including 5 module-level skips); all four
  failures subsequently passed unchanged in the focused JUnit run.
- 2026-10-18: Canonical affected Docker rerun completed successfully:
  `bash tools/verify_docker_integration.sh --pytest-path tests/e2e/test_media_tonemap.py`
  exited 0, 2 passed in 6.56 seconds, no skips. Runtime/provenance/decoder/render
  proof and production-image tooling/application/generated-artifact proof all
  passed. Combined with the unchanged 302 passing cases from the full run, this
  verifies the corrected code without repeating the full media matrix. Original
  full-run failures remain recorded separately, not relabelled clean runs.
  R1 dispatched read-only against
  `25d1e75ac9323f6a238fb398b3a4a8d15646a590..b7856f53097bba31a6526db5867528069cfd1ea1`,
  child `01a14e2a-8714-7aa0-b440-c50d84995333`, executor `gpt-6.1-sol`, effort
  `high`; callback pending. Separate long alignment
  resource proof is not required because whole-track memory bounds, maximum lag,
  and the streaming collector are unchanged.
- 2026-10-18: R1 completed against the exact integrated range above with no
  validated material correctness or maintainability findings. Reviewed all 23
  changed tracked files, the complete plan, and downstream authority, cache,
  window, and VSView readers. Accepted the no-finding conclusion after reconciling
  it with the inspected diffs and evidence; no remediation or deep-reviewer
  escalation was needed. R1 ran read-only source/caller inspection and
  `git diff --check` for the reviewed range; no suites or Docker were repeated.
  All four child chats are complete; their canonical IDs are the dispatch IDs
  above (some worker callback bodies contained ID typos).

  Final gate ledger:
  - `uv run --no-sync pyright --warnings`: exit 0, 0 errors/warnings.
  - `uv run --no-sync ruff check .`: exit 0, all checks passed.
  - `uv run --no-sync ruff format --check .`: exit 0, 542 files already formatted.
  - `uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium`:
    exit 0, 0 medium/high issues (28 low findings outside this severity gate).
  - `uv run --no-sync lint-imports --config importlinter.ini`: exit 0,
    2 contracts kept, 0 broken.
  - `uv run --no-sync pytest -q tests/test_cli_contract_docs.py`: exit 0,
    5 passed.
  - `uv run --no-sync pytest -q -n4 --dist loadgroup`: exit 1,
    3698 passed, 4 failed, 298 skipped. The four unchanged failed cases passed
    in the focused rerun (4 passed, 0 failed/skipped); original full-run result
    remains a failure, not a clean-run claim. Skip categories are documented
    above and do not establish native-media or Windows acceptance.
  - `bash tools/verify_docker_integration.sh`: exit 1,
    302 passed, 1 failed, 0 skipped. Its sole failure was the corrected test setup;
    product source remained unchanged after this full run.
  - `bash tools/verify_docker_integration.sh --pytest-path tests/e2e/test_media_tonemap.py`:
    exit 0, 2 passed, 0 skipped, with all runtime and production-image proofs.
    This is the affected rerun completing the full run's missing proof; the
    original full command's exit code is preserved above.
  - Focused unit checks and W2 real-media Docker proof retain the exact results
    recorded above. Final `git diff --check` passed. No separate long-running
    alignment resource module was run because its changed-behavior triggers do
    not apply.

  Laptop implementation, integration, evidence reconciliation, and R1 are
  complete. This execution record is committed as
  `docs(plans): record Kill Bill fix execution`. Windows acceptance remains
  outstanding: rerun the real Kill Bill pair without the saved manual override,
  with default `match_fps`, recording the exact source SHA, an approximately
  504-frame audio candidate, video confirmation, and stability classification.
  The K3 study and any later tone-map-default decision also remain outstanding.
  Both require a Windows-host handoff; no Windows or K3 pass is claimed here.
  Branch `v0.7.0` was retained. Nothing was pushed; no signing, publication, or
  release action was taken.
