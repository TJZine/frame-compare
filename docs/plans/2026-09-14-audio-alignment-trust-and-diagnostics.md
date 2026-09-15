---
search:
  exclude: true
---

Status: Active
Scope: Replace independent audio-window seeks with bounded continuous collection, qualify automatic alignment authority, and complete runtime/release proof.
Owner: Main GPT-5.6 Sol orchestration task; sequential Codex new tasks with controller-owned integration.

# Audio-alignment redesign — replacement implementation plan

**Repository:** `TJZine/frame-compare`
**Branch:** `dev/v0.6.0-review-remediation`
**Tracked path:** `docs/plans/2026-09-14-audio-alignment-trust-and-diagnostics.md`
**Original plan date:** September 14, 2026
**Replacement date:** September 15, 2026
**Inspected pushed head:** `0df9c369a9abf19de3cce87de95ccd50ef7ecf1a`
**Original investigation baseline:** `326da610a1f6d9baee7ea58d509f05f59af0f004`
**Replacement packages:** R0–R7, all not started at authoring.

This document replaces the previous contents at this path. It is the only active plan for this workstream. Completed historical work remains recorded below and in its immutable commits and scalar evidence. Historical instructions prohibiting continuous production decoding or directing another P5 seek experiment are superseded, not outstanding tasks.

The latest pushed changes inspected here are test/evidence changes. Production extraction and policy remain `stream-timeline-distributed-2097152-v5`; the automatic-authority safety hold is **not installed yet**. R0 is the first production change. Authoring this replacement did not execute tests, implement code, or establish new runtime measurements. [E1, E2, E3, E4]

## 1. Decision, scope, and non-negotiable outcomes

Replace independent seek-per-window extraction with continuous origin-based streaming collection. Retain distributed analysis windows. Use a second continuous pass at the requested rate when discovery uses a lower rate. This architecture is settled; the completed feasibility program is not repeated.

The implementation must provide:

- Bounded retained PCM, pipe buffers, stderr, subprocess lifetimes, FFT work, scoring work, and per-comparison diagnostics.
- Sequential reference/comparison collection and sequential comparison lifetimes; no cross-comparison PCM cache.
- Truthful sample coordinates and observed-EOF handling, including AAC padding discrepancies.
- Three separate gates: extraction integrity, estimation quality, and automatic authority.
- Useful provisional candidates without automatic application, including legitimate `+0f`.
- Qualified temporal support and a credible-contradiction veto before automatic authority is restored.
- Existing immutable-attempt, manual-review, persistence, and native validation safeguards.

No new runtime dependency, user-facing tuning switch, independent-seek fallback, temporary whole-track PCM, Python resampler, codec-specific backend registry, adaptive stream search, diagnostic retry, or special zero-check is authorized. Do not increase preroll, correction radii, quality tolerances, or budgets to make fixtures pass. Do not add another planning document or an automatic legacy-cache migration.

Continuous decoding is not whole-track retention. It also is not exhaustive edit detection: discarded intervals are not analyzed. Acceptance means sufficiently strong distributed support for one correction without a credible contradiction in sampled evidence, not proof that every source frame or every audio sample matches.

The canonical audio coordinate system does not independently prove the relationship to video frame zero. Preserve the existing `reference source frame - comparison source frame` sign convention and the product's matching-A/V-relationship assumption. Do not add timestamp compensation, silence insertion, stretching, or inferred A/V-origin correction. Independently labeled video/real-media evidence is required for release claims about frame alignment.

## 2. Preserved history and evidence limits

### 2.1 Historical ledger

| Historical package | Pushed reference | Retained result and current interpretation |
| --- | --- | --- |
| P1 — immutable evidence and diagnostic persistence | `14d82237011da0e2efd518ed6c70e64e732d9a21` | Complete. Retained selected streams, all planned window outcomes, provisional candidates, original-attempt history, and bounded run-local diagnostics. Deliberately preserved v5 acceptance, including one survivor/four failures. Reuse this work. |
| P2 — terminal/native review | `1d29ef131d6c307a1efa6f3b3512524ed8fd1d29` | Implementation complete. Metadata v2/result v1 and accepted/provisional/unavailable presentation exist. Physical-Windows visible acceptance remained outstanding. Extend, do not rebuild. |
| P3 — independent continuous oracle and proposed-policy evaluator | `7f342a6208944e53a4e48c77d3449ffdc05e9085`; results recorded by `8e8dacad560c99b9732d3a1880adb977b8069e8d` | Complete investigation with a failed extraction gate. The proposed evaluator passed its finite holdout matrix; that was not deployed v5 authority proof. |
| P5A — ten-second preroll | `1e79b94c0d4487ff816f4506987757b3f408a97e`; result `624f2e79d25bee84761825e14dfe095b16c9ca90` | Rejected. Positive-start native failure unchanged; Docker 48→8 kHz improved 3→1 samples, while 44.1→48 kHz worsened 10→12. No production change. |
| P5B — grid-preserving seek/resample/crop experiment | `114928fe6f885c28e2c73cf5eb9fafda2e67c4dd`; result `251d1bf922ae225bdf38eb44e5db77932cf79e79` | Rejected. Repaired the positive-start fixture but did not satisfy the declared cross-runtime extraction gate. No production recipe or estimator change survived. |
| Continuous-collector feasibility, recorded in `p6-results.json` | `38293b3a2d5dc4b06411f12e4aaf1ce324435921`; completed/corrected by `0df9c369a9abf19de3cce87de95ccd50ef7ecf1a` | Completed feasibility evidence supports the selected direction. Production collector, endpoint semantics, full-pair/resource proof, and Windows proof remain to implement or establish. |

The old plan also names `ba5364d...` and `1f4269fb` for experiments. Their equivalence to the pushed commits above was not independently established in this authoring session. Preserve those identifiers in the linked historical plan; use the inspected pushed lineage for this implementation baseline.

The old plan's unexecuted **P6 release-acceptance package** is not the completed experiment whose scalar filename is `p6-results.json`. R6/R7 below own the remaining production/release gates. Do not mark historical release acceptance complete because a file is named P6. [E1, E2, E3, E4]

### 2.2 Measurements carried forward

P3 recorded native macOS FFmpeg 9.0.1 returning **945/2,048** samples for positive-start 44.1→48 kHz AAC, with a **29-sample** oracle displacement. Its asymmetric audio pair produced **+1,115 samples / +1 frame**, score **0.8713582429603048**, against a zero audio-content oracle target. Docker FFmpeg 7.1.5 passed that positive-start pair but had late-window discrepancies of **3 samples at 8 kHz** and **10 at 48 kHz**. These findings do not establish the original incident's cause. [E4]

P5B changed the native positive-start result to **2,048/2,048**, zero lag, and a pair result of **0 samples / +0 frames / score 1.0**. Remaining AAC grid discrepancies included native 48→8 kHz **2 samples**, Docker 48→8 kHz **3**, and Docker 44.1→48 kHz **10**. The reported approximately **0.9335** minimum oracle correlations are retained observations, not permission to alter thresholds. [E4]

The proposed-policy holdouts retained **80 weak-dissent acceptances** and **80 localized-edit credible conflicts per exercised runtime**, with no localized-edit false acceptance. Important families used PCM-generated fixtures and a test-only evaluator. They do not prove every AAC path or deployed v5 authority. Preserve that distinction in future summaries. [E4]

### 2.3 What the completed streaming feasibility proves

At `0df9c369`, native macOS FFmpeg/ffprobe **9.0.1** and Docker/Linux arm64 FFmpeg/ffprobe **7.1.5-0+deb13u1** passed focused retained-window comparisons against each runtime's own continuous oracle. Positive-start AAC was exercised at **8 and 48 kHz**. The selected pre-end windows were sample-equal with zero measured lag. Docker's five focused cases passed with zero skips. [E2, E3]

The native three-hour traversal measured:

```text
Source:                    one synthetic 48 kHz AAC source
Output:                    48 kHz mono float32
Traversed output:          518,400,000 samples / 2,073,600,000 bytes
Retained intervals:        16 × 2 seconds
Retained PCM:              6,144,000 bytes
Decode wall time:          6.080185584010906 seconds
Configured spike timeout:  900 seconds
Pair timing:               not measured
Combined parent/child RSS: not measured
Three-hour oracle compare: not run; outside the existing oracle storage cap
```

The earlier `38293b3a` snapshot separately recorded a three-hour 8 kHz traversal with five 30-second retained intervals, **4,800,000 retained bytes**, and **6.822971500005224 seconds**. These are different runs/configurations, not a controlled performance comparison. Neither measures production comparison margins, full-pair correlation/rescoring, or a production 120-second timeout contract. [E2, E3]

Direct cancellation was exercised on native macOS and Docker. The recorded Docker case required kill escalation and completed in approximately **4.0715 seconds**, after two successive two-second waits. This proves that exercised path only, not general lifecycle safety. The spike's stdout reader uses a finally-delivered EOF sentinel without propagating a stdout-reader exception; do not copy that failure contract into production. [E2, E3]

### 2.4 Known EOF and proof gaps

The feasibility pass excluded AAC metadata-padding endpoints from its principal oracle comparisons. Separate excluded probes recorded **1,902/2,048**, **4,014/4,096**, and Docker near-end **1,341/2,048** samples. These are explicit unresolved endpoint observations, not passing complete-window cases. [E2]

Insufficient data for release acceptance: production-sized pair retention, actual pair/verification latency, combined RSS, Windows portable execution, external cancellation, reader errors, sustained stderr, timeout/uncooperative-child cases, integrated trust/cache/native behavior, and independently labeled real-media/video checks.

Keep `p3-results.json`, `p5-results.json`, `p5b-results.json`, and `p6-results.json` as historical scalar records. New production proof goes into one separate test-evidence record, `tests/fixtures/alignment_oracle/streaming-production-results.json`; it is evidence, not a second plan. Never overwrite historical measurements with prospective results.

## 3. Execution control and skill requirements

### 3.1 One controller; Codex new tasks, not subagents

The main GPT-5.6 Sol task owns decisions, communications, allowed scope, integration, staging, commits, pushes, and release handoff. Dispatch **one bounded write task at a time**. New tasks must not spawn subagents, create parallel writers, broaden scope, or perform git operations. Repository multi-agent settings are capability limits, not instructions to use them.

Each task receives:

```text
UNIT | STARTING SHA | OBJECTIVE | OWNER/WRITE BOUNDARY | DEPENDENCIES
INVARIANTS | ACCEPTANCE | VERIFICATION | EXPECTED RETURN | EFFORT BOUND | STOP CONDITIONS
```

Each returns:

```text
RESULT | FILES CHANGED | PROOF EXECUTED/NOT EXECUTED | ASSUMPTIONS | BLOCKERS
```

The controller inspects every diff and verification output, rejects unrelated edits, integrates the approved change, and records the actual commit and proof state before dispatching the next dependent write. Reuse still-current proof; rerun what a code, fixture, runtime, or integration change invalidates.

### 3.2 Model resolution for this program

Resolve `.codex/config.toml` and its referenced files at every dispatch. At the inspected head:

| Role reference | Resolved file | Configured setting |
| --- | --- | --- |
| `worker_luna` | `.codex/agents/worker-luna.toml` | `gpt-5.6-luna`, reasoning `max` |
| `worker` | `.codex/agents/worker.toml` | `gpt-5.6-sol`, reasoning `medium` |

**Explicit task-specific resolution:** the maintainer requested standalone new tasks with Luna **xhigh**, not the configured Luna subagent role. Use that explicit new-task setting and record it as an override of the subagent profile, not as an alias for `max`. Do not silently launch `worker_luna`, edit the role TOML, or assert `max == xhigh`. If the installed new-task launcher cannot honor xhigh, stop dispatch and obtain a resolved setting; do not guess.

Use Luna xhigh for settled, bounded units with direct proof. Use Sol medium only for the concrete cross-boundary/lifecycle/proof-interpretation risks identified in the unit. The controller reassesses actual risk at dispatch and records any justified change. These are this program's execution instructions, not a new repository-wide model policy. [E5]

### 3.3 Skills and Ponytail full mode

Read `AGENTS.md`, the relevant runbook sections, current architecture/CLI contracts, and `importlinter.ini`. Use `execution-plan-authoring` and the controller/checkpoint rules from `large-task-orchestration`, adapted to the explicitly requested new-task workflow. Apply `bounded-worker-execution`, `architecture-boundaries`, `runtime-integration-boundaries`, `persistence-boundaries`, `cli-contract-boundaries`, `python-test-design`, and `closeout-verification` only where each unit touches that boundary.

Load the **installed Ponytail skill in full mode** and record its actual location/revision at execution bootstrap. Ponytail is not tracked in this repository's inspected skill tree. Its upstream full-mode rules were inspected, but the implementation host's installed revision was not. If it cannot be resolved, report that missing execution prerequisite before a code-writing task; do not invent a skill file or install a plugin silently. [E5, E6]

Apply its reuse/stdlib/native-first ladder without weakening validation, cleanup, accessibility, tests explicitly required here, or the runbook. No new backend interface, processing framework, persistent cache, retry machinery, or compatibility reader. A single streaming owner is justified by the new subprocess/pipe/lifetime responsibility.

One independent read-only review is justified before activation by the **new concurrent pipe lifetime plus automatic-authority/cache boundary**. Its packet contains the integrated diff, invariants, evidence, and known risks—not implementation transcripts. No habitual planner task, per-unit reviewer, whole-repo audit, or repeated clean review is required.

## 4. Ownership and internal/public contracts

| Owner | Responsibility in the replacement |
| --- | --- |
| `services/alignment_audio.py` | Existing stream probing/selection; duration normalization; deterministic discovery/verification planning; exact sample-coordinate conversion; FFmpeg recipe; resource admission. |
| New adjacent `services/alignment_streaming.py` | One continuous FFmpeg invocation, bounded pipe readers, interval intersection collection, observed counts/end condition, typed failure, cancellation, and cleanup. No trust or cache policy. |
| `utils/subproc.py` | Existing executable resolution, including Windows portable overrides. Reuse it; do not replace unrelated subprocess callers. |
| `services/alignment_correlation.py` | Numeric correlation/refinement, bounded scoring work, estimator identity. No subprocess or presentation logic. |
| `services/alignment_consensus.py` | Staged evidence consumption, review candidate, qualification, useful overlap, temporal support, contradiction veto, and the sole automatic-authority gate. |
| `services/alignment.py` | Reuse/manual precedence, sequential comparison execution, immutable attempt construction, diagnostics/presentation/native review, final provenance. |
| `services/types.py`, `services/errors.py` | Existing evidence/results extended only with needed collection/coverage facts and typed failure categories. No class hierarchy per stage. |
| `services/alignment_diagnostics.py` | Existing bounded path-contained atomic artifact writer and original-attempt digest. |
| `services/alignment_previous_offsets.py`, `alignment_reuse_cache.py` | Accepted authority only; policy/runtime/config identity checks; no diagnostic-file reads. |
| `orchestration/phase_alignment.py`, `execution.py` | Cancellation-aware invocation and application of completed phase output; trims consume authorized values only. |
| `services/alignment_vsview.py`, `vsview/session_script.py`, `alignment_review_contract.py`, `alignment_review_panel.py` | Extend the existing native projection and exact validation together. Preserve result actions, raw-frame bounds, session identity, and whole-set confirmation. |

Keep existing import direction. The streaming owner accepts a prepared argument vector, scalar interval specifications, limits, and cancellation signal; it does not import the planning owner back. Reuse the existing `AudioAnalysisPlan`, `AudioWindowSpec`, and `AudioWindow` concepts instead of adding a parallel domain model. Small immutable interval/collection return records are permitted where the process boundary actually needs them.

The supported public surface remains CLI/config/output behavior. No new flags or tuning fields are introduced. Numeric configuration ranges remain valid; resource-incompatible requests yield explicit non-applied budget results rather than silently changing the requested window/search. Internal async signatures may change in R4; update all callers and generated API reference rather than preserving a second synchronous workflow. [E5, E7]

## 5. Collection and estimation sequence

### 5.1 Freeze selection, source identity, and planning

Reuse deterministic selected-stream ranking and explicit ordinals. Resolve once per comparison, reuse reference metadata within the run, and freeze the selected streams/channel treatment for both passes. Do not search additional streams after a weak result.

Check source path/size/mtime identity before and after staged collection. A changed source invalidates the attempt; never combine two revisions. This follows the existing performance-first source-identity contract, not a promise of content-hash identity.

Require usable selected-stream duration metadata. Do not substitute container duration or discover duration with an unbounded scan. Let `D` be the original shared selected-stream duration used for planning.

Discovery uses `a = min(requested_rate, 8000)`. If that cannot satisfy FFT admission, try 4000 Hz once when distinct. If neither fits, reject before decode. This deliberately standardizes high-requested-rate discovery at a low rate; it is a versioned estimator change, not a transparent refactor. When `a == requested_rate`, discovery supplies requested-rate evidence and no second pass occurs.

Preserve explicit window length/stride and offset-search extent. R5 installs the final default duration tiers in §8. Never drop difficult windows after observing their results to recover budget.

### 5.2 Canonical continuous sequence

For each source/rate/channel treatment, use one ordinary origin decode:

```text
selected audio -> existing channel treatment -> aresample at selected output rate
               -> final atrim end_sample=H -> mono float32 little-endian stdout
```

`H` is the largest admitted interval endpoint for that source/pass. It is a positive FFmpeg-representable integer. No input `-ss`, `-copyts` special case, per-window trim before resampling, `-fs`, timestamp compensation, or asynchronous sample stretching is used.

Use the same mono-downmix or existing best-channel treatment as the current contract. Do not combine this change with a channel-mixing revision. The only permitted trim is the final post-resample sample endpoint; production proof must show it does not alter retained prefixes relative to the untrimmed continuous oracle.

The collector counts every emitted complete float32 sample, including discarded gaps, and copies only interval intersections. A retained sample's coordinate is its ordinal in this continuous output sequence—not a timestamp-derived assertion or an independently measured video origin.

### 5.3 Sequential discovery

Collect reference intervals, then comparison intervals. There is at most one FFmpeg child at a time. Retain both sources' bounded interval stores and analyze window pairs sequentially with one numeric workspace.

Preserve every planned logical window and actual counts. Convert local lags using the actual retained interval starts. Collect bounded scalar estimates for all windows, then release all discovery PCM before requested-rate collection.

No reference PCM survives into another comparison; retain neither arrays in diagnostic records nor failure tracebacks in a per-window history. Duplicate/overlapping intervals may be stored separately within the charged bound; a deduplicating interval-cache abstraction is unnecessary.

### 5.4 Continuous requested-rate verification

When `a != R`, convert each usable coarse candidate and interval to requested-rate coordinates using exact rational arithmetic and the existing rounding convention. Freeze all verification intervals before starting their I/O. Reserve their worst-case cost when admitting discovery, not opportunistically after weak windows fail.

Preserve the existing global correction radius `h = ceil(R/a)`. Add up to `h` requested-rate samples on each comparison side when available so the admitted hypotheses can be scored without accidentally losing their intended overlap. Charge those samples. Clip physical intervals to nonnegative coordinates and known bounds; never pad unavailable edges.

Crucial coordinate invariant: a comparison halo changes the pair's local origin delta. Evaluate the same global hypotheses `[d0-h, d0+h]`, intersected with configured offset bounds. Translate those global hypotheses into local scoring coordinates; do not blindly recenter a local `±h` search around the halo-shifted origin.

Collect requested-rate reference intervals continuously, then comparison intervals continuously. Score each pair sequentially. Requested-rate score determines qualification; the discovery peak ratio retains its discovery-stage/rate label. A candidate that cannot be verified within the original admitted neighborhood remains non-authoritative. No search expansion or re-decode follows failure.

At most **two FFmpeg decodes per comparison** when rates match, **four** when verification is needed. No extra decode per window or per hypothesis.

### 5.5 Observed-EOF semantics

A successful collection has all of: stdout fully consumed through its termination condition, no partial float, no reader error, successful FFmpeg exit, and completed reader/process cleanup.

Distinguish:

| Condition | Meaning and treatment |
| --- | --- |
| Exactly `H` samples returned successfully | `planned_end_reached`; total source length is not measured. Do not call this natural EOF. |
| Successful exit with `E < H` complete samples | `observed_eof`; record `E` and clamp each interval to its intersection with `[0,E)`. Preserve original planned endpoints/counts and mark shortened/empty rows. |
| Timeout, cancellation, reader failure, invalid trailing bytes, excess output, or nonzero exit | Failed/aborted collection. Reject its PCM, even if a requested interval had already filled. Counts may survive as scalar diagnostics only. |

For each planned interval `[s,e)`, usable output is `[s,min(e,E))` at observed EOF; if `s >= E`, it is empty. Do not remove the last window as the spike did. Do not backfill from an earlier interval, pad zeros, duplicate a neighbor, or re-label a short interval complete.

Compute useful aligned overlap from actual source intersections and the candidate offset. For the signed sample correction `d = reference - comparison`, shift the comparison interval by `+d` into reference coordinates and intersect it with the reference core interval. The resulting start/end are the useful support interval. Comparison search margins and verification halos are not additional reference support. Apply the same geometry to the pre-EOF planned core/source limits for the expected denominator. Coverage is:

```text
actual useful aligned samples / candidate-available samples expected before observed EOF
```

The denominator includes ordinary geometric clipping by the candidate and original selected-stream limits, but is **not reduced merely because decode ended early**. Preserve both counts. For voting, require at least 90% coverage plus signal/quality/support gates. A clean EOF-clamped interval may qualify under those rules while remaining explicitly labeled short. An empty or lower-coverage interval cannot vote.

Do not lower the duration tier or redefine `D` after an unexpectedly early EOF to turn poor long-source coverage into a short-source success. Known natural EOF can cap subsequent physical reads, but cannot shrink the previously reserved work or evidence denominator. Actual requested-rate counts are independently observed; do not assume scaled discovery EOF is an exact requested-rate endpoint.

## 6. Production resource contract

All limits below are enforced or measured as specified; none is inferred from the spike's small retained buffers.

### 6.1 Hard admission and allocation limits

| Resource | Contract |
| --- | --- |
| Primary windows | At most 16; no auxiliary retries/checks. |
| Peak logical correlation FFT | 2,097,152 points. |
| Total logical correlation FFT work | 16,777,216 points; charge every correlation invocation. |
| Requested-rate verification PCM per pair | At most 3,000,000 samples across both sources, including halos and rounding. |
| Requested-rate verification PCM total | At most 15,000,000 samples, including halos and rounding. |
| Active comparisons / FFmpeg children / numeric workspaces | One of each. |
| Active PCM stores | One comparison's discovery store OR verification store, never both. |
| Stdout read size / queue | 65,536 bytes / at most eight chunks, retaining the spike's fixed queue capacity. |
| Stderr | Drain continuously; retain at most 65,536 bytes plus counters/truncation flag. |
| Partial float carry | At most three bytes. |
| ffprobe timeout | 15 seconds per invocation. |
| FFmpeg timeout | 120 seconds per invocation, not the spike's 900 seconds. |
| Production PCM disk use | Zero. |
| Persistent diagnostic artifact | At most 128 KiB per comparison; one initial write and at most one final review-envelope replacement. |

Kernel pipe buffers are finite platform-managed buffers, not included in the Python queue claim. Charge in-flight reader/consumer chunks separately; keep total application-owned transport buffers below 1 MiB excluding small thread/object overhead. No `communicate()` or `capture_output=True` for PCM, growing chunk list, or whole-output concatenation.

### 6.2 Retained PCM formulas

For discovery pair `i`:

```text
Fi = next_power_of_two(n_reference_i + n_comparison_i - 1)
n_reference_i + n_comparison_i <= Fi + 1
B_discovery <= 4 * sum(Fi + 1)
            <= 4 * (16,777,216 + 16)
            = 67,108,928 bytes
```

This is 64 MiB plus 64 bytes. Preallocate only admitted interval capacities; retain read-only views of initialized samples without whole-store copying. Numeric float64 conversions/FFT scratch are additional but restricted to one active pair/workspace.

Verification store bound:

```text
B_verification <= 4 * 15,000,000 = 60,000,000 bytes
```

These are alternative phase stores, not additive persistent allocations.

### 6.3 Production-sized default example

For a sufficiently long source, five 30-second windows, a 30-second maximum offset, and 8 kHz discovery:

```text
Reference per interior window:  30 * 8,000 = 240,000 samples
Comparison search interval:    (30 + 2*30) * 8,000 = 720,000 samples
Pair total:                    960,000 samples
FFT size:                      1,048,576 points
Five-window FFT total:         5,242,880 points
Conservative retained PCM:     5 * 960,000 * 4 = 19,200,000 bytes
```

Ordinary first/last boundary clipping reduces the five-window retention to **17,280,000 bytes** when both selected durations coincide. Admission uses actual integer intervals; 19.2 MB is the conservative unclipped example, not a measured RSS result.

For 48 kHz verification after 8 kHz discovery, `h=6`:

```text
One pair with comparison halo:  2*30*48,000 + 2*6 = 2,880,012 samples
Five pairs:                    14,400,060 samples
Retained PCM:                  57,600,240 bytes
Headroom under total cap:      599,940 samples
```

Six such pairs exceed the total scoring cap. A request for more qualifying windows must be rejected at planning when it cannot fit; never decode 16 full-size pairs and then discard inconvenient evidence. The spike's 16 two-second intervals do not establish this production capacity.

### 6.4 Scoring and decode work

Retain the current maximum of 65,536 sampled positions per overlap-score evaluation. Reserve initial scoring, optional local refinement, and every requested-rate correction hypothesis:

```text
Q = sum_i K_i * min(overlap_i, 65,536)
```

Under the selected rate/refinement domains, admit no more than 512 score evaluations per primary window; verify that bound against all supported rate/rounding transitions. Thus `Q <= 16*512*65,536 = 536,870,912` scored positions. Use the actual smaller reservation for normal requests. No uncharged rescoring or diagnostic FFT is allowed.

FFT-point accounting retains the current per-correlation definition; it is not a claim that a correlation performs only one physical FFT transform.

Decode work is bounded by each finite endpoint `H`, the 120-second process deadline, and at most two/four source decodes per comparison. Media duration may increase traversed bytes and latency, not retained PCM. The decode portion is at most 240/480 seconds before bounded cleanup and probes; numerical work is separately admitted. Run totals scale explicitly with the finite comparison count.

### 6.5 RSS and latency release gates

Require production-size short, 150-second, and multi-hour cases on the supported runtimes. Record absolute and incremental **simultaneously sampled** application-plus-active-FFmpeg RSS; do not add separate historical maxima and call that combined peak. Record sampling cadence, maximum sampling gap, baseline, sample count, and platform method. Target sampling at 20 ms or faster; separately label process high-water measurements.

The release acceptance ceiling is **512 MiB incremental combined sampled RSS above the pre-alignment baseline**, alongside allocation assertions and a duration-independent retained-memory plateau. This is a measured release gate, not an OS memory sandbox or proof that no sub-sampling transient existed. Unavailable RSS remains an unpassed gate.

Measure actual two-source discovery and, when needed, verification plus correlation/scoring. Report cold/warm filesystem conditions, input container/codec/channels, hardware, tool versions, and each phase's wall time. Do not multiply the single-source 6.080-second spike result into a claimed pair measurement.

Keep the 120-second production deadline. If required representative sources cannot complete within it, keep automatic authority held and return the concrete evidence for a bounded resource-contract decision. Do not silently increase timeouts, add a seek fallback, or reopen feasibility by parameter sweep.

## 7. Subprocess lifecycle and cancellation

### 7.1 Streaming owner

Use `Popen` with explicit argument arrays, resolved executable, `shell=False`, binary pipes, and `stdin=DEVNULL`. Preserve portable executable overrides and DLL/PATH isolation. Use unbuffered or equivalently bounded reads so partial chunks are observable without waiting for a full requested read.

Use two owned readers: stdout to the fixed queue; stderr to the fixed capture/counters. Reader completion and reader errors must be distinct from data/EOF. An error must reach the caller even when the data queue is full; an out-of-band first-error slot plus completion/stop events is sufficient. No generic event bus is needed.

Enter cleanup ownership immediately after process creation, including failures while starting either reader or allocating/collecting data. A reader exception is not EOF. A filled interval is not success until process exit, both readers, and payload validation succeed.

Use one monotonic execution deadline through output drainage and normal process completion. Initial OS process creation may itself be non-interruptible; do not claim a stronger wall-clock guarantee than the platform provides. [E8]

### 7.2 Deterministic stop sequence

On timeout, cancellation, reader error, or payload/consumer failure:

1. Record the first causal category and request stop; wake any queue-pressure loop.
2. Request termination once; allow at most two seconds.
3. If still running, request kill once; allow at most two further seconds to reap.
4. Close owned pipes in safe order and join both readers under one additional shared one-second deadline.
5. Release all PCM and scratch. Preserve the original failure; report cleanup failure separately.

Do not reproduce the spike's second terminate/wait cycle. Queue waits/checks are at most 100 ms. A leftover child or reader is `cleanup_failed`, never successful cleanup or usable PCM. The orchestration boundary must treat incomplete cleanup as fatal rather than continue rendering with a live worker.

On Windows, use supported process termination APIs through `Popen`; do not depend on POSIX signals, `select()` on anonymous pipes, process-group behavior, or FFmpeg reading console input. `kill()` is not a stronger independent signal than `terminate()` on Windows; validate handle release and process exit rather than expecting a POSIX return code. [E8]

The supported launcher is the directly resolved FFmpeg executable, not a shell/wrapper tree. Do not introduce a process-tree manager absent an observed need.

### 7.3 Cancellation through the actual application

Current alignment is invoked synchronously inside the async phase executor. A collector-local synthetic cancellation counter is insufficient. [E7]

R4 makes the internal service/phase invocation awaitable and runs **only the blocking audio computation** in one owned worker thread with a thread-safe cancellation event. Keep cache prompts, diagnostic publication, and existing native-review sequencing in their established execution context; do not move the whole interactive workflow into a thread.

On outer task cancellation, set the event, wait for the worker's cooperative cleanup using a shielded completion path, then re-raise the original cancellation. Cancelling an await does not by itself stop a running thread. No phase output, shared-cache write, review launch, or trim application may occur after cancellation. [E8]

Check cancellation before each process, while consuming output, between comparisons/windows, and between bounded scoring hypotheses. A native FFT already executing is allowed to reach its bounded safe boundary; do not promise instantaneous interruption or kill Python threads. Measure end-to-end cancellation at maximum admitted work.

Preserve existing service error translation and outer optional-versus-forced alignment behavior for ordinary dependency/decode failures. Cancellation must not become a warn-only alignment failure. Incomplete cleanup is explicitly fatal. A best-effort aborted diagnostic may retain scalar facts, but must never mask the original exception or launch optional review from failed PCM.

## 8. Integrity, quality, and authority gates

### 8.1 Gate I — extraction integrity

Require the canonical recipe, frozen source/stream/channel identity, admitted bounds, valid finite retained samples, truthful coordinates/counts/end status, successful process/readers, and complete cleanup. Planned endpoint completion and valid observed EOF are different successful transport outcomes. Failure invalidates that collection's PCM.

For same-runtime/source/recipe tests, retained intervals must match the independent continuous oracle's indexed samples. Do not demand bit-identical output or equal total decoded sample counts between FFmpeg versions. Do not reuse a single-source oracle tolerance derived from a pair's refinement radius.

### 8.2 Gate Q — candidate quality and support

Preserve all successful, weak, failed, short, and unattempted primary rows. Do not collapse missing evidence into zero.

**Base credible/review-qualified:** finite requested-rate score at least **0.90**, peak ratio at least **1.50**, meaningful finite signal/overlap, valid in-range candidate, and correct score-stage provenance. An explicitly unbounded peak may pass; missing/NaN does not. These are policy floors, not calibrated probabilities.

**Voting-qualified:** base credible, at least 90% useful coverage, and thresholds at least `max(base_floor, configured_value)`. Preserve any larger configured minimum-window count. A stricter user threshold must not hide a base-credible contradiction.

**Hard veto:** any base-credible primary estimate in a different applied frame bin prevents automatic acceptance, regardless of majority, configured ratio, diagnostic stability, or a favorable other window. No weighting, adjacent-bin merge, retry-to-majority, or weak-vote denominator manipulation.

Default `consensus_minimum_ratio` stays 1.0 and now means unanimity of voting-qualified windows. Zero voters have no consensus. A ratio below 1.0 cannot override the contradiction veto. Report raw, credible, voting, winning, and independent counts explicitly.

Use the existing `samples_to_frames` convention. Keep raw offsets and the observed lower median within the winning bin. Exact half-frame cases are non-authoritative even though math tests retain the existing tie conversion. For requested-rate verification, a best score at a search edge or an admitted global correction neighborhood crossing a frame-bin boundary is provisional: do not expand the search to force certainty. This is a conservative guard on the existing search domain, not a calibrated statistical error interval.

### 8.3 Temporal support

| Original shared duration `D` | Default plan | Automatic support requirement |
| --- | --- | --- |
| `D <= 30 s` | One full shared-duration interval | One qualified interval covering at least 90% of the full candidate-available shared overlap, plus any larger configured minimum. A small custom window is not full-source support merely because it filled. |
| `30 s < D < 90 s` | Two disjoint endpoint intervals, each `min(30 s, D/2)` | At least two disjoint useful intervals reaching early and late coverage, plus configured minimum. |
| `D >= 90 s` | Five distributed 30-second intervals | At least three disjoint useful intervals, with one beginning at/before `D/3` and one ending at/after `2D/3`, plus configured minimum. |

For explicit length/stride, preserve the requested shape. Extra rows may satisfy a configured count but overlapping useful intervals do not become independent. No duplicate logical interval can satisfy a larger minimum. Budget-incompatible plans reject before collection; support-incompatible evidence remains provisional/unavailable.

Find a deterministic qualifying disjoint subset using actual useful reference intervals. With at most 16 rows, a bounded subset enumeration of at most 65,536 subsets is acceptable and simpler than a new interval-graph abstraction. Endpoint requirements must hold for the selected subset, not unrelated rows outside it.

One successful window and four failures on a long source never authorize trimming. Same-bin jitter is not by itself a credible cross-frame contradiction. No drift compensation or exhaustive edit guarantee is introduced.

### 8.4 Gate A — automatic authority

Only one service-owned decision path can create `trusted_automatic` and an applied computed result. It requires Gate I, Gate Q, valid application-domain offset, current estimator/cache identity, and the release safety hold being disabled.

While held, an otherwise qualified candidate remains provisional with reason `automatic_authority_held`; other rejection reasons remain visible too. Applied frame/time fields and trusted native hints are null for every computed result. Low-quality or tied evidence stays unavailable rather than being promoted to a hint.

A provisional candidate comes from the unique largest base-review-qualified frame group; ties expose competing details but no single suggestion. Candidates never prefill confirmation inputs, move playheads, satisfy readiness, or enter trim/cache authority.

Manual confirmation is a separate validated fact. Preserve the original attempt object and canonical digest. Keep-current on an unresolved comparison is not zero confirmation.

## 9. Evidence, native projection, identity, and public behavior

### 9.1 Reuse P1/P2 and extend only required facts

Retain the existing immutable attempt/result/provenance association, diagnostic writer, pre-review presentation, and native panel. Add at most four bounded collection summaries per comparison: phase/role, output rate, requested horizon, emitted and retained counts/bytes, completion/end category, observed EOF when known, elapsed time, and cleanup/failure counters.

Window evidence must preserve original planned counts, actual discovery/verification counts, `continuous_sample_count` origin basis, actual useful reference interval, pre-EOF expected overlap, actual coverage, short/empty status, and quality/vote disposition. Derive counts from records or validate redundant serialized totals against them. No raw PCM, arbitrary exception objects, full stderr, media paths, or full commands enter the attempt.

The revised strict evidence shape requires a coordinated **diagnostic schema v2 / native metadata v3** change. Keep native **result v1**, shared-cache **v2**, and manual-override **v1**. New metadata is generated and parsed together; old metadata requires session regeneration. Old diagnostic files remain inert and are not migrated/read for authority. Both diagnostic artifacts and native projections stay within **128 KiB per comparison**.

R2 installs the schema extension before collection integration. During the brief held-v5 intermediate state, collection summaries are explicitly absent/not observed; no fake streaming facts are emitted. This is not a compatibility reader for old native sessions.

Preserve one pre-review snapshot and at most one final envelope update, the original-attempt digest, containment/symlink defenses, and ordinary write-failure warnings without changing authority. Sharing diagnostics still shares bounded labels, source identity digests, stream metadata, and timing facts.

### 9.2 Safety hold and estimator identity

Use one internal release-authority latch, initially held. It has no config, environment, CLI, GUI, or artifact override. Isolated tests may exercise both states; production users cannot bypass it.

Use distinct estimator identities at behavior-changing checkpoints, reserving these descriptive values unless the controller discovers a collision:

```text
R0: audio-authority-hold-2097152-v6
R3: continuous-origin-distributed-2097152-v7-held
R5: continuous-origin-qualified-2097152-v8-held
R7: continuous-origin-qualified-2097152-v9
```

Every later extraction/scoring/trust change or behavioral rollback gets a fresh identity. Never restore an old token to resurrect withdrawn cached authority.

Preserve the existing full source-set/config/FPS/trim/selection identity and managed-runtime alignment fingerprint. A policy bump invalidates both computed and shared human-confirmed entries under the existing key design. That conservative inconvenience is preferable to splitting cache identities here. Run-local explicit manual overrides retain precedence; newly confirmed manual results remain eligible under the current identity.

While held, no computed result or embedded computed result is cache-write eligible. Old-policy computed entries cannot bypass the hold. Keep cache schema v2 and accepted-only semantics; do not persist rejected attempts or rich traces there.

Unmanaged-runtime fingerprint limitations remain the existing documented contract: changing unmanaged FFmpeg/decoder binaries requires clearing generated caches/indexes. Do not silently claim binary attestation or add a new runtime-fingerprinting project. Acceptance evidence records actual executable version lines/package/build identities; production fields remain `not_observed` unless actually observed. [E5]

### 9.3 User-facing behavior

Normal stderr, before optional review:

```text
Audio alignment automatic application is temporarily disabled.
Audio evidence is available for manual review; no computed correction was applied.
Comparison 1: provisional +0f. Reason: automatic_authority_held.
```

Show actual failure/quality/coverage reasons when those gates also fail. After activation, show the new qualified-window policy, raw versus qualified counts, independent support, and any EOF-clamped evidence. Display zero, provisional zero, and absence distinctly.

Use existing quiet/no-color/non-TTY behavior. Actionable rejection/hold notices remain visible in quiet mode. `run --json` stdout is unchanged JSON only; notices are bounded structured stderr events. Preserve existing JSON/interactive incompatibilities, optional/forced review semantics, native whole-set actions, and source-frame validation.

Do not say every source is literally untrimmed: explicit/manual offsets and common-domain normalization may still affect geometry. The guarantee is that computed audio evidence cannot authorize an automatic correction during the hold.

Update current architecture/CLI/guide text in each behavior-changing package. Remove the existing overstated claim that five-second early handling avoids cross-version AAC grids. Do not describe proposed later behavior as already deployed.

## 10. Sequential implementation packages

### Common dispatch, proof, and commit rules

Execute in order: **R0 -> R1 -> R2 -> R3 -> R4 -> R5 -> R6 -> R7**. Only the controller edits this ledger, stages changes, or commits. A task returns its diff and observed proof; the controller audits both and commits the bounded unit. No automatic push, PR, release, signing operation, or branch reset is authorized by a package's commit instruction.

Each unit has an effort boundary of one objective, its directly affected callers/tests/docs, and repairs caused by that change. It does not include unrelated cleanup or another architecture experiment. A consequential scope/contract change returns to the controller before dependent work proceeds. Read-only investigation inside the unit and routine implementation judgment do not require a separate planning task.

Use the verification groups in §12. Distinguish `implemented/local proof complete` from `required runtime acceptance complete`. A controller-reviewed candidate commit may be needed for Windows packaging; that commit is not permission to release. Missing host proof stays in the ledger and blocks activation. A failed required test is not converted into a skip or passing gate.

Before R0, the controller installs this replacement at the existing path, verifies its preamble/references and `git diff --check`, and uses:

```text
docs(plan): replace audio alignment implementation plan
```

That is a plan-only checkpoint, not another implementation package.

### R0 — Install the automatic-authority safety hold

**Dispatch:** Luna xhigh. The outcome and authority/cache invariants are settled and directly testable.
**Dependencies:** Installed replacement plan and resolved execution prerequisites.

**Write boundary / likely files:** `services/alignment_consensus.py`, `alignment_correlation.py`, `alignment.py`, `alignment_previous_offsets.py`, `alignment_reuse_cache.py`, their service/orchestration tests, and governing CLI/guide text. Extend existing types only if necessary; do not change extraction or native wire shape here.

**Work:** Install the service-owned internal hold and R0 estimator identity. Reuse existing review-qualified candidate selection, preserving all v5 evidence while making every computed result non-applied. Cover fresh computed results, shared computed hits, and embedded computed results in human-origin cache entries. Preserve explicit/manual authority and original-attempt history. Record the safety-hold reason without pretending other failed gates passed.

**Public behavior:** Explain the hold before review; no computed correction reaches trims. Old shared identities miss, including shared human entries under the existing key design. Newly validated manual results still work and can be cached without embedding rejected computed authority.

**Acceptance/tests:** Through `align_clips_from_request` and the orchestration trim boundary, assert null applied offsets, `applied=false`, null trusted hints, and no computed cache writes for ordinary strong positives and the asymmetric positive-start case. Verify default permissive settings, one survivor/four failures, both offset signs, zero, old computed/embedded cache entries, manual zero, mixed manual/unresolved comparisons, and keep-current. Do not use only the test-only policy evaluator.

**Verification:** G1, G2, G5. Existing native fixture execution supplies regression evidence where available; no extraction change is claimed.

**Rollback:** Do not roll back to trusted v5. Repair the hold or withdraw the candidate; keep manual operation and diagnostics. Any replacement hold identity is fresh.

**Stop/replan:** Any computed/cache path still authorizes trims, a manual decision loses its attempt, or the fix requires weakening native/session validation.

**Controller commit:** `fix(alignment): hold automatic audio authority`

### R1 — Build the production continuous collector

**Dispatch:** Sol medium, justified by pipe concurrency, exception precedence, and Windows process/reader lifetime.
**Dependencies:** R0.

**Write boundary / likely files:** New `services/alignment_streaming.py`, `services/errors.py`, existing executable-resolution usage, new `tests/services/test_alignment_streaming.py`, focused real-FFmpeg integration tests, and the architecture owner description. Do not replace unrelated `run_subprocess` callers.

**Work:** Implement §§5.2, 5.5, and 7.1–7.2 with preallocated admitted interval buffers, explicit complete/EOF-clamped results, distinct reader errors, one execution deadline, and bounded termination/kill/join. Return PCM only after successful transport and cleanup. Failures expose bounded scalar facts, not a partially usable collection. The owner may be independently tested before R3 wires it into normal alignment.

**Public behavior:** No extraction switch yet; the R0 hold remains. No new configuration or dependencies.

**Acceptance/tests:** Use controlled child processes and injected stream failures to cover fragmented float bytes, EOF, overlapping/disjoint intervals, discarded gaps, excess output, source errors after filled windows, stdout-reader and stderr-reader failure, full queues, sustained stderr beyond 64 KiB, second-reader startup failure, timeout with no output, uncooperative child, and cleanup failure. Use the existing oracle fixtures against the production collector for sample-index regression. These are implementation tests, not a new feasibility program.

**Verification:** G1; focused new owner tests; G3/G4 and Windows process tests as available, with remaining platform cells explicitly pending. Assert readers and children actually terminate rather than merely checking an error return.

**Rollback:** Before integration, remove the unused collector coherently while R0 remains. After R3, withdraw dependent collection behavior under a fresh held identity; do not restore trusted seeks.

**Stop/replan:** Unbounded capture/queues, reader errors disappearing as EOF, a blocked cleanup path, required native dependency, or a need to return failed PCM as usable data.

**Controller commit:** `feat(alignment): add bounded continuous audio collector`

### R2 — Extend retained evidence and the existing native contract

**Dispatch:** Luna xhigh. The existing owners and coordinated schema transition are explicit; proof is contract-focused.
**Dependencies:** R0–R1; collector scalar return facts are frozen.

**Write boundary / likely files:** `services/types.py`, `alignment_diagnostics.py`, `alignment.py`, `alignment_vsview.py`; `vsview/session_script.py`, `alignment_review_contract.py`, `alignment_review_panel.py`; matching service/native/package contract tests and authority docs.

**Work:** Add only the collection, endpoint, expected/actual useful-overlap, and vote facts in §9.1. Coordinate diagnostic v2/native metadata v3; retain result v1/cache v2/manual v1. Reuse the existing panel, buttons, markers, original-attempt digest, bounded serializer, and atomic writer. During held-v5 operation, new collection facts are explicitly unobserved rather than fabricated.

**Public behavior:** Existing accepted/provisional/unavailable and manual/history presentation remains. New sessions require metadata v3; old sessions are regenerated. Details explain observed EOF and held authority without becoming an authority input.

**Acceptance/tests:** Exact field/topology validation, nonfinite/boolean/bounds rejection, maximum 16-window/four-collection serialization under 128 KiB, old metadata refusal, no candidate autofill/readiness effect, manual-zero digest preservation, mixed-source results, original-attempt retention, disk-full/containment failures, and artifact tampering unable to change application. Native result v1 remains unchanged.

**Verification:** G1, G2, G5, G6; offscreen native contract tests now, physical Windows acceptance in R6. Update existing packaging/verifier fixtures only where they embed the changed metadata contract.

**Rollback:** Revert generator/parser/panel/fixture changes together and regenerate sessions. Leave historical diagnostics inert; no compatibility reader or inferred trust upgrade.

**Stop/replan:** Producer/parser disagreement, serialization overflow, service-policy imports in the panel, changed result actions, or original-attempt mutation.

**Controller commit:** `feat(alignment): retain continuous collection evidence`

### R3 — Integrate staged collection, EOF handling, and production budgets

**Dispatch:** Sol medium, justified by rate/origin translation, verification halos, lifetime transitions, and the production/test extraction boundary.
**Dependencies:** R0–R2.

**Write boundary / likely files:** `alignment_audio.py`, `alignment.py`, `alignment_consensus.py`, narrowly necessary scoring signatures in `alignment_correlation.py`; distributed/planner/FFmpeg/service tests and the continuous integration fixtures. Update architecture/CLI/guide descriptions and generated API reference.

**Work:** Implement §5's low-rate discovery, sequential reference/comparison stores, scalar candidate staging, complete discovery-store release, and conditional continuous requested-rate verification. Enforce §6's exact worst-case admission, halo accounting, and scoring work. Implement observed EOF without dropping endpoint rows or shrinking evidence denominators/duration tiers. Install the R3 held identity.

Remove independent seeking from the production path. Migrate active regression tests to the new owner/entrypoint and retire obsolete recipe-only experimental runners when they no longer have a live target. Preserve all P3/P5/P6 scalar evidence and immutable historical source links. Do not keep a second production extractor or copy an old seek backend into tests simply to keep obsolete assertions green. Preserve the underlying positive, negative, and boundary regressions.

**Public behavior:** Continuous extraction supplies diagnostics/manual candidates; automatic authority remains held. Oversized requests reject before decoding. No extra stream search, opportunistic retry, or cross-comparison PCM reuse.

**Acceptance/tests:** Actual 30-second windows with 30-second margins; 4/8/48 kHz and noninteger conversion ratios; both signs; asymmetric starts; exact global hypotheses after halos; direct-rate operation; EOF-clamped/empty endpoints; 90% coverage boundary; source identity change between passes; maximum windows/scoring/FFT limits; one active child/workspace; noncoexisting phase stores. Verify known-zero/nonzero candidates through the service without changing correction radius.

**Verification:** G1–G5, including a new production-facing `tests/integration/test_alignment_continuous_pipeline.py`. Same-runtime oracle comparisons exercise the final endpoint-limited recipe, not only the spike primitive. Old expected failures do not count as proof of the replacement.

**Rollback:** Return to held diagnostic/manual operation with a fresh identity. A coherent withdrawal may remove R3 and dependent work, but cannot reactivate old computed cache entries or trusted seeks.

**Stop/replan:** Any sample-origin change is unexplained, expected coverage depends on padded/fabricated samples, actual reservations exceed caps, or a second full decode per individual window becomes necessary.

**Controller commit:** `refactor(alignment): collect distributed windows continuously`

### R4 — Propagate real application cancellation

**Dispatch:** Sol medium, justified by async-to-thread ownership and cancellation across computation, phase output, and subsequent review/cache work.
**Dependencies:** R0–R3.

**Write boundary / likely files:** `services/alignment.py`, cancellation parameters in the collector/numeric loop, `orchestration/phase_alignment.py`, `execution.py`, service/phase call sites and test support, typed cleanup failure, and directly governing docs.

**Work:** Implement §7.3. Make internal alignment invocation awaitable, offloading only blocking audio computation to one owned thread. Propagate a cancellation event and wait for cleanup before re-raising cancellation. Keep interactive/cache/presentation owners in their established context. Add incomplete-cleanup failure to the phase's fatal handling; ordinary service failure retains its existing outer optional/forced treatment.

**Public behavior:** Cancelling alignment stops further audio work and cannot apply partial phase output, publish a new cache entry, or launch review afterward. No new cancel flag, signal-handler framework, or synchronous compatibility entrypoint.

**Acceptance/tests:** Cancel the actual application task during a discarded gap, queue pressure, requested-rate collection, and bounded scoring; verify no next comparison, phase-output application, review launch, or cache write. Test repeated cancellation while cleanup is awaited, worker error plus cancellation, Ctrl+C behavior, and Windows reader/process release. Measure completion at maximum admitted numeric work; a running native FFT is not represented as instantly interruptible.

**Verification:** G1–G5; focused service and orchestration cancellation tests must execute the real ownership path, not just `cancel_after_samples` in the spike. Update all affected async callers/tests and API reference.

**Rollback:** Keep authority held and revert the caller/worker/cancellation seam coherently. Do not leave an abandoned background worker or revert only one side of an async signature.

**Stop/replan:** The event loop still cannot request cancellation during audio work, cleanup is unawaited, GUI/manual work must be moved into the computation thread, or partial output escapes after cancellation.

**Controller commit:** `fix(alignment): propagate cancellation through audio collection`

### R5 — Implement qualified trust and independent temporal support

**Dispatch:** Luna xhigh. The policy, owner, populations, thresholds, and expected outcomes are settled in §8.
**Dependencies:** R0–R4.

**Write boundary / likely files:** `alignment_consensus.py`, default-tier planning in `alignment_audio.py`, estimator identity in `alignment_correlation.py`, existing evidence projections as required, policy/planner/service tests, and CLI/guide/architecture text.

**Work:** Implement all three gates, the duration-tier plan, base-credible veto, voting populations, pre-EOF coverage, actual useful support intervals, frame-boundary guard, and unique review candidate. Keep the safety hold enabled and install the R5 held identity. Do not tune floors, add weights, merge frame bins, or broaden correction search.

**Public behavior:** Explain raw versus qualified evidence, shortages, EOF clamping, and credible contradictions. Document the changed meaning of ratio/minimum-window settings. Users' stronger requirements are never reduced. Held results remain provisional/unavailable even when the future authority policy would pass.

**Acceptance/tests:** Four strong windows plus finite weak dissent can satisfy the prospective policy only with independent support; credible shifted evidence vetoes even at ratio 0.8 or with a stricter user threshold excluding it from voting. One survivor/four failures stays provisional. Cover silence, repeated/unrelated audio, wrong streams, exact and neighboring frame boundaries, short/medium/long/custom shapes, overlapping support, explicit minimum five, coverage just below/at 90%, and all failed reasons. Test both internal hold states in isolation without exposing a runtime bypass.

**Verification:** G1–G5. Run labeled controls through the actual production service/policy, not only `evaluate_predeclared_policy`. R6 extends the production codec/runtime/real-media proof.

**Rollback:** Restore held authority under a fresh identity, retaining evidence. Do not restore permissive v5 acceptance or a withdrawn cache identity.

**Stop/replan:** Any credible contradiction is accepted, a failed positive requires tuning against holdouts, actual useful support cannot be established, or the policy needs a different product contract.

**Controller commit:** `fix(alignment): qualify distributed audio evidence`

### R6 — Complete production runtime, resource, and real-media acceptance

**Dispatch:** Sol medium, justified by interpreting cross-runtime measurements, simultaneous RSS, failure precedence, and real-media labels.
**Dependencies:** R0–R5; R5 policy and collector frozen for measurement.

**Write boundary / likely files:** Production integration tests, `tests/integration/test_alignment_continuous_pipeline.py`, a focused `test_alignment_streaming_resources.py`, existing Windows/runtime verifier fixtures where necessary, scalar `tests/fixtures/alignment_oracle/streaming-production-results.json`, and this ledger/current docs. No estimator tuning is bundled into an evidence task.

**Work:** Complete §11 using production-sized collection, actual two-source discovery and verification, the 120-second process deadline, retained-allocation assertions, simultaneous RSS, and actual application cancellation. Add only test-side platform measurement plumbing; use standard-library/platform facilities rather than a production monitoring dependency. Preserve old scalar files unchanged.

Reuse historical fixture recipes and still-current evidence where applicable. Do not rerun the spike to choose the architecture. Required new executions prove the production implementation, endpoint behavior, policy, full-pair resource use, and previously untested hosts/failures.

Exercise prospective automatic authority through isolated tests of the existing internal latch; the shipped default remains held. Run the one bounded independent read-only review of integrated pipe lifetime and authority/cache paths described in §3.3. The controller adjudicates findings; material fixes return to their bounded owner with a fresh proof record, not an unbounded review loop.

**Acceptance:** Every mandatory matrix cell has an observed result or remains explicitly blocking. Record native/Docker/Windows executable identities, source/bundle SHA, platform/hardware, fixture identity/settings, counts, end status, frame/quality/authority outcomes, phase/pair timings, retained bytes, sampled RSS methodology/results, and cancellation/cleanup. Physical Windows visible review completes the outstanding P2 requirement on the updated metadata contract. Include at least real constant-zero, known signed-offset, and mismatched mix/cut/track pairs with separated visual checks.

**Verification:** G1–G6 plus all §11 measurements. A successful fixture import, skipped long test, offscreen panel, or unchanged historical JSON is not the missing native proof. Candidate commits may precede packaging measurements; record exactly which SHA each execution tested.

**Rollback:** Keep authority held; correct invalid test/instrumentation evidence without erasing the original record. Do not reinterpret failed production proof as successful feasibility.

**Stop/replan:** Any negative gains authority, production-sized allocations/RSS/deadlines fail, required endpoint or cancellation behavior differs across supported runtimes, real-media labels contradict the assumed frame relationship, or a required host is unavailable. Missing proof blocks activation, not the already settled architecture by itself.

**Controller commit:** `test(alignment): verify continuous alignment release gates`

### R7 — Activate only the verified integrated estimator

**Dispatch:** Luna xhigh for the bounded latch/identity/documentation change after the controller verifies R6 acceptance.
**Dependencies:** R0–R6 accepted; consequential review findings resolved; no missing required runtime/real-media/resource/physical-Windows gate.

**Write boundary / likely files:** The service-owned authority latch, estimator identity, explicit activation/cache/trim tests, release/CLI/guide/architecture text, and this ledger. No extraction, thresholds, planner, or scoring changes.

**Work:** Disable the hold, install the R7 fresh identity, and document the exact delivered support and residual sampling/A/V assumptions. Remove temporary hold-specific user copy from the active path, but keep regression proof and the conservative rollback route.

**Acceptance/tests:** Run unpatched production-default positive and negative service/CLI tests. Verify actual trusted zero/nonzero, provisional/unavailable outcomes, trim inputs, manual preservation, old held-policy cache misses, and current accepted-cache reuse. Rebuild the candidate package from committed source and obtain matching-SHA runtime/visible-native smoke for the changed authority presentation. Do not publish while candidate proof is pending.

**Verification:** G1–G6, reusing unchanged measurements only with an explicit relevance explanation. The unpatched default authority and its cache/UI/trim integration require fresh proof; they are not satisfied by R6's isolated latch tests.

**Rollback:** If activation proof fails, immediately restore the hold in a controller-owned follow-up commit with another fresh estimator identity; do not reuse any earlier token or release the failed candidate. Preserve manual overrides and inert history.

**Stop/replan:** Any default differs from isolated proof, a stale cache bypasses the gates, packaged source differs from tested source, or activation would require an algorithm change. Return that change to its bounded owner and repeat invalidated acceptance.

**Controller commit:** `feat(alignment): enable verified continuous audio alignment`

## 11. Mandatory production verification matrix

This is a covering matrix with explicit required intersections, not a claim that every theoretical Cartesian combination has been exercised. Record cells, recipes, and results. Codec/rate rows require both sources to be compared to their own oracle; pair-authority rows require the actual service and trim boundary.

| Surface | Required cells and assertions |
| --- | --- |
| Codec/rates | PCM and AAC, 44.1/48 kHz inputs, 4/8/48 kHz outputs; direct and discovery/verification paths; asymmetric input rates/codecs; both channel strategies and representative multichannel sources. Verify sample coordinates/counts and expected frame/qualification, not cross-build byte equality. |
| Origins and positions | Origin; former five-second boundary ± one sample; early/middle/late; final windows included. Zero/positive selected-stream starts, negative PTS, common timestamp shifts, asymmetric starts, and independently labeled A/V-origin cases. No padding or automatic timestamp compensation. |
| EOF integrity | Complete horizon, clean early EOF, the excluded AAC endpoint families, empty last interval, counts above/below 90% coverage, and metadata duration excess. Keep planned rows/denominators and original duration tier. Failed process/reader output cannot use the clean-EOF path. |
| Frame decisions | Both signs, clean zero, known signed offsets; 24 and 24000/1001 FPS; exact/neighboring half-frame values; halo/global-coordinate conversion; best hypothesis at verification edge. No boundary merge or wider search. |
| Duration/support | Subsecond, 3, 30, 31, 65, 90, 150–180 seconds; two and three hours. Short full overlap, medium disjoint endpoints, long three-region support, custom overlapping shapes, explicit counts, one survivor/four failures. |
| Safety controls | Preserve the 80 weak-dissent and 80 localized-edit recipe families plus insertion/deletion/drift controls, all positions/signs/FPS. Extend representative controls to AAC/resampling, not only PCM. Silence, quiet independent noise, unrelated audio, tones, repeats, wrong/explicit streams, stricter user thresholds. No false automatic acceptance in the labeled matrix. |
| Sampling limitations | Include a local edit inside an analyzed interval and one entirely between intervals. Observed credible conflict must veto; an unseen edit documents the sampling limitation rather than forcing an impossible exhaustive guarantee. |
| Production resources | Five actual 30-second windows with ±30-second comparison margins; 48 kHz verification plus halos; maximum admitted custom FFT/scoring/window plans and rejected neighbors. Assert allocation formulas, no simultaneous phase stores, zero PCM disk, and one active child/workspace. |
| RSS/latency | Native macOS, canonical Docker/Linux, and Windows portable. Short and multi-hour pairs; real large containers/storage, not only audio-only synthetic files. Simultaneous parent/child sampling, absolute and incremental RSS, plateau, actual discovery/verification/numeric/pair time, exact 120-second production deadline. |
| Failure/lifetime | Spawn failure, reader startup/failure, partial float, nonfinite retained data, excess output, source replacement, nonzero exit after filled windows, sustained stderr, full queue, no-output timeout, ignored termination, cleanup failure, repeated cancellation. Observe child/reader/handle release on each supported platform. |
| Application cancellation | Cancel the real outer task/CLI during discarded gaps, verification, and admitted scoring. No review/cache write/phase application/next comparison afterward. Preserve cancellation and original failure precedence; incomplete cleanup is fatal. |
| Persistence/authority | Fresh/cached/embedded computed results under hold and activation; manual zero; mixed source sets; keep-current; old identities; malicious diagnostics; metadata mismatch. Only eligible computed or validated manual authority reaches trims. |
| Native UI/release | Physical Windows, packaged candidate SHA, metadata v3/result v1: accepted/provisional/unavailable and mixed states, details/EOF labels, no prefill, marker bounds, keyboard/focus, both manual bases, close-without-save, keep-current, malformed-result refusal, digest preservation. Offscreen/hosted proof is separate. |
| Real media | At least constant zero, signed known offset, and mismatched mix/cut/track pairs. Check early/middle/late and disputed intervals visually; record selected streams/runtime/settings privately with share-safe scalar findings. Original incident reproduction is optional and must not be fabricated. |

Controlled tests require correct expected decisions, not only “no exception.” Preserve any failing record before repairs. Unsupported/missing codecs or unavailable platforms are explicit blocked cells, not silently reduced matrix scope.

## 12. Verification command groups

Run commands from the repository root. These are instructions, not executions performed while authoring. Use exact candidate checkout and locked dependencies; inspect test skips. New test paths below become commands only after their owning package creates them.

### G1 — Canonical full Python verification

```bash
uv sync --group dev --frozen
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
git diff --check
```

### G2 — Focused service, orchestration, CLI, and native-contract proof

```bash
uv run --no-sync pytest -q tests/services -k alignment
uv run --no-sync pytest -q tests/orchestration -k alignment
uv run --no-sync pytest -q tests/cli tests/test_cli_contract_docs.py
uv run --no-sync pytest -q tests/vsview
# From R1 onward:
uv run --no-sync pytest -q tests/services/test_alignment_streaming.py
```

Load the locked VSView extra when required: `uv sync --extra vsview --group dev --frozen`. A mocked missing native runtime does not prove native media behavior.

### G3 — Production native FFmpeg integration and measurements

```bash
ffmpeg -version
ffprobe -version
uv run --no-sync pytest -q tests/integration -k alignment -rsx
# From R3 onward:
uv run --no-sync pytest -q tests/integration/test_alignment_continuous_pipeline.py -rsx
# From R6 onward; this explicit file must execute its production long/resource cases:
FRAME_COMPARE_CONTINUOUS_ALIGNMENT_RESOURCES=1 uv run --no-sync pytest -q tests/integration/test_alignment_streaming_resources.py -rsx
```

Mark the expensive resource tests `integration` and `slow`, and require the test-only opt-in `FRAME_COMPARE_CONTINUOUS_ALIGNMENT_RESOURCES=1`; no production code reads it. The explicit command above enables those cases. Every mandatory selected resource case must execute; a missing measurement capability or platform prerequisite blocks acceptance rather than becoming a passed skip. Do not use the spike's 900-second override for production acceptance.

Version commands must refer to the executables actually used. In a portable environment, resolve the existing executable overrides and record those binaries' version lines; unrelated PATH versions are insufficient.

### G4 — Canonical Docker/runtime verification

```bash
bash tools/verify_docker_integration.sh
```

Select the production pipeline through the existing verifier option, then run the expensive resource tests explicitly in the same verified image:

```bash
bash tools/verify_docker_integration.sh --pytest-path tests/integration/test_alignment_continuous_pipeline.py
docker compose run --rm --no-deps \
  -e FRAME_COMPARE_CONTINUOUS_ALIGNMENT_RESOURCES=1 \
  --entrypoint python frame-compare-test \
  -m pytest -q tests/integration/test_alignment_streaming_resources.py -rsx
```

The targeted verifier invocation may satisfy the canonical gate above when its full runtime/application checks run; do not repeat an identical clean gate solely for its default spelling. Use `--no-build` only when the tested image/source/runtime identity is already established as current. Confirm the resource command uses that same candidate image and no stale bind mount. Record Debian package identity, FFmpeg/ffprobe versions, architecture, image/build context, candidate SHA, and output. Docker does not prove native Windows or visible VSView.

### G5 — Documentation, public contracts, and generated reference

```bash
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync pytest -q tests/test_cli_contract_docs.py
git diff --check
```

When signatures change, regenerate with `uv run --no-sync python scripts/generate_api_docs.py` and inspect the generated diff. For the strict site build, use the runbook's locked docs environment:

```bash
uv sync --group dev --group docs --locked
uv run --no-sync zensical build --clean --strict
```

Do not leave new behavior described only in this internal plan; update the current architecture, CLI contract, and audio guide in the package that changes it.

### G6 — Distribution and Windows portable/visible acceptance

Use the runbook's Python distribution verification for new module inclusion and changed installed/internal entrypoints:

```bash
distribution_dir=$(mktemp -d "${TMPDIR:-/tmp}/frame-compare-dist.XXXXXX")
uv build --out-dir "$distribution_dir"
uv venv "$distribution_dir/venv" --python 3.13
"$distribution_dir/venv/bin/python" scripts/verify_distribution.py "$distribution_dir"
uv pip install --python "$distribution_dir/venv/bin/python" "$distribution_dir"/*.whl
"$distribution_dir/venv/bin/frame-compare" version
"$distribution_dir/venv/bin/frame-compare" --help
```

On Windows:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/validate_update_public_key.ps1 -PublicKeyPath tools/windows_portable/update_public_key.xml
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir dist/frame-compare-portable-win-x64 -CacheDir .portable_cache
dist/frame-compare-portable-win-x64/frame-compare.ps1 doctor --json
```

Extend the existing build-owned native Python proof to exercise the production collector and service with generated fixtures, reusing its interpreter, executable overrides, and runtime setup. Do not assume pytest is installed in a clean bundle or add test dependencies to the release artifact. Run the larger failure matrix in the test environment against the packaged media executables, and separately measure the actual bundled application through its existing launcher. Record which layer each proof covers. Capture visible native review on the physical Windows desktop through Frame Compare-generated sessions, not hand-authored metadata.

The portable builder packages application source/wheel metadata from committed HEAD. A clean old-HEAD bundle cannot validate uncommitted source edits. Candidate commits are controller-owned checkpoints; publication remains blocked until matching-SHA proof passes. Hosted package/offscreen success cannot replace physical Windows acceptance. No unrelated updater/signing/native-runtime refresh is part of this workstream. [E5]

## 13. Evidence recording, release posture, and execution ledger

### 13.1 Evidence handling

Keep `p3-results.json`, `p5-results.json`, `p5b-results.json`, and `p6-results.json` as historical evidence. Do not overwrite their dispositions with production outcomes. New production scalar evidence records its own purpose, schema, tested source SHA, runtime identity, exact executed commands, fixtures/settings, results, and explicit limitations.

Store no real media, PCM, absolute private paths, credentials, full stderr, or packet dumps in tracked scalar evidence. Retain fixture recipe identities and safe hashes/labels as appropriate. Measurements of retained bytes, sampled combined RSS, process high-water memory, and whole-pair latency are distinct fields. Null/unavailable is not zero or passed.

No test count alone establishes a population error rate. An evaluator result is not the final service result; a source-only oracle match is not an A/V mapping proof; single-source traversal is not pair timing; a collector-local cancellation test is not outer application cancellation.

### 13.2 Immediate and final release posture

Until R7 passes, automatic computed authority remains held. A diagnostics/manual-only release may proceed only with its own complete applicable Python/native/physical-Windows acceptance and clear hold disclosure. It must not claim the estimator redesign or original incident is fixed.

Do not ship either rejected P5 extraction experiment, trusted v5 as a rollback, a PCM-only policy branch, an unbounded whole-track path, or an unverified timeout/RSS claim. Required missing evidence keeps the hold; it does not justify bypass flags or another automatic fallback.

After activation, publish the actual qualified policy, cache invalidation, session regeneration, EOF handling, resource ceilings, and finite-sampling/A/V limitations. Manual confirmation remains separate from computed evidence. Record rollback as a new held identity, never an old-policy resurrection.

### 13.3 Controller-maintained ledger

| Unit | Initial state | Integrated SHA | Proof and outstanding acceptance |
| --- | --- | --- | --- |
| Plan replacement | Authored; installation pending | — | No implementation/test execution claimed by authoring. |
| R0 safety hold | Not started | — | Hold is absent at inspected head. |
| R1 streaming owner | Not started | — | Production failure/lifecycle and Windows proof required. |
| R2 evidence/native extension | Not started | — | Reuse P1/P2; extend exact contract and complete visible acceptance. |
| R3 staged extraction | Not started | — | Production endpoints/margins/rate coordinates/budgets required. |
| R4 application cancellation | Not started | — | Outer-task cancellation and cleanup required. |
| R5 trust policy | Not started | — | Actual policy and service proof; authority still held. |
| R6 production acceptance | Not started | — | Runtime, RSS, real-media, Windows, and bounded independent review required. |
| R7 activation | Blocked by R0–R6 acceptance | — | Unpatched defaults and packaged candidate proof required. |

For each checkpoint record task model/effort actually used, owner disposition, files, commit, commands/results/skips, evidence locations, unresolved risks, and the next permitted unit. Do not mark a package accepted from intended tests. When the workstream and release handoff are complete, change this file to `Status: Historical` in the same pass; otherwise keep the unresolved gate explicit.

## 14. Source record

Repository references are pinned to the inspected pushed state unless explicitly historical. Source inspection is separate from recorded measurements; proposed contracts/budgets in this replacement are design decisions, not claims that current production already implements them.

- **E1 — Pushed lineage and preserved plan:** [inspected head](https://github.com/TJZine/frame-compare/commit/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a), [initial collector feasibility](https://github.com/TJZine/frame-compare/commit/38293b3a2d5dc4b06411f12e4aaf1ce324435921), and [the pre-replacement active plan, including historical execution records](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/docs/plans/2026-09-14-audio-alignment-trust-and-diagnostics.md).
- **E2 — Completed feasibility scalar evidence:** [p6-results.json](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/tests/fixtures/alignment_oracle/p6-results.json). These are prior measured results, not production acceptance.
- **E3 — Feasibility implementation and oracle:** [test_alignment_continuous_streaming_collector.py](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/tests/integration/test_alignment_continuous_streaming_collector.py) and [alignment_oracle.py](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/tests/integration/alignment_oracle.py).
- **E4 — Preserved failed-extraction and policy evidence:** [P3](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/tests/fixtures/alignment_oracle/p3-results.json), [P5A](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/tests/fixtures/alignment_oracle/p5-results.json), and [P5B](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/tests/fixtures/alignment_oracle/p5b-results.json); historical execution details remain in E1.
- **E5 — Workflow and current contract:** [AGENTS.md](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/AGENTS.md), [runbook](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/docs/ENGINEERING_RUNBOOK.md), [architecture](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/docs/current-architecture.md), [CLI contract](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/docs/current-cli-contract.md), [.codex/config.toml](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/.codex/config.toml), [Luna profile](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/.codex/agents/worker-luna.toml), [Sol profile](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/.codex/agents/worker.toml), and [repo-local skills](https://github.com/TJZine/frame-compare/tree/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/.agents/skills).
- **E6 — Ponytail:** [upstream full-mode skill inspected for this plan](https://github.com/DietrichGebert/ponytail/blob/main/skills/ponytail/SKILL.md), Git blob `02c0712c86277d49d18a77da3a2b825657bf02d1`. This does not identify the implementation host's installed version; resolve that at bootstrap.
- **E7 — Production owners inspected:** [alignment services](https://github.com/TJZine/frame-compare/tree/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/src/frame_compare/services), [phase_alignment.py](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/src/frame_compare/orchestration/phase_alignment.py), [execution.py](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/src/frame_compare/orchestration/execution.py), and [subproc.py](https://github.com/TJZine/frame-compare/blob/0df9c369a9abf19de3cce87de95ccd50ef7ecf1a/src/frame_compare/utils/subproc.py).
- **E8 — Python primary documentation:** [Python 3.13 subprocess](https://docs.python.org/3.13/library/subprocess.html) and [Python 3.13 asyncio task/thread/cancellation APIs](https://docs.python.org/3.13/library/asyncio-task.html). Platform and cancellation facts support the lifecycle contract; they are not evidence that the new implementation has been tested.
